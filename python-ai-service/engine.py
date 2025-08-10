"""engine.py – unified LLM engine (params + API calling + streaming).

This module owns:
- Parameter building for all models (including GPT‑5 specifics)
- API calling (OpenAI client for GPT‑5, LiteLLM for others)
- Optional streaming support

It intentionally knows nothing about sessions, tools, or caching.
"""
from __future__ import annotations

from typing import Any, List, Dict, Optional
import logging

import litellm
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter
from openai import AsyncOpenAI

from config import config

logger = logging.getLogger(__name__)


class LLMEngine:
    """Unified wrapper for an LLM model.

    Parameters
    ----------
    model : str
        The model name (e.g. "gpt-4o-mini", "gpt-5-large")
    """

    def __init__(self, model: str) -> None:
        self.model = model

    async def completion(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        stream: bool = False,
    ):
        """Obtain a completion (streaming or non-streaming).

        Returns the underlying client result. If stream=True, this is an async-iterable
        streaming object (compatible with `async for chunk in <result>` usage).
        """
        params = self._build_params(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            stream=stream,
        )
        logger.debug("LLMEngine: calling model=%s stream=%s", self.model, stream)
        return await self._call_with_retry(**params)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _build_params(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        max_tokens: int,
        tools: Optional[List[Dict[str, Any]]],
        tool_choice: Optional[str],
        stream: bool,
    ) -> Dict[str, Any]:
        # GPT‑5 uses max_completion_tokens and supports reasoning/verbosity
        if model.startswith("gpt-5"):
            params: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "max_completion_tokens": max_tokens,
                "temperature": config.TEMPERATURE,
                "reasoning_effort": getattr(config, "GPT5_REASONING_EFFORT", "minimal"),
                "verbosity": getattr(config, "GPT5_VERBOSITY", "low"),
            }
        else:
            params = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": config.TEMPERATURE,
            }

        if tools is not None:
            params["tools"] = tools
        if tool_choice is not None:
            params["tool_choice"] = tool_choice
        if stream:
            params["stream"] = True
        return params

    @staticmethod
    def _is_retryable_error(error: Exception) -> bool:
        err = str(error).lower()
        return any(
            k in err
            for k in (
                "rate limit",
                "429",
                "connection",
                "timeout",
                "network",
                "502",
                "503",
                "504",
                "service unavailable",
                "internal server error",
            )
        )

    @retry(
        retry=retry_if_exception(_is_retryable_error),
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(1.0, 60.0),
        reraise=True,
    )
    async def _call_with_retry(self, **params):
        model = params.get("model", "")

        # Use OpenAI client directly for GPT‑5 models
        if model.startswith("gpt-5"):
            client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
            openai_params: Dict[str, Any] = {
                "model": params["model"],
                "messages": params["messages"],
                "temperature": params.get("temperature", 0.3),
                "stream": params.get("stream", False),
            }

            # GPT‑5 specific knobs
            if "max_completion_tokens" in params:
                openai_params["max_completion_tokens"] = params["max_completion_tokens"]
            if "reasoning_effort" in params:
                openai_params["reasoning_effort"] = params["reasoning_effort"]
            if "verbosity" in params:
                openai_params["verbosity"] = params["verbosity"]
            if "tools" in params:
                openai_params["tools"] = params["tools"]
            if "tool_choice" in params:
                openai_params["tool_choice"] = params["tool_choice"]

            return await client.chat.completions.create(**openai_params)

        # Fallback to LiteLLM for non‑GPT‑5 models
        return await litellm.acompletion(**params)