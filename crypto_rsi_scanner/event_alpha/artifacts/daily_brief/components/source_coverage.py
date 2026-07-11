"""Source Coverage helpers for daily brief."""

from __future__ import annotations

from .runtime import *

def _source_coverage_summary_lines(
    rows: Iterable[Mapping[str, Any] | object],
    near_misses: Iterable[event_near_miss.EventNearMissCandidate],
    upgrade_candidates: Iterable[event_near_miss.EventNearMissCandidate],
    *,
    acquisition_rows: Iterable[Mapping[str, Any]] = (),
    source_coverage_report_path: str | Path | None = None,
) -> list[str]:
    coverage = _load_source_coverage_json(source_coverage_report_path)
    if coverage:
        return _source_coverage_json_summary_lines(coverage, source_coverage_report_path=source_coverage_report_path)
    row_maps = [_row_mapping(row) for row in rows]
    row_maps = [row for row in row_maps if row]
    summary = event_source_registry.format_source_coverage_summary(row_maps)
    near = list(near_misses)
    upgrades = list(upgrade_candidates)
    gaps = [item for item in (*near, *upgrades) if item.source_coverage_gap]
    planned = [item for item in (*near, *upgrades) if item.evidence_acquisition_plan]
    planned_attempted = [item for item in (*near, *upgrades) if item.evidence_acquisition_attempted]
    executed_rows = [dict(row) for row in acquisition_rows if isinstance(row, Mapping)]
    provider_queries = sum(
        int(row.get("queries_executed") or row.get("evidence_acquisition_queries_executed") or 0)
        for row in executed_rows
    )
    accepted = sum(
        1 for row in executed_rows
        if str(row.get("status") or "") == event_evidence_acquisition.EvidenceAcquisitionStatus.ACCEPTED_EVIDENCE_FOUND.value
        or bool(row.get("accepted_evidence"))
    )
    no_results = sum(
        1 for row in executed_rows
        if str(row.get("status") or "") == event_evidence_acquisition.EvidenceAcquisitionStatus.NO_RESULTS.value
    )
    rejected_only = sum(
        1 for row in executed_rows
        if str(row.get("status") or "") == event_evidence_acquisition.EvidenceAcquisitionStatus.REJECTED_RESULTS_ONLY.value
    )
    accepted_by_source_class: dict[str, int] = {}
    article_quality_counts: dict[str, int] = {}
    for row in executed_rows:
        evidence_items = (*_evidence_items(row.get("accepted_evidence")), *_evidence_items(row.get("rejected_evidence_samples") or row.get("rejected_evidence")))
        accepted_items = _evidence_items(row.get("accepted_evidence"))
        for evidence in accepted_items:
            source_class = str(evidence.get("source_class") or "unknown")
            accepted_by_source_class[source_class] = accepted_by_source_class.get(source_class, 0) + 1
        for evidence in evidence_items:
            enrichment = evidence.get("source_enrichment") if isinstance(evidence.get("source_enrichment"), Mapping) else {}
            status = str(enrichment.get("article_quality_status") or "").strip()
            if status:
                article_quality_counts[status] = article_quality_counts.get(status, 0) + 1
    accepted_source_text = ", ".join(
        f"{source_class}={count}"
        for source_class, count in sorted(accepted_by_source_class.items(), key=lambda item: (-item[1], item[0]))
    ) or "none"
    article_quality_text = ", ".join(
        f"{status}={count}"
        for status, count in sorted(article_quality_counts.items(), key=lambda item: (-item[1], item[0]))
    ) or "none"
    next_source = _source_coverage_next_source(gaps, executed_rows)
    report_path = Path(source_coverage_report_path) if source_coverage_report_path else None
    report_status = "not written yet"
    if report_path is not None:
        report_label = event_artifact_paths.artifact_display_path(report_path)
        report_status = report_label if report_path.exists() else f"{report_label} (not written yet)"
    return [
        f"- Detailed source coverage report: {report_status}",
        f"- Source registry: {summary}",
        (
            "- Evidence acquisition funnel: "
            f"evidence_plans_created={len(planned) or len(planned_attempted)}, "
            f"llm_evidence_plans_created={len(planned)}, "
            f"acquisition_requests_executed={len(executed_rows)}, "
            f"deterministic_acquisition_requests_executed={len(executed_rows)}, "
            f"provider_queries_executed={provider_queries}, "
            f"accepted_evidence_found={accepted}, "
            f"no_results={no_results}, "
            f"rejected_only={rejected_only}"
        ),
        f"- Accepted evidence by source class: {accepted_source_text}",
        f"- Source enrichment article quality: {article_quality_text}",
        f"- Source coverage gaps: {len(gaps)} candidate(s) need healthier or more specific source coverage.",
        f"- Largest current source-pack coverage gap: {next_source}",
        *_source_activation_plan_lines(source_coverage_report_path),
        "- Evidence absence rule: broad/degraded RSS/GDELT/Polymarket gaps are not treated as strong negative proof.",
    ]

