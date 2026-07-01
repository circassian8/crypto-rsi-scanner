"""Official exchange announcement artifacts for Event Alpha research.

This module normalizes fixture or explicitly configured exchange announcement
payloads into local research artifacts. It is intentionally artifact-only:
it does not send notifications, open paper trades, write normal RSI rows,
execute orders, or create ``TRIGGERED_FADE``.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import config, event_market_reaction
from .event_providers._announcement_common import (
    _announcement_contracts,
    _announcement_items,
    _announcement_pairs,
    _announcement_symbols,
)
from .event_providers.manual_json import parse_datetime


EXCHANGE_ANNOUNCEMENTS_FILENAME = "event_exchange_announcements.jsonl"
OFFICIAL_EXCHANGE_EVENTS_FILENAME = "event_official_exchange_events.jsonl"
OFFICIAL_LISTING_CANDIDATES_FILENAME = "event_official_listing_candidates.jsonl"
OFFICIAL_EXCHANGE_REPORT_FILENAME = "event_official_exchange_report.md"

SOURCE_CLASS = "official_exchange"
SOURCE_STRENGTH = "official_structured"

SPOT_LISTING = "spot_listing"
PERP_LISTING = "perp_listing"
MARGIN_LISTING = "margin_listing"
NEW_TRADING_PAIR = "new_trading_pair"
LAUNCHPOOL = "launchpool"
LAUNCHPAD = "launchpad"
AIRDROP = "airdrop"
STAKING_EARN = "staking_earn"
DELISTING = "delisting"
TRADING_SUSPENSION = "trading_suspension"
TRADING_RESUMPTION = "trading_resumption"
MAINTENANCE = "maintenance"
OTHER_EXCHANGE_NOTICE = "other_exchange_notice"

QUOTE_ASSETS = {
    "USD",
    "USDT",
    "USDC",
    "FDUSD",
    "TUSD",
    "BUSD",
    "DAI",
    "BTC",
    "ETH",
    "BNB",
    "EUR",
    "TRY",
    "BRL",
}
MAJOR_PAIR_BASE_ASSETS = {"BTC", "ETH", "USDT", "USDC", "FDUSD", "TUSD", "BUSD", "DAI"}

RISK_EVENT_TYPES = {DELISTING, TRADING_SUSPENSION, MAINTENANCE}
LISTING_EVENT_TYPES = {
    SPOT_LISTING,
    PERP_LISTING,
    MARGIN_LISTING,
    NEW_TRADING_PAIR,
    LAUNCHPOOL,
    LAUNCHPAD,
    AIRDROP,
    STAKING_EARN,
}


@dataclass(frozen=True)
class OfficialExchangeScanResult:
    namespace_dir: Path
    announcements_path: Path
    events_path: Path
    candidates_path: Path
    report_path: Path
    announcement_count: int
    event_count: int
    candidate_count: int
    events: tuple[dict[str, Any], ...]
    candidates: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...] = ()


def run_official_exchange_scan(
    *,
    namespace_dir: str | Path,
    provider_paths: Mapping[str, str | Path | None],
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
    observed_at: datetime | str | None = None,
) -> OfficialExchangeScanResult:
    """Normalize configured official exchange fixture payloads and write artifacts."""
    directory = Path(namespace_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    observed = _as_utc(_parse_time(observed_at) or datetime.now(timezone.utc)).isoformat()
    warnings: list[str] = []
    announcement_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []

    for provider, path in provider_paths.items():
        if path is None:
            warnings.append(f"{provider}:not_configured")
            continue
        items = _load_fixture_items(path)
        if not items:
            warnings.append(f"{provider}:no_fixture_rows")
            continue
        for item in items:
            announcement = _announcement_row(
                item,
                provider=provider,
                observed_at=observed,
                profile=profile,
                artifact_namespace=artifact_namespace,
                run_mode=run_mode,
                run_id=run_id,
            )
            announcement_rows.append(announcement)
            event = normalize_official_exchange_event(
                item,
                provider=provider,
                observed_at=observed,
                profile=profile,
                artifact_namespace=artifact_namespace,
                run_mode=run_mode,
                run_id=run_id,
            )
            event_rows.append(event)
            candidate_rows.extend(_candidate_rows_for_event(event, item))

    announcements_path = directory / EXCHANGE_ANNOUNCEMENTS_FILENAME
    events_path = directory / OFFICIAL_EXCHANGE_EVENTS_FILENAME
    candidates_path = directory / OFFICIAL_LISTING_CANDIDATES_FILENAME
    report_path = directory / OFFICIAL_EXCHANGE_REPORT_FILENAME
    _write_jsonl(announcements_path, announcement_rows)
    _write_jsonl(events_path, event_rows)
    _write_jsonl(candidates_path, candidate_rows)
    report_path.write_text(
        format_official_exchange_report(
            event_rows,
            candidate_rows,
            profile=profile,
            artifact_namespace=artifact_namespace,
            warnings=warnings,
        ),
        encoding="utf-8",
    )
    return OfficialExchangeScanResult(
        namespace_dir=directory,
        announcements_path=announcements_path,
        events_path=events_path,
        candidates_path=candidates_path,
        report_path=report_path,
        announcement_count=len(announcement_rows),
        event_count=len(event_rows),
        candidate_count=len(candidate_rows),
        events=tuple(event_rows),
        candidates=tuple(candidate_rows),
        warnings=tuple(warnings),
    )


def normalize_official_exchange_event(
    item: Mapping[str, Any],
    *,
    provider: str,
    observed_at: str | datetime | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Return one normalized official exchange event row."""
    title = _title(item)
    body = _body(item)
    text = f"{title} {body}"
    event_type = classify_exchange_event_type(title, body)
    exchange = _exchange(provider, item)
    published_at = _event_time(
        item,
        "published_at",
        "publishedAt",
        "releaseDate",
        "publishDate",
        "publishTime",
        "publish_time",
        "dateTimestamp",
    )
    effective_time = _event_time(
        item,
        "effective_time",
        "event_time",
        "listing_time",
        "listingTime",
        "launchTime",
        "tradingStartTime",
        "tradeStartTime",
        "startDateTimestamp",
        "startDataTimestamp",
        "resumeTime",
        "suspensionTime",
    )
    symbols = _extract_symbols(item, title, body)
    pairs = tuple(dict.fromkeys(_announcement_pairs(title, body)))
    contracts = tuple(dict.fromkeys(_announcement_contracts(title, body)))
    quote_assets = tuple(dict.fromkeys(pair.split("/", 1)[1] for pair in pairs if "/" in pair))
    coin_ids = _coin_ids_for_symbols(item, symbols)
    reason_codes = _reason_codes_for_event(event_type, symbols=symbols, coin_ids=coin_ids, pairs=pairs)
    announcement_id = _announcement_id(provider, item, title, published_at)
    url = str(item.get("source_url") or item.get("url") or item.get("articleUrl") or item.get("link") or "")
    confidence = _confidence(event_type, symbols, coin_ids)
    return {
        "schema_version": 1,
        "row_type": "official_exchange_event",
        "profile": profile,
        "artifact_namespace": artifact_namespace,
        "run_mode": run_mode,
        "run_id": run_id,
        "provider": provider,
        "exchange": exchange,
        "announcement_id": announcement_id,
        "official_exchange_event_id": f"oxe:{exchange}:{_digest(f'{provider}|{announcement_id}|{title}')}",
        "title": title,
        "body": body,
        "url": url or None,
        "source_url": url or None,
        "published_at": published_at,
        "locale": str(item.get("locale") or item.get("lang") or "en-US"),
        "category": item.get("category") or item.get("catalogName") or item.get("categoryName"),
        "type": item.get("type") or item.get("announcement_type") or item.get("announcementType"),
        "tag": item.get("tag") or item.get("tags"),
        "event_type": event_type,
        "symbols": symbols,
        "coin_ids": coin_ids,
        "quote_assets": quote_assets,
        "major_pair_simple_announcement": _is_simple_major_pair_event(event_type, symbols=symbols, pairs=pairs),
        "pairs": pairs,
        "contracts": contracts,
        "effective_time": effective_time,
        "listing_scope": listing_scope_for_event_type(event_type),
        "source_class": SOURCE_CLASS,
        "source_strength": SOURCE_STRENGTH,
        "confidence": confidence,
        "raw_payload_redacted": _redacted_payload(item),
        "reason_codes": reason_codes,
        "resolver_warnings": _resolver_warnings(symbols, coin_ids),
        "source_pack": source_pack_for_event_type(event_type),
        "impact_path_type": impact_path_for_event_type(event_type),
        "negative_catalyst": event_type in RISK_EVENT_TYPES,
        "observed_at": _as_utc(_parse_time(observed_at) or datetime.now(timezone.utc)).isoformat(),
        "research_only": True,
    }


