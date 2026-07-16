"""Read models for the local radar dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field, replace as dataclass_replace
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


class DashboardLoadError(RuntimeError):
    """Raised when an exact, coherent operator generation cannot be read."""


class _DashboardSnapshotViews:
    """Computed render views kept separate from the immutable field contract."""

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
            and row.get("_decision_expired_at_read_time") is not True
            and row.get("_dashboard_route") != "diagnostic"
        )

    @property
    def diagnostic_candidates(self) -> tuple[dict[str, Any], ...]:
        if not self.generation_authoritative:
            return ()
        return tuple(
            row
            for row in self.current_candidates
            if row.get("_decision_expired_at_read_time") is not True
            and is_canonical_diagnostic_candidate(row)
        )

    @property
    def expired_visible_current_candidates(self) -> tuple[dict[str, Any], ...]:
        """Expired canonical operator routes retained as read-only history."""
        return _expired_candidate_view(self, diagnostics=False)

    @property
    def expired_diagnostic_candidates(self) -> tuple[dict[str, Any], ...]:
        """Expired diagnostic rows available only through explicit opt-in."""
        return _expired_candidate_view(self, diagnostics=True)

    @property
    def expired_current_candidates(self) -> tuple[dict[str, Any], ...]:
        """Compatibility alias for expired operator-visible canonical routes."""
        return self.expired_visible_current_candidates


@dataclass(frozen=True)
class DashboardSnapshot(_DashboardSnapshotViews):
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
    current_market_observations: tuple[dict[str, Any], ...] = ()
    exact_market_history: tuple[dict[str, Any], ...] = ()
    exact_market_history_metadata: Mapping[str, Any] = field(default_factory=dict)
    current_calendar_events: tuple[dict[str, Any], ...] = ()
    current_outcomes: tuple[dict[str, Any], ...] = ()
    current_outcomes_metadata: Mapping[str, Any] = field(default_factory=dict)
    current_request_ledger: Mapping[str, Any] = field(default_factory=dict)
    current_request_ledger_metadata: Mapping[str, Any] = field(default_factory=dict)
    source_coverage: Mapping[str, Any] = field(default_factory=dict)
    market_generation: Mapping[str, Any] = field(default_factory=dict)
    cumulative_feedback: tuple[dict[str, Any], ...] = ()
    cumulative_outcomes: tuple[dict[str, Any], ...] = ()
    campaign_outcomes: tuple[dict[str, Any], ...] = ()
    campaign_attempts: tuple[dict[str, Any], ...] = ()
    campaign_latest_attempt: Mapping[str, Any] = field(default_factory=dict)
    campaign_reservation: Mapping[str, Any] = field(default_factory=dict)
    campaign_history_metadata: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    maintenance_service: Mapping[str, Any] = field(default_factory=dict)
    maintenance_state: Mapping[str, Any] = field(default_factory=dict)
    maintenance_current_status: Mapping[str, Any] = field(default_factory=dict)
    maintenance_cycles: tuple[dict[str, Any], ...] = ()
    maintenance_history_metadata: Mapping[str, Mapping[str, Any]] = field(
        default_factory=dict
    )
    cumulative_history_metadata: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    provider_readiness: Mapping[str, Any] = field(default_factory=dict)
    provider_health: Mapping[str, Any] = field(default_factory=dict)
    provider_health_read_at: str | None = None
    provider_health_sha256: str | None = None
    provider_health_error: str | None = None
    research_lab: Mapping[str, Any] = field(default_factory=dict)


def is_canonical_diagnostic_candidate(row: Mapping[str, Any]) -> bool:
    """Return whether the stored Decision projection is diagnostic.

    The read-time expiry overlay deliberately changes ``_dashboard_route`` to
    ``diagnostic`` without mutating the canonical route.  Diagnostic visibility
    therefore has to be decided from the canonical projection rather than the
    effective read-time route.
    """

    return (
        row.get("_decision_model_status") != "v2"
        or str(row.get("radar_route") or "").strip().casefold() == "diagnostic"
    )


def _expired_candidate_view(
    snapshot: DashboardSnapshot,
    *,
    diagnostics: bool,
) -> tuple[dict[str, Any], ...]:
    if not snapshot.generation_authoritative:
        return ()
    return tuple(
        row
        for row in snapshot.current_candidates
        if row.get("_decision_expired_at_read_time") is True
        and is_canonical_diagnostic_candidate(row) is diagnostics
    )


def suppress_untrusted_current_data(snapshot: DashboardSnapshot) -> DashboardSnapshot:
    """Return a render-only view with every untrusted current artifact quarantined."""

    if snapshot.generation_authoritative:
        return snapshot
    suppressed = {
        "authority": "suppressed_untrusted_generation",
        "artifact_name": None,
        "sha256": None,
        "fingerprint_kind": None,
        "source_row_count": 0,
        "returned_row_count": 0,
        "truncated": False,
        "error": "generation_authority_failed",
    }
    doctor = snapshot.operator_state.get("doctor")
    safe_operator_state = {
        "run_id": snapshot.run_id,
        "profile": snapshot.profile,
        "artifact_namespace": snapshot.artifact_namespace,
        "revision": snapshot.revision,
        "manifest_status": snapshot.manifest_status,
        "doctor": dict(doctor) if isinstance(doctor, Mapping) else {},
    }
    for field_name in ("run_started_at", "generated_at"):
        timestamp = _safe_authority_timestamp(snapshot.operator_state.get(field_name))
        if timestamp is not None:
            safe_operator_state[field_name] = timestamp
    return dataclass_replace(
        snapshot,
        operator_state=safe_operator_state,
        current_candidates=(),
        current_market_anomalies=(),
        current_market_observations=(),
        exact_market_history=(),
        exact_market_history_metadata=suppressed,
        current_calendar_events=(),
        current_outcomes=(),
        current_outcomes_metadata=suppressed,
        current_request_ledger={},
        current_request_ledger_metadata=suppressed,
        source_coverage={},
        market_generation={},
        provider_readiness={},
    )


def _safe_authority_timestamp(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip() or len(value) > 64:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return value.strip()


@dataclass(frozen=True)
class DashboardGenerationBinding:
    """Exact operator generation accepted by a pointer-started dashboard."""

    artifact_namespace: str
    run_id: str
    revision: int
    operator_state_sha256: str

    @classmethod
    def from_snapshot(cls, snapshot: DashboardSnapshot) -> "DashboardGenerationBinding":
        """Capture the authority identity that was validated before serving."""

        if not snapshot.generation_authoritative:
            raise ValueError("dashboard generation binding requires an authoritative snapshot")
        return cls(
            artifact_namespace=snapshot.artifact_namespace,
            run_id=snapshot.run_id,
            revision=snapshot.revision,
            operator_state_sha256=snapshot.operator_state_sha256,
        )


@dataclass(frozen=True)
class DashboardResponse:
    status_code: int
    reason: str
    body: str


def build_dashboard_snapshot(
    namespace_dir: Path,
    *,
    identity: tuple[str, str, str, int],
    state: Mapping[str, Any],
    state_digest: str,
    now: datetime,
    authority_reasons: list[str],
    current_rows: tuple[
        tuple[dict[str, Any], ...],
        tuple[dict[str, Any], ...],
        tuple[dict[str, Any], ...],
        tuple[dict[str, Any], ...],
    ],
    current_metadata: tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]],
    exact_supporting_data: Mapping[str, Any],
    history: Mapping[str, Any],
    provider_health: tuple[Mapping[str, Any], str | None, str | None],
) -> DashboardSnapshot:
    """Assemble an immutable read model after the loader closes all checks."""

    run_id, profile, namespace, revision = identity
    current_candidates, current_anomalies, current_observations, current_calendar = current_rows
    source_coverage, market_generation, provider_readiness = current_metadata
    health_values, health_digest, health_error = provider_health
    doctor = state.get("doctor") if isinstance(state.get("doctor"), Mapping) else {}
    verified_revision = doctor.get("verified_revision")
    if isinstance(verified_revision, bool) or not isinstance(verified_revision, int):
        verified_revision = None
    return DashboardSnapshot(
        namespace_dir=namespace_dir,
        run_id=run_id,
        profile=profile,
        artifact_namespace=namespace,
        revision=revision,
        manifest_status=str(state.get("manifest_status") or "unknown"),
        doctor_status=str(doctor.get("status") or "not_run"),
        doctor_verified_revision=verified_revision,
        generation_authority_status=("authoritative" if not authority_reasons else "untrusted"),
        generation_authority_reasons=tuple(authority_reasons),
        generation_authority_checked_at=now.isoformat(),
        operator_state_sha256=state_digest,
        operator_state=state,
        current_candidates=current_candidates,
        current_market_anomalies=current_anomalies,
        current_market_observations=current_observations,
        exact_market_history=exact_supporting_data["exact_market_history"],
        exact_market_history_metadata=exact_supporting_data["exact_market_history_metadata"],
        current_calendar_events=tuple(dict(row) for row in current_calendar),
        current_outcomes=history["current_outcomes"],
        current_outcomes_metadata=exact_supporting_data["current_outcomes_metadata"],
        current_request_ledger=exact_supporting_data["current_request_ledger"],
        current_request_ledger_metadata=exact_supporting_data[
            "current_request_ledger_metadata"
        ],
        source_coverage=source_coverage,
        market_generation=market_generation,
        cumulative_feedback=history["feedback"],
        cumulative_outcomes=history["outcomes"],
        campaign_outcomes=history["campaign_outcomes"],
        campaign_attempts=history["campaign_attempts"],
        campaign_latest_attempt=history["campaign_latest_attempt"],
        campaign_reservation=history["campaign_reservation"],
        campaign_history_metadata=history["campaign_metadata"],
        maintenance_service=history["maintenance_service"],
        maintenance_state=history["maintenance_state"],
        maintenance_current_status=history["maintenance_current_status"],
        maintenance_cycles=history["maintenance_cycles"],
        maintenance_history_metadata=history["maintenance_metadata"],
        cumulative_history_metadata=history["metadata"],
        provider_readiness=provider_readiness,
        provider_health=health_values,
        provider_health_read_at=now.isoformat() if health_digest else None,
        provider_health_sha256=health_digest,
        provider_health_error=health_error,
    )


__all__ = (
    "DashboardGenerationBinding",
    "DashboardLoadError",
    "DashboardResponse",
    "DashboardSnapshot",
    "build_dashboard_snapshot",
    "suppress_untrusted_current_data",
)
