"""Models helpers for integrated radar."""

from __future__ import annotations

from .runtime import *

@dataclass(frozen=True)
class _IntegratedRadarRequiredFields:
    namespace_dir: Path
    run_id: str
    profile: str
    run_mode: str
    artifact_namespace: str
    started_at: datetime
    finished_at: datetime
    raw_events: int
    candidates: int
    core_opportunity_rows_written: int
    core_opportunity_write_attempted: bool
    core_opportunity_write_success: bool
    core_opportunity_write_block_reason: str | None
    research_card_paths: tuple[Path, ...]
    research_cards_dir: str
    integrated_candidates_path: Path
    integrated_report_path: Path
    daily_brief_path: Path
    notification_preview_path: Path
    integrated_delivery_path: Path | None
    run_ledger_path: str
    core_opportunity_store_path: str


@dataclass(frozen=True)
class _IntegratedRadarOptionalArtifactFields:
    input_manifest_path: Path | None = None
    source_coverage_json_path: Path | None = None
    source_coverage_path: Path | None = None
    asset_registry_path: Path | None = None
    instrument_resolution_path: Path | None = None
    asset_resolution_report_path: Path | None = None
    research_observed_at: datetime | None = None
    wall_started_at: datetime | None = None
    wall_finished_at: datetime | None = None
    market_anomalies: int = 0
    market_state_snapshots: int = 0
    official_exchange_events: int = 0
    official_listing_candidates: int = 0
    scheduled_catalysts: int = 0
    unlock_candidates: int = 0
    derivatives_state_rows: int = 0
    derivatives_crowding_candidates: int = 0
    fade_review_candidates: int = 0
    dex_pool_state_rows: int = 0
    dex_pool_anomaly_rows: int = 0
    protocol_fundamental_rows: int = 0
    asset_registry_assets: int = 0
    instrument_resolution_rows: int = 0
    integrated_candidates: int = 0
    alerts: tuple[Mapping[str, Any], ...] = ()
    routed: int = 0
    alertable: int = 0


@dataclass(frozen=True)
class _IntegratedRadarSendFields:
    send_requested: bool = False
    send_attempted: bool = False
    send_success: bool = False
    send_items_attempted: int = 0
    send_items_delivered: int = 0
    send_would_send_items: int = 0
    send_lane_items_attempted: Mapping[str, int] | None = None
    send_lane_items_delivered: Mapping[str, int] | None = None
    send_heartbeat_due: bool = True
    send_heartbeat_sent: bool = False
    send_block_reason: str | None = "no_send_guard_enabled"
    research_review_digest_enabled: bool = False
    research_review_digest_candidates: int = 0
    research_review_digest_would_send: int = 0
    research_review_digest_sent: int = 0
    research_review_digest_block_reason: str | None = "no_send_guard_enabled"


@dataclass(frozen=True)
class _IntegratedRadarSnapshotFields:
    snapshot_write_attempted: bool = True
    snapshot_write_success: bool = True
    snapshot_rows_written: int = 0
    strict_alerts: int = 0
    alertable_decisions: int = 0
    research_candidates: int = 0
    raw_source_candidates: int = 0
    cards_written: int = 0
    research_cards_written: int = 0
    preview_rendered_items: int = 0
    preview_eligible_items: int = 0
    preview_skipped_items: int = 0
    preview_skip_reason_counts: Mapping[str, int] | None = None
    integrated_delivery_rows: int = 0
    integrated_lanes_rendered: Mapping[str, int] | None = None
    integrated_lanes_empty: Mapping[str, int] | None = None
    operator_absolute_path_count: int = 0
    artifact_doctor_status: str | None = None
    source_coverage_json_path_rel: str | None = None
    source_coverage_md_path_rel: str | None = None
    warnings: tuple[str, ...] = ()
    cycle_completed: bool = True


@dataclass(frozen=True)
class EventIntegratedRadarResult(
    _IntegratedRadarSnapshotFields,
    _IntegratedRadarSendFields,
    _IntegratedRadarOptionalArtifactFields,
    _IntegratedRadarRequiredFields,
):
    pass

__all__ = (
    'EventIntegratedRadarResult',
)
