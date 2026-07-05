"""Utilities for the legacy notification pipeline."""

from __future__ import annotations

from .runtime import *

def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _provider_failure_count(warnings: Iterable[str]) -> int:
    tokens = ("failed", "failure", "backoff", "rate limit", "timeout", "dns", "429")
    return sum(1 for warning in warnings if any(token in warning.casefold() for token in tokens))

def _runtime_budget_exhausted(warnings: Iterable[str]) -> bool:
    return any("notification_runtime_budget_exhausted" in warning for warning in warnings)

__all__ = (
    '_float_or_none',
    '_provider_failure_count',
    '_runtime_budget_exhausted',
)
