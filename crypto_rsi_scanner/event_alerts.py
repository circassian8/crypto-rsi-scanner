"""Research-only alert ranking for event-discovery candidates.

This layer surfaces manageable event-fade research candidates. It does not
write live signal rows, open paper trades, or imply execution.
"""

from __future__ import annotations

import html
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable

from . import event_fade
from .event_classification import (
    ROLE_DIRECT_BENEFICIARY,
    ROLE_INFRASTRUCTURE,
    ROLE_MENTIONED_ASSET,
    ROLE_PROXY_VENUE,
    ROLE_TICKER_WORD_COLLISION,
)
from .event_models import DiscoveredEventFadeCandidate, EventDiscoveryResult
from .event_resolver import SOURCE_PUBLISHER_NAMES, clean_text, is_market_recap_event


class EventAlertTier(str, Enum):
    STORE_ONLY = "STORE_ONLY"
    RADAR_DIGEST = "RADAR_DIGEST"
    WATCHLIST = "WATCHLIST"
    HIGH_PRIORITY_WATCH = "HIGH_PRIORITY_WATCH"
    TRIGGERED_FADE = "TRIGGERED_FADE"


@dataclass(frozen=True)
class EventAlertConfig:
    enabled: bool = False
    mode: str = "research_only"
    min_digest_score: int = 55
    min_watchlist_score: int = 70
    min_high_priority_score: int = 80
    max_digest_items: int = 10
    max_instant_per_day: int = 3
    cooldown_hours: float = 12.0
    allow_proxy_venue: bool = False


@dataclass(frozen=True)
class EventAlertCandidate:
    discovery_candidate: DiscoveredEventFadeCandidate
    tier: EventAlertTier
    opportunity_score: int
    score_components: dict[str, int] = field(default_factory=dict)
    reason: str = ""
    verify: tuple[str, ...] = ()
    rejected_reason: str | None = None

    @property
    def symbol(self) -> str:
        return self.discovery_candidate.asset.symbol

    @property
    def coin_id(self) -> str:
        return self.discovery_candidate.asset.coin_id

    @property
    def event_name(self) -> str:
        return self.discovery_candidate.event.event_name

    @property
    def external_asset(self) -> str | None:
        return self.discovery_candidate.event.external_asset

    @property
    def asset_role(self) -> str:
        return self.discovery_candidate.classification.asset_role

    @property
    def source(self) -> str:
        return self.discovery_candidate.event.source


def build_event_alert_candidates(
    result: EventDiscoveryResult,
    *,
    cfg: EventAlertConfig | None = None,
    now: datetime | None = None,
) -> list[EventAlertCandidate]:
    cfg = cfg or EventAlertConfig()
    now = _as_utc(now or datetime.now(timezone.utc))
    alerts = [_build_alert_candidate(candidate, cfg, now) for candidate in result.candidates]
    return sorted(alerts, key=_alert_sort_key)


def digest_candidates(
    alerts: Iterable[EventAlertCandidate],
    *,
    cfg: EventAlertConfig | None = None,
) -> list[EventAlertCandidate]:
    cfg = cfg or EventAlertConfig()
    keep = [alert for alert in alerts if alert.tier != EventAlertTier.STORE_ONLY]
    return sorted(keep, key=_alert_sort_key)[: max(0, cfg.max_digest_items)]


