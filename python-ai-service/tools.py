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
                           volume_m3: float = None, ach: float = 1.0, peopleCount: int = 0, 
                           pool_area_m2: float = 0, waterTempC: float = None,
                           pool_activity: str = "low", vent_factor: float = 1.0,
                           additional_loads_lpd: float = 0, air_velocity_mps: float = 0.12,
                           outdoorTempC: float = None, outdoorRH: float = None,
                           covered_hours_per_day: float = 0.0, cover_reduction: float = 0.7,
                           air_movement_level: str = 'still', vent_level: str = 'low', mode: str = 'field_calibrated',
                           field_bias: float = 0.80, min_ratio_vs_standard: float = 0.70,
                           calibrate_to_data: bool = False, measured_data: list = None) -> Dict[str, Any]:
        """Thin wrapper around sizing.compute_load_components for backward compatibility.

        New optional params: outdoorTempC, outdoorRH, air_velocity_mps (default 0.12),
        pool_activity (default 'low'), covered_hours_per_day, cover_reduction, ach default 1.0.
        """
        from sizing import compute_load_components
        try:
            result = compute_load_components(
                current_rh=currentRH,
                target_rh=targetRH,
                indoor_temp_c=indoorTemp,
                length=length,
                width=width,
                height=height,
                volume_m3=volume_m3,
                ach=ach,
                people_count=peopleCount,
                pool_area_m2=pool_area_m2,
                water_temp_c=waterTempC,
                pool_activity=pool_activity,
                vent_factor=vent_factor,
                additional_loads_lpd=additional_loads_lpd,
                air_velocity_mps=air_velocity_mps,
                outdoor_temp_c=outdoorTempC,
                outdoor_rh_percent=outdoorRH,
                covered_hours_per_day=covered_hours_per_day,
                cover_reduction=cover_reduction,
                air_movement_level=air_movement_level,
                vent_level=vent_level,
                mode=mode,
                field_bias=field_bias,
                min_ratio_vs_standard=min_ratio_vs_standard,
                calibrate_to_data=calibrate_to_data,
                measured_data=measured_data,
            )
            # Map to legacy keys while preserving plot_data
            components = result["components"]
            legacy = {
                "volume": round(result["inputs"]["volume_m3"], 1),
                "latentLoad_L24h": result["total_lpd"],
                "room_area_m2": round(result["derived"]["room_area_m2"], 1) if result["derived"]["room_area_m2"] else None,
                "calculationNotes": "; ".join(result["notes"]),
                "components_breakdown": components,
                "plot_data": result.get("plot_data", {}),
                "steady_latent_kw": result.get("steady_latent_kw"),
                "pulldown_air_l": result.get("pulldown_air_l", 0.0),
            }

            # Enrich plot_data with product capacities and target line for charting
            try:
                required_lpd = legacy["latentLoad_L24h"]
                # Pool-safe filter if pool present
                pool_required = (pool_area_m2 or 0) > 0
                catalog = self.get_catalog_with_effective_capacity(include_pool_safe_only=pool_required)
                # Apply derate factor for indoor conditions at target RH
                derate = self.calculate_derate_factor(indoorTemp, targetRH)
                products_for_plot = []
                for p in catalog:
                    eff = p.get("effective_capacity_lpd")
                    if eff is None:
                        continue
                    eff_adj = round(eff * derate, 1)
                    products_for_plot.append({
                        "sku": p.get("sku"),
                        "name": p.get("name", p.get("sku")),
                        "capacity_lpd": eff_adj,
                        "url": p.get("url"),
                        "type": p.get("type")
                    })
                # Select a concise set for visualization: products around the required load
                if products_for_plot:
                    # Prefer those that meet or exceed required, then a couple below
                    above = [x for x in products_for_plot if x["capacity_lpd"] >= required_lpd]
                    below = [x for x in products_for_plot if x["capacity_lpd"] < required_lpd]
                    above.sort(key=lambda x: x["capacity_lpd"])  # ascending
                    below.sort(key=lambda x: x["capacity_lpd"], reverse=True)
                    selected = (below[:2] + above[:8])[:8] if above else below[:8]
                    # Keep ascending for chart
                    selected.sort(key=lambda x: x["capacity_lpd"])
                    legacy["plot_data"]["products"] = selected
                    legacy["plot_data"]["target_line_lpd"] = required_lpd
            except Exception as _e:
                # Don't fail the tool if product enrichment has an issue
                pass
            return legacy
        except Exception as e:
            logger.error(f"Error calculating dehumidifier load: {str(e)}")
            return {
                "error": f"Calculation error: {str(e)}",
                "volume": 0,
                "latentLoad_L24h": 0,
                "room_area_m2": 0,
                "calculationNotes": f"Error in calculation: {str(e)}",
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
        
    # --- Deprecated: moved to psychrometrics.py; kept for backward compatibility ---
    def saturation_vp(self, T: float) -> float:
        from psychrometrics import saturation_vp as _svp
        return _svp(T)

    def calculate_dew_point(self, temp: float, rh: float) -> float:
        from psychrometrics import dew_point as _dew
        return _dew(temp, rh)

    def calculate_derate_factor(self, temp: float, rh: float) -> float:
        from psychrometrics import derate_factor as _derate
        return _derate(temp, rh)

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
            
            # Dynamic source prioritization (no hard-coded filenames)
            # Boost any document whose source filename appears to match tokens found in the query.
            query_upper = query.strip().upper()
            # Tokens: continuous sequences with letters/numbers/dashes, length >= 3
            raw_tokens = re.findall(r"[A-Z0-9][A-Z0-9\-]{2,}", query_upper)
            tokens = {t for t in raw_tokens}

            if tokens:
                def score(doc):
                    src = (doc.metadata.get('source') or '').upper()
                    # Count token matches in source filename
                    matches = sum(1 for t in tokens if t in src)
                    return matches

                # Preserve original order on ties by enumerating
                indexed = list(enumerate(docs))
                indexed.sort(key=lambda iv: ( -score(iv[1]), iv[0]))
                docs = [d for _, d in indexed]
            
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
        available = [
            "calculate_dehum_load",
            "get_product_manual",
            "get_product_catalog",
        ]
        # Reflect RAG availability truthfully for /health
        if self.vectorstore is not None:
            available.append("retrieve_relevant_docs")
        return available