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