def format_event_alert_report(alerts: Iterable[EventAlertCandidate]) -> str:
    rows = [
        "=" * 76,
        "EVENT RESEARCH ALERT REPORT (research-only; not trade signals)",
        "=" * 76,
    ]
    alerts = list(alerts)
    rows.append(f"Candidates: {len(alerts)}")
    rows.append("")
    if not alerts:
        rows.append("No event-alert candidates.")
        return "\n".join(rows)
    for alert in alerts:
        c = alert.discovery_candidate
        event_time = c.event.event_time.isoformat() if c.event.event_time else "unknown"
        source_url = c.event.source_urls[0] if c.event.source_urls else "none"
        rows.append(
            f"{alert.tier.value:<20} score={alert.opportunity_score:>3} "
            f"{alert.symbol}/{alert.coin_id}"
        )
        rows.append(f"  event: {alert.event_name}")
        rows.append(
            f"  external: {alert.external_asset or 'unknown'} · role: {alert.asset_role} · "
            f"relationship: {c.classification.relationship_type}"
        )
        rows.append(f"  source: {alert.source} · time: {event_time} · url: {source_url}")
        rows.append(f"  reason: {alert.reason}")
        rows.append(f"  what user should verify: {'; '.join(alert.verify)}")
        if alert.rejected_reason:
            rows.append(f"  rejected: {alert.rejected_reason}")
        rows.append(
            "  components: "
            + ", ".join(f"{name}={value}" for name, value in alert.score_components.items())
        )
        rows.append("")
    return "\n".join(rows).rstrip()


def format_event_alert_telegram_digest(alerts: Iterable[EventAlertCandidate]) -> str:
    keep = list(alerts)
    lines = [
        "<b>Event research alerts</b>",
        "<i>Research alert only. Not a trade signal, not paper trading, not execution.</i>",
    ]
    if not keep:
        lines.append("No research candidates above the digest threshold.")
        return "\n".join(lines)
    for alert in keep:
        c = alert.discovery_candidate
        lines.append("")
        lines.append(
            f"<b>{_esc(alert.tier.value)}</b> score={alert.opportunity_score} "
            f"<b>{_esc(alert.symbol)}</b>"
        )
        lines.append(f"{_esc(alert.event_name)}")
        lines.append(
            f"external={_esc(alert.external_asset or 'unknown')} "
            f"role={_esc(alert.asset_role)} rel={_esc(c.classification.relationship_type)}"
        )
        lines.append(f"verify: {_esc('; '.join(alert.verify))}")
    return "\n".join(lines)


def _build_alert_candidate(
    candidate: DiscoveredEventFadeCandidate,
    cfg: EventAlertConfig,
    now: datetime,
) -> EventAlertCandidate:
    components = _score_components(candidate, now)
    score = _weighted_score(components)
    rejected = _rejected_reason(candidate, cfg)
    tier = _tier(candidate, cfg, score, components, rejected)
    reason = _reason(candidate, tier, components)
    verify = _verify_items(candidate, tier)
    return EventAlertCandidate(
        discovery_candidate=candidate,
        tier=tier,
        opportunity_score=score,
        score_components=components,
        reason=reason,
        verify=verify,
        rejected_reason=rejected,
    )


def _score_components(candidate: DiscoveredEventFadeCandidate, now: datetime) -> dict[str, int]:
    cls = candidate.classification
    event = candidate.event
    fade_candidate = candidate.fade_candidate
    signal = candidate.fade_signal
    source_quality = event.confidence * 100
    source_quality += min(10, max(0, len(event.raw_ids) - 1) * 5)
    if is_market_recap_event(event):
        source_quality -= 25
    return {
        "asset_resolution": _clamp(candidate.link.link_confidence * 100),
        "proxy_relationship": _proxy_quality(candidate),
        "external_catalyst": _external_catalyst_quality(candidate),
        "market_move_volume": _market_move_quality(fade_candidate),
        "source_quality": _clamp(source_quality),
        "derivatives_crowding": _derivatives_quality(fade_candidate),
        "event_time_quality": _clamp((event.event_time_confidence if event.event_time else 0.0) * 100),
        "novelty_freshness": _novelty_quality(event.first_seen_time, now, len(event.raw_ids)),
        "fade_score": _clamp(signal.fade_score if signal else 0),
        "classifier": _clamp(cls.confidence * 100),
    }


def _weighted_score(components: dict[str, int]) -> int:
    return _clamp(
        components["asset_resolution"] * 0.20
        + components["proxy_relationship"] * 0.20
        + components["external_catalyst"] * 0.15
        + components["market_move_volume"] * 0.15
        + components["source_quality"] * 0.10
        + components["derivatives_crowding"] * 0.10
        + components["event_time_quality"] * 0.05
        + components["novelty_freshness"] * 0.05
    )