def _source_coverage_json_summary_lines(
    coverage: Mapping[str, Any],
    *,
    source_coverage_report_path: str | Path | None,
) -> list[str]:
    report_path = Path(source_coverage_report_path) if source_coverage_report_path else None
    json_path = _source_coverage_json_path(source_coverage_report_path)
    report_status = "not written yet"
    if report_path is not None:
        report_label = event_artifact_paths.artifact_display_path(report_path)
        report_status = report_label if report_path.exists() else f"{report_label} (not written yet)"
    lines = [
        f"- Detailed source coverage report: {report_status}",
        (
            "- CryptoPanic effective coverage: "
            f"configured={str(bool(coverage.get('cryptopanic_configured'))).lower()} "
            f"selected_for_run={str(bool(coverage.get('cryptopanic_selected_for_run'))).lower()} "
            f"live_call_allowed={str(bool(coverage.get('cryptopanic_live_call_allowed'))).lower()} "
            f"status={coverage.get('cryptopanic_health_status') or 'unknown'} "
            f"coverage={coverage.get('cryptopanic_coverage_status') or 'unknown'} "
            f"observed={str(bool(coverage.get('cryptopanic_observed'))).lower()} "
            f"successful_requests={int(coverage.get('cryptopanic_successful_requests') or 0)} "
            f"failed_requests={int(coverage.get('cryptopanic_failed_requests') or 0)} "
            f"accepted={int(coverage.get('cryptopanic_accepted_evidence') or 0)} "
            f"rejected={int(coverage.get('cryptopanic_rejected_evidence') or 0)} "
            f"stale_backoff_reconciled={str(bool(coverage.get('cryptopanic_backoff_reconciled_after_success'))).lower()}"
        ),
    ]
    recommendation = str(coverage.get("cryptopanic_recommendation") or "none")
    if recommendation and recommendation != "none":
        lines.append(f"- CryptoPanic recommendation: {recommendation}")
    packs = [pack for pack in coverage.get("packs") or [] if isinstance(pack, Mapping)]
    blocked = int(coverage.get("candidates_blocked_by_source_coverage") or 0)
    if "candidates_blocked_by_source_coverage" not in coverage:
        blocked = sum(int(pack.get("candidates_blocked_by_coverage_gap") or 0) for pack in packs)
    accepted = sum(int(pack.get("accepted_evidence_count") or 0) for pack in packs)
    rejected_only = sum(int(pack.get("rejected_only_count") or 0) for pack in packs)
    skipped_budget = sum(int(pack.get("skipped_budget_count") or 0) for pack in packs)
    provider_unavailable = sum(int(pack.get("provider_unavailable_count") or 0) for pack in packs)
    lines.append(
        "- Evidence acquisition funnel: "
        f"acquisition_requests_executed={int(coverage.get('acquisition_rows') or 0)}, "
        f"accepted_evidence_found={accepted}, "
        f"rejected_only={rejected_only}, "
        f"skipped_budget={skipped_budget}, "
        f"provider_unavailable={provider_unavailable}"
    )
    lines.append(f"- Source coverage gaps: {blocked} candidate(s) need healthier or more specific source coverage.")
    lines.append(
        "- Coverage blocker accounting: "
        f"missing_strong_source={int(coverage.get('candidates_blocked_by_missing_strong_source') or 0)}, "
        f"missing_official_source={int(coverage.get('candidates_blocked_by_missing_official_source') or 0)}, "
        f"missing_structured_source={int(coverage.get('candidates_blocked_by_missing_structured_source') or 0)}, "
        f"evidence_not_acquired={int(coverage.get('candidates_blocked_by_evidence_not_acquired') or 0)}, "
        f"provider_unavailable={int(coverage.get('candidates_blocked_by_provider_unavailable') or 0)}, "
        f"market_context={int(coverage.get('candidates_blocked_by_market_context') or 0)}"
    )
    lines.append(
        "- Coverage-blocked visible families: "
        f"source={int(coverage.get('candidate_families_blocked_by_source_coverage') or 0)}, "
        f"market={int(coverage.get('candidate_families_blocked_by_market_coverage') or 0)}"
    )
    next_source = _source_coverage_json_next_source(packs, coverage)
    lines.append(f"- Largest current source-pack coverage gap: {next_source}")
    lines.append(
        "- Source coverage JSON: "
        + (event_artifact_paths.artifact_display_path(json_path) if json_path and json_path.exists() else "not written yet")
    )
    lines.extend(_source_activation_plan_lines(source_coverage_report_path, coverage=coverage))
    lines.append("- Evidence absence rule: broad/degraded RSS/GDELT/Polymarket gaps are not treated as strong negative proof.")
    return lines

