"""Research-only market anomaly discovery for the event alpha radar."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

import crypto_rsi_scanner.event_alpha.radar.market_enrichment as event_market_enrichment
from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent


@dataclass(frozen=True)
class EventAnomalyScannerConfig:
    enabled: bool = False
    min_return_24h: float = 0.30
    min_volume_mcap: float = 0.25
    min_volume_zscore: float = 3.0
    max_assets: int = 50


def discover_market_anomalies(
    market_rows: Iterable[Mapping[str, Any]],
    *,
    cfg: EventAnomalyScannerConfig | None = None,
    now: datetime | None = None,
) -> tuple[RawDiscoveredEvent, ...]:
    """Convert hot market rows into low-authority research raw events."""
    cfg = cfg or EventAnomalyScannerConfig()
    if not cfg.enabled:
        return ()
    observed_at = _as_utc(now or datetime.now(timezone.utc))
    candidates: list[tuple[float, Mapping[str, Any], dict[str, Any], tuple[str, ...]]] = []
    for row in market_rows:
        snapshot = event_market_enrichment.market_snapshot_from_row(row, now=observed_at)
        reasons = _anomaly_reasons(row, snapshot, cfg)
        if not reasons:
            continue
        score = _anomaly_score(row, snapshot, cfg)
        candidates.append((score, row, snapshot, reasons))
    candidates.sort(key=lambda item: item[0], reverse=True)
    out: list[RawDiscoveredEvent] = []
    for score, row, snapshot, reasons in candidates[: max(0, cfg.max_assets)]:
        out.append(_raw_event_from_anomaly(row, snapshot, reasons, score, observed_at))
    return tuple(out)


def _anomaly_reasons(
    row: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    cfg: EventAnomalyScannerConfig,
) -> tuple[str, ...]:
    reasons: list[str] = []
    r24 = snapshot.get("return_24h")
    if isinstance(r24, (int, float)) and r24 >= cfg.min_return_24h:
        reasons.append(f"24h return {r24:.1%}")
    volume_mcap = event_market_enrichment.volume_to_market_cap(row)
    if volume_mcap is not None and volume_mcap >= cfg.min_volume_mcap:
        reasons.append(f"volume/mcap {volume_mcap:.2f}")
    vz = snapshot.get("volume_zscore_24h")
    if isinstance(vz, (int, float)) and vz >= cfg.min_volume_zscore:
        reasons.append(f"volume z-score {vz:.1f}")
    return tuple(reasons)


def _anomaly_score(
    row: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    cfg: EventAnomalyScannerConfig,
) -> float:
    r24 = max(0.0, float(snapshot.get("return_24h") or 0.0))
    r7 = max(0.0, float(snapshot.get("return_7d") or 0.0))
    volume_mcap = max(0.0, float(event_market_enrichment.volume_to_market_cap(row) or 0.0))
    vz = max(0.0, float(snapshot.get("volume_zscore_24h") or 0.0))
    return (
        min(1.0, r24 / max(cfg.min_return_24h, 0.01)) * 45
        + min(1.0, r7 / max(cfg.min_return_24h * 2, 0.01)) * 15
        + min(1.0, volume_mcap / max(cfg.min_volume_mcap, 0.01)) * 25
        + min(1.0, vz / max(cfg.min_volume_zscore, 0.1)) * 15
    )


def _raw_event_from_anomaly(
    row: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    reasons: tuple[str, ...],
    score: float,
    observed_at: datetime,
) -> RawDiscoveredEvent:
    symbol = str(snapshot.get("symbol") or row.get("symbol") or "").upper()
    coin_id = str(snapshot.get("coin_id") or row.get("id") or "")
    name = str(row.get("name") or coin_id or symbol)
    title = f"{symbol or name} market anomaly: {', '.join(reasons)}"
    body = (
        f"{name} ({symbol}) matched market-anomaly research filters: {', '.join(reasons)}. "
        "No dated external catalyst has been validated; keep as radar/store-only until source evidence exists."
    )
    payload = {
        "event": {
            "event_id": f"market_anomaly:{coin_id or symbol}:{observed_at.date().isoformat()}",
            "event_name": title,
            "event_type": "market_anomaly",
            "event_time": None,
            "event_time_confidence": 0.0,
            "external_asset": None,
            "confidence": min(0.75, 0.35 + score / 200),
            "description": body,
        },
        "market": snapshot,
        "anomaly": {
            "score": round(score, 2),
            "reasons": list(reasons),
            "research_only": True,
            "requires_catalyst_evidence": True,
        },
    }
    raw_payload = {
        "raw_id": payload["event"]["event_id"],
        "provider": "market_anomaly",
        "fetched_at": observed_at.isoformat(),
        "published_at": observed_at.isoformat(),
        "source_url": None,
        "title": title,
        "body": body,
        "source_confidence": 0.55,
        **payload,
    }
    return RawDiscoveredEvent(
        raw_id=str(payload["event"]["event_id"]),
        provider="market_anomaly",
        fetched_at=observed_at,
        published_at=observed_at,
        source_url=None,
        title=title,
        body=body,
        raw_json=raw_payload,
        source_confidence=0.55,
        content_hash=_content_hash(raw_payload),
    )


def _content_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
