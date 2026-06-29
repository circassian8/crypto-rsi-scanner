"""Research-only LLM catalyst-frame analysis.

The LLM is used as a semantic parser for source evidence. It does not score,
route, trade, paper trade, write normal RSI rows, or create event-fade triggers.
Validated output can be embedded as catalyst-frame evidence for deterministic
incident and impact-path code to consume.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_catalyst_frames, event_claim_semantics
from .event_models import NormalizedEvent, RawDiscoveredEvent
from .event_resolver import clean_text
from .llm_providers.base import LLMCatalystFrameProvider, LLMProviderResult


LLM_CATALYST_FRAME_SCHEMA_VERSION = "event_llm_catalyst_frames_v1"

FRAME_ROLE_VALUES = frozenset({
    event_catalyst_frames.ROLE_MAIN,
    event_catalyst_frames.ROLE_BACKGROUND,
    event_catalyst_frames.ROLE_HISTORICAL,
    event_catalyst_frames.ROLE_NEGATED,
    event_catalyst_frames.ROLE_CORRECTIVE,
    event_catalyst_frames.ROLE_SIDE_NOTE,
    event_catalyst_frames.ROLE_MARKET_REACTION,
    event_catalyst_frames.ROLE_UNKNOWN,
})
FRAME_TYPE_VALUES = frozenset({
    event_catalyst_frames.TYPE_STRATEGIC_INVESTMENT,
    event_catalyst_frames.TYPE_ACQUISITION_OR_STAKE,
    event_catalyst_frames.TYPE_VALUATION_EVENT,
    event_catalyst_frames.TYPE_EXPLOIT_SECURITY,
    event_catalyst_frames.TYPE_PRIOR_EXPLOIT_CONTEXT,
    event_catalyst_frames.TYPE_DENIED_EXPLOIT,
    event_catalyst_frames.TYPE_LISTING_LIQUIDITY,
    event_catalyst_frames.TYPE_UNLOCK_SUPPLY,
    event_catalyst_frames.TYPE_MARKET_DISLOCATION,
    event_catalyst_frames.TYPE_PROXY_ATTENTION,
    event_catalyst_frames.TYPE_POLICY_CONTEXT,
    event_catalyst_frames.TYPE_GENERIC_CONTEXT,
})
CLAIM_POLARITY_VALUES = frozenset(item.value for item in event_claim_semantics.ClaimPolarity)
CAUSE_STATUS_VALUES = frozenset(item.value for item in event_claim_semantics.CauseStatus)


class EventLLMCatalystFrameValidationError(ValueError):
    """Raised when provider output violates the catalyst-frame schema."""


@dataclass(frozen=True)
class EventLLMCatalystFrame:
    frame_type: str
    frame_role: str
    subject: str | None
    actor: str | None = None
    object: str | None = None
    affected_entities: tuple[str, ...] = ()
    affected_assets: tuple[str, ...] = ()
    event_archetype: str | None = None
    claim_polarity: str = event_claim_semantics.ClaimPolarity.UNKNOWN.value
    cause_status: str = event_claim_semantics.CauseStatus.UNKNOWN.value
    confidence: float = 0.0
    evidence_quote: str = ""
    why_this_role: str = ""
    found_in_source: bool = False


@dataclass(frozen=True)
class EventLLMCatalystFrameAnalysis:
    schema_version: str
    provider: str
    model: str | None
    prompt_version: str
    raw_id: str
    main_catalyst_frame: EventLLMCatalystFrame | None
    background_frames: tuple[EventLLMCatalystFrame, ...] = ()
    negated_or_corrective_frames: tuple[EventLLMCatalystFrame, ...] = ()
    external_entities: tuple[str, ...] = ()
    crypto_assets: tuple[str, ...] = ()
    rejected_impact_paths: tuple[str, ...] = ()
    manual_verification_items: tuple[str, ...] = ()
    semantic_confidence: float = 0.0
    warnings: tuple[str, ...] = ()
    raw_response: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @property
    def all_frames(self) -> tuple[EventLLMCatalystFrame, ...]:
        frames: list[EventLLMCatalystFrame] = []
        if self.main_catalyst_frame is not None:
            frames.append(self.main_catalyst_frame)
        frames.extend(self.background_frames)
        frames.extend(self.negated_or_corrective_frames)
        return tuple(frames)


@dataclass(frozen=True)
class EventLLMCatalystFrameConfig:
    enabled: bool = False
    provider: str = "fixture"
    model: str | None = None
    max_rows_per_run: int = 20
    min_source_score: float = 0.50
    use_enriched_text: bool = True
    only_ambiguous: bool = True
    require_evidence_quotes: bool = True
    prompt_version: str = "llm_catalyst_frames_v1"
    deadline_at: datetime | None = None


@dataclass(frozen=True)
class EventLLMCatalystFrameReportRow:
    raw_event: RawDiscoveredEvent
    analysis: EventLLMCatalystFrameAnalysis | None
    warnings: tuple[str, ...] = ()
    selected: bool = False
    frame_required: bool = False
    frame_required_reason: str | None = None


def structured_output_schema() -> dict[str, Any]:
    """Return the strict JSON schema expected from an LLM provider."""
    frame_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "frame_type": {"type": "string", "enum": sorted(FRAME_TYPE_VALUES)},
            "frame_role": {"type": "string", "enum": sorted(FRAME_ROLE_VALUES)},
            "subject": {"type": ["string", "null"]},
            "actor": {"type": ["string", "null"]},
            "object": {"type": ["string", "null"]},
            "affected_entities": {"type": "array", "items": {"type": "string"}},
            "affected_assets": {"type": "array", "items": {"type": "string"}},
            "event_archetype": {"type": ["string", "null"]},
            "claim_polarity": {"type": "string", "enum": sorted(CLAIM_POLARITY_VALUES)},
            "cause_status": {"type": "string", "enum": sorted(CAUSE_STATUS_VALUES)},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence_quote": {"type": "string"},
            "why_this_role": {"type": "string"},
        },
        "required": [
            "frame_type",
            "frame_role",
            "subject",
            "actor",
            "object",
            "affected_entities",
            "affected_assets",
            "event_archetype",
            "claim_polarity",
            "cause_status",
            "confidence",
            "evidence_quote",
            "why_this_role",
        ],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "main_catalyst_frame": {"anyOf": [frame_schema, {"type": "null"}]},
            "background_frames": {"type": "array", "items": frame_schema},
            "negated_or_corrective_frames": {"type": "array", "items": frame_schema},
            "external_entities": {"type": "array", "items": {"type": "string"}},
            "crypto_assets": {"type": "array", "items": {"type": "string"}},
            "rejected_impact_paths": {"type": "array", "items": {"type": "string"}},
            "manual_verification_items": {"type": "array", "items": {"type": "string"}},
            "semantic_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "main_catalyst_frame",
            "background_frames",
            "negated_or_corrective_frames",
            "external_entities",
            "crypto_assets",
            "rejected_impact_paths",
            "manual_verification_items",
            "semantic_confidence",
            "warnings",
        ],
    }


def analyze_raw_events(
    raw_events: Iterable[RawDiscoveredEvent],
    provider: LLMCatalystFrameProvider,
    *,
    cfg: EventLLMCatalystFrameConfig | None = None,
    events_by_raw_id: Mapping[str, NormalizedEvent] | None = None,
) -> tuple[EventLLMCatalystFrameReportRow, ...]:
    cfg = cfg or EventLLMCatalystFrameConfig()
    selected = _select_raw_events(raw_events, cfg=cfg)
    rows: list[EventLLMCatalystFrameReportRow] = []
    for raw in selected:
        event = events_by_raw_id.get(raw.raw_id) if events_by_raw_id else None
        packet = build_catalyst_frame_packet(raw, event=event, cfg=cfg)
        provider_result = _analyze_catalyst_frames_with_deadline(provider, packet, cfg=cfg)
        warnings: list[str] = []
        if provider_result.warning:
            warnings.append(provider_result.warning)
        analysis = None
        if provider_result.raw is not None:
            try:
                analysis = parse_catalyst_frame_analysis(
                    provider_result.raw,
                    packet=packet,
                    provider_name=str(getattr(provider, "name", cfg.provider)),
                    provider_model=getattr(provider, "model", cfg.model),
                    cfg=cfg,
                )
            except EventLLMCatalystFrameValidationError as exc:
                warnings.append(str(exc))
        required, required_reason = frame_requirement_for_raw(raw)
        rows.append(EventLLMCatalystFrameReportRow(
            raw_event=raw,
            analysis=analysis,
            warnings=tuple(warnings),
            selected=True,
            frame_required=required,
            frame_required_reason=required_reason,
        ))
    return tuple(rows)


def _analyze_catalyst_frames_with_deadline(
    provider: LLMCatalystFrameProvider,
    packet: Mapping[str, Any],
    *,
    cfg: EventLLMCatalystFrameConfig,
) -> LLMProviderResult:
    if _deadline_exhausted(cfg.deadline_at):
        return LLMProviderResult(warning=_deadline_warning())
    remaining = _remaining_deadline_seconds(cfg.deadline_at)
    if remaining is None or not hasattr(provider, "timeout"):
        return provider.analyze_catalyst_frames(packet)
    try:
        original_timeout = float(getattr(provider, "timeout"))
    except (TypeError, ValueError):
        return provider.analyze_catalyst_frames(packet)
    bounded_timeout = max(1.0, min(original_timeout, remaining))
    if bounded_timeout <= 1.0 and remaining <= 1.0:
        return LLMProviderResult(warning=_deadline_warning())
    try:
        setattr(provider, "timeout", bounded_timeout)
        return provider.analyze_catalyst_frames(packet)
    finally:
        setattr(provider, "timeout", original_timeout)


def build_catalyst_frame_packet(
    raw_event: RawDiscoveredEvent,
    *,
    event: NormalizedEvent | None = None,
    cfg: EventLLMCatalystFrameConfig | None = None,
) -> dict[str, Any]:
    cfg = cfg or EventLLMCatalystFrameConfig()
    payload = raw_event.raw_json if isinstance(raw_event.raw_json, Mapping) else {}
    enrichment = payload.get("source_enrichment") if isinstance(payload.get("source_enrichment"), Mapping) else {}
    enriched_text = str(enrichment.get("enriched_text") or "") if cfg.use_enriched_text else ""
    packet = {
        "schema_version": LLM_CATALYST_FRAME_SCHEMA_VERSION,
        "prompt_version": cfg.prompt_version,
        "raw_id": raw_event.raw_id,
        "provider": raw_event.provider,
        "source_url": raw_event.source_url,
        "published_at": raw_event.published_at.isoformat() if raw_event.published_at else None,
        "fetched_at": raw_event.fetched_at.isoformat() if raw_event.fetched_at else None,
        "source_confidence": raw_event.source_confidence,
        "title": raw_event.title,
        "body": raw_event.body,
        "enriched_text": enriched_text,
        "event": {
            "event_id": event.event_id,
            "event_name": event.event_name,
            "event_type": event.event_type,
            "external_asset": event.external_asset,
            "description": event.description,
        } if event is not None else {},
        "instructions": (
            "Separate the main catalyst from background, historical, negated, "
            "corrective, side-note, and market-reaction frames. Use exact quotes "
            "from title/body/enriched_text. Do not recommend trades or alerts."
        ),
    }
    packet["packet_hash"] = hashlib.sha1(json.dumps(packet, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return packet


def parse_catalyst_frame_analysis(
    raw: Mapping[str, Any],
    *,
    packet: Mapping[str, Any],
    provider_name: str = "fixture",
    provider_model: str | None = None,
    cfg: EventLLMCatalystFrameConfig | None = None,
) -> EventLLMCatalystFrameAnalysis:
    cfg = cfg or EventLLMCatalystFrameConfig()
    warnings: list[str] = [str(item) for item in raw.get("warnings", ()) if item]
    source_text = _packet_source_text(packet)

    def parse_frame(value: Any, *, default_role: str | None = None) -> EventLLMCatalystFrame | None:
        if value is None:
            return None
        if not isinstance(value, Mapping):
            raise EventLLMCatalystFrameValidationError("LLM catalyst frame entry must be an object")
        frame_type = str(value.get("frame_type") or "")
        frame_role = str(value.get("frame_role") or default_role or "")
        if frame_type not in FRAME_TYPE_VALUES:
            raise EventLLMCatalystFrameValidationError(f"invalid LLM catalyst frame_type: {frame_type}")
        if frame_role not in FRAME_ROLE_VALUES:
            raise EventLLMCatalystFrameValidationError(f"invalid LLM catalyst frame_role: {frame_role}")
        polarity = str(value.get("claim_polarity") or event_claim_semantics.ClaimPolarity.UNKNOWN.value)
        cause = str(value.get("cause_status") or event_claim_semantics.CauseStatus.UNKNOWN.value)
        if polarity not in CLAIM_POLARITY_VALUES:
            raise EventLLMCatalystFrameValidationError(f"invalid LLM catalyst claim_polarity: {polarity}")
        if cause not in CAUSE_STATUS_VALUES:
            raise EventLLMCatalystFrameValidationError(f"invalid LLM catalyst cause_status: {cause}")
        quote = _string(value.get("evidence_quote"))
        found = _quote_found(quote, source_text)
        if cfg.require_evidence_quotes and quote and not found:
            warnings.append(f"quote_not_found:{frame_type}:{frame_role}")
        return EventLLMCatalystFrame(
            frame_type=frame_type,
            frame_role=frame_role,
            subject=_optional_str(value.get("subject")),
            actor=_optional_str(value.get("actor")),
            object=_optional_str(value.get("object")),
            affected_entities=_string_tuple(value.get("affected_entities")),
            affected_assets=_string_tuple(value.get("affected_assets")),
            event_archetype=_optional_str(value.get("event_archetype")) or frame_type,
            claim_polarity=polarity,
            cause_status=cause,
            confidence=_clamp_float(value.get("confidence")),
            evidence_quote=quote,
            why_this_role=_string(value.get("why_this_role")),
            found_in_source=found,
        )

    main = parse_frame(raw.get("main_catalyst_frame"), default_role=event_catalyst_frames.ROLE_MAIN)
    background = tuple(
        frame for frame in (
            parse_frame(item) for item in _list(raw.get("background_frames"))
        )
        if frame is not None
    )
    negated = tuple(
        frame for frame in (
            parse_frame(item) for item in _list(raw.get("negated_or_corrective_frames"))
        )
        if frame is not None
    )
    if cfg.require_evidence_quotes and any(not frame.found_in_source for frame in (main, *background, *negated) if frame is not None):
        warnings.append("one_or_more_catalyst_frame_quotes_missing")
    return EventLLMCatalystFrameAnalysis(
        schema_version=LLM_CATALYST_FRAME_SCHEMA_VERSION,
        provider=provider_name,
        model=provider_model,
        prompt_version=cfg.prompt_version,
        raw_id=str(packet.get("raw_id") or raw.get("raw_id") or ""),
        main_catalyst_frame=main,
        background_frames=background,
        negated_or_corrective_frames=negated,
        external_entities=_string_tuple(raw.get("external_entities")),
        crypto_assets=_string_tuple(raw.get("crypto_assets")),
        rejected_impact_paths=_string_tuple(raw.get("rejected_impact_paths")),
        manual_verification_items=_string_tuple(raw.get("manual_verification_items")),
        semantic_confidence=_clamp_float(raw.get("semantic_confidence")),
        warnings=tuple(dict.fromkeys(warnings)),
        raw_response=dict(raw),
    )


def analysis_to_dict(analysis: EventLLMCatalystFrameAnalysis) -> dict[str, Any]:
    return {
        "schema_version": analysis.schema_version,
        "provider": analysis.provider,
        "model": analysis.model,
        "prompt_version": analysis.prompt_version,
        "raw_id": analysis.raw_id,
        "main_catalyst_frame": _frame_to_dict(analysis.main_catalyst_frame),
        "background_frames": [_frame_to_dict(frame) for frame in analysis.background_frames],
        "negated_or_corrective_frames": [_frame_to_dict(frame) for frame in analysis.negated_or_corrective_frames],
        "external_entities": list(analysis.external_entities),
        "crypto_assets": list(analysis.crypto_assets),
        "rejected_impact_paths": list(analysis.rejected_impact_paths),
        "manual_verification_items": list(analysis.manual_verification_items),
        "semantic_confidence": analysis.semantic_confidence,
        "warnings": list(analysis.warnings),
    }


def _frame_to_dict(frame: EventLLMCatalystFrame | None) -> dict[str, Any] | None:
    if frame is None:
        return None
    return {
        "frame_type": frame.frame_type,
        "frame_role": frame.frame_role,
        "subject": frame.subject,
        "actor": frame.actor,
        "object": frame.object,
        "affected_entities": list(frame.affected_entities),
        "affected_assets": list(frame.affected_assets),
        "event_archetype": frame.event_archetype,
        "claim_polarity": frame.claim_polarity,
        "cause_status": frame.cause_status,
        "confidence": frame.confidence,
        "evidence_quote": frame.evidence_quote,
        "why_this_role": frame.why_this_role,
        "found_in_source": frame.found_in_source,
    }


def frame_requirement_for_raw(raw: RawDiscoveredEvent) -> tuple[bool, str | None]:
    """Return whether catalyst-frame analysis is required for this raw source."""
    text = clean_text(" ".join((raw.title or "", raw.body or "", _enriched_text(raw))))
    if not text:
        return False, None
    exploit_terms = any(term in text for term in ("exploit", "hack", "hacked", "breach", "attack", "security incident"))
    background_terms = any(term in text for term in ("fallout", "despite", "background", "after the", "previously", "earlier", "not hacked", "no exploit", "no hack"))
    investment_terms = any(term in text for term in ("stake", "investment", "valuation", "acquisition", "acquire", "buy"))
    proxy_terms = any(term in text for term in ("pre ipo", "pre-ipo", "tokenized", "synthetic exposure", "prediction market"))
    competing = sum(1 for flag in (exploit_terms, investment_terms, proxy_terms) if flag)
    if exploit_terms and background_terms:
        return True, "security_background_or_negation_terms"
    if investment_terms:
        return True, "investment_or_valuation_terms"
    if proxy_terms:
        return True, "proxy_or_tokenized_exposure_terms"
    if competing >= 2:
        return True, "multiple_plausible_catalysts"
    return False, None


def _select_raw_events(raw_events: Iterable[RawDiscoveredEvent], *, cfg: EventLLMCatalystFrameConfig) -> tuple[RawDiscoveredEvent, ...]:
    selected: list[RawDiscoveredEvent] = []
    for raw in raw_events:
        if float(raw.source_confidence or 0.0) < cfg.min_source_score:
            continue
        required, _reason = frame_requirement_for_raw(raw)
        if cfg.only_ambiguous and not required:
            continue
        selected.append(raw)
        if len(selected) >= max(0, cfg.max_rows_per_run):
            break
    return tuple(selected)


def _needs_frame_analysis(raw: RawDiscoveredEvent) -> bool:
    required, _reason = frame_requirement_for_raw(raw)
    return required


def _packet_source_text(packet: Mapping[str, Any]) -> str:
    return " ".join(
        str(packet.get(key) or "")
        for key in ("title", "body", "enriched_text")
    )


def _quote_found(quote: str, source_text: str) -> bool:
    quote_clean = clean_text(quote)
    source_clean = clean_text(source_text)
    if not quote_clean:
        return False
    if quote_clean in source_clean:
        return True
    quote_terms = {term for term in quote_clean.split() if len(term) > 3}
    if not quote_terms:
        return False
    source_terms = set(source_clean.split())
    overlap = len(quote_terms & source_terms) / max(1, len(quote_terms))
    return overlap >= 0.80


def _enriched_text(raw: RawDiscoveredEvent) -> str:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    enrichment = payload.get("source_enrichment") if isinstance(payload.get("source_enrichment"), Mapping) else {}
    return str(enrichment.get("enriched_text") or "")


def _string(value: Any) -> str:
    return str(value or "").strip()


def _optional_str(value: Any) -> str | None:
    text = _string(value)
    return text or None


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, Mapping)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clamp_float(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _deadline_exhausted(deadline_at: datetime | None) -> bool:
    if deadline_at is None:
        return False
    deadline = deadline_at.replace(tzinfo=timezone.utc) if deadline_at.tzinfo is None else deadline_at.astimezone(timezone.utc)
    return datetime.now(timezone.utc) >= deadline


def _remaining_deadline_seconds(deadline_at: datetime | None) -> float | None:
    if deadline_at is None:
        return None
    deadline = deadline_at.replace(tzinfo=timezone.utc) if deadline_at.tzinfo is None else deadline_at.astimezone(timezone.utc)
    return max(0.0, (deadline - datetime.now(timezone.utc)).total_seconds())


def _deadline_warning() -> str:
    return "LLM catalyst-frame analysis skipped: notification runtime deadline exhausted"


def default_fixture_path() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "event_discovery" / "llm_catalyst_frame_cases.json"