def _source_activation_plan_lines(
    source_coverage_report_path: str | Path | None,
    *,
    coverage: Mapping[str, Any] | None = None,
) -> list[str]:
    base = Path(source_coverage_report_path).parent if source_coverage_report_path is not None else None
    readiness_md = base / event_alpha_source_coverage.LIVE_PROVIDER_READINESS_MD if base is not None else None
    readiness_label = (
        event_artifact_paths.artifact_display_path(readiness_md)
        if readiness_md is not None
        else event_alpha_source_coverage.LIVE_PROVIDER_READINESS_MD
    )
    priorities = []
    if coverage is not None:
        priorities = [item for item in coverage.get("category_priorities") or [] if isinstance(item, Mapping)]
    if not priorities:
        priorities = list(event_alpha_source_coverage.SOURCE_COVERAGE_CATEGORY_PRIORITIES)
    top = []
    for item in priorities[:3]:
        category = str(item.get("category") or "").strip()
        providers = item.get("providers") or ()
        if category:
            top.append(f"{category} ({', '.join(str(provider) for provider in providers if str(provider)) or 'providers TBD'})")
    lines = [
        f"- Live-provider activation readiness: {readiness_label}",
        "- Strategic activation order (not readiness): " + ("; ".join(top) if top else "none"),
    ]
    if base is not None:
        coinalyze_json = base / event_coinalyze_preflight.PREFLIGHT_JSON
        coinalyze_md = base / event_coinalyze_preflight.PREFLIGHT_MD
        coverage_preflight_status = str((coverage or {}).get("coinalyze_preflight_status") or "")
        coverage_rehearsal_status = str((coverage or {}).get("coinalyze_rehearsal_status") or "")
        coverage_rehearsal_path = str((coverage or {}).get("coinalyze_rehearsal_report_path") or "")
        coverage_ledger_path = str((coverage or {}).get("coinalyze_request_ledger_path") or "")
        if coinalyze_json.exists() and coinalyze_md.exists():
            try:
                payload = json.loads(coinalyze_json.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
            status = coverage_preflight_status or str(payload.get("preflight_status") or "unreadable")
            lines.append(
                "- Coinalyze preflight: "
                f"{status} ({event_artifact_paths.artifact_display_path(coinalyze_md)})"
            )
        else:
            namespace = str((coverage or {}).get("artifact_namespace") or Path(base).name)
            profile = str((coverage or {}).get("profile") or "notify_llm_deep")
            lines.append(
                "- Coinalyze preflight: not generated "
                f"(command: make event-alpha-coinalyze-preflight ARTIFACT_NAMESPACE={namespace} PROFILE={profile} PYTHON=python3)"
            )
        if coverage_rehearsal_status and coverage_rehearsal_status != "not_generated":
            detail = f" ({coverage_rehearsal_path})" if coverage_rehearsal_path else ""
            ledger = f" ledger={coverage_ledger_path}" if coverage_ledger_path else ""
            lines.append(f"- Coinalyze rehearsal: {coverage_rehearsal_status}{detail}{ledger}")
        else:
            lines.append("- Coinalyze rehearsal: not generated")
    if readiness_md is None or not readiness_md.exists():
        lines.append("- Readiness command: make event-alpha-live-provider-readiness PROFILE=notify_llm_deep")
    return lines

def _source_coverage_json_next_source(packs: Iterable[Mapping[str, Any]], coverage: Mapping[str, Any]) -> str:
    candidates: list[tuple[int, str, str]] = []
    for pack in packs:
        actions = pack.get("recommended_actions")
        action_text = "; ".join(str(item) for item in actions[:2]) if isinstance(actions, list) else ""
        if not action_text:
            continue
        # If CryptoPanic is already observed healthy, avoid recommending it as
        # the "missing" next source. The pack action may still mention another
        # corroborating source, which remains useful.
        if (
            bool(coverage.get("cryptopanic_successful_requests"))
            and "cryptopanic" in action_text.casefold()
            and not any(
                token in action_text.casefold()
                for token in ("official", "sports", "coinalyze", "tokenomist", "binance", "bybit", "defillama")
            )
        ):
            continue
        priority = int(pack.get("candidates_blocked_by_coverage_gap") or 0)
        if priority <= 0:
            priority = int(pack.get("skipped_budget_count") or 0) + int(pack.get("provider_unavailable_count") or 0)
        candidates.append((priority, str(pack.get("source_pack") or "unknown"), action_text))
    if not candidates:
        return "none; current source-pack evidence is not the main blocker"
    _, pack_name, action = sorted(candidates, key=lambda item: (-item[0], item[1]))[0]
    return f"{pack_name}: {action}"

def _load_source_coverage_json(source_coverage_report_path: str | Path | None) -> Mapping[str, Any]:
    path = _source_coverage_json_path(source_coverage_report_path)
    if path is None or not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, Mapping) else {}

