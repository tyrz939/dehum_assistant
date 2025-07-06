"""
Dehumidifier Assistant AI Service
FastAPI service with OpenAI integration and function calling
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
from datetime import datetime
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import our custom modules
from ai_agent import DehumidifierAgent
from models import ChatMessage, ChatRequest, ChatResponse, SessionInfo
from config import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Dehumidifier Assistant AI Service",
    description="AI-powered dehumidifier sizing and recommendation service",
    version="1.0.0"
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

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy", "service": "dehumidifier-ai-service", "version": "1.0.0"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
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
        "models_available": agent.get_available_models()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.SERVICE_HOST, port=config.SERVICE_PORT) 