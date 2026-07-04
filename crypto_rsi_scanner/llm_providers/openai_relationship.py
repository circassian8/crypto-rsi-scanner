"""OpenAI Responses API relationship/catalyst-frame provider."""

from __future__ import annotations

from typing import Any, Mapping
from urllib.request import urlopen

from .base import LLMProviderResult
from .openai_support import (
    analyze_openai_catalyst_frames,
    analyze_openai_relationship,
    build_catalyst_frame_request_payload,
    build_relationship_request_payload,
    initialize_openai_provider,
)


class OpenAILLMRelationshipProvider:
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str | None = None,
        prompt_version: str = "llm_proxy_context_v1",
        timeout: float = 30.0,
        base_url: str = "https://api.openai.com/v1/responses",
        opener=urlopen,
    ) -> None:
        initialize_openai_provider(
            self,
            api_key=api_key,
            model=model,
            prompt_version=prompt_version,
            timeout=timeout,
            base_url=base_url,
            opener=opener,
        )

    def analyze_relationship(self, packet: Mapping[str, Any]) -> LLMProviderResult:
        return analyze_openai_relationship(self, packet)

    def analyze_catalyst_frames(self, packet: Mapping[str, Any]) -> LLMProviderResult:
        return analyze_openai_catalyst_frames(self, packet)

    def _request_payload(self, packet: Mapping[str, Any]) -> dict[str, Any]:
        return build_relationship_request_payload(self, packet)

    def _catalyst_frame_request_payload(self, packet: Mapping[str, Any]) -> dict[str, Any]:
        return build_catalyst_frame_request_payload(self, packet)


__all__ = ("OpenAILLMRelationshipProvider",)
