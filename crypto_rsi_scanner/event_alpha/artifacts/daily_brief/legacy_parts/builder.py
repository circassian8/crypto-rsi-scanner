"""Builder helpers for legacy daily brief."""

from __future__ import annotations

from .runtime import *

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
    include_legacy_artifacts: bool = False,
    include_diagnostics: bool = False,
    clock_status: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> str:
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    raw_runs = [dict(row) for row in run_rows if isinstance(row, Mapping)]
    legacy_available = any(event_alpha_artifacts.is_legacy_row(row) for row in raw_runs)
    runs = event_alpha_artifacts.filter_artifact_rows(
        raw_runs,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    alerts = event_alpha_artifacts.filter_artifact_rows(
        alert_rows,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    feedback = event_alpha_artifacts.filter_artifact_rows(
        feedback_rows,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    missed = event_alpha_artifacts.filter_artifact_rows(
        missed_rows,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    stored_core_rows = event_alpha_artifacts.filter_artifact_rows(
        [dict(row) for row in core_opportunity_rows if isinstance(row, Mapping)],
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    hypotheses = event_alpha_artifacts.filter_artifact_rows(
        [dict(row) for row in hypothesis_rows if isinstance(row, Mapping)],
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    incidents = event_alpha_artifacts.filter_artifact_rows(
        [dict(row) for row in incident_rows if isinstance(row, Mapping)],
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    acquisition_rows = event_alpha_artifacts.filter_artifact_rows(
        [dict(row) for row in evidence_acquisition_rows if isinstance(row, Mapping)],
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    raw_market_anomalies = (
        [dict(row) for row in market_anomaly_rows if isinstance(row, Mapping)]
        if market_anomaly_rows is not None
        else list(event_market_anomaly_scanner.load_market_anomaly_rows(Path(run_ledger_path).parent if run_ledger_path else None))
    )
    market_anomalies = event_alpha_artifacts.filter_artifact_rows(
        raw_market_anomalies,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    raw_official_exchange_candidates = (
        [dict(row) for row in official_exchange_candidate_rows if isinstance(row, Mapping)]
        if official_exchange_candidate_rows is not None
        else list(event_official_exchange.load_official_listing_candidates(Path(run_ledger_path).parent if run_ledger_path else None))
    )
    official_exchange_candidates = event_alpha_artifacts.filter_artifact_rows(
        raw_official_exchange_candidates,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    raw_scheduled_catalysts = (
        [dict(row) for row in scheduled_catalyst_rows if isinstance(row, Mapping)]
        if scheduled_catalyst_rows is not None
        else list(event_scheduled_catalysts.load_scheduled_catalysts(Path(run_ledger_path).parent if run_ledger_path else None))
    )
    scheduled_catalysts = event_alpha_artifacts.filter_artifact_rows(
        raw_scheduled_catalysts,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    raw_unlock_candidates = (
        [dict(row) for row in unlock_candidate_rows if isinstance(row, Mapping)]
        if unlock_candidate_rows is not None
        else list(event_scheduled_catalysts.load_unlock_candidates(Path(run_ledger_path).parent if run_ledger_path else None))
    )
    unlock_candidates = event_alpha_artifacts.filter_artifact_rows(
        raw_unlock_candidates,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    raw_derivatives_state = (
        [dict(row) for row in derivatives_state_rows if isinstance(row, Mapping)]
        if derivatives_state_rows is not None
        else list(event_derivatives_crowding.load_derivatives_state(Path(run_ledger_path).parent if run_ledger_path else None))
    )
    derivatives_state = event_alpha_artifacts.filter_artifact_rows(
        raw_derivatives_state,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    raw_fade_review_candidates = (
        [dict(row) for row in fade_review_candidate_rows if isinstance(row, Mapping)]
        if fade_review_candidate_rows is not None
        else list(event_derivatives_crowding.load_fade_review_candidates(Path(run_ledger_path).parent if run_ledger_path else None))
    )
    fade_review_candidates = event_alpha_artifacts.filter_artifact_rows(
        raw_fade_review_candidates,
        profile=requested_profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )
    entries = list(watchlist_entries)
    decisions = list(router_result.decisions if router_result else ())
    alertable = [decision for decision in list(router_result.alertable_decisions if router_result else ()) if event_alpha_router.alertable_after_quality_gate(decision)]
    if stored_core_rows:
        core_opportunities = event_core_opportunity_store.core_opportunities_from_rows(stored_core_rows)
        core_source_rows: list[Any] = stored_core_rows
    else:
        core_opportunities = event_core_opportunities.aggregate_core_opportunities([*decisions, *hypotheses])
        core_source_rows = [*(decision.entry for decision in decisions), *hypotheses]
    core_sections = _core_opportunity_sections(core_opportunities)
    lane_sections = _core_opportunity_lane_sections(core_opportunities)
    source_coverage_report_path = (
        Path(run_ledger_path).parent / "event_alpha_source_coverage.md"
        if run_ledger_path
        else None
    )
    core_alertable_count = _core_alertable_count(core_opportunities)
    diagnostic_core_rows = sum(item.diagnostic_row_count for item in core_opportunities)
    diagnostic_control_rows = sum(item.source_noise_control_count for item in core_opportunities)
    diagnostic_capped_rows = sum(item.quality_capped_supporting_rows for item in core_opportunities)
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
    high_priority_core_asset_keys = {
        event_core_opportunities.asset_key_for_opportunity(item)
        for item in core_sections["strong"]
    }
    near_misses = event_near_miss.detect_near_miss_rows(
        core_source_rows,
        route_decisions=decisions,
    )
    _, raw_upgrade_candidates = event_near_miss.split_near_miss_candidates(near_misses)
    near_miss_candidates = tuple(
        item for item in near_misses
        if not event_near_miss.is_upgrade_candidate(item)
        and event_core_opportunities.incident_asset_key_for_values(
            item.incident_id,
            item.coin_id,
            item.symbol,
        ) not in promoted_core_asset_keys
        and event_core_opportunities.asset_key_for_values(item.coin_id, item.symbol) not in promoted_core_assets
    )
    upgrade_candidates = tuple(
        item for item in raw_upgrade_candidates
        if event_core_opportunities.incident_asset_key_for_values(
            item.incident_id,
            item.coin_id,
            item.symbol,
        ) not in {
            event_core_opportunities.incident_asset_key_for_opportunity(core)
            for core in core_sections["strong"]
        }
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
    latest = event_alpha_run_ledger.latest_run(runs, requested_profile) or {}
    selected_profile = str(latest.get("profile") or "default") if latest else "none"
    selected_namespace = str(latest.get("artifact_namespace") or "legacy") if latest else "none"
    requested = str(requested_profile or "latest").strip() or "latest"
    profile_match = (
        "n/a"
        if not latest or requested_profile is None
        else str(selected_profile == str(requested_profile)).lower()
    )
    mismatch_warning = event_alpha_run_ledger.run_profile_mismatch_warning(requested_profile, latest)
    lines = [
        "# Event Alpha Daily Brief",
        "",
        f"Generated at: {generated.isoformat()}",
        _format_clock_status(clock_status or {}),
        *_format_clock_warning_lines(clock_status or {}),
        f"Requested profile: {requested}",
        f"Artifact namespace: {artifact_namespace or 'any'}",
        f"Run mode: {run_mode or 'unknown'}",
        f"Run ledger path: {event_alpha_artifacts.safe_path_label(run_ledger_path) if run_ledger_path else 'unknown'}",
        f"Alert store path: {event_alpha_artifacts.safe_path_label(alert_store_path) if alert_store_path else 'unknown'}",
        f"Selected run profile: {selected_profile}",
        f"Selected run namespace: {selected_namespace}",
        f"Profile match: {profile_match}",
        "",
        "Research-only. Not a trade signal, paper trade, live RSI signal, or execution.",
        "Canonical operator view: Core Opportunities sections above. Diagnostics appendix contains raw/supporting/control rows and may repeat assets for debugging.",
        "",
        "## Executive Summary",
        f"- Core opportunities: {len(core_opportunities)} "
        f"(canonical_store_rows={len(stored_core_rows)}, "
        f"high_priority={len(core_sections['strong'])}, digest={len(core_sections['digest'])}, "
        f"watchlist={len(core_sections['watchlist'])}, near_miss={len(near_miss_candidates)}, "
        f"upgrade={len(upgrade_candidates)}, "
        f"local_or_capped={len(local_core_rows)})",
        f"- Alertable routed decisions: {core_alertable_count}",
        f"- Near-miss candidates: {len(near_miss_candidates)}",
        f"- Upgrade candidates: {len(upgrade_candidates)}",
        "- Opportunity lanes: "
        + ", ".join(
            f"{name}={len(items)}"
            for name, items in lane_sections.items()
            if name != "diagnostics"
        ),
        "",
        "## Burn-In Readiness",
        *_burn_in_readiness_lines(
            latest=latest,
            core_opportunities=core_opportunities,
            card_paths=card_paths,
            evidence_acquisition_rows=acquisition_rows,
            provider_health_rows=provider_health_rows or {},
            requested_profile=requested_profile,
        ),
        "",
        "## Opportunity Lanes",
        "Research-only lane classification. Not a trade signal.",
        "",
        "### Early Long Research",
        *_core_opportunity_lines(lane_sections["early"], limit=8),
        "",
        "### Confirmed Long Research",
        *_core_opportunity_lines(lane_sections["confirmed"], limit=8),
        "",
        "### Fade / Short-Review",
        *_core_opportunity_lines(lane_sections["fade"], limit=8),
        "",
        "### Risk Only",
        *_core_opportunity_lines(lane_sections["risk"], limit=8),
        "",
        "### Unconfirmed Research",
        *_core_opportunity_lines(lane_sections["unconfirmed"], limit=8),
        "",
        "## High-Priority Core Opportunities",
        *_core_opportunity_lines(core_sections["strong"], limit=8),
        "",
        "## Validated Digest Core Opportunities",
        *_core_opportunity_lines(core_sections["digest"], limit=8),
        "",
        "## Watchlist Core Opportunities",
        *_core_opportunity_lines(core_sections["watchlist"], limit=8),
        "",
        "## Near-Miss Candidates",
        *_near_miss_daily_lines(near_miss_candidates, limit=8),
        "",
        "## Upgrade Candidates",
        *_near_miss_daily_lines(upgrade_candidates, limit=8),
        "",
        "## Quality-Capped / Local-Only Candidates",
        *_core_opportunity_lines(local_core_rows, limit=8),
        "",
        "## Live Confirmation Gated Candidates",
        *_live_confirmation_gated_core_lines(core_opportunities, limit=8),
        "",
        "## Top Market Anomalies Needing Catalyst Search",
        *_market_anomaly_daily_lines(market_anomalies, limit=10),
        "",
        "## Fresh Official Exchange Catalysts",
        *_official_exchange_daily_lines(official_exchange_candidates, limit=10),
        "",
        "## Upcoming Scheduled Catalysts",
        *_scheduled_catalyst_daily_lines(scheduled_catalysts, limit=10),
        "",
        "## Unlock / Supply Risk",
        *_unlock_risk_daily_lines(unlock_candidates, limit=10),
        "",
        "## Derivatives Crowding / Fade-Review Research",
        *_derivatives_fade_review_daily_lines(fade_review_candidates, derivatives_state, limit=10),
        "",
        "## Catalyst Calendar Gaps",
        *_calendar_gap_daily_lines([*scheduled_catalysts, *unlock_candidates], limit=10),
        "",
        "## Near-Term Events Needing Market Watch",
        *_scheduled_market_watch_lines([*scheduled_catalysts, *unlock_candidates], limit=10),
        "",
        "## Canonical Incidents",
        *_canonical_incident_lines(incidents),
        "",
        "## System Health",
        *_system_health_summary_lines(latest),
        "",
        "## Source Coverage / Evidence Acquisition",
        *_source_coverage_summary_lines(
            [*core_source_rows, *alerts],
            near_miss_candidates,
            upgrade_candidates,
            acquisition_rows=acquisition_rows,
            source_coverage_report_path=source_coverage_report_path,
        ),
        "",
        "### Provider Health by Source Pack",
        *_provider_health_by_pack_lines(
            provider_health_rows or {},
            source_coverage_report_path=source_coverage_report_path,
        ),
        "",
        "### Evidence Acquisition Results",
        *_evidence_acquisition_result_lines(
            (*near_miss_candidates, *upgrade_candidates),
            acquisition_rows=acquisition_rows,
            core_opportunities=core_opportunities,
            limit=8,
        ),
        "",
        "### Candidates Blocked by Source Coverage",
        *_coverage_blocked_candidate_lines((*near_miss_candidates, *upgrade_candidates), limit=8),
        "",
        "## Market Freshness Readiness",
        *_market_freshness_readiness_lines([*core_source_rows, *alerts], requested_profile=requested_profile),
        "",
        "## Diagnostics Appendix",
        "### Diagnostic Appendix: Diagnostics / Source-Noise / Controls",
        (
            "- Hidden from main opportunity sections by default: "
            f"diagnostic_rows={diagnostic_core_rows}, "
            f"source_noise_controls={diagnostic_control_rows}, "
            f"quality_capped_support={diagnostic_capped_rows}, "
            f"diagnostic_lane_cores={len(lane_sections['diagnostics'])}"
        ),
        (
            "- Pass include_diagnostics in local tooling to inspect collapsed controls."
            if diagnostic_core_rows or diagnostic_control_rows or diagnostic_capped_rows
            else "- None."
        ),
        "",
        "### System Health / Providers / Budget",
    ]
    if mismatch_warning:
        lines.append(f"- Profile warning: {mismatch_warning}")
    if requested_profile and not runs and legacy_available and not include_legacy_artifacts:
        lines.append("- Profile warning: only legacy/default run rows were available; they were ignored for this profile brief")
    if latest:
        run_alertable = int(latest.get("alertable") or 0)
        alertable_text = str(core_alertable_count)
        if run_alertable != core_alertable_count:
            alertable_text = f"{core_alertable_count} (run_ledger_pre_core={run_alertable})"
        lines.extend([
            f"- Run: {latest.get('run_id') or 'unknown'}",
            f"- Profile: {latest.get('profile') or 'default'}",
            f"- Success: {str(bool(latest.get('success'))).lower()}",
            f"- Raw/events/candidates/alerts: {int(latest.get('raw_events') or 0)} / {int(latest.get('candidates') or 0)} / {int(latest.get('alerts') or 0)}",
            f"- Routed/alertable/sent: {int(latest.get('routed') or 0)} / {alertable_text} / {str(bool(latest.get('sent'))).lower()}",
            f"- Sent/delivered/block: {int(latest.get('send_items_delivered') or 0)}/{int(latest.get('send_items_attempted') or 0)} / {latest.get('send_block_reason') or 'none'}",
            "- Catalyst frames analyzed/validated/disagreements/unresolved: "
            f"{int(latest.get('catalyst_frames_analyzed') or latest.get('catalyst_frame_rows') or 0)} / "
            f"{int(latest.get('catalyst_frame_validations') or latest.get('catalyst_frame_validations_applied') or 0)} / "
            f"{int(latest.get('catalyst_frame_disagreements') or 0)} / "
            f"{int(latest.get('catalyst_frame_unresolved') or 0)}",
            f"- Catalyst frame rows skipped/missing: {int(latest.get('catalyst_frame_rows_skipped') or 0)}",
        ])
        catalyst_frame_skip = latest.get("catalyst_frame_skip_reasons") or {}
        if isinstance(catalyst_frame_skip, Mapping) and catalyst_frame_skip:
            lines.append(
                "- Catalyst frame skip reasons: "
                + ", ".join(f"{key}={int(value or 0)}" for key, value in sorted(catalyst_frame_skip.items()))
            )
        warnings = [str(w) for w in latest.get("warnings") or [] if str(w)]
        if warnings:
            lines.append("- Warnings: " + "; ".join(warnings[:6]))
    else:
        lines.append("- No run ledger rows found.")
    latest_notification = _latest_notification_run(notification_runs)
    if latest_notification is not None:
        lines.append(
            "- Notify lock/deliveries: "
            f"lock_acquired={str(bool(latest_notification.get('lock_acquired'))).lower()} "
            f"skipped_active_lock={str(bool(latest_notification.get('skipped_due_to_active_lock'))).lower()} "
            f"deliveries={int(latest_notification.get('deliveries_delivered') or 0)}d/"
            f"{int(latest_notification.get('deliveries_partial_delivered') or 0)}partial/"
            f"{int(latest_notification.get('deliveries_failed') or 0)}f/"
            f"{int(latest_notification.get('deliveries_skipped_duplicate') or 0)}dup/"
            f"{int(latest_notification.get('deliveries_skipped_in_flight') or 0)}flight/"
            f"{int(latest_notification.get('deliveries_blocked') or 0)}blocked"
        )
        if event_alpha_notification_runs.row_has_delivery_failures(latest_notification):
            lines.append(
                f"- Notify delivery failures: {int(latest_notification.get('deliveries_failed') or 0)} "
                "failed delivery row(s) — run --event-alpha-notification-deliveries-report"
            )
    lines.extend(["", "#### Provider Health"])
    lines.extend(_provider_health_lines(provider_health_rows or {}))
    lines.extend(["", "#### LLM Budget"])
    lines.extend(_llm_budget_lines(latest))
    lines.extend(["", "### Impact Hypotheses"])
    if latest:
        lines.append(
            f"- Generated/validated/promoted: {int(latest.get('impact_hypotheses') or 0)} / "
            f"{int(latest.get('hypotheses_validated') or 0)} / {int(latest.get('hypothesis_promotions') or 0)}"
        )
        lines.append(
            f"- Validation queries/results: {int(latest.get('hypothesis_search_queries') or 0)} / "
            f"{int(latest.get('hypothesis_search_results') or 0)}"
        )
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
    else:
        lines.append("- No run row available.")
    if hypotheses:
        status_counts = _field_counts(hypotheses, "status")
        stage_counts = _field_counts(hypotheses, "validation_stage")
        category_counts = _field_counts(hypotheses, "impact_category")
        schema_counts = _field_counts(hypotheses, "schema_version")
        why_counts = _multi_field_counts(hypotheses, "why_not_promoted")
        legacy_count = sum(
            1 for row in hypotheses
            if not str(row.get("schema_version") or "").startswith("event_impact_hypothesis_store_")
            or any(
                field not in row
                for field in ("validation_stage", "hypothesis_score", "external_entities", "crypto_candidate_assets")
            )
        )
        lines.append("- Stored rows: " + str(len(hypotheses)))
        lines.append("- Stored schema versions: " + _format_counts(schema_counts) + f" (legacy={legacy_count})")
        lines.append("- Stored statuses: " + _format_counts(status_counts))
        lines.append("- Stored validation stages: " + _format_counts(stage_counts))
        lines.append("- Stored categories: " + _format_counts(category_counts))
        lines.append("- Why not promoted: " + _format_counts(why_counts))
        pending = [
            row for row in hypotheses
            if str(row.get("status") or "") in {"validation_search_pending", "hypothesis"}
        ]
        validated = [
            row for row in hypotheses
            if str(row.get("status") or "") in {"validation_evidence_found", "validated"}
        ]
        rejected = [
            row for row in hypotheses
            if str(row.get("status") or "") == "rejected" or row.get("rejection_reasons")
        ]
        lines.append("- Validated stored hypotheses: " + (_brief_hypothesis_labels(validated[:3]) or "none"))
        lines.append("- Pending stored hypotheses: " + (_brief_hypothesis_labels(pending[:3]) or "none"))
        lines.append("- Top rejected hypotheses: " + (_brief_hypothesis_labels(rejected[:3]) or "none"))
        ranked = sorted(
            hypotheses,
            key=lambda row: _float(row.get("hypothesis_score") or _float(row.get("confidence")) * 100),
            reverse=True,
        )
        lines.append("- Top hypothesis scores: " + (_brief_hypothesis_labels(ranked[:3]) or "none"))
        rejected_samples = sum(
            1
            for row in hypotheses
            for sample in (row.get("rejected_validation_samples") or [])
            if isinstance(sample, Mapping) and (not bool(sample.get("accepted")) or sample.get("rejection_reason"))
        )
        if rejected_samples:
            lines.append(f"- Rejected validation evidence samples: {rejected_samples}")
            reason_counts: dict[str, int] = {}
            titles: list[str] = []
            for row in hypotheses:
                for sample in row.get("rejected_validation_samples") or []:
                    if not isinstance(sample, Mapping):
                        continue
                    if bool(sample.get("accepted")) and not sample.get("rejection_reason"):
                        continue
                    reason = str(sample.get("rejection_reason") or "unknown")
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1
                    title = str(sample.get("result_title") or "").strip()
                    if title and title not in titles:
                        titles.append(title)
            lines.append("- Rejected evidence reasons: " + _format_counts(reason_counts))
            if titles:
                lines.append("- Rejected evidence examples: " + " | ".join(titles[:3]))
    elif latest and int(latest.get("impact_hypotheses") or 0) > 0:
        lines.append("- Stored rows: none loaded for this profile; inspect --event-impact-hypotheses-report.")
    lines.extend(["", "### Catalyst Search Skip Reasons"])
    if latest:
        skip_reasons = latest.get("catalyst_search_skip_reasons") or {}
        if isinstance(skip_reasons, Mapping) and skip_reasons:
            for key, value in sorted(skip_reasons.items()):
                lines.append(f"- {key}: {int(value or 0)}")
        elif int(latest.get("market_anomalies") or 0) > 0 and int(latest.get("catalyst_queries") or 0) == 0:
            lines.append("- unknown: market anomalies were present but no catalyst queries were generated.")
        else:
            lines.append("- None.")
    else:
        lines.append("- No run row available.")
    lines.extend(["", "### New Since Last Run"])
    lines.extend(_new_since_last_run_lines(runs))
    lines.extend(["", "### Watchlist Got Hotter"])
    lines.extend(_watchlist_hotter_lines(entries))
    lines.extend(["", "### Alertable Decisions"])
    if core_alertable_count > 0:
        lines.append(f"- {core_alertable_count} canonical alertable core opportunity/opportunities; see core opportunity sections above.")
    elif alertable and include_diagnostics:
        lines.append("- Raw pre-policy route attempts only; these are diagnostic rows and are not operator alert truth.")
        for decision in alertable[:10]:
            entry = decision.entry
            lines.append(f"- diagnostic {event_alpha_router.final_route_value(decision)}: {entry.symbol}/{entry.coin_id} state={event_watchlist.final_state_value(entry)} score={entry.latest_score} reason={decision.reason}")
    else:
        lines.append("- None.")
    lines.extend(["", "### Validated Impact Hypothesis Routing"])
    alertable_hypotheses = [
        decision for decision in decisions
        if decision.entry.relationship_type == "impact_hypothesis" and event_alpha_router.alertable_after_quality_gate(decision)
    ]
    impact_path_validated_hypotheses = [
        decision for decision in decisions
        if (
            decision.entry.relationship_type == "impact_hypothesis"
            and str((decision.entry.latest_score_components or {}).get("validation_stage") or "") in {
                "impact_path_validated",
                "market_confirmed",
                "promoted_to_radar",
            }
        )
    ]
    local_validated_hypotheses = [
        decision for decision in decisions
        if (
            decision.entry.relationship_type == "impact_hypothesis"
            and not event_alpha_router.alertable_after_quality_gate(decision)
            and event_watchlist.final_state_value(decision.entry) == event_watchlist.EventWatchlistState.RADAR.value
            and decision.entry.symbol.upper() != "SECTOR"
        )
    ]
    weak_local_hypotheses = [
        decision for decision in local_validated_hypotheses
        if (
            str((decision.entry.latest_score_components or {}).get("validation_stage") or "") == "catalyst_link_validated"
            or str((decision.entry.latest_score_components or {}).get("impact_path_strength") or "") in {"weak", "none"}
            or bool((decision.entry.latest_score_components or {}).get("why_digest_ineligible"))
        )
    ]
    generic_blocked_hypotheses = [
        decision for decision in local_validated_hypotheses
        if str((decision.entry.latest_score_components or {}).get("impact_path_type") or "") == "generic_cooccurrence_only"
    ]
    strong_opportunity_hypotheses = [
        decision for decision in decisions
        if decision.entry.relationship_type == "impact_hypothesis"
        and str((decision.entry.latest_score_components or {}).get("opportunity_level") or "") in {
            "watchlist",
            "high_priority",
        }
    ]
    market_unconfirmed_hypotheses = [
        decision for decision in local_validated_hypotheses
        if str((decision.entry.latest_score_components or {}).get("market_confirmation_level") or "") in {
            "",
            "none",
            "weak",
        }
        and str((decision.entry.latest_score_components or {}).get("opportunity_level") or "") in {
            "local_only",
            "exploratory",
            "",
        }
    ]
    exploratory_sector_hypotheses = [
        entry for entry in entries
        if entry.relationship_type == "impact_hypothesis"
        and event_watchlist.final_state_value(entry) == event_watchlist.EventWatchlistState.HYPOTHESIS.value
    ]
    rejected_hypotheses = [
        row for row in hypotheses
        if str(row.get("status") or "") == "rejected" or row.get("why_not_promoted") or row.get("rejection_reasons")
    ]
    lines.append("- Strong opportunity candidates: " + (_brief_core_opportunities(core_opportunities, section="strong", limit=5) or "none"))
    digest_candidates = _brief_core_opportunities(core_opportunities, section="digest", limit=5)
    if not digest_candidates and include_diagnostics:
        digest_candidates = (
            "raw diagnostic only: "
            + (_brief_decisions(alertable_hypotheses[:5]) or _brief_decisions(impact_path_validated_hypotheses[:5]) or "none")
        )
    lines.append("- Impact-path validated digest candidates: " + (digest_candidates or "none"))
    lines.append("- Validated but market-unconfirmed: " + (_brief_decisions(market_unconfirmed_hypotheses[:5]) or "none"))
    lines.append("- Weak validated local-only hypotheses: " + (_brief_decisions(weak_local_hypotheses[:5]) or "none"))
    lines.append("- Generic co-occurrence blocked: " + (_brief_decisions(generic_blocked_hypotheses[:5]) or "none"))
    lines.append("- Sector hypotheses awaiting validation: " + (_brief_entries(exploratory_sector_hypotheses[:5]) or "none"))
    lines.append("- Rejected/why-not-promoted hypotheses: " + (_brief_hypothesis_labels(rejected_hypotheses[:5]) or "none"))
    lines.append("- Market confirmation by playbook: " + _market_confirmation_by_playbook(decisions))
    lines.append("- Top upgrade candidates: " + (_upgrade_candidate_line(decisions) or "none"))
    lines.append("- Top downgrade risks: " + (_downgrade_risk_line(decisions) or "none"))
    lines.extend(["", "### Near-Miss Diagnostics"])
    lines.extend(_near_miss_diagnostic_lines(near_miss_candidates, limit=8))
    lines.extend(["", "### Upgrade Candidate Diagnostics"])
    lines.extend(_near_miss_diagnostic_lines(upgrade_candidates, limit=8))
    lines.extend(["", "### Signal Quality Summary"])
    lines.append("- Opportunity Verdict Distribution: " + _quality_decision_counts(decisions, "opportunity_level"))
    lines.append("- Impact Path Distribution: " + _quality_decision_counts(decisions, "impact_path_type"))
    lines.append("- Candidate Role Distribution: " + _quality_decision_counts(decisions, "candidate_role"))
    lines.append("- Incident Archetype Distribution: " + _quality_decision_counts(decisions, "event_archetype"))
    lines.append("- Cause Status Distribution: " + _quality_decision_counts(decisions, "cause_status"))
    lines.append("- Market Reaction Confirmed: " + _quality_decision_counts(decisions, "market_reaction_confirmed"))
    lines.append("- Causal Mechanism Confirmed: " + _quality_decision_counts(decisions, "causal_mechanism_confirmed"))
    lines.append("- Evidence Specificity Distribution: " + _quality_decision_counts(decisions, "evidence_specificity"))
    lines.append("- Market Confirmation Distribution: " + _quality_decision_counts(decisions, "market_confirmation_level"))
    lines.append("- Market Context Freshness: " + _quality_decision_counts(decisions, "market_context_freshness_status"))
    lines.append("- Top Upgrade Candidates: " + (_upgrade_candidate_line(decisions) or "none"))
    lines.append("- Top Downgrade Risks: " + (_downgrade_risk_line(decisions) or "none"))
    lines.append("- Candidate Discovery Funnel: " + _candidate_discovery_funnel_line(hypotheses))
    lines.append("- Feedback by Impact Path: " + _feedback_by_impact_path(alerts, feedback))
    lines.extend(["", "### Quality Gate Downgrades"])
    downgraded = _quality_gate_downgrades(decisions)
    lines.append("- Downgraded items: " + (_brief_decisions(downgraded[:5]) or "none"))
    lines.append("- Top blocked route attempts: " + (_blocked_route_attempts_line(downgraded) or "none"))
    lines.append("- Reason counts: " + _quality_gate_reason_counts(downgraded))
    lines.extend(["", "### Legacy Quality Conflicts"])
    conflicts = _legacy_quality_conflicts(alerts)
    lines.extend(_legacy_quality_conflict_lines(conflicts[:8]))
    research_review = event_alpha_notifications.select_research_review_candidates(
        decisions,
        cfg=event_alpha_notifications.EventAlphaNotificationConfig(
            research_review_digest_enabled=True,
            research_review_digest_max_items=5,
            research_review_digest_min_score=60,
            research_review_digest_include_local_only=False,
        ),
        now=generated,
    )
    research_review = tuple(
        item for item in research_review
        if event_core_opportunities.incident_asset_key_for_values(
            getattr(item.decision.entry, "incident_id", None),
            item.decision.entry.coin_id,
            item.decision.entry.symbol,
        ) not in promoted_core_asset_keys
        and event_core_opportunities.asset_key_for_values(item.decision.entry.coin_id, item.decision.entry.symbol)
        not in promoted_core_assets
    )
    lines.extend(["", "### Research Review Digest"])
    review_due = _lane_count(latest_notification, "lane_counts_due", event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST)
    review_sent = _lane_count(latest_notification, "lane_counts_sent", event_alpha_notifications.LANE_RESEARCH_REVIEW_DIGEST)
    if latest:
        lines.append(
            "- Run ledger: "
            f"research_review_digest_enabled={str(bool(latest.get('research_review_digest_enabled'))).lower()} "
            f"research_review_digest_candidates={int(latest.get('research_review_digest_candidates') or 0)} "
            f"research_review_digest_would_send={int(latest.get('research_review_digest_would_send') or 0)} "
            f"research_review_digest_block={latest.get('research_review_digest_block_reason') or 'none'}"
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
    exploratory = event_alpha_notifications.select_exploratory_candidates(
        decisions,
        cfg=event_alpha_notifications.EventAlphaNotificationConfig(
            exploratory_digest_enabled=True,
            exploratory_digest_max_items=5,
        ),
        now=generated,
    )
    exploratory = tuple(
        item for item in exploratory
        if event_core_opportunities.incident_asset_key_for_values(
            getattr(item.decision.entry, "incident_id", None),
            item.decision.entry.coin_id,
            item.decision.entry.symbol,
        ) not in promoted_core_asset_keys
        and event_core_opportunities.asset_key_for_values(item.decision.entry.coin_id, item.decision.entry.symbol)
        not in promoted_core_assets
    )
    lines.extend(["", "### Exploratory Digest"])
    exploratory_due = _lane_count(latest_notification, "lane_counts_due", event_alpha_notifications.LANE_EXPLORATORY_DIGEST)
    exploratory_sent = _lane_count(latest_notification, "lane_counts_sent", event_alpha_notifications.LANE_EXPLORATORY_DIGEST)
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
    lines.extend(["", "### Active Watchlist"])
    active = [
        entry for entry in entries
        if not event_watchlist.state_is_quality_capped(entry)
        and event_watchlist.final_state_value(entry) in {
            event_watchlist.EventWatchlistState.RADAR.value,
            event_watchlist.EventWatchlistState.WATCHLIST.value,
            event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            event_watchlist.EventWatchlistState.EVENT_PASSED.value,
            event_watchlist.EventWatchlistState.ARMED.value,
        }
    ]
    active = _dedupe_watchlist_entries(active)
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
    capped = _dedupe_watchlist_entries([entry for entry in entries if event_watchlist.state_is_quality_capped(entry)])
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
    lines.extend(["", "### Research Cards"])
    cards = [Path(path) for path in card_paths]
    if cards:
        grouped_cards = _card_groups_for_daily_brief(cards)
        for group_name in event_research_cards.CARD_INDEX_GROUPS:
            paths = grouped_cards.get(group_name, [])
            if group_name == "Diagnostic / Source-Noise / Control Cards" and not include_diagnostics:
                lines.append(f"#### {group_name}")
                hidden_count = len(paths)
                lines.append(
                    f"- Hidden from main card list by default: cards={hidden_count}, "
                    f"diagnostics={diagnostic_core_rows}, quality_capped_support={diagnostic_capped_rows}"
                )
                continue
            lines.append(f"#### {group_name}")
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
    else:
        lines.append("- No cards written for this brief.")
    lines.extend(["", "### Missed Opportunities"])
    if missed:
        for row in sorted(missed, key=lambda item: abs(_float(item.get("return_pct"))), reverse=True)[:5]:
            lines.append(f"- {row.get('symbol') or row.get('coin_id')}: {row.get('move_window')} {row.get('return_pct')} stage={row.get('failure_stage')}")
    else:
        lines.append("- No missed-opportunity rows found.")
    lines.extend(["", "### Source Reliability"])
    lines.append(_compact(event_source_reliability.format_source_reliability_report(
        alerts,
        feedback_rows=feedback,
        missed_rows=missed,
        run_rows=runs[:10],
    )))
    lines.extend(["", "### Calibration Recommendations"])
    lines.append(_compact(event_alpha_calibration.format_calibration_report(
        alerts,
        feedback_rows=feedback,
        missed_rows=missed,
    )))
    lines.extend(["", "### Top Suppression Reasons"])
    lines.extend(_suppression_lines(decisions, entries))
    if core_alertable_count <= 0:
        lines.extend(["", "### Why No Alerts"])
        lines.append(_compact(event_alpha_explain.format_last_run_explanation(
            runs,
            alert_rows=alerts,
            requested_profile=requested_profile,
            artifact_namespace=artifact_namespace,
            include_test_artifacts=include_test_artifacts,
            include_legacy_artifacts=include_legacy_artifacts,
        )))
    elif alertable and include_diagnostics:
        lines.extend(["", "### Raw Pre-Policy Route Attempts / Diagnostics"])
        lines.append("- These rows were generated before canonical core/live-confirmation policy and are not proof of sent alerts.")
        for decision in alertable[:8]:
            lines.append(f"- {decision.entry.symbol}/{decision.entry.coin_id}: {decision.reason}")
    else:
        lines.extend(["", "### Why Alertable Core Routes Exist"])
        lines.append("- Canonical core opportunities passed final quality and live-confirmation gates; no raw pre-policy route text is shown by default.")
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