def classify_exchange_event_type(title: str, body: str = "") -> str:
    """Classify one official announcement title/body into an exchange event type."""
    text = _clean(f"{title} {body}")
    if any(term in text for term in ("resume trading", "trading resumption", "resume deposits", "resume withdrawals", "resumption of")):
        return TRADING_RESUMPTION
    if any(term in text for term in ("suspend trading", "trading suspension", "suspension of", "deposits and withdrawals suspended")):
        return TRADING_SUSPENSION
    if any(term in text for term in ("delist", "delisting", "remove trading pair", "remove spot trading pair", "cease trading")):
        return DELISTING
    if "launchpool" in text:
        return LAUNCHPOOL
    if "launchpad" in text:
        return LAUNCHPAD
    if "airdrop" in text:
        return AIRDROP
    if any(term in text for term in ("simple earn", "earn product", "staking", "savings", "staking campaign")):
        return STAKING_EARN
    if "margin" in text and any(term in text for term in ("list", "add", "trading pair", "new")):
        return MARGIN_LISTING
    if any(term in text for term in ("perpetual", "perp", "futures", "contract")) and any(term in text for term in ("list", "launch", "add", "new")):
        return PERP_LISTING
    if "new spot trading pair" in text or "new trading pair" in text or "new pairs" in text:
        return NEW_TRADING_PAIR
    if any(term in text for term in ("will list", "new listing", "lists ", "list ", "spot trading for", "open spot trading", "opens trading")):
        return SPOT_LISTING
    if any(term in text for term in ("maintenance", "wallet maintenance", "network upgrade", "system upgrade")):
        return MAINTENANCE
    return OTHER_EXCHANGE_NOTICE


