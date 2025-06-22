# Dehumidifier Assistant

A conversational AI assistant for dehumidifier sizing and selection, with seamless WordPress integration.

## ✨ Features

- **Smart Conversation Memory**: Remembers context throughout the chat session
- **Demo Mode**: Works without API key for testing and demonstrations
- **WordPress Integration**: Professional floating chat button with modal popup
- **Mobile Responsive**: Optimized for all device sizes
- **Analytics Ready**: Built-in tracking for Google Analytics and WordPress
- **Secure**: Input validation, CORS protection, and WordPress security best practices

## 🚀 Quick Start

### 1. Flask Application

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

### 2. WordPress Integration

**Option A: Add to Theme**
1. Copy the content from `wordpress-integration.php`
2. Paste it at the end of your theme's `functions.php` file
3. Update the `DEFAULT_SERVER_URL` constant with your Flask app URL

**Option B: Create Plugin**
1. Create a WordPress plugin using the code in `wordpress-integration.php`
2. Activate the plugin in WordPress admin
3. Configure settings at **Settings > Dehumidifier Chat**

## 📁 Project Structure

```
dehum_assistant/
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies  
├── prompt_template.txt         # AI system prompt
├── wordpress-integration.php   # WordPress integration
├── templates/
│   ├── index.html             # Main chat interface
│   └── popup.html             # WordPress popup version
├── conversation_logs/         # Chat logs (auto-created)
├── flask_sessions/           # Session storage (auto-created)
├── DEPLOYMENT.md             # Detailed deployment guide
└── README.md                 # This file
```

## 🎯 Demo Mode

The application automatically enters demo mode when no OpenAI API key is provided. In demo mode:
- Provides intelligent hardcoded responses for common queries
- Maintains conversation flow and context
- Perfect for testing and demonstrations
- Gracefully handles API failures

## 🔧 Configuration

### Environment Variables
```bash
OPENAI_API_KEY=sk-...          # OpenAI API key (optional)
SECRET_KEY=your-secret-key     # Flask session secret
FLASK_ENV=production          # Environment (development/production)
PORT=5001                     # Port to run on
```

### WordPress Settings
After installation, configure the chat widget in WordPress admin:
- **Settings > Dehumidifier Chat**
- Set server URL, customize appearance, control page targeting

## 🛡️ Security Features

- **Input Validation**: 400 character limit, message count limits
- **Session Security**: Secure session management with Flask
- **CORS Protection**: Configurable cross-origin resource sharing
- **WordPress Security**: Nonce verification, input sanitization, capability checks

## 📊 Analytics & Monitoring

- **Conversation Logging**: Automatic logging to `conversation_logs/`
- **Health Check Endpoint**: `GET /api/health`
- **WordPress Analytics**: Built-in tracking with Google Analytics integration
- **Error Monitoring**: Comprehensive error logging and handling

## 🎨 Customization

### Page Targeting
Control where the chat widget appears by editing the `should_show_chat()` method in the WordPress integration.

### Styling
Customize the chat button appearance by modifying the CSS in `get_chat_styles()`.

### AI Behavior
Edit `prompt_template.txt` to customize the AI assistant's knowledge and responses.

## 🚀 Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for comprehensive deployment instructions including:
- Production server setup
- WordPress plugin creation
- Security configurations
- Troubleshooting guide

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: Report bugs or request features via GitHub issues
- **Documentation**: See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed setup instructions
- **Health Check**: Use `/api/health` endpoint to verify application status

---

**Ready to deploy!** 🎉 This application is production-ready with WordPress integration, security features, and comprehensive documentation.