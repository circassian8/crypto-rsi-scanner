"""Event Alpha signal-quality review reports for local artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from . import event_alpha_artifacts, event_alpha_quality_fields, event_opportunity_verdict, event_watchlist


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
        "evidence_specificity: " + _format_counts(_counts(rows, "evidence_specificity")),
        "market_confirmation_levels: " + _format_counts(_counts(rows, "market_confirmation_level")),
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
    lines.extend(["", "Top upgrade candidates:"])
    lines.extend(_upgrade_lines(rows, limit=6))
    lines.extend(["", "Top downgrade risks:"])
    lines.extend(_downgrade_lines(rows, limit=6))
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
        "state": entry.state,
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
        "candidates_added": 0,
        "candidates_validated": 0,
        "candidates_promoted": 0,
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
        out["false_positive_rejections"] += sum(1 for item in rejected if isinstance(item, Mapping) and _rejection_is_false_positive(item))
        for item in rejected:
            if not isinstance(item, Mapping):
                continue
            reason = str(item.get("reason") or item.get("rejection_reason") or item.get("identity_reason") or "unknown_rejection")
            if reason:
                out[f"rejected_{reason}"] = out.get(f"rejected_{reason}", 0) + 1
        out["candidates_added"] += candidate_like
        if str(row.get("validation_stage") or "") in {"catalyst_link_validated", "impact_path_validated", "market_confirmed", "promoted_to_radar"}:
            out["candidates_validated"] += 1
            out["context_validated_candidates"] += 1
        if str(row.get("opportunity_level") or "") in {"validated_digest", "watchlist", "high_priority"}:
            out["candidates_promoted"] += 1
            out["promoted_candidates"] += 1
    return out


def _candidate_like_term(item: Mapping[str, Any]) -> bool:
    symbol = str(item.get("symbol") or "").strip()
    coin_id = str(item.get("coin_id") or "").strip()
    name = str(item.get("name") or item.get("project_name") or "").strip()
    reason = str(item.get("reason") or item.get("rejection_reason") or item.get("identity_reason") or "").casefold()
    if any(token in reason for token in ("source_noise", "publisher", "word_collision", "url_only", "generic_symbol")):
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
    needles = ("source_noise", "ticker_collision", "word_collision", "generic_cooccurrence", "identity")
    return [
        row for row in rows
        if any(needle in str(row).lower() for needle in needles)
    ]


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


def _quality_gate_conflict(row: Mapping[str, Any]) -> bool:
    if row.get("quality_gate_block_reason"):
        return True
    route_alertable = bool(row.get("route_alertable"))
    route = str(row.get("route") or "")
    if not route_alertable and route not in {"RESEARCH_DIGEST", "HIGH_PRIORITY_RESEARCH"}:
        return False
    if route == "TRIGGERED_FADE_RESEARCH":
        return False
    return _quality_gate_conflict_reason(row) != "none"


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
    if not rows:
        return ["- none"]
    out = []
    for row in sorted(rows, key=lambda item: float(item.get("opportunity_score_final") or item.get("latest_score") or item.get("hypothesis_score") or 0), reverse=True)[:limit]:
        label = row.get("symbol") or row.get("validated_symbol") or row.get("coin_id") or row.get("hypothesis_id") or row.get("event_id") or "candidate"
        out.append(
            f"- {label}: level={row.get('opportunity_level') or 'unknown'} "
            f"market={row.get('market_confirmation_level') or 'unknown'} "
            f"path={row.get('impact_path_type') or 'unknown'} "
            f"source={row.get('source_class') or 'unknown'}/{row.get('evidence_specificity') or 'unknown'}"
        )
    return out


def _upgrade_lines(rows: list[dict[str, Any]], *, limit: int) -> list[str]:
    candidates = []
    for row in rows:
        upgrade = event_opportunity_verdict.explain_upgrade_path(components=row.get("_components") or row)
        if not upgrade.upgrade_requirements:
            continue
        candidates.append((float(row.get("opportunity_score_final") or row.get("latest_score") or 0), row, upgrade))
    if not candidates:
        return ["- none"]
    out = []
    for _score, row, upgrade in sorted(candidates, key=lambda item: item[0], reverse=True)[:limit]:
        out.append(f"- {_label(row)}: {', '.join(upgrade.upgrade_requirements[:3])}")
    return out


def _downgrade_lines(rows: list[dict[str, Any]], *, limit: int) -> list[str]:
    candidates = []
    for row in rows:
        upgrade = event_opportunity_verdict.explain_upgrade_path(components=row.get("_components") or row)
        if not upgrade.downgrade_warnings:
            continue
        candidates.append((float(row.get("opportunity_score_final") or row.get("latest_score") or 0), row, upgrade))
    if not candidates:
        return ["- none"]
    out = []
    for _score, row, upgrade in sorted(candidates, key=lambda item: item[0], reverse=True)[:limit]:
        out.append(f"- {_label(row)}: {', '.join(upgrade.downgrade_warnings[:3])}")
    return out


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


def _label(row: Mapping[str, Any]) -> str:
    return str(row.get("symbol") or row.get("validated_symbol") or row.get("coin_id") or row.get("hypothesis_id") or row.get("alert_id") or "candidate")
