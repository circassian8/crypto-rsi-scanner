"""OpenAI Responses API raw-event extraction provider."""

from __future__ import annotations

from typing import Any, Mapping
from urllib.request import urlopen

from .base import LLMProviderResult
from .openai_support import (
    OpenAIRequestGate,
    build_extraction_request_payload,
    extract_openai_raw_event,
    initialize_openai_provider,
)


class OpenAILLMExtractionProvider:
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str | None = None,
        prompt_version: str = "llm_raw_event_extraction_v1",
        timeout: float = 30.0,
        base_url: str = "https://api.openai.com/v1/responses",
        opener=urlopen,
        request_gate: OpenAIRequestGate | None = None,
    ) -> None:
        initialize_openai_provider(
            self,
            api_key=api_key,
            model=model,
            prompt_version=prompt_version,
            timeout=timeout,
            base_url=base_url,
            opener=opener,
            request_gate=request_gate,
        )

    def extract_raw_event(self, packet: Mapping[str, Any]) -> LLMProviderResult:
        return extract_openai_raw_event(self, packet)

    def _request_payload(self, packet: Mapping[str, Any]) -> dict[str, Any]:
        return build_extraction_request_payload(self, packet)


__all__ = ("OpenAILLMExtractionProvider",)