def _source_coverage_json_path(source_coverage_report_path: str | Path | None) -> Path | None:
    if source_coverage_report_path is None:
        return None
    path = Path(source_coverage_report_path)
    if path.suffix == ".json":
        return path
    return path.with_suffix(".json")

def _source_coverage_next_source(
    gaps: Iterable[event_near_miss.EventNearMissCandidate],
    acquisition_rows: Iterable[Mapping[str, Any]],
) -> str:
    pack_counts: dict[str, int] = {}
    for item in gaps:
        pack = str(item.source_pack or "market_anomaly_pack")
        pack_counts[pack] = pack_counts.get(pack, 0) + 1
    for row in acquisition_rows:
        status = str(row.get("status") or "")
        if status not in {"skipped_budget", "no_results", "rejected_results_only", "provider_unavailable", "provider_backoff", "failed_soft"}:
            continue
        pack = str(row.get("source_pack") or "market_anomaly_pack")
        pack_counts[pack] = pack_counts.get(pack, 0) + 1
    if not pack_counts:
        return "none; current source-pack evidence is not the main blocker"
    pack = sorted(pack_counts, key=lambda key: (-pack_counts[key], key))[0]
    suggestions = {
        "proxy_preipo_rwa_pack": "CryptoPanic tagged token news or official project source",
        "strategic_investment_pack": "CryptoPanic/official project confirmation plus DefiLlama protocol metrics",
        "security_shock_pack": "CryptoPanic tagged exploit coverage or official project update",
        "listing_liquidity_pack": "official Binance/Bybit exchange announcement",
        "fan_sports_pack": "sports fixture plus fan-token/project source",
        "market_anomaly_pack": "CryptoPanic tagged catalyst, official exchange/project source, or DefiLlama metrics",
        "unlock_supply_pack": "Tokenomist/structured unlock source",
        "perp_listing_squeeze_pack": "official perp listing plus Coinalyze OI/funding",
    }
    return suggestions.get(pack, f"{pack} source-pack evidence")

