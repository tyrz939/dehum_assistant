"""
Dehumidifier Assistant AI Agent
Handles OpenAI integration, function calling, and conversation management
"""

import litellm
import json
import os
import time
import asyncio
from typing import Dict, List, Optional, Any, Tuple, AsyncGenerator
from datetime import datetime
import logging
from models import ChatRequest, ChatResponse, ChatMessage, MessageRole, SessionInfo, StreamingChatResponse
from tools import DehumidifierTools
from config import config
import requests

# Configuration constants
MAX_CONVERSATION_HISTORY = 10
DEFAULT_MAX_TOKENS = 1000
THINKING_MODEL_MAX_TOKENS = 80000
MAX_RETRIES = 3  # Increased for better reliability
REASONING_EFFORT_LEVEL = "medium"
RETRY_DELAY_BASE = 1.0  # Base delay for exponential backoff
MAX_RETRY_DELAY = 60.0  # Maximum delay between retries

logger = logging.getLogger(__name__)

class DehumidifierAgent:
    """Main AI agent for dehumidifier assistance"""

    def __init__(self):
        self.sessions: Dict[str, SessionInfo] = {}
        self.tools = DehumidifierTools()
        self.model = self._validate_model(config.DEFAULT_MODEL, "DEFAULT_MODEL")
        self.thinking_model = self._validate_model(config.THINKING_MODEL, "THINKING_MODEL")
        self.wp_ajax_url = config.WORDPRESS_URL + "/wp-admin/admin-ajax.php"
        self.wp_api_key = os.getenv("WP_API_KEY")
        self.wp_nonce = os.getenv("WP_NONCE", "default_nonce")
        self._setup_litellm()
        
    def _validate_model(self, model: str, env_var_name: str) -> str:
        """Validate that required model is configured"""
        if model is None:
            raise ValueError(f"{env_var_name} environment variable is required but not set")
        return model
        
    def _setup_litellm(self):
        """Initialize LiteLLM with proper logging configuration"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not found in environment variables")
        
        # Use environment variable for debug logging (modern approach)
        debug_mode = os.getenv('DEBUG', '').lower() == 'true'
        if debug_mode:
            os.environ['LITELLM_LOG'] = 'DEBUG'
        
        # Disable deprecated verbose setting
        litellm.set_verbose = False
        
    def _make_tool_key(self, name: str, args: Dict[str, Any]) -> str:
        """Create a stable cache key for a tool call"""
        try:
            return name + "|" + json.dumps(args, sort_keys=True, separators=(",", ":"))
        except TypeError:
            return name + "|" + str(args)
            
    def _get_temperature(self, model: str) -> float:
        """Get appropriate temperature for model"""
        return 1.0 if model.startswith('o') else 0.3
        
    def _get_completion_params(self, model: str, messages: List[Dict], max_tokens: int) -> Dict[str, Any]:
        """Build completion parameters based on model capabilities"""
        params = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        
        # Only add temperature for models that support it
        if not model.startswith('o4'):
            params["temperature"] = self._get_temperature(model)
        
        # Add reasoning effort for o4 models
        if model.startswith('o4'):
            params["extra_body"] = {"reasoning_effort": REASONING_EFFORT_LEVEL}
            
        return params
        
    def get_system_prompt(self) -> str:
        """Load the system prompt from an external template file"""
        template_path = os.path.join(os.path.dirname(__file__), "prompt_template.txt")
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                base_prompt = f.read()
        except FileNotFoundError:
            logger.error("Prompt template not found at %s", template_path)
            base_prompt = "You are Dehumidifier Assistant."
        
        # Add context-awareness instructions
        context_instructions = """

CONTEXT AWARENESS:
- You have access to previous session data and conversation history
- If you see previous load calculations that are relevant to the current query, REUSE them intelligently
- For follow-up questions like "ducted alternatives", "other options", "different brands" - use existing calculations
- Only call calculate_dehum_load if you need NEW calculations or the user changed parameters
- For variations/alternatives, skip tools and go directly to product recommendations using existing data

DECISION MAKING:
- Analyze the full conversation context before deciding on actions
- If user asks "ducted alternatives" after getting recommendations, they want different TYPES not new calculations
- If user asks "cheaper options" or "other brands", use existing load data for new recommendations
- Only recalculate if room size, humidity levels, or other core parameters actually changed"""
        
        return base_prompt + context_instructions

    def get_streaming_system_prompt(self) -> str:
        """Get a system prompt optimized for streaming responses - stops after load calculation"""
        return """You are Dehumidifier Assistant, a professional dehumidifier sizing expert.

