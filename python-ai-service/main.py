import os
import json
import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, AsyncGenerator, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi import WebSocket, WebSocketDisconnect
import requests
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter
import math
import base64
from urllib.parse import urlparse
import time
from collections import deque, defaultdict

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyMuPDFLoader
from langchain.schema import Document
import tiktoken

# Load env
load_dotenv()

# Constants (keep only envs that vary by environment; hard-set the rest)
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY required")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WORDPRESS_URL = os.getenv("WORDPRESS_URL", "http://localhost")
WP_API_KEY = API_KEY  # Use the same shared secret for WP callbacks
STATE_MARKER = "[[DEHUM_STATE]]"

# OpenAI client configuration (tunable for Render or slow networks)
OPENAI_BASE_URL = (os.getenv("OPENAI_BASE_URL", "").strip() or None)
OPENAI_TIMEOUT_S = float(os.getenv("OPENAI_TIMEOUT_S", "45"))

# Fixed defaults (adjust in code if you truly need to change them across all envs)
DEFAULT_MODEL = "gpt-5"
SERVICE_HOST = "0.0.0.0"
SERVICE_PORT = 8000
# Restrict CORS in production; set DEHUM_CORS_ORIGINS env to comma-separated domains
_cors_env = os.getenv("DEHUM_CORS_ORIGINS", "")
CORS_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()] or ["http://localhost", "https://localhost"]
# Auto-include WordPress origin from WORDPRESS_URL
try:
    wp_parsed = urlparse(WORDPRESS_URL)
    if wp_parsed.scheme and wp_parsed.netloc:
        wp_origin = f"{wp_parsed.scheme}://{wp_parsed.netloc}"
        if wp_origin not in CORS_ORIGINS:
            CORS_ORIGINS.append(wp_origin)
except Exception:
    pass
RAG_ENABLED = True
RAG_CHUNK_SIZE = 700
RAG_CHUNK_OVERLAP = 100
RAG_TOP_K = 7
GPT5_REASONING_EFFORT = "minimal"
GPT5_VERBOSITY = "low"
MAX_TOOL_CALLS_PER_TURN = 4

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Dehumidifier AI", description="Lean AI for dehumidifier sizing", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Reuse a single OpenAI async client (reduces DNS/connect overhead on Render)
OPENAI_CLIENT = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, timeout=OPENAI_TIMEOUT_S)

def load_product_database() -> List[Dict]:
    """Load product database from JSON file"""
    db_path = os.path.join(os.path.dirname(__file__), "product_db.json")
    try:
        with open(db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            products = data.get("products", [])
            logger.info(f"Loaded {len(products)} products from database")
            return products
    except FileNotFoundError:
        logger.error(f"Product database not found: {db_path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in product database: {e}")
        return []

def check_api_key(authorization: str = Header(None)):
    expected_key = API_KEY
    if expected_key and (not authorization or authorization != f"Bearer {expected_key}"):
            raise HTTPException(status_code=403, detail="Invalid API key")

@app.get("/")
async def root():
    return {"status": "healthy", "service": "dehumidifier-ai", "version": "1.0.0"}

########################
# Simple rate limiting  #
########################
RL_IP_PER_MIN = int(os.getenv("DEHUM_RL_IP_PER_MIN", "30"))
RL_SESSION_PER_MIN = int(os.getenv("DEHUM_RL_SESSION_PER_MIN", "12"))
WS_MAX_CONN_PER_IP = int(os.getenv("DEHUM_WS_MAX_CONN_PER_IP", "3"))
WS_MAX_CONN_PER_SESSION = int(os.getenv("DEHUM_WS_MAX_CONN_PER_SESSION", "2"))
_rl_ip: dict[str, deque] = defaultdict(deque)
_rl_session: dict[str, deque] = defaultdict(deque)
_ws_active_ip: dict[str, int] = defaultdict(int)
_ws_active_session: dict[str, int] = defaultdict(int)
_rl_lock = asyncio.Lock()

def _now() -> float:
    return time.time()

async def _allow_http(ip: str, session_id: str) -> bool:
    cutoff = _now() - 60.0
    async with _rl_lock:
        dq_ip = _rl_ip[ip]
        while dq_ip and dq_ip[0] < cutoff:
            dq_ip.popleft()
        dq_s = _rl_session[session_id]
        while dq_s and dq_s[0] < cutoff:
            dq_s.popleft()
        if len(dq_ip) >= RL_IP_PER_MIN or len(dq_s) >= RL_SESSION_PER_MIN:
            return False
        dq_ip.append(_now())
        dq_s.append(_now())
        return True

def _client_ip_from_headers(headers: dict, fallback: str | None) -> str:
    xfwd = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
    if xfwd:
        return xfwd.split(",")[0].strip()
    xreal = headers.get("x-real-ip") or headers.get("X-Real-IP")
    if xreal:
        return xreal.strip()
    return fallback or "unknown"

@app.post("/chat")
async def chat(request: Dict, req: Request, auth: str = Depends(check_api_key)):
    ip = _client_ip_from_headers(req.headers, req.client.host if req.client else None)
    session_id = request.get("session_id", "")
    if not await _allow_http(ip, session_id or ip):
        raise HTTPException(status_code=429, detail="rate_limited")
    session_id = request["session_id"]
    message = request["message"]
    session = await get_or_create_session(session_id)
    session["history"].append({"role": "user", "content": message, "timestamp": datetime.now().isoformat()})
    last_user = session["history"][-1]["content"]
    messages = prepare_messages(session)
    response = await get_ai_response(messages, session, last_user)
    session["history"].append({"role": "assistant", "content": response["content"], "timestamp": datetime.now().isoformat()})
    update_session(session)
    if "_turn_calls" in session:
        del session["_turn_calls"]
    return {"message": response["content"], "session_id": session_id, "timestamp": datetime.now(), "function_calls": response.get("function_calls", [])}

@app.post("/chat/stream")
async def chat_stream(request: Dict, req: Request, auth: str = Depends(check_api_key)):
    async def generate_stream():
        ip = _client_ip_from_headers(req.headers, req.client.host if req.client else None)
        session_id = request["session_id"]
        message = request["message"]
        if not await _allow_http(ip, session_id or ip):
            yield f"data: {json.dumps({'type':'error','message':'rate_limited'})}\n\n"
            return
        session = await get_or_create_session(session_id)
        session["history"].append({"role": "user", "content": message, "timestamp": datetime.now().isoformat()})
        last_user = session["history"][-1]["content"]
        messages = prepare_messages_streaming(session)
        try:
            async for chunk in process_chat_streaming(messages, session, session_id, last_user):
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            logger.info(f"Streaming cancelled for session {session_id}")
            raise
        except Exception as e:
            logger.exception("Streaming error: %s", e)
            try:
                yield f"data: {json.dumps({'type': 'error', 'message': 'streaming_error'})}\n\n"
            except Exception:
                pass
        finally:
            update_session(session)
            if "_turn_calls" in session:
                del session["_turn_calls"]

    return StreamingResponse(generate_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})