def _evidence_items(value: object) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()

def _provider_health_by_pack_lines(
    provider_health_rows: Mapping[str, Mapping[str, Any]],
    *,
    source_coverage_report_path: str | Path | None = None,
) -> list[str]:
    coverage = _load_source_coverage_json(source_coverage_report_path)
    if coverage:
        packs = [pack for pack in coverage.get("packs") or [] if isinstance(pack, Mapping)]
        if not packs:
            return ["- Source coverage JSON had no pack rows."]
        lines: list[str] = []
        for pack in packs:
            lines.append(
                f"- {pack.get('source_pack') or 'unknown'}: "
                f"coverage={pack.get('provider_coverage_status') or pack.get('source_pack_coverage_status') or 'unknown'} "
                f"healthy={_join_json_values(pack.get('healthy_providers'))} "
                f"unknown={_join_json_values(pack.get('unknown_or_unobserved_providers'))} "
                f"degraded={_join_json_values(pack.get('degraded_or_backoff_providers'))} "
                f"missing={_join_json_values(pack.get('missing_providers'))} "
                f"blocked={int(pack.get('candidates_blocked_by_coverage_gap') or 0)}"
            )
        return lines
    if not provider_health_rows:
        return ["- No provider health rows found."]
    lines: list[str] = []
    for pack_name in event_source_packs.source_pack_names():
        pack = event_source_packs.get_source_pack(pack_name)
        statuses: list[str] = []
        for provider in pack.preferred_providers[:5]:
            row = provider_health_rows.get(provider) or provider_health_rows.get(provider.replace("_announcements", ""))
            status = "unknown"
            if isinstance(row, Mapping):
                status = str(row.get("coverage_status") or row.get("status") or row.get("ready") or "unknown")
            statuses.append(f"{provider}={status}")
        lines.append(f"- {pack.name}: " + ", ".join(statuses))
    return lines

def _join_json_values(value: object) -> str:
    if isinstance(value, str):
        return value or "none"
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        items = [str(item) for item in value if str(item)]
        return ", ".join(items) if items else "none"
    return "none"

