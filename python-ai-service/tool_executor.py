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
            func_name = tool_call.function.name
            try:
                func_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                logger.warning("Malformed JSON in tool arguments; falling back to empty dict")
                func_args = {}

            cache_key = _make_tool_key(func_name, func_args)
            if cache_key in session.tool_cache:
                logger.debug("ToolExecutor: using cached result for %s", func_name)
                result = session.tool_cache[cache_key]
            else:
                result = self._invoke(func_name, func_args)
                session.tool_cache[cache_key] = result

            results.append({"name": func_name, "arguments": func_args, "result": result})

        return results

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _invoke(self, func_name: str, func_args: Dict[str, Any]):
        """Call the real python implementation behind `func_name`."""
        if func_name == "calculate_dehumidifier_sizing":
            if "waterTempC" in func_args:
                func_args["water_temp_c"] = func_args.pop("waterTempC")
            return self._tools.calculate_sizing(**func_args)
        elif func_name == "calculate_dehum_load":
            return self._tools.calculate_dehum_load(**func_args)
        else:
            raise ValueError(f"Unknown function: {func_name}") 