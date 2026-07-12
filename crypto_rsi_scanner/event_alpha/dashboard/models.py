"""Read models for the local radar dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


class DashboardLoadError(RuntimeError):
    """Raised when an exact, coherent operator generation cannot be read."""


@dataclass(frozen=True)
class DashboardSnapshot:
    namespace_dir: Path
    run_id: str
    profile: str
    artifact_namespace: str
    revision: int
    manifest_status: str
    doctor_status: str
    doctor_verified_revision: int | None
    generation_authority_status: str
    generation_authority_reasons: tuple[str, ...]
    generation_authority_checked_at: str
    operator_state_sha256: str
    operator_state: Mapping[str, Any]
    current_candidates: tuple[dict[str, Any], ...] = ()
    current_market_anomalies: tuple[dict[str, Any], ...] = ()
    current_calendar_events: tuple[dict[str, Any], ...] = ()
    cumulative_feedback: tuple[dict[str, Any], ...] = ()
    cumulative_outcomes: tuple[dict[str, Any], ...] = ()
    cumulative_history_metadata: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    provider_readiness: Mapping[str, Any] = field(default_factory=dict)
    provider_health: Mapping[str, Any] = field(default_factory=dict)
    provider_health_read_at: str | None = None
    provider_health_sha256: str | None = None
    provider_health_error: str | None = None

    @property
    def generation_authoritative(self) -> bool:
        return self.generation_authority_status == "authoritative"

    @property
    def current_generation_count(self) -> int:
        return len(self.current_candidates)

    @property
    def cumulative_store_count(self) -> int:
        try:
            return max(0, int(self.operator_state.get("cumulative_store_rows") or 0))
        except (TypeError, ValueError):
            return 0

    @property
    def visible_current_candidates(self) -> tuple[dict[str, Any], ...]:
        if not self.generation_authoritative:
            return ()
        return tuple(
            row
            for row in self.current_candidates
            if row.get("_decision_model_status") == "v2"
            and row.get("_dashboard_route") != "diagnostic"
        )

    @property
    def diagnostic_candidates(self) -> tuple[dict[str, Any], ...]:
        if not self.generation_authoritative:
            return ()
        return tuple(
            row
            for row in self.current_candidates
            if row.get("_decision_model_status") != "v2"
            or row.get("_dashboard_route") == "diagnostic"
        )


@dataclass(frozen=True)
class DashboardResponse:
    status_code: int
    reason: str
    body: str


__all__ = ("DashboardLoadError", "DashboardResponse", "DashboardSnapshot")
