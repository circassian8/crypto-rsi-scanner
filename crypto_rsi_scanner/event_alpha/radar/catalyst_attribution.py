"""Closed temporal-semantic attribution for catalyst evidence.

The contract distinguishes when a source became public from the event time it
claims. A later article may remain useful research context, but it cannot be
used as antecedent causal evidence for an earlier market observation.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from crypto_rsi_scanner.event_core.models import RawDiscoveredEvent
from crypto_rsi_scanner.event_alpha.providers import source_registry

from . import catalyst_frame_binding, catalyst_frames


SCHEMA_ID = "event_alpha.catalyst_attribution"
SCHEMA_VERSION = 1
CONTEMPORANEOUS_TOLERANCE_SECONDS = 5 * 60
TEMPORAL_RELATIONS = {
    "antecedent",
    "contemporaneous",
    "retrospective",
    "unknown",
}
EVIDENCE_USES = {
    "causal_candidate",
    "scheduled_anticipation",
    "retrospective_context",
    "background_context",
    "disproof",
    "unknown",
}
CAUSAL_BASES = {"direct_official", "validated_direct_beneficiary", "none"}
SEMANTIC_ROLES = {
    catalyst_frames.ROLE_MAIN,
    catalyst_frames.ROLE_BACKGROUND,
    catalyst_frames.ROLE_HISTORICAL,
    catalyst_frames.ROLE_NEGATED,
    catalyst_frames.ROLE_CORRECTIVE,
    catalyst_frames.ROLE_SIDE_NOTE,
    catalyst_frames.ROLE_MARKET_REACTION,
    catalyst_frames.ROLE_UNKNOWN,
}
_CONTEXT_ROLES = {
    catalyst_frames.ROLE_BACKGROUND,
    catalyst_frames.ROLE_HISTORICAL,
    catalyst_frames.ROLE_MARKET_REACTION,
    catalyst_frames.ROLE_SIDE_NOTE,
}
_DISPROOF_ROLES = {
    catalyst_frames.ROLE_NEGATED,
    catalyst_frames.ROLE_CORRECTIVE,
}
_DIRECT_CANDIDATE_ROLES = {
    "direct_subject",
    "direct_beneficiary",
    "affected_asset",
    "primary_subject",
}
_STRONG_IMPACT_VALUES = {
    "strong",
    "direct",
    "explicit",
    "validated",
    "high",
    "confirmed",
}
_OFFICIAL_SOURCE_CLASSES = {
    "official_exchange",
    "official_project",
    "structured_calendar",
    "structured_unlock",
}
_KEYS = {
    "schema_id",
    "schema_version",
    "anomaly_id",
    "anomaly_observed_at",
    "anomaly_binding_digest",
    "source_id",
    "source_identity_kind",
    "source_provider",
    "source_class",
    "source_authority_verified",
    "source_can_validate_catalyst",
    "source_can_validate_impact_path",
    "source_registry_reason_codes",
    "source_url",
    "source_content_hash",
    "source_published_at",
    "source_fetched_at",
    "source_public_at",
    "publication_lag_seconds",
    "temporal_relation",
    "event_time",
    "event_time_source",
    "event_time_confidence",
    "semantic_role",
    "semantic_role_validated",
    "candidate_role",
    "impact_path_strength",
    "cause_status",
    "causal_basis",
    "evidence_use",
    "causal_eligible",
    "reason_codes",
    "research_only",
    "auto_apply",
    "attribution_digest",
}


def assess_catalyst_attribution(
    anomaly: RawDiscoveredEvent,
    source: RawDiscoveredEvent,
) -> dict[str, Any]:
    """Assess one exact raw source against one exact market anomaly."""

    frame = _source_frame(source)
    source_payload = source.raw_json if isinstance(source.raw_json, Mapping) else {}
    anomaly_payload = (
        anomaly.raw_json if isinstance(anomaly.raw_json, Mapping) else {}
    )
    event_payload = _mapping(source_payload.get("event"))
    source_values: dict[str, Any] = {
        "raw_id": source.raw_id,
        "provider": source.provider,
        "source_url": source.source_url,
        "content_hash": source.content_hash,
        "published_at": source.published_at,
        "fetched_at": source.fetched_at,
        "event_time": event_payload.get("event_time") or source_payload.get("event_time"),
        "event_time_source": (
            event_payload.get("event_time_source")
            or source_payload.get("event_time_source")
        ),
        "event_time_confidence": (
            event_payload.get("event_time_confidence")
            if "event_time_confidence" in event_payload
            else source_payload.get("event_time_confidence")
        ),
        "main_frame_role": frame.get("frame_role"),
        "cause_status": frame.get("cause_status"),
        "candidate_role": _raw_candidate_role(source_payload),
        "impact_path_strength": _raw_impact_strength(source_payload),
        "source_class": source_payload.get("source_class"),
        "source_strength": source_payload.get("source_strength"),
        "accepted_evidence_count": source_payload.get("accepted_evidence_count"),
        "row_type": source_payload.get("row_type"),
    }
    anomaly_values = {
        "market_anomaly_id": anomaly.raw_id,
        "observed_at": anomaly.published_at or anomaly.fetched_at,
        "provider": anomaly.provider,
        "content_hash": anomaly.content_hash,
        **(
            dict(anomaly_payload.get("market"))
            if isinstance(anomaly_payload.get("market"), Mapping)
            else {}
        ),
    }
    return assess_mapping_attribution(anomaly_values, source_values)


def assess_mapping_attribution(
    anomaly: Mapping[str, Any],
    source: Mapping[str, Any],
) -> dict[str, Any]:
    """Assess already-normalized sidecar mappings without hidden I/O."""

    existing = source.get("catalyst_attribution")
    if isinstance(existing, Mapping) and not validate_contract(existing):
        return dict(existing)
    values = _attribution_inputs(anomaly, source)
    classification = _attribution_classification(source, values)
    reasons = [*values.pop("reason_codes"), *classification.pop("reason_codes")]
    row: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        **values,
        **classification,
        "reason_codes": sorted(set(reasons)),
        "research_only": True,
        "auto_apply": False,
    }
    row["attribution_digest"] = _digest(row)
    errors = validate_contract(row)
    if errors:  # pragma: no cover - construction and validation are co-tested.
        raise ValueError("catalyst attribution construction failed: " + ";".join(errors))
    return row


def _attribution_inputs(
    anomaly: Mapping[str, Any],
    source: Mapping[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    anomaly_id = _first_text(
        anomaly, "market_anomaly_id", "anomaly_id", "raw_id", "observation_id"
    )
    if not anomaly_id:
        anomaly_id = "derived:" + _digest(_identity_surface(anomaly))
        reasons.append("anomaly_identity_derived")
    anomaly_time = _first_time(
        anomaly, "observed_at", "market_context_observed_at", "published_at", "fetched_at"
    )
    if anomaly_time is None:
        anomaly_time = _first_time(
            _mapping(anomaly.get("market_state_snapshot")), "observed_at", "timestamp"
        )
    source_id = _first_text(
        source, "raw_id", "source_event_id", "official_exchange_event_id", "event_id", "candidate_id"
    )
    identity_kind = "declared"
    if not source_id:
        source_id = "derived:" + _digest(_identity_surface(source))
        identity_kind = "derived"
        reasons.append("source_identity_derived")
    content_hash = _first_text(source, "content_hash", "source_content_hash")
    if not content_hash:
        content_hash = _digest(_identity_surface(source))
        reasons.append("source_content_hash_derived")
    elif not _is_sha256(content_hash):
        content_hash = _digest({"declared_content_hash": content_hash})
        reasons.append("source_content_hash_normalized")
    official_event = _mapping(source.get("official_exchange_event"))
    published = _first_time(source, "published_at", "source_published_at")
    fetched = _first_time(source, "fetched_at", "source_fetched_at")
    published = published or _first_time(official_event, "published_at")
    fetched = fetched or _first_time(official_event, "fetched_at", "observed_at")
    public = published or fetched
    lag, relation = _temporal_relation(anomaly_time, public)
    if relation == "retrospective":
        reasons.append("source_published_after_anomaly")
    elif relation == "unknown":
        reasons.append("source_public_clock_missing")
    source_url, source_url_reason = _safe_source_url(
        _first_text(source, "source_url", "latest_source_url", "url")
    )
    if source_url_reason:
        reasons.append(source_url_reason)
    return {
        "anomaly_id": anomaly_id,
        "anomaly_observed_at": _iso(anomaly_time),
        "anomaly_binding_digest": _digest(
            _anomaly_binding_surface(anomaly, anomaly_id, anomaly_time)
        ),
        "source_id": source_id,
        "source_identity_kind": identity_kind,
        "source_provider": _first_text(
            source, "provider", "source_provider", "latest_source", "source_class"
        ) or "unknown",
        "source_url": source_url,
        "source_content_hash": content_hash,
        "source_published_at": _iso(published),
        "source_fetched_at": _iso(fetched),
        "source_public_at": _iso(public),
        "publication_lag_seconds": lag,
        "temporal_relation": relation,
        "event_time": _iso(_first_time(source, "event_time", "effective_time", "scheduled_at")),
        "event_time_source": _first_text(source, "event_time_source", "time_source") or None,
        "event_time_confidence": _finite_number(source.get("event_time_confidence")),
        "reason_codes": reasons,
    }


def _attribution_classification(
    source: Mapping[str, Any],
    values: Mapping[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    semantic_role, semantic_role_validated = _semantic_role_value(source)
    if not semantic_role_validated:
        reasons.append("semantic_role_unrecognized")
    candidate_role = _first_text(source, "candidate_role", "asset_role") or "unknown"
    impact_strength = _first_text(
        source, "impact_path_strength", "relationship_strength", "impact_strength"
    ) or "unknown"
    cause_status = _first_text(source, "cause_status", "incident_cause_status")
    disproof = semantic_role in _DISPROOF_ROLES or cause_status in {
        "ruled_out", "disproven", "denied"
    }
    context_only = semantic_role in _CONTEXT_ROLES or candidate_role in {
        "background_context", "historical_context", "market_reaction", "side_note"
    }
    if context_only:
        reasons.append("semantic_context_only")
    if disproof:
        reasons.append("source_disproof")
    registry_source = dict(source)
    registry_source.pop("source_url", None)
    registry_source.pop("url", None)
    registry_source.pop("latest_source_url", None)
    if values.get("source_url"):
        registry_source["source_url"] = values["source_url"]
    assessment = source_registry.assess_source(registry_source)
    authority_verified = (
        "source_authority_unverified" not in assessment.reason_codes
        and assessment.source_class != source_registry.SourceClass.SOCIAL_OR_UNKNOWN.value
    )
    can_validate_catalyst = bool(
        assessment.can_validate_catalyst and authority_verified
    )
    can_validate_impact_path = bool(
        assessment.can_validate_impact_path and authority_verified
    )
    direct_official = bool(
        semantic_role in {catalyst_frames.ROLE_MAIN, catalyst_frames.ROLE_UNKNOWN}
        and semantic_role_validated
        and assessment.source_class in _OFFICIAL_SOURCE_CLASSES
        and can_validate_catalyst
    )
    validated_beneficiary = bool(
        candidate_role in _DIRECT_CANDIDATE_ROLES
        and impact_strength.casefold() in _STRONG_IMPACT_VALUES
        and can_validate_catalyst
        and can_validate_impact_path
        and semantic_role_validated
    )
    causal_semantics = direct_official or validated_beneficiary
    causal_basis = (
        "direct_official"
        if direct_official
        else "validated_direct_beneficiary"
        if validated_beneficiary
        else "none"
    )
    timing_eligible = values.get("temporal_relation") in {"antecedent", "contemporaneous"}
    eligible = bool(timing_eligible and not disproof and not context_only and causal_semantics)
    if eligible:
        reasons.append("causal_source_precedes_or_matches_anomaly")
    elif not disproof and not context_only and not timing_eligible:
        reasons.append("causal_timing_ineligible")
    elif not disproof and not context_only and not causal_semantics:
        reasons.append("causal_semantics_unproven")
    event_time = _parse_time(values.get("event_time"))
    anomaly_time = _parse_time(values.get("anomaly_observed_at"))
    if disproof:
        evidence_use = "disproof"
    elif values.get("temporal_relation") == "retrospective":
        evidence_use = "retrospective_context"
    elif context_only:
        evidence_use = "background_context"
    elif eligible and event_time is not None and anomaly_time is not None and event_time > anomaly_time:
        evidence_use = "scheduled_anticipation"
    elif eligible:
        evidence_use = "causal_candidate"
    else:
        evidence_use = "unknown"
    return {
        "source_class": assessment.source_class,
        "source_authority_verified": authority_verified,
        "source_can_validate_catalyst": can_validate_catalyst,
        "source_can_validate_impact_path": can_validate_impact_path,
        "source_registry_reason_codes": sorted(set(assessment.reason_codes)),
        "semantic_role": semantic_role,
        "semantic_role_validated": semantic_role_validated,
        "candidate_role": candidate_role,
        "impact_path_strength": impact_strength,
        "cause_status": cause_status or None,
        "causal_basis": causal_basis,
        "evidence_use": evidence_use,
        "causal_eligible": eligible,
        "reason_codes": reasons,
    }


def validate_contract(value: Mapping[str, Any]) -> list[str]:
    """Validate exact keys, digest, clocks, enums, and causal implications."""

    if not isinstance(value, Mapping):
        return ["not_mapping"]
    errors: list[str] = []
    if set(value) != _KEYS:
        errors.append("fields_not_closed")
    if value.get("schema_id") != SCHEMA_ID:
        errors.append("schema_id_invalid")
    if (
        type(value.get("schema_version")) is not int
        or value.get("schema_version") != SCHEMA_VERSION
    ):
        errors.append("schema_version_invalid")
    for field in (
        "anomaly_id",
        "anomaly_binding_digest",
        "source_id",
        "source_identity_kind",
        "source_provider",
        "source_class",
        "source_content_hash",
        "temporal_relation",
        "semantic_role",
        "candidate_role",
        "impact_path_strength",
        "causal_basis",
        "evidence_use",
    ):
        if not _exact_text(value.get(field)):
            errors.append(f"{field}_invalid")
    if not _is_sha256(value.get("anomaly_binding_digest")):
        errors.append("anomaly_binding_digest_invalid")
    if not _is_sha256(value.get("source_content_hash")):
        errors.append("source_content_hash_invalid")
    for field in ("source_url", "event_time_source", "cause_status"):
        if value.get(field) is not None and not _exact_text(value.get(field)):
            errors.append(f"{field}_invalid")
    if value.get("source_url") is not None and _safe_source_url(
        str(value.get("source_url"))
    ) != (value.get("source_url"), None):
        errors.append("source_url_unsafe")
    for field in (
        "anomaly_observed_at",
        "source_published_at",
        "source_fetched_at",
        "source_public_at",
        "event_time",
    ):
        if value.get(field) is not None and _parse_time(value.get(field)) is None:
            errors.append(f"{field}_invalid")
    lag = value.get("publication_lag_seconds")
    if lag is not None and (
        type(lag) not in {int, float} or not math.isfinite(float(lag))
    ):
        errors.append("publication_lag_seconds_invalid")
    confidence = value.get("event_time_confidence")
    if confidence is not None and (
        type(confidence) not in {int, float}
        or not math.isfinite(float(confidence))
        or not 0 <= float(confidence) <= 1
    ):
        errors.append("event_time_confidence_invalid")
    if (
        type(value.get("temporal_relation")) is not str
        or value.get("temporal_relation") not in TEMPORAL_RELATIONS
    ):
        errors.append("temporal_relation_invalid")
    if (
        type(value.get("evidence_use")) is not str
        or value.get("evidence_use") not in EVIDENCE_USES
    ):
        errors.append("evidence_use_invalid")
    if (
        type(value.get("causal_basis")) is not str
        or value.get("causal_basis") not in CAUSAL_BASES
    ):
        errors.append("causal_basis_invalid")
    if (
        type(value.get("source_identity_kind")) is not str
        or value.get("source_identity_kind") not in {"declared", "derived"}
    ):
        errors.append("source_identity_kind_invalid")
    if (
        type(value.get("source_class")) is not str
        or value.get("source_class")
        not in {item.value for item in source_registry.SourceClass}
    ):
        errors.append("source_class_invalid")
    if (
        type(value.get("semantic_role")) is not str
        or value.get("semantic_role") not in SEMANTIC_ROLES
    ):
        errors.append("semantic_role_invalid")
    for field in (
        "causal_eligible", "source_authority_verified", "source_can_validate_catalyst",
        "source_can_validate_impact_path", "semantic_role_validated",
    ):
        if type(value.get(field)) is not bool:
            errors.append(f"{field}_invalid")
    if value.get("research_only") is not True or value.get("auto_apply") is not False:
        errors.append("safety_contract_invalid")
    reasons = value.get("reason_codes")
    if (
        type(reasons) is not list
        or not all(_exact_text(reason) for reason in reasons)
        or reasons != sorted(set(reasons))
    ):
        errors.append("reason_codes_invalid")
    registry_reasons = value.get("source_registry_reason_codes")
    if (
        type(registry_reasons) is not list
        or not all(_exact_text(reason) for reason in registry_reasons)
        or registry_reasons != sorted(set(registry_reasons))
    ):
        errors.append("source_registry_reason_codes_invalid")
    expected_lag, expected_relation = _temporal_relation(
        _parse_time(value.get("anomaly_observed_at")),
        _parse_time(value.get("source_public_at")),
    )
    if lag != expected_lag:
        errors.append("publication_lag_mismatch")
    if value.get("temporal_relation") != expected_relation:
        errors.append("temporal_relation_mismatch")
    if value.get("causal_eligible") is True and (
        expected_relation not in {"antecedent", "contemporaneous"}
        or str(value.get("evidence_use") or "")
        not in {"causal_candidate", "scheduled_anticipation"}
    ):
        errors.append("causal_eligibility_inconsistent")
    if value.get("evidence_use") == "retrospective_context" and expected_relation != "retrospective":
        errors.append("retrospective_use_inconsistent")
    errors.extend(_contract_clock_consistency_errors(value))
    errors.extend(_contract_semantic_consistency_errors(value))
    digest_payload = dict(value)
    digest_payload.pop("attribution_digest", None)
    if value.get("attribution_digest") != _digest(digest_payload):
        errors.append("attribution_digest_invalid")
    return sorted(set(errors))


def _contract_clock_consistency_errors(value: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    parsed = {
        field: _parse_time(value.get(field))
        for field in (
            "anomaly_observed_at", "source_published_at", "source_fetched_at",
            "source_public_at", "event_time",
        )
    }
    for field, timestamp in parsed.items():
        if timestamp is not None and value.get(field) != _iso(timestamp):
            errors.append(f"{field}_noncanonical")
    expected_public = parsed["source_published_at"] or parsed["source_fetched_at"]
    if parsed["source_public_at"] != expected_public:
        errors.append("source_public_clock_mismatch")
    event_time = parsed["event_time"]
    anomaly_time = parsed["anomaly_observed_at"]
    scheduled = value.get("evidence_use") == "scheduled_anticipation"
    if scheduled and (
        event_time is None or anomaly_time is None or event_time <= anomaly_time
    ):
        errors.append("scheduled_anticipation_time_inconsistent")
    if (
        value.get("causal_eligible") is True
        and event_time is not None
        and anomaly_time is not None
        and event_time > anomaly_time
        and not scheduled
    ):
        errors.append("future_event_requires_scheduled_anticipation")
    return errors


def _contract_semantic_consistency_errors(value: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    semantic_role = str(value.get("semantic_role") or "")
    candidate_role = str(value.get("candidate_role") or "")
    impact_strength = str(value.get("impact_path_strength") or "").casefold()
    source_class = (
        value.get("source_class") if type(value.get("source_class")) is str else ""
    )
    cause_status = str(value.get("cause_status") or "").casefold()
    registry_reasons = value.get("source_registry_reason_codes")
    registry_reasons = registry_reasons if isinstance(registry_reasons, list) else []
    authority_verified = value.get("source_authority_verified") is True
    can_validate = value.get("source_can_validate_catalyst") is True
    can_validate_impact = value.get("source_can_validate_impact_path") is True
    role_validated = value.get("semantic_role_validated") is True
    temporal_relation = (
        value.get("temporal_relation")
        if type(value.get("temporal_relation")) is str
        else ""
    )
    if "source_authority_unverified" in registry_reasons and authority_verified:
        errors.append("source_authority_verification_inconsistent")
    if (
        source_class == source_registry.SourceClass.SOCIAL_OR_UNKNOWN.value
        and authority_verified
    ):
        errors.append("source_authority_verification_inconsistent")
    direct_official = bool(
        authority_verified
        and can_validate
        and source_class in _OFFICIAL_SOURCE_CLASSES
        and semantic_role in {catalyst_frames.ROLE_MAIN, catalyst_frames.ROLE_UNKNOWN}
        and role_validated
    )
    beneficiary = bool(
        authority_verified
        and can_validate
        and candidate_role in _DIRECT_CANDIDATE_ROLES
        and impact_strength in _STRONG_IMPACT_VALUES
        and can_validate_impact
        and role_validated
    )
    expected_basis = (
        "direct_official" if direct_official
        else "validated_direct_beneficiary" if beneficiary
        else "none"
    )
    if value.get("causal_basis") != expected_basis:
        errors.append("causal_basis_inconsistent")
    if expected_basis == "direct_official":
        identity_assessment = source_registry.assess_source(
            provider=str(value.get("source_provider") or ""),
            source_url=str(value.get("source_url") or ""),
        )
        if (
            identity_assessment.source_class != source_class
            or not identity_assessment.can_validate_catalyst
            or "source_authority_unverified" in identity_assessment.reason_codes
        ):
            errors.append("source_registry_identity_inconsistent")
    context_only = semantic_role in _CONTEXT_ROLES or candidate_role in {
        "background_context", "historical_context", "market_reaction", "side_note"
    }
    disproof = semantic_role in _DISPROOF_ROLES or cause_status in {
        "ruled_out", "disproven", "denied"
    }
    expected_eligible = bool(
        temporal_relation in {"antecedent", "contemporaneous"}
        and expected_basis != "none"
        and not context_only
        and not disproof
    )
    if value.get("causal_eligible") is not expected_eligible:
        errors.append("causal_semantics_inconsistent")
    event_time = _parse_time(value.get("event_time"))
    anomaly_time = _parse_time(value.get("anomaly_observed_at"))
    if disproof:
        expected_use = "disproof"
    elif temporal_relation == "retrospective":
        expected_use = "retrospective_context"
    elif context_only:
        expected_use = "background_context"
    elif (
        expected_eligible
        and event_time is not None
        and anomaly_time is not None
        and event_time > anomaly_time
    ):
        expected_use = "scheduled_anticipation"
    elif expected_eligible:
        expected_use = "causal_candidate"
    else:
        expected_use = "unknown"
    evidence_use = (
        value.get("evidence_use") if type(value.get("evidence_use")) is str else ""
    )
    if evidence_use != expected_use:
        errors.append("evidence_use_inconsistent")
    return errors


def validate_source_binding(
    value: Mapping[str, Any],
    anomaly: RawDiscoveredEvent,
    source: RawDiscoveredEvent,
) -> list[str]:
    errors = validate_contract(value)
    if not errors and dict(value) != assess_catalyst_attribution(anomaly, source):
        errors.append("source_binding_mismatch")
    return sorted(set(errors))


def validate_mapping_binding(
    value: Mapping[str, Any],
    anomaly: Mapping[str, Any],
    source: Mapping[str, Any],
) -> list[str]:
    """Recompute one normalized source/anomaly pair and reject binding drift."""

    errors = validate_contract(value)
    if errors:
        return errors
    clean_source = dict(source)
    clean_source.pop("catalyst_attribution", None)
    clean_source.pop("catalyst_attributions", None)
    if dict(value) != assess_mapping_attribution(anomaly, clean_source):
        errors.append("mapping_binding_mismatch")
    return sorted(set(errors))


def _source_frame(source: RawDiscoveredEvent) -> Mapping[str, Any]:
    validation = catalyst_frame_binding.current_validation_for_raw(source)
    if isinstance(validation, Mapping):
        selected = validation.get("selected_main_frame")
        if isinstance(selected, Mapping):
            return selected
    frames = catalyst_frames.build_catalyst_frames((source,))
    selected, _supporting = catalyst_frames.select_main_catalyst_frame(frames)
    if selected is None:
        return {}
    return {
        "frame_role": selected.frame_role,
        "cause_status": selected.cause_status,
    }


def _semantic_role_value(source: Mapping[str, Any]) -> tuple[str, bool]:
    role = _first_text(source, "main_frame_role", "frame_role", "semantic_role")
    if role:
        normalized = role.casefold()
        return (
            (normalized, True)
            if normalized in SEMANTIC_ROLES
            else (catalyst_frames.ROLE_UNKNOWN, False)
        )
    row_type = _first_text(source, "row_type").casefold()
    if row_type.startswith("official_") or row_type in {
        "scheduled_catalyst",
        "unlock_event",
    }:
        return catalyst_frames.ROLE_MAIN, True
    return catalyst_frames.ROLE_UNKNOWN, True


def _raw_candidate_role(payload: Mapping[str, Any]) -> Any:
    event = _mapping(payload.get("event"))
    return payload.get("candidate_role") or event.get("candidate_role")


def _raw_impact_strength(payload: Mapping[str, Any]) -> Any:
    event = _mapping(payload.get("event"))
    return payload.get("impact_path_strength") or event.get("impact_path_strength")


def _temporal_relation(
    anomaly_time: datetime | None,
    source_time: datetime | None,
) -> tuple[float | None, str]:
    if anomaly_time is None or source_time is None:
        return None, "unknown"
    lag = (source_time - anomaly_time).total_seconds()
    if lag > CONTEMPORANEOUS_TOLERANCE_SECONDS:
        return lag, "retrospective"
    if lag < -CONTEMPORANEOUS_TOLERANCE_SECONDS:
        return lag, "antecedent"
    return lag, "contemporaneous"


def _identity_surface(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "raw_id",
            "provider",
            "source_provider",
            "source_url",
            "url",
            "title",
            "published_at",
            "fetched_at",
            "event_id",
            "candidate_id",
            "market_anomaly_id",
            "observed_at",
        )
        if row.get(key) not in (None, "")
    }


def _anomaly_binding_surface(
    row: Mapping[str, Any],
    anomaly_id: str,
    observed_at: datetime | None,
) -> dict[str, Any]:
    return {
        "anomaly_id": anomaly_id,
        "observed_at": _iso(observed_at),
        "provider": _first_text(row, "provider", "source_provider", "_source_origin"),
        "content_hash": _first_text(row, "content_hash", "anomaly_content_hash"),
        "canonical_asset_id": _first_text(row, "canonical_asset_id"),
        "coin_id": _first_text(row, "coin_id", "validated_coin_id"),
        "symbol": _first_text(row, "symbol", "validated_symbol").upper(),
        "market_snapshot_id": _first_text(row, "market_snapshot_id"),
        "market_state_class": _first_text(row, "market_state_class", "market_state"),
        "market_anomaly_bucket": _first_text(
            row, "market_anomaly_bucket", "anomaly_bucket"
        ),
        "market_state_snapshot": row.get("market_state_snapshot")
        if isinstance(row.get("market_state_snapshot"), Mapping)
        else None,
    }


def _safe_source_url(value: str) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    parsed = urlsplit(value)
    if (
        parsed.scheme.casefold() not in {"http", "https"}
        or not parsed.netloc
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None, "source_url_credential_or_scheme_rejected"
    path_parts = [part.casefold().replace("-", "_") for part in parsed.path.split("/")]
    secret_path_names = {
        "api_key", "apikey", "key", "token", "auth", "authorization",
        "credential", "credentials", "secret", "password", "signature",
    }
    if any(
        part in secret_path_names and index + 1 < len(path_parts) and path_parts[index + 1]
        for index, part in enumerate(path_parts)
    ) or any(
        marker in parsed.path.casefold()
        for marker in ("api_key=", "apikey=", "token=", "auth=", "credential=", "secret=", "password=")
    ):
        return None, "source_url_credential_path_rejected"
    safe = urlunsplit(
        (
            parsed.scheme.casefold(),
            parsed.netloc,
            parsed.path,
            "",
            "",
        )
    )
    return safe, "source_url_query_removed" if parsed.query or parsed.fragment else None


def _first_text(row: Mapping[str, Any], *fields: str) -> str:
    for field in fields:
        value = row.get(field)
        if value not in (None, ""):
            text = str(value).strip()
            if text:
                return text
    return ""


def _first_time(row: Mapping[str, Any], *fields: str) -> datetime | None:
    for field in fields:
        parsed = _parse_time(row.get(field))
        if parsed is not None:
            return parsed
    return None


def _parse_time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat() if value is not None else None


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _exact_text(value: object) -> bool:
    return type(value) is str and bool(value) and value == value.strip()


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return _iso(value) or ""
    return str(value)


__all__ = (
    "CONTEMPORANEOUS_TOLERANCE_SECONDS",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "assess_catalyst_attribution",
    "assess_mapping_attribution",
    "validate_contract",
    "validate_mapping_binding",
    "validate_source_binding",
)
