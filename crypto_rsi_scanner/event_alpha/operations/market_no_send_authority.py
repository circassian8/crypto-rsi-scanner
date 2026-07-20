"""Exact operator authority and lineage helpers for market/no-send runs."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..artifacts import operator_state, run_ledger, schema_v1
from ..radar import (
    market_anomaly_receipt,
    market_anomaly_scanner,
    market_shadow_surprise,
)
from . import (
    market_no_send_calendar,
    market_no_send_provider,
    market_provenance,
)
from .market_no_send_io import (
    parse_jsonl_bytes,
    read_jsonl,
)
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
    history_artifact: str,
    history_sha256: str,
    minimum_shadow_sample_count: int,
) -> market_anomaly_scanner.MarketAnomalyScanResult:
    """Attach provenance and post-scan-only shadow evidence to market artifacts."""

    source_rows = tuple(dict(row) for row in normalized_rows if isinstance(row, Mapping))
    by_coin = {
        str(row.get("coin_id") or ""): dict(row)
        for row in source_rows
        if str(row.get("coin_id") or "")
    }
    if Path(history_artifact).name != history_artifact:
        raise MarketNoSendError("market shadow history artifact must be a basename")
    history_path = namespace_dir / history_artifact
    identity = (scan_result.namespace_device, scan_result.namespace_inode)
    scanner_names = (
        market_anomaly_scanner.MARKET_STATE_SNAPSHOT_FILENAME,
        market_anomaly_scanner.MARKET_ANOMALY_FILENAME,
        market_anomaly_scanner.MARKET_ANOMALY_CATALYST_SEARCH_QUEUE_FILENAME,
        market_anomaly_scanner.MARKET_ANOMALY_REPORT_FILENAME,
    )
    scanner_paths = (
        scan_result.snapshots_path,
        scan_result.anomalies_path,
        scan_result.catalyst_search_queue_path,
        scan_result.report_path,
    )
    payloads = market_anomaly_receipt.artifact_payloads(
        namespace_dir,
        namespace_identity=identity,
        paths=(history_path, *scanner_paths),
        expected_names=(history_artifact, *scanner_names),
    )
    history_bytes = payloads[history_artifact]
    if hashlib.sha256(history_bytes).hexdigest() != history_sha256:
        raise MarketNoSendError("market shadow history artifact fingerprint mismatch")
    expected_scanner_sha256 = {
        scanner_names[0]: scan_result.snapshots_sha256,
        scanner_names[1]: scan_result.anomalies_sha256,
        scanner_names[2]: scan_result.catalyst_search_queue_sha256,
        scanner_names[3]: scan_result.report_sha256,
    }
    if any(
        market_anomaly_receipt.sha256(payloads[name]) != expected
        for name, expected in expected_scanner_sha256.items()
    ):
        raise RuntimeError(
            "market_anomaly_completion_receipt_invalid:artifact_identity"
        )
    shadow_by_observation = _shadow_surprise_by_observation_id(
        source_rows,
        parse_jsonl_bytes(history_bytes),
        minimum_sample_count=minimum_shadow_sample_count,
        history_artifact=history_artifact,
        history_sha256=history_sha256,
    )
    snapshot_path = scan_result.snapshots_path
    anomaly_path = scan_result.anomalies_path
    snapshot_rows = parse_jsonl_bytes(payloads[scanner_names[0]])
    anomaly_rows = parse_jsonl_bytes(payloads[scanner_names[1]])
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
        _copy_shadow_temporal_surprise(row, source, shadow_by_observation)
    for row in anomaly_rows:
        source = by_coin.get(str(row.get("coin_id") or ""), {})
        row.update(lineage)
        row["provider_generation_id"] = run_id
        _copy_shadow_temporal_surprise(row, source, shadow_by_observation)
        snapshot = row.get("market_state_snapshot")
        if isinstance(snapshot, Mapping):
            attached = dict(snapshot)
            attached.update(lineage)
            _copy_market_quality_fields(attached, source)
            row["market_state_snapshot"] = attached
    market_anomaly_receipt.write_artifacts_atomic(
        namespace_dir,
        payloads={
            scanner_names[0]: _jsonl_payload(snapshot_path, snapshot_rows),
            scanner_names[1]: _jsonl_payload(anomaly_path, anomaly_rows),
            scanner_names[2]: payloads[scanner_names[2]],
            scanner_names[3]: payloads[scanner_names[3]],
        },
        expected_names=scanner_names,
        expected_namespace_identity=identity,
        expected_existing_sha256=expected_scanner_sha256,
        expected_guarded_sha256={history_artifact: history_sha256},
    )
    return market_anomaly_scanner.refresh_market_anomaly_scan_result(scan_result)


def _shadow_surprise_by_observation_id(
    normalized_rows: Iterable[Mapping[str, Any]],
    history_rows: Iterable[Mapping[str, Any]],
    *,
    minimum_sample_count: int,
    history_artifact: str,
    history_sha256: str,
) -> dict[str, dict[str, Any]]:
    history = tuple(dict(row) for row in history_rows if isinstance(row, Mapping))
    by_observation: dict[str, list[dict[str, Any]]] = {}
    for row in history:
        observation_id = str(row.get("observation_id") or "")
        if observation_id:
            by_observation.setdefault(observation_id, []).append(row)
    result: dict[str, dict[str, Any]] = {}
    seen_source_observations: set[str] = set()
    for source in normalized_rows:
        observation_id = str(source.get("market_history_observation_id") or "")
        if not observation_id:
            continue
        if observation_id in seen_source_observations:
            raise MarketNoSendError(
                "market shadow source observation identity is not unique"
            )
        seen_source_observations.add(observation_id)
        matches = by_observation.get(observation_id, [])
        if len(matches) != 1:
            raise MarketNoSendError(
                "market shadow current observation has no unique history row"
            )
        current = matches[0]
        asset_id = str(current.get("canonical_asset_id") or "")
        source_asset_id = str(source.get("canonical_asset_id") or "")
        current_at = _market_history_time(current.get("observed_at"))
        if (
            not asset_id
            or not source_asset_id
            or asset_id != source_asset_id
            or current_at is None
        ):
            raise MarketNoSendError("market shadow current observation identity is invalid")
        prior = tuple(
            row
            for row in history
            if str(row.get("canonical_asset_id") or "") == asset_id
            and row.get("baseline_counted") is True
            and (observed_at := _market_history_time(row.get("observed_at"))) is not None
            and observed_at < current_at
        )
        benchmark_observations = {
            benchmark: _benchmark_history_rows(
                history,
                asset_ids=asset_ids,
                current_at=current_at,
            )
            for benchmark, asset_ids in market_shadow_surprise.BENCHMARK_ASSET_IDS.items()
        }
        result[observation_id] = market_shadow_surprise.evaluate_shadow_temporal_surprise(
            current,
            prior,
            minimum_sample_count=minimum_sample_count,
            history_artifact=history_artifact,
            history_sha256=history_sha256,
            benchmark_observations=benchmark_observations,
        )
    return result


def _benchmark_history_rows(
    history: tuple[dict[str, Any], ...],
    *,
    asset_ids: tuple[str, ...],
    current_at: datetime,
) -> tuple[dict[str, Any], ...]:
    selected_asset_id = next(
        (
            asset_id
            for asset_id in asset_ids
            if any(
                str(row.get("canonical_asset_id") or "") == asset_id
                for row in history
            )
        ),
        None,
    )
    if selected_asset_id is None:
        return ()
    return tuple(
        row
        for row in history
        if str(row.get("canonical_asset_id") or "") == selected_asset_id
        and row.get("baseline_counted") is True
        and (observed_at := _market_history_time(row.get("observed_at"))) is not None
        and observed_at <= current_at
    )


def _copy_shadow_temporal_surprise(
    target: dict[str, Any],
    source: Mapping[str, Any],
    shadow_by_observation: Mapping[str, Mapping[str, Any]],
) -> None:
    observation_id = str(source.get("market_history_observation_id") or "")
    shadow = shadow_by_observation.get(observation_id)
    if shadow is not None:
        target["shadow_temporal_surprise"] = copy.deepcopy(dict(shadow))


def _market_history_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _jsonl_payload(path: Path, rows: Iterable[Mapping[str, Any]]) -> bytes:
    lines = [
        json.dumps(
            schema_v1.stamp_artifact_row(row, path=path),
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )
        for row in rows
    ]
    return (("\n".join(lines) + "\n") if lines else "").encode("utf-8")


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
