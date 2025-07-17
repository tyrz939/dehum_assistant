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
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter
from engine import LLMEngine
from tool_executor import ToolExecutor
from session_store import InMemorySessionStore, WordPressSessionStore

# Configuration constants
MAX_CONVERSATION_HISTORY = 10
DEFAULT_MAX_TOKENS = 10000
THINKING_MODEL_MAX_TOKENS = 80000
MAX_RETRIES = 3
REASONING_EFFORT_LEVEL = "medium"
RETRY_DELAY_BASE = 1.0
MAX_RETRY_DELAY = 60.0
STREAMING_TIMEOUT_SECONDS = 300

MODEL_TOKEN_LIMITS = {
    "o4": 100000,
    "gpt-4": 16384,
}

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
        self._setup_litellm()
        
        self.engine = LLMEngine(
            model=self.model,
            completion_params_builder=self._get_completion_params,
            api_caller=self._make_api_call_with_retry,
        )
        self.tool_executor = ToolExecutor(self.tools)
        
        if self.wp_api_key:
            self.session_store = WordPressSessionStore(config.WORDPRESS_URL, self.wp_api_key)
        else:
            self.session_store = InMemorySessionStore()
        
    def _validate_model(self, model: str, env_var_name: str) -> str:
        if model is None:
            raise ValueError(f"{env_var_name} environment variable is required but not set")
        return model
        
    def _setup_litellm(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not found in environment variables")
        
        debug_mode = os.getenv('DEBUG', '').lower() == 'true'
        if debug_mode:
            os.environ['LITELLM_LOG'] = 'DEBUG'
        litellm.set_verbose = False
        
    def _make_tool_key(self, name: str, args: Dict[str, Any]) -> str:
        try:
            return name + "|" + json.dumps(args, sort_keys=True, separators=(",", ":"))
        except TypeError:
            return name + "|" + str(args)
            
    def _get_temperature(self, model: str) -> float:
        return 1.0 if model.startswith('o') else 0.3
        
    def _cap_max_tokens(self, model: str, requested: int) -> int:
        for prefix, limit in MODEL_TOKEN_LIMITS.items():
            if model.startswith(prefix):
                return min(requested, limit)
        return min(requested, 16000)
        
    def _get_completion_params(self, model: str, messages: List[Dict], max_tokens: int) -> Dict[str, Any]:
        params = {
            "model": model,
            "messages": messages,
            "max_tokens": self._cap_max_tokens(model, max_tokens),
        }
        if not model.startswith('o4'):
            params["temperature"] = self._get_temperature(model)
        if model.startswith('o4'):
            params["extra_body"] = {"reasoning_effort": REASONING_EFFORT_LEVEL}
        return params
        
    def _load_prompt_from_file(self, filename: str) -> str:
        prompt_path = os.path.join(os.path.dirname(__file__), "prompts", filename)
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Prompt file not found at {prompt_path}")
            return "You are a helpful assistant."

    def get_system_prompt(self) -> str:
        return self._load_prompt_from_file("system_prompt.txt")

    def get_streaming_system_prompt(self) -> str:
        return self._load_prompt_from_file("streaming_system_prompt.txt")

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        session = self.get_or_create_session(request.session_id)
        user_message = ChatMessage(role=MessageRole.USER, content=request.message, timestamp=datetime.now())
        session.conversation_history.append(user_message)
        
        messages = self._prepare_messages(session)
        response = await self._get_ai_response(messages, session)
            
        assistant_message = ChatMessage(
            role=MessageRole.ASSISTANT,
            content=response["content"],
            timestamp=datetime.now(),
            metadata=response.get("metadata", {})
        )
        session.conversation_history.append(assistant_message)
        self._update_session(session)
            
        return ChatResponse(
            message=response["content"],
            session_id=request.session_id,
            timestamp=datetime.now(),
            function_calls=response.get("function_calls", []),
            recommendations=response.get("recommendations", []),
            metadata=response.get("metadata", {})
        )
    
    async def process_chat_streaming(self, request: ChatRequest) -> AsyncGenerator[StreamingChatResponse, None]:
        """Stream assistant response back to the client in small chunks.

        For now we generate the full response with the non-streaming logic (which
        already handles tool-calls, catalogue recommendations, etc.) and then
        yield it to the caller in ~150-character chunks so the WordPress chat
        widget can progressively render the answer.  This keeps the business
        logic unchanged while restoring a good user-experience.

        When the underlying OpenAI call is later migrated to native token level
        streaming we can swap the chunking implementation without impacting the
        frontend contract.
        """

        session = self.get_or_create_session(request.session_id)
        user_message = ChatMessage(role=MessageRole.USER, content=request.message, timestamp=datetime.now())
        session.conversation_history.append(user_message)
            
        try:
            # Phase 1: Initial response with tools
            messages = self._prepare_messages_streaming(session)  # Use streaming-specific prompt
            initial_response = await self._get_initial_response(messages, session)
            content = initial_response["content"]
            tool_calls = initial_response.get("tool_calls", [])

            tool_results = []
            follow_up_generator = None
            if tool_calls:
                # Add the assistant message with tool_calls to history
                assistant_msg = {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls
                }
                messages.append(assistant_msg)
                tool_results, follow_up_generator = await self._process_tool_calls(tool_calls, messages, session)

            # Create assistant message in history (but mark as streaming/incomplete)
            assistant_message = ChatMessage(
                role=MessageRole.ASSISTANT,
                content="",  # will be filled incrementally
                timestamp=datetime.now(),
                metadata=initial_response.get("metadata", {})
            )
            session.conversation_history.append(assistant_message)

            # Stream the follow-up summary token-by-token if tools were called, else yield initial content as summary (chunk if long)
            accumulated_summary = ""
            if follow_up_generator:
                async for token in follow_up_generator:
                    accumulated_summary += token
                    yield StreamingChatResponse(
                        message=token,
                        session_id=request.session_id,
                        timestamp=datetime.now(),
                        is_streaming_chunk=True,
                        metadata={"phase": "initial_summary"}
                    )
                content = accumulated_summary  # Use streamed content as summary
            else:
                # No tools: yield initial content as summary (chunk if long)
                chunk_size = 150
                if len(content) > chunk_size:
                    for i in range(0, len(content), chunk_size):
                        chunk = content[i : i + chunk_size]
                        accumulated_summary += chunk
                        assistant_message.content = accumulated_summary  # partial update
                        yield StreamingChatResponse(
                            message=chunk,
                            session_id=request.session_id,
                            timestamp=datetime.now(),
                            is_streaming_chunk=True,
                            metadata={"phase": "initial_summary"}
                        )
                else:
                    yield StreamingChatResponse(
                        message=content,
                        session_id=request.session_id,
                        timestamp=datetime.now(),
                        is_streaming_chunk=True,
                        metadata={"phase": "initial_summary"}
                    )
                    accumulated_summary = content
            assistant_message.content = accumulated_summary

            accumulated_recommendations = ""
            full_content = content

            # Check if we need recommendations phase
            if self._needs_recommendations(tool_results):  # Change to tool_results (executed)
                # Phase 2: Thinking message
                async for thinking_chunk in self._stream_thinking_response(request.session_id):
                    yield thinking_chunk
                
                # Phase 3: Streaming recommendations
                # Yield a starter for new bubble
                yield StreamingChatResponse(
                    message="",
                    session_id=request.session_id,
                    timestamp=datetime.now(),
                    is_streaming_chunk=False,
                    metadata={"phase": "recommendations"}
                )
                async for text_chunk in self._generate_recommendations_streaming(session, request.message):
                    accumulated_recommendations += text_chunk
                    yield StreamingChatResponse(
                        message=text_chunk,
                        session_id=request.session_id,
                        timestamp=datetime.now(),
                        is_streaming_chunk=True,
                        metadata={"phase": "recommendations"}
                    )
                full_content = f"{content}\n\n{accumulated_recommendations}"

            # Finalize with full_content
            assistant_message.content = full_content
            self._update_session(session)

            yield StreamingChatResponse(
                message="",
                session_id=request.session_id,
                timestamp=datetime.now(),
                is_final=True,
                function_calls=tool_results,  # Use executed results
                recommendations=initial_response.get("recommendations"),
                metadata={"phase": "final", "model": self.model}
            )
                        
        except Exception as e:
            logger.error("Streaming chat error", exc_info=True)
            yield self._create_error_response(request.session_id, str(e))
    
    async def _get_ai_response(self, messages: List[Dict[str, str]], session: SessionInfo) -> Dict[str, Any]:
        last_user_content = self._get_last_user_message(messages)
        initial_response = await self._make_initial_api_call(messages)
        content = initial_response["content"]
        tool_calls = initial_response["tool_calls"]
        
        tool_calls_list = []
        
        if tool_calls:
            # Add the assistant message with tool_calls to history
            assistant_msg = {
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls
            }
            messages.append(assistant_msg)
            tool_calls_list, new_content = await self._process_tool_calls(tool_calls, messages, session)
            content = new_content or content
        
        if tool_calls_list and self._has_load_calculation(tool_calls_list):
            thinking_message = "\n\n🤔 Let me analyze available options...\n\n"
            content_with_thinking = (content or "") + thinking_message
            catalog_recommendations = "".join([chunk async for chunk in self._generate_catalog_recommendations_only(session, last_user_content, "")])
            final_content = content_with_thinking + catalog_recommendations
        else:
            final_content = content
        
        return {"content": final_content, "tool_calls": tool_calls_list, "recommendations": [], "metadata": {"model": self.model}}
    
    async def _get_initial_response(self, messages: List[Dict], session: SessionInfo) -> Dict:
        tools = self._get_tool_definitions()
        params = self._get_completion_params(self.model, messages, DEFAULT_MAX_TOKENS)
        params.update({"tools": tools, "tool_choice": "auto", "stream": True})
        accumulated_content = ""
        tool_call_dicts = {}  # Use dict with index as key to merge deltas
        async for chunk in await self._make_api_call_with_retry(**params):
            delta = chunk.choices[0].delta
            if delta.content:
                accumulated_content += delta.content or ""
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    index = tc_delta.index
                    if index not in tool_call_dicts:
                        tool_call_dicts[index] = {
                            "id": tc_delta.id,
                            "type": tc_delta.type,
                            "function": {
                                "name": tc_delta.function.name or "",
                                "arguments": tc_delta.function.arguments or ""
                            }
                        }
                    else:
                        if tc_delta.function.name:
                            tool_call_dicts[index]["function"]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_call_dicts[index]["function"]["arguments"] += tc_delta.function.arguments
        tool_calls = list(tool_call_dicts.values())
        return {"content": accumulated_content, "tool_calls": tool_calls}
    
    def _get_last_user_message(self, messages: List[Dict[str, str]]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "") or ""
        return ""
    
    async def _make_initial_api_call(self, messages: List[Dict[str, str]]):
        tools = self._get_tool_definitions()
        params = self._get_completion_params(self.model, messages, DEFAULT_MAX_TOKENS)
        params.update({"tools": tools, "tool_choice": "auto", "stream": True})
        
        accumulated_content = ""
        tool_call_dicts = {}  # Use dict with index as key to merge deltas
        async for chunk in await self._make_api_call_with_retry(**params):
            delta = chunk.choices[0].delta
            if delta.content:
                accumulated_content += delta.content or ""
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    index = tc_delta.index
                    if index not in tool_call_dicts:
                        tool_call_dicts[index] = {
                            "id": tc_delta.id,
                            "type": tc_delta.type,
                            "function": {
                                "name": tc_delta.function.name or "",
                                "arguments": tc_delta.function.arguments or ""
                            }
                        }
                    else:
                        if tc_delta.function.name:
                            tool_call_dicts[index]["function"]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_call_dicts[index]["function"]["arguments"] += tc_delta.function.arguments
        tool_calls = list(tool_call_dicts.values())
        return {"content": accumulated_content, "tool_calls": tool_calls}
                
    async def _process_tool_calls(self, tool_calls, messages: List[Dict], session: SessionInfo) -> Tuple[List[Dict], AsyncGenerator[str, None]]:
        tool_results = []
        for tc in tool_calls:
            func_name = tc["function"]["name"]
            func_args_str = tc["function"]["arguments"]
            try:
                func_args = json.loads(func_args_str)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in tool arguments: {func_args_str}")
                continue  # Skip invalid tool calls
            result = self._execute_tool_function(func_name, func_args, session)
            tool_results.append({"name": func_name, "arguments": func_args, "result": result})
            messages.append({"role": "tool", "tool_call_id": tc["id"], "name": func_name, "content": json.dumps(result)})
        
        params = self._get_completion_params(self.model, messages, DEFAULT_MAX_TOKENS)
        params["stream"] = True  # Enable streaming for follow-up
        
        async def stream_follow_up_content():
            async for chunk in await self._make_api_call_with_retry(**params):
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        
        return tool_results, stream_follow_up_content()
    
    async def _generate_catalog_recommendations_only(self, session: SessionInfo, last_user_content: str, fallback_content: str) -> AsyncGenerator[str, None]:
        load_info = self._get_latest_load_info(session)
        if not load_info:
            yield fallback_content
            return
        
        preferred_types = self._detect_preferred_types(last_user_content)
        catalog = self.tools.get_catalog_with_effective_capacity(include_pool_safe_only=load_info["pool_required"])
        if preferred_types: catalog = [p for p in catalog if p.get("type") in preferred_types]
        
        catalog_data = {
            "required_load_lpd": load_info["latentLoad_L24h"],
            "room_area_m2": load_info["room_area_m2"],
            "pool_area_m2": load_info["pool_area_m2"],
            "pool_required": load_info["pool_required"],
            "preferred_types": preferred_types,
            "catalog": catalog,
        }

        catalog_json = json.dumps(catalog_data, ensure_ascii=False)

        catalog_request = (
            "Using ONLY the products provided in the JSON catalog below, "
            f"recommend exactly 2-3 unique, non-repeating options that can handle roughly {load_info['latentLoad_L24h']} L/day latent load. Output the list only once, without repetition. "
            "Each option should use as few units as possible (prefer single unit if viable, or minimal combinations to meet/exceed load with little margin; slight undershoot OK if within 10%, max overshoot 20%). "
            "Be dynamic with combos (e.g., for 330L/day: 2x150 + 1x50 or 1x150 + 2x100, if same brand). "
            "Stick to the same brand per recommendation (no mixing brands in one option). "
            "Prioritize pool-safe if pool_required is true, and match preferred_types if specified. "
            "Format as a spaced Markdown list with detailed reasons:\n\n"
            "- **Option 1: Brand Name**\n  - Units: Xx SKU: name (type, capacity L/day, price AUD)\n  - Total Capacity: Y L/day (Z% margin)\n  - Reason: Detailed explanation why this combo fits, pros/cons.\n  - Pool-safe: yes/no\n  - [View Product](url)\n\n"
        )

        thinking_messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "system", "content": f"AVAILABLE_PRODUCT_CATALOG_JSON = {catalog_json}"},
            {"role": "user", "content": last_user_content},
            {"role": "assistant", "content": f"Calculated latent load: {load_info['latentLoad_L24h']} L/day"},
            {"role": "user", "content": catalog_request},
        ]

        params = self._get_completion_params(self.thinking_model, thinking_messages, THINKING_MODEL_MAX_TOKENS)
        params["stream"] = True
        async for chunk in await self._make_api_call_with_retry(**params):
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [
            {"type": "function", "function": { "name": "calculate_dehum_load", "description": "Calculate latent moisture load for a room based on sizing spec v0.1", "parameters": { "type": "object", "properties": { "length": {"type": "number"}, "width": {"type": "number"}, "height": {"type": "number"}, "currentRH": {"type": "number"}, "targetRH": {"type": "number"}, "indoorTemp": {"type": "number"}, "ach": {"type": "number"}, "peopleCount": {"type": "number"}, "pool_area_m2": {"type": "number"}, "waterTempC": {"type": "number"}}, "required": ["length", "width", "height", "currentRH", "targetRH", "indoorTemp"]}}}
        ]
    
    def _has_load_calculation(self, tool_calls_list: List[Dict]) -> bool:
        return any(call.get("name") == "calculate_dehum_load" for call in tool_calls_list)
    
    def _get_latest_load_info(self, session: SessionInfo) -> Optional[Dict[str, Any]]:
        for cache_key, result in reversed(list(session.tool_cache.items())):
            if 'calculate_dehum_load' in cache_key:
                try:
                    args = json.loads(cache_key.split('|', 1)[1])
                    return {"latentLoad_L24h": result.get('latentLoad_L24h'), "room_area_m2": result.get('room_area_m2'), "volume": result.get('volume'), "pool_area_m2": args.get('pool_area_m2', 0), "pool_required": args.get('pool_area_m2', 0) > 0}
                except (json.JSONDecodeError, IndexError): continue
        return None

    def _detect_preferred_types(self, text: str) -> List[str]:
        if not text: return []
        text_lower = text.lower()
        types = []
        if "ducted" in text_lower: types.append("ducted")
        if "wall" in text_lower: types.append("wall_mount")
        if "portable" in text_lower: types.append("portable")
        return types
    
    def get_session_info(self, session_id: str) -> SessionInfo:
        if session_id not in self.sessions: raise ValueError(f"Session {session_id} not found")
        return self.sessions[session_id]
    
    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.conversation_history, session.message_count, session.tool_cache = [], 0, {}
            self._set_streaming_state(session, False)
    
    def _is_session_stuck_streaming(self, session: SessionInfo) -> bool:
        if not session.is_streaming: return False
        if session.streaming_start_time and (datetime.now() - session.streaming_start_time).total_seconds() > STREAMING_TIMEOUT_SECONDS:
            logger.warning(f"Session {session.session_id} streaming timeout")
            return True
        return False
    
    def _set_streaming_state(self, session: SessionInfo, is_streaming: bool):
        session.is_streaming = is_streaming
        session.streaming_start_time = datetime.now() if is_streaming else None
        logger.debug(f"Session {session.session_id} streaming state: {is_streaming}")
    
    def _create_abort_response(self, session_id: str) -> StreamingChatResponse:
        if session_id in self.sessions: self._set_streaming_state(self.sessions[session_id], False)
        message = "⚠️ **Session Recovery Needed**\n\nYour session was stuck but has been cleared. Please resend your message."
        return StreamingChatResponse(message=message, session_id=session_id, timestamp=datetime.now(), is_final=True, metadata={"recovery": True})

    def get_health_status(self) -> Dict[str, Any]:
        return {"active_sessions": len(self.sessions), "model": self.model, "tools_loaded": len(self.tools.get_available_tools()), "status": "healthy"}
    
    def get_available_models(self) -> List[str]:
        return [self.model, self.thinking_model]

    @staticmethod
    def _is_retryable_error_static(error: Exception) -> bool:
        err = str(error).lower()
        return any(k in err for k in ("rate limit", "429", "connection", "timeout", "network", "502", "503", "504", "service unavailable", "internal server error"))
        
    @retry(retry=retry_if_exception(_is_retryable_error_static), stop=stop_after_attempt(MAX_RETRIES + 1), wait=wait_exponential_jitter(RETRY_DELAY_BASE, MAX_RETRY_DELAY), reraise=True)
    async def _call_openai(self, **params):
        return await litellm.acompletion(**params)
                
    async def _make_api_call_with_retry(self, **params):
        return await self._call_openai(**params)

    def _update_session(self, session: SessionInfo):
        try:
            session.last_activity = datetime.now()
            session.message_count += 2
            self.session_store.save(session)
        except Exception as e:
            logger.critical("SESSION UPDATE ERROR", exc_info=True)

    def _prepare_messages(self, session: SessionInfo) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        if session.tool_cache:
            context_info = self._build_context_from_cache(session.tool_cache)
            if context_info: messages.append({"role": "system", "content": f"PREVIOUS SESSION DATA:\n{context_info}"})
        
        for msg in session.conversation_history:
            try:
                message_dict = {"role": msg.role.value, "content": msg.content}
                if msg.tool_calls: message_dict["tool_calls"] = msg.tool_calls
                messages.append(message_dict)
            except Exception:
                logger.critical("MESSAGE PREPARATION ERROR", exc_info=True)
                continue
        return messages

    def _build_context_from_cache(self, tool_cache: Dict[str, Any]) -> str:
        if not tool_cache: return ""
        lines = []
        for key, result in tool_cache.items():
            if 'calculate_dehum_load' in key:
                try:
                    args = json.loads(key.split('|', 1)[1])
                    lines.append(f"Load Calc: Pool={args.get('pool_area_m2',0)}m², Load={result.get('latentLoad_L24h','N/A')}L/day")
                except (json.JSONDecodeError, IndexError): continue
        return "\n".join(lines)
    
    def get_or_create_session(self, session_id: str) -> SessionInfo:
        if session_id in self.sessions:
            return self.sessions[session_id]
        
        session = self.session_store.load(session_id)
        if session:
            self.sessions[session_id] = session
            return session
        
        new_session = SessionInfo(
                    session_id=session_id,
            conversation_history=[],
            created_at=datetime.now(),
            last_activity=datetime.now(),
            message_count=0
        )
        self.sessions[session_id] = new_session
        return new_session

    def _create_error_response(self, session_id: str, error: str) -> StreamingChatResponse:
        return StreamingChatResponse(
            message=f"I apologize, but an error occurred: {error}",
                session_id=session_id,
                timestamp=datetime.now(),
            is_final=True,
            metadata={"error": error}
        )

    def _execute_tool_function(self, func_name: str, func_args: Dict, session: SessionInfo) -> Dict:
        cache_key = self._make_tool_key(func_name, func_args)
        if cache_key in session.tool_cache:
            return session.tool_cache[cache_key]
        result = self.tools.calculate_dehum_load(**func_args) if func_name == 'calculate_dehum_load' else {}
        session.tool_cache[cache_key] = result
        return result

    def _prepare_messages_streaming(self, session: SessionInfo) -> List[Dict]:
        messages = [{"role": "system", "content": self.get_streaming_system_prompt()}]
        for msg in session.conversation_history[-MAX_CONVERSATION_HISTORY:]:
            messages.append({"role": msg.role.value, "content": msg.content})
        return messages

    def _needs_recommendations(self, tool_calls_list: List[Any]) -> bool:
        return any(tc.get("name") == "calculate_dehum_load" for tc in tool_calls_list if isinstance(tc, dict))

    async def _stream_thinking_response(self, session_id: str) -> AsyncGenerator[StreamingChatResponse, None]:
        thinking_message = "🤔 Let me analyze the available options..."
        for char in thinking_message:
            yield StreamingChatResponse(
                message=char,
                session_id=session_id,
                timestamp=datetime.now(),
                is_thinking=True,
                is_final=False
            )
            await asyncio.sleep(0.03)
        yield StreamingChatResponse(
            message=thinking_message,
            session_id=session_id,
            timestamp=datetime.now(),
            is_thinking=True,
            is_final=False,
            metadata={"phase": "thinking_complete"}
        )

    async def _generate_recommendations_streaming(self, session: SessionInfo, last_user_content: str) -> AsyncGenerator[str, None]:
        load_info = self._get_latest_load_info(session)
        if not load_info:
            yield ""
            return
        
        preferred_types = self._detect_preferred_types(last_user_content)
        catalog = self.tools.get_catalog_with_effective_capacity(include_pool_safe_only=load_info["pool_required"])
        if preferred_types: catalog = [p for p in catalog if p.get("type") in preferred_types]
            
        catalog_data = {
            "required_load_lpd": load_info["latentLoad_L24h"],
            "room_area_m2": load_info["room_area_m2"],
            "pool_area_m2": load_info["pool_area_m2"],
            "pool_required": load_info["pool_required"],
            "preferred_types": preferred_types,
            "catalog": catalog,
        }

        catalog_json = json.dumps(catalog_data, ensure_ascii=False)

        catalog_request = (
            "Using ONLY the products provided in the JSON catalog below, "
            f"recommend exactly 2-3 unique, non-repeating options that can handle roughly {load_info['latentLoad_L24h']} L/day latent load. Output the list only once, without repetition. "
            "Each option should use as few units as possible (prefer single unit if viable, or minimal combinations to meet/exceed load with little margin; slight undershoot OK if within 10%, max overshoot 20%). "
            "Be dynamic with combos (e.g., for 330L/day: 2x150 + 1x50 or 1x150 + 2x100, if same brand). "
            "Stick to the same brand per recommendation (no mixing brands in one option). "
            "Prioritize pool-safe if pool_required is true, and match preferred_types if specified. "
            "Format as a spaced Markdown list with detailed reasons:\n\n"
            "- **Option 1: Brand Name**\n  - Units: Xx SKU: name (type, capacity L/day, price AUD)\n  - Total Capacity: Y L/day (Z% margin)\n  - Reason: Detailed explanation why this combo fits, pros/cons.\n  - Pool-safe: yes/no\n  - [View Product](url)\n\n"
        )

        thinking_messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "system", "content": f"AVAILABLE_PRODUCT_CATALOG_JSON = {catalog_json}"},
            {"role": "user", "content": last_user_content},
            {"role": "assistant", "content": f"Calculated latent load: {load_info['latentLoad_L24h']} L/day"},
            {"role": "user", "content": catalog_request},
        ]

        params = self._get_completion_params(self.thinking_model, thinking_messages, THINKING_MODEL_MAX_TOKENS)
        params["stream"] = True
        async for chunk in await self._make_api_call_with_retry(**params):
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _save_session_to_wp(self, session_id: str, history: List[ChatMessage]):
        # Implement WP save logic from old file
        pass  # Placeholder

    def get_tool_definitions(self) -> List[Dict]:
        return [
            {"type": "function", "function": {"name": "get_product_manual", "parameters": {"type": "object", "properties": {"sku": {"type": "string"}}}}},
            # Add other tools
        ]