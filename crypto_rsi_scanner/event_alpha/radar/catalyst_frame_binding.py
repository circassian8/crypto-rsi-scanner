"""Exact source bindings for LLM-proposed catalyst frames.

Bindings are deterministic research provenance.  They prevent a quoted claim
from being validated against a neighbouring article, an event summary, or a
later-mutated source row.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Mapping

import crypto_rsi_scanner.event_alpha.radar.source_enrichment as event_source_enrichment
from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent

from .resolver import clean_text


CATALYST_FRAME_VALIDATION_SCHEMA_VERSION = "event_llm_catalyst_frame_validation_v2"
CATALYST_FRAME_SOURCE_BINDING_SCHEMA_VERSION = "event_llm_catalyst_frame_source_binding_v1"
EVIDENCE_SOURCE_FIELDS = ("title", "body", "enriched_text")
MIN_EVIDENCE_QUOTE_NORMALIZED_CHARS = 10
MIN_EVIDENCE_QUOTE_TERMS = 2
ALLOWED_FRAME_TYPES = frozenset({
    "strategic_investment",
    "acquisition_or_stake",
    "valuation_event",
    "exploit_security_event",
    "prior_exploit_context",
    "denied_or_negated_exploit",
    "listing_liquidity_event",
    "unlock_supply_event",
    "market_dislocation_unknown",
    "proxy_attention",
    "policy_or_regulatory_context",
    "generic_context",
})
ALLOWED_FRAME_ROLES = frozenset({
    "main_catalyst",
    "background_context",
    "historical_context",
    "negated_claim",
    "corrective_context",
    "side_note",
    "market_reaction",
    "unknown",
})
ALLOWED_CLAIM_POLARITIES = frozenset({
    "asserted",
    "negated",
    "uncertain",
    "alleged",
    "rumored",
    "disputed",
    "denied",
    "ruled_out",
    "unknown",
})
ALLOWED_CAUSE_STATUSES = frozenset({"confirmed", "suspected", "unknown", "ruled_out"})
ALLOWED_EVENT_ARCHETYPES = ALLOWED_FRAME_TYPES
_GENERIC_IDENTITY_TERMS = frozenset({
    "the", "and", "for", "with", "from", "into", "token", "coin",
    "protocol", "project", "network", "exchange", "market", "event",
    "exposure", "users", "miner", "pre", "ipo",
})
FRAME_REQUIRED_FIELDS = frozenset({
    "frame_id",
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
    "source_raw_id",
    "source_provider",
    "source_url",
    "published_at",
    "fetched_at",
    "source_confidence",
    "source_binding_schema_version",
    "source_content_hash",
    "source_surface_hash",
    "source_surface_provenance_hash",
    "analysis_sha256",
    "evidence_source_field",
    "evidence_normalized_start",
    "evidence_normalized_end",
})
VALIDATION_REQUIRED_FIELDS = frozenset({
    "schema_version",
    "source_binding_schema_version",
    "source_raw_id",
    "source_provider",
    "source_url",
    "source_published_at",
    "source_fetched_at",
    "source_confidence",
    "source_content_hash",
    "source_surface_hash",
    "source_surface_provenance_hash",
    "analysis_sha256",
    "validation_payload_sha256",
    "valid_frames",
    "invalid_frames",
    "frame_warnings",
    "rule_llm_disagreements",
    "selected_main_frame",
    "rejected_impact_paths",
    "rule_predicted_impact_path",
    "llm_predicted_main_frame_type",
    "frame_rule_disagreement",
    "disagreement_reason",
    "resolution",
    "external_entities",
    "crypto_assets",
    "manual_verification_items",
})
INVALID_FRAME_FIELDS = frozenset({
    "frame_type",
    "frame_role",
    "subject",
    "reason",
    "evidence_quote",
})
VALIDATION_LIST_FIELDS = (
    "invalid_frames",
    "frame_warnings",
    "rule_llm_disagreements",
    "rejected_impact_paths",
    "external_entities",
    "crypto_assets",
    "manual_verification_items",
)


@dataclass(frozen=True)
class EvidenceQuoteBinding:
    source_field: str
    normalized_start: int
    normalized_end: int


def evidence_source_fields(raw: RawDiscoveredEvent) -> dict[str, str]:
    """Return the closed, quality-gated text surface eligible for LLM proof."""
    return {
        "title": str(raw.title or ""),
        "body": str(raw.body or ""),
        "enriched_text": event_source_enrichment.enriched_text_for_llm(raw),
    }


def normalized_evidence_source_fields(raw: RawDiscoveredEvent) -> dict[str, str]:
    return {
        field: clean_text(value)
        for field, value in evidence_source_fields(raw).items()
    }


def source_surface_hash(raw: RawDiscoveredEvent) -> str:
    payload = {
        field: value
        for field, value in normalized_evidence_source_fields(raw).items()
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def source_surface_provenance_hash(raw: RawDiscoveredEvent) -> str:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    enrichment = (
        payload.get("source_enrichment")
        if isinstance(payload.get("source_enrichment"), Mapping)
        else {}
    )
    provenance = {
        "raw_id": raw.raw_id,
        "provider": raw.provider,
        "source_url": raw.source_url,
        "published_at": raw.published_at.isoformat() if raw.published_at else None,
        "fetched_at": raw.fetched_at.isoformat(),
        "source_confidence": float(raw.source_confidence),
        "content_hash": raw.content_hash,
        "source_enrichment": enrichment,
    }
    encoded = json.dumps(
        provenance,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_payload_sha256(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validation_payload_sha256(validation: Mapping[str, object]) -> str:
    payload = {
        key: value
        for key, value in validation.items()
        if key != "validation_payload_sha256"
    }
    return canonical_payload_sha256(payload)


def validation_matches_analysis(
    validation: Mapping[str, object],
    analysis: Mapping[str, object],
) -> bool:
    analysis_frames: list[Mapping[str, object]] = []
    main = analysis.get("main_catalyst_frame")
    if isinstance(main, Mapping):
        analysis_frames.append(main)
    for field in ("background_frames", "negated_or_corrective_frames"):
        values = analysis.get(field)
        if not isinstance(values, list):
            return False
        if any(not isinstance(value, Mapping) for value in values):
            return False
        analysis_frames.extend(value for value in values if isinstance(value, Mapping))
    valid_frames = validation.get("valid_frames")
    invalid_frames = validation.get("invalid_frames")
    if not isinstance(valid_frames, list) or not isinstance(invalid_frames, list):
        return False
    if len(valid_frames) + len(invalid_frames) != len(analysis_frames):
        return False
    remaining = list(analysis_frames)
    for frame in valid_frames:
        if not isinstance(frame, Mapping):
            return False
        key = _analysis_frame_key(frame)
        match_index = next(
            (index for index, proposal in enumerate(remaining) if _analysis_frame_key(proposal) == key),
            None,
        )
        if match_index is None:
            return False
        remaining.pop(match_index)
    for frame in invalid_frames:
        if not isinstance(frame, Mapping):
            return False
        match_index = next(
            (
                index for index, proposal in enumerate(remaining)
                if _invalid_frame_matches_analysis(frame, proposal)
            ),
            None,
        )
        if match_index is None:
            return False
        remaining.pop(match_index)
    return not remaining


def _analysis_frame_key(frame: Mapping[str, object]) -> str:
    entities = list(frame.get("affected_entities") or [])
    subject = frame.get("subject")
    if subject and subject not in entities:
        entities.append(subject)
    confidence = frame.get("confidence")
    normalized = {
        "frame_type": frame.get("frame_type"),
        "frame_role": frame.get("frame_role"),
        "subject": subject,
        "actor": frame.get("actor"),
        "object": frame.get("object"),
        "affected_entities": entities,
        "affected_assets": list(frame.get("affected_assets") or []),
        "event_archetype": frame.get("event_archetype") or frame.get("frame_type"),
        "claim_polarity": frame.get("claim_polarity"),
        "cause_status": frame.get("cause_status"),
        "confidence": round(float(confidence), 4) if isinstance(confidence, (int, float)) else confidence,
        "evidence_quote": frame.get("evidence_quote"),
    }
    return canonical_payload_sha256(normalized)


def _invalid_frame_matches_analysis(
    invalid: Mapping[str, object],
    proposal: Mapping[str, object],
) -> bool:
    return all(
        invalid.get(field) == proposal.get(field)
        for field in ("frame_type", "frame_role", "subject", "evidence_quote")
    ) and isinstance(invalid.get("reason"), str) and bool(invalid.get("reason"))


def quote_is_informative(quote: str) -> bool:
    cleaned = clean_text(quote)
    terms = re.findall(r"[\w$]+", cleaned, flags=re.UNICODE)
    return bool(
        len(cleaned) >= MIN_EVIDENCE_QUOTE_NORMALIZED_CHARS
        and len(terms) >= MIN_EVIDENCE_QUOTE_TERMS
        and any(len(term.strip("$")) >= 4 for term in terms)
    )


def identity_in_evidence(value: str, source_text: str) -> bool:
    cleaned = clean_text(value)
    source = clean_text(source_text)
    if not cleaned or not source:
        return False
    if _bounded_term_present(cleaned, source):
        return True
    terms = tuple(
        term for term in re.findall(r"[\w$]+", cleaned, flags=re.UNICODE)
        if len(term.strip("$")) >= 3 and term not in _GENERIC_IDENTITY_TERMS
    )
    return bool(terms and any(_bounded_term_present(term, source) for term in terms))


def asset_identity_in_evidence(value: str, source_text: str) -> bool:
    cleaned = clean_text(value).strip("$")
    source = clean_text(source_text)
    if not cleaned or not source:
        return False
    if _bounded_term_present(f"${cleaned}", source):
        return True
    if not _bounded_term_present(cleaned, source):
        return False
    if len(cleaned) > 3:
        return True
    context = r"(?:token|coin|crypto|listing|listed|treasury|trading|perp|blockchain|mainnet)"
    ticker = rf"(?<![\w$]){re.escape(cleaned)}(?![\w])"
    return bool(
        re.search(rf"{ticker}.{{0,24}}\b{context}\b", source)
        or re.search(rf"\b{context}\b.{{0,24}}{ticker}", source)
    )


def canonical_llm_frame_id(
    *,
    raw_id: str,
    frame_type: str,
    frame_role: str,
    subject: str | None,
    evidence_quote: str,
) -> str:
    basis = "|".join((
        raw_id,
        frame_type,
        frame_role,
        clean_text(subject or ""),
        clean_text(evidence_quote)[:160],
        "llm",
    ))
    return "frame:llm:" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def find_quote_binding(
    quote: str,
    source_fields: Mapping[str, str],
) -> EvidenceQuoteBinding | None:
    """Bind a normalized contiguous quote inside one canonical source field."""
    quote_clean = clean_text(quote)
    if not quote_is_informative(quote):
        return None
    for field in EVIDENCE_SOURCE_FIELDS:
        surface = clean_text(source_fields.get(field) or "")
        start = surface.find(quote_clean)
        if start >= 0:
            return EvidenceQuoteBinding(
                source_field=field,
                normalized_start=start,
                normalized_end=start + len(quote_clean),
            )
    return None


def _bounded_term_present(term: str, source: str) -> bool:
    return re.search(
        rf"(?<![\w$]){re.escape(term)}(?![\w])",
        source,
        flags=re.UNICODE,
    ) is not None


def quote_binding_matches(
    raw: RawDiscoveredEvent,
    *,
    quote: str,
    source_field: object,
    normalized_start: object,
    normalized_end: object,
) -> bool:
    field = str(source_field or "")
    if field not in EVIDENCE_SOURCE_FIELDS:
        return False
    try:
        start = int(normalized_start)
        end = int(normalized_end)
    except (TypeError, ValueError):
        return False
    quote_clean = clean_text(quote)
    surface = normalized_evidence_source_fields(raw)[field]
    return bool(
        quote_clean
        and start >= 0
        and end == start + len(quote_clean)
        and end <= len(surface)
        and surface[start:end] == quote_clean
    )


def validation_binding_matches_raw(
    validation: Mapping[str, object],
    raw: RawDiscoveredEvent,
) -> bool:
    return bool(
        validation.get("schema_version") == CATALYST_FRAME_VALIDATION_SCHEMA_VERSION
        and validation.get("source_binding_schema_version")
        == CATALYST_FRAME_SOURCE_BINDING_SCHEMA_VERSION
        and str(validation.get("source_raw_id") or "") == raw.raw_id
        and str(validation.get("source_provider") or "") == raw.provider
        and (validation.get("source_url") or None) == (raw.source_url or None)
        and (validation.get("source_published_at") or None)
        == (raw.published_at.isoformat() if raw.published_at else None)
        and str(validation.get("source_fetched_at") or "") == raw.fetched_at.isoformat()
        and _same_finite_float(validation.get("source_confidence"), raw.source_confidence)
        and str(validation.get("source_content_hash") or "") == raw.content_hash
        and str(validation.get("source_surface_hash") or "") == source_surface_hash(raw)
        and str(validation.get("source_surface_provenance_hash") or "")
        == source_surface_provenance_hash(raw)
    )


def frame_binding_matches_raw(
    frame: Mapping[str, object],
    raw: RawDiscoveredEvent,
) -> bool:
    return bool(
        frame.get("source_binding_schema_version")
        == CATALYST_FRAME_SOURCE_BINDING_SCHEMA_VERSION
        and str(frame.get("source_raw_id") or "") == raw.raw_id
        and str(frame.get("source_provider") or "") == raw.provider
        and (frame.get("source_url") or None) == (raw.source_url or None)
        and (frame.get("published_at") or None)
        == (raw.published_at.isoformat() if raw.published_at else None)
        and str(frame.get("fetched_at") or "") == raw.fetched_at.isoformat()
        and _same_finite_float(frame.get("source_confidence"), raw.source_confidence)
        and str(frame.get("source_content_hash") or "") == raw.content_hash
        and str(frame.get("source_surface_hash") or "") == source_surface_hash(raw)
        and str(frame.get("source_surface_provenance_hash") or "")
        == source_surface_provenance_hash(raw)
        and _sha256_text(frame.get("analysis_sha256"))
        and quote_binding_matches(
            raw,
            quote=str(frame.get("evidence_quote") or ""),
            source_field=frame.get("evidence_source_field"),
            normalized_start=frame.get("evidence_normalized_start"),
            normalized_end=frame.get("evidence_normalized_end"),
        )
    )


def frame_contract_valid(frame: Mapping[str, object], raw: RawDiscoveredEvent) -> bool:
    if (
        set(frame) != FRAME_REQUIRED_FIELDS
        or not _frame_primitive_types_valid(frame)
        or not frame_binding_matches_raw(frame, raw)
    ):
        return False
    frame_type = frame.get("frame_type")
    frame_role = frame.get("frame_role")
    if frame_type not in ALLOWED_FRAME_TYPES or frame_role not in ALLOWED_FRAME_ROLES:
        return False
    if frame.get("claim_polarity") not in ALLOWED_CLAIM_POLARITIES:
        return False
    if frame.get("cause_status") not in ALLOWED_CAUSE_STATUSES:
        return False
    if frame.get("event_archetype") not in ALLOWED_EVENT_ARCHETYPES:
        return False
    expected_id = canonical_llm_frame_id(
        raw_id=raw.raw_id,
        frame_type=str(frame_type),
        frame_role=str(frame_role),
        subject=str(frame.get("subject") or "") or None,
        evidence_quote=str(frame.get("evidence_quote") or ""),
    )
    if frame.get("frame_id") != expected_id:
        return False
    source_text = " ".join(evidence_source_fields(raw).values())
    subject = str(frame.get("subject") or "")
    actor = str(frame.get("actor") or "")
    if subject and not identity_in_evidence(subject, source_text):
        return False
    if actor and not identity_in_evidence(actor, source_text):
        return False
    identities = (subject, *[str(value) for value in frame.get("affected_entities") or []])
    assets = tuple(str(value) for value in frame.get("affected_assets") or [])
    if not any(identity_in_evidence(value, source_text) for value in identities if value) and not any(
        asset_identity_in_evidence(value, source_text) for value in assets
    ):
        return False
    if any(not identity_in_evidence(value, source_text) for value in identities if value):
        return False
    if any(not asset_identity_in_evidence(value, source_text) for value in assets):
        return False
    return True


def current_validation_for_raw(raw: RawDiscoveredEvent) -> Mapping[str, object] | None:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    validation = payload.get("llm_catalyst_frame_validation")
    if (
        not isinstance(validation, Mapping)
        or set(validation) != VALIDATION_REQUIRED_FIELDS
        or not _validation_primitive_types_valid(validation)
        or not validation_binding_matches_raw(validation, raw)
    ):
        return None
    analysis = payload.get("llm_catalyst_frame_analysis")
    if (
        not isinstance(analysis, Mapping)
        or str(analysis.get("raw_id") or "") != raw.raw_id
        or str(validation.get("analysis_sha256") or "") != canonical_payload_sha256(analysis)
        or not validation_matches_analysis(validation, analysis)
        or validation.get("validation_payload_sha256") != validation_payload_sha256(validation)
    ):
        return None
    raw_frames = validation.get("valid_frames")
    if not isinstance(raw_frames, list) or any(
        not isinstance(frame, Mapping)
        or not frame_contract_valid(frame, raw)
        or frame.get("analysis_sha256") != validation.get("analysis_sha256")
        for frame in raw_frames
    ):
        return None
    selected = validation.get("selected_main_frame")
    if bool(raw_frames) != (selected is not None):
        return None
    if selected is not None and (
        not isinstance(selected, Mapping)
        or not frame_contract_valid(selected, raw)
        or selected.get("analysis_sha256") != validation.get("analysis_sha256")
        or selected not in raw_frames
    ):
        return None
    if not _derived_validation_metadata_valid(validation, raw_frames, selected):
        return None
    return validation


def _frame_primitive_types_valid(frame: Mapping[str, object]) -> bool:
    required_strings = (
        "frame_id",
        "frame_type",
        "frame_role",
        "event_archetype",
        "claim_polarity",
        "cause_status",
        "evidence_quote",
        "source_raw_id",
        "source_provider",
        "fetched_at",
        "source_binding_schema_version",
        "source_content_hash",
        "source_surface_hash",
        "source_surface_provenance_hash",
        "analysis_sha256",
        "evidence_source_field",
    )
    if any(type(frame.get(field)) is not str or not frame.get(field) for field in required_strings):
        return False
    if any(
        frame.get(field) is not None and type(frame.get(field)) is not str
        for field in ("subject", "actor", "object", "source_url", "published_at")
    ):
        return False
    if any(
        type(frame.get(field)) is not list
        or any(type(value) is not str or not value.strip() for value in frame.get(field, []))
        for field in ("affected_entities", "affected_assets")
    ):
        return False
    if any(type(frame.get(field)) is not int for field in (
        "evidence_normalized_start",
        "evidence_normalized_end",
    )):
        return False
    return _bounded_finite_number(frame.get("confidence"), lower_open=True) and (
        _bounded_finite_number(frame.get("source_confidence"), lower_open=False)
    )


def _validation_primitive_types_valid(validation: Mapping[str, object]) -> bool:
    required_strings = (
        "schema_version",
        "source_binding_schema_version",
        "source_raw_id",
        "source_provider",
        "source_fetched_at",
        "source_content_hash",
        "source_surface_hash",
        "source_surface_provenance_hash",
        "analysis_sha256",
        "validation_payload_sha256",
        "resolution",
    )
    if any(
        type(validation.get(field)) is not str or not validation.get(field)
        for field in required_strings
    ):
        return False
    if any(
        validation.get(field) is not None and type(validation.get(field)) is not str
        for field in (
            "source_url",
            "source_published_at",
            "rule_predicted_impact_path",
            "llm_predicted_main_frame_type",
            "disagreement_reason",
        )
    ):
        return False
    if type(validation.get("valid_frames")) is not list:
        return False
    if any(
        type(validation.get(field)) is not list
        or any(type(value) is not str for value in validation.get(field, []))
        for field in VALIDATION_LIST_FIELDS
        if field != "invalid_frames"
    ):
        return False
    invalid_frames = validation.get("invalid_frames")
    if type(invalid_frames) is not list or any(
        not _invalid_frame_primitive_types_valid(frame)
        for frame in invalid_frames
    ):
        return False
    if type(validation.get("frame_rule_disagreement")) is not bool:
        return False
    selected = validation.get("selected_main_frame")
    if selected is not None and not isinstance(selected, Mapping):
        return False
    return _bounded_finite_number(
        validation.get("source_confidence"),
        lower_open=False,
    ) and all(
        _sha256_text(validation.get(field))
        for field in ("analysis_sha256", "validation_payload_sha256")
    )


def _invalid_frame_primitive_types_valid(frame: object) -> bool:
    if not isinstance(frame, Mapping) or set(frame) != INVALID_FRAME_FIELDS:
        return False
    return bool(
        all(
            type(frame.get(field)) is str
            for field in ("frame_type", "frame_role", "reason", "evidence_quote")
        )
        and frame.get("frame_type")
        and frame.get("frame_role")
        and frame.get("reason")
        and (frame.get("subject") is None or type(frame.get("subject")) is str)
    )


def _bounded_finite_number(value: object, *, lower_open: bool) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    number = float(value)
    return bool(
        math.isfinite(number)
        and (number > 0.0 if lower_open else number >= 0.0)
        and number <= 1.0
    )


def _derived_validation_metadata_valid(
    validation: Mapping[str, object],
    frames: list[object],
    selected: object,
) -> bool:
    selected_frame = selected if isinstance(selected, Mapping) else {}
    llm_type = str(selected_frame.get("frame_type") or "") or None
    rule_type = str(validation.get("rule_predicted_impact_path") or "") or None
    if rule_type is not None and rule_type not in ALLOWED_FRAME_TYPES:
        return False
    disagreement = bool(rule_type and llm_type and rule_type != llm_type)
    expected_reason = f"rules={rule_type};llm={llm_type}" if disagreement else None
    resolution = "unresolved"
    if selected_frame and selected_frame.get("frame_role") == "main_catalyst":
        resolution = "llm_wins" if disagreement else "rules_win"
    if validation.get("invalid_frames") and not selected_frame:
        resolution = "rules_win" if rule_type else "unresolved"
    hard_gate = any(
        isinstance(frame, Mapping)
        and (
            frame.get("frame_role") in {"negated_claim", "corrective_context"}
            or frame.get("frame_type") in {"prior_exploit_context", "denied_or_negated_exploit"}
        )
        for frame in frames
    )
    if disagreement and hard_gate:
        resolution = "llm_wins"
    expected_disagreements = [expected_reason] if expected_reason else []
    if disagreement and hard_gate:
        expected_disagreements.append("negation_or_background_hard_gate_supported_by_quote")
    return bool(
        validation.get("llm_predicted_main_frame_type") == llm_type
        and type(validation.get("frame_rule_disagreement")) is bool
        and validation.get("frame_rule_disagreement") is disagreement
        and validation.get("disagreement_reason") == expected_reason
        and validation.get("resolution") == resolution
        and validation.get("rule_llm_disagreements") == expected_disagreements
    )


def _same_finite_float(left: object, right: object) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return False
    try:
        left_value = float(left)
        right_value = float(right)
    except (TypeError, ValueError):
        return False
    return bool(
        math.isfinite(left_value)
        and math.isfinite(right_value)
        and left_value == right_value
    )


def _sha256_text(value: object) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or "")))
