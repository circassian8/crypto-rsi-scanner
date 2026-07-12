"""Builder helpers for daily brief."""

from __future__ import annotations

from .runtime import *
from .decision_model import decision_model_daily_brief_lines
from .run_health import _latest_notification_health_lines, _latest_run_health_lines


@dataclass(frozen=True)
class _DailyBriefRows:
    legacy_available: bool
    runs: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    feedback: list[dict[str, Any]]
    missed: list[dict[str, Any]]
    stored_core_rows: list[dict[str, Any]]
    hypotheses: list[dict[str, Any]]
    incidents: list[dict[str, Any]]
    acquisition_rows: list[dict[str, Any]]
    market_anomalies: list[dict[str, Any]]
    official_exchange_candidates: list[dict[str, Any]]
    scheduled_catalysts: list[dict[str, Any]]
    unlock_candidates: list[dict[str, Any]]
    derivatives_state: list[dict[str, Any]]
    fade_review_candidates: list[dict[str, Any]]


@dataclass(frozen=True)
class _DailyBriefContext:
    entries: list[event_watchlist.EventWatchlistEntry]
    decisions: list[Any]
    alertable: list[Any]
    all_core_opportunities: list[Any]
    core_opportunities: list[Any]
    core_source_rows: list[Any]
    core_sections: dict[str, list[Any]]
    lane_sections: dict[str, list[Any]]
    source_coverage_report_path: Path | None
    core_alertable_count: int
    diagnostic_core_rows: int
    diagnostic_control_rows: int
    diagnostic_capped_rows: int
    promoted_core_asset_keys: set[Any]
    promoted_core_assets: set[Any]
    near_miss_candidates: tuple[Any, ...]
    upgrade_candidates: tuple[Any, ...]
    local_core_rows: list[Any]
    latest: Mapping[str, Any]
    latest_notification: Mapping[str, Any] | None
    selected_profile: str
    selected_namespace: str
    requested: str
    profile_match: str
    mismatch_warning: str | None


def _daily_brief_artifact_dir(run_ledger_path: str | Path | None) -> Path | None:
    return Path(run_ledger_path).parent if run_ledger_path else None


def _materialize_mapping_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _filter_daily_brief_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    requested_profile: str | None,
    artifact_namespace: str | None,
    include_test_artifacts: bool,
    include_api_artifacts: bool,
) -> list[dict[str, Any]]:
    return event_alpha_artifacts.filter_artifact_rows(
        rows,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
    )


def _optional_daily_brief_rows(
    rows: Iterable[Mapping[str, Any]] | None,
    loader: Callable[[Path | None], Iterable[Mapping[str, Any]]],
    artifact_dir: Path | None,
) -> list[dict[str, Any]]:
    if rows is not None:
        return _materialize_mapping_rows(rows)
    return _materialize_mapping_rows(loader(artifact_dir))


def _load_daily_brief_rows(
    *,
    run_rows: Iterable[Mapping[str, Any]],
    alert_rows: Iterable[Mapping[str, Any]],
    feedback_rows: Iterable[Mapping[str, Any]],
    missed_rows: Iterable[Mapping[str, Any]],
    core_opportunity_rows: Iterable[Mapping[str, Any]],
    hypothesis_rows: Iterable[Mapping[str, Any]],
    incident_rows: Iterable[Mapping[str, Any]],
    evidence_acquisition_rows: Iterable[Mapping[str, Any]],
    market_anomaly_rows: Iterable[Mapping[str, Any]] | None,
    official_exchange_candidate_rows: Iterable[Mapping[str, Any]] | None,
    scheduled_catalyst_rows: Iterable[Mapping[str, Any]] | None,
    unlock_candidate_rows: Iterable[Mapping[str, Any]] | None,
    derivatives_state_rows: Iterable[Mapping[str, Any]] | None,
    fade_review_candidate_rows: Iterable[Mapping[str, Any]] | None,
    requested_profile: str | None,
    artifact_namespace: str | None,
    run_ledger_path: str | Path | None,
    include_test_artifacts: bool,
    include_api_artifacts: bool,
) -> _DailyBriefRows:
    artifact_dir = _daily_brief_artifact_dir(run_ledger_path)
    raw_runs = _materialize_mapping_rows(run_rows)
    filter_kwargs = {
        "requested_profile": requested_profile,
        "artifact_namespace": artifact_namespace,
        "include_test_artifacts": include_test_artifacts,
        "include_api_artifacts": include_api_artifacts,
    }
    return _DailyBriefRows(
        legacy_available=any(event_alpha_artifacts.is_api_row(row) for row in raw_runs),
        runs=_filter_daily_brief_rows(raw_runs, **filter_kwargs),
        alerts=_filter_daily_brief_rows(alert_rows, **filter_kwargs),
        feedback=_filter_daily_brief_rows(feedback_rows, **filter_kwargs),
        missed=_filter_daily_brief_rows(missed_rows, **filter_kwargs),
        stored_core_rows=_filter_daily_brief_rows(_materialize_mapping_rows(core_opportunity_rows), **filter_kwargs),
        hypotheses=_filter_daily_brief_rows(_materialize_mapping_rows(hypothesis_rows), **filter_kwargs),
        incidents=_filter_daily_brief_rows(_materialize_mapping_rows(incident_rows), **filter_kwargs),
        acquisition_rows=_filter_daily_brief_rows(_materialize_mapping_rows(evidence_acquisition_rows), **filter_kwargs),
        market_anomalies=_filter_daily_brief_rows(
            _optional_daily_brief_rows(market_anomaly_rows, event_market_anomaly_scanner.load_market_anomaly_rows, artifact_dir),
            **filter_kwargs,
        ),
        official_exchange_candidates=_filter_daily_brief_rows(
            _optional_daily_brief_rows(
                official_exchange_candidate_rows,
                event_official_exchange.load_official_listing_candidates,
                artifact_dir,
            ),
            **filter_kwargs,
        ),
        scheduled_catalysts=_filter_daily_brief_rows(
            _optional_daily_brief_rows(scheduled_catalyst_rows, event_scheduled_catalysts.load_scheduled_catalysts, artifact_dir),
            **filter_kwargs,
        ),
        unlock_candidates=_filter_daily_brief_rows(
            _optional_daily_brief_rows(unlock_candidate_rows, event_scheduled_catalysts.load_unlock_candidates, artifact_dir),
            **filter_kwargs,
        ),
        derivatives_state=_filter_daily_brief_rows(
            _optional_daily_brief_rows(derivatives_state_rows, event_derivatives_crowding.load_derivatives_state, artifact_dir),
            **filter_kwargs,
        ),
        fade_review_candidates=_filter_daily_brief_rows(
            _optional_daily_brief_rows(
                fade_review_candidate_rows,
                event_derivatives_crowding.load_fade_review_candidates,
                artifact_dir,
            ),
            **filter_kwargs,
        ),
    )