CORE PRINCIPLES
- Stay strictly on-topic: Respond only to dehumidifier sizing, selection, or related queries
- Anti-hallucination: Base ALL responses on provided tool outputs only
- Conciseness: Keep responses professional and focused

STREAMING WORKFLOW
1. Gather Information: If query lacks key details (room dimensions, humidity levels, temperature), ask for them explicitly
2. Calculate Load: Use the calculate_dehum_load function with available parameters
3. STOP AFTER LOAD CALCULATION: Only provide a brief summary of the load calculation results

For load calculations:
- Extract numeric values from user input (e.g., "terrible humidity" = 90%, "high humidity" = 80%)
- For pools: Include pool_area_m2 (calculate from dimensions) and waterTempC (use provided or default 28°C)
- Use defaults: ACH=0.5, peopleCount=0 if not specified

RESPONSE FORMAT
After calculating load, respond with:
"Based on your [room type] specifications, I've calculated your dehumidification requirements."

DO NOT provide product recommendations in this response - that will be handled separately.
"""

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        """Process a chat request and generate response"""
        try:
            session = self.get_or_create_session(request.session_id)
            
            # Add user message to conversation history
            user_message = ChatMessage(
                role=MessageRole.USER,
                content=request.message,
                timestamp=datetime.now()
            )
            session.conversation_history.append(user_message)
            
            # Prepare messages and get AI response
            messages = self._prepare_messages(session)
            response = await self._get_ai_response(messages, session)
            
            # Create and store assistant message
            assistant_message = ChatMessage(
                role=MessageRole.ASSISTANT,
                content=response["content"],
                timestamp=datetime.now(),
                metadata=response.get("metadata", {})
            )
            session.conversation_history.append(assistant_message)
            
            # Update session and trigger integrations
            self._update_session(session)
            self._save_session_to_wp(request.session_id, session.conversation_history)
            self._trigger_n8n_webhook(request.session_id, response)
            
            return ChatResponse(
                message=response["content"],
                session_id=request.session_id,
                timestamp=datetime.now(),
                function_calls=response.get("function_calls", []),
                recommendations=response.get("recommendations", []),
                metadata=response.get("metadata", {})
            )
            
        except Exception as e:
            logger.error(f"Error processing chat: {str(e)}")
            raise
    
    async def process_chat_streaming(self, request: ChatRequest) -> AsyncGenerator[StreamingChatResponse, None]:
        """Process a chat request with streaming responses"""
        try:
            session = self.get_or_create_session(request.session_id)
            
            # Add user message to conversation history
            user_message = ChatMessage(
                role=MessageRole.USER,
                content=request.message,
                timestamp=datetime.now()
            )
            session.conversation_history.append(user_message)
            
            # Phase 1: Execute tools and send immediate response
            tool_calls_list = await self._execute_tools_only(session)
            initial_response = self._create_initial_response(request.session_id, tool_calls_list)
            yield initial_response
            
            # Phase 2: Send thinking message if we need recommendations
            if self._needs_recommendations(tool_calls_list):
                thinking_response = self._create_thinking_response(request.session_id)
                yield thinking_response
                
                # Phase 3: Generate and stream recommendations in real-time
                accumulated_content = ""
                async for text_chunk in self._generate_recommendations_streaming(session, request.message):
                    accumulated_content += text_chunk
                    
                    # Send progressive updates
                    chunk_response = StreamingChatResponse(
                        message=text_chunk,
                        session_id=request.session_id,
                        timestamp=datetime.now(),
                        is_final=False,
                        is_streaming_chunk=True,
                        metadata={"model": self.thinking_model}
                    )
                    yield chunk_response
                
                # Send final marker with complete content
                final_response = StreamingChatResponse(
                    message=accumulated_content,
                    session_id=request.session_id,
                    timestamp=datetime.now(),
                    is_final=True,
                    metadata={"model": self.thinking_model}
                )
                yield final_response
                
                # Store complete conversation
                complete_content = f"{initial_response.message}\n\n{thinking_response.message}\n\n{accumulated_content}"
            else:
                # No recommendations needed, mark as final
                final_response = self._create_final_response(request.session_id, "")
                yield final_response
                complete_content = initial_response.message
            
            # Save to session history
            self._save_complete_response(session, complete_content, tool_calls_list)
            self._update_session(session)
            self._save_session_to_wp(request.session_id, session.conversation_history)
            
        except Exception as e:
            logger.error(f"Error in streaming chat: {str(e)}")
            yield self._create_error_response(request.session_id, str(e))

    async def _execute_tools_only(self, session: SessionInfo) -> List[Dict]:
        """Execute tools without AI model calls - now with context awareness"""
        
        # Check if we have existing load calculation data
        existing_load_data = self._get_latest_load_info(session)
        
        # Prepare messages with full context (including cached data)
        messages = self._prepare_messages(session)
        
        # Make API call to get tool calls - but LLM now has full context
        response = await self._make_initial_api_call(messages)
        message_obj = response.choices[0].message
        
        # If LLM decided no tools are needed (context-aware decision), return empty
        if not hasattr(message_obj, 'tool_calls') or not message_obj.tool_calls:
            return []
            
        # Execute tools only if LLM decided they're necessary
        tool_calls_list = []
        for tool_call in message_obj.tool_calls:
            func_name = tool_call.function.name
            try:
                func_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                func_args = {}
            
            # Check if this is a redundant calculation
            if func_name == "calculate_dehum_load" and existing_load_data:
                logger.info(f"LLM requested {func_name} but existing data available - proceeding with LLM's decision")
            
            result = self._execute_tool_function(func_name, func_args, session)
            tool_calls_list.append({
                "name": func_name,
                "arguments": func_args,
                "result": result
            })
        
        return tool_calls_list

    def _create_initial_response(self, session_id: str, tool_calls_list: List[Dict]) -> StreamingChatResponse:
        """Create the initial response with load calculation"""
        if self._has_load_calculation(tool_calls_list):
            load_info = self._get_latest_load_info_from_tools(tool_calls_list)
            
            # Get the user's original message for context
            tool_args = next((call["arguments"] for call in tool_calls_list if call["name"] == "calculate_dehum_load"), {})
            
            # Create a conversational response that echoes back their situation
            response_parts = []
            
            # Acknowledge their space
            room_area = load_info['room_area_m2']
            if tool_args.get('pool_area_m2', 0) > 0:
                response_parts.append(f"I understand you have a pool room that's {room_area} m²")
            else:
                response_parts.append(f"I see you have a {room_area} m² space")
            
            # Acknowledge humidity situation
            current_rh = tool_args.get('currentRH')
            target_rh = tool_args.get('targetRH')
            if current_rh and target_rh:
                if current_rh >= 85:
                    humidity_desc = "very high humidity"
                elif current_rh >= 75:
                    humidity_desc = "high humidity"
                else:
                    humidity_desc = "elevated humidity"
                response_parts.append(f"with {humidity_desc} around {current_rh}% that you want to bring down to {target_rh}%")
            
            # Add the calculated load
            response_parts.append(f"Based on your specifications, I've calculated you need **{load_info['latentLoad_L24h']} L/day** dehumidification capacity")
            
            # Combine into a natural sentence
            message = ". ".join(response_parts) + ". Let me now analyze the best equipment options for your specific situation..."
            
        else:
            # No new tools executed - check if we have existing data for follow-up
            session_obj = self.sessions.get(session_id)
            if session_obj:
                existing_load_data = self._get_latest_load_info(session_obj)
                if existing_load_data:
                    message = f"I'll help you find alternatives using your existing requirements of **{existing_load_data['latentLoad_L24h']} L/day** for your **{existing_load_data['room_area_m2']} m²** space."
                else:
                    message = "I've processed your request and I'm ready to help you find the right dehumidifier solution."
            else:
                message = "I've processed your request and I'm ready to help you find the right dehumidifier solution."
            
        return StreamingChatResponse(
            message=message,
            session_id=session_id,
            timestamp=datetime.now(),
            is_final=False,
            function_calls=tool_calls_list,
            metadata={"model": self.model}
        )

    def _create_thinking_response(self, session_id: str) -> StreamingChatResponse:
        """Create the thinking message"""
        return StreamingChatResponse(
            message="🤔 Let me analyze the available options and find the best dehumidifier combinations for your specific requirements...",
            session_id=session_id,
            timestamp=datetime.now(),
            is_thinking=True,
            is_final=False,
            metadata={"model": self.thinking_model}
        )

    def _create_final_response(self, session_id: str, recommendations: str) -> StreamingChatResponse:
        """Create the final response with recommendations"""
        return StreamingChatResponse(
            message=recommendations,
            session_id=session_id,
            timestamp=datetime.now(),
            is_final=True,
            metadata={"model": self.thinking_model}
        )

    def _create_error_response(self, session_id: str, error: str) -> StreamingChatResponse:
        """Create an error response"""
        return StreamingChatResponse(
            message=f"I apologize, but I'm experiencing technical difficulties. Please try again in a moment.",
            session_id=session_id,
            timestamp=datetime.now(),
            is_final=True,
            metadata={"error": error}
        )

    def _needs_recommendations(self, tool_calls_list: List[Dict]) -> bool:
        """Check if we need to generate product recommendations"""
        # If we just calculated load, definitely need recommendations
        if self._has_load_calculation(tool_calls_list):
            return True
        
        # If no tools executed but we have existing data, we might still need recommendations
        # This will be determined by the LLM context - let's assume yes for follow-ups
        return len(tool_calls_list) == 0

    async def _generate_recommendations(self, session: SessionInfo, user_message: str) -> str:
        """Generate product recommendations using the thinking model"""
        load_info = self._get_latest_load_info(session)
        if not load_info:
            return "Unable to generate recommendations without load calculation."
        
        # Build catalog data
        preferred_types = self._detect_preferred_types(user_message)
        catalog = self.tools.get_catalog_with_effective_capacity(
            include_pool_safe_only=load_info["pool_required"]
        )
        
        if preferred_types:
            catalog = [p for p in catalog if p.get("type") in preferred_types]
        
        catalog_data = {
            "required_load_lpd": load_info["latentLoad_L24h"],
            "room_area_m2": load_info["room_area_m2"],
            "pool_area_m2": load_info["pool_area_m2"],
            "pool_required": load_info["pool_required"],
            "preferred_types": preferred_types,
            "catalog": catalog
        }
        
        # Generate recommendations
        catalog_request = f"""Provide specific product recommendations for a load of {load_info['latentLoad_L24h']} L/day in a {load_info['room_area_m2']} m² room.

