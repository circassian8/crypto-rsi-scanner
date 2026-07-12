"""Provider protocol for research-only event relationship LLM analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class LLMProviderResult:
    raw: dict[str, Any] | None = None
    warning: str | None = None
    error_class: str | None = None
    http_status: int | None = None
    retryable: bool | None = None
    retry_after_seconds: float | None = None


def provider_batch_backoff_requested(result: LLMProviderResult) -> bool:
    """Return whether the remaining calls in this provider batch should stop."""
    return result.error_class in {
        "provider_backoff",
        "rate_limited",
        "quota_exhausted",
        "auth_failed",
        "access_forbidden",
    }


class LLMRelationshipProvider(Protocol):
    name: str

    def analyze_relationship(self, packet: Mapping[str, Any]) -> LLMProviderResult:
        """Return one structured relationship analysis for an evidence packet."""


class LLMExtractionProvider(Protocol):
    name: str

    def extract_raw_event(self, packet: Mapping[str, Any]) -> LLMProviderResult:
        """Return one structured extraction for a raw event evidence packet."""


class LLMCatalystFrameProvider(Protocol):
    name: str

    def analyze_catalyst_frames(self, packet: Mapping[str, Any]) -> LLMProviderResult:
        """Return one structured catalyst-frame analysis for raw event evidence."""


class LLMSourceQualityProvider(Protocol):
    name: str

    def judge_source_quality(self, packet: Mapping[str, Any]) -> LLMProviderResult:
        """Return one structured source-quality judgment for raw source evidence."""
