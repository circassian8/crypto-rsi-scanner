"""Shadow-only Event Alpha calibration-prior review for research alerts."""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
from ..artifacts import json_lines as artifact_json_lines
from . import feedback_eligibility
from .calibration import (
    CALIBRATION_PRIORS_ROW_TYPE,
    CALIBRATION_PRIORS_SCHEMA_VERSION,
    PRIOR_GROUP_NAMES,
)


PRIOR_ROW_FIELDS = frozenset(
    {
        "samples",
        "useful",
        "junk",
        "watch",
        "median_primary_horizon_return",
        "score_adjustment",
        "min_sample_warning",
    }
)
MAX_PRIOR_GROUP_KEY_CHARS = 512
PRIOR_PAYLOAD_FIELDS = frozenset(
    {
        "schema_version",
        "row_type",
        "generated_at",
        "feedback_firewall_evaluated_at",
        "feedback_firewall_applied",
        "feedback_eligibility_contract_version",
        "alert_rows_supplied",
        "feedback_rows_supplied",
        "feedback_rows_eligible",
        "feedback_rows_excluded",
        "feedback_exclusion_reason_counts",
        "min_sample",
        "min_sample_warning",
        *PRIOR_GROUP_NAMES,
        "research_only",
        "recommendation_only",
        "eligible_for_auto_apply",
        "auto_apply",
    }
)


@dataclass(frozen=True)
class EventAlphaPriorsConfig:
    enabled: bool = False
    path: Path | None = None
    min_multiplier: float = 0.70
    max_multiplier: float = 1.30


@dataclass(frozen=True)
class EventAlphaPriors:
    path: Path
    schema_version: str | None
    generated_at: str | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class EventAlphaPriorsShadowRow:
    alert_key: str
    symbol: str
    coin_id: str
    playbook: str
    tier_before: str
    tier_after: str
    score_before: int
    score_after: int
    multipliers_applied: dict[str, float]
    hard_gate: str | None = None


@dataclass(frozen=True)
class EventAlphaPriorsShadowResult:
    rows: tuple[EventAlphaPriorsShadowRow, ...]
    prior_file: str | None
    warnings: tuple[str, ...] = ()


def load_priors(cfg: EventAlphaPriorsConfig) -> EventAlphaPriors | None:
    if not _valid_config(cfg) or cfg.path is None:
        return None
    try:
        path = cfg.path.expanduser()
        if not path.exists():
            return None
        payload = artifact_json_lines.loads_no_duplicate_keys(
            path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, ValueError, RuntimeError):
        return None
    if not isinstance(payload, dict) or not prior_payload_is_valid(payload):
        return None
    return EventAlphaPriors(
        path=path,
        schema_version=str(payload.get("schema_version") or ""),
        generated_at=str(payload.get("generated_at") or ""),
        payload=payload,
    )


def apply_priors_to_alerts(
    alerts: Iterable[event_alerts.EventAlertCandidate],
    *,
    cfg: EventAlphaPriorsConfig,
    alert_cfg: event_alerts.EventAlertConfig | None = None,
) -> list[event_alerts.EventAlertCandidate]:
    """Return alerts unchanged while accepted policy keeps priors shadow-only."""

    return list(alerts)


def apply_priors_shadow(
    alerts: Iterable[event_alerts.EventAlertCandidate],
    *,
    cfg: EventAlphaPriorsConfig,
    alert_cfg: event_alerts.EventAlertConfig | None = None,
) -> list[event_alerts.EventAlertCandidate]:
    """Apply reviewed recommendation priors in memory for comparison only."""

    priors = load_priors(cfg)
    data = list(alerts)
    if priors is None:
        return data
    alert_cfg = alert_cfg or event_alerts.EventAlertConfig()
    adjusted = [
        _apply_to_alert(alert, priors, cfg=cfg, alert_cfg=alert_cfg)
        for alert in data
    ]
    return sorted(adjusted, key=lambda item: (-_tier_rank(item.tier), -item.opportunity_score, item.symbol))


