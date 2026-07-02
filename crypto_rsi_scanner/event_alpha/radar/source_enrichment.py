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
from typing import Any, Callable, Iterable, Mapping, Protocol
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ... import config
from ...event_models import RawDiscoveredEvent
from ...event_resolver import clean_text
from ...llm_providers.base import LLMProviderResult


FetchFn = Callable[[str, float], object]
SOURCE_ENRICHMENT_SCHEMA_VERSION = "event_source_enrichment_cache_v3"
SOURCE_ENRICHMENT_EXTRACTOR_VERSION = "source_enrichment_extractor_v1"

ARTICLE_QUALITY_GOOD = "good"
ARTICLE_QUALITY_THIN = "thin"
ARTICLE_QUALITY_BOILERPLATE_HEAVY = "boilerplate_heavy"
ARTICLE_QUALITY_REDIRECT_PLACEHOLDER = "redirect_placeholder"
ARTICLE_QUALITY_PAYWALL_OR_BLOCKED = "paywall_or_blocked"
ARTICLE_QUALITY_FETCH_FAILED = "fetch_failed"
ARTICLE_QUALITY_FIXTURE_TEXT_USED = "fixture_text_used"
USABLE_ARTICLE_QUALITY_STATUSES = frozenset({
    ARTICLE_QUALITY_GOOD,
    ARTICLE_QUALITY_FIXTURE_TEXT_USED,
})
LLM_SOURCE_PAGE_TYPES = frozenset({
    "article",
    "official_announcement",
    "market_recap",
    "seo_affiliate",
    "prediction_market_context",
    "redirect_placeholder",
    "blocked_or_paywalled",
    "source_noise",
    "unknown",
})

SOURCE_TRIAGE_SEND_TO_LLM = "send_to_llm_frame_analyzer"
SOURCE_TRIAGE_RAW_OBSERVATION = "keep_raw_observation"
SOURCE_TRIAGE_DIAGNOSTIC_ONLY = "diagnostic_only"
SOURCE_TRIAGE_REJECT = "reject"


@dataclass(frozen=True)
class EventSourceEnrichmentConfig:
    enabled: bool = False
    cache_dir: Path | None = None
    timeout_seconds: float = 10.0
    max_chars: int = 12000
    max_rows_per_run: int = 0
    min_source_confidence: float = 0.55
    extractor_version: str = SOURCE_ENRICHMENT_EXTRACTOR_VERSION
    cleaner_version: str = config.EVENT_SOURCE_ENRICHMENT_CLEANER_VERSION


@dataclass(frozen=True)
class EventSourceFetchResult:
    body: str | bytes
    fetched_url: str
    final_url: str
    redirect_chain: tuple[str, ...] = ()
    status_code: int | None = None


@dataclass(frozen=True)
class EventArticleExtraction:
    extractor_version: str
    cleaner_version: str
    fetched_url: str | None
    final_url: str | None
    canonical_url: str | None
    redirect_chain: tuple[str, ...] = ()
    title: str | None = None
    byline: str | None = None
    source: str | None = None
    published_at: str | None = None
    body_text: str = ""
    body_char_count: int = 0
    boilerplate_ratio: float = 0.0
    ticker_sidebar_detected: bool = False
    article_quality_status: str = ARTICLE_QUALITY_THIN
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "extractor_version": self.extractor_version,
            "cleaner_version": self.cleaner_version,
            "fetched_url": self.fetched_url,
            "final_url": self.final_url,
            "canonical_url": self.canonical_url,
            "redirect_chain": list(self.redirect_chain),
            "title": self.title,
            "byline": self.byline,
            "source": self.source,
            "published_at": self.published_at,
            "body_text": self.body_text,
            "body_char_count": self.body_char_count,
            "boilerplate_ratio": self.boilerplate_ratio,
            "ticker_sidebar_detected": self.ticker_sidebar_detected,
            "article_quality_status": self.article_quality_status,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class EventSourceTriageResult:
    is_real_article: bool
    source_is_official: bool
    source_is_recapped_news: bool
    source_is_affiliate_or_seo: bool
    source_has_direct_token_mechanism: bool
    source_has_candidate_and_catalyst: bool
    source_quality_score: float
    decision: str
    reason_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_real_article": self.is_real_article,
            "source_is_official": self.source_is_official,
            "source_is_recapped_news": self.source_is_recapped_news,
            "source_is_affiliate_or_seo": self.source_is_affiliate_or_seo,
            "source_has_direct_token_mechanism": self.source_has_direct_token_mechanism,
            "source_has_candidate_and_catalyst": self.source_has_candidate_and_catalyst,
            "source_quality_score": self.source_quality_score,
            "decision": self.decision,
            "reason_codes": list(self.reason_codes),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class EventSourceQualityJudgment:
    is_real_article: bool
    article_quality_status: str
    source_quality_score: float
    reason: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventLLMSourceTriage:
    page_type: str
    is_real_article: bool
    article_quality: str
    boilerplate_ratio_estimate: float
    is_official_source: bool
    is_recap: bool
    is_affiliate_or_seo: bool
    candidate_catalyst_mechanism_present: bool
    evidence_quote: str
    confidence: float
    reason: str = ""
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_type": self.page_type,
            "is_real_article": self.is_real_article,
            "article_quality": self.article_quality,
            "boilerplate_ratio_estimate": self.boilerplate_ratio_estimate,
            "is_official_source": self.is_official_source,
            "is_recap": self.is_recap,
            "is_affiliate_or_seo": self.is_affiliate_or_seo,
            "candidate_catalyst_mechanism_present": self.candidate_catalyst_mechanism_present,
            "evidence_quote": self.evidence_quote,
            "confidence": self.confidence,
            "reason": self.reason,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class EventSourceQualityJudgeConfig:
    enabled: bool = False
    min_importance_score: float = 70.0
    prompt_version: str = "llm_source_quality_v1"


class LLMSourceQualityJudgeProvider(Protocol):
    name: str

    def judge_source_quality(self, packet: Mapping[str, Any]) -> LLMProviderResult:
        """Return structured article-quality metadata for a source packet."""


