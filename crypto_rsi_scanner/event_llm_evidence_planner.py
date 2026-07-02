"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner`."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar.llm import evidence_planner as _llm_evidence_planner

globals().update(
    {
        name: getattr(_llm_evidence_planner, name)
        for name in dir(_llm_evidence_planner)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_llm_evidence_planner)
    if not (name.startswith("__") and name.endswith("__"))
)
