"""Read-only helpers for presenting Crypto Radar Decision Model v2 fields.

The scoring model owns these values.  This module only projects already-
persisted fields into operator surfaces and deliberately returns no defaults
for legacy rows, so older artifacts cannot be silently promoted.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any
from urllib.parse import quote

import crypto_rsi_scanner.event_alpha.operations.market_provenance as event_market_provenance

from ..artifacts.schema.decision_model import (
    DECISION_PROJECTION_SCHEMA_VERSION,
    validate_contract,
)
from .decision_models import actionability_score_cohort


DECISION_MODEL_FIELD_NAMES = (
    "research_only",
    "decision_model_version",
    "decision_model_enabled",
    "thesis_origin",
    "primary_thesis_origin",
    "thesis_origins",
    "directional_bias",
    "catalyst_status",
    "confidence_band",
    "timing_state",
    "tradability_status",
    "spread_status",
    "radar_route",
    "radar_route_reason",
    "radar_actionable",
    "actionability_score",
    "evidence_confidence_score",
    "risk_score",
    "urgency_score",
    "market_phase",
    "preferred_horizon",
    "expires_at",
    "chase_risk_score",
    "actionability_score_components",
    "actionability_penalty_components",
    "evidence_confidence_components",
    "evidence_confidence_score_components",
    "risk_score_components",
    "decision_hard_blockers",
    "decision_soft_penalties",
    "decision_warnings",
    "decision_missing_data",
    "why_still_worth_reviewing",
    "radar_what_confirms",
    "radar_what_invalidates",
    "actionability_score_cohort",
    "anomaly_type",
    "decision_source_side_effect_safety_failed",
    "decision_source_secret_safety_failed",
    "decision_source_path_safety_failed",
)

# These fields make the projection self-validating and self-rendering.  They
# intentionally live outside ``DECISION_MODEL_FIELD_NAMES`` because several
# names (for example ``warnings`` and ``what_confirms``) also exist in the
# legacy Catalyst Radar schema.  Downstream code should copy the canonical
# projection as a unit instead of treating those aliases as legacy fields.
DECISION_PROJECTION_FIELD_NAMES = (
    *DECISION_MODEL_FIELD_NAMES,
    "decision_projection_schema_version",
    "hard_blockers",
    "soft_penalties",
    "warnings",
    "why_now",
    "supporting_facts",
    "missing_information",
    "main_risks",
    "what_confirms",
    "what_invalidates",
    "calendar_evidence",
    "calendar_evidence_ids",
    "rsi_context",
    "rsi_context_references",
    "observation_ids",
    "source_provider_lineage",
    "market_provenance",
    "market_context_reference",
    "decision_evaluated_at",
    "decision_safety_invariants",
)

PREVIEW_LANE_TITLES = {
    "high_confidence": "High-Confidence Ideas",
    "actionable": "Actionable Ideas",
    "rapid_market_anomaly": "Rapid Market Anomalies",
    "dashboard_watch": "Dashboard Watch",
    "fade_exhaustion_review": "Fade / Exhaustion Review",
    "risk_watch": "Risk Watch",
    "calendar_risk": "Calendar / Scheduled Risk",
    "decision_diagnostic": "Decision Diagnostics",
}

PREVIEW_LANE_ORDER = tuple(PREVIEW_LANE_TITLES)


def decision_model_values(*rows: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return one complete, explicit v2 authority without cross-row merging.

    Argument order is authority order.  A malformed explicit v2 payload fails
    closed instead of borrowing fields from a later row or an unversioned
    mapping.  Explicit empty lists/maps are meaningful canonical values and
    must survive projection into outcomes and other persisted surfaces.
    """

    for row in rows:
        if not isinstance(row, Mapping):
            continue
        nested = row.get("decision_projection")
        authorities: list[Mapping[str, Any]] = []
        if isinstance(nested, Mapping) and nested:
            if not _nested_projection_matches_row(nested, row):
                return {}
            authorities.append(nested)
        authorities.append(row)
        authorities.extend(
            components
            for components_key in ("score_components", "latest_score_components")
            if isinstance((components := row.get(components_key)), Mapping)
        )
        for authority in authorities:
            if not _has_decision_model_marker(authority):
                continue
            if not decision_model_is_enabled(authority):
                return {}
            if (
                "decision_projection_schema_version" in authority
                and validate_contract(authority)
            ):
                return {}
            projection = _project_fields(authority)
            _normalize_projection_collections(projection)
            if not projection.get("actionability_score_cohort"):
                cohort = actionability_score_cohort(projection.get("actionability_score"))
                if cohort:
                    projection["actionability_score_cohort"] = cohort
            closed_values = _closed_projection_values(authority, projection)
            # Historical v2 artifacts predate explicit observation/evaluation
            # identity.  Keep their former readable projection without
            # pretending that missing provenance can be reconstructed.  Every
            # current candidate/core/outcome row has both and receives the
            # closed, schema-marked projection below.
            closed_projection = bool(
                closed_values.get("observation_ids")
                and closed_values.get("decision_evaluated_at")
            )
            if closed_projection:
                projection.update(closed_values)
            contract_payload = dict(authority)
            contract_payload.update(projection)
            if validate_contract(contract_payload):
                return {}
            # Raw validation protects upstream fields such as declared return
            # units.  This second validation is the closed-value guarantee:
            # no consumer may need fields that projection removed.
            if closed_projection and validate_contract(projection):
                return {}
            return projection
    return {}


