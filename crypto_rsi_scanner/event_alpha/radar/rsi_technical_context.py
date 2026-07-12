"""Pure read-only RSI context adapter for Crypto Radar Decision Model v2.

The adapter accepts already-supplied RSI signal artifact mappings.  It never
opens storage, calls a provider, routes an alert, creates a paper/live trade,
changes a backtest, or writes a normal RSI/Event Alpha row.  Its adjustments
are explicit bounded metadata for a caller to apply during pure decision
evaluation; this module does not mutate the canonical decision score itself.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import math
from typing import Any, Mapping

from ...signal_registry import (
    canonical_market_regime,
    edge_conviction_prior,
    market_alignment,
    setup_definition,
    setup_for,
)


RSI_TECHNICAL_CONTEXT_VERSION = "rsi_technical_context_v1"
DEFAULT_MAX_AGE_HOURS = 36.0

_SETUP_FIELDS = ("setup_type", "technical_setup_type", "rsi_setup_type")
_RSI_FIELDS = ("rsi_value", "rsi_daily", "rsi_1d", "rsi_4h", "rsi_weekly")
_SEVERITY_FIELDS = ("rsi_severity", "severity")
_REGIME_FIELDS = ("market_regime", "regime")
_CONVICTION_FIELDS = ("conviction", "conviction_score")
_DIRECTION_FIELDS = ("expected_dir", "expected_direction", "direction")
_FRESHNESS_FIELDS = ("rsi_freshness_status", "freshness_status", "signal_freshness")
_TIMESTAMP_FIELDS = ("observed_at", "generated_at", "created_at", "scan_at", "timestamp")

_SEVERITIES = {"normal", "approaching", "watch", "alert", "extreme"}
_REGIMES = {"UPTREND", "DOWNTREND", "RANGE", "UNKNOWN", "NA"}
_FRESH = {"fresh", "current", "valid"}
_STALE = {"stale", "expired", "old"}
_INVALID_FRESHNESS = {"invalid", "future", "malformed"}


@dataclass(frozen=True)
class RsiTechnicalContext:
    """Normalized technical evidence derived from one supplied RSI row."""

    context_version: str
    valid: bool
    symbol: str | None
    coin_id: str | None
    setup_type: str | None
    rsi_severity: str | None
    rsi_value: float | None
    rsi_timeframe: str | None
    market_regime: str | None
    market_alignment: str
    conviction: float | None
    effective_conviction: float | None
    conviction_cap: float | None
    setup_edge_prior: float | None
    setup_has_edge: bool | None
    expected_direction: str | None
    freshness_status: str
    observed_at: str | None
    age_hours: float | None
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["warnings"] = list(self.warnings)
        return row


@dataclass(frozen=True)
class _RsiContextAdjustment:
    """Transparent bounded score deltas produced by normalized RSI context."""

    compatibility: str
    actionability_adjustment: float
    risk_adjustment: float
    actionability_bonus: float
    actionability_penalty: float
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["reason_codes"] = list(self.reason_codes)
        return row


def normalize_rsi_signal_artifact(
    artifact: Mapping[str, Any] | None,
    *,
    evaluated_at: datetime | str | None = None,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
) -> RsiTechnicalContext:
    """Normalize one supplied RSI artifact without I/O or wall-clock fallback.

    Registered fields use first-present authority: a malformed earlier field
    cannot borrow a later alias.  Invalid or stale evidence is retained as
    diagnostic context, but its score adjustment is zero.
    """

    row = artifact if isinstance(artifact, Mapping) else {}
    warnings: list[str] = []

    symbol = str(row.get("symbol") or row.get("asset_symbol") or "").strip().upper()
    coin_id = str(row.get("coin_id") or row.get("asset_coin_id") or "").strip().casefold()
    if not symbol and not coin_id:
        warnings.append("rsi_asset_identity_missing")

    setup_raw, setup_field = _first_present(row, _SETUP_FIELDS)
    regime_raw, _regime_field = _first_present(row, _REGIME_FIELDS)
    flag = str(row.get("flag") or "").strip().upper()
    regime = canonical_market_regime(str(regime_raw)) if regime_raw not in (None, "") else ""
    if regime and regime not in _REGIMES:
        warnings.append("rsi_market_regime_invalid")
        regime = ""

    derived_setup, derived_direction = setup_for(flag, regime) if flag else ("", "")
    setup_type = str(setup_raw or "").strip().casefold()
    if not setup_type and setup_field is None:
        setup_type = derived_setup
    setup = setup_definition(setup_type)
    if setup is None:
        warnings.append("rsi_setup_type_missing" if setup_raw in (None, "") else "rsi_setup_type_invalid")
        setup_type = ""
    elif setup_field and derived_setup and derived_setup != setup_type:
        warnings.append("rsi_setup_flag_regime_mismatch")

    rsi_raw, rsi_field = _first_present(row, _RSI_FIELDS)
    rsi_value = _bounded_number(rsi_raw, minimum=0.0, maximum=100.0)
    if rsi_value is None:
        warnings.append("rsi_value_missing" if rsi_raw is None else "rsi_value_invalid")

    severity_raw, _severity_field = _first_present(row, _SEVERITY_FIELDS)
    if severity_raw in (None, ""):
        severity = _severity_from_value(rsi_value)
    else:
        severity = str(severity_raw).strip().casefold()
        if severity not in _SEVERITIES:
            warnings.append("rsi_severity_invalid")
            severity = None

    conviction_raw, _conviction_field = _first_present(row, _CONVICTION_FIELDS)
    conviction = _bounded_number(conviction_raw, minimum=0.0, maximum=100.0)
    if conviction is None:
        warnings.append("rsi_conviction_missing" if conviction_raw is None else "rsi_conviction_invalid")

    direction_raw, _direction_field = _first_present(row, _DIRECTION_FIELDS)
    direction = _direction_value(direction_raw)
    if direction_raw not in (None, "") and direction is None:
        warnings.append("rsi_expected_direction_invalid")
    if direction is None and derived_direction:
        direction = _direction_value(derived_direction)

    alignment = market_alignment(setup_type, regime) if setup is not None else "neutral"
    edge_prior = (
        edge_conviction_prior(setup_type, alignment, overrides={})
        if setup is not None
        else None
    )
    has_edge = setup.has_edge if setup is not None else None
    conviction_cap = float(edge_prior) if setup is not None and not setup.has_edge and edge_prior is not None else None
    effective_conviction = conviction
    if conviction is not None and conviction_cap is not None:
        effective_conviction = min(conviction, conviction_cap)
        if conviction > effective_conviction:
            warnings.append("rsi_no_edge_conviction_capped")

    freshness, observed_at, age_hours, freshness_warnings = _freshness(
        row,
        evaluated_at=evaluated_at,
        max_age_hours=max_age_hours,
    )
    warnings.extend(freshness_warnings)
    fatal = {
        "rsi_setup_type_missing",
        "rsi_setup_type_invalid",
        "rsi_market_regime_invalid",
        "rsi_value_missing",
        "rsi_value_invalid",
        "rsi_severity_invalid",
        "rsi_conviction_missing",
        "rsi_conviction_invalid",
        "rsi_expected_direction_invalid",
        "rsi_freshness_status_invalid",
        "rsi_freshness_invalid",
        "rsi_timestamp_invalid",
        "rsi_timestamp_in_future",
        "rsi_evaluated_at_invalid",
        "rsi_max_age_invalid",
        "rsi_asset_identity_missing",
        "rsi_asset_identity_mismatch",
    }
    valid = not any(item in fatal for item in warnings)
    return RsiTechnicalContext(
        context_version=RSI_TECHNICAL_CONTEXT_VERSION,
        valid=valid,
        symbol=symbol or None,
        coin_id=coin_id or None,
        setup_type=setup_type or None,
        rsi_severity=severity,
        rsi_value=rsi_value,
        rsi_timeframe=_rsi_timeframe(rsi_field),
        market_regime=regime or None,
        market_alignment=alignment,
        conviction=conviction,
        effective_conviction=effective_conviction,
        conviction_cap=conviction_cap,
        setup_edge_prior=float(edge_prior) if edge_prior is not None else None,
        setup_has_edge=has_edge,
        expected_direction=direction,
        freshness_status=freshness,
        observed_at=observed_at,
        age_hours=age_hours,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def rsi_context_adjustment(
    context: RsiTechnicalContext,
    *,
    directional_bias: object,
) -> _RsiContextAdjustment:
    """Return bounded, explainable actionability/risk deltas.

    Stale, unknown-freshness, or invalid context is fail-soft and contributes
    no score change.  A setup without measured edge cannot manufacture
    conviction: its effective conviction is capped at the registry prior and
    the adjustment remains a disclosed penalty.
    """

    if not context.valid:
        return _adjustment("invalid", reasons=("rsi_context_invalid_no_adjustment",))
    if context.freshness_status != "fresh":
        return _adjustment(
            context.freshness_status,
            reasons=(f"rsi_context_{context.freshness_status}_no_adjustment",),
        )
    if context.setup_has_edge is False:
        raw = context.conviction or 0.0
        effective = context.effective_conviction or 0.0
        cap_penalty = min(6.0, max(0.0, raw - effective) / 12.0)
        return _adjustment(
            "no_edge",
            actionability_penalty=6.0 + cap_penalty,
            risk_adjustment=8.0,
            reasons=(
                "rsi_setup_without_measured_edge",
                "rsi_no_edge_conviction_cap_applied",
            ),
        )

    radar_direction = _direction_value(directional_bias)
    if radar_direction is None or context.expected_direction is None:
        return _adjustment("neutral", reasons=("rsi_direction_compatibility_unknown",))
    if radar_direction != context.expected_direction:
        penalty = min(14.0, 6.0 + (context.effective_conviction or 0.0) * 0.08)
        return _adjustment(
            "incompatible",
            actionability_penalty=penalty,
            risk_adjustment=10.0,
            reasons=("rsi_direction_conflicts_with_radar_thesis",),
        )
    if context.market_alignment == "adverse":
        return _adjustment(
            "adverse_regime",
            actionability_penalty=5.0,
            risk_adjustment=6.0,
            reasons=("rsi_setup_market_regime_adverse",),
        )

    severity_bonus = {
        "normal": 0.0,
        "approaching": 0.5,
        "watch": 1.0,
        "alert": 2.0,
        "extreme": 3.0,
    }.get(context.rsi_severity or "normal", 0.0)
    alignment_bonus = 2.0 if context.market_alignment == "favorable" else 0.0
    bonus = min(
        12.0,
        3.0 + (context.effective_conviction or 0.0) * 0.07 + severity_bonus + alignment_bonus,
    )
    return _adjustment(
        "compatible",
        actionability_bonus=bonus,
        risk_adjustment=-4.0 if context.market_alignment == "favorable" else -2.0,
        reasons=(
            "rsi_direction_supports_radar_thesis",
            f"rsi_market_alignment_{context.market_alignment}",
        ),
    )


def apply_rsi_technical_context(
    candidate: Mapping[str, Any],
    artifact: Mapping[str, Any] | None,
    *,
    evaluated_at: datetime | str | None = None,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
) -> dict[str, Any]:
    """Return a copied candidate with normalized RSI context and shadow deltas."""

    context = normalize_rsi_signal_artifact(
        artifact,
        evaluated_at=evaluated_at,
        max_age_hours=max_age_hours,
    )
    candidate_symbol = str(candidate.get("symbol") or candidate.get("asset_symbol") or "").strip().upper()
    candidate_coin_id = str(candidate.get("coin_id") or candidate.get("asset_coin_id") or "").strip().casefold()
    identity_matches = bool(
        (context.symbol and candidate_symbol and context.symbol == candidate_symbol)
        or (context.coin_id and candidate_coin_id and context.coin_id == candidate_coin_id)
    )
    identity_conflicts = bool(
        context.symbol
        and candidate_symbol
        and context.symbol != candidate_symbol
        or context.coin_id
        and candidate_coin_id
        and context.coin_id != candidate_coin_id
    )
    if not identity_matches or identity_conflicts:
        context = replace(
            context,
            valid=False,
            warnings=tuple(
                dict.fromkeys((*context.warnings, "rsi_asset_identity_mismatch"))
            ),
        )
    bias = candidate.get("directional_bias") or candidate.get("bias") or candidate.get("direction")
    adjustment = rsi_context_adjustment(context, directional_bias=bias)
    out = dict(candidate)
    context_row = context.to_dict()
    adjustment_row = adjustment.to_dict()
    out.update(
        {
            "rsi_context": context_row,
            "rsi_context_version": context.context_version,
            "rsi_context_valid": context.valid,
            "rsi_setup_type": context.setup_type,
            "rsi_severity": context.rsi_severity,
            "rsi_value": context.rsi_value,
            "rsi_market_regime": context.market_regime,
            "rsi_conviction": context.conviction,
            "rsi_effective_conviction": context.effective_conviction,
            "rsi_conviction_cap": context.conviction_cap,
            "rsi_setup_edge_prior": context.setup_edge_prior,
            "rsi_setup_has_edge": context.setup_has_edge,
            "rsi_expected_direction": context.expected_direction,
            "rsi_freshness_status": context.freshness_status,
            "rsi_context_compatibility": adjustment.compatibility,
            "rsi_actionability_adjustment": adjustment.actionability_adjustment,
            "rsi_risk_adjustment": adjustment.risk_adjustment,
            "rsi_actionability_bonus": adjustment.actionability_bonus,
            "rsi_actionability_penalty": adjustment.actionability_penalty,
            "rsi_adjustment_reason_codes": list(adjustment.reason_codes),
            "rsi_context_adjustment": adjustment_row,
            "rsi_context_safety": {
                "read_only": True,
                "provider_calls": 0,
                "alerts_created": 0,
                "trades_created": 0,
                "paper_trades_created": 0,
                "normal_rsi_signal_rows_written": 0,
                "triggered_fade_created": 0,
            },
        }
    )
    base_actionability = _bounded_number(
        candidate.get("actionability_score"),
        minimum=0.0,
        maximum=100.0,
    )
    base_risk = _bounded_number(candidate.get("risk_score"), minimum=0.0, maximum=100.0)
    if base_actionability is not None:
        out["rsi_adjusted_actionability_score"] = _clamp(
            base_actionability + adjustment.actionability_adjustment
        )
    if base_risk is not None:
        out["rsi_adjusted_risk_score"] = _clamp(base_risk + adjustment.risk_adjustment)
    return out


def validated_rsi_score_adjustments(
    candidate: Mapping[str, Any],
) -> tuple[float, float, tuple[str, ...]]:
    """Return coherent adapter deltas for canonical pure evaluation.

    Callers must not trust free-standing scalar fields.  This gate requires
    the complete read-only safety attestation, matching nested/top-level
    adapter output, bounded deltas, fresh valid context, and reason codes.
    Malformed or partial context contributes no score change.
    """

    if candidate.get("rsi_context_version") != RSI_TECHNICAL_CONTEXT_VERSION:
        return 0.0, 0.0, ()
    context = candidate.get("rsi_context")
    adjustment = candidate.get("rsi_context_adjustment")
    safety = candidate.get("rsi_context_safety")
    if not all(isinstance(value, Mapping) for value in (context, adjustment, safety)):
        return 0.0, 0.0, ()
    if (
        context.get("context_version") != RSI_TECHNICAL_CONTEXT_VERSION
        or context.get("valid") is not True
        or context.get("freshness_status") != "fresh"
        or safety.get("read_only") is not True
    ):
        return 0.0, 0.0, ()
    for field in (
        "provider_calls",
        "alerts_created",
        "trades_created",
        "paper_trades_created",
        "normal_rsi_signal_rows_written",
        "triggered_fade_created",
    ):
        if safety.get(field) != 0 or isinstance(safety.get(field), bool):
            return 0.0, 0.0, ()
    actionability = _finite_number(candidate.get("rsi_actionability_adjustment"))
    risk = _finite_number(candidate.get("rsi_risk_adjustment"))
    nested_actionability = _finite_number(adjustment.get("actionability_adjustment"))
    nested_risk = _finite_number(adjustment.get("risk_adjustment"))
    if (
        actionability is None
        or risk is None
        or nested_actionability != actionability
        or nested_risk != risk
        or not -15.0 <= actionability <= 12.0
        or not -8.0 <= risk <= 15.0
    ):
        return 0.0, 0.0, ()
    reasons = adjustment.get("reason_codes")
    top_reasons = candidate.get("rsi_adjustment_reason_codes")
    if (
        not isinstance(reasons, list)
        or not reasons
        or not all(isinstance(item, str) and item for item in reasons)
        or top_reasons != reasons
    ):
        return 0.0, 0.0, ()
    return round(actionability, 2), round(risk, 2), tuple(dict.fromkeys(reasons))


def _adjustment(
    compatibility: str,
    *,
    actionability_bonus: float = 0.0,
    actionability_penalty: float = 0.0,
    risk_adjustment: float = 0.0,
    reasons: tuple[str, ...],
) -> _RsiContextAdjustment:
    bonus = round(max(0.0, min(12.0, float(actionability_bonus))), 2)
    penalty = round(max(0.0, min(15.0, float(actionability_penalty))), 2)
    return _RsiContextAdjustment(
        compatibility=compatibility,
        actionability_adjustment=round(bonus - penalty, 2),
        risk_adjustment=round(max(-8.0, min(15.0, float(risk_adjustment))), 2),
        actionability_bonus=bonus,
        actionability_penalty=penalty,
        reason_codes=tuple(dict.fromkeys(reasons)),
    )


def _freshness(
    row: Mapping[str, Any],
    *,
    evaluated_at: datetime | str | None,
    max_age_hours: float,
) -> tuple[str, str | None, float | None, tuple[str, ...]]:
    warnings: list[str] = []
    explicit_raw, _explicit_field = _first_present(row, _FRESHNESS_FIELDS)
    explicit = str(explicit_raw or "").strip().casefold()
    if explicit and explicit not in _FRESH | _STALE | _INVALID_FRESHNESS | {"unknown", "missing"}:
        warnings.append("rsi_freshness_status_invalid")
        explicit = "invalid"

    timestamp_raw, _timestamp_field = _first_present(row, _TIMESTAMP_FIELDS)
    observed = _parse_aware_timestamp(timestamp_raw)
    if timestamp_raw not in (None, "") and observed is None:
        warnings.append("rsi_timestamp_invalid")
    evaluated = _parse_aware_timestamp(evaluated_at)
    if evaluated_at not in (None, "") and evaluated is None:
        warnings.append("rsi_evaluated_at_invalid")
    try:
        max_age = float(max_age_hours)
    except (TypeError, ValueError):
        max_age = -1.0
    if not math.isfinite(max_age) or max_age <= 0:
        warnings.append("rsi_max_age_invalid")

    age_hours: float | None = None
    derived = "unknown"
    if observed is not None and evaluated is not None and max_age > 0:
        age_hours = round((evaluated - observed).total_seconds() / 3600.0, 4)
        if age_hours < -(5.0 / 60.0):
            derived = "invalid"
            warnings.append("rsi_timestamp_in_future")
        elif age_hours > max_age:
            derived = "stale"
        else:
            derived = "fresh"
    elif observed is not None and evaluated is None:
        derived = "unknown"

    if explicit in _INVALID_FRESHNESS:
        warnings.append("rsi_freshness_invalid")
        status = "invalid"
    elif explicit in _STALE:
        status = "stale"
    elif derived in {"invalid", "stale"}:
        status = derived
    elif explicit in _FRESH and derived == "fresh":
        status = "fresh"
    elif derived == "fresh":
        status = "fresh"
    else:
        status = "unknown"
    return (
        status,
        observed.isoformat() if observed is not None else None,
        age_hours,
        tuple(dict.fromkeys(warnings)),
    )


def _first_present(row: Mapping[str, Any], fields: tuple[str, ...]) -> tuple[Any, str | None]:
    for field in fields:
        if field in row:
            return row.get(field), field
    return None, None


def _bounded_number(value: object, *, minimum: float, maximum: float) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < minimum or number > maximum:
        return None
    return round(number, 4)


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _severity_from_value(value: float | None) -> str | None:
    if value is None:
        return None
    distance = abs(value - 50.0)
    if distance >= 35.0:
        return "extreme"
    if distance >= 25.0:
        return "alert"
    if distance >= 20.0:
        return "watch"
    return "normal"


def _direction_value(value: object) -> str | None:
    text = str(value or "").strip().casefold()
    if text in {"up", "long", "bull", "bullish", "trend_continuation", "dip_buy"}:
        return "up"
    if text in {
        "down",
        "short",
        "bear",
        "bearish",
        "fade_short_review",
        "risk",
        "risk_watch",
        "breakdown_risk",
    }:
        return "down"
    return None


def _rsi_timeframe(field: str | None) -> str | None:
    return {
        "rsi_value": "unspecified",
        "rsi_daily": "1d",
        "rsi_1d": "1d",
        "rsi_4h": "4h",
        "rsi_weekly": "1w",
    }.get(field or "")


def _parse_aware_timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)


__all__ = (
    "DEFAULT_MAX_AGE_HOURS",
    "RSI_TECHNICAL_CONTEXT_VERSION",
    "RsiTechnicalContext",
    "apply_rsi_technical_context",
    "normalize_rsi_signal_artifact",
    "rsi_context_adjustment",
    "validated_rsi_score_adjustments",
)
