# 🚀 Step 1.2: WordPress Installation Guide

**Quick guide to install and test the MVP plugin on WordPress**

## 📦 **Installation Steps**

### **1. Copy Plugin Files**
```bash
# If using FTP/cPanel File Manager:
# Upload the entire 'dehum-assistant-mvp' folder to:
# /public_html/wp-content/plugins/dehum-assistant-mvp/

# If using command line:
cp -r dehum-assistant-mvp/ /path/to/wordpress/wp-content/plugins/
```

### **2. Set File Permissions** (if needed)
```bash
chmod 755 wp-content/plugins/dehum-assistant-mvp/
chmod 644 wp-content/plugins/dehum-assistant-mvp/dehum-assistant-mvp.php
chmod 644 wp-content/plugins/dehum-assistant-mvp/assets/css/chat.css
chmod 644 wp-content/plugins/dehum-assistant-mvp/assets/js/chat.js
```

### **3. Enable Debug Mode** (recommended for testing)
Add to `wp-config.php`:
```php
define('WP_DEBUG', true);
define('WP_DEBUG_LOG', true);
define('WP_DEBUG_DISPLAY', false);
```

### **4. Activate Plugin**
1. Go to WordPress Admin → **Plugins**
2. Find "**Dehumidifier Assistant MVP**"  
3. Click "**Activate**"
4. ✅ Look for success notice: "Dehumidifier Assistant MVP is active!"

## 🧪 **Immediate Tests**

### **Test 1: Admin Confirmation**
- ✅ **Expected**: Green success notice in WordPress admin
- ✅ **Expected**: Plugin listed as "Active" in plugins page
- ❌ **Check**: No error messages or warnings

### **Test 2: Frontend Chat Button**
1. Visit your website frontend
2. ✅ **Expected**: Blue chat button in bottom-right corner
3. Click the chat button
4. ✅ **Expected**: Chat modal opens smoothly

### **Test 3: Demo Conversation**
1. In chat modal, type: "Hello"
2. Click "Send" button
3. ✅ **Expected**: Typing indicator appears
4. ✅ **Expected**: Demo response: "Thanks for your message: 'Hello'..."

### **Test 4: Mobile Check**
1. Open website on mobile (or use browser dev tools)
2. ✅ **Expected**: Chat button visible and tappable
3. ✅ **Expected**: Chat modal fills full screen on mobile

## 🔍 **Debugging**

### **If Plugin Not Showing in Admin**:
- Check file paths are correct
- Verify plugin headers in main PHP file
- Check file permissions

### **If Chat Button Not Appearing**:
- Open browser dev tools (F12)
- Check Console tab for JavaScript errors
- Verify theme has `<?php wp_footer(); ?>` in footer
- Try switching to default WordPress theme

### **If AJAX Not Working**:
- Check browser Network tab when sending message
- Look for POST request to `admin-ajax.php`
- Check WordPress debug log for PHP errors

## 📊 **Success Checklist**

**Step 1.2 Complete When All Pass**:
- [ ] Plugin activates without errors
- [ ] Success notice appears in admin
- [ ] Chat button visible on frontend
- [ ] Chat modal opens and closes
- [ ] Demo AJAX response works
- [ ] No JavaScript console errors
- [ ] Mobile responsive behavior works

## ⏰ **Time Investment**
- **Installation**: 5 minutes
- **Testing**: 10 minutes  
- **Debugging** (if needed): 15 minutes
- **Total**: ~30 minutes

## 🎯 **Next Step**
Once all tests pass, you're ready for **Day 2: n8n Workflow Setup**!

---

**Need Help?** Check `TESTING_STEP_1_2.md` for detailed troubleshooting guide. 