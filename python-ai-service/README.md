# Dehumidifier Assistant AI Service

A FastAPI-based AI service for dehumidifier sizing, product recommendations, and intelligent chat assistance.

## Features

- **AI-Powered Chat**: OpenAI integration with function calling
- **Model Flexibility**: LiteLLM support for OpenAI, Claude, Gemini, and more
- **Smart Sizing**: Professional dehumidifier capacity calculations
- **Product Recommendations**: Intelligent product matching from catalog
- **Session Management**: Conversation history and context preservation
- **RESTful API**: FastAPI with automatic documentation

## Quick Start

### 1. Environment Setup

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Unix/MacOS)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create your environment file:

```bash
# Copy the example environment file
copy env.example .env

# Edit .env with your actual API keys
# OPENAI_API_KEY=your_actual_openai_api_key_here
```

**Important**: Never commit the `.env` file to version control! It contains your secret API keys.

### 3. Run Tests

```bash
python test_service.py
```

### 4. Start Service

```bash
# Method 1: Direct
python main.py

# Method 2: With uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

### Chat Endpoint
```
POST /chat
```

Request body:
```json
{
  "message": "I need help sizing a dehumidifier for my 5x4 meter room",
  "session_id": "unique_session_id",
  "user_id": "optional_user_id"
}
```

### Health Check
```
GET /health
```

### Session Management
```
GET /session/{session_id}
POST /session/{session_id}/clear
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (required) | - |
| `DEFAULT_MODEL` | Default AI model | `gpt-4o-mini` |
| `SERVICE_HOST` | Service host | `0.0.0.0` |
| `SERVICE_PORT` | Service port | `8000` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Architecture

- **FastAPI**: Modern web framework for building APIs
- **LiteLLM**: Model-agnostic AI integration
- **Pydantic**: Data validation and serialization
- **OpenAI Functions**: Tool calling for sizing and recommendations

## Integration

This service is designed to integrate with:
- WordPress plugin (frontend chat widget)
- n8n workflows (business intelligence)
- CRM systems (lead management)

## Development

### Project Structure
```
python-ai-service/
├── main.py              # FastAPI application
├── ai_agent.py          # AI agent with OpenAI integration
├── models.py            # Pydantic models
├── tools.py             # Sizing and recommendation tools
├── config.py            # Configuration management
├── test_service.py      # Test suite
├── requirements.txt     # Dependencies
└── README.md           # This file
```

### Adding New Models

The service supports multiple AI providers through LiteLLM:
```python
# Available models
models = [
    "gpt-4o-mini",
    "gpt-4o", 
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
    "gemini/gemini-1.5-pro"
]
```

## Testing

Run the test suite to verify functionality:
```bash
python test_service.py
```

The test suite verifies:
- Product database loading
- Sizing calculations
- Product recommendations
- AI agent initialization

## Documentation

Once running, visit `http://localhost:8000/docs` for interactive API documentation. 