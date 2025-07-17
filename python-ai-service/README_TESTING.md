# Testing Guide for Dehumidifier Assistant

## Information Gathering Tests

The assistant must intelligently decide when to ask for more information vs when to proceed with calculations.

### Quick Test Suite

Run the basic scenarios to verify core functionality:

```bash
python test_quick_pool.py
```

**Test Scenarios:**
1. **Incomplete Info**: "I have an indoor pool" → Should ask for room dimensions, pool size, humidity
2. **Complete Info**: Full room and pool specs → Should calculate load and provide recommendations

### Comprehensive Test Suite

Run the full test suite for thorough validation:

```bash
python test_information_gathering.py
```

**Test Coverage:**
- ✅ Incomplete pool queries ask for info
- ✅ Vague humidity queries ask for details  
- ✅ Complete info proceeds with calculation
- ✅ Pool calculations include pool parameters
- ✅ Partial info asks for missing details
- ✅ Follow-up conversations work correctly
- ✅ Descriptive humidity gets converted to numbers
- ✅ Error handling is user-friendly
- ✅ Manual/brochure questions don't need sizing info

### Expected Behaviors

#### ✅ GOOD Responses (Incomplete Info)
```
"I'd be happy to help size a dehumidifier for your indoor pool! To provide accurate recommendations, I need:
• Room dimensions (length x width x height in meters)
• Current humidity level (% or description like 'very humid')
• Pool size (length x width in meters)

What are your room and pool dimensions?"
```

#### ❌ BAD Responses (What to Avoid)
```
"Unable to generate recommendations without load calculation."
"Error: Missing required parameters"
"I need more information to proceed"
```

### Key Test Scenarios

#### Scenario 1: Minimal Pool Query
**Input**: "I have an indoor pool"
**Expected**: Ask for room dimensions, pool size, humidity level
**Should NOT**: Attempt calculation or show error messages

#### Scenario 2: Complete Pool Information
**Input**: "I have a 12m x 10m x 3m pool room with an 8m x 4m pool. Humidity is 80%, want 50%, temp 25°C"
**Expected**: Calculate load, show "X L/day", provide product recommendations
**Should NOT**: Ask for more information

#### Scenario 3: Partial Information
**Input**: "My basement is humid"
**Expected**: Ask for room dimensions and specific humidity level
**Should NOT**: Attempt calculation

#### Scenario 4: Manual Questions
**Input**: "How do I install the SP500C_PRO?"
**Expected**: Retrieve manual text, provide installation instructions
**Should NOT**: Ask for room dimensions

### Humidity Level Conversion

The agent should convert descriptive humidity to numeric values:
- "terrible humidity" → 85%
- "very high humidity" → 80%
- "high humidity" → 75%
- "pretty humid" → 70%
- "moderately humid" → 65%

### Running Tests in Development

For continuous development, run quick tests after any prompt changes:

```bash
# Quick validation
python test_quick_pool.py

# Full validation before deployment  
python test_information_gathering.py
```

### Test Environment Setup

Ensure you have the required environment variables:
```bash
export OPENAI_API_KEY="your_api_key"
export DEFAULT_MODEL="gpt-4-turbo-preview"
export THINKING_MODEL="o4-mini"
```

### Adding New Test Cases

When adding new scenarios, follow this pattern:

```python
@pytest.mark.asyncio
async def test_new_scenario(self, agent):
    """Test: Description of what should happen"""
    request = ChatRequest(
        message="User input",
        session_id="test_session_unique"
    )
    
    response = await agent.process_chat(request)
    
    # Verify expected behavior
    assert "expected_text" in response.message.lower()
    assert len(response.function_calls) == expected_count
```

### Performance Expectations

- **Response Time**: < 5 seconds for information requests
- **Accuracy**: 100% correct decision on complete vs incomplete info
- **User Experience**: Friendly, helpful tone in all responses
- **No Technical Errors**: Users should never see system error messages 