"""
Dehumidifier Assistant AI Agent
Handles OpenAI integration, function calling, and conversation management
"""

import litellm
import json
import os
import asyncio
from typing import Dict, List, Optional, Any, Tuple, AsyncGenerator
from datetime import datetime
import logging
from models import ChatRequest, ChatResponse, ChatMessage, MessageRole, SessionInfo, StreamingChatResponse
from tools import DehumidifierTools
from config import config
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter
from engine import LLMEngine
from tool_executor import ToolExecutor
from session_store import InMemorySessionStore, WordPressSessionStore

DEFAULT_MAX_TOKENS = 16000
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0
MAX_RETRY_DELAY = 60.0
STREAMING_TIMEOUT_SECONDS = 300

logger = logging.getLogger(__name__)

class DehumidifierAgent:
    """Main AI agent for dehumidifier assistance"""

    def __init__(self):
        self.sessions: Dict[str, SessionInfo] = {}
        self.tools = DehumidifierTools()
        self.model = config.DEFAULT_MODEL
        self.temperature = config.TEMPERATURE
        self.wp_api_key = os.getenv("WP_API_KEY")
        
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
            
    def _make_tool_key(self, name: str, args: Dict[str, Any]) -> str:
        return name + "|" + json.dumps(args, sort_keys=True, separators=(",", ":"))
            
    def _get_completion_params(self, model: str, messages: List[Dict], max_tokens: int) -> Dict[str, Any]:
        return {
            "model": model,
            "messages": messages,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "temperature": self.temperature
        }
        
    def _load_prompt_from_file(self, filename: str) -> str:
        prompt_path = os.path.join(os.path.dirname(__file__), "prompts", filename)
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

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
        session = self.get_or_create_session(request.session_id)
        user_message = ChatMessage(role=MessageRole.USER, content=request.message, timestamp=datetime.now())
        session.conversation_history.append(user_message)
            
        messages = self._prepare_messages_streaming(session)
        initial_response = await self._get_initial_completion(messages)
        content = initial_response["content"]
        tool_calls = initial_response.get("tool_calls", [])

        tool_results = []
        follow_up_generator = None
        if tool_calls:
            assistant_msg = {
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls
            }
            messages.append(assistant_msg)
            tool_results, follow_up_generator = await self._process_tool_calls(tool_calls, messages, session, request.message)

        assistant_message = ChatMessage(
            role=MessageRole.ASSISTANT,
            content="",  
            timestamp=datetime.now(),
            metadata=initial_response.get("metadata", {})
        )
        session.conversation_history.append(assistant_message)

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
            content = accumulated_summary  
        else:
            chunk_size = 150
            if len(content) > chunk_size:
                for i in range(0, len(content), chunk_size):
                    chunk = content[i : i + chunk_size]
                    accumulated_summary += chunk
                    assistant_message.content = accumulated_summary  
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

        self._update_session(session)

        yield StreamingChatResponse(
            message="",
            session_id=request.session_id,
            timestamp=datetime.now(),
            is_final=True,
            function_calls=tool_results,  
            recommendations=initial_response.get("recommendations"),
            metadata={"phase": "final", "model": self.model}
        )
                        
    async def _get_ai_response(self, messages: List[Dict[str, str]], session: SessionInfo) -> Dict[str, Any]:
        last_user_content = self._get_last_user_message(messages)
        initial_response = await self._get_initial_completion(messages)
        content = initial_response["content"]
        tool_calls = initial_response["tool_calls"]
        
        tool_calls_list = []
        
        if tool_calls:
            assistant_msg = {
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls
            }
            messages.append(assistant_msg)
            tool_calls_list, follow_up_gen = await self._process_tool_calls(tool_calls, messages, session, last_user_content)
            new_content = ""
            async for token in follow_up_gen:
                new_content += token
            content = new_content or content
        
        return {"content": content, "tool_calls": tool_calls_list, "recommendations": [], "metadata": {"model": self.model}}
    
    async def _get_initial_completion(self, messages: List[Dict]) -> Dict:
        tools = self._get_tool_definitions()
        params = self._get_completion_params(self.model, messages, DEFAULT_MAX_TOKENS)
        params.update({"tools": tools, "tool_choice": "auto", "stream": True})
        
        accumulated_content = ""
        tool_call_dicts = {}
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
    
    async def _process_tool_calls(self, tool_calls, messages: List[Dict], session: SessionInfo, last_user_content: str) -> Tuple[List[Dict], AsyncGenerator[str, None]]:
        tool_results = []
        for tc in tool_calls:
            func_name = tc["function"]["name"]
            try:
                func_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                continue
            result = self._execute_tool_function(func_name, func_args, session)
            tool_results.append({"name": func_name, "arguments": func_args, "result": result})
            messages.append({"role": "tool", "tool_call_id": tc["id"], "name": func_name, "content": json.dumps(result)})

        load_info = self._get_latest_load_info(session)
        if load_info:
            preferred_types = self._detect_preferred_types(last_user_content)
            catalog = self.tools.get_catalog_with_effective_capacity(include_pool_safe_only=load_info["pool_required"])
            if preferred_types:
                catalog = [p for p in catalog if p.get("type") in preferred_types]

            temp = load_info['indoorTemp']
            rh = load_info['targetRH']
            derate_factor = min(1.0, max(0.3, 0.5 + 0.5 * (temp / 30) ** 1.5 * (rh / 80) ** 2))
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

            messages.append({"role": "system", "content": f"AVAILABLE_PRODUCT_CATALOG_JSON = {catalog_json}\nWhen recommending products, always include the 'url' field as a clickable link in the format: [View](url) for each product, as specified in the FORMAT section."})


        
        params = self._get_completion_params(self.model, messages, DEFAULT_MAX_TOKENS)
        params["stream"] = True  
        
        async def stream_follow_up_content():
            follow_up_content = ""
            async for chunk in await self._make_api_call_with_retry(**params):
                if chunk.choices[0].delta.content:
                    content_chunk = chunk.choices[0].delta.content
                    follow_up_content += content_chunk
                    yield content_chunk
        
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
                    return {
                        "latentLoad_L24h": result.get('latentLoad_L24h'),
                        "room_area_m2": result.get('room_area_m2'),
                        "volume": result.get('volume'),
                        "pool_area_m2": args.get('pool_area_m2', 0),
                        "pool_required": args.get('pool_area_m2', 0) > 0,
                        "indoorTemp": args.get('indoorTemp', 30.0),
                        "currentRH": args.get('currentRH', 80.0),
                        "targetRH": args.get('targetRH', 60.0)
                    }
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
        return self.sessions[session_id]
    
    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            session = self.sessions[session_id]
            (session.conversation_history, session.message_count, session.tool_cache) = [], 0, {}
            self._set_streaming_state(session, False)
    
    def _set_streaming_state(self, session: SessionInfo, is_streaming: bool):
        session.is_streaming = is_streaming
        session.streaming_start_time = datetime.now() if is_streaming else None
    
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
        session.last_activity = datetime.now()
        session.message_count += 2
        self.session_store.save(session)

    def _prepare_messages(self, session: SessionInfo) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        if session.tool_cache:
            context_info = self._build_context_from_cache(session.tool_cache)
            if context_info: messages.append({"role": "system", "content": f"PREVIOUS SESSION DATA:\n{context_info}"})
        
        for msg in session.conversation_history:
            message_dict = {"role": msg.role.value, "content": msg.content}
            if msg.tool_calls: message_dict["tool_calls"] = msg.tool_calls
            messages.append(message_dict)
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
        for msg in session.conversation_history:
            messages.append({"role": msg.role.value, "content": msg.content})
        
        load_info = self._get_latest_load_info(session)
        if load_info:
            user_contents = " ".join([m.content for m in session.conversation_history if m.role == MessageRole.USER])
            preferred_types = self._detect_preferred_types(user_contents)
            catalog = self.tools.get_catalog_with_effective_capacity(include_pool_safe_only=load_info["pool_required"])
            if preferred_types:
                catalog = [p for p in catalog if p.get("type") in preferred_types]
            
            temp = load_info['indoorTemp']
            rh = load_info['targetRH']
            derate_factor = min(1.0, max(0.3, 0.5 + 0.5 * (temp / 30) ** 1.5 * (rh / 80) ** 2))
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
            messages.append({"role": "system", "content": f"AVAILABLE_PRODUCT_CATALOG_JSON = {catalog_json}\nWhen recommending products, always include the 'url' field as a clickable link in the format: [View](url) for each product, as specified in the FORMAT section."})
            

        
        return messages