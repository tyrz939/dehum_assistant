# Dehumidifier Assistant - Project Roadmap & Vision

## 🎯 Core Vision
Transform the dehumidifier assistant from a basic chat interface into a comprehensive business tool that:
- Qualifies leads through intelligent conversation
- Provides accurate sizing calculations
- Seamlessly hands off complex cases to human experts
- Integrates directly into WordPress/Elementor for maximum reach

## 🏗️ **AGREED ARCHITECTURE: PHP Plugin + n8n Hybrid**

### **Architecture Decision**
**Hybrid approach combining WordPress-native PHP plugin with self-hosted n8n workflows:**

- **PHP Plugin (UI Shell)**: WordPress integration, Elementor widget, chat interface, local logging, admin dashboard
- **n8n Workflows (Intelligence Engine)**: AI processing, sizing calculations, lead scoring, external integrations, data routing

### **Division of Responsibilities**
```
User Interaction → PHP Plugin → n8n Webhook → AI Processing → Response
                      ↓                           ↓
              WP Database                External Systems
              (conversations)            (CRM, email, etc.)
```

**Benefits:**
- ✅ Native WordPress integration (PHP handles what PHP does best)
- ✅ Powerful AI workflows (n8n handles complex logic)
- ✅ Future-proof (easy to modify workflows without touching WordPress)
- ✅ Scalable (add integrations without code changes)
- ✅ Cost-effective (self-hosted n8n, no monthly fees)

---

## 📋 Current Requirements (Your Specifications)

### 1. **Sizing Calculation Tool**
- **Goal**: AI can use dedicated calculation functions instead of estimating
- **Implementation**: Separate calc module that AI calls with parameters
- **Benefits**: More accurate, consistent, auditable sizing recommendations
- **Priority**: HIGH

### 2. **Elementor Integration**
- **Goal**: Easy placement of chat widget in WordPress pages via Elementor
- **Implementation**: Custom Elementor widget/block for the chat interface
- **Benefits**: Marketing team can place assistant anywhere without developer help
- **Priority**: MEDIUM-HIGH

### 3. **Comprehensive Reference Materials**
- **Goal**: AI has access to detailed specs and installation manuals
- **Components**: 
  - Full product specification database
  - Complete installation manual (accessible when needed)
  - Technical documentation library
- **Implementation**: Searchable knowledge base with AI access
- **Priority**: MEDIUM

### 4. **Domain-Specific Filtering**
- **Goal**: Only respond to dehumidifier-related questions
- **Implementation**: Input validation and topic classification
- **Benefits**: Prevents off-topic usage, maintains professional focus
- **Example**: "I can only help with dehumidifier sizing and selection. How can I assist with your humidity control needs?"
- **Priority**: MEDIUM

### 5. **Comprehensive Chat Logging**
- **Goal**: Log all conversations for business intelligence and review
- **Implementation**: WordPress-side logging system with admin dashboard
- **Features**: 
  - Search/filter conversations
  - Lead identification and tracking
  - Performance analytics
  - Export capabilities
- **Priority**: MEDIUM

---

## 🚀 Implementation Priority Matrix (Updated for Hybrid Architecture)

| Feature | PHP Plugin | n8n Workflow | Technical Complexity | Priority |
|---------|------------|--------------|---------------------|----------|
| Basic Chat Interface | ✅ UI Shell | ✅ AI Processing | LOW | 1 |
| Elementor Integration | ✅ Widget | ❌ None | LOW | 2 |
| Chat Logging (WP) | ✅ Database | ✅ Enrichment | LOW | 3 |
| Domain Filtering | ✅ Basic | ✅ AI Classification | LOW | 4 |
| Sizing Calc Tool | ❌ None | ✅ Full Logic | MEDIUM | 5 |
| Human Handoff Engine | ✅ Contact Form | ✅ Lead Routing | MEDIUM | 6 |
| Reference Materials | ✅ Search UI | ✅ Document Processing | MEDIUM | 7 |
| Lead Scoring | ❌ None | ✅ Full Logic | MEDIUM | 8 |
| Quote Generation | ✅ Display | ✅ PDF Creation | HIGH | 9 |

---

## 📊 Success Metrics
- **Conversion Rate**: Chat sessions → qualified leads
- **Accuracy**: Sizing recommendation correctness
- **Engagement**: Average conversation length and depth
- **Sales Impact**: Revenue attributed to AI assistant
- **Efficiency**: Reduction in manual sizing requests

---

## 🔄 Implementation Roadmap

### **Phase 1: Foundation (Week 1-2)**
**Goal: Replace Flask with PHP+n8n hybrid, maintain current functionality**

**PHP Plugin Tasks:**
- WordPress plugin structure and activation
- Basic chat interface (replicate current UI)
- Elementor widget registration
- Database tables for conversation logging
- Admin dashboard for viewing conversations

**n8n Workflow Tasks:**
- Basic webhook receiver for chat messages
- OpenAI API integration with existing prompt
- Simple response logic (sizing recommendations)
- WordPress webhook for storing conversations

**Deliverable: Working chat system with feature parity to current Flask app**

### **Phase 2: Enhanced Intelligence (Week 3-4)**
**Goal: Add smart features that were difficult in Flask**

**PHP Plugin Tasks:**
- Contact capture form for escalations
- Enhanced admin dashboard with lead management
- Search interface for reference materials

**n8n Workflow Tasks:**
- Lead scoring logic based on conversation content
- Human handoff decision engine
- Email notifications for qualified leads
- Domain filtering with AI classification

**Deliverable: Smart lead qualification and routing system**

### **Phase 3: Advanced Features (Month 2)**
**Goal: Add business-critical advanced functionality**

**PHP Plugin Tasks:**
- Quote display interface
- Advanced admin analytics dashboard
- User management and permissions

**n8n Workflow Tasks:**
- Dedicated sizing calculation engine
- Reference material search and processing
- PDF quote generation
- CRM integration workflows
- Multi-step conversation flows

**Deliverable: Complete business tool with advanced features**

---

## 🎯 **Immediate Next Steps**
1. **Set up development environment** (WordPress + n8n connection)
2. **Create basic PHP plugin structure** 
3. **Build first n8n workflow** (webhook → OpenAI → response)
4. **Test integration** between PHP and n8n
5. **Migrate core functionality** from Flask to hybrid system 