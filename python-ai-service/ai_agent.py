"""
Dehumidifier Assistant AI Agent
Handles OpenAI integration, function calling, and conversation management
"""

import openai
import litellm
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
from models import ChatRequest, ChatResponse, ChatMessage, MessageRole, SessionInfo, ProductRecommendation, SizingCalculation
from tools import DehumidifierTools
from config import config

logger = logging.getLogger(__name__)

class DehumidifierAgent:
    """Main AI agent for dehumidifier assistance"""
    
    def __init__(self):
        self.sessions: Dict[str, SessionInfo] = {}
        self.tools = DehumidifierTools()
        # Use model from configuration or fallback
        self.model = config.DEFAULT_MODEL or "gpt-4o-mini"
        self.setup_openai()
        
    def setup_openai(self):
        """Initialize OpenAI client"""
        # Get API key from environment
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not found in environment variables")
        
        # Configure LiteLLM for model flexibility
        litellm.set_verbose = False
        
    def get_system_prompt(self) -> str:
        """Load the system prompt from an external template file"""
        template_path = os.path.join(os.path.dirname(__file__), "prompt_template.txt")
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.error("Prompt template not found at %s", template_path)
            return "You are Dehumidifier Assistant."

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        """Process a chat request and generate response"""
        try:
            # Get or create session
            session = self.get_or_create_session(request.session_id)
            
            # Add user message to conversation history
            user_message = ChatMessage(
                role=MessageRole.USER,
                content=request.message,
                timestamp=datetime.now()
            )
            session.conversation_history.append(user_message)
            
            # Prepare messages for OpenAI
            messages = self.prepare_messages(session)
            
            # Get AI response with function calling
            response = await self.get_ai_response(messages)
            
            # Create assistant message
            assistant_message = ChatMessage(
                role=MessageRole.ASSISTANT,
                content=response["content"],
                timestamp=datetime.now(),
                metadata=response.get("metadata", {})
            )
            session.conversation_history.append(assistant_message)
            
            # Update session info
            session.last_activity = datetime.now()
            session.message_count += 2  # User + Assistant
            
            return ChatResponse(
                message=response["content"],
                session_id=request.session_id,
                timestamp=datetime.now(),
                function_calls=response.get("function_calls", []),
                metadata=response.get("metadata", {})
            )
            
        except Exception as e:
            logger.error(f"Error processing chat: {str(e)}")
            raise
    
    def get_or_create_session(self, session_id: str) -> SessionInfo:
        """Get existing session or create new one"""
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionInfo(
                session_id=session_id,
                conversation_history=[],
                created_at=datetime.now(),
                last_activity=datetime.now(),
                message_count=0
            )
        return self.sessions[session_id]
    
    def prepare_messages(self, session: SessionInfo) -> List[Dict[str, str]]:
        """Prepare messages for OpenAI API"""
        messages = [
            {"role": "system", "content": self.get_system_prompt()}
        ]
        
        # Add conversation history
        for msg in session.conversation_history[-10:]:  # Keep last 10 messages
            messages.append({
                "role": msg.role.value,
                "content": msg.content
            })
        
        return messages
    
    async def get_ai_response(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Get response from OpenAI with function calling"""
        try:
            # Determine last user message content for preference detection
            last_user_content = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    last_user_content = m.get("content", "") or ""
                    break

            # Define available functions
            functions = [
                {
                    "name": "calculate_dehumidifier_sizing",
                    "description": "Calculate optimal dehumidifier capacity based on room dimensions and conditions",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "room_length_m": {"type": "number", "description": "Room length in meters"},
                            "room_width_m": {"type": "number", "description": "Room width in meters"},
                            "ceiling_height_m": {"type": "number", "description": "Ceiling height in meters"},
                            "humidity_level": {"type": "string", "description": "Current humidity level (low/medium/high/extreme)"},
                            "has_pool": {"type": "boolean", "description": "Whether the space has a pool"},
                            "pool_area_m2": {"type": "number", "description": "Pool area in square meters if applicable"}
                        },
                        "required": ["room_length_m", "room_width_m", "ceiling_height_m", "humidity_level"]
                    }
                },
                {
                    "name": "calculate_dehum_load",
                    "description": "Calculate latent moisture load for a room based on sizing spec v0.1",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "length": {"type": "number", "description": "Room length in meters"},
                            "width": {"type": "number", "description": "Room width in meters"},
                            "height": {"type": "number", "description": "Ceiling height in meters"},
                            "currentRH": {"type": "number", "description": "Current relative humidity %"},
                            "targetRH": {"type": "number", "description": "Target relative humidity %"},
                            "indoorTemp": {"type": "number", "description": "Indoor temperature °C"},
                            "ach": {"type": "number", "description": "Air changes per hour"},
                            "peopleCount": {"type": "number", "description": "Number of occupants"},
                            "pool_area_m2": {"type": "number", "description": "Pool surface area in square meters"},
                            "waterTempC": {"type": "number", "description": "Pool water temperature in °C"}
                        },
                        "required": ["length", "width", "height", "currentRH", "targetRH", "indoorTemp"]
                    }
                }
            ]
            
            # Make API call with function calling
            response = await litellm.acompletion(
                model=self.model,
                messages=messages,
                functions=functions,
                function_call="auto",
                temperature=0.7,
                max_tokens=1000
            )
            
            message_obj = response.choices[0].message
            
            # Normalize message to dict for easier handling
            message_dict = {
                "content": getattr(message_obj, "content", None),
                "function_call": None
            }
            
            # LiteLLM may return function_call as a pydantic object rather than a dict
            if hasattr(message_obj, "function_call") and message_obj.function_call:
                fc = message_obj.function_call
                if isinstance(fc, dict):
                    message_dict["function_call"] = fc
                else:
                    # Convert pydantic / dataclass style object to dict
                    message_dict["function_call"] = {
                        "name": getattr(fc, "name", None),
                        "arguments": getattr(fc, "arguments", "{}")
                    }
            
            # Handle function calls
            function_calls = []
            catalog_data = None
            
            if message_dict["function_call"]:
                func_call = message_dict["function_call"]
                func_name = func_call.get("name")
                try:
                    func_args = json.loads(func_call.get("arguments", "{}"))
                except json.JSONDecodeError:
                    logger.error("Could not decode function call arguments JSON")
                    func_args = {}
                
                logger.info(f"Function call: {func_name} with args: {func_args}")
                
                # Execute function
                if func_name == "calculate_dehumidifier_sizing":
                    result = self.tools.calculate_sizing(**func_args)
                    function_calls.append({
                        "name": func_name,
                        "arguments": func_args,
                        "result": result
                    })

                    # Auto-run product recommendations based on sizing result
                    room_area = result.get("room_area_m2")
                    room_volume = result.get("room_volume_m3")
                    pool_area = func_args.get("pool_area_m2", 0)
                    pool_required = bool(func_args.get("has_pool", False)) or pool_area > 0
                    # Detect form-factor preference from the latest user message
                    preferred_types = self._detect_preferred_types(last_user_content)
                    catalog = self.tools.get_catalog_with_effective_capacity(include_pool_safe_only=pool_required)
                    if preferred_types:
                        filtered = [p for p in catalog if p.get("type") in preferred_types]
                        # Fallback to full catalog if no items match the preference
                        catalog = filtered if filtered else catalog

                    catalog_data = {
                        "required_load_lpd": result.get("recommended_capacity_lpd"),
                        "preferred_types": preferred_types,
                        "catalog": catalog
                    }
                elif func_name == "calculate_dehum_load":
                    result = self.tools.calculate_dehum_load(**func_args)
                    function_calls.append({
                        "name": func_name,
                        "arguments": func_args,
                        "result": result
                    })

                    # Auto-run product recommendations based on load result
                    room_area = result.get("room_area_m2") or (func_args.get("length", 0) * func_args.get("width", 0))
                    room_volume = result.get("volume")
                    pool_area = func_args.get("pool_area_m2", 0)
                    pool_required = bool(func_args.get("has_pool", False)) or pool_area > 0
                    # Detect form-factor preference from the latest user message
                    preferred_types = self._detect_preferred_types(last_user_content)
                    catalog = self.tools.get_catalog_with_effective_capacity(include_pool_safe_only=pool_required)
                    if preferred_types:
                        filtered = [p for p in catalog if p.get("type") in preferred_types]
                        catalog = filtered if filtered else catalog

                    catalog_data = {
                        "required_load_lpd": result.get("latentLoad_L24h"),
                        "preferred_types": preferred_types,
                        "catalog": catalog
                    }
                
                # Get follow-up response with function result
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "function_call": func_call
                })
                messages.append({
                    "role": "function",
                    "name": func_name,
                    "content": json.dumps(result)
                })
                
                follow_up_response = await litellm.acompletion(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1000
                )
                
                content = follow_up_response.choices[0].message.content
            else:
                content = message_dict["content"]
            
            # After load calculation, provide catalog to LLM for final recommendation
            if catalog_data:
                messages.append({
                    "role": "assistant",
                    "content": "Here is the product catalog with effective capacities and specs:" + "\n```json\n" + json.dumps(catalog_data) + "\n```\n"
                })
                follow_final = await litellm.acompletion(
                    model=self.model,
                    messages=messages,
                    temperature=0.6,
                    max_tokens=800
                )
                content = follow_final.choices[0].message.content

            return {
                "content": content,
                "function_calls": function_calls,
                "metadata": {
                    "model": self.model
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting AI response: {str(e)}")
            return {
                "content": "I apologize, but I'm experiencing technical difficulties. Please try again or contact support if the issue persists.",
                "function_calls": [],
                "metadata": {"error": str(e)}
            }
    
    def get_session_info(self, session_id: str) -> SessionInfo:
        """Get session information"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        return self.sessions[session_id]
    
    def clear_session(self, session_id: str):
        """Clear session conversation history"""
        if session_id in self.sessions:
            self.sessions[session_id].conversation_history = []
            self.sessions[session_id].message_count = 0
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the agent"""
        return {
            "active_sessions": len(self.sessions),
            "model": self.model,
            "tools_loaded": len(self.tools.get_available_tools()),
            "status": "healthy"
        }
    
    def get_available_models(self) -> List[str]:
        """Get list of available AI models"""
        return [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-3.5-turbo",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307"
        ] 

    def _detect_preferred_types(self, text: str) -> List[str]:
        """Simple heuristic to detect preferred installation types from user text"""
        if not text:
            return []
        t = text.lower()
        prefs = []
        if "ducted" in t or "duct" in t:
            prefs.append("ducted")
        if "wall" in t:
            # treat 'wall mount' or 'wall-mounted'
            prefs.append("wall_mount")
        if "portable" in t:
            prefs.append("portable")
        return prefs
    