def _prepare_daily_brief_context(
    rows: _DailyBriefRows,
    *,
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry],
    router_result: event_alpha_router.EventAlphaRouterResult | None,
    notification_runs: Iterable[Mapping[str, Any]],
    requested_profile: str | None,
    run_ledger_path: str | Path | None,
) -> _DailyBriefContext:
    entries = list(watchlist_entries)
    decisions = list(router_result.decisions if router_result else ())
    alertable = [
        decision
        for decision in list(router_result.alertable_decisions if router_result else ())
        if event_alpha_router.alertable_after_quality_gate(decision)
    ]
    if rows.stored_core_rows:
        all_core_opportunities = event_core_opportunity_store.core_opportunities_from_rows(rows.stored_core_rows)
        core_source_rows: list[Any] = rows.stored_core_rows
    else:
        all_core_opportunities = list(
            event_core_opportunities.aggregate_core_opportunities([*decisions, *rows.hypotheses])
        )
        core_source_rows = [*(decision.entry for decision in decisions), *rows.hypotheses]
    core_opportunities = [
        item for item in all_core_opportunities
        if event_core_opportunities.core_opportunity_is_visible(item)
    ]
    core_sections = _core_opportunity_sections(core_opportunities)
    lane_sections = _core_opportunity_lane_sections(core_opportunities)
    promoted_core_asset_keys = {
        event_core_opportunities.incident_asset_key_for_opportunity(item)
        for item in core_opportunities
        if item.alertable or item.is_high_priority or item.is_watchlist or item.is_validated_digest
    }
    promoted_core_assets = {
        event_core_opportunities.asset_key_for_opportunity(item)
        for item in core_opportunities
        if item.alertable or item.is_high_priority or item.is_watchlist or item.is_validated_digest
    }
    near_misses = event_near_miss.detect_near_miss_rows(core_source_rows, route_decisions=decisions)
    _, raw_upgrade_candidates = event_near_miss.split_near_miss_candidates(near_misses)
    near_miss_candidates = tuple(
        item for item in near_misses
        if not event_near_miss.is_upgrade_candidate(item)
        and event_core_opportunities.incident_asset_key_for_values(item.incident_id, item.coin_id, item.symbol)
        not in promoted_core_asset_keys
        and event_core_opportunities.asset_key_for_values(item.coin_id, item.symbol) not in promoted_core_assets
    )
    high_priority_core_asset_keys = {
        event_core_opportunities.asset_key_for_opportunity(item)
        for item in core_sections["strong"]
    }
    upgrade_candidates = tuple(
        item for item in raw_upgrade_candidates
        if event_core_opportunities.incident_asset_key_for_values(item.incident_id, item.coin_id, item.symbol)
        not in {event_core_opportunities.incident_asset_key_for_opportunity(core) for core in core_sections["strong"]}
        and event_core_opportunities.asset_key_for_values(item.coin_id, item.symbol) not in high_priority_core_asset_keys
    )
    near_miss_asset_keys = {
        event_core_opportunities.asset_key_for_values(item.coin_id, item.symbol)
        for item in near_miss_candidates
    }
    near_miss_incident_asset_keys = {
        event_core_opportunities.incident_asset_key_for_values(item.incident_id, item.coin_id, item.symbol)
        for item in near_miss_candidates
    }
    local_core_rows = [
        item for item in core_sections["local"]
        if event_core_opportunities.asset_key_for_opportunity(item) not in near_miss_asset_keys
        and event_core_opportunities.incident_asset_key_for_opportunity(item) not in near_miss_incident_asset_keys
    ]
    latest = event_alpha_run_ledger.latest_run(rows.runs, requested_profile) or {}
    if latest and run_ledger_path:
        latest = event_alpha_operator_state.enrich_run_row_from_core_store(
            Path(run_ledger_path).parent,
            latest,
        )
    selected_profile = str(latest.get("profile") or "default") if latest else "none"
    selected_namespace = str(latest.get("artifact_namespace") or "legacy") if latest else "none"
    requested = str(requested_profile or "latest").strip() or "latest"
    return _DailyBriefContext(
        entries=entries,
        decisions=decisions,
        alertable=alertable,
        all_core_opportunities=all_core_opportunities,
        core_opportunities=core_opportunities,
        core_source_rows=core_source_rows,
        core_sections=core_sections,
        lane_sections=lane_sections,
        source_coverage_report_path=(
            Path(run_ledger_path).parent / "event_alpha_source_coverage.md"
            if run_ledger_path
            else None
        ),
        core_alertable_count=_core_alertable_count(core_opportunities),
        diagnostic_core_rows=sum(item.diagnostic_row_count for item in all_core_opportunities),
        diagnostic_control_rows=sum(item.source_noise_control_count for item in all_core_opportunities),
        diagnostic_capped_rows=sum(item.quality_capped_supporting_rows for item in all_core_opportunities),
        promoted_core_asset_keys=promoted_core_asset_keys,
        promoted_core_assets=promoted_core_assets,
        near_miss_candidates=near_miss_candidates,
        upgrade_candidates=upgrade_candidates,
        local_core_rows=local_core_rows,
        latest=latest,
        latest_notification=_latest_notification_run(notification_runs),
        selected_profile=selected_profile,
        selected_namespace=selected_namespace,
        requested=requested,
        profile_match=(
            "n/a"
            if not latest or requested_profile is None
            else str(selected_profile == str(requested_profile)).lower()
        ),
        mismatch_warning=event_alpha_run_ledger.run_profile_mismatch_warning(requested_profile, latest),
    )


