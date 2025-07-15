"""
Test script for context-aware follow-up functionality
"""
import asyncio
import os
from ai_agent import DehumidifierAgent
from models import ChatRequest

# Set up environment for testing
os.environ.setdefault("DEBUG", "true")

async def test_context_aware_followups():
    """Test the context-aware follow-up handling"""
    print("🧪 Testing Context-Aware Follow-up Functionality...")
    
    agent = DehumidifierAgent()
    session_id = "context_test_session"
    
    # First message - establish context with pool scenario
    initial_message = "i have a pool 8x4 that is running at 32c. terrible humidity in the room. can you help here? room is 9x8x3m current like 90% and target is 60%. indoor temp about 29c"
    
    print(f"\n📝 Initial Message: {initial_message}")
    print("\n🔄 Initial Response:")
    print("-" * 60)
    
    # Process initial request
    initial_request = ChatRequest(message=initial_message, session_id=session_id)
    
    # Collect the streaming response
    initial_parts = []
    async for response in agent.process_chat_streaming(initial_request):
        if response.is_thinking:
            print(f"💭 THINKING: {response.message}")
        elif response.is_streaming_chunk:
            print(f"📝 CHUNK: {response.message}", end="", flush=True)
        elif response.is_final:
            print(f"\n✅ INITIAL COMPLETE")
            initial_parts.append(response.message)
        else:
            print(f"🚀 INITIAL: {response.message}")
    
    print("-" * 60)
    
    # Now test follow-up question
    followup_message = "ideas for ducted alternatives"
    print(f"\n🔄 Follow-up Message: {followup_message}")
    print("\n🎯 Testing Context Awareness:")
    print("-" * 60)
    
    # Process follow-up request
    followup_request = ChatRequest(message=followup_message, session_id=session_id)
    
    followup_parts = []
    async for response in agent.process_chat_streaming(followup_request):
        if response.is_thinking:
            print(f"💭 THINKING: {response.message}")
        elif response.is_streaming_chunk:
            print(f"📝 CHUNK: {response.message}", end="", flush=True)
        elif response.is_final:
            print(f"\n✅ FOLLOWUP COMPLETE")
            followup_parts.append(response.message)
        else:
            print(f"🎯 CONTEXT-AWARE: {response.message}")
    
    print("-" * 60)
    print("✅ Context-aware follow-up test completed!")
    
    # Check if it reused existing data
    session = agent.sessions.get(session_id)
    if session and session.tool_cache:
        print(f"📊 Session has cached data: {len(session.tool_cache)} entries")
        for key in session.tool_cache.keys():
            if 'calculate_dehum_load' in key:
                print(f"✅ Found cached load calculation: {key[:50]}...")
    else:
        print("❌ No cached data found")

if __name__ == "__main__":
    asyncio.run(test_context_aware_followups()) 