def listing_scope_for_event_type(event_type: str) -> str:
    if event_type == SPOT_LISTING or event_type == NEW_TRADING_PAIR:
        return "spot"
    if event_type == PERP_LISTING:
        return "perp"
    if event_type == MARGIN_LISTING:
        return "margin"
    if event_type in {LAUNCHPOOL, LAUNCHPAD, AIRDROP, STAKING_EARN}:
        return event_type
    if event_type == DELISTING:
        return "delisting"
    if event_type == TRADING_SUSPENSION:
        return "suspension"
    if event_type == TRADING_RESUMPTION:
        return "resumption"
    if event_type == MAINTENANCE:
        return "maintenance"
    return "other"


def source_pack_for_event_type(event_type: str) -> str:
    if event_type == PERP_LISTING:
        return "official_perp_listing_pack"
    if event_type in RISK_EVENT_TYPES:
        return "official_exchange_risk_pack"
    return "official_exchange_listing_pack"


def impact_path_for_event_type(event_type: str) -> str:
    if event_type == PERP_LISTING:
        return "perp_listing"
    if event_type in RISK_EVENT_TYPES:
        return "exchange_tradability_risk"
    if event_type in {LAUNCHPOOL, LAUNCHPAD, AIRDROP, STAKING_EARN}:
        return "exchange_campaign_event"
    return "listing_liquidity_event"


