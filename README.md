# Dehumidifier Sizing Assistant (Flask + GPT-4o)

This is a Flask-based web assistant that helps users choose the right dehumidifier based on their room size, use-case, and environmental conditions.

It uses OpenAI's GPT-4o model for intelligent recommendations, with real-world sizing logic built in. The frontend is styled like a modern AI chat interface and is embeddable via iframe into a WordPress site.

---

## 🧠 Features

- GPT-4o or local LLM support (Ollama-compatible)
- Supports streaming responses with typing animation
- Full web chat interface (no JS frameworks)
- Dynamic memory of previous chat history
- Logic-aware sizing prompt for dehumidifier models
- Designed for embedding in websites (e.g. via iframe in WordPress)

---

## ⚙️ Requirements

- Python 3.9+
- OpenAI API Key (for GPT-4o usage)
- Flask
- Flask-Session
- python-dotenv

---

## 🚀 Getting Started

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt


example .env:
OPENAI_API_KEY=your-key-here
FLASK_SECRET_KEY=super-secret-key
USE_OPENAI=true
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama2