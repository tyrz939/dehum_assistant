"""
Dehumidifier Assistant - Clean, Simple Implementation
A conversational assistant for dehumidifier sizing and selection.
"""

import os
import uuid
import json
import re
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, request, render_template, session, Response

# Optional CORS support for WordPress integration
try:
    from flask_cors import CORS
    CORS_AVAILABLE = True
except ImportError:
    CORS_AVAILABLE = False
    print("Flask-CORS not installed. Install with: pip install Flask-CORS==4.0.0")

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
MAX_INPUT_LENGTH = int(os.getenv("MAX_INPUT_LENGTH", 400))
MAX_CONVERSATION_LENGTH = int(os.getenv("MAX_CONVERSATION_LENGTH", 20))
DEMO_MODE = not OPENAI_API_KEY or OPENAI_API_KEY in ["test_key", "your_api_key_here"]

# Initialize Flask app
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['SESSION_PERMANENT'] = False

# Add CORS support for WordPress integration (if available)
if CORS_AVAILABLE:
    CORS(app, origins=[
        'http://localhost:3000',  # Development
        'https://dehumsaust.com.au',  # Replace with actual WordPress domain
        'https://www.dehumsaust.com.au',  # Replace with actual WordPress domain
        '*'  # Allow all origins for now - restrict later for security
    ])
else:
    # Manual CORS headers for basic support
    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response