def load_official_exchange_events(path: str | Path | None) -> tuple[dict[str, Any], ...]:
    return tuple(_load_rows(path, OFFICIAL_EXCHANGE_EVENTS_FILENAME, "official_exchange_event"))


def load_official_listing_candidates(path: str | Path | None) -> tuple[dict[str, Any], ...]:
    return tuple(_load_rows(path, OFFICIAL_LISTING_CANDIDATES_FILENAME, "official_listing_candidate"))


def format_official_exchange_report(
    events: Iterable[Mapping[str, Any]],
    candidates: Iterable[Mapping[str, Any]],
    *,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    warnings: Iterable[str] = (),
    limit: int = 20,
) -> str:
    event_rows = [dict(row) for row in events if isinstance(row, Mapping)]
    candidate_rows = [dict(row) for row in candidates if isinstance(row, Mapping)]
    event_counts = _counts(row.get("event_type") for row in event_rows)
    lane_counts = _counts(row.get("opportunity_type") for row in candidate_rows)
    lines = [
        "# Event Alpha Official Exchange Announcement Report",
        "",
        "Research-only. Not a trade signal, paper trade, live RSI signal, or execution.",
        f"Profile: {profile or 'unknown'}",
        f"Artifact namespace: {artifact_namespace or 'unknown'}",
        f"Official exchange events: {len(event_rows)}",
        f"Candidate rows: {len(candidate_rows)}",
        "Event types: " + (_format_counts(event_counts) or "none"),
        "Opportunity lanes: " + (_format_counts(lane_counts) or "none"),
        "",
        "## Fresh Official Exchange Catalysts",
    ]
    if not candidate_rows:
        lines.append("- None.")
    for row in candidate_rows[: max(0, limit)]:
        lines.append(
            "- "
            f"{row.get('symbol') or 'UNRESOLVED'}/{row.get('coin_id') or 'unresolved'} "
            f"{row.get('event_type') or 'unknown'} "
            f"lane={row.get('opportunity_type') or 'unknown'} "
            f"market_state={row.get('market_state') or 'unknown'} "
            f"scope={row.get('listing_scope') or 'other'} "
            f"source_pack={row.get('source_pack') or 'unknown'}"
        )
        if row.get("resolver_warnings"):
            lines.append("  - Resolver: " + "; ".join(str(item) for item in row.get("resolver_warnings") or ()))
        if row.get("why_not_alertable"):
            lines.append("  - Why not alertable: " + "; ".join(str(item) for item in row.get("why_not_alertable") or ()))
        if row.get("source_url"):
            lines.append(f"  - Source: {row.get('source_url')}")
    warning_rows = [str(item) for item in warnings if str(item)]
    if warning_rows:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in warning_rows[:10])
    return "\n".join(lines) + "\n"