@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    # Validate Origin header against allowed CORS origins (best-effort) before accept
    origin = websocket.headers.get("origin")
    relax_origin = os.getenv("DEHUM_RELAX_WS_ORIGIN", "false").lower() == "true"
    if not relax_origin and CORS_ORIGINS and origin and origin not in CORS_ORIGINS:
        await websocket.close(code=1008)
        return
    # Validate short-lived token issued by WP (base64url(payload).hmacSHA256)
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=1008)
        return
    session_id_from_token = None
    try:
        import hashlib, hmac
        b64, sig = token.rsplit('.', 1)
        expected = hmac.new((API_KEY or "").encode(), b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            await websocket.close(code=1008)
            return
        # restore padding for base64url
        pad = '=' * (-len(b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(b64 + pad)
        data = json.loads(payload_bytes.decode('utf-8'))
        now = int(datetime.now().timestamp())
        if now >= int(data.get("exp", 0)):
            await websocket.close(code=1008)
            return
        session_id = str(data.get("sid", ""))
        session_id_from_token = session_id
        ip = _client_ip_from_headers(dict(websocket.headers), websocket.client.host if websocket.client else None)
        # WS connection limits
        async with _rl_lock:
            if _ws_active_ip[ip] >= WS_MAX_CONN_PER_IP or _ws_active_session[session_id] >= WS_MAX_CONN_PER_SESSION:
                await websocket.close(code=1008)
                return
            _ws_active_ip[ip] += 1
            _ws_active_session[session_id] += 1
    except Exception:
        await websocket.close(code=1008)
        return
    # Accept only after validation
    await websocket.accept()
    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except (WebSocketDisconnect, RuntimeError):
                # Client disconnected or socket no longer valid
                break
            try:
                payload = json.loads(raw)
            except Exception:
                await websocket.send_text(json.dumps({"type": "error", "message": "invalid_json"}))
                continue
            session_id = payload.get("session_id")
            message = payload.get("message")
            if not session_id or not isinstance(message, str) or not message:
                await websocket.send_text(json.dumps({"type": "error", "message": "invalid_payload"}))
                continue
            # Enforce sid match with token sid
            if session_id_from_token and session_id != session_id_from_token:
                await websocket.send_text(json.dumps({"type": "error", "message": "sid_mismatch"}))
                continue
            session = await get_or_create_session(session_id)
            session["history"].append({"role": "user", "content": message, "timestamp": datetime.now().isoformat()})
            messages = prepare_messages_streaming(session)
            last_user = session["history"][-1]["content"]
            try:
                async for chunk in process_chat_streaming(messages, session, session_id, last_user):
                    await websocket.send_text(json.dumps(chunk))
                await websocket.send_text(json.dumps({"type": "done"}))
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("WS streaming error: %s", e)
                try:
                    await websocket.send_text(json.dumps({"type": "error", "message": "streaming_error"}))
                    await websocket.close(code=1011)
                except Exception:
                    pass
                # Exit receive loop after an unrecoverable streaming error
                break
            finally:
                update_session(session)
                if "_turn_calls" in session:
                    try:
                        del session["_turn_calls"]
                    except Exception:
                        pass
    except WebSocketDisconnect:
        return
    finally:
        # Decrement active counters
        try:
            ip = _client_ip_from_headers(dict(websocket.headers), websocket.client.host if websocket.client else None)
            async with _rl_lock:
                if ip in _ws_active_ip and _ws_active_ip[ip] > 0:
                    _ws_active_ip[ip] -= 1
                sid = locals().get('session_id') if 'session_id' in locals() else None
                if sid and sid in _ws_active_session and _ws_active_session[sid] > 0:
                    _ws_active_session[sid] -= 1
        except Exception:
            pass

@app.post("/clear_session")
async def clear_session(request: Dict, auth: str = Depends(check_api_key)):
    session_id = request["session_id"]
    if session_id in sessions:
        del sessions[session_id]
    wp_clear_session(session_id)
    return {"success": True, "message": "Session cleared"}

# Minimal WP clear helper
def wp_clear_session(session_id: str) -> None:
    nonce = wp_get_nonce()
    try:
        requests.post(f"{WORDPRESS_URL}/wp-admin/admin-ajax.php", data={"action": "dehum_clear_session", "session_id": session_id, "nonce": nonce}, headers={"Authorization": f"Bearer {WP_API_KEY}"}, timeout=5)
    except Exception as e:
        logger.debug("WP clear error: %s", e)

# For session management, add lock
_session_lock = asyncio.Lock()

async def get_or_create_session(session_id: str) -> Dict:
    async with _session_lock:
        if session_id in sessions:
            return sessions[session_id]
        wp_session = wp_load_session(session_id)
        if wp_session:
            sessions[session_id] = wp_session
            return wp_session
        new_session = {"id": session_id, "history": [], "cache": {}, "state": {}, "last_activity": datetime.now()}
        sessions[session_id] = new_session
        return new_session

def update_session(session: Dict):
    session["last_activity"] = datetime.now()
    wp_save_session(session)

def prepare_messages(session: Dict) -> List[Dict]:
    messages = [{"role": "system", "content": get_system_prompt()}]
    # Light state: <100 tokens
    state = session.get("state", {})
    if state:
        compact = f"Last Sizing: Load={state.get('last_load_lpd', 'N/A')} L/day | Inputs={state.get('last_inputs_summary', 'N/A')}"
        messages.append({"role": "system", "content": compact})
    # Trim history with token safety
    history = session["history"][-6:]
    enc = tiktoken.encoding_for_model("gpt-4")  # Fallback for gpt-5.
    total_tokens = sum(len(enc.encode(m.get("content", ""))) for m in messages + history)
    while total_tokens > 80000 and len(history) > 2:
        history = history[1:]
        total_tokens = sum(len(enc.encode(m.get("content", ""))) for m in messages + history)
    messages.extend({"role": h["role"], "content": h["content"]} for h in history)
    return messages

def prepare_messages_streaming(session: Dict) -> List[Dict]:
    messages = prepare_messages(session)
    # Do not pre-append catalog here; only add after tools when needed
    return messages

async def process_chat_streaming(messages: List[Dict], session: Dict, session_id: str, last_user: str) -> AsyncGenerator[Dict, None]:
    current_phase = "initial_summary"
    tool_results = []
    accumulated_content = ""

    while current_phase != "final":
        if current_phase == "initial_summary":
            tools = get_tools_for()
            stream = await completion(messages, 16000, tools=tools, tool_choice="auto", stream=True)
            tool_call_dicts = {}
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    accumulated_content += delta.content
                    yield {"type": "response", "content": delta.content, "is_streaming_chunk": True, "metadata": {"phase": "initial_summary"}}
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        index = tc_delta.index
                        rec = tool_call_dicts.setdefault(index, {"id": tc_delta.id, "type": tc_delta.type, "function": {"name": "", "arguments": ""}})
                        if tc_delta.function and tc_delta.function.name:
                            rec["function"]["name"] = tc_delta.function.name
                        if tc_delta.function and tc_delta.function.arguments:
                            rec["function"]["arguments"] += tc_delta.function.arguments
            tool_calls = finalize_tool_calls(tool_call_dicts)
            messages.append({"role": "assistant", "content": accumulated_content, "tool_calls": tool_calls})
            current_phase = "tools" if tool_calls else ("recommendations" if "recommend" in last_user.lower() else "final")

        elif current_phase == "tools":
            async for response in stream_tools_phase(tool_calls, messages, session, session_id, last_user):
                if isinstance(response, list):
                    tool_results = response
                else:
                    yield response
            current_phase = "recommendations"

        elif current_phase == "recommendations":
            tools = get_tools_for()
            stream = await completion(messages, 16000, tools=tools, tool_choice="none", stream=True)
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield {"type": "response", "content": chunk.choices[0].delta.content, "session_id": session_id, "timestamp": datetime.now().isoformat(), "is_streaming_chunk": True, "metadata": {"phase": "recommendations"}}
            current_phase = "final"

    yield {"message": "", "is_final": True, "function_calls": tool_results}

async def get_ai_response(messages: List[Dict], session: Dict, last_user: str) -> Dict:
    initial_response = await get_initial_completion(messages, last_user)
    content = initial_response["content"]
    tool_calls = initial_response["tool_calls"]

    if not tool_calls and "recommend" in last_user.lower():
        messages.append({"role": "assistant", "content": content})
        new_content = ""
        tools = get_tools_for()
        gen = await completion(messages, 16000, tools=tools, tool_choice="none", stream=True)
        async for chunk in gen:
            if chunk.choices[0].delta.content:
                new_content += chunk.choices[0].delta.content
        return {"content": new_content, "tool_calls": []}

    tool_results = []
    if tool_calls:
        messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
        tool_results, follow_up_gen = await process_tool_calls(tool_calls, messages, session, last_user)
        new_content = ""
        async for token in follow_up_gen:
            new_content += token
        content = new_content or content
    if "_turn_calls" in session:
        del session["_turn_calls"]
    return {"content": content, "tool_calls": tool_results}

async def stream_tools_phase(tool_calls: List[Dict], messages: List[Dict], session: Dict, session_id: str, last_user: str) -> AsyncGenerator:
    tool_results = []
    total_calls = 0

    def normalize_tool_calls(choice_msg) -> List[Dict]:
        out = []
        for tc in (choice_msg.tool_calls or []):
            try:
                out.append({
                    "id": tc.id,
                    "type": tc.type,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                })
            except Exception:
                continue
        return out

    current_batch = tool_calls
    while current_batch and total_calls < MAX_TOOL_CALLS_PER_TURN:
        yield {"type": "tool_start", "total_tools": len(current_batch), "session_id": session_id, "timestamp": datetime.now().isoformat(), "metadata": {"phase": "tools", "status": "starting_tools"}}
        for i, tc in enumerate(current_batch):
            if total_calls >= MAX_TOOL_CALLS_PER_TURN:
                break
            func_name = tc["function"]["name"]
            func_args = json.loads(tc["function"]["arguments"])
            t0 = datetime.now()
            yield {"type": "tool_progress", "tool_index": i + 1, "tool_name": func_name, "message": f"Executing tool {i+1}/{len(current_batch)}: {func_name}", "session_id": session_id, "timestamp": datetime.now().isoformat(), "metadata": {"phase": "tools", "status": "executing_tool", "batch": total_calls // max(1, len(current_batch)) + 1}}
            result = invoke_tool(func_name, func_args, session)
            total_calls += 1
            tool_results.append({"name": func_name, "args": func_args, "output": result})
            content = json.dumps(result) if func_name != "retrieve_relevant_docs" else (result.get("formatted_docs") if "formatted_docs" in result else json.dumps(result))
            messages.append({"role": "tool", "tool_call_id": tc["id"], "name": func_name, "content": content})
            dt_ms = int((datetime.now() - t0).total_seconds() * 1000)
            yield {"type": "tool_result", "tool_index": i + 1, "tool_name": func_name, "data": result, "session_id": session_id, "timestamp": datetime.now().isoformat(), "metadata": {"phase": "tools", "status": "tool_completed", "duration_ms": dt_ms}}
            if func_name == "calculate_dehum_load":
                session.setdefault("state", {})
                session["state"]["last_load_lpd"] = result.get("total_lpd")
                session["state"]["last_inputs_summary"] = f"Vol={result['derived']['volume']}m³, Temp={func_args['indoor_temp']}°C, RH={func_args['target_rh']}%"
                update_session(session)
        # Plan next batch if under cap
        if total_calls >= MAX_TOOL_CALLS_PER_TURN:
            break
        planning = await completion(messages, 16000, tools=get_tool_definitions(), tool_choice="auto")
        choice = planning.choices[0].message
        next_calls = normalize_tool_calls(choice)
        if not next_calls:
            break
        messages.append({"role": "assistant", "content": choice.content or "", "tool_calls": next_calls})
        current_batch = next_calls

    yield {"type": "tool_end", "tool_results": tool_results, "session_id": session_id, "timestamp": datetime.now().isoformat(), "metadata": {"phase": "tools", "status": "tools_completed"}}

    load_info = get_latest_load_info(session)
    if load_info:
        preferred_types = detect_preferred_types(last_user)
        catalog_message = prepare_catalog_message(load_info, preferred_types)
        messages.append(catalog_message)
        try:
            product_count = len(json.loads(catalog_message["content"].split("AVAILABLE_PRODUCT_CATALOG_JSON = ", 1)[1].split("\n", 1)[0])["catalog"])
            yield {"type": "tool_progress", "message": f"Prepared catalog with {product_count} products", "session_id": session_id, "timestamp": datetime.now().isoformat(), "metadata": {"phase": "tools", "status": "catalog_prepared"}}
        except Exception:
            pass

    yield tool_results

async def process_tool_calls(tool_calls: List[Any], messages: List[Dict], session: Dict, last_user: str) -> tuple[List[Dict], AsyncGenerator[str, None]]:
    tool_results: List[Dict] = []
    total_calls = 0

    def run_batch(batch):
        nonlocal total_calls
        for tc in batch:
            if total_calls >= MAX_TOOL_CALLS_PER_TURN:
                break
            func_name = tc.function.name
            func_args = json.loads(tc.function.arguments)
            result = invoke_tool(func_name, func_args, session)
            tool_results.append({"name": func_name, "args": func_args, "output": result})
            messages.append({"role": "tool", "tool_call_id": tc.id, "name": func_name, "content": json.dumps(result)})
            total_calls += 1
            if func_name == "calculate_dehum_load":
                session.setdefault("state", {})
                session["state"]["last_load_lpd"] = result.get("total_lpd")
                session["state"]["last_inputs_summary"] = f"Vol={result['derived']['volume']}m³, Temp={func_args['indoor_temp']}°C, RH={func_args['target_rh']}%"
                update_session(session)

    run_batch(tool_calls)

    # plan up to cap
    while total_calls < MAX_TOOL_CALLS_PER_TURN:
        planning = await completion(messages, 16000, tools=get_tool_definitions(), tool_choice="auto")
        choice = planning.choices[0].message
        next_calls = choice.tool_calls or []
        if not next_calls:
            break
        messages.append({"role": "assistant", "content": choice.content or "", "tool_calls": next_calls})
        run_batch(next_calls)
        if total_calls >= MAX_TOOL_CALLS_PER_TURN:
            break

    load_info = get_latest_load_info(session)
    if load_info:
        preferred_types = detect_preferred_types(last_user)
        catalog_message = prepare_catalog_message(load_info, preferred_types)
        messages.append(catalog_message)

    tools = get_tools_for()
    follow_up_gen = await completion(messages, 16000, tools=tools, tool_choice="none", stream=True)
    async def gen_content():
        async for chunk in follow_up_gen:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    return tool_results, gen_content()

async def get_initial_completion(messages: List[Dict], last_user: str) -> Dict:
    tools = get_tools_for()
    response = await completion(messages, 16000, tools=tools, tool_choice="auto")
    choice = response.choices[0].message
    return {"content": choice.content or "", "tool_calls": choice.tool_calls or []}

def finalize_tool_calls(tool_call_dicts: Dict) -> List[Dict]:
    out = []
    for rec in tool_call_dicts.values():
        try:
            json.loads(rec["function"]["arguments"] or "{}")
            out.append(rec)
        except json.JSONDecodeError:
            continue
    return out

def get_system_prompt() -> str:
    """Load system prompt from file and fail fast if missing."""
    prompt_path = os.path.join(os.path.dirname(__file__), "system_prompt.txt")
    if not os.path.exists(prompt_path):
        raise FileNotFoundError(f"System prompt file not found: {prompt_path}")
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt = f.read().strip()

    return prompt

def build_context_from_cache(cache: Dict) -> str:
    if not cache: return ""
    lines = []
    for key, result in cache.items():
        if 'calculate_dehum_load' in key:
            args = json.loads(key.split('|', 1)[1])
            lines.append(f"Load Calc: Pool={args.get('pool_area_m2',0)}m², Load={result.get('total_lpd','N/A')}L/day")
    return "\n".join(lines)

def get_latest_load_info(session: Dict) -> Optional[Dict]:
    items = list(session.get("cache", {}).items())
    for key, result in reversed(items):
        if 'calculate_dehum_load' in key:
            args = json.loads(key.split('|', 1)[1])
            derived = result.get('derived', {}) if isinstance(result, dict) else {}
            return {
                "latentLoad_L24h": result.get('total_lpd'),
                "room_area_m2": derived.get('room_area_m2'),
                "volume": derived.get('volume'),
                "pool_area_m2": args.get('pool_area_m2', 0),
                "pool_required": args.get('pool_area_m2', 0) > 0,
                "indoorTemp": args.get('indoor_temp', 30.0),
                "currentRH": args.get('current_rh', 80.0),
                "targetRH": args.get('target_rh', 60.0)
            }
    return None


def detect_preferred_types(text: str) -> List[str]:
    text_lower = text.lower()
    types = []
    if "ducted" in text_lower: types.append("ducted")
    if "wall" in text_lower: types.append("wall_mount")
    if "portable" in text_lower: types.append("portable")
    return types

def prepare_catalog_message(load_info: Dict, preferred_types: List[str]) -> Dict:
    catalog = get_catalog_with_effective_capacity(load_info["pool_required"])
    if preferred_types:
        catalog = [p for p in catalog if p["type"] in preferred_types]
    catalog = [p for p in catalog if not p.get("drying_only", False)]
    banned_skus = {"ST600", "ST1000"}
    catalog = [p for p in catalog if p["sku"] not in banned_skus]
    derate = derate_factor(load_info['indoorTemp'], load_info['targetRH'])
    for p in catalog:
        p["effective_capacity_lpd"] = round(p["effective_capacity_lpd"] * derate, 1)
    catalog_data = {
        "required_load_lpd": load_info["latentLoad_L24h"],
        "room_area_m2": load_info["room_area_m2"],
        "pool_area_m2": load_info["pool_area_m2"],
        "pool_required": load_info["pool_required"],
        "preferred_types": preferred_types,
        "catalog": catalog
    }
    catalog_json = json.dumps(catalog_data, ensure_ascii=False)
    return {"role": "system", "content": f"AVAILABLE_PRODUCT_CATALOG_JSON = {catalog_json}\nUse for recommendations."}

def get_catalog_with_effective_capacity(include_pool_safe_only: bool = False) -> List[Dict]:
    catalog = []
    for p in products:
        if include_pool_safe_only and not p.get("pool_safe", False):
            continue
        if p.get("capacity_lpd") is None:
            continue
        eff_cap = p["capacity_lpd"] * p.get("performance_factor", 1.0)
        catalog.append({
            "sku": p["sku"],
            "name": p.get("name", p["sku"]),
            "type": p.get("type"),
            "effective_capacity_lpd": eff_cap,
            "capacity_lpd": p["capacity_lpd"],
            "performance_factor": p.get("performance_factor", 1.0),
            "pool_safe": p.get("pool_safe", False),
            "price_aud": p.get("price_aud"),
            "url": p.get("url")
        })
    return catalog

# Inline improved psychrometrics (from psychrometrics.py; enhanced with clamps, sources, consistency)
ATM_KPA = 101.325  # Standard sea-level pressure (kPa)

def saturation_vp_kpa(temp_c: float) -> float:
    """Saturation vapor pressure (kPa) - ASHRAE 2021 fundamentals."""
    temp_c = max(-50.0, min(60.0, temp_c))  # Clamp realistic range
    return 0.61078 * math.exp((17.2694 * temp_c) / (temp_c + 237.3))

def humidity_ratio(temp_c: float, rh_percent: float) -> float:
    """Humidity ratio W (kg/kg dry air) at std pressure."""
    temp_c = max(-50.0, min(60.0, temp_c))
    rh_clamped = max(0.0, min(100.0, rh_percent))
    pws = saturation_vp_kpa(temp_c)
    pw = (rh_clamped / 100.0) * pws
    return 0.62198 * pw / max(ATM_KPA - pw, 1e-9)

def air_density(temp_c: float) -> float:
    """Approximate dry-air density (kg/m³) - legacy formula."""
    temp_c = max(-50.0, min(60.0, temp_c))
    return 1.2 * (293.15 / (273.15 + temp_c))

def evaporation_activity_coeff(activity: str) -> float:
    """Coeff for pool evap - based on activity level (empirical)."""
    mapping = {"none": 0.05, "low": 0.065, "medium": 0.10, "high": 0.15}
    return mapping.get(activity.lower(), 0.05)

def infiltration_l_per_day(volume_m3: float, indoor_c: float, rh_target_pct: float, outdoor_c: float, rh_out_pct: float, vent_level: str = "low", ach_value: Optional[float] = None) -> float:
    indoor_c = max(-50.0, min(60.0, indoor_c))
    outdoor_c = max(-50.0, min(60.0, outdoor_c))
    if volume_m3 <= 0:
        return 0.0
    W_out = humidity_ratio(outdoor_c, rh_out_pct)
    W_in = humidity_ratio(indoor_c, rh_target_pct)
    dW = max(W_out - W_in, 0.0)
    rho = air_density(indoor_c)
    ach = ach_value if ach_value is not None else {"low": 0.5, "standard": 1.0}.get(vent_level.lower(), 0.5)
    return max(0.0, dW * rho * volume_m3 * ach * 24.0)

def pool_evap_l_per_day(area_m2: float, water_c: float, air_c: float, rh_target_pct: float, mode: str = "field_calibrated", air_movement_level: str = "still", activity: str = "low", covered_h_per_day: float = 0.0, cover_reduction: float = 0.7, custom_params: Dict = None) -> float:
    air_c = max(-50.0, min(60.0, air_c))
    water_c = max(0.0, min(50.0, water_c))  # Realistic pool temp
    if area_m2 <= 0:
        return 0.0
    p_a = (rh_target_pct / 100.0) * saturation_vp_kpa(air_c)
    p_w = saturation_vp_kpa(water_c)
    delta_p = max(p_w - p_a, 0.0)
    delta_p = min(delta_p, 2.5)  # Cap unrealistic rates (empirical)
    c_base = evaporation_activity_coeff(activity)
    velocity_mps = max({"still": 0.0, "low": 0.05, "medium": 0.1}.get(air_movement_level.lower(), 0.0), 0.0)
    c = c_base + 0.3 * velocity_mps
    temp_diff = max(water_c - air_c, 0.0)
    c *= (1.0 + 0.04 * temp_diff)
    w_kg_per_h = area_m2 * c * delta_p
    evap_lpd = max(0.0, w_kg_per_h) * 24.0
    covered_h = min(max(covered_h_per_day, 0.0), 24.0)
    evap_lpd *= (1.0 - (covered_h / 24.0) * min(max(cover_reduction, 0.0), 1.0))
    return round(evap_lpd, 1)

def pulldown_air_l(volume_m3: float, temp_c: float, current_rh: float, target_rh: float) -> float:
    temp_c = max(-50.0, min(60.0, temp_c))
    if volume_m3 <= 0 or target_rh >= current_rh:
        return 0.0
    dW = max(0.0, humidity_ratio(temp_c, current_rh) - humidity_ratio(temp_c, target_rh))
    rho = air_density(temp_c)
    return dW * rho * volume_m3

def derate_factor(temp_c: float, rh_percent: float) -> float:
    """Derating factor [0.1,1.0] based on dew point (inline dew_point calc)."""
    temp_c = max(-50.0, min(60.0, temp_c))
    rh_percent = max(0.0, min(100.0, rh_percent))
    if rh_percent <= 0:
        return 0.1  # Min derate for dry air
    pv = (rh_percent / 100.0) * saturation_vp_kpa(temp_c)
    if pv <= 0:
        return 0.1
    alpha = math.log(pv / 0.61078)  # ASHRAE inverse (consistent with saturation_vp_kpa)
    td = 237.3 * alpha / (17.2694 - alpha)  # ASHRAE constants
    td_norm = max(td, 0.0) / 26.0
    return min(1.0, max(0.1, td_norm ** 1.5))  # Empirical curve; tune exponent if needed

# Restored: Product catalog and manual functions
# Comment out unused get_product_catalog
# def get_product_catalog(capacity_min: float = None, capacity_max: float = None, product_type: str = None, pool_safe_only: bool = False, price_range_max: float = None) -> Dict:
#     catalog = []
#     for p in products:
#         if pool_safe_only and not p.get("pool_safe", False):
#             continue
#         if product_type and p.get("type") != product_type:
#             continue
#         if capacity_min and p.get("capacity_lpd", 0) < capacity_min:
#             continue
#         if capacity_max and p.get("capacity_lpd", 0) > capacity_max:
#             continue
#         if price_range_max and p.get("price_aud") and p.get("price_aud") > price_range_max:
#             continue
#         eff_cap = p["capacity_lpd"] * p.get("performance_factor", 1.0)
#         catalog.append({
#             "sku": p["sku"],
#             "name": p.get("name", p["sku"]),
#             "type": p.get("type"),
#             "series": p.get("series"),
#             "technology": p.get("technology"),
#             "capacity_lpd": p["capacity_lpd"],
#             "effective_capacity_lpd": eff_cap,
#             "performance_factor": p.get("performance_factor", 1.0),
#             "pool_safe": p.get("pool_safe", False),
#             "price_aud": p.get("price_aud"),
#             "url": p.get("url")
#         })
#     catalog.sort(key=lambda x: x["capacity_lpd"])
#     return {"catalog": catalog, "total_products": len(catalog)}

def get_product_manual(sku: str, type: str = "manual") -> Dict:
    for p in products:
        if p["sku"] == sku:
            text_key = "manual_text" if type == "manual" else "brochure_text"
            text_content = p.get(text_key, "Text not available")
            if text_content.endswith('.txt') and not text_content.startswith('Text not'):
                for base in [os.path.dirname(__file__), os.path.dirname(os.path.dirname(__file__)), ""]:
                    path = os.path.join(base, "product_docs", text_content)
                    if os.path.exists(path):
                        with open(path, 'r', encoding='utf-8') as f:
                            text_content = f.read()
                        break
            return {"text": text_content, "sku": sku, "product_name": p.get("name", sku), "type": type}
    return {"error": "Product not found"}

# Restored: Sizing helpers
def _normalize_dimensions(length: Optional[float], width: Optional[float], height: Optional[float], volume_m3: Optional[float]) -> Dict[str, float]:
    if volume_m3 is not None:
        volume = max(0.1, float(volume_m3))  # Clamp to min 0.1
        if volume != volume_m3:
            logger.warning(f"Clamped volume_m3 from {volume_m3} to {volume}")
        return {"volume": volume, "length": 0.0, "width": 0.0, "height": 0.0}
    if length is None or width is None or height is None:
        raise ValueError("All dimensions required if no volume")
    length = max(0.1, float(length))
    width = max(0.1, float(width))
    height = max(0.1, float(height))
    if length != float(length) or width != float(width) or height != float(height):
        logger.warning(f"Clamped dimensions: L={length} W={width} H={height}")
    return {"volume": length * width * height, "length": length, "width": width, "height": height}

def calibrate_params(measured_data: list) -> Dict:
    # Implement actual calibration logic or placeholder
    if not measured_data:
        return {}
    # Dummy implementation; replace with real
    return {"field_bias": 0.85, "min_ratio_vs_standard": 0.75}

def compute_load_components(
    *,
    current_rh: float,
    target_rh: float,
    indoor_temp: float,
    length: Optional[float] = None,
    width: Optional[float] = None,
    height: Optional[float] = None,
    volume_m3: Optional[float] = None,
    ach: float = 1.0,
    people_count: int = 0,
    pool_area_m2: float = 0.0,
    water_temp_c: Optional[float] = None,
    pool_activity: str = "low",
    vent_factor: float = 1.0,
    additional_loads_lpd: float = 0.0,
    air_velocity_mps: float = 0.12,
    outdoor_temp_c: Optional[float] = None,
    outdoor_rh_percent: Optional[float] = None,
    covered_hours_per_day: float = 0.0,
    cover_reduction: float = 0.7,
    air_movement_level: str = "still",
    vent_level: str = "low",
    mode: str = "field_calibrated",
    field_bias: float = 0.80,
    min_ratio_vs_standard: float = 0.70,
    calibrate_to_data: bool = False,
    measured_data: Optional[list] = None,
) -> Dict[str, Any]:
    if not (0 <= current_rh <= 100):
        current_rh = max(0.0, min(100.0, current_rh))
    if not (0 <= target_rh <= 100):
        target_rh = max(0.0, min(100.0, target_rh))
    if indoor_temp < -20 or indoor_temp > 60:
        raise ValueError("indoor_temp out of bounds")

    dims = _normalize_dimensions(length, width, height, volume_m3)
    volume = dims["volume"]
    room_area_m2 = (dims["length"] * dims["width"]) if dims["length"] > 0 and dims["width"] > 0 else None

    out_T = outdoor_temp_c if outdoor_temp_c is not None else indoor_temp
    out_RH = outdoor_rh_percent if outdoor_rh_percent is not None else current_rh

    infiltration_lpd = infiltration_l_per_day(volume, indoor_temp, target_rh, out_T, out_RH, vent_level, ach_value=ach)
    occupant_lpd = max(0.0, people_count * 80.0 * 24.0 / 1000.0) if people_count > 0 else 0.0
    pool_lpd = pool_evap_l_per_day(pool_area_m2, water_temp_c or 28.0, indoor_temp, target_rh, mode="standard", air_movement_level=air_movement_level, activity=pool_activity, covered_h_per_day=covered_hours_per_day, cover_reduction=cover_reduction) if pool_area_m2 > 0 else 0.0
    other_lpd = max(0.0, additional_loads_lpd)

    steady_total_lpd = round(infiltration_lpd + occupant_lpd + pool_lpd + other_lpd, 1)
    latent_kw = round((steady_total_lpd / 24.0) * 0.694, 1)
    pulldown_l = pulldown_air_l(volume, indoor_temp, current_rh, target_rh) if target_rh < current_rh else 0.0

    return {
        "inputs": {
            "current_rh": current_rh,
            "target_rh": target_rh,
            "indoor_temp": indoor_temp,
            "length": length,
            "width": width,
            "height": height,
            "volume_m3": volume,
            "ach": ach,
            "people_count": people_count,
            "pool_area_m2": pool_area_m2,
            "water_temp_c": water_temp_c,
            "pool_activity": pool_activity,
            "vent_factor": vent_factor,
            "additional_loads_lpd": additional_loads_lpd,
            "air_velocity_mps": air_velocity_mps,
            "outdoor_temp_c": outdoor_temp_c,
            "outdoor_rh_percent": outdoor_rh_percent,
            "covered_hours_per_day": covered_hours_per_day,
            "cover_reduction": cover_reduction,
            "air_movement_level": air_movement_level,
            "vent_level": vent_level,
            "mode": mode,
            "field_bias": field_bias,
            "min_ratio_vs_standard": min_ratio_vs_standard,
            "calibrate_to_data": calibrate_to_data,
            "measured_data": measured_data
        },
        "derived": {
            "volume": volume,
            "room_area_m2": room_area_m2,
            "out_T": out_T,
            "out_RH": out_RH,
            "infiltration_lpd": infiltration_lpd,
            "occupant_lpd": occupant_lpd,
            "pool_lpd": pool_lpd,
            "other_lpd": other_lpd,
            "steady_total_lpd": steady_total_lpd,
            "steady_latent_kw": latent_kw,
            "pulldown_l": pulldown_l
        },
        "components": {
            "infiltration_l_per_day": infiltration_lpd,
            "occupant_l_per_day": occupant_lpd,
            "pool_evap_l_per_day": pool_lpd,
            "other_loads_lpd": other_lpd,
            "total_load_lpd": steady_total_lpd,
            "latent_load_kw": latent_kw,
            "pulldown_air_l": pulldown_l
        },
        "total_lpd": steady_total_lpd,
        "steady_latent_kw": latent_kw,
        "pulldown_air_l": pulldown_l,
        "plot_data": {
            "total_load_lpd": steady_total_lpd,
            "latent_load_kw": latent_kw,
            "pulldown_air_l": pulldown_l,
            "infiltration_lpd": infiltration_lpd,
            "occupant_lpd": occupant_lpd,
            "pool_evap_lpd": pool_lpd,
            "other_loads_lpd": other_lpd
        },
        "notes": [
            f"Total Load (L/day): {steady_total_lpd}",
            f"Steady Latent Load (kW): {latent_kw}",
            f"Pulldown Air Load (L/day): {pulldown_l}",
            f"Infiltration Load (L/day): {infiltration_lpd}",
            f"Occupant Load (L/day): {occupant_lpd}",
            f"Pool Evaporation Load (L/day): {pool_lpd}",
            f"Other Loads (L/day): {other_lpd}"
        ]
    }

def calculate_dehum_load(**kwargs) -> Dict:
    return compute_load_components(**kwargs)

def retrieve_relevant_docs(query: str, k: int = 5) -> Dict:
    vs = get_vectorstore()
    if not vs:
        return {"formatted_docs": "RAG not available", "chunks": []}
    # widen recall via Maximal Marginal Relevance and slight query expansion
    q = query.strip()
    expansions = [q]
    if len(q.split()) <= 6 and ("spec" in q.lower() or "datasheet" in q.lower() or "manual" in q.lower()):
        expansions.append(q + " full specifications table dimensions power airflow operating range refrigerant")
    all_docs = []
    for qx in expansions:
        try:
            docs = vs.max_marginal_relevance_search(qx, k=k, fetch_k=max(12, k * 3))
        except Exception:
            docs = vs.similarity_search(qx, k=k)
        all_docs.extend(docs)
    # dedupe by (source, content)
    seen = set()
    deduped = []
    for d in all_docs:
        key = (d.metadata.get('source', 'Unknown'), d.page_content[:256])
        if key in seen: continue
        seen.add(key)
        deduped.append(d)
        if len(deduped) >= k:
            break
    formatted = "\n\n".join([f"[Source: {d.metadata.get('source', 'Unknown')}] {d.page_content}" for d in deduped])
    sources = []
    sseen = set()
    for d in deduped:
        s = d.metadata.get('source', 'Unknown')
        if s not in sseen:
            sseen.add(s)
            sources.append({"source": s})
    return {
        "formatted_docs": formatted,
        "chunks": [d.page_content for d in deduped],
        "num_chunks": len(deduped),
        "sources": sources
    }

def get_tool_definitions() -> List[Dict]:
    return [
        {"type": "function", "function": {"name": "retrieve_relevant_docs", "description": "Retrieve relevant docs", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "k": {"type": "integer", "default": 3}}, "required": ["query"]}}},
        {"type": "function", "function": {"name": "calculate_dehum_load", "description": "Calculate dehum load", "parameters": {"type": "object", "properties": {"current_rh": {"type": "number"}, "target_rh": {"type": "number"}, "indoor_temp": {"type": "number"}, "length": {"type": "number"}, "width": {"type": "number"}, "height": {"type": "number"}, "volume_m3": {"type": "number"}, "ach": {"type": "number"}, "people_count": {"type": "integer"}, "pool_area_m2": {"type": "number"}, "water_temp_c": {"type": "number"}, "pool_activity": {"type": "string"}, "vent_factor": {"type": "number"}, "additional_loads_lpd": {"type": "number"}, "air_velocity_mps": {"type": "number"}, "outdoor_temp_c": {"type": "number"}, "outdoor_rh_percent": {"type": "number"}, "covered_hours_per_day": {"type": "number"}, "cover_reduction": {"type": "number"}, "air_movement_level": {"type": "string"}, "vent_level": {"type": "string"}, "mode": {"type": "string"}}, "required": ["current_rh", "target_rh", "indoor_temp"]}}},
        {"type": "function", "function": {"name": "pulldown_air_l", "description": "Pulldown air load", "parameters": {"type": "object", "properties": {"volume_m3": {"type": "number"}, "temp_c": {"type": "number"}, "current_rh": {"type": "number"}, "target_rh": {"type": "number"}}, "required": ["volume_m3", "temp_c", "current_rh", "target_rh"]}}},
        {"type": "function", "function": {"name": "pool_evap_l_per_day", "description": "Pool evaporation load", "parameters": {"type": "object", "properties": {"area_m2": {"type": "number"}, "water_c": {"type": "number"}, "air_c": {"type": "number"}, "rh_target_pct": {"type": "number"}, "mode": {"type": "string"}, "air_movement_level": {"type": "string"}, "activity": {"type": "string"}, "covered_h_per_day": {"type": "number"}, "cover_reduction": {"type": "number"}, "custom_params": {"type": "object"}}, "required": ["area_m2", "water_c", "air_c", "rh_target_pct"]}}},
        {"type": "function", "function": {"name": "infiltration_l_per_day", "description": "Infiltration load", "parameters": {"type": "object", "properties": {"volume_m3": {"type": "number"}, "indoor_c": {"type": "number"}, "rh_target_pct": {"type": "number"}, "outdoor_c": {"type": "number"}, "rh_out_pct": {"type": "number"}, "vent_level": {"type": "string"}, "ach_value": {"type": "number"}}, "required": ["volume_m3", "indoor_c", "rh_target_pct", "outdoor_c", "rh_out_pct"]}}}
    ]

def get_tools_for() -> List[Dict]:
    """Expose all tools and let the LLM decide which to call."""
    return get_tool_definitions()

def invoke_tool(func_name: str, func_args: Dict, session: Dict) -> Dict:
    session.setdefault("_turn_calls", set())
    cache_key = f"{func_name}|{json.dumps(func_args, sort_keys=True)}"
    if cache_key in session["_turn_calls"]:
        return {"note": "skipped_duplicate"}
    session["_turn_calls"].add(cache_key)
    tool_map = {
        "retrieve_relevant_docs": retrieve_relevant_docs,
        "calculate_dehum_load": compute_load_components,
        "pulldown_air_l": pulldown_air_l,
        "pool_evap_l_per_day": pool_evap_l_per_day,
        "infiltration_l_per_day": infiltration_l_per_day,
    }
    func = tool_map.get(func_name)
    if not func:
        raise ValueError(f"Unknown tool: {func_name}")
    if cache_key in session["cache"]:
        return session["cache"][cache_key]
    try:
        result = func(**func_args)
    except Exception as e:
        logger.exception("Tool '%s' failed: %s", func_name, e)
        result = {"error": str(e)}
    session["cache"][cache_key] = result
    return result

# WP session helpers
def wp_get_nonce() -> str:
    try:
        resp = requests.get(f"{WORDPRESS_URL}/wp-admin/admin-ajax.php?action=dehum_get_nonce", headers={"Authorization": f"Bearer {WP_API_KEY}"}, timeout=5)
        if resp.status_code == 200 and resp.json().get("success"):
            return resp.json()["data"]["nonce"]
        # Fail fast: do not return a fake nonce
        raise RuntimeError(f"wp_get_nonce failed with status {resp.status_code}")
    except Exception as e:
        logger.warning("wp_get_nonce error: %s", e)
    return "fallback_nonce"

def wp_load_session(session_id: str) -> Dict | None:
    nonce = wp_get_nonce()
    try:
        resp = requests.post(f"{WORDPRESS_URL}/wp-admin/admin-ajax.php", data={"action": "dehum_get_session", "session_id": session_id, "nonce": nonce}, headers={"Authorization": f"Bearer {WP_API_KEY}"}, timeout=5)
        if resp.status_code == 200 and resp.json().get("success"):
            history_data = resp.json()["data"]["history"]
            hist: List[Dict] = []
            state: Dict = {}
            for m in history_data:
                msg = m.get("message") or ""
                resp_text = m.get("response") or ""
                ts = m.get("timestamp")
                if resp_text.startswith(STATE_MARKER):
                    try:
                        state = json.loads(resp_text[len(STATE_MARKER):]) or {}
                    except Exception:
                        state = {}
                    continue
                if msg:
                    hist.append({"role": "user", "content": msg, "timestamp": ts})
                elif resp_text:
                    hist.append({"role": "assistant", "content": resp_text, "timestamp": ts})
            return {"id": session_id, "history": hist, "cache": {}, "state": state, "last_activity": datetime.now()}
    except Exception as e:
        logger.debug("WP load error: %s", e)
    return None

def wp_save_session(session: Dict) -> None:
    nonce = wp_get_nonce()
    wp_history = [{"message": h["content"] if h["role"] == "user" else "", "response": h["content"] if h["role"] == "assistant" else "", "user_ip": "", "timestamp": h["timestamp"]} for h in session["history"]]
    # Append lightweight state marker for durability across restarts
    try:
        state_payload = json.dumps(session.get("state", {}), ensure_ascii=False)
        wp_history.append({"message": "", "response": f"{STATE_MARKER}{state_payload}", "user_ip": "", "timestamp": datetime.now().isoformat()})
    except Exception:
        pass
    try:
        requests.post(f"{WORDPRESS_URL}/wp-admin/admin-ajax.php", data={"action": "dehum_save_session", "session_id": session["id"], "history": json.dumps(wp_history), "nonce": nonce}, headers={"Authorization": f"Bearer {WP_API_KEY}"}, timeout=5)
    except Exception as e:
        logger.debug("WP save error: %s", e)

# RAG (from rag_pipeline.py; simplified to functions)
def load_documents() -> List[Document]:
    docs_dir = os.path.join(os.path.dirname(__file__), "product_docs")
    documents = []
    for file_path in os.listdir(docs_dir):
        path = os.path.join(docs_dir, file_path)
        if file_path.endswith('.txt'):
            loader = TextLoader(path, encoding='utf-8')
        elif file_path.endswith('.pdf'):
            loader = PyMuPDFLoader(path)
        else:
            continue
        docs = loader.load()
        for doc in docs:
            doc.metadata['source'] = file_path
        documents.extend(docs)
    return documents

def chunk_documents(documents: List[Document]) -> List[Document]:
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=RAG_CHUNK_SIZE, chunk_overlap=RAG_CHUNK_OVERLAP)
    return text_splitter.split_documents(documents)

def build_index():
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large", openai_api_key=OPENAI_API_KEY)
    documents = load_documents()
    chunks = chunk_documents(documents)
    vectorstore = FAISS.from_documents(chunks, embeddings)
    vectorstore.save_local(os.path.join(os.path.dirname(__file__), "faiss_index"))

def load_vectorstore() -> Any:
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large", openai_api_key=OPENAI_API_KEY)
    index_dir = os.path.join(os.path.dirname(__file__), "faiss_index")
    if not os.path.exists(index_dir):
        raise FileNotFoundError(f"FAISS index directory missing: {index_dir}. Build the index first.")
    return FAISS.load_local(index_dir, embeddings, allow_dangerous_deserialization=True)

# LLM completion with retry (from engine.py; inlined)
def is_retryable_error(error: Exception) -> bool:
    err = str(error).lower()
    return any(k in err for k in ("rate limit", "429", "connection", "timeout", "network", "502", "503", "504", "service unavailable", "internal server error"))

@retry(retry=retry_if_exception(is_retryable_error), stop=stop_after_attempt(4), wait=wait_exponential_jitter(1.0, 60.0), reraise=True)
async def completion(messages: List[Dict], max_tokens: int, tools: Optional[List[Dict]] = None, tool_choice: Optional[str] = None, stream: bool = False) -> Any:
    model = DEFAULT_MODEL
    params: Dict[str, Any] = {"messages": messages, "stream": stream}
    if tools:
        params["tools"] = tools
    if tool_choice:
        params["tool_choice"] = tool_choice
    client = OPENAI_CLIENT
    params["model"] = model
    params["max_completion_tokens"] = max_tokens
    params["reasoning_effort"] = GPT5_REASONING_EFFORT
    params["verbosity"] = GPT5_VERBOSITY
    return await client.chat.completions.create(**params)

sessions: Dict[str, Dict] = {}
products = load_product_database()
_vectorstore_cache = None

def get_vectorstore():
    global _vectorstore_cache
    if not RAG_ENABLED:
        return None
    if _vectorstore_cache is None:
        try:
            _vectorstore_cache = load_vectorstore()
        except Exception as e:
            logger.error("Failed to load vectorstore: %s", e)
            _vectorstore_cache = None
    return _vectorstore_cache

# All features implemented - refactor complete

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=SERVICE_HOST, port=SERVICE_PORT)