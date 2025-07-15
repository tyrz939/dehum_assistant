"""
Dehumidifier Assistant AI Service
FastAPI service with OpenAI integration and function calling
"""

from datetime import datetime
import logging
import os
import json

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.responses import JSONResponse

# Import our custom modules
from ai_agent import DehumidifierAgent
from models import ChatRequest, ChatResponse, StreamingChatResponse
from config import config
from logging.handlers import RotatingFileHandler

# Load environment variables from .env file
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('ai_service.log', maxBytes=1000000, backupCount=5)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

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

# Initialize the AI agent
agent = DehumidifierAgent()


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
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
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
    Clear conversation history for a session
    """
    try:
        agent.clear_session(session_id)
        return {"status": "success", "message": "Session cleared"}
    except Exception as e:
        logger.error(f"Error clearing session: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


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
