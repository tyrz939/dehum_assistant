# 🚀 MVP WordPress Plugin Implementation Plan

**Goal**: Build a minimal viable WordPress plugin that delivers the core features from PROJECT_ROADMAP.md through small, testable increments.

## 🎯 **MVP Success Criteria**
- ✅ Chat widget appears on WordPress pages
- ✅ Messages sent to n8n workflow  
- ✅ AI responses displayed in chat
- ✅ Basic conversation logging
- ✅ Elementor integration working
- ✅ Domain filtering active

---

## 📋 **PHASE 1: FOUNDATION (Week 1)**
*Goal: Get basic chat working end-to-end*

### **Day 1: Project Setup & Basic Plugin**

#### **Step 1.1: Create Plugin Structure** (30 mins)
```
wp-content/plugins/dehum-assistant-mvp/
├── dehum-assistant-mvp.php      # Main plugin file
├── assets/
│   ├── css/chat.css            # Chat widget styles
│   └── js/chat.js              # Chat functionality
└── README.md                   # Plugin documentation
```

#### **Step 1.2: Basic Plugin Registration** (30 mins)
- WordPress plugin headers
- Activation/deactivation hooks
- Enqueue CSS/JS files
- **Test**: Plugin appears in WordPress admin

#### **Step 1.3: Static Chat Widget** (1 hour)
- Copy styling from `templates/popup.html`
- Add floating chat button (bottom-right)
- Static modal popup (no functionality)
- **Test**: Chat button appears and opens modal

---

### **Day 2: n8n Workflow Setup**

#### **Step 2.1: Create Basic n8n Workflow** (1 hour)
- Webhook trigger node
- HTTP Response node (echo back input)
- **Test**: Webhook receives POST and responds

#### **Step 2.2: Add OpenAI Integration** (30 mins)
- Add OpenAI node to workflow
- Use existing `prompt_template.txt`
- **Test**: n8n can call OpenAI and get response

#### **Step 2.3: Response Formatting** (30 mins)
- Format n8n response for WordPress
- Return JSON: `{"success": true, "response": "text"}`
- **Test**: Webhook returns properly formatted JSON

---

### **Day 3: WordPress ↔ n8n Integration**

#### **Step 3.1: AJAX Handler** (1 hour)
- `wp_ajax_dehum_chat` handler
- Basic nonce security
- Send to n8n webhook via `wp_remote_post()`
- **Test**: WordPress can call n8n successfully

#### **Step 3.2: Frontend JavaScript** (1 hour)
- Send messages via AJAX
- Display responses in chat interface
- Basic error handling
- **Test**: Full chat conversation works

#### **Step 3.3: Message History** (30 mins)
- Store conversation in localStorage
- Display chat history on page refresh
- **Test**: Conversation persists across page loads

---

### **Day 4: Error Handling & Polish**

#### **Step 4.1: Error Handling** (1 hour)
- Handle n8n webhook failures
- Retry mechanism (3 attempts)
- User-friendly error messages
- **Test**: Graceful degradation when n8n fails

#### **Step 4.2: Basic Rate Limiting** (30 mins)
- WordPress transients for rate limiting
- 20 messages per day per IP
- **Test**: Rate limiting prevents abuse

#### **Step 4.3: Mobile Optimization** (30 mins)
- Responsive CSS for mobile devices
- Touch-friendly chat interface
- **Test**: Works well on mobile devices

---

### **Day 5: Basic Logging**

#### **Step 5.1: Database Table** (30 mins)
- Create `wp_dehum_conversations` table
- Simple schema: session_id, message, response, timestamp
- **Test**: Table created on plugin activation

#### **Step 5.2: Conversation Logging** (30 mins)
- Log all conversations to database
- Include user IP and timestamp
- **Test**: Conversations appear in database

#### **Step 5.3: Basic Admin View** (1 hour)
- Simple admin page to view conversations
- Basic search/filter functionality
- **Test**: Admin can view conversation logs

---

## 📋 **PHASE 2: SMART FEATURES (Week 2)**
*Goal: Add intelligence and business logic*

### **Day 6-7: Elementor Integration**

#### **Step 6.1: Elementor Widget Class** (2 hours)
- Register custom Elementor widget
- Widget controls (title, settings)
- Render chat interface in widget
- **Test**: Widget appears in Elementor editor

#### **Step 6.2: Widget Customization** (1 hour)
- Widget settings (enable/disable, positioning)
- Custom styling options
- **Test**: Marketing team can place widget anywhere

### **Day 8-9: Domain Filtering**

#### **Step 8.1: n8n Domain Filter** (1 hour)
- Add domain filtering node to n8n workflow
- Keyword detection for dehumidifier topics
- **Test**: Off-topic questions get polite redirect

