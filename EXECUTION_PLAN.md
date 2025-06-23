# Dehumidifier Assistant - Execution Plan
## PHP Plugin + n8n Hybrid Migration

---

## 🎯 **Phase 1: Foundation (Week 1-2)**
**Goal: Replace Flask with PHP+n8n hybrid, maintain current functionality**

### **Chunk 1: Development Environment Setup (Day 1)**

**WordPress Development Site:**
- Fresh WordPress install (local or staging)
- Enable WP debug mode (`WP_DEBUG = true`)
- Install development tools:
  - Query Monitor (debugging)
  - Advanced Custom Fields (if needed)
  - Code Snippets (for testing)

**n8n Connection Test:**
- Create simple test workflow in your self-hosted n8n
- Test webhook reception from external source
- Verify n8n can make HTTP requests back to WordPress
- Test basic OpenAI node functionality

**Deliverable:** Working development environment with WordPress ↔ n8n communication

---

### **Chunk 2: Basic PHP Plugin Structure (Day 2-3)**

**Plugin Foundation:**
```
dehum-assistant/
├── dehum-assistant.php (main plugin file)
├── includes/
│   ├── class-dehum-admin.php
│   ├── class-dehum-ajax.php
│   └── class-dehum-database.php
├── assets/
│   ├── css/dehum-style.css
│   ├── js/dehum-chat.js
│   └── images/
└── templates/
    └── chat-interface.php
```

**Core Files:**
- Main plugin file with proper headers
- Activation/deactivation hooks
- Basic admin menu structure
- Enqueue scripts and styles

**Database Setup:**
- Create `dehum_conversations` table
- Create `dehum_leads` table (for future use)
- Database creation on activation
- Cleanup on deactivation

**Deliverable:** WordPress plugin structure with database tables

---

### **Chunk 3: Basic Chat Interface (Day 4-5)**

**Frontend Chat UI:**
- **IMPORTANT: Keep the clickable box in bottom right corner** ✅
- Copy existing HTML/CSS/JS from current templates
- Adapt JavaScript to use WordPress AJAX instead of Flask endpoints
- Maintain current styling and user experience
- Preserve retry functionality and error handling

**WordPress AJAX Integration:**
- `wp_ajax_dehum_chat` handler for logged-in users
- `wp_ajax_nopriv_dehum_chat` handler for visitors
- Proper nonce verification for security
- JSON response formatting

**Key Features to Preserve:**
- ✅ Bottom-right clickable chat box
- ✅ Expandable chat interface
- ✅ Message history in localStorage
- ✅ Character counter
- ✅ Retry buttons on errors
- ✅ Typing indicators

**Deliverable:** Working chat interface that matches current Flask UI

---

### **Chunk 4: First n8n Workflow (Day 6-7)**

**Basic n8n Workflow Nodes:**
1. **Webhook Trigger** - Receive chat messages from WordPress
2. **Data Processing** - Extract user input and conversation history
3. **OpenAI Node** - Process with existing prompt template
4. **Response Formatting** - Structure response for WordPress
5. **HTTP Request** - Send response back to WordPress
6. **Error Handling** - Manage API failures gracefully

**Workflow Configuration:**
- Import existing prompt template from `prompt_template.txt`
- Import product database from `product_db.json`
- Configure OpenAI API key
- Set up proper error handling and retries

**Integration Points:**
- WordPress sends: `{user_input, conversation_history, session_id}`
- n8n returns: `{response, success, error_info}`
- Logging: Both systems log for debugging

**Deliverable:** Complete WordPress ↔ n8n ↔ OpenAI workflow

---

### **Chunk 5: Integration Testing & Refinement (Day 8-10)**

**End-to-End Testing:**
- Test complete conversation flow
- Verify conversation history persistence
- Test error handling and retry functionality
- Performance testing (response times)
- Mobile responsiveness check

**Migration Validation:**
- Compare responses with current Flask system
- Verify all current features work
- Test edge cases and error conditions
- Validate conversation logging

**Deliverable:** Feature parity with current Flask system

---

## 🎯 **Phase 2: Enhanced Intelligence (Week 3-4)**

### **Chunk 6: Contact Capture System (Day 11-12)**

**PHP Plugin Enhancements:**
- Contact form modal for escalation scenarios
- Lead management in WordPress admin
- Email notification system
- Lead status tracking

**n8n Workflow Additions:**
- Human handoff decision logic
- Lead scoring based on conversation content
- Email routing to sales team
- CRM integration preparation

**Deliverable:** Smart lead capture and routing system

---

### **Chunk 7: Domain Filtering & AI Classification (Day 13-14)**

**Input Validation:**
- Basic keyword filtering in PHP
- Off-topic detection and polite redirects
- Usage analytics and tracking

**n8n AI Classification:**
- Advanced topic classification using AI
- Context-aware response routing
- Conversation quality scoring

**Deliverable:** Professional, focused chat experience

---

## 🎯 **Phase 3: Advanced Features (Month 2)**

### **Chunk 8: Dedicated Sizing Calculator (Day 15-18)**

**n8n Calculation Engine:**
- Port Python sizing logic to JavaScript
- Enhanced calculation accuracy
- Multiple unit recommendations
- Temperature multiplier handling

**PHP Display Interface:**
- Calculation result formatting
- Alternative product suggestions
- Visual sizing recommendations

**Deliverable:** Professional sizing tool with accurate calculations

---

### **Chunk 9: Reference Materials System (Day 19-22)**

**Document Management:**
- PDF storage and indexing
- Search functionality
- Context-aware document retrieval

**n8n Processing:**
- Document search workflows
- Content extraction and formatting
- Relevant information filtering

**Deliverable:** Comprehensive reference system

---

### **Chunk 10: Quote Generation & CRM Integration (Day 23-30)**

**Quote System:**
- PDF generation with company branding
- Pricing calculations
- Quote tracking and follow-up

**CRM Integration:**
- Lead export to external systems
- Automated follow-up sequences
- Sales pipeline integration

**Deliverable:** Complete business tool with sales integration

---

## 📋 **Key Requirements Checklist**

### **UI/UX Requirements:**
- ✅ **Keep clickable box in bottom right corner** (CRITICAL)
- ✅ Maintain current chat interface design
- ✅ Preserve retry functionality
- ✅ Keep conversation history
- ✅ Mobile responsiveness

### **Functional Requirements:**
- ✅ Elementor widget integration
- ✅ WordPress admin dashboard
- ✅ Conversation logging
- ✅ Lead capture and routing
- ✅ Domain-specific filtering
- ✅ Accurate sizing calculations

### **Technical Requirements:**
- ✅ Self-hosted n8n integration
- ✅ OpenAI API compatibility
- ✅ Error handling and retries
- ✅ Security (nonces, validation)
- ✅ Performance optimization

---

## 🚀 **Success Metrics**

**Phase 1 Success:**
- Chat interface works identically to Flask version
- Response times under 3 seconds
- Zero data loss during migration
- All current features functional

**Phase 2 Success:**
- Lead capture rate >80% for escalation scenarios
- Off-topic queries properly redirected
- Email notifications working reliably

**Phase 3 Success:**
- Sizing accuracy improved over current system
- Quote generation functional
- CRM integration operational
- Complete business workflow automated

---

## 📞 **Support & Troubleshooting**

**Common Issues:**
- WordPress AJAX not working → Check nonce verification
- n8n webhook not receiving → Verify URL and method
- OpenAI API errors → Check rate limits and error handling
- Chat box not appearing → Check CSS/JS enqueuing

**Testing Checklist:**
- [ ] Chat box appears in bottom right
- [ ] Messages send and receive properly
- [ ] Conversation history persists
- [ ] Error handling works
- [ ] Admin dashboard shows conversations
- [ ] n8n workflow processes correctly
- [ ] OpenAI responses are relevant
- [ ] Mobile interface works

**Next Phase Readiness:**
- [ ] All current features migrated
- [ ] Performance acceptable
- [ ] No critical bugs
- [ ] Documentation updated
- [ ] Backup and rollback plan ready 