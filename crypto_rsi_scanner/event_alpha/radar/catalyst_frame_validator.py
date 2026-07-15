"""Deterministic validation for LLM catalyst-frame analyses.

LLM catalyst frames are semantic proposals. This module enforces source-quote,
identity, negation, and rule-disagreement constraints before frames can be used
as research evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Any, Iterable

import crypto_rsi_scanner.event_alpha.radar.catalyst_frame_binding as event_catalyst_frame_binding
import crypto_rsi_scanner.event_alpha.radar.catalyst_frames as event_catalyst_frames
import crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames as event_llm_catalyst_frames
from crypto_rsi_scanner.event_core.models import NormalizedEvent, RawDiscoveredEvent
from crypto_rsi_scanner.event_alpha.radar.resolver import clean_text


RESOLUTION_LLM_WINS = "llm_wins"
RESOLUTION_RULES_WIN = "rules_win"
RESOLUTION_UNRESOLVED = "unresolved"


class _CatalystFrameBindingError(ValueError):
    """Raised when a validated frame is applied outside its exact source."""


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
    schema_version: str = event_catalyst_frame_binding.CATALYST_FRAME_VALIDATION_SCHEMA_VERSION
    source_binding_schema_version: str | None = None
    source_raw_id: str | None = None
    source_provider: str | None = None
    source_url: str | None = None
    source_published_at: str | None = None
    source_fetched_at: str | None = None
    source_confidence: float | None = None
    source_content_hash: str | None = None
    source_surface_hash: str | None = None
    source_surface_provenance_hash: str | None = None
    analysis_sha256: str | None = None


def validate_llm_catalyst_frames(
    analysis: event_llm_catalyst_frames.EventLLMCatalystFrameAnalysis,
    raw_events: Iterable[RawDiscoveredEvent],
    *,
    event: NormalizedEvent | None = None,
    rule_frames: Iterable[event_catalyst_frames.EventCatalystFrame] = (),
) -> CatalystFrameValidationResult:
    raws = tuple(raw_events)
    source_raw, binding_error = _resolve_analysis_raw(analysis.raw_id, raws)
    if source_raw is None:
        return _invalid_source_binding_result(analysis, binding_error or "llm_frame_source_binding_invalid")
    source_fields = event_catalyst_frame_binding.evidence_source_fields(source_raw)
    source_text = " ".join(source_fields.values())
    analysis_payload = event_llm_catalyst_frames.analysis_to_dict(analysis)
    analysis_sha256 = event_catalyst_frame_binding.canonical_payload_sha256(analysis_payload)
    supplied_rule_rows = tuple(rule_frames)
    candidate_rule_rows = (
        tuple(
            frame
            for frame in supplied_rule_rows
            if frame.source_raw_id in {None, source_raw.raw_id}
        )
        if supplied_rule_rows
        else event_catalyst_frames.build_catalyst_frames((source_raw,), event=event)
    )
    rule_rows = tuple(
        frame for frame in candidate_rule_rows
        if not frame.frame_id.startswith("frame:llm:")
    )
    rule_main, _ = event_catalyst_frames.select_main_catalyst_frame(rule_rows, event)
    valid: list[event_catalyst_frames.EventCatalystFrame] = []
    invalid: list[dict[str, Any]] = []
    warnings: list[str] = list(analysis.warnings)
    rejected: list[str] = list(analysis.rejected_impact_paths)
    external_entities = tuple(analysis.external_entities)
    crypto_assets = tuple(analysis.crypto_assets)

    for frame in analysis.all_frames:
        quote_binding = event_catalyst_frame_binding.find_quote_binding(
            frame.evidence_quote,
            source_fields,
        )
        reason = _invalid_frame_reason(
            frame,
            source_text,
            quote_binding=quote_binding,
            external_entities=external_entities,
        )
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
        assert quote_binding is not None
        valid.append(_to_event_frame(
            frame,
            source_raw,
            quote_binding=quote_binding,
            analysis_sha256=analysis_sha256,
        ))
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
        source_binding_schema_version=(
            event_catalyst_frame_binding.CATALYST_FRAME_SOURCE_BINDING_SCHEMA_VERSION
        ),
        source_raw_id=source_raw.raw_id,
        source_provider=source_raw.provider,
        source_url=source_raw.source_url,
        source_published_at=source_raw.published_at.isoformat() if source_raw.published_at else None,
        source_fetched_at=source_raw.fetched_at.isoformat(),
        source_confidence=float(source_raw.source_confidence),
        source_content_hash=source_raw.content_hash,
        source_surface_hash=event_catalyst_frame_binding.source_surface_hash(source_raw),
        source_surface_provenance_hash=(
            event_catalyst_frame_binding.source_surface_provenance_hash(source_raw)
        ),
        analysis_sha256=analysis_sha256,
    )


def apply_validation_to_raw_event(
    raw: RawDiscoveredEvent,
    analysis: event_llm_catalyst_frames.EventLLMCatalystFrameAnalysis,
    validation: CatalystFrameValidationResult,
) -> RawDiscoveredEvent:
    serialized_analysis = event_llm_catalyst_frames.analysis_to_dict(analysis)
    serialized_validation = validation_to_dict(validation)
    if analysis.raw_id != raw.raw_id:
        raise _CatalystFrameBindingError("catalyst frame analysis raw_id does not match target raw")
    if not event_catalyst_frame_binding.validation_binding_matches_raw(serialized_validation, raw):
        raise _CatalystFrameBindingError("catalyst frame validation source binding is stale or mismatched")
    if serialized_validation["analysis_sha256"] != event_catalyst_frame_binding.canonical_payload_sha256(
        serialized_analysis
    ):
        raise _CatalystFrameBindingError("catalyst frame validation belongs to a different analysis")
    if not event_catalyst_frame_binding.validation_matches_analysis(
        serialized_validation,
        serialized_analysis,
    ):
        raise _CatalystFrameBindingError("catalyst frame validation does not match analysis frames")
    if any(
        not event_catalyst_frame_binding.frame_contract_valid(frame, raw)
        for frame in serialized_validation["valid_frames"]
    ):
        raise _CatalystFrameBindingError("catalyst frame quote binding is stale or mismatched")
    selected = serialized_validation["selected_main_frame"]
    if selected is not None and (
        not event_catalyst_frame_binding.frame_contract_valid(selected, raw)
        or selected not in serialized_validation["valid_frames"]
    ):
        raise _CatalystFrameBindingError("selected catalyst frame binding is stale or mismatched")
    payload = dict(raw.raw_json or {})
    payload["llm_catalyst_frame_analysis"] = serialized_analysis
    payload["llm_catalyst_frame_validation"] = serialized_validation
    return replace(raw, raw_json=payload)


def validation_to_dict(result: CatalystFrameValidationResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": result.schema_version,
        "source_binding_schema_version": result.source_binding_schema_version,
        "source_raw_id": result.source_raw_id,
        "source_provider": result.source_provider,
        "source_url": result.source_url,
        "source_published_at": result.source_published_at,
        "source_fetched_at": result.source_fetched_at,
        "source_confidence": result.source_confidence,
        "source_content_hash": result.source_content_hash,
        "source_surface_hash": result.source_surface_hash,
        "source_surface_provenance_hash": result.source_surface_provenance_hash,
        "analysis_sha256": result.analysis_sha256,
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
    payload["validation_payload_sha256"] = (
        event_catalyst_frame_binding.validation_payload_sha256(payload)
    )
    return payload


def _resolve_analysis_raw(
    analysis_raw_id: str,
    raws: tuple[RawDiscoveredEvent, ...],
) -> tuple[RawDiscoveredEvent | None, str | None]:
    if not str(analysis_raw_id or ""):
        return None, "llm_frame_analysis_raw_id_missing"
    matches = tuple(raw for raw in raws if raw.raw_id == analysis_raw_id)
    if not matches:
        return None, "llm_frame_analysis_raw_id_not_found"
    if len(matches) != 1:
        return None, "llm_frame_analysis_raw_id_not_unique"
    if not str(matches[0].content_hash or ""):
        return None, "llm_frame_source_content_hash_missing"
    return matches[0], None


def _invalid_source_binding_result(
    analysis: event_llm_catalyst_frames.EventLLMCatalystFrameAnalysis,
    reason: str,
) -> CatalystFrameValidationResult:
    invalid = tuple(
        {
            "frame_type": frame.frame_type,
            "frame_role": frame.frame_role,
            "subject": frame.subject,
            "reason": reason,
            "evidence_quote": frame.evidence_quote,
        }
        for frame in analysis.all_frames
    ) or ({
        "frame_type": "analysis",
        "frame_role": event_catalyst_frames.ROLE_UNKNOWN,
        "subject": None,
        "reason": reason,
        "evidence_quote": "",
    },)
    return CatalystFrameValidationResult(
        valid_frames=(),
        invalid_frames=invalid,
        frame_warnings=tuple(dict.fromkeys((*analysis.warnings, reason))),
        rule_llm_disagreements=(),
        selected_main_frame=None,
        rejected_impact_paths=tuple(analysis.rejected_impact_paths),
        rule_predicted_impact_path=None,
        llm_predicted_main_frame_type=None,
        frame_rule_disagreement=False,
        disagreement_reason=None,
        resolution=RESOLUTION_UNRESOLVED,
        external_entities=tuple(analysis.external_entities),
        crypto_assets=tuple(analysis.crypto_assets),
        manual_verification_items=tuple(analysis.manual_verification_items),
    )


def _invalid_frame_reason(
    frame: event_llm_catalyst_frames.EventLLMCatalystFrame,
    source_text: str,
    *,
    quote_binding: event_catalyst_frame_binding.EvidenceQuoteBinding | None,
    external_entities: tuple[str, ...],
) -> str | None:
    if frame.frame_type not in event_catalyst_frame_binding.ALLOWED_FRAME_TYPES:
        return "llm_frame_type_invalid"
    if frame.frame_role not in event_catalyst_frame_binding.ALLOWED_FRAME_ROLES:
        return "llm_frame_role_invalid"
    if frame.claim_polarity not in event_catalyst_frame_binding.ALLOWED_CLAIM_POLARITIES:
        return "llm_frame_claim_polarity_invalid"
    if frame.cause_status not in event_catalyst_frame_binding.ALLOWED_CAUSE_STATUSES:
        return "llm_frame_cause_status_invalid"
    archetype = frame.event_archetype or frame.frame_type
    if archetype not in event_catalyst_frame_binding.ALLOWED_EVENT_ARCHETYPES:
        return "llm_frame_event_archetype_invalid"
    if (
        isinstance(frame.confidence, bool)
        or not isinstance(frame.confidence, (int, float))
        or not math.isfinite(float(frame.confidence))
        or not 0.0 < float(frame.confidence) <= 1.0
    ):
        return "llm_frame_confidence_invalid"
    if not event_catalyst_frame_binding.quote_is_informative(frame.evidence_quote):
        return "llm_frame_quote_too_weak"
    if quote_binding is None:
        return "llm_frame_quote_not_found"
    for asset in frame.affected_assets:
        reason = _invalid_asset_reason(asset, source_text, external_entities)
        if reason:
            return reason
    identities = tuple(value for value in (
        frame.subject,
        frame.actor,
        *frame.affected_entities,
    ) if str(value or "").strip())
    if not identities and not frame.affected_assets:
        return "llm_frame_identity_missing"
    if any(
        not event_catalyst_frame_binding.identity_in_evidence(str(value), source_text)
        for value in identities
    ):
        return "llm_frame_identity_not_in_source"
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
    if not event_catalyst_frame_binding.asset_identity_in_evidence(asset, source_text):
        return "crypto_asset_identity_not_in_source"
    return None


def _to_event_frame(
    frame: event_llm_catalyst_frames.EventLLMCatalystFrame,
    raw: RawDiscoveredEvent,
    *,
    quote_binding: event_catalyst_frame_binding.EvidenceQuoteBinding,
    analysis_sha256: str,
) -> event_catalyst_frames.EventCatalystFrame:
    return event_catalyst_frames.EventCatalystFrame(
        frame_id=_frame_id(raw.raw_id, frame),
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
        source_raw_id=raw.raw_id,
        source_provider=raw.provider,
        source_url=raw.source_url,
        published_at=raw.published_at,
        fetched_at=raw.fetched_at,
        source_confidence=float(raw.source_confidence),
        source_binding_schema_version=(
            event_catalyst_frame_binding.CATALYST_FRAME_SOURCE_BINDING_SCHEMA_VERSION
        ),
        source_content_hash=raw.content_hash,
        source_surface_hash=event_catalyst_frame_binding.source_surface_hash(raw),
        source_surface_provenance_hash=(
            event_catalyst_frame_binding.source_surface_provenance_hash(raw)
        ),
        analysis_sha256=analysis_sha256,
        evidence_source_field=quote_binding.source_field,
        evidence_normalized_start=quote_binding.normalized_start,
        evidence_normalized_end=quote_binding.normalized_end,
    )


def _has_hard_gate(frames: tuple[event_catalyst_frames.EventCatalystFrame, ...]) -> bool:
    return any(
        frame.frame_role in {event_catalyst_frames.ROLE_NEGATED, event_catalyst_frames.ROLE_CORRECTIVE}
        or frame.frame_type in {event_catalyst_frames.TYPE_PRIOR_EXPLOIT_CONTEXT, event_catalyst_frames.TYPE_DENIED_EXPLOIT}
        for frame in frames
    )


def _frame_id(raw_id: str | None, frame: event_llm_catalyst_frames.EventLLMCatalystFrame) -> str:
    return event_catalyst_frame_binding.canonical_llm_frame_id(
        raw_id=str(raw_id or ""),
        frame_type=frame.frame_type,
        frame_role=frame.frame_role,
        subject=frame.subject,
        evidence_quote=frame.evidence_quote,
    )