def _candidate_rows_for_event(event: Mapping[str, Any], item: Mapping[str, Any]) -> list[dict[str, Any]]:
    symbols = tuple(str(symbol).upper() for symbol in event.get("symbols") or () if str(symbol).strip())
    coin_ids = tuple(str(coin_id) for coin_id in event.get("coin_ids") or () if str(coin_id).strip())
    if not symbols:
        symbols = ("",)
    rows: list[dict[str, Any]] = []
    for index, symbol in enumerate(symbols):
        coin_id = coin_ids[index] if index < len(coin_ids) else ""
        market_snapshot = _market_snapshot_for_symbol(item, symbol)
        reaction = event_market_reaction.evaluate_market_reaction({
            "symbol": symbol,
            "coin_id": coin_id,
            "source_class": SOURCE_CLASS,
            "source_pack": event.get("source_pack"),
            "impact_path_type": event.get("impact_path_type"),
            "evidence_quality_score": 92.0 if coin_id else 70.0,
            "accepted_evidence_count": 1,
            "accepted_evidence_reason_codes": event.get("reason_codes") or (),
            "market_snapshot": market_snapshot,
            "negative_catalyst": bool(event.get("negative_catalyst")),
            "catalyst_fresh": True,
        })
        opportunity_type = reaction.opportunity_type
        why_not = list(reaction.why_not_alertable)
        warnings = list(event.get("resolver_warnings") or ())
        reason_codes = list(event.get("reason_codes") or ())
        major_pair_noise = bool(event.get("major_pair_simple_announcement")) and not bool(config.EVENT_ALPHA_ALLOW_MAJOR_PAIR_CATALYSTS)
        if major_pair_noise:
            opportunity_type = event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value
            why_not.append("major_pair_simple_announcement_not_alpha")
            warnings.append("major_pair_simple_pair_capped")
            reason_codes.append("major_pair_simple_announcement_capped")
        if not coin_id:
            opportunity_type = event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value
            why_not.append("deterministic_resolver_validation_missing")
            warnings.append("unresolved_symbol")
        if not symbol:
            opportunity_type = event_market_reaction.EventOpportunityType.DIAGNOSTIC.value
            why_not.append("no_asset_symbol_extracted")
        row = {
            "schema_version": 1,
            "row_type": "official_listing_candidate",
            "profile": event.get("profile"),
            "artifact_namespace": event.get("artifact_namespace"),
            "run_mode": event.get("run_mode"),
            "run_id": event.get("run_id"),
            "candidate_id": f"oxc:{event.get('exchange')}:{_digest(str(event.get('announcement_id')) + '|' + symbol + '|' + coin_id)}",
            "official_exchange_event_id": event.get("official_exchange_event_id"),
            "provider": event.get("provider"),
            "exchange": event.get("exchange"),
            "announcement_id": event.get("announcement_id"),
            "symbol": symbol,
            "coin_id": coin_id or None,
            "validated_symbol": symbol or None,
            "validated_coin_id": coin_id or None,
            "title": event.get("title"),
            "event_name": event.get("title"),
            "event_type": event.get("event_type"),
            "listing_scope": event.get("listing_scope"),
            "published_at": event.get("published_at"),
            "effective_time": event.get("effective_time"),
            "source_url": event.get("source_url"),
            "source_class": SOURCE_CLASS,
            "source_strength": SOURCE_STRENGTH,
            "source_pack": event.get("source_pack"),
            "impact_path_type": event.get("impact_path_type"),
            "reason_codes": tuple(dict.fromkeys(reason_codes)),
            "major_pair_simple_announcement": major_pair_noise,
            "resolver_warnings": tuple(dict.fromkeys(warnings)),
            "market_snapshot": market_snapshot,
            "market_state_snapshot": reaction.market_state_snapshot.to_dict(),
            "market_state": reaction.market_state,
            "opportunity_type": opportunity_type,
            "source_requirements_met": reaction.source_requirements_met,
            "market_requirements_met": reaction.market_requirements_met,
            "fade_requirements_met": reaction.fade_requirements_met,
            "why_now": reaction.why_now,
            "what_confirms": reaction.what_confirms,
            "what_invalidates": reaction.what_invalidates,
            "why_not_alertable": tuple(dict.fromkeys(why_not)),
            "research_only": True,
            "created_alert": False,
            "notification_send_enabled": False,
        }
        rows.append(row)
    return rows


def _announcement_row(
    item: Mapping[str, Any],
    *,
    provider: str,
    observed_at: str,
    profile: str | None,
    artifact_namespace: str | None,
    run_mode: str | None,
    run_id: str | None,
) -> dict[str, Any]:
    title = _title(item)
    return {
        "schema_version": 1,
        "row_type": "exchange_announcement",
        "profile": profile,
        "artifact_namespace": artifact_namespace,
        "run_mode": run_mode,
        "run_id": run_id,
        "provider": provider,
        "exchange": _exchange(provider, item),
        "announcement_id": _announcement_id(provider, item, title, None),
        "title": title,
        "source_url": str(item.get("source_url") or item.get("url") or item.get("articleUrl") or item.get("link") or "") or None,
        "published_at": _event_time(item, "published_at", "publishedAt", "releaseDate", "publishDate", "publishTime", "dateTimestamp"),
        "raw_payload_redacted": _redacted_payload(item),
        "observed_at": observed_at,
        "research_only": True,
    }


