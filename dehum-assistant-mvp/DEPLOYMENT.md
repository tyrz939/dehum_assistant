# 🚀 Deployment Guide: Git-Based WordPress Plugin Updates

This guide shows you how to set up automatic plugin updates directly from your Git repository.

## 📋 Prerequisites

- WordPress website with admin access
- Git repository (GitHub, GitLab, etc.)
- Basic knowledge of WordPress plugins

## 🔧 Setup Methods

### Method 1: GitHub Updater (Recommended)

**Best for**: Most users, easiest setup, most reliable

#### Step 1: Install GitHub Updater Plugin

1. **Download GitHub Updater**:
   - Go to: https://github.com/afragen/github-updater
   - Download latest release
   - Install via WordPress admin → Plugins → Add New → Upload

2. **Activate GitHub Updater**:
   - Activate the plugin in WordPress admin

#### Step 2: Configure Repository

1. **Update Plugin Header**:
   ```php
   // In dehum-assistant-mvp.php, already configured:
   * GitHub Plugin URI: tyrz939/dehum_assistant
   
   // This is already set for your repository!
   ```

2. **Update Updater Class**:
   ```php
   // In dehum-assistant-mvp.php, already configured:
   new Dehum_MVP_Updater(__FILE__, 'tyrz939/dehum_assistant');
   
   // This is already set for your repository!
   ```

#### Step 3: Deploy Plugin

1. **Upload to WordPress**:
   ```bash
   # Method A: Direct upload
   zip -r dehum-assistant-mvp.zip dehum-assistant-mvp/
   # Upload via WordPress admin
   
   # Method B: FTP/SSH
   scp -r dehum-assistant-mvp/ user@yoursite.com:/wp-content/plugins/
   ```

2. **Activate Plugin**:
   - Go to WordPress admin → Plugins
   - Activate "Dehumidifier Assistant MVP"

### Method 2: Built-in Updater (Backup)

**Best for**: Advanced users, custom setups

The plugin includes a built-in updater that works automatically if GitHub Updater is not available.

## 🔄 Update Workflow

### For Developers (Pushing Updates)

1. **Make Changes**:
   ```bash
   # Edit plugin files
   git add .
   git commit -m "Add new feature"
   ```

2. **Update Version**:
   ```php
   // In dehum-assistant-mvp.php
   * Version: 2.4.0  // Increment version number
   ```

3. **Create Release**:
   ```bash
   # Tag the release
   git tag v2.4.0
   git push origin main --tags
   ```

4. **GitHub Release (Optional)**:
   - Go to GitHub → Releases → Create new release
   - Use tag `v2.4.0`
   - Add release notes

### For Website Owners (Receiving Updates)

1. **Automatic Detection**:
   - WordPress checks for updates every 12 hours
   - Updates appear in admin → Plugins → Updates

2. **Manual Check**:
   - Go to admin → Plugins
   - Click "Check for updates"

3. **Update Plugin**:
   - Click "Update now" like any WordPress plugin
   - Plugin updates automatically from Git

## 🔒 Security Considerations

### Public Repositories

```php
// Plugin works with public GitHub repos out of the box
* GitHub Plugin URI: username/public-repo
```

### Private Repositories

1. **GitHub Personal Access Token**:
   ```php
   // Add to wp-config.php
   define('GITHUB_ACCESS_TOKEN', 'your_token_here');
   ```

2. **WordPress Constants**:
   ```php
   // In wp-config.php
   define('GITHUB_UPDATER_EXTENDED_NAMING', true);
   ```

## 🐛 Troubleshooting

### Updates Not Appearing

1. **Check Repository URL**:
   ```php
   // Verify in plugin header
   * GitHub Plugin URI: correct-username/correct-repo
   ```

2. **Clear WordPress Caches**:
   ```bash
   # Delete transients
   wp transient delete --all
   ```

3. **Check Error Logs**:
   ```bash
   # WordPress debug log
   tail -f /wp-content/debug.log
   ```

### Plugin Not Updating

1. **Version Numbers**:
   - Ensure new version > current version
   - Use semantic versioning (2.1.0, 2.1.1, 2.2.0)

2. **GitHub Releases**:
   - Create proper GitHub releases with tags
   - Use format: `v2.1.0`

3. **Plugin Header**:
   ```php
   // Must match exactly
   * Version: 2.1.0
   define('DEHUM_MVP_VERSION', '2.1.0');
   ```

## 📊 Update Monitoring

### WordPress Admin

- **Plugins Page**: Shows available updates
- **Dashboard**: Update notifications
- **Tools → Dehumidifier Logs**: Plugin-specific logs

### Developer Monitoring

```bash
# Check update transients
wp transient get dehum_mvp_remote_version

# Force update check
wp transient delete dehum_mvp_remote_version
```

## 🚀 Production Deployment Checklist

### Initial Deployment

- [ ] Repository configured correctly
- [ ] GitHub Updater installed and activated
- [ ] Plugin uploaded and activated
- [ ] n8n webhook configured
- [ ] Test chat functionality
- [ ] Verify admin interface works

### Update Deployment

- [ ] Version number incremented
- [ ] Changes committed to Git
- [ ] Release tagged (v2.x.x)
- [ ] GitHub release created (optional)
- [ ] WordPress update detected
- [ ] Update tested on staging site
- [ ] Update applied to production

## 🔄 Rollback Procedure

### If Update Fails

1. **Via WordPress**:
   - Deactivate plugin
   - Delete plugin folder
   - Re-upload previous version

2. **Via Git**:
   ```bash
   # Revert to previous version
   git checkout v2.2.0
   git tag v2.2.1  # Higher version number
   git push origin main --tags
   ```

3. **Emergency Rollback**:
   ```bash
   # Quick file replacement
   cd /wp-content/plugins/
   rm -rf dehum-assistant-mvp/
   # Upload backup copy
   ```

## ✅ Success Indicators

- **Updates appear in WordPress admin**
- **Version numbers increment correctly**
- **Plugin functionality remains intact**
- **No PHP errors in logs**
- **Admin interface accessible**
- **Chat widget works on frontend**

---

## 📞 Support

### Common Issues

1. **"No updates available"**:
   - Check repository URL in plugin header
   - Verify GitHub Updater is active
   - Clear WordPress transients

2. **"Update failed"**:
   - Check file permissions
   - Verify repository access
   - Review WordPress error logs

3. **"Plugin broken after update"**:
   - Check PHP error logs
   - Verify all files uploaded correctly
   - Consider rollback procedure

### Getting Help

- **WordPress Logs**: `/wp-content/debug.log`
- **Plugin Logs**: Tools → Dehumidifier Logs
- **GitHub Issues**: Repository issues page
- **WordPress Support**: WordPress.org forums

---

**🎉 You're now ready for professional Git-based plugin updates!** 