"""
Dehumidifier Assistant AI Agent
Handles OpenAI integration, function calling, and conversation management

REFACTORING NOTES (Updated for Strict Environment):
- Assumes all dependencies (tools, engine, etc.) are provided—no defaults.
- Requires WP_API_KEY env var; crashes if unset.
- No input validations or fallbacks; fails fast on invalid states.
- Removed timeouts, redundant try-excepts, and deprecated methods.
- Simplified streaming: No artificial chunking, direct yields (full static content at once, but LLM tokens incremental).
- Enforces RAG always enabled with vectorstore present.
- Maintained state machine but stripped safeties for fixed setup.

TARGETED FIXES APPLIED (Streamlined):
1. Preserve initial content before tools.
2. Yield tool progress directly.
3. Added strict error raising.
4. Strengthened tool defs with exclusive language.

ADDITIONAL UPDATES:
- Used dataclasses and enums as-is.
- Kept asyncio.Lock for concurrency.
- Removed legacy sync methods entirely.
"""

import litellm
import json
import os
import asyncio
from typing import Dict, List, Any, Tuple, AsyncGenerator, Optional
from datetime import datetime
import logging
from enum import Enum
from dataclasses import dataclass

from models import ChatRequest, ChatResponse, ChatMessage, MessageRole, SessionInfo, StreamingChatResponse
from tools import DehumidifierTools
from config import config
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter
from engine import LLMEngine
from tool_executor import ToolExecutor
from session_store import WordPressSessionStore

DEFAULT_MAX_TOKENS = 16000
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0
MAX_RETRY_DELAY = 60.0

logger = logging.getLogger(__name__)


class StreamingPhase(Enum):
    INITIAL = "initial_summary"
    TOOLS = "tools"
    SYNTHESIS = "recommendations"
    FINAL = "final"


@dataclass
class ToolResults:
    tool_results: List[Dict]