def _load_fixture_items(path: str | Path) -> tuple[Mapping[str, Any], ...]:
    source = Path(path).expanduser()
    if not source.exists():
        return ()
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
        return tuple(dict(item) for item in _announcement_items(raw))
    except Exception:
        return ()


def _load_rows(path: str | Path | None, filename: str, row_type: str) -> list[dict[str, Any]]:
    if path is None:
        return []
    source = Path(path).expanduser()
    if source.is_dir():
        source = source / filename
    if not source.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, Mapping) and row.get("row_type") == row_type:
            out.append(dict(row))
    return out


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(_json_ready(dict(row)), sort_keys=True, separators=(",", ":"), default=str) + "\n")


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    return value


def _extract_symbols(item: Mapping[str, Any], title: str, body: str) -> tuple[str, ...]:
    explicit = item.get("symbols") or item.get("baseAssets") or item.get("base_assets")
    explicit_coin_ids = item.get("coin_ids") or item.get("coinIds") or {}
    explicit_symbols = {str(key).upper() for key in explicit_coin_ids.keys()} if isinstance(explicit_coin_ids, Mapping) else set()
    out: list[str] = []
    if isinstance(explicit, str):
        out.extend(_tokenize_symbols(explicit))
    elif isinstance(explicit, Iterable):
        out.extend(str(value).upper() for value in explicit if str(value).strip())
    out.extend(_announcement_symbols(title, body))
    pair_bases: set[str] = set()
    for pair in _announcement_pairs(title, body):
        base, _quote = pair.split("/", 1)
        if f"{base}{_quote}".upper() in QUOTE_ASSETS:
            continue
        pair_bases.add(base.upper())
        out.append(base)
    clean: list[str] = []
    for symbol in out:
        candidate = str(symbol or "").upper().strip()
        if not candidate:
            continue
        if candidate in QUOTE_ASSETS and candidate not in pair_bases and candidate not in explicit_symbols:
            continue
        if any(candidate.endswith(quote) and len(candidate) > len(quote) for quote in QUOTE_ASSETS):
            for quote in sorted(QUOTE_ASSETS, key=len, reverse=True):
                if candidate.endswith(quote) and len(candidate) > len(quote):
                    candidate = candidate[: -len(quote)]
                    break
        if candidate and (candidate not in QUOTE_ASSETS or candidate in pair_bases or candidate in explicit_symbols):
            clean.append(candidate)
    return tuple(dict.fromkeys(clean))


def _tokenize_symbols(text: str) -> list[str]:
    return [item.upper() for item in re.split(r"[,/\\s]+", text) if item.strip()]


def _coin_ids_for_symbols(item: Mapping[str, Any], symbols: tuple[str, ...]) -> tuple[str, ...]:
    explicit = item.get("coin_ids") or item.get("coinIds") or item.get("coin_id") or item.get("coinId")
    if isinstance(explicit, str):
        values = [explicit]
    elif isinstance(explicit, Mapping):
        return tuple(str(explicit.get(symbol) or "").strip() for symbol in symbols if str(explicit.get(symbol) or "").strip())
    elif isinstance(explicit, Iterable):
        values = [str(value) for value in explicit if str(value).strip()]
    else:
        values = []
    return tuple(dict.fromkeys(value for value in values if value))


def _market_snapshot_for_symbol(item: Mapping[str, Any], symbol: str) -> dict[str, Any]:
    market = item.get("market_snapshot") or item.get("market") or {}
    if isinstance(market, Mapping):
        symbol_market = market.get(symbol) or market.get(str(symbol).upper()) or market.get(str(symbol).lower())
        if isinstance(symbol_market, Mapping):
            return dict(symbol_market)
        return dict(market)
    return {}


