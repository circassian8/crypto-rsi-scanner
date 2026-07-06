"""Weekly burn-in measurement dashboard for Event Alpha artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from . import common
from . import evidence_semantics
from . import namespace_policy
from .daily_burn_in import RUN_JSON


DASHBOARD_JSON = "event_alpha_burn_in_measurement_dashboard.json"
DASHBOARD_MD = "event_alpha_burn_in_measurement_dashboard.md"


def build_measurement_dashboard(
    *,
    profile: str = "live_burn_in_no_send",
    artifact_namespace: str | None = None,
    base_dir: str | Path | None = None,
    days: int = 30,
    include_notification_rehearsals: bool = False,
    include_no_key_namespaces: bool = False,
    include_provider_rehearsals: bool = False,
    include_fixture_namespaces: bool = False,
    include_stale_namespaces: bool = False,
    include_live_rehearsals_without_burn_in_run: bool = False,
    include_namespaces: tuple[str, ...] = (),
) -> dict[str, Any]:
    context = common.context_for(profile=profile, artifact_namespace=artifact_namespace or profile, base_dir=base_dir)
    base = context.base_dir
    cutoff = common.date_window(days)
    policy = namespace_policy.build_namespace_policy(
        profile=profile,
        artifact_namespace=context.artifact_namespace,
        base_dir=base,
        include_notification_rehearsals=include_notification_rehearsals,
        include_no_key_namespaces=include_no_key_namespaces,
        include_provider_rehearsals=include_provider_rehearsals,
        include_fixture_namespaces=include_fixture_namespaces,
        include_stale_namespaces=include_stale_namespaces,
        include_live_rehearsals_without_burn_in_run=include_live_rehearsals_without_burn_in_run,
        include_namespaces=((artifact_namespace,) if artifact_namespace else include_namespaces),
    )
    included_namespaces = namespace_policy.included_namespace_names(policy)
    candidates = _rows(base, "event_integrated_radar_candidates.jsonl", cutoff=cutoff, namespaces=included_namespaces)
    cores = _rows(base, "event_core_opportunities.jsonl", cutoff=cutoff, namespaces=included_namespaces)
    deliveries = _rows(base, "event_alpha_notification_deliveries.jsonl", cutoff=cutoff, namespaces=included_namespaces)
    feedback = _rows(base, "event_alpha_feedback.jsonl", cutoff=cutoff, namespaces=included_namespaces)
    outcomes = _rows(base, "event_integrated_radar_outcomes.jsonl", cutoff=cutoff, namespaces=included_namespaces) + _rows(base, "event_alpha_outcomes.jsonl", cutoff=cutoff, namespaces=included_namespaces)
    coverage_docs = [common.read_json(base / namespace / "event_alpha_source_coverage.json") for namespace in included_namespaces]
    provider_health = [common.read_json(base / namespace / "event_provider_health.json") for namespace in included_namespaces]
    daily_runs = _json_docs(base, RUN_JSON, namespaces=included_namespaces)
    evidence_summaries = evidence_semantics.namespace_summaries(base, included_namespaces, cutoff=cutoff, policy=policy)
    evidence_aggregate = evidence_semantics.aggregate_namespace_summaries(evidence_summaries)
    fixture_cycles = [
        name for name, status in (policy.get("namespace_status") or {}).items()
        if name not in included_namespaces and ("fixture" in str(name).casefold() or "smoke" in str(name).casefold() or status == "active_fixture_smoke")
    ]
    stale_cycles = [
        name for name, status in (policy.get("namespace_status") or {}).items()
        if name not in included_namespaces and status in {"stale_deprecated", "archived", "quarantine"}
    ]
    diagnostic_rows = [row for row in candidates + cores if common.row_lane(row) == "DIAGNOSTIC"]
    main_candidates = [row for row in candidates if common.row_lane(row) != "DIAGNOSTIC"]
    labels_by_lane = common.count_by(feedback, "lane", "opportunity_type")
    label_coverage = _label_coverage(feedback, candidates + cores)
    explicit_scope = bool(artifact_namespace) or _has_explicit_policy_flags(policy.get("explicit_inclusion_flags") or {})
    contract_countable = not explicit_scope
    real_burn_in_candidate_count = len(evidence_aggregate["real_candidate_rows"]) if contract_countable else 0
    non_burn_in_candidate_count = max(0, len(candidates) - real_burn_in_candidate_count)
    evidence_scope, candidate_evidence_explanation = _evidence_scope(
        explicit_scope=explicit_scope,
        contract_countable=contract_countable,
        included_namespaces=included_namespaces,
        candidate_evidence=evidence_aggregate,
        policy=policy,
    )
    explicit_scope_warning = (
        "explicit namespace diagnostic; not counted as burn-in contract aggregate"
        if explicit_scope
        else ""
    )
    low_sample_warning = len(feedback) < 150 or len(outcomes) < 100 or not included_namespaces or bool(explicit_scope_warning)
    enough_data_reasons = _enough_data_reasons(
        included_namespaces=included_namespaces if contract_countable else [],
        feedback=feedback,
        outcomes=outcomes,
        daily_runs=daily_runs,
    )
    if explicit_scope_warning:
        enough_data_reasons = ["explicit_namespace_not_counted_for_burn_in_contract", *enough_data_reasons]
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_burn_in_measurement_dashboard_v1",
            "row_type": "event_alpha_burn_in_measurement_dashboard",
            "generated_at": common.utc_now().isoformat(),
            "profile": profile,
            "artifact_namespace": context.artifact_namespace,
            "namespace_dir": common.rel_path(context.namespace_dir),
            "window_days": days,
            "namespace_policy": _policy_summary(policy),
            **_policy_flat_fields(policy, included_namespaces),
            "evidence_scope": evidence_scope,
            "burn_in_contract_scope": "explicit_single_namespace_diagnostic" if explicit_scope else "active_burn_in_namespaces",
            "candidate_source_scope": "single_namespace" if artifact_namespace else "active_burn_in_namespaces",
            "explicit_scope_warning": explicit_scope_warning,
            "included_namespace_count": len(included_namespaces),
            "excluded_namespace_count": len(policy.get("excluded_namespaces") or []),
            "live_cycles": len(daily_runs),
            "fixture_cycles": len(fixture_cycles),
            "stale_cycles": len(stale_cycles),
            "real_burn_in_candidate_count": real_burn_in_candidate_count,
            "non_burn_in_candidate_count": non_burn_in_candidate_count,
            "contract_counted_candidate_count": real_burn_in_candidate_count,
            "candidate_evidence_explanation": candidate_evidence_explanation,
            **evidence_semantics.payload_fields(evidence_aggregate),
            "notification_rehearsal_candidate_count": _category_candidate_count(base, policy, "notification_rehearsal", cutoff=cutoff),
            "provider_rehearsal_candidate_count": _category_candidate_count(base, policy, "provider_rehearsal", cutoff=cutoff),
            "fixture_candidate_count": _category_candidate_count(base, policy, "fixture", cutoff=cutoff),
            "stale_candidate_count": _category_candidate_count(base, policy, "stale", cutoff=cutoff),
            "no_key_candidate_count": _category_candidate_count(base, policy, "no_key", cutoff=cutoff),
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
            "label_coverage": label_coverage,
            "label_coverage_pct": label_coverage,
            "outcome_rows_by_status": common.count_by(outcomes, "status", "outcome_status", "validation_status"),
            "outcome_rows_by_horizon": common.count_by(outcomes, "horizon", "horizon_days"),
            "source_coverage_docs": len([row for row in coverage_docs if row]),
            "diagnostic_rows_excluded_from_main_aggregate": len(diagnostic_rows),
            "low_sample_warning": low_sample_warning,
            "min_sample_warning": low_sample_warning,
            "enough_data": not enough_data_reasons,
            "enough_data_reasons": enough_data_reasons,
            "source_yield_confidence": "low" if low_sample_warning else "measured",
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
        f"- evidence_scope: `{payload.get('evidence_scope')}`",
        f"- burn_in_contract_scope: `{payload.get('burn_in_contract_scope')}`",
        f"- included_namespaces: `{', '.join(payload.get('included_namespaces') or []) or 'none'}`",
        f"- explicit_scope_warning: `{payload.get('explicit_scope_warning') or 'none'}`",
        f"- real_burn_in_candidate_count: `{payload.get('real_burn_in_candidate_count')}`",
        f"- contract_counted_candidate_count: `{payload.get('contract_counted_candidate_count')}`",
        f"- candidate_evidence_explanation: `{payload.get('candidate_evidence_explanation')}`",
        f"- non_burn_in_candidate_count: `{payload.get('non_burn_in_candidate_count')}`",
        f"- low_sample_warning: `{payload.get('low_sample_warning')}`",
        f"- enough_data: `{payload.get('enough_data')}`",
        f"- enough_data_reasons: `{', '.join(payload.get('enough_data_reasons') or []) or 'none'}`",
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


def _rows(base: Path, filename: str, *, cutoff, namespaces: list[str] | tuple[str, ...]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for namespace in namespaces:
        path = base / namespace / filename
        for row in common.read_jsonl(path):
            if (common.timestamp_for_row(row) or common.utc_now()) >= cutoff:
                out.append(row)
    return out


def _json_docs(base: Path, filename: str, *, namespaces: list[str] | tuple[str, ...]) -> list[dict[str, Any]]:
    return [row for namespace in namespaces if (row := common.read_json(base / namespace / filename))]


def _policy_summary(policy: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "namespace_policy_version": policy.get("namespace_policy_version"),
        "included_namespaces": policy.get("included_namespaces") or [],
        "excluded_namespaces": policy.get("excluded_namespaces") or [],
        "exclusion_reasons": policy.get("exclusion_reasons") or {},
        "excluded_reasons": policy.get("excluded_reasons") or policy.get("exclusion_reasons") or {},
        "explicit_inclusion_flags": policy.get("explicit_inclusion_flags") or {},
        "namespace_status": policy.get("namespace_status") or {},
        "latest_doctor_status": policy.get("latest_doctor_status") or {},
        "latest_run_id": policy.get("latest_run_id") or {},
        "artifact_counts": policy.get("artifact_counts") or {},
    }


def _policy_flat_fields(policy: Mapping[str, Any], included_namespaces: list[str]) -> dict[str, Any]:
    summary = _policy_summary(policy)
    return {
        "namespace_policy_version": summary["namespace_policy_version"],
        "explicit_inclusion_flags": summary["explicit_inclusion_flags"],
        "included_namespaces": included_namespaces,
        "excluded_namespaces": summary["excluded_namespaces"],
        "exclusion_reasons": summary["exclusion_reasons"],
        "excluded_reasons": summary["excluded_reasons"],
        "namespace_status": summary["namespace_status"],
        "latest_doctor_status": summary["latest_doctor_status"],
        "latest_run_id": summary["latest_run_id"],
        "artifact_counts": summary["artifact_counts"],
    }


def _evidence_scope(
    *,
    explicit_scope: bool,
    contract_countable: bool,
    included_namespaces: list[str],
    candidate_evidence: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> tuple[str, str]:
    if explicit_scope and not contract_countable:
        return "explicit_single_namespace_diagnostic", "explicit namespace is diagnostic unless counted intentionally"
    if _mixed_non_burn_in_categories(policy):
        return "mixed_explicit_diagnostic", "explicit non-burn-in namespace categories are mixed into the selection"
    return evidence_semantics.evidence_scope_from_summary(
        explicit_scope=explicit_scope,
        contract_countable=contract_countable,
        included_namespaces=included_namespaces,
        aggregate=candidate_evidence,
    )


def _has_explicit_policy_flags(flags: Mapping[str, Any]) -> bool:
    for key, value in flags.items():
        if key == "include_namespace":
            if value:
                return True
        elif bool(value):
            return True
    return False


def _mixed_non_burn_in_categories(policy: Mapping[str, Any]) -> bool:
    for row in policy.get("included_namespace_details") or []:
        if not isinstance(row, Mapping):
            continue
        categories = {str(item) for item in row.get("categories") or []}
        if categories & {"notification_rehearsal", "provider_rehearsal", "fixture", "stale", "no_key", "active_live_rehearsal"}:
            return True
    return False


def _category_candidate_count(base: Path, policy: Mapping[str, Any], category: str, *, cutoff) -> int:
    namespaces: list[str] = []
    for section in ("included_namespace_details", "excluded_namespace_details"):
        for row in policy.get(section) or []:
            if isinstance(row, Mapping) and category in {str(item) for item in row.get("categories") or []}:
                name = str(row.get("namespace") or "")
                if name:
                    namespaces.append(name)
    return len(_rows(base, "event_integrated_radar_candidates.jsonl", cutoff=cutoff, namespaces=sorted(dict.fromkeys(namespaces))))


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


def _enough_data_reasons(
    *,
    included_namespaces: list[str],
    feedback: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    daily_runs: list[dict[str, Any]],
) -> list[str]:
    reasons: list[str] = []
    if not included_namespaces:
        reasons.append("no_active_burn_in_namespaces")
    if not daily_runs:
        reasons.append("no_live_no_send_cycles")
    if len(feedback) < 150:
        reasons.append(f"min_human_labels:{len(feedback)}/150")
    if len(outcomes) < 100:
        reasons.append(f"min_outcome_rows:{len(outcomes)}/100")
    return reasons


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write Event Alpha burn-in weekly measurement dashboard.")
    parser.add_argument("--profile", default="live_burn_in_no_send")
    parser.add_argument("--artifact-namespace", default=None)
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--include-notification-rehearsals", action="store_true")
    parser.add_argument("--include-no-key-namespaces", action="store_true")
    parser.add_argument("--include-provider-rehearsals", action="store_true")
    parser.add_argument("--include-fixture-namespaces", action="store_true")
    parser.add_argument("--include-stale-namespaces", action="store_true")
    parser.add_argument("--include-live-rehearsals-without-burn-in-run", action="store_true")
    parser.add_argument("--include-namespace", action="append", default=[])
    args = parser.parse_args(argv)
    payload = build_measurement_dashboard(
        profile=args.profile,
        artifact_namespace=args.artifact_namespace,
        base_dir=args.base_dir,
        days=args.days,
        include_notification_rehearsals=args.include_notification_rehearsals,
        include_no_key_namespaces=args.include_no_key_namespaces,
        include_provider_rehearsals=args.include_provider_rehearsals,
        include_fixture_namespaces=args.include_fixture_namespaces,
        include_stale_namespaces=args.include_stale_namespaces,
        include_live_rehearsals_without_burn_in_run=args.include_live_rehearsals_without_burn_in_run,
        include_namespaces=tuple(args.include_namespace),
    )
    print(f"event_alpha_burn_in_measurement_dashboard: {payload['namespace_dir']}/{DASHBOARD_MD}")
    print(f"low_sample_warning={payload['low_sample_warning']} auto_apply_thresholds={payload['auto_apply_thresholds']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