class DehumidifierAgent:
    def __init__(
        self,
        tools: DehumidifierTools,
        engine: LLMEngine,
        tool_executor: ToolExecutor,
        session_store: WordPressSessionStore,
    ):
        self.sessions: Dict[str, SessionInfo] = {}
        self.tools = tools
        self.model = config.DEFAULT_MODEL
        self.temperature = config.TEMPERATURE
        self.wp_api_key = os.getenv("WP_API_KEY")
        if not self.wp_api_key:
            raise ValueError("WP_API_KEY environment variable is not set")
        
        self.engine = engine
        self.tool_executor = tool_executor
        self.session_store = session_store
        
        self._session_lock = asyncio.Lock()
            
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
        base_prompt = self._load_prompt_from_file("system_prompt.txt")
        
        tool_guidance = """
## Tool Selection Guidance

You have access to two main tools:

**retrieve_relevant_docs**: Use when users need specific technical information, installation guidance, troubleshooting help, maintenance instructions, specifications, or other details from product manuals and documentation.

**calculate_dehum_load**: Use when users need to determine what size or type of dehumidifier is suitable for their space based on room dimensions, humidity levels, and environmental conditions.

Use your contextual understanding to choose the most appropriate tool based on what the user is asking for. Both tools can work together when needed.

"""
        return tool_guidance + base_prompt

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        async with self._session_lock:
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
        async with self._session_lock:
            session = self.get_or_create_session(request.session_id)
            user_message = ChatMessage(role=MessageRole.USER, content=request.message, timestamp=datetime.now())
            session.conversation_history.append(user_message)
            
            messages = self._prepare_messages_streaming(session)
            assistant_message = ChatMessage(
                role=MessageRole.ASSISTANT,
                content="",
                timestamp=datetime.now(),
                metadata={}
            )
            session.conversation_history.append(assistant_message)
        
        current_phase = StreamingPhase.INITIAL
        tool_results = []
        
        while current_phase != StreamingPhase.FINAL:
            
            if current_phase == StreamingPhase.INITIAL:
                tools = self._get_tool_definitions()
                params = self._get_completion_params(self.model, messages, DEFAULT_MAX_TOKENS)
                params.update({"tools": tools, "tool_choice": "auto", "stream": True})
                
                accumulated_content = ""
                tool_call_dicts = {}
                
                async for chunk in await self._make_api_call_with_retry(**params):
                    delta = chunk.choices[0].delta
                    if delta.content:
                        content_chunk = delta.content
                        accumulated_content += content_chunk
                        yield self._yield_streaming_response(
                            message=content_chunk,
                            session_id=request.session_id,
                            timestamp=datetime.now(),
                            is_streaming_chunk=True,
                            metadata={"phase": StreamingPhase.INITIAL.value}
                        )
                        assistant_message.content += content_chunk
                    if delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            index = tc_delta.index
                            if index not in tool_call_dicts:
                                tool_call_dicts[index] = {
                                    "id": tc_delta.id,
                                    "type": tc_delta.type,
                                    "function": {
                                        "name": tc_delta.function.name,
                                        "arguments": tc_delta.function.arguments
                                    }
                                }
                            else:
                                if tc_delta.function.name:
                                    tool_call_dicts[index]["function"]["name"] += tc_delta.function.name
                                if tc_delta.function.arguments:
                                    tool_call_dicts[index]["function"]["arguments"] += tc_delta.function.arguments
                
                tool_calls = list(tool_call_dicts.values())
                
                current_phase = StreamingPhase.TOOLS if tool_calls else StreamingPhase.FINAL
                
            elif current_phase == StreamingPhase.TOOLS:
                async for response in self._stream_tools_phase(
                    tool_calls, messages, session, request.message, 
                    request.session_id, accumulated_content
                ):
                    if isinstance(response, ToolResults):
                        tool_results = response.tool_results
                    else:
                        yield response
                
                current_phase = StreamingPhase.SYNTHESIS
                
            elif current_phase == StreamingPhase.SYNTHESIS:
                async for chunk in self._stream_follow_up_synthesis(messages, request.session_id):
                    assistant_message.content += chunk.message
                    yield chunk
                
                current_phase = StreamingPhase.FINAL
        
        async with self._session_lock:
            self._update_session(session)
        yield self._yield_streaming_response(
            message="",
            session_id=request.session_id,
            timestamp=datetime.now(),
            is_final=True,
            function_calls=tool_results,
            recommendations=[],
            metadata={"phase": StreamingPhase.FINAL.value, "model": self.model}
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
    
    async def _stream_tools_phase(
        self, 
        tool_calls: List[Dict], 
        messages: List[Dict], 
        session: SessionInfo, 
        last_user_content: str,
        session_id: str,
        initial_content: str = ""
    ) -> AsyncGenerator:
        tool_results = []
        
        assistant_msg = {
            "role": "assistant", 
            "content": initial_content,
            "tool_calls": tool_calls
        }
        messages.append(assistant_msg)
        
        yield self._yield_streaming_response(
            message=f"🔧 Starting {len(tool_calls)} tool{'s' if len(tool_calls) > 1 else ''}...",
            session_id=session_id,
            timestamp=datetime.now(),
            is_streaming_chunk=True,
            metadata={
                "phase": StreamingPhase.TOOLS.value, 
                "status": "starting_tools",
                "tool_count": len(tool_calls)
            }
        )
        
        for i, tc in enumerate(tool_calls):
            func_name = tc["function"]["name"]
            
            yield self._yield_streaming_response(
                message=f"⚙️ Executing tool {i+1}/{len(tool_calls)}: {func_name}",
                session_id=session_id,
                timestamp=datetime.now(),
                is_streaming_chunk=True,
                metadata={
                    "phase": StreamingPhase.TOOLS.value,
                    "status": "executing_tool",
                    "tool_name": func_name,
                    "tool_index": i + 1,
                    "total_tools": len(tool_calls)
                }
            )
            
            func_args = json.loads(tc["function"]["arguments"])
            result = self._execute_tool_function(func_name, func_args, session)
            tool_results.append({
                "name": func_name, 
                "arguments": func_args, 
                "result": result
            })
            
            if func_name == 'retrieve_relevant_docs' and 'formatted_docs' in result:
                content = result['formatted_docs']
            else:
                content = json.dumps(result)
            
            messages.append({
                "role": "tool", 
                "tool_call_id": tc["id"], 
                "name": func_name, 
                "content": content
            })
            
            yield self._yield_streaming_response(
                message=f"✅ Completed tool {i+1}/{len(tool_calls)}: {func_name}",
                session_id=session_id,
                timestamp=datetime.now(),
                is_streaming_chunk=True,
                metadata={
                    "phase": StreamingPhase.TOOLS.value,
                    "status": "tool_completed",
                    "tool_name": func_name,
                    "tool_index": i + 1,
                    "total_tools": len(tool_calls)
                }
            )
        
        load_info = self._get_latest_load_info(session)
        if load_info:
            preferred_types = self._detect_preferred_types(last_user_content)
            catalog_message = self._prepare_catalog_message(load_info, preferred_types)
            messages.append(catalog_message)
            
            product_count = self._compute_product_count(catalog_message)
            
            yield self._yield_streaming_response(
                message=f"📋 Prepared product catalog with {product_count} matching products",
                session_id=session_id,
                timestamp=datetime.now(),
                is_streaming_chunk=True,
                metadata={
                    "phase": StreamingPhase.TOOLS.value,
                    "status": "catalog_prepared",
                    "product_count": product_count
                }
            )
        
        yield ToolResults(tool_results)
    
    def _compute_product_count(self, catalog_message: Dict) -> int:
        catalog_content = catalog_message.get("content", "")
        json_start = catalog_content.find("AVAILABLE_PRODUCT_CATALOG_JSON = ") + len("AVAILABLE_PRODUCT_CATALOG_JSON = ")
        json_end = catalog_content.find("\nWhen recommending", json_start)
        if json_end == -1:
            json_end = len(catalog_content)
        catalog_json = catalog_content[json_start:json_end].strip()
        catalog_data = json.loads(catalog_json)
        return len(catalog_data.get("catalog", []))
    
    async def _stream_follow_up_synthesis(self, messages: List[Dict], session_id: str) -> AsyncGenerator[StreamingChatResponse, None]:
        params = self._get_completion_params(self.model, messages, DEFAULT_MAX_TOKENS)
        params["stream"] = True
        
        async for chunk in await self._make_api_call_with_retry(**params):
            if chunk.choices[0].delta.content:
                content_chunk = chunk.choices[0].delta.content
                yield self._yield_streaming_response(
                    message=content_chunk,
                    session_id=session_id,
                    timestamp=datetime.now(),
                    is_streaming_chunk=True,
                    metadata={"phase": StreamingPhase.SYNTHESIS.value}
                )
    
    def _get_last_user_message(self, messages: List[Dict[str, str]]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""
    
    async def _process_tool_calls(self, tool_calls, messages: List[Dict], session: SessionInfo, last_user_content: str) -> Tuple[List[Dict], AsyncGenerator[str, None]]:
        tool_results = []
        for tc in tool_calls:
            func_name = tc["function"]["name"]
            func_args = json.loads(tc["function"]["arguments"])
            result = self._execute_tool_function(func_name, func_args, session)
            tool_results.append({"name": func_name, "arguments": func_args, "result": result})
            
            if func_name == 'retrieve_relevant_docs' and 'formatted_docs' in result:
                content = result['formatted_docs']
            else:
                content = json.dumps(result)
            
            messages.append({"role": "tool", "tool_call_id": tc["id"], "name": func_name, "content": content})

        load_info = self._get_latest_load_info(session)
        if load_info:
            preferred_types = self._detect_preferred_types(last_user_content)
            catalog_message = self._prepare_catalog_message(load_info, preferred_types)
            messages.append(catalog_message)

        params = self._get_completion_params(self.model, messages, DEFAULT_MAX_TOKENS)
        params["stream"] = True  
        
        async def stream_follow_up_content():
            async for chunk in await self._make_api_call_with_retry(**params):
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        
        return tool_results, stream_follow_up_content()
    
    def _get_tool_definitions(self) -> List[Dict[str, Any]]:
        tools = []
        
        rag_tool = {
            "type": "function", 
            "function": {
                "name": "retrieve_relevant_docs",
                "description": "Retrieve specific technical information from product manuals and documentation. Use this when users need installation guidance, troubleshooting help, maintenance instructions, specifications, error codes, warranty information, or other technical details about specific products. This provides authoritative, accurate information directly from manufacturer documentation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Specific search query for documents (e.g., 'installation steps', 'troubleshooting unit not starting', 'filter maintenance', 'SP500C specifications')"
                        },
                        "k": {
                            "type": "integer",
                            "description": "Number of relevant chunks to retrieve (default 3)",
                            "default": 3
                        }
                    },
                    "required": ["query"]
                }
            }
        }
        tools.append(rag_tool)
        
        catalog_tool = {
            "type": "function", 
            "function": { 
                "name": "get_product_catalog", 
                "description": "Get product catalog with prices and specifications for browsing, comparison, and pricing queries. Use this when users ask about prices, costs, product listings, model comparisons, or want to browse available products. DO NOT use for sizing calculations.",
                "parameters": { 
                    "type": "object", 
                    "properties": { 
                        "capacity_min": {"type": "number", "description": "Minimum capacity in L/day (optional filter)"}, 
                        "capacity_max": {"type": "number", "description": "Maximum capacity in L/day (optional filter)"}, 
                        "product_type": {"type": "string", "enum": ["wall_mount", "ducted", "portable"], "description": "Filter by product type (optional)"}, 
                        "pool_safe_only": {"type": "boolean", "description": "Only return pool-safe models (optional)"}, 
                        "price_range_max": {"type": "number", "description": "Maximum price in AUD (optional filter)"}
                    }, 
                    "required": []
                }
            }
        }
        tools.append(catalog_tool)

        sizing_tool = {
            "type": "function", 
            "function": { 
                "name": "calculate_dehum_load", 
                "description": "Calculate moisture load and recommend appropriate dehumidifier models based on room dimensions, humidity levels, and environmental conditions. Use this when users need to determine what size or type of dehumidifier is suitable for their specific space or application. DO NOT use for pricing queries.",
                "parameters": { 
                    "type": "object", 
                    "properties": { 
                        "currentRH": {"type": "number", "description": "Current relative humidity percentage"}, 
                        "targetRH": {"type": "number", "description": "Target relative humidity percentage"}, 
                        "indoorTemp": {"type": "number", "description": "Indoor temperature in Celsius"}, 
                        "length": {"type": "number", "description": "Room length in meters"}, 
                        "width": {"type": "number", "description": "Room width in meters"}, 
                        "height": {"type": "number", "description": "Room height in meters"}, 
                        "volume_m3": {"type": "number", "description": "Room volume in cubic meters (alternative to length/width/height)"}, 
                        "ach": {"type": "number", "description": "Air changes per hour"}, 
                        "peopleCount": {"type": "number", "description": "Number of people in the space"}, 
                        "pool_area_m2": {"type": "number", "description": "Pool area in square meters if applicable"}, 
                        "waterTempC": {"type": "number", "description": "Water temperature in Celsius for pools"}
                    }, 
                    "required": ["currentRH", "targetRH", "indoorTemp"]
                }
            }
        }
        tools.append(sizing_tool)
        
        return tools
    
    def _get_latest_load_info(self, session: SessionInfo) -> Optional[Dict[str, Any]]:
        for cache_key, result in reversed(list(session.tool_cache.items())):
            if 'calculate_dehum_load' in cache_key:
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
        return None

    def _detect_preferred_types(self, text: str) -> List[str]:
        text_lower = text.lower()
        types = []
        if "ducted" in text_lower: types.append("ducted")
        if "wall" in text_lower: types.append("wall_mount")
        if "portable" in text_lower: types.append("portable")
        return types
    
    def _prepare_catalog_message(self, load_info: Dict[str, Any], preferred_types: List[str]) -> Dict[str, str]:
        catalog = self.tools.get_catalog_with_effective_capacity(include_pool_safe_only=load_info["pool_required"])
        if preferred_types:
            catalog = [p for p in catalog if p.get("type") in preferred_types]

        temp = load_info['indoorTemp']
        rh = load_info['targetRH']
        derate_factor = self.tools.calculate_derate_factor(temp, rh)

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
        return {"role": "system", "content": f"AVAILABLE_PRODUCT_CATALOG_JSON = {catalog_json}\nWhen recommending products, always include the 'url' field as a clickable link in the format: [View](url) for each product, as specified in the FORMAT section."}
    
    def get_session_info(self, session_id: str) -> SessionInfo:
        return self.sessions[session_id]
    
    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            session = self.sessions[session_id]
            (session.conversation_history, session.message_count, session.tool_cache) = [], 0, {}
    
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

    def _enhance_rag_query_with_context(self, query: str, session: SessionInfo) -> str:
        if not session.conversation_history:
            return query
            
        recent_messages = session.conversation_history[-5:]
        product_context = set()
        
        product_patterns = [
            'SP500C', 'SP1000C', 'SP1500C', 'SP500', 'SP1000', 'SP1500',  
            'IDHR60', 'IDHR96', 'IDHR120',  
            'DA-X60i', 'DA-X140i', 'DA-X60', 'DA-X140',  
            'Suntec', 'Fairland', 'Luko',  
            'SP Pro', 'SP series', 'IDHR series', 'DA-X series'  
        ]
        
        for msg in recent_messages:
            if msg.role.value == 'user':
                content_lower = msg.content.lower()
                for pattern in product_patterns:
                    if pattern.lower() in content_lower:
                        product_context.add(pattern)
        
        if product_context:
            specific_models = [p for p in product_context if any(char.isdigit() for char in p)]
            if specific_models:
                most_specific = max(specific_models, key=len)
                enhanced_query = f"{most_specific} {query}"
            else:
                most_relevant = max(product_context, key=len)
                enhanced_query = f"{most_relevant} {query}"
            
            return enhanced_query
        
        return query

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
                args = json.loads(key.split('|', 1)[1])
                lines.append(f"Load Calc: Pool={args.get('pool_area_m2',0)}m², Load={result.get('latentLoad_L24h','N/A')}L/day")
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

    def _execute_tool_function(self, func_name: str, func_args: Dict, session: SessionInfo) -> Dict:
        cache_key = self._make_tool_key(func_name, func_args)
        if cache_key in session.tool_cache:
            return session.tool_cache[cache_key]
        
        if func_name == 'calculate_dehum_load':
            result = self.tools.calculate_dehum_load(**func_args)
        elif func_name == 'get_product_catalog':
            result = self.tools.get_product_catalog(**func_args)
        elif func_name == 'retrieve_relevant_docs':
            query = func_args.get('query', '')
            k = func_args.get('k', 3)
            
            enhanced_query = self._enhance_rag_query_with_context(query, session)
            chunks = self.tools.retrieve_relevant_docs(enhanced_query, k)
            
            if chunks:
                query_info = f"'{enhanced_query}'" if enhanced_query != query else f"'{query}'"
                formatted_content = f"RELEVANT DOCUMENTATION for query {query_info}:\n\n"
                for i, chunk in enumerate(chunks):
                    formatted_content += f"--- Document {i+1} ---\n{chunk}\n\n"
                formatted_content += "END OF DOCUMENTATION\n\nPlease use this information to provide an accurate, specific answer."
                result = {"formatted_docs": formatted_content, "chunks": chunks}
            else:
                query_info = f"'{enhanced_query}'" if enhanced_query != query else f"'{query}'"
                result = {"formatted_docs": f"No relevant documentation found for query {query_info}. I don't have specific information about this topic in my available documentation.", "chunks": []}
        else:
            raise ValueError(f"Unknown tool: {func_name}")
        
        if func_name != 'retrieve_relevant_docs':
            session.tool_cache[cache_key] = result
        
        return result

    def _prepare_messages_streaming(self, session: SessionInfo) -> List[Dict]:
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        
        for msg in session.conversation_history:
            messages.append({"role": msg.role.value, "content": msg.content})
        
        load_info = self._get_latest_load_info(session)
        if load_info:
            preferred_types = self._detect_preferred_types(" ".join([m.content for m in session.conversation_history if m.role == MessageRole.USER]))
            catalog_message = self._prepare_catalog_message(load_info, preferred_types)
            messages.append(catalog_message)
        
        return messages
    
    def _yield_streaming_response(self, **kwargs) -> StreamingChatResponse:
        return StreamingChatResponse(**kwargs)
    
    async def _get_initial_completion(self, messages: List[Dict]) -> Dict:
        tools = self._get_tool_definitions()
        params = self._get_completion_params(self.model, messages, DEFAULT_MAX_TOKENS)
        params.update({"tools": tools, "tool_choice": "auto", "stream": True})
        
        accumulated_content = ""
        tool_call_dicts = {}
        
        async for chunk in await self._make_api_call_with_retry(**params):
            delta = chunk.choices[0].delta
            if delta.content:
                accumulated_content += delta.content
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    index = tc_delta.index
                    if index not in tool_call_dicts:
                        tool_call_dicts[index] = {
                            "id": tc_delta.id,
                            "type": tc_delta.type,
                            "function": {
                                "name": tc_delta.function.name,
                                "arguments": tc_delta.function.arguments
                            }
                        }
                    else:
                        if tc_delta.function.name:
                            tool_call_dicts[index]["function"]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_call_dicts[index]["function"]["arguments"] += tc_delta.function.arguments
        
        tool_calls = list(tool_call_dicts.values())
        
        return {"content": accumulated_content, "tool_calls": tool_calls}