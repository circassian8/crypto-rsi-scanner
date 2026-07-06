"""Burn-in scorecard artifact writer for Event Alpha daily operations."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from . import common
from .daily_burn_in import RUN_JSON
from . import namespace_policy


SCORECARD_JSON = "event_alpha_burn_in_scorecard.json"
SCORECARD_MD = "event_alpha_burn_in_scorecard.md"


def build_scorecard(
    *,
    profile: str = "live_burn_in_no_send",
    artifact_namespace: str | None = None,
    base_dir: str | Path | None = None,
    days: int = 30,
    include_fixture_namespaces: bool = False,
    include_stale_namespaces: bool = False,
    include_namespaces: tuple[str, ...] = (),
) -> dict[str, Any]:
    context = common.context_for(profile=profile, artifact_namespace=artifact_namespace or profile, base_dir=base_dir)
    base = context.base_dir
    contract = common.load_contract()
    cutoff = common.date_window(days)
    policy = namespace_policy.build_namespace_policy(
        profile=profile,
        artifact_namespace=context.artifact_namespace,
        base_dir=base,
        include_fixture_namespaces=include_fixture_namespaces,
        include_stale_namespaces=include_stale_namespaces,
        include_namespaces=((artifact_namespace,) if artifact_namespace else include_namespaces),
    )
    included_namespaces = namespace_policy.included_namespace_names(policy)
    daily_runs = _daily_runs(base, cutoff=cutoff, namespaces=included_namespaces)
    candidate_rows = _all_rows(base, "event_integrated_radar_candidates.jsonl", cutoff=cutoff, namespaces=included_namespaces)
    core_rows = _all_rows(base, "event_core_opportunities.jsonl", cutoff=cutoff, namespaces=included_namespaces)
    alert_rows = _all_rows(base, "event_alpha_alerts.jsonl", cutoff=cutoff, namespaces=included_namespaces)
    feedback_rows = _all_rows(base, "event_alpha_feedback.jsonl", cutoff=cutoff, namespaces=included_namespaces)
    outcome_rows = _all_rows(base, "event_integrated_radar_outcomes.jsonl", cutoff=cutoff, namespaces=included_namespaces) + _all_rows(base, "event_alpha_outcomes.jsonl", cutoff=cutoff, namespaces=included_namespaces)
    source_coverage_rows = [common.read_json(base / namespace / "event_alpha_source_coverage.json") for namespace in included_namespaces]
    fixture_namespaces = [
        name
        for name, status in (policy.get("namespace_status") or {}).items()
        if name not in included_namespaces and ("fixture" in str(name).casefold() or "smoke" in str(name).casefold() or status == "active_fixture_smoke")
    ]
    stale_namespaces = [
        name
        for name, status in (policy.get("namespace_status") or {}).items()
        if name not in included_namespaces and status in {"stale_deprecated", "archived", "quarantine"}
    ]
    fixture_candidate_count = len(_all_rows(base, "event_integrated_radar_candidates.jsonl", cutoff=cutoff, namespaces=fixture_namespaces))
    stale_candidate_count = len(_all_rows(base, "event_integrated_radar_candidates.jsonl", cutoff=cutoff, namespaces=stale_namespaces))
    provider_categories = sorted(
        {
            str(row.get("provider") or row.get("source_provider") or row.get("source_origin") or "").strip()
            for row in [*candidate_rows, *core_rows, *source_coverage_rows]
            if str(row.get("provider") or row.get("source_provider") or row.get("source_origin") or "").strip()
        }
    )
    near_misses = [row for row in [*candidate_rows, *core_rows, *alert_rows] if _mentions(row, "near")]
    quality_capped = [row for row in [*candidate_rows, *core_rows, *alert_rows] if _mentions(row, "quality") or _mentions(row, "cap")]
    labeled_near_misses = [
        row for row in feedback_rows
        if _mentions(row, "near") or str(row.get("lane") or row.get("opportunity_type") or "").upper() == "UNCONFIRMED_RESEARCH"
    ]
    enough_data_reasons = _enough_data_reasons(
        contract=contract,
        included_namespaces=included_namespaces,
        daily_runs=daily_runs,
        candidate_rows=candidate_rows,
        feedback_rows=feedback_rows,
        labeled_near_misses=labeled_near_misses,
        outcome_rows=outcome_rows,
    )
    enough_data = (
        not enough_data_reasons
        and included_namespaces
        and (
        len(daily_runs) >= common.contract_threshold(contract, "min_live_no_send_cycles")
        and len(candidate_rows) >= common.contract_threshold(contract, "min_real_candidates")
        and len(feedback_rows) >= common.contract_threshold(contract, "min_human_labels")
        and len(labeled_near_misses) >= common.contract_threshold(contract, "min_labeled_near_misses")
        and len(outcome_rows) >= common.contract_threshold(contract, "min_outcome_rows")
        )
    )
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_burn_in_scorecard_v1",
            "row_type": "event_alpha_burn_in_scorecard",
            "generated_at": common.utc_now().isoformat(),
            "profile": profile,
            "artifact_namespace": context.artifact_namespace,
            "namespace_dir": common.rel_path(context.namespace_dir),
            "window_days": days,
            "namespace_scope": "single_namespace" if artifact_namespace else "policy",
            "include_reason": "explicit_user_namespace" if artifact_namespace else "burn_in_namespace_policy",
            "namespace_policy": {
                "included_namespaces": policy.get("included_namespaces") or [],
                "excluded_namespaces": policy.get("excluded_namespaces") or [],
                "exclusion_reasons": policy.get("exclusion_reasons") or {},
                "namespace_status": policy.get("namespace_status") or {},
                "latest_doctor_status": policy.get("latest_doctor_status") or {},
                "latest_run_id": policy.get("latest_run_id") or {},
                "artifact_counts": policy.get("artifact_counts") or {},
            },
            "included_namespaces": included_namespaces,
            "excluded_namespaces": policy.get("excluded_namespaces") or [],
            "exclusion_reasons": policy.get("exclusion_reasons") or {},
            "namespace_status": policy.get("namespace_status") or {},
            "latest_doctor_status": policy.get("latest_doctor_status") or {},
            "latest_run_id": policy.get("latest_run_id") or {},
            "artifact_counts": policy.get("artifact_counts") or {},
            "contract": contract,
            "live_no_send_cycles_completed": len(daily_runs),
            "real_candidates_seen": len(candidate_rows),
            "fixture_candidate_count": fixture_candidate_count,
            "stale_candidate_count": stale_candidate_count,
            "core_opportunities_seen": len(core_rows),
            "near_misses_seen": len(near_misses),
            "quality_capped_rows": len(quality_capped),
            "strict_count": _count_tier(alert_rows, "STRICT"),
            "strict_alerts": _count_tier(alert_rows, "STRICT"),
            "research_candidates": len(candidate_rows) + len(core_rows),
            "near_misses": len(near_misses),
            "quality_capped": len(quality_capped),
            "digest_count": _count_tier(alert_rows, "RADAR_DIGEST", "daily_digest"),
            "watchlist_count": _count_tier(alert_rows, "WATCHLIST"),
            "high_priority_count": _count_tier(alert_rows, "HIGH_PRIORITY_WATCH"),
            "rendered_research_review_count": _count_field(alert_rows, "rendered", True),
            "skipped_research_review_count": _count_field(alert_rows, "skipped", True),
            "labels_collected": len(feedback_rows),
            "labels": len(feedback_rows),
            "labeled_near_misses": len(labeled_near_misses),
            "outcome_rows": len(outcome_rows),
            "outcomes": len(outcome_rows),
            "provider_categories_observed": provider_categories,
            "provider_categories_observed_count": len(provider_categories),
            "enough_data": enough_data,
            "enough_data_reasons": enough_data_reasons,
            "promotion_freeze_status_by_lane": _lane_statuses(contract, enough_data),
            "auto_apply_thresholds": bool(contract.get("auto_apply_thresholds") is True),
            "auto_apply": False,
            "warnings": _warnings(contract, daily_runs, feedback_rows, enough_data, included_namespaces),
        }
    )
    common.write_json(context.namespace_dir / SCORECARD_JSON, payload)
    common.write_text(context.namespace_dir / SCORECARD_MD, format_scorecard(payload))
    return payload


def format_scorecard(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Event Alpha Burn-In Scorecard",
        "",
        "Research-only burn-in measurement. No thresholds are auto-applied.",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- profile: `{payload.get('profile')}`",
        f"- artifact_namespace: `{payload.get('artifact_namespace')}`",
        f"- namespace_scope: `{payload.get('namespace_scope')}`",
        f"- included_namespaces: `{', '.join(payload.get('included_namespaces') or []) or 'none'}`",
        f"- live_no_send_cycles_completed: `{payload.get('live_no_send_cycles_completed')}`",
        f"- real_candidates_seen: `{payload.get('real_candidates_seen')}`",
        f"- near_misses_seen: `{payload.get('near_misses_seen')}`",
        f"- quality_capped_rows: `{payload.get('quality_capped_rows')}`",
        f"- labels_collected: `{payload.get('labels_collected')}`",
        f"- labeled_near_misses: `{payload.get('labeled_near_misses')}`",
        f"- outcome_rows: `{payload.get('outcome_rows')}`",
        f"- provider_categories_observed_count: `{payload.get('provider_categories_observed_count')}`",
        f"- enough_data: `{payload.get('enough_data')}`",
        f"- enough_data_reasons: `{', '.join(payload.get('enough_data_reasons') or []) or 'none'}`",
        f"- auto_apply_thresholds: `{payload.get('auto_apply_thresholds')}`",
        "",
        "## Route Counts",
        "",
        f"- strict: `{payload.get('strict_count')}`",
        f"- digest: `{payload.get('digest_count')}`",
        f"- watchlist: `{payload.get('watchlist_count')}`",
        f"- high_priority: `{payload.get('high_priority_count')}`",
        f"- rendered_research_review: `{payload.get('rendered_research_review_count')}`",
        f"- skipped_research_review: `{payload.get('skipped_research_review_count')}`",
        "",
        "## Promotion / Freeze Status By Lane",
        "",
    ]
    for lane, status in sorted((payload.get("promotion_freeze_status_by_lane") or {}).items()):
        lines.append(f"- {lane}: `{status}`")
    warnings = payload.get("warnings") or []
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in warnings)
    lines.append("")
    lines.append("No sends, trades, paper trades, normal RSI rows, or Event Alpha TRIGGERED_FADE were created.")
    return "\n".join(lines).rstrip()


def _daily_runs(base: Path, *, cutoff, namespaces: list[str] | tuple[str, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for namespace in namespaces:
        path = base / namespace / RUN_JSON
        row = common.read_json(path)
        if row and (common.parse_utc(row.get("generated_at")) or common.utc_now()) >= cutoff:
            rows.append(row)
    return rows


def _all_rows(base: Path, filename: str, *, cutoff, namespaces: list[str] | tuple[str, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for namespace in namespaces:
        path = base / namespace / filename
        for row in common.read_jsonl(path):
            if (common.timestamp_for_row(row) or common.utc_now()) >= cutoff:
                rows.append(row)
    return rows


def _mentions(row: Mapping[str, Any], needle: str) -> bool:
    text = " ".join(str(value) for value in row.values() if not isinstance(value, (dict, list, tuple)))
    return needle.casefold() in text.casefold()


def _count_tier(rows: list[dict[str, Any]], *needles: str) -> int:
    wanted = {item.casefold() for item in needles}
    return sum(1 for row in rows if str(row.get("tier") or row.get("lane") or row.get("route") or "").casefold() in wanted)


def _count_field(rows: list[dict[str, Any]], field: str, value: Any) -> int:
    return sum(1 for row in rows if row.get(field) == value)


def _lane_statuses(contract: Mapping[str, Any], enough_data: bool) -> dict[str, str]:
    lanes = contract.get("opportunity_lanes") if isinstance(contract.get("opportunity_lanes"), Mapping) else {}
    lane_names = lanes.keys() if lanes else (
        "EARLY_LONG_RESEARCH",
        "CONFIRMED_LONG_RESEARCH",
        "FADE_SHORT_REVIEW",
        "RISK_ONLY",
        "UNCONFIRMED_RESEARCH",
        "DIAGNOSTIC",
    )
    return {str(lane): ("review_ready" if enough_data else "frozen_insufficient_data") for lane in lane_names}


def _enough_data_reasons(
    *,
    contract: Mapping[str, Any],
    included_namespaces: list[str],
    daily_runs: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    feedback_rows: list[dict[str, Any]],
    labeled_near_misses: list[dict[str, Any]],
    outcome_rows: list[dict[str, Any]],
) -> list[str]:
    if not included_namespaces:
        return [
            "no_active_burn_in_namespaces",
            "next_command:make event-alpha-daily-live-no-send-burn-in",
        ]
    checks = (
        ("min_live_no_send_cycles", len(daily_runs)),
        ("min_real_candidates", len(candidate_rows)),
        ("min_human_labels", len(feedback_rows)),
        ("min_labeled_near_misses", len(labeled_near_misses)),
        ("min_outcome_rows", len(outcome_rows)),
    )
    reasons: list[str] = []
    for key, observed in checks:
        threshold = common.contract_threshold(contract, key)
        if threshold and observed < threshold:
            reasons.append(f"{key}:{observed}/{threshold}")
    return reasons


def _warnings(contract: Mapping[str, Any], runs: list[dict[str, Any]], feedback: list[dict[str, Any]], enough_data: bool, included_namespaces: list[str]) -> list[str]:
    warnings: list[str] = []
    if not contract:
        warnings.append("burn-in contract missing")
    if not included_namespaces:
        warnings.append("no active burn-in namespaces selected by namespace policy")
    if contract.get("auto_apply_thresholds") is True:
        warnings.append("auto_apply_thresholds=true is blocked")
    if runs and len(feedback) < max(1, len(runs) * 3):
        warnings.append("label coverage low for completed burn-in cycles")
    if not enough_data:
        warnings.append("insufficient burn-in data; promotion/freeze status remains frozen")
    return warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write Event Alpha burn-in scorecard artifacts.")
    parser.add_argument("--profile", default="live_burn_in_no_send")
    parser.add_argument("--artifact-namespace", default=None)
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--include-fixture-namespaces", action="store_true")
    parser.add_argument("--include-stale-namespaces", action="store_true")
    parser.add_argument("--include-namespace", action="append", default=[])
    args = parser.parse_args(argv)
    payload = build_scorecard(
        profile=args.profile,
        artifact_namespace=args.artifact_namespace,
        base_dir=args.base_dir,
        days=args.days,
        include_fixture_namespaces=args.include_fixture_namespaces,
        include_stale_namespaces=args.include_stale_namespaces,
        include_namespaces=tuple(args.include_namespace),
    )
    print(f"event_alpha_burn_in_scorecard: {payload['namespace_dir']}/{SCORECARD_MD}")
    print(f"enough_data={payload['enough_data']} labels={payload['labels_collected']} outcomes={payload['outcome_rows']}")
    return 1 if payload.get("auto_apply_thresholds") is True else 0


if __name__ == "__main__":
    raise SystemExit(main())