def _daily_brief_header_lines(
    *,
    generated: datetime,
    clock_status: Mapping[str, Any],
    requested_profile: str | None,
    artifact_namespace: str | None,
    run_mode: str | None,
    run_ledger_path: str | Path | None,
    alert_store_path: str | Path | None,
    rows: _DailyBriefRows,
    context: _DailyBriefContext,
    card_paths: Iterable[Path],
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None,
) -> list[str]:
    counters = event_alpha_run_counters.canonical_run_counters(context.latest)
    return [
        "# Event Alpha Daily Brief",
        "",
        f"Generated at: {generated.isoformat()}",
        _format_clock_status(clock_status or {}),
        *_format_clock_warning_lines(clock_status or {}),
        f"Requested profile: {context.requested}",
        f"Artifact namespace: {artifact_namespace or 'any'}",
        f"Run mode: {run_mode or 'unknown'}",
        f"Run ledger path: {event_alpha_artifacts.safe_path_label(run_ledger_path) if run_ledger_path else 'unknown'}",
        f"Alert store path: {event_alpha_artifacts.safe_path_label(alert_store_path) if alert_store_path else 'unknown'}",
        f"Selected run profile: {context.selected_profile}",
        f"Selected run namespace: {context.selected_namespace}",
        f"Profile match: {context.profile_match}",
        "",
        "Research-only. Not a trade signal, paper trade, live RSI signal, or execution.",
        "Canonical operator view: Core Opportunities sections above. Diagnostics appendix contains raw/supporting/control rows and may repeat assets for debugging.",
        "",
        "## Executive Summary",
        (
            f"- Run event funnel: raw_events={counters['raw_events']}, "
            f"candidate_events={counters['candidate_events']}, "
            f"research_candidates={counters['research_candidates']}"
        ),
        (
            f"- Canonical core scopes: source_alert_snapshots={counters['source_alert_snapshots']}, "
            f"current_generation_core_rows={counters['current_generation_core_rows']}, "
            f"current_generation_visible_core_rows={counters['current_generation_visible_core_rows']}, "
            f"cumulative_store_rows={counters['cumulative_store_rows']}"
        ),
        (
            f"- Decision/preview output: alertable_decisions={counters['alertable_decisions']}, "
            f"strict_alerts={counters['strict_alerts']}, "
            f"preview_rendered_items={counters['preview_rendered_items']}"
        ),
        f"- Current-generation visible core opportunity identities: {len(context.core_opportunities)} "
        f"(high_priority={len(context.core_sections['strong'])}, digest={len(context.core_sections['digest'])}, "
        f"watchlist={len(context.core_sections['watchlist'])}, near_miss={len(context.near_miss_candidates)}, "
        f"upgrade={len(context.upgrade_candidates)}, "
        f"local_or_capped={len(context.local_core_rows)})",
        f"- Visible core rows passing final alertability gates: {context.core_alertable_count}",
        f"- Near-miss candidates: {len(context.near_miss_candidates)}",
        f"- Upgrade candidates: {len(context.upgrade_candidates)}",
        "- Opportunity lanes: "
        + ", ".join(
            f"{name}={len(items)}"
            for name, items in context.lane_sections.items()
            if name != "diagnostics"
        ),
        "",
        "## Burn-In Readiness",
        *_burn_in_readiness_lines(
            latest=context.latest,
            core_opportunities=context.core_opportunities,
            card_paths=card_paths,
            evidence_acquisition_rows=rows.acquisition_rows,
            provider_health_rows=provider_health_rows or {},
            requested_profile=requested_profile,
            source_coverage_report_path=context.source_coverage_report_path,
        ),
        "",
    ]


def _daily_brief_opportunity_lines(rows: _DailyBriefRows, context: _DailyBriefContext) -> list[str]:
    return [
        "## Opportunity Lanes",
        "Research-only lane classification. Not a trade signal.",
        "",
        "### Early Long Research",
        *_core_opportunity_lines(context.lane_sections["early"], limit=8),
        "",
        "### Confirmed Long Research",
        *_core_opportunity_lines(context.lane_sections["confirmed"], limit=8),
        "",
        "### Fade / Short-Review",
        *_core_opportunity_lines(context.lane_sections["fade"], limit=8),
        "",
        "### Risk Only",
        *_core_opportunity_lines(context.lane_sections["risk"], limit=8),
        "",
        "### Unconfirmed Research",
        *_core_opportunity_lines(context.lane_sections["unconfirmed"], limit=8),
        "",
        "## High-Priority Core Opportunities",
        *_core_opportunity_lines(context.core_sections["strong"], limit=8),
        "",
        "## Validated Digest Core Opportunities",
        *_core_opportunity_lines(context.core_sections["digest"], limit=8),
        "",
        "## Watchlist Core Opportunities",
        *_core_opportunity_lines(context.core_sections["watchlist"], limit=8),
        "",
        "## Near-Miss Candidates",
        *_near_miss_daily_lines(context.near_miss_candidates, limit=8),
        "",
        "## Upgrade Candidates",
        *_near_miss_daily_lines(context.upgrade_candidates, limit=8),
        "",
        "## Quality-Capped / Local-Only Candidates",
        *_core_opportunity_lines(context.local_core_rows, limit=8),
        "",
        "## Live Confirmation Gated Candidates",
        *_live_confirmation_gated_core_lines(context.core_opportunities, limit=8),
        "",
        "## Market Anomalies / Catalyst Enrichment Queue (legacy alert gate)",
        *_market_anomaly_daily_lines(rows.market_anomalies, limit=10),
        "",
        "## Fresh Official Exchange Catalysts",
        *_official_exchange_daily_lines(rows.official_exchange_candidates, limit=10),
        "",
        "## Upcoming Scheduled Catalysts",
        *_scheduled_catalyst_daily_lines(rows.scheduled_catalysts, limit=10),
        "",
        "## Unlock / Supply Risk",
        *_unlock_risk_daily_lines(rows.unlock_candidates, limit=10),
        "",
        "## Derivatives Crowding / Fade-Review Research",
        *_derivatives_fade_review_daily_lines(rows.fade_review_candidates, rows.derivatives_state, limit=10),
        "",
        "## Catalyst Calendar Gaps",
        *_calendar_gap_daily_lines([*rows.scheduled_catalysts, *rows.unlock_candidates], limit=10),
        "",
        "## Near-Term Events Needing Market Watch",
        *_scheduled_market_watch_lines([*rows.scheduled_catalysts, *rows.unlock_candidates], limit=10),
        "",
        "## Canonical Incidents",
        *_canonical_incident_lines(rows.incidents),
        "",
    ]