def compare_priors_shadow(
    alerts: Iterable[event_alerts.EventAlertCandidate],
    *,
    cfg: EventAlphaPriorsConfig,
    alert_cfg: event_alerts.EventAlertConfig | None = None,
) -> EventAlphaPriorsShadowResult:
    """Compare Event Alpha priors in memory without writing artifacts."""
    data = list(alerts)
    enabled_cfg = EventAlphaPriorsConfig(
        enabled=True,
        path=cfg.path,
        min_multiplier=cfg.min_multiplier,
        max_multiplier=cfg.max_multiplier,
    )
    priors = load_priors(enabled_cfg)
    if priors is None:
        return EventAlphaPriorsShadowResult(
            rows=(),
            prior_file=str(cfg.path) if cfg.path else None,
            warnings=(f"priors file not found or invalid: {cfg.path}" if cfg.path else "priors path is not configured",),
        )
    adjusted = apply_priors_shadow(data, cfg=enabled_cfg, alert_cfg=alert_cfg)
    adjusted_by_key = {_alert_key(alert): alert for alert in adjusted}
    rows: list[EventAlphaPriorsShadowRow] = []
    for alert in data:
        key = _alert_key(alert)
        after = adjusted_by_key.get(key, alert)
        rows.append(EventAlphaPriorsShadowRow(
            alert_key=key,
            symbol=alert.symbol,
            coin_id=alert.coin_id,
            playbook=alert.effective_playbook_type or alert.playbook_type or "unknown",
            tier_before=alert.tier.value,
            tier_after=after.tier.value,
            score_before=alert.opportunity_score,
            score_after=after.opportunity_score,
            multipliers_applied=dict(after.prior_multipliers_applied),
            hard_gate=_hard_gate_reason(alert, after),
        ))
    return EventAlphaPriorsShadowResult(
        rows=tuple(rows),
        prior_file=str(priors.path),
        warnings=(),
    )


def format_priors_shadow_report(result: EventAlphaPriorsShadowResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA PRIORS SHADOW REPORT (research-only; no stored changes)",
        "=" * 76,
        f"prior_file: {result.prior_file or 'none'}",
        f"rows: {len(result.rows)}",
    ]
    if result.warnings:
        lines.append("warnings: " + "; ".join(result.warnings))
    if not result.rows:
        lines.append("No priors comparison rows.")
        lines.append("No sends, paper trades, live DB rows, or execution were used.")
        return "\n".join(lines)
    lines.append("")
    for row in result.rows[:50]:
        multipliers = (
            ", ".join(f"{key}={value:.3f}" for key, value in sorted(row.multipliers_applied.items()))
            if row.multipliers_applied
            else "none"
        )
        lines.append(
            f"{row.alert_key or row.symbol}: {row.symbol}/{row.coin_id} playbook={row.playbook} "
            f"tier={row.tier_before}->{row.tier_after} score={row.score_before}->{row.score_after}"
        )
        lines.append(f"  multipliers: {multipliers}")
        if row.hard_gate:
            lines.append(f"  hard_gate: {row.hard_gate}")
    lines.append("No sends, paper trades, live DB rows, or execution were used.")
    return "\n".join(lines).rstrip()


def _apply_to_alert(
    alert: event_alerts.EventAlertCandidate,
    priors: EventAlphaPriors,
    *,
    cfg: EventAlphaPriorsConfig,
    alert_cfg: event_alerts.EventAlertConfig,
) -> event_alerts.EventAlertCandidate:
    if (
        alert.tier in {
            event_alerts.EventAlertTier.TRIGGERED_FADE,
            event_alerts.EventAlertTier.STORE_ONLY,
        }
        or alert.rejected_reason
        or alert.llm_asset_role in {"source_noise", "ticker_word_collision"}
        or alert.effective_playbook_type == "source_noise_control"
    ):
        return alert
    before = int(alert.opportunity_score)
    multipliers = _multipliers_for(alert, priors.payload, cfg=cfg)
    if not multipliers:
        return alert
    combined = 1.0
    for value in multipliers.values():
        combined *= value
    combined = _clamp(combined, cfg.min_multiplier, cfg.max_multiplier)
    after = max(0, min(100, int(round(before * combined))))
    next_tier = _tier_after_priors(alert, after, alert_cfg)
    return replace(
        alert,
        opportunity_score=after,
        tier=next_tier,
        score_before_priors=before,
        score_after_priors=after,
        prior_file=str(priors.path),
        prior_version=priors.schema_version,
        prior_generated_at=priors.generated_at,
        prior_multipliers_applied=multipliers,
    )


def _alert_key(alert: event_alerts.EventAlertCandidate) -> str:
    event = alert.discovery_candidate.event
    return "|".join((
        str(event.event_id or ""),
        str(alert.coin_id or ""),
        str(alert.effective_playbook_type or alert.playbook_type or ""),
    ))


