# Dehumidifier Assistant - Deployment Guide

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Flask environment
- WordPress site (for integration)
- OpenAI API key (optional - has demo mode)

### 1. Flask App Deployment

#### Local Development
```bash
# Clone repository
git clone <your-repo-url>
cd dehum_assistant

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY="your-openai-api-key"
export SECRET_KEY="your-secret-key"

# Run application
python app.py
```

#### Production Deployment

**Option A: Simple Server**
```bash
# Install dependencies
pip install -r requirements.txt gunicorn

# Create .env file
echo "OPENAI_API_KEY=your-key-here" > .env
echo "SECRET_KEY=your-secret-key-here" >> .env
echo "FLASK_ENV=production" >> .env

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

**Option B: Docker (if needed later)**
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5001
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5001", "app:app"]
```

### 2. WordPress Integration

#### Method 1: Add to Theme (Single Site)
1. Copy content from `wordpress-integration.php`
2. Paste at end of your theme's `functions.php`
3. Update `DEFAULT_SERVER_URL` constant with your Flask app URL

#### Method 2: Create Plugin (Multiple Sites)
1. Create directory: `wp-content/plugins/dehumidifier-chat/`
2. Create file: `dehumidifier-chat.php` with plugin headers:

```php
<?php
/**
 * Plugin Name: Dehumidifier Chat Assistant
 * Description: Integrates dehumidifier sizing chat assistant
 * Version: 1.0.0
 * Author: Your Name
 */

// Prevent direct access
if (!defined('ABSPATH')) exit;

// Include the integration code
include_once plugin_dir_path(__FILE__) . 'wordpress-integration.php';
```

3. Copy `wordpress-integration.php` to the plugin directory
4. Activate plugin in WordPress admin

## ⚙️ Configuration

### Flask App Environment Variables
```bash
OPENAI_API_KEY=sk-...           # OpenAI API key (optional - demo mode if missing)
SECRET_KEY=your-secret-key      # Flask session secret
FLASK_ENV=production           # Set to production for deployment
PORT=5001                      # Port to run on (default: 5001)
```

### WordPress Settings
After installation, go to **Settings > Dehumidifier Chat** in WordPress admin:

- **Enable/Disable**: Toggle chat widget
- **Server URL**: Your Flask app URL (e.g., `https://your-domain.com:5001`)
- **Title/Subtitle**: Customize button text
- **Page Targeting**: Control where chat appears

## 🔧 Customization

### Page Targeting
Edit the `should_show_chat()` method in `wordpress-integration.php`:

```php
private function should_show_chat() {
    // Show on specific pages
    if (is_page(['contact', 'hvac', 'dehumidifiers'])) return true;
    
    // Show on posts with specific tags
    if (is_single() && has_tag(['humidity', 'mold'])) return true;
    
    // Show on category pages
    if (is_category(['home-improvement'])) return true;
    
    return false;
}
```

### Styling
Modify the `get_chat_styles()` method:

```php
private function get_chat_styles() {
    return "
    #dehum-chat-button {
        background: linear-gradient(135deg, #your-color, #your-color-dark);
        bottom: 30px;  /* Adjust position */
        right: 30px;
    }
    ";
}
```

### Analytics
The integration automatically tracks:
- Google Analytics events (if gtag is available)
- WordPress action hooks for custom analytics
- Server-side logging in Flask app

## 🛡️ Security

### Flask App
- Session-based conversation memory
- Input validation and sanitization
- Rate limiting (400 char limit, 20 message max)
- CORS configuration for WordPress domains

### WordPress Integration
- Nonce verification for AJAX requests
- Input sanitization with WordPress functions
- Capability checks for admin functions
- Escaped output for XSS prevention

## 📊 Monitoring

### Flask App Logs
- Conversation logs: `conversation_logs/`
- Application logs: Console output
- Health check: `GET /api/health`

### WordPress Analytics
- Admin page shows connection status
- Error logging to WordPress error log
- Custom action hooks for tracking

## 🚨 Troubleshooting

### Common Issues

**Chat button not appearing:**
- Check `should_show_chat()` logic
- Verify WordPress admin settings
- Check browser console for JavaScript errors

**Connection failed:**
- Verify Flask app is running
- Check CORS configuration
- Confirm server URL in WordPress settings

**Demo mode active:**
- Set `OPENAI_API_KEY` environment variable
- Restart Flask application
- Check `/api/health` endpoint

**Mobile issues:**
- Test responsive CSS breakpoints
- Check viewport meta tag on WordPress site
- Verify iframe sizing on small screens

### Debug Mode
Enable debug logging in Flask:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📁 File Structure

```
dehum_assistant/
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── prompt_template.txt         # AI system prompt
├── wordpress-integration.php   # WordPress integration code
├── templates/
│   ├── index.html             # Main chat interface
│   └── popup.html             # WordPress popup version
├── conversation_logs/         # Chat logs (auto-created)
├── flask_sessions/           # Session storage (auto-created)
└── DEPLOYMENT.md             # This file
```

## 🔄 Updates

### Updating Flask App
1. Pull latest code
2. Install new dependencies: `pip install -r requirements.txt`
3. Restart application

### Updating WordPress Integration
1. Update `wordpress-integration.php`
2. Clear any WordPress caches
3. Test functionality

## 📞 Support

### Health Checks
- Flask: `http://your-domain:5001/api/health`
- WordPress: Settings > Dehumidifier Chat (connection status)

### Logs
- Flask: `conversation_logs/` directory
- WordPress: WordPress error logs
- Browser: Developer console

---

## 🎯 Production Checklist

- [ ] Set strong `SECRET_KEY`
- [ ] Configure `OPENAI_API_KEY` (or use demo mode)
- [ ] Update CORS origins in Flask app
- [ ] Set correct server URL in WordPress
- [ ] Test on mobile devices
- [ ] Verify analytics tracking
- [ ] Check security headers
- [ ] Monitor error logs
- [ ] Set up backup strategy 