def _daily_brief_source_intro_lines(
    *,
    rows: _DailyBriefRows,
    context: _DailyBriefContext,
    requested_profile: str | None,
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None,
) -> list[str]:
    return [
        "## System Health",
        *_system_health_summary_lines(context.latest),
        "",
        "## Source Coverage / Evidence Acquisition",
        *_source_coverage_summary_lines(
            [*context.core_source_rows, *rows.alerts],
            context.near_miss_candidates,
            context.upgrade_candidates,
            acquisition_rows=rows.acquisition_rows,
            source_coverage_report_path=context.source_coverage_report_path,
        ),
        "",
        "### Provider Health by Source Pack",
        *_provider_health_by_pack_lines(
            provider_health_rows or {},
            source_coverage_report_path=context.source_coverage_report_path,
        ),
        "",
        "### Evidence Acquisition Results",
        *_evidence_acquisition_result_lines(
            (*context.near_miss_candidates, *context.upgrade_candidates),
            acquisition_rows=rows.acquisition_rows,
            core_opportunities=context.core_opportunities,
            limit=8,
        ),
        "",
        "### Candidates Blocked by Source Coverage",
        *_coverage_blocked_candidate_lines((*context.near_miss_candidates, *context.upgrade_candidates), limit=8),
        "",
        "## Market Freshness Readiness",
        *_market_freshness_readiness_lines([*context.core_source_rows, *rows.alerts], requested_profile=requested_profile),
        "",
        "## Diagnostics Appendix",
        "### Diagnostic Appendix: Diagnostics / Source-Noise / Controls",
        (
            "- Hidden from main opportunity sections by default: "
            f"diagnostic_rows={context.diagnostic_core_rows}, "
            f"source_noise_controls={context.diagnostic_control_rows}, "
            f"quality_capped_support={context.diagnostic_capped_rows}, "
            f"hidden_nonvisible_core_identities={len(context.all_core_opportunities) - len(context.core_opportunities)}"
        ),
        (
            "- Pass include_diagnostics in local tooling to inspect collapsed controls."
            if context.diagnostic_core_rows or context.diagnostic_control_rows or context.diagnostic_capped_rows
            else "- None."
        ),
        "",
        "### System Health / Providers / Budget",
    ]


def _append_system_health_detail_sections(
    lines: list[str],
    *,
    rows: _DailyBriefRows,
    context: _DailyBriefContext,
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None,
    requested_profile: str | None,
    include_api_artifacts: bool,
) -> None:
    if context.mismatch_warning:
        lines.append(f"- Profile warning: {context.mismatch_warning}")
    if requested_profile and not rows.runs and rows.legacy_available and not include_api_artifacts:
        lines.append("- Profile warning: only legacy/default run rows were available; they were ignored for this profile brief")
    if context.latest:
        run_alertable = int(context.latest.get("alertable") or 0)
        alertable_text = str(context.core_alertable_count)
        if run_alertable != context.core_alertable_count:
            alertable_text = f"{context.core_alertable_count} (run_ledger_pre_core={run_alertable})"
        lines.extend(_latest_run_health_lines(context.latest, alertable_text))
    else:
        lines.append("- No run ledger rows found.")
    if context.latest_notification is not None:
        lines.extend(_latest_notification_health_lines(context.latest_notification))
    lines.extend(["", "#### Provider Health"])
    lines.extend(_provider_health_lines(provider_health_rows or {}))
    lines.extend(["", "#### LLM Budget"])
    lines.extend(_llm_budget_lines(context.latest))


def _append_hypothesis_sections(lines: list[str], *, rows: _DailyBriefRows, context: _DailyBriefContext) -> None:
    lines.extend(["", "### Impact Hypotheses"])
    if context.latest:
        lines.extend(_run_hypothesis_summary_lines(context.latest))
    else:
        lines.append("- No run row available.")
    if rows.hypotheses:
        lines.extend(_stored_hypothesis_summary_lines(rows.hypotheses))
    elif context.latest and int(context.latest.get("impact_hypotheses") or 0) > 0:
        lines.append("- Stored rows: none loaded for this profile; inspect --event-impact-hypotheses-report.")
    lines.extend(["", "### Catalyst Search Skip Reasons"])
    lines.extend(_catalyst_search_skip_lines(context.latest))


def _run_hypothesis_summary_lines(latest: Mapping[str, Any]) -> list[str]:
    lines = [
        f"- Generated/validated/promoted: {int(latest.get('impact_hypotheses') or 0)} / "
        f"{int(latest.get('hypotheses_validated') or 0)} / {int(latest.get('hypothesis_promotions') or 0)}",
        f"- Validation queries/results: {int(latest.get('hypothesis_search_queries') or 0)} / "
        f"{int(latest.get('hypothesis_search_results') or 0)}",
    ]
    query_types = latest.get("hypothesis_search_queries_by_type") or {}
    result_types = latest.get("hypothesis_search_results_by_type") or {}
    if isinstance(query_types, Mapping) or isinstance(result_types, Mapping):
        lines.append(
            "- Validation query types: "
            f"queries={_format_counts(query_types if isinstance(query_types, Mapping) else {})}; "
            f"results={_format_counts(result_types if isinstance(result_types, Mapping) else {})}"
        )
    if int(latest.get("hypotheses_validated") or 0) <= 0:
        lines.append("- Validated hypotheses: none yet.")
    if int(latest.get("impact_hypotheses") or 0) > int(latest.get("hypotheses_validated") or 0):
        lines.append("- Top rejected/pending hypotheses: see Event Alpha pipeline report and local watchlist HYPOTHESIS rows.")
    hypothesis_skip = latest.get("hypothesis_search_skip_reasons") or {}
    if isinstance(hypothesis_skip, Mapping) and hypothesis_skip:
        lines.append(
            "- Hypothesis validation skips: "
            + ", ".join(f"{key}={int(value or 0)}" for key, value in sorted(hypothesis_skip.items()))
        )
    return lines


def _stored_hypothesis_summary_lines(hypotheses: list[dict[str, Any]]) -> list[str]:
    lines = [
        "- Stored rows: " + str(len(hypotheses)),
        "- Stored schema versions: "
        + _format_counts(_field_counts(hypotheses, "schema_version"))
        + f" (legacy={_api_hypothesis_count(hypotheses)})",
        "- Stored statuses: " + _format_counts(_field_counts(hypotheses, "status")),
        "- Stored validation stages: " + _format_counts(_field_counts(hypotheses, "validation_stage")),
        "- Stored categories: " + _format_counts(_field_counts(hypotheses, "impact_category")),
        "- Why not promoted: " + _format_counts(_multi_field_counts(hypotheses, "why_not_promoted")),
    ]
    pending = [row for row in hypotheses if str(row.get("status") or "") in {"validation_search_pending", "hypothesis"}]
    validated = [row for row in hypotheses if str(row.get("status") or "") in {"validation_evidence_found", "validated"}]
    rejected = [row for row in hypotheses if str(row.get("status") or "") == "rejected" or row.get("rejection_reasons")]
    ranked = sorted(
        hypotheses,
        key=lambda row: _float(row.get("hypothesis_score") or _float(row.get("confidence")) * 100),
        reverse=True,
    )
    lines.append("- Validated stored hypotheses: " + (_brief_hypothesis_labels(validated[:3]) or "none"))
    lines.append("- Pending stored hypotheses: " + (_brief_hypothesis_labels(pending[:3]) or "none"))
    lines.append("- Top rejected hypotheses: " + (_brief_hypothesis_labels(rejected[:3]) or "none"))
    lines.append("- Top hypothesis scores: " + (_brief_hypothesis_labels(ranked[:3]) or "none"))
    lines.extend(_rejected_hypothesis_sample_lines(hypotheses))
    return lines