def _tier(
    candidate: DiscoveredEventFadeCandidate,
    cfg: EventAlertConfig,
    score: int,
    components: dict[str, int],
    rejected: str | None,
) -> EventAlertTier:
    signal_type = candidate.fade_signal.signal_type if candidate.fade_signal else event_fade.FadeSignalType.NO_TRADE
    if rejected:
        return EventAlertTier.STORE_ONLY
    if signal_type == event_fade.FadeSignalType.SHORT_TRIGGERED:
        return EventAlertTier.TRIGGERED_FADE
    if score < cfg.min_digest_score:
        return EventAlertTier.STORE_ONLY
    if candidate.classification.asset_role == ROLE_PROXY_VENUE and not cfg.allow_proxy_venue:
        return EventAlertTier.RADAR_DIGEST
    if (
        score >= cfg.min_high_priority_score
        and (
            components["event_time_quality"] >= 80
            or components["derivatives_crowding"] >= 70
        )
    ):
        return EventAlertTier.HIGH_PRIORITY_WATCH
    if score >= cfg.min_watchlist_score and components["market_move_volume"] >= 40:
        return EventAlertTier.WATCHLIST
    return EventAlertTier.RADAR_DIGEST


def _rejected_reason(candidate: DiscoveredEventFadeCandidate, cfg: EventAlertConfig) -> str | None:
    cls = candidate.classification
    reasons: list[str] = []
    if cls.is_direct_beneficiary or cls.asset_role == ROLE_DIRECT_BENEFICIARY:
        reasons.append("direct beneficiary")
    if cls.relationship_type == "ambiguous" or not cls.is_proxy_narrative:
        reasons.append("not a confirmed proxy narrative")
    if cls.asset_role in {ROLE_TICKER_WORD_COLLISION, ROLE_INFRASTRUCTURE, ROLE_MENTIONED_ASSET}:
        reasons.append(cls.asset_role)
    if candidate.link.link_confidence < 0.80:
        reasons.append("low asset-resolution confidence")
    if cls.confidence < 0.70:
        reasons.append("low classifier confidence")
    if _publisher_only_evidence(candidate):
        reasons.append("publisher/source-only asset evidence")
    if is_market_recap_event(candidate.event):
        reasons.append("market recap evidence only")
    return "; ".join(dict.fromkeys(reasons)) or None


def _proxy_quality(candidate: DiscoveredEventFadeCandidate) -> int:
    cls = candidate.classification
    if cls.is_direct_beneficiary:
        return 0
    if not cls.is_proxy_narrative:
        return min(40, _clamp(cls.confidence * 100))
    role_weight = {
        "proxy_instrument": 1.00,
        "proxy_venue": 0.70,
    }.get(cls.asset_role, 0.45)
    return _clamp(cls.confidence * 100 * role_weight)


def _external_catalyst_quality(candidate: DiscoveredEventFadeCandidate) -> int:
    event = candidate.event
    if not event.external_asset:
        return 15
    base = 65
    if event.event_type in {"ipo_proxy", "external_proxy_event", "sports_event", "political_event"}:
        base += 10
    if event.event_time is not None:
        base += 15 * event.event_time_confidence
    if candidate.classification.relationship_type == "proxy_exposure":
        base += 10
    return _clamp(base)


def _market_move_quality(candidate: event_fade.FadeCandidate | None) -> int:
    if candidate is None:
        return 0
    market = candidate.market
    returns = [
        _return_score(market.return_24h, 0.75),
        _return_score(market.return_72h, 1.50),
        _return_score(market.return_7d, 3.00),
    ]
    volume = _ratio_score(market.volume_zscore_24h, 5.0)
    if market.volume_24h and market.market_cap and market.market_cap > 0:
        volume = max(volume, _ratio_score(market.volume_24h / market.market_cap, 0.75))
    return _clamp(max(returns) * 0.65 + volume * 0.35)


