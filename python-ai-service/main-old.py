"""
Dehumidifier Assistant AI Service
FastAPI service with OpenAI integration and function calling
"""

from datetime import datetime
import logging
import os
import json

import litellm
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Configure LiteLLM to be minimal (no logging, no proxy features)
os.environ["LITELLM_LOG"] = "ERROR"
os.environ["LITELLM_LOG_LEVEL"] = "ERROR"
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.responses import JSONResponse

# Import our custom modules
from ai_agent import DehumidifierAgent
from models import ChatRequest, ChatResponse, StreamingChatResponse
from config import config
from logging.handlers import RotatingFileHandler
from tools import DehumidifierTools
from engine import LLMEngine
from tool_executor import ToolExecutor
from session_store import WordPressSessionStore

# Load environment variables from .env file
load_dotenv()

# Configure logging for the entire application
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('ai_service.log', maxBytes=1000000, backupCount=5),
        logging.StreamHandler() # Also print to console
    ]
)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="Dehumidifier Assistant AI Service",
    description="AI-powered dehumidifier sizing and recommendation service",
    version="1.0.0",
)

# Configure CORS for WordPress integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the AI agent with required dependencies
def create_ai_agent():
    """Create and configure the AI agent with all required dependencies"""
    wp_api_key = os.getenv("WP_API_KEY")
    if not wp_api_key:
        raise ValueError("WP_API_KEY environment variable is required")
    
    # Create tools instance
    tools = DehumidifierTools()
    
    # Create unified engine (engine owns params + API calling)
    engine = LLMEngine(model=config.DEFAULT_MODEL)
    
    # Create tool executor
    tool_executor = ToolExecutor(tools)
    
    # Create session store
    session_store = WordPressSessionStore(config.WORDPRESS_URL, wp_api_key)
    
    # Create and return agent
    return DehumidifierAgent(
        tools=tools,
        engine=engine, 
        tool_executor=tool_executor,
        session_store=session_store
    )

agent = create_ai_agent()


def check_api_key(authorization: str = Header(None)):
    expected_key = os.getenv("API_KEY")
    if expected_key:  # Only enforce if key is set
        if authorization is None or authorization != f"Bearer {expected_key}":
            raise HTTPException(status_code=403, detail="Invalid API key")
    return authorization


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "dehumidifier-ai-service",
        "version": "1.0.0",
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, auth: str = Depends(check_api_key)):
    """
    Main chat endpoint for dehumidifier assistance
    """
    try:
        logger.info(f"Received chat request for session: {request.session_id}")

        # Process the chat request through our AI agent
        response = await agent.process_chat(request)

        logger.info(f"Generated response for session: {request.session_id}")
        return response

    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, auth: str = Depends(check_api_key)):
    """
    Streaming chat endpoint for dehumidifier assistance
    """
    try:
        logger.info(f"Received streaming chat request for session: {request.session_id}")

        async def generate_stream():
            try:
                # Process the chat request through our AI agent (streaming version)
                async for response_part in agent.process_chat_streaming(request):
                    # Convert to JSON and yield
                    response_json = response_part.model_dump_json()
                    yield f"data: {response_json}\n\n"
                
                # Send final end marker
                yield "data: [DONE]\n\n"
                
            except Exception as e:
                logger.error(f"Error in streaming chat: {str(e)}")
                error_response = StreamingChatResponse(
                    message=f"I apologize, but I'm experiencing technical difficulties. Please try again in a moment.",
                    session_id=request.session_id,
                    timestamp=datetime.now(),
                    is_final=True,
                    metadata={"error": str(e)}
                )
                yield f"data: {error_response.model_dump_json()}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    except Exception as e:
        logger.error(f"Error setting up streaming chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """
    Get session information and conversation history
    """
    try:
        session_info = agent.get_session_info(session_id)
        return session_info
    except Exception as e:
        logger.error(f"Error getting session info: {str(e)}")
        raise HTTPException(status_code=404, detail="Session not found")


@app.post("/session/{session_id}/clear")
async def clear_session(session_id: str):
    """
    Clear session conversation history and reset state
    """
    try:
        agent.clear_session(session_id)
        return {"message": "Session cleared successfully", "session_id": session_id}
    except Exception as e:
        logger.error(f"Error clearing session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to clear session")

@app.post("/session/{session_id}/abort")
async def abort_session_streaming(session_id: str):
    """
    Force abort any stuck streaming operations for a session
    """
    try:
        session = agent.sessions.get(session_id)
        if session:
            # Simply clear the session as the streaming state tracking was removed
            agent.clear_session(session_id)
            return {
                "message": "Session cleared successfully", 
                "session_id": session_id,
                "was_streaming": True
            }
        else:
            return {
                "message": "Session not found", 
                "session_id": session_id,
                "was_streaming": False
            }
    except Exception as e:
        logger.error(f"Error aborting session streaming: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to abort session streaming")


@app.get("/diagnostic")
async def diagnostic_check():
    """
    Basic diagnostic endpoint for service health check.
    """
    try:
        # Basic diagnostic information
        diagnostic_info = {
            "agent_status": agent.get_health_status(),
            "models_available": agent.get_available_models(),
            "active_sessions": len(agent.sessions),
            "tools_available": len(agent.tools.get_available_tools()) if hasattr(agent.tools, 'get_available_tools') else 'unknown'
        }
        return {
            "status": "diagnostic_complete",
            "timestamp": datetime.now().isoformat(),
            **diagnostic_info
        }
    except Exception as e:
        logger.error(f"Error in diagnostic check: {str(e)}")
        return {
            "status": "diagnostic_failed",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


@app.get("/health")
async def health_check():
    """
    Detailed health check endpoint
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "agent_status": agent.get_health_status(),
        "models_available": agent.get_available_models(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.SERVICE_HOST, port=config.SERVICE_PORT)
