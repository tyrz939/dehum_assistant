import os
from dotenv import load_dotenv
load_dotenv()  # 🟢 move this before anything else

from flask import Flask, request, jsonify, render_template_string, session, stream_with_context, Response
from flask_session import Session
from model_client import stream_completion

# Load environment variables from .env
load_dotenv()

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecret")
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Load the system prompt safely
prompt_path = "prompt_template.txt"
if os.path.exists(prompt_path):
    with open(prompt_path, "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()
else:
    SYSTEM_PROMPT = "You are a dehumidifier assistant."

# HTML template for frontend
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Dehumidifier Sizing Assistant</title>
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <style>
        html, body { height: 100%; margin: 0; font-family: Arial, sans-serif; background: #e9f1f7; color: #003366; display: flex; flex-direction: column; }
        #chat-wrapper { flex: 1; display: flex; flex-direction: column; max-width: 800px; margin: 0 auto; width: 100%; }
        #chat { flex: 1; background: white; padding: 1rem 1.5rem; border-radius: 10px 10px 0 0; box-shadow: 0 0 15px rgba(0,0,0,0.1); overflow-y: auto; scroll-behavior: smooth; display: flex; flex-direction: column; }
        .msg { margin: 0.5rem 0; }
        .user { font-weight: bold; color: #004080; margin-bottom: 0.2rem; }
        .assistant { background: #f0f8ff; padding: 0.6rem; border-radius: 6px; white-space: pre-wrap; color: #002244; }
        #input-area { background: white; padding: 1rem 1.5rem; border-radius: 0 0 10px 10px; box-shadow: 0 -2px 10px rgba(0,0,0,0.05); display: flex; flex-direction: column; gap: 0.5rem; position: sticky; bottom: 0; z-index: 10; }
        textarea { width: 100%; padding: 0.5rem; border-radius: 5px; border: 1px solid #ccc; font-size: 1rem; resize: none; box-sizing: border-box; }
        button { align-self: flex-end; padding: 0.5rem 1.5rem; background: #0074d9; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 1rem; }
        button:hover { background: #005fa3; }
    </style>
</head>
<body>
    <div id=\"chat-wrapper\">
        <div id=\"chat\">
            <div id=\"messages\">
                <div class='msg assistant'>Hello! I'm your Dehumidifier Assistant. Ask me anything about sizing or model selection.</div>
            </div>
            <div id=\"bottom-scroll-anchor\"></div>
        </div>
        <div id=\"input-area\">
            <textarea id=\"user_input\" rows=\"3\" placeholder=\"Enter your question...\"></textarea>
            <button onclick=\"sendMessage()\">Send</button>
        </div>
    </div>

    <script>
        const inputBox = document.getElementById("user_input");
        const messagesDiv = document.getElementById("messages");
        const scrollAnchor = document.getElementById("bottom-scroll-anchor");

        inputBox.addEventListener("keydown", function(e) {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        async function sendMessage() {
            const userInput = inputBox.value.trim();
            if (!userInput) return;

            messagesDiv.innerHTML += `<div class='msg user'>You: ${userInput}</div>`;
            inputBox.value = "";
            scrollAnchor.scrollIntoView({ behavior: "smooth" });

            const response = await fetch("/api/assistant", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ input: userInput })
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let result = "<div class='msg assistant'>";
            const el = document.createElement("div");
            el.classList.add("msg", "assistant");
            messagesDiv.appendChild(el);
            let cursor = true;

            function blink() {
                if (!el.innerHTML.endsWith("█")) return;
                el.innerHTML = el.innerHTML.slice(0, -1) + (cursor ? " " : "█");
                cursor = !cursor;
                requestAnimationFrame(blink);
            }
            blink();

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value, { stream: true });
                result += chunk;
                el.innerHTML = result + "█";
                scrollAnchor.scrollIntoView({ behavior: "smooth" });
            }

            el.innerHTML = result;
            scrollAnchor.scrollIntoView({ behavior: "smooth" });
        }
    </script>
<div style="text-align: center; font-size: 0.75rem; color: #666; padding: 1rem 0;">
        This assistant provides recommendations based on available sizing rules and input. It may occasionally make mistakes—please verify before making critical decisions.
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    session["history"] = [
        {"role": "assistant", "content": "Hello! I'm your Dehumidifier Assistant. Ask me anything about sizing or model selection."}
    ]
    return render_template_string(HTML_PAGE)

@app.route("/api/assistant", methods=["POST"])
def assistant():
    user_input = request.json.get("input")

    if "history" not in session:
        session["history"] = []

    session["history"].append({"role": "user", "content": user_input})
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + session["history"]

    def generate():
        reply_accum = ""
        for delta in stream_completion(messages):
            reply_accum += delta
            yield delta
        session["history"].append({"role": "assistant", "content": reply_accum})

    return Response(stream_with_context(generate()), mimetype="text/plain")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
