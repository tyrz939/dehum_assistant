import os
from dotenv import load_dotenv
load_dotenv()

from flask import (
    Flask, request, render_template,
    stream_with_context,   # <<< re-added this
    Response, make_response,
    after_this_request, g
)
import uuid
import json
from datetime import datetime
from model_client import stream_completion

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecret")

# Load system prompt
prompt_path = "prompt_template_test.txt"
if os.path.exists(prompt_path):
    with open(prompt_path, "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()
else:
    SYSTEM_PROMPT = "You are a dehumidifier assistant."

@app.route("/")
def index():
    session_id = request.cookies.get("session_id") or str(uuid.uuid4())
    chat_count = request.cookies.get("chat_count") or "0"
    date_stamp = request.cookies.get("chat_date") or datetime.utcnow().strftime('%Y-%m-%d')

    today = datetime.utcnow().strftime('%Y-%m-%d')
    if date_stamp != today:
        chat_count = "0"

    initial_history = [
        {"role": "assistant", "content": "Hello! I'm your Dehumidifier Assistant. Ask me anything about sizing or model selection."}
    ]
    response = make_response(render_template("index.html"))
    response.set_cookie("session_id", session_id)
    response.set_cookie("history", json.dumps(initial_history))
    response.set_cookie("chat_count", chat_count)
    response.set_cookie("chat_date", today)
    return response

@app.route("/api/assistant", methods=["POST"])
def assistant():
    # 1) Load history from JSON body (preferred), else from cookie
    data = request.get_json() or {}
    incoming = data.get("history")
    if isinstance(incoming, list):
        history = incoming
    else:
        raw = request.cookies.get("history") or "[]"
        try:
            history = json.loads(raw)
        except:
            history = []
    app.logger.info("🔷 Received history: %s", history)

    # 2) Get user input
    user_input = data.get("input", "")
    if len(user_input) > 400:
        return Response(
            "Your message exceeds the 400 character limit.",
            mimetype="text/plain"
        ), 400

    # 3) Enforce daily limit
    chat_count = int(request.cookies.get("chat_count") or 0)
    if chat_count >= 20:
        return Response(
            "You’ve reached the daily limit of 20 questions.",
            mimetype="text/plain"
        ), 429

    # 4) Append user turn & prepare new_history
    history.append({"role": "user", "content": user_input})
    g.new_history = json.dumps(history)

    # 5) Build messages list
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    # 6) Stream from the model and store assistant turn when done
    def generate_and_store():
        reply_accum = ""
        for delta in stream_completion(messages):
            reply_accum += delta
            yield delta
        history.append({"role": "assistant", "content": reply_accum})
        g.new_history = json.dumps(history)

    # 7) After-streaming, overwrite the history cookie
    @after_this_request
    def set_history_cookie(response):
        response.set_cookie("history", g.new_history)
        return response

    # 8) Return streaming response and bump chat_count
    resp = Response(
        stream_with_context(generate_and_store()),
        mimetype="text/plain"
    )
    resp.set_cookie("chat_count", str(chat_count + 1))
    return resp

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), debug=False)