def _api_hypothesis_count(hypotheses: list[dict[str, Any]]) -> int:
    return sum(
        1 for row in hypotheses
        if not str(row.get("schema_version") or "").startswith("event_impact_hypothesis_store_")
        or any(field not in row for field in ("validation_stage", "hypothesis_score", "external_entities", "crypto_candidate_assets"))
    )


def _rejected_hypothesis_sample_lines(hypotheses: list[dict[str, Any]]) -> list[str]:
    rejected_samples = [
        sample
        for row in hypotheses
        for sample in (row.get("rejected_validation_samples") or [])
        if isinstance(sample, Mapping) and (not bool(sample.get("accepted")) or sample.get("rejection_reason"))
    ]
    if not rejected_samples:
        return []
    reason_counts: dict[str, int] = {}
    titles: list[str] = []
    for sample in rejected_samples:
        reason = str(sample.get("rejection_reason") or "unknown")
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        title = str(sample.get("result_title") or "").strip()
        if title and title not in titles:
            titles.append(title)
    lines = [
        f"- Rejected validation evidence samples: {len(rejected_samples)}",
        "- Rejected evidence reasons: " + _format_counts(reason_counts),
    ]
    if titles:
        lines.append("- Rejected evidence examples: " + " | ".join(titles[:3]))
    return lines


def _catalyst_search_skip_lines(latest: Mapping[str, Any]) -> list[str]:
    if not latest:
        return ["- No run row available."]
    skip_reasons = latest.get("catalyst_search_skip_reasons") or {}
    if isinstance(skip_reasons, Mapping) and skip_reasons:
        return [f"- {key}: {int(value or 0)}" for key, value in sorted(skip_reasons.items())]
    if int(latest.get("market_anomalies") or 0) > 0 and int(latest.get("catalyst_queries") or 0) == 0:
        return ["- unknown: market anomalies were present but no catalyst queries were generated."]
    return ["- None."]


def _append_recent_activity_sections(
    lines: list[str],
    *,
    rows: _DailyBriefRows,
    context: _DailyBriefContext,
    include_diagnostics: bool,
) -> None:
    lines.extend(["", "### New Since Last Run"])
    lines.extend(_new_since_last_run_lines(rows.runs))
    lines.extend(["", "### Watchlist Got Hotter"])
    lines.extend(_watchlist_hotter_lines(context.entries))
    lines.extend(["", "### Alertable Decisions"])
    if context.core_alertable_count > 0:
        lines.append(f"- {context.core_alertable_count} canonical alertable core opportunity/opportunities; see core opportunity sections above.")
    elif context.alertable and include_diagnostics:
        lines.append("- Raw pre-policy route attempts only; these are diagnostic rows and are not operator alert truth.")
        for decision in context.alertable[:10]:
            entry = decision.entry
            lines.append(
                f"- diagnostic {event_alpha_router.final_route_value(decision)}: {entry.symbol}/{entry.coin_id} "
                f"state={event_watchlist.final_state_value(entry)} score={entry.latest_score} reason={decision.reason}"
            )
    else:
        lines.append("- None.")


def _append_impact_quality_sections(
    lines: list[str],
    *,
    rows: _DailyBriefRows,
    context: _DailyBriefContext,
    include_diagnostics: bool,
) -> None:
    routing = _impact_hypothesis_routing_context(rows, context)
    lines.extend(["", "### Validated Impact Hypothesis Routing"])
    lines.append("- Strong opportunity candidates: " + (_brief_core_opportunities(context.core_opportunities, section="strong", limit=5) or "none"))
    digest_candidates = _brief_core_opportunities(context.core_opportunities, section="digest", limit=5)
    if not digest_candidates and include_diagnostics:
        digest_candidates = (
            "raw diagnostic only: "
            + (_brief_decisions(routing["alertable"][:5]) or _brief_decisions(routing["impact_path_validated"][:5]) or "none")
        )
    lines.append("- Impact-path validated digest candidates: " + (digest_candidates or "none"))
    lines.append("- Validated but market-unconfirmed: " + (_brief_decisions(routing["market_unconfirmed"][:5]) or "none"))
    lines.append("- Weak validated local-only hypotheses: " + (_brief_decisions(routing["weak_local"][:5]) or "none"))
    lines.append("- Generic co-occurrence blocked: " + (_brief_decisions(routing["generic_blocked"][:5]) or "none"))
    lines.append("- Sector hypotheses awaiting validation: " + (_brief_entries(routing["exploratory_sector"][:5]) or "none"))
    lines.append("- Rejected/why-not-promoted hypotheses: " + (_brief_hypothesis_labels(routing["rejected"][:5]) or "none"))
    lines.append("- Market confirmation by playbook: " + _market_confirmation_by_playbook(context.decisions))
    lines.append("- Top upgrade candidates: " + (_upgrade_candidate_line(context.decisions) or "none"))
    lines.append("- Top downgrade risks: " + (_downgrade_risk_line(context.decisions) or "none"))
    lines.extend(["", "### Near-Miss Diagnostics"])
    lines.extend(_near_miss_diagnostic_lines(context.near_miss_candidates, limit=8))
    lines.extend(["", "### Upgrade Candidate Diagnostics"])
    lines.extend(_near_miss_diagnostic_lines(context.upgrade_candidates, limit=8))
    _append_signal_quality_lines(lines, rows, context)