@dataclass(frozen=True)
class EventSourceEnrichmentResult:
    raw_event: RawDiscoveredEvent
    enriched_text: str
    used_cache: bool = False
    fetched: bool = False
    warning: str | None = None
    status: str | None = None
    article: EventArticleExtraction | None = None
    triage: EventSourceTriageResult | None = None


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
    if _fixture_source_url(raw_event.source_url):
        article = _fixture_article(raw_event, cfg=cfg, text=original)
        triage = triage_source(raw_event, article=article)
        return EventSourceEnrichmentResult(
            raw_event=raw_event,
            enriched_text=original,
            warning=None,
            status="fixture_text_used",
            article=article,
            triage=triage,
        )

    cache_path = _cache_path(cfg.cache_dir, raw_event.source_url)
    if cache_path and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            text = str(cached.get("text") or "")
            if text and _cache_entry_current(cached, raw_event, cleaner_version=cfg.cleaner_version):
                article = _article_from_cache(cached, fallback_text=text)
                triage = _triage_from_cache(cached) or triage_source(raw_event, article=article)
                return EventSourceEnrichmentResult(
                    raw_event=raw_event,
                    enriched_text=text[: max(1, int(cfg.max_chars or 1))],
                    used_cache=True,
                    status="cache_hit",
                    article=article,
                    triage=triage,
                )
        except Exception:  # noqa: BLE001 - broken cache should fail soft and refetch.
            pass

    try:
        fetch_result = _fetch(raw_event.source_url, cfg.timeout_seconds, fetch_fn)
        article = extract_article(fetch_result, cfg=cfg, fallback_title=raw_event.title)
        extracted = article.body_text[: max(1, int(cfg.max_chars or 1))]
        enriched = extracted or original
        triage = triage_source(raw_event, article=article)
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(
                    {
                        "schema_version": SOURCE_ENRICHMENT_SCHEMA_VERSION,
                        "extractor_version": cfg.extractor_version,
                        "cleaner_version": cfg.cleaner_version,
                        "fetched_at": raw_event.fetched_at.isoformat() if raw_event.fetched_at else None,
                        "url": raw_event.source_url,
                        "fetched_url": article.fetched_url,
                        "final_url": article.final_url,
                        "canonical_url": article.canonical_url,
                        "redirect_chain": list(article.redirect_chain),
                        "source_content_hash": _source_content_hash(raw_event),
                        "cleaned_text_hash": hashlib.sha1(enriched.encode("utf-8")).hexdigest(),
                        "text": enriched,
                        "article": article.to_dict(),
                        "triage": triage.to_dict(),
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
        return EventSourceEnrichmentResult(
            raw_event=raw_event,
            enriched_text=enriched,
            fetched=True,
            status=article.article_quality_status,
            article=article,
            triage=triage,
            warning=_quality_warning(article, triage),
        )
    except HTTPError as exc:
        article = _failed_article(raw_event, cfg=cfg, status=ARTICLE_QUALITY_PAYWALL_OR_BLOCKED, warning=f"http_{exc.code}")
        triage = triage_source(raw_event, article=article)
        return EventSourceEnrichmentResult(
            raw_event=raw_event,
            enriched_text=original,
            warning=f"source enrichment failed: HTTPError",
            status=ARTICLE_QUALITY_PAYWALL_OR_BLOCKED,
            article=article,
            triage=triage,
        )
    except Exception as exc:  # noqa: BLE001 - live source fetch must never crash a research cycle.
        article = _failed_article(raw_event, cfg=cfg, status=ARTICLE_QUALITY_FETCH_FAILED, warning=type(exc).__name__)
        triage = triage_source(raw_event, article=article)
        return EventSourceEnrichmentResult(
            raw_event=raw_event,
            enriched_text=original,
            warning=f"source enrichment failed: {type(exc).__name__}",
            status=ARTICLE_QUALITY_FETCH_FAILED,
            article=article,
            triage=triage,
        )


def annotate_raw_event_with_enrichment(result: EventSourceEnrichmentResult) -> RawDiscoveredEvent:
    """Return a raw event carrying enriched source text in raw_json metadata."""
    payload = dict(result.raw_event.raw_json or {})
    payload["source_enrichment"] = {
        "schema_version": SOURCE_ENRICHMENT_SCHEMA_VERSION,
        "extractor_version": result.article.extractor_version if result.article else SOURCE_ENRICHMENT_EXTRACTOR_VERSION,
        "cleaner_version": result.article.cleaner_version if result.article else config.EVENT_SOURCE_ENRICHMENT_CLEANER_VERSION,
        "enriched_text": result.enriched_text,
        "used_cache": result.used_cache,
        "fetched": result.fetched,
        "warning": result.warning,
        "status": result.status,
        "article_quality_status": result.article.article_quality_status if result.article else result.status,
        "article": result.article.to_dict() if result.article else None,
        "source_triage": result.triage.to_dict() if result.triage else None,
        "research_only": True,
    }
    return replace(result.raw_event, raw_json=payload)


def enriched_text_for_llm(raw_event: RawDiscoveredEvent) -> str:
    """Return enriched text only when the article-quality gate considers it usable."""
    payload = raw_event.raw_json if isinstance(raw_event.raw_json, Mapping) else {}
    enrichment = payload.get("source_enrichment") if isinstance(payload.get("source_enrichment"), Mapping) else {}
    if not enrichment:
        return ""
    status = str(enrichment.get("article_quality_status") or enrichment.get("status") or "").strip()
    triage = enrichment.get("source_triage") if isinstance(enrichment.get("source_triage"), Mapping) else {}
    decision = str(triage.get("decision") or "").strip()
    if status not in USABLE_ARTICLE_QUALITY_STATUSES:
        return ""
    if decision in {SOURCE_TRIAGE_DIAGNOSTIC_ONLY, SOURCE_TRIAGE_REJECT}:
        return ""
    return str(enrichment.get("enriched_text") or "")


def source_enrichment_metadata(raw_event: RawDiscoveredEvent | Mapping[str, Any]) -> dict[str, Any]:
    """Return compact enrichment metadata for packets/cards/audits."""
    payload: Mapping[str, Any]
    if isinstance(raw_event, Mapping):
        payload = raw_event.get("raw_json") if isinstance(raw_event.get("raw_json"), Mapping) else raw_event
    else:
        payload = raw_event.raw_json if isinstance(raw_event.raw_json, Mapping) else {}
    enrichment = payload.get("source_enrichment") if isinstance(payload.get("source_enrichment"), Mapping) else {}
    article = enrichment.get("article") if isinstance(enrichment.get("article"), Mapping) else {}
    triage = enrichment.get("source_triage") if isinstance(enrichment.get("source_triage"), Mapping) else {}
    return {
        "extractor_version": enrichment.get("extractor_version") or article.get("extractor_version"),
        "cleaner_version": enrichment.get("cleaner_version") or article.get("cleaner_version"),
        "article_quality_status": enrichment.get("article_quality_status") or article.get("article_quality_status") or enrichment.get("status"),
        "body_char_count": article.get("body_char_count"),
        "boilerplate_ratio": article.get("boilerplate_ratio"),
        "ticker_sidebar_detected": article.get("ticker_sidebar_detected"),
        "fetched_url": article.get("fetched_url"),
        "final_url": article.get("final_url"),
        "canonical_url": article.get("canonical_url"),
        "source_triage_decision": triage.get("decision"),
        "source_quality_score": triage.get("source_quality_score"),
        "is_real_article": triage.get("is_real_article"),
        "source_has_direct_token_mechanism": triage.get("source_has_direct_token_mechanism"),
        "source_has_candidate_and_catalyst": triage.get("source_has_candidate_and_catalyst"),
        "warnings": tuple(str(item) for item in (article.get("warnings") or enrichment.get("warnings") or ()) if item),
    }


def extract_article(
    fetch_result: EventSourceFetchResult | Mapping[str, Any] | str | bytes,
    *,
    cfg: EventSourceEnrichmentConfig | None = None,
    fallback_title: str | None = None,
) -> EventArticleExtraction:
    """Extract article text and auditable quality metadata from a fetch result."""
    cfg = cfg or EventSourceEnrichmentConfig()
    normalized = _normalize_fetch_result(fetch_result, fetched_url=None)
    data = normalized.body.decode("utf-8", errors="ignore") if isinstance(normalized.body, bytes) else str(normalized.body or "")
    stripped = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", data)
    parser = _TextHTMLParser()
    parser.feed(stripped)
    raw_text = " ".join(html.unescape(part).strip() for part in parser.parts if str(part or "").strip())
    cleaned_parts = _clean_text_parts(parser.parts)
    body_text = html.unescape(re.sub(r"\s+", " ", " ".join(cleaned_parts))).strip()
    metadata = _html_metadata(stripped)
    title = metadata.get("title") or fallback_title
    ticker_sidebar_detected = _ticker_sidebar_detected(raw_text)
    boilerplate_ratio = _boilerplate_ratio(raw_text, body_text, ticker_sidebar_detected=ticker_sidebar_detected)
    warnings: list[str] = []
    if ticker_sidebar_detected:
        warnings.append("ticker_sidebar_detected")
    if boilerplate_ratio >= 0.55:
        warnings.append("boilerplate_heavy")
    if normalized.status_code is not None and normalized.status_code >= 400:
        status = ARTICLE_QUALITY_PAYWALL_OR_BLOCKED
        warnings.append(f"http_{normalized.status_code}")
    elif _blocked_or_paywalled(data, body_text):
        status = ARTICLE_QUALITY_PAYWALL_OR_BLOCKED
        warnings.append("paywall_or_blocked")
    elif _redirect_placeholder(normalized, body_text, title):
        status = ARTICLE_QUALITY_REDIRECT_PLACEHOLDER
        warnings.append("redirect_placeholder")
    elif len(body_text) < 220:
        status = ARTICLE_QUALITY_THIN
        warnings.append("thin_article_body")
    elif ticker_sidebar_detected or boilerplate_ratio >= 0.60:
        status = ARTICLE_QUALITY_BOILERPLATE_HEAVY
    else:
        status = ARTICLE_QUALITY_GOOD
    return EventArticleExtraction(
        extractor_version=cfg.extractor_version,
        cleaner_version=cfg.cleaner_version,
        fetched_url=normalized.fetched_url,
        final_url=normalized.final_url,
        canonical_url=metadata.get("canonical_url"),
        redirect_chain=normalized.redirect_chain,
        title=title,
        byline=metadata.get("byline"),
        source=metadata.get("source"),
        published_at=metadata.get("published_at"),
        body_text=body_text,
        body_char_count=len(body_text),
        boilerplate_ratio=round(boilerplate_ratio, 3),
        ticker_sidebar_detected=ticker_sidebar_detected,
        article_quality_status=status,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def extract_html_text(source: str | bytes) -> str:
    """Extract readable text from HTML using the stdlib only."""
    return extract_article(source).body_text


def triage_source(
    raw_event: RawDiscoveredEvent,
    *,
    article: EventArticleExtraction | None = None,
) -> EventSourceTriageResult:
    """Cheap deterministic source triage before spending LLM budget."""
    payload = raw_event.raw_json if isinstance(raw_event.raw_json, Mapping) else {}
    source_origin = clean_text(str(payload.get("source_origin") or raw_event.provider or ""))
    domain = clean_text(urlparse(str(raw_event.source_url or "")).netloc)
    article_text = article.body_text if article else ""
    text = clean_text(" ".join(str(item or "") for item in (
        raw_event.title,
        raw_event.body,
        article_text,
        payload.get("description"),
        source_origin,
    )))
    status = article.article_quality_status if article else ARTICLE_QUALITY_THIN
    is_real_article = status in USABLE_ARTICLE_QUALITY_STATUSES
    source_is_official = any(term in " ".join((domain, source_origin)) for term in (
        "official", "binance", "bybit", "coinbase", "okx", "kraken", "project blog",
    ))
    source_is_recapped_news = any(term in text for term in (
        "market recap", "price prediction", "top gainers", "today's crypto prices", "technical analysis",
    ))
    source_is_affiliate_or_seo = any(term in text for term in (
        "referral code", "invite code", "sign up now", "register binance", "lifetime fee", "bonus",
    ))
    source_has_direct_token_mechanism = any(term in text for term in (
        "tokenized stock", "pre ipo", "pre-ipo", "lets users trade", "exposure", "listing",
        "listed on", "perp listing", "unlock", "vesting", "exploit", "hack", "strategic investment",
        "acquisition", "stake", "fan token",
    ))
    source_has_candidate_and_catalyst = _has_candidate_and_catalyst(text, payload)
    score = _triage_score(
        status=status,
        is_real_article=is_real_article,
        source_is_official=source_is_official,
        source_is_recapped_news=source_is_recapped_news,
        source_is_affiliate_or_seo=source_is_affiliate_or_seo,
        source_has_direct_token_mechanism=source_has_direct_token_mechanism,
        source_has_candidate_and_catalyst=source_has_candidate_and_catalyst,
        boilerplate_ratio=article.boilerplate_ratio if article else 1.0,
    )
    reasons: list[str] = [f"article_quality_{status}"]
    warnings: list[str] = list(article.warnings if article else ())
    if source_is_official:
        reasons.append("official_source")
    if source_has_direct_token_mechanism:
        reasons.append("direct_token_mechanism")
    if source_has_candidate_and_catalyst:
        reasons.append("candidate_and_catalyst")
    if source_is_affiliate_or_seo:
        reasons.append("affiliate_or_seo")
        warnings.append("affiliate_or_seo_source")
    if source_is_recapped_news:
        reasons.append("recapped_news")
    if status in {
        ARTICLE_QUALITY_REDIRECT_PLACEHOLDER,
        ARTICLE_QUALITY_PAYWALL_OR_BLOCKED,
        ARTICLE_QUALITY_FETCH_FAILED,
    }:
        decision = SOURCE_TRIAGE_REJECT
    elif source_is_affiliate_or_seo or status == ARTICLE_QUALITY_BOILERPLATE_HEAVY:
        decision = SOURCE_TRIAGE_DIAGNOSTIC_ONLY
    elif "polymarket" in domain or "prediction market" in source_origin:
        decision = SOURCE_TRIAGE_RAW_OBSERVATION
        reasons.append("prediction_market_context_only")
    elif is_real_article and (source_is_official or source_has_direct_token_mechanism or source_has_candidate_and_catalyst):
        decision = SOURCE_TRIAGE_SEND_TO_LLM
    else:
        decision = SOURCE_TRIAGE_RAW_OBSERVATION
    return EventSourceTriageResult(
        is_real_article=is_real_article,
        source_is_official=source_is_official,
        source_is_recapped_news=source_is_recapped_news,
        source_is_affiliate_or_seo=source_is_affiliate_or_seo,
        source_has_direct_token_mechanism=source_has_direct_token_mechanism,
        source_has_candidate_and_catalyst=source_has_candidate_and_catalyst,
        source_quality_score=round(max(0.0, min(100.0, score)), 2),
        decision=decision,
        reason_codes=tuple(dict.fromkeys(reasons)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def build_source_quality_judge_packet(
    raw_event: RawDiscoveredEvent,
    *,
    article: EventArticleExtraction | None = None,
    triage: EventSourceTriageResult | None = None,
    prompt_version: str = "llm_source_quality_v1",
) -> dict[str, Any]:
    article = article or _article_from_payload(raw_event) or _fixture_article(
        raw_event,
        cfg=EventSourceEnrichmentConfig(),
        text=_summary_text(raw_event),
    )
    triage = triage or triage_source(raw_event, article=article)
    return {
        "schema_version": "event_source_quality_judge_v1",
        "prompt_version": prompt_version,
        "raw_id": raw_event.raw_id,
        "provider": raw_event.provider,
        "source_url": raw_event.source_url,
        "title": raw_event.title,
        "body_excerpt": article.body_text[:4000],
        "article": article.to_dict(),
        "deterministic_triage": triage.to_dict(),
        "instructions": (
            "Classify article extraction quality only. Do not recommend trades, "
            "alert tiers, catalysts, or assets."
        ),
    }


def build_llm_source_triage_packet(
    raw_event: RawDiscoveredEvent,
    *,
    article: EventArticleExtraction | None = None,
    triage: EventSourceTriageResult | None = None,
    prompt_version: str = "llm_source_triage_v1",
) -> dict[str, Any]:
    article = article or _article_from_payload(raw_event) or _fixture_article(
        raw_event,
        cfg=EventSourceEnrichmentConfig(),
        text=_summary_text(raw_event),
    )
    triage = triage or triage_source(raw_event, article=article)
    return {
        "schema_version": "event_source_triage_v1",
        "prompt_version": prompt_version,
        "raw_id": raw_event.raw_id,
        "provider": raw_event.provider,
        "source_url": raw_event.source_url,
        "title": raw_event.title,
        "body_excerpt": article.body_text[:4000],
        "article": article.to_dict(),
        "deterministic_triage": triage.to_dict(),
        "allowed_page_types": sorted(LLM_SOURCE_PAGE_TYPES),
        "allowed_article_quality": sorted({
            ARTICLE_QUALITY_GOOD,
            ARTICLE_QUALITY_THIN,
            ARTICLE_QUALITY_BOILERPLATE_HEAVY,
            ARTICLE_QUALITY_REDIRECT_PLACEHOLDER,
            ARTICLE_QUALITY_PAYWALL_OR_BLOCKED,
            ARTICLE_QUALITY_FETCH_FAILED,
            ARTICLE_QUALITY_FIXTURE_TEXT_USED,
        }),
        "instructions": (
            "Classify source quality and whether the page contains a candidate/catalyst "
            "mechanism. Do not recommend trades, alerts, or routes."
        ),
    }


def run_llm_source_triage(
    raw_event: RawDiscoveredEvent,
    *,
    provider: LLMSourceQualityJudgeProvider | None,
    cfg: EventSourceQualityJudgeConfig | None = None,
) -> EventLLMSourceTriage | None:
    """Run optional LLM source triage, constrained by deterministic source triage."""
    cfg = cfg or EventSourceQualityJudgeConfig()
    if not cfg.enabled or provider is None:
        return None
    article = _article_from_payload(raw_event)
    deterministic = triage_source(raw_event, article=article) if article else None
    if deterministic and deterministic.source_quality_score < cfg.min_importance_score and deterministic.decision != SOURCE_TRIAGE_DIAGNOSTIC_ONLY:
        return None
    packet = build_llm_source_triage_packet(
        raw_event,
        article=article,
        triage=deterministic,
        prompt_version=cfg.prompt_version,
    )
    try:
        result = provider.judge_source_quality(packet)
    except Exception as exc:  # noqa: BLE001 - optional LLM triage must fail soft.
        return EventLLMSourceTriage(
            page_type="unknown",
            is_real_article=False,
            article_quality=ARTICLE_QUALITY_FETCH_FAILED,
            boilerplate_ratio_estimate=1.0,
            is_official_source=False,
            is_recap=False,
            is_affiliate_or_seo=False,
            candidate_catalyst_mechanism_present=False,
            evidence_quote="",
            confidence=0.0,
            reason=f"llm_source_triage_failed:{type(exc).__name__}",
            warnings=("llm_source_triage_failed",),
        )
    if result.warning or not result.raw:
        return EventLLMSourceTriage(
            page_type="unknown",
            is_real_article=False,
            article_quality=ARTICLE_QUALITY_FETCH_FAILED,
            boilerplate_ratio_estimate=1.0,
            is_official_source=False,
            is_recap=False,
            is_affiliate_or_seo=False,
            candidate_catalyst_mechanism_present=False,
            evidence_quote="",
            confidence=0.0,
            reason=result.warning or "llm_source_triage_missing_output",
            warnings=tuple(item for item in (result.warning,) if item),
        )
    return validate_llm_source_triage(
        result.raw,
        source_text=" ".join(str(part or "") for part in (raw_event.title, raw_event.body, article.body_text if article else "")),
        deterministic=deterministic,
    )


def run_source_quality_judge(
    raw_event: RawDiscoveredEvent,
    *,
    provider: LLMSourceQualityJudgeProvider | None,
    cfg: EventSourceQualityJudgeConfig | None = None,
) -> EventSourceQualityJudgment | None:
    """Run optional fixture/LLM source-quality judge with deterministic safety caps."""
    cfg = cfg or EventSourceQualityJudgeConfig()
    if not cfg.enabled or provider is None:
        return None
    article = _article_from_payload(raw_event)
    triage = triage_source(raw_event, article=article) if article else None
    if triage and triage.source_quality_score < cfg.min_importance_score and triage.decision != SOURCE_TRIAGE_DIAGNOSTIC_ONLY:
        return None
    packet = build_source_quality_judge_packet(
        raw_event,
        article=article,
        triage=triage,
        prompt_version=cfg.prompt_version,
    )
    try:
        result = provider.judge_source_quality(packet)
    except Exception as exc:  # noqa: BLE001 - optional judge must fail soft.
        return EventSourceQualityJudgment(
            is_real_article=False,
            article_quality_status=ARTICLE_QUALITY_FETCH_FAILED,
            source_quality_score=0.0,
            reason=f"source_quality_judge_failed:{type(exc).__name__}",
            warnings=("source_quality_judge_failed",),
        )
    if result.warning or not result.raw:
        return EventSourceQualityJudgment(
            is_real_article=False,
            article_quality_status=ARTICLE_QUALITY_FETCH_FAILED,
            source_quality_score=0.0,
            reason=result.warning or "source_quality_judge_missing_output",
            warnings=tuple(item for item in (result.warning,) if item),
        )
    return _validate_source_quality_judgment(result.raw, deterministic=triage)


def _fetch(url: str, timeout: float, fetch_fn: FetchFn | None) -> EventSourceFetchResult:
    if fetch_fn is not None:
        return _normalize_fetch_result(fetch_fn(url, timeout), fetched_url=url)
    request = Request(url, headers={"User-Agent": "crypto-rsi-scanner-event-alpha/1.0"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - explicit opt-in research fetch.
        final_url = response.geturl() or url
        redirect_chain = (url, final_url) if final_url != url else (url,)
        return EventSourceFetchResult(
            body=response.read(),
            fetched_url=url,
            final_url=final_url,
            redirect_chain=redirect_chain,
            status_code=getattr(response, "status", None),
        )


def _normalize_fetch_result(value: object, *, fetched_url: str | None) -> EventSourceFetchResult:
    if isinstance(value, EventSourceFetchResult):
        return value
    if isinstance(value, Mapping):
        body = value.get("body", value.get("text", value.get("html", value.get("content", ""))))
        final_url = str(value.get("final_url") or value.get("url") or fetched_url or "")
        redirect_chain_raw = value.get("redirect_chain") or (fetched_url, final_url)
        redirect_chain = tuple(str(item) for item in redirect_chain_raw if item) if isinstance(redirect_chain_raw, Iterable) and not isinstance(redirect_chain_raw, (str, bytes, Mapping)) else tuple(str(item) for item in (fetched_url, final_url) if item)
        return EventSourceFetchResult(
            body=body if isinstance(body, (str, bytes)) else str(body or ""),
            fetched_url=str(value.get("fetched_url") or fetched_url or final_url),
            final_url=final_url,
            redirect_chain=redirect_chain,
            status_code=_int_or_none(value.get("status_code")),
        )
    return EventSourceFetchResult(
        body=value if isinstance(value, (str, bytes)) else str(value or ""),
        fetched_url=str(fetched_url or ""),
        final_url=str(fetched_url or ""),
        redirect_chain=tuple(str(item) for item in (fetched_url,) if item),
    )


def _fixture_source_url(url: str) -> bool:
    try:
        parsed = urlparse(str(url or ""))
    except Exception:  # noqa: BLE001 - malformed fixture URLs should fail soft.
        return False
    host = (parsed.hostname or "").casefold()
    path = (parsed.path or "").casefold()
    return (
        host in {"example.test", "fixture.test", "test.local"}
        or host.endswith(".example.test")
        or host.endswith(".fixture.test")
        or "/fixtures/" in path
    )


def _summary_text(raw_event: RawDiscoveredEvent) -> str:
    return " ".join(str(part or "") for part in (raw_event.title, raw_event.body)).strip()


def _cache_path(cache_dir: Path | None, url: str) -> Path | None:
    if cache_dir is None:
        return None
    digest = hashlib.sha1(str(url or "").encode("utf-8")).hexdigest()
    return Path(cache_dir).expanduser() / f"{digest}.json"


def _cache_entry_current(
    cached: dict[str, object],
    raw_event: RawDiscoveredEvent,
    *,
    cleaner_version: str,
) -> bool:
    if cached.get("schema_version") != SOURCE_ENRICHMENT_SCHEMA_VERSION:
        return False
    if str(cached.get("cleaner_version") or "") != str(cleaner_version or ""):
        return False
    if str(cached.get("source_content_hash") or "") != _source_content_hash(raw_event):
        return False
    if not cached.get("cleaned_text_hash"):
        return False
    return True


def _source_content_hash(raw_event: RawDiscoveredEvent) -> str:
    source = " ".join(str(part or "") for part in (raw_event.title, raw_event.body, raw_event.content_hash))
    return hashlib.sha1(source.encode("utf-8")).hexdigest()


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


def _html_metadata(data: str) -> dict[str, str | None]:
    return {
        "title": _first_html_value(
            data,
            (
                r"(?is)<meta[^>]+property=[\"']og:title[\"'][^>]+content=[\"']([^\"']+)[\"']",
                r"(?is)<meta[^>]+name=[\"']twitter:title[\"'][^>]+content=[\"']([^\"']+)[\"']",
                r"(?is)<title[^>]*>(.*?)</title>",
                r"(?is)<h1[^>]*>(.*?)</h1>",
            ),
        ),
        "canonical_url": _first_html_value(
            data,
            (r"(?is)<link[^>]+rel=[\"']canonical[\"'][^>]+href=[\"']([^\"']+)[\"']",),
        ),
        "byline": _first_html_value(
            data,
            (
                r"(?is)<meta[^>]+name=[\"']author[\"'][^>]+content=[\"']([^\"']+)[\"']",
                r"(?is)<meta[^>]+property=[\"']article:author[\"'][^>]+content=[\"']([^\"']+)[\"']",
                r"(?is)<[^>]+class=[\"'][^\"']*(?:byline|author)[^\"']*[\"'][^>]*>(.*?)</[^>]+>",
            ),
        ),
        "source": _first_html_value(
            data,
            (
                r"(?is)<meta[^>]+property=[\"']og:site_name[\"'][^>]+content=[\"']([^\"']+)[\"']",
                r"(?is)<meta[^>]+name=[\"']application-name[\"'][^>]+content=[\"']([^\"']+)[\"']",
            ),
        ),
        "published_at": _first_html_value(
            data,
            (
                r"(?is)<meta[^>]+property=[\"']article:published_time[\"'][^>]+content=[\"']([^\"']+)[\"']",
                r"(?is)<time[^>]+datetime=[\"']([^\"']+)[\"']",
            ),
        ),
    }


def _first_html_value(data: str, patterns: Iterable[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, data)
        if match:
            value = html.unescape(re.sub(r"(?is)<[^>]+>", " ", match.group(1)))
            value = re.sub(r"\s+", " ", value).strip()
            if value:
                return value
    return None


def _ticker_sidebar_detected(raw_text: str) -> bool:
    compact = re.sub(r"\s+", " ", str(raw_text or ""))
    ticker_price = re.findall(r"\b[A-Z0-9]{2,12}\b\s*\$?\d[\d,.]*(?:\.\d+)?\s*(?:[+-]?\d+(?:\.\d+)?%)?", compact)
    crypto_tickers = re.findall(r"\b(?:BTC|ETH|SOL|XRP|DOGE|BNB|ADA|TRX|LINK|HYPE|ZEC|XMR|XLM)\b", compact)
    pct_count = compact.count("%")
    dollar_count = compact.count("$")
    return len(ticker_price) >= 8 or (len(crypto_tickers) >= 8 and pct_count >= 5 and dollar_count >= 5)


def _boilerplate_ratio(raw_text: str, body_text: str, *, ticker_sidebar_detected: bool) -> float:
    raw_len = max(1, len(str(raw_text or "")))
    body_len = len(str(body_text or ""))
    removed_ratio = max(0.0, min(1.0, (raw_len - body_len) / raw_len))
    nav_hits = sum(1 for token in ("latest news", "editor's choice", "most popular", "newsletter", "advertise", "terms of service") if token in clean_text(raw_text))
    ratio = removed_ratio
    if ticker_sidebar_detected:
        ratio = max(ratio, 0.72)
    if nav_hits >= 4:
        ratio = max(ratio, 0.62)
    elif nav_hits >= 2:
        ratio = max(ratio, 0.48)
    return round(ratio, 3)


def _blocked_or_paywalled(raw_data: str, body_text: str) -> bool:
    text = clean_text(" ".join((raw_data, body_text)))
    return any(
        phrase in text
        for phrase in (
            "access denied",
            "403 forbidden",
            "enable javascript",
            "checking your browser",
            "verify you are human",
            "captcha",
            "subscribe to continue",
            "sign in to continue",
            "paywall",
            "temporarily blocked",
        )
    )


def _redirect_placeholder(fetch_result: EventSourceFetchResult, body_text: str, title: str | None) -> bool:
    urls = " ".join(str(item or "") for item in (fetch_result.fetched_url, fetch_result.final_url, *fetch_result.redirect_chain)).casefold()
    normalized = clean_text(" ".join((body_text, title or "")))
    google_news_url = "news.google." in urls or "news.url.google." in urls
    if google_news_url and (normalized in {"google news", "news"} or len(normalized) <= 80):
        return True
    if "google news" == normalized and len(body_text) <= 80:
        return True
    return False


def _fixture_article(raw_event: RawDiscoveredEvent, *, cfg: EventSourceEnrichmentConfig, text: str) -> EventArticleExtraction:
    return EventArticleExtraction(
        extractor_version=cfg.extractor_version,
        cleaner_version=cfg.cleaner_version,
        fetched_url=raw_event.source_url,
        final_url=raw_event.source_url,
        canonical_url=raw_event.source_url,
        redirect_chain=tuple(str(item) for item in (raw_event.source_url,) if item),
        title=raw_event.title,
        body_text=text,
        body_char_count=len(text),
        article_quality_status=ARTICLE_QUALITY_FIXTURE_TEXT_USED,
    )


def _failed_article(
    raw_event: RawDiscoveredEvent,
    *,
    cfg: EventSourceEnrichmentConfig,
    status: str,
    warning: str,
) -> EventArticleExtraction:
    text = _summary_text(raw_event)
    return EventArticleExtraction(
        extractor_version=cfg.extractor_version,
        cleaner_version=cfg.cleaner_version,
        fetched_url=raw_event.source_url,
        final_url=raw_event.source_url,
        canonical_url=None,
        redirect_chain=tuple(str(item) for item in (raw_event.source_url,) if item),
        title=raw_event.title,
        body_text=text,
        body_char_count=len(text),
        article_quality_status=status,
        warnings=(warning,),
    )


def _article_from_cache(cached: Mapping[str, Any], *, fallback_text: str) -> EventArticleExtraction:
    article = cached.get("article") if isinstance(cached.get("article"), Mapping) else {}
    return EventArticleExtraction(
        extractor_version=str(article.get("extractor_version") or cached.get("extractor_version") or SOURCE_ENRICHMENT_EXTRACTOR_VERSION),
        cleaner_version=str(article.get("cleaner_version") or cached.get("cleaner_version") or config.EVENT_SOURCE_ENRICHMENT_CLEANER_VERSION),
        fetched_url=_optional_str(article.get("fetched_url") or cached.get("fetched_url") or cached.get("url")),
        final_url=_optional_str(article.get("final_url") or cached.get("final_url") or cached.get("url")),
        canonical_url=_optional_str(article.get("canonical_url") or cached.get("canonical_url")),
        redirect_chain=tuple(str(item) for item in (article.get("redirect_chain") or cached.get("redirect_chain") or ()) if item),
        title=_optional_str(article.get("title")),
        byline=_optional_str(article.get("byline")),
        source=_optional_str(article.get("source")),
        published_at=_optional_str(article.get("published_at")),
        body_text=str(article.get("body_text") or fallback_text or ""),
        body_char_count=_int_or_none(article.get("body_char_count")) or len(str(article.get("body_text") or fallback_text or "")),
        boilerplate_ratio=_float_or_zero(article.get("boilerplate_ratio")),
        ticker_sidebar_detected=bool(article.get("ticker_sidebar_detected")),
        article_quality_status=str(article.get("article_quality_status") or cached.get("article_quality_status") or ARTICLE_QUALITY_THIN),
        warnings=tuple(str(item) for item in (article.get("warnings") or ()) if item),
    )


def _triage_from_cache(cached: Mapping[str, Any]) -> EventSourceTriageResult | None:
    triage = cached.get("triage") if isinstance(cached.get("triage"), Mapping) else {}
    if not triage:
        return None
    return EventSourceTriageResult(
        is_real_article=bool(triage.get("is_real_article")),
        source_is_official=bool(triage.get("source_is_official")),
        source_is_recapped_news=bool(triage.get("source_is_recapped_news")),
        source_is_affiliate_or_seo=bool(triage.get("source_is_affiliate_or_seo")),
        source_has_direct_token_mechanism=bool(triage.get("source_has_direct_token_mechanism")),
        source_has_candidate_and_catalyst=bool(triage.get("source_has_candidate_and_catalyst")),
        source_quality_score=_float_or_zero(triage.get("source_quality_score")),
        decision=str(triage.get("decision") or SOURCE_TRIAGE_RAW_OBSERVATION),
        reason_codes=tuple(str(item) for item in (triage.get("reason_codes") or ()) if item),
        warnings=tuple(str(item) for item in (triage.get("warnings") or ()) if item),
    )


def _article_from_payload(raw_event: RawDiscoveredEvent) -> EventArticleExtraction | None:
    payload = raw_event.raw_json if isinstance(raw_event.raw_json, Mapping) else {}
    enrichment = payload.get("source_enrichment") if isinstance(payload.get("source_enrichment"), Mapping) else {}
    article = enrichment.get("article") if isinstance(enrichment.get("article"), Mapping) else {}
    if not article:
        return None
    return _article_from_cache({"article": article, **dict(enrichment)}, fallback_text=str(enrichment.get("enriched_text") or ""))


def _quality_warning(article: EventArticleExtraction, triage: EventSourceTriageResult) -> str | None:
    if article.article_quality_status in {
        ARTICLE_QUALITY_THIN,
        ARTICLE_QUALITY_BOILERPLATE_HEAVY,
        ARTICLE_QUALITY_REDIRECT_PLACEHOLDER,
        ARTICLE_QUALITY_PAYWALL_OR_BLOCKED,
    }:
        return f"article quality {article.article_quality_status}"
    if triage.decision in {SOURCE_TRIAGE_DIAGNOSTIC_ONLY, SOURCE_TRIAGE_REJECT}:
        return f"source triage {triage.decision}"
    return None


def _has_candidate_and_catalyst(text: str, payload: Mapping[str, Any]) -> bool:
    catalyst_terms = (
        "ipo",
        "pre ipo",
        "pre-ipo",
        "listing",
        "unlock",
        "exploit",
        "hack",
        "world cup",
        "prediction market",
        "strategic investment",
        "acquisition",
        "stake",
        "perp",
    )
    candidate_terms = (
        str(payload.get("symbol") or ""),
        str(payload.get("validated_symbol") or ""),
        str(payload.get("coin_id") or "").replace("-", " "),
        str(payload.get("validated_coin_id") or "").replace("-", " "),
        " token",
        " protocol",
    )
    has_catalyst = any(term and term in text for term in catalyst_terms)
    has_candidate = any(term and clean_text(term) in text for term in candidate_terms)
    return has_catalyst and has_candidate


def _triage_score(
    *,
    status: str,
    is_real_article: bool,
    source_is_official: bool,
    source_is_recapped_news: bool,
    source_is_affiliate_or_seo: bool,
    source_has_direct_token_mechanism: bool,
    source_has_candidate_and_catalyst: bool,
    boilerplate_ratio: float,
) -> float:
    score = 35.0
    if is_real_article:
        score += 25.0
    if source_is_official:
        score += 18.0
    if source_has_direct_token_mechanism:
        score += 18.0
    elif source_has_candidate_and_catalyst:
        score += 12.0
    if status == ARTICLE_QUALITY_FIXTURE_TEXT_USED:
        score += 8.0
    if status == ARTICLE_QUALITY_THIN:
        score -= 18.0
    if status == ARTICLE_QUALITY_BOILERPLATE_HEAVY:
        score -= 28.0
    if status in {ARTICLE_QUALITY_REDIRECT_PLACEHOLDER, ARTICLE_QUALITY_PAYWALL_OR_BLOCKED, ARTICLE_QUALITY_FETCH_FAILED}:
        score -= 45.0
    if source_is_recapped_news:
        score -= 14.0
    if source_is_affiliate_or_seo:
        score -= 35.0
    score -= max(0.0, min(25.0, boilerplate_ratio * 20.0))
    return score


def _validate_source_quality_judgment(
    raw: Mapping[str, Any],
    *,
    deterministic: EventSourceTriageResult | None,
) -> EventSourceQualityJudgment:
    status = str(raw.get("article_quality_status") or "").strip()
    if status not in {
        ARTICLE_QUALITY_GOOD,
        ARTICLE_QUALITY_THIN,
        ARTICLE_QUALITY_BOILERPLATE_HEAVY,
        ARTICLE_QUALITY_REDIRECT_PLACEHOLDER,
        ARTICLE_QUALITY_PAYWALL_OR_BLOCKED,
        ARTICLE_QUALITY_FETCH_FAILED,
        ARTICLE_QUALITY_FIXTURE_TEXT_USED,
    }:
        status = ARTICLE_QUALITY_THIN
    is_real = bool(raw.get("is_real_article")) and status in USABLE_ARTICLE_QUALITY_STATUSES
    score = max(0.0, min(100.0, _float_or_zero(raw.get("source_quality_score"))))
    warnings = [str(item) for item in (raw.get("warnings") or ()) if item]
    if deterministic is not None and deterministic.decision in {SOURCE_TRIAGE_DIAGNOSTIC_ONLY, SOURCE_TRIAGE_REJECT}:
        is_real = False
        score = min(score, deterministic.source_quality_score, 45.0)
        warnings.append("deterministic_triage_override")
    if deterministic is not None and deterministic.source_is_affiliate_or_seo:
        status = ARTICLE_QUALITY_BOILERPLATE_HEAVY
        is_real = False
        score = min(score, 35.0)
        warnings.append("affiliate_or_seo_override")
    return EventSourceQualityJudgment(
        is_real_article=is_real,
        article_quality_status=status,
        source_quality_score=round(score, 2),
        reason=str(raw.get("reason") or "source_quality_judged"),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def validate_llm_source_triage(
    raw: Mapping[str, Any],
    *,
    source_text: str,
    deterministic: EventSourceTriageResult | None = None,
) -> EventLLMSourceTriage:
    page_type = str(raw.get("page_type") or "").strip()
    if page_type not in LLM_SOURCE_PAGE_TYPES:
        raise ValueError(f"invalid LLM source page_type: {page_type}")
    quality = str(raw.get("article_quality") or raw.get("article_quality_status") or "").strip()
    if quality not in {
        ARTICLE_QUALITY_GOOD,
        ARTICLE_QUALITY_THIN,
        ARTICLE_QUALITY_BOILERPLATE_HEAVY,
        ARTICLE_QUALITY_REDIRECT_PLACEHOLDER,
        ARTICLE_QUALITY_PAYWALL_OR_BLOCKED,
        ARTICLE_QUALITY_FETCH_FAILED,
        ARTICLE_QUALITY_FIXTURE_TEXT_USED,
    }:
        raise ValueError(f"invalid LLM source article_quality: {quality}")
    quote = str(raw.get("evidence_quote") or "").strip()
    warnings = [str(item) for item in (raw.get("warnings") or ()) if item]
    confidence = max(0.0, min(1.0, _float_or_zero(raw.get("confidence"))))
    clean_quote = clean_text(quote)
    clean_source = clean_text(source_text)
    if quote and clean_quote not in clean_source:
        warnings.append("evidence_quote_missing_from_source")
        confidence = min(confidence, 0.50)
    if bool(raw.get("candidate_catalyst_mechanism_present")) and not quote:
        warnings.append("mechanism_without_quote")
        confidence = min(confidence, 0.50)
    is_affiliate = bool(raw.get("is_affiliate_or_seo")) or page_type == "seo_affiliate"
    is_real = bool(raw.get("is_real_article")) and quality in USABLE_ARTICLE_QUALITY_STATUSES
    is_official = bool(raw.get("is_official_source")) or page_type == "official_announcement"
    if deterministic is not None and deterministic.decision in {SOURCE_TRIAGE_DIAGNOSTIC_ONLY, SOURCE_TRIAGE_REJECT}:
        is_real = False
        confidence = min(confidence, 0.45)
        warnings.append("deterministic_triage_override")
    if deterministic is not None and deterministic.source_is_affiliate_or_seo:
        is_real = False
        is_affiliate = True
        quality = ARTICLE_QUALITY_BOILERPLATE_HEAVY
        confidence = min(confidence, 0.35)
        warnings.append("affiliate_or_seo_override")
    if is_affiliate:
        is_real = False
        confidence = min(confidence, 0.45)
    if page_type in {"redirect_placeholder", "blocked_or_paywalled", "source_noise"}:
        is_real = False
        confidence = min(confidence, 0.50)
    return EventLLMSourceTriage(
        page_type=page_type,
        is_real_article=is_real,
        article_quality=quality,
        boilerplate_ratio_estimate=max(0.0, min(1.0, _float_or_zero(raw.get("boilerplate_ratio_estimate")))),
        is_official_source=is_official,
        is_recap=bool(raw.get("is_recap")) or page_type == "market_recap",
        is_affiliate_or_seo=is_affiliate,
        candidate_catalyst_mechanism_present=bool(raw.get("candidate_catalyst_mechanism_present")) and bool(quote),
        evidence_quote=quote if not quote or clean_quote in clean_source else "",
        confidence=round(confidence, 3),
        reason=str(raw.get("reason") or "llm_source_triage_validated"),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _int_or_none(value: object) -> int | None:
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _float_or_zero(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
