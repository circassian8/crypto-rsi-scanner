"""Evidence acquisition provider and raw-result helpers."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

from .... import (
    event_evidence_quality,
    event_llm_evidence_planner,
)
from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
from ....event_resolver import clean_text
from ...providers import source_packs as event_source_packs
from ...providers import source_registry as event_source_registry
from .. import catalyst_search as event_catalyst_search
from .. import core_opportunities as event_core_opportunities
from .. import impact_hypotheses as event_impact_hypotheses
from .. import source_enrichment as event_source_enrichment
from .models import *  # noqa: F403 - split modules share legacy model names


def _raw_mapping(raw: RawDiscoveredEvent) -> dict[str, Any]:
    payload = dict(raw.raw_json or {})
    return {
        **payload,
        "provider": raw.provider,
        "source_url": raw.source_url,
        "title": raw.title,
        "body": raw.body,
        "raw_json": payload,
        "source_confidence": raw.source_confidence,
    }


def _currency_tags_from_raw_map(raw_map: Mapping[str, Any]) -> tuple[str, ...]:
    tags: list[str] = []

    def collect(value: object) -> None:
        if value in (None, ""):
            return
        if isinstance(value, str):
            for part in value.replace(";", ",").split(","):
                cleaned = part.strip()
                if cleaned:
                    tags.append(cleaned.upper())
            return
        if isinstance(value, Mapping):
            for key in ("code", "symbol", "slug", "title", "name"):
                item = value.get(key)
                if item not in (None, ""):
                    tags.append(str(item).strip().upper())
            return
        if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
            for item in value:
                collect(item)

    for key in ("currency_tags", "currencyTags", "currencies", "tags"):
        collect(raw_map.get(key))
    nested = raw_map.get("raw_json")
    if isinstance(nested, Mapping):
        for key in ("currency_tags", "currencyTags", "currencies", "tags"):
            collect(nested.get(key))
    return tuple(dict.fromkeys(value for value in tags if value))


def _exchange_metadata_from_raw_map(raw_map: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "exchange": _text_or_none(raw_map.get("exchange")),
        "announcement_kind": _text_or_none(raw_map.get("announcement_kind")),
        "exchange_product_type": _text_or_none(raw_map.get("exchange_product_type")),
        "announcement_symbols": _tuple_text(raw_map.get("announcement_symbols")),
        "announcement_pairs": _tuple_text(raw_map.get("announcement_pairs")),
        "announcement_contracts": _tuple_text(raw_map.get("announcement_contracts")),
        "announcement_time": _text_or_none(raw_map.get("announcement_time")),
        "announcement_published_at": _text_or_none(raw_map.get("announcement_published_at")),
    }


def _official_exchange_identity_match(
    raw_map: Mapping[str, Any],
    request: EvidenceAcquisitionRequest,
) -> bool:
    if str(raw_map.get("source_class") or "").strip() != event_source_registry.SourceClass.OFFICIAL_EXCHANGE.value:
        return False
    expected = {_compact_exchange_identity(request.symbol)}
    if request.coin_id:
        expected.add(_compact_exchange_identity(request.coin_id))
    expected.discard("")
    if not expected:
        return False
    values: list[str] = []
    event = raw_map.get("event") if isinstance(raw_map.get("event"), Mapping) else {}
    for source in (raw_map, event):
        for key in (
            "announcement_symbols",
            "announcement_pairs",
            "announcement_contracts",
            "symbols",
            "pairs",
            "contracts",
        ):
            values.extend(str(item) for item in _tuple_text(source.get(key)))
    return any(_exchange_metadata_value_matches(value, expected) for value in values)


def _compact_exchange_identity(value: object) -> str:
    return str(value or "").upper().replace("-", "").replace("_", "").replace("/", "").replace(" ", "").strip()


def _exchange_metadata_value_matches(value: object, expected: set[str]) -> bool:
    raw = str(value or "").upper().strip()
    clean = _compact_exchange_identity(raw)
    if not clean:
        return False
    candidates = {clean}
    for sep in ("/", "-", "_", " "):
        if sep in raw:
            base = raw.split(sep, 1)[0]
            if _compact_exchange_identity(base):
                candidates.add(_compact_exchange_identity(base))
    for suffix in _QUOTE_ASSET_SUFFIXES:
        if clean.endswith(suffix) and len(clean) > len(suffix):
            candidates.add(clean[: -len(suffix)])
    return bool(candidates & expected)


_QUOTE_ASSET_SUFFIXES = (
    "USDT",
    "USDC",
    "FDUSD",
    "TUSD",
    "BUSD",
    "USD",
    "BTC",
    "ETH",
    "BNB",
    "TRY",
    "EUR",
)


def _structured_metadata_from_raw_map(raw_map: Mapping[str, Any]) -> dict[str, Any]:
    event = raw_map.get("event") if isinstance(raw_map.get("event"), Mapping) else {}
    calendar = raw_map.get("calendar") if isinstance(raw_map.get("calendar"), Mapping) else {}
    supply = raw_map.get("supply") if isinstance(raw_map.get("supply"), Mapping) else {}
    event_time = (
        raw_map.get("event_time")
        or event.get("event_time")
        or calendar.get("event_time")
        or supply.get("timestamp")
    )
    unlock_pct = supply.get("unlock_pct_circulating", raw_map.get("unlock_pct_circulating"))
    unlock_materiality = (
        supply.get("unlock_materiality")
        or event.get("unlock_materiality")
        or _unlock_materiality(unlock_pct)
    )
    return {
        "structured_event_time": _text_or_none(event_time),
        "structured_event_time_source": _text_or_none(event.get("event_time_source") or calendar.get("event_time_source")),
        "calendar_event_category": _text_or_none(event.get("event_category") or calendar.get("event_category")),
        "calendar_confirmed": _bool_or_none(event.get("calendar_confirmed", calendar.get("confirmed"))),
        "calendar_original_source_url": _text_or_none(event.get("calendar_original_source_url") or calendar.get("original_source_url")),
        "unlock_amount": supply.get("unlock_amount", raw_map.get("unlock_amount")),
        "unlock_pct_circulating": unlock_pct,
        "unlock_type": _text_or_none(supply.get("unlock_type") or event.get("unlock_type") or raw_map.get("unlock_type")),
        "vesting_category": _text_or_none(supply.get("vesting_category") or event.get("vesting_category") or raw_map.get("vesting_category")),
        "unlock_materiality": _text_or_none(unlock_materiality),
    }


def _unlock_materiality(value: object) -> str | None:
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return None
    pct = pct / 100.0 if pct > 1.0 else pct
    if pct >= 0.10:
        return "large"
    if pct >= 0.05:
        return "material"
    if pct > 0:
        return "small"
    return "none"


def _bool_or_none(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    return str(value).strip().casefold() in {"1", "true", "yes", "confirmed", "verified"}


def _text_or_none(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _tuple_text(value: object) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.replace(";", ",").split(",") if part.strip())
    if isinstance(value, Mapping):
        return tuple(str(item).strip() for item in value.values() if str(item).strip())
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return (str(value),)


def _row_from_object(item: object | Mapping[str, Any] | None) -> dict[str, Any]:
    if item is None:
        return {}
    if isinstance(item, Mapping):
        return dict(item)
    return dict(getattr(item, "__dict__", {}) or {})


def _merge_preserving_non_empty(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in dict(overlay).items():
        if value in (None, "", [], {}, ()):
            continue
        merged[key] = value
    return merged


def _find_hypothesis(hypotheses: Iterable[object], hypothesis_id: str | None) -> object | None:
    if not hypothesis_id:
        return None
    for item in hypotheses:
        if str(getattr(item, "hypothesis_id", "") or "") == hypothesis_id:
            return item
    return None


def _catalyst_link_ok(
    text: str,
    request: EvidenceAcquisitionRequest,
    plan_query: event_llm_evidence_planner.EvidencePlanQuery,
) -> bool:
    terms = [
        request.external_asset,
        request.event_name,
        request.source_pack.replace("_pack", "").replace("_", " "),
        plan_query.purpose.replace("_", " "),
    ]
    catalyst_terms = (
        "listing", "perp", "futures", "unlock", "vesting", "exploit", "hack",
        "pre ipo", "pre-ipo", "tokenized stock", "exposure", "stake",
        "strategic investment", "valuation", "world cup", "fan token",
        "prediction market", "official", "announcement", "acquisition",
    )
    if any(clean_text(term) and clean_text(term) in text for term in terms):
        return True
    return any(term in text for term in catalyst_terms)


def _generic_cooccurrence(text: str, request: EvidenceAcquisitionRequest) -> bool:
    asset = clean_text(request.symbol or request.coin_id)
    if not asset or asset not in text:
        return False
    mechanism_terms = ("because", "driven by", "after", "listing", "unlock", "exploit", "hack", "exposure", "stake", "valuation", "resumes trading")
    return not any(term in text for term in mechanism_terms)


def _denial_or_correction(text: str) -> bool:
    return any(term in text for term in ("denies", "denied", "not affiliated", "false report", "correction", "not hacked", "ruled out"))


def _case_sensitive_symbol(raw: RawDiscoveredEvent, symbol: str) -> bool:
    if not symbol:
        return False
    haystack = " ".join(str(value or "") for value in (raw.title, raw.body))
    return symbol.upper() in haystack or f"${symbol.upper()}" in haystack


def _provider_unavailable_from_warnings(warnings: Iterable[str]) -> bool:
    text = " ".join(str(warning) for warning in warnings).casefold()
    return any(token in text for token in ("missing api token", "missing api key", "not configured", "requires"))


def _provider_backoff_from_warnings(warnings: Iterable[str]) -> bool:
    return "backoff" in " ".join(str(warning) for warning in warnings).casefold()


def _absence_meaningful_for_hint(provider_hint: str, coverage_status: str) -> bool:
    status = str(coverage_status or event_source_registry.ProviderCoverageStatus.COMPLETE.value)
    if status != event_source_registry.ProviderCoverageStatus.COMPLETE.value:
        return False
    hint = str(provider_hint or "").casefold()
    return hint in {
        "official_exchange",
        "project_blog_rss",
        "coinmarketcal",
        "tokenomist",
        "coinalyze",
        "binance_announcements",
        "bybit_announcements",
    }


def _request_dedupe_key(request: EvidenceAcquisitionRequest | None) -> str | None:
    if request is None:
        return None
    if request.core_opportunity_id:
        return "|".join(("core", request.core_opportunity_id, request.source_pack))
    return "|".join(("asset", request.incident_id or "", request.coin_id or request.symbol, request.source_pack))


def _core_opportunity_id_for_row(row: Mapping[str, Any]) -> str | None:
    explicit = str(row.get("core_opportunity_id") or row.get("aggregated_candidate_id") or "").strip()
    if explicit:
        return explicit
    try:
        return event_core_opportunities.core_opportunity_id_for_row(row)
    except Exception:  # noqa: BLE001 - acquisition planning must fail soft.
        return None