def _impact_hypothesis_routing_context(rows: _DailyBriefRows, context: _DailyBriefContext) -> dict[str, list[Any]]:
    local_validated = [
        decision for decision in context.decisions
        if decision.entry.relationship_type == "impact_hypothesis"
        and not event_alpha_router.alertable_after_quality_gate(decision)
        and event_watchlist.final_state_value(decision.entry) == event_watchlist.EventWatchlistState.RADAR.value
        and decision.entry.symbol.upper() != "SECTOR"
    ]
    return {
        "alertable": [
            decision for decision in context.decisions
            if decision.entry.relationship_type == "impact_hypothesis" and event_alpha_router.alertable_after_quality_gate(decision)
        ],
        "impact_path_validated": [
            decision for decision in context.decisions
            if decision.entry.relationship_type == "impact_hypothesis"
            and str((decision.entry.latest_score_components or {}).get("validation_stage") or "")
            in {"impact_path_validated", "market_confirmed", "promoted_to_radar"}
        ],
        "weak_local": [
            decision for decision in local_validated
            if str((decision.entry.latest_score_components or {}).get("validation_stage") or "") == "catalyst_link_validated"
            or str((decision.entry.latest_score_components or {}).get("impact_path_strength") or "") in {"weak", "none"}
            or bool((decision.entry.latest_score_components or {}).get("why_digest_ineligible"))
        ],
        "generic_blocked": [
            decision for decision in local_validated
            if str((decision.entry.latest_score_components or {}).get("impact_path_type") or "") == "generic_cooccurrence_only"
        ],
        "market_unconfirmed": [
            decision for decision in local_validated
            if str((decision.entry.latest_score_components or {}).get("market_confirmation_level") or "") in {"", "none", "weak"}
            and str((decision.entry.latest_score_components or {}).get("opportunity_level") or "") in {"local_only", "exploratory", ""}
        ],
        "exploratory_sector": [
            entry for entry in context.entries
            if entry.relationship_type == "impact_hypothesis"
            and event_watchlist.final_state_value(entry) == event_watchlist.EventWatchlistState.HYPOTHESIS.value
        ],
        "rejected": [
            row for row in rows.hypotheses
            if str(row.get("status") or "") == "rejected" or row.get("why_not_promoted") or row.get("rejection_reasons")
        ],
    }


def _append_signal_quality_lines(lines: list[str], rows: _DailyBriefRows, context: _DailyBriefContext) -> None:
    lines.extend(["", "### Signal Quality Summary"])
    for field, label in (
        ("opportunity_level", "Opportunity Verdict Distribution"),
        ("impact_path_type", "Impact Path Distribution"),
        ("candidate_role", "Candidate Role Distribution"),
        ("event_archetype", "Incident Archetype Distribution"),
        ("cause_status", "Cause Status Distribution"),
        ("market_reaction_confirmed", "Market Reaction Confirmed"),
        ("causal_mechanism_confirmed", "Causal Mechanism Confirmed"),
        ("evidence_specificity", "Evidence Specificity Distribution"),
        ("market_confirmation_level", "Market Confirmation Distribution"),
    ):
        lines.append(f"- {label}: " + _quality_decision_counts(context.decisions, field))
    quality_rows = [
        decision for decision in context.decisions
        if decision.entry.relationship_type == "impact_hypothesis"
    ]
    lines.append(
        f"- quality_row_market_freshness: total={len(quality_rows)}; statuses="
        + _quality_decision_counts(quality_rows, "market_context_freshness_status")
    )
    lines.append("- Top Upgrade Candidates: " + (_upgrade_candidate_line(context.decisions) or "none"))
    lines.append("- Top Downgrade Risks: " + (_downgrade_risk_line(context.decisions) or "none"))
    lines.append("- Candidate Discovery Funnel: " + _candidate_discovery_funnel_line(rows.hypotheses))
    lines.append("- Feedback by Impact Path: " + _feedback_by_impact_path(rows.alerts, rows.feedback))
    lines.extend(["", "### Quality Gate Downgrades"])
    downgraded = _quality_gate_downgrades(context.decisions)
    lines.append("- Downgraded items: " + (_brief_decisions(downgraded[:5]) or "none"))
    lines.append("- Top blocked route attempts: " + (_blocked_route_attempts_line(downgraded) or "none"))
    lines.append("- Reason counts: " + _quality_gate_reason_counts(downgraded))
    lines.extend(["", "### Legacy Quality Conflicts"])
    lines.extend(_api_quality_conflict_lines(_api_quality_conflicts(rows.alerts)[:8]))


def _append_notification_digest_sections(
    lines: list[str],
    *,
    context: _DailyBriefContext,
    generated: datetime,
    run_ledger_path: str | Path | None,
) -> None:
    _append_research_review_digest(lines, context=context, generated=generated, run_ledger_path=run_ledger_path)
    _append_exploratory_digest(lines, context=context, generated=generated)


def _append_research_review_digest(
    lines: list[str],
    *,
    context: _DailyBriefContext,
    generated: datetime,
    run_ledger_path: str | Path | None,
) -> None:
    research_review = event_alpha_notifications.select_research_review_candidates(
        context.decisions,
        cfg=event_alpha_notifications.EventAlphaNotificationConfig(
            research_review_digest_enabled=True,
            research_review_digest_max_items=5,
            research_review_digest_min_score=60,
            research_review_digest_include_local_only=False,
        ),
        now=generated,
    )
    research_review = tuple(item for item in research_review if _review_item_is_not_promoted(item, context))
    lines.extend(["", "### Research Review Digest"])
    review_due = _lane_count(context.latest_notification, "lane_counts_due", event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST)
    review_sent = _lane_count(context.latest_notification, "lane_counts_sent", event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST)
    if context.latest:
        lines.append(
            "- Run ledger: "
            f"research_review_digest_enabled={str(bool(context.latest.get('research_review_digest_enabled'))).lower()} "
            f"research_review_digest_candidates={int(context.latest.get('research_review_digest_candidates') or 0)} "
            f"research_review_digest_would_send={int(context.latest.get('research_review_digest_would_send') or 0)} "
            f"research_review_digest_block={context.latest.get('research_review_digest_block_reason') or 'none'}"
        )
    lines.append(f"- Lane count sent/due: {review_sent}/{review_due}")
    lines.append("- Near-miss research review only; not alertable, missing confirmation, and not a trade signal.")
    planned_review_deliveries = _research_review_delivery_rows(run_ledger_path)
    if research_review:
        for item in research_review[:5]:
            entry = item.decision.entry
            lines.append(
                f"- {entry.symbol}/{entry.coin_id} level={event_alpha_notifications._research_review_level(item.decision) or 'unknown'} "
                f"score={event_alpha_notifications._research_review_score(item.decision):g} "
                f"why_not_alertable={'; '.join(item.why_not_alertable) or 'missing confirmation'}"
            )
    elif planned_review_deliveries:
        for row in planned_review_deliveries[:5]:
            lines.append(_research_review_delivery_line(row))
        if len(planned_review_deliveries) > 5:
            lines.append(f"- +{len(planned_review_deliveries) - 5} more research-review delivery candidates")
    else:
        lines.append("- None.")