def _hard_gate_reason(
    before: event_alerts.EventAlertCandidate,
    after: event_alerts.EventAlertCandidate,
) -> str | None:
    if before.tier == event_alerts.EventAlertTier.TRIGGERED_FADE and after.tier == before.tier:
        return "triggered_fade_authoritative"
    if before.tier == event_alerts.EventAlertTier.STORE_ONLY and after.tier == before.tier:
        return before.rejected_reason or "store_only_hard_gate"
    if before.effective_playbook_type == "source_noise_control" and after.tier == event_alerts.EventAlertTier.STORE_ONLY:
        return "source_noise_control_store_only"
    return None


def _tier_after_priors(
    alert: event_alerts.EventAlertCandidate,
    score: int,
    cfg: event_alerts.EventAlertConfig,
) -> event_alerts.EventAlertTier:
    if alert.tier == event_alerts.EventAlertTier.TRIGGERED_FADE:
        return alert.tier
    if alert.rejected_reason or alert.tier == event_alerts.EventAlertTier.STORE_ONLY:
        return alert.tier
    if alert.llm_asset_role in {"source_noise", "ticker_word_collision"}:
        return event_alerts.EventAlertTier.STORE_ONLY
    if alert.effective_playbook_type == "source_noise_control":
        return event_alerts.EventAlertTier.STORE_ONLY
    if score >= cfg.min_high_priority_score:
        return event_alerts.EventAlertTier.HIGH_PRIORITY_WATCH
    if score >= cfg.min_watchlist_score:
        return event_alerts.EventAlertTier.WATCHLIST
    if score >= cfg.min_digest_score:
        return event_alerts.EventAlertTier.RADAR_DIGEST
    return event_alerts.EventAlertTier.STORE_ONLY


def _multipliers_for(
    alert: event_alerts.EventAlertCandidate,
    payload: Mapping[str, Any],
    *,
    cfg: EventAlphaPriorsConfig,
) -> dict[str, float]:
    specs = (
        ("playbook", "playbook_priors", alert.effective_playbook_type or alert.playbook_type),
        ("provider", "provider_priors", _provider(alert)),
        ("llm_role", "llm_role_priors", alert.llm_asset_role),
        ("tier", "tier_priors", alert.tier.value),
    )
    out: dict[str, float] = {}
    for label, group_name, key in specs:
        if not key:
            continue
        group = payload.get(group_name)
        if not isinstance(group, Mapping):
            continue
        row = group.get(str(key))
        if not isinstance(row, Mapping):
            continue
        multiplier = _row_multiplier(row)
        if multiplier is None:
            continue
        out[label] = _clamp(multiplier, cfg.min_multiplier, cfg.max_multiplier)
    return out


def _row_multiplier(row: Mapping[str, Any]) -> float | None:
    if row.get("min_sample_warning") is not False:
        return None
    adjustment = row.get("score_adjustment")
    if type(adjustment) is not int or adjustment == 0:
        return None
    return 1.0 + (adjustment / 100.0)


def _provider(alert: event_alerts.EventAlertCandidate) -> str:
    event = alert.discovery_candidate.event
    return str(event.source or alert.source or "unknown")


def _valid_config(cfg: EventAlphaPriorsConfig) -> bool:
    if cfg.enabled is not True or not isinstance(cfg.path, Path):
        return False
    low = _strict_finite_number(cfg.min_multiplier)
    high = _strict_finite_number(cfg.max_multiplier)
    return (
        low is not None
        and high is not None
        and 0.0 < low <= 1.0 <= high <= 2.0
    )


def prior_payload_is_valid(payload: Mapping[str, Any]) -> bool:
    """Return the exact fail-closed acceptance decision used by the loader.

    Artifact schema validation calls this public contract too, so a prior file
    cannot pass doctor validation while the runtime loader would reject it.
    """

    return _valid_prior_payload(payload)


