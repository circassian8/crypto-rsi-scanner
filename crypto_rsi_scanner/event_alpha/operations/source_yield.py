"""Source-pack/provider yield report for Event Alpha burn-in artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from . import common
from . import namespace_policy
from .daily_burn_in import RUN_JSON


SOURCE_YIELD_JSON = "event_alpha_source_yield_report.json"
SOURCE_YIELD_MD = "event_alpha_source_yield_report.md"


def build_source_yield_report(
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
        include_namespaces=((artifact_namespace,) if artifact_namespace else include_namespaces),
    )
    included_namespaces = namespace_policy.included_namespace_names(policy)
    candidates = _rows(base, "event_integrated_radar_candidates.jsonl", cutoff=cutoff, namespaces=included_namespaces)
    cores = _rows(base, "event_core_opportunities.jsonl", cutoff=cutoff, namespaces=included_namespaces)
    feedback = _rows(base, "event_alpha_feedback.jsonl", cutoff=cutoff, namespaces=included_namespaces)
    outcomes = _rows(base, "event_integrated_radar_outcomes.jsonl", cutoff=cutoff, namespaces=included_namespaces) + _rows(base, "event_alpha_outcomes.jsonl", cutoff=cutoff, namespaces=included_namespaces)
    daily_runs = [common.read_json(base / namespace / RUN_JSON) for namespace in included_namespaces]
    daily_runs = [row for row in daily_runs if row]
    evidence_scope = _evidence_scope(artifact_namespace, policy)
    explicit_scope_warning = (
        "explicit namespace diagnostic; not counted as burn-in contract aggregate"
        if artifact_namespace
        else ""
    )
    contract_countable = not bool(artifact_namespace)
    enough_data_reasons = _enough_data_reasons(included_namespaces=included_namespaces if contract_countable else [], feedback=feedback, outcomes=outcomes, daily_runs=daily_runs)
    if explicit_scope_warning:
        enough_data_reasons = ["explicit_namespace_not_counted_for_burn_in_contract", *enough_data_reasons]
    rows = [*candidates, *cores]
    providers = sorted({_provider(row) for row in [*rows, *feedback]})
    source_packs = sorted({_source_pack(row) for row in [*rows, *feedback]})
    provider_rows = {
        provider: _summary_for(provider, "provider", rows=rows, feedback=feedback, outcomes=outcomes)
        for provider in providers
    }
    source_pack_rows = {
        pack: _summary_for(pack, "source_pack", rows=rows, feedback=feedback, outcomes=outcomes)
        for pack in source_packs
    }
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_source_yield_report_v1",
            "row_type": "event_alpha_source_yield_report",
            "generated_at": common.utc_now().isoformat(),
            "profile": profile,
            "artifact_namespace": context.artifact_namespace,
            "namespace_dir": common.rel_path(context.namespace_dir),
            "window_days": days,
            "namespace_policy": {
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
            },
            "namespace_policy_version": policy.get("namespace_policy_version"),
            "evidence_scope": evidence_scope,
            "burn_in_contract_scope": "explicit_single_namespace_diagnostic" if artifact_namespace else "active_burn_in_namespaces",
            "candidate_source_scope": "single_namespace" if artifact_namespace else "active_burn_in_namespaces",
            "explicit_scope_warning": explicit_scope_warning,
            "included_namespaces": included_namespaces,
            "excluded_namespaces": policy.get("excluded_namespaces") or [],
            "exclusion_reasons": policy.get("exclusion_reasons") or {},
            "excluded_reasons": policy.get("excluded_reasons") or policy.get("exclusion_reasons") or {},
            "included_namespace_count": len(included_namespaces),
            "excluded_namespace_count": len(policy.get("excluded_namespaces") or []),
            "namespace_status": policy.get("namespace_status") or {},
            "latest_doctor_status": policy.get("latest_doctor_status") or {},
            "latest_run_id": policy.get("latest_run_id") or {},
            "artifact_counts": policy.get("artifact_counts") or {},
            "live_cycles": len(daily_runs),
            "fixture_cycles": sum(1 for name, status in (policy.get("namespace_status") or {}).items() if name not in included_namespaces and ("fixture" in str(name).casefold() or "smoke" in str(name).casefold() or status == "active_fixture_smoke")),
            "stale_cycles": sum(1 for name, status in (policy.get("namespace_status") or {}).items() if name not in included_namespaces and status in {"stale_deprecated", "archived", "quarantine"}),
            "providers": provider_rows,
            "source_packs": source_pack_rows,
            "candidate_count": len(candidates),
            "real_burn_in_candidate_count": len(candidates) if contract_countable else 0,
            "non_burn_in_candidate_count": 0 if contract_countable else len(candidates),
            "core_opportunity_count": len(cores),
            "feedback_count": len(feedback),
            "outcome_count": len(outcomes),
            "recommendations_only": True,
            "auto_apply": False,
            "auto_apply_thresholds": False,
            "label_coverage": _label_coverage(feedback, rows),
            "enough_data": not enough_data_reasons,
            "enough_data_reasons": enough_data_reasons,
            "min_sample_warning": bool(enough_data_reasons),
            "source_yield_confidence": "low" if enough_data_reasons else "measured",
            "warnings": _warnings(provider_rows, source_pack_rows),
        }
    )
    common.write_json(context.namespace_dir / SOURCE_YIELD_JSON, payload)
    common.write_text(context.namespace_dir / SOURCE_YIELD_MD, format_source_yield_report(payload))
    return payload


def format_source_yield_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Event Alpha Source Yield Report",
        "",
        "Research-only source/provider usefulness report. Recommendations are advisory and never auto-apply thresholds.",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- profile: `{payload.get('profile')}`",
        f"- artifact_namespace: `{payload.get('artifact_namespace')}`",
        f"- evidence_scope: `{payload.get('evidence_scope')}`",
        f"- burn_in_contract_scope: `{payload.get('burn_in_contract_scope')}`",
        f"- explicit_scope_warning: `{payload.get('explicit_scope_warning') or 'none'}`",
        f"- included_namespaces: `{', '.join(payload.get('included_namespaces') or []) or 'none'}`",
        f"- real_burn_in_candidate_count: `{payload.get('real_burn_in_candidate_count')}`",
        f"- non_burn_in_candidate_count: `{payload.get('non_burn_in_candidate_count')}`",
        f"- recommendations_only: `{payload.get('recommendations_only')}`",
        f"- auto_apply: `{payload.get('auto_apply')}`",
        f"- enough_data: `{payload.get('enough_data')}`",
        f"- enough_data_reasons: `{', '.join(payload.get('enough_data_reasons') or []) or 'none'}`",
        "",
        "## Providers",
        "",
    ]
    for provider, row in sorted((payload.get("providers") or {}).items()):
        lines.append(
            f"- {provider}: candidates={row.get('candidate_count')} labels={row.get('label_count')} "
            f"useful={row.get('useful_label_count')} noise={row.get('noise_label_count')} "
            f"recommendation=`{row.get('recommended_action')}`"
        )
    lines.extend(["", "## Source Packs", ""])
    for pack, row in sorted((payload.get("source_packs") or {}).items()):
        lines.append(
            f"- {pack}: candidates={row.get('candidate_count')} labels={row.get('label_count')} "
            f"useful={row.get('useful_label_count')} noise={row.get('noise_label_count')} "
            f"recommendation=`{row.get('recommended_action')}`"
        )
    warnings = payload.get("warnings") or []
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines).rstrip()


def _rows(base: Path, filename: str, *, cutoff, namespaces: list[str] | tuple[str, ...]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for namespace in namespaces:
        path = base / namespace / filename
        for row in common.read_jsonl(path):
            if (common.timestamp_for_row(row) or common.utc_now()) >= cutoff:
                out.append(row)
    return out


def _evidence_scope(artifact_namespace: str | None, policy: Mapping[str, Any]) -> str:
    if not artifact_namespace:
        return "real_burn_in_evidence" if policy.get("included_namespaces") else "no_active_burn_in_namespaces"
    details = [
        row
        for section in ("included_namespace_details", "excluded_namespace_details")
        for row in (policy.get(section) or [])
        if isinstance(row, Mapping) and row.get("namespace") == artifact_namespace
    ]
    categories = {str(item) for row in details for item in (row.get("categories") or [])}
    if "fixture" in categories:
        return "fixture"
    if "no_key" in categories:
        return "no_key_diagnostic"
    if "stale" in categories:
        return "stale_historical_diagnostic"
    if "notification_rehearsal" in categories:
        return "explicit_single_namespace_diagnostic"
    return "explicit_single_namespace_diagnostic"


def _provider(row: Mapping[str, Any]) -> str:
    return str(row.get("provider") or row.get("source_provider") or row.get("source_origin") or "unknown")


def _source_pack(row: Mapping[str, Any]) -> str:
    return str(row.get("source_pack") or row.get("source_pack_id") or row.get("source_class") or "unknown")


def _summary_for(
    name: str,
    kind: str,
    *,
    rows: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    key_fn = _provider if kind == "provider" else _source_pack
    candidate_rows = [row for row in rows if key_fn(row) == name]
    label_rows = [row for row in feedback if key_fn(row) == name]
    useful = [row for row in label_rows if str(row.get("label") or "") in {"useful", "watch", "promising_source_type"}]
    noisy = [row for row in label_rows if str(row.get("label") or "") in {"junk", "source_noise", "false_positive", "duplicate"}]
    late = [row for row in label_rows if str(row.get("label") or "") == "late"]
    outcome_rows = [row for row in outcomes if key_fn(row) == name]
    return {
        "name": name,
        "kind": kind,
        "candidate_count": len(candidate_rows),
        "label_count": len(label_rows),
        "useful_label_count": len(useful),
        "noise_label_count": len(noisy),
        "late_label_count": len(late),
        "outcome_count": len(outcome_rows),
        "source_noise_rate_pct": round(100.0 * len(noisy) / len(label_rows), 2) if label_rows else 0.0,
        "usefulness_rate_pct": round(100.0 * len(useful) / len(label_rows), 2) if label_rows else 0.0,
        "recommended_action": _recommend_action(name, candidate_rows, label_rows, noisy, useful),
        "auto_apply": False,
    }


def _recommend_action(
    name: str,
    candidate_rows: list[dict[str, Any]],
    label_rows: list[dict[str, Any]],
    noisy: list[dict[str, Any]],
    useful: list[dict[str, Any]],
) -> str:
    lowered = name.casefold()
    if "coinalyze" in lowered and not label_rows:
        return "activate_next"
    if label_rows and len(label_rows) < 10:
        return "needs_more_labels"
    if any(token in lowered for token in ("gdelt", "rss")) and label_rows and len(noisy) >= max(2, len(useful) * 2):
        return "context_only_or_quarantine"
    if label_rows and len(useful) > len(noisy):
        return "keep_and_measure"
    if candidate_rows and not label_rows:
        return "needs_labels"
    return "hold_no_threshold_change"


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


def _warnings(provider_rows: Mapping[str, Mapping[str, Any]], source_pack_rows: Mapping[str, Mapping[str, Any]]) -> list[str]:
    warnings: list[str] = []
    if not provider_rows and not source_pack_rows:
        warnings.append("no source yield rows found")
    for name, row in provider_rows.items():
        if row.get("candidate_count") and not row.get("label_count"):
            warnings.append(f"provider needs labels: {name}")
    return warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write Event Alpha source-yield report.")
    parser.add_argument("--profile", default="live_burn_in_no_send")
    parser.add_argument("--artifact-namespace", default=None)
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--include-notification-rehearsals", action="store_true")
    parser.add_argument("--include-no-key-namespaces", action="store_true")
    parser.add_argument("--include-provider-rehearsals", action="store_true")
    parser.add_argument("--include-fixture-namespaces", action="store_true")
    parser.add_argument("--include-stale-namespaces", action="store_true")
    parser.add_argument("--include-namespace", action="append", default=[])
    args = parser.parse_args(argv)
    payload = build_source_yield_report(
        profile=args.profile,
        artifact_namespace=args.artifact_namespace,
        base_dir=args.base_dir,
        days=args.days,
        include_notification_rehearsals=args.include_notification_rehearsals,
        include_no_key_namespaces=args.include_no_key_namespaces,
        include_provider_rehearsals=args.include_provider_rehearsals,
        include_fixture_namespaces=args.include_fixture_namespaces,
        include_stale_namespaces=args.include_stale_namespaces,
        include_namespaces=tuple(args.include_namespace),
    )
    print(f"event_alpha_source_yield_report: {payload['namespace_dir']}/{SOURCE_YIELD_MD}")
    print(f"providers={len(payload['providers'])} source_packs={len(payload['source_packs'])} auto_apply={payload['auto_apply']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
