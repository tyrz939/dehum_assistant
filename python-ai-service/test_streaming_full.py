"""
Test script for full OpenAI streaming implementation
"""
import asyncio
import os
from ai_agent import DehumidifierAgent
from models import ChatRequest

# Set up environment for testing
os.environ.setdefault("DEBUG", "true")

async def test_streaming():
    """Test the full streaming flow"""
    print("🧪 Testing Full OpenAI Streaming Implementation...")
    
    agent = DehumidifierAgent()
    
    # Test message with pool scenario
    test_message = "i have a pool 8x4 that is running at 32c. terrible humidity in the room. can you help here? room is 9x8x3m current like 90% and target is 60%. indoor temp about 29c"
    
    request = ChatRequest(
        message=test_message,
        session_id="test_streaming_session"
    )
    
    print(f"\n📝 Test Message: {test_message}")
    print("\n🔄 Streaming Response:")
    print("-" * 60)
    
    response_count = 0
    async for response in agent.process_chat_streaming(request):
        response_count += 1
        
        if response.is_thinking:
            print(f"💭 THINKING: {response.message}")
        elif response.is_streaming_chunk:
            print(f"📝 CHUNK: {response.message}", end="", flush=True)
        elif response.is_final:
            print(f"\n✅ FINAL: Response complete ({len(response.message)} chars)")
        else:
            print(f"🚀 INITIAL: {response.message}")
    
    print("-" * 60)
    print(f"✅ Test completed! Received {response_count} response parts")

if __name__ == "__main__":
    asyncio.run(test_streaming()) 