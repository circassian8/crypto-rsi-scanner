"""Small value objects for guarded market/no-send operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping


SAFETY_COUNTERS = {
    "trades_created": 0,
    "paper_trades_created": 0,
    "normal_rsi_signal_rows_written": 0,
    "triggered_fade_created": 0,
    "telegram_sends": 0,
}


class MarketNoSendError(RuntimeError):
    """A concise, credential-free market generation failure."""


class MarketProviderBackoff(MarketNoSendError):
    """Raised before a call when the exact local provider is in backoff."""


@dataclass(frozen=True)
class MarketProviderResponse:
    rows: tuple[Mapping[str, Any], ...]
    telemetry: Mapping[str, Any]


@dataclass(frozen=True)
class MarketProviderFetchResult:
    rows: tuple[Mapping[str, Any], ...]
    telemetry: dict[str, Any]


class MarketProviderRequestError(MarketNoSendError):
    """A provider failure carrying allowlisted, credential-free telemetry."""

    def __init__(self, error_class: str, telemetry: Mapping[str, Any]):
        super().__init__("market provider request was unavailable")
        allowed = {
            "endpoint_path", "request_started_at", "request_ended_at",
            "duration_ms", "http_status", "result_count", "retry_count",
            "error_class", "cache_behavior",
        }
        self.error_class = str(error_class or "provider_error")[:80]
        self.request_telemetry = {
            key: telemetry.get(key) for key in allowed if key in telemetry
        }


@dataclass(frozen=True)
class MarketNoSendReadiness:
    status: str
    provider: str
    live_provider_authorized: bool
    provider_call_attempted: bool
    fixture_mode: bool
    no_send: bool
    research_only: bool
    top_n: int
    fetch_limit: int
    artifact_namespace: str
    reasons: tuple[str, ...]
    will_call_provider: bool = False
    data_acquisition_mode: str = "preflight_only"
    candidate_source_mode: str = "preflight_only"
    baseline_status: str = "not_evaluated"
    baseline_observation_count: int = 0
    baseline_counted_observation_count: int = 0
    baseline_too_close_observation_count: int = 0
    baseline_asset_count: int = 0
    baseline_warm_asset_count: int = 0
    baseline_min_observations: int = 8
    baseline_newest_observed_at: str | None = None
    baseline_newest_counted_observed_at: str | None = None
    minimum_observation_spacing_seconds: int = 3600
    next_eligible_observation_at: str | None = None
    cadence_status: str = "eligible"
    history_next_eligible_observation_at: str | None = None
    provider_call_reservation_next_at: str | None = None
    provider_backoff_disabled_until: str | None = None
    cadence_eligible_now: bool = True
    baseline_feature_readiness: dict[str, Any] = field(default_factory=dict)
    baseline_asset_readiness: dict[str, Any] = field(default_factory=dict)
    baseline_rejection_counts: dict[str, int] = field(default_factory=dict)
    cache_status: str = "missing"
    cache_error: str | None = None
    spread_data_status: str = "not_evaluated"
    calendar_snapshot_status: str = "not_configured"
    calendar_snapshot_configured: bool = False
    calendar_snapshot_retained_rows: int = 0
    calendar_snapshot_source_mode: str = "not_configured"
    market_feature_policy: str = "temporal_when_warm; provider_price_volume_market_cap; explicit_proxies_otherwise"
    measurement_program: str = "decision_radar_live_observation_campaign_v2"
    decision_radar_campaign_eligible: bool = False
    burn_in_eligible: bool = False
    pointer_eligible: bool = False
    pointer_eligibility_status: str = "pending_complete_strict_doctor"
    artifact_paths: tuple[str, ...] = ()
    universe_policy: str = "bounded_top_liquid_by_total_volume"
    next_safe_command: str = "make radar-daily-ops-cycle"

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reasons"] = list(self.reasons)
        payload["artifact_paths"] = list(self.artifact_paths)
        payload["ready"] = self.ready
        return payload


@dataclass(frozen=True)
class MarketNoSendGenerationResult:
    status: str
    profile: str
    artifact_namespace: str
    namespace_dir: Path | None
    data_mode: str
    provider: str
    observed_at: str
    live_provider_authorized: bool
    provider_call_attempted: bool
    provider_request_succeeded: bool
    raw_market_rows: int = 0
    selected_market_rows: int = 0
    market_anomalies: int = 0
    candidates: int = 0
    core_rows: int = 0
    cards: int = 0
    run_id: str | None = None
    request_cache_path: Path | None = None
    manifest_path: Path | None = None
    failure_class: str | None = None
    data_acquisition_mode: str = "preflight_only"
    candidate_source_mode: str = "preflight_only"
    provenance_contract_valid: bool = False
    measurement_program: str = "decision_radar_live_observation_campaign_v2"
    decision_radar_campaign_eligible: bool = False
    decision_radar_campaign_counted: bool = False
    decision_radar_campaign_reason: str = "not_counted"
    burn_in_eligible: bool = False
    burn_in_counted: bool = False
    baseline_status: str = "not_evaluated"
    baseline_warm_assets: int = 0
    baseline_warming_assets: int = 0
    direct_feature_count: int = 0
    proxy_feature_count: int = 0
    request_ledger_path: Path | None = None
    history_path: Path | None = None
    outcomes_path: Path | None = None
    audit_json_path: Path | None = None
    audit_markdown_path: Path | None = None

    @property
    def complete(self) -> bool:
        return self.status == "complete"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["namespace_dir"] = str(self.namespace_dir) if self.namespace_dir else None
        payload["request_cache_path"] = str(self.request_cache_path) if self.request_cache_path else None
        payload["request_ledger_path"] = str(self.request_ledger_path) if self.request_ledger_path else None
        payload["history_path"] = str(self.history_path) if self.history_path else None
        payload["outcomes_path"] = str(self.outcomes_path) if self.outcomes_path else None
        payload["audit_json_path"] = str(self.audit_json_path) if self.audit_json_path else None
        payload["audit_markdown_path"] = str(self.audit_markdown_path) if self.audit_markdown_path else None
        payload["manifest_path"] = str(self.manifest_path) if self.manifest_path else None
        payload["complete"] = self.complete
        payload.update(SAFETY_COUNTERS)
        payload.update({"no_send": True, "research_only": True, "pointer_published": False})
        return payload


__all__ = (
    "MarketNoSendError",
    "MarketNoSendGenerationResult",
    "MarketNoSendReadiness",
    "MarketProviderBackoff",
    "MarketProviderFetchResult",
    "MarketProviderRequestError",
    "MarketProviderResponse",
    "SAFETY_COUNTERS",
)