def _evidence_acquisition_result_lines(
    candidates: Iterable[event_near_miss.EventNearMissCandidate],
    *,
    acquisition_rows: Iterable[Mapping[str, Any]] = (),
    core_opportunities: Iterable[event_core_opportunities.CoreOpportunity] = (),
    limit: int,
) -> list[str]:
    executed = [dict(row) for row in acquisition_rows if isinstance(row, Mapping)]
    core_by_id = {
        item.core_opportunity_id: item
        for item in core_opportunities
        if item.core_opportunity_id
    }
    if executed:
        lines: list[str] = []
        status_counts: dict[str, int] = {}
        for row in executed:
            status = str(row.get("status") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        lines.append(
            "- Executed source-pack searches: "
            + ", ".join(f"{key}={value}" for key, value in sorted(status_counts.items()))
        )
        for row in executed[:limit]:
            accepted = row.get("accepted_evidence") if isinstance(row.get("accepted_evidence"), list) else ()
            rejected = row.get("rejected_evidence_samples") if isinstance(row.get("rejected_evidence_samples"), list) else ()
            core = core_by_id.get(str(row.get("core_opportunity_id") or ""))
            core_row = core.primary_row if core is not None else {}
            canonical_level = (
                core_row.get("final_opportunity_level")
                or (core.opportunity_level if core is not None else None)
                or row.get("final_opportunity_level")
                or row.get("opportunity_level_after")
                or "unknown"
            )
            canonical_source = core_row.get("final_verdict_source") or row.get("final_verdict_source") or "canonical_core"
            lines.append(
                f"- {row.get('symbol') or row.get('coin_id') or row.get('hypothesis_id') or 'UNKNOWN'}: "
                f"pack={row.get('source_pack') or 'unknown'} status={row.get('status') or 'unknown'} "
                f"accepted={len(accepted or ())} rejected={len(rejected or ())} "
                f"score={row.get('opportunity_score_before')}->{row.get('opportunity_score_after')} "
                f"evidence={row.get('acquisition_evidence_status') or 'unknown'} "
                f"final={row.get('final_upgrade_status') or row.get('acquisition_upgrade_status') or 'unchanged'} "
                f"verdict={canonical_level} "
                f"source={canonical_source}"
            )
        if len(executed) > limit:
            lines.append(f"- +{len(executed) - limit} more acquisition rows in local artifacts")
        return lines
    rows = [item for item in candidates if item.evidence_acquisition_attempted or item.evidence_acquisition_results]
    if not rows:
        return ["- None."]
    lines: list[str] = []
    for item in rows[:limit]:
        plan = item.evidence_acquisition_plan or {}
        queries = plan.get("evidence_query_plan") if isinstance(plan, Mapping) else ()
        needed = plan.get("evidence_needed") if isinstance(plan, Mapping) else ()
        lines.append(
            f"- {item.symbol}/{item.coin_id}: pack={item.source_pack or 'unknown'} "
            f"queries={len(queries) if isinstance(queries, Iterable) and not isinstance(queries, (str, bytes, Mapping)) else 0} "
            f"needed={'; '.join(str(value) for value in list(needed or ())[:3]) or 'none'} "
            f"result={item.upgrade_reason or item.no_upgrade_reason or item.refresh_upgrade_status or 'planned'}"
        )
    if len(rows) > limit:
        lines.append(f"- +{len(rows) - limit} more evidence acquisition candidates")
    return lines

def _coverage_blocked_candidate_lines(
    candidates: Iterable[event_near_miss.EventNearMissCandidate],
    *,
    limit: int,
) -> list[str]:
    rows = [
        item
        for item in candidates
        if item.source_coverage_gap
        or item.provider_coverage_status in {"degraded", "unavailable", "not_configured", "partial"}
        or bool(
            set(item.recommended_refresh_actions)
            & {"source_pack_search", "targeted_evidence_refresh", "official_source_search"}
        )
    ]
    if not rows:
        return ["- None."]
    lines: list[str] = []
    for item in rows[:limit]:
        lines.append(
            f"- {item.symbol}/{item.coin_id}: pack={item.source_pack or 'unknown'} "
            f"coverage={item.provider_coverage_status or 'unknown'} gap={item.source_coverage_gap or 'source_specificity_gap'} "
            f"absence_meaningful={str(bool(item.evidence_absence_is_meaningful)).lower()}"
        )
    if len(rows) > limit:
        lines.append(f"- +{len(rows) - limit} more coverage-blocked candidates")
    return lines

def _friendly_reason(reason: object) -> str:
    return event_alpha_reason_text.humanize_event_alpha_reason(reason)

def _friendly_reason_list(reasons: Iterable[object]) -> str:
    translated = [_friendly_reason(reason) for reason in reasons]
    translated = [reason for reason in translated if reason]
    return "; ".join(dict.fromkeys(translated[:5]))

def _friendly_action(action: object) -> str:
    return event_alpha_reason_text.humanize_event_alpha_action(action)

def _friendly_action_list(actions: Iterable[object]) -> str:
    translated = [_friendly_action(action) for action in actions]
    translated = [action for action in translated if action]
    return "; ".join(dict.fromkeys(translated[:5]))

def _friendly_level(level: object) -> str:
    return str(level or "unknown").replace("_", " ")

__all__ = (
    '_source_coverage_summary_lines',
    '_source_coverage_json_summary_lines',
    '_source_activation_plan_lines',
    '_source_coverage_json_next_source',
    '_load_source_coverage_json',
    '_source_coverage_json_path',
    '_source_coverage_next_source',
    '_evidence_items',
    '_provider_health_by_pack_lines',
    '_join_json_values',
    '_evidence_acquisition_result_lines',
    '_coverage_blocked_candidate_lines',
    '_friendly_reason',
    '_friendly_reason_list',
    '_friendly_action',
    '_friendly_action_list',
    '_friendly_level',
)
