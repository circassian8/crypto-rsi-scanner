# ---------------------------------------------------------------------------
# Moved from crypto_rsi_scanner/event_alpha_quality_review.py
# ---------------------------------------------------------------------------
"""Event Alpha signal-quality review reports for local artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from ... import (
    event_alpha_alert_store,
    event_alpha_quality_fields,
    event_alpha_reason_text,
    event_alpha_router,
    event_watchlist,
)
from ..artifacts import context as event_alpha_artifacts
from ..radar import core_opportunities as event_core_opportunities
from ..radar import opportunity_verdict as event_opportunity_verdict


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
    core_opportunity_rows: Iterable[Mapping[str, Any]] = (),
    stale_warning: str | None = None,
) -> EventAlphaQualityReviewResult:
    rows = [
        *_normalize_rows(core_opportunity_rows, source="core_opportunity"),
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
    primary_rows = _primary_review_rows(rows)
    diagnostic_rows = _diagnostic_review_rows(rows, primary_rows)
    section_rows = primary_rows or rows
    lines = [
        "=" * 76,
        "EVENT ALPHA QUALITY REVIEW (research-only; no sends/trades)",
        "=" * 76,
        f"profile: {result.profile or 'default'}",
        f"candidates: {len(primary_rows) if primary_rows else len(rows)} core_or_primary ({len(rows)} total rows)",
        "fresh_vs_legacy: " + _fresh_legacy_summary(rows),
        "quality_coverage: " + _quality_coverage_summary(rows),
        "latest_run: " + _latest_run_summary(rows),
        "opportunity_levels: " + _format_counts(_counts(section_rows, "opportunity_level")),
        "impact_path_types: " + _format_counts(_counts(section_rows, "impact_path_type")),
        "candidate_roles: " + _format_counts(_counts(section_rows, "candidate_role")),
        "event_archetypes: " + _format_counts(_counts(section_rows, "event_archetype")),
        "cause_statuses: " + _format_counts(_counts(section_rows, "cause_status")),
        "market_reaction_confirmed: " + _format_counts(_counts(section_rows, "market_reaction_confirmed")),
        "causal_mechanism_confirmed: " + _format_counts(_counts(section_rows, "causal_mechanism_confirmed")),
        "evidence_specificity: " + _format_counts(_counts(section_rows, "evidence_specificity")),
        "market_confirmation_levels: " + _format_counts(_counts(section_rows, "market_confirmation_level")),
        "derivatives_confirmation_levels: " + _format_counts(_counts(section_rows, "derivatives_confirmation_level")),
        "dex_liquidity_levels: " + _format_counts(_counts(section_rows, "dex_liquidity_level")),
        "protocol_metrics_levels: " + _format_counts(_counts(section_rows, "protocol_metrics_level")),
        "snapshot_quality_classifications: " + _format_counts(_counts(rows, "_snapshot_quality_classification")),
        "watchlist_state_quality: " + _format_counts(_counts(rows, "state_quality_classification")),
        "candidate_discovery_funnel: " + _format_counts(result.candidate_discovery_funnel),
        "live_confirmation_gates: " + _format_counts(_live_confirmation_counts(section_rows)),
        f"operator_view: canonical_core_rows={len([row for row in rows if _is_core_review_row(row)])} support_or_diagnostic_rows={len(diagnostic_rows)}",
        "quality_note: unknown/insufficient_data rows are conservative local-only verdicts or legacy rows, not hidden promotions.",
        "",
        "Strong opportunities:",
    ]
    if result.stale_warning:
        lines.append("stale_artifact_warning: " + result.stale_warning)
    lines.extend(_candidate_lines(_strong_opportunities(section_rows), limit=8))
    lines.extend(["", "Validated but market-unconfirmed:"])
    lines.extend(_candidate_lines(_market_unconfirmed(section_rows), limit=8))
    lines.extend(["", "Watchlist opportunities:"])
    lines.extend(_candidate_lines(_watchlist_opportunities(section_rows), limit=8))
    lines.extend(["", "Near-miss candidates:"])
    lines.extend(_candidate_lines(_near_miss_rows(section_rows), limit=8))
    lines.extend(["", "Weak co-occurrence / local-only:"])
    lines.extend(_candidate_lines(_weak_local(section_rows), limit=8))
    lines.extend(["", "Sector hypotheses awaiting validation:"])
    lines.extend(_candidate_lines(_sector_pending(section_rows), limit=8))
    lines.extend(["", "Rejected candidates worth reviewing:"])
    lines.extend(_candidate_lines(_rejected_review(rows), limit=8))
    lines.extend(["", "Possible false positives:"])
    lines.extend(_candidate_lines(_possible_false_positives(rows), limit=8))
    lines.extend(["", "Quality Gate Conflicts:"])
    lines.extend(_quality_gate_conflict_lines(rows, limit=8))
    lines.extend(["", "Quality-Capped Watchlist Rows:"])
    lines.extend(_quality_capped_state_lines(rows, limit=8))
    lines.extend(["", "Live Confirmation Gated Candidates:"])
    lines.extend(_live_confirmation_gated_lines(section_rows, limit=8))
    lines.extend(["", "Market Freshness Readiness:"])
    lines.extend(_market_freshness_readiness_lines(section_rows, limit=8))
    lines.extend(["", "Top upgrade candidates:"])
    lines.extend(_upgrade_lines(section_rows, limit=6))
    lines.extend(["", "Top downgrade risks:"])
    lines.extend(_downgrade_lines(section_rows, limit=6))
    lines.extend(["", "Quality Tuning Suggestions:"])
    lines.extend(_tuning_suggestion_lines(section_rows, result.candidate_discovery_funnel))
    lines.extend(["", "Diagnostics / support rows:"])
    lines.extend(_diagnostic_summary_lines(diagnostic_rows, limit=8))
    lines.extend(["", "Gaps:"])
    lines.append("- missing market confirmation: " + _format_count_list(_missing(section_rows, "market_confirmation_level", {"", "unknown", "none"})))
    lines.append("- missing direct impact path: " + _format_count_list(_missing(section_rows, "impact_path_strength", {"", "unknown", "none", "weak"})))
    lines.append("- blocked by source quality: " + _format_count_list(_source_quality_blocked(section_rows)))
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


def _primary_review_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    core_rows = [row for row in rows if _is_core_review_row(row)]
    if core_rows:
        return sorted(core_rows, key=lambda row: _row_rank(row), reverse=True)
    return _dedupe_core_opportunity_rows(rows)


def _is_core_review_row(row: Mapping[str, Any]) -> bool:
    return str(row.get("_review_source") or "") == "core_opportunity" or str(row.get("row_type") or "") == "event_core_opportunity"


def _diagnostic_review_rows(rows: list[dict[str, Any]], primary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    primary_ids = {str(row.get("core_opportunity_id") or "").strip() for row in primary_rows if str(row.get("core_opportunity_id") or "").strip()}
    diagnostics: list[dict[str, Any]] = []
    for row in rows:
        if _is_core_review_row(row):
            continue
        core_id = str(row.get("core_opportunity_id") or "").strip()
        if event_core_opportunities.row_is_diagnostic(row) or (core_id and core_id in primary_ids):
            diagnostics.append(row)
    return diagnostics


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


def _watchlist_opportunities(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if str(row.get("opportunity_level") or "") == "watchlist"
        or str(row.get("final_state_after_quality_gate") or row.get("state") or "") == "WATCHLIST"
    ]


def _near_miss_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if _row_is_already_promoted(row):
            continue
        if _false_positive_suspicion_reason(row):
            continue
        level = str(row.get("opportunity_level") or "")
        impact = str(row.get("impact_path_type") or "")
        try:
            score = float(row.get("opportunity_score_final") or row.get("latest_score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        if level in {"exploratory", "local_only"} and score >= 50 and impact not in {"generic_cooccurrence_only", "insufficient_data"}:
            out.append(row)
    return out


def _weak_local(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if not _row_is_already_promoted(row)
        and (
            str(row.get("opportunity_level") or "") in {"local_only", "exploratory", "unknown"}
            or str(row.get("impact_path_type") or "") == "generic_cooccurrence_only"
            or str(row.get("impact_path_strength") or "") in {"weak", "none"}
        )
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


def _live_confirmation_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    out = {
        "live_confirmation_missing": 0,
        "rejected_only_capped": 0,
        "skipped_budget_capped": 0,
        "no_results_capped": 0,
        "sector_only_capped": 0,
    }
    for row in rows:
        if not _truthy(row.get("live_confirmation_capped")):
            continue
        out["live_confirmation_missing"] += 1
        status = str(row.get("evidence_acquisition_status") or "").strip()
        reason = str(row.get("live_confirmation_reason") or "").strip()
        if status == "rejected_results_only" or reason == "rejected_results_only_not_confirmation":
            out["rejected_only_capped"] += 1
        if status == "skipped_budget" or reason == "skipped_budget_not_confirmation":
            out["skipped_budget_capped"] += 1
        if status == "no_results" or reason == "no_results_not_confirmation":
            out["no_results_capped"] += 1
        if reason == "sector_only_digest_not_allowed" or str(row.get("symbol") or "").upper() == "SECTOR":
            out["sector_only_capped"] += 1
    return out


def _live_confirmation_gated_lines(rows: list[dict[str, Any]], *, limit: int) -> list[str]:
    gated = [row for row in rows if _truthy(row.get("live_confirmation_capped"))]
    if not gated:
        return ["- none"]
    out: list[str] = []
    for row in gated[:limit]:
        missing = row.get("live_confirmation_missing_requirements")
        if not isinstance(missing, list):
            missing = []
        out.append(
            f"- {_label(row)}: requested={row.get('requested_opportunity_level_before_live_confirmation') or 'unknown'} "
            f"final={row.get('final_opportunity_level') or row.get('opportunity_level') or 'unknown'} "
            f"acquisition={row.get('evidence_acquisition_status') or 'unknown'} "
            f"confirmation={row.get('acquisition_confirmation_status') or 'unknown'} "
            f"reason={row.get('live_confirmation_reason') or 'live_confirmation_missing'}"
        )
        if missing:
            out.append("  missing: " + "; ".join(str(value) for value in missing[:3]))
    if len(gated) > limit:
        out.append(f"- +{len(gated) - limit} more live-confirmation gated rows")
    return out


def _market_freshness_readiness_lines(rows: list[dict[str, Any]], *, limit: int) -> list[str]:
    statuses = _counts(rows, "market_context_freshness_status")
    capped = [
        row for row in rows
        if _truthy(row.get("market_context_freshness_cap_applied"))
        or str(row.get("market_context_freshness_status") or "") == "stale"
    ]
    missing = [
        row for row in rows
        if str(row.get("market_context_freshness_status") or "missing") in {"missing", "unknown"}
    ]
    refresh_needed = [
        row for row in rows
        if row in capped or row in missing
    ]
    out = [
        "- statuses: " + _format_counts(statuses),
        f"- fresh_market_context={statuses.get('fresh', 0)}",
        f"- capped_by_stale_context={len(capped)}",
        f"- missing_or_unknown_context={len(missing)}",
        f"- targeted_market_refresh_needed={len(refresh_needed)}",
    ]
    for row in refresh_needed[:limit]:
        out.append(
            f"- {_label(row)}: status={row.get('market_context_freshness_status') or 'missing'} "
            f"source={row.get('market_context_source') or 'unknown'} "
            f"age={_market_age_label(row)} "
            f"cap_applied={str(_truthy(row.get('market_context_freshness_cap_applied'))).lower()}"
        )
    if len(refresh_needed) > limit:
        out.append(f"- +{len(refresh_needed) - limit} more rows need refresh")
    return out


def _market_age_label(row: Mapping[str, Any]) -> str:
    try:
        hours = float(row.get("market_context_age_hours"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "unknown"
    if hours < 1:
        return f"{hours * 60:.0f}m"
    return f"{hours:.1f}h"


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y"}
    return bool(value)


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
        if _row_is_high_priority(row) or str(row.get("opportunity_level") or "") not in {"validated_digest", "watchlist"}:
            continue
        upgrade = event_opportunity_verdict.explain_upgrade_path(components=row.get("_components") or row)
        if not upgrade.upgrade_requirements:
            continue
        candidates.append((float(row.get("opportunity_score_final") or row.get("latest_score") or 0), row, upgrade))
    if not candidates:
        return ["- none"]
    out = []
    for _score, row, upgrade in sorted(candidates, key=lambda item: item[0], reverse=True)[:limit]:
        verdict_copy = event_opportunity_verdict.build_verdict_aware_upgrade_downgrade_text(row.get("_components") or row)
        out.append(
            f"- {_label(row)}: "
            + (
                verdict_copy.upgrade_text
                if _row_is_already_promoted(row)
                else (event_alpha_reason_text.humanize_event_alpha_reasons(upgrade.upgrade_requirements, limit=3) or "manual analyst review")
            )
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
        verdict_copy = event_opportunity_verdict.build_verdict_aware_upgrade_downgrade_text(row.get("_components") or row)
        out.append(
            f"- {_label(row)}: "
            + (
                verdict_copy.downgrade_text
                if _row_is_already_promoted(row)
                else (event_alpha_reason_text.humanize_event_alpha_reasons(upgrade.downgrade_warnings, limit=3) or "source correction or failed confirmation")
            )
        )
    return out


def _dedupe_core_opportunity_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows_list = [dict(row) for row in rows]
    core_rows = [row for row in rows_list if _is_core_review_row(row)]
    if core_rows:
        return sorted(core_rows, key=lambda row: _row_rank(row), reverse=True)
    return [dict(item.primary_row) for item in event_core_opportunities.aggregate_core_opportunities(rows_list)]


def _row_is_high_priority(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("opportunity_level") or "") == "high_priority"
        or str(row.get("final_route_after_quality_gate") or row.get("route") or "") == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
        or str(row.get("final_state_after_quality_gate") or row.get("state") or "") == event_watchlist.EventWatchlistState.HIGH_PRIORITY.value
    )


def _row_is_already_promoted(row: Mapping[str, Any]) -> bool:
    route = str(row.get("final_route_after_quality_gate") or row.get("route") or "")
    level = str(row.get("opportunity_level") or "")
    state = str(row.get("final_state_after_quality_gate") or row.get("state") or "")
    return (
        event_alpha_router.route_value_is_alertable(route)
        or route in {
            event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value,
        }
        or level in {"validated_digest", "watchlist", "high_priority"}
        or state in {
            event_watchlist.EventWatchlistState.WATCHLIST.value,
            event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            event_watchlist.EventWatchlistState.TRIGGERED_FADE.value,
        }
    )


def _diagnostic_summary_lines(rows: list[dict[str, Any]], *, limit: int) -> list[str]:
    if not rows:
        return ["- none"]
    out = [
        f"- support_or_diagnostic_rows={len(rows)}",
        "- by_source: " + _format_counts(_counts(rows, "_review_source")),
    ]
    for row in rows[:limit]:
        out.append(
            f"- {_label(row)}: source={row.get('_review_source') or 'row'} "
            f"level={row.get('opportunity_level') or 'unknown'} "
            f"path={row.get('impact_path_type') or 'unknown'} "
            f"reason={row.get('why_other_rows_hidden') or row.get('quality_gate_block_reason') or row.get('quality_state_block_reason') or 'support'}"
        )
    if len(rows) > limit:
        out.append(f"- +{len(rows) - limit} more support/diagnostic rows")
    return out


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


# ---------------------------------------------------------------------------
# Moved from crypto_rsi_scanner/event_alpha_quality_coverage.py
# ---------------------------------------------------------------------------
"""Fresh-run Event Alpha signal-quality artifact coverage reports."""


import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ... import event_alpha_quality_fields
from ..artifacts import context as event_alpha_artifacts
from ..artifacts import run_ledger as event_alpha_run_ledger


STALE_QUALITY_ARTIFACT_WARNING = (
    "This namespace may contain pre-quality-layer artifacts; rerun profile to refresh."
)


@dataclass(frozen=True)
class EventAlphaQualityCoverageMissingRow:
    row_key: str
    missing_fields: tuple[str, ...]


@dataclass(frozen=True)
class EventAlphaQualityCoverageBucket:
    row_type: str
    rows: int
    complete: int
    missing_rows: tuple[EventAlphaQualityCoverageMissingRow, ...]


@dataclass(frozen=True)
class EventAlphaQualityCoverageResult:
    profile: str | None
    artifact_namespace: str | None
    run_id: str | None
    status: str
    stale_warning: str | None
    buckets: tuple[EventAlphaQualityCoverageBucket, ...]
    warnings: tuple[str, ...] = ()


def read_jsonl_rows(path: str | Path, *, row_type: str | None = None) -> list[dict[str, Any]]:
    """Read local JSONL artifact rows, tolerating missing/malformed files."""
    p = Path(path).expanduser()
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                text = line.strip()
                if not text:
                    continue
                try:
                    row = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                if row_type is not None and row.get("row_type") != row_type:
                    continue
                rows.append(row)
    except OSError:
        return []
    return rows


def build_latest_run_quality_coverage(
    *,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_rows: Iterable[Mapping[str, Any]] = (),
    hypothesis_rows: Iterable[Mapping[str, Any]] = (),
    watchlist_rows: Iterable[Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    reference_quality_rows: Iterable[Mapping[str, Any]] = (),
    include_legacy: bool = False,
) -> EventAlphaQualityCoverageResult:
    """Build a top-level quality-field coverage report for the newest run only."""
    runs = [dict(row) for row in run_rows if isinstance(row, Mapping)]
    raw_hypotheses = [dict(row) for row in hypothesis_rows if isinstance(row, Mapping)]
    raw_watchlist = [dict(row) for row in watchlist_rows if isinstance(row, Mapping)]
    raw_alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    raw_reference = [dict(row) for row in reference_quality_rows if isinstance(row, Mapping)]
    latest = event_alpha_run_ledger.latest_run(runs, profile)
    warnings: list[str] = []
    if not latest:
        buckets = (
            _bucket("hypothesis", ()),
            _bucket("watchlist", ()),
            _bucket("alert_snapshot", ()),
        )
        return EventAlphaQualityCoverageResult(
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_id=None,
            status="WARN",
            stale_warning=stale_quality_artifact_warning(
                [*raw_hypotheses, *raw_watchlist, *raw_alerts],
                reference_rows=raw_reference,
            ),
            buckets=buckets,
            warnings=("no_latest_run_row",),
        )

    run_id = str(latest.get("run_id") or "")
    if not run_id:
        warnings.append("latest_run_missing_run_id")
    started = _parse_dt(latest.get("started_at"))
    finished = _parse_dt(latest.get("finished_at")) or started
    if started is None:
        warnings.append("latest_run_missing_started_at")
    if finished is None and started is None:
        warnings.append("latest_run_missing_finished_at")

    hypotheses = [
        dict(row) for row in raw_hypotheses
        if _row_in_latest_run(row, run_id=run_id, include_legacy=include_legacy)
    ]
    alerts = [
        dict(row) for row in raw_alerts
        if _row_in_latest_run(row, run_id=run_id, include_legacy=include_legacy)
    ]
    watchlist = [
        dict(row) for row in raw_watchlist
        if _watchlist_row_in_run_window(row, started=started, finished=finished, include_legacy=include_legacy)
    ]
    buckets = (
        _bucket("hypothesis", hypotheses),
        _bucket("watchlist", watchlist),
        _bucket("alert_snapshot", alerts),
    )
    missing = sum(len(bucket.missing_rows) for bucket in buckets)
    status = "BLOCKED" if missing else "OK"
    if not any(bucket.rows for bucket in buckets):
        status = "WARN"
        warnings.append("latest_run_has_no_quality_rows")
    return EventAlphaQualityCoverageResult(
        profile=profile,
        artifact_namespace=artifact_namespace,
        run_id=run_id or None,
        status=status,
        stale_warning=stale_quality_artifact_warning(
            [*raw_hypotheses, *raw_watchlist, *raw_alerts],
            reference_rows=raw_reference,
        ),
        buckets=buckets,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def stale_quality_artifact_warning(
    rows: Iterable[Mapping[str, Any]],
    *,
    reference_rows: Iterable[Mapping[str, Any]] = (),
) -> str | None:
    """Warn when a namespace looks stale but the quality-validation namespace is clean."""
    current = [dict(row) for row in rows if isinstance(row, Mapping)]
    reference = [dict(row) for row in reference_rows if isinstance(row, Mapping)]
    if not current or not reference:
        return None
    current_missing = any(
        event_alpha_quality_fields.missing_top_level_quality_fields(row)
        for row in current
    )
    reference_clean = bool(reference) and all(
        not event_alpha_quality_fields.missing_top_level_quality_fields(row)
        for row in reference
    )
    return STALE_QUALITY_ARTIFACT_WARNING if current_missing and reference_clean else None


def format_quality_coverage_report(result: EventAlphaQualityCoverageResult) -> str:
    """Return an operator-readable fresh-run quality coverage report."""
    lines = [
        "=" * 76,
        "EVENT ALPHA QUALITY COVERAGE REPORT (fresh artifacts only)",
        "=" * 76,
        f"status: {result.status}",
        f"profile: {result.profile or 'default'}",
        f"namespace: {result.artifact_namespace or 'default'}",
        f"latest_run_id: {result.run_id or 'none'}",
        "required_fields: " + ", ".join(event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS),
        "",
        "coverage:",
    ]
    for bucket in result.buckets:
        lines.append(
            f"- {bucket.row_type}: rows={bucket.rows} complete={bucket.complete} "
            f"missing_rows={len(bucket.missing_rows)}"
        )
        for missing in bucket.missing_rows[:10]:
            lines.append(
                f"  - {missing.row_key}: missing={', '.join(missing.missing_fields)}"
            )
        if len(bucket.missing_rows) > 10:
            lines.append(f"  - +{len(bucket.missing_rows) - 10} more missing rows")
    if result.stale_warning:
        lines.extend(["", f"stale_artifact_warning: {result.stale_warning}"])
    lines.extend(["", "warnings:"])
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- none")
    lines.append("")
    lines.append("Coverage checks local artifacts only; no sends, trades, paper rows, live RSI rows, or trigger state changed.")
    return "\n".join(lines).rstrip()


def _bucket(row_type: str, rows: Iterable[Mapping[str, Any]]) -> EventAlphaQualityCoverageBucket:
    data = [dict(row) for row in rows if isinstance(row, Mapping)]
    missing_rows: list[EventAlphaQualityCoverageMissingRow] = []
    for row in data:
        missing = event_alpha_quality_fields.missing_top_level_quality_fields(row)
        if missing:
            missing_rows.append(EventAlphaQualityCoverageMissingRow(_row_key(row), missing))
    return EventAlphaQualityCoverageBucket(
        row_type=row_type,
        rows=len(data),
        complete=len(data) - len(missing_rows),
        missing_rows=tuple(missing_rows),
    )


def _row_in_latest_run(row: Mapping[str, Any], *, run_id: str, include_legacy: bool) -> bool:
    data = dict(row)
    if not include_legacy and event_alpha_artifacts.is_legacy_row(data):
        return False
    if not run_id:
        return False
    return str(data.get("run_id") or "") == run_id


def _watchlist_row_in_run_window(
    row: Mapping[str, Any],
    *,
    started: datetime | None,
    finished: datetime | None,
    include_legacy: bool,
) -> bool:
    data = dict(row)
    if started is None:
        return False
    observed = _parse_dt(data.get("last_seen_at") or data.get("observed_at") or data.get("first_seen_at"))
    if observed is None:
        return False
    end = finished or started
    return (started - timedelta(seconds=5)) <= observed <= (end + timedelta(minutes=5))


def _row_key(row: Mapping[str, Any]) -> str:
    for key in (
        "alert_id",
        "alert_key",
        "hypothesis_id",
        "key",
        "event_id",
        "snapshot_id",
        "run_id",
    ):
        value = str(row.get(key) or "").strip()
        if value:
            return value[:160]
    return "unknown_row"


def _parse_dt(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Moved from crypto_rsi_scanner/event_alpha_signal_quality.py
# ---------------------------------------------------------------------------
"""Offline signal-quality benchmark for Event Alpha research decisions."""


import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Mapping

from ... import (
    event_claim_semantics,
    event_evidence_quality,
    event_incident_graph,
    event_impact_path_validator,
    event_market_confirmation,
    event_alpha_reason_text,
)
from ...event_models import NormalizedEvent, RawDiscoveredEvent
from ..radar import core_opportunities as event_core_opportunities
from ..radar import incidents as event_incident_store
from ..radar import opportunity_verdict as event_opportunity_verdict


DEFAULT_SIGNAL_QUALITY_CASES_PATH = Path("fixtures/event_discovery/event_alpha_signal_quality_cases.json")


@dataclass(frozen=True)
class SignalQualityCaseResult:
    case_id: str
    title: str
    passed: bool
    stage_failures: tuple[str, ...]
    expected: Mapping[str, Any]
    actual: Mapping[str, Any]
    diffs: tuple[str, ...]


@dataclass(frozen=True)
class SignalQualityEvalResult:
    path: Path
    total_cases: int
    passed_cases: int
    failed_cases: int
    case_results: tuple[SignalQualityCaseResult, ...]


def load_signal_quality_cases(path: str | Path = DEFAULT_SIGNAL_QUALITY_CASES_PATH) -> tuple[dict[str, Any], ...]:
    p = Path(path).expanduser()
    data = json.loads(p.read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, Mapping) else data
    if not isinstance(cases, list):
        raise ValueError("signal quality fixture must contain a list or {'cases': [...]}")
    return tuple(dict(case) for case in cases if isinstance(case, Mapping))


def evaluate_signal_quality_cases(
    path: str | Path = DEFAULT_SIGNAL_QUALITY_CASES_PATH,
) -> SignalQualityEvalResult:
    p = Path(path).expanduser()
    results = tuple(evaluate_signal_quality_case(case) for case in load_signal_quality_cases(p))
    passed = sum(1 for result in results if result.passed)
    return SignalQualityEvalResult(
        path=p,
        total_cases=len(results),
        passed_cases=passed,
        failed_cases=len(results) - passed,
        case_results=results,
    )


def evaluate_signal_quality_case(case: Mapping[str, Any]) -> SignalQualityCaseResult:
    case_id = str(case.get("case_id") or "unknown")
    title = str(case.get("title") or case_id)
    raw = _raw_event(case)
    hypothesis = _hypothesis(case)
    symbol = _optional_str(case.get("candidate_symbol"))
    coin_id = _optional_str(case.get("candidate_coin_id"))
    identity_rejection = _identity_rejection_reason(raw, symbol=symbol, coin_id=coin_id)

    impact = event_impact_path_validator.validate_impact_path(
        raw,
        hypothesis,
        symbol=symbol,
        coin_id=coin_id,
        score_components=dict(case.get("score_components") or {}),
    )
    claims = event_claim_semantics.extract_event_claims((raw,))
    archetype = event_incident_graph.event_archetype(None, (raw,), claims=claims)
    incident = event_incident_graph.build_incidents(
        (_normalized_event_for_case(case, raw),),
        {raw.raw_id: raw},
    )[0]
    market = event_market_confirmation.evaluate_market_confirmation(
        event_market_confirmation.EventMarketConfirmationInput(
            market_snapshot=_mapping(case.get("market_snapshot")),
            derivatives_snapshot=_mapping(case.get("derivatives_snapshot")),
            supply_snapshot=_mapping(case.get("supply_snapshot")),
            btc_context=_mapping(case.get("btc_context")),
            sector_benchmark=_mapping(case.get("sector_benchmark")),
            playbook_type=str(case.get("playbook_hint") or case.get("impact_category") or ""),
            impact_category=str(case.get("impact_category") or ""),
            now=case.get("now") or "2026-06-15T16:00:00Z",
            market_context_observed_at=(
                case.get("market_context_observed_at")
                if "market_context_observed_at" in case
                else raw.fetched_at.isoformat()
            ),
            market_context_source=str(case.get("market_context_source") or "fixture_signal_quality"),
            market_context_max_age_hours=float(case.get("market_context_max_age_hours") or 6.0),
            allow_stale_fixture_market_context=bool(case.get("allow_stale_fixture_market_context", True)),
            stale_cap_level=str(case.get("stale_cap_level") or "weak"),
        )
    )
    evidence = event_evidence_quality.evaluate_evidence_quality(
        raw,
        hypothesis=hypothesis,
        symbol=symbol,
        coin_id=coin_id,
    )
    components = dict(case.get("score_components") or {})
    components.update({
        "market_confirmation": market.market_confirmation_score,
        "source_quality": evidence.evidence_quality_score,
        "source_class": evidence.source_class,
        "evidence_specificity": evidence.evidence_specificity,
        "validation_strength": 95.0 if not identity_rejection and symbol else 30.0,
        "candidate_asset_strength": 90.0 if not identity_rejection and symbol else 10.0,
        "timing_event_window": float(case.get("timing_event_window") or components.get("event_clarity") or 70.0),
        "liquidity_tradability": max(float(case.get("liquidity_tradability") or 0.0), market.market_confirmation_score),
    })
    verdict = event_opportunity_verdict.evaluate_opportunity(
        impact_path=impact,
        market_confirmation=market,
        evidence_quality=evidence,
        hypothesis=hypothesis,
        score_components=components,
    )
    opportunity_level = verdict.opportunity_level
    route_tier = _route_tier(opportunity_level)
    digest = verdict.digest_eligible
    watchlist = verdict.watchlist_eligible
    high_priority = verdict.high_priority_eligible
    reason_codes = tuple(dict.fromkeys((
        *(verdict.verdict_reason_codes or ()),
        *(verdict.missing_requirements or ()),
        *(evidence.reason_codes or ()),
        *(market.reasons or ()),
        *(market.warnings or ()),
        impact.impact_path_reason,
    )))
    blocked = verdict.why_local_only or verdict.why_not_watchlist
    if identity_rejection:
        opportunity_level = "local_only"
        route_tier = "STORE_ONLY"
        digest = False
        watchlist = False
        high_priority = False
        blocked = identity_rejection
        reason_codes = tuple(dict.fromkeys((*reason_codes, identity_rejection, "needs_identity_validation")))
    incident_hypothesis_generated = bool(
        case.get(
            "incident_hypothesis_generated",
            bool(case.get("candidate_symbol") or case.get("candidate_coin_id")),
        )
    )
    incident_hypothesis_row = _incident_hypothesis_row(
        hypothesis,
        incident_id=incident.incident_id,
        symbol=symbol,
        coin_id=coin_id,
        impact=impact,
        evidence=evidence,
        verdict=verdict,
        opportunity_level=opportunity_level,
        identity_rejection=identity_rejection,
    )
    incident_relevance = event_incident_store.classify_incident_relevance(
        incident,
        raw_by_id={raw.raw_id: raw},
        hypotheses=(incident_hypothesis_row,) if incident_hypothesis_generated else (),
        watchlist_rows=(),
    )
    core_opportunities = event_core_opportunities.aggregate_core_opportunities((incident_hypothesis_row,))
    core = core_opportunities[0] if core_opportunities else None
    reported_impact_path = impact.impact_path_type
    reported_role = impact.candidate_role
    if not symbol and not coin_id:
        reported_impact_path = "generic_cooccurrence_only"
        reported_role = "generic_mention"
        reason_codes = tuple(dict.fromkeys((*reason_codes, "needs_identity_validation", "candidate_discovery_pending")))
    false_positive_reason = _false_positive_reason(
        identity_rejection=identity_rejection,
        impact_path_type=reported_impact_path,
        candidate_role=reported_role,
        incident_relevance_status=incident_relevance["incident_relevance_status"],
        source_class=evidence.source_class,
    )
    brief_section = _brief_section(
        opportunity_level=opportunity_level,
        route_tier=route_tier,
        identity_rejection=identity_rejection,
        false_positive_reason=false_positive_reason,
    )
    actual = {
        "impact_path_type": reported_impact_path,
        "candidate_role": reported_role,
        "claim_polarities": tuple(dict.fromkeys(claim.polarity for claim in claims)),
        "cause_status": event_claim_semantics.current_cause_status(claims, "exploit"),
        "event_archetype": archetype,
        "primary_subject": impact.primary_subject,
        "affected_ecosystem": impact.affected_ecosystem,
        "market_reaction_confirmed": market.level in {"weak", "moderate", "strong"},
        "causal_mechanism_confirmed": impact.cause_status == "confirmed" or (
            impact.impact_path_strength in {"strong", "medium"}
            and impact.impact_path_type != "market_dislocation_unknown"
            and impact.impact_path_reason not in {"alleged_exploit_unconfirmed", "cause_unknown_market_dislocation"}
        ),
        "evidence_specificity": evidence.evidence_specificity,
        "market_confirmation_level": market.level,
        "market_context_freshness_status": market.market_context_freshness_status,
        "market_context_age_hours": market.market_context_age_hours,
        "freshness_cap_applied": market.freshness_cap_applied,
        "opportunity_level": opportunity_level,
        "route_tier": route_tier,
        "digest_eligible": digest,
        "watchlist_eligible": watchlist,
        "high_priority_eligible": high_priority,
        "reason_codes": reason_codes,
        "blocked_reason": blocked,
        "triggered_fade": False,
        "identity_rejection_reason": identity_rejection,
        "incident_relevance_status": incident_relevance["incident_relevance_status"],
        "incident_relevance_score": incident_relevance["incident_relevance_score"],
        "canonical_persistence_reason": incident_relevance["canonical_persistence_reason"],
        "qualified_link_count": incident_relevance.get("qualified_link_count"),
        "weak_link_count": incident_relevance.get("weak_link_count"),
        "quality_blocked_link_count": incident_relevance.get("quality_blocked_link_count"),
        "unknown_role_link_count": incident_relevance.get("unknown_role_link_count"),
        "link_quality_reasons": incident_relevance.get("link_quality_reasons"),
        "diagnostic_hidden_by_default": incident_relevance["incident_relevance_status"] in {
            event_incident_store.RELEVANCE_RAW_OBSERVATION,
            event_incident_store.RELEVANCE_EXTERNAL_CONTEXT_ONLY,
            event_incident_store.RELEVANCE_DIAGNOSTIC_ONLY,
            event_incident_store.RELEVANCE_REJECTED_INCIDENT,
        },
        "external_context_hidden_by_default": incident_relevance["incident_relevance_status"]
        == event_incident_store.RELEVANCE_EXTERNAL_CONTEXT_ONLY,
        "selected_main_frame_type": incident.main_frame_type,
        "background_frame_count": _frame_role_count(incident.frame_summary, {"background_context", "historical_context"}),
        "negated_frame_count": _frame_role_count(incident.frame_summary, {"negated_claim", "corrective_context"}),
        "frame_rule_disagreement": bool(
            (raw.raw_json if isinstance(raw.raw_json, Mapping) else {})
            .get("llm_catalyst_frame_validation", {})
            .get("frame_rule_disagreement", False)
        ),
        "frame_disagreement_resolution": (
            (raw.raw_json if isinstance(raw.raw_json, Mapping) else {})
            .get("llm_catalyst_frame_validation", {})
            .get("resolution")
        ),
        "core_opportunity_id": core.core_opportunity_id if core is not None else None,
        "aggregation_status": "core_opportunity" if core is not None else "no_validated_core",
        "near_miss_inclusion": _near_miss_status(opportunity_level, route_tier, identity_rejection),
        "card_group": _card_group(opportunity_level, route_tier, identity_rejection),
        "brief_section": brief_section,
        "diagnostic_visibility": _diagnostic_visibility(brief_section),
        "false_positive_reason": false_positive_reason,
        "human_readable_reason": _human_readable_reason(blocked, identity_rejection, reason_codes),
        "frame_counter_status": "frame_present" if incident.main_frame_type else "frame_not_required_or_missing",
    }
    expected = _expected(case)
    diffs, stages = _diff_expected(expected, actual)
    return SignalQualityCaseResult(
        case_id=case_id,
        title=title,
        passed=not diffs,
        stage_failures=tuple(stages),
        expected=expected,
        actual=actual,
        diffs=tuple(diffs),
    )


def format_signal_quality_eval(result: SignalQualityEvalResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA SIGNAL QUALITY EVAL (offline fixtures; research-only)",
        "=" * 76,
        f"path: {result.path}",
        f"cases: {result.total_cases} · passed: {result.passed_cases} · failed: {result.failed_cases}",
    ]
    failures_by_stage: dict[str, int] = {}
    for case in result.case_results:
        for stage in case.stage_failures:
            failures_by_stage[stage] = failures_by_stage.get(stage, 0) + 1
    lines.append(
        "failures_by_stage: "
        + (", ".join(f"{stage}={count}" for stage, count in sorted(failures_by_stage.items())) or "none")
    )
    for case in result.case_results:
        status = "PASS" if case.passed else "FAIL"
        lines.append("")
        lines.append(f"{status} {case.case_id}: {case.title}")
        if case.passed:
            lines.append(
                "  actual: "
                f"path={case.actual.get('impact_path_type')} role={case.actual.get('candidate_role')} "
                f"market={case.actual.get('market_confirmation_level')} "
                f"freshness={case.actual.get('market_context_freshness_status')} "
                f"age_h={case.actual.get('market_context_age_hours')} "
                f"cap={case.actual.get('freshness_cap_applied')} "
                f"level={case.actual.get('opportunity_level')} route={case.actual.get('route_tier')} "
                f"core={case.actual.get('core_opportunity_id') or 'none'} "
                f"aggregation={case.actual.get('aggregation_status')} "
                f"near_miss={case.actual.get('near_miss_inclusion')} "
                f"card_group={case.actual.get('card_group')} "
                f"brief_section={case.actual.get('brief_section')} "
                f"diagnostic_visibility={case.actual.get('diagnostic_visibility')} "
                f"false_positive={case.actual.get('false_positive_reason')} "
                f"reason=\"{case.actual.get('human_readable_reason')}\" "
                f"frame_counter={case.actual.get('frame_counter_status')}"
            )
            continue
        for diff in case.diffs:
            lines.append(f"  diff: {diff}")
        lines.append("  expected: " + _compact(case.expected))
        lines.append("  actual: " + _compact(case.actual))
    lines.append("")
    lines.append("No live providers, Telegram sends, paper trades, normal RSI rows, or execution were used.")
    return "\n".join(lines).rstrip()


def _raw_event(case: Mapping[str, Any]) -> RawDiscoveredEvent:
    row = dict(case.get("raw_event") or {})
    fetched_at = _parse_dt(row.get("fetched_at")) or datetime(2026, 6, 15, tzinfo=timezone.utc)
    published_at = _parse_dt(row.get("published_at"))
    raw_json = dict(row.get("raw_json") or {})
    raw_json.setdefault("market", dict(case.get("market_snapshot") or {}))
    raw_json.setdefault("derivatives", dict(case.get("derivatives_snapshot") or {}))
    raw_json.setdefault("supply", dict(case.get("supply_snapshot") or {}))
    return RawDiscoveredEvent(
        raw_id=str(row.get("raw_id") or case.get("case_id") or "signal-quality-case"),
        provider=str(row.get("provider") or "fixture_signal_quality"),
        fetched_at=fetched_at,
        published_at=published_at,
        source_url=_optional_str(row.get("source_url")),
        title=str(row.get("title") or case.get("title") or ""),
        body=_optional_str(row.get("body")),
        raw_json=raw_json,
        source_confidence=float(row.get("source_confidence") or case.get("source_confidence") or 0.8),
        content_hash=str(row.get("content_hash") or row.get("raw_id") or case.get("case_id") or ""),
    )


def _frame_role_count(frame_summary: Iterable[Mapping[str, Any]], roles: set[str]) -> int:
    keys = {
        (
            str(frame.get("frame_type") or ""),
            str(frame.get("subject") or ""),
        )
        for frame in frame_summary
        if isinstance(frame, Mapping) and str(frame.get("frame_role") or "") in roles
    }
    return len(keys)


def _normalized_event_for_case(case: Mapping[str, Any], raw: RawDiscoveredEvent) -> NormalizedEvent:
    return NormalizedEvent(
        event_id=str(case.get("event_id") or case.get("case_id") or raw.raw_id),
        raw_ids=(raw.raw_id,),
        event_name=str(case.get("title") or raw.title or raw.raw_id),
        event_type=str(case.get("event_type") or case.get("impact_category") or "news"),
        event_time=None,
        event_time_confidence=0.0,
        first_seen_time=raw.fetched_at,
        source=str(raw.provider or "fixture_signal_quality"),
        source_urls=(raw.source_url,) if raw.source_url else (),
        external_asset=_optional_str(case.get("external_asset")),
        description=raw.body,
        confidence=float(case.get("source_confidence") or raw.source_confidence or 0.8),
    )


def _hypothesis(case: Mapping[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        impact_category=str(case.get("impact_category") or "market_anomaly_unknown"),
        external_asset=_optional_str(case.get("external_asset")),
        playbook_hint=_optional_str(case.get("playbook_hint")) or _optional_str(case.get("impact_category")),
        score_components=dict(case.get("score_components") or {}),
    )


def _incident_hypothesis_row(
    hypothesis: SimpleNamespace,
    *,
    incident_id: str,
    symbol: str | None,
    coin_id: str | None,
    impact: event_impact_path_validator.ImpactPathValidation,
    evidence: event_evidence_quality.EvidenceQualityResult,
    verdict: event_opportunity_verdict.OpportunityVerdict,
    opportunity_level: str,
    identity_rejection: str | None,
) -> dict[str, Any]:
    level = "local_only" if identity_rejection else opportunity_level
    return {
        "row_type": "event_impact_hypothesis",
        "hypothesis_id": f"signal-quality:{incident_id}",
        "incident_id": incident_id,
        "validated_symbol": None if identity_rejection else symbol,
        "validated_coin_id": None if identity_rejection else coin_id,
        "candidate_symbols": (symbol,) if symbol else (),
        "candidate_coin_ids": (coin_id,) if coin_id else (),
        "candidate_sectors": ("tokenized_stock_venues",) if not symbol and str(getattr(hypothesis, "impact_category", "")).endswith("_proxy") else (),
        "impact_category": getattr(hypothesis, "impact_category", None),
        "impact_path_type": impact.impact_path_type,
        "impact_path_strength": impact.impact_path_strength,
        "candidate_role": impact.candidate_role,
        "evidence_specificity": evidence.evidence_specificity,
        "source_class": evidence.source_class,
        "opportunity_level": level,
        "opportunity_score_final": 0.0 if identity_rejection else verdict.opportunity_score_final,
        "why_local_only": identity_rejection or verdict.why_local_only,
        "why_not_watchlist": identity_rejection or verdict.why_not_watchlist,
    }


def _expected(case: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in dict(case.get("expected") or {}).items()}


def _diff_expected(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    diffs: list[str] = []
    stages: list[str] = []
    stage_by_key = {
        "impact_path_type": "impact_path",
        "candidate_role": "candidate_role",
        "evidence_specificity": "evidence_quality",
        "market_confirmation_level": "market_confirmation",
        "market_context_freshness_status": "market_freshness",
        "market_context_age_hours": "market_freshness",
        "freshness_cap_applied": "market_freshness",
        "opportunity_level": "opportunity_verdict",
        "route_tier": "routing",
        "digest_eligible": "routing",
        "watchlist_eligible": "routing",
        "high_priority_eligible": "routing",
        "reason_codes": "opportunity_verdict",
        "blocked_reason": "opportunity_verdict",
        "triggered_fade": "routing",
        "identity_rejection_reason": "identity",
        "claim_polarities": "claim_semantics",
        "cause_status": "cause_status",
        "event_archetype": "incident_identity",
        "primary_subject": "primary_subject",
        "affected_ecosystem": "candidate_role",
        "market_reaction_confirmed": "market_reaction_vs_cause",
        "causal_mechanism_confirmed": "market_reaction_vs_cause",
        "incident_relevance_status": "incident_relevance",
        "incident_relevance_score": "incident_relevance",
        "canonical_persistence_reason": "incident_relevance",
        "qualified_link_count": "incident_relevance",
        "weak_link_count": "incident_relevance",
        "quality_blocked_link_count": "incident_relevance",
        "unknown_role_link_count": "incident_relevance",
        "link_quality_reasons": "incident_relevance",
        "diagnostic_hidden_by_default": "incident_relevance",
        "external_context_hidden_by_default": "incident_relevance",
        "selected_main_frame_type": "catalyst_frame",
        "background_frame_count": "catalyst_frame",
        "negated_frame_count": "catalyst_frame",
        "frame_rule_disagreement": "catalyst_frame",
        "frame_disagreement_resolution": "catalyst_frame",
        "core_opportunity_id": "core_aggregation",
        "aggregation_status": "core_aggregation",
        "near_miss_inclusion": "near_miss",
        "card_group": "research_card",
        "brief_section": "operator_brief",
        "diagnostic_visibility": "diagnostics",
        "false_positive_reason": "false_positive_filter",
        "human_readable_reason": "reason_text",
        "frame_counter_status": "catalyst_frame",
    }
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        ok = _matches(expected_value, actual_value)
        if not ok:
            diffs.append(f"{key}: expected {expected_value!r}, actual {actual_value!r}")
            stages.append(stage_by_key.get(key, key))
    return diffs, list(dict.fromkeys(stages))


def _matches(expected: Any, actual: Any) -> bool:
    if isinstance(expected, list):
        if key_set := {str(item) for item in expected if not str(item).startswith("contains:")}:
            if str(actual) in key_set:
                return True
        contains = [str(item).split("contains:", 1)[1] for item in expected if str(item).startswith("contains:")]
        if contains:
            values = actual if isinstance(actual, (list, tuple, set)) else (actual,)
            return any(str(value) in contains for value in values)
        return False
    if isinstance(expected, str) and expected.startswith("contains:"):
        needle = expected.split("contains:", 1)[1]
        values = actual if isinstance(actual, (list, tuple, set)) else (actual,)
        return any(str(value) == needle for value in values)
    return expected == actual


def _identity_rejection_reason(raw: RawDiscoveredEvent, *, symbol: str | None, coin_id: str | None) -> str | None:
    text = " ".join(str(value or "") for value in (raw.title, raw.body)).casefold()
    sym = str(symbol or "").upper()
    if sym == "BTC" and "bitcoin world" in text and "$btc" not in text and "btcusdt" not in text:
        return "publisher_source_name_not_asset_identity"
    if sym == "XRP" and "ripple effects" in text and "$xrp" not in text and "xrpusdt" not in text:
        return "common_phrase_not_asset_identity"
    if sym == "PRIME" and "prime minister" in text:
        return "common_word_or_title_not_asset_identity"
    if sym == "HYPE" and "hyperliquid" not in text and "$hype" not in text and "hypeusdt" not in text:
        return "generic_symbol_without_project_identity"
    return None


def _route_tier(level: str) -> str:
    return {
        "local_only": "STORE_ONLY",
        "exploratory": "STORE_ONLY",
        "validated_digest": "RADAR_DIGEST",
        "watchlist": "WATCHLIST",
        "high_priority": "HIGH_PRIORITY",
    }.get(level, "STORE_ONLY")


def _near_miss_status(level: str, route_tier: str, identity_rejection: str | None) -> str:
    if identity_rejection:
        return "diagnostic_not_near_miss"
    if level in {"validated_digest", "watchlist", "high_priority"} or route_tier in {
        "RADAR_DIGEST",
        "WATCHLIST",
        "HIGH_PRIORITY",
    }:
        return "excluded_already_promoted"
    return "eligible_if_close_to_threshold"


def _card_group(level: str, route_tier: str, identity_rejection: str | None) -> str:
    if identity_rejection:
        return "diagnostic_control"
    if level in {"validated_digest", "watchlist", "high_priority"} or route_tier in {
        "RADAR_DIGEST",
        "WATCHLIST",
        "HIGH_PRIORITY",
    }:
        return "core_opportunity"
    return "local_only_quality_capped"


def _brief_section(
    *,
    opportunity_level: str,
    route_tier: str,
    identity_rejection: str | None,
    false_positive_reason: str,
) -> str:
    if identity_rejection or false_positive_reason not in {"", "none"}:
        return "diagnostics"
    if opportunity_level == "high_priority" or route_tier == "HIGH_PRIORITY":
        return "high_priority_core"
    if opportunity_level == "watchlist" or route_tier == "WATCHLIST":
        return "watchlist_core"
    if opportunity_level == "validated_digest" or route_tier == "RADAR_DIGEST":
        return "validated_digest_core"
    if opportunity_level == "exploratory":
        return "near_miss"
    return "local_only_quality_capped"


def _diagnostic_visibility(brief_section: str) -> str:
    if brief_section == "diagnostics":
        return "hidden_by_default"
    if brief_section.endswith("_core"):
        return "main_section"
    return "review_section"


def _false_positive_reason(
    *,
    identity_rejection: str | None,
    impact_path_type: str,
    candidate_role: str,
    incident_relevance_status: str,
    source_class: str,
) -> str:
    text = " ".join(str(value or "") for value in (
        identity_rejection,
        impact_path_type,
        candidate_role,
        incident_relevance_status,
        source_class,
    )).casefold()
    if identity_rejection:
        if "publisher" in text or "source_name" in text or "source_origin" in text:
            return "source_noise"
        if "common" in text or "generic_symbol" in text or "ticker" in text:
            return "ticker_collision"
        return "identity_low_confidence"
    if "source_noise" in text or "publisher_suffix_false_positive" in text:
        return "source_noise"
    if "ticker_word_collision" in text:
        return "ticker_collision"
    if impact_path_type == "generic_cooccurrence_only":
        return "generic_cooccurrence_only"
    return "none"


def _human_readable_reason(
    blocked: Any,
    identity_rejection: str | None,
    reason_codes: Iterable[Any],
) -> str:
    if blocked not in (None, "", [], ()):
        values = blocked if isinstance(blocked, (list, tuple, set)) else (blocked,)
        return event_alpha_reason_text.humanize_event_alpha_reasons(values, limit=2)
    if identity_rejection:
        return event_alpha_reason_text.humanize_event_alpha_reason(identity_rejection)
    return event_alpha_reason_text.humanize_event_alpha_reasons(reason_codes, limit=2) or "qualified core opportunity"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _compact(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, default=str)[:1200]


# ---------------------------------------------------------------------------
# Moved from crypto_rsi_scanner/event_alpha_signal_quality_export.py
# ---------------------------------------------------------------------------
"""Export proposed Event Alpha signal-quality benchmark cases from artifacts."""


import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ... import event_alpha_quality_fields


@dataclass(frozen=True)
class EventAlphaSignalQualityExportResult:
    path: Path
    cases_written: int
    reasons: tuple[str, ...]


def export_signal_quality_cases(
    path: str | Path,
    *,
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
    hypothesis_rows: Iterable[Mapping[str, Any]] = (),
    generated_at: datetime | None = None,
) -> EventAlphaSignalQualityExportResult:
    """Write proposed benchmark cases from local artifacts only."""
    feedback_by_key = _feedback_by_key(feedback_rows)
    cases: list[dict[str, Any]] = []
    reasons: list[str] = []
    for row in alert_rows:
        if not isinstance(row, Mapping):
            continue
        feedback = _matching_feedback(row, feedback_by_key)
        reason = _case_reason(row, feedback=feedback)
        if not reason:
            continue
        cases.append(_case_from_row(row, reason=reason, feedback=feedback))
        reasons.append(reason)
    for row in hypothesis_rows:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("opportunity_level") or "") in {"local_only", "exploratory"}:
            cases.append(_case_from_row(row, reason="local_only_weak_hypothesis"))
            reasons.append("local_only_weak_hypothesis")
    for row in missed_rows:
        if not isinstance(row, Mapping):
            continue
        cases.append(_case_from_row(row, reason="missed_opportunity_recall_case"))
        reasons.append("missed_opportunity_recall_case")
    deduped = _dedupe_cases(cases)
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "event_alpha_signal_quality_proposed_cases_v1",
        "generated_at": (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        "research_only": True,
        "cases": deduped,
    }
    target.write_text(json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return EventAlphaSignalQualityExportResult(
        path=target,
        cases_written=len(deduped),
        reasons=tuple(dict.fromkeys(reasons)),
    )


def format_signal_quality_export_result(result: EventAlphaSignalQualityExportResult) -> str:
    return "\n".join([
        "=" * 76,
        "EVENT ALPHA SIGNAL-QUALITY CASE EXPORT (research-only)",
        "=" * 76,
        f"path: {result.path}",
        f"cases_written: {result.cases_written}",
        "reasons: " + (", ".join(result.reasons) or "none"),
        "Canonical fixtures were not modified. No sends, trades, paper rows, live RSI rows, or watchlist state were written.",
    ])


def _feedback_by_key(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        for key in _row_keys(row):
            out[key] = row
    return out


def _matching_feedback(row: Mapping[str, Any], feedback_by_key: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any] | None:
    return next((feedback_by_key[key] for key in _row_keys(row) if key in feedback_by_key), None)


def _case_reason(row: Mapping[str, Any], *, feedback: Mapping[str, Any] | None) -> str | None:
    label = str((feedback or {}).get("label") or (feedback or {}).get("feedback") or "").lower()
    if label == "useful":
        return "useful_feedback_positive_case"
    if label == "junk":
        return "junk_feedback_negative_case"
    if label == "watch":
        return "watch_feedback_borderline_case"
    if str(row.get("opportunity_level") or "") in {"local_only", "exploratory"}:
        return "local_only_weak_case"
    if row.get("rejected_candidate_assets") or row.get("rejected_validation_samples"):
        return "high_scoring_rejected_candidate"
    if str(row.get("tier") or "") in {"RADAR_DIGEST", "WATCHLIST", "HIGH_PRIORITY_WATCH"}:
        return "delivered_alert_candidate"
    return None


def _case_from_row(row: Mapping[str, Any], *, reason: str, feedback: Mapping[str, Any] | None = None) -> dict[str, Any]:
    components = event_alpha_quality_fields.quality_components(row)
    symbol = row.get("symbol") or row.get("validated_symbol")
    coin_id = row.get("coin_id") or row.get("validated_coin_id")
    feedback_label = (feedback or {}).get("label") or (feedback or {}).get("feedback")
    expected_level = _expected_level_for_case(row, reason=reason, feedback_label=feedback_label)
    return {
        "case_id": _safe_case_id(row, reason),
        "reason_to_add_case": reason,
        "raw_evidence_summary": row.get("event_name") or row.get("latest_event_name") or row.get("title") or row.get("hypothesis_id") or "artifact row",
        "candidate_symbol": symbol,
        "candidate_coin_id": coin_id,
        "core_opportunity_id": row.get("core_opportunity_id") or (feedback or {}).get("core_opportunity_id"),
        "feedback_target": (feedback or {}).get("feedback_target") or (feedback or {}).get("target") or row.get("feedback_target"),
        "external_asset": row.get("external_asset"),
        "source_metadata": {
            "source": row.get("source") or row.get("latest_source"),
            "source_class": components.get("source_class"),
            "source_provider": row.get("source_provider") or (feedback or {}).get("source_provider"),
            "source_domain": row.get("source_domain") or (feedback or {}).get("source_domain"),
            "source_pack": row.get("source_pack") or (feedback or {}).get("source_pack"),
            "evidence_specificity": components.get("evidence_specificity"),
        },
        "impact_path": {
            "impact_path_type": components.get("impact_path_type"),
            "impact_path_strength": components.get("impact_path_strength"),
            "candidate_role": components.get("candidate_role"),
        },
        "market_confirmation": {
            "market_confirmation_score": components.get("market_confirmation_score"),
            "market_confirmation_level": components.get("market_confirmation_level"),
        },
        "evidence_quality": {
            "evidence_quality_score": components.get("evidence_quality_score"),
            "source_class": components.get("source_class"),
            "evidence_specificity": components.get("evidence_specificity"),
        },
        "opportunity": {
            "opportunity_score_final": components.get("opportunity_score_final"),
            "opportunity_level": components.get("opportunity_level"),
            "opportunity_verdict_reasons": components.get("opportunity_verdict_reasons") or [],
            "why_local_only": components.get("why_local_only"),
            "why_not_watchlist": components.get("why_not_watchlist"),
        },
        "expected_opportunity_level": expected_level,
        "expected_route_behavior": _expected_route_behavior(expected_level),
        "expected_current_decision": row.get("route") or row.get("tier") or row.get("latest_tier") or components.get("opportunity_level"),
        "suggested_expected_label": feedback_label,
        "why_this_should_become_eval_case": _why_eval_case(reason, feedback=feedback),
        "feedback": dict(feedback or {}),
    }


def _expected_level_for_case(row: Mapping[str, Any], *, reason: str, feedback_label: object) -> str:
    label = str(feedback_label or "").lower()
    if label == "junk" or "negative" in reason:
        return "local_only"
    if label == "useful" or "positive" in reason:
        return str(row.get("opportunity_level") or row.get("final_opportunity_level") or "validated_digest")
    if label == "watch":
        return "watchlist"
    if "missed" in reason:
        return "watchlist_or_validated_digest"
    return str(row.get("opportunity_level") or row.get("final_opportunity_level") or "review")


def _expected_route_behavior(level: str) -> str:
    if level in {"local_only", "exploratory"}:
        return "store_only_or_local_report"
    if level in {"watchlist", "watchlist_or_validated_digest"}:
        return "watchlist_if_quality_gates_pass"
    if level == "high_priority":
        return "high_priority_if_quality_gates_pass"
    return "research_digest_if_quality_gates_pass"


def _why_eval_case(reason: str, *, feedback: Mapping[str, Any] | None) -> str:
    note = str((feedback or {}).get("notes") or "").strip()
    if note:
        return f"{reason}: {note}"
    if reason == "missed_opportunity_recall_case":
        return "missed opportunity should test source/resolver/quality recall"
    if reason == "junk_feedback_negative_case":
        return "operator marked this as junk; preserve or tighten rejection behavior"
    if reason == "useful_feedback_positive_case":
        return "operator marked this as useful; preserve or improve promotion behavior"
    if reason == "watch_feedback_borderline_case":
        return "operator marked this as watch; keep as threshold/borderline eval"
    return reason


def _safe_case_id(row: Mapping[str, Any], reason: str) -> str:
    raw = str(row.get("alert_id") or row.get("alert_key") or row.get("key") or row.get("hypothesis_id") or row.get("symbol") or "case")
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in raw).strip("_")[:60] or "case"
    return f"{cleaned}_{reason}"


def _key(row: Mapping[str, Any]) -> str:
    return str(row.get("alert_key") or row.get("alert_id") or row.get("key") or row.get("hypothesis_id") or "")


def _row_keys(row: Mapping[str, Any]) -> tuple[str, ...]:
    keys: list[str] = []
    for field in (
        "key",
        "target",
        "feedback_target",
        "core_opportunity_id",
        "alert_key",
        "alert_id",
        "card_id",
        "hypothesis_id",
        "incident_id",
        "symbol",
        "coin_id",
        "asset_symbol",
        "asset_coin_id",
        "validated_symbol",
        "validated_coin_id",
    ):
        value = str(row.get(field) or "").strip()
        if not value:
            continue
        keys.append(value)
        if value.startswith("ea:"):
            keys.append(value[3:])
        else:
            keys.append(f"ea:{value}")
    return tuple(dict.fromkeys(keys))


def _dedupe_cases(cases: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for case in cases:
        key = str(case.get("case_id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(dict(case))
    return out


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


# ---------------------------------------------------------------------------
# Moved from crypto_rsi_scanner/event_alpha_tuning.py
# ---------------------------------------------------------------------------
"""Weekly tuning worksheet for Event Alpha research artifacts."""


from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class EventAlphaTuningSuggestion:
    area: str
    recommendation: str
    evidence: str
    action_type: str = "manual_review"


@dataclass(frozen=True)
class EventAlphaTuningWorksheet:
    alert_rows: int
    feedback_rows: int
    missed_rows: int
    run_rows: int
    suggestions: tuple[EventAlphaTuningSuggestion, ...]


def build_tuning_worksheet(
    *,
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
    run_rows: Iterable[Mapping[str, Any]] = (),
    priors_shadow_rows: Iterable[Mapping[str, Any]] = (),
) -> EventAlphaTuningWorksheet:
    """Build deterministic threshold/source suggestions without applying them."""
    alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    missed = [dict(row) for row in missed_rows if isinstance(row, Mapping)]
    runs = [dict(row) for row in run_rows if isinstance(row, Mapping)]
    suggestions: list[EventAlphaTuningSuggestion] = []
    suggestions.extend(_playbook_feedback_suggestions(alerts, feedback))
    suggestions.extend(_source_feedback_suggestions(alerts, feedback))
    suggestions.extend(_missed_suggestions(missed))
    suggestions.extend(_run_suggestions(runs))
    suggestions.extend(_priors_suggestions(priors_shadow_rows))
    if not suggestions:
        suggestions.append(EventAlphaTuningSuggestion(
            area="sample",
            recommendation="collect more burn-in rows before changing thresholds",
            evidence=f"alerts={len(alerts)} feedback={len(feedback)} missed={len(missed)} runs={len(runs)}",
        ))
    return EventAlphaTuningWorksheet(
        alert_rows=len(alerts),
        feedback_rows=len(feedback),
        missed_rows=len(missed),
        run_rows=len(runs),
        suggestions=tuple(dict.fromkeys(suggestions)),
    )


def format_tuning_worksheet(worksheet: EventAlphaTuningWorksheet) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA WEEKLY TUNING WORKSHEET (research-only)",
        "=" * 76,
        (
            "inputs: "
            f"alerts={worksheet.alert_rows} feedback={worksheet.feedback_rows} "
            f"missed={worksheet.missed_rows} runs={worksheet.run_rows}"
        ),
        "",
        "suggestions:",
    ]
    for item in worksheet.suggestions:
        lines.append(f"- [{item.area}] {item.recommendation}")
        lines.append(f"  evidence: {item.evidence}")
        lines.append(f"  action: {item.action_type}")
    lines.append("No thresholds, priors, alert tiers, paper trades, live DB rows, or execution were changed.")
    return "\n".join(lines).rstrip()


def _playbook_feedback_suggestions(
    alerts: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
) -> tuple[EventAlphaTuningSuggestion, ...]:
    feedback_by_key = _feedback_labels_by_key(feedback)
    counts: dict[str, dict[str, int]] = {}
    for row in alerts:
        key = str(row.get("alert_key") or row.get("key") or "")
        labels = feedback_by_key.get(key, ())
        if not labels:
            continue
        playbook = str(row.get("playbook_type") or row.get("effective_playbook_type") or "unknown")
        bucket = counts.setdefault(playbook, {"useful": 0, "junk": 0, "watch": 0})
        for label in labels:
            if label in bucket:
                bucket[label] += 1
    out: list[EventAlphaTuningSuggestion] = []
    for playbook, bucket in sorted(counts.items()):
        useful = bucket.get("useful", 0) + bucket.get("watch", 0)
        junk = bucket.get("junk", 0)
        if junk >= 2 and junk > useful:
            out.append(EventAlphaTuningSuggestion(
                area=f"playbook:{playbook}",
                recommendation="consider raising this playbook's alert threshold or requiring stronger identity/source evidence",
                evidence=f"junk={junk} useful_or_watch={useful}",
                action_type="threshold_review",
            ))
        elif useful >= 2 and useful > junk:
            out.append(EventAlphaTuningSuggestion(
                area=f"playbook:{playbook}",
                recommendation="consider preserving this playbook's current threshold and collecting more outcomes before any boost",
                evidence=f"useful_or_watch={useful} junk={junk}",
                action_type="prior_review",
            ))
    return tuple(out)


def _source_feedback_suggestions(
    alerts: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
) -> tuple[EventAlphaTuningSuggestion, ...]:
    feedback_by_key = _feedback_labels_by_key(feedback)
    counts: dict[str, dict[str, int]] = {}
    for row in alerts:
        key = str(row.get("alert_key") or row.get("key") or "")
        labels = feedback_by_key.get(key, ())
        if not labels:
            continue
        source = str(row.get("source") or row.get("source_provider") or "unknown")
        bucket = counts.setdefault(source, {"useful": 0, "junk": 0, "watch": 0})
        for label in labels:
            if label in bucket:
                bucket[label] += 1
    out: list[EventAlphaTuningSuggestion] = []
    for source, bucket in sorted(counts.items()):
        useful = bucket.get("useful", 0) + bucket.get("watch", 0)
        junk = bucket.get("junk", 0)
        if junk >= 2 and junk > useful:
            out.append(EventAlphaTuningSuggestion(
                area=f"source:{source}",
                recommendation="consider demoting or adding extra review gates for this source",
                evidence=f"junk={junk} useful_or_watch={useful}",
                action_type="source_prior_review",
            ))
    return tuple(out)


def _missed_suggestions(missed: list[dict[str, Any]]) -> tuple[EventAlphaTuningSuggestion, ...]:
    counts: dict[str, int] = {}
    for row in missed:
        stage = str(row.get("failure_stage") or "unknown")
        counts[stage] = counts.get(stage, 0) + 1
    out: list[EventAlphaTuningSuggestion] = []
    for stage, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        if count < 2:
            continue
        if stage == "resolver_missed_asset":
            recommendation = "add resolver aliases/eval cases for repeatedly missed assets"
        elif stage == "no_source_event":
            recommendation = "review source coverage or catalyst-search queries for this missed cohort"
        elif stage == "watchlist_not_escalated":
            recommendation = "review watchlist escalation thresholds and market-confirmation requirements"
        else:
            recommendation = "review repeated missed-opportunity stage before tuning thresholds"
        out.append(EventAlphaTuningSuggestion(
            area=f"missed:{stage}",
            recommendation=recommendation,
            evidence=f"missed_count={count}",
            action_type="eval_case_review",
        ))
    return tuple(out)


def _run_suggestions(runs: list[dict[str, Any]]) -> tuple[EventAlphaTuningSuggestion, ...]:
    if not runs:
        return (EventAlphaTuningSuggestion(
            area="runs",
            recommendation="schedule daily no-key burn-in before tuning",
            evidence="run ledger is empty",
            action_type="operations",
        ),)
    failures = sum(1 for row in runs if not bool(row.get("success")))
    if failures:
        return (EventAlphaTuningSuggestion(
            area="runs",
            recommendation="fix run failures before interpreting alert precision or recall",
            evidence=f"failed_runs={failures} total_runs={len(runs)}",
            action_type="operations",
        ),)
    return ()


def _priors_suggestions(rows: Iterable[Mapping[str, Any]]) -> tuple[EventAlphaTuningSuggestion, ...]:
    data = [dict(row) for row in rows if isinstance(row, Mapping)]
    if not data:
        return ()
    changed = sum(1 for row in data if row.get("tier_before") != row.get("tier_after"))
    if changed:
        return (EventAlphaTuningSuggestion(
            area="priors_shadow",
            recommendation="review priors shadow rows before applying calibration priors",
            evidence=f"tier_changes={changed}",
            action_type="prior_review",
        ),)
    return ()


def _feedback_labels_by_key(feedback: list[dict[str, Any]]) -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {}
    for row in feedback:
        key = str(row.get("key") or row.get("target") or "")
        if key:
            out.setdefault(key, []).append(str(row.get("label") or ""))
    return {key: tuple(value for value in values if value) for key, values in out.items()}
