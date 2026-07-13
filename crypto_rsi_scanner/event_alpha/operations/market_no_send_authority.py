"""Exact operator authority and lineage helpers for market/no-send runs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..artifacts import operator_state, run_ledger
from ..radar import market_anomaly_scanner
from . import (
    market_no_send_calendar,
    market_no_send_provider,
    market_provenance,
)
from .market_no_send_io import read_jsonl, write_jsonl
from .market_no_send_models import MarketNoSendError, MarketNoSendReadiness


def initialize_exact_operator_state(
    context: Any,
    *,
    run_id: str,
    provenance: Mapping[str, Any],
) -> None:
    """Build exact operator state from the matching persisted run-ledger row."""

    rows = run_ledger.load_run_records(context.run_ledger_path, limit=20).rows
    matching = [
        dict(row)
        for row in rows
        if str(row.get("run_id") or "") == run_id
        and str(row.get("profile") or "default") == context.profile
        and str(row.get("artifact_namespace") or "") == context.artifact_namespace
    ]
    if len(matching) != 1:
        raise MarketNoSendError(
            "market generation has no unique persisted run-ledger authority"
        )
    exact = matching[0]
    for key, value in tuple(exact.items()):
        if key.endswith("_abs_debug") and value not in (None, "", [], {}):
            exact[key[: -len("_abs_debug")]] = value
    if exact.get("integrated_source_coverage_json_path_abs_debug"):
        exact["source_coverage_json_path_rel"] = exact[
            "integrated_source_coverage_json_path_abs_debug"
        ]
    if exact.get("source_coverage_path_abs_debug"):
        exact["source_coverage_md_path_rel"] = exact[
            "source_coverage_path_abs_debug"
        ]
    operator_state.begin_run(
        context.namespace_dir,
        exact,
        run_ledger_path=context.run_ledger_path,
        updated_at=datetime.now(timezone.utc),
    )
    _record_operator_provenance(context, run_id=run_id, provenance=provenance)


def _record_operator_provenance(
    context: Any,
    *,
    run_id: str,
    provenance: Mapping[str, Any],
) -> None:
    """Attach bounded generation provenance to the exact operator state."""

    with operator_state._state_lock(context.namespace_dir):  # noqa: SLF001
        loaded = operator_state.load_operator_state(context.namespace_dir)
        state = dict(loaded.state or {}) if loaded.valid else {}
        if not operator_state.state_matches_run(
            state,
            {
                "run_id": run_id,
                "profile": context.profile,
                "artifact_namespace": context.artifact_namespace,
            },
            profile=context.profile,
            artifact_namespace=context.artifact_namespace,
        ):
            raise MarketNoSendError(
                "market provenance has no matching operator generation"
            )
        state["market_no_send_provenance"] = dict(provenance)
        state["revision"] = int(state.get("revision") or 0) + 1
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        state["doctor"] = {
            "status": "not_run",
            "run_id": run_id,
            "authoritative": False,
            "strict": False,
            "schema_only": False,
            "skip_api_checks": False,
            "verified_at": None,
            "verified_revision": None,
            "blocker_count": 0,
            "warning_count": 0,
        }
        operator_state.write_json_atomic(
            operator_state.operator_state_path(context.namespace_dir),
            state,
        )


def attach_market_no_send_lineage(
    namespace_dir: Path,
    *,
    scan_result: market_anomaly_scanner.MarketAnomalyScanResult,
    normalized_rows: Iterable[Mapping[str, Any]],
    provider: str,
    data_mode: str,
    request_cache_artifact: str,
    request_ledger_artifact: str,
    run_id: str,
    provenance: Mapping[str, Any],
    safety_counters: Mapping[str, int],
) -> market_anomaly_scanner.MarketAnomalyScanResult:
    """Attach one closed provenance contract to scanner snapshots and anomalies."""

    by_coin = {
        str(row.get("coin_id") or ""): dict(row)
        for row in normalized_rows
        if str(row.get("coin_id") or "")
    }
    snapshot_path = namespace_dir / market_anomaly_scanner.MARKET_STATE_SNAPSHOT_FILENAME
    anomaly_path = namespace_dir / market_anomaly_scanner.MARKET_ANOMALY_FILENAME
    snapshot_rows = read_jsonl(snapshot_path)
    anomaly_rows = read_jsonl(anomaly_path)
    lineage = _lineage_values(
        provider=provider,
        data_mode=data_mode,
        request_cache_artifact=request_cache_artifact,
        request_ledger_artifact=request_ledger_artifact,
        provenance=provenance,
        safety_counters=safety_counters,
    )
    for row in snapshot_rows:
        source = by_coin.get(str(row.get("coin_id") or ""), {})
        row.update(lineage)
        _copy_market_quality_fields(row, source)
    for row in anomaly_rows:
        source = by_coin.get(str(row.get("coin_id") or ""), {})
        row.update(lineage)
        row["provider_generation_id"] = run_id
        snapshot = row.get("market_state_snapshot")
        if isinstance(snapshot, Mapping):
            attached = dict(snapshot)
            attached.update(lineage)
            _copy_market_quality_fields(attached, source)
            row["market_state_snapshot"] = attached
    write_jsonl(snapshot_path, snapshot_rows)
    write_jsonl(anomaly_path, anomaly_rows)
    return market_anomaly_scanner.refresh_market_anomaly_scan_result(scan_result)


def _lineage_values(
    *,
    provider: str,
    data_mode: str,
    request_cache_artifact: str,
    request_ledger_artifact: str,
    provenance: Mapping[str, Any],
    safety_counters: Mapping[str, int],
) -> dict[str, Any]:
    counted = provenance.get("decision_radar_campaign_counted") is True
    return {
        "candidate_provenance": "market_anomaly",
        "provider": provider,
        "source_provider": provider,
        "latest_source": provider,
        "source_class": "market_data",
        "source_pack": "market_anomaly_pack",
        "data_mode": data_mode,
        "data_acquisition_mode": provenance.get("data_acquisition_mode"),
        "candidate_source_mode": provenance.get("candidate_source_mode"),
        "provider_request_succeeded": True,
        "provider_source_artifact": request_cache_artifact,
        "provider_source_artifact_sha256": provenance.get(
            "provider_source_artifact_sha256"
        ),
        "request_ledger_path": request_ledger_artifact,
        "request_ledger_sha256": provenance.get("request_ledger_sha256"),
        "provenance_contract_valid": provenance.get("provenance_contract_valid") is True,
        "measurement_program": provenance.get("measurement_program"),
        "decision_radar_campaign_eligible": provenance.get(
            "decision_radar_campaign_eligible"
        )
        is True,
        "decision_radar_campaign_counted": counted,
        "decision_radar_campaign_reason": provenance.get(
            "decision_radar_campaign_reason"
        ),
        "burn_in_eligible": provenance.get("burn_in_eligible") is True,
        "burn_in_counted": provenance.get("burn_in_counted") is True,
        "contract_counted_candidate": counted,
        "burn_in_reason": provenance.get("burn_in_reason"),
        "contract_counted_status": "counted" if counted else "not_counted",
        "market_provenance": dict(provenance),
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        **dict(safety_counters),
    }


def _copy_market_quality_fields(
    target: dict[str, Any],
    source: Mapping[str, Any],
) -> None:
    for key in (
        "liquidity_basis",
        "volume_zscore_basis",
        "spread_status",
        "market_feature_basis",
        "market_data_quality",
        "direct_market_feature_count",
        "proxy_market_feature_count",
        "market_snapshot_id",
        "market_history_observation_id",
    ):
        if source.get(key) is not None:
            target[key] = source[key]


def closed_market_provenance(
    *,
    contract_version: int,
    data_mode: str,
    provider: str,
    observed_at: datetime,
    run_id: str,
    readiness: MarketNoSendReadiness,
    source_artifact: str,
    source_artifact_sha256: str,
    request_ledger_artifact: str,
    request_ledger_sha256: str,
    feature_basis: Mapping[str, Any],
    data_quality: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the exact, fail-closed market lineage shared by all surfaces."""

    live = data_mode == "live"
    raw = {
        "schema_version": market_provenance.MARKET_PROVENANCE_SCHEMA_VERSION,
        "contract_version": contract_version,
        "data_mode": data_mode,
        "data_acquisition_mode": "live_provider" if live else "mocked_fixture",
        "candidate_source_mode": "live_no_send" if live else "mocked_fixture",
        "provider": provider,
        "measurement_program": market_provenance.DECISION_RADAR_MEASUREMENT_PROGRAM,
        "provider_generation_id": run_id,
        "live_provider_authorized": readiness.live_provider_authorized,
        "fixture_mode": readiness.fixture_mode,
        "provider_call_attempted": True,
        "provider_call_succeeded": True,
        "provider_source_artifact": source_artifact,
        "provider_source_artifact_sha256": source_artifact_sha256,
        "request_ledger_path": request_ledger_artifact,
        "request_ledger_sha256": request_ledger_sha256,
        "cache_status": "write_through",
        "feature_basis": dict(feature_basis),
        "data_quality": {
            **dict(data_quality),
            "observed_at": observed_at.isoformat(),
            "no_send": True,
            "research_only": True,
        },
    }
    return market_provenance.normalize_market_provenance(raw)