def _valid_prior_payload(payload: Mapping[str, Any]) -> bool:
    if set(payload) != PRIOR_PAYLOAD_FIELDS:
        return False
    if (
        payload.get("schema_version") != CALIBRATION_PRIORS_SCHEMA_VERSION
        or payload.get("row_type") != CALIBRATION_PRIORS_ROW_TYPE
        or payload.get("research_only") is not True
        or payload.get("recommendation_only") is not True
        or payload.get("feedback_firewall_applied") is not True
        or payload.get("feedback_eligibility_contract_version")
        != feedback_eligibility.FEEDBACK_ELIGIBILITY_CONTRACT_VERSION
        or type(payload.get("eligible_for_auto_apply")) is not bool
        or payload.get("auto_apply") is not False
    ):
        return False

    generated_at = _valid_timestamp(payload.get("generated_at"))
    evaluated_at = _valid_timestamp(payload.get("feedback_firewall_evaluated_at"))
    if generated_at is None or evaluated_at is None or generated_at < evaluated_at:
        return False

    min_sample = payload.get("min_sample")
    if type(min_sample) is not int or min_sample < 1:
        return False
    telemetry_names = (
        "alert_rows_supplied",
        "feedback_rows_supplied",
        "feedback_rows_eligible",
        "feedback_rows_excluded",
    )
    if any(
        type(payload.get(name)) is not int or payload.get(name) < 0
        for name in telemetry_names
    ):
        return False
    supplied = payload["feedback_rows_supplied"]
    eligible = payload["feedback_rows_eligible"]
    excluded = payload["feedback_rows_excluded"]
    if supplied != eligible + excluded:
        return False
    if payload.get("min_sample_warning") is not (eligible < min_sample):
        return False
    if not _valid_exclusion_counts(
        payload.get("feedback_exclusion_reason_counts"),
        excluded=excluded,
    ):
        return False

    has_adjustment = False
    for group_name in PRIOR_GROUP_NAMES:
        group = payload.get(group_name)
        if not _valid_prior_group(group, min_sample=min_sample, expected_samples=eligible):
            return False
        has_adjustment |= any(
            row["score_adjustment"] != 0
            for row in group.values()
        )
    return payload.get("eligible_for_auto_apply") is has_adjustment


def _valid_prior_group(
    value: Any,
    *,
    min_sample: int,
    expected_samples: int,
) -> bool:
    if not isinstance(value, Mapping):
        return False
    samples_seen = 0
    for key, row in value.items():
        if not _safe_group_key(key) or not isinstance(row, Mapping):
            return False
        if set(row) != PRIOR_ROW_FIELDS:
            return False
        counts = tuple(row.get(name) for name in ("samples", "useful", "junk", "watch"))
        if any(type(count) is not int or count < 0 for count in counts):
            return False
        samples, useful, junk, watch = counts
        if useful + junk + watch > samples:
            return False
        warning = row.get("min_sample_warning")
        if type(warning) is not bool or warning is not (samples < min_sample):
            return False
        median_return = row.get("median_primary_horizon_return")
        if median_return is not None and _strict_finite_number(median_return) is None:
            return False
        adjustment = row.get("score_adjustment")
        if type(adjustment) is not int:
            return False
        expected_adjustment = 0
        if key != "unknown" and samples >= min_sample:
            if useful > junk and useful >= 2:
                expected_adjustment = 3
            elif junk > useful and junk >= 2:
                expected_adjustment = -5
        if adjustment != expected_adjustment:
            return False
        samples_seen += samples
    return samples_seen == expected_samples


def _valid_exclusion_counts(value: Any, *, excluded: int) -> bool:
    if not isinstance(value, Mapping):
        return False
    total = 0
    for reason, count in value.items():
        if (
            type(reason) is not str
            or reason not in feedback_eligibility.FEEDBACK_INELIGIBLE_REASONS
            or type(count) is not int
            or count < 1
            or count > excluded
        ):
            return False
        total += count
    return (total == 0) if excluded == 0 else (total >= excluded)


def _valid_timestamp(value: Any) -> datetime | None:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or unicodedata.normalize("NFC", value) != value
        or any(unicodedata.category(character).startswith("C") for character in value)
    ):
        return None
    parsed = feedback_eligibility.parse_aware_feedback_time(value)
    if parsed is None:
        return None
    # UTC conversion can raise on platform-edge datetime values.  Keep loading
    # fail-closed even when a hand-edited artifact contains one.
    try:
        parsed.astimezone(timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
    if parsed.isoformat() != value:
        return None
    return parsed


def _safe_group_key(value: Any) -> bool:
    return (
        type(value) is str
        and bool(value)
        and len(value) <= MAX_PRIOR_GROUP_KEY_CHARS
        and value == value.strip()
        and unicodedata.normalize("NFC", value) == value
        and not any(unicodedata.category(character).startswith("C") for character in value)
    )


def _strict_finite_number(value: Any) -> float | None:
    if type(value) not in (int, float):
        return None
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _tier_rank(tier: event_alerts.EventAlertTier) -> int:
    ranks = {
        event_alerts.EventAlertTier.TRIGGERED_FADE: 4,
        event_alerts.EventAlertTier.HIGH_PRIORITY_WATCH: 3,
        event_alerts.EventAlertTier.WATCHLIST: 2,
        event_alerts.EventAlertTier.RADAR_DIGEST: 1,
        event_alerts.EventAlertTier.STORE_ONLY: 0,
    }
    return ranks.get(tier, 0)
