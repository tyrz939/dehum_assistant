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
            # Try to load from current directory first (for deployment)
            current_dir_path = os.path.join(os.path.dirname(__file__), "product_db.json")
            if os.path.exists(current_dir_path):
                with open(current_dir_path, 'r') as f:
                    data = json.load(f)
                    return data.get("products", [])
            
            # Fallback to parent directory (for development)
            product_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "product_db.json")
            if os.path.exists(product_db_path):
                with open(product_db_path, 'r') as f:
                    data = json.load(f)
                    return data.get("products", [])
            
            # Final fallback to working directory
            with open("product_db.json", 'r') as f:
                data = json.load(f)
                return data.get("products", [])
                
        except FileNotFoundError:
            logger.error("Product database not found. Using empty product list.")
            return []
        except json.JSONDecodeError:
            logger.error("Invalid JSON in product database. Using empty product list.")
            return []
    
    def calculate_dehum_load(self, currentRH: float, targetRH: float, indoorTemp: float,
                           length: float = None, width: float = None, height: float = None,
                           volume_m3: float = None, ach: float = 0.6, peopleCount: int = 0, 
                           pool_area_m2: float = 0, waterTempC: float = None,
                           pool_activity: str = "none", vent_factor: float = 1.0,
                           additional_loads_lpd: float = 0) -> Dict[str, Any]:
        """
        Calculate latent moisture load for a room based on sizing spec v0.1
        
        Args:
            currentRH: Current relative humidity %
            targetRH: Target relative humidity %
            indoorTemp: Indoor temperature °C
            length: Room length in meters (optional if volume_m3 provided)
            width: Room width in meters (optional if volume_m3 provided)
            height: Ceiling height in meters (optional if volume_m3 provided)
            volume_m3: Room volume in cubic meters (alternative to L×W×H)
            ach: Air changes per hour (default 0.6)
            peopleCount: Number of occupants (default 0)
            pool_area_m2: Pool surface area in square meters (default 0)
            waterTempC: Pool water temperature in °C (optional, default 28°C)
            pool_activity: Pool activity level ("none" default=0.100 C, "low"=0.118, "medium"=0.136, "high"=0.156 kg/m²/h/kPa)
            vent_factor: Multiplier for infiltration load (default 1.0, e.g., 1.2 for poor ventilation)
            additional_loads_lpd: Additional latent loads in L/day (default 0, e.g., from plants/showers)
            
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
            
            # Step 1: Determine volume and dimensions
            if volume_m3 is not None:
                # Volume provided directly - fabricate cube-root dimensions for downstream compatibility
                if volume_m3 <= 0:
                    raise ValueError("volume_m3 must be greater than 0")
                volume = volume_m3
                edge = volume_m3 ** (1/3)  # Cube root for fabricated dimensions
                length = width = height = edge
            elif length is not None and width is not None and height is not None:
                # Traditional L×W×H provided
                if length <= 0 or width <= 0 or height <= 0:
                    raise ValueError("length, width, and height must be greater than 0")
                volume = length * width * height
            else:
                raise ValueError("Either volume_m3 OR all three dimensions (length, width, height) must be provided")
            
            # Define saturation vapor pressure function (Magnus formula, kPa)
            def saturation_vp(T):
                return 0.61094 * math.exp((17.625 * T) / (T + 243.04))
            
            # Atmospheric pressure (kPa, standard sea level)
            P_atm = 101.325
            
            # Step 2: Calculate humidity ratios (kg/kg dry air)
            # Current conditions
            P_v_current = (currentRH / 100) * saturation_vp(indoorTemp)
            W_current = 0.62198 * P_v_current / (P_atm - P_v_current)
            
            # Target conditions
            P_v_target = (targetRH / 100) * saturation_vp(indoorTemp)
            W_target = 0.62198 * P_v_target / (P_atm - P_v_target)
            
            delta_W = W_current - W_target  # kg/kg
            
            # Step 3: Calculate air mass (approximate air density at room temperature)
            # Air density ≈ 1.2 kg/m³ at 20°C, decreases with temperature
            air_density = 1.2 * (293.15 / (273.15 + indoorTemp))  # kg/m³
            air_mass = air_density * volume  # kg
            
            # Step 4: Calculate infiltration load
            # ACH determines how much outside air enters
            infiltration_load_kgph = ach * air_mass * delta_W  # kg/h
            infiltration_load_L24h = infiltration_load_kgph * 24  # L/day (1 kg ≈ 1 L)
            infiltration_load_L24h *= vent_factor  # Apply vent factor
            
            # Step 5: Calculate occupant load
            # Typical latent load per person: 50-120 g/h depending on activity
            occupant_load_gph = peopleCount * 80  # g/h (moderate activity)
            occupant_load_L24h = (occupant_load_gph * 24) / 1000  # L/day
            
            # Step 6: Calculate pool load (if applicable)
            pool_load_L24h = 0
            if pool_area_m2 > 0:
                # Room partial VP (kPa)
                P_a = P_v_current  # From current RH/temp
                
                # Water temp (default 28°C if not provided)
                T_w = waterTempC if waterTempC is not None else 28.0
                
                # Water saturation VP (kPa)
                P_w = saturation_vp(T_w)
                
                # Delta P (no negative evaporation)
                delta_P = max(P_w - P_a, 0)
                
                # Evaporation coefficient (kg/m²/h/kPa) based on activity
                activity_coeffs = {
                    "none": 0.100,  # Still water
                    "low": 0.118,   # Light use
                    "medium": 0.136,  # Moderate activity
                    "high": 0.156   # Jets/heavy use
                }
                C = activity_coeffs.get(pool_activity.lower(), 0.100)
                
                # Evaporation rate (kg/h)
                W = pool_area_m2 * C * delta_P
                
                # Convert to L/day (1 kg ≈ 1 L)
                pool_load_L24h = round(W * 24, 1)
            
            # Step 7: Aggregate loads
            total_load_L24h = max(0, infiltration_load_L24h) + occupant_load_L24h + pool_load_L24h + additional_loads_lpd
            
            # Round to 1 decimal place
            total_load_L24h = round(total_load_L24h, 1)
            
            # Create calculation notes
            notes = []
            if volume_m3 is not None:
                notes.append(f"Room: {volume:.1f}m³ (given volume, fabricated dimensions {edge:.1f}×{edge:.1f}×{edge:.1f}m)")
            else:
                notes.append(f"Room: {length}×{width}×{height}m = {volume:.1f}m³")
            notes.append(f"Volume: {volume:.1f}m³, ACH: {ach}")
            notes.append(f"RH reduction: {currentRH}% → {targetRH}% at {indoorTemp}°C")
            notes.append(f"Humidity ratio difference: {delta_W:.4f} kg/kg")
            notes.append(f"Air mass: {air_mass:.1f} kg")
            notes.append(f"Infiltration load: {infiltration_load_L24h:.1f} L/day (vent_factor={vent_factor})")
            
            if peopleCount > 0:
                notes.append(f"Occupants: {peopleCount} people, {occupant_load_L24h:.1f} L/day")
            
            if pool_area_m2 > 0:
                pool_temp_note = f" at {T_w}°C" if waterTempC is not None else " at default 28°C"
                notes.append(f"Pool: {pool_area_m2}m²{pool_temp_note}, evap load: {pool_load_L24h:.1f} L/day (activity={pool_activity}, C={C} kg/m²/h/kPa)")
            
            if additional_loads_lpd > 0:
                notes.append(f"Additional loads: {additional_loads_lpd:.1f} L/day")
            
            notes.append(f"Total latent load: {total_load_L24h} L/day")
            
            return {
                "volume": round(volume, 1),
                "latentLoad_L24h": total_load_L24h,
                "room_area_m2": round(length * width, 1),
                "calculationNotes": "; ".join(notes)
            }
            
        except Exception as e:
            logger.error(f"Error calculating dehumidifier load: {str(e)}")
            # Handle case where dimensions may be None
            try:
                error_volume = volume_m3 if volume_m3 is not None else (length * width * height if all(x is not None for x in [length, width, height]) else 0)
                error_area = length * width if all(x is not None for x in [length, width]) else 0
            except:
                error_volume = 0
                error_area = 0
            
            return {
                "error": f"Calculation error: {str(e)}",
                "volume": error_volume,
                "latentLoad_L24h": 0,
                "room_area_m2": error_area,
                "calculationNotes": f"Error in calculation: {str(e)}"
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
    
    def get_product_manual(self, sku: str, type: str = "manual") -> Dict[str, Any]:
        """
        Retrieve the manual or brochure text for a specific product
        
        Args:
            sku: The product SKU to look up
            type: "manual" or "brochure" (default: "manual")
            
        Returns:
            Dictionary containing text content and SKU, or error if not found
        """
        try:
            # Find product by SKU
            product = None
            for p in self.products:
                if p.get("sku") == sku:
                    product = p
                    break
            
            if not product:
                return {"error": "Product not found"}
            
            # Get the appropriate text field
            if type == "manual":
                text_content = product.get("manual_text", "Text not available")
            elif type == "brochure":
                text_content = product.get("brochure_text", "Text not available")
            else:
                return {"error": "Invalid type. Must be 'manual' or 'brochure'"}
            
            # If text_content looks like a file path, try to read from file
            if text_content and text_content.endswith('.txt') and not text_content.startswith('Text not'):
                try:
                    # Try local product_docs first (for deployment)
                    local_file_path = os.path.join(os.path.dirname(__file__), "product_docs", text_content)
                    if os.path.exists(local_file_path):
                        with open(local_file_path, 'r', encoding='utf-8') as f:
                            text_content = f.read()
                    else:
                        # Fallback to parent directory (for development)
                        parent_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "product_docs", text_content)
                        if os.path.exists(parent_file_path):
                            with open(parent_file_path, 'r', encoding='utf-8') as f:
                                text_content = f.read()
                        else:
                            text_content = f"File not found: {text_content}"
                except Exception as file_error:
                    text_content = f"Error reading file {text_content}: {str(file_error)}"
            
            return {
                "text": text_content,
                "sku": sku,
                "product_name": product.get("name", sku),
                "type": type
            }
            
        except Exception as e:
            logger.error(f"Error retrieving product {type} for SKU {sku}: {str(e)}")
            return {"error": f"Error retrieving {type}: {str(e)}"}

    def calculate_derate_factor(self, temp: float, rh: float) -> float:
        """
        Calculate derating factor for dehumidifier capacity based on temperature and humidity.
        
        Args:
            temp: Indoor temperature in °C
            rh: Target relative humidity in %
            
        Returns:
            Derating factor between 0.1 and 1.0
        """
        return min(1.0, max(0.1, 0.4 + 0.7 * (temp / 30) ** 2.2 * (rh / 85) ** 2.8))

    def get_available_tools(self) -> List[str]:
        """Get list of available tool names"""
        return [
            "calculate_dehum_load",
            "get_product_manual"
        ]