def _nested_projection_matches_row(
    projection: Mapping[str, Any],
    row: Mapping[str, Any],
) -> bool:
    """Fail closed when a stored projection drifts from its top-level mirror."""

    if projection.get("decision_projection_schema_version") != DECISION_PROJECTION_SCHEMA_VERSION:
        return False
    if validate_contract(projection):
        return False
    if _has_decision_model_marker(row) and not decision_model_is_enabled(row):
        return False
    for field in DECISION_MODEL_FIELD_NAMES:
        if field not in row or row.get(field) in (None, ""):
            continue
        left = deepcopy(projection.get(field))
        right = deepcopy(row.get(field))
        if field in {
            "thesis_origins", "decision_hard_blockers", "decision_soft_penalties",
            "decision_warnings", "decision_missing_data", "why_still_worth_reviewing",
            "radar_what_confirms", "radar_what_invalidates",
        }:
            left = _items(left)
            right = _items(right)
        if left != right:
            return False
    market_reference = row.get("market_context_reference")
    if isinstance(market_reference, Mapping) and market_reference:
        if dict(projection.get("market_context_reference") or {}) != dict(market_reference):
            return False
        aliases = {
            "source": ("market_context_source", "market_data_source"),
            "observed_at": ("market_context_observed_at",),
            "freshness_status": (
                "market_context_freshness_status",
                "market_data_freshness",
            ),
            "market_snapshot_id": ("market_snapshot_id",),
        }
        for reference_field, row_fields in aliases.items():
            expected = market_reference.get(reference_field)
            for row_field in row_fields:
                observed = row.get(row_field)
                if observed not in (None, "") and observed != expected:
                    return False
    return True


def decision_model_is_enabled(values: Mapping[str, Any]) -> bool:
    version = str(values.get("decision_model_version") or "").strip()
    enabled = values.get("decision_model_enabled")
    return version == "crypto_radar_decision_model_v2" and enabled is True


def decision_preview_lane(values: Mapping[str, Any]) -> str:
    """Map a v2 route to one operator preview lane without changing routing."""

    projected = decision_model_values(values)
    if not projected:
        return "decision_diagnostic"
    route = str(projected.get("radar_route") or "diagnostic").strip().casefold()
    if route == "high_confidence_watch":
        return "high_confidence"
    if route == "actionable_watch":
        return "actionable"
    if route == "rapid_market_anomaly":
        return "rapid_market_anomaly"
    if route == "dashboard_watch":
        return "dashboard_watch"
    if route == "fade_exhaustion_review":
        return "fade_exhaustion_review"
    if route == "risk_watch":
        return "risk_watch"
    if route == "calendar_risk":
        return "calendar_risk"
    return "decision_diagnostic"


