# Dehumidifier Assistant MVP

A complete WordPress plugin for dehumidifier sales and support, featuring AI-powered chat assistance, professional admin interface, and seamless n8n integration.

## 🚀 Features

- **AI-Powered Chat Widget**: Responsive chat interface with n8n integration
- **Professional Admin Interface**: Conversation logging with natural chat flow display
- **Session Management**: Proper conversation threading and persistence
- **Security & Performance**: Rate limiting, encrypted credentials, optimized database
- **Mobile-First Design**: Responsive across all devices
- **Automatic Updates**: GitHub-based update system

## 📋 Requirements

- WordPress 5.0+
- PHP 7.4+
- n8n instance (self-hosted or cloud)
- OpenAI API access

## 🔧 Installation

### Method 1: GitHub Updater (Recommended)

1. **Install GitHub Updater Plugin**:
   ```bash
   # Download from: https://github.com/afragen/github-updater
   # Or install via WordPress admin
   ```

2. **Install This Plugin**:
   - Download the latest release from this repository
   - Upload to `/wp-content/plugins/dehum-assistant-mvp/`
   - Activate in WordPress admin

3. **Configure Auto-Updates**:
   - GitHub Updater will automatically detect updates
   - Updates appear in WordPress admin under Plugins → Updates

### Method 2: Manual Installation

1. **Download & Upload**:
   ```bash
   cd /wp-content/plugins/
git clone https://github.com/tyrz939/dehum_assistant.git dehum-assistant-mvp
   ```

2. **Activate Plugin**:
   - Go to WordPress admin → Plugins
   - Activate "Dehumidifier Assistant MVP"

## ⚙️ Configuration

### 1. n8n Webhook Setup

1. **Create n8n Workflow**:
   - Add Webhook Trigger node
   - Add OpenAI Chat Model node
   - Add HTTP Response node
   - Deploy workflow

2. **Configure WordPress**:
   - Go to Tools → Dehumidifier Logs
   - Enter your n8n webhook URL
   - Add webhook credentials (if using Basic Auth)
   - Save settings

### 2. Basic n8n Workflow Structure

```json
{
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "path": "dehum-chat",
        "httpMethod": "POST"
      }
    },
    {
      "name": "OpenAI Chat Model",
      "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
      "parameters": {
        "model": "gpt-4o",
        "temperature": 0.7
      }
    },
    {
      "name": "Response",
      "type": "n8n-nodes-base.respondToWebhook",
      "parameters": {
        "responseBody": "={{ {\"success\": true, \"response\": $json.response} }}"
      }
    }
  ]
}
```

## 🔄 Updates

### Automatic Updates (GitHub Updater)

1. **Push to Repository**:
   ```bash
   git add .
   git commit -m "Update plugin to v2.4.0"
   git tag v2.4.0
   git push origin main --tags
   ```

2. **Update Plugin Header**:
   ```php
   * Version: 2.4.0
   ```

3. **WordPress Will Detect**:
   - Updates appear in admin within 24 hours
   - Users can update via standard WordPress update process

### Manual Updates

```bash
cd /wp-content/plugins/dehum-assistant-mvp/
git pull origin main
```

## 📊 Usage

### For End Users

1. **Chat Widget**: Appears on all frontend pages
2. **Mobile**: Full-screen chat experience
3. **Desktop**: Floating chat widget (bottom-right)
4. **Clear Conversation**: Use 🗑️ button to start fresh

### For Administrators

1. **View Conversations**: Tools → Dehumidifier Logs
2. **Filter & Search**: Use built-in filtering options
3. **Export Data**: Export conversations to CSV
4. **Manage Settings**: Configure n8n webhook and credentials

## 🛠️ Development

### Local Development Setup

```bash
# Clone repository
git clone https://github.com/tyrz939/dehum_assistant.git

# Install in WordPress
ln -s /path/to/dehum-assistant /wp-content/plugins/dehum-assistant-mvp

# Activate plugin in WordPress admin
```

### File Structure

```
dehum-assistant-mvp/
├── assets/
│   ├── css/
│   │   ├── admin.css
│   │   └── chat.css
│   └── js/
│       ├── admin.js
│       └── chat.js
├── includes/
│   ├── class-dehum-mvp-main.php
│   ├── class-dehum-mvp-admin.php
│   ├── class-dehum-mvp-frontend.php
│   ├── class-dehum-mvp-ajax.php
│   ├── class-dehum-mvp-database.php
│   └── views/
│       ├── view-dashboard-widget.php
│       └── view-logs-page.php
├── dehum-assistant-mvp.php
└── README.md
```

## 🔒 Security Features

- **Nonce Protection**: All AJAX requests protected
- **Rate Limiting**: 50 messages per day per IP
- **Encrypted Credentials**: n8n passwords encrypted with WordPress salts
- **Input Sanitization**: All user inputs sanitized
- **SQL Injection Protection**: Prepared statements throughout

## 📈 Performance

- **Database Optimization**: Composite indexes for fast queries
- **Caching**: WordPress transients for rate limiting
- **Minimal Footprint**: Only loads assets when needed
- **Responsive Design**: Optimized for all devices

## 🆘 Support

### Common Issues

1. **Chat Not Working**:
   - Check n8n webhook URL in settings
   - Verify n8n workflow is active
   - Check browser console for errors

2. **Admin Interface Issues**:
   - Clear browser cache
   - Check WordPress error logs
   - Verify user permissions

3. **Update Issues**:
   - Ensure GitHub Updater is installed
   - Check repository permissions
   - Verify plugin header format

### Logs & Debugging

- **WordPress Logs**: Check `wp-content/debug.log`
- **Plugin Logs**: Tools → Dehumidifier Logs
- **Browser Console**: Check for JavaScript errors
- **n8n Logs**: Check n8n execution history

## 📝 Changelog

### Version 2.3.0
- ✅ Fixed session ID continuity
- ✅ Enhanced admin conversation display
- ✅ Added clear conversation feature
- ✅ Improved responsive design
- ✅ Added GitHub Updater support

### Version 2.2.0
- ✅ Added credential encryption
- ✅ Implemented database indexes
- ✅ Enhanced security measures
- ✅ Mobile chat widget improvements

### Version 2.1.0
- ✅ Refactored to class-based architecture
- ✅ Added professional admin interface
- ✅ Implemented conversation logging
- ✅ Added rate limiting

## 📄 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

**Ready for production deployment with automatic updates!** 🚀 