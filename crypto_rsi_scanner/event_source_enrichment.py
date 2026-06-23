"""Fail-soft full-source enrichment for Event Alpha research rows."""

from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable
from urllib.request import Request, urlopen

from .event_models import RawDiscoveredEvent


FetchFn = Callable[[str, float], str | bytes]


@dataclass(frozen=True)
class EventSourceEnrichmentConfig:
    enabled: bool = False
    cache_dir: Path | None = None
    timeout_seconds: float = 10.0
    max_chars: int = 12000
    max_rows_per_run: int = 0
    min_source_confidence: float = 0.55


@dataclass(frozen=True)
class EventSourceEnrichmentResult:
    raw_event: RawDiscoveredEvent
    enriched_text: str
    used_cache: bool = False
    fetched: bool = False
    warning: str | None = None


def should_enrich_source(raw_event: RawDiscoveredEvent, *, min_source_confidence: float = 0.55) -> bool:
    """Return true for high-signal rows worth full-content enrichment."""
    if not raw_event.source_url:
        return False
    if float(raw_event.source_confidence or 0.0) < min_source_confidence:
        return False
    text = " ".join(str(part or "") for part in (raw_event.title, raw_event.body)).casefold()
    return any(
        phrase in text
        for phrase in (
            "pre-ipo",
            "pre ipo",
            "tokenized stock",
            "prediction market",
            "listing",
            "unlock",
            "exploit",
            "hack",
            "regulatory",
            "stablecoin",
            "world cup",
            "fan token",
        )
    )


def enrich_source_text(
    raw_event: RawDiscoveredEvent,
    *,
    cfg: EventSourceEnrichmentConfig | None = None,
    fetch_fn: FetchFn | None = None,
) -> EventSourceEnrichmentResult:
    """Fetch/cache source text, returning the original summary on failure."""
    cfg = cfg or EventSourceEnrichmentConfig()
    original = _summary_text(raw_event)[: max(1, int(cfg.max_chars or 1))]
    if not cfg.enabled:
        return EventSourceEnrichmentResult(raw_event=raw_event, enriched_text=original, warning="source enrichment disabled")
    if not should_enrich_source(raw_event, min_source_confidence=cfg.min_source_confidence):
        return EventSourceEnrichmentResult(raw_event=raw_event, enriched_text=original, warning="source not selected for enrichment")
    if not raw_event.source_url:
        return EventSourceEnrichmentResult(raw_event=raw_event, enriched_text=original, warning="missing source URL")

    cache_path = _cache_path(cfg.cache_dir, raw_event.source_url)
    if cache_path and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            text = str(cached.get("text") or "")
            if text:
                return EventSourceEnrichmentResult(
                    raw_event=raw_event,
                    enriched_text=text[: max(1, int(cfg.max_chars or 1))],
                    used_cache=True,
                )
        except Exception:  # noqa: BLE001 - broken cache should fail soft and refetch.
            pass

    try:
        raw_html = _fetch(raw_event.source_url, cfg.timeout_seconds, fetch_fn)
        extracted = extract_html_text(raw_html)[: max(1, int(cfg.max_chars or 1))]
        enriched = extracted or original
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps({"url": raw_event.source_url, "text": enriched}, sort_keys=True), encoding="utf-8")
        return EventSourceEnrichmentResult(raw_event=raw_event, enriched_text=enriched, fetched=True)
    except Exception as exc:  # noqa: BLE001 - live source fetch must never crash a research cycle.
        return EventSourceEnrichmentResult(
            raw_event=raw_event,
            enriched_text=original,
            warning=f"source enrichment failed: {type(exc).__name__}",
        )


def annotate_raw_event_with_enrichment(result: EventSourceEnrichmentResult) -> RawDiscoveredEvent:
    """Return a raw event carrying enriched source text in raw_json metadata."""
    payload = dict(result.raw_event.raw_json or {})
    payload["source_enrichment"] = {
        "enriched_text": result.enriched_text,
        "used_cache": result.used_cache,
        "fetched": result.fetched,
        "warning": result.warning,
        "research_only": True,
    }
    return replace(result.raw_event, raw_json=payload)


def extract_html_text(source: str | bytes) -> str:
    """Extract readable text from HTML using the stdlib only."""
    data = source.decode("utf-8", errors="ignore") if isinstance(source, bytes) else str(source or "")
    data = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", data)
    parser = _TextHTMLParser()
    parser.feed(data)
    text = " ".join(_clean_text_parts(parser.parts))
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fetch(url: str, timeout: float, fetch_fn: FetchFn | None) -> str | bytes:
    if fetch_fn is not None:
        return fetch_fn(url, timeout)
    request = Request(url, headers={"User-Agent": "crypto-rsi-scanner-event-alpha/1.0"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - explicit opt-in research fetch.
        return response.read()


def _summary_text(raw_event: RawDiscoveredEvent) -> str:
    return " ".join(str(part or "") for part in (raw_event.title, raw_event.body)).strip()


def _cache_path(cache_dir: Path | None, url: str) -> Path | None:
    if cache_dir is None:
        return None
    digest = hashlib.sha1(str(url or "").encode("utf-8")).hexdigest()
    return Path(cache_dir).expanduser() / f"{digest}.json"


class _TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = str(data or "").strip()
        if text:
            self.parts.append(text)


_NAV_OR_FOOTER_TEXT = {
    "markets",
    "prices",
    "crypto prices",
    "market cap",
    "learn",
    "news",
    "newsletter",
    "advertise",
    "about",
    "contact",
    "privacy policy",
    "terms of service",
    "sign in",
    "log in",
    "subscribe",
    "sponsored",
}


def _clean_text_parts(parts: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    for part in parts:
        text = html.unescape(str(part or "")).strip()
        if not text:
            continue
        if _is_source_noise_text(text):
            continue
        cleaned.append(text)
    return cleaned


def _is_source_noise_text(text: str) -> bool:
    compact = re.sub(r"\s+", " ", text).strip()
    lowered = compact.casefold()
    if lowered in _NAV_OR_FOOTER_TEXT:
        return True
    if len(compact) <= 80 and (lowered.startswith("by ") or lowered.startswith("edited by ")):
        return True
    if len(compact) <= 120 and re.search(r"\b(home|markets|prices|news|learn|advertise|newsletter)\b", lowered):
        nav_hits = sum(1 for token in ("home", "markets", "prices", "news", "learn", "advertise", "newsletter") if token in lowered)
        if nav_hits >= 3:
            return True
    ticker_fragments = re.findall(r"\b[A-Z0-9]{2,12}(?:USDT|USD)?\b\s*(?:[$€£]?\d[\d,.]*|[+-]?\d+(?:\.\d+)?%)", compact)
    if len(ticker_fragments) >= 3:
        return True
    if len(compact) <= 220 and compact.count("%") >= 3 and compact.count("$") >= 2:
        return True
    if len(compact) <= 220 and re.search(r"\bBTC\b.*\bETH\b.*\bSOL\b", compact):
        return True
    return False
