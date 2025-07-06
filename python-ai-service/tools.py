"""
Dehumidifier Tools - Sizing calculations and product recommendations
"""

import json
import os
import math
from typing import Dict, List, Optional, Any
from models import ProductRecommendation, SizingCalculation
import logging

logger = logging.getLogger(__name__)

class DehumidifierTools:
    """Tools for dehumidifier sizing and product recommendations"""
    
    def __init__(self):
        self.products = self.load_product_database()
        
    def load_product_database(self) -> List[Dict[str, Any]]:
        """Load product database from JSON file"""
        try:
            # Try to load from parent directory first (where product_db.json is located)
            product_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "product_db.json")
            if os.path.exists(product_db_path):
                with open(product_db_path, 'r') as f:
                    data = json.load(f)
                    return data.get("products", [])
            
            # Fallback to current directory
            with open("product_db.json", 'r') as f:
                data = json.load(f)
                return data.get("products", [])
                
        except FileNotFoundError:
            logger.error("Product database not found. Using empty product list.")
            return []
        except json.JSONDecodeError:
            logger.error("Invalid JSON in product database. Using empty product list.")
            return []
    
    def calculate_sizing(self, room_length_m: float, room_width_m: float, ceiling_height_m: float, 
                        humidity_level: str, has_pool: bool = False, pool_area_m2: float = 0) -> Dict[str, Any]:
        """
        Calculate optimal dehumidifier capacity based on room dimensions and conditions
        
        Args:
            room_length_m: Room length in meters
            room_width_m: Room width in meters  
            ceiling_height_m: Ceiling height in meters
            humidity_level: Current humidity level (low/medium/high/extreme)
            has_pool: Whether the space has a pool
            pool_area_m2: Pool area in square meters if applicable
            
        Returns:
            Dictionary containing sizing calculation results
        """
        try:
            # Calculate basic dimensions
            room_area_m2 = room_length_m * room_width_m
            room_volume_m3 = room_area_m2 * ceiling_height_m
            
            # Base capacity calculation (simplified industry standard)
            # Starting point: 1 liter per day per square meter for normal conditions
            base_capacity_lpd = room_area_m2 * 1.0
            
            # Humidity level multipliers
            humidity_multipliers = {
                "low": 0.8,      # 40-50% RH
                "medium": 1.0,   # 50-60% RH  
                "high": 1.4,     # 60-70% RH
                "extreme": 1.8   # 70%+ RH
            }
            
            multiplier = humidity_multipliers.get(humidity_level.lower(), 1.0)
            adjusted_capacity_lpd = base_capacity_lpd * multiplier
            
            # Pool adjustment
            pool_capacity_lpd = 0
            if has_pool and pool_area_m2 > 0:
                # Pool evaporation: approximately 4-6 L/day per m² of pool surface
                pool_capacity_lpd = pool_area_m2 * 5.0
                
            total_capacity_lpd = adjusted_capacity_lpd + pool_capacity_lpd
            
            # Determine capacity category
            if total_capacity_lpd <= 30:
                capacity_category = "Small (up to 30L/day)"
            elif total_capacity_lpd <= 60:
                capacity_category = "Medium (30-60L/day)"
            elif total_capacity_lpd <= 100:
                capacity_category = "Large (60-100L/day)"
            else:
                capacity_category = "Industrial (100L+/day)"
            
            calculation_notes = [
                f"Room area: {room_area_m2:.1f} m²",
                f"Room volume: {room_volume_m3:.1f} m³",
                f"Humidity level: {humidity_level.title()}",
                f"Base capacity: {base_capacity_lpd:.1f} L/day",
                f"Adjusted for humidity: {adjusted_capacity_lpd:.1f} L/day"
            ]
            
            if has_pool:
                calculation_notes.append(f"Pool evaporation: {pool_capacity_lpd:.1f} L/day")
            
            calculation_notes.append(f"Total recommended capacity: {total_capacity_lpd:.1f} L/day")
            
            return {
                "room_area_m2": room_area_m2,
                "room_volume_m3": room_volume_m3,
                "pool_area_m2": pool_area_m2 if has_pool else 0,
                "room_height_m": ceiling_height_m,
                "humidity_level": humidity_level,
                "recommended_capacity": capacity_category,
                "recommended_capacity_lpd": total_capacity_lpd,
                "calculation_notes": "; ".join(calculation_notes)
            }
            
        except Exception as e:
            logger.error(f"Error calculating sizing: {str(e)}")
            return {
                "error": f"Calculation error: {str(e)}",
                "room_area_m2": room_length_m * room_width_m,
                "room_volume_m3": room_length_m * room_width_m * ceiling_height_m,
                "recommended_capacity": "Unable to calculate - please contact support"
            }
    
    def recommend_products(self, room_area_m2: float, room_volume_m3: float,
                          pool_area_m2: float = 0, pool_required: bool = False,
                          budget_max: Optional[float] = None,
                          preferred_types: Optional[List[str]] = None,
                          required_load_lpd: Optional[float] = None,
                          max_units: int = 3) -> List[Dict[str, Any]]:
        """
        Recommend specific dehumidifier products based on requirements
        
        Args:
            room_area_m2: Room area in square meters
            room_volume_m3: Room volume in cubic meters
            pool_area_m2: Pool area in square meters if applicable
            pool_required: Whether pool-safe dehumidifier is required
            budget_max: Maximum budget in AUD
            preferred_types: List of preferred installation types (wall_mount/ducted/portable)
            required_load_lpd: Required load in L/day
            max_units: Maximum number of units to recommend
            
        Returns:
            List of product recommendations with confidence scores
        """
        try:
            # pre-filter products and compute effective capacity
            candidates = []
            for product in self.products:
                # Skip if pool required but product is not pool-safe
                if pool_required and not product.get("pool_safe", False):
                    continue
                # Preferred types filter (soft). Hard filter if list provided
                if preferred_types and product.get("type") not in preferred_types:
                    continue
                # Skip if over budget
                if budget_max and product.get("price_aud") and product["price_aud"] > budget_max:
                    continue
                # Determine effective capacity
                if product.get("capacity_lpd") is None:
                    continue  # skip items without capacity until data filled

                perf = product.get("performance_factor", 1.0)
                eff_capacity = product["capacity_lpd"] * perf

                candidates.append({"product": product, "eff_capacity": eff_capacity})

            if not candidates:
                return []

            # Build combinations
            import itertools
            combos = []
            req_load = required_load_lpd or 0

            for units in range(1, max_units + 1):
                # allow same model multiple times via combinations_with_replacement
                for combo in itertools.combinations_with_replacement(candidates, units):
                    skus = [c["product"]["sku"] for c in combo]
                    names = [c["product"].get("name", c["product"].get("sku")) for c in combo]
                    total_capacity = sum(c["eff_capacity"] for c in combo)
                    # Pool capacity check if required
                    if pool_required:
                        total_pool_cap = sum(c["product"].get("max_pool_m2", 0) for c in combo)
                        if total_pool_cap < pool_area_m2:
                            continue  # insufficient pool coverage
                    else:
                        total_pool_cap = None

                    if total_capacity < req_load:
                        continue  # doesn't meet load

                    total_price = sum(c["product"].get("price_aud") or 0 for c in combo)
                    overshoot = total_capacity - req_load
                    form_factors = list({c["product"]["type"] for c in combo})

                    combos.append({
                        "skus": skus,
                        "names": names,
                        "units": units,
                        "total_capacity": round(total_capacity, 1),
                        "total_price_aud": total_price if total_price > 0 else None,
                        "form_factors": form_factors,
                        "overshoot": overshoot,
                        "total_pool_capacity_m2": total_pool_cap,
                        "pool_required": pool_required
                    })

            if not combos:
                return []

            # Sort: fewer units, lower overshoot, adequate pool coverage, then price
            def combo_sort_key(c):
                pool_overshoot = 0
                if c["pool_required"] and c["total_pool_capacity_m2"] is not None:
                    pool_overshoot = c["total_pool_capacity_m2"] - pool_area_m2
                return (c["units"], pool_overshoot, c["overshoot"], c["total_price_aud"] or 0)

            combos.sort(key=combo_sort_key)

            # Add reasoning and confidence
            top_recommendations = []
            for combo in combos[:3]:
                confidence = 0.8 if combo["overshoot"] <= req_load * 0.1 else 0.6
                display_name = ", ".join(combo["names"]) if "names" in combo else ", ".join(combo["skus"])
                reason = f"Meets load with {combo['units']} unit(s) and {combo['overshoot']:.1f} L/day headroom"
                if combo["pool_required"]:
                    reason += f"; Pool coverage {combo['total_pool_capacity_m2']}m² vs required {pool_area_m2}m²"

                top_recommendations.append({
                    **combo,
                    "display_name": display_name,
                    "confidence_score": confidence,
                    "reasoning": reason
                })

            return top_recommendations

        except Exception as e:
            logger.error(f"Error recommending products: {str(e)}")
            return []
    
    def calculate_product_suitability(self, product: Dict[str, Any], room_area_m2: float, 
                                    room_volume_m3: float, pool_area_m2: float, 
                                    pool_required: bool) -> float:
        """Legacy scoring used elsewhere (kept)"""
        try:
            score = 0.0
            
            perf = product.get("performance_factor", 1.0)
            max_room_m2_eff = product.get("max_room_m2") * perf if product.get("max_room_m2") else None
            if max_room_m2_eff:
                if room_area_m2 <= max_room_m2_eff:
                    # Perfect if within 80-100% of capacity
                    if room_area_m2 >= max_room_m2_eff * 0.8:
                        score += 0.4
                    # Good if within 60-80% of capacity
                    elif room_area_m2 >= max_room_m2_eff * 0.6:
                        score += 0.3
                    # Acceptable if within 40-60% of capacity
                    elif room_area_m2 >= max_room_m2_eff * 0.4:
                        score += 0.2
                    # Marginal if under 40% of capacity
                    else:
                        score += 0.1
                else:
                    # Penalize if over capacity
                    score -= 0.2
            
            # Room volume suitability
            if product.get("max_room_m3"):
                if room_volume_m3 <= product["max_room_m3"]:
                    if room_volume_m3 >= product["max_room_m3"] * 0.8:
                        score += 0.3
                    elif room_volume_m3 >= product["max_room_m3"] * 0.6:
                        score += 0.2
                    else:
                        score += 0.1
                else:
                    score -= 0.1
            
            # Pool requirements
            if pool_required:
                if product.get("pool_safe", False):
                    score += 0.2
                    # Check pool capacity
                    if product.get("max_pool_m2") and pool_area_m2 > 0:
                        if pool_area_m2 <= product["max_pool_m2"]:
                            score += 0.1
                        else:
                            score -= 0.1
                else:
                    score -= 0.5  # Major penalty for not being pool-safe when required
            
            # Technology bonus
            if product.get("technology") == "inverter":
                score += 0.05  # Inverter technology bonus
            elif product.get("technology") == "panasonic_inverter":
                score += 0.1   # Premium inverter technology
            
            return max(0.0, min(1.0, score))  # Clamp between 0 and 1
            
        except Exception as e:
            logger.error(f"Error calculating product suitability: {str(e)}")
            return 0.0
    
    def generate_product_reasoning(self, product: Dict[str, Any], room_area_m2: float,
                                 room_volume_m3: float, pool_area_m2: float, 
                                 pool_required: bool, confidence_score: float) -> str:
        """Generate reasoning for product recommendation"""
        try:
            reasons = []
            
            # Capacity reasoning
            if product.get("max_room_m2"):
                if room_area_m2 <= product["max_room_m2"]:
                    coverage_pct = (room_area_m2 / product["max_room_m2"]) * 100
                    reasons.append(f"Covers {coverage_pct:.0f}% of room area capacity ({product['max_room_m2']} m²)")
                else:
                    reasons.append("May be undersized for this room area")
            
            # Pool suitability
            if pool_required:
                if product.get("pool_safe", False):
                    if product.get("max_pool_m2") and pool_area_m2 > 0:
                        if pool_area_m2 <= product["max_pool_m2"]:
                            reasons.append(f"Pool-safe and suitable for {pool_area_m2:.1f} m² pool")
                        else:
                            reasons.append("Pool-safe but may need multiple units for large pool")
                    else:
                        reasons.append("Pool-safe design")
            
            # Technology advantages
            if product.get("technology") == "inverter":
                reasons.append("Inverter technology for energy efficiency")
            elif product.get("technology") == "panasonic_inverter":
                reasons.append("Premium Panasonic inverter technology")
            
            # Installation type
            if product.get("type") == "wall_mount":
                reasons.append("Wall-mounted installation")
            elif product.get("type") == "ducted":
                reasons.append("Ducted system for whole-home solution")
            elif product.get("type") == "portable":
                reasons.append("Portable for flexible use")
            
            # Price information
            if product.get("price_aud"):
                reasons.append(f"Priced at ${product['price_aud']:,.0f} AUD")
            
            # Confidence level
            if confidence_score >= 0.8:
                conf_text = "Excellent match"
            elif confidence_score >= 0.6:
                conf_text = "Good match"
            elif confidence_score >= 0.4:
                conf_text = "Suitable option"
            else:
                conf_text = "Marginal fit"
            
            reasoning = f"{conf_text} - {'; '.join(reasons)}"
            return reasoning
            
        except Exception as e:
            logger.error(f"Error generating reasoning: {str(e)}")
            return "Product recommendation available"
    
    def calculate_dehum_load(self, **kwargs) -> Dict[str, Any]:
        """Quick heuristic latent moisture load calculation (spec v0.1)
        Accepts flexible kwargs based on RoomSizingInput. Missing optional fields
        default to reasonable values so the AI can call with partial data.
        Returns dict with volume, latentLoad_L24h, calculationNotes.
        """
        try:
            # Required fields
            length = float(kwargs.get('length'))
            width = float(kwargs.get('width'))
            height = float(kwargs.get('height'))
            current_rh = float(kwargs.get('currentRH'))
            target_rh = float(kwargs.get('targetRH'))
            indoor_temp = float(kwargs.get('indoorTemp'))
        except (TypeError, ValueError):
            return {
                'error': 'VALIDATION_ERROR',
                'message': 'Missing or invalid required fields (length, width, height, currentRH, targetRH, indoorTemp)'
            }

        # Basic validation
        if not (0 < current_rh <= 100 and 0 < target_rh < current_rh <= 100):
            return {'error': 'RANGE_ERROR', 'message': 'Invalid RH values'}
        if not (0 < indoor_temp <= 50):
            return {'error': 'RANGE_ERROR', 'message': 'Invalid indoorTemp'}

        # Optional fields with defaults
        ach = float(kwargs.get('ach', 0.5))
        people_count = int(kwargs.get('peopleCount', 0))
        usage_hours = float(kwargs.get('usageHours', 24))
        special_loads = kwargs.get('specialLoads', []) or []

        # Step 1: Room volume
        volume = length * width * height  # m3
        room_area_m2 = length * width

        # Step 2-3: Simple latent load heuristic
        # ΔRH fraction
        delta_rh_frac = (current_rh - target_rh) / 100.0
        # Base factor: 0.25 L/day per m³ at 100 %→0 % drop (empirical)
        base_factor = 0.25
        base_load = volume * delta_rh_frac * base_factor

        # Step 4: Infiltration / ACH adjustment (very coarse)
        infil_load = volume * ach * 0.02  # L/day per ACH heuristic

        # Step 5: Occupant load (~0.12 L/hr latent per person)
        occupant_load = people_count * 0.12 * usage_hours

        # Pool parameters (if supplied)
        pool_area_m2 = float(kwargs.get('pool_area_m2', 0))
        water_temp_c = float(kwargs.get('waterTempC', 28))  # default typical pool

        # Water temperature multiplier (simple): upto 30C ->1, 31-35 ->1.5, 36+ ->2
        if water_temp_c <= 30:
            temp_mult = 1.0
        elif water_temp_c <= 35:
            temp_mult = 1.5
        else:
            temp_mult = 2.0

        # Step 6 special loads
        special_total = 0.0
        if pool_area_m2 > 0:
            # Refined spec: 3.33 L/24h per m² @ 28 °C baseline (100 L handles 30 m²)
            base_evap_L24h_per_m2 = 3.33
            # Temperature adjustment: +20 % per °C above 28, no reduction below
            temp_adjust = 1.0 + max(0.0, (water_temp_c - 28)) * 0.20
            special_L24h = pool_area_m2 * base_evap_L24h_per_m2 * temp_adjust
            special_total += special_L24h

        for sl in special_loads:
            if isinstance(sl, dict):
                if sl.get('evaporationRate_Lph'):
                    special_total += float(sl['evaporationRate_Lph']) * usage_hours
                elif sl.get('type') in ('Pool', 'Spa') and sl.get('surfaceArea_m2'):
                    # Mid-range pool evaporation 0.2 L/h per m² at 10 % ΔRH, scale linearly
                    evap_lph = float(sl['surfaceArea_m2']) * 0.2 * delta_rh_frac
                    special_total += evap_lph * usage_hours
                # Laundry / Custom could be extended later

        # Aggregate
        latent_load = base_load + infil_load + occupant_load + special_total
        latent_load = round(latent_load, 1)

        # After latent_load computation, before return, add debug dict and logging
        debug_info = {
            'volume_m3': volume,
            'delta_rh_frac': delta_rh_frac,
            'base_load_L24h': round(base_load, 2),
            'infiltration_L24h': round(infil_load, 2),
            'occupant_L24h': round(occupant_load, 2),
            'special_L24h': round(special_total, 2),
            'latent_load_L24h': latent_load,
            'pool_area_m2': pool_area_m2,
            'water_temp_c': water_temp_c,
            'temp_multiplier': temp_mult
        }

        # Pretty debug print when env DEBUG=true
        if os.getenv('DEBUG', '').lower() == 'true':
            import pprint; pprint.pprint({'DEHUM_LOAD_DEBUG': debug_info})

        notes_parts = [
            f"Volume={volume:.1f} m³",
            f"ΔRH={delta_rh_frac*100:.0f}%",
            f"ACH={ach}",
            f"People={people_count}",
        ]
        if special_total > 0:
            notes_parts.append(f"SpecialLoads={special_total:.1f} L/day")

        return {
            'room_area_m2': round(room_area_m2, 1),
            'volume': round(volume, 1),
            'latentLoad_L24h': latent_load,
            'calculationNotes': '; '.join(notes_parts),
            'debug': debug_info if os.getenv('DEBUG', '').lower() == 'true' else None
        }
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names"""
        return [
            "calculate_sizing",
            "calculate_dehum_load"
        ]

    # NEW HELPER
    def get_catalog_with_effective_capacity(self, include_pool_safe_only: bool = False) -> List[Dict[str, Any]]:
        """Return product catalog with pre-computed effective capacity (capacity_lpd × performance_factor)."""
        catalog = []
        for p in self.products:
            if include_pool_safe_only and not p.get("pool_safe", False):
                continue
            if p.get("capacity_lpd") is None:
                continue  # skip incomplete entries
            eff_cap = p["capacity_lpd"] * p.get("performance_factor", 1.0)
            catalog.append({
                "sku": p["sku"],
                "name": p.get("name", p["sku"]),
                "effective_capacity_lpd": eff_cap,
                "capacity_lpd": p["capacity_lpd"],
                "performance_factor": p.get("performance_factor", 1.0),
                "max_pool_m2": p.get("max_pool_m2"),
                "pool_safe": p.get("pool_safe", False),
                "max_room_m2": p.get("max_room_m2"),
                "max_room_m3": p.get("max_room_m3"),
                "price_aud": p.get("price_aud")
            })
        return catalog 