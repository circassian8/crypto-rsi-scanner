"""Research-only outcomes and calibration for integrated Event Alpha radar."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping

from ..artifacts import paths as event_artifact_paths
from ..artifacts import schema_v1
from ..radar import integrated_radar as event_integrated_radar
from ..radar.decision_model_surfaces import decision_model_values
from . import outcome_eligibility
from .artifact_io import (
    read_jsonl as _read_jsonl,
    write_json as _write_json,
    write_jsonl as _write_jsonl,
)
from .integrated_radar_outcome_rows import (
    _group_by,
    _outcome_placeholder_row,
    _outcome_row,
    _validation_label,
)


HORIZONS = outcome_eligibility.OUTCOME_HORIZONS
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
    "primary_thesis_origin",
    "thesis_origin_contributor",
    "catalyst_status",
    "confidence_band",
    "actionability_score_cohort",
    "evidence_confidence_score_cohort",
    "risk_score_cohort",
    "anomaly_type",
    "radar_route",
    "market_phase",
    "tradability_status",
)
PERFORMANCE_LANES = (
    "EARLY_LONG_RESEARCH",
    "CONFIRMED_LONG_RESEARCH",
    "FADE_SHORT_REVIEW",
    "RISK_ONLY",
    "UNCONFIRMED_RESEARCH",
)
MATURED_STATES = ("matured",)


def fill_integrated_radar_outcomes(
    namespace_dir: str | Path,
    *,
    observed_at: datetime | str | None = None,
) -> tuple[dict[str, Any], ...]:
    """Fill deterministic, research-only outcomes for integrated radar candidates."""
    base = Path(namespace_dir)
    candidates = _read_jsonl(base / event_integrated_radar.INTEGRATED_CANDIDATES_FILENAME)
    core_rows = _read_jsonl(base / CORE_OPPORTUNITIES_FILENAME)
    now = _iso(_parse_time(observed_at) or datetime.now(timezone.utc))
    outcomes_path = base / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME
    rows = tuple(schema_v1.stamp_artifact_row(_outcome_row(candidate, now=now), path=outcomes_path) for candidate in candidates)
    _write_jsonl(outcomes_path, rows)
    report = format_integrated_radar_outcome_report(
        rows,
        candidate_rows=candidates,
        core_rows=core_rows,
        evaluated_at=now,
    )
    (base / event_integrated_radar.INTEGRATED_OUTCOME_REPORT_FILENAME).write_text(report, encoding="utf-8")
    calibration = format_integrated_radar_calibration_report(
        rows,
        candidate_rows=candidates,
        core_rows=core_rows,
        evaluated_at=now,
    )
    (base / event_integrated_radar.INTEGRATED_CALIBRATION_REPORT_FILENAME).write_text(calibration, encoding="utf-8")
    priors = build_integrated_radar_calibration_priors(
        rows,
        candidate_rows=candidates,
        core_rows=core_rows,
        evaluated_at=now,
    )
    _write_json(base / event_integrated_radar.INTEGRATED_CALIBRATION_PRIORS_FILENAME, priors)
    return rows


def write_integrated_radar_outcome_placeholders(
    namespace_dir: str | Path,
    candidates: Iterable[Mapping[str, Any]],
    *,
    observed_at: datetime | str | None = None,
) -> tuple[dict[str, Any], ...]:
    """Write one pending, non-calibration outcome row for every v2 idea.

    This establishes coverage at idea creation time without pretending that
    future prices or human preference labels exist.  The regular fill command
    later replaces these rows with observed or explicitly synthetic outcomes.
    """

    base = Path(namespace_dir)
    now = _iso(_parse_time(observed_at) or datetime.now(timezone.utc))
    outcomes_path = base / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME
    rows = tuple(
        schema_v1.stamp_artifact_row(
            _outcome_placeholder_row(candidate, now=now),
            path=outcomes_path,
        )
        for candidate in candidates
        if isinstance(candidate, Mapping)
        and decision_model_values(candidate)
    )
    _write_jsonl(outcomes_path, rows)
    return rows


def load_integrated_radar_outcomes(namespace_dir: str | Path) -> tuple[dict[str, Any], ...]:
    return tuple(_read_jsonl(Path(namespace_dir) / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME))


def load_integrated_radar_outcome_authority(
    namespace_dir: str | Path,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    base = Path(namespace_dir)
    return (
        tuple(_read_jsonl(base / event_integrated_radar.INTEGRATED_CANDIDATES_FILENAME)),
        tuple(_read_jsonl(base / CORE_OPPORTUNITIES_FILENAME)),
    )


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
    eligible_main_rows = [
        row for row in main_rows
        if row.get("calibration_eligible") is True
        and row.get("maturation_state") == "matured"
    ]
    exclusion_reasons = Counter(
        reason
        for row in main_rows
        if row.get("calibration_eligible") is not True
        for reason in row.get("calibration_ineligible_reasons") or ()
        if type(reason) is str
    )
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
        "rows_evaluated": len(eligible_main_rows),
        "diagnostic_rows_excluded": diagnostic_count,
        "calibration_ineligible_rows_excluded": len(main_rows) - len(eligible_main_rows),
        "calibration_exclusion_reason_counts": dict(sorted(exclusion_reasons.items())),
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
        "Automatic market outcomes and human preference feedback are separate evidence streams.",
        "Preference review target: 3-5 targeted labels per day; first useful sample 30-50 labels.",
        "Routing-policy changes require explicit human approval.",
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


def format_integrated_radar_outcome_report(
    rows: Iterable[Mapping[str, Any]],
    *,
    candidate_rows: Iterable[Mapping[str, Any]] = (),
    core_rows: Iterable[Mapping[str, Any]] = (),
    evaluated_at: Any = None,
) -> str:
    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    performance_rows, excluded_rows, exclusion_reasons = (
        outcome_eligibility.partition_joined_calibration_outcomes(
            materialized,
            candidate_rows,
            core_rows,
            evaluated_at=evaluated_at,
        )
    )
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
        f"- Non-authoritative rows excluded from calibration: {len(excluded_rows)}",
        f"- Calibration exclusions: {_format_counts(exclusion_reasons)}",
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
        returns = [
            number
            for row in lane_rows
            if (number := outcome_eligibility.finite_number(row.get("primary_horizon_return"))) is not None
        ]
        thesis_returns = [
            number
            for row in lane_rows
            if (number := outcome_eligibility.finite_number(row.get("thesis_primary_move"))) is not None
        ]
        thesis_favorable = [
            number
            for row in lane_rows
            if (
                number := outcome_eligibility.finite_number(
                    row.get("thesis_favorable_excursion")
                )
            ) is not None
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
    if excluded_rows:
        lines.extend(["", "## Calibration-Excluded Rows"])
        lines.append(
            "Synthetic, pending, legacy, unmatched, duplicate, and provenance-failed rows "
            "remain visible here but are not performance evidence."
        )
        for row in excluded_rows[:10]:
            lines.append(
                f"- {row.get('symbol')}/{row.get('coin_id')} lane={row.get('opportunity_type')} "
                f"label={row.get('synthetic_diagnostic_label') or row.get('outcome_label')} "
                f"status={row.get('outcome_status')} "
                f"reasons={','.join(row.get('calibration_ineligible_reasons') or ()) or 'unknown'}"
            )
    return "\n".join(lines).rstrip() + "\n"


def format_integrated_radar_calibration_report(
    rows: Iterable[Mapping[str, Any]],
    *,
    candidate_rows: Iterable[Mapping[str, Any]] = (),
    core_rows: Iterable[Mapping[str, Any]] = (),
    evaluated_at: Any = None,
) -> str:
    all_rows = [dict(row) for row in rows if isinstance(row, Mapping)]
    materialized, excluded_rows, exclusion_reasons = (
        outcome_eligibility.partition_joined_calibration_outcomes(
            all_rows,
            candidate_rows,
            core_rows,
            evaluated_at=evaluated_at,
        )
    )
    lines = [
        "# Event Alpha Integrated Radar Calibration Report",
        "",
        event_integrated_radar.RESEARCH_DISCLAIMER,
        "Recommendations only. Thresholds and priors are not changed automatically.",
        "Sample sizes are too small for automatic threshold changes.",
        "Collect 3-5 targeted preference labels per day; review the first 30-50 before proposing policy changes.",
        "Any routing-policy or threshold change requires explicit human approval.",
        f"Non-authoritative rows excluded from calibration: {len(excluded_rows)}",
        f"Calibration exclusion reasons: {_format_counts(exclusion_reasons)}",
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
            filled = sum(
                1 for row in group
                if outcome_eligibility.primary_horizon_maturation_state(row) == "matured"
            )
            rate = _safe_rate(validated, validated + invalidated)
            thesis_moves = [
                number
                for row in group
                if (
                    number := outcome_eligibility.finite_number(
                        row.get("thesis_favorable_excursion")
                    )
                ) is not None
            ]
            median_thesis = _pct(median(thesis_moves)) if thesis_moves else "n/a"
            lines.append(
                f"- {key}: rows={len(group)} filled={filled} validated={validated} "
                f"invalidated/noise={invalidated} inconclusive={inconclusive} "
                f"validation_rate={_rate_text(rate)} median_thesis_favorable_move={median_thesis}"
            )
        lines.append("")
    lines.extend([
        "## Recommended Next Experiments",
        "- Keep confirmed-long lanes gated by source plus market confirmation.",
        "- Keep fade/short-review lanes review-only until crowding/exhaustion outcomes have larger samples.",
        "- Treat low-sample source priors as suggestions, not live thresholds.",
    ])
    return "\n".join(lines).rstrip() + "\n"


def build_integrated_radar_calibration_priors(
    rows: Iterable[Mapping[str, Any]],
    *,
    candidate_rows: Iterable[Mapping[str, Any]] = (),
    core_rows: Iterable[Mapping[str, Any]] = (),
    evaluated_at: Any = None,
) -> dict[str, Any]:
    all_rows = [dict(row) for row in rows if isinstance(row, Mapping)]
    materialized, diagnostics, exclusion_reasons = (
        outcome_eligibility.partition_joined_calibration_outcomes(
            all_rows,
            candidate_rows,
            core_rows,
            evaluated_at=evaluated_at,
        )
    )
    authority_rows = [
        row
        for row in (*materialized, *diagnostics)
        if "core_core_opportunity_id" in row
    ]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in authority_rows:
        if str(row.get("opportunity_type") or "").upper() == "DIAGNOSTIC":
            continue
        groups[str(row.get("opportunity_type") or "unknown")].append(row)
    eligible_groups = _group_by(materialized, "opportunity_type")
    priors = {}
    min_sample = 25
    for lane, lane_rows in groups.items():
        eligible_lane_rows = eligible_groups.get(lane, [])
        validated = sum(1 for row in eligible_lane_rows if _validation_label(row) == "validated")
        invalidated = sum(1 for row in eligible_lane_rows if _validation_label(row) == "invalidated/noise")
        inconclusive = sum(1 for row in eligible_lane_rows if _validation_label(row) == "inconclusive")
        sample_size = validated + invalidated
        thesis_moves = [
            number
            for row in eligible_lane_rows
            if (
                number := outcome_eligibility.finite_number(
                    row.get("thesis_favorable_excursion")
                )
            ) is not None
        ]
        validation_rate = _safe_rate(validated, validated + invalidated)
        priors[lane] = {
            "sample_size": sample_size,
            "input_rows": len(lane_rows),
            "calibration_eligible_rows": len(eligible_lane_rows),
            "calibration_ineligible_rows": len(lane_rows) - len(eligible_lane_rows),
            "eligible_inconclusive_count": inconclusive,
            "min_sample_size": min_sample,
            "min_sample_warning": sample_size < min_sample,
            "validated_count": validated,
            "invalidated_count": invalidated,
            "invalidated_noise_count": invalidated,
            "inconclusive_count": inconclusive,
            "validation_rate": validation_rate,
            "median_thesis_favorable_move": median(thesis_moves) if thesis_moves else None,
            "legacy_aliases": {
                "useful_deprecated_alias": validated,
                "junk_deprecated_alias": invalidated,
                "suggested_prior_deprecated_alias": validation_rate,
            },
            "suggested_prior": validation_rate,
            "confidence": "low" if sample_size < min_sample else "medium",
            "recommendation_only": True,
            "eligible_for_auto_apply": False,
            "auto_apply": False,
            "generated_from_fixture": bool(lane_rows) and all(
                row.get("outcome_data_source") == "synthetic_fixture"
                for row in lane_rows
            ),
            "excluded_from_auto_apply_reason": "fixture_or_small_sample_research_only",
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
            "horizon_basis": "primary_horizon",
        }
    diagnostic_priors: dict[str, Any] = {}
    authority_diagnostics = [
        row for row in diagnostics if "core_core_opportunity_id" in row
    ]
    for lane, lane_rows in _group_by(authority_diagnostics, "opportunity_type").items():
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
        "calibration_eligible_rows": len(materialized),
        "calibration_ineligible_rows": len(diagnostics),
        "calibration_unattributed_rows": len(diagnostics) - len(authority_diagnostics),
        "calibration_exclusion_reason_counts": exclusion_reasons,
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
    candidate_rows = [dict(row) for row in candidates if isinstance(row, Mapping)]
    core_materialized = [dict(row) for row in core_rows if isinstance(row, Mapping)]
    outcome_materialized = [dict(row) for row in outcome_rows if isinstance(row, Mapping)]
    delivery_identities = {
        identity
        for row in delivery_rows
        if isinstance(row, Mapping)
        if (identity := outcome_eligibility.canonical_join_identity(row)) is not None
    }
    cores_by_key: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for core in core_materialized:
        key = _core_join_key(core)
        if key is not None:
            cores_by_key[key].append(core)
    base_join_reasons: dict[int, tuple[str, ...]] = {}
    for target in candidate_rows:
        authority_reasons: list[str] = []
        if not outcome_eligibility.valid_candidate_authority(target):
            authority_reasons.append("candidate_authority_contract_invalid")
        matching_cores = cores_by_key.get(_core_join_key(target) or (), [])
        if len(matching_cores) != 1:
            authority_reasons.append(
                "ambiguous_outcome_identity"
                if len(matching_cores) > 1
                else "unmatched_outcome_identity"
            )
        else:
            core = matching_cores[0]
            if not outcome_eligibility.valid_core_authority(core):
                authority_reasons.append("core_authority_contract_invalid")
            else:
                target.update({f"core_{key}": value for key, value in core.items()})
                for key, value in core.items():
                    if key not in target or target.get(key) in (None, "", (), []):
                        target[key] = value
        if authority_reasons:
            base_join_reasons[id(target)] = tuple(authority_reasons)
    base_rows = candidate_rows
    bases_by_identity: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    invalid_bases: list[dict[str, Any]] = []
    for row in base_rows:
        identity = outcome_eligibility.canonical_join_identity(
            row,
            allow_integrated_candidate_alias=True,
        )
        if identity is None:
            invalid_bases.append(row)
        else:
            bases_by_identity[identity].append(row)
    outcomes_by_identity: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    invalid_outcomes: list[dict[str, Any]] = []
    for row in outcome_materialized:
        identity = outcome_eligibility.canonical_join_identity(row)
        if identity is None:
            invalid_outcomes.append(row)
        else:
            outcomes_by_identity[identity].append(row)
    base_aliases = {
        alias
        for row in base_rows
        for alias in _loose_identity_aliases(row)
    }
    outcome_aliases = {
        alias
        for row in outcome_materialized
        for alias in _loose_identity_aliases(row)
    }
    out: list[dict[str, Any]] = []
    for identity in sorted(set(bases_by_identity) | set(outcomes_by_identity)):
        bases = bases_by_identity.get(identity, [])
        outcomes = outcomes_by_identity.get(identity, [])
        if len(bases) == 1 and len(outcomes) == 1:
            _append_performance_observation(
                out, namespace_dir, bases[0], outcomes[0], identity in delivery_identities,
                generated_at, stale_after_days, base_join_reasons.get(id(bases[0]), ()),
            )
            continue
        if len(bases) == 1 and len(outcomes) > 1:
            for outcome in outcomes:
                _append_performance_observation(
                    out, namespace_dir, bases[0], outcome, identity in delivery_identities,
                    generated_at, stale_after_days,
                    (*base_join_reasons.get(id(bases[0]), ()), "duplicate_outcome_identity"),
                )
            continue
        if bases:
            reasons = ("ambiguous_outcome_identity",) if len(bases) > 1 else (
                "identity_mismatch"
                if any(alias in outcome_aliases for row in bases for alias in _loose_identity_aliases(row))
                else "unmatched_outcome_identity",
            )
            for row in bases:
                _append_performance_observation(
                    out, namespace_dir, row, {}, identity in delivery_identities,
                    generated_at, stale_after_days, reasons,
                )
        if outcomes:
            reasons = ("duplicate_outcome_identity",) if len(outcomes) > 1 else (
                "identity_mismatch"
                if any(alias in base_aliases for alias in _loose_identity_aliases(outcomes[0]))
                else "unmatched_outcome_identity",
            )
            for outcome in outcomes:
                _append_performance_observation(
                    out, namespace_dir, outcome, outcome, identity in delivery_identities,
                    generated_at, stale_after_days, reasons,
                )
    for row in invalid_bases:
        _append_performance_observation(
            out, namespace_dir, row, {}, False, generated_at, stale_after_days,
            ("ambiguous_outcome_identity",) if _loose_identity_aliases(row) else ("unmatched_outcome_identity",),
        )
    for outcome in invalid_outcomes:
        _append_performance_observation(
            out, namespace_dir, outcome, outcome, False, generated_at, stale_after_days,
            ("ambiguous_outcome_identity",) if _loose_identity_aliases(outcome) else ("unmatched_outcome_identity",),
        )
    return out


def _performance_observation_row(
    namespace_dir: Path,
    row: Mapping[str, Any],
    *,
    outcome: Mapping[str, Any],
    delivered: bool,
    generated_at: str,
    stale_after_days: int,
    join_ineligible_reasons: Iterable[str] = (),
) -> dict[str, Any]:
    authoritative_outcome = dict(outcome)
    for field in outcome_eligibility.OUTCOME_ATTRIBUTION_FIELDS:
        authoritative_outcome.pop(field, None)
        value = row.get(field)
        if value in (None, "", (), []):
            value = row.get(f"core_{field}")
        authoritative_outcome[field] = (
            value if value not in (None, "", (), []) else "unknown"
        )
    lane = _first_text(
        authoritative_outcome,
        row,
        "opportunity_type",
        default="UNCONFIRMED_RESEARCH",
    ).upper()
    label = str(authoritative_outcome.get("outcome_label") or "").strip()
    maturation_state = _maturation_state(
        row,
        authoritative_outcome,
        generated_at=generated_at,
        stale_after_days=stale_after_days,
    )
    calibration_eligible, calibration_reasons = outcome_eligibility.effective_calibration_state(
        authoritative_outcome,
        additional_reasons=join_ineligible_reasons,
        evaluated_at=generated_at,
    )
    validation = (
        outcome_eligibility.deterministic_validation_status(authoritative_outcome)
        if calibration_eligible
        else "inconclusive"
    )
    if maturation_state in {"pending", "stale"} and not label:
        validation = "inconclusive"
    provider = _dimension_primary(row, {}, "provider")
    source_pack = _dimension_primary(row, {}, "source_pack")
    source_origin = _dimension_primary(row, {}, "source_origin")
    decision = decision_model_values(row)
    return {
        "namespace": namespace_dir.name,
        "run_id": _first_text(outcome, row, "run_id", default=""),
        "profile": _first_text(outcome, row, "profile", default=""),
        "artifact_namespace": _first_text(outcome, row, "artifact_namespace", default=""),
        "candidate_id": _first_text(outcome, row, "candidate_id", default=""),
        "core_opportunity_id": _first_text(outcome, row, "core_opportunity_id", default=""),
        "symbol": _first_text(row, {}, "symbol", default="UNKNOWN"),
        "coin_id": _first_text(row, {}, "coin_id", default=""),
        "opportunity_type": lane,
        "source_origin": source_origin,
        "source_pack": source_pack,
        "provider": provider,
        "market_state_class": _dimension_primary(row, {}, "market_state_class"),
        "crowding_class": _dimension_primary(row, {}, "crowding_class"),
        "source_strength": _dimension_primary(row, {}, "source_strength"),
        **decision,
        "maturation_state": maturation_state,
        "outcome_data_source": str(authoritative_outcome.get("outcome_data_source") or "legacy"),
        "primary_horizon": str(authoritative_outcome.get("primary_horizon") or ""),
        "calibration_eligible": calibration_eligible,
        "calibration_ineligible_reasons": list(calibration_reasons),
        "outcome_label": label or ("pending" if maturation_state == "pending" else maturation_state),
        "validation_label": validation,
        "delivered": delivered,
        "time_to_confirmation_hours": (
            _time_to_confirmation_hours(lane, authoritative_outcome)
            if calibration_eligible
            else None
        ),
        "observed_at": _first_text(authoritative_outcome, row, "observed_at", default=""),
        "preview_time": str(authoritative_outcome.get("preview_time") or ""),
        "include_in_main_aggregate": (
            lane != "DIAGNOSTIC"
            and str(decision.get("radar_route") or "").strip().casefold() != "diagnostic"
        ),
    }


def _append_performance_observation(
    target: list[dict[str, Any]],
    namespace_dir: Path,
    row: Mapping[str, Any],
    outcome: Mapping[str, Any],
    delivered: bool,
    generated_at: str,
    stale_after_days: int,
    reasons: Iterable[str],
) -> None:
    target.append(_performance_observation_row(
        namespace_dir,
        row,
        outcome=outcome,
        delivered=delivered,
        generated_at=generated_at,
        stale_after_days=stale_after_days,
        join_ineligible_reasons=reasons,
    ))


def _core_join_key(row: Mapping[str, Any]) -> tuple[str, ...] | None:
    values = (
        row.get("core_opportunity_id"),
        row.get("run_id"),
        row.get("profile"),
        row.get("artifact_namespace"),
    )
    return tuple(values) if all(type(value) is str and value and value == value.strip() for value in values) else None


def _loose_identity_aliases(row: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    aliases: list[tuple[str, str]] = []
    candidate_id = row.get("candidate_id") or row.get("integrated_candidate_id")
    core_id = row.get("core_opportunity_id")
    if type(candidate_id) is str and candidate_id:
        aliases.append(("candidate_id", candidate_id))
    if type(core_id) is str and core_id:
        aliases.append(("core_opportunity_id", core_id))
    return tuple(aliases)


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
        "thesis_origin_contributor": ("thesis_origins",),
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
    canonical_state = outcome_eligibility.primary_horizon_maturation_state(outcome)
    if canonical_state is not None:
        return canonical_state
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
    return outcome_eligibility.filled_horizon_count(row)


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
    matured_rows = [
        row for row in materialized
        if row.get("calibration_eligible") is True
        and row.get("maturation_state") == "matured"
    ]
    validated = sum(1 for row in matured_rows if row.get("validation_label") == "validated")
    noise = sum(1 for row in matured_rows if row.get("validation_label") == "invalidated/noise")
    inconclusive = sum(1 for row in matured_rows if row.get("validation_label") == "inconclusive")
    time_values = [_safe_number(row.get("time_to_confirmation_hours")) for row in matured_rows]
    time_values = [value for value in time_values if value is not None]
    return {
        "rows": len(matured_rows),
        "input_rows": len(materialized),
        "calibration_eligible_rows": len(matured_rows),
        "calibration_ineligible_rows": len(materialized) - len(matured_rows),
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
        if row.get("calibration_eligible") is True
        and row.get("validation_label") == "validated"
        and row.get("maturation_state") == "matured"
    )
    noise = sum(
        1
        for row in unconfirmed_rows
        if row.get("calibration_eligible") is True
        and row.get("validation_label") == "invalidated/noise"
        and row.get("maturation_state") == "matured"
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
    sample = int(summary["validated_count"]) + int(summary["invalidated_noise_count"])
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
    return outcome_eligibility.finite_number(value)


def _rate_text(value: Any) -> str:
    number = _safe_number(value)
    return "n/a" if number is None else f"{number:.2f}"


def _number_text(value: Any) -> str:
    number = _safe_number(value)
    return "n/a" if number is None else f"{number:.2f}"


def _pct(value: Any) -> str:
    number = outcome_eligibility.finite_number(value)
    return "n/a" if number is None else f"{number * 100:+.2f}%"


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