def _review_item_is_not_promoted(item: Any, context: _DailyBriefContext) -> bool:
    entry = item.decision.entry
    return (
        event_core_opportunities.incident_asset_key_for_values(getattr(entry, "incident_id", None), entry.coin_id, entry.symbol)
        not in context.promoted_core_asset_keys
        and event_core_opportunities.asset_key_for_values(entry.coin_id, entry.symbol) not in context.promoted_core_assets
    )


def _append_exploratory_digest(lines: list[str], *, context: _DailyBriefContext, generated: datetime) -> None:
    exploratory = event_alpha_notifications.select_exploratory_candidates(
        context.decisions,
        cfg=event_alpha_notifications.EventAlphaNotificationConfig(
            exploratory_digest_enabled=True,
            exploratory_digest_max_items=5,
        ),
        now=generated,
    )
    exploratory = tuple(item for item in exploratory if _review_item_is_not_promoted(item, context))
    lines.extend(["", "### Exploratory Digest"])
    exploratory_due = _lane_count(context.latest_notification, "lane_counts_due", event_alpha_notifications.LANE_EXPLORATORY_DIGEST)
    exploratory_sent = _lane_count(context.latest_notification, "lane_counts_sent", event_alpha_notifications.LANE_EXPLORATORY_DIGEST)
    lines.append(f"- Lane count sent/due: {exploratory_sent}/{exploratory_due}")
    lines.append("- Unvalidated suppressed/store-only rows for learning; not alertable and not a trade signal.")
    if exploratory:
        for item in exploratory[:5]:
            entry = item.decision.entry
            lines.append(
                f"- {entry.symbol}/{entry.coin_id} score={entry.latest_score} "
                f"playbook={entry.latest_playbook_type or 'unknown'} reason={entry.suppressed_reason or item.decision.reason}"
            )
    else:
        lines.append("- None.")


def _append_watchlist_sections(lines: list[str], context: _DailyBriefContext) -> None:
    lines.extend(["", "### Active Watchlist"])
    active = _dedupe_watchlist_entries([
        entry for entry in context.entries
        if not event_watchlist.state_is_quality_capped(entry)
        and event_watchlist.final_state_value(entry) in {
            event_watchlist.EventWatchlistState.RADAR.value,
            event_watchlist.EventWatchlistState.WATCHLIST.value,
            event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            event_watchlist.EventWatchlistState.EVENT_PASSED.value,
            event_watchlist.EventWatchlistState.ARMED.value,
        }
    ])
    if active:
        for entry in sorted(active, key=lambda item: item.latest_score, reverse=True)[:5]:
            lines.append(
                f"- {event_watchlist.final_state_value(entry)}: {entry.symbol}/{entry.coin_id} "
                f"score={entry.latest_score} playbook={entry.latest_playbook_type or 'unknown'}"
                f"{_watchlist_identity_suffix(entry)}"
            )
    else:
        lines.append("- No active watchlist entries.")
    lines.extend(["", "### Quality-Capped Watchlist Rows"])
    capped = _dedupe_watchlist_entries([entry for entry in context.entries if event_watchlist.state_is_quality_capped(entry)])
    if capped:
        for entry in sorted(capped, key=lambda item: item.latest_score, reverse=True)[:10]:
            lines.append(
                f"- {entry.symbol}/{entry.coin_id}: requested={event_watchlist.requested_state_value(entry)} "
                f"final={event_watchlist.final_state_value(entry)} "
                f"level={entry.opportunity_level or 'unknown'} "
                f"path={entry.impact_path_type or 'unknown'} "
                f"score={entry.opportunity_score_final if entry.opportunity_score_final is not None else 'n/a'} "
                f"block={entry.quality_state_block_reason or 'quality_state_capped'}"
            )
    else:
        lines.append("- None.")


def _append_card_sections(
    lines: list[str],
    *,
    context: _DailyBriefContext,
    card_paths: Iterable[Path],
    include_diagnostics: bool,
) -> None:
    lines.extend(["", "### Research Cards"])
    cards = [Path(path) for path in card_paths]
    if not cards:
        lines.append("- No cards written for this brief.")
        return
    grouped_cards = _card_groups_for_daily_brief(cards)
    for group_name in event_research_cards.CARD_INDEX_GROUPS:
        paths = grouped_cards.get(group_name, [])
        lines.append(f"#### {group_name}")
        if group_name == "Diagnostic / Source-Noise / Control Cards" and not include_diagnostics:
            lines.append(
                f"- Hidden from main card list by default: cards={len(paths)}, "
                f"diagnostics={context.diagnostic_core_rows}, quality_capped_support={context.diagnostic_capped_rows}"
            )
            continue
        if not paths:
            lines.append("- None.")
            continue
        collapsed_paths = event_research_cards.collapse_card_paths_for_group(
            paths,
            group_name=group_name,
            card_groups=grouped_cards,
        )
        for path, hidden_count in collapsed_paths[:20]:
            target = event_research_cards.card_feedback_target(path)
            suffix = f" · feedback target: `{target}`" if target else ""
            if hidden_count:
                suffix += f" · +{hidden_count} related diagnostic/support card(s) hidden"
            display_path = event_artifact_paths.artifact_display_path(path)
            lines.append(f"- [{path.name}]({display_path}) · group: {group_name}{suffix}")
        if len(collapsed_paths) > 20:
            lines.append(f"- +{len(collapsed_paths) - 20} more card families")


