import os
from dotenv import load_dotenv
load_dotenv()  # Load environment variables

from flask import (
    Flask, request, render_template,
    stream_with_context, Response, make_response,
    after_this_request, g
)
import uuid
import json
from datetime import datetime
from model_client import stream_completion

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecret")

# Load the system prompt safely using UTF-8
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

    # Reset daily count if new day
    today = datetime.utcnow().strftime('%Y-%m-%d')
    if date_stamp != today:
        chat_count = "0"

    # Start new history if not present in cookie
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
    user_input = request.json.get("input")
    if len(user_input) > 400:
        return Response("Your message exceeds the 400 character limit.", mimetype="text/plain"), 400

    raw_history = request.cookies.get("history")
    chat_count = int(request.cookies.get("chat_count") or 0)

    if chat_count >= 20:
        return Response("You’ve reached the daily limit of 20 questions.", mimetype="text/plain"), 429

    try:
        history = json.loads(raw_history) if raw_history else []
    except Exception:
        history = []

    # Append user's message and initialize new_history
    history.append({"role": "user", "content": user_input})
    g.new_history = json.dumps(history)  # ensure g.new_history is always set

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    def generate_and_store():
        reply_accum = ""
        for delta in stream_completion(messages):
            reply_accum += delta
            yield delta
        # After streaming finishes, append assistant reply and update new_history
        history.append({"role": "assistant", "content": reply_accum})
        g.new_history = json.dumps(history)

    @after_this_request
    def set_history_cookie(response):
        # Overwrite the history cookie after generate_and_store has run
        response.set_cookie("history", g.new_history)
        return response

    response = Response(
        stream_with_context(generate_and_store()),
        mimetype="text/plain"
    )
    # Increment chat count as before
    response.set_cookie("chat_count", str(chat_count + 1))
    return response

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), debug=False)
