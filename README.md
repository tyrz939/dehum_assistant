# Dehumidifier Assistant

A conversational AI assistant for dehumidifier sizing and selection. Currently running as a Flask application with plans for WordPress plugin integration.

## 🎯 Current Status

**PRODUCTION SYSTEM:** Flask application serving real users (active conversation logs)
**NEXT PHASE:** Building minimal viable WordPress plugin for broader deployment

## ✨ Current Features

- **Smart Conversation Memory**: Remembers context throughout chat sessions
- **Demo Mode**: Works without API key for testing and demonstrations  
- **Professional Chat Interface**: Optimized for all device sizes
- **Product Catalog Integration**: Real dehumidifier sizing recommendations
- **Comprehensive Logging**: All conversations logged for business intelligence

## 🚀 Quick Start

### Flask Application

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (optional - demo mode if not set)
export OPENAI_API_KEY="your-openai-api-key"
export SECRET_KEY="your-secret-key"

# Run the application
python app.py
```

The app will be available at `http://localhost:5001`

## 📁 Project Structure

```
dehum_assistant/
├── app.py                      # Main Flask application (PRODUCTION)
├── requirements.txt            # Python dependencies  
├── prompt_template.txt         # AI system prompt
├── product_db.json            # Product catalog
├── templates/
│   ├── index.html             # Main chat interface
│   └── popup.html             # WordPress popup version  
├── conversation_logs/         # Active user conversations
├── flask_sessions/           # User session data
├── PROJECT_ROADMAP.md        # Development roadmap
└── README.md                 # This file
```

## 🎯 Roadmap

See [PROJECT_ROADMAP.md](PROJECT_ROADMAP.md) for the complete development plan including:
- WordPress plugin MVP development
- n8n workflow integration
- Lead qualification system
- Advanced business features

## 🎨 Templates

- **`index.html`**: Standalone chat interface
- **`popup.html`**: WordPress integration template

These templates will be used as reference for the upcoming WordPress plugin MVP.

## 🔧 Configuration

### Environment Variables
```bash
OPENAI_API_KEY=sk-...          # OpenAI API key (optional - demo mode without)
SECRET_KEY=your-secret-key     # Flask session secret
FLASK_ENV=production          # Environment setting
PORT=5001                     # Port to run on
```

## 📊 Active Usage

Check `conversation_logs/` directory for real user interactions. The Flask app is currently serving live traffic and should remain operational during WordPress plugin development.

## 🛡️ Security Features

- Input validation and rate limiting
- Session-based conversation memory
- Comprehensive error handling and logging
- Demo mode fallback for reliability

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Status: Flask app is production-ready and actively serving users. WordPress plugin MVP development ready to begin.**