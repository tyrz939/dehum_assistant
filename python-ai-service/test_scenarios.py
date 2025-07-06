"""Quick scenario smoke tests for Dehumidifier Assistant
Run with:  python test_scenarios.py
Assumes OPENAI_API_KEY and other env vars already configured.
"""
import asyncio
import os
from datetime import datetime

from ai_agent import DehumidifierAgent
from models import ChatRequest

# Helpful flag for verbose output from calculate_dehum_load
os.environ.setdefault("DEBUG", "true")

SCENARIOS = [
    # --- Pools ---
    ("pool_small", "We have an indoor pool of 20m², room is 6x6x2.4 m, humidity 90%, water 28°C. What dehumidifier do we need?"),
    ("pool_large", "Commercial pool 40m², hall 20x10x4 m, water 30°C, RH 80%. Recommend units."),
    # --- Garages ---
    ("garage_one", "Single car garage 6x3x2.7 m, damp smells, RH 75%. What unit?"),
    ("garage_two", "Double garage 7x7x3 m, condensation on tools, RH 85%. Suggestions?"),
    # --- Other facilities ---
    ("gym", "Small gym studio 12x8x3 m, heavy sweat, RH 70%, need comfort."),
    ("museum", "Heritage museum room 15x10x3.5 m, target 50% RH, current 65%. Sensitive artefacts."),
    ("wine_cellar", "Wine cellar 5x4x2.4 m, keep at 60% RH currently 75%."),
    ("basement", "Damp basement 10x6x2.4 m, must reduce mould, RH 80%."),
    ("laundry", "Laundry 4x3x2.4 m, lots of drying, RH 85%."),
    ("warehouse", "Storage warehouse 30x20x6 m, cardboard boxes, RH 80%.")
]


aagent = DehumidifierAgent()

async def run_scenarios():
    for sid, prompt in SCENARIOS:
        print("\n" + "="*60)
        print(f"Scenario: {sid} | {datetime.now().isoformat()}")
        req = ChatRequest(message=prompt, session_id=sid)
        resp = await aagent.process_chat(req)
        print(resp.message)

if __name__ == "__main__":
    asyncio.run(run_scenarios()) 