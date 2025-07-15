"""
Dehumidifier Tools - Sizing calculations and product recommendations
"""

import json
import os
import math
from typing import Dict, List, Optional, Any
from models import ProductRecommendation, SizingCalculation
import logging
import re

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
    
    def calculate_dehum_load(self, length: float, width: float, height: float, 
                           currentRH: float, targetRH: float, indoorTemp: float,
                           ach: float = 0.5, peopleCount: int = 0, 
                           pool_area_m2: float = 0, waterTempC: float = None) -> Dict[str, Any]:
        """
        Calculate latent moisture load for a room based on sizing spec v0.1
        
        Args:
            length: Room length in meters
            width: Room width in meters
            height: Ceiling height in meters
            currentRH: Current relative humidity %
            targetRH: Target relative humidity %
            indoorTemp: Indoor temperature °C
            ach: Air changes per hour (default 0.5)
            peopleCount: Number of occupants (default 0)
            pool_area_m2: Pool surface area in square meters (default 0)
            waterTempC: Pool water temperature in °C (optional)
            
        Returns:
            Dictionary containing volume, latentLoad_L24h, and calculationNotes
        """
        try:
            # Validation
            if currentRH < 0 or currentRH > 100:
                raise ValueError("currentRH must be between 0 and 100")
            if targetRH < 0 or targetRH > 100:
                raise ValueError("targetRH must be between 0 and 100")
            if targetRH >= currentRH:
                raise ValueError("targetRH must be less than currentRH")
            if indoorTemp < 0 or indoorTemp > 50:
                raise ValueError("indoorTemp must be between 0 and 50°C")
            
            # Step 1: Calculate room volume
            volume = length * width * height
            
            # Step 2: Calculate moisture difference (simplified psychrometric calculation)
            # Using approximate formula: moisture capacity increases ~7% per °C
            # At 20°C, 100% RH ≈ 17.3 g/kg dry air
            saturation_pressure_20c = 17.3  # g/kg at 20°C, 100% RH
            temp_factor = 1.07 ** (indoorTemp - 20)  # 7% increase per °C
            max_moisture_capacity = saturation_pressure_20c * temp_factor
            
            current_moisture = (currentRH / 100) * max_moisture_capacity
            target_moisture = (targetRH / 100) * max_moisture_capacity
            moisture_difference = current_moisture - target_moisture  # g/kg
            
            # Step 3: Calculate air mass (approximate air density at room temperature)
            # Air density ≈ 1.2 kg/m³ at 20°C, decreases with temperature
            air_density = 1.2 * (293.15 / (273.15 + indoorTemp))  # kg/m³
            air_mass = air_density * volume  # kg
            
            # Step 4: Calculate infiltration load
            # ACH determines how much outside air enters
            infiltration_load_gph = ach * air_mass * moisture_difference  # g/h
            infiltration_load_L24h = (infiltration_load_gph * 24) / 1000  # L/day
            
            # Step 5: Calculate occupant load
            # Typical latent load per person: 50-120 g/h depending on activity
            occupant_load_gph = peopleCount * 80  # g/h (moderate activity)
            occupant_load_L24h = (occupant_load_gph * 24) / 1000  # L/day
            
            # Step 6: Calculate pool load (if applicable)
            pool_load_L24h = 0
            if pool_area_m2 > 0:
                # Pool evaporation rate depends on water temperature and air conditions
                # Simplified formula: ~4-6 L/m²/day for typical pool conditions
                # Higher water temperature increases evaporation
                base_evap_rate = 5.0  # L/m²/day
                if waterTempC is not None:
                    # Increase evaporation rate by ~10% per °C above 25°C
                    temp_adjustment = 1 + max(0, (waterTempC - 25) * 0.1)
                    base_evap_rate *= temp_adjustment
                
                pool_load_L24h = pool_area_m2 * base_evap_rate
            
            # Step 7: Aggregate loads
            total_load_L24h = max(0, infiltration_load_L24h) + occupant_load_L24h + pool_load_L24h
            
            # Round to 1 decimal place
            total_load_L24h = round(total_load_L24h, 1)
            
            # Create calculation notes
            notes = []
            notes.append(f"Room: {length}×{width}×{height}m = {volume:.1f}m³")
            notes.append(f"RH reduction: {currentRH}% → {targetRH}% at {indoorTemp}°C")
            notes.append(f"Moisture difference: {moisture_difference:.1f} g/kg")
            notes.append(f"Air mass: {air_mass:.1f} kg")
            notes.append(f"ACH: {ach}, Infiltration load: {infiltration_load_L24h:.1f} L/day")
            
            if peopleCount > 0:
                notes.append(f"Occupants: {peopleCount} people, {occupant_load_L24h:.1f} L/day")
            
            if pool_area_m2 > 0:
                pool_temp_note = f" at {waterTempC}°C" if waterTempC is not None else ""
                notes.append(f"Pool: {pool_area_m2}m²{pool_temp_note}, {pool_load_L24h:.1f} L/day")
            
            notes.append(f"Total latent load: {total_load_L24h} L/day")
            
            return {
                "volume": round(volume, 1),
                "latentLoad_L24h": total_load_L24h,
                "room_area_m2": round(length * width, 1),
                "calculationNotes": "; ".join(notes)
            }
            
        except Exception as e:
            logger.error(f"Error calculating dehumidifier load: {str(e)}")
            return {
                "error": f"Calculation error: {str(e)}",
                "volume": length * width * height,
                "latentLoad_L24h": 0,
                "room_area_m2": length * width,
                "calculationNotes": f"Error in calculation: {str(e)}"
            }

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
                "type": p.get("type"),
                "effective_capacity_lpd": eff_cap,
                "capacity_lpd": p["capacity_lpd"],
                "performance_factor": p.get("performance_factor", 1.0),
                "pool_safe": p.get("pool_safe", False),
                "price_aud": p.get("price_aud"),
                "url": p.get("url")
            })
        return catalog
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names"""
        return [
            "calculate_sizing",
            "calculate_dehum_load"
        ]