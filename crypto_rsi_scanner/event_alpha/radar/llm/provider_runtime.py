"""Shared live-LLM provider assembly for one Event Alpha operating cycle."""

from __future__ import annotations

from typing import Any, Callable

from ....llm_providers.openai_support import OpenAIRequestGate


ProviderFactory = Callable[[Any], Any]


def build_shared_openai_inputs(
    extraction_cfg: Any,
    catalyst_frame_cfg: Any,
    relationship_cfg: Any,
    *,
    extraction_factory: ProviderFactory,
    catalyst_frame_factory: ProviderFactory,
    relationship_factory: ProviderFactory,
) -> dict[str, Any]:
    """Build the three provider roles and share one OpenAI failure gate."""
    extraction_provider = extraction_factory(extraction_cfg)
    catalyst_frame_provider = catalyst_frame_factory(catalyst_frame_cfg)
    relationship_provider = relationship_factory(relationship_cfg)
    request_gate = OpenAIRequestGate()
    for provider in (extraction_provider, catalyst_frame_provider, relationship_provider):
        if str(getattr(provider, "name", "")).casefold() == "openai" and hasattr(provider, "request_gate"):
            provider.request_gate = request_gate
    return {
        "extraction_cfg": extraction_cfg,
        "extraction_provider": extraction_provider,
        "catalyst_frame_cfg": catalyst_frame_cfg,
        "catalyst_frame_provider": catalyst_frame_provider,
        "relationship_cfg": relationship_cfg,
        "relationship_provider": relationship_provider,
    }


__all__ = ("build_shared_openai_inputs",)
