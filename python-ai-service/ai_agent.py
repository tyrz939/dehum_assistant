### TLDR Update of Code Changes
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
import re
import tiktoken

# Configuration constants
MAX_CONVERSATION_HISTORY = 5
DEFAULT_MAX_TOKENS = 80000
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0
MAX_RETRY_DELAY = 60.0
STREAMING_TIMEOUT_SECONDS = 300

MODEL_TOKEN_LIMITS = {
    "gpt-4": 16384,
    "gpt-4o": 128000,
    "gpt-4-turbo": 128000,
}

logger = logging.getLogger(__name__)

class DehumidifierAgent:
    """Main AI agent for dehumidifier assistance"""

    def __init__(self):
        self.sessions: Dict[str, SessionInfo] = {}
        self.tools = DehumidifierTools()
        self.model = self._validate_model(config.DEFAULT_MODEL, "DEFAULT_MODEL")
        self.temperature = config.TEMPERATURE
        self.wp_ajax_url = config.WORDPRESS_URL + "/wp-admin/admin-ajax.php"
        self.wp_api_key = os.getenv("WP_API_KEY")
        
        # Initialize debug mode before setup methods that use it
        self.debug_mode = os.getenv('DEBUG', '').lower() == 'true'
        self._setup_litellm()
        self._init_token_encoder()
        
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
        
    def _init_token_encoder(self):
        """Initialize tiktoken encoder based on the model"""
        try:
            if self.model.startswith('gpt-4o') or self.model.startswith('gpt-4-turbo'):
                self.encoder = tiktoken.encoding_for_model("gpt-4")  # gpt-4o uses gpt-4 encoding
            elif self.model.startswith('gpt-4'):
                self.encoder = tiktoken.encoding_for_model("gpt-4")
            elif self.model.startswith('gpt-3.5'):
                self.encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")
            else:
                # Fallback to cl100k_base encoding for unknown models
                self.encoder = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(f"Failed to initialize tiktoken encoder: {e}, using cl100k_base")
            self.encoder = tiktoken.get_encoding("cl100k_base")
    
    def _count_tokens(self, messages: List[Dict]) -> int:
        """Count tokens in messages using tiktoken"""
        try:
            token_count = 0
            for message in messages:
                # Count tokens for role and content
                if isinstance(message.get('content'), str):
                    token_count += len(self.encoder.encode(message['content']))
                token_count += len(self.encoder.encode(message.get('role', '')))
                
                # Count tokens for tool calls if present
                if 'tool_calls' in message:
                    for tool_call in message['tool_calls']:
                        if isinstance(tool_call, dict):
                            token_count += len(self.encoder.encode(str(tool_call)))
                
                # Add some overhead tokens per message (based on OpenAI's token counting)
                token_count += 4  # Every message has some overhead
            
            # Add some tokens for the conversation structure
            token_count += 2  # priming tokens
            return token_count
        except Exception as e:
            logger.warning(f"Token counting failed: {e}")
            return 0
    
    def _count_response_tokens(self, content: str) -> int:
        """Count tokens in a response string"""
        try:
            return len(self.encoder.encode(content))
        except Exception as e:
            logger.warning(f"Response token counting failed: {e}")
            return 0
        
    def _validate_model(self, model: str, env_var_name: str) -> str:
        if model is None:
            raise ValueError(f"{env_var_name} environment variable is required but not set")
        return model
        
    def _setup_litellm(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not found in environment variables")
        
        if self.debug_mode:
            os.environ['LITELLM_LOG'] = 'DEBUG'
        litellm.set_verbose = False
        
    def _make_tool_key(self, name: str, args: Dict[str, Any]) -> str:
        try:
            return name + "|" + json.dumps(args, sort_keys=True, separators=(",", ":"))
        except TypeError:
            return name + "|" + str(args)
            
    def _get_temperature(self, model: str) -> float:
        return self.temperature
        
    def _cap_max_tokens(self, model: str, requested: int) -> int:
        for prefix, limit in MODEL_TOKEN_LIMITS.items():
            if model.startswith(prefix):
                return min(requested, limit)
        return min(requested, 16000)
        
    def _get_completion_params(self, model: str, messages: List[Dict], max_tokens: int) -> Dict[str, Any]:
        params = {
            "model": model,
            "messages": messages,
            "max_tokens": self._cap_max_tokens(model, DEFAULT_MAX_TOKENS),
        }
        params["temperature"] = self._get_temperature(model)
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
        """Stream assistant response back to the client in small chunks."""

        session = self.get_or_create_session(request.session_id)
        user_message = ChatMessage(role=MessageRole.USER, content=request.message, timestamp=datetime.now())
        session.conversation_history.append(user_message)
            
        try:
            # Phase 1: Initial response with tools
            messages = self._prepare_messages_streaming(session)  # Use streaming-specific prompt
            initial_response = await self._get_initial_completion(messages)
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
                tool_results, follow_up_generator = await self._process_tool_calls(tool_calls, messages, session, request.message)

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

            # Finalize with full_content
            assistant_message.content = accumulated_summary
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
        initial_response = await self._get_initial_completion(messages)
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
            tool_calls_list, new_content = await self._process_tool_calls(tool_calls, messages, session, last_user_content)
            content = new_content or content
        
        return {"content": content, "tool_calls": tool_calls_list, "recommendations": [], "metadata": {"model": self.model}}
    
    async def _get_initial_completion(self, messages: List[Dict]) -> Dict:
        tools = self._get_tool_definitions()
        params = self._get_completion_params(self.model, messages, DEFAULT_MAX_TOKENS)
        params.update({"tools": tools, "tool_choice": "auto", "stream": True})
        
        # Count input tokens
        input_tokens = self._count_tokens(messages)
        if self.debug_mode:
            print(f"DEBUG: Input tokens: {input_tokens}")
        
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
        
        # Count output tokens
        output_tokens = self._count_response_tokens(accumulated_content)
        for tool_call in tool_calls:
            # Count tokens in tool call arguments
            if tool_call.get("function", {}).get("arguments"):
                output_tokens += self._count_response_tokens(tool_call["function"]["arguments"])
        
        if self.debug_mode:
            print(f"DEBUG: Output tokens: {output_tokens}")
            print(f"DEBUG: Total tokens: {input_tokens + output_tokens}")
        
        return {"content": accumulated_content, "tool_calls": tool_calls}
    
    def _get_last_user_message(self, messages: List[Dict[str, str]]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "") or ""
        return ""
    
    async def _process_tool_calls(self, tool_calls, messages: List[Dict], session: SessionInfo, last_user_content: str) -> Tuple[List[Dict], AsyncGenerator[str, None]]:
        tool_results = []
        for tc in tool_calls:
            func_name = tc["function"]["name"]
            try:
                func_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in tool arguments: {tc['function']['arguments']}")
                continue  # Skip invalid tool calls
            result = self._execute_tool_function(func_name, func_args, session)
            tool_results.append({"name": func_name, "arguments": func_args, "result": result})
            messages.append({"role": "tool", "tool_call_id": tc["id"], "name": func_name, "content": json.dumps(result)})

        # If load calculation was performed, inject catalog JSON and recommendation instructions
        load_info = self._get_latest_load_info(session)
        if load_info:
            preferred_types = self._detect_preferred_types(last_user_content)
            catalog = self.tools.get_catalog_with_effective_capacity(include_pool_safe_only=load_info["pool_required"])
            if preferred_types:
                catalog = [p for p in catalog if p.get("type") in preferred_types]

            temp, rh = self._extract_temp_rh(session.conversation_history)
            print(self._extract_temp_rh(session.conversation_history))
            derate_factor = min(1.0, max(0.3, (temp / 30) ** 1.5 * (rh / 80) ** 2))
            for p in catalog:
                if "effective_capacity_lpd" in p:
                    p["effective_capacity_lpd"] = round(p["effective_capacity_lpd"] * derate_factor, 1)
            
            catalog_data = {
                "required_load_lpd": load_info["latentLoad_L24h"],
                "room_area_m2": load_info["room_area_m2"],
                "pool_area_m2": load_info["pool_area_m2"],
                "pool_required": load_info["pool_required"],
                "preferred_types": preferred_types,
                "catalog": catalog,
            }

            catalog_json = json.dumps(catalog_data, ensure_ascii=False)

            # Add catalog to context
            messages.append({"role": "system", "content": f"AVAILABLE_PRODUCT_CATALOG_JSON = {catalog_json}"})


        
        params = self._get_completion_params(self.model, messages, DEFAULT_MAX_TOKENS)
        params["stream"] = True  # Enable streaming for follow-up
        
        # Count input tokens for follow-up call
        follow_up_input_tokens = self._count_tokens(messages)
        if self.debug_mode:
            print(f"DEBUG: Follow-up input tokens: {follow_up_input_tokens}")
        
        async def stream_follow_up_content():
            follow_up_content = ""
            async for chunk in await self._make_api_call_with_retry(**params):
                if chunk.choices[0].delta.content:
                    content_chunk = chunk.choices[0].delta.content
                    follow_up_content += content_chunk
                    yield content_chunk
            
            # Count output tokens for follow-up
            if self.debug_mode and follow_up_content:
                follow_up_output_tokens = self._count_response_tokens(follow_up_content)
                print(f"DEBUG: Follow-up output tokens: {follow_up_output_tokens}")
                print(f"DEBUG: Follow-up total tokens: {follow_up_input_tokens + follow_up_output_tokens}")
        
        return tool_results, stream_follow_up_content()
    
    def _get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [
            {"type": "function", "function": { "name": "calculate_dehum_load", "description": "Calculate latent moisture load for a room. Provide either (length, width, height) OR volume_m3", "parameters": { "type": "object", "properties": { "currentRH": {"type": "number"}, "targetRH": {"type": "number"}, "indoorTemp": {"type": "number"}, "length": {"type": "number"}, "width": {"type": "number"}, "height": {"type": "number"}, "volume_m3": {"type": "number"}, "ach": {"type": "number"}, "peopleCount": {"type": "number"}, "pool_area_m2": {"type": "number"}, "waterTempC": {"type": "number"}}, "required": ["currentRH", "targetRH", "indoorTemp"]}}}
        ]
    
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
    
    def _extract_temp_rh(self, history: List[ChatMessage]) -> Tuple[float, float]:
        user_texts = [m.content.lower() for m in history if m.role == MessageRole.USER]
        full_text = ' '.join(user_texts)

        # Find temp
        temp_pattern = r'(\d+(?:-\d+)?)\s*(?:°?c|degrees?|temp(?:erature)?|celsius|c)'
        temps = re.findall(temp_pattern, full_text)
        temp = 30.0
        if temps:
            last_temp_str = temps[-1]
            if '-' in last_temp_str:
                parts = last_temp_str.split('-')
                if len(parts) == 2:
                    try:
                        high = float(parts[1])
                        temp = high  # peak
                    except ValueError:
                        pass
            else:
                try:
                    temp = float(last_temp_str)
                except ValueError:
                    pass

        # Find RH - look for both current and target values
        current_rh = None
        target_rh = None
        
        # First, look for explicit "from X to Y" patterns - these are most reliable
        from_to_patterns = [
            r'(?:from|reduce\s+from|starting\s+at)\s*(\d+)\s*%\s*(?:to|down\s+to|target\s+of)\s*(\d+)\s*%',
            r'(\d+)\s*%\s*(?:to|down\s+to)\s*(\d+)\s*%'
        ]
        
        for pattern in from_to_patterns:
            matches = re.findall(pattern, full_text)
            if matches:
                try:
                    current_rh = float(matches[-1][0])  # First number is current
                    target_rh = float(matches[-1][1])   # Second number is target
                    break
                except ValueError:
                    pass
        
        # If no from_to pattern found, look for explicit current RH indicators
        if current_rh is None:
            current_patterns = [
                r'current(?:\s+humidity|\s+rh|\s+relative\s+humidity)?\s*(?:is\s*|:\s*)?(\d+)\s*%',
                r'(?:currently|now)\s*(?:at\s*)?(\d+)\s*%',
                r'(\d+)\s*%\s*(?:current|currently|now|right\s+now)',
                r'(?:starts?\s+at|starting\s+at|beginning\s+at)\s*(\d+)\s*%'
            ]
            
            for pattern in current_patterns:
                matches = re.findall(pattern, full_text)
                if matches:
                    try:
                        current_rh = float(matches[-1])
                        break
                    except ValueError:
                        pass
        
        # Look for explicit target RH indicators
        if target_rh is None:
            target_patterns = [
                r'target(?:\s+humidity|\s+rh|\s+relative\s+humidity)?\s*(?:is\s*|of\s*|:\s*)?(\d+)\s*%',
                r'(?:want|need|desire)\s*(?:to\s+get\s+)?\s*(?:to\s*|down\s+to\s*)?(\d+)\s*%',
                r'(\d+)\s*%\s*(?:target|goal|desired|aim)',
                r'(?:bring\s+(?:it\s+)?down\s+to|reduce\s+to|get\s+to)\s*(\d+)\s*%'
            ]
            
            for pattern in target_patterns:
                matches = re.findall(pattern, full_text)
                if matches:
                    try:
                        target_rh = float(matches[-1])
                        break
                    except ValueError:
                        pass
        
        # Fall back to generic RH pattern if no specific patterns found
        if current_rh is None and target_rh is None:
            rh_pattern = r'(\d+)\s*(?:%|rh|humidity|relative\s+humidity)'
            rhs = re.findall(rh_pattern, full_text)
            if rhs:
                try:
                    # If only one RH value found, assume it's current (worst case)
                    current_rh = float(rhs[-1])
                except ValueError:
                    pass
        
        # Set rh based on current_rh if available, else default to 80.0 (ignore target for derate)
        rh = current_rh if current_rh is not None else 80.0
        
        # Debug output
        print(f"DEBUG: Extracted current_rh={current_rh}, target_rh={target_rh}, using rh={rh}")

        return temp, rh
    
    def get_session_info(self, session_id: str) -> SessionInfo:
        if session_id not in self.sessions: raise ValueError(f"Session {session_id} not found")
        return self.sessions[session_id]
    
    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            session = self.sessions[session_id]
            (session.conversation_history, session.message_count, session.tool_cache) = [], 0, {}
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
        return [self.model]

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
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        for msg in session.conversation_history[-MAX_CONVERSATION_HISTORY:]:
            messages.append({"role": msg.role.value, "content": msg.content})
        
        # Inject catalog and recommendation instructions if prior load info exists
        load_info = self._get_latest_load_info(session)
        if load_info:
            user_contents = " ".join([m.content for m in session.conversation_history if m.role == MessageRole.USER])
            preferred_types = self._detect_preferred_types(user_contents)
            catalog = self.tools.get_catalog_with_effective_capacity(include_pool_safe_only=load_info["pool_required"])
            if preferred_types:
                catalog = [p for p in catalog if p.get("type") in preferred_types]
            
            temp, rh = self._extract_temp_rh(session.conversation_history)
            derate_factor = min(1.0, max(0.3, (temp / 30) ** 1.5 * (rh / 80) ** 2))
            for p in catalog:
                if "effective_capacity_lpd" in p:
                    p["effective_capacity_lpd"] = round(p["effective_capacity_lpd"] * derate_factor, 1)
            
            catalog_data = {
                "required_load_lpd": load_info["latentLoad_L24h"],
                "room_area_m2": load_info["room_area_m2"],
                "pool_area_m2": load_info["pool_area_m2"],
                "pool_required": load_info["pool_required"],
                "preferred_types": preferred_types,
                "catalog": catalog,
            }

            catalog_json = json.dumps(catalog_data, ensure_ascii=False)
            messages.append({"role": "system", "content": f"AVAILABLE_PRODUCT_CATALOG_JSON = {catalog_json}"})
            

        
        return messages