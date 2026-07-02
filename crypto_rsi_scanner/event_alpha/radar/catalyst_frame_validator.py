"""Deterministic validation for LLM catalyst-frame analyses.

LLM catalyst frames are semantic proposals. This module enforces source-quote,
identity, negation, and rule-disagreement constraints before frames can be used
as research evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

from crypto_rsi_scanner import event_catalyst_frames, event_llm_catalyst_frames
from crypto_rsi_scanner.event_models import NormalizedEvent, RawDiscoveredEvent
from crypto_rsi_scanner.event_resolver import clean_text


RESOLUTION_LLM_WINS = "llm_wins"
RESOLUTION_RULES_WIN = "rules_win"
RESOLUTION_UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class CatalystFrameValidationResult:
    valid_frames: tuple[event_catalyst_frames.EventCatalystFrame, ...]
    invalid_frames: tuple[dict[str, Any], ...]
    frame_warnings: tuple[str, ...]
    rule_llm_disagreements: tuple[str, ...]
    selected_main_frame: event_catalyst_frames.EventCatalystFrame | None
    rejected_impact_paths: tuple[str, ...]
    rule_predicted_impact_path: str | None
    llm_predicted_main_frame_type: str | None
    frame_rule_disagreement: bool
    disagreement_reason: str | None
    resolution: str
    external_entities: tuple[str, ...] = ()
    crypto_assets: tuple[str, ...] = ()
    manual_verification_items: tuple[str, ...] = ()


def validate_llm_catalyst_frames(
    analysis: event_llm_catalyst_frames.EventLLMCatalystFrameAnalysis,
    raw_events: Iterable[RawDiscoveredEvent],
    *,
    event: NormalizedEvent | None = None,
    rule_frames: Iterable[event_catalyst_frames.EventCatalystFrame] = (),
) -> CatalystFrameValidationResult:
    raws = tuple(raw_events)
    source_text = _source_text(raws, event=event)
    rule_rows = tuple(rule_frames) or event_catalyst_frames.build_catalyst_frames(raws, event=event)
    rule_main, _ = event_catalyst_frames.select_main_catalyst_frame(rule_rows, event)
    valid: list[event_catalyst_frames.EventCatalystFrame] = []
    invalid: list[dict[str, Any]] = []
    warnings: list[str] = list(analysis.warnings)
    rejected: list[str] = list(analysis.rejected_impact_paths)
    external_entities = tuple(analysis.external_entities)
    crypto_assets = tuple(analysis.crypto_assets)

    for frame in analysis.all_frames:
        reason = _invalid_frame_reason(frame, source_text, external_entities=external_entities)
        if reason:
            invalid.append({
                "frame_type": frame.frame_type,
                "frame_role": frame.frame_role,
                "subject": frame.subject,
                "reason": reason,
                "evidence_quote": frame.evidence_quote,
            })
            warnings.append(reason)
            continue
        valid.append(_to_event_frame(frame, raws[0] if raws else None))
        if frame.frame_role in {event_catalyst_frames.ROLE_BACKGROUND, event_catalyst_frames.ROLE_HISTORICAL}:
            rejected.append(f"{frame.frame_type}:background_for:{frame.subject or 'unknown'}")
            rejected.append("background_context_not_primary_catalyst")
            if frame.frame_role == event_catalyst_frames.ROLE_HISTORICAL:
                rejected.append("historical_context_only")
        if frame.frame_role in {event_catalyst_frames.ROLE_NEGATED, event_catalyst_frames.ROLE_CORRECTIVE}:
            rejected.append(f"{frame.frame_type}:negated_for:{frame.subject or 'unknown'}")
            rejected.append("negated_claim_blocks_impact_path")

    selected, _supporting = event_catalyst_frames.select_main_catalyst_frame(valid, event)
    llm_main_type = selected.frame_type if selected is not None else None
    rule_path = rule_main.frame_type if rule_main is not None else None
    disagreement = bool(rule_path and llm_main_type and rule_path != llm_main_type)
    disagreement_reason = None
    disagreements: list[str] = []
    resolution = RESOLUTION_UNRESOLVED
    if disagreement:
        disagreement_reason = f"rules={rule_path};llm={llm_main_type}"
        disagreements.append(disagreement_reason)
    if selected is not None and selected.frame_role == event_catalyst_frames.ROLE_MAIN:
        resolution = RESOLUTION_LLM_WINS if disagreement else RESOLUTION_RULES_WIN
        if any(
            frame.frame_role in {event_catalyst_frames.ROLE_BACKGROUND, event_catalyst_frames.ROLE_HISTORICAL}
            for frame in valid
        ):
            rejected.append("main_catalyst_selected_over_background")
    if invalid and selected is None:
        resolution = RESOLUTION_RULES_WIN if rule_main is not None else RESOLUTION_UNRESOLVED
    if disagreement and _has_hard_gate(valid):
        resolution = RESOLUTION_LLM_WINS
        disagreements.append("negation_or_background_hard_gate_supported_by_quote")
    if disagreement and resolution == RESOLUTION_UNRESOLVED:
        warnings.append("unresolved_rule_llm_frame_disagreement")

    return CatalystFrameValidationResult(
        valid_frames=tuple(valid),
        invalid_frames=tuple(invalid),
        frame_warnings=tuple(dict.fromkeys(warnings)),
        rule_llm_disagreements=tuple(dict.fromkeys(disagreements)),
        selected_main_frame=selected,
        rejected_impact_paths=tuple(dict.fromkeys(rejected)),
        rule_predicted_impact_path=rule_path,
        llm_predicted_main_frame_type=llm_main_type,
        frame_rule_disagreement=disagreement,
        disagreement_reason=disagreement_reason,
        resolution=resolution,
        external_entities=external_entities,
        crypto_assets=crypto_assets,
        manual_verification_items=tuple(analysis.manual_verification_items),
    )


def apply_validation_to_raw_event(
    raw: RawDiscoveredEvent,
    analysis: event_llm_catalyst_frames.EventLLMCatalystFrameAnalysis,
    validation: CatalystFrameValidationResult,
) -> RawDiscoveredEvent:
    payload = dict(raw.raw_json or {})
    payload["llm_catalyst_frame_analysis"] = event_llm_catalyst_frames.analysis_to_dict(analysis)
    payload["llm_catalyst_frame_validation"] = validation_to_dict(validation)
    return replace(raw, raw_json=payload)


def validation_to_dict(result: CatalystFrameValidationResult) -> dict[str, Any]:
    return {
        "valid_frames": [event_catalyst_frames.frame_summary((frame,))[0] for frame in result.valid_frames],
        "invalid_frames": list(result.invalid_frames),
        "frame_warnings": list(result.frame_warnings),
        "rule_llm_disagreements": list(result.rule_llm_disagreements),
        "selected_main_frame": event_catalyst_frames.frame_summary((result.selected_main_frame,))[0]
        if result.selected_main_frame is not None else None,
        "rejected_impact_paths": list(result.rejected_impact_paths),
        "rule_predicted_impact_path": result.rule_predicted_impact_path,
        "llm_predicted_main_frame_type": result.llm_predicted_main_frame_type,
        "frame_rule_disagreement": result.frame_rule_disagreement,
        "disagreement_reason": result.disagreement_reason,
        "resolution": result.resolution,
        "external_entities": list(result.external_entities),
        "crypto_assets": list(result.crypto_assets),
        "manual_verification_items": list(result.manual_verification_items),
    }


def _invalid_frame_reason(
    frame: event_llm_catalyst_frames.EventLLMCatalystFrame,
    source_text: str,
    *,
    external_entities: tuple[str, ...],
) -> str | None:
    if frame.confidence <= 0.0:
        return "llm_frame_invalid_zero_confidence"
    if not _quote_found(frame.evidence_quote, source_text):
        return "llm_frame_quote_not_found"
    for asset in frame.affected_assets:
        reason = _invalid_asset_reason(asset, source_text, external_entities)
        if reason:
            return reason
    return None


def _invalid_asset_reason(asset: str, source_text: str, external_entities: tuple[str, ...]) -> str | None:
    cleaned_asset = clean_text(asset)
    cleaned_source = clean_text(source_text)
    if not cleaned_asset:
        return None
    if cleaned_asset in {clean_text(entity) for entity in external_entities}:
        return "external_entity_cannot_be_crypto_asset"
    if cleaned_asset in {"openai", "spacex", "anthropic", "kraken"}:
        return "external_entity_cannot_be_crypto_asset"
    if cleaned_asset == "hype" and "hyperliquid" not in cleaned_source and "$hype" not in source_text.lower():
        return "ticker_word_collision_rejected"
    if cleaned_asset not in cleaned_source and f"${asset.lower()}" not in source_text.lower():
        return "crypto_asset_identity_not_in_source"
    return None


def _to_event_frame(
    frame: event_llm_catalyst_frames.EventLLMCatalystFrame,
    raw: RawDiscoveredEvent | None,
) -> event_catalyst_frames.EventCatalystFrame:
    return event_catalyst_frames.EventCatalystFrame(
        frame_id=_frame_id(raw.raw_id if raw else None, frame),
        frame_type=frame.frame_type,
        frame_role=frame.frame_role,
        subject=frame.subject,
        actor=frame.actor,
        object=frame.object,
        affected_entities=tuple(dict.fromkeys((*(frame.affected_entities or ()), frame.subject or ""))) if frame.subject else tuple(frame.affected_entities),
        affected_assets=tuple(frame.affected_assets),
        event_archetype=frame.event_archetype or frame.frame_type,
        claim_polarity=frame.claim_polarity,
        cause_status=frame.cause_status,
        confidence=frame.confidence,
        evidence_quote=frame.evidence_quote,
        source_raw_id=raw.raw_id if raw else None,
        source_url=raw.source_url if raw else None,
        published_at=raw.published_at if raw else None,
    )


def _has_hard_gate(frames: tuple[event_catalyst_frames.EventCatalystFrame, ...]) -> bool:
    return any(
        frame.frame_role in {event_catalyst_frames.ROLE_NEGATED, event_catalyst_frames.ROLE_CORRECTIVE}
        or frame.frame_type in {event_catalyst_frames.TYPE_PRIOR_EXPLOIT_CONTEXT, event_catalyst_frames.TYPE_DENIED_EXPLOIT}
        for frame in frames
    )


def _source_text(raws: tuple[RawDiscoveredEvent, ...], *, event: NormalizedEvent | None) -> str:
    parts: list[str] = []
    if event is not None:
        parts.extend([event.event_name, event.description or "", event.external_asset or ""])
    for raw in raws:
        parts.extend([raw.title, raw.body or ""])
        payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
        enrichment = payload.get("source_enrichment") if isinstance(payload.get("source_enrichment"), Mapping) else {}
        parts.append(str(enrichment.get("enriched_text") or ""))
    return " ".join(str(part or "") for part in parts)


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
    return len(quote_terms & source_terms) / max(1, len(quote_terms)) >= 0.80


def _frame_id(raw_id: str | None, frame: event_llm_catalyst_frames.EventLLMCatalystFrame) -> str:
    basis = "|".join((
        str(raw_id or ""),
        frame.frame_type,
        frame.frame_role,
        clean_text(frame.subject or ""),
        clean_text(frame.evidence_quote)[:160],
        "llm",
    ))
    import hashlib

    return "frame:llm:" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]
