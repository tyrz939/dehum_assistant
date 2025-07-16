#!/usr/bin/env python3
"""
Test frontend streaming behavior with focus on phase preservation
"""

import asyncio
import json
import time
from ai_agent import DehumidifierAgent

async def test_phase_content_preservation():
    """Test that Phase 1 content is preserved when Phase 3 starts"""
    print("=" * 60)
    print("FRONTEND STREAMING TEST - Phase Content Preservation")
    print("=" * 60)
    
    agent = DehumidifierAgent()
    
    # Test request that should trigger both phases
    request_data = {
        "message": "I have a 4x5 meter room with terrible humidity, around 90%. I want to get it down to 55%. The ceiling is 2.8m high.",
        "session_id": "test_phase_preservation"
    }
    
    phase_1_content = ""
    phase_2_content = ""
    phase_3_content = ""
    
    chunks_by_phase = {
        "initial": 0,
        "thinking": 0,
        "recommendations": 0,
        "other": 0
    }
    
    total_chunks = 0
    
    print("\n🔄 Starting streaming test...")
    start_time = time.time()
    
    from models import ChatRequest
    request = ChatRequest(**request_data)
    
    async for chunk in agent.process_chat_streaming(request):
        total_chunks += 1
        phase = chunk.metadata.get("phase", "unknown")
        
        print(f"\nChunk #{total_chunks} | Phase: {phase} | Length: {len(chunk.message)}")
        print(f"Is streaming chunk: {chunk.is_streaming_chunk}")
        print(f"Is thinking: {chunk.is_thinking}")
        print(f"Is final: {chunk.is_final}")
        print(f"Content preview: {repr(chunk.message[:50])}")
        
        # Track content by phase
        if phase in ["initial", "initial_complete"]:
            chunks_by_phase["initial"] += 1
            if chunk.is_streaming_chunk or phase == "initial_complete":
                phase_1_content += chunk.message
        elif phase in ["thinking", "thinking_complete"]:
            chunks_by_phase["thinking"] += 1
            phase_2_content += chunk.message
        elif chunk.is_streaming_chunk and not chunk.is_thinking:
            chunks_by_phase["recommendations"] += 1
            phase_3_content += chunk.message
        else:
            chunks_by_phase["other"] += 1
    
    end_time = time.time()
    
    print("\n" + "=" * 60)
    print("PHASE CONTENT ANALYSIS")
    print("=" * 60)
    
    print(f"\n📊 CHUNK DISTRIBUTION:")
    for phase, count in chunks_by_phase.items():
        print(f"  {phase.capitalize()}: {count} chunks")
    print(f"  Total: {total_chunks} chunks")
    print(f"  Duration: {end_time - start_time:.2f} seconds")
    
    print(f"\n📝 CONTENT LENGTHS:")
    print(f"  Phase 1 (Initial): {len(phase_1_content)} characters")
    print(f"  Phase 2 (Thinking): {len(phase_2_content)} characters") 
    print(f"  Phase 3 (Recommendations): {len(phase_3_content)} characters")
    print(f"  Total Content: {len(phase_1_content) + len(phase_2_content) + len(phase_3_content)} characters")
    
    print(f"\n📋 CONTENT PREVIEW:")
    print(f"\n🔵 PHASE 1 (Load Calculation Response):")
    print("-" * 40)
    print(phase_1_content[:200] + "..." if len(phase_1_content) > 200 else phase_1_content)
    
    print(f"\n🟡 PHASE 2 (Thinking Message):")
    print("-" * 40)
    print(phase_2_content[:200] + "..." if len(phase_2_content) > 200 else phase_2_content)
    
    print(f"\n🟢 PHASE 3 (Product Recommendations):")
    print("-" * 40)
    print(phase_3_content[:200] + "..." if len(phase_3_content) > 200 else phase_3_content)
    
    # Simulate frontend behavior
    print(f"\n🖥️  SIMULATED FRONTEND DISPLAY:")
    print("=" * 60)
    
    # This is what the frontend should show after all streaming
    combined_content = phase_1_content
    if phase_3_content:
        combined_content += "\n\n" + phase_3_content
        
    print("FINAL COMBINED MESSAGE CONTENT:")
    print("-" * 40)
    print(combined_content)
    
    # Validation checks
    print(f"\n✅ VALIDATION RESULTS:")
    print("-" * 40)
    
    has_phase_1 = len(phase_1_content) > 0
    has_phase_3 = len(phase_3_content) > 0
    has_load_calc = "L/day" in phase_1_content
    has_recommendations = any(word in phase_3_content.lower() for word in ["recommend", "product", "model", "option"])
    
    print(f"  ✓ Phase 1 content present: {has_phase_1} ({len(phase_1_content)} chars)")
    print(f"  ✓ Phase 3 content present: {has_phase_3} ({len(phase_3_content)} chars)")
    print(f"  ✓ Contains load calculation: {has_load_calc}")
    print(f"  ✓ Contains recommendations: {has_recommendations}")
    print(f"  ✓ Both phases preserved: {has_phase_1 and has_phase_3}")
    
    if has_phase_1 and has_phase_3:
        print(f"\n🎉 SUCCESS: Both Phase 1 (load calculation) and Phase 3 (recommendations) content preserved!")
        print(f"   Frontend should show: Load calculation + Thinking indicator + Recommendations")
        print(f"   Total visible content: {len(combined_content)} characters")
    else:
        print(f"\n❌ ISSUE: Missing content phases")
        if not has_phase_1:
            print(f"   - Phase 1 (load calculation) missing or empty")
        if not has_phase_3:
            print(f"   - Phase 3 (recommendations) missing or empty")
    
    return {
        "total_chunks": total_chunks,
        "phase_1_chars": len(phase_1_content),
        "phase_3_chars": len(phase_3_content),
        "combined_chars": len(combined_content),
        "has_both_phases": has_phase_1 and has_phase_3,
        "duration": end_time - start_time
    }

if __name__ == "__main__":
    asyncio.run(test_phase_content_preservation()) 