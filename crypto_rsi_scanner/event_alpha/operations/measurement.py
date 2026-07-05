"""Weekly burn-in measurement dashboard for Event Alpha artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from . import common


DASHBOARD_JSON = "event_alpha_burn_in_measurement_dashboard.json"
DASHBOARD_MD = "event_alpha_burn_in_measurement_dashboard.md"


def build_measurement_dashboard(
    *,
    profile: str = "live_burn_in_no_send",
    artifact_namespace: str | None = None,
    base_dir: str | Path | None = None,
    days: int = 30,
) -> dict[str, Any]:
    context = common.context_for(profile=profile, artifact_namespace=artifact_namespace or profile, base_dir=base_dir)
    base = context.base_dir
    cutoff = common.date_window(days)
    candidates = _rows(base, "event_integrated_radar_candidates.jsonl", cutoff=cutoff)
    cores = _rows(base, "event_core_opportunities.jsonl", cutoff=cutoff)
    deliveries = _rows(base, "event_alpha_notification_deliveries.jsonl", cutoff=cutoff)
    feedback = _rows(base, "event_alpha_feedback.jsonl", cutoff=cutoff)
    outcomes = _rows(base, "event_integrated_radar_outcomes.jsonl", cutoff=cutoff) + _rows(base, "event_alpha_outcomes.jsonl", cutoff=cutoff)
    coverage_docs = [common.read_json(path) for path in base.glob("*/event_alpha_source_coverage.json")]
    provider_health = [common.read_json(path) for path in base.glob("*/event_provider_health.json")]
    diagnostic_rows = [row for row in candidates + cores if common.row_lane(row) == "DIAGNOSTIC"]
    main_candidates = [row for row in candidates if common.row_lane(row) != "DIAGNOSTIC"]
    labels_by_lane = common.count_by(feedback, "lane", "opportunity_type")
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_burn_in_measurement_dashboard_v1",
            "row_type": "event_alpha_burn_in_measurement_dashboard",
            "generated_at": common.utc_now().isoformat(),
            "profile": profile,
            "artifact_namespace": context.artifact_namespace,
            "namespace_dir": common.rel_path(context.namespace_dir),
            "window_days": days,
            "candidates_by_opportunity_type": common.count_by(main_candidates, "opportunity_type", "lane"),
            "rendered_vs_skipped_counts": {
                "rendered": sum(1 for row in deliveries if str(row.get("state") or "").casefold() in {"sent", "would_send", "rendered"}),
                "skipped": sum(1 for row in deliveries if "skip" in str(row.get("state") or "").casefold()),
            },
            "labels_by_lane": labels_by_lane,
            "feedback_label_counts": common.count_by(feedback, "label"),
            "validation_rate_by_lane": _validation_rates(outcomes),
            "source_noise_rate_by_provider": _source_noise_rate(feedback, "source_provider", "provider"),
            "source_noise_rate_by_source_pack": _source_noise_rate(feedback, "source_pack"),
            "accepted_evidence_rate": _accepted_evidence_rate(candidates + cores),
            "market_confirmation_rate": _market_confirmation_rate(candidates + cores),
            "near_miss_count": sum(1 for row in candidates + cores if _mentions(row, "near")),
            "quality_capped_count": sum(1 for row in candidates + cores if _mentions(row, "quality") or _mentions(row, "cap")),
            "provider_degraded_backoff_rate": _provider_degraded_rate(provider_health),
            "label_coverage_pct": _label_coverage(feedback, candidates + cores),
            "outcome_rows_by_status": common.count_by(outcomes, "status", "outcome_status", "validation_status"),
            "outcome_rows_by_horizon": common.count_by(outcomes, "horizon", "horizon_days"),
            "source_coverage_docs": len([row for row in coverage_docs if row]),
            "diagnostic_rows_excluded_from_main_aggregate": len(diagnostic_rows),
            "low_sample_warning": len(feedback) < 150 or len(outcomes) < 100,
            "auto_apply_thresholds": False,
            "first_real_run_interpretation": {
                "source": "notify_llm_deep_cryptopanic_rehearsal",
                "real_candidates": 59,
                "high_priority": 0,
                "digest": 0,
                "watchlist": 0,
                "near_miss": 14,
                "quality_capped": 36,
                "interpretation": "inconclusive until human labels and outcome rows meet burn-in thresholds",
            },
        }
    )
    common.write_json(context.namespace_dir / DASHBOARD_JSON, payload)
    common.write_text(context.namespace_dir / DASHBOARD_MD, format_measurement_dashboard(payload))
    return payload


def format_measurement_dashboard(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Event Alpha Burn-In Measurement Dashboard",
        "",
        "Research-only measurement dashboard. Counts are descriptive and do not auto-change thresholds.",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- profile: `{payload.get('profile')}`",
        f"- artifact_namespace: `{payload.get('artifact_namespace')}`",
        f"- low_sample_warning: `{payload.get('low_sample_warning')}`",
        f"- auto_apply_thresholds: `{payload.get('auto_apply_thresholds')}`",
        f"- diagnostic_rows_excluded_from_main_aggregate: `{payload.get('diagnostic_rows_excluded_from_main_aggregate')}`",
        "",
        "## Aggregates",
        "",
        common.table_line("candidates_by_opportunity_type", payload.get("candidates_by_opportunity_type") or {}),
        common.table_line("feedback_label_counts", payload.get("feedback_label_counts") or {}),
        common.table_line("labels_by_lane", payload.get("labels_by_lane") or {}),
        common.table_line("outcome_rows_by_status", payload.get("outcome_rows_by_status") or {}),
        "",
        "## Rates",
        "",
        f"- accepted_evidence_rate: `{payload.get('accepted_evidence_rate')}`",
        f"- market_confirmation_rate: `{payload.get('market_confirmation_rate')}`",
        f"- provider_degraded_backoff_rate: `{payload.get('provider_degraded_backoff_rate')}`",
        f"- label_coverage_pct: `{payload.get('label_coverage_pct')}`",
        "",
        "## First Real Run Interpretation",
        "",
    ]
    first = payload.get("first_real_run_interpretation") or {}
    for key, value in first.items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    lines.append("Interpretation remains inconclusive until label and outcome thresholds are met.")
    return "\n".join(lines).rstrip()


def _rows(base: Path, filename: str, *, cutoff) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in base.glob("*/" + filename):
        for row in common.read_jsonl(path):
            if (common.timestamp_for_row(row) or common.utc_now()) >= cutoff:
                out.append(row)
    return out


def _mentions(row: Mapping[str, Any], needle: str) -> bool:
    return needle.casefold() in " ".join(str(value) for value in row.values()).casefold()


def _validation_rates(rows: list[dict[str, Any]]) -> dict[str, float]:
    by_lane: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_lane.setdefault(common.row_lane(row), []).append(row)
    out: dict[str, float] = {}
    for lane, lane_rows in by_lane.items():
        validated = sum(1 for row in lane_rows if str(row.get("validation_status") or row.get("status") or "").casefold() in {"validated", "continued", "continuation"})
        out[lane] = round(100.0 * validated / len(lane_rows), 2) if lane_rows else 0.0
    return out


def _source_noise_rate(rows: list[dict[str, Any]], *fields: str) -> dict[str, float]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = next((str(row.get(field) or "").strip() for field in fields if str(row.get(field) or "").strip()), "unknown")
        groups.setdefault(key, []).append(row)
    return {
        key: round(100.0 * sum(1 for row in data if str(row.get("label") or "") in {"junk", "source_noise", "false_positive"}) / len(data), 2)
        for key, data in sorted(groups.items())
        if data
    }


def _accepted_evidence_rate(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    accepted = sum(1 for row in rows if row.get("accepted_evidence") or common.int_value(row.get("accepted_evidence_count")) > 0)
    return round(100.0 * accepted / len(rows), 2)


def _market_confirmation_rate(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    confirmed = sum(1 for row in rows if str(row.get("market_confirmation_level") or row.get("market_state_class") or "").casefold() in {"confirmed", "strong", "breakout", "fresh"})
    return round(100.0 * confirmed / len(rows), 2)


def _provider_degraded_rate(rows: list[dict[str, Any]]) -> float:
    flattened: list[Mapping[str, Any]] = []
    for row in rows:
        if isinstance(row, Mapping):
            for value in row.values():
                if isinstance(value, Mapping):
                    flattened.append(value)
    if not flattened:
        return 0.0
    degraded = sum(1 for row in flattened if str(row.get("status") or row.get("provider_health_status") or "").casefold() in {"degraded", "backoff", "provider_unavailable", "rate_limited"})
    return round(100.0 * degraded / len(flattened), 2)


def _label_coverage(feedback: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> float:
    if not candidates:
        return 0.0
    targets = {common.item_family(row) for row in candidates}
    labels = {common.item_family(row) for row in feedback}
    return round(100.0 * len(targets & labels) / len(targets), 2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write Event Alpha burn-in weekly measurement dashboard.")
    parser.add_argument("--profile", default="live_burn_in_no_send")
    parser.add_argument("--artifact-namespace", default=None)
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args(argv)
    payload = build_measurement_dashboard(profile=args.profile, artifact_namespace=args.artifact_namespace, base_dir=args.base_dir, days=args.days)
    print(f"event_alpha_burn_in_measurement_dashboard: {payload['namespace_dir']}/{DASHBOARD_MD}")
    print(f"low_sample_warning={payload['low_sample_warning']} auto_apply_thresholds={payload['auto_apply_thresholds']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
