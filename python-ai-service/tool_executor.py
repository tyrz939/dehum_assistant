"""tool_executor.py – Executes OpenAI tool calls and handles caching.

This module is deliberately ignorant of prompts, sessions, or streaming – it
only cares about turning the LLM-generated `tool_calls` into actual Python
function invocations and returning structured results.
"""
from __future__ import annotations

import json
import logging
from typing import Dict, Any, List

from tools import DehumidifierTools
from models import SessionInfo

logger = logging.getLogger(__name__)


def _make_tool_key(name: str, args: Dict[str, Any]) -> str:
    """Create stable cache key (same logic as legacy agent)."""
    try:
        return name + "|" + json.dumps(args, sort_keys=True, separators=(",", ":"))
    except TypeError:
        return name + "|" + str(args)


class ToolExecutor:
    """Executes tool calls with caching."""

    def __init__(self, dehum_tools: DehumidifierTools):
        self._tools = dehum_tools

    def execute(
        self,
        tool_calls: List[Any],  # `openai.types.ToolCall` or similar
        session: SessionInfo,
    ) -> List[Dict[str, Any]]:
        """Run all tool calls and return list with name/args/result."""
        results: List[Dict[str, Any]] = []

        for tool_call in tool_calls:
            # Support both dict-shaped and object-shaped tool calls
            if hasattr(tool_call, "function"):
                func_obj = tool_call.function
                func_name = getattr(func_obj, "name", "")
                raw_args = getattr(func_obj, "arguments", "{}")
            else:
                func_dict = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
                func_name = func_dict.get("name", "")
                raw_args = func_dict.get("arguments", "{}")

            try:
                func_args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except json.JSONDecodeError:
                logger.warning("Malformed JSON in tool arguments; falling back to empty dict")
                func_args = {}

            cache_key = _make_tool_key(func_name, func_args)
            use_cache = func_name != "retrieve_relevant_docs"

            if use_cache and cache_key in session.tool_cache:
                logger.debug("ToolExecutor: using cached result for %s", func_name)
                result = session.tool_cache[cache_key]
            else:
                result = self._invoke(func_name, func_args, session)
                if use_cache:
                    session.tool_cache[cache_key] = result

            results.append({"name": func_name, "arguments": func_args, "result": result})

        return results

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _invoke(self, func_name: str, func_args: Dict[str, Any], session: SessionInfo):
        """Call the real python implementation behind `func_name`."""
        if func_name == "calculate_dehum_load":
            return self._tools.calculate_dehum_load(**func_args)
        if func_name == "get_product_catalog":
            return self._tools.get_product_catalog(**func_args)
        if func_name == "retrieve_relevant_docs":
            query = func_args.get("query", "")
            k = func_args.get("k", 3)
            enhanced_query = self._enhance_rag_query_with_context(query, session)
            chunks = self._tools.retrieve_relevant_docs(enhanced_query, k)
            if chunks:
                query_info = f"'{enhanced_query}'" if enhanced_query != query else f"'{query}'"
                formatted_content = f"RELEVANT DOCUMENTATION for query {query_info}:\n\n"
                for i, chunk in enumerate(chunks):
                    formatted_content += f"--- Document {i+1} ---\n{chunk}\n\n"
                formatted_content += (
                    "END OF DOCUMENTATION\n\nPlease use this information to provide an accurate, specific answer."
                )
                return {"formatted_docs": formatted_content, "chunks": chunks}
            else:
                query_info = f"'{enhanced_query}'" if enhanced_query != query else f"'{query}'"
                return {
                    "formatted_docs": (
                        f"No relevant documentation found for query {query_info}. "
                        "I don't have specific information about this topic in my available documentation."
                    ),
                    "chunks": [],
                }
        else:
            raise ValueError(f"Unknown function: {func_name}") 

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _enhance_rag_query_with_context(self, query: str, session: SessionInfo) -> str:
        if not session.conversation_history:
            return query

        recent_messages = session.conversation_history[-5:]
        product_context = set()

        product_patterns = [
            "SP500C",
            "SP1000C",
            "SP1500C",
            "SP500",
            "SP1000",
            "SP1500",
            "IDHR60",
            "IDHR96",
            "IDHR120",
            "DA-X60i",
            "DA-X140i",
            "DA-X60",
            "DA-X140",
            "Suntec",
            "Fairland",
            "Luko",
            "SP Pro",
            "SP series",
            "IDHR series",
            "DA-X series",
        ]

        for msg in recent_messages:
            if getattr(msg.role, "value", msg.role) == "user":
                content_lower = msg.content.lower()
                for pattern in product_patterns:
                    if pattern.lower() in content_lower:
                        product_context.add(pattern)

        if product_context:
            specific_models = [p for p in product_context if any(ch.isdigit() for ch in p)]
            if specific_models:
                most_specific = max(specific_models, key=len)
                return f"{most_specific} {query}"
            most_relevant = max(product_context, key=len)
            return f"{most_relevant} {query}"

        return query