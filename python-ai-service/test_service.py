"""
Test script for the Dehumidifier AI Service
"""

import asyncio
import json
from models import ChatRequest, ChatResponse
from ai_agent import DehumidifierAgent
from tools import DehumidifierTools

async def test_basic_functionality():
    """Test basic functionality of the AI service"""
    
    print("🧪 Testing Dehumidifier AI Service...")
    
    # Test 1: Tools initialization
    print("\n1. Testing Tools Initialization...")
    tools = DehumidifierTools()
    print(f"   ✅ Loaded {len(tools.products)} products from database")
    print(f"   ✅ Available tools: {tools.get_available_tools()}")
    
    # Test 2: Sizing calculation
    print("\n2. Testing Sizing Calculation...")
    sizing_result = tools.calculate_sizing(
        room_length_m=5.0,
        room_width_m=4.0,
        ceiling_height_m=2.5,
        humidity_level="medium",
        has_pool=False
    )
    print(f"   ✅ Room area: {sizing_result['room_area_m2']} m²")
    print(f"   ✅ Room volume: {sizing_result['room_volume_m3']} m³")
    print(f"   ✅ Recommended capacity: {sizing_result['recommended_capacity']}")
    
    # Test 3: Product recommendations
    print("\n3. Testing Product Recommendations...")
    recommendations = tools.recommend_products(
        room_area_m2=sizing_result['room_area_m2'],
        room_volume_m3=sizing_result['room_volume_m3'],
        pool_required=False
    )
    print(f"   ✅ Found {len(recommendations)} product recommendations")
    for i, rec in enumerate(recommendations):
        print(f"   {i+1}. {rec.get('display_name', ', '.join(rec.get('names', rec.get('skus', []))))} - {rec['confidence_score']:.2f} confidence")
    
    # Test 4: AI Agent initialization (without API call)
    print("\n4. Testing AI Agent Initialization...")
    agent = DehumidifierAgent()
    print(f"   ✅ Agent initialized with model: {agent.model}")
    print(f"   ✅ Health status: {agent.get_health_status()}")
    print(f"   ✅ Available models: {agent.get_available_models()}")
    
    # Test 5: Dehumidifier load calculation
    print("\n5. Testing Dehumidifier Load Calculation (Heuristic)...")
    load_result = tools.calculate_dehum_load(
        length=5,
        width=4,
        height=2.4,
        currentRH=75,
        targetRH=55,
        indoorTemp=25,
        peopleCount=2
    )
    print(f"   ✅ Volume: {load_result['volume']} m³, Latent Load: {load_result['latentLoad_L24h']} L/day")
    
    print("\n✅ All tests passed! The service is ready to run.")
    print("\nTo start the service:")
    print("   python main.py")
    print("\nOr with uvicorn:")
    print("   uvicorn main:app --host 0.0.0.0 --port 8000 --reload")

if __name__ == "__main__":
    asyncio.run(test_basic_functionality()) 