def _append_tail_sections(
    lines: list[str],
    *,
    rows: _DailyBriefRows,
    context: _DailyBriefContext,
    requested_profile: str | None,
    artifact_namespace: str | None,
    include_test_artifacts: bool,
    include_api_artifacts: bool,
    include_diagnostics: bool,
) -> None:
    lines.extend(["", "### Missed Opportunities"])
    if rows.missed:
        for row in sorted(rows.missed, key=lambda item: abs(_float(item.get("return_pct"))), reverse=True)[:5]:
            lines.append(f"- {row.get('symbol') or row.get('coin_id')}: {row.get('move_window')} {row.get('return_pct')} stage={row.get('failure_stage')}")
    else:
        lines.append("- No missed-opportunity rows found.")
    lines.extend(["", "### Source Reliability"])
    lines.append(_compact(event_source_reliability.format_source_reliability_report(
        rows.alerts,
        feedback_rows=rows.feedback,
        missed_rows=rows.missed,
        run_rows=rows.runs[:10],
    )))
    lines.extend(["", "### Calibration Recommendations"])
    lines.append(_compact(event_alpha_calibration.format_calibration_report(
        rows.alerts,
        feedback_rows=rows.feedback,
        missed_rows=rows.missed,
    )))
    lines.extend(["", "### Top Suppression Reasons"])
    lines.extend(_suppression_lines(context.decisions, context.entries))
    if context.core_alertable_count <= 0:
        lines.extend(["", "### Why No Strict Alerts"])
        lines.append(_compact(event_alpha_explain.format_last_run_explanation(
            rows.runs,
            alert_rows=rows.alerts,
            requested_profile=requested_profile,
            artifact_namespace=artifact_namespace,
            include_test_artifacts=include_test_artifacts,
            include_api_artifacts=include_api_artifacts,
        )))
    elif context.alertable and include_diagnostics:
        lines.extend(["", "### Raw Pre-Policy Route Attempts / Diagnostics"])
        lines.append("- These rows were generated before canonical core/live-confirmation policy and are not proof of sent notification items.")
        for decision in context.alertable[:8]:
            lines.append(f"- {decision.entry.symbol}/{decision.entry.coin_id}: {decision.reason}")
    else:
        lines.extend(["", "### Why Alertable Core Routes Exist"])
        lines.append("- Canonical core opportunities passed final quality and live-confirmation gates; no raw pre-policy route text is shown by default.")


def build_daily_brief(
    *,
    run_rows: Iterable[Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
    core_opportunity_rows: Iterable[Mapping[str, Any]] = (),
    notification_runs: Iterable[Mapping[str, Any]] = (),
    hypothesis_rows: Iterable[Mapping[str, Any]] = (),
    incident_rows: Iterable[Mapping[str, Any]] = (),
    evidence_acquisition_rows: Iterable[Mapping[str, Any]] = (),
    market_anomaly_rows: Iterable[Mapping[str, Any]] | None = None,
    official_exchange_candidate_rows: Iterable[Mapping[str, Any]] | None = None,
    scheduled_catalyst_rows: Iterable[Mapping[str, Any]] | None = None,
    unlock_candidate_rows: Iterable[Mapping[str, Any]] | None = None,
    derivatives_state_rows: Iterable[Mapping[str, Any]] | None = None,
    fade_review_candidate_rows: Iterable[Mapping[str, Any]] | None = None,
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry] = (),
    router_result: event_alpha_router.EventAlphaRouterResult | None = None,
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    card_paths: Iterable[Path] = (),
    requested_profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_ledger_path: str | Path | None = None,
    alert_store_path: str | Path | None = None,
    include_test_artifacts: bool = False,
    include_api_artifacts: bool = False,
    include_diagnostics: bool = False,
    clock_status: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> str:
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rows = _load_daily_brief_rows(
        run_rows=run_rows,
        alert_rows=alert_rows,
        feedback_rows=feedback_rows,
        missed_rows=missed_rows,
        core_opportunity_rows=core_opportunity_rows,
        hypothesis_rows=hypothesis_rows,
        incident_rows=incident_rows,
        evidence_acquisition_rows=evidence_acquisition_rows,
        market_anomaly_rows=market_anomaly_rows,
        official_exchange_candidate_rows=official_exchange_candidate_rows,
        scheduled_catalyst_rows=scheduled_catalyst_rows,
        unlock_candidate_rows=unlock_candidate_rows,
        derivatives_state_rows=derivatives_state_rows,
        fade_review_candidate_rows=fade_review_candidate_rows,
        requested_profile=requested_profile,
        artifact_namespace=artifact_namespace,
        run_ledger_path=run_ledger_path,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
    )
    context = _prepare_daily_brief_context(
        rows,
        watchlist_entries=watchlist_entries,
        router_result=router_result,
        notification_runs=notification_runs,
        requested_profile=requested_profile,
        run_ledger_path=run_ledger_path,
    )
    lines = _daily_brief_header_lines(
        generated=generated,
        clock_status=clock_status or {},
        requested_profile=requested_profile,
        artifact_namespace=artifact_namespace,
        run_mode=run_mode,
        run_ledger_path=run_ledger_path,
        alert_store_path=alert_store_path,
        rows=rows,
        context=context,
        card_paths=card_paths,
        provider_health_rows=provider_health_rows,
    )
    lines.extend(_daily_brief_opportunity_lines(rows, context))
    lines.extend(decision_model_daily_brief_lines(
        rows.stored_core_rows,
        include_diagnostics=include_diagnostics,
    ))
    lines.extend(_daily_brief_source_intro_lines(
        rows=rows,
        context=context,
        requested_profile=requested_profile,
        provider_health_rows=provider_health_rows,
    ))
    _append_system_health_detail_sections(
        lines,
        rows=rows,
        context=context,
        provider_health_rows=provider_health_rows,
        requested_profile=requested_profile,
        include_api_artifacts=include_api_artifacts,
    )
    _append_hypothesis_sections(lines, rows=rows, context=context)
    _append_recent_activity_sections(lines, rows=rows, context=context, include_diagnostics=include_diagnostics)
    _append_impact_quality_sections(lines, rows=rows, context=context, include_diagnostics=include_diagnostics)
    _append_notification_digest_sections(lines, context=context, generated=generated, run_ledger_path=run_ledger_path)
    _append_watchlist_sections(lines, context)
    _append_card_sections(lines, context=context, card_paths=card_paths, include_diagnostics=include_diagnostics)
    _append_tail_sections(
        lines,
        rows=rows,
        context=context,
        requested_profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_api_artifacts=include_api_artifacts,
        include_diagnostics=include_diagnostics,
    )
    return _strip_sensitive("\n".join(lines).rstrip() + "\n")


def write_daily_brief(
    path: str | Path,
    *,
    markdown: str,
    card_paths: Iterable[Path] = (),
) -> EventAlphaDailyBriefResult:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    clean = _strip_sensitive(markdown)
    target.write_text(clean, encoding="utf-8")
    return EventAlphaDailyBriefResult(path=target, markdown=clean, cards=tuple(Path(p) for p in card_paths))


def format_daily_brief_result(result: EventAlphaDailyBriefResult) -> str:
    return "\n".join([
        "=" * 76,
        "EVENT ALPHA DAILY BRIEF WRITTEN (research artifact only)",
        "=" * 76,
        f"path: {event_artifact_paths.artifact_display_path(result.path)}",
        f"cards_linked: {len(result.cards)}",
        "No live RSI alerts, paper trades, live DB rows, or execution were changed.",
    ])


__all__ = (
    'build_daily_brief',
    'write_daily_brief',
    'format_daily_brief_result',
)
