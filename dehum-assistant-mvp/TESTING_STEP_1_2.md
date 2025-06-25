# 🧪 Step 1.2 Testing Checklist - Basic Plugin Registration

**Goal**: Verify plugin registration works correctly across different WordPress environments.

## 📋 **Testing Requirements**

### **✅ Primary Tests**
- [ ] Plugin appears in WordPress admin
- [ ] Activation works without errors
- [ ] Deactivation works cleanly
- [ ] No PHP errors in debug log
- [ ] Assets load correctly

### **✅ Compatibility Tests**
- [ ] Works with default WordPress themes
- [ ] No JavaScript conflicts
- [ ] Mobile responsive across devices
- [ ] Works with common page builders

---

## 🔧 **Test Procedures**

### **Test 1: WordPress Installation**

1. **Copy Plugin**:
   ```bash
   # Copy entire folder to WordPress
   cp -r dehum-assistant-mvp/ /path/to/wordpress/wp-content/plugins/
   ```

2. **Check File Permissions**:
   - Plugin folder: 755
   - PHP files: 644
   - CSS/JS files: 644

3. **Verify Structure**:
   ```
   wp-content/plugins/dehum-assistant-mvp/
   ├── dehum-assistant-mvp.php
   ├── assets/css/chat.css
   ├── assets/js/chat.js
   └── README.md
   ```

### **Test 2: Plugin Activation**

1. **Enable WordPress Debug Mode**:
   ```php
   // Add to wp-config.php
   define('WP_DEBUG', true);
   define('WP_DEBUG_LOG', true);
   define('WP_DEBUG_DISPLAY', false);
   ```

2. **Activate Plugin**:
   - Go to WordPress Admin → Plugins
   - Find "Dehumidifier Assistant MVP"
   - Click "Activate"
   - ✅ **Expected**: No error messages

3. **Check Debug Log**:
   ```bash
   # Check for errors
   tail -f wp-content/debug.log
   ```
   - ✅ **Expected**: No PHP errors related to our plugin

### **Test 3: Frontend Verification**

1. **Visit Frontend**:
   - Go to any page on your site
   - ✅ **Expected**: Blue chat button appears bottom-right

2. **Test Chat Widget**:
   - Click chat button
   - ✅ **Expected**: Modal opens smoothly
   - Type a message and send
   - ✅ **Expected**: Demo response appears

3. **Check Browser Console**:
   - Press F12 → Console tab
   - ✅ **Expected**: See "Dehumidifier Assistant MVP loaded successfully!"
   - ❌ **No Errors**: No JavaScript errors

### **Test 4: Asset Loading**

1. **Verify CSS Loading**:
   - View page source
   - Search for: `chat.css`
   - ✅ **Expected**: CSS file included with version number

2. **Verify JS Loading**:
   - View page source  
   - Search for: `chat.js`
   - ✅ **Expected**: JS file included with jQuery dependency

3. **Check Network Tab**:
   - F12 → Network tab → Reload page
   - ✅ **Expected**: Both CSS and JS files load (200 status)

### **Test 5: Theme Compatibility**

1. **Test with Default Themes**:
   - Twenty Twenty-Three
   - Twenty Twenty-Two
   - Twenty Twenty-One
   - ✅ **Expected**: Chat button appears on all themes

2. **Check Footer Hook**:
   - Ensure theme has `<?php wp_footer(); ?>`
   - ✅ **Expected**: Chat widget renders via wp_footer hook

### **Test 6: Mobile Testing**

1. **Responsive Design**:
   - Test on mobile device or browser dev tools
   - ✅ **Expected**: Chat modal fills full screen on mobile
   - ✅ **Expected**: Touch interactions work properly

2. **Touch Events**:
   - Tap chat button
   - Tap send button
   - Tap close button
   - ✅ **Expected**: All touch interactions work

### **Test 7: AJAX Functionality**

1. **Send Test Message**:
   - Open chat → Type "Hello" → Send
   - ✅ **Expected**: Typing indicator appears
   - ✅ **Expected**: Demo response: "Thanks for your message: 'Hello'..."

2. **Check AJAX Request**:
   - F12 → Network tab
   - Send message
   - Look for POST to `admin-ajax.php`
   - ✅ **Expected**: 200 status with JSON response

### **Test 8: Plugin Deactivation**

1. **Deactivate Plugin**:
   - WordPress Admin → Plugins → Deactivate
   - ✅ **Expected**: No errors

2. **Verify Cleanup**:
   - Visit frontend
   - ✅ **Expected**: Chat button no longer appears
   - Check debug log
   - ✅ **Expected**: No errors during deactivation

---

## 🚨 **Common Issues & Solutions**

### **Issue: Plugin Not Appearing**
```php
// Check plugin headers in dehum-assistant-mvp.php
/**
 * Plugin Name: Dehumidifier Assistant MVP
 * Version: 1.0.0
 * Description: Minimal viable chat widget...
 */
```
**Solution**: Ensure proper plugin headers format

### **Issue: Chat Button Not Showing**
**Possible Causes**:
- Theme missing `wp_footer()` hook
- JavaScript errors preventing load
- CSS conflicts

**Debug Steps**:
1. Check browser console for errors
2. Verify wp_footer() in theme
3. Test with default theme

### **Issue: AJAX Not Working**
**Debug Steps**:
1. Check nonce verification
2. Verify admin-ajax.php endpoint
3. Check for JavaScript errors

### **Issue: Assets Not Loading**
**Debug Steps**:
1. Check file permissions
2. Verify asset URLs in source
3. Check for 404 errors in Network tab

---

## 📊 **Step 1.2 Success Criteria**

### **Must Pass All**:
- [ ] Plugin activates without errors
- [ ] Chat button appears on frontend
- [ ] AJAX demo responses work
- [ ] No JavaScript console errors
- [ ] Mobile responsive design works
- [ ] Deactivation works cleanly

### **Performance Targets**:
- [ ] Page load time increase < 100ms
- [ ] CSS file size < 10KB
- [ ] JS file size < 15KB
- [ ] Chat modal opens in < 300ms

---

## 🎯 **Next Steps After Step 1.2**

### **If All Tests Pass**:
✅ Move to **Day 2: n8n Workflow Setup**
- Create basic n8n workflow
- Test webhook integration
- Add OpenAI processing

### **If Tests Fail**:
❌ Fix issues before proceeding:
- Debug specific failing tests
- Check WordPress error logs  
- Test with different themes
- Verify file permissions

---

**Time Estimate**: 30 minutes testing  
**Tools Needed**: WordPress site, browser dev tools, file access  
**Output**: Verified working plugin ready for n8n integration 