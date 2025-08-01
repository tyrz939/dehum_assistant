"""
Pydantic models for the Dehumidifier Assistant AI Service
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

class MessageRole(str, Enum):
    """Message roles for conversation"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool" # Add TOOL role

class ChatMessage(BaseModel):
    """Individual chat message"""
    role: MessageRole
    content: str
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    # Add optional fields for tool calls
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str = Field(..., description="User message", max_length=1200)
    session_id: str = Field(..., description="Session identifier")
    user_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    message: str
    session_id: str
    timestamp: datetime
    function_calls: Optional[List[Dict[str, Any]]] = None
    recommendations: Optional[List[Dict[str, Any]]] = None
    conversation_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class StreamingChatResponse(BaseModel):
    """Streaming response model for chat endpoint"""
    message: str
    session_id: str
    timestamp: datetime
    is_final: bool = False
    is_thinking: bool = False
    is_streaming_chunk: bool = False  # Indicates real-time text chunks from OpenAI
    function_calls: Optional[List[Dict[str, Any]]] = None
    recommendations: Optional[List[Dict[str, Any]]] = None
    conversation_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class SessionInfo(BaseModel):
    """Session information model"""
    session_id: str
    conversation_history: List[ChatMessage]
    created_at: datetime
    last_activity: datetime
    message_count: int
    metadata: Optional[Dict[str, Any]] = None
    tool_cache: Dict[str, Any] = Field(default_factory=dict)  # per-session cache of tool results
    # Add streaming state tracking
    is_streaming: bool = False
    streaming_start_time: Optional[datetime] = None
    streaming_task_id: Optional[str] = None

@dataclass
class Product:
    """Product information"""
    sku: str
    name: str
    type: str  # wall_mount, ducted, portable
    capacity_lpd: float
    price_aud: Optional[float] = None
    url: Optional[str] = None
    pool_safe: bool = False
    performance_factor: float = 1.0
    max_room_m2: Optional[float] = None
    max_room_m3: Optional[float] = None

class ProductRecommendation(BaseModel):
    """Product recommendation model"""
    sku: str
    name: str
    type: str
    series: str
    technology: str
    max_room_m2: Optional[float] = None
    max_room_m3: Optional[float] = None
    pool_safe: bool = False
    price_aud: Optional[float] = None
    operating_temp_range: Optional[str] = None
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    reasoning: str

class SizingCalculation(BaseModel):
    """Sizing calculation result"""
    room_area_m2: Optional[float] = None
    room_volume_m3: Optional[float] = None
    pool_area_m2: Optional[float] = None
    room_height_m: Optional[float] = None
    humidity_level: Optional[str] = None
    temperature_range: Optional[str] = None
    recommended_capacity: Optional[str] = None
    calculation_notes: Optional[str] = None

class FunctionCall(BaseModel):
    """Function call made by the AI"""
    name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None
    execution_time: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None 