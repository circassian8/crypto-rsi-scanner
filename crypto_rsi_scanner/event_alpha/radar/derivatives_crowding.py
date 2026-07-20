"""Derivatives crowding and fade-review artifacts for Event Alpha research.

This module normalizes fixture or explicitly configured derivatives payloads
into local research artifacts. It is intentionally artifact-only: it does not
send notifications, open paper trades, write normal RSI rows, execute orders, or
create ``TRIGGERED_FADE``.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import crypto_rsi_scanner.event_alpha.radar.market_reaction as event_market_reaction
from ..artifacts import schema_v1
from ...event_providers.manual_json import parse_datetime


DERIVATIVES_STATE_FILENAME = "event_derivatives_state.jsonl"
DERIVATIVES_CROWDING_CANDIDATES_FILENAME = "event_derivatives_crowding_candidates.jsonl"
DERIVATIVES_CROWDING_REPORT_FILENAME = "event_derivatives_crowding_report.md"
FADE_SHORT_REVIEW_CANDIDATES_FILENAME = "event_fade_short_review_candidates.jsonl"

FADE_REVIEW_LANE = "FADE_SHORT_REVIEW"
RESEARCH_DISCLAIMER = "Research-only. Not a trade signal."
METRIC_STATUS_IMPLEMENTED = "implemented"
METRIC_STATUS_NOT_IMPLEMENTED = "not_implemented"
METRIC_STATUS_PROVIDER_UNAVAILABLE = "provider_unavailable"
METRIC_STATUS_FIXTURE_ONLY = "fixture_only"
METRIC_STATUS_MISSING_FROM_RESPONSE = "missing_from_response"
SUPPORTED_METRIC_STATUSES = (
    METRIC_STATUS_IMPLEMENTED,
    METRIC_STATUS_NOT_IMPLEMENTED,
    METRIC_STATUS_PROVIDER_UNAVAILABLE,
    METRIC_STATUS_FIXTURE_ONLY,
    METRIC_STATUS_MISSING_FROM_RESPONSE,
)
DERIVATIVES_SUPPORTED_METRICS = (
    "open_interest",
    "funding_rate",
    "predicted_funding",
    "liquidations",
    "long_short_ratio",
    "basis",
    "perp_volume",
)
DERIVATIVES_LIVE_METRIC_IMPLEMENTATION_STATUS = {
    "open_interest": METRIC_STATUS_IMPLEMENTED,
    "funding_rate": METRIC_STATUS_IMPLEMENTED,
    "predicted_funding": METRIC_STATUS_IMPLEMENTED,
    "liquidations": METRIC_STATUS_IMPLEMENTED,
    "long_short_ratio": METRIC_STATUS_IMPLEMENTED,
    "basis": METRIC_STATUS_FIXTURE_ONLY,
    "perp_volume": METRIC_STATUS_IMPLEMENTED,
}


@dataclass(frozen=True)
class DerivativesCrowdingScanResult:
    namespace_dir: Path
    derivatives_state_path: Path
    derivatives_candidates_path: Path
    fade_review_candidates_path: Path
    report_path: Path
    derivatives_state_count: int
    evaluated_candidate_count: int
    fade_review_candidate_count: int
    derivatives_state_rows: tuple[dict[str, Any], ...]
    candidate_rows: tuple[dict[str, Any], ...]
    fade_review_candidates: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _DerivativesMetricValues:
    long_liq: float | None
    short_liq: float | None
    liquidation_imbalance: float | None
    perp_volume: float | None
    spot_volume: float | None
    perp_spot_ratio: float | None
    funding: float | None
    predicted_funding: float | None
    funding_z: float | None
    open_interest: float | None
    open_interest_delta_1h: float | None
    open_interest_delta_4h: float | None
    open_interest_delta_24h: float | None
    futures_return_24h: float | None
    futures_return_4h: float | None
    long_short_ratio: float | None
    basis: float | None


def run_derivatives_crowding_scan(
    *,
    namespace_dir: str | Path,
    derivatives_path: str | Path | None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
    observed_at: datetime | str | None = None,
) -> DerivativesCrowdingScanResult:
    """Normalize derivatives state and write research-only fade-review artifacts."""
    directory = Path(namespace_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    observed = _as_utc(_parse_time(observed_at) or datetime.now(timezone.utc))
    warnings: list[str] = []
    state_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []

    if derivatives_path is None:
        warnings.append("derivatives:not_configured")
    else:
        payload = _load_payload(derivatives_path)
        raw_state_rows = _payload_rows(payload, "derivatives", "snapshots", "data")
        raw_candidates = _payload_rows(payload, "candidates")
        if not raw_state_rows:
            warnings.append("derivatives:no_fixture_rows")
        for row in raw_state_rows:
            state_rows.append(
                normalize_derivatives_state(
                    row,
                    observed_at=observed,
                    profile=profile,
                    artifact_namespace=artifact_namespace,
                    run_mode=run_mode,
                    run_id=run_id,
                )
            )
        state_by_key = _state_index(state_rows)
        if not raw_candidates:
            warnings.append("fade_review_candidates:no_fixture_rows")
        for item in raw_candidates:
            state = _lookup_state_for_candidate(item, state_by_key)
            candidate_rows.append(
                evaluate_derivatives_fade_candidate(
                    item,
                    derivatives_state=state,
                    observed_at=observed,
                    profile=profile,
                    artifact_namespace=artifact_namespace,
                    run_mode=run_mode,
                    run_id=run_id,
                )
            )

    fade_rows = [row for row in candidate_rows if row.get("opportunity_type") == FADE_REVIEW_LANE]
    state_path = directory / DERIVATIVES_STATE_FILENAME
    candidates_path = directory / DERIVATIVES_CROWDING_CANDIDATES_FILENAME
    fade_path = directory / FADE_SHORT_REVIEW_CANDIDATES_FILENAME
    report_path = directory / DERIVATIVES_CROWDING_REPORT_FILENAME
    _write_jsonl(state_path, state_rows)
    _write_jsonl(candidates_path, candidate_rows)
    _write_jsonl(fade_path, fade_rows)
    report_path.write_text(
        format_derivatives_crowding_report(
            state_rows=state_rows,
            candidate_rows=candidate_rows,
            profile=profile,
            artifact_namespace=artifact_namespace,
            warnings=warnings,
        ),
        encoding="utf-8",
    )
    return DerivativesCrowdingScanResult(
        namespace_dir=directory,
        derivatives_state_path=state_path,
        derivatives_candidates_path=candidates_path,
        fade_review_candidates_path=fade_path,
        report_path=report_path,
        derivatives_state_count=len(state_rows),
        evaluated_candidate_count=len(candidate_rows),
        fade_review_candidate_count=len(fade_rows),
        derivatives_state_rows=tuple(state_rows),
        candidate_rows=tuple(candidate_rows),
        fade_review_candidates=tuple(fade_rows),
        warnings=tuple(warnings),
    )


def run_derivatives_crowding_scan_from_state_rows(
    *,
    namespace_dir: str | Path,
    state_rows: Iterable[Mapping[str, Any]],
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
    observed_at: datetime | str | None = None,
    no_send_rehearsal: bool = False,
    warnings: Iterable[str] = (),
) -> DerivativesCrowdingScanResult:
    """Evaluate already-normalized derivatives state into research candidates."""
    directory = Path(namespace_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    observed = _as_utc(_parse_time(observed_at) or datetime.now(timezone.utc))
    states = [dict(row) for row in state_rows if isinstance(row, Mapping)]
    candidate_rows: list[dict[str, Any]] = []
    for state in states:
        candidate = evaluate_derivatives_fade_candidate(
            _candidate_from_derivatives_state(state, observed_at=observed),
            derivatives_state=state,
            observed_at=observed,
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_mode=run_mode,
            run_id=run_id,
        )
        candidate["research_only"] = True
        candidate["no_send_rehearsal"] = bool(no_send_rehearsal)
        for lineage_key in (
            "provider_generation_id",
            "provider_request_succeeded",
            "provider_source_artifact",
            "request_ledger_path",
        ):
            if state.get(lineage_key) not in (None, ""):
                candidate[lineage_key] = state.get(lineage_key)
        candidate["strict_alerts_created"] = 0
        candidate["telegram_sends"] = 0
        candidate["trades_created"] = 0
        candidate["paper_trades_created"] = 0
        candidate["normal_rsi_signal_rows_written"] = 0
        candidate["triggered_fade_created"] = False
        candidate_rows.append(candidate)

    fade_rows = [row for row in candidate_rows if row.get("opportunity_type") == FADE_REVIEW_LANE]
    state_path = directory / DERIVATIVES_STATE_FILENAME
    candidates_path = directory / DERIVATIVES_CROWDING_CANDIDATES_FILENAME
    fade_path = directory / FADE_SHORT_REVIEW_CANDIDATES_FILENAME
    report_path = directory / DERIVATIVES_CROWDING_REPORT_FILENAME
    _write_jsonl(state_path, states)
    _write_jsonl(candidates_path, candidate_rows)
    _write_jsonl(fade_path, fade_rows)
    report_path.write_text(
        format_derivatives_crowding_report(
            state_rows=states,
            candidate_rows=candidate_rows,
            profile=profile,
            artifact_namespace=artifact_namespace,
            warnings=warnings,
        ),
        encoding="utf-8",
    )
    return DerivativesCrowdingScanResult(
        namespace_dir=directory,
        derivatives_state_path=state_path,
        derivatives_candidates_path=candidates_path,
        fade_review_candidates_path=fade_path,
        report_path=report_path,
        derivatives_state_count=len(states),
        evaluated_candidate_count=len(candidate_rows),
        fade_review_candidate_count=len(fade_rows),
        derivatives_state_rows=tuple(states),
        candidate_rows=tuple(candidate_rows),
        fade_review_candidates=tuple(fade_rows),
        warnings=tuple(warnings),
    )


def normalize_derivatives_state(
    row: Mapping[str, Any],
    *,
    observed_at: datetime | str | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Return one normalized derivatives-state snapshot."""
    observed = _as_utc(_parse_time(observed_at) or datetime.now(timezone.utc))
    timestamp = _parse_time(_first(row, "observed_at", "timestamp", "time", "created_at", "updated_at"))
    source_timestamp = _as_utc(timestamp) if timestamp else None
    observed_source = source_timestamp or observed
    explicit_freshness = _explicit_freshness_status(row)
    symbol = _base_symbol(row)
    coin_id = _text(_first(row, "coin_id", "id", "asset_id"))
    values = _derivatives_metric_values(row)
    freshness = _derivatives_freshness_fields(
        row,
        observed_at=observed,
        fallback_timestamp=source_timestamp,
        fallback_status=explicit_freshness,
        values=values,
    )
    derivatives_snapshot_freshness = _combined_freshness_status(
        freshness["open_interest_freshness"],
        freshness["funding_freshness"],
        freshness["liquidation_freshness"],
        freshness["long_short_freshness"],
        freshness["basis_freshness"],
    )
    metric_values = _derivatives_metric_presence(values)
    supported_metric_status = _supported_metric_status(metric_values, provider_unavailable=bool(row.get("provider_unavailable")))
    open_interest_unit = _unit(row, "open_interest_unit", default="usd_notional")
    funding_rate_unit = _unit(row, "funding_rate_unit", default="decimal_rate")
    basis_unit = _unit(row, "basis_unit", default="decimal_rate")
    liquidation_unit = _unit(row, "liquidation_unit", default="usd_notional")
    volume_unit = _unit(row, "volume_unit", default="provider_native")
    warnings = _derivatives_warnings(
        timestamp=observed_source,
        observed_at=observed,
        funding_rate=values.funding,
        open_interest=values.open_interest,
    )
    return {
        "schema_version": 1,
        "row_type": "derivatives_state_snapshot",
        "profile": profile,
        "artifact_namespace": artifact_namespace,
        "run_mode": run_mode,
        "run_id": run_id,
        "derivatives_state_id": f"deriv:{coin_id or symbol or 'unknown'}:{_digest(str(row.get('symbol') or row.get('market_symbol') or symbol) + '|' + observed_source.isoformat())}",
        "symbol": symbol,
        "coin_id": coin_id or None,
        "observed_at": observed_source.isoformat(),
        "provider": _text(_first(row, "provider")) or "coinalyze",
        "market": _text(_first(row, "market", "market_symbol", "symbol")) or None,
        "exchange": _text(_first(row, "exchange")) or None,
        "open_interest": values.open_interest,
        "open_interest_delta_1h": values.open_interest_delta_1h,
        "open_interest_delta_4h": values.open_interest_delta_4h,
        "open_interest_delta_24h": values.open_interest_delta_24h,
        "funding_rate": values.funding,
        "predicted_funding_rate": values.predicted_funding,
        "funding_zscore": values.funding_z,
        "futures_price_return_24h_pct": values.futures_return_24h,
        "futures_price_return_4h_pct": values.futures_return_4h,
        "liquidation_long_usd": values.long_liq,
        "liquidation_short_usd": values.short_liq,
        "liquidation_imbalance": values.liquidation_imbalance,
        "long_short_ratio": values.long_short_ratio,
        "basis": values.basis,
        "perp_volume": values.perp_volume,
        "spot_volume": values.spot_volume,
        "perp_spot_volume_ratio": values.perp_spot_ratio,
        "supported_metric_status": supported_metric_status,
        "implemented_metrics": tuple(metric for metric, status in supported_metric_status.items() if status == METRIC_STATUS_IMPLEMENTED and metric_values.get(metric)),
        "fixture_only_metrics": tuple(metric for metric, status in supported_metric_status.items() if status == METRIC_STATUS_FIXTURE_ONLY and metric_values.get(metric)),
        "missing_metrics": tuple(metric for metric, status in supported_metric_status.items() if status in {METRIC_STATUS_MISSING_FROM_RESPONSE, METRIC_STATUS_NOT_IMPLEMENTED, METRIC_STATUS_PROVIDER_UNAVAILABLE}),
        "open_interest_freshness": freshness["open_interest_freshness"],
        "funding_freshness": freshness["funding_freshness"],
        "liquidation_freshness": freshness["liquidation_freshness"],
        "long_short_freshness": freshness["long_short_freshness"],
        "basis_freshness": freshness["basis_freshness"],
        "derivatives_snapshot_freshness_status": derivatives_snapshot_freshness,
        "freshness_status": derivatives_snapshot_freshness,
        "open_interest_unit": open_interest_unit,
        "funding_rate_unit": funding_rate_unit,
        "basis_unit": basis_unit,
        "liquidation_unit": liquidation_unit,
        "volume_unit": volume_unit,
        "unit_metadata": {
            "open_interest_unit": open_interest_unit,
            "funding_rate_unit": funding_rate_unit,
            "basis_unit": basis_unit,
            "liquidation_unit": liquidation_unit,
            "volume_unit": volume_unit,
        },
        "warnings": warnings,
        "raw_payload_redacted": _redacted_payload(row),
        "research_only": True,
        "created_alert": False,
        "notification_send_enabled": False,
    }


