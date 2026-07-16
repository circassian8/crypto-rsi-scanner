"""Pure point-in-time Decision-v2 replay kernel.

The kernel consumes already-normalized historical observations.  It performs
no I/O, provider calls, authorization inspection, publication, or production
mutation.  Every historical idea is evaluated by the production Decision-v2
function and then closed through the canonical projection used by current
operator artifacts.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from ..radar import market_anomaly_scanner
from ..radar.decision_model import reevaluate_radar_decision_fields
from ..radar.decision_model_surfaces import DECISION_MODEL_FIELD_NAMES, decision_model_values
from ..radar.decision_models import RadarDecisionConfig
from . import empirical_validation_protocol


SCHEMA_ID = "decision_radar.empirical_replay_idea"
SCHEMA_VERSION = 1
TRACE_SCHEMA_ID = "decision_radar.empirical_replay_trace_summary"
TRACE_SCHEMA_VERSION = 1
_VISIBLE_ROUTES = {
    "high_confidence_watch",
    "actionable_watch",
    "rapid_market_anomaly",
    "dashboard_watch",
    "fade_exhaustion_review",
    "risk_watch",
    "calendar_risk",
}


@dataclass(frozen=True)
class ReplayKernelResult:
    ideas: tuple[dict[str, Any], ...]
    trace_rows: tuple[dict[str, Any], ...]
    trace_summary: dict[str, Any]


def run_replay_kernel(
    observations: Iterable[Mapping[str, Any]],
    *,
    mode: str,
    artifact_namespace: str,
    allowed_partitions: Iterable[str],
    protocol: Mapping[str, Any] | None = None,
    decision_config: RadarDecisionConfig | None = None,
) -> ReplayKernelResult:
    """Evaluate normalized observations without future or external context.

    ``observations`` must already contain only feature values knowable at the
    declared ``observed_at``.  The kernel deliberately ignores any outcome or
    future-prefixed fields supplied by a caller.
    """

    frozen = dict(protocol or empirical_validation_protocol.protocol_values())
    errors = empirical_validation_protocol.validate_protocol(frozen)
    if errors:
        raise ValueError("empirical replay protocol invalid: " + ";".join(errors))
    permitted = frozenset(str(value) for value in allowed_partitions)
    known = {str(row["name"]) for row in frozen["partitions"]}
    if mode == "fixture":
        known.add("fixture")
    if not permitted or not permitted <= known:
        raise ValueError("allowed replay partitions invalid")
    if "final_test" in permitted and mode != "final_test":
        raise ValueError("final_test requires the sealed final_test run mode")

    cfg = decision_config or RadarDecisionConfig()
    ideas: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    for raw in sorted(
        (dict(row) for row in observations if isinstance(row, Mapping)),
        key=lambda row: (str(row.get("observed_at") or ""), str(row.get("symbol") or "")),
    ):
        trace, idea = _evaluate_observation(
            raw,
            protocol=frozen,
            mode=mode,
            artifact_namespace=artifact_namespace,
            allowed_partitions=permitted,
            decision_config=cfg,
        )
        traces.append(trace)
        if idea is not None:
            ideas.append(idea)
    summary = _trace_summary(
        traces,
        ideas,
        mode=mode,
        artifact_namespace=artifact_namespace,
        protocol=frozen,
    )
    return ReplayKernelResult(tuple(ideas), tuple(traces), summary)


def _evaluate_observation(
    row: dict[str, Any],
    *,
    protocol: Mapping[str, Any],
    mode: str,
    artifact_namespace: str,
    allowed_partitions: frozenset[str],
    decision_config: RadarDecisionConfig,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    observed_at = _required_utc(row.get("observed_at"))
    partition = "fixture" if mode == "fixture" else partition_for_timestamp(observed_at, protocol)
    symbol = str(row.get("symbol") or "").strip().upper()
    canonical = str(row.get("canonical_asset_id") or symbol).strip().casefold()
    base = {
        "schema_id": "decision_radar.empirical_replay_trace",
        "schema_version": 1,
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": empirical_validation_protocol.protocol_sha256(protocol),
        "mode": mode,
        "partition": partition,
        "observed_at": observed_at.isoformat(),
        "symbol": symbol,
        "canonical_asset_id": canonical,
        "point_in_time_universe_member": row.get("point_in_time_universe_member") is True,
        "point_in_time_volume_rank": _finite(row.get("point_in_time_volume_rank")),
        "baseline_status": str(row.get("baseline_status") or "missing"),
        "market_regime": str(row.get("market_regime") or "unknown"),
        "liquidity_tier": str(row.get("liquidity_tier") or "unknown"),
        "liquidity_usd": _finite(row.get("liquidity_usd")),
        "data_quality_mode": str(row.get("data_quality_mode") or "missing"),
        "feature_basis": _mapping(row.get("feature_basis")),
        "missing_features": _strings(row.get("missing_features")),
        "research_only": True,
    }
    if partition not in allowed_partitions:
        return {**base, "trace_status": "excluded", "failure_stage": "outside_selected_partition"}, None
    if not symbol or not canonical:
        return {**base, "trace_status": "rejected", "failure_stage": "identity_failure"}, None
    if row.get("point_in_time_universe_member") is not True:
        return {**base, "trace_status": "excluded", "failure_stage": "universe_exclusion"}, None
    if str(row.get("baseline_status") or "") != "warm":
        return {**base, "trace_status": "rejected", "failure_stage": "insufficient_history"}, None

    snapshot = _market_snapshot(row, observed_at=observed_at)
    anomaly_type = market_anomaly_scanner.classify_market_state(snapshot, row)
    anomaly_bucket = _anomaly_bucket(anomaly_type, row)
    if anomaly_type == market_anomaly_scanner.NO_REACTION:
        return {
            **base,
            "trace_status": "no_idea",
            "failure_stage": "no_anomaly_generated",
            "anomaly_type": anomaly_type,
            "market_snapshot": snapshot,
        }, None

    candidate = _candidate(
        row,
        snapshot=snapshot,
        anomaly_type=anomaly_type,
        anomaly_bucket=anomaly_bucket,
        partition=partition,
        mode=mode,
        artifact_namespace=artifact_namespace,
        protocol=protocol,
        observed_at=observed_at,
    )
    evaluated = {
        **candidate,
        **reevaluate_radar_decision_fields(candidate, cfg=decision_config),
    }
    projection = decision_model_values(evaluated)
    if not projection or decision_model_values(projection) != projection:
        return {
            **base,
            "trace_status": "rejected",
            "failure_stage": "canonical_projection_invalid",
            "anomaly_type": anomaly_type,
        }, None
    idea = dict(evaluated)
    idea["decision_projection"] = projection
    idea["replay_partition"] = partition
    idea["replay_mode"] = mode
    idea["replay_protocol_version"] = protocol["protocol_version"]
    idea["replay_protocol_sha256"] = empirical_validation_protocol.protocol_sha256(protocol)
    idea["operator_visible"] = str(projection.get("radar_route")) in _VISIBLE_ROUTES
    idea["replay_feature_quality"] = {
        "source_mode": str(row.get("source_mode") or mode),
        "market_data_basis": str(row.get("market_data_basis") or "historical_ohlcv"),
        "volume_anomaly_basis": str(row.get("volume_anomaly_basis") or "historical_ohlcv"),
        "liquidity_basis": str(row.get("liquidity_basis") or "historical_ohlcv"),
        "spread_basis": str(row.get("spread_basis") or "unavailable"),
        "baseline_maturity": str(row.get("baseline_status") or "missing"),
        "catalyst_evidence_timing": str(row.get("catalyst_evidence_timing") or "missing"),
        "calendar_evidence_timing": str(row.get("calendar_evidence_timing") or "missing"),
        "rsi_context_timing": str(row.get("rsi_context_timing") or "temporal_direct"),
        "feature_basis": _mapping(row.get("feature_basis")),
        "missing_features": _strings(row.get("missing_features")),
        "direct_proxy_class": str(row.get("direct_proxy_class") or "temporal_direct"),
    }
    trace = {
        **base,
        "trace_status": "idea",
        "failure_stage": None,
        "candidate_id": idea["candidate_id"],
        "anomaly_type": anomaly_type,
        "anomaly_bucket": anomaly_bucket,
        "radar_route": projection["radar_route"],
        "operator_visible": idea["operator_visible"],
        "actionability_score": projection["actionability_score"],
        "evidence_confidence_score": projection["evidence_confidence_score"],
        "risk_score": projection["risk_score"],
        "urgency_score": projection["urgency_score"],
        "chase_risk_score": projection["chase_risk_score"],
        "directional_bias": projection["directional_bias"],
        "hard_blockers": list(projection["hard_blockers"]),
        "market_snapshot": snapshot,
    }
    return trace, idea


def _market_snapshot(row: Mapping[str, Any], *, observed_at: datetime) -> dict[str, Any]:
    return_fields = (
        "return_24h",
        "return_72h",
        "return_7d",
        "relative_return_vs_btc_24h",
        "relative_return_vs_eth_24h",
    )
    values = {
        field: value
        for field in return_fields
        if (value := _finite(row.get(field))) is not None
    }
    units = {field: "percent_points" for field in values}
    quality = {
        "baseline_status": str(row.get("baseline_status") or "missing"),
        "direct_feature_count": int(row.get("direct_feature_count") or 0),
        "proxy_feature_count": int(row.get("proxy_feature_count") or 0),
        "spread_available": False,
        "spread_basis": "unavailable",
        "liquidity_basis": str(row.get("liquidity_basis") or "historical_ohlcv_trailing_quote_volume"),
        "volume_zscore_basis": str(row.get("volume_zscore_basis") or "historical_ohlcv_prior_90d"),
        "research_only": True,
    }
    snapshot = {
        "symbol": str(row.get("symbol") or "").upper(),
        "coin_id": str(row.get("canonical_asset_id") or row.get("symbol") or "").casefold(),
        "canonical_asset_id": str(row.get("canonical_asset_id") or row.get("symbol") or "").casefold(),
        "observed_at": observed_at.isoformat(),
        "price": _finite(row.get("close")),
        **values,
        "return_unit": "percent_points",
        "return_units": units,
        "source_return_unit": "percent_points",
        "source_return_units": units,
        "threshold_unit": "percent_points",
        "volume_24h": _finite(row.get("quote_volume")),
        "volume_zscore_24h": _finite(row.get("volume_zscore_24h")),
        "liquidity_usd": _finite(row.get("liquidity_usd")),
        "liquidity_tier": str(row.get("liquidity_tier") or "unknown"),
        "spread_status": "unavailable",
        "freshness_status": "fresh",
        "market_context_freshness_status": "fresh",
        "market_data_source": str(row.get("market_data_source") or "binance_historical_ohlcv"),
        "market_data_quality": quality,
        "data_quality": quality,
        "unit_warnings": [],
    }
    return snapshot


def _candidate(
    row: Mapping[str, Any],
    *,
    snapshot: Mapping[str, Any],
    anomaly_type: str,
    anomaly_bucket: str,
    partition: str,
    mode: str,
    artifact_namespace: str,
    protocol: Mapping[str, Any],
    observed_at: datetime,
) -> dict[str, Any]:
    symbol = str(row["symbol"]).upper()
    canonical = str(row.get("canonical_asset_id") or symbol).casefold()
    digest = hashlib.sha256(
        f"{protocol['protocol_version']}|{mode}|{canonical}|{observed_at.isoformat()}|{anomaly_type}".encode()
    ).hexdigest()[:20]
    candidate_id = f"empirical:{digest}"
    run_id = f"{protocol['protocol_version']}|{mode}|{partition}"
    provider = str(row.get("market_data_source") or "binance_historical_ohlcv")
    candidate = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": candidate_id,
        "candidate_family_id": f"{canonical}|{anomaly_type}",
        "core_opportunity_id": f"empirical-core:{digest}",
        "incident_id": f"empirical-incident:{digest}",
        "market_anomaly_id": f"empirical-anomaly:{digest}",
        "symbol": symbol,
        "validated_symbol": symbol,
        "coin_id": canonical,
        "validated_coin_id": canonical,
        "canonical_asset_id": canonical,
        "instrument_resolver_status": "resolved",
        "instrument_resolver_confidence": 1.0,
        "instrument_resolver_match_reason": "historical_symbol_exact",
        "instrument_identity_trusted": True,
        "is_tradable_asset": True,
        "is_quote_asset": False,
        "quote_asset_excluded": False,
        "is_theme_or_sector": False,
        "source_origin": "market_anomaly",
        "source_origins": ["market_anomaly"],
        "source_pack": "integrated_radar_pack",
        "source_packs": ["integrated_radar_pack"],
        "source_class": "market_data",
        "source_provider": provider,
        "provider": provider,
        "anomaly_type": anomaly_type,
        "market_state_class": anomaly_type,
        "market_state": anomaly_type,
        "market_anomaly_bucket": anomaly_bucket,
        "anomaly_bucket": anomaly_bucket,
        "market_snapshot": dict(snapshot),
        "latest_market_snapshot": dict(snapshot),
        "market_state_snapshot": dict(snapshot),
        "market_context_source": provider,
        "market_context_observed_at": observed_at.isoformat(),
        "market_context_freshness_status": "fresh",
        "market_data_freshness": "fresh",
        "market_snapshot_id": f"empirical-market:{digest}",
        "observed_at": observed_at.isoformat(),
        "created_at": observed_at.isoformat(),
        "decision_evaluated_at": observed_at.isoformat(),
        "run_mode": "fixture" if mode == "fixture" else "replay",
        "data_mode": "fixture" if mode == "fixture" else "replay",
        "profile": "empirical_validation",
        "artifact_namespace": artifact_namespace,
        "run_id": run_id,
        "provider_generation_id": hashlib.sha256(run_id.encode()).hexdigest()[:16],
        "research_only": True,
        "notification_send_enabled": False,
        "paper_trade_created": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "decision_source_side_effect_safety_failed": False,
        "decision_source_secret_safety_failed": False,
        "decision_source_path_safety_failed": False,
        "source_independence": {},
        "source_independence_status": "unassessed",
        "source_independence_errors": [],
        "independent_source_count": 0,
        "independent_corroboration_count": 0,
        "source_content_cluster_count": 0,
        "replay_partition": partition,
        "replay_data_quality_mode": str(row.get("data_quality_mode") or "historical_ohlcv"),
        "market_regime": str(row.get("market_regime") or "unknown"),
        "liquidity_tier": str(row.get("liquidity_tier") or "unknown"),
        "point_in_time_volume_rank": _finite(row.get("point_in_time_volume_rank")),
        "point_in_time_universe_member": True,
    }
    for field in ("rsi_context", "rsi_context_references"):
        if row.get(field) not in (None, "", [], {}):
            candidate[field] = row[field]
    return candidate


def partition_for_timestamp(value: datetime | str, protocol: Mapping[str, Any] | None = None) -> str:
    frozen = dict(protocol or empirical_validation_protocol.protocol_values())
    observed = _required_utc(value)
    for row in frozen["partitions"]:
        if _required_utc(row["start_inclusive"]) <= observed < _required_utc(row["end_exclusive"]):
            return str(row["name"])
    return "outside_protocol_window"


def _anomaly_bucket(anomaly_type: str, row: Mapping[str, Any]) -> str:
    if anomaly_type == market_anomaly_scanner.SUSPICIOUS_ILLIQUID_MOVE:
        return market_anomaly_scanner.LOW_LIQUIDITY_SUSPICIOUS
    if anomaly_type == market_anomaly_scanner.CONFIRMED_BREAKOUT:
        return market_anomaly_scanner.HIGH_LIQUIDITY_BREAKOUT
    if anomaly_type in {
        market_anomaly_scanner.LATE_MOMENTUM,
        market_anomaly_scanner.BLOWOFF_CROWDED,
        market_anomaly_scanner.POST_EVENT_FADE_SETUP,
    }:
        return market_anomaly_scanner.LATE_MOMENTUM_NEEDS_CROWDING_CHECK
    if anomaly_type == market_anomaly_scanner.RISK_OFF_SELL_PRESSURE:
        return market_anomaly_scanner.SELLOFF_RISK
    return str(row.get("anomaly_bucket") or market_anomaly_scanner.NEEDS_CATALYST_SEARCH)


def _trace_summary(
    traces: list[Mapping[str, Any]],
    ideas: list[Mapping[str, Any]],
    *,
    mode: str,
    artifact_namespace: str,
    protocol: Mapping[str, Any],
) -> dict[str, Any]:
    statuses = Counter(str(row.get("trace_status") or "unknown") for row in traces)
    failures = Counter(str(row.get("failure_stage") or "none") for row in traces)
    routes = Counter(str(row.get("radar_route") or "diagnostic") for row in ideas)
    partitions = Counter(str(row.get("replay_partition") or "unknown") for row in ideas)
    return {
        "schema_id": TRACE_SCHEMA_ID,
        "schema_version": TRACE_SCHEMA_VERSION,
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": empirical_validation_protocol.protocol_sha256(protocol),
        "mode": mode,
        "artifact_namespace": artifact_namespace,
        "observation_count": len(traces),
        "idea_count": len(ideas),
        "operator_visible_idea_count": sum(1 for row in ideas if row.get("operator_visible") is True),
        "trace_status_counts": dict(sorted(statuses.items())),
        "failure_stage_counts": dict(sorted(failures.items())),
        "route_counts": dict(sorted(routes.items())),
        "partition_counts": dict(sorted(partitions.items())),
        "research_only": True,
        "auto_apply": False,
        "provider_calls": 0,
        "authorization_mutations": 0,
        "telegram_sends": 0,
        "trades": 0,
        "orders": 0,
        "event_alpha_paper_trades": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
        "dashboard_authority_mutations": 0,
    }


def canonical_idea_bytes(idea: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(idea), sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def _required_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("observation timestamp required")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observation timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _finite(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _strings(value: Any) -> list[str]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, Mapping)):
        return []
    return list(dict.fromkeys(str(item) for item in value if str(item).strip()))


__all__ = [
    "ReplayKernelResult",
    "canonical_idea_bytes",
    "partition_for_timestamp",
    "run_replay_kernel",
]
