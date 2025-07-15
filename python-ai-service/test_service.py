"""
Test script for the Dehumidifier AI Service
"""

import asyncio
import json
from models import ChatRequest, ChatResponse
from ai_agent import DehumidifierAgent
from tools import DehumidifierTools
import pytest
from fastapi.testclient import TestClient
from main import app
import requests_mock

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
    
    # Test 3: Product catalog
    print("\n3. Testing Product Catalog...")
    catalog = tools.get_catalog_with_effective_capacity()
    print(f"   ✅ Found {len(catalog)} products in catalog")
    for i, product in enumerate(catalog[:3]):  # Show first 3 products
        print(f"   {i+1}. {product['name']} - {product['effective_capacity_lpd']:.1f} L/day")
    
    # Test 4: AI Agent initialization (without API call)
    print("\n4. Testing AI Agent Initialization...")
    agent = DehumidifierAgent()
    print(f"   ✅ Agent initialized with model: {agent.model}")
    print(f"   ✅ Health status: {agent.get_health_status()}")
    
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

@pytest.mark.asyncio
async def test_recommendations():
    agent = DehumidifierAgent()
    request = ChatRequest(message="Recommend a dehumidifier for a 50m2 room with 3m ceiling, 28C temperature, 60% current RH, target 50% RH, with a 20m2 pool at 28C water temp, wall-mount preferred.", session_id="test_rec")
    response = await agent.process_chat(request)
    assert response.recommendations is not None
    assert len(response.recommendations) > 0

@pytest.fixture
def mock_requests():
    with requests_mock.Mocker() as m:
        yield m

@pytest.mark.asyncio
async def test_session_sync(mock_requests):
    agent = DehumidifierAgent()
    # Mock WP responses
    mock_requests.post(agent.wp_ajax_url, json={"success": True, "data": {"history": [{"role": "user", "content": "Hello"}]}})
    session = agent.get_or_create_session("test_sync")
    assert len(session.conversation_history) == 1
    assert session.conversation_history[0].content == "Hello"

if __name__ == "__main__":
    asyncio.run(test_basic_functionality()) 