# Setup logging
os.makedirs('conversation_logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'conversation_logs/app_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load product catalog and system prompt
PRODUCT_CATALOG = {}
SYSTEM_PROMPT = ""

def load_product_catalog():
    """Load product catalog from JSON file"""
    global PRODUCT_CATALOG
    try:
        with open("product_db.json", "r", encoding="utf-8") as f:
            PRODUCT_CATALOG = json.load(f)
        logger.info(f"Loaded product catalog v{PRODUCT_CATALOG.get('catalog_version', 'unknown')}")
        return True
    except FileNotFoundError:
        logger.error("product_db.json not found - using empty catalog")
        PRODUCT_CATALOG = {"catalog_version": "none", "products": [], "sizing_rules": {}}
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in product_db.json: {e}")
        PRODUCT_CATALOG = {"catalog_version": "error", "products": [], "sizing_rules": {}}
        return False

def load_system_prompt():
    """Load system prompt with product catalog injection"""
    global SYSTEM_PROMPT
    
    # Try new modular prompt first
    try:
        with open("prompt_template_new.txt", "r", encoding="utf-8") as f:
            prompt_template = f.read()
        logger.info("Loaded new modular system prompt")
    except FileNotFoundError:
        # Fallback to original prompt
        try:
            with open("prompt_template.txt", "r", encoding="utf-8") as f:
                prompt_template = f.read()
            logger.info("Loaded original system prompt (fallback)")
        except FileNotFoundError:
            # Default fallback prompt
            prompt_template = """You are a knowledgeable dehumidifier sizing and selection assistant. Help users choose the right dehumidifier for their specific needs by asking about:
- Space type (room, garage, basement, pool area, etc.)
- Square meters or dimensions
- Special conditions (temperature, existing humidity issues, etc.)

Provide specific product recommendations with model numbers, capacity ratings, and installation requirements. Be concise but thorough."""
            logger.info("Using default system prompt")
    
    # Inject product catalog into prompt
    catalog_info = f"""

PRODUCT CATALOG (Version: {PRODUCT_CATALOG.get('catalog_version', 'unknown')}):
{json.dumps(PRODUCT_CATALOG, indent=2)}

Use this catalog data for all recommendations. Never invent products not in this catalog.
"""
    
    SYSTEM_PROMPT = prompt_template + catalog_info
    logger.info(f"System prompt ready with {len(PRODUCT_CATALOG.get('products', []))} products")

# Load resources on startup
load_product_catalog()
load_system_prompt()

def get_demo_response(user_input: str) -> str:
    """Provide demo responses when no API key is available"""
    user_lower = user_input.lower()
    
    # Try to extract JSON from demo responses for consistency
    if any(word in user_lower for word in ['garage', 'workshop']):
        demo_json = {
            "session_id": "demo",
            "input_used": {"space_m2": 40, "application": "garage"},
            "recommendation": {"sku": "IDHR60", "name": "FAIRLAND IDHR60", "coverage_ratio": 3.0, "price_aud": 3900},
            "alternatives": [{"sku": "SP500C_PRO", "name": "SUNTEC SP500C PRO", "coverage_ratio": 2.7, "price_aud": 2999}],
            "warnings": [],
            "catalog_version": "2024-01-15",
            "audit_note": "Demo mode response"
        }
        return f"""```json
{json.dumps(demo_json, indent=2)}
```

For a 40m² garage, I recommend the **FAIRLAND IDHR60** inverter unit ($3,900). It provides efficient coverage with a 3.0x safety ratio and includes energy-saving inverter technology.

*Note: This is a demo. Set OPENAI_API_KEY for real AI responses.*"""
    
    elif any(word in user_lower for word in ['basement', 'cellar']):
        return """**Demo Response**

For basements/cellars:

• **Typical recommendation**: 20-30L/day refrigerant dehumidifier
• **Key features needed**: Low-temperature operation, continuous drainage
• **Installation**: Wall-mounted units save floor space

*Note: This is a demo. Set OPENAI_API_KEY for real AI responses.*"""
    
    elif any(word in user_lower for word in ['size', 'need', 'recommend']):
        return """**Demo Response**

To recommend the right dehumidifier, I need:

1. **Space type** - Room, garage, pool area, etc.?
2. **Size** - Square meters or dimensions?
3. **Conditions** - Any specific humidity problems?

*Note: This is a demo. Set OPENAI_API_KEY for real AI responses.*"""
    
    else:
        return """**Demo Response**

I help with dehumidifier sizing and selection. Try asking about:
- "What size dehumidifier for a 40m² garage?"
- "Best dehumidifier for basement?"
- "Pool area humidity control"

*Note: This is a demo. Set OPENAI_API_KEY for real AI responses.*"""

def call_openai_api(messages: list, retry_count: int = 0) -> str:
    """Call OpenAI API with proper error handling and retry logic"""
    if DEMO_MODE:
        return get_demo_response(messages[-1]['content'])
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using cheaper model for cost efficiency
            messages=messages,
            max_tokens=800,  # Increased for JSON + summary
            temperature=0.3,  # Lower temperature for more consistent JSON
            response_format={"type": "text"}  # Ensure text response that can include JSON
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        error_str = str(e).lower()
        logger.error(f"OpenAI API error (attempt {retry_count + 1}): {str(e)}")
        
        # Handle specific error types
        if "invalid_api_key" in error_str:
            logger.warning("Invalid API key, falling back to demo mode")
            return get_demo_response(messages[-1]['content'])
        
        elif any(keyword in error_str for keyword in ['rate_limit', 'quota', 'billing']):
            return "⚠️ API quota exceeded. Please try again later or contact support."
        
        elif any(keyword in error_str for keyword in ['timeout', 'connection', 'network']):
            return "🔌 Connection timeout. Please check your internet and try again."
        
        elif any(keyword in error_str for keyword in ['server_error', '500', '502', '503']):
            return "🔧 OpenAI servers are experiencing issues. Please try again in a few minutes."
        
        elif "content_filter" in error_str or "policy" in error_str:
            return "⚠️ Your message was flagged by content filters. Please rephrase and try again."
        
        else:
            # Generic error with helpful message
            return f"❌ Technical error occurred. Please try the retry button. (Error: {str(e)[:50]}...)"

def parse_ai_response(response_text: str) -> tuple:
    """
    Parse AI response to separate structured JSON data from customer-facing text.
    Returns: (structured_data_dict, clean_customer_response_string)
    """
    # Extract JSON block for internal use
    json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
    
    if json_match:
        try:
            # Parse the JSON data
            structured_data = json.loads(json_match.group(1))
            
            # Remove JSON block from customer response, including extra newlines
            clean_response = re.sub(r'```json\n.*?\n```\n*', '', response_text, flags=re.DOTALL)
            clean_response = clean_response.strip()
            
            return structured_data, clean_response
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from AI response: {e}")
            return None, response_text
    
    # No JSON found, return original response
    return None, response_text

def log_conversation(session_id: str, user_input: str, assistant_response: str, structured_data: dict = None):
    """Log conversations with optional structured data for analysis"""
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'session_id': session_id,
        'user_input': user_input[:200],  # Truncate for privacy
        'assistant_response': assistant_response[:300],
        'structured_data': structured_data,  # Now passed explicitly
        'demo_mode': DEMO_MODE,
        'catalog_version': PRODUCT_CATALOG.get('catalog_version', 'unknown')
    }
    
    log_file = f'conversation_logs/conversations_{datetime.now().strftime("%Y%m%d")}.log'
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry) + '\n')