def _derivatives_metric_values(row: Mapping[str, Any]) -> _DerivativesMetricValues:
    long_liq = _float(_first(row, "liquidation_long_usd", "long_liquidations_usd", "long_liquidations", "liquidations_long"))
    short_liq = _float(_first(row, "liquidation_short_usd", "short_liquidations_usd", "short_liquidations", "liquidations_short"))
    liquidation_imbalance = _float(_first(row, "liquidation_imbalance", "long_liquidation_imbalance", "liquidation_skew"))
    if liquidation_imbalance is None:
        liquidation_imbalance = _liquidation_imbalance(long_liq, short_liq)
    perp_volume = _float(_first(row, "perp_volume", "futures_volume_24h", "volume_24h"))
    spot_volume = _float(_first(row, "spot_volume", "spot_volume_24h"))
    perp_spot_ratio = _float(_first(row, "perp_spot_volume_ratio"))
    if perp_spot_ratio is None and perp_volume is not None and spot_volume and spot_volume > 0:
        perp_spot_ratio = perp_volume / spot_volume
    return _DerivativesMetricValues(
        long_liq=long_liq,
        short_liq=short_liq,
        liquidation_imbalance=liquidation_imbalance,
        perp_volume=perp_volume,
        spot_volume=spot_volume,
        perp_spot_ratio=perp_spot_ratio,
        funding=_float(_first(row, "funding_rate", "funding_rate_8h", "funding")),
        predicted_funding=_float(_first(row, "predicted_funding_rate", "predicted_funding")),
        funding_z=_float(_first(row, "funding_zscore", "funding_rate_zscore")),
        open_interest=_float(_first(row, "open_interest", "oi")),
        open_interest_delta_1h=_pct(_first(row, "open_interest_delta_1h", "oi_delta_1h", "open_interest_1h_change_pct")),
        open_interest_delta_4h=_pct(_first(row, "open_interest_delta_4h", "oi_delta_4h", "open_interest_4h_change_pct")),
        open_interest_delta_24h=_pct(_first(row, "open_interest_delta_24h", "open_interest_24h_change_pct", "oi_24h_change_pct", "open_interest_change_24h")),
        futures_return_24h=_pct(_first(row, "futures_price_return_24h_pct", "futures_price_24h_change_pct", "price_return_24h", "return_24h", "price_change_24h")),
        futures_return_4h=_pct(_first(row, "futures_price_return_4h_pct", "futures_price_4h_change_pct", "price_return_4h", "return_4h", "price_change_4h")),
        long_short_ratio=_float(_first(row, "long_short_ratio")),
        basis=_float(_first(row, "basis")),
    )


