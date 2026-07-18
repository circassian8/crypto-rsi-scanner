"""Exact request value object for historical outcome-price recovery."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OutcomePriceRecoveryRequest:
    """One exact, credential-free historical price request plan."""

    request_id: str
    outcome_identity_key: str
    source_artifact_namespace: str
    candidate_id: str
    core_opportunity_id: str
    symbol: str
    coin_id: str
    observed_at: str
    primary_horizon: str
    due_at: str
    allowed_latest_price_at: str
    allowed_lag_seconds: int
    endpoint_path: str
    query: tuple[tuple[str, str], ...]


__all__ = ("OutcomePriceRecoveryRequest",)
