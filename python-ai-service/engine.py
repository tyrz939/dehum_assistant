"""engine.py – thin wrapper around LiteLLM completion + helper utilities.

This module intentionally knows *nothing* about sessions, tools, or caching –
those concerns live elsewhere.  It simply exposes an async method to obtain a
completion from a model, with optional OpenAI tools.
"""
from __future__ import annotations

from typing import Any, Callable, List, Dict, Optional
import litellm
import logging

logger = logging.getLogger(__name__)


class LLMEngine:
    """Light-weight wrapper for an LLM model.

    Parameters
    ----------
    model : str
        The model name (e.g. "gpt-4o-mini")
    completion_params_builder : Callable[[str, List[Dict[str, str]], int], Dict[str, Any]]
        Function that returns a parameter dict compatible with `litellm.acompletion`.
    api_caller : Callable[..., Any]
        Awaitable that actually performs the API request (allows custom retry logic).
    """

    def __init__(
        self,
        model: str,
        completion_params_builder: Callable[[str, List[Dict[str, str]], int], Dict[str, Any]],
        api_caller: Callable[..., Any],
    ) -> None:
        self.model = model
        self._build_params = completion_params_builder
        self._api_caller = api_caller

    async def completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str | None = None,
        stream: bool = False,
    ):  # -> OpenAI Response object
        params = self._build_params(self.model, messages, max_tokens)
        if tools is not None:
            params["tools"] = tools
        if tool_choice is not None:
            params["tool_choice"] = tool_choice
        if stream:
            params["stream"] = True
        logger.debug("LLMEngine: calling model=%s stream=%s", self.model, stream)
        return await self._api_caller(**params) 