def get_session_id():
    """Get or create session ID"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        session['daily_message_count'] = 0
        session['last_message_date'] = datetime.now().strftime('%Y-%m-%d')
        logger.info(f"New session created: {session['session_id']}")
    return session['session_id']

def check_and_update_daily_limit():
    """Check daily message limit and reset if new day"""
    today = datetime.now().strftime('%Y-%m-%d')
    last_date = session.get('last_message_date', today)
    
    # Reset count if new day
    if last_date != today:
        session['daily_message_count'] = 0
        session['last_message_date'] = today
        logger.info(f"Daily message count reset for session {session.get('session_id')}")
    
    # Check if limit exceeded
    current_count = session.get('daily_message_count', 0)
    if current_count >= MAX_CONVERSATION_LENGTH:
        return False, current_count
    
    # Increment count
    session['daily_message_count'] = current_count + 1
    return True, current_count + 1

@app.route('/')
def index():
    """Main chat interface"""
    get_session_id()  # Initialize session
    return render_template('index.html', demo_mode=DEMO_MODE, max_input_length=MAX_INPUT_LENGTH)

@app.route('/popup')
def popup():
    """WordPress popup integration version"""
    get_session_id()  # Initialize session
    
    # Get referrer for analytics
    referrer = request.headers.get('Referer', '')
    
    return render_template('popup.html', 
                         demo_mode=DEMO_MODE,
                         referrer=referrer,
                         popup_mode=True,
                         max_input_length=MAX_INPUT_LENGTH)

@app.route('/api/assistant', methods=['POST'])
def assistant():
    """Process chat messages"""
    try:
        session_id = get_session_id()
        
        # Get and validate input
        data = request.get_json() or {}
        user_input = data.get('input', '').strip()
        
        if not user_input:
            return Response("Please enter a message.", status=400)
        
        if len(user_input) > MAX_INPUT_LENGTH:
            return Response(f"Message too long. Please keep under {MAX_INPUT_LENGTH} characters.", status=400)
        
        # Check daily message limit
        can_send, message_count = check_and_update_daily_limit()
        if not can_send:
            return Response(f"Daily message limit reached ({MAX_CONVERSATION_LENGTH} messages). Limit resets tomorrow.", status=429)
        
        # Get conversation history from request (client-side storage)
        history = data.get('history', [])
        
        # Build messages for API
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history[-10:])  # Last 10 messages for context
        messages.append({"role": "user", "content": user_input})
        
        # Get response
        assistant_response = call_openai_api(messages)
        
        # Parse response to separate structured data from customer text
        structured_data, clean_response = parse_ai_response(assistant_response)
        
        # Store clean response in conversation history (client will store it)
        history.extend([
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": clean_response}
        ])
        
        # Log conversation with structured data for internal use
        log_conversation(session_id, user_input, clean_response, structured_data)
        
        # Log structured data separately if present (for future calc functions)
        if structured_data:
            logger.info(f"Structured data for session {session_id}: {json.dumps(structured_data, indent=2)}")
        
        logger.info(f"Processed message for session {session_id}")
        return {
            'response': clean_response,
            'history': history,
            'success': True
        }
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'error_type': 'server_error',
            'message': 'Technical difficulties. Please use the retry button.'
        }, 500

@app.route('/api/retry', methods=['POST'])
def retry_message():
    """Retry last message with exponential backoff"""
    try:
        session_id = get_session_id()
        
        # Get and validate input
        data = request.get_json() or {}
        user_input = data.get('input', '').strip()
        retry_count = data.get('retry_count', 0)
        
        if not user_input:
            return {'success': False, 'message': 'No message to retry'}, 400
        
        if retry_count > 3:  # Max 3 retries
            return {
                'success': False, 
                'message': 'Maximum retry attempts reached. Please try again later.',
                'error_type': 'max_retries'
            }, 429
        
        # Check daily message limit (retries count towards limit)
        can_send, message_count = check_and_update_daily_limit()
        if not can_send:
            return {
                'success': False,
                'message': f"Daily message limit reached ({MAX_CONVERSATION_LENGTH} messages). Limit resets tomorrow.",
                'error_type': 'rate_limit'
            }, 429
        
        # Get conversation history from request
        history = data.get('history', [])
        
        # Build messages for API
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history[-10:])  # Last 10 messages for context
        messages.append({"role": "user", "content": user_input})
        
        # Add exponential backoff delay for retries
        if retry_count > 0:
            import time
            delay = min(2 ** retry_count, 8)  # Cap at 8 seconds
            logger.info(f"Retry {retry_count + 1} with {delay}s delay")
            time.sleep(delay)
        
        # Get response with retry count
        assistant_response = call_openai_api(messages, retry_count)
        
        # Parse response to separate structured data from customer text
        structured_data, clean_response = parse_ai_response(assistant_response)
        
        # Store clean response in conversation history
        history.extend([
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": clean_response}
        ])
        
        # Log conversation with retry info
        log_conversation(session_id, f"[RETRY {retry_count + 1}] {user_input}", clean_response, structured_data)
        
        # Log structured data separately if present
        if structured_data:
            logger.info(f"Structured data for session {session_id} (retry {retry_count + 1}): {json.dumps(structured_data, indent=2)}")
        
        logger.info(f"Retry {retry_count + 1} successful for session {session_id}")
        return {
            'response': clean_response,
            'history': history,
            'success': True,
            'retry_count': retry_count + 1
        }
        
    except Exception as e:
        logger.error(f"Error processing retry: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'error_type': 'server_error',
            'message': 'Retry failed. Please try again later.'
        }, 500

@app.route('/api/health')
def health():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'demo_mode': DEMO_MODE,
        'timestamp': datetime.utcnow().isoformat()
    }

@app.route('/api/stats')
def stats():
    """Simple stats endpoint"""
    if os.getenv('FLASK_ENV') == 'production':
        return {'error': 'Not available in production'}, 404
    
    session_id = get_session_id()
    daily_count = session.get('daily_message_count', 0)
    last_date = session.get('last_message_date', 'N/A')
    
    return {
        'session_id': session_id,
        'conversation_length': 'Stored client-side',
        'daily_message_count': daily_count,
        'daily_limit': MAX_CONVERSATION_LENGTH,
        'last_message_date': last_date,
        'demo_mode': DEMO_MODE,
        'catalog_version': PRODUCT_CATALOG.get('catalog_version', 'unknown'),
        'product_count': len(PRODUCT_CATALOG.get('products', []))
    }

@app.route('/api/reload-catalog', methods=['POST'])
def reload_catalog():
    """Reload product catalog (development only)"""
    if os.getenv('FLASK_ENV') == 'production':
        return {'error': 'Not available in production'}, 404
    
    try:
        success = load_product_catalog()
        if success:
            load_system_prompt()  # Reload prompt with new catalog
            return {
                'status': 'success',
                'catalog_version': PRODUCT_CATALOG.get('catalog_version', 'unknown'),
                'product_count': len(PRODUCT_CATALOG.get('products', []))
            }
        else:
            return {'status': 'error', 'message': 'Failed to load catalog'}, 500
    except Exception as e:
        logger.error(f"Catalog reload error: {str(e)}")
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/api/clear', methods=['POST'])
def clear_conversation():
    """Clear conversation history (but keep daily message count)"""
    session_id = get_session_id()
    daily_count = session.get('daily_message_count', 0)
    logger.info(f"Conversation cleared for session {session_id} (daily count: {daily_count})")
    
    return {
        'status': 'cleared',
        'session_id': session_id,
        'message': 'Conversation history cleared (client-side)',
        'daily_message_count': daily_count,
        'note': 'Daily message limit not reset'
    }

@app.route('/api/history')
def get_history():
    """Legacy endpoint - history now stored client-side"""
    session_id = get_session_id()
    
    return {
        'session_id': session_id,
        'history': [],
        'length': 0,
        'note': 'History stored client-side in localStorage'
    }

if __name__ == '__main__':
    logger.info(f"Starting Dehumidifier Assistant (Demo Mode: {DEMO_MODE})")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=True) 