```json
{json.dumps(catalog_data)}
```

Select combinations that meet the load requirement (≥{load_info['latentLoad_L24h']} L/day total effective capacity) with minimal overshoot. Use effective_capacity_lpd values for calculations."""
        
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": catalog_request}
        ]
        
        params = self._get_completion_params(self.thinking_model, messages, THINKING_MODEL_MAX_TOKENS)
        response = await self._make_api_call_with_retry(**params)
        return response.choices[0].message.content or ""

    async def _generate_recommendations_streaming(self, session: SessionInfo, user_message: str) -> AsyncGenerator[str, None]:
        """Generate product recommendations using the thinking model with real-time streaming"""
        load_info = self._get_latest_load_info(session)
        if not load_info:
            yield "Unable to generate recommendations without load calculation."
            return
        
        # Build catalog data
        preferred_types = self._detect_preferred_types(user_message)
        catalog = self.tools.get_catalog_with_effective_capacity(
            include_pool_safe_only=load_info["pool_required"]
        )
        
        if preferred_types:
            catalog = [p for p in catalog if p.get("type") in preferred_types]
        
        catalog_data = {
            "required_load_lpd": load_info["latentLoad_L24h"],
            "room_area_m2": load_info["room_area_m2"],
            "pool_area_m2": load_info["pool_area_m2"],
            "pool_required": load_info["pool_required"],
            "preferred_types": preferred_types,
            "catalog": catalog
        }
        
        # Generate recommendations with streaming
        catalog_request = f"""Provide specific product recommendations for a load of {load_info['latentLoad_L24h']} L/day in a {load_info['room_area_m2']} m² room.