def group_decision_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    include_diagnostics: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    groups = {lane: [] for lane in PREVIEW_LANE_ORDER}
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        values = decision_model_values(row)
        if not values:
            if include_diagnostics and _row_has_decision_model_marker(row):
                groups["decision_diagnostic"].append(row)
            continue
        lane = decision_preview_lane(values)
        if lane == "decision_diagnostic" and not include_diagnostics:
            continue
        groups[lane].append(row)
    for lane_rows in groups.values():
        lane_rows.sort(key=_decision_row_rank, reverse=True)
    return groups


def decision_model_markdown_lines(values: Mapping[str, Any]) -> list[str]:
    """Render transparent, non-prescriptive v2 decision details."""

    raw_values = values
    projected = decision_model_values(values)
    if not projected:
        return []
    values = projected
    lines = [
        f"- Decision model: {values.get('decision_model_version')}",
        f"- Radar route: {values.get('radar_route') or 'diagnostic'}",
        f"- Radar actionable: {str(bool(values.get('radar_actionable'))).lower()}",
        (
            "- Primary / contributing origins: "
            f"{values.get('primary_thesis_origin') or values.get('thesis_origin') or 'unknown'} / "
            f"{', '.join(_items(values.get('thesis_origins'))) or values.get('thesis_origin') or 'unknown'}"
        ),
        f"- Directional bias: {values.get('directional_bias') or 'neutral'}",
        f"- Catalyst status: {values.get('catalyst_status') or 'unknown'}",
        (
            "- Confidence / phase / timing: "
            f"{values.get('confidence_band') or 'diagnostic'} / "
            f"{values.get('market_phase') or 'unknown'} / {values.get('timing_state') or 'stale'}"
        ),
        (
            "- Tradability / spread: "
            f"{values.get('tradability_status') or 'blocked'} / {values.get('spread_status') or 'unavailable'}"
        ),
        (
            "- Actionability / evidence confidence / risk: "
            f"{_score(values.get('actionability_score'))} / "
            f"{_score(values.get('evidence_confidence_score'))} / "
            f"{_score(values.get('risk_score'))}"
        ),
        (
            "- Urgency / chase risk: "
            f"{_score(values.get('urgency_score'))} / {_score(values.get('chase_risk_score'))}"
        ),
        (
            "- Preferred horizon / expiry: "
            f"{values.get('preferred_horizon') or 'unknown'} / {values.get('expires_at') or 'not set'}"
        ),
    ]
    reason = str(values.get("radar_route_reason") or "").strip()
    if reason:
        lines.append(f"- Route reason: {reason}")
    why_now = str(values.get("why_now") or "").strip()
    if why_now:
        lines.append(f"- Why now: {why_now}")
    why = _items(values.get("why_still_worth_reviewing"))
    if why:
        lines.append(f"- Why this is still worth human review: {'; '.join(why[:6])}")
    for label, field in (
        ("Hard blockers", "decision_hard_blockers"),
        ("Soft penalties", "decision_soft_penalties"),
        ("Missing data", "decision_missing_data"),
        ("Decision warnings", "decision_warnings"),
        ("What confirms", "radar_what_confirms"),
        ("What invalidates", "radar_what_invalidates"),
    ):
        items = _items(values.get(field))
        lines.append(f"- {label}: {'; '.join(items[:6]) if items else 'none'}")
    for label, field in (
        ("Actionability components", "actionability_score_components"),
        ("Actionability penalties", "actionability_penalty_components"),
        ("Evidence-confidence components", "evidence_confidence_components"),
        ("Evidence-confidence components", "evidence_confidence_score_components"),
        ("Risk components", "risk_score_components"),
    ):
        components = values.get(field)
        if isinstance(components, Mapping) and components:
            rendered = "; ".join(f"{key}={value}" for key, value in sorted(components.items()))
            lines.append(f"- {label}: {rendered}")
    if str(values.get("catalyst_status") or "").casefold() == "unknown":
        lines.append("- Catalyst unknown: this lowers evidence confidence but is not, by itself, a hard blocker for a market-led idea.")
    if any("manip" in item.casefold() or "illiquid" in item.casefold() for item in _items(values.get("decision_warnings"))):
        lines.append("- Higher manipulation risk: review liquidity, spread, turnover, and venue concentration manually.")
    dashboard_id = next(
        (
            str(raw_values.get(field) or "").strip()
            for field in ("core_opportunity_id", "candidate_id", "integrated_candidate_id")
            if str(raw_values.get(field) or "").strip()
        ),
        "",
    )
    if dashboard_id:
        lines.append(f"- Dashboard: /candidate/{quote(dashboard_id, safe='')}")
    provenance = event_market_provenance.market_provenance_values(values)
    if provenance:
        lines.extend(_market_provenance_markdown_lines(provenance))
    market_reference = values.get("market_context_reference")
    if isinstance(market_reference, Mapping) and market_reference:
        lines.append(
            "- Market context reference: "
            f"source={market_reference.get('source') or 'unknown'}; "
            f"observed_at={market_reference.get('observed_at') or 'unknown'}; "
            f"freshness={market_reference.get('freshness_status') or 'unknown'}; "
            f"snapshot_id={market_reference.get('market_snapshot_id') or 'unknown'}"
        )
    lines.append("- Research idea, not a trade instruction.")
    return lines


def _project_fields(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: deepcopy(source[field])
        for field in DECISION_MODEL_FIELD_NAMES
        if field in source and source.get(field) is not None and source.get(field) != ""
    }


def _normalize_projection_collections(projection: dict[str, Any]) -> None:
    """Keep the canonical value JSON-shaped regardless of in-memory tuples."""

    for field in (
        "thesis_origins", "decision_hard_blockers", "decision_soft_penalties",
        "decision_warnings", "decision_missing_data", "why_still_worth_reviewing",
        "radar_what_confirms", "radar_what_invalidates",
    ):
        if field in projection:
            projection[field] = _items(projection.get(field))


def _closed_projection_values(
    source: Mapping[str, Any],
    projection: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the deterministic, context-complete Decision v2 value."""

    blockers = _items(projection.get("decision_hard_blockers"))
    penalties = _items(projection.get("decision_soft_penalties"))
    warnings = _items(projection.get("decision_warnings"))
    missing = _items(projection.get("decision_missing_data"))
    confirms = _items(projection.get("radar_what_confirms"))
    invalidates = _items(projection.get("radar_what_invalidates"))
    why_review = _items(projection.get("why_still_worth_reviewing"))

    # Decision Radar owns the primary trader-facing rationale.  The raw
    # ``why_now`` field belongs to the legacy Catalyst Radar classification and
    # may describe why a candidate is STORE_ONLY even when Decision v2 has a
    # valid market-led thesis.  Prefer the model's explicit review rationale so
    # the closed projection cannot inherit that semantic contradiction.
    why_now = why_review[0] if why_review else ""
    if not why_now:
        why_now = str(source.get("why_now") or "").strip()
    supporting_facts = _items(source.get("supporting_facts"))
    if not supporting_facts:
        supporting_facts = list(dict.fromkeys((*why_review, *_items(source.get("supporting_evidence_quotes")))))
    main_risks = _items(source.get("main_risks"))
    if not main_risks:
        main_risks = list(dict.fromkeys((*warnings, *penalties)))

    calendar_evidence = _calendar_evidence(source)
    rsi_context = (
        deepcopy(source.get("rsi_context"))
        if isinstance(source.get("rsi_context"), Mapping)
        else {}
    )
    rsi_references = _rsi_context_references(source, rsi_context)
    closed = {
        "decision_projection_schema_version": DECISION_PROJECTION_SCHEMA_VERSION,
        "hard_blockers": blockers,
        "soft_penalties": penalties,
        "warnings": warnings,
        "why_now": why_now,
        "supporting_facts": supporting_facts,
        "missing_information": missing,
        "main_risks": main_risks,
        "what_confirms": confirms,
        "what_invalidates": invalidates,
        "calendar_evidence": calendar_evidence,
        "calendar_evidence_ids": [
            str(row.get("calendar_event_id"))
            for row in calendar_evidence
            if str(row.get("calendar_event_id") or "").strip()
        ],
        "rsi_context": rsi_context,
        "rsi_context_references": rsi_references,
        "observation_ids": _observation_ids(source),
        "source_provider_lineage": _source_provider_lineage(source),
        "market_context_reference": market_context_reference(source),
        "decision_evaluated_at": _evaluation_timestamp(source),
        "decision_safety_invariants": _safety_invariants(source),
    }
    provenance = event_market_provenance.market_provenance_values(source)
    if provenance:
        closed["market_provenance"] = provenance
        closed.update(event_market_provenance.market_provenance_flat_fields(provenance))
    return closed


def _calendar_evidence(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    canonical = source.get("calendar_evidence")
    canonical_rows = _mapping_rows(canonical)
    from_canonical_projection = bool(canonical_rows)
    if canonical_rows:
        rows.extend(canonical_rows)
    else:
        for field in ("unified_calendar_context", "nearby_calendar_events", "calendar_events"):
            rows.extend(_mapping_rows(source.get(field)))
        if not rows:
            for field in (
                "unified_calendar_event", "calendar_event", "scheduled_catalyst_event", "unlock_event",
            ):
                value = source.get(field)
                if isinstance(value, Mapping) and value:
                    rows.append(value)
        if not rows and source.get("scheduled_at") not in (None, ""):
            rows.append(
                {
                    "calendar_event_id": "",
                    "evidence_reference": _candidate_schedule_reference(source),
                    "event_kind": source.get("event_kind") or source.get("event_type") or "scheduled",
                    "scheduled_at": source.get("scheduled_at"),
                    "time_certainty": source.get("time_certainty") or "exact",
                    "importance": source.get("importance") or "unknown",
                }
            )

    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for raw in rows:
        event_kind = str(
            raw.get("event_kind") or raw.get("category") or raw.get("event_type") or "unknown"
        ).strip().casefold()
        scheduled_at = raw.get("scheduled_at") or raw.get("event_start_time") or raw.get("effective_time")
        window_start = raw.get("window_start")
        window_end = raw.get("window_end")
        if all(value in (None, "") for value in (scheduled_at, window_start, window_end)):
            continue
        certainty = str(raw.get("time_certainty") or "").strip().casefold()
        if not certainty:
            certainty = "window" if window_start not in (None, "") and window_end not in (None, "") else (
                "exact" if scheduled_at not in (None, "") else "unknown"
            )
        event_id = str(raw.get("calendar_event_id") or raw.get("event_id") or "").strip()
        reference = raw.get("evidence_reference")
        if not event_id and not reference and not from_canonical_projection:
            reference = _candidate_schedule_reference(source)
        key = (event_id, str(reference or ""), str(scheduled_at or window_start or ""), event_kind)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "calendar_event_id": event_id,
                "evidence_reference": deepcopy(reference),
                "category": event_kind,
                "event_kind": event_kind,
                "scheduled_at": scheduled_at,
                "window_start": window_start,
                "window_end": window_end,
                "time_certainty": certainty,
                "importance": str(raw.get("importance") or "unknown").strip().casefold(),
                "source": str(raw.get("source") or raw.get("provider") or "calendar").strip(),
                "source_url": str(raw.get("source_url") or "").strip(),
            }
        )
    return normalized


def _rsi_context_references(
    source: Mapping[str, Any],
    context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    existing = _mapping_rows(source.get("rsi_context_references"))
    if existing:
        return [deepcopy(dict(row)) for row in existing]
    if not context:
        return []
    return [{
        "context_version": str(
            source.get("rsi_context_version") or context.get("context_version") or ""
        ).strip(),
        "symbol": context.get("symbol"),
        "coin_id": context.get("coin_id"),
        "setup_type": context.get("setup_type"),
        "rsi_timeframe": context.get("rsi_timeframe"),
        "observed_at": context.get("observed_at"),
        "freshness_status": context.get("freshness_status"),
        "valid": context.get("valid"),
    }]


def _observation_ids(source: Mapping[str, Any]) -> list[str]:
    existing = _items(source.get("observation_ids"))
    if existing:
        return list(dict.fromkeys(existing))
    return list(dict.fromkeys(
        str(source.get(field) or "").strip()
        for field in (
            "candidate_id", "integrated_candidate_id", "core_opportunity_id", "market_anomaly_id",
            "incident_id", "alert_id", "observation_id", "outcome_id", "feedback_id",
            "delivery_id", "target", "key", "event_id",
        )
        if str(source.get(field) or "").strip()
    ))


def _source_provider_lineage(source: Mapping[str, Any]) -> dict[str, Any]:
    provenance = event_market_provenance.market_provenance_values(source)
    existing = source.get("source_provider_lineage")
    if isinstance(existing, Mapping):
        lineage = deepcopy(dict(existing))
        preferred_mode = str(
            provenance.get("data_acquisition_mode")
            or source.get("candidate_source_mode")
            or source.get("data_acquisition_mode")
            or source.get("data_mode")
            or lineage.get("data_mode")
            or source.get("run_mode")
            or "unknown"
        ).strip()
        lineage["data_mode"] = preferred_mode
        if provenance:
            providers = list(dict.fromkeys((
                str(provenance.get("provider") or "").strip(),
                *_items(lineage.get("providers")),
            )))
            lineage["providers"] = [provider for provider in providers if provider]
            lineage["market_provenance"] = deepcopy(provenance)
            lineage["candidate_source_mode"] = provenance.get("candidate_source_mode")
            lineage["provenance_contract_valid"] = provenance.get("provenance_contract_valid")
            lineage["measurement_program"] = provenance.get("measurement_program")
            lineage["decision_radar_campaign_counted"] = provenance.get("decision_radar_campaign_counted")
            lineage["burn_in_counted"] = provenance.get("burn_in_counted")
        return lineage
    providers = list(dict.fromkeys(
        str(source.get(field) or "").strip()
        for field in ("primary_source_provider", "source_provider", "latest_source", "provider")
        if str(source.get(field) or "").strip()
    ))
    origins = list(dict.fromkeys((
        *_items(source.get("source_origins")),
        *_items(source.get("source_origin")),
    )))
    packs = list(dict.fromkeys((
        *_items(source.get("source_packs")),
        *_items(source.get("source_pack")),
    )))
    if provenance.get("provider"):
        providers = list(dict.fromkeys((str(provenance["provider"]), *providers)))
    lineage = {
        "data_mode": str(
            provenance.get("data_acquisition_mode")
            or source.get("candidate_source_mode")
            or source.get("data_acquisition_mode")
            or source.get("data_mode")
            or source.get("run_mode")
            or "unknown"
        ).strip(),
        "providers": providers,
        "origins": origins,
        "source_packs": packs,
        "provider_generation_id": str(source.get("provider_generation_id") or "").strip(),
        "run_id": str(source.get("run_id") or "").strip(),
        "profile": str(source.get("profile") or "").strip(),
        "artifact_namespace": str(source.get("artifact_namespace") or "").strip(),
    }
    if provenance:
        lineage.update({
            "market_provenance": deepcopy(provenance),
            "candidate_source_mode": provenance.get("candidate_source_mode"),
            "provenance_contract_valid": provenance.get("provenance_contract_valid"),
            "measurement_program": provenance.get("measurement_program"),
            "decision_radar_campaign_counted": provenance.get("decision_radar_campaign_counted"),
            "burn_in_counted": provenance.get("burn_in_counted"),
        })
    return lineage


def market_context_reference(source: Mapping[str, Any]) -> dict[str, Any]:
    """Return one copy-safe identity for the market snapshot behind a decision."""

    existing = source.get("market_context_reference")
    if isinstance(existing, Mapping) and existing:
        normalized = {
            "source": _optional_text(existing.get("source")),
            "observed_at": _optional_text(existing.get("observed_at")),
            "freshness_status": _optional_text(existing.get("freshness_status")),
            "market_snapshot_id": _optional_text(existing.get("market_snapshot_id")),
        }
        return normalized if any(value is not None for value in normalized.values()) else {}
    snapshot: Mapping[str, Any] = {}
    for field in ("latest_market_snapshot", "market_snapshot", "market_state_snapshot"):
        value = source.get(field)
        if isinstance(value, Mapping) and value:
            snapshot = value
            break
    quality = (
        snapshot.get("market_data_quality")
        if isinstance(snapshot.get("market_data_quality"), Mapping)
        else {}
    )
    provenance = event_market_provenance.market_provenance_values(source)
    provenance_quality = (
        provenance.get("data_quality")
        if isinstance(provenance.get("data_quality"), Mapping)
        else {}
    )
    reference = {
        "source": _optional_text(
            source.get("market_context_source")
            or source.get("integrated_market_context_source")
            or snapshot.get("market_data_source")
            or snapshot.get("source_provider")
            or snapshot.get("latest_source")
            or snapshot.get("source")
            or provenance.get("provider")
        ),
        "observed_at": _optional_text(
            source.get("market_context_observed_at")
            or snapshot.get("observed_at")
            or snapshot.get("timestamp")
            or provenance_quality.get("observed_at")
        ),
        "freshness_status": _optional_text(
            source.get("market_context_freshness_status")
            or source.get("market_data_freshness")
            or source.get("integrated_market_freshness_status")
            or snapshot.get("market_context_freshness_status")
            or snapshot.get("freshness_status")
            or provenance_quality.get("freshness_status")
        ),
        "market_snapshot_id": _optional_text(
            source.get("market_snapshot_id")
            or source.get("market_history_observation_id")
            or snapshot.get("market_snapshot_id")
            or snapshot.get("market_history_observation_id")
            or quality.get("market_snapshot_id")
            or quality.get("baseline_observation_id")
        ),
    }
    return reference if any(value is not None for value in reference.values()) else {}


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _market_provenance_markdown_lines(provenance: Mapping[str, Any]) -> list[str]:
    request_path = str(provenance.get("request_ledger_path") or "none")
    source_path = str(provenance.get("provider_source_artifact") or "none")
    return [
        (
            "- Market provenance mode / source / provider: "
            f"{provenance.get('data_acquisition_mode') or 'unknown'} / "
            f"{provenance.get('candidate_source_mode') or 'unknown'} / "
            f"{provenance.get('provider') or 'unknown'}"
        ),
        (
            "- Market provenance contract / provider call / cache: "
            f"valid={str(bool(provenance.get('provenance_contract_valid'))).lower()} / "
            f"attempted={str(bool(provenance.get('provider_call_attempted'))).lower()} / "
            f"succeeded={str(bool(provenance.get('provider_call_succeeded'))).lower()} / "
            f"{provenance.get('cache_status') or 'unknown'}"
        ),
        (
            "- Decision Radar campaign eligible / counted: "
            f"{str(bool(provenance.get('decision_radar_campaign_eligible'))).lower()} / "
            f"{str(bool(provenance.get('decision_radar_campaign_counted'))).lower()} "
            f"({provenance.get('decision_radar_campaign_reason') or 'not_counted'})"
        ),
        f"- Market request ledger / source artifact: {request_path} / {source_path}",
        f"- Feature basis: {_mapping_summary(provenance.get('feature_basis'))}",
        f"- Market data quality: {_mapping_summary(provenance.get('data_quality'))}",
    ]


def _mapping_summary(value: Any) -> str:
    if not isinstance(value, Mapping) or not value:
        return "not recorded"
    return "; ".join(
        f"{key}={item}"
        for key, item in list(sorted(value.items(), key=lambda pair: str(pair[0])))[:8]
    )


def _evaluation_timestamp(source: Mapping[str, Any]) -> Any:
    for field in (
        "decision_evaluated_at", "evaluated_at", "generated_at", "observed_at", "created_at",
    ):
        if source.get(field) not in (None, ""):
            return source.get(field)
    return None


def _safety_invariants(source: Mapping[str, Any]) -> dict[str, bool]:
    return {
        "research_only": source.get("research_only") is True,
        "no_live_trading": not _truthy_any(source, ("trade_created", "trades_created", "execution_enabled")),
        "no_event_alpha_paper_trading": not _truthy_any(
            source, ("paper_trade_created", "paper_trades_created", "paper_trading_enabled")
        ),
        "no_normal_rsi_writes": not _truthy_any(
            source, ("normal_rsi_signal_written", "normal_rsi_signal_rows_written", "normal_rsi_routing_enabled")
        ),
        "no_triggered_fade_creation": not _truthy_any(source, ("triggered_fade_created",)),
        "no_notification_send": not _truthy_any(
            source, ("notification_send_enabled", "sent", "telegram_sends", "created_alert")
        ),
        "source_side_effect_safety_passed": source.get("decision_source_side_effect_safety_failed") is not True,
        "source_secret_safety_passed": source.get("decision_source_secret_safety_failed") is not True,
        "source_path_safety_passed": source.get("decision_source_path_safety_failed") is not True,
    }


def _truthy_any(source: Mapping[str, Any], fields: Iterable[str]) -> bool:
    return any(
        value is True
        or isinstance(value, (int, float)) and not isinstance(value, bool) and value != 0
        or str(value or "").strip().casefold() in {"1", "true", "yes", "on"}
        for field in fields
        for value in (source.get(field),)
    )


def _mapping_rows(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        return [row for row in value if isinstance(row, Mapping) and row]
    return []


def _candidate_schedule_reference(source: Mapping[str, Any]) -> str:
    for field in ("candidate_id", "integrated_candidate_id", "core_opportunity_id"):
        value = str(source.get(field) or "").strip()
        if value:
            return f"candidate_schedule:{value}"
    return ""


def _has_decision_model_marker(source: Mapping[str, Any]) -> bool:
    return any(
        source.get(field) not in (None, "")
        for field in ("decision_model_version", "decision_model_enabled")
    )


def _row_has_decision_model_marker(row: Mapping[str, Any]) -> bool:
    if _has_decision_model_marker(row):
        return True
    return any(
        isinstance(row.get(key), Mapping) and _has_decision_model_marker(row[key])
        for key in ("score_components", "latest_score_components")
    )


def _items(value: Any) -> list[str]:
    if value in (None, "", [], {}, ()):
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]
    if isinstance(value, Mapping):
        return [f"{key}={child}" for key, child in value.items()]
    if isinstance(value, Iterable):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _score(value: Any) -> str:
    try:
        return f"{float(value):.1f}/100"
    except (TypeError, ValueError):
        return "n/a"


def _decision_row_rank(row: Mapping[str, Any]) -> tuple[float, float, str]:
    values = decision_model_values(row)
    try:
        actionability = float(values.get("actionability_score") or 0.0)
    except (TypeError, ValueError):
        actionability = 0.0
    try:
        evidence = float(values.get("evidence_confidence_score") or 0.0)
    except (TypeError, ValueError):
        evidence = 0.0
    return actionability, evidence, str(row.get("symbol") or "")


__all__ = (
    "DECISION_MODEL_FIELD_NAMES",
    "DECISION_PROJECTION_FIELD_NAMES",
    "DECISION_PROJECTION_SCHEMA_VERSION",
    "PREVIEW_LANE_ORDER",
    "PREVIEW_LANE_TITLES",
    "actionability_score_cohort",
    "decision_model_is_enabled",
    "decision_model_markdown_lines",
    "decision_model_values",
    "decision_preview_lane",
    "group_decision_rows",
    "market_context_reference",
)
