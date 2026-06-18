"""Missed-opportunity diagnostics for Event Alpha Radar."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_identity, event_market_enrichment, event_watchlist
from .event_models import RawDiscoveredEvent


MISSED_SCHEMA_VERSION = "event_alpha_missed_v1"

FAILURE_STAGES = (
    "outside_universe",
    "no_source_event",
    "no_catalyst_search_result",
    "resolver_missed_asset",
    "llm_classified_noise",
    "low_score_suppressed",
    "watchlist_not_escalated",
    "provider_disabled",
    "unknown",
)


@dataclass(frozen=True)
class MissedOpportunity:
    schema_version: str
    row_type: str
    symbol: str
    coin_id: str
    name: str
    move_window: str
    return_pct: float
    failure_stage: str
    reason: str
    suggested_queries: tuple[str, ...]


@dataclass(frozen=True)
class MissedOpportunityResult:
    rows: list[MissedOpportunity]
    market_rows: int
    alert_rows: int
    watchlist_entries: int


def detect_missed_opportunities(
    market_rows: Iterable[Mapping[str, Any]],
    *,
    alert_rows: Iterable[Mapping[str, Any]] = (),
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry] = (),
    raw_events: Iterable[RawDiscoveredEvent] = (),
    min_return_24h: float = 1.0,
    min_return_72h: float = 1.5,
    min_return_7d: float = 2.0,
    min_volume_mcap: float = 0.60,
) -> MissedOpportunityResult:
    markets = [dict(row) for row in market_rows if isinstance(row, Mapping)]
    alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    watch = list(watchlist_entries)
    raw = list(raw_events)
    alerted = _alerted_assets(alerts, watch)
    rows: list[MissedOpportunity] = []
    for market in markets:
        symbol = str(market.get("symbol") or "").upper()
        coin_id = str(market.get("id") or market.get("coin_id") or "")
        name = str(market.get("name") or coin_id or symbol)
        if not symbol and not coin_id:
            continue
        if _asset_key(symbol, coin_id) in alerted:
            continue
        snapshot = event_market_enrichment.market_snapshot_from_row(market)
        windows = (
            ("24h", _float(snapshot.get("return_24h")), min_return_24h),
            ("72h", _float(snapshot.get("return_72h")), min_return_72h),
            ("7d", _float(snapshot.get("return_7d")), min_return_7d),
        )
        triggered = [(window, value) for window, value, threshold in windows if value is not None and value >= threshold]
        volume_mcap = event_market_enrichment.volume_to_market_cap(market)
        if volume_mcap is not None and volume_mcap >= min_volume_mcap:
            triggered.append(("volume_mcap", volume_mcap))
        for window, value in triggered:
            stage, reason = _failure_stage(symbol, coin_id, raw, alerts, watch)
            rows.append(MissedOpportunity(
                schema_version=MISSED_SCHEMA_VERSION,
                row_type="event_alpha_missed",
                symbol=symbol,
                coin_id=coin_id,
                name=name,
                move_window=window,
                return_pct=round(value, 6),
                failure_stage=stage,
                reason=reason,
                suggested_queries=_queries(symbol, name),
            ))
            break
    rows.sort(key=lambda row: row.return_pct, reverse=True)
    return MissedOpportunityResult(
        rows=rows,
        market_rows=len(markets),
        alert_rows=len(alerts),
        watchlist_entries=len(watch),
    )


def format_missed_report(result: MissedOpportunityResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA MISSED OPPORTUNITY REPORT (research-only)",
        "=" * 76,
        (
            f"market_rows={result.market_rows} · alert_rows={result.alert_rows} · "
            f"watchlist_entries={result.watchlist_entries} · missed={len(result.rows)}"
        ),
    ]
    if not result.rows:
        lines.append("")
        lines.append("No missed opportunities crossed configured thresholds.")
        return "\n".join(lines)
    counts: dict[str, int] = {}
    for row in result.rows:
        counts[row.failure_stage] = counts.get(row.failure_stage, 0) + 1
    lines.append("failure_stages: " + ", ".join(f"{stage}={count}" for stage, count in sorted(counts.items())))
    lines.append("")
    for row in result.rows[:25]:
        lines.append(
            f"{row.symbol}/{row.coin_id or 'unknown'} {row.move_window}={row.return_pct * 100:+.1f}% "
            f"stage={row.failure_stage}"
        )
        lines.append(f"  reason: {row.reason}")
        lines.append("  follow-up: " + "; ".join(row.suggested_queries[:3]))
    return "\n".join(lines).rstrip()


def write_missed_rows(path: str | Path, rows: Iterable[MissedOpportunity]) -> int:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with p.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row.__dict__, sort_keys=True, separators=(",", ":")))
            fh.write("\n")
            count += 1
    return count


def load_missed_rows(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path).expanduser()
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("row_type") == "event_alpha_missed":
                rows.append(row)
    return rows


def load_market_rows(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    p = Path(path).expanduser()
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(raw, list):
        return [dict(row) for row in raw if isinstance(row, Mapping)]
    if isinstance(raw, Mapping):
        for key in ("coins", "markets", "data", "rows"):
            rows = raw.get(key)
            if isinstance(rows, list):
                return [dict(row) for row in rows if isinstance(row, Mapping)]
    return []


def _alerted_assets(
    alert_rows: Iterable[Mapping[str, Any]],
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry],
) -> set[str]:
    out: set[str] = set()
    alert_tiers = {"RADAR_DIGEST", "WATCHLIST", "HIGH_PRIORITY_WATCH", "TRIGGERED_FADE"}
    watch_states = {
        event_watchlist.EventWatchlistState.RADAR.value,
        event_watchlist.EventWatchlistState.WATCHLIST.value,
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
    }
    for row in alert_rows:
        if str(row.get("tier") or "") not in alert_tiers:
            continue
        out.add(_asset_key(row.get("asset_symbol"), row.get("asset_coin_id")))
    for entry in watchlist_entries:
        if entry.state in watch_states:
            out.add(_asset_key(entry.symbol, entry.coin_id))
    return {item for item in out if item}


def _failure_stage(
    symbol: str,
    coin_id: str,
    raw_events: Iterable[RawDiscoveredEvent],
    alert_rows: Iterable[Mapping[str, Any]],
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry],
) -> tuple[str, str]:
    identity_hints = [_raw_identity_hint(raw, symbol, coin_id) for raw in raw_events]
    if any(hint == "strong_identity" for hint in identity_hints):
        return "resolver_missed_asset", "Source evidence mentions the asset, but no prior alert/watchlist row exists."
    weak_hints = [hint for hint in identity_hints if hint in {"weak_url_only_identity_hint", "metadata_only_identity_hint"}]
    if weak_hints:
        return (
            "no_source_event",
            "Only weak identity hints were found; "
            + ", ".join(dict.fromkeys(weak_hints))
            + " is not enough to diagnose a resolver miss.",
        )
    if any(_row_matches(row, symbol, coin_id) and str(row.get("tier") or "") == "STORE_ONLY" for row in alert_rows):
        return "low_score_suppressed", "The asset exists in alert snapshots but was suppressed below radar tier."
    if any(_entry_matches(entry, symbol, coin_id) for entry in watchlist_entries):
        return "watchlist_not_escalated", "The asset existed in watchlist state but did not escalate."
    return "no_source_event", "No prior Event Alpha source evidence, alert, or watchlist row was found."


def _queries(symbol: str, name: str) -> tuple[str, ...]:
    clean_name = name.strip()
    base = symbol or clean_name
    return tuple(dict.fromkeys((
        f"{base} crypto catalyst",
        f"{base} why up",
        f"{clean_name} Binance listing" if clean_name else "",
        f"{base} pre-IPO exposure",
    )))[:4]


def _raw_identity_hint(raw: RawDiscoveredEvent, symbol: str, coin_id: str) -> str | None:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    event_payload = payload.get("event") if isinstance(payload.get("event"), Mapping) else {}
    strong_fields = (
        raw.title,
        raw.body,
        event_payload.get("event_name"),
        event_payload.get("description"),
    )
    result = event_identity.match_asset_identity(
        event_identity.AssetIdentity(
            symbol=str(symbol or "").upper(),
            coin_id=coin_id,
            is_common_word_symbol=str(symbol or "").upper() in event_identity.COMMON_WORD_SYMBOLS,
        ),
        event_identity.IdentityEvidence(
            strong_content=tuple(str(field or "") for field in strong_fields),
            llm_quotes=event_identity.validated_llm_identity_quotes(payload, strong_fields),
            url=str(raw.source_url or ""),
            source_origin=tuple(str(value or "") for value in (
                raw.provider,
                payload.get("source_origin"),
                payload.get("publisher"),
                payload.get("source_provider"),
            )),
        ),
    )
    if result.matched and result.strength == event_identity.STRENGTH_STRONG:
        return "strong_identity"
    if result.reason == "identity_source_origin_rejected":
        return "metadata_only_identity_hint"
    if result.reason == "identity_url_only_rejected":
        return "weak_url_only_identity_hint"
    return None


def _validated_llm_quote_mentions_identity(
    payload: Mapping[str, Any],
    strong_fields: Iterable[object],
    symbol: str,
    coin_id: str,
) -> bool:
    extraction = payload.get("llm_extraction")
    if not isinstance(extraction, Mapping):
        return False
    source_text = " ".join(str(field or "") for field in strong_fields).casefold()
    for quote in _llm_quote_texts(extraction):
        if not quote:
            continue
        quote_l = quote.casefold()
        if quote_l not in source_text:
            continue
        if _contains_identity(quote, symbol, coin_id):
            return True
    return False


def _llm_quote_texts(extraction: Mapping[str, Any]) -> Iterable[str]:
    for key in ("crypto_asset_mentions", "external_catalysts", "false_positive_terms"):
        rows = extraction.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            quotes = row.get("evidence_quotes")
            if not isinstance(quotes, list):
                continue
            for quote in quotes:
                if isinstance(quote, Mapping):
                    text = str(quote.get("text") or "").strip()
                else:
                    text = str(quote or "").strip()
                if text:
                    yield text


def _contains_identity(value: object, symbol: str, coin_id: str) -> bool:
    text = str(value or "").casefold()
    if not text:
        return False
    return bool((symbol and symbol.casefold() in text) or (coin_id and coin_id.casefold() in text))


def _row_matches(row: Mapping[str, Any], symbol: str, coin_id: str) -> bool:
    return _asset_key(row.get("asset_symbol"), row.get("asset_coin_id")) == _asset_key(symbol, coin_id)


def _entry_matches(entry: event_watchlist.EventWatchlistEntry, symbol: str, coin_id: str) -> bool:
    return _asset_key(entry.symbol, entry.coin_id) == _asset_key(symbol, coin_id)


def _asset_key(symbol: object, coin_id: object) -> str:
    cid = str(coin_id or "").strip().casefold()
    sym = str(symbol or "").strip().upper()
    return cid or sym


def _float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
