import os
import uuid
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from flask import (
    Flask, request, render_template, session,
    stream_with_context, Response, make_response, g
)
from flask_session import Session
import redis
import structlog

from model_client import stream_completion
from utils import (
    validate_input, is_relevant_question, optimize_context,
    estimate_tokens, get_session_key, safe_json_loads, safe_json_dumps,
    DEHUMIDIFIER_KEYWORDS
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecret")

# Redis session configuration
redis_client = None
if os.getenv("REDIS_URL"):
    try:
        redis_client = redis.from_url(os.getenv("REDIS_URL"))
        # Test the connection
        redis_client.ping()
        app.config['SESSION_TYPE'] = 'redis'
        app.config['SESSION_REDIS'] = redis_client
        app.config['SESSION_PERMANENT'] = False
        app.config['SESSION_USE_SIGNER'] = True
        app.config['SESSION_KEY_PREFIX'] = 'dehum:'
        app.config['SESSION_COOKIE_HTTPONLY'] = True
        # Set secure cookies in production (when HTTPS is available)
        app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production' or bool(os.getenv('REDIS_URL'))
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
        Session(app)
        logger.info("Redis session storage configured successfully")
    except Exception as e:
        logger.error("Failed to connect to Redis, falling back to filesystem sessions", error=str(e))
        redis_client = None

if not redis_client:
    # Fallback to filesystem sessions for local development
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_COOKIE_SECURE'] = False
    Session(app)
    logger.warning("Using filesystem sessions - not recommended for production")

# Load system prompt
prompt_path = "prompt_template_test.txt"
if os.path.exists(prompt_path):
    with open(prompt_path, "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()
    logger.info("System prompt loaded", prompt_file=prompt_path)
else:
    SYSTEM_PROMPT = "You are a dehumidifier assistant."
    logger.warning("System prompt file not found, using default")

# Configuration
MAX_DAILY_QUESTIONS = 20
MAX_DAILY_TOKENS = 50000  # Rough daily token limit for cost control

def get_or_create_session_id():
    """Get existing session ID or create new one"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        session['created_at'] = datetime.utcnow().isoformat()
        logger.info("New session created", session_id=session['session_id'])
    return session['session_id']

def get_daily_usage(session_id: str) -> dict:
    """Get daily usage stats for a session"""
    today = datetime.utcnow().strftime('%Y-%m-%d')
    
    if redis_client:
        try:
            usage_key = f"usage:{session_id}:{today}"
            usage_data = redis_client.get(usage_key)
            if usage_data:
                return safe_json_loads(usage_data, {'questions': 0, 'tokens': 0, 'date': today})
            else:
                return {'questions': 0, 'tokens': 0, 'date': today}
        except Exception as e:
            logger.error("Failed to get daily usage from Redis", error=str(e))
            return {'questions': 0, 'tokens': 0, 'date': today}
    else:
        # Fallback to filesystem for local development
        try:
            import os
            usage_file = f"flask_session/usage_{session_id}_{today}.json"
            if os.path.exists(usage_file):
                with open(usage_file, 'r', encoding='utf-8') as f:
                    return safe_json_loads(f.read(), {'questions': 0, 'tokens': 0, 'date': today})
            return {'questions': 0, 'tokens': 0, 'date': today}
        except Exception as e:
            logger.error("Failed to get daily usage from filesystem", error=str(e))
            return {'questions': 0, 'tokens': 0, 'date': today}

def update_daily_usage(session_id: str, tokens_used: int):
    """Update daily usage stats"""
    today = datetime.utcnow().strftime('%Y-%m-%d')
    
    if redis_client:
        try:
            usage_key = f"usage:{session_id}:{today}"
            current_usage = get_daily_usage(session_id)
            current_usage['questions'] += 1
            current_usage['tokens'] += tokens_used
            current_usage['date'] = today
            
            # Store with 25-hour expiry (slightly more than 1 day)
            redis_client.setex(usage_key, timedelta(hours=25), safe_json_dumps(current_usage))
            
            logger.info("Usage updated", 
                       session_id=session_id,
                       daily_questions=current_usage['questions'],
                       daily_tokens=current_usage['tokens'])
        except Exception as e:
            logger.error("Failed to update daily usage to Redis", error=str(e))
    else:
        # Fallback to filesystem for local development
        try:
            import os
            current_usage = get_daily_usage(session_id)
            current_usage['questions'] += 1
            current_usage['tokens'] += tokens_used
            current_usage['date'] = today
            
            os.makedirs("flask_session", exist_ok=True)
            usage_file = f"flask_session/usage_{session_id}_{today}.json"
            with open(usage_file, 'w', encoding='utf-8') as f:
                f.write(safe_json_dumps(current_usage))
            
            logger.info("Usage updated (filesystem)", 
                       session_id=session_id,
                       daily_questions=current_usage['questions'],
                       daily_tokens=current_usage['tokens'])
        except Exception as e:
            logger.error("Failed to update daily usage to filesystem", error=str(e))

def get_conversation_history(session_id: str) -> list:
    """Get conversation history from Redis or filesystem"""
    if redis_client:
        try:
            history_key = f"history:{session_id}"
            history_data = redis_client.get(history_key)
            return safe_json_loads(history_data, [])
        except Exception as e:
            logger.error("Failed to get conversation history from Redis", error=str(e))
            return []
    else:
        # Fallback to filesystem for local development
        try:
            import os
            history_file = f"flask_session/history_{session_id}.json"
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    return safe_json_loads(f.read(), [])
            return []
        except Exception as e:
            logger.error("Failed to get conversation history from filesystem", error=str(e))
            return []

def save_conversation_history(session_id: str, history: list):
    """Save conversation history to Redis or filesystem"""
    if redis_client:
        try:
            history_key = f"history:{session_id}"
            # Store with 7-day expiry
            redis_client.setex(history_key, timedelta(days=7), safe_json_dumps(history))
        except Exception as e:
            logger.error("Failed to save conversation history to Redis", error=str(e))
    else:
        # Fallback to filesystem for local development
        try:
            import os
            os.makedirs("flask_session", exist_ok=True)
            history_file = f"flask_session/history_{session_id}.json"
            with open(history_file, 'w', encoding='utf-8') as f:
                f.write(safe_json_dumps(history))
        except Exception as e:
            logger.error("Failed to save conversation history to filesystem", error=str(e))

@app.route("/")
def index():
    session_id = get_or_create_session_id()
    
    # Get conversation history
    history = get_conversation_history(session_id)
    if not history:
        # Initialize with welcome message
        history = [{
            "role": "assistant", 
            "content": "Hello! I'm your Dehumidifier Assistant. Ask me anything about sizing or model selection."
        }]
        save_conversation_history(session_id, history)
    
    logger.info("Index page loaded", session_id=session_id, history_length=len(history))
    return render_template("index.html")

@app.route("/api/assistant", methods=["POST"])
def assistant():
    try:
        session_id = get_or_create_session_id()
        
        # Get user input
        data = request.get_json() or {}
        user_input = data.get("input", "").strip()
        
        # Validate input
        is_valid, validated_input = validate_input(user_input)
        if not is_valid:
            logger.warning("Invalid input", session_id=session_id, error=validated_input)
            return Response(validated_input, mimetype="text/plain"), 400
        
        # Get conversation history first
        history = get_conversation_history(session_id)
        
        # Check if question is relevant (more permissive if we have conversation history)
        has_conversation_context = len(history) > 1  # More than just welcome message
        if not is_relevant_question(validated_input, conversation_context=has_conversation_context):
            logger.warning("Question filtered as irrelevant", 
                         session_id=session_id, 
                         question=validated_input, 
                         has_context=has_conversation_context,
                         history_length=len(history))
            return Response(
                f"I'm specialized in dehumidifier sizing and selection. Your question '{validated_input}' seems off-topic. Please ask about humidity control, room sizing, or specific dehumidifier models.",
                mimetype="text/plain"
            ), 400
        
        # Check daily limits
        daily_usage = get_daily_usage(session_id)
        if daily_usage['questions'] >= MAX_DAILY_QUESTIONS:
            logger.warning("Daily question limit exceeded", session_id=session_id)
            return Response(
                "You've reached the daily limit of 20 questions. Please try again tomorrow.",
                mimetype="text/plain"
            ), 429
        
        if daily_usage['tokens'] >= MAX_DAILY_TOKENS:
            logger.warning("Daily token limit exceeded", session_id=session_id)
            return Response(
                "Daily usage limit reached. Please try again tomorrow.",
                mimetype="text/plain"
            ), 429
        
        # Add user message to history
        history.append({"role": "user", "content": validated_input})
        
        # Optimize context for API call
        optimized_history = optimize_context(history)
        
        # Build messages for API
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + optimized_history
        
        # Estimate tokens for cost tracking
        estimated_tokens = estimate_tokens(messages)
        
        logger.info("Processing question",
                   session_id=session_id,
                   question=validated_input[:100],  # First 100 chars for debugging
                   question_length=len(validated_input),
                   history_length=len(history),
                   optimized_length=len(optimized_history),
                   estimated_tokens=estimated_tokens,
                   has_conversation_context=has_conversation_context)
        
        # Stream response and collect for history
        def generate_and_store():
            reply_accum = ""
            try:
                for delta in stream_completion(messages):
                    reply_accum += delta
                    yield delta
                
                # Add assistant response to history
                history.append({"role": "assistant", "content": reply_accum})
                save_conversation_history(session_id, history)
                
                # Update usage stats
                actual_tokens = estimate_tokens([{"role": "assistant", "content": reply_accum}])
                update_daily_usage(session_id, estimated_tokens + actual_tokens)
                
                logger.info("Question processed successfully",
                           session_id=session_id,
                           response_length=len(reply_accum),
                           tokens_used=estimated_tokens + actual_tokens)
                
            except Exception as e:
                logger.error("Error during streaming", session_id=session_id, error=str(e))
                yield "I apologize, but I'm experiencing technical difficulties. Please try again in a moment."
        
        return Response(
            stream_with_context(generate_and_store()),
            mimetype="text/plain"
        )
        
    except Exception as e:
        logger.error("Unexpected error in assistant endpoint", error=str(e))
        return Response(
            "An unexpected error occurred. Please try again.",
            mimetype="text/plain"
        ), 500

@app.route("/api/health")
def health():
    """Health check endpoint"""
    try:
        redis_status = "not_configured"
        redis_error = None
        
        # Test Redis connection
        if os.getenv("REDIS_URL"):
            try:
                if redis_client:
                    redis_client.ping()
                    redis_status = "connected"
                else:
                    redis_status = "failed_to_initialize"
            except Exception as e:
                redis_status = "connection_failed"
                redis_error = str(e)
        
        # Check session configuration
        session_type = app.config.get('SESSION_TYPE', 'unknown')
        session_secure = app.config.get('SESSION_COOKIE_SECURE', False)
        
        return {
            "status": "healthy",
            "redis": {
                "status": redis_status,
                "error": redis_error,
                "url_configured": bool(os.getenv("REDIS_URL"))
            },
            "session": {
                "type": session_type,
                "secure_cookies": session_secure
            },
            "environment": {
                "flask_env": os.getenv("FLASK_ENV", "not_set"),
                "has_redis_url": bool(os.getenv("REDIS_URL"))
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return {"status": "unhealthy", "error": str(e)}, 500

@app.route("/api/stats")
def stats():
    """Basic usage stats (for debugging)"""
    try:
        session_id = get_or_create_session_id()
        daily_usage = get_daily_usage(session_id)
        history = get_conversation_history(session_id)
        
        return {
            "session_id": session_id,
            "daily_questions": daily_usage['questions'],
            "daily_tokens": daily_usage['tokens'],
            "conversation_length": len(history),
            "questions_remaining": MAX_DAILY_QUESTIONS - daily_usage['questions']
        }
    except Exception as e:
        logger.error("Stats endpoint failed", error=str(e))
        return {"error": str(e)}, 500

@app.route("/api/debug/relevance", methods=["POST"])
def debug_relevance():
    """Debug endpoint to test relevance filtering"""
    try:
        data = request.get_json() or {}
        test_question = data.get("question", "")
        
        session_id = get_or_create_session_id()
        history = get_conversation_history(session_id)
        has_context = len(history) > 1
        
        is_relevant = is_relevant_question(test_question, conversation_context=has_context)
        
        return {
            "question": test_question,
            "is_relevant": is_relevant,
            "has_conversation_context": has_context,
            "history_length": len(history),
            "keywords_found": [kw for kw in DEHUMIDIFIER_KEYWORDS if kw in test_question.lower()],
            "debug_info": f"Question '{test_question}' was {'ACCEPTED' if is_relevant else 'REJECTED'}"
        }
    except Exception as e:
        logger.error("Debug relevance endpoint failed", error=str(e))
        return {"error": str(e)}, 500

@app.route("/api/debug/history")
def debug_history():
    """Debug endpoint to see conversation history and context optimization"""
    try:
        session_id = get_or_create_session_id()
        history = get_conversation_history(session_id)
        optimized_history = optimize_context(history)
        
        return {
            "session_id": session_id,
            "full_history": history,
            "full_history_length": len(history),
            "optimized_history": optimized_history,
            "optimized_history_length": len(optimized_history),
            "optimization_stats": {
                "messages_removed": len(history) - len(optimized_history),
                "reduction_percent": round((1 - len(optimized_history) / max(len(history), 1)) * 100, 1)
            }
        }
    except Exception as e:
        logger.error("Debug history endpoint failed", error=str(e))
        return {"error": str(e)}, 500

if __name__ == "__main__":
    # Development server only
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), debug=True)
