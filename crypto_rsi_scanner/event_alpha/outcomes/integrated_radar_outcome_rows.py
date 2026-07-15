"""Row construction helpers for integrated Event Alpha radar outcomes."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from ..operations import market_provenance as event_market_provenance
from ..radar.decision_model_surfaces import decision_model_values
from ..radar.decision_models import (
    evidence_confidence_score_cohort,
    risk_score_cohort,
)
from . import outcome_eligibility


HORIZONS = outcome_eligibility.OUTCOME_HORIZONS


def _persisted_decision_values(candidate: Mapping[str, Any]) -> dict[str, Any]:
    values = decision_model_values(candidate)
    sequence_fields = {
        "thesis_origins",
        "decision_hard_blockers",
        "decision_soft_penalties",
        "decision_missing_data",
        "decision_warnings",
        "why_still_worth_reviewing",
        "radar_what_confirms",
        "radar_what_invalidates",
    }
    return {
        key: list(value) if key in sequence_fields and isinstance(value, tuple) else value
        for key, value in values.items()
    }


def _calendar_evidence_values(candidate: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "unified_calendar_event",
        "calendar_event",
        "scheduled_catalyst_event",
        "unlock_event",
        "nearby_calendar_events",
        "calendar_events",
        "scheduled_at",
    )
    out: dict[str, Any] = {}
    for field in fields:
        value = candidate.get(field)
        if value in (None, "", [], {}, ()):
            continue
        if isinstance(value, tuple):
            value = list(value)
        out[field] = value
    return out


def _outcome_placeholder_row(candidate: Mapping[str, Any], *, now: str) -> dict[str, Any]:
    lane = str(candidate.get("opportunity_type") or "UNCONFIRMED_RESEARCH")
    primary_horizon = outcome_eligibility.primary_horizon_for_lane(lane) or "24h"
    identity_fields = outcome_eligibility.build_outcome_identity_fields(candidate)
    horizon_metadata = outcome_eligibility.build_pending_horizon_metadata(
        observed_at=identity_fields["observed_at"],
        evaluated_at=now,
    )
    primary_status = str(horizon_metadata[primary_horizon]["maturity_status"])
    decision = _persisted_decision_values(candidate)
    market_provenance = event_market_provenance.market_provenance_values(candidate)
    market_provenance_fields = (
        {
            "market_provenance": market_provenance,
            **event_market_provenance.market_provenance_flat_fields(market_provenance),
        }
        if market_provenance
        else {}
    )
    empty_returns = {horizon: None for horizon in HORIZONS}
    row = {
        "schema_version": 1,
        "row_type": "event_integrated_radar_outcome",
        **identity_fields,
        "outcome_eligibility_contract_version": (
            outcome_eligibility.OUTCOME_ELIGIBILITY_CONTRACT_VERSION
        ),
        "outcome_data_source": "pending_observation",
        "outcome_evaluated_at": now,
        "calibration_eligible": False,
        "calibration_ineligible_reasons": [],
        "symbol": str(candidate.get("symbol") or "UNKNOWN"),
        "coin_id": candidate.get("coin_id"),
        "run_mode": candidate.get("run_mode"),
        "opportunity_type": lane,
        "source_origin": candidate.get("source_origin"),
        "source_pack": candidate.get("source_pack"),
        "provider": candidate.get("provider") or candidate.get("source_class"),
        "market_state_class": candidate.get("market_state_class"),
        "source_strength": candidate.get("source_strength"),
        "crowding_class": candidate.get("crowding_class"),
        **_calendar_evidence_values(candidate),
        "decision_projection": dict(decision),
        **decision,
        **market_provenance_fields,
        "evidence_confidence_score_cohort": (
            evidence_confidence_score_cohort(
                decision.get("evidence_confidence_score")
            )
            or "unknown"
        ),
        "risk_score_cohort": risk_score_cohort(decision.get("risk_score")) or "unknown",
        "preview_time": now,
        "price_at_observation": None,
        "observation_price_source": None,
        "observation_price_id": None,
        "observation_price_observed_at": None,
        "price_source": "pending_observation",
        "observation_price_provenance_status": "missing",
        "horizons": dict(empty_returns),
        "horizon_metadata": horizon_metadata,
        "outcome_horizons": list(HORIZONS),
        "return_by_horizon": dict(empty_returns),
        "relative_return_vs_btc_by_horizon": dict(empty_returns),
        "relative_return_vs_eth_by_horizon": dict(empty_returns),
        "primary_horizon": primary_horizon,
        "primary_horizon_return": None,
        "max_favorable_excursion_by_window": dict(empty_returns),
        "max_adverse_excursion_by_window": dict(empty_returns),
        "thesis_direction": _thesis_direction(lane),
        "thesis_primary_move": None,
        "thesis_return_by_horizon": dict(empty_returns),
        "thesis_relative_return_vs_btc_by_horizon": dict(empty_returns),
        "thesis_favorable_excursion_by_window": dict(empty_returns),
        "thesis_adverse_excursion_by_window": dict(empty_returns),
        "thesis_outcome_interpretation": "Pending automatic market outcome; no preference label inferred.",
        "outcome_label": "pending" if primary_status == "pending" else "inconclusive",
        "validation_label": "inconclusive",
        "outcome_status": primary_status,
        "missing_data_reason": (
            None if primary_status == "pending" else "outcome_window_elapsed_without_price"
        ),
        "include_in_performance": False,
        "automatic_outcome": True,
        "human_preference_feedback": None,
        "research_only": True,
        "no_send_rehearsal": True,
        "sent": False,
        "no_trade_created": True,
        "no_paper_trade_created": True,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
    }
    row["calibration_ineligible_reasons"] = list(
        outcome_eligibility.calibration_ineligibility_reasons(row)
    )
    return row


def _outcome_row(candidate: Mapping[str, Any], *, now: str) -> dict[str, Any]:
    symbol = str(candidate.get("symbol") or "UNKNOWN")
    lane = str(candidate.get("opportunity_type") or "UNCONFIRMED_RESEARCH")
    returns = _fixture_returns(symbol, lane)
    btc_returns = _benchmark_returns("BTC")
    eth_returns = _benchmark_returns("ETH")
    primary_horizon = outcome_eligibility.primary_horizon_for_lane(lane) or "24h"
    primary_return = returns.get(primary_horizon)
    label = _label_for(symbol, lane, primary_return)
    price = _price(candidate)
    status = "filled" if returns else "missing_data"
    missing_reason = None if returns else "no_cached_price_fixture"
    relative_vs_btc = {
        horizon: _relative_return(returns.get(horizon), btc_returns.get(horizon))
        for horizon in HORIZONS
    }
    thesis_direction = _thesis_direction(lane)
    thesis_returns = _thesis_returns(returns, lane)
    thesis_relative_vs_btc = _thesis_returns(relative_vs_btc, lane)
    thesis_favorable = _window_extremes(thesis_returns, want_peak=True)
    thesis_adverse = _window_extremes(thesis_returns, want_peak=False)
    thesis_primary = thesis_returns.get(primary_horizon)
    numeric_returns = [
        number
        for horizon in HORIZONS
        if (number := outcome_eligibility.finite_number(returns.get(horizon))) is not None
    ]
    decision = _persisted_decision_values(candidate)
    identity_fields = outcome_eligibility.build_outcome_identity_fields(candidate)
    horizon_metadata = outcome_eligibility.build_synthetic_horizon_metadata(
        observed_at=identity_fields["observed_at"],
        evaluated_at=now,
    )
    primary_maturity = horizon_metadata[primary_horizon]["maturity_status"]
    row = {
        "schema_version": 1,
        "row_type": "event_integrated_radar_outcome",
        **identity_fields,
        "outcome_eligibility_contract_version": (
            outcome_eligibility.OUTCOME_ELIGIBILITY_CONTRACT_VERSION
        ),
        "outcome_data_source": "synthetic_fixture",
        "outcome_evaluated_at": now,
        "calibration_eligible": False,
        "calibration_ineligible_reasons": [],
        "symbol": symbol,
        "coin_id": candidate.get("coin_id"),
        "run_mode": candidate.get("run_mode"),
        "opportunity_type": lane,
        "source_origin": candidate.get("source_origin"),
        "source_pack": candidate.get("source_pack"),
        "provider": candidate.get("provider") or candidate.get("source_class"),
        "market_state_class": candidate.get("market_state_class"),
        "source_strength": candidate.get("source_strength"),
        "crowding_class": candidate.get("crowding_class"),
        **_calendar_evidence_values(candidate),
        "decision_projection": dict(decision),
        **decision,
        "evidence_confidence_score_cohort": (
            evidence_confidence_score_cohort(
                decision.get("evidence_confidence_score")
            )
            or "unknown"
        ),
        "risk_score_cohort": risk_score_cohort(decision.get("risk_score")) or "unknown",
        "preview_time": now,
        "price_at_observation": price,
        "observation_price_source": None,
        "observation_price_id": None,
        "observation_price_observed_at": None,
        "price_source": "candidate_market_snapshot" if price is not None else "missing",
        "observation_price_provenance_status": "synthetic_fixture",
        "horizons": {horizon: returns.get(horizon) for horizon in HORIZONS},
        "horizon_metadata": horizon_metadata,
        "outcome_horizons": list(HORIZONS),
        "return_by_horizon": {horizon: returns.get(horizon) for horizon in HORIZONS},
        "relative_return_vs_btc_by_horizon": relative_vs_btc,
        "relative_return_vs_eth_by_horizon": {
            horizon: _relative_return(returns.get(horizon), eth_returns.get(horizon))
            for horizon in HORIZONS
        },
        "benchmark_btc_price_at_observation": 65000.0,
        "benchmark_eth_price_at_observation": 3500.0,
        "benchmark_btc_return_by_horizon": {horizon: btc_returns.get(horizon) for horizon in HORIZONS},
        "benchmark_eth_return_by_horizon": {horizon: eth_returns.get(horizon) for horizon in HORIZONS},
        "primary_horizon": primary_horizon,
        "primary_horizon_return": primary_return,
        "relative_return_vs_btc_24h": returns.get("relative_vs_btc_24h"),
        "mfe": max(numeric_returns, default=None),
        "mae": min(numeric_returns, default=None),
        "max_favorable_excursion_by_window": _window_extremes(returns, want_peak=True),
        "max_adverse_excursion_by_window": _window_extremes(returns, want_peak=False),
        "thesis_direction": thesis_direction,
        "thesis_primary_move": thesis_primary,
        "thesis_return_by_horizon": thesis_returns,
        "thesis_relative_return_vs_btc_by_horizon": thesis_relative_vs_btc,
        "thesis_favorable_excursion_by_window": thesis_favorable,
        "thesis_adverse_excursion_by_window": thesis_adverse,
        "thesis_favorable_excursion": _best_mapping_value(thesis_favorable, want_peak=True),
        "thesis_adverse_excursion": _best_mapping_value(thesis_adverse, want_peak=False),
        "thesis_outcome_interpretation": (
            "Synthetic fixture diagnostic only: "
            + _thesis_interpretation(lane, label, thesis_primary)
        ),
        "time_to_peak": _time_to_extreme(returns, want_peak=True),
        "time_to_trough": _time_to_extreme(returns, want_peak=False),
        "time_to_peak_hours": _time_to_extreme_hours(returns, want_peak=True),
        "time_to_trough_hours": _time_to_extreme_hours(returns, want_peak=False),
        "catalyst_confirmed_after_observation": "unknown",
        "market_confirmed_after_observation": "unknown",
        "market_confirmed": False,
        "fade_confirmed": False,
        "risk_validated": False,
        "outcome_label": "inconclusive",
        "synthetic_diagnostic_label": label,
        "validation_label": "inconclusive",
        "outcome_status": primary_maturity,
        "missing_data_reason": (
            "primary_horizon_not_observed"
            if primary_maturity == "missing_data"
            else missing_reason
        ),
        "include_in_performance": False,
        "research_only": True,
        "no_send_rehearsal": True,
        "sent": False,
        "no_trade_created": True,
        "no_paper_trade_created": True,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
    }
    row["calibration_ineligible_reasons"] = list(
        outcome_eligibility.calibration_ineligibility_reasons(row)
    )
    return row


def _fixture_returns(symbol: str, lane: str) -> dict[str, float]:
    table = {
        "TESTLIST": {"15m": 0.002, "1h": 0.006, "4h": 0.022, "24h": 0.08, "3d": 0.12, "7d": 0.18, "relative_vs_btc_24h": 0.075},
        "TESTPERP": {"15m": 0.006, "1h": 0.024, "4h": 0.055, "24h": 0.11, "3d": 0.16, "7d": 0.2, "relative_vs_btc_24h": 0.105},
        "TESTFADE": {"15m": -0.01, "1h": -0.035, "4h": -0.08, "24h": -0.14, "3d": -0.18, "7d": -0.2, "relative_vs_btc_24h": -0.13},
        "TESTUNLOCK": {"15m": -0.003, "1h": -0.01, "4h": -0.035, "24h": -0.09, "3d": -0.12, "7d": -0.16, "relative_vs_btc_24h": -0.085},
        "BTC": {"15m": 0.0, "1h": 0.001, "4h": 0.001, "24h": 0.002, "3d": 0.004, "7d": 0.006, "relative_vs_btc_24h": 0.0},
        "TESTRUMOR": {"15m": 0.0, "1h": -0.001, "4h": 0.001, "24h": 0.003, "3d": 0.0, "7d": -0.002, "relative_vs_btc_24h": 0.001},
        "SECTOR": {"15m": 0.0, "1h": 0.0, "4h": 0.0, "24h": 0.0, "3d": 0.0, "7d": 0.0, "relative_vs_btc_24h": 0.0},
    }
    return dict(table.get(symbol.upper(), table.get("SECTOR" if lane == "DIAGNOSTIC" else "", {})))


def _thesis_direction(lane: str) -> str:
    return {
        "EARLY_LONG_RESEARCH": "upside_research",
        "CONFIRMED_LONG_RESEARCH": "upside_research",
        "FADE_SHORT_REVIEW": "downside_or_risk_research",
        "RISK_ONLY": "downside_or_risk_research",
        "UNCONFIRMED_RESEARCH": "neutral_validation_research",
        "DIAGNOSTIC": "diagnostic",
    }.get(str(lane or "").upper(), "neutral_validation_research")


def _thesis_multiplier(lane: str) -> float | None:
    lane_upper = str(lane or "").upper()
    if lane_upper in {"EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH"}:
        return 1.0
    if lane_upper in {"FADE_SHORT_REVIEW", "RISK_ONLY"}:
        return -1.0
    return None


def _thesis_returns(values: Mapping[str, float | None], lane: str) -> dict[str, float | None]:
    multiplier = _thesis_multiplier(lane)
    out: dict[str, float | None] = {}
    for horizon in HORIZONS:
        value = outcome_eligibility.finite_number(values.get(horizon))
        if multiplier is None or value is None:
            out[horizon] = None
            continue
        out[horizon] = value * multiplier
    return out


def _best_mapping_value(values: Mapping[str, float | None], *, want_peak: bool) -> float | None:
    numeric = [
        number
        for value in values.values()
        if (number := outcome_eligibility.finite_number(value)) is not None
    ]
    if not numeric:
        return None
    return max(numeric) if want_peak else min(numeric)


def _thesis_interpretation(lane: str, label: str, thesis_primary: float | None) -> str:
    direction = _thesis_direction(lane)
    lane_upper = str(lane or "").upper()
    if direction == "upside_research":
        if thesis_primary is None:
            return "long research thesis pending; no primary market outcome available"
        return "validated long-research reaction" if thesis_primary > 0 else "not validated by primary market reaction"
    if direction == "downside_or_risk_research" and lane_upper == "FADE_SHORT_REVIEW":
        if thesis_primary is None:
            return "fade-review thesis pending; no primary market outcome available"
        return (
            "validated fade-review thesis: asset fell after the crowded move"
            if thesis_primary > 0
            else "not validated: asset return did not favor the fade thesis"
        )
    if direction == "downside_or_risk_research":
        if thesis_primary is None:
            return "risk thesis pending; no primary market outcome available"
        return (
            "validated risk thesis: asset sold off in the evaluation window"
            if thesis_primary > 0
            else "not validated: asset did not sell off enough for the risk thesis"
        )
    if str(label or "") == "remained_noise":
        return "neutral/noise validation: no directional research thesis scored"
    if direction == "diagnostic":
        return "diagnostic row excluded from performance calibration"
    return "inconclusive research validation; no directional thesis scored"


def _benchmark_returns(symbol: str) -> dict[str, float]:
    if symbol == "ETH":
        return {"15m": 0.0005, "1h": 0.0015, "4h": 0.003, "24h": 0.006, "3d": 0.01, "7d": 0.018}
    return {"15m": 0.0003, "1h": 0.001, "4h": 0.002, "24h": 0.005, "3d": 0.008, "7d": 0.012}


def _relative_return(value: float | None, benchmark: float | None) -> float | None:
    numeric_value = outcome_eligibility.finite_number(value)
    numeric_benchmark = outcome_eligibility.finite_number(benchmark)
    if numeric_value is None or numeric_benchmark is None:
        return None
    return numeric_value - numeric_benchmark


def _window_extremes(returns: Mapping[str, float], *, want_peak: bool) -> dict[str, float | None]:
    values: dict[str, float | None] = {}
    ordered: list[float] = []
    for horizon in HORIZONS:
        value = outcome_eligibility.finite_number(returns.get(horizon))
        if value is not None:
            ordered.append(value)
            values[horizon] = max(ordered) if want_peak else min(ordered)
        else:
            values[horizon] = None
    return values


def _time_to_extreme_hours(returns: Mapping[str, float], *, want_peak: bool) -> float | None:
    horizon = _time_to_extreme(returns, want_peak=want_peak)
    return {
        "15m": 0.25,
        "1h": 1.0,
        "4h": 4.0,
        "24h": 24.0,
        "3d": 72.0,
        "7d": 168.0,
    }.get(str(horizon or ""))


def _confirmed_after_observation(label: str, *, kind: str) -> str:
    if label in {"early_good", "continuation_good", "fade_review_good", "risk_validated"}:
        return "yes"
    if label in {"remained_noise", "diagnostic_only"}:
        return "no"
    return "unknown"


def _group_by(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(dict(row))
    return grouped


def _primary_horizon(lane: str) -> str:
    return outcome_eligibility.primary_horizon_for_lane(lane) or "24h"


def _label_for(symbol: str, lane: str, primary_return: float | None) -> str:
    if primary_return is None:
        return "missing_data"
    symbol_upper = symbol.upper()
    if symbol_upper == "TESTLIST":
        return "early_good"
    if symbol_upper == "TESTPERP":
        return "continuation_good"
    if symbol_upper == "TESTFADE":
        return "fade_review_good"
    if symbol_upper == "TESTUNLOCK":
        return "risk_validated"
    if symbol_upper in {"BTC", "TESTRUMOR"}:
        return "remained_noise"
    if lane in {"EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH"}:
        return "useful" if primary_return > 0.03 else "junk"
    if lane in {"FADE_SHORT_REVIEW", "RISK_ONLY"}:
        return "useful" if primary_return < -0.03 else "junk"
    if lane == "DIAGNOSTIC":
        return "diagnostic_only"
    return "remained_noise" if abs(primary_return) < 0.02 else "watch"


def _truth_label(row: Mapping[str, Any]) -> str:
    label = str(row.get("outcome_label") or "")
    if label in {"useful", "early_good", "continuation_good", "fade_review_good", "risk_validated", "watch"}:
        return "useful"
    if label == "junk":
        return "junk"
    if label in {"remained_noise", "diagnostic_only"}:
        return "junk"
    return "watch"


def _validation_label(row: Mapping[str, Any]) -> str:
    if row.get("calibration_eligible") is not True:
        return "inconclusive"
    return outcome_eligibility.deterministic_validation_status(row)


def _time_to_extreme(values: Mapping[str, float], *, want_peak: bool) -> str | None:
    ordered = [
        (horizon, number)
        for horizon in HORIZONS
        if (number := outcome_eligibility.finite_number(values.get(horizon))) is not None
    ]
    if not ordered:
        return None
    horizon, _value = max(ordered, key=lambda item: item[1]) if want_peak else min(ordered, key=lambda item: item[1])
    return horizon


def _price(candidate: Mapping[str, Any]) -> float | None:
    for key in ("latest_market_snapshot", "market_snapshot", "market_state_snapshot"):
        snapshot = candidate.get(key)
        if isinstance(snapshot, Mapping):
            price = outcome_eligibility.finite_number(snapshot.get("price"))
            if price is not None and price > 0:
                return price
    return None


def _pct(value: Any) -> str:
    number = outcome_eligibility.finite_number(value)
    return "n/a" if number is None else f"{number * 100:+.2f}%"


__all__ = ()