```json
{json.dumps(catalog_data)}
```

Select combinations that meet the load requirement (≥{load_info['latentLoad_L24h']} L/day total effective capacity) with minimal overshoot. Use effective_capacity_lpd values for calculations."""
        
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": catalog_request}
        ]
        
        # Use streaming completion
        params = self._get_completion_params(self.thinking_model, messages, THINKING_MODEL_MAX_TOKENS)
        params["stream"] = True
        
        try:
            response = await litellm.acompletion(**params)
            
            async for chunk in response:
                if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
                        
        except Exception as e:
            logger.error(f"Error in streaming recommendations: {str(e)}")
            yield f"I apologize, but I'm experiencing technical difficulties generating recommendations. Error: {str(e)}"

    def _get_latest_load_info_from_tools(self, tool_calls_list: List[Dict]) -> Dict[str, Any]:
        """Get load info directly from tool calls"""
        for tool_call in tool_calls_list:
            if tool_call["name"] == "calculate_dehum_load":
                result = tool_call["result"]
                args = tool_call["arguments"]
                return {
                    "latentLoad_L24h": result.get('latentLoad_L24h'),
                    "room_area_m2": result.get('room_area_m2'),
                    "volume": result.get('volume'),
                    "pool_area_m2": args.get('pool_area_m2', 0),
                    "pool_required": args.get('pool_area_m2', 0) > 0
                }
        return {}

    def _save_complete_response(self, session: SessionInfo, content: str, tool_calls_list: List[Dict]):
        """Save the complete response to session history"""
        assistant_message = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=content,
            timestamp=datetime.now(),
            metadata={"model": self.model, "function_calls": tool_calls_list}
        )
        session.conversation_history.append(assistant_message)
    
    def get_or_create_session(self, session_id: str) -> SessionInfo:
        """Get existing session or create new one"""
        if session_id in self.sessions:
            return self.sessions[session_id]
            
        # Try to fetch from WordPress
        history = self._fetch_session_from_wp(session_id)
        if history:
            session = SessionInfo(
                session_id=session_id,
                conversation_history=[ChatMessage(**msg) for msg in history],
                created_at=datetime.now(),
                last_activity=datetime.now(),
                message_count=len(history)
            )
        else:
            session = SessionInfo(
                session_id=session_id,
                conversation_history=[],
                created_at=datetime.now(),
                last_activity=datetime.now(),
                message_count=0
            )
        
        self.sessions[session_id] = session
        return session
    
    def _prepare_messages(self, session: SessionInfo) -> List[Dict[str, str]]:
        """Prepare messages for OpenAI API with full context"""
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        
        # Add context from previous tool results if available
        if session.tool_cache:
            context_info = self._build_context_from_cache(session.tool_cache)
            if context_info:
                messages.append({
                    "role": "system", 
                    "content": f"PREVIOUS SESSION DATA:\n{context_info}\n\nUse this information if relevant to the current query. If the user is asking for alternatives or variations, you can reuse existing calculations."
                })
        
        # Add ALL conversation history (not just recent) for full context
        for msg in session.conversation_history:
            messages.append({
                "role": msg.role.value,
                "content": msg.content
            })
        
        return messages
    
    def _build_context_from_cache(self, tool_cache: Dict[str, Any]) -> str:
        """Build context information from cached tool results"""
        context_parts = []
        
        for cache_key, result in tool_cache.items():
            if 'calculate_dehum_load' in cache_key:
                try:
                    # Extract arguments from cache key
                    args = json.loads(cache_key.split('|', 1)[1])
                    
                    # Build readable context
                    room_info = f"Room: {result.get('room_area_m2', 'unknown')} m² ({args.get('length', '?')}x{args.get('width', '?')}x{args.get('height', '?')}m)"
                    humidity_info = f"Humidity: {args.get('currentRH', '?')}% → {args.get('targetRH', '?')}%"
                    load_info = f"Required Capacity: {result.get('latentLoad_L24h', '?')} L/day"
                    
                    context_parts.append(f"Previous Load Calculation:\n- {room_info}\n- {humidity_info}\n- {load_info}")
                    
                    if args.get('pool_area_m2', 0) > 0:
                        pool_info = f"- Pool: {args.get('pool_area_m2')} m² at {args.get('waterTempC', 28)}°C"
                        context_parts.append(pool_info)
                        
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                    
        return "\n\n".join(context_parts)
    
    def _prepare_messages_streaming(self, session: SessionInfo) -> List[Dict[str, str]]:
        """Prepare messages for streaming OpenAI API with streaming-specific system prompt"""
        messages = [{"role": "system", "content": self.get_streaming_system_prompt()}]
        
        # Add recent conversation history
        recent_history = session.conversation_history[-MAX_CONVERSATION_HISTORY:]
        for msg in recent_history:
            messages.append({
                "role": msg.role.value,
                "content": msg.content
            })
        
        return messages
    
    def _update_session(self, session: SessionInfo):
        """Update session metadata"""
        session.last_activity = datetime.now()
        session.message_count += 2  # User + Assistant
    
    async def _get_ai_response(self, messages: List[Dict[str, str]], session: SessionInfo) -> Dict[str, Any]:
        """Get response from AI with function calling and catalog recommendations"""
        logger.debug(f"Starting AI response generation for session {session.session_id}")
        
        try:
            # Get last user message for preference detection
            last_user_content = self._get_last_user_message(messages)
            
            # Make initial API call with tools
            response = await self._make_initial_api_call(messages)
            message_obj = response.choices[0].message
            
            # Process tool calls if present
            tool_calls_list = []
            content = getattr(message_obj, "content", None)
            
            if hasattr(message_obj, 'tool_calls') and message_obj.tool_calls:
                logger.debug(f"Processing {len(message_obj.tool_calls)} tool calls")
                tool_calls_list, content = await self._process_tool_calls(
                    message_obj.tool_calls, messages, session
                )
            
            # Handle catalog recommendations if load calculation was performed
            if tool_calls_list and self._has_load_calculation(tool_calls_list):
                # Add thinking message to the content
                thinking_message = "\n\n🤔 Let me analyze the available options and find the best dehumidifier combinations for your specific requirements...\n\n"
                content_with_thinking = content + thinking_message
                
                # Generate catalog recommendations
                catalog_recommendations = await self._generate_catalog_recommendations_only(
                    session, last_user_content, ""
                )
                
                # Combine all content
                final_content = content_with_thinking + catalog_recommendations
            else:
                final_content = content
            
            return {
                "content": final_content,
                "tool_calls": tool_calls_list,
                "recommendations": [],
                "metadata": {"model": self.model}
            }
            
        except Exception as e:
            logger.error(f"Error in AI response generation: {str(e)}")
            return {
                "content": f"I apologize, but I'm experiencing technical difficulties. Please try again in a moment. Error: {str(e)}",
                "tool_calls": [],
                "metadata": {"error": str(e), "model": self.model}
            }
    
    def _get_last_user_message(self, messages: List[Dict[str, str]]) -> str:
        """Extract the last user message content"""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "") or ""
        return ""
    
    async def _make_initial_api_call(self, messages: List[Dict[str, str]]):
        """Make initial API call with tool definitions"""
        tools = self._get_tool_definitions()
        params = self._get_completion_params(self.model, messages, DEFAULT_MAX_TOKENS)
        params.update({
            "tools": tools,
            "tool_choice": "auto"
        })
        
        logger.debug(f"Making API call with model {self.model}")
        return await self._make_api_call_with_retry(**params)
    
    def _get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get OpenAI tool definitions"""
        return [
                    {
                        "type": "function",
                        "function": {
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
                        }
                    },
                    {
                        "type": "function",
                        "function": {
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
                    }
                ]
                
    async def _process_tool_calls(self, tool_calls, messages: List[Dict], session: SessionInfo) -> Tuple[List[Dict], str]:
        """Process tool calls and return results"""
        tool_calls_list = []
        
        for i, tool_call in enumerate(tool_calls):
            func_name = tool_call.function.name
            try:
                func_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                logger.error("Could not decode tool call arguments JSON")
                func_args = {}
            
            logger.info(f"Executing tool call: {func_name}")
            
            # Execute function with caching
            result = self._execute_tool_function(func_name, func_args, session)
            tool_calls_list.append({
                "name": func_name, 
                "arguments": func_args, 
                "result": result
            })
            
            # Add to message history for follow-up
            messages.append({"role": "assistant", "content": None, "tool_calls": [tool_call]})
            messages.append({
                "role": "tool", 
                "tool_call_id": tool_call.id, 
                "name": func_name, 
                "content": json.dumps(result)
            })
        
        # Get follow-up response with tool results using retry logic
        params = self._get_completion_params(self.model, messages, DEFAULT_MAX_TOKENS)
        follow_up_response = await self._make_api_call_with_retry(**params)
        content = follow_up_response.choices[0].message.content
        
        return tool_calls_list, content
    
    def _execute_tool_function(self, func_name: str, func_args: Dict, session: SessionInfo) -> Dict[str, Any]:
        """Execute a tool function with caching"""
        cache_key = self._make_tool_key(func_name, func_args)
        cached_result = session.tool_cache.get(cache_key)
        
        if cached_result is not None:
            logger.debug(f"Using cached result for {func_name}")
            return cached_result
        
        # Execute function
        if func_name == "calculate_dehumidifier_sizing":
            if 'waterTempC' in func_args:
                func_args['water_temp_c'] = func_args.pop('waterTempC')
            result = self.tools.calculate_sizing(**func_args)
        elif func_name == "calculate_dehum_load":
            result = self.tools.calculate_dehum_load(**func_args)
        else:
            raise ValueError(f"Unknown function: {func_name}")
        
        # Cache and return result
        session.tool_cache[cache_key] = result
        return result
    
    def _has_load_calculation(self, tool_calls_list: List[Dict]) -> bool:
        """Check if any tool call was a load calculation"""
        return any(call["name"] == "calculate_dehum_load" for call in tool_calls_list)
    
    def _get_latest_load_info(self, session: SessionInfo) -> Optional[Dict[str, Any]]:
        """Get the most recent load calculation from session cache"""
        for cache_key, result in reversed(list(session.tool_cache.items())):
            if 'calculate_dehum_load' in cache_key:
                try:
                    args = json.loads(cache_key.split('|', 1)[1])
                    return {
                        "latentLoad_L24h": result.get('latentLoad_L24h'),
                        "room_area_m2": result.get('room_area_m2'),
                        "volume": result.get('volume'),
                        "pool_area_m2": args.get('pool_area_m2', 0),
                        "pool_required": args.get('pool_area_m2', 0) > 0
                    }
                except (json.JSONDecodeError, IndexError):
                    continue
        return None
    
    async def _generate_catalog_recommendations_only(self, session: SessionInfo, last_user_content: str, fallback_content: str) -> str:
        """Generate only the catalog recommendations without thinking message"""
        load_info = self._get_latest_load_info(session)
        if not load_info:
            return fallback_content
        
        try:
            # Build catalog data
            preferred_types = self._detect_preferred_types(last_user_content)
            catalog = self.tools.get_catalog_with_effective_capacity(
                include_pool_safe_only=load_info["pool_required"]
            )
            
            if preferred_types:
                catalog = [p for p in catalog if p.get("type") in preferred_types]
            
            catalog_data = {
                "required_load_lpd": load_info["latentLoad_L24h"],
                "room_area_m2": load_info["room_area_m2"],
                "pool_area_m2": load_info["pool_area_m2"],
                "pool_required": load_info["pool_required"],
                "preferred_types": preferred_types,
                "catalog": catalog
            }
            
            # Create thinking model request
            catalog_request = f"""Now please provide specific product recommendations. I need dehumidifiers for a load of {load_info['latentLoad_L24h']} L/day in a {load_info['room_area_m2']} m² room.

Here is the available product catalog:

```json
{json.dumps(catalog_data)}
```

Please select the best combination(s) that meet the load requirement (≥{load_info['latentLoad_L24h']} L/day total effective capacity) with minimal overshoot. Use effective_capacity_lpd values for calculations. Provide exact model names, prices, and URLs from the catalog above."""

            thinking_messages = [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": last_user_content},
                {"role": "assistant", "content": f"Load: {load_info['latentLoad_L24h']} L/day | Room: {load_info['room_area_m2']} m²"},
                {"role": "user", "content": catalog_request}
            ]
            
            # Call thinking model with retry logic
            params = self._get_completion_params(self.thinking_model, thinking_messages, THINKING_MODEL_MAX_TOKENS)
            logger.debug(f"Calling thinking model {self.thinking_model} for recommendations")
            
            response = await self._make_api_call_with_retry(**params)
            return response.choices[0].message.content or fallback_content
            
        except Exception as e:
            logger.error(f"Error generating catalog recommendations: {str(e)}")
            return fallback_content

    def _detect_preferred_types(self, text: str) -> List[str]:
        """Detect preferred installation types from user text"""
        if not text:
            return []
        
        text_lower = text.lower()
        preferred_types = []
        
        if "ducted" in text_lower or "duct" in text_lower:
            preferred_types.append("ducted")
        if "wall" in text_lower:
            preferred_types.append("wall_mount")
        if "portable" in text_lower:
            preferred_types.append("portable")
            
        return preferred_types
    
    def get_session_info(self, session_id: str) -> SessionInfo:
        """Get session information"""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        return self.sessions[session_id]
    
    def clear_session(self, session_id: str):
        """Clear session conversation history"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.conversation_history = []
            session.message_count = 0
            session.tool_cache.clear()
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the agent"""
        return {
            "active_sessions": len(self.sessions),
            "model": self.model,
            "tools_loaded": len(self.tools.get_available_tools()),
            "status": "healthy"
        }
    
    def _get_wp_nonce(self) -> str:
        """Get WordPress nonce for authentication"""
        if not self.wp_api_key:
            logger.debug("WordPress API key not configured, skipping nonce request")
            return 'fallback_nonce'
            
        try:
            response = requests.get(
                self.wp_ajax_url, 
                params={'action': 'dehum_get_nonce'}, 
                headers={'Authorization': f'Bearer {self.wp_api_key}'},
                timeout=5  # Add timeout to prevent hanging
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data['data']['nonce']
            logger.debug(f'WordPress nonce request failed with status {response.status_code}')
            return 'fallback_nonce'
        except requests.exceptions.RequestException as e:
            logger.debug(f'WordPress nonce request failed: {e}')
            return 'fallback_nonce'
        except Exception as e:
            logger.debug(f'Unexpected error getting WordPress nonce: {e}')
            return 'fallback_nonce'

    def _fetch_session_from_wp(self, session_id: str) -> List[Dict]:
        """Fetch session history from WordPress"""
        if not self.wp_api_key:
            logger.debug("WordPress API key not configured, skipping session fetch")
            return []
            
        nonce = self._get_wp_nonce()
        try:
            response = requests.post(
                self.wp_ajax_url,
                data={
                    "action": "dehum_get_session", 
                    "session_id": session_id, 
                    "nonce": nonce
                },
                headers={"Authorization": f"Bearer {self.wp_api_key}"},
                timeout=5
            )
            if response.status_code != 200:
                logger.debug(f"WordPress session fetch failed with status {response.status_code}")
                return []
            
            data = response.json()
            if data.get("success"):
                return data["data"]["history"]
            logger.debug("WordPress session fetch returned unsuccessful response")
            return []
        except requests.exceptions.RequestException as e:
            logger.debug(f"WordPress session fetch failed: {e}")
            return []
        except Exception as e:
            logger.debug(f"Unexpected error fetching session from WordPress: {e}")
            return []

    def _save_session_to_wp(self, session_id: str, history: List[ChatMessage]):
        """Save session history to WordPress"""
        if not self.wp_api_key:
            logger.debug("WordPress API key not configured, skipping session save")
            return
            
        nonce = self._get_wp_nonce()
        try:
            # Convert history to WordPress format
            wp_history = []
            for msg in history:
                if msg.role == MessageRole.USER:
                    wp_history.append({
                        "message": msg.content,
                        "response": "",
                        "user_ip": "",
                        "timestamp": msg.timestamp.isoformat()
                    })
                else:
                    wp_history.append({
                        "message": "",
                        "response": msg.content,
                        "user_ip": "",
                        "timestamp": msg.timestamp.isoformat()
                    })
            
            response = requests.post(
                self.wp_ajax_url,
                data={
                    "action": "dehum_save_session",
                    "session_id": session_id,
                    "history": json.dumps(wp_history),
                    "nonce": nonce
                },
                headers={"Authorization": f"Bearer {self.wp_api_key}"},
                timeout=5
            )
            
            if response.status_code != 200:
                logger.debug(f"WordPress session save failed with status {response.status_code}")
                return
                
            if not response.json().get("success"):
                logger.debug("WordPress session save returned unsuccessful response")
        except requests.exceptions.RequestException as e:
            logger.debug(f"WordPress session save failed: {e}")
        except Exception as e:
            logger.debug(f"Unexpected error saving session to WordPress: {e}")

    def _trigger_n8n_webhook(self, session_id: str, response: Dict):
        """Trigger n8n webhook with response data"""
        n8n_url = os.getenv("N8N_WEBHOOK_URL")
        if not n8n_url:
            logger.debug("N8N webhook URL not configured, skipping webhook trigger")
            return
            
        payload = {
            "session_id": session_id,
            "message": response["content"],
            "recommendations": response.get("recommendations", []),
            "function_calls": response.get("function_calls", [])
        }
        
        try:
            requests.post(n8n_url, json=payload, timeout=5)
            logger.debug("N8N webhook triggered successfully")
        except requests.exceptions.RequestException as e:
            logger.debug(f"N8N webhook trigger failed: {e}")
        except Exception as e:
            logger.debug(f"Unexpected error triggering N8N webhook: {e}")

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter"""
        delay = min(RETRY_DELAY_BASE * (2 ** attempt), MAX_RETRY_DELAY)
        # Add jitter to prevent thundering herd
        jitter = delay * 0.1 * (0.5 - os.urandom(1)[0] / 255.0)
        return delay + jitter
        
    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is retryable"""
        error_str = str(error).lower()
        
        # Rate limiting errors
        if "rate limit" in error_str or "429" in error_str:
            return True
            
        # Network/connection errors
        if any(keyword in error_str for keyword in [
            "connection", "timeout", "network", "502", "503", "504"
        ]):
            return True
            
        # OpenAI service errors
        if any(keyword in error_str for keyword in [
            "service unavailable", "internal server error", "502", "503"
        ]):
            return True
            
        return False
        
    async def _make_api_call_with_retry(self, **params) -> Any:
        """Make API call with robust retry logic"""
        last_error = None
        
        for attempt in range(MAX_RETRIES + 1):
            try:
                logger.debug(f"API call attempt {attempt + 1}/{MAX_RETRIES + 1}")
                return await litellm.acompletion(**params)
                
            except Exception as e:
                last_error = e
                logger.warning(f"API call attempt {attempt + 1} failed: {str(e)}")
                
                # Don't retry on final attempt
                if attempt == MAX_RETRIES:
                    break
                    
                # Only retry if error is retryable
                if not self._is_retryable_error(e):
                    logger.error(f"Non-retryable error: {str(e)}")
                    break
                    
                # Calculate and apply delay
                delay = self._calculate_retry_delay(attempt)
                logger.info(f"Retrying in {delay:.2f} seconds...")
                await asyncio.sleep(delay)
        
        # If we get here, all retries failed
        logger.error(f"API call failed after {MAX_RETRIES + 1} attempts. Last error: {str(last_error)}")
        raise last_error