def _derivatives_metric_presence(values: _DerivativesMetricValues) -> dict[str, bool]:
    return {
        "open_interest": (
            values.open_interest is not None
            or values.open_interest_delta_24h is not None
            or values.open_interest_delta_4h is not None
        ),
        "funding_rate": values.funding is not None,
        "predicted_funding": values.predicted_funding is not None,
        "liquidations": (
            values.long_liq is not None
            or values.short_liq is not None
            or values.liquidation_imbalance is not None
        ),
        "long_short_ratio": values.long_short_ratio is not None,
        "basis": values.basis is not None,
        "perp_volume": values.perp_volume is not None or values.perp_spot_ratio is not None,
    }


def _derivatives_freshness_fields(
    row: Mapping[str, Any],
    *,
    observed_at: datetime,
    fallback_timestamp: datetime | None,
    fallback_status: str | None,
    values: _DerivativesMetricValues,
) -> dict[str, str]:
    return {
        "open_interest_freshness": _metric_freshness(
            row,
            observed_at=observed_at,
            value_present=(
                values.open_interest is not None
                or values.open_interest_delta_24h is not None
                or values.open_interest_delta_4h is not None
            ),
            fallback_timestamp=fallback_timestamp,
            fallback_status=fallback_status,
            keys=("open_interest_timestamp", "open_interest_history_timestamp", "open_interest_observed_at"),
        ),
        "funding_freshness": _metric_freshness(
            row,
            observed_at=observed_at,
            value_present=values.funding is not None or values.predicted_funding is not None or values.funding_z is not None,
            fallback_timestamp=fallback_timestamp,
            fallback_status=fallback_status,
            keys=("funding_timestamp", "predicted_funding_timestamp", "funding_observed_at", "predicted_funding_observed_at"),
        ),
        "liquidation_freshness": _metric_freshness(
            row,
            observed_at=observed_at,
            value_present=values.long_liq is not None or values.short_liq is not None or values.liquidation_imbalance is not None,
            fallback_timestamp=fallback_timestamp,
            fallback_status=fallback_status,
            keys=("liquidation_timestamp", "liquidation_observed_at"),
        ),
        "long_short_freshness": _metric_freshness(
            row,
            observed_at=observed_at,
            value_present=values.long_short_ratio is not None,
            fallback_timestamp=fallback_timestamp,
            fallback_status=fallback_status,
            keys=("long_short_timestamp", "long_short_observed_at"),
        ),
        "basis_freshness": _metric_freshness(
            row,
            observed_at=observed_at,
            value_present=values.basis is not None,
            fallback_timestamp=fallback_timestamp,
            fallback_status=fallback_status,
            keys=("basis_timestamp", "basis_observed_at"),
        ),
    }


