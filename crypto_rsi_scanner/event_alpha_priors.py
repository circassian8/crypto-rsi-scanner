"""Opt-in Event Alpha calibration-prior application for research alerts."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_alerts


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
    if not cfg.enabled or cfg.path is None:
        return None
    path = cfg.path.expanduser()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
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
    adjusted = apply_priors_to_alerts(data, cfg=enabled_cfg, alert_cfg=alert_cfg)
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
    before = int(alert.opportunity_score)
    multipliers = _multipliers_for(alert, priors.payload, cfg=cfg)
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
    for key in ("multiplier", "score_multiplier", "prior_multiplier"):
        value = _float(row.get(key))
        if value is not None:
            return value
    adjustment = _float(row.get("score_adjustment"))
    if adjustment is not None:
        return 1.0 + (adjustment / 100.0)
    useful = _float(row.get("useful")) or 0.0
    junk = _float(row.get("junk")) or 0.0
    if useful or junk:
        return 1.0 + max(-0.15, min(0.15, (useful - junk) / max(10.0, useful + junk) * 0.20))
    return None


def _provider(alert: event_alerts.EventAlertCandidate) -> str:
    event = alert.discovery_candidate.event
    return str(event.source or alert.source or "unknown")


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
