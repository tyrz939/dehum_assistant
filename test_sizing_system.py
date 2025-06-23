#!/usr/bin/env python3
"""
Permanent Sizing System Test Suite
Tests the dehumidifier sizing logic against various scenarios to ensure accuracy.
"""

import json
import sys
import os
from datetime import datetime
from sizing_edge_case_tests import run_edge_case_tests, load_product_catalog

def test_catalog_integrity():
    """Test that the product catalog is properly formatted and complete"""
    print("=== CATALOG INTEGRITY TEST ===")
    
    catalog = load_product_catalog()
    if not catalog:
        print("❌ Failed to load catalog")
        return False
    
    products = catalog.get('products', [])
    print(f"📦 Products loaded: {len(products)}")
    
    # Check for required fields
    required_fields = ['sku', 'name', 'max_room_m3', 'max_pool_m2', 'pool_safe']
    issues = []
    
    for i, product in enumerate(products):
        for field in required_fields:
            if field not in product:
                issues.append(f"Product {i+1} ({product.get('sku', 'UNKNOWN')}) missing field: {field}")
            elif field == 'max_room_m3' and product.get(field, 0) == 0:
                issues.append(f"Product {i+1} ({product.get('sku', 'UNKNOWN')}) has zero room capacity")
    
    if issues:
        print("⚠️  Catalog issues found:")
        for issue in issues:
            print(f"   {issue}")
        return False
    else:
        print("✅ Catalog integrity check passed")
        return True

def test_sizing_calculations():
    """Test specific sizing calculation scenarios"""
    print("\n=== SIZING CALCULATION TESTS ===")
    
    from sizing_edge_case_tests import calculate_effective_pool_area, find_suitable_units
    
    catalog = load_product_catalog()
    if not catalog:
        return False
    
    # Test temperature multipliers
    test_cases = [
        (25, 30, 25.0),   # 25m² at 30°C = 25m² (1.0x)
        (25, 33, 37.5),   # 25m² at 33°C = 37.5m² (1.5x)
        (25, 36, 50.0),   # 25m² at 36°C = 50m² (2.0x)
    ]
    
    print("🌡️  Temperature multiplier tests:")
    for pool_area, temp, expected in test_cases:
        result = calculate_effective_pool_area(pool_area, temp)
        status = "✅" if abs(result - expected) < 0.1 else "❌"
        print(f"   {status} {pool_area}m² at {temp}°C = {result:.1f}m² (expected {expected:.1f}m²)")
    
    # Test unit selection
    print("\n🏠 Unit selection tests:")
    test_scenarios = [
        ("Small room", 50, 0, "Should find multiple options"),
        ("Medium room", 150, 0, "Should find good matches"),
        ("Large room", 500, 0, "Should find larger units"),
        ("Small pool", 100, 15, "Should handle small pools"),
        ("Medium pool", 150, 30, "Should handle medium pools"),
        ("Large pool", 200, 45, "Should handle large pools"),
    ]
    
    for name, room_vol, pool_area, description in test_scenarios:
        units = find_suitable_units(catalog, room_vol, pool_area)
        status = "✅" if units else "❌"
        count = len(units)
        best_unit = units[0]['sku'] if units else "None"
        print(f"   {status} {name}: {count} units found, best: {best_unit}")
    
    return True

def test_prompt_consistency():
    """Test that the prompt template is consistent with catalog rules"""
    print("\n=== PROMPT CONSISTENCY TEST ===")
    
    try:
        with open('prompt_template.txt', 'r', encoding='utf-8') as f:
            prompt = f.read()
        
        catalog = load_product_catalog()
        if not catalog:
            return False
        
        rules = catalog.get('sizing_rules', {})
        
        # Check ratio limits
        prompt_room_max = "1.0-3.0x" in prompt
        prompt_pool_max = "1.0-2.0x" in prompt
        
        catalog_room_max = rules.get('room_ratio_max', 0) == 3.0
        catalog_pool_max = rules.get('pool_ratio_max', 0) == 2.0
        
        print(f"📏 Room ratio limits: Prompt={'✅' if prompt_room_max else '❌'}, Catalog={'✅' if catalog_room_max else '❌'}")
        print(f"🏊 Pool ratio limits: Prompt={'✅' if prompt_pool_max else '❌'}, Catalog={'✅' if catalog_pool_max else '❌'}")
        
        # Check temperature multipliers
        temp_33_in_prompt = "33°C: multiplier = 1.5" in prompt
        temp_33_in_catalog = rules.get('water_temp_multipliers', {}).get('33') == 1.5
        
        print(f"🌡️  Temperature multipliers: Prompt={'✅' if temp_33_in_prompt else '❌'}, Catalog={'✅' if temp_33_in_catalog else '❌'}")
        
        consistency_ok = all([prompt_room_max, prompt_pool_max, catalog_room_max, catalog_pool_max, temp_33_in_prompt, temp_33_in_catalog])
        
        if consistency_ok:
            print("✅ Prompt-catalog consistency check passed")
        else:
            print("❌ Prompt-catalog consistency issues found")
        
        return consistency_ok
        
    except Exception as e:
        print(f"❌ Error checking prompt consistency: {e}")
        return False

def run_full_test_suite():
    """Run the complete test suite"""
    print("🧪 DEHUMIDIFIER SIZING SYSTEM - FULL TEST SUITE")
    print(f"⏰ Test run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    tests = [
        ("Catalog Integrity", test_catalog_integrity),
        ("Sizing Calculations", test_sizing_calculations),
        ("Prompt Consistency", test_prompt_consistency),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🏃 Running {test_name}...")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    # Run edge case tests
    print(f"\n🏃 Running Edge Case Analysis...")
    try:
        run_edge_case_tests()
        results.append(("Edge Case Analysis", True))
    except Exception as e:
        print(f"❌ Edge Case Analysis failed with error: {e}")
        results.append(("Edge Case Analysis", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUITE SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:8} {test_name}")
    
    print("-" * 60)
    print(f"📈 Overall: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - SYSTEM READY!")
    else:
        print("⚠️  SOME TESTS FAILED - REVIEW REQUIRED")
    
    return passed == total

if __name__ == '__main__':
    success = run_full_test_suite()
    sys.exit(0 if success else 1) 