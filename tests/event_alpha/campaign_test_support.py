"""Exact local artifact fixtures for Decision Radar campaign tests."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from crypto_rsi_scanner.event_alpha.operations import market_no_send_io
from crypto_rsi_scanner.event_alpha.operations.market_no_send_models import (
    SAFETY_COUNTERS,
)
from crypto_rsi_scanner.event_alpha.operations.market_provenance import (
    DECISION_RADAR_MEASUREMENT_PROGRAM,
)


def write_countable_generation(
    base: Path,
    namespace: str,
    observed_at: str,
    *,
    candidates: Sequence[Mapping[str, Any]],
    legacy: bool = False,
    direct_feature_count: int | None = None,
    proxy_feature_count: int = 0,
    core_rows: Sequence[Mapping[str, Any]] = (),
    integrated_outcome_rows: Sequence[Mapping[str, Any]] = (),
) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    directory = base / namespace
    directory.mkdir(parents=True, exist_ok=True)
    profile = "no_key_live"
    run_id = f"{observed_at}|{profile}"
    run_mode = "burn_in" if legacy else "operational"
    selected_count = max(1, len(candidates))
    raw_count = selected_count
    campaign = {} if legacy else {
        "measurement_program": DECISION_RADAR_MEASUREMENT_PROGRAM,
        "decision_radar_campaign_eligible": True,
        "decision_radar_campaign_counted": True,
        "decision_radar_campaign_reason": "counted_live_no_send_exact_lineage",
    }
    common = {
        "contract_version": 2,
        "profile": profile,
        "artifact_namespace": namespace,
        "run_mode": run_mode,
        "run_id": run_id,
        "data_mode": "live",
        "data_acquisition_mode": "live_provider",
        "candidate_source_mode": "live_no_send",
        "provider": "coingecko",
        "observed_at": observed_at,
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "raw_market_row_count": raw_count,
        "selected_market_row_count": selected_count,
        "provenance_contract_valid": True,
        **campaign,
        "burn_in_eligible": legacy,
        "burn_in_counted": legacy,
        "burn_in_reason": (
            "counted_live_no_send_exact_lineage"
            if legacy
            else "not_counted_separate_decision_radar_campaign"
        ),
        "contract_counted_status": "counted",
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        **SAFETY_COUNTERS,
    }
    source_path = directory / "event_market_no_send_market_rows.json"
    market_no_send_io.write_json_atomic(source_path, {
        **common,
        "row_type": "event_market_no_send_source_cache",
        "rows": [
            {
                "coin_id": f"fixture-{index}",
                "symbol": f"F{index}",
                "observed_at": observed_at,
                "research_only": True,
            }
            for index in range(selected_count)
        ],
    })
    source_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    ledger_path = directory / "event_market_no_send_request_ledger.json"
    ledger = {
        **common,
        "row_type": "event_market_no_send_request_ledger",
        "live_provider_authorized": True,
        "fixture_mode": False,
        "provider_source_artifact": source_path.name,
        "provider_source_artifact_sha256": source_digest,
        "cache_status": "write_through",
    }
    if not legacy:
        ledger.update({
            "endpoint_path": "/coins/markets",
            "request_started_at": observed_at,
            "request_ended_at": observed_at,
            "duration_ms": 0,
            "http_status": 200,
            "result_count": raw_count,
            "retry_count": 0,
            "error_class": None,
            "cache_behavior": "network",
        })
    market_no_send_io.write_json_atomic(ledger_path, ledger)
    ledger_digest = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    provenance = {
        "schema_version": "crypto_radar_market_provenance_v2",
        "contract_version": 2,
        "data_acquisition_mode": "live_provider",
        "candidate_source_mode": "live_no_send",
        "provider": "coingecko",
        "provider_call_attempted": True,
        "provider_call_succeeded": True,
        "live_provider_authorized": True,
        "request_ledger_path": ledger_path.name,
        "request_ledger_sha256": ledger_digest,
        "provider_source_artifact": source_path.name,
        "provider_source_artifact_sha256": source_digest,
        "provider_generation_id": run_id,
        "cache_status": "write_through",
        "provenance_contract_valid": True,
        "burn_in_eligible": legacy,
        "burn_in_counted": legacy,
        "burn_in_reason": common["burn_in_reason"],
        "feature_basis": {"returns": "provider_observed"},
        "data_quality": {
            "direct_feature_count": (
                selected_count
                if direct_feature_count is None
                else direct_feature_count
            ),
            "proxy_feature_count": proxy_feature_count,
            "spread_available_count": 0,
            "baseline_status_counts": {"warming": selected_count},
            "baseline_warm_assets": 0,
            "baseline_warming_assets": selected_count,
            "observed_at": observed_at,
            "no_send": True,
            "research_only": True,
        },
        "validation_errors": [],
        **campaign,
    }
    materialized: list[dict[str, Any]] = []
    for source in candidates:
        row = dict(source)
        row.update({
            "artifact_namespace": namespace,
            "run_id": run_id,
            "profile": profile,
            "research_only": True,
            "notification_send_enabled": False,
            "paper_trade_created": False,
            "normal_rsi_signal_written": False,
            "triggered_fade_created": False,
            "market_provenance": provenance,
        })
        materialized.append(row)
    candidate_path = directory / "event_integrated_radar_candidates.jsonl"
    market_no_send_io.write_jsonl(candidate_path, materialized)
    candidate_raw = candidate_path.read_bytes()
    candidate_digest = hashlib.sha256(candidate_raw).hexdigest()
    core_path = directory / "event_core_opportunities.jsonl"
    outcome_path = directory / "event_integrated_radar_outcomes.jsonl"
    materialized_core = [dict(row) for row in core_rows]
    materialized_outcomes = [dict(row) for row in integrated_outcome_rows]
    market_no_send_io.write_jsonl(core_path, materialized_core)
    market_no_send_io.write_jsonl(outcome_path, materialized_outcomes)
    market_no_send_io.write_json_atomic(
        directory / "event_provider_health.json",
        {
            "schema_version": "event_provider_health_v1",
            "providers": {
                "market_universe:market_no_send": {
                    "provider": "coingecko",
                    "run_id": run_id,
                    "last_error_class": None,
                    "request_http_status": ledger.get("http_status"),
                    "request_result_count": ledger.get("result_count"),
                    "request_retry_count": ledger.get("retry_count"),
                    "no_send": True,
                    "research_only": True,
                }
            },
        },
    )
    manifest = {
        **common,
        "row_type": "event_market_no_send_generation",
        "status": "complete",
        "live_provider_authorized": True,
        "fixture_mode": False,
        "pointer_published": False,
        "candidate_count": len(materialized),
        "candidate_artifact": candidate_path.name,
        "candidate_artifact_sha256": candidate_digest,
        "core_artifact": core_path.name,
        "core_artifact_sha256": hashlib.sha256(core_path.read_bytes()).hexdigest(),
        "core_artifact_row_count": len(materialized_core),
        "integrated_outcome_artifact": outcome_path.name,
        "integrated_outcome_artifact_sha256": hashlib.sha256(outcome_path.read_bytes()).hexdigest(),
        "integrated_outcome_artifact_row_count": len(materialized_outcomes),
        "request_cache_artifact": source_path.name,
        "request_cache_sha256": source_digest,
        "request_ledger_artifact": ledger_path.name,
        "request_ledger_sha256": ledger_digest,
        "market_provenance": provenance,
    }
    manifest_path = directory / "event_market_no_send_generation.json"
    market_no_send_io.write_json_atomic(manifest_path, manifest)
    if legacy:
        for field in (
            "candidate_artifact", "candidate_artifact_sha256",
            "core_artifact", "core_artifact_sha256", "core_artifact_row_count",
            "integrated_outcome_artifact", "integrated_outcome_artifact_sha256",
            "integrated_outcome_artifact_row_count",
        ):
            manifest.pop(field, None)
        market_no_send_io.write_json_atomic(manifest_path, manifest)
        market_no_send_io.write_json_atomic(
            directory / "event_alpha_operator_state.json",
            {
                "artifact_namespace": namespace,
                "run_id": run_id,
                "profile": profile,
                "run_mode": run_mode,
                "market_no_send_provenance": provenance,
                "artifacts": {
                    "integrated_candidates": {
                        "status": "current", "path": candidate_path.name,
                        "run_id": run_id, "count": len(materialized),
                        "item_count": len(materialized),
                        "size_bytes": len(candidate_raw), "sha256": candidate_digest,
                    },
                    "core_opportunities": _operator_jsonl_binding(
                        core_path, run_id=run_id, count=len(materialized_core)
                    ),
                    "integrated_outcomes": _operator_jsonl_binding(
                        outcome_path, run_id=run_id, count=len(materialized_outcomes)
                    ),
                },
            },
        )
    return manifest_path, manifest, materialized


def _operator_jsonl_binding(path: Path, *, run_id: str, count: int) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "status": "current",
        "path": path.name,
        "run_id": run_id,
        "count": count,
        "item_count": count,
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
