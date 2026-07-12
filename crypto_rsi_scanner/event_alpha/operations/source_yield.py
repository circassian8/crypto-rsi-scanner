"""Source-pack/provider yield report for Event Alpha burn-in artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from . import common
from . import evidence_semantics
from . import namespace_policy
from . import outcome_evidence
from .daily_burn_in import CANDIDATE_MODE_MANIFEST_JSON, RUN_JSON


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
    include_live_rehearsals_without_burn_in_run: bool = False,
    include_namespaces: tuple[str, ...] = (),
) -> dict[str, Any]:
    context = common.context_for(profile=profile, artifact_namespace=artifact_namespace or profile, base_dir=base_dir)
    base = context.base_dir
    evaluation_now = common.utc_now()
    cutoff = common.date_window(days, now=evaluation_now)
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
    (candidates, cores, supplied_outcomes, outcomes, excluded_outcomes,
     outcome_exclusion_reason_counts) = outcome_evidence.load_exact_namespace_outcomes(
        base, cutoff, included_namespaces, _rows, evaluation_now)
    feedback = _rows(base, "event_alpha_feedback.jsonl", cutoff=cutoff, namespaces=included_namespaces)
    daily_runs = [common.read_json(base / namespace / RUN_JSON) for namespace in included_namespaces]
    daily_runs = [row for row in daily_runs if row]
    candidate_mode_manifests = [
        common.read_json(base / namespace / CANDIDATE_MODE_MANIFEST_JSON)
        for namespace in included_namespaces
    ]
    candidate_mode_manifests = [row for row in candidate_mode_manifests if row]
    evidence_summaries = evidence_semantics.namespace_summaries(base, included_namespaces, cutoff=cutoff, policy=policy)
    evidence_aggregate = evidence_semantics.aggregate_namespace_summaries(evidence_summaries)
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
    enough_data_reasons = _enough_data_reasons(included_namespaces=included_namespaces if contract_countable else [], feedback=feedback, outcomes=outcomes, daily_runs=daily_runs)
    if explicit_scope_warning:
        enough_data_reasons = ["explicit_namespace_not_counted_for_burn_in_contract", *enough_data_reasons]
    real_candidate_rows = list(evidence_aggregate["real_candidate_rows"]) if contract_countable else []
    rows = real_candidate_rows
    providers = sorted({_provider(row) for row in [*rows, *feedback]})
    source_packs = sorted({_source_pack(row) for row in [*rows, *feedback]})
    provider_rows = {
        provider: _summary_for(provider, "provider", rows=rows, feedback=feedback, outcomes=outcomes)
        for provider in providers
    }
    _merge_activation_rows(provider_rows, candidate_mode_manifests)
    source_pack_rows = {
        pack: _summary_for(pack, "source_pack", rows=rows, feedback=feedback, outcomes=outcomes)
        for pack in source_packs
    }
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_source_yield_report_v1",
            "row_type": "event_alpha_source_yield_report",
            "generated_at": evaluation_now.isoformat(),
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
            "burn_in_contract_scope": "explicit_single_namespace_diagnostic" if explicit_scope else "active_burn_in_namespaces",
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
            "real_candidate_rows": len(real_candidate_rows),
            "accepted_evidence_rows": sum(1 for row in rows if row.get("accepted_evidence") or common.int_value(row.get("accepted_evidence_count")) > 0),
            "provider_readiness_rows": evidence_aggregate.get("readiness_rows", 0),
            "source_coverage_rows": evidence_aggregate.get("source_coverage_rows", 0),
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
            "core_opportunity_count": len(cores),
            "feedback_count": len(feedback),
            "outcome_count": len(outcomes),
            **outcome_evidence.telemetry(supplied_outcomes, outcomes, excluded_outcomes, outcome_exclusion_reason_counts),
            "recommendations_only": True,
            "auto_apply": False,
            "auto_apply_thresholds": False,
            "label_coverage": _label_coverage(feedback, rows),
            "enough_data": not enough_data_reasons,
            "enough_data_reasons": enough_data_reasons,
            "min_sample_warning": bool(enough_data_reasons),
            "source_yield_confidence": "insufficient_labels" if not feedback or not outcomes else ("low" if enough_data_reasons else "measured"),
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
        f"- contract_counted_candidate_count: `{payload.get('contract_counted_candidate_count')}`",
        f"- candidate_evidence_explanation: `{payload.get('candidate_evidence_explanation')}`",
        f"- real_candidate_rows: `{payload.get('real_candidate_rows')}`",
        f"- provider_readiness_rows: `{payload.get('provider_readiness_rows')}`",
        f"- source_coverage_rows: `{payload.get('source_coverage_rows')}`",
        f"- non_burn_in_candidate_count: `{payload.get('non_burn_in_candidate_count')}`",
        f"- outcome_rows_supplied: `{payload.get('outcome_rows_supplied')}`",
        f"- outcome_rows_eligible: `{payload.get('outcome_rows_eligible')}`",
        f"- outcome_rows_excluded: `{payload.get('outcome_rows_excluded')}`",
        common.table_line(
            "outcome_exclusion_reason_counts",
            payload.get("outcome_exclusion_reason_counts") or {},
        ),
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
            f"candidates_produced={row.get('candidates_produced')} "
            f"evidence_accepted={row.get('evidence_accepted')} "
            f"useful={row.get('useful_label_count')} noise={row.get('noise_label_count')} "
            f"outcomes={row.get('outcome_count')} "
            f"activation=`{row.get('activation_status') or 'not_observed'}` "
            f"configured=`{row.get('configured')}` allow=`{row.get('allow_flag_set')}` "
            f"ledger_rows=`{row.get('request_ledger_rows')}` "
            f"confidence=`{row.get('source_yield_confidence')}` "
            f"recommendation=`{row.get('recommended_action')}`"
        )
    lines.extend(["", "## Source Packs", ""])
    for pack, row in sorted((payload.get("source_packs") or {}).items()):
        lines.append(
            f"- {pack}: candidates={row.get('candidate_count')} labels={row.get('label_count')} "
            f"useful={row.get('useful_label_count')} noise={row.get('noise_label_count')} "
            f"outcomes={row.get('outcome_count')} "
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
    accepted_rows = [
        row
        for row in candidate_rows
        if row.get("accepted_evidence") or common.int_value(row.get("accepted_evidence_count")) > 0
    ]
    label_rows = [row for row in feedback if key_fn(row) == name]
    useful = [row for row in label_rows if str(row.get("label") or "") in {"useful", "watch", "promising_source_type"}]
    noisy = [row for row in label_rows if str(row.get("label") or "") in {"junk", "source_noise", "false_positive", "duplicate"}]
    late = [row for row in label_rows if str(row.get("label") or "") == "late"]
    outcome_rows = [row for row in outcomes if key_fn(row) == name]
    return {
        "name": name,
        "kind": kind,
        "candidate_count": len(candidate_rows),
        "candidates_produced": len(candidate_rows),
        "evidence_accepted": len(accepted_rows),
        "label_count": len(label_rows),
        "useful_label_count": len(useful),
        "noise_label_count": len(noisy),
        "late_label_count": len(late),
        "outcome_count": len(outcome_rows),
        "source_noise_rate_pct": round(100.0 * len(noisy) / len(label_rows), 2) if label_rows else 0.0,
        "usefulness_rate_pct": round(100.0 * len(useful) / len(label_rows), 2) if label_rows else 0.0,
        "recommended_action": _recommend_action(name, candidate_rows, label_rows, noisy, useful),
        "activation_status": "candidate_rows_observed" if candidate_rows else "not_observed",
        "configured": None,
        "allow_flag_set": None,
        "live_call_allowed": None,
        "live_calls_attempted": bool(candidate_rows),
        "request_ledger_rows": sum(common.int_value(row.get("request_ledger_rows")) for row in candidate_rows),
        "candidate_production_status": "produced_candidates" if candidate_rows else "no_candidates",
        "source_yield_confidence": "insufficient_labels" if not label_rows else "labeled",
        "auto_apply": False,
    }


def _merge_activation_rows(provider_rows: dict[str, dict[str, Any]], manifests: list[Mapping[str, Any]]) -> None:
    for manifest in manifests:
        providers = manifest.get("providers") if isinstance(manifest.get("providers"), Mapping) else {}
        ledger_rows_by_provider = manifest.get("request_ledger_rows") if isinstance(manifest.get("request_ledger_rows"), Mapping) else {}
        for provider, status in providers.items():
            if not isinstance(status, Mapping):
                continue
            row = provider_rows.setdefault(
                str(provider),
                {
                    "name": str(provider),
                    "kind": "provider",
                    "candidate_count": 0,
                    "candidates_produced": 0,
                    "evidence_accepted": 0,
                    "label_count": 0,
                    "useful_label_count": 0,
                    "noise_label_count": 0,
                    "late_label_count": 0,
                    "outcome_count": 0,
                    "source_noise_rate_pct": 0.0,
                    "usefulness_rate_pct": 0.0,
                    "auto_apply": False,
                },
            )
            request_ledger_rows = common.int_value(ledger_rows_by_provider.get(provider))
            activation_status = str(status.get("status") or "unknown")
            row.update(
                {
                    "activation_status": activation_status,
                    "configured": bool(status.get("configured")),
                    "allow_flag_set": bool(status.get("allow_flag_set")),
                    "live_call_allowed": bool(status.get("live_call_allowed")),
                    "live_calls_attempted": request_ledger_rows > 0,
                    "request_budget": status.get("request_budget"),
                    "request_ledger_path": status.get("request_ledger_path"),
                    "request_ledger_rows": request_ledger_rows,
                    "candidates_produced": common.int_value(row.get("candidate_count")),
                    "candidate_production_status": _candidate_production_status(row, activation_status),
                    "source_yield_confidence": _activation_confidence(row, activation_status),
                    "recommended_action": _activation_recommendation(activation_status),
                }
            )


def _candidate_production_status(row: Mapping[str, Any], activation_status: str) -> str:
    if common.int_value(row.get("candidate_count")) > 0:
        return "produced_candidates"
    if activation_status == "skipped_missing_config":
        return "missing_config"
    if activation_status in {"skipped_live_calls_disabled", "live_call_blocked_by_default"}:
        return "config_ready_no_live"
    if activation_status == "request_budget_not_small":
        return "request_budget_not_small"
    return "active_burn_in_candidate_mode_no_candidates"


def _activation_confidence(row: Mapping[str, Any], activation_status: str) -> str:
    if common.int_value(row.get("candidate_count")) > 0:
        return "insufficient_labels" if common.int_value(row.get("label_count")) == 0 else "candidate_rows_observed"
    if activation_status in {"skipped_missing_config", "skipped_live_calls_disabled", "live_call_blocked_by_default"}:
        return "activation_pending"
    return "no_candidates_yet"


def _activation_recommendation(activation_status: str) -> str:
    if activation_status == "skipped_missing_config":
        return "activate_next/missing_config"
    if activation_status in {"skipped_live_calls_disabled", "live_call_blocked_by_default"}:
        return "config_ready_no_live"
    if activation_status == "request_budget_not_small":
        return "set_small_request_budget"
    if activation_status == "ready_live_no_send":
        return "measure_candidate_yield"
    return "hold_no_threshold_change"


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
    parser.add_argument("--include-live-rehearsals-without-burn-in-run", action="store_true")
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
        include_live_rehearsals_without_burn_in_run=args.include_live_rehearsals_without_burn_in_run,
        include_namespaces=tuple(args.include_namespace),
    )
    print(f"event_alpha_source_yield_report: {payload['namespace_dir']}/{SOURCE_YIELD_MD}")
    print(f"providers={len(payload['providers'])} source_packs={len(payload['source_packs'])} auto_apply={payload['auto_apply']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
