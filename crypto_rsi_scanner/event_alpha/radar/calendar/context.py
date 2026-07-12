"""Pure calendar-risk context for Crypto Radar research ideas.

This module only annotates in-memory mappings.  It does not fetch calendars,
write artifacts, route notifications, or create trading state.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any


_GLOBAL_ASSETS = frozenset({"ALL", "CRYPTO", "CRYPTO_MARKET", "MARKET_WIDE"})
_IMPORTANCE_RISK = {"low": 4.0, "medium": 8.0, "high": 14.0, "critical": 20.0}


def overlay_calendar_context(
    candidate: Mapping[str, Any],
    events: Iterable[Mapping[str, Any]],
    *,
    now: datetime | str,
) -> dict[str, Any]:
    """Return a candidate copy annotated with nearby, asset-relevant events.

    Calendar context may add risk and cap an idea's lifetime, but it never
    manufactures a directional bias or changes legacy Event Alpha lanes.
    """

    observed = _as_utc(_parse_time(now))
    symbol = str(candidate.get("symbol") or candidate.get("asset_symbol") or "").upper()
    coin_id = str(candidate.get("coin_id") or candidate.get("asset_coin_id") or "").upper()
    matched: list[dict[str, Any]] = []
    expiries: list[datetime] = []
    for raw in events:
        if not isinstance(raw, Mapping) or not _matches_asset(raw, symbol=symbol, coin_id=coin_id):
            continue
        bounds = _impact_bounds(raw)
        if bounds is None:
            continue
        impact_start, event_start, event_end, impact_end = bounds
        if not impact_start <= observed <= impact_end:
            continue
        if event_start >= observed:
            expiries.append(event_start)
        matched.append(
            {
                "calendar_event_id": str(raw.get("calendar_event_id") or raw.get("event_id") or ""),
                "title": str(raw.get("title") or raw.get("event_name") or "scheduled event"),
                "event_kind": str(raw.get("event_kind") or "unknown"),
                "importance": str(raw.get("importance") or "medium"),
                "scheduled_at": raw.get("scheduled_at"),
                "window_start": raw.get("window_start"),
                "window_end": raw.get("window_end"),
                "impact_window_before": str(raw.get("impact_window_before") or "24h"),
                "impact_window_after": str(raw.get("impact_window_after") or "4h"),
                "source": str(raw.get("source") or "calendar"),
                "source_url": str(raw.get("source_url") or ""),
            }
        )
    if not matched:
        return dict(candidate)

    out = dict(candidate)
    matched.sort(key=lambda row: str(row.get("scheduled_at") or row.get("window_start") or ""))
    risk_points = min(
        30.0,
        sum(_IMPORTANCE_RISK.get(str(row.get("importance") or "medium").casefold(), 8.0) for row in matched),
    )
    existing_warnings = _items(out.get("decision_warnings"))
    warning = f"nearby_calendar_risk:{','.join(row['event_kind'] for row in matched)}"
    out.update(
        {
            "calendar_event_attached": True,
            "calendar_context_count": len(matched),
            "unified_calendar_context": matched,
            "nearby_calendar_events": matched,
            "calendar_risk_score_adjustment": risk_points,
            "calendar_context_warning": warning,
            "decision_warnings": list(dict.fromkeys((*existing_warnings, warning))),
        }
    )
    if expiries:
        expiry_cap = min(expiries).isoformat()
        current_expiry = _parse_optional_time(out.get("expires_at"))
        if current_expiry is None or min(expiries) < current_expiry:
            out["expires_at"] = expiry_cap
        out["calendar_expiry_cap"] = expiry_cap
    return out


def overlay_calendar_context_rows(
    candidates: Iterable[Mapping[str, Any]],
    events: Iterable[Mapping[str, Any]],
    *,
    now: datetime | str,
) -> tuple[dict[str, Any], ...]:
    materialized_events = tuple(dict(row) for row in events if isinstance(row, Mapping))
    return tuple(
        overlay_calendar_context(row, materialized_events, now=now)
        for row in candidates
        if isinstance(row, Mapping)
    )


def _impact_bounds(row: Mapping[str, Any]) -> tuple[datetime, datetime, datetime, datetime] | None:
    scheduled = _parse_optional_time(row.get("scheduled_at"))
    window_start = _parse_optional_time(row.get("window_start"))
    window_end = _parse_optional_time(row.get("window_end"))
    event_start = scheduled or window_start
    event_end = scheduled or window_end or event_start
    if event_start is None or event_end is None:
        return None
    before = _duration(str(row.get("impact_window_before") or "24h"))
    after = _duration(str(row.get("impact_window_after") or "4h"))
    if before is None or after is None:
        return None
    return event_start - before, event_start, event_end, event_end + after


def _matches_asset(row: Mapping[str, Any], *, symbol: str, coin_id: str) -> bool:
    raw_assets = row.get("affected_assets") or ()
    if isinstance(raw_assets, str):
        raw_assets = (raw_assets,)
    if not isinstance(raw_assets, Iterable) or isinstance(raw_assets, (bytes, Mapping)):
        return False
    assets = {str(value).strip().upper().replace(" ", "_") for value in raw_assets if str(value).strip()}
    return bool(assets & _GLOBAL_ASSETS or symbol and symbol in assets or coin_id and coin_id in assets)


def _duration(value: str) -> timedelta | None:
    text = value.strip().casefold()
    if len(text) < 2:
        return None
    try:
        amount = int(text[:-1])
    except ValueError:
        return None
    if amount <= 0:
        return None
    factors = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
    seconds = factors.get(text[-1])
    return timedelta(seconds=amount * seconds) if seconds else None


def _parse_time(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    return _as_utc(parsed)


def _parse_optional_time(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return _parse_time(str(value))
    except (TypeError, ValueError):
        return None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _items(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return tuple(item.strip() for item in value.replace(";", ",").split(",") if item.strip())
    if isinstance(value, Iterable) and not isinstance(value, (bytes, Mapping)):
        return tuple(str(item) for item in value if str(item))
    return ()


__all__ = ("overlay_calendar_context", "overlay_calendar_context_rows")
