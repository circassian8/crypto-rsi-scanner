"""Research-only outcomes and calibration for integrated Event Alpha radar."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping

from ..artifacts import paths as event_artifact_paths
from ..artifacts import schema_v1
from ..radar import integrated_radar as event_integrated_radar
from ..radar.decision_model_surfaces import decision_model_values


HORIZONS = ("15m", "1h", "4h", "24h", "3d", "7d")
CORE_OPPORTUNITIES_FILENAME = "event_core_opportunities.jsonl"
ALPHA_NOTIFICATION_DELIVERIES_FILENAME = "event_alpha_notification_deliveries.jsonl"
PERFORMANCE_DIMENSIONS = (
    "opportunity_type",
    "source_origin",
    "source_pack",
    "provider",
    "market_state_class",
    "crowding_class",
    "source_strength",
    "thesis_origin",
    "catalyst_status",
    "confidence_band",
    "actionability_score_cohort",
    "anomaly_type",
    "radar_route",
    "tradability_status",
)
PERFORMANCE_LANES = (
    "EARLY_LONG_RESEARCH",
    "CONFIRMED_LONG_RESEARCH",
    "FADE_SHORT_REVIEW",
    "RISK_ONLY",
    "UNCONFIRMED_RESEARCH",
)
MATURED_STATES = ("partially_matured", "matured")


def fill_integrated_radar_outcomes(
    namespace_dir: str | Path,
    *,
    observed_at: datetime | str | None = None,
) -> tuple[dict[str, Any], ...]:
    """Fill deterministic, research-only outcomes for integrated radar candidates."""
    base = Path(namespace_dir)
    candidates = _read_jsonl(base / event_integrated_radar.INTEGRATED_CANDIDATES_FILENAME)
    now = _iso(_parse_time(observed_at) or datetime.now(timezone.utc))
    outcomes_path = base / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME
    rows = tuple(schema_v1.stamp_artifact_row(_outcome_row(candidate, now=now), path=outcomes_path) for candidate in candidates)
    _write_jsonl(outcomes_path, rows)
    report = format_integrated_radar_outcome_report(rows)
    (base / event_integrated_radar.INTEGRATED_OUTCOME_REPORT_FILENAME).write_text(report, encoding="utf-8")
    calibration = format_integrated_radar_calibration_report(rows)
    (base / event_integrated_radar.INTEGRATED_CALIBRATION_REPORT_FILENAME).write_text(calibration, encoding="utf-8")
    priors = build_integrated_radar_calibration_priors(rows)
    _write_json(base / event_integrated_radar.INTEGRATED_CALIBRATION_PRIORS_FILENAME, priors)
    return rows


def load_integrated_radar_outcomes(namespace_dir: str | Path) -> tuple[dict[str, Any], ...]:
    return tuple(_read_jsonl(Path(namespace_dir) / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME))


def write_radar_performance_dashboard(
    namespace_dirs: Iterable[str | Path],
    *,
    output_namespace_dir: str | Path | None = None,
    generated_at: datetime | str | None = None,
    min_sample: int = 25,
    stale_after_days: int = 14,
) -> dict[str, Any]:
    """Write cross-namespace, recommendation-only radar performance artifacts."""
    dirs = tuple(namespace_dirs)
    payload = build_radar_provider_performance(
        dirs,
        generated_at=generated_at,
        min_sample=min_sample,
        stale_after_days=stale_after_days,
    )
    output = Path(output_namespace_dir) if output_namespace_dir is not None else _first_namespace_dir(dirs)
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / event_integrated_radar.RADAR_PROVIDER_PERFORMANCE_FILENAME, payload)
    dashboard = format_radar_performance_dashboard(payload)
    (output / event_integrated_radar.RADAR_PERFORMANCE_DASHBOARD_FILENAME).write_text(dashboard, encoding="utf-8")
    return payload


def build_radar_provider_performance(
    namespace_dirs: Iterable[str | Path],
    *,
    generated_at: datetime | str | None = None,
    min_sample: int = 25,
    stale_after_days: int = 14,
) -> dict[str, Any]:
    generated = _iso(_parse_time(generated_at) or datetime.now(timezone.utc))
    namespace_inputs = [_namespace_inputs(Path(path), generated_at=generated, stale_after_days=stale_after_days) for path in namespace_dirs]
    rows = [row for inputs in namespace_inputs for row in inputs["rows"]]
    main_rows = [
        row for row in rows
        if row.get("opportunity_type") != "DIAGNOSTIC"
        and str(row.get("radar_route") or "").casefold() != "diagnostic"
    ]
    diagnostic_count = len(rows) - len(main_rows)
    maturation_counts = Counter(str(row.get("maturation_state") or "unknown") for row in main_rows)
    lane_summaries = _dimension_summary(main_rows, "opportunity_type")
    dimension_summaries = {dimension: _dimension_summary(main_rows, dimension) for dimension in PERFORMANCE_DIMENSIONS}
    provider_performance = dimension_summaries["provider"]
    performance_views = _performance_views(main_rows)
    source_pack_suggestions = {
        key: _prior_suggestion(key, group, generated_at=generated, min_sample=min_sample)
        for key, group in sorted(_group_rows_by_dimension(main_rows, "source_pack").items())
    }
    provider_suggestions = {
        key: _prior_suggestion(key, group, generated_at=generated, min_sample=min_sample)
        for key, group in sorted(_group_rows_by_dimension(main_rows, "provider").items())
    }
    lane_suggestions = {
        key: _prior_suggestion(key, group, generated_at=generated, min_sample=min_sample)
        for key, group in sorted(_group_rows_by_dimension(main_rows, "opportunity_type").items())
    }
    return {
        "schema_version": 1,
        "row_type": "event_radar_provider_performance",
        "generated_at": generated,
        "research_only": True,
        "recommendation_only": True,
        "auto_apply": False,
        "eligible_for_auto_apply": False,
        "thresholds_changed": False,
        "min_sample_size": min_sample,
        "source_namespaces": [
            {
                "namespace": item["namespace"],
                "path": item["path"],
                "candidates_read": item["candidates_read"],
                "core_opportunities_read": item["core_opportunities_read"],
                "outcomes_read": item["outcomes_read"],
                "deliveries_read": item["deliveries_read"],
            }
            for item in namespace_inputs
        ],
        "rows_evaluated": len(main_rows),
        "diagnostic_rows_excluded": diagnostic_count,
        "maturation_counts": dict(sorted(maturation_counts.items())),
        "main_aggregate": _aggregate_summary(main_rows),
        "lane_summaries": lane_summaries,
        "dimension_summaries": dimension_summaries,
        "performance_views": performance_views,
        "provider_performance": provider_performance,
        "source_pack_prior_suggestions": source_pack_suggestions,
        "provider_prior_suggestions": provider_suggestions,
        "lane_threshold_suggestions": lane_suggestions,
        "safety": {
            "research_only": True,
            "recommendation_only": True,
            "auto_apply": False,
            "thresholds_changed": False,
            "normal_rsi_signal_rows_written": 0,
            "triggered_fade_created": 0,
            "telegram_sends": 0,
        },
    }


def format_radar_performance_dashboard(payload: Mapping[str, Any]) -> str:
    views = payload.get("performance_views") if isinstance(payload.get("performance_views"), Mapping) else {}
    provider_performance = payload.get("provider_performance") if isinstance(payload.get("provider_performance"), Mapping) else {}
    maturation = payload.get("maturation_counts") if isinstance(payload.get("maturation_counts"), Mapping) else {}
    lines = [
        "# Event Alpha Radar Performance Dashboard",
        "",
        "Research-only dashboard. Recommendations only. Thresholds are not changed automatically.",
        "",
        "## Summary",
        f"- Namespaces: {len(payload.get('source_namespaces') or ())}",
        f"- Evaluated rows: {int(payload.get('rows_evaluated') or 0)}",
        f"- Diagnostics excluded: {int(payload.get('diagnostic_rows_excluded') or 0)}",
        f"- Maturation: {_format_counts(Counter({str(k): int(v) for k, v in dict(maturation).items()}))}",
        f"- Threshold changes applied: {str(bool(payload.get('thresholds_changed'))).lower()}",
        "",
        "## Performance Views",
    ]
    for key in (
        "early_long_conversion_rate",
        "confirmed_long_continuation_rate",
        "fade_review_exhaustion_rate",
        "risk_only_validation_rate",
        "unconfirmed_later_confirmation_noise_rate",
    ):
        view = views.get(key) if isinstance(views, Mapping) else None
        if not isinstance(view, Mapping):
            continue
        lines.append(
            f"- {key}: rows={int(view.get('rows') or 0)} matured={int(view.get('matured_rows') or 0)} "
            f"validated={int(view.get('validated_count') or view.get('later_confirmation_count') or 0)} "
            f"noise={int(view.get('noise_count') or view.get('invalidated_noise_count') or 0)} "
            f"rate={_rate_text(view.get('rate') if view.get('rate') is not None else view.get('later_confirmation_rate'))}"
        )
    lines.extend(["", "## Provider Usefulness"])
    if not provider_performance:
        lines.append("- None yet.")
    for provider, summary in sorted(provider_performance.items()):
        if not isinstance(summary, Mapping):
            continue
        lines.append(
            f"- {provider}: rows={int(summary.get('rows') or 0)} matured={int(summary.get('matured_rows') or 0)} "
            f"usefulness={_rate_text(summary.get('validation_rate'))} "
            f"noise={_rate_text(summary.get('noise_rate'))} "
            f"avg_time_to_confirmation_hours={_number_text(summary.get('average_time_to_confirmation_hours'))}"
        )
    lines.extend(["", "## Recommendation-Only Priors"])
    for section_key, title in (
        ("source_pack_prior_suggestions", "Source Packs"),
        ("provider_prior_suggestions", "Providers"),
        ("lane_threshold_suggestions", "Lanes"),
    ):
        lines.append(f"### {title}")
        suggestions = payload.get(section_key) if isinstance(payload.get(section_key), Mapping) else {}
        if not suggestions:
            lines.append("- None yet.")
            continue
        for key, suggestion in sorted(suggestions.items()):
            if not isinstance(suggestion, Mapping):
                continue
            lines.append(
                f"- {key}: sample={int(suggestion.get('sample_size') or 0)} "
                f"min_sample_warning={str(bool(suggestion.get('min_sample_warning'))).lower()} "
                f"validation_rate={_rate_text(suggestion.get('validation_rate'))} "
                f"auto_apply={str(bool(suggestion.get('auto_apply'))).lower()} "
                f"recommendation={suggestion.get('recommendation') or 'insufficient_sample'}"
            )
    return "\n".join(lines).rstrip() + "\n"


def format_radar_learning_snapshot(payload: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(payload, Mapping):
        return ("- Dashboard not available yet.",)
    views = payload.get("performance_views") if isinstance(payload.get("performance_views"), Mapping) else {}
    provider_performance = payload.get("provider_performance") if isinstance(payload.get("provider_performance"), Mapping) else {}
    maturation = payload.get("maturation_counts") if isinstance(payload.get("maturation_counts"), Mapping) else {}
    lines = [
        f"- Dashboard: {event_integrated_radar.RADAR_PERFORMANCE_DASHBOARD_FILENAME}",
        f"- Evaluated rows: {int(payload.get('rows_evaluated') or 0)}",
        f"- Maturation: {_format_counts(Counter({str(k): int(v) for k, v in dict(maturation).items()}))}",
        "- Recommendations only; no automatic threshold changes were applied.",
    ]
    early = views.get("early_long_conversion_rate") if isinstance(views, Mapping) else None
    fade = views.get("fade_review_exhaustion_rate") if isinstance(views, Mapping) else None
    if isinstance(early, Mapping):
        lines.append(f"- Early-long conversion rate: {_rate_text(early.get('rate'))}")
    if isinstance(fade, Mapping):
        lines.append(f"- Fade-review exhaustion rate: {_rate_text(fade.get('rate'))}")
    ranked = sorted(
        (
            (str(provider), summary)
            for provider, summary in provider_performance.items()
            if isinstance(summary, Mapping)
        ),
        key=lambda item: (float(item[1].get("validated_count") or 0), float(item[1].get("rows") or 0)),
        reverse=True,
    )
    if ranked:
        provider, summary = ranked[0]
        lines.append(
            f"- Top provider by validated research rows: {provider} "
            f"({int(summary.get('validated_count') or 0)}/{int(summary.get('rows') or 0)})"
        )
    return tuple(lines)


def format_integrated_radar_outcome_report(rows: Iterable[Mapping[str, Any]]) -> str:
    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    performance_rows = [row for row in materialized if _truthy(row.get("include_in_performance"))]
    diagnostic_rows = [row for row in materialized if not _truthy(row.get("include_in_performance"))]
    status_counts = Counter(str(row.get("outcome_status") or "unknown") for row in materialized)
    lane_counts = Counter(str(row.get("opportunity_type") or "unknown") for row in performance_rows)
    lines = [
        "# Event Alpha Integrated Radar Outcome Report",
        "",
        event_integrated_radar.RESEARCH_DISCLAIMER,
        "Research-only outcomes from fixtures/cached rows. No trades or paper trades are created.",
        "",
        "## Summary",
        f"- Outcome rows: {len(materialized)}",
        f"- Performance rows: {len(performance_rows)}",
        f"- Diagnostics excluded from performance: {len(diagnostic_rows)}",
        f"- Status: {_format_counts(status_counts)}",
        f"- Lanes: {_format_counts(lane_counts)}",
        "",
        "## Outcomes By Lane",
    ]
    by_lane: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in performance_rows:
        by_lane[str(row.get("opportunity_type") or "unknown")].append(row)
    for lane in sorted(by_lane):
        lane_rows = by_lane[lane]
        returns = [float(row.get("primary_horizon_return") or 0.0) for row in lane_rows if row.get("outcome_status") == "filled"]
        thesis_returns = [
            float(row.get("thesis_primary_move") or 0.0)
            for row in lane_rows
            if row.get("outcome_status") == "filled" and row.get("thesis_primary_move") is not None
        ]
        thesis_favorable = [
            float(row.get("thesis_favorable_excursion") or 0.0)
            for row in lane_rows
            if row.get("outcome_status") == "filled" and row.get("thesis_favorable_excursion") is not None
        ]
        lines.append(f"### {lane}")
        lines.append(f"- Rows: {len(lane_rows)}")
        lines.append(f"- Median asset primary return: {_pct(median(returns)) if returns else 'n/a'}")
        lines.append(f"- Median thesis primary move: {_pct(median(thesis_returns)) if thesis_returns else 'n/a'}")
        lines.append(f"- Median thesis-favorable move: {_pct(median(thesis_favorable)) if thesis_favorable else 'n/a'}")
        for row in lane_rows[:10]:
            lines.append(
                f"- {row.get('symbol')}/{row.get('coin_id')} label={row.get('outcome_label')} "
                f"asset={_pct(row.get('primary_horizon_return')) if row.get('primary_horizon_return') is not None else 'n/a'} "
                f"thesis={_pct(row.get('thesis_primary_move')) if row.get('thesis_primary_move') is not None else 'n/a'} "
                f"status={row.get('outcome_status')}"
            )
    if diagnostic_rows:
        lines.extend(["", "## Diagnostics Appendix"])
        lines.append("DIAGNOSTIC rows are excluded from performance and calibration priors.")
        for row in diagnostic_rows[:10]:
            lines.append(
                f"- {row.get('symbol')}/{row.get('coin_id')} lane={row.get('opportunity_type')} "
                f"label={row.get('outcome_label')} status={row.get('outcome_status')}"
            )
    return "\n".join(lines).rstrip() + "\n"


def format_integrated_radar_calibration_report(rows: Iterable[Mapping[str, Any]]) -> str:
    all_rows = [dict(row) for row in rows if isinstance(row, Mapping)]
    materialized = [row for row in all_rows if _truthy(row.get("include_in_performance"))]
    excluded = len(all_rows) - len(materialized)
    lines = [
        "# Event Alpha Integrated Radar Calibration Report",
        "",
        event_integrated_radar.RESEARCH_DISCLAIMER,
        "Recommendations only. Thresholds and priors are not changed automatically.",
        "Sample sizes are too small for automatic threshold changes.",
        f"Diagnostics excluded from performance: {excluded}",
        "",
    ]
    for dimension in PERFORMANCE_DIMENSIONS:
        lines.extend([f"## By {dimension}", ""])
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in materialized:
            groups[str(row.get(dimension) or "unknown")].append(row)
        for key in sorted(groups):
            group = groups[key]
            validated = sum(1 for row in group if _validation_label(row) == "validated")
            invalidated = sum(1 for row in group if _validation_label(row) == "invalidated/noise")
            inconclusive = sum(1 for row in group if _validation_label(row) == "inconclusive")
            filled = sum(1 for row in group if row.get("outcome_status") == "filled")
            rate = validated / max(1, validated + invalidated)
            thesis_moves = [
                float(row.get("thesis_favorable_excursion") or 0.0)
                for row in group
                if row.get("thesis_favorable_excursion") is not None
            ]
            median_thesis = _pct(median(thesis_moves)) if thesis_moves else "n/a"
            lines.append(
                f"- {key}: rows={len(group)} filled={filled} validated={validated} "
                f"invalidated/noise={invalidated} inconclusive={inconclusive} "
                f"validation_rate={rate:.2f} median_thesis_favorable_move={median_thesis}"
            )
        lines.append("")
    lines.extend([
        "## Recommended Next Experiments",
        "- Keep confirmed-long lanes gated by source plus market confirmation.",
        "- Keep fade/short-review lanes review-only until crowding/exhaustion outcomes have larger samples.",
        "- Treat low-sample source priors as suggestions, not live thresholds.",
    ])
    return "\n".join(lines).rstrip() + "\n"


def build_integrated_radar_calibration_priors(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    all_rows = [dict(row) for row in rows if isinstance(row, Mapping)]
    materialized = [row for row in all_rows if _truthy(row.get("include_in_performance"))]
    diagnostics = [row for row in all_rows if not _truthy(row.get("include_in_performance"))]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in materialized:
        groups[str(row.get("opportunity_type") or "unknown")].append(row)
    priors = {}
    min_sample = 25
    for lane, lane_rows in groups.items():
        validated = sum(1 for row in lane_rows if _validation_label(row) == "validated")
        invalidated = sum(1 for row in lane_rows if _validation_label(row) == "invalidated/noise")
        inconclusive = sum(1 for row in lane_rows if _validation_label(row) == "inconclusive")
        sample_size = len(lane_rows)
        thesis_moves = [
            float(row.get("thesis_favorable_excursion") or 0.0)
            for row in lane_rows
            if row.get("thesis_favorable_excursion") is not None
        ]
        priors[lane] = {
            "sample_size": sample_size,
            "min_sample_size": min_sample,
            "min_sample_warning": sample_size < min_sample,
            "validated_count": validated,
            "invalidated_count": invalidated,
            "invalidated_noise_count": invalidated,
            "inconclusive_count": inconclusive,
            "validation_rate": round(validated / max(1, validated + invalidated), 4),
            "median_thesis_favorable_move": median(thesis_moves) if thesis_moves else None,
            "legacy_aliases": {
                "useful_deprecated_alias": validated,
                "junk_deprecated_alias": invalidated,
                "suggested_prior_deprecated_alias": round(validated / max(1, validated + invalidated), 4),
            },
            "suggested_prior": round(validated / max(1, validated + invalidated), 4),
            "confidence": "low" if sample_size < min_sample else "medium",
            "recommendation_only": True,
            "eligible_for_auto_apply": False,
            "auto_apply": False,
            "generated_from_fixture": True,
            "excluded_from_auto_apply_reason": "fixture_or_small_sample_research_only",
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
            "horizon_basis": "primary_horizon",
        }
    diagnostic_priors: dict[str, Any] = {}
    for lane, lane_rows in _group_by(diagnostics, "opportunity_type").items():
        diagnostic_priors[lane] = {
            "sample_size": len(lane_rows),
            "excluded_from_performance": True,
            "recommendation_only": True,
            "eligible_for_auto_apply": False,
            "auto_apply": False,
        }
    return {
        "schema_version": 1,
        "row_type": "event_integrated_radar_calibration_priors",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "recommendation_only": True,
        "eligible_for_auto_apply": False,
        "auto_apply": False,
        "opportunity_type_priors": priors,
        "diagnostic_debug_priors": diagnostic_priors,
    }


def _first_namespace_dir(namespace_dirs: Iterable[str | Path]) -> Path:
    for path in namespace_dirs:
        return Path(path)
    return Path(".")


def _namespace_inputs(
    namespace_dir: Path,
    *,
    generated_at: str,
    stale_after_days: int,
) -> dict[str, Any]:
    candidates = _read_jsonl(namespace_dir / event_integrated_radar.INTEGRATED_CANDIDATES_FILENAME)
    cores = _read_jsonl(namespace_dir / CORE_OPPORTUNITIES_FILENAME)
    outcomes = _read_jsonl(namespace_dir / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME)
    deliveries = [
        *_read_jsonl(namespace_dir / ALPHA_NOTIFICATION_DELIVERIES_FILENAME),
        *_read_jsonl(namespace_dir / event_integrated_radar.INTEGRATED_DELIVERIES_FILENAME),
    ]
    rows = _performance_observation_rows(
        namespace_dir,
        candidates=candidates,
        core_rows=cores,
        outcome_rows=outcomes,
        delivery_rows=deliveries,
        generated_at=generated_at,
        stale_after_days=stale_after_days,
    )
    return {
        "namespace": namespace_dir.name,
        "path": event_artifact_paths.artifact_display_path(namespace_dir),
        "candidates_read": len(candidates),
        "core_opportunities_read": len(cores),
        "outcomes_read": len(outcomes),
        "deliveries_read": len(deliveries),
        "rows": rows,
    }


def _performance_observation_rows(
    namespace_dir: Path,
    *,
    candidates: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
    outcome_rows: Iterable[Mapping[str, Any]],
    delivery_rows: Iterable[Mapping[str, Any]],
    generated_at: str,
    stale_after_days: int,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in core_rows:
        if not isinstance(row, Mapping):
            continue
        key = _row_key(row)
        if not key:
            continue
        merged.setdefault(key, {}).update({f"core_{k}": v for k, v in dict(row).items()})
        _fill_missing(merged[key], dict(row))
    for row in candidates:
        if not isinstance(row, Mapping):
            continue
        key = _row_key(row)
        if not key:
            continue
        merged.setdefault(key, {}).update(dict(row))
    outcomes_by_key: dict[str, dict[str, Any]] = {}
    for row in outcome_rows:
        if not isinstance(row, Mapping):
            continue
        key = _row_key(row)
        if key:
            outcomes_by_key[key] = dict(row)
    delivery_keys: set[str] = set()
    for row in delivery_rows:
        if not isinstance(row, Mapping):
            continue
        for key in ("candidate_id", "core_opportunity_id"):
            value = str(row.get(key) or "").strip()
            if value:
                delivery_keys.add(f"{key}:{value}")
    out: list[dict[str, Any]] = []
    for key, row in sorted(merged.items()):
        outcome = outcomes_by_key.get(key) or outcomes_by_key.get(_alternate_key(row)) or {}
        out.append(_performance_observation_row(
            namespace_dir,
            row,
            outcome=outcome,
            delivered=key in delivery_keys or _alternate_key(row) in delivery_keys,
            generated_at=generated_at,
            stale_after_days=stale_after_days,
        ))
    for key, outcome in sorted(outcomes_by_key.items()):
        if key in merged:
            continue
        out.append(_performance_observation_row(
            namespace_dir,
            outcome,
            outcome=outcome,
            delivered=key in delivery_keys,
            generated_at=generated_at,
            stale_after_days=stale_after_days,
        ))
    return out


def _performance_observation_row(
    namespace_dir: Path,
    row: Mapping[str, Any],
    *,
    outcome: Mapping[str, Any],
    delivered: bool,
    generated_at: str,
    stale_after_days: int,
) -> dict[str, Any]:
    lane = _first_text(outcome, row, "opportunity_type", default="UNCONFIRMED_RESEARCH").upper()
    label = str(outcome.get("outcome_label") or "").strip()
    maturation_state = _maturation_state(row, outcome, generated_at=generated_at, stale_after_days=stale_after_days)
    validation = _validation_label(outcome) if outcome else "inconclusive"
    if maturation_state in {"pending", "stale"} and not label:
        validation = "inconclusive"
    provider = _dimension_primary(row, outcome, "provider")
    source_pack = _dimension_primary(row, outcome, "source_pack")
    source_origin = _dimension_primary(row, outcome, "source_origin")
    decision = decision_model_values(outcome, row)
    return {
        "namespace": namespace_dir.name,
        "candidate_id": _first_text(outcome, row, "candidate_id", default=""),
        "core_opportunity_id": _first_text(outcome, row, "core_opportunity_id", default=""),
        "symbol": _first_text(outcome, row, "symbol", default="UNKNOWN"),
        "coin_id": _first_text(outcome, row, "coin_id", default=""),
        "opportunity_type": lane,
        "source_origin": source_origin,
        "source_pack": source_pack,
        "provider": provider,
        "market_state_class": _dimension_primary(row, outcome, "market_state_class"),
        "crowding_class": _dimension_primary(row, outcome, "crowding_class"),
        "source_strength": _dimension_primary(row, outcome, "source_strength"),
        **decision,
        "maturation_state": maturation_state,
        "outcome_label": label or ("pending" if maturation_state == "pending" else maturation_state),
        "validation_label": validation,
        "delivered": delivered,
        "time_to_confirmation_hours": _time_to_confirmation_hours(lane, outcome),
        "observed_at": _first_text(outcome, row, "observed_at", default=""),
        "preview_time": str(outcome.get("preview_time") or ""),
        "include_in_main_aggregate": (
            lane != "DIAGNOSTIC"
        ),
    }


def _row_key(row: Mapping[str, Any]) -> str:
    candidate_id = str(row.get("candidate_id") or "").strip()
    if candidate_id:
        return f"candidate_id:{candidate_id}"
    core_id = str(row.get("core_opportunity_id") or "").strip()
    if core_id:
        return f"core_opportunity_id:{core_id}"
    symbol = str(row.get("symbol") or "").strip().upper()
    coin_id = str(row.get("coin_id") or "").strip().casefold()
    lane = str(row.get("opportunity_type") or "").strip().upper()
    if symbol or coin_id:
        return f"identity:{symbol}:{coin_id}:{lane}"
    return ""


def _alternate_key(row: Mapping[str, Any]) -> str:
    candidate_id = str(row.get("candidate_id") or "").strip()
    core_id = str(row.get("core_opportunity_id") or "").strip()
    if candidate_id and _row_key(row).startswith("core_opportunity_id:"):
        return f"candidate_id:{candidate_id}"
    if core_id and _row_key(row).startswith("candidate_id:"):
        return f"core_opportunity_id:{core_id}"
    return ""


def _fill_missing(target: dict[str, Any], row: Mapping[str, Any]) -> None:
    for key, value in row.items():
        if key not in target or target.get(key) in (None, "", (), []):
            target[key] = value


def _first_text(first: Mapping[str, Any], second: Mapping[str, Any], key: str, *, default: str = "unknown") -> str:
    for row in (first, second):
        value = row.get(key)
        if value not in (None, "", (), []):
            return str(value)
    core_value = second.get(f"core_{key}")
    if core_value not in (None, "", (), []):
        return str(core_value)
    return default


def _dimension_primary(row: Mapping[str, Any], outcome: Mapping[str, Any], dimension: str) -> str:
    values = _dimension_values(row, outcome, dimension)
    return values[0] if values else "unknown"


def _dimension_values(row: Mapping[str, Any], outcome: Mapping[str, Any], dimension: str) -> tuple[str, ...]:
    plural = {
        "provider": ("providers", "source_providers"),
        "source_origin": ("source_origins",),
        "source_pack": ("source_packs",),
    }.get(dimension, ())
    values: list[str] = []
    for source in (outcome, row):
        scalar = source.get(dimension)
        if scalar not in (None, "", (), []):
            values.append(str(scalar))
        for key in plural:
            nested = source.get(key)
            if isinstance(nested, str):
                values.append(nested)
            elif isinstance(nested, (list, tuple, set)):
                values.extend(str(item) for item in nested if str(item).strip())
    cleaned = []
    seen = set()
    for value in values:
        for part in str(value).replace(";", ",").split(","):
            item = part.strip()
            if item and item not in seen:
                seen.add(item)
                cleaned.append(item)
    return tuple(cleaned)


def _maturation_state(
    row: Mapping[str, Any],
    outcome: Mapping[str, Any],
    *,
    generated_at: str,
    stale_after_days: int,
) -> str:
    if outcome:
        status = str(outcome.get("outcome_status") or "").strip().casefold()
        if status in {"missing_data", "missing_price_data", "no_price_data"}:
            return "missing_price_data"
        if status in {"partial", "partially_matured"}:
            return "partially_matured"
        if status == "filled":
            return "matured" if _filled_horizon_count(outcome) >= len(HORIZONS) else "partially_matured"
        if _filled_horizon_count(outcome):
            return "partially_matured"
    observed = _parse_time(row.get("observed_at") or row.get("created_at") or row.get("preview_time"))
    generated = _parse_time(generated_at)
    if observed and generated and (generated - observed).total_seconds() > stale_after_days * 86400:
        return "stale"
    return "pending"


def _filled_horizon_count(row: Mapping[str, Any]) -> int:
    for key in ("return_by_horizon", "horizons"):
        values = row.get(key)
        if isinstance(values, Mapping):
            return sum(1 for horizon in HORIZONS if isinstance(values.get(horizon), (int, float)))
    return 1 if isinstance(row.get("primary_horizon_return"), (int, float)) else 0


def _time_to_confirmation_hours(lane: str, outcome: Mapping[str, Any]) -> float | None:
    if not outcome or _validation_label(outcome) != "validated":
        return None
    key = "time_to_trough_hours" if lane in {"FADE_SHORT_REVIEW", "RISK_ONLY"} else "time_to_peak_hours"
    value = outcome.get(key)
    if value is None and lane == "UNCONFIRMED_RESEARCH":
        candidates = [_safe_number(outcome.get("time_to_peak_hours")), _safe_number(outcome.get("time_to_trough_hours"))]
        numeric = [item for item in candidates if item is not None]
        return min(numeric) if numeric else None
    return _safe_number(value)


def _aggregate_summary(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    matured_rows = [row for row in materialized if row.get("maturation_state") in MATURED_STATES]
    validated = sum(1 for row in matured_rows if row.get("validation_label") == "validated")
    noise = sum(1 for row in matured_rows if row.get("validation_label") == "invalidated/noise")
    inconclusive = sum(1 for row in matured_rows if row.get("validation_label") == "inconclusive")
    time_values = [_safe_number(row.get("time_to_confirmation_hours")) for row in matured_rows]
    time_values = [value for value in time_values if value is not None]
    return {
        "rows": len(materialized),
        "matured_rows": len(matured_rows),
        "validated_count": validated,
        "invalidated_noise_count": noise,
        "inconclusive_count": inconclusive,
        "pending_count": sum(1 for row in materialized if row.get("maturation_state") == "pending"),
        "partially_matured_count": sum(1 for row in materialized if row.get("maturation_state") == "partially_matured"),
        "missing_price_data_count": sum(1 for row in materialized if row.get("maturation_state") == "missing_price_data"),
        "stale_count": sum(1 for row in materialized if row.get("maturation_state") == "stale"),
        "validation_rate": _safe_rate(validated, validated + noise),
        "noise_rate": _safe_rate(noise, validated + noise),
        "average_time_to_confirmation_hours": round(sum(time_values) / len(time_values), 4) if time_values else None,
    }


def _performance_views(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    by_lane = _group_rows_by_dimension(materialized, "opportunity_type")
    early = _aggregate_summary(by_lane.get("EARLY_LONG_RESEARCH", ()))
    confirmed = _aggregate_summary(by_lane.get("CONFIRMED_LONG_RESEARCH", ()))
    fade = _aggregate_summary(by_lane.get("FADE_SHORT_REVIEW", ()))
    risk = _aggregate_summary(by_lane.get("RISK_ONLY", ()))
    unconfirmed_rows = by_lane.get("UNCONFIRMED_RESEARCH", ())
    unconfirmed = _aggregate_summary(unconfirmed_rows)
    later_confirmed = sum(
        1
        for row in unconfirmed_rows
        if row.get("validation_label") == "validated" and row.get("maturation_state") in MATURED_STATES
    )
    noise = sum(
        1
        for row in unconfirmed_rows
        if row.get("validation_label") == "invalidated/noise" and row.get("maturation_state") in MATURED_STATES
    )
    provider = _dimension_summary(materialized, "provider")
    return {
        "early_long_conversion_rate": {**early, "rate": early["validation_rate"]},
        "confirmed_long_continuation_rate": {**confirmed, "rate": confirmed["validation_rate"]},
        "fade_review_exhaustion_rate": {**fade, "rate": fade["validation_rate"]},
        "risk_only_validation_rate": {**risk, "rate": risk["validation_rate"]},
        "unconfirmed_later_confirmation_noise_rate": {
            **unconfirmed,
            "later_confirmation_count": later_confirmed,
            "noise_count": noise,
            "later_confirmation_rate": _safe_rate(later_confirmed, later_confirmed + noise),
            "noise_rate": _safe_rate(noise, later_confirmed + noise),
        },
        "provider_usefulness": provider,
        "provider_noise_rate": {
            key: {
                "rows": value["rows"],
                "noise_rate": value["noise_rate"],
                "invalidated_noise_count": value["invalidated_noise_count"],
            }
            for key, value in provider.items()
        },
    }


def _dimension_summary(rows: Iterable[Mapping[str, Any]], dimension: str) -> dict[str, dict[str, Any]]:
    return {
        key: _aggregate_summary(group)
        for key, group in sorted(_group_rows_by_dimension(rows, dimension).items())
    }


def _group_rows_by_dimension(rows: Iterable[Mapping[str, Any]], dimension: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        values = _dimension_values(row, {}, dimension) or ("unknown",)
        for value in values:
            grouped[str(value or "unknown")].append(dict(row))
    return grouped


def _prior_suggestion(
    key: str,
    rows: Iterable[Mapping[str, Any]],
    *,
    generated_at: str,
    min_sample: int,
) -> dict[str, Any]:
    summary = _aggregate_summary(rows)
    sample = int(summary["rows"])
    rate = summary["validation_rate"]
    noise_rate = summary["noise_rate"]
    if sample < min_sample:
        recommendation = "insufficient_sample_collect_more_outcomes"
    elif rate is not None and rate >= 0.6 and (noise_rate or 0.0) <= 0.25:
        recommendation = "review_for_higher_research_prior"
    elif noise_rate is not None and noise_rate >= 0.5:
        recommendation = "review_for_lower_research_priority"
    else:
        recommendation = "maintain_current_research_priority"
    return {
        "key": key,
        "sample_size": sample,
        "min_sample_size": min_sample,
        "min_sample_warning": sample < min_sample,
        "validated_count": summary["validated_count"],
        "invalidated_noise_count": summary["invalidated_noise_count"],
        "inconclusive_count": summary["inconclusive_count"],
        "validation_rate": rate,
        "noise_rate": noise_rate,
        "average_time_to_confirmation_hours": summary["average_time_to_confirmation_hours"],
        "recommendation": recommendation,
        "recommendation_only": True,
        "eligible_for_auto_apply": False,
        "auto_apply": False,
        "excluded_from_auto_apply_reason": "cross_run_research_dashboard_recommendation_only",
        "last_updated_at": generated_at,
    }


def _safe_rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _safe_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rate_text(value: Any) -> str:
    number = _safe_number(value)
    return "n/a" if number is None else f"{number:.2f}"


def _number_text(value: Any) -> str:
    number = _safe_number(value)
    return "n/a" if number is None else f"{number:.2f}"


def _outcome_row(candidate: Mapping[str, Any], *, now: str) -> dict[str, Any]:
    symbol = str(candidate.get("symbol") or "UNKNOWN")
    lane = str(candidate.get("opportunity_type") or "UNCONFIRMED_RESEARCH")
    returns = _fixture_returns(symbol, lane)
    btc_returns = _benchmark_returns("BTC")
    eth_returns = _benchmark_returns("ETH")
    primary_horizon = _primary_horizon(lane)
    primary_return = returns.get(primary_horizon)
    label = _label_for(symbol, lane, primary_return)
    price = _price(candidate)
    status = "filled" if returns else "missing_data"
    missing_reason = None if returns else "no_cached_price_fixture"
    relative_vs_btc = {
        horizon: _relative_return(returns.get(horizon), btc_returns.get(horizon))
        for horizon in HORIZONS
    }
    thesis_direction = _thesis_direction(lane)
    thesis_returns = _thesis_returns(returns, lane)
    thesis_relative_vs_btc = _thesis_returns(relative_vs_btc, lane)
    thesis_favorable = _window_extremes(thesis_returns, want_peak=True)
    thesis_adverse = _window_extremes(thesis_returns, want_peak=False)
    thesis_primary = thesis_returns.get(primary_horizon)
    decision = decision_model_values(candidate)
    return {
        "schema_version": 1,
        "row_type": "event_integrated_radar_outcome",
        "candidate_id": candidate.get("candidate_id"),
        "core_opportunity_id": candidate.get("core_opportunity_id"),
        "run_id": candidate.get("run_id"),
        "profile": candidate.get("profile"),
        "artifact_namespace": candidate.get("artifact_namespace"),
        "symbol": symbol,
        "coin_id": candidate.get("coin_id"),
        "opportunity_type": lane,
        "source_origin": candidate.get("source_origin"),
        "source_pack": candidate.get("source_pack"),
        "provider": candidate.get("provider") or candidate.get("source_class"),
        "market_state_class": candidate.get("market_state_class"),
        "source_strength": candidate.get("source_strength"),
        "crowding_class": candidate.get("crowding_class"),
        **decision,
        "observed_at": candidate.get("observed_at"),
        "preview_time": now,
        "price_at_observation": price,
        "price_source": "fixture_or_candidate_snapshot",
        "horizons": {horizon: returns.get(horizon) for horizon in HORIZONS},
        "outcome_horizons": list(HORIZONS),
        "return_by_horizon": {horizon: returns.get(horizon) for horizon in HORIZONS},
        "relative_return_vs_btc_by_horizon": relative_vs_btc,
        "relative_return_vs_eth_by_horizon": {
            horizon: _relative_return(returns.get(horizon), eth_returns.get(horizon))
            for horizon in HORIZONS
        },
        "benchmark_btc_price_at_observation": 65000.0,
        "benchmark_eth_price_at_observation": 3500.0,
        "benchmark_btc_return_by_horizon": {horizon: btc_returns.get(horizon) for horizon in HORIZONS},
        "benchmark_eth_return_by_horizon": {horizon: eth_returns.get(horizon) for horizon in HORIZONS},
        "primary_horizon": primary_horizon,
        "primary_horizon_return": primary_return,
        "relative_return_vs_btc_24h": returns.get("relative_vs_btc_24h"),
        "mfe": max((value for key, value in returns.items() if key in HORIZONS and isinstance(value, (int, float))), default=None),
        "mae": min((value for key, value in returns.items() if key in HORIZONS and isinstance(value, (int, float))), default=None),
        "max_favorable_excursion_by_window": _window_extremes(returns, want_peak=True),
        "max_adverse_excursion_by_window": _window_extremes(returns, want_peak=False),
        "thesis_direction": thesis_direction,
        "thesis_primary_move": thesis_primary,
        "thesis_return_by_horizon": thesis_returns,
        "thesis_relative_return_vs_btc_by_horizon": thesis_relative_vs_btc,
        "thesis_favorable_excursion_by_window": thesis_favorable,
        "thesis_adverse_excursion_by_window": thesis_adverse,
        "thesis_favorable_excursion": _best_mapping_value(thesis_favorable, want_peak=True),
        "thesis_adverse_excursion": _best_mapping_value(thesis_adverse, want_peak=False),
        "thesis_outcome_interpretation": _thesis_interpretation(lane, label, thesis_primary),
        "time_to_peak": _time_to_extreme(returns, want_peak=True),
        "time_to_trough": _time_to_extreme(returns, want_peak=False),
        "time_to_peak_hours": _time_to_extreme_hours(returns, want_peak=True),
        "time_to_trough_hours": _time_to_extreme_hours(returns, want_peak=False),
        "catalyst_confirmed_after_observation": _confirmed_after_observation(label, kind="catalyst"),
        "market_confirmed_after_observation": _confirmed_after_observation(label, kind="market"),
        "market_confirmed": lane == "CONFIRMED_LONG_RESEARCH" and label in {"continuation_good", "useful"},
        "fade_confirmed": lane == "FADE_SHORT_REVIEW" and label in {"fade_review_good", "useful"},
        "risk_validated": lane == "RISK_ONLY" and label in {"risk_validated", "useful"},
        "outcome_label": label,
        "outcome_status": status,
        "missing_data_reason": missing_reason,
        "include_in_performance": (
            lane != "DIAGNOSTIC"
            and status == "filled"
        ),
        "research_only": True,
        "no_trade_created": True,
        "no_paper_trade_created": True,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
    }


def _fixture_returns(symbol: str, lane: str) -> dict[str, float]:
    table = {
        "TESTLIST": {"15m": 0.002, "1h": 0.006, "4h": 0.022, "24h": 0.08, "3d": 0.12, "7d": 0.18, "relative_vs_btc_24h": 0.075},
        "TESTPERP": {"15m": 0.006, "1h": 0.024, "4h": 0.055, "24h": 0.11, "3d": 0.16, "7d": 0.2, "relative_vs_btc_24h": 0.105},
        "TESTFADE": {"15m": -0.01, "1h": -0.035, "4h": -0.08, "24h": -0.14, "3d": -0.18, "7d": -0.2, "relative_vs_btc_24h": -0.13},
        "TESTUNLOCK": {"15m": -0.003, "1h": -0.01, "4h": -0.035, "24h": -0.09, "3d": -0.12, "7d": -0.16, "relative_vs_btc_24h": -0.085},
        "BTC": {"15m": 0.0, "1h": 0.001, "4h": 0.001, "24h": 0.002, "3d": 0.004, "7d": 0.006, "relative_vs_btc_24h": 0.0},
        "TESTRUMOR": {"15m": 0.0, "1h": -0.001, "4h": 0.001, "24h": 0.003, "3d": 0.0, "7d": -0.002, "relative_vs_btc_24h": 0.001},
        "SECTOR": {"15m": 0.0, "1h": 0.0, "4h": 0.0, "24h": 0.0, "3d": 0.0, "7d": 0.0, "relative_vs_btc_24h": 0.0},
    }
    return dict(table.get(symbol.upper(), table.get("SECTOR" if lane == "DIAGNOSTIC" else "", {})))


def _thesis_direction(lane: str) -> str:
    return {
        "EARLY_LONG_RESEARCH": "upside_research",
        "CONFIRMED_LONG_RESEARCH": "upside_research",
        "FADE_SHORT_REVIEW": "downside_or_risk_research",
        "RISK_ONLY": "downside_or_risk_research",
        "UNCONFIRMED_RESEARCH": "neutral_validation_research",
        "DIAGNOSTIC": "diagnostic",
    }.get(str(lane or "").upper(), "neutral_validation_research")


def _thesis_multiplier(lane: str) -> float | None:
    lane_upper = str(lane or "").upper()
    if lane_upper in {"EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH"}:
        return 1.0
    if lane_upper in {"FADE_SHORT_REVIEW", "RISK_ONLY"}:
        return -1.0
    return None


def _thesis_returns(values: Mapping[str, float | None], lane: str) -> dict[str, float | None]:
    multiplier = _thesis_multiplier(lane)
    out: dict[str, float | None] = {}
    for horizon in HORIZONS:
        value = values.get(horizon)
        if multiplier is None or value is None:
            out[horizon] = None
            continue
        try:
            out[horizon] = float(value) * multiplier
        except (TypeError, ValueError):
            out[horizon] = None
    return out


def _best_mapping_value(values: Mapping[str, float | None], *, want_peak: bool) -> float | None:
    numeric = [float(value) for value in values.values() if isinstance(value, (int, float))]
    if not numeric:
        return None
    return max(numeric) if want_peak else min(numeric)


def _thesis_interpretation(lane: str, label: str, thesis_primary: float | None) -> str:
    direction = _thesis_direction(lane)
    lane_upper = str(lane or "").upper()
    if direction == "upside_research":
        if thesis_primary is None:
            return "long research thesis pending; no primary market outcome available"
        return "validated long-research reaction" if thesis_primary > 0 else "not validated by primary market reaction"
    if direction == "downside_or_risk_research" and lane_upper == "FADE_SHORT_REVIEW":
        if thesis_primary is None:
            return "fade-review thesis pending; no primary market outcome available"
        return (
            "validated fade-review thesis: asset fell after the crowded move"
            if thesis_primary > 0
            else "not validated: asset return did not favor the fade thesis"
        )
    if direction == "downside_or_risk_research":
        if thesis_primary is None:
            return "risk thesis pending; no primary market outcome available"
        return (
            "validated risk thesis: asset sold off in the evaluation window"
            if thesis_primary > 0
            else "not validated: asset did not sell off enough for the risk thesis"
        )
    if str(label or "") == "remained_noise":
        return "neutral/noise validation: no directional research thesis scored"
    if direction == "diagnostic":
        return "diagnostic row excluded from performance calibration"
    return "inconclusive research validation; no directional thesis scored"


def _benchmark_returns(symbol: str) -> dict[str, float]:
    if symbol == "ETH":
        return {"15m": 0.0005, "1h": 0.0015, "4h": 0.003, "24h": 0.006, "3d": 0.01, "7d": 0.018}
    return {"15m": 0.0003, "1h": 0.001, "4h": 0.002, "24h": 0.005, "3d": 0.008, "7d": 0.012}


def _relative_return(value: float | None, benchmark: float | None) -> float | None:
    if value is None or benchmark is None:
        return None
    return float(value) - float(benchmark)


def _window_extremes(returns: Mapping[str, float], *, want_peak: bool) -> dict[str, float | None]:
    values: dict[str, float | None] = {}
    ordered: list[float] = []
    for horizon in HORIZONS:
        value = returns.get(horizon)
        if isinstance(value, (int, float)):
            ordered.append(float(value))
            values[horizon] = max(ordered) if want_peak else min(ordered)
        else:
            values[horizon] = None
    return values


def _time_to_extreme_hours(returns: Mapping[str, float], *, want_peak: bool) -> float | None:
    horizon = _time_to_extreme(returns, want_peak=want_peak)
    return {
        "15m": 0.25,
        "1h": 1.0,
        "4h": 4.0,
        "24h": 24.0,
        "3d": 72.0,
        "7d": 168.0,
    }.get(str(horizon or ""))


def _confirmed_after_observation(label: str, *, kind: str) -> str:
    if label in {"early_good", "continuation_good", "fade_review_good", "risk_validated"}:
        return "yes"
    if label in {"remained_noise", "diagnostic_only"}:
        return "no"
    return "unknown"


def _group_by(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(dict(row))
    return grouped


def _primary_horizon(lane: str) -> str:
    return {
        "EARLY_LONG_RESEARCH": "3d",
        "CONFIRMED_LONG_RESEARCH": "24h",
        "FADE_SHORT_REVIEW": "24h",
        "RISK_ONLY": "24h",
        "UNCONFIRMED_RESEARCH": "24h",
        "DIAGNOSTIC": "24h",
    }.get(lane, "24h")


def _label_for(symbol: str, lane: str, primary_return: float | None) -> str:
    if primary_return is None:
        return "missing_data"
    symbol_upper = symbol.upper()
    if symbol_upper == "TESTLIST":
        return "early_good"
    if symbol_upper == "TESTPERP":
        return "continuation_good"
    if symbol_upper == "TESTFADE":
        return "fade_review_good"
    if symbol_upper == "TESTUNLOCK":
        return "risk_validated"
    if symbol_upper in {"BTC", "TESTRUMOR"}:
        return "remained_noise"
    if lane in {"EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH"}:
        return "useful" if primary_return > 0.03 else "junk"
    if lane in {"FADE_SHORT_REVIEW", "RISK_ONLY"}:
        return "useful" if primary_return < -0.03 else "junk"
    if lane == "DIAGNOSTIC":
        return "diagnostic_only"
    return "remained_noise" if abs(primary_return) < 0.02 else "watch"


def _truth_label(row: Mapping[str, Any]) -> str:
    label = str(row.get("outcome_label") or "")
    if label in {"useful", "early_good", "continuation_good", "fade_review_good", "risk_validated", "watch"}:
        return "useful"
    if label == "junk":
        return "junk"
    if label in {"remained_noise", "diagnostic_only"}:
        return "junk"
    return "watch"


def _validation_label(row: Mapping[str, Any]) -> str:
    label = str(row.get("outcome_label") or "")
    if label in {"useful", "early_good", "continuation_good", "fade_review_good", "risk_validated"}:
        return "validated"
    if label in {"junk", "remained_noise"}:
        return "invalidated/noise"
    if label == "diagnostic_only":
        return "invalidated/noise"
    return "inconclusive"


def _time_to_extreme(values: Mapping[str, float], *, want_peak: bool) -> str | None:
    ordered = [(horizon, values.get(horizon)) for horizon in HORIZONS if isinstance(values.get(horizon), (int, float))]
    if not ordered:
        return None
    horizon, _value = max(ordered, key=lambda item: item[1]) if want_peak else min(ordered, key=lambda item: item[1])
    return horizon


def _price(candidate: Mapping[str, Any]) -> float | None:
    for key in ("latest_market_snapshot", "market_snapshot", "market_state_snapshot"):
        snapshot = candidate.get(key)
        if isinstance(snapshot, Mapping):
            try:
                return float(snapshot.get("price"))
            except (TypeError, ValueError):
                continue
    return 1.0


def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:+.2f}%"
    except (TypeError, ValueError):
        return "n/a"


def _format_counts(values: Mapping[str, int] | Counter[Any]) -> str:
    items = [(str(key), int(value)) for key, value in dict(values).items() if int(value)]
    return ", ".join(f"{key}={value}" for key, value in sorted(items)) if items else "none"


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "on"}


def _parse_time(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, Mapping):
                rows.append(dict(value))
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            stamped = schema_v1.stamp_artifact_row(row, path=path)
            handle.write(json.dumps(_json_ready(stamped), sort_keys=True, separators=(",", ":")) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamped = schema_v1.stamp_artifact_payload(payload, path=path)
    path.write_text(json.dumps(_json_ready(stamped), sort_keys=True), encoding="utf-8")


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return event_artifact_paths.artifact_display_path(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value