def evaluate_derivatives_fade_candidate(
    item: Mapping[str, Any],
    *,
    derivatives_state: Mapping[str, Any] | None = None,
    observed_at: datetime | str | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Evaluate one candidate for research-only fade/short-review metadata."""
    observed = _as_utc(_parse_time(observed_at) or datetime.now(timezone.utc))
    state = dict(derivatives_state or {})
    market_snapshot = _market_snapshot(item)
    derivatives_snapshot = _reaction_derivatives_snapshot(state)
    reaction = event_market_reaction.evaluate_market_reaction({
        "source_class": item.get("source_class"),
        "source_pack": item.get("source_pack"),
        "impact_path_type": item.get("impact_path_type") or item.get("playbook_type"),
        "playbook_type": item.get("playbook_type"),
        "evidence_quality_score": item.get("evidence_quality_score"),
        "accepted_evidence_count": item.get("accepted_evidence_count"),
        "accepted_evidence_reason_codes": item.get("accepted_evidence_reason_codes") or item.get("reason_codes"),
        "market_confirmation_level": item.get("market_confirmation_level"),
        "market_confirmation_score": item.get("market_confirmation_score"),
        "negative_catalyst": item.get("negative_catalyst"),
        "market_snapshot": market_snapshot,
        "derivatives_snapshot": derivatives_snapshot,
        "event_age_hours": item.get("event_age_hours") or market_snapshot.get("event_age_hours"),
    })
    completed_move = _completed_move(market_snapshot, reaction.market_state)
    crowding_evidence = _crowding_evidence(state)
    liquidity_sane = _liquidity_sane(market_snapshot)
    opportunity = reaction.opportunity_type
    warnings = list(reaction.warnings)
    if reaction.opportunity_type == event_market_reaction.EventOpportunityType.CONFIRMED_LONG_RESEARCH.value and crowding_evidence:
        warnings.append("confirmed_long_derivatives_crowding_warning")
    if not liquidity_sane and completed_move:
        opportunity = event_market_reaction.EventOpportunityType.RISK_ONLY.value
        warnings.append("suspicious_illiquid_move_not_fade_review")
    freshness_ok = _state_fresh_for_fade_review(state)
    if opportunity == FADE_REVIEW_LANE and not freshness_ok:
        warnings.append("fade_review_requires_fresh_derivatives_state")
    fade_ready = (
        opportunity == FADE_REVIEW_LANE
        and completed_move
        and bool(crowding_evidence)
        and liquidity_sane
        and freshness_ok
        and not _negative_without_crowding(item, state)
    )
    if opportunity == FADE_REVIEW_LANE and not fade_ready:
        opportunity = event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value
        warnings.append("fade_review_requires_completed_move_crowding_and_liquidity")
    symbol = _text(_first(item, "symbol", "validated_symbol")) or _text(state.get("symbol")) or "UNKNOWN"
    coin_id = _text(_first(item, "coin_id", "validated_coin_id")) or _text(state.get("coin_id")) or None
    row = {
        "schema_version": 1,
        "row_type": "fade_short_review_candidate",
        "profile": profile,
        "artifact_namespace": artifact_namespace,
        "run_mode": run_mode,
        "run_id": run_id,
        "fade_review_candidate_id": f"fade_review:{coin_id or symbol}:{_digest(str(item.get('event_name') or item.get('title') or '') + '|' + observed.isoformat())}",
        "symbol": symbol,
        "coin_id": coin_id,
        "event_name": _text(_first(item, "event_name", "title")) or "unknown catalyst",
        "source_class": _text(item.get("source_class")) or None,
        "source_pack": _text(item.get("source_pack")) or None,
        "impact_path_type": _text(item.get("impact_path_type")) or None,
        "playbook_type": _text(item.get("playbook_type")) or None,
        "market_state": reaction.market_state,
        "market_state_class": reaction.market_state,
        "market_state_snapshot": reaction.market_state_snapshot.to_dict(),
        "derivatives_state_snapshot": dict(state),
        "supported_metric_status": dict(state.get("supported_metric_status") or {}),
        "open_interest_unit": state.get("open_interest_unit"),
        "funding_rate_unit": state.get("funding_rate_unit"),
        "basis_unit": state.get("basis_unit"),
        "liquidation_unit": state.get("liquidation_unit"),
        "volume_unit": state.get("volume_unit"),
        "unit_metadata": dict(state.get("unit_metadata") or {}),
        "derivatives_snapshot_freshness_status": state.get("derivatives_snapshot_freshness_status") or state.get("freshness_status"),
        "open_interest_freshness": state.get("open_interest_freshness"),
        "funding_freshness": state.get("funding_freshness"),
        "liquidation_freshness": state.get("liquidation_freshness"),
        "long_short_freshness": state.get("long_short_freshness"),
        "basis_freshness": state.get("basis_freshness"),
        "opportunity_type": opportunity,
        "opportunity_type_original": reaction.opportunity_type,
        "opportunity_type_fade_requirements_met": bool(fade_ready),
        "fade_requirements_met": bool(fade_ready),
        "completed_move": bool(completed_move),
        "crowding_exhaustion_evidence": tuple(crowding_evidence),
        "crowding_class": _crowding_class(state),
        "liquidity_sane": bool(liquidity_sane),
        "fade_readiness": "ready_for_review" if fade_ready else "not_ready",
        "why_now": reaction.why_now if fade_ready else "derivatives context collected; fade review not confirmed",
        "what_confirms_fade_review": (
            "completed move remains visible",
            "OI/funding/liquidation/perp-volume crowding persists",
            "liquidity and spread remain sane enough for manual review",
        ),
        "what_invalidates_fade_review": (
            "OI/funding cools off",
            "price consolidates without failed reclaim",
            "liquidity is too thin or spread is too wide",
        ),
        "research_only_disclaimer": RESEARCH_DISCLAIMER,
        "triggered_fade_created": False,
        "created_alert": False,
        "normal_rsi_signal_written": False,
        "paper_trade_created": False,
        "notification_send_enabled": False,
        "warnings": tuple(dict.fromkeys(warnings)),
        "reason_codes": tuple(dict.fromkeys((*reaction.reason_codes, *crowding_evidence))),
        "observed_at": observed.isoformat(),
        "raw_payload_redacted": _redacted_payload(item),
    }
    return row


def load_derivatives_state(namespace_dir: str | Path | None) -> tuple[dict[str, Any], ...]:
    if namespace_dir is None:
        return ()
    return tuple(_read_jsonl(Path(namespace_dir) / DERIVATIVES_STATE_FILENAME))


def load_fade_review_candidates(namespace_dir: str | Path | None) -> tuple[dict[str, Any], ...]:
    if namespace_dir is None:
        return ()
    return tuple(_read_jsonl(Path(namespace_dir) / FADE_SHORT_REVIEW_CANDIDATES_FILENAME))


def load_derivatives_candidates(namespace_dir: str | Path | None) -> tuple[dict[str, Any], ...]:
    if namespace_dir is None:
        return ()
    return tuple(_read_jsonl(Path(namespace_dir) / DERIVATIVES_CROWDING_CANDIDATES_FILENAME))


def format_derivatives_crowding_report(
    *,
    state_rows: Iterable[Mapping[str, Any]],
    candidate_rows: Iterable[Mapping[str, Any]],
    profile: str | None = None,
    artifact_namespace: str | None = None,
    warnings: Iterable[str] = (),
) -> str:
    states = [dict(row) for row in state_rows]
    candidates = [dict(row) for row in candidate_rows]
    fade = [row for row in candidates if row.get("opportunity_type") == FADE_REVIEW_LANE]
    lanes = _counts(str(row.get("opportunity_type") or "UNKNOWN") for row in candidates)
    crowding = _counts(str(row.get("crowding_class") or "unknown") for row in candidates)
    lines = [
        "# Event Alpha Derivatives Crowding Report",
        "",
        "Research-only. Not a trade signal, paper trade, live RSI signal, or execution.",
        f"Profile: {profile or 'default'}",
        f"Artifact namespace: {artifact_namespace or 'default'}",
        f"Derivatives state rows: {len(states)}",
        f"Evaluated candidates: {len(candidates)}",
        f"Fade / short-review candidates: {len(fade)}",
        "Opportunity lanes: " + (_format_counts(lanes) or "none"),
        "Crowding classes: " + (_format_counts(crowding) or "none"),
        "Implemented metric values: " + (_join(_metrics_by_status(states, METRIC_STATUS_IMPLEMENTED)) or "none"),
        "Fixture-only metric values: " + (_join(_metrics_by_status(states, METRIC_STATUS_FIXTURE_ONLY)) or "none"),
        "Missing/planned metric values: " + (_join(_metrics_by_status(states, METRIC_STATUS_MISSING_FROM_RESPONSE, METRIC_STATUS_NOT_IMPLEMENTED, METRIC_STATUS_PROVIDER_UNAVAILABLE)) or "none"),
        "",
        "## Fade / Short-Review Research",
        "Move may be crowded/exhausted; review risk and invalidation. Research-only. Not a trade signal.",
    ]
    if not fade:
        lines.append("- none")
    for row in fade:
        lines.extend([
            (
                f"- {row.get('symbol')}/{row.get('coin_id')} {row.get('event_name')} "
                f"market_state={row.get('market_state')} crowding={row.get('crowding_class')}"
            ),
            "  move: " + _move_summary(row),
            "  evidence: " + (_join(row.get("crowding_exhaustion_evidence")) or "none"),
            "  invalidates: " + _join(row.get("what_invalidates_fade_review")),
        ])
    lines.extend(["", "## Evaluated Candidate Summary"])
    if not candidates:
        lines.append("- none")
    for row in candidates:
        lines.append(
            f"- {row.get('symbol')}/{row.get('coin_id')} lane={row.get('opportunity_type')} "
            f"market_state={row.get('market_state')} crowding={row.get('crowding_class')} "
            f"fade_ready={row.get('fade_readiness')}"
        )
        row_warnings = [str(item) for item in row.get("warnings") or () if str(item)]
        if row_warnings:
            lines.append("  - warnings: " + "; ".join(row_warnings[:5]))
    lines.extend(["", "## Derivatives State"])
    if not states:
        lines.append("- none")
    for row in states:
        lines.append(
            f"- {row.get('symbol')}/{row.get('coin_id')} provider={row.get('provider')} "
            f"freshness={row.get('derivatives_snapshot_freshness_status') or row.get('freshness_status')} "
            f"oi_delta_24h={_fmt_pct(row.get('open_interest_delta_24h'))} "
            f"funding={_fmt_pct(row.get('funding_rate'))} "
            f"predicted_funding={_fmt_metric_pct(row, 'predicted_funding', 'predicted_funding_rate')} "
            f"funding_z={_fmt_number(row.get('funding_zscore'))} "
            f"basis={_fmt_metric_pct(row, 'basis', 'basis')} "
            f"metric_status={_format_metric_status(row.get('supported_metric_status'))} "
            f"units={_format_unit_metadata(row)}"
        )
    if warnings:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines) + "\n"


def _candidate_from_derivatives_state(state: Mapping[str, Any], *, observed_at: datetime) -> dict[str, Any]:
    symbol = (_text(state.get("symbol")) or "UNKNOWN").upper()
    coin_id = _text(state.get("coin_id")) or symbol.lower()
    market_snapshot = _market_snapshot_from_derivatives_state(state, observed_at=observed_at)
    confirmation_score = _state_market_confirmation_score(market_snapshot, state)
    if confirmation_score >= 75:
        confirmation_level = "strong"
    elif confirmation_score >= 50:
        confirmation_level = "moderate"
    else:
        confirmation_level = "weak"
    return {
        "symbol": symbol,
        "coin_id": coin_id,
        "event_name": f"{symbol} Coinalyze derivatives crowding rehearsal",
        "source_class": "derivatives_provider",
        "source_pack": "derivatives_crowding_pack",
        "impact_path_type": "derivatives_crowding_research",
        "playbook_type": "derivatives_crowding_research",
        "evidence_quality_score": 82,
        "accepted_evidence_count": 1,
        "accepted_evidence_reason_codes": ("coinalyze_derivatives_state",),
        "market_confirmation_level": confirmation_level,
        "market_confirmation_score": confirmation_score,
        "market_snapshot": market_snapshot,
    }


def _market_snapshot_from_derivatives_state(state: Mapping[str, Any], *, observed_at: datetime) -> dict[str, Any]:
    return_24h = _return_fraction(_first(state, "futures_price_return_24h_pct", "futures_price_return_24h", "price_return_24h", "return_24h"))
    return_4h = _return_fraction(_first(state, "futures_price_return_4h_pct", "futures_price_return_4h", "price_return_4h", "return_4h"))
    volume_ratio = _float(state.get("perp_spot_volume_ratio"))
    volume_z = None
    if volume_ratio is not None:
        if volume_ratio >= 4:
            volume_z = 4.0
        elif volume_ratio >= 3:
            volume_z = 3.0
        elif volume_ratio >= 2:
            volume_z = 2.0
    market: dict[str, Any] = {
        "return_24h": return_24h,
        "return_4h": return_4h,
        "volume_zscore_24h": volume_z,
        "market_context_freshness_status": state.get("derivatives_snapshot_freshness_status") or state.get("freshness_status") or "unknown",
        "market_context_source": "coinalyze_derivatives_rehearsal",
    }
    age = _state_age_hours(state, observed_at=observed_at)
    if age is not None:
        market["event_age_hours"] = age
    return {key: value for key, value in market.items() if value is not None}


def _state_market_confirmation_score(market: Mapping[str, Any], state: Mapping[str, Any]) -> int:
    r24 = _return_pct(market.get("return_24h"))
    r4 = _return_pct(market.get("return_4h"))
    if (r24 is not None and r24 >= 30) or (r4 is not None and r4 >= 20):
        return 82
    if (r24 is not None and r24 >= 12) or (r4 is not None and r4 >= 5):
        return 62
    if _crowding_evidence(state):
        return 45
    return 30


def _state_age_hours(state: Mapping[str, Any], *, observed_at: datetime) -> float | None:
    source_time = _parse_time(state.get("observed_at"))
    if source_time is None:
        return None
    return max(0.0, (observed_at - _as_utc(source_time)).total_seconds() / 3600.0)


def _return_fraction(value: object) -> float | None:
    number = _float(value)
    if number is None:
        return None
    if abs(number) <= 3.0:
        return number
    return number / 100.0


def _return_pct(value: object) -> float | None:
    number = _float(value)
    if number is None:
        return None
    if abs(number) <= 3.0:
        return number * 100.0
    return number


def _load_payload(path: str | Path) -> Any:
    text = Path(path).expanduser().read_text(encoding="utf-8")
    return json.loads(text)


def _payload_rows(payload: Any, *keys: str) -> list[Mapping[str, Any]]:
    rows: Any = None
    if isinstance(payload, Mapping):
        for key in keys:
            if isinstance(payload.get(key), list):
                rows = payload.get(key)
                break
    elif isinstance(payload, list):
        rows = payload
    if not isinstance(rows, list):
        return []
    out: list[Mapping[str, Any]] = []
    for row in rows:
        if isinstance(row, Mapping):
            out.append(row)
    return out


def _state_index(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        for value in (row.get("coin_id"), row.get("symbol"), row.get("market")):
            text = _text(value)
            if not text:
                continue
            out[text.casefold()] = row
            out[text.upper()] = row
    return out


def _lookup_state_for_candidate(item: Mapping[str, Any], state_by_key: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any] | None:
    for value in (_first(item, "coin_id", "validated_coin_id"), _first(item, "symbol", "validated_symbol")):
        text = _text(value)
        if not text:
            continue
        found = state_by_key.get(text.casefold()) or state_by_key.get(text.upper())
        if found:
            return found
    return None


def _reaction_derivatives_snapshot(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "open_interest_delta": _first(state, "open_interest_delta_24h", "open_interest_delta_4h", "open_interest_delta_1h"),
        "open_interest_24h_change_pct": state.get("open_interest_delta_24h"),
        "funding_rate_8h": state.get("funding_rate"),
        "predicted_funding_rate": state.get("predicted_funding_rate"),
        "funding_zscore": state.get("funding_zscore"),
        "liquidation_imbalance": state.get("liquidation_imbalance"),
        "long_short_ratio": state.get("long_short_ratio"),
        "basis": state.get("basis"),
        "perp_spot_volume_ratio": state.get("perp_spot_volume_ratio"),
        "supported_metric_status": dict(state.get("supported_metric_status") or {}),
        "unit_metadata": dict(state.get("unit_metadata") or {}),
    }


def _market_snapshot(item: Mapping[str, Any]) -> dict[str, Any]:
    raw = item.get("market_snapshot")
    if isinstance(raw, Mapping):
        out = dict(raw)
    else:
        out = {}
    for key in (
        "return_5m",
        "return_15m",
        "return_1h",
        "return_4h",
        "return_24h",
        "relative_return_vs_btc",
        "volume_zscore_24h",
        "volume_turnover_zscore",
        "volume_to_market_cap",
        "liquidity_usd",
        "spread_bps",
        "event_age_hours",
        "market_context_freshness_status",
    ):
        value = item.get(key)
        if value not in (None, "", [], {}, ()):
            out.setdefault(key, value)
    return out


def _crowding_evidence(state: Mapping[str, Any]) -> tuple[str, ...]:
    evidence: list[str] = []
    oi4 = _pct(state.get("open_interest_delta_4h"))
    oi24 = _pct(state.get("open_interest_delta_24h"))
    funding = _pct(state.get("funding_rate"))
    funding_z = _float(state.get("funding_zscore"))
    liq = _float(state.get("liquidation_imbalance"))
    perp_spot = _float(state.get("perp_spot_volume_ratio"))
    basis = _pct(state.get("basis"))
    if oi4 is not None and oi4 >= 30:
        evidence.append("open_interest_delta_4h_high")
    if oi24 is not None and oi24 >= 35:
        evidence.append("open_interest_delta_24h_high")
    if funding is not None and abs(funding) >= 0.05:
        evidence.append("funding_elevated")
    if funding_z is not None and abs(funding_z) >= 2:
        evidence.append("funding_zscore_elevated")
    if liq is not None and abs(liq) >= 1.5:
        evidence.append("liquidation_imbalance_extreme")
    if perp_spot is not None and perp_spot >= 3:
        evidence.append("perp_spot_volume_divergence")
    if basis is not None and funding is not None and abs(basis) >= 0.25 and abs(funding) >= 0.01 and _sign(basis) != _sign(funding):
        evidence.append("basis_funding_disagreement")
    return tuple(evidence)


def _crowding_class(state: Mapping[str, Any]) -> str:
    count = len(_crowding_evidence(state))
    if count >= 4:
        return "extreme"
    if count >= 2:
        return "high"
    if count == 1:
        return "moderate"
    return "none"


def _completed_move(market: Mapping[str, Any], market_state: str) -> bool:
    event_age = _float(_first(market, "event_age_hours", "age_hours"))
    return any((
        str(market_state) in {"blowoff_crowded", "post_event_fade_setup", "late_momentum"},
        (_pct(_first(market, "return_24h", "price_change_24h")) or 0) >= 25,
        (_pct(_first(market, "return_4h", "price_change_4h")) or 0) >= 15,
        event_age is not None
        and event_age >= 0
        and ((_pct(_first(market, "return_24h")) or 0) >= 15),
    ))


def _liquidity_sane(market: Mapping[str, Any]) -> bool:
    liquidity = _float(_first(market, "liquidity_usd", "order_book_depth_2pct", "depth_2pct_usd"))
    spread = _float(_first(market, "spread_bps", "bid_ask_spread_bps"))
    if liquidity is not None and liquidity < 50_000:
        return False
    if spread is not None and spread > 150:
        return False
    return True


def _negative_without_crowding(item: Mapping[str, Any], state: Mapping[str, Any]) -> bool:
    text = f"{item.get('impact_path_type') or ''} {item.get('source_pack') or ''} {item.get('playbook_type') or ''}".casefold()
    return any(token in text for token in ("exploit", "security", "risk", "delisting")) and not _crowding_evidence(state)


def _state_fresh_for_fade_review(state: Mapping[str, Any]) -> bool:
    status = str(
        state.get("derivatives_snapshot_freshness_status")
        or state.get("freshness_status")
        or ""
    ).casefold()
    return status in {"fresh", "fixture_allowed_stale"}


def _derivatives_warnings(
    *,
    timestamp: datetime,
    observed_at: datetime,
    funding_rate: float | None,
    open_interest: float | None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if _freshness_status(timestamp, observed_at) in {"stale", "expired"}:
        warnings.append("derivatives_state_stale")
    if funding_rate is None:
        warnings.append("funding_rate_missing")
    if open_interest is None:
        warnings.append("open_interest_missing")
    return tuple(warnings)


def _freshness_status(timestamp: datetime | None, observed_at: datetime) -> str:
    if timestamp is None:
        return "unknown"
    age_hours = max(0.0, (observed_at - timestamp).total_seconds() / 3600.0)
    if age_hours <= 6:
        return "fresh"
    if age_hours <= 24:
        return "stale"
    return "expired"


def _metric_freshness(
    row: Mapping[str, Any],
    *,
    observed_at: datetime,
    value_present: bool,
    fallback_timestamp: datetime | None,
    fallback_status: str | None = None,
    keys: Iterable[str],
) -> str:
    if not value_present:
        return "missing"
    timestamp: datetime | None = None
    for key in keys:
        timestamp = _parse_time(row.get(key))
        if timestamp is not None:
            break
    if timestamp is None:
        timestamp = fallback_timestamp
    if timestamp is None and fallback_status:
        return fallback_status
    return _freshness_status(_as_utc(timestamp), observed_at) if timestamp else "unknown"


def _explicit_freshness_status(row: Mapping[str, Any]) -> str | None:
    value = str(_first(row, "derivatives_snapshot_freshness_status", "freshness_status") or "").strip().casefold()
    if value in {"fresh", "stale", "expired", "unknown", "missing", "fixture_allowed_stale"}:
        return value
    return None


def _combined_freshness_status(*statuses: str) -> str:
    useful = [str(status or "").strip().casefold() for status in statuses if str(status or "").strip()]
    useful = [status for status in useful if status != "missing"]
    if not useful:
        return "missing"
    for status in ("expired", "stale", "unknown"):
        if status in useful:
            return status
    return "fresh" if "fresh" in useful else useful[0]


def _supported_metric_status(metric_values: Mapping[str, bool], *, provider_unavailable: bool = False) -> dict[str, str]:
    out: dict[str, str] = {}
    for metric in DERIVATIVES_SUPPORTED_METRICS:
        if provider_unavailable:
            out[metric] = METRIC_STATUS_PROVIDER_UNAVAILABLE
            continue
        base_status = DERIVATIVES_LIVE_METRIC_IMPLEMENTATION_STATUS.get(metric, METRIC_STATUS_NOT_IMPLEMENTED)
        present = bool(metric_values.get(metric))
        if base_status == METRIC_STATUS_FIXTURE_ONLY:
            out[metric] = METRIC_STATUS_FIXTURE_ONLY if present else METRIC_STATUS_NOT_IMPLEMENTED
        elif base_status == METRIC_STATUS_IMPLEMENTED:
            out[metric] = METRIC_STATUS_IMPLEMENTED if present else METRIC_STATUS_MISSING_FROM_RESPONSE
        else:
            out[metric] = base_status
    return out


def _unit(row: Mapping[str, Any], key: str, *, default: str) -> str:
    value = str(row.get(key) or "").strip()
    return value or default


def _liquidation_imbalance(long_usd: float | None, short_usd: float | None) -> float | None:
    if long_usd is None or short_usd is None:
        return None
    if long_usd == 0 and short_usd == 0:
        return 0.0
    if short_usd == 0:
        return 99.0
    if long_usd == 0:
        return -99.0
    if long_usd >= short_usd:
        return long_usd / short_usd
    return -(short_usd / long_usd)


def _base_symbol(row: Mapping[str, Any]) -> str | None:
    explicit = _text(_first(row, "base_symbol", "base_asset", "symbol_base"))
    if explicit:
        return explicit.upper()
    symbol = _text(_first(row, "symbol", "market_symbol", "market"))
    if not symbol:
        return None
    upper = symbol.upper().split(".", 1)[0]
    raw = upper.replace("-", "").replace("_", "").replace("/", "")
    for suffix in ("PERP", "USDT", "USD"):
        if raw.endswith(suffix) and len(raw) > len(suffix):
            raw = raw[: -len(suffix)]
    return raw or upper


def _redacted_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        lower = str(key).casefold()
        if "api_key" in lower or "token" in lower or "secret" in lower:
            out[str(key)] = "<redacted>"
        else:
            out[str(key)] = _diagnostic_value(value)
    return out


def _diagnostic_value(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return "<non_finite>"
    if isinstance(value, Mapping):
        return {str(key): _diagnostic_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_diagnostic_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_diagnostic_value(item) for item in value)
    return value


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            stamped = schema_v1.stamp_artifact_row(row, path=path)
            handle.write(json.dumps(_jsonable(stamped), sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(raw, Mapping):
            out.append(dict(raw))
    return out


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _parse_time(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, bool):
        raise ValueError(f"invalid datetime {value!r}")
    if isinstance(value, (int, float)):
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError(f"invalid datetime {value!r}")
        seconds = numeric / 1000.0 if numeric > 10_000_000_000 else numeric
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OSError, OverflowError, ValueError) as exc:
            raise ValueError(f"invalid datetime {value!r}") from exc
    return parse_datetime(value)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _first(row: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", [], {}, ()):
            return value
    return None


def _text(value: object) -> str:
    return str(value or "").strip()


def _float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        if value in (None, ""):
            return None
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _pct(value: object) -> float | None:
    number = _float(value)
    if number is None:
        return None
    if abs(number) <= 3.0:
        return number * 100.0
    return number


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _fmt_pct(value: object) -> str:
    number = _pct(value)
    return "n/a" if number is None else f"{number:.1f}%"


def _fmt_number(value: object) -> str:
    number = _float(value)
    return "n/a" if number is None else f"{number:g}"


def _fmt_metric_pct(row: Mapping[str, Any], metric: str, value_key: str) -> str:
    value = row.get(value_key)
    if _float(value) is not None:
        return _fmt_pct(value)
    return _metric_status(row, metric) or "missing_from_response"


def _metric_status(row: Mapping[str, Any], metric: str) -> str:
    status = row.get("supported_metric_status")
    if isinstance(status, Mapping):
        return str(status.get(metric) or "").strip()
    return ""


def _format_metric_status(value: object) -> str:
    if not isinstance(value, Mapping):
        return "none"
    parts = [f"{metric}={value.get(metric)}" for metric in DERIVATIVES_SUPPORTED_METRICS if value.get(metric)]
    return ", ".join(parts) if parts else "none"


def _format_unit_metadata(row: Mapping[str, Any]) -> str:
    units = row.get("unit_metadata") if isinstance(row.get("unit_metadata"), Mapping) else row
    keys = ("open_interest_unit", "funding_rate_unit", "basis_unit", "liquidation_unit", "volume_unit")
    parts = [f"{key}={units.get(key)}" for key in keys if units.get(key)]  # type: ignore[union-attr]
    return ", ".join(parts) if parts else "none"


def _metrics_by_status(rows: Iterable[Mapping[str, Any]], *statuses: str) -> tuple[str, ...]:
    wanted = {str(status) for status in statuses}
    out: list[str] = []
    for row in rows:
        metric_status = row.get("supported_metric_status")
        if not isinstance(metric_status, Mapping):
            continue
        for metric in DERIVATIVES_SUPPORTED_METRICS:
            status = str(metric_status.get(metric) or "")
            if status in wanted:
                out.append(f"{metric}:{status}")
    return tuple(dict.fromkeys(out))


def _move_summary(row: Mapping[str, Any]) -> str:
    snap = row.get("market_state_snapshot") if isinstance(row.get("market_state_snapshot"), Mapping) else {}
    return f"24h={_fmt_pct(snap.get('return_24h'))}, 4h={_fmt_pct(snap.get('return_4h'))}"


def _join(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return ", ".join(str(key) for key, item in value.items() if item)
    try:
        return ", ".join(str(item) for item in value if str(item))  # type: ignore[union-attr]
    except TypeError:
        return str(value)


def _counts(values: Iterable[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items()))


def _format_counts(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in counts.items())


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