def _derivatives_quality(candidate: event_fade.FadeCandidate | None) -> int:
    if candidate is None or candidate.derivatives is None:
        return 0
    d = candidate.derivatives
    values = [
        _ratio_score(d.open_interest_24h_change_pct, 0.75),
        _ratio_score(d.open_interest_to_market_cap, 0.50),
        _ratio_score(d.funding_rate_8h, 0.0010),
        _ratio_score(d.perp_spot_volume_ratio, 20.0),
        _ratio_score(d.long_short_ratio, 2.0),
    ]
    return max(values)


def _novelty_quality(first_seen: datetime | None, now: datetime, source_count: int) -> int:
    if first_seen is None:
        return 45
    hours = max(0.0, (_as_utc(now) - _as_utc(first_seen)).total_seconds() / 3600.0)
    freshness = 100 if hours <= 24 else 75 if hours <= 72 else 45 if hours <= 168 else 20
    return _clamp(freshness + min(10, max(0, source_count - 1) * 5))


def _reason(candidate: DiscoveredEventFadeCandidate, tier: EventAlertTier, components: dict[str, int]) -> str:
    if tier == EventAlertTier.TRIGGERED_FADE:
        return "Existing event-fade engine emitted SHORT_TRIGGERED; still research-only."
    if tier == EventAlertTier.STORE_ONLY:
        return "Stored for research evidence, but quality or relationship gates are not strong enough for a research alert."
    parts = [
        f"proxy={components['proxy_relationship']}",
        f"asset={components['asset_resolution']}",
        f"market={components['market_move_volume']}",
    ]
    if components["derivatives_crowding"] >= 50:
        parts.append(f"crowding={components['derivatives_crowding']}")
    if candidate.event.event_time:
        parts.append(f"time={components['event_time_quality']}")
    return "Plausible proxy-event candidate: " + ", ".join(parts) + "."


def _verify_items(candidate: DiscoveredEventFadeCandidate, tier: EventAlertTier) -> tuple[str, ...]:
    items = [
        "confirm the crypto asset is the proxy instrument, not merely venue/infrastructure",
        "confirm the external catalyst and source timestamp",
    ]
    if candidate.event.event_time is None:
        items.append("find or reject a dated catalyst before treating it as event-fade eligible")
    elif candidate.event.event_time_confidence < 0.80:
        items.append("confirm machine-inferred event time from an independent source")
    if candidate.classification.asset_role == ROLE_PROXY_VENUE:
        items.append("venue-token thesis is review-only by default")
    if tier == EventAlertTier.TRIGGERED_FADE:
        items.append("check post-event technical failure and invalidation level manually")
    return tuple(items)


def _publisher_only_evidence(candidate: DiscoveredEventFadeCandidate) -> bool:
    evidence = {clean_text(item) for item in candidate.link.evidence}
    return bool(evidence) and evidence.issubset(SOURCE_PUBLISHER_NAMES)


def _return_score(value: object, full_score_at: float) -> int:
    value = _num(value)
    if value <= 0:
        return 0
    return _ratio_score(value, full_score_at)


def _ratio_score(value: object, full_score_at: float) -> int:
    value = _num(value)
    if value <= 0 or full_score_at <= 0:
        return 0
    return _clamp((value / full_score_at) * 100)


def _num(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    return out


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> int:
    if not math.isfinite(float(value)):
        return 0
    return int(round(max(lo, min(hi, float(value)))))


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _alert_sort_key(alert: EventAlertCandidate) -> tuple[int, int, str]:
    tier_rank = {
        EventAlertTier.TRIGGERED_FADE: 0,
        EventAlertTier.HIGH_PRIORITY_WATCH: 1,
        EventAlertTier.WATCHLIST: 2,
        EventAlertTier.RADAR_DIGEST: 3,
        EventAlertTier.STORE_ONLY: 4,
    }
    return (tier_rank[alert.tier], -alert.opportunity_score, alert.symbol)


def _esc(value: object) -> str:
    return html.escape(str(value), quote=False)
