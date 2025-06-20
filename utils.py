"""
Utility functions for the dehumidifier assistant
"""
import re
import json
from typing import List, Dict, Tuple, Optional

# Dehumidifier-related keywords for relevance checking
DEHUMIDIFIER_KEYWORDS = [
    # Core dehumidifier terms
    'dehumidifier', 'humidity', 'moisture', 'damp', 'wet', 'condensation', 'humid',
    
    # Spaces and areas
    'pool', 'room', 'space', 'area', 'basement', 'garage', 'warehouse', 'office',
    'home', 'house', 'building', 'floor', 'level', 'zone', 'indoor', 'inside',
    
    # Measurements and sizing
    'm²', 'm2', 'sqm', 'square', 'meter', 'cubic', 'm³', 'm3', 'feet', 'ft',
    'sizing', 'size', 'large', 'small', 'big', 'dimensions', 'footprint',
    
    # Product brands and models
    'suntec', 'fairland', 'luko', 'sp-pro', 'idhr', 'fd-ss', 'fd-xx',
    
    # Technical terms
    'capacity', 'coverage', 'installation', 'install', 'ducted', 'wall', 'mounted',
    'portable', 'inverter', 'compressor', 'drain', 'condensate', 'rh', 'relative',
    
    # Common consultation words
    'recommendation', 'recommend', 'suggest', 'advice', 'help', 'need', 'want',
    'what', 'how', 'which', 'where', 'when', 'why', 'info', 'information',
    'details', 'more', 'tell', 'explain', 'compare', 'best', 'better', 'good',
    'cost', 'price', 'budget', 'cheap', 'expensive', 'energy', 'power', 'efficient',
    
    # Problem descriptions
    'problem', 'issue', 'trouble', 'mold', 'mould', 'smell', 'odor', 'musty',
    'water', 'leak', 'drip', 'steam', 'vapor', 'fog', 'window', 'glass', 'wall'
]

def is_relevant_question(text: str, conversation_context: bool = False) -> bool:
    """
    Check if question is related to dehumidifiers
    
    Args:
        text: The question text
        conversation_context: True if this is part of an ongoing conversation
    """
    text_lower = text.lower()
    
    # Very permissive for short conversational responses in context
    if conversation_context and len(text.strip()) < 50:
        conversational_patterns = [
            'what', 'how', 'why', 'where', 'when', 'which', 'who',
            'yes', 'no', 'ok', 'okay', 'sure', 'thanks', 'thank',
            'more', 'info', 'tell', 'explain', 'help', 'need',
            'good', 'great', 'perfect', 'excellent', 'nice'
        ]
        if any(pattern in text_lower for pattern in conversational_patterns):
            return True
    
    # Check against main keyword list
    return any(keyword in text_lower for keyword in DEHUMIDIFIER_KEYWORDS)

def validate_input(text: str) -> Tuple[bool, str]:
    """Validate user input for security and relevance"""
    if not text or not text.strip():
        return False, "Empty input"
    
    if len(text) > 400:
        return False, "Message exceeds 400 character limit"
    
    # Basic injection pattern detection
    suspicious_patterns = [
        r'<script.*?>.*?</script>',
        r'javascript:',
        r'data:text/html',
        r'vbscript:',
        r'onload\s*=',
        r'onerror\s*=',
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return False, "Invalid input detected"
    
    return True, text.strip()

def optimize_context(history: List[Dict], max_exchanges: int = 8) -> List[Dict]:
    """
    Bulletproof conversation context optimization that prioritizes customer requirements
    
    Strategy:
    1. ALWAYS preserve customer requirements (sizing, room type, constraints)  
    2. Keep recent exchanges for conversation flow
    3. Keep product discussions as secondary priority
    4. Maintain chronological order for coherent context
    """
    if not history or len(history) <= max_exchanges:
        return history
    
    # Always keep recent exchanges
    recent_exchanges = history[-max_exchanges:]
    
    # CRITICAL: Customer requirement keywords (sizing, space, constraints)
    customer_requirement_keywords = [
        # Sizing and measurements - HIGHEST PRIORITY
        'm²', 'm2', 'sqm', 'square', 'meter', 'cubic', 'm³', 'm3', 'feet', 'ft',
        'size', 'area', 'large', 'small', 'big', 'dimensions', 'footprint',
        
        # Room/space types - CRITICAL CONTEXT  
        'garage', 'basement', 'pool', 'room', 'space', 'warehouse', 'office',
        'home', 'house', 'building', 'floor', 'level', 'zone',
        
        # Installation constraints - IMPORTANT REQUIREMENTS
        'wall', 'mounted', 'ducted', 'portable', 'ceiling', 'floor',
        'installation', 'install', 'placement', 'location',
        
        # Performance requirements - CUSTOMER NEEDS
        'budget', 'noise', 'quiet', 'energy', 'efficient', 'power',
        'inverter', 'compressor', 'capacity', 'coverage'
    ]
    
    # Product keywords (lower priority)
    product_keywords = ['suntec', 'fairland', 'luko', 'sp-pro', 'idhr', 'fd-ss', 'fd-xx']
    
    # Find critical earlier messages
    critical_earlier = []
    product_earlier = []
    
    for msg in history[:-max_exchanges]:
        content_lower = msg.get('content', '').lower()
        
        # HIGH PRIORITY: Customer requirements
        if any(keyword in content_lower for keyword in customer_requirement_keywords):
            critical_earlier.append(msg)
        # LOWER PRIORITY: Product mentions  
        elif any(keyword in content_lower for keyword in product_keywords):
            product_earlier.append(msg)
    
    # Combine with smart prioritization
    max_total = max_exchanges + 6  # Generous limit for alpha
    
    # Build final context: critical customer info + recent + product mentions if space
    essential_context = critical_earlier + recent_exchanges
    
    if len(essential_context) <= max_total:
        # We have space for some product context too
        remaining_slots = max_total - len(essential_context)
        final_context = critical_earlier + product_earlier[:remaining_slots] + recent_exchanges
    else:
        # Prioritize customer requirements over recent if needed
        if len(critical_earlier) <= max_total // 2:
            # Keep all critical + fill with recent
            remaining_for_recent = max_total - len(critical_earlier)
            final_context = critical_earlier + recent_exchanges[-remaining_for_recent:]
        else:
            # Even critical context is too much, keep most important + some recent
            final_context = critical_earlier[:max_total//2] + recent_exchanges[-(max_total//2):]
    
    # Sort by original order to maintain conversation flow
    final_context_ordered = []
    for msg in history:
        if msg in final_context:
            final_context_ordered.append(msg)
    
    return final_context_ordered

def estimate_tokens(messages: List[Dict]) -> int:
    """Rough token estimation for cost tracking"""
    total_chars = sum(len(msg.get('content', '')) for msg in messages)
    # Rough approximation: ~4 characters per token
    return total_chars // 4

def get_session_key(session_id: str, key: str) -> str:
    """Generate Redis key for session data"""
    return f"session:{session_id}:{key}"

def safe_json_loads(json_str: str, default=None):
    """Safely parse JSON with fallback"""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default or []

def safe_json_dumps(data) -> str:
    """Safely serialize to JSON"""
    try:
        return json.dumps(data)
    except (TypeError, ValueError):
        return "[]" 