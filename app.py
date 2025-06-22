"""
Dehumidifier Assistant - Clean, Simple Implementation
A conversational assistant for dehumidifier sizing and selection.
"""

import os
import uuid
import json
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

# Load system prompt
SYSTEM_PROMPT = """You are a knowledgeable dehumidifier sizing and selection assistant. Help users choose the right dehumidifier for their specific needs by asking about:
- Space type (room, garage, basement, pool area, etc.)
- Square meters or dimensions
- Special conditions (temperature, existing humidity issues, etc.)

Provide specific product recommendations with model numbers, capacity ratings, and installation requirements. Be concise but thorough."""

try:
    with open("prompt_template.txt", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()
    logger.info("Loaded custom system prompt")
except FileNotFoundError:
    logger.info("Using default system prompt")

def get_demo_response(user_input: str) -> str:
    """Provide demo responses when no API key is available"""
    user_lower = user_input.lower()
    
    if any(word in user_lower for word in ['garage', 'workshop']):
        return """**Demo Response**

For a garage/workshop, I'd typically recommend:

• **Small garages (up to 30m²)**: Desiccant dehumidifier, 10-12L/day capacity
• **Medium garages (30-60m²)**: Refrigerant dehumidifier, 20-25L/day capacity  
• **Large workshops (60m²+)**: Commercial unit, 30L+ capacity

Key considerations:
- Insulation level
- Ventilation 
- Temperature range
- Power supply (240V standard vs 415V three-phase)

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

def call_openai_api(messages: list) -> str:
    """Call OpenAI API with proper error handling"""
    if DEMO_MODE:
        return get_demo_response(messages[-1]['content'])
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using cheaper model for cost efficiency
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}")
        if "invalid_api_key" in str(e):
            return get_demo_response(messages[-1]['content'])
        return "I'm experiencing technical difficulties. Please try again in a moment."

def log_conversation(session_id: str, user_input: str, assistant_response: str):
    """Log conversations for analysis"""
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'session_id': session_id,
        'user_input': user_input[:200],  # Truncate for privacy
        'assistant_response': assistant_response[:300],
        'demo_mode': DEMO_MODE
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
        
        # Return updated conversation history (client will store it)
        history.extend([
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": assistant_response}
        ])
        
        # Log conversation
        log_conversation(session_id, user_input, assistant_response)
        
        logger.info(f"Processed message for session {session_id}")
        return {
            'response': assistant_response,
            'history': history
        }
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return Response("Technical difficulties. Please try again.", status=500)

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
        'demo_mode': DEMO_MODE
    }

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