def _reason_codes_for_event(event_type: str, *, symbols: tuple[str, ...], coin_ids: tuple[str, ...], pairs: tuple[str, ...]) -> tuple[str, ...]:
    reasons = ["official_exchange_announcement"]
    if symbols:
        reasons.append("symbol_or_pair_match")
    if coin_ids:
        reasons.append("deterministic_asset_identity")
    elif symbols:
        reasons.append("unresolved_symbol_candidate")
    if pairs:
        reasons.append("official_pair_match")
    if event_type == PERP_LISTING:
        reasons.append("official_perp_listing")
    elif event_type in {SPOT_LISTING, NEW_TRADING_PAIR, MARGIN_LISTING}:
        reasons.append("official_listing")
    elif event_type in RISK_EVENT_TYPES:
        reasons.append("official_exchange_risk_notice")
    elif event_type in {LAUNCHPOOL, LAUNCHPAD, AIRDROP, STAKING_EARN}:
        reasons.append("official_exchange_campaign")
    return tuple(dict.fromkeys(reasons))


def _is_simple_major_pair_event(event_type: str, *, symbols: tuple[str, ...], pairs: tuple[str, ...]) -> bool:
    if event_type not in {SPOT_LISTING, NEW_TRADING_PAIR}:
        return False
    bases = {str(symbol or "").upper() for symbol in symbols if str(symbol or "").strip()}
    for pair in pairs:
        if "/" not in str(pair):
            continue
        base, quote = str(pair).upper().split("/", 1)
        bases.add(base)
        if base in MAJOR_PAIR_BASE_ASSETS and quote in QUOTE_ASSETS:
            return True
    return bool(bases and bases.issubset(MAJOR_PAIR_BASE_ASSETS))


def _resolver_warnings(symbols: tuple[str, ...], coin_ids: tuple[str, ...]) -> tuple[str, ...]:
    warnings: list[str] = []
    if not symbols:
        warnings.append("no_symbol_extracted")
    if symbols and not coin_ids:
        warnings.append("coin_id_unresolved")
    return tuple(warnings)


def _confidence(event_type: str, symbols: tuple[str, ...], coin_ids: tuple[str, ...]) -> float:
    base = 0.94 if event_type != OTHER_EXCHANGE_NOTICE else 0.70
    if not symbols:
        base -= 0.22
    if symbols and not coin_ids:
        base -= 0.12
    return round(max(0.10, min(0.98, base)), 2)


def _redacted_payload(item: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in item.items():
        clean_key = str(key)
        if any(secret_word in clean_key.casefold() for secret_word in ("token", "secret", "apikey", "api_key", "signature")):
            out[clean_key] = "<redacted>"
        else:
            out[clean_key] = value
    return out


def _title(item: Mapping[str, Any]) -> str:
    return str(item.get("title") or item.get("name") or item.get("headline") or "").strip()


def _body(item: Mapping[str, Any]) -> str:
    return str(item.get("body") or item.get("content") or item.get("summary") or item.get("description") or "").strip()


def _exchange(provider: str, item: Mapping[str, Any]) -> str:
    explicit = str(item.get("exchange") or "").strip().casefold()
    if explicit:
        return explicit
    text = str(provider or "").casefold()
    if "binance" in text:
        return "binance"
    if "bybit" in text:
        return "bybit"
    return text.replace("_announcements", "").replace("_", "-") or "exchange"


def _announcement_id(provider: str, item: Mapping[str, Any], title: str, published_at: str | None) -> str:
    explicit = item.get("announcement_id") or item.get("id") or item.get("code") or item.get("articleId")
    if explicit:
        return str(explicit)
    return f"{provider}:{_digest(f'{title}|{published_at or ''}')}"


def _event_time(item: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        parsed = _parse_time(item.get(key))
        if parsed is not None:
            return parsed.isoformat()
    return None


def _parse_time(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000.0 if float(value) > 10_000_000_000 else float(value)
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    return parse_datetime(value)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def _digest(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def _counts(values: Iterable[object]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        key = str(value or "unknown")
        out[key] = out.get(key, 0) + 1
    return out


def _format_counts(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()) if value)