def record_market_authority_artifacts(
    context: Any,
    *,
    run_id: str,
    request_path: Path,
    request_ledger_path: Path,
    manifest_path: Path,
    candidates_path: Path,
    outcomes_path: Path,
    history_filename: str,
) -> None:
    """Bind every mutable pilot product input to exact operator authority."""

    materialized = [
        ("market_no_send_source_cache", request_path, 1),
        ("market_no_send_request_ledger", request_ledger_path, 1),
        ("market_no_send_generation", manifest_path, 1),
        ("integrated_candidates", candidates_path, len(read_jsonl(candidates_path))),
        ("integrated_outcomes", outcomes_path, len(read_jsonl(outcomes_path))),
    ]
    history_path = context.namespace_dir / history_filename
    if history_path.exists():
        materialized.append(
            ("market_history", history_path, len(read_jsonl(history_path)))
        )
    calendar_source_path = (
        context.namespace_dir / market_no_send_calendar.CALENDAR_SOURCE_COPY_FILENAME
    )
    if calendar_source_path.exists():
        materialized.append(
            ("market_no_send_calendar_source", calendar_source_path, 1)
        )
    for name, filename in _optional_market_jsonl_artifacts():
        path = context.namespace_dir / filename
        if path.exists():
            materialized.append((name, path, len(read_jsonl(path))))
    provider_health_path = (
        context.namespace_dir / market_no_send_provider.PROVIDER_HEALTH_FILENAME
    )
    if provider_health_path.exists():
        materialized.append(("provider_health", provider_health_path, 1))
    for name, path, count in materialized:
        operator_state.record_artifact(
            context.namespace_dir,
            run_id=run_id,
            profile=context.profile,
            artifact_namespace=context.artifact_namespace,
            name=name,
            path=path,
            count=count,
        )


def _optional_market_jsonl_artifacts() -> tuple[tuple[str, str], ...]:
    return (
        ("market_state_snapshots", market_anomaly_scanner.MARKET_STATE_SNAPSHOT_FILENAME),
        ("market_anomalies", market_anomaly_scanner.MARKET_ANOMALY_FILENAME),
        (
            "market_anomaly_catalyst_search_queue",
            market_anomaly_scanner.MARKET_ANOMALY_CATALYST_SEARCH_QUEUE_FILENAME,
        ),
    )


__all__ = (
    "attach_market_no_send_lineage",
    "closed_market_provenance",
    "initialize_exact_operator_state",
    "record_market_authority_artifacts",
)