#### **Step 8.2: Professional Responses** (30 mins)
- Template responses for off-topic queries
- Redirect to dehumidifier-related help
- **Test**: Users guided back to relevant topics

### **Day 10: Product Database Integration**

#### **Step 10.1: Product Data in n8n** (1 hour)
- Import `product_db.json` into n8n workflow
- Make product data available to AI
- **Test**: AI can recommend specific products

#### **Step 10.2: Structured Responses** (1 hour)
- Parse AI responses for product recommendations
- Display product info in chat (name, price, SKU)
- **Test**: Product recommendations formatted nicely

---

## 📋 **PHASE 3: BUSINESS FEATURES (Week 3)**
*Goal: Add lead capture and handoff logic*

### **Day 11-12: Lead Scoring**

#### **Step 11.1: n8n Lead Scoring** (2 hours)
- Add lead scoring logic to n8n workflow
- Score based on: room size, commercial use, budget mentions
- **Test**: Conversations generate lead scores

#### **Step 11.2: High-Value Lead Detection** (1 hour)
- Trigger alerts for high-scoring leads
- Log lead scores in WordPress database
- **Test**: High-value leads flagged appropriately

### **Day 13-14: Human Handoff**

#### **Step 13.1: Escalation Triggers** (1 hour)
- Detect when conversation needs human help
- Trigger contact form in chat interface
- **Test**: Complex questions trigger handoff

#### **Step 13.2: Contact Capture** (2 hours)
- Contact form modal in chat interface
- Save lead information to database
- Email notifications to sales team
- **Test**: Lead capture workflow complete

### **Day 15: Reference Materials**

#### **Step 15.1: Reference Integration** (2 hours)
- Add reference materials to n8n workflow
- Smart reference selection based on context
- **Test**: AI provides relevant technical information

---

## 🎯 **VALIDATION CHECKPOINTS**

### **End of Week 1:**
- [ ] Chat widget works end-to-end
- [ ] n8n integration functional
- [ ] Basic conversation logging active
- [ ] Error handling robust
- [ ] Mobile-friendly interface

### **End of Week 2:**
- [ ] Elementor integration complete
- [ ] Domain filtering active
- [ ] Product recommendations working
- [ ] Professional user experience

### **End of Week 3:**
- [ ] Lead scoring operational
- [ ] Human handoff triggers working
- [ ] Contact capture functional
- [ ] Reference materials integrated

---

## 🛠️ **DAILY WORKFLOW**

### **Start Each Day:**
1. **Test previous day's work** (15 mins)
2. **Plan today's tasks** (15 mins)
3. **Code/implement** (3-4 hours)
4. **Test thoroughly** (30 mins)
5. **Document progress** (15 mins)

### **End Each Day:**
- [ ] All tests pass
- [ ] Code committed to git
- [ ] Next day's tasks planned
- [ ] Any blockers identified

---

## 🚨 **RISK MITIGATION**

### **Common Pitfalls:**
- **n8n webhook fails**: Implement fallback demo mode
- **WordPress conflicts**: Use unique function names and CSS classes
- **Mobile issues**: Test on real devices frequently
- **Performance problems**: Implement proper caching

### **Success Metrics:**
- **Response time**: < 3 seconds for AI responses
- **Error rate**: < 5% of conversations fail
- **User engagement**: Average 3+ messages per conversation
- **Mobile usage**: Works on 95% of mobile devices

---

## 📊 **PROGRESS TRACKING**

### **Week 1 Progress:**
- [x] Day 1: Basic plugin structure ✅ **COMPLETE**
  - [x] Step 1.1: Create Plugin Structure ✅ 
  - [x] Step 1.2: Basic Plugin Registration ✅
  - [x] Step 1.3: Static Chat Widget ✅ 
- [ ] Day 2: n8n workflow setup 
- [ ] Day 3: WordPress integration 
- [ ] Day 4: Error handling 
- [ ] Day 5: Basic logging

### **Week 2 Progress:**
- [ ] Day 6-7: Elementor integration ✅
- [ ] Day 8-9: Domain filtering ✅
- [ ] Day 10: Product database ✅

### **Week 3 Progress:**
- [ ] Day 11-12: Lead scoring ✅
- [ ] Day 13-14: Human handoff ✅
- [ ] Day 15: Reference materials ✅

---

**Total Time Investment: ~40 hours over 3 weeks**
**Expected Outcome: Production-ready MVP with all roadmap features**

## 🎯 **NEXT STEP**

Ready to start? Begin with **Step 1.1: Create Plugin Structure** and work through each step methodically. Each step should take 30 minutes to 2 hours maximum.

**Remember**: Test everything immediately, commit often, and don't move to the next step until the current one works perfectly. 