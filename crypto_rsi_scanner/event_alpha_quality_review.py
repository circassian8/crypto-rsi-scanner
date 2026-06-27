"""Event Alpha signal-quality review reports for local artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from . import (
    event_alpha_alert_store,
    event_alpha_artifacts,
    event_core_opportunities,
    event_alpha_quality_fields,
    event_alpha_router,
    event_alpha_reason_text,
    event_opportunity_verdict,
    event_watchlist,
)


@dataclass(frozen=True)
class EventAlphaQualityReviewResult:
    profile: str | None
    rows: tuple[dict[str, Any], ...]
    candidate_discovery_funnel: dict[str, int]
    stale_warning: str | None = None


def build_quality_review(
    *,
    profile: str | None = None,
    hypothesis_rows: Iterable[Mapping[str, Any]] = (),
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry | Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    stale_warning: str | None = None,
) -> EventAlphaQualityReviewResult:
    rows = [
        *_normalize_rows(hypothesis_rows, source="hypothesis"),
        *_normalize_rows((_entry_row(entry) for entry in watchlist_entries), source="watchlist"),
        *_normalize_rows(alert_rows, source="alert_snapshot"),
    ]
    return EventAlphaQualityReviewResult(
        profile=profile,
        rows=tuple(rows),
        candidate_discovery_funnel=_candidate_discovery_funnel(rows),
        stale_warning=stale_warning,
    )


def format_quality_review(result: EventAlphaQualityReviewResult) -> str:
    rows = list(result.rows)
    lines = [
        "=" * 76,
        "EVENT ALPHA QUALITY REVIEW (research-only; no sends/trades)",
        "=" * 76,
        f"profile: {result.profile or 'default'}",
        f"candidates: {len(rows)}",
        "fresh_vs_legacy: " + _fresh_legacy_summary(rows),
        "quality_coverage: " + _quality_coverage_summary(rows),
        "latest_run: " + _latest_run_summary(rows),
        "opportunity_levels: " + _format_counts(_counts(rows, "opportunity_level")),
        "impact_path_types: " + _format_counts(_counts(rows, "impact_path_type")),
        "candidate_roles: " + _format_counts(_counts(rows, "candidate_role")),
        "event_archetypes: " + _format_counts(_counts(rows, "event_archetype")),
        "cause_statuses: " + _format_counts(_counts(rows, "cause_status")),
        "market_reaction_confirmed: " + _format_counts(_counts(rows, "market_reaction_confirmed")),
        "causal_mechanism_confirmed: " + _format_counts(_counts(rows, "causal_mechanism_confirmed")),
        "evidence_specificity: " + _format_counts(_counts(rows, "evidence_specificity")),
        "market_confirmation_levels: " + _format_counts(_counts(rows, "market_confirmation_level")),
        "snapshot_quality_classifications: " + _format_counts(_counts(rows, "_snapshot_quality_classification")),
        "watchlist_state_quality: " + _format_counts(_counts(rows, "state_quality_classification")),
        "candidate_discovery_funnel: " + _format_counts(result.candidate_discovery_funnel),
        "quality_note: unknown/insufficient_data rows are conservative local-only verdicts or legacy rows, not hidden promotions.",
        "",
        "Strong opportunities:",
    ]
    if result.stale_warning:
        lines.append("stale_artifact_warning: " + result.stale_warning)
    lines.extend(_candidate_lines(_strong_opportunities(rows), limit=8))
    lines.extend(["", "Validated but market-unconfirmed:"])
    lines.extend(_candidate_lines(_market_unconfirmed(rows), limit=8))
    lines.extend(["", "Weak co-occurrence / local-only:"])
    lines.extend(_candidate_lines(_weak_local(rows), limit=8))
    lines.extend(["", "Sector hypotheses awaiting validation:"])
    lines.extend(_candidate_lines(_sector_pending(rows), limit=8))
    lines.extend(["", "Rejected candidates worth reviewing:"])
    lines.extend(_candidate_lines(_rejected_review(rows), limit=8))
    lines.extend(["", "Possible false positives:"])
    lines.extend(_candidate_lines(_possible_false_positives(rows), limit=8))
    lines.extend(["", "Quality Gate Conflicts:"])
    lines.extend(_quality_gate_conflict_lines(rows, limit=8))
    lines.extend(["", "Quality-Capped Watchlist Rows:"])
    lines.extend(_quality_capped_state_lines(rows, limit=8))
    lines.extend(["", "Top upgrade candidates:"])
    lines.extend(_upgrade_lines(rows, limit=6))
    lines.extend(["", "Top downgrade risks:"])
    lines.extend(_downgrade_lines(rows, limit=6))
    lines.extend(["", "Quality Tuning Suggestions:"])
    lines.extend(_tuning_suggestion_lines(rows, result.candidate_discovery_funnel))
    lines.extend(["", "Gaps:"])
    lines.append("- missing market confirmation: " + _format_count_list(_missing(rows, "market_confirmation_level", {"", "unknown", "none"})))
    lines.append("- missing direct impact path: " + _format_count_list(_missing(rows, "impact_path_strength", {"", "unknown", "none", "weak"})))
    lines.append("- blocked by source quality: " + _format_count_list(_source_quality_blocked(rows)))
    lines.append("")
    lines.append("Research-only review; no notifications, trades, paper rows, live RSI rows, or event-fade state were changed.")
    return "\n".join(lines).rstrip()


def _normalize_rows(rows: Iterable[Mapping[str, Any]], *, source: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        data = dict(row)
        components_key = "latest_score_components" if source == "watchlist" else "score_components"
        quality_source = event_alpha_quality_fields.quality_source(data, components_key=components_key)
        top_missing = event_alpha_quality_fields.missing_top_level_quality_fields(data)
        components = event_alpha_quality_fields.quality_components(data)
        data.update(event_alpha_quality_fields.ensure_quality_fields(data, components=components))
        data["_review_source"] = source
        data["_components"] = components
        data["_quality_source"] = quality_source
        data["_top_level_missing_fields"] = list(top_missing)
        data["_legacy_quality_row"] = event_alpha_artifacts.is_legacy_row(data)
        data["_snapshot_quality_classification"] = (
            event_alpha_alert_store.classify_alert_snapshot(data)
            if source == "alert_snapshot"
            else "not_alert_snapshot"
        )
        data["state_quality_classification"] = (
            "quality_capped"
            if bool(data.get("state_quality_capped"))
            else "uncapped"
            if source == "watchlist"
            else "not_watchlist"
        )
        out.append(data)
    return out


def _entry_row(entry: event_watchlist.EventWatchlistEntry | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(entry, Mapping):
        return dict(entry)
    data = {
        "key": entry.key,
        "event_id": entry.event_id,
        "symbol": entry.symbol,
        "coin_id": entry.coin_id,
        "state": event_watchlist.final_state_value(entry),
        "requested_state_before_quality_gate": event_watchlist.requested_state_value(entry),
        "final_state_after_quality_gate": event_watchlist.final_state_value(entry),
        "quality_state_block_reason": entry.quality_state_block_reason,
        "state_quality_capped": event_watchlist.state_is_quality_capped(entry),
        "tier": entry.latest_tier,
        "relationship_type": entry.relationship_type,
        "external_asset": entry.external_asset,
        "latest_score": entry.latest_score,
        "latest_event_name": entry.latest_event_name,
        "latest_score_components": dict(entry.latest_score_components or {}),
        "warnings": list(entry.warnings),
        "suppressed_reason": entry.suppressed_reason,
    }
    for key in event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS:
        value = getattr(entry, key, None)
        if value not in (None, "", [], {}):
            data[key] = value
    return data


def _counts(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        out[value] = out.get(value, 0) + 1
    return out


def _format_counts(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none"


def _candidate_discovery_funnel(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {
        "queries_generated": 0,
        "queries_executed": 0,
        "source_results_fetched": 0,
        "source_results_accepted": 0,
        "source_results_rejected": 0,
        "raw_terms_extracted": 0,
        "candidate_like_terms": 0,
        "resolver_accepted_candidates": 0,
        "resolver_rejected_terms": 0,
        "context_validated_candidates": 0,
        "promoted_candidates": 0,
        "asset_terms_extracted": 0,
        "resolver_accepted": 0,
        "resolver_rejected": 0,
        "candidates_validated": 0,
        "candidates_promoted": 0,
        "resolver_attempted": 0,
        "raw_candidate_terms_added": 0,
        "legacy_candidate_terms_added": 0,
        "resolver_validated_candidates_added": 0,
        "false_positive_rejections": 0,
    }
    for row in rows:
        generated = row.get("generated_queries") or []
        executed = row.get("executed_queries") or []
        crypto = row.get("crypto_candidate_assets") or row.get("_components", {}).get("crypto_candidate_assets") or []
        rejected = row.get("rejected_candidate_assets") or row.get("_components", {}).get("rejected_candidate_assets") or []
        out["queries_generated"] += len(generated) if isinstance(generated, list) else 0
        out["queries_executed"] += len(executed) if isinstance(executed, list) else 0
        rejected_samples = row.get("rejected_validation_samples") or []
        accepted_samples = row.get("accepted_validation_samples") or row.get("validation_samples") or []
        out["source_results_fetched"] += len(rejected_samples) + len(accepted_samples) if isinstance(rejected_samples, list) and isinstance(accepted_samples, list) else 0
        out["source_results_accepted"] += len(accepted_samples) if isinstance(accepted_samples, list) else 0
        out["source_results_rejected"] += len(rejected_samples) if isinstance(rejected_samples, list) else 0
        all_terms = [*(crypto if isinstance(crypto, list) else []), *(rejected if isinstance(rejected, list) else [])]
        candidate_like = sum(1 for item in all_terms if isinstance(item, Mapping) and _candidate_like_term(item))
        accepted = sum(1 for item in crypto if isinstance(item, Mapping) and bool(item.get("accepted", item.get("validated", False))))
        rejected_count = len(rejected) if isinstance(rejected, list) else 0
        out["raw_terms_extracted"] += len(all_terms)
        out["candidate_like_terms"] += candidate_like
        out["resolver_accepted_candidates"] += accepted
        out["resolver_rejected_terms"] += rejected_count
        out["asset_terms_extracted"] += len(all_terms)
        out["resolver_accepted"] += accepted
        out["resolver_rejected"] += rejected_count
        out["resolver_attempted"] += accepted + rejected_count
        out["false_positive_rejections"] += sum(1 for item in rejected if isinstance(item, Mapping) and _rejection_is_false_positive(item))
        for item in rejected:
            if not isinstance(item, Mapping):
                continue
            reason = str(item.get("reason") or item.get("rejection_reason") or item.get("identity_reason") or "unknown_rejection")
            if reason:
                out[f"rejected_{reason}"] = out.get(f"rejected_{reason}", 0) + 1
        out["raw_candidate_terms_added"] += len(all_terms)
        out["legacy_candidate_terms_added"] += candidate_like
        if str(row.get("validation_stage") or "") in {"catalyst_link_validated", "impact_path_validated", "market_confirmed", "promoted_to_radar"}:
            out["candidates_validated"] += 1
            out["context_validated_candidates"] += 1
            out["resolver_validated_candidates_added"] += 1
        if str(row.get("opportunity_level") or "") in {"validated_digest", "watchlist", "high_priority"}:
            out["candidates_promoted"] += 1
            out["promoted_candidates"] += 1
    return out


def _candidate_like_term(item: Mapping[str, Any]) -> bool:
    symbol = str(item.get("symbol") or "").strip()
    coin_id = str(item.get("coin_id") or "").strip()
    name = str(item.get("name") or item.get("project_name") or "").strip()
    source = str(item.get("source") or "").strip().casefold()
    mention_type = str(item.get("mention_type") or item.get("type") or "").strip().casefold()
    reason = str(item.get("reason") or item.get("rejection_reason") or item.get("identity_reason") or "").casefold()
    accepted = bool(item.get("accepted") or item.get("validated"))
    if any(token in reason for token in ("source_noise", "publisher", "word_collision", "url_only", "generic_symbol")):
        return False
    if any(token in mention_type for token in ("source_noise", "publisher", "navigation", "nav", "word_collision")):
        return False
    if source in {"taxonomy", "source_origin", "publisher", "nav", "navigation"} and not accepted:
        return False
    return bool(symbol or coin_id or name)


def _rejection_is_false_positive(item: Mapping[str, Any]) -> bool:
    text = " ".join(str(value or "") for value in item.values()).casefold()
    return any(term in text for term in ("false_positive", "source_noise", "ticker", "word_collision", "url_only", "publisher"))


def _fresh_legacy_summary(rows: list[dict[str, Any]]) -> str:
    fresh = sum(1 for row in rows if not row.get("_legacy_quality_row"))
    legacy = len(rows) - fresh
    return f"fresh={fresh}, legacy_or_unscoped={legacy}"


def _quality_coverage_summary(rows: list[dict[str, Any]]) -> str:
    full = sum(1 for row in rows if not row.get("_top_level_missing_fields"))
    nested = sum(1 for row in rows if row.get("_quality_source") == "nested_score_components")
    partial = sum(1 for row in rows if row.get("_quality_source") == "partial_quality_fields")
    recomputed = sum(1 for row in rows if row.get("_quality_source") == "recomputed")
    return (
        f"full_top_level={full}, nested_only={nested}, "
        f"partial_top_level={partial}, recomputed_or_missing={recomputed}"
    )


def _latest_run_summary(rows: list[dict[str, Any]]) -> str:
    run_ids = [str(row.get("run_id") or "") for row in rows if str(row.get("run_id") or "")]
    if not run_ids:
        return "none"
    latest = sorted(run_ids)[-1]
    latest_rows = sum(1 for row in rows if str(row.get("run_id") or "") == latest)
    return f"{latest} rows={latest_rows}"


def _strong_opportunities(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get("opportunity_level") or "") in {"watchlist", "high_priority"}]


def _market_unconfirmed(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if str(row.get("validation_stage") or row.get("_components", {}).get("validation_stage") or "") in {"catalyst_link_validated", "impact_path_validated", "market_confirmed", "promoted_to_radar"}
        and str(row.get("market_confirmation_level") or "") in {"", "unknown", "none", "weak"}
    ]


def _weak_local(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if str(row.get("opportunity_level") or "") in {"local_only", "exploratory", "unknown"}
        or str(row.get("impact_path_type") or "") == "generic_cooccurrence_only"
        or str(row.get("impact_path_strength") or "") in {"weak", "none"}
    ]


def _sector_pending(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if str(row.get("symbol") or "").upper() == "SECTOR"
        or str(row.get("hypothesis_scope") or row.get("_components", {}).get("hypothesis_scope") or "") == "sector"
    ]


def _rejected_review(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if row.get("rejected_candidate_assets") or row.get("rejected_validation_samples") or row.get("rejection_reasons")
    ]


def _possible_false_positives(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    promoted_core_keys = {
        event_core_opportunities.incident_asset_key_for_opportunity(item)
        for item in event_core_opportunities.aggregate_core_opportunities(rows)
        if item.alertable or item.is_high_priority or item.is_watchlist or item.is_validated_digest
    }
    promoted_asset_keys = {
        event_core_opportunities.asset_key_for_opportunity(item)
        for item in event_core_opportunities.aggregate_core_opportunities(rows)
        if item.alertable or item.is_high_priority or item.is_watchlist or item.is_validated_digest
    }
    return [
        row for row in rows
        if _false_positive_suspicion_reason(row) is not None
        and event_core_opportunities.incident_asset_key_for_values(
            row.get("incident_id") or (row.get("_components") or {}).get("incident_id"),
            row.get("coin_id") or row.get("validated_coin_id") or (row.get("_components") or {}).get("validated_coin_id"),
            row.get("symbol") or row.get("validated_symbol") or (row.get("_components") or {}).get("validated_symbol"),
        ) not in promoted_core_keys
        and event_core_opportunities.asset_key_for_values(
            row.get("coin_id") or row.get("validated_coin_id") or (row.get("_components") or {}).get("validated_coin_id"),
            row.get("symbol") or row.get("validated_symbol") or (row.get("_components") or {}).get("validated_symbol"),
        ) not in promoted_asset_keys
    ]


_FALSE_POSITIVE_SUSPICION_TERMS = {
    "diagnostic_only",
    "source_noise",
    "invalid_subject",
    "ticker_collision",
    "ticker_word_collision",
    "word_collision_false_positive",
    "generic_cooccurrence_only",
    "identity_low_confidence",
    "source_origin_only_identity",
    "identity_source_origin_rejected",
    "common_word_collision",
    "rejected_candidate_asset",
    "publisher_suffix_false_positive",
    "identity_url_only_rejected",
}


def _false_positive_suspicion_reason(row: Mapping[str, Any]) -> str | None:
    components = row.get("_components") if isinstance(row.get("_components"), Mapping) else {}
    level = str(row.get("opportunity_level") or components.get("opportunity_level") or "").casefold()
    role = str(row.get("candidate_role") or components.get("candidate_role") or "").casefold()
    impact = str(row.get("impact_path_type") or components.get("impact_path_type") or "").casefold()
    source_class = str(row.get("source_class") or components.get("source_class") or "").casefold()
    explicit_noise_text = " ".join(str(value or "") for value in (
        role,
        impact,
        source_class,
        row.get("quality_gate_block_reason"),
        row.get("quality_state_block_reason"),
        row.get("route_block_reason"),
        row.get("rejection_reasons"),
        row.get("warnings"),
        row.get("rejected_candidate_assets"),
        components.get("rejected_candidate_assets"),
    )).casefold()
    explicit_noise_terms = {
        "diagnostic_only",
        "source_noise",
        "invalid_subject",
        "ticker_collision",
        "ticker_word_collision",
        "word_collision_false_positive",
        "generic_cooccurrence_only",
        "identity_low_confidence",
        "source_origin_only_identity",
        "identity_source_origin_rejected",
        "common_word_collision",
        "rejected_candidate_asset",
        "publisher_suffix_false_positive",
        "identity_url_only_rejected",
    }
    if (
        impact == "market_dislocation_unknown"
        and role in {"direct_subject", "macro_affected_asset", "ecosystem_affected_asset"}
        and not any(term in explicit_noise_text for term in explicit_noise_terms)
    ):
        return None
    if (
        level in {"validated_digest", "watchlist", "high_priority"}
        and role not in {"source_noise", "ticker_word_collision", "ambiguous", "generic_mention"}
        and impact != "generic_cooccurrence_only"
        and source_class not in {"publisher_suffix_false_positive", "source_noise"}
    ):
        return None
    fields: list[object] = [
        role,
        impact,
        source_class,
        row.get("evidence_specificity"),
        components.get("evidence_specificity"),
        row.get("quality_gate_block_reason"),
        row.get("quality_state_block_reason"),
        row.get("route_block_reason"),
        row.get("why_local_only"),
        row.get("why_not_watchlist"),
        row.get("why_not_promoted"),
        row.get("rejection_reasons"),
        row.get("warnings"),
        row.get("rejected_candidate_assets"),
        components.get("rejected_candidate_assets"),
    ]
    if row.get("rejected_candidate_assets") or components.get("rejected_candidate_assets"):
        fields.append("rejected_candidate_asset")
    text = " ".join(str(value or "") for value in fields).casefold()
    for term in sorted(_FALSE_POSITIVE_SUSPICION_TERMS):
        if term in text:
            return term
    return None


def _quality_gate_conflict_lines(rows: list[dict[str, Any]], *, limit: int) -> list[str]:
    conflicts = [row for row in rows if _quality_gate_conflict(row)]
    if not conflicts:
        return ["- none"]
    out: list[str] = []
    for row in conflicts[:limit]:
        out.append(
            f"- {_label(row)}: route={row.get('route') or 'unknown'} "
            f"requested={row.get('requested_route_before_quality_gate') or 'unknown'} "
            f"final={row.get('final_route_after_quality_gate') or row.get('route') or 'unknown'} "
            f"level={row.get('opportunity_level') or 'unknown'} "
            f"score={row.get('opportunity_score_final') if row.get('opportunity_score_final') is not None else 'n/a'} "
            f"block={row.get('quality_gate_block_reason') or _quality_gate_conflict_reason(row)}"
        )
    if len(conflicts) > limit:
        out.append(f"- +{len(conflicts) - limit} more conflict rows")
    return out


def _quality_capped_state_lines(rows: list[dict[str, Any]], *, limit: int) -> list[str]:
    capped = [row for row in rows if bool(row.get("state_quality_capped"))]
    if not capped:
        return ["- none"]
    out: list[str] = []
    for row in capped[:limit]:
        out.append(
            f"- {_label(row)}: requested_state={row.get('requested_state_before_quality_gate') or row.get('state') or 'unknown'} "
            f"final_state={row.get('final_state_after_quality_gate') or row.get('state') or 'unknown'} "
            f"level={row.get('opportunity_level') or 'unknown'} "
            f"path={row.get('impact_path_type') or 'unknown'} "
            f"score={row.get('opportunity_score_final') if row.get('opportunity_score_final') is not None else 'n/a'} "
            f"block={row.get('quality_state_block_reason') or 'quality_state_capped'}"
        )
    if len(capped) > limit:
        out.append(f"- +{len(capped) - limit} more quality-capped rows")
    return out


def _quality_gate_conflict(row: Mapping[str, Any]) -> bool:
    classification = str(row.get("_snapshot_quality_classification") or "")
    if classification == event_alpha_alert_store.SNAPSHOT_LEGACY_CONFLICT:
        return True
    if classification in {
        event_alpha_alert_store.SNAPSHOT_CURRENT_CLEAN,
        event_alpha_alert_store.SNAPSHOT_QUALITY_GATED_LOCAL,
    }:
        return False
    components = row.get("_components") if isinstance(row.get("_components"), Mapping) else row.get("score_components")
    if not isinstance(components, Mapping):
        components = {}
    final_route, block = event_alpha_router.quality_gate_route_for_row(row, components=components, require_quality=False)
    persisted_alertable = bool(row.get("route_alertable"))
    final_alertable = event_alpha_router.route_value_is_alertable(final_route)
    route = str(row.get("route") or "")
    persisted_route_alertable = event_alpha_router.route_value_is_alertable(route)
    if (persisted_alertable or persisted_route_alertable) and not final_alertable:
        return True
    if persisted_route_alertable and route != final_route:
        return True
    if not final_alertable and final_route not in {"RESEARCH_DIGEST", "HIGH_PRIORITY_RESEARCH"}:
        return False
    if final_route == "TRIGGERED_FADE_RESEARCH":
        return False
    if not final_alertable and route not in {"RESEARCH_DIGEST", "HIGH_PRIORITY_RESEARCH"}:
        return False
    if block and str(block).startswith("opportunity_level_caps_high_priority"):
        return False
    return bool(block) or _quality_gate_conflict_reason(row) != "none"


def _quality_gate_conflict_reason(row: Mapping[str, Any]) -> str:
    level = str(row.get("opportunity_level") or "")
    if level in {"", "local_only", "exploratory"}:
        return f"opportunity_level:{level or 'missing'}"
    if str(row.get("impact_path_type") or "") == "insufficient_data":
        return "impact_path_type_insufficient_data"
    if str(row.get("candidate_role") or "") == "unknown_with_reason":
        return "candidate_role_unknown_with_reason"
    if str(row.get("source_class") or "") == "insufficient_data":
        return "source_class_insufficient_data"
    if str(row.get("evidence_specificity") or "") == "insufficient_data":
        return "evidence_specificity_insufficient_data"
    try:
        score = float(row.get("opportunity_score_final") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    if score <= 0.0:
        return "opportunity_score_final_zero"
    return "none"


def _candidate_lines(rows: list[dict[str, Any]], *, limit: int) -> list[str]:
    rows = _dedupe_core_opportunity_rows(rows) or list(rows)
    if not rows:
        return ["- none"]
    out = []
    for row in sorted(rows, key=lambda item: float(item.get("opportunity_score_final") or item.get("latest_score") or item.get("hypothesis_score") or 0), reverse=True)[:limit]:
        label = row.get("symbol") or row.get("validated_symbol") or row.get("coin_id") or row.get("hypothesis_id") or row.get("event_id") or "candidate"
        components = row.get("_components") if isinstance(row.get("_components"), Mapping) else {}
        supporting_count = int(row.get("supporting_hypothesis_count") or components.get("supporting_hypothesis_count") or 0)
        supporting_categories = row.get("supporting_categories") or components.get("supporting_categories") or ()
        supporting_impact_paths = row.get("supporting_impact_paths") or components.get("supporting_impact_paths") or ()
        supporting_text = ""
        if supporting_count > 1:
            categories = ",".join(str(item) for item in list(supporting_categories)[:3])
            paths = ",".join(str(item) for item in list(supporting_impact_paths)[:3])
            supporting_text = f" supporting={supporting_count}"
            if categories:
                supporting_text += f" categories={categories}"
            if paths:
                supporting_text += f" paths={paths}"
        out.append(
            f"- {label}: level={row.get('opportunity_level') or 'unknown'} "
            f"market={row.get('market_confirmation_level') or 'unknown'} "
            f"path={row.get('impact_path_type') or 'unknown'} "
            f"source={row.get('source_class') or 'unknown'}/{row.get('evidence_specificity') or 'unknown'}"
            f"{supporting_text}"
        )
    return out


def _upgrade_lines(rows: list[dict[str, Any]], *, limit: int) -> list[str]:
    candidates = []
    for row in _dedupe_core_opportunity_rows(rows):
        upgrade = event_opportunity_verdict.explain_upgrade_path(components=row.get("_components") or row)
        if not upgrade.upgrade_requirements:
            continue
        candidates.append((float(row.get("opportunity_score_final") or row.get("latest_score") or 0), row, upgrade))
    if not candidates:
        return ["- none"]
    out = []
    for _score, row, upgrade in sorted(candidates, key=lambda item: item[0], reverse=True)[:limit]:
        out.append(
            f"- {_label(row)}: "
            + (event_alpha_reason_text.humanize_event_alpha_reasons(upgrade.upgrade_requirements, limit=3) or "manual analyst review")
        )
    return out


def _downgrade_lines(rows: list[dict[str, Any]], *, limit: int) -> list[str]:
    candidates = []
    for row in _dedupe_core_opportunity_rows(rows):
        upgrade = event_opportunity_verdict.explain_upgrade_path(components=row.get("_components") or row)
        if not upgrade.downgrade_warnings:
            continue
        candidates.append((float(row.get("opportunity_score_final") or row.get("latest_score") or 0), row, upgrade))
    if not candidates:
        return ["- none"]
    out = []
    for _score, row, upgrade in sorted(candidates, key=lambda item: item[0], reverse=True)[:limit]:
        out.append(
            f"- {_label(row)}: "
            + (event_alpha_reason_text.humanize_event_alpha_reasons(upgrade.downgrade_warnings, limit=3) or "source correction or failed confirmation")
        )
    return out


def _dedupe_core_opportunity_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(item.primary_row) for item in event_core_opportunities.aggregate_core_opportunities(rows)]


def _core_opportunity_key(row: Mapping[str, Any]) -> str:
    components = row.get("_components") if isinstance(row.get("_components"), Mapping) else {}
    aggregate = row.get("aggregated_candidate_id") or components.get("aggregated_candidate_id")
    if aggregate:
        return f"aggregate:{aggregate}"
    incident = row.get("incident_id") or components.get("incident_id") or row.get("event_cluster_id") or row.get("cluster_id") or row.get("event_id")
    asset = (
        row.get("validated_coin_id")
        or components.get("validated_coin_id")
        or row.get("coin_id")
        or components.get("coin_id")
        or row.get("validated_symbol")
        or components.get("validated_symbol")
        or row.get("symbol")
        or components.get("symbol")
        or "unknown_asset"
    )
    role = row.get("candidate_role") or components.get("candidate_role") or row.get("relationship_type") or "unknown_role"
    path = row.get("primary_impact_path") or components.get("primary_impact_path") or row.get("impact_path_type") or components.get("impact_path_type") or row.get("impact_category") or "unknown_path"
    return "|".join(str(part or "unknown") for part in (incident, asset, role, path))


def _row_rank(row: Mapping[str, Any]) -> tuple[float, int, int]:
    score = float(row.get("opportunity_score_final") or row.get("latest_score") or row.get("hypothesis_score") or 0.0)
    source_rank = {"hypothesis": 3, "watchlist": 2, "alert_snapshot": 1}.get(str(row.get("_review_source") or ""), 0)
    supporting = int(row.get("supporting_hypothesis_count") or 0)
    return (score, source_rank, supporting)


def _missing(rows: list[dict[str, Any]], key: str, missing_values: set[str]) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get(key) or "").lower() in missing_values]


def _source_quality_blocked(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if str(row.get("source_class") or "") in {"unknown", "low", "single_low_quality"}
        or float(row.get("evidence_quality_score") or 0) < 40
    ]


def _format_count_list(rows: list[dict[str, Any]]) -> str:
    return str(len(rows)) + (" (" + ", ".join(_label(row) for row in rows[:5]) + ")" if rows else "")


def _tuning_suggestion_lines(rows: list[dict[str, Any]], funnel: Mapping[str, int]) -> list[str]:
    lines: list[str] = []
    digest_candidates = _closest_to_threshold(rows, threshold=65.0, allowed_levels={"exploratory", "local_only"})
    watch_candidates = _closest_to_threshold(rows, threshold=75.0, allowed_levels={"validated_digest", "exploratory"})
    lines.append("- closest_to_digest_threshold: " + _threshold_labels(digest_candidates))
    lines.append("- closest_to_watchlist_threshold: " + _threshold_labels(watch_candidates))
    weak_patterns = _counts(
        [
            row for row in rows
            if str(row.get("impact_path_type") or "") in {"generic_cooccurrence_only", "insufficient_data"}
            or str(row.get("impact_path_strength") or "") in {"weak", "none"}
        ],
        "impact_path_type",
    )
    lines.append("- repeated_weak_cooccurrence_patterns: " + _format_counts(weak_patterns))
    local_sources = _counts(
        [row for row in rows if str(row.get("opportunity_level") or "") in {"local_only", "exploratory"}],
        "source_class",
    )
    lines.append("- sources_producing_local_only_rows: " + _format_counts(local_sources))
    impact_paths = _counts(
        [row for row in rows if str(row.get("opportunity_level") or "") in {"validated_digest", "watchlist", "high_priority"}],
        "impact_path_type",
    )
    lines.append("- impact_paths_producing_alertable_rows: " + _format_counts(impact_paths))
    blockers = _common_blockers(rows)
    lines.append("- most_common_missing_evidence: " + _format_counts(blockers))
    lines.append(
        "- candidate_discovery_experiment: "
        f"raw_terms={funnel.get('raw_terms_extracted', 0)} "
        f"candidate_like={funnel.get('candidate_like_terms', 0)} "
        f"resolver_accepted={funnel.get('resolver_accepted_candidates', 0)} "
        f"context_validated={funnel.get('context_validated_candidates', 0)} "
        f"promoted={funnel.get('promoted_candidates', 0)}"
    )
    lines.append("- next_experiments: inspect near-threshold rows, add source-specific negative fixtures, and tune only after feedback/outcome labels.")
    return lines


def _closest_to_threshold(
    rows: list[dict[str, Any]],
    *,
    threshold: float,
    allowed_levels: set[str],
    limit: int = 5,
) -> list[tuple[float, dict[str, Any]]]:
    candidates: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        level = str(row.get("opportunity_level") or "")
        if level not in allowed_levels:
            continue
        try:
            score = float(row.get("opportunity_score_final") or row.get("latest_score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        if score <= 0:
            continue
        candidates.append((abs(threshold - score), row))
    return sorted(candidates, key=lambda item: (item[0], _label(item[1])))[:limit]


def _threshold_labels(rows: list[tuple[float, dict[str, Any]]]) -> str:
    if not rows:
        return "none"
    return ", ".join(
        f"{_label(row)}({float(row.get('opportunity_score_final') or row.get('latest_score') or 0):.0f})"
        for _distance, row in rows
    )


def _common_blockers(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        upgrade = event_opportunity_verdict.explain_upgrade_path(components=row.get("_components") or row)
        for value in (*upgrade.upgrade_requirements, *upgrade.downgrade_warnings):
            key = event_alpha_reason_text.humanize_event_alpha_reason(value)
            if key:
                counts[key] = counts.get(key, 0) + 1
    return counts


def _label(row: Mapping[str, Any]) -> str:
    return str(row.get("symbol") or row.get("validated_symbol") or row.get("coin_id") or row.get("hypothesis_id") or row.get("alert_id") or "candidate")
