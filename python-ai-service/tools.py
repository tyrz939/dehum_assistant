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

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# RAG imports with fallback
try:
    from rag_pipeline import load_vectorstore
    RAG_AVAILABLE = True
except ImportError as e:
    logger.warning(f"RAG pipeline not available: {e}")
    RAG_AVAILABLE = False
    def load_vectorstore():
        return None

class DehumidifierTools:
    """Tools for dehumidifier sizing and product recommendations"""
    
    def __init__(self):
        self.products = self.load_product_database()
        
        # Initialize RAG vectorstore
        self.vectorstore = None
        if RAG_AVAILABLE:
            try:
                self.vectorstore = load_vectorstore()
                if self.vectorstore:
                    logger.info("RAG vectorstore loaded successfully")
                else:
                    logger.warning("RAG vectorstore could not be loaded")
            except Exception as e:
                logger.error(f"Error loading RAG vectorstore: {e}")
                self.vectorstore = None
        
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
                           additional_loads_lpd: float = 0, air_velocity_mps: float = 0.1) -> Dict[str, Any]:
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
            air_velocity_mps: Air velocity over pool surface in m/s (default 0.1, range 0.05-0.3 for indoor pools)
            
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
            if air_velocity_mps < 0 or air_velocity_mps > 1.0:
                raise ValueError("air_velocity_mps must be between 0 and 1.0 m/s")
            
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
            
            # Step 6: Calculate pool load (improved)
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
                
                # Base evaporation coefficient (kg/m²/h/kPa) based on activity (ASHRAE-aligned)
                activity_coeffs = {
                    "none": 0.05,   # Unoccupied baseline
                    "low": 0.065,   # Residential/light
                    "medium": 0.10,  # Moderate/therapy
                    "high": 0.15    # Public/heavy
                }
                C_base = activity_coeffs.get(pool_activity.lower(), 0.05)
                
                # Velocity-dependent adjustment (from ASHRAE Carrier: increases with air speed)
                C = C_base + 0.3 * air_velocity_mps  # Tuned: +0.03 at 0.1 m/s
                
                # Convection boost if water warmer than air (buoyancy enhancement)
                temp_diff = max(T_w - indoorTemp, 0)
                C *= (1 + 0.08 * temp_diff)  # +32% at +4°C, matches real-world boosts
                
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
                notes.append(f"Pool: {pool_area_m2}m²{pool_temp_note}, evap load: {pool_load_L24h:.1f} L/day (activity={pool_activity}, C={C:.3f} kg/m²/h/kPa, velocity={air_velocity_mps}m/s, convection boost={1 + 0.08 * temp_diff:.2f})")
            
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


    
    def get_product_catalog(self, 
                           capacity_min: float = None, 
                           capacity_max: float = None,
                           product_type: str = None,
                           pool_safe_only: bool = False,
                           price_range_max: float = None) -> Dict[str, Any]:
        """
        Get product catalog for pricing and comparison queries.
        
        Args:
            capacity_min: Minimum capacity in L/day (optional)
            capacity_max: Maximum capacity in L/day (optional) 
            product_type: Filter by type: 'wall_mount', 'ducted', 'portable' (optional)
            pool_safe_only: Only return pool-safe models (optional)
            price_range_max: Maximum price in AUD (optional)
            
        Returns:
            Dictionary with filtered catalog and summary info
        """
        catalog = []
        for p in self.products:
            # Skip incomplete entries
            if p.get("capacity_lpd") is None:
                continue
                
            # Apply filters
            if pool_safe_only and not p.get("pool_safe", False):
                continue
            if product_type and p.get("type") != product_type:
                continue
            if capacity_min and p.get("capacity_lpd", 0) < capacity_min:
                continue
            if capacity_max and p.get("capacity_lpd", 0) > capacity_max:
                continue
            if price_range_max and p.get("price_aud") and p.get("price_aud") > price_range_max:
                continue
                
            # Calculate effective capacity
            eff_cap = p["capacity_lpd"] * p.get("performance_factor", 1.0)
            
            catalog.append({
                "sku": p["sku"],
                "name": p.get("name", p["sku"]),
                "type": p.get("type"),
                "series": p.get("series"),
                "technology": p.get("technology"),
                "capacity_lpd": p["capacity_lpd"],
                "effective_capacity_lpd": eff_cap,
                "performance_factor": p.get("performance_factor", 1.0),
                "pool_safe": p.get("pool_safe", False),
                "price_aud": p.get("price_aud"),
                "url": p.get("url")
            })
        
        # Sort by capacity for easier browsing
        catalog.sort(key=lambda x: x["capacity_lpd"])
        
        return {
            "catalog": catalog,
            "total_products": len(catalog),
            "capacity_range": {
                "min": min([p["capacity_lpd"] for p in catalog]) if catalog else 0,
                "max": max([p["capacity_lpd"] for p in catalog]) if catalog else 0
            },
            "price_range": {
                "min": min([p["price_aud"] for p in catalog if p["price_aud"]]) if [p for p in catalog if p["price_aud"]] else None,
                "max": max([p["price_aud"] for p in catalog if p["price_aud"]]) if [p for p in catalog if p["price_aud"]] else None
            },
            "filters_applied": {
                "capacity_min": capacity_min,
                "capacity_max": capacity_max,
                "product_type": product_type,
                "pool_safe_only": pool_safe_only,
                "price_range_max": price_range_max
            }
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
        
    def saturation_vp(self, T: float) -> float:
        """Calculate saturation vapor pressure in kPa using Magnus formula."""
        return 0.61094 * math.exp((17.625 * T) / (T + 243.04))

    def calculate_dew_point(self, temp: float, rh: float) -> float:
        """Calculate dew point in °C using Magnus formula."""
        if rh <= 0 or rh > 100:
            return -100.0  # Invalid, arbitrary low
        pv = (rh / 100.0) * self.saturation_vp(temp)  # Note: assumes saturation_vp method exists or define it here if needed
        if pv <= 0:
            return -100.0
        alpha = math.log(pv / 0.61094)
        td = 243.04 * alpha / (17.625 - alpha)
        return td

    def calculate_derate_factor(self, temp: float, rh: float) -> float:
        """
        Calculate derating factor for dehumidifier capacity based on temperature and humidity.
        
        Args:
            temp: Indoor temperature in °C
            rh: Target relative humidity in %
            
        Returns:
            Derating factor between 0.1 and 1.0
        """
        td = self.calculate_dew_point(temp, rh)
        td_norm = max(td, 0.0) / 26.0  # Normalize to rated Td at 30°C/80% RH, floor at 0
        return min(1.0, max(0.1, td_norm ** 1.5))  # Exponent 1.5 for nonlinear tanking at low Td

    def retrieve_relevant_docs(self, query: str, k: int = 3) -> List[str]:
        """
        Retrieve relevant document chunks using RAG with product-aware prioritization
        
        Args:
            query: The search query
            k: Number of top chunks to return (default 3)
            
        Returns:
            List of relevant document chunks as strings
        """
        if not self.vectorstore:
            logger.warning("RAG vectorstore not available for document retrieval")
            return []
        
        if not query or not query.strip():
            logger.warning("Empty query provided for document retrieval")
            return []
        
        try:
            # Perform similarity search with more candidates for filtering
            search_k = min(k * 3, 15)  # Get more candidates to filter from
            docs = self.vectorstore.similarity_search(query.strip(), k=search_k)
            
            # Product-source mapping
            product_sources = {
                'SP500C': 'SUNTEC_SP_SERIES_INFO.txt',
                'SP1000C': 'SUNTEC_SP_SERIES_INFO.txt', 
                'SP1500C': 'SUNTEC_SP_SERIES_INFO.txt',
                'SP500': 'SUNTEC_SP_SERIES_INFO.txt',
                'SP1000': 'SUNTEC_SP_SERIES_INFO.txt',
                'SP1500': 'SUNTEC_SP_SERIES_INFO.txt',
                'Suntec': 'SUNTEC_SP_SERIES_INFO.txt',
                'SP Pro': 'SUNTEC_SP_SERIES_INFO.txt',
                'IDHR60': 'FAIRLAND_IDHR_SERIES_INFO.txt',
                'IDHR96': 'FAIRLAND_IDHR_SERIES_INFO.txt',
                'IDHR120': 'FAIRLAND_IDHR_SERIES_INFO.txt',
                'Fairland': 'FAIRLAND_IDHR_SERIES_INFO.txt',
                'DA-X60i': 'LUKO_DA-X_SERIES_INFO.txt',
                'DA-X140i': 'LUKO_DA-X_SERIES_INFO.txt',
                'DA-X60': 'LUKO_DA-X_SERIES_INFO.txt',
                'DA-X140': 'LUKO_DA-X_SERIES_INFO.txt',
                'Luko': 'LUKO_DA-X_SERIES_INFO.txt',
                'DA-X': 'LUKO_DA-X_SERIES_INFO.txt'
            }
            
            # Check if query contains specific product mentions
            query_upper = query.upper()
            target_source = None
            for product, source in product_sources.items():
                if product.upper() in query_upper:
                    target_source = source
                    break
            
            # Prioritize chunks from the target source if product is specified
            if target_source:
                # First, get chunks from the target source
                target_chunks = [doc for doc in docs if doc.metadata.get('source') == target_source]
                other_chunks = [doc for doc in docs if doc.metadata.get('source') != target_source]
                
                # Prioritize target source chunks, then fill with others if needed
                prioritized_docs = target_chunks[:k] + other_chunks[:max(0, k - len(target_chunks))]
                docs = prioritized_docs[:k]
                
                logger.info(f"Product-aware search: Found {len(target_chunks)} chunks from {target_source} for query '{query}'")
            
            # Extract content and format chunks
            chunks = []
            for doc in docs:
                source = doc.metadata.get('source', 'Unknown')
                content = doc.page_content.strip()
                
                if content:  # Only include non-empty chunks
                    # Format chunk with source information
                    formatted_chunk = f"[Source: {source}]\n{content}"
                    chunks.append(formatted_chunk)
            
            logger.info(f"Retrieved {len(chunks)} relevant chunks for query: '{query[:50]}{'...' if len(query) > 50 else ''}'")
            return chunks
            
        except Exception as e:
            logger.error(f"Error retrieving relevant docs for query '{query}': {e}")
            return []

    def get_available_tools(self) -> List[str]:
        """Get list of available tool names"""
        tools = [
            "calculate_dehum_load",
            "get_product_manual"
        ]
        
        # RAG tool is now managed by agent tool definitions based on config
        # No need for conditional inclusion here
        
        return tools