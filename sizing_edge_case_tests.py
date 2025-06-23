#!/usr/bin/env python3

import json
import sys
from typing import List, Dict, Tuple

def load_product_catalog():
    """Load the product catalog for testing"""
    try:
        with open('product_db.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to load catalog: {e}")
        return None

def calculate_effective_pool_area(pool_area_m2: float, water_temp_c: int) -> float:
    """Calculate effective pool area with temperature multiplier"""
    multipliers = {30: 1.0, 33: 1.5, 36: 2.0}
    
    # Find closest temperature multiplier
    if water_temp_c <= 30:
        multiplier = 1.0
    elif water_temp_c <= 33:
        multiplier = 1.5
    elif water_temp_c >= 36:
        multiplier = 2.0
    else:
        # Interpolate between 33 and 36
        multiplier = 1.5 + (water_temp_c - 33) * (2.0 - 1.5) / (36 - 33)
    
    return pool_area_m2 * multiplier

def find_suitable_units(catalog: Dict, room_volume_m3: float, effective_pool_area: float) -> List[Dict]:
    """Find units that meet both room and pool requirements"""
    suitable_units = []
    
    for product in catalog['products']:
        # Skip non-pool-safe units for pool applications
        if effective_pool_area > 0 and not product.get('pool_safe', False):
            continue
            
        # Check room capacity
        max_room_m3 = product.get('max_room_m3', 0)
        if max_room_m3 == 0:  # Skip units without room capacity data
            continue
            
        room_ok = max_room_m3 >= room_volume_m3
        
        # Check pool capacity
        max_pool_m2 = product.get('max_pool_m2', 0)
        pool_ok = max_pool_m2 >= effective_pool_area if effective_pool_area > 0 else True
        
        if room_ok and pool_ok:
            # Calculate coverage ratios
            room_ratio = max_room_m3 / room_volume_m3 if room_volume_m3 > 0 else float('inf')
            pool_ratio = max_pool_m2 / effective_pool_area if effective_pool_area > 0 else float('inf')
            
            # Calculate efficiency score (prefer closer ratios)
            if effective_pool_area > 0:
                efficiency_score = min(room_ratio, pool_ratio)  # Limiting factor
            else:
                efficiency_score = room_ratio
            
            suitable_units.append({
                'sku': product['sku'],
                'name': product['name'],
                'type': product.get('type', 'unknown'),
                'technology': product.get('technology', 'unknown'),
                'max_room_m3': max_room_m3,
                'max_pool_m2': max_pool_m2,
                'room_ratio': room_ratio,
                'pool_ratio': pool_ratio,
                'efficiency_score': efficiency_score,
                'price_aud': product.get('price_aud'),
                'room_ok': room_ok,
                'pool_ok': pool_ok
            })
    
    # Sort by efficiency score (closest to 1.0 is best)
    suitable_units.sort(key=lambda x: abs(x['efficiency_score'] - 1.0))
    
    return suitable_units

def analyze_sizing_scenario(scenario: Dict, catalog: Dict) -> Dict:
    """Analyze a single sizing scenario"""
    # Calculate room volume
    length = scenario['length_m']
    width = scenario['width_m']
    height = scenario.get('height_m', 2.7)
    room_volume_m3 = length * width * height
    
    # Calculate effective pool area
    pool_area_m2 = scenario.get('pool_area_m2', 0)
    water_temp_c = scenario.get('water_temp_c', 30)
    effective_pool_area = calculate_effective_pool_area(pool_area_m2, water_temp_c) if pool_area_m2 > 0 else 0
    
    # Find suitable units
    suitable_units = find_suitable_units(catalog, room_volume_m3, effective_pool_area)
    
    # Analyze results
    has_suitable_units = len(suitable_units) > 0
    min_room_ratio = min([u['room_ratio'] for u in suitable_units]) if suitable_units else float('inf')
    min_pool_ratio = min([u['pool_ratio'] for u in suitable_units]) if suitable_units and effective_pool_area > 0 else float('inf')
    
    # Check guardrails
    room_ratio_ok = 1.0 <= min_room_ratio <= 3.0 if min_room_ratio != float('inf') else False
    pool_ratio_ok = 1.0 <= min_pool_ratio <= 2.0 if min_pool_ratio != float('inf') else True
    
    return {
        'scenario': scenario,
        'room_volume_m3': room_volume_m3,
        'effective_pool_area': effective_pool_area,
        'suitable_units': suitable_units,
        'has_suitable_units': has_suitable_units,
        'min_room_ratio': min_room_ratio,
        'min_pool_ratio': min_pool_ratio,
        'room_ratio_ok': room_ratio_ok,
        'pool_ratio_ok': pool_ratio_ok,
        'should_escalate': not has_suitable_units or not room_ratio_ok or not pool_ratio_ok
    }

def run_edge_case_tests():
    """Run comprehensive edge case testing"""
    print("=== DEHUMIDIFIER SIZING EDGE CASE TESTS ===")
    print()
    
    # Load catalog
    catalog = load_product_catalog()
    if not catalog:
        return
    
    print(f"📦 Loaded catalog: {len(catalog['products'])} products")
    print()
    
    # Define test scenarios
    test_scenarios = [
        {
            'name': 'Original Problem Case',
            'description': '8x5x3m room, 24m² pool at 33°C (should need IDHR120/SP1500C)',
            'length_m': 8, 'width_m': 5, 'height_m': 3,
            'pool_area_m2': 24, 'water_temp_c': 33
        },
        {
            'name': 'Small Pool Room',
            'description': '6x4x2.7m room, 10m² pool at 30°C',
            'length_m': 6, 'width_m': 4, 'height_m': 2.7,
            'pool_area_m2': 10, 'water_temp_c': 30
        },
        {
            'name': 'Large Pool Room',
            'description': '12x8x3.5m room, 50m² pool at 33°C',
            'length_m': 12, 'width_m': 8, 'height_m': 3.5,
            'pool_area_m2': 50, 'water_temp_c': 33
        },
        {
            'name': 'Hot Pool Edge Case',
            'description': '10x6x3m room, 30m² pool at 36°C (2x multiplier)',
            'length_m': 10, 'width_m': 6, 'height_m': 3,
            'pool_area_m2': 30, 'water_temp_c': 36
        },
        {
            'name': 'Very Hot Pool',
            'description': '8x5x3m room, 25m² pool at 38°C (should escalate)',
            'length_m': 8, 'width_m': 5, 'height_m': 3,
            'pool_area_m2': 25, 'water_temp_c': 38
        },
        {
            'name': 'High Ceiling Challenge',
            'description': '8x8x5m room, 20m² pool at 33°C (high volume)',
            'length_m': 8, 'width_m': 8, 'height_m': 5,
            'pool_area_m2': 20, 'water_temp_c': 33
        },
        {
            'name': 'Tiny Pool Room',
            'description': '4x3x2.7m room, 5m² pool at 33°C',
            'length_m': 4, 'width_m': 3, 'height_m': 2.7,
            'pool_area_m2': 5, 'water_temp_c': 33
        },
        {
            'name': 'No Pool Room',
            'description': '10x8x2.7m room, no pool (room-only sizing)',
            'length_m': 10, 'width_m': 8, 'height_m': 2.7,
            'pool_area_m2': 0, 'water_temp_c': 25
        },
        {
            'name': 'Massive Room',
            'description': '20x15x4m room, no pool (very large space)',
            'length_m': 20, 'width_m': 15, 'height_m': 4,
            'pool_area_m2': 0, 'water_temp_c': 25
        },
        {
            'name': 'Edge Pool Size',
            'description': '7x7x3m room, 25m² pool at 33°C (exactly at limits)',
            'length_m': 7, 'width_m': 7, 'height_m': 3,
            'pool_area_m2': 25, 'water_temp_c': 33
        },
        {
            'name': 'Commercial Pool',
            'description': '15x10x4m room, 80m² pool at 33°C (beyond residential)',
            'length_m': 15, 'width_m': 10, 'height_m': 4,
            'pool_area_m2': 80, 'water_temp_c': 33
        }
    ]
    
    # Run tests
    results = []
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"🧪 TEST {i:2d}: {scenario['name']}")
        print(f"    {scenario['description']}")
        
        result = analyze_sizing_scenario(scenario, catalog)
        results.append(result)
        
        # Display results
        if result['has_suitable_units']:
            best_unit = result['suitable_units'][0]  # Already sorted by efficiency
            print(f"    ✅ Best unit: {best_unit['sku']} ({best_unit['name']})")
            print(f"       Type: {best_unit['type']} ({best_unit['technology']})")
            print(f"       Room: {result['room_volume_m3']:.0f}m³ → {best_unit['max_room_m3']}m³ (ratio: {best_unit['room_ratio']:.1f}x)")
            if result['effective_pool_area'] > 0:
                print(f"       Pool: {result['effective_pool_area']:.0f}m² eff → {best_unit['max_pool_m2']}m² (ratio: {best_unit['pool_ratio']:.1f}x)")
            if best_unit['price_aud']:
                print(f"       Price: A${best_unit['price_aud']:,}")
            else:
                print(f"       Price: Contact for pricing")
        else:
            print(f"    ❌ No suitable units found!")
            print(f"       Room: {result['room_volume_m3']:.0f}m³, Pool: {result['effective_pool_area']:.0f}m² effective")
        
        if result['should_escalate']:
            reasons = []
            if not result['has_suitable_units']:
                reasons.append("no suitable units")
            if not result['room_ratio_ok']:
                reasons.append("room ratio out of bounds")
            if not result['pool_ratio_ok']:
                reasons.append("pool ratio out of bounds")
            print(f"    ⚠️  Should escalate: {', '.join(reasons)}")
        
        print()
    
    # Summary
    print("=== TEST SUMMARY ===")
    total_tests = len(results)
    has_solutions = sum(1 for r in results if r['has_suitable_units'])
    needs_escalation = sum(1 for r in results if r['should_escalate'])
    
    print(f"📊 Total tests: {total_tests}")
    print(f"✅ Has solutions: {has_solutions}/{total_tests} ({has_solutions/total_tests*100:.0f}%)")
    print(f"⚠️  Needs escalation: {needs_escalation}/{total_tests} ({needs_escalation/total_tests*100:.0f}%)")
    print()
    
    # Identify potential issues
    issues = []
    for i, result in enumerate(results):
        scenario_name = test_scenarios[i]['name']
        
        if not result['has_suitable_units']:
            issues.append(f"❌ {scenario_name}: No suitable units available")
        elif result['min_room_ratio'] < 1.0:
            issues.append(f"⚠️  {scenario_name}: Room undersized (ratio {result['min_room_ratio']:.2f})")
        elif result['min_pool_ratio'] < 1.0:
            issues.append(f"⚠️  {scenario_name}: Pool undersized (ratio {result['min_pool_ratio']:.2f})")
        elif result['min_room_ratio'] > 3.0:
            issues.append(f"⚠️  {scenario_name}: Room oversized (ratio {result['min_room_ratio']:.2f})")
        elif result['min_pool_ratio'] > 2.0:
            issues.append(f"⚠️  {scenario_name}: Pool oversized (ratio {result['min_pool_ratio']:.2f})")
    
    if issues:
        print("🚨 POTENTIAL ISSUES FOUND:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print("🎯 NO SIZING ISSUES DETECTED!")
    
    print()
    print("🔍 EDGE CASE ANALYSIS COMPLETE")

if __name__ == '__main__':
    run_edge_case_tests() 