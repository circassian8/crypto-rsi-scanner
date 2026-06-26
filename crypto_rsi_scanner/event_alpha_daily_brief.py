"""Daily Markdown brief for Event Alpha research artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import (
    event_alpha_calibration,
    event_alpha_alert_store,
    event_alpha_artifacts,
    event_alpha_notifications,
    event_alpha_notification_runs,
    event_alpha_explain,
    event_alpha_run_ledger,
    event_alpha_router,
    event_opportunity_verdict,
    event_research_cards,
    event_source_reliability,
    event_watchlist,
)


@dataclass(frozen=True)
class EventAlphaDailyBriefResult:
    path: Path
    markdown: str
    cards: tuple[Path, ...] = ()


def build_daily_brief(
    *,
    run_rows: Iterable[Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
    notification_runs: Iterable[Mapping[str, Any]] = (),
    hypothesis_rows: Iterable[Mapping[str, Any]] = (),
    incident_rows: Iterable[Mapping[str, Any]] = (),
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
    entries = list(watchlist_entries)
    decisions = list(router_result.decisions if router_result else ())
    alertable = [decision for decision in list(router_result.alertable_decisions if router_result else ()) if event_alpha_router.alertable_after_quality_gate(decision)]
    latest = event_alpha_run_ledger.latest_run(runs, requested_profile) or {}
    selected_profile = str(latest.get("profile") or "default") if latest else "none"
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
        f"Profile match: {profile_match}",
        "",
        "Research-only. Not a trade signal, paper trade, live RSI signal, or execution.",
        "",
        "## Last Run Health",
    ]
    if mismatch_warning:
        lines.append(f"- Profile warning: {mismatch_warning}")
    if requested_profile and not runs and legacy_available and not include_legacy_artifacts:
        lines.append("- Profile warning: only legacy/default run rows were available; they were ignored for this profile brief")
    if latest:
        lines.extend([
            f"- Run: {latest.get('run_id') or 'unknown'}",
            f"- Profile: {latest.get('profile') or 'default'}",
            f"- Success: {str(bool(latest.get('success'))).lower()}",
            f"- Raw/events/candidates/alerts: {int(latest.get('raw_events') or 0)} / {int(latest.get('candidates') or 0)} / {int(latest.get('alerts') or 0)}",
            f"- Routed/alertable/sent: {int(latest.get('routed') or 0)} / {int(latest.get('alertable') or 0)} / {str(bool(latest.get('sent'))).lower()}",
            f"- Sent/delivered/block: {int(latest.get('send_items_delivered') or 0)}/{int(latest.get('send_items_attempted') or 0)} / {latest.get('send_block_reason') or 'none'}",
        ])
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
    lines.extend(["", "## Provider Health"])
    lines.extend(_provider_health_lines(provider_health_rows or {}))
    lines.extend(["", "## LLM Budget"])
    lines.extend(_llm_budget_lines(latest))
    lines.extend(["", "## Impact Hypotheses"])
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
    lines.extend(["", "## Canonical Incidents"])
    lines.extend(_canonical_incident_lines(incidents))
    lines.extend(["", "## Catalyst Search Skip Reasons"])
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
    lines.extend(["", "## New Since Last Run"])
    lines.extend(_new_since_last_run_lines(runs))
    lines.extend(["", "## Watchlist Got Hotter"])
    lines.extend(_watchlist_hotter_lines(entries))
    lines.extend(["", "## Alertable Decisions"])
    if alertable:
        for decision in alertable[:10]:
            entry = decision.entry
            lines.append(f"- {event_alpha_router.final_route_value(decision)}: {entry.symbol}/{entry.coin_id} state={event_watchlist.final_state_value(entry)} score={entry.latest_score} reason={decision.reason}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Validated Impact Hypothesis Routing"])
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
    lines.append("- Strong opportunity candidates: " + (_brief_decisions(strong_opportunity_hypotheses[:5]) or "none"))
    lines.append("- Impact-path validated digest candidates: " + (_brief_decisions(alertable_hypotheses[:5]) or _brief_decisions(impact_path_validated_hypotheses[:5]) or "none"))
    lines.append("- Validated but market-unconfirmed: " + (_brief_decisions(market_unconfirmed_hypotheses[:5]) or "none"))
    lines.append("- Weak validated local-only hypotheses: " + (_brief_decisions(weak_local_hypotheses[:5]) or "none"))
    lines.append("- Generic co-occurrence blocked: " + (_brief_decisions(generic_blocked_hypotheses[:5]) or "none"))
    lines.append("- Sector hypotheses awaiting validation: " + (_brief_entries(exploratory_sector_hypotheses[:5]) or "none"))
    lines.append("- Rejected/why-not-promoted hypotheses: " + (_brief_hypothesis_labels(rejected_hypotheses[:5]) or "none"))
    lines.append("- Market confirmation by playbook: " + _market_confirmation_by_playbook(decisions))
    lines.append("- Top upgrade candidates: " + (_upgrade_candidate_line(decisions) or "none"))
    lines.append("- Top downgrade risks: " + (_downgrade_risk_line(decisions) or "none"))
    lines.extend(["", "## Signal Quality Summary"])
    lines.append("- Opportunity Verdict Distribution: " + _quality_decision_counts(decisions, "opportunity_level"))
    lines.append("- Impact Path Distribution: " + _quality_decision_counts(decisions, "impact_path_type"))
    lines.append("- Candidate Role Distribution: " + _quality_decision_counts(decisions, "candidate_role"))
    lines.append("- Incident Archetype Distribution: " + _quality_decision_counts(decisions, "event_archetype"))
    lines.append("- Cause Status Distribution: " + _quality_decision_counts(decisions, "cause_status"))
    lines.append("- Market Reaction Confirmed: " + _quality_decision_counts(decisions, "market_reaction_confirmed"))
    lines.append("- Causal Mechanism Confirmed: " + _quality_decision_counts(decisions, "causal_mechanism_confirmed"))
    lines.append("- Evidence Specificity Distribution: " + _quality_decision_counts(decisions, "evidence_specificity"))
    lines.append("- Market Confirmation Distribution: " + _quality_decision_counts(decisions, "market_confirmation_level"))
    lines.append("- Top Upgrade Candidates: " + (_upgrade_candidate_line(decisions) or "none"))
    lines.append("- Top Downgrade Risks: " + (_downgrade_risk_line(decisions) or "none"))
    lines.append("- Candidate Discovery Funnel: " + _candidate_discovery_funnel_line(hypotheses))
    lines.append("- Feedback by Impact Path: " + _feedback_by_impact_path(alerts, feedback))
    lines.extend(["", "## Quality Gate Downgrades"])
    downgraded = _quality_gate_downgrades(decisions)
    lines.append("- Downgraded items: " + (_brief_decisions(downgraded[:5]) or "none"))
    lines.append("- Top blocked route attempts: " + (_blocked_route_attempts_line(downgraded) or "none"))
    lines.append("- Reason counts: " + _quality_gate_reason_counts(downgraded))
    lines.extend(["", "## Legacy Quality Conflicts"])
    conflicts = _legacy_quality_conflicts(alerts)
    lines.extend(_legacy_quality_conflict_lines(conflicts[:8]))
    exploratory = event_alpha_notifications.select_exploratory_candidates(
        decisions,
        cfg=event_alpha_notifications.EventAlphaNotificationConfig(
            exploratory_digest_enabled=True,
            exploratory_digest_max_items=5,
        ),
        now=generated,
    )
    lines.extend(["", "## Exploratory Digest"])
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
    lines.extend(["", "## Active Watchlist"])
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
    if active:
        for entry in sorted(active, key=lambda item: item.latest_score, reverse=True)[:5]:
            lines.append(f"- {event_watchlist.final_state_value(entry)}: {entry.symbol}/{entry.coin_id} score={entry.latest_score} playbook={entry.latest_playbook_type or 'unknown'}")
    else:
        lines.append("- No active watchlist entries.")
    lines.extend(["", "## Quality-Capped Watchlist Rows"])
    capped = [entry for entry in entries if event_watchlist.state_is_quality_capped(entry)]
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
    lines.extend(["", "## Research Cards"])
    cards = [Path(path) for path in card_paths]
    if cards:
        for path in cards[:20]:
            lines.append(f"- [{path.name}]({path})")
    else:
        lines.append("- No cards written for this brief.")
    lines.extend(["", "## Missed Opportunities"])
    if missed:
        for row in sorted(missed, key=lambda item: abs(_float(item.get("return_pct"))), reverse=True)[:5]:
            lines.append(f"- {row.get('symbol') or row.get('coin_id')}: {row.get('move_window')} {row.get('return_pct')} stage={row.get('failure_stage')}")
    else:
        lines.append("- No missed-opportunity rows found.")
    lines.extend(["", "## Source Reliability"])
    lines.append(_compact(event_source_reliability.format_source_reliability_report(
        alerts,
        feedback_rows=feedback,
        missed_rows=missed,
        run_rows=runs[:10],
    )))
    lines.extend(["", "## Calibration Recommendations"])
    lines.append(_compact(event_alpha_calibration.format_calibration_report(
        alerts,
        feedback_rows=feedback,
        missed_rows=missed,
    )))
    lines.extend(["", "## Top Suppression Reasons"])
    lines.extend(_suppression_lines(decisions, entries))
    if not alertable:
        lines.extend(["", "## Why No Alerts"])
        lines.append(_compact(event_alpha_explain.format_last_run_explanation(
            runs,
            alert_rows=alerts,
            requested_profile=requested_profile,
            artifact_namespace=artifact_namespace,
            include_test_artifacts=include_test_artifacts,
            include_legacy_artifacts=include_legacy_artifacts,
        )))
    else:
        lines.extend(["", "## Why Alerts Were Sent"])
        for decision in alertable[:8]:
            lines.append(f"- {decision.entry.symbol}/{decision.entry.coin_id}: {decision.reason}")
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
        f"path: {result.path}",
        f"cards_linked: {len(result.cards)}",
        "No live RSI alerts, paper trades, live DB rows, or execution were changed.",
    ])


def _compact(report: str) -> str:
    lines = [line for line in str(report or "").splitlines() if line and not line.startswith("=")]
    return "\n".join(f"> {line}" for line in lines[:20])


def _latest_notification_run(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    ordered = sorted(
        (dict(row) for row in rows if isinstance(row, Mapping)),
        key=lambda row: str(row.get("started_at") or ""),
        reverse=True,
    )
    return ordered[0] if ordered else None


def _provider_health_lines(rows: Mapping[str, Mapping[str, Any]]) -> list[str]:
    if not rows:
        return ["- No provider health rows found."]
    grouped: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for provider, row in rows.items():
        grouped.setdefault(str(row.get("provider_kind") or "unclassified"), []).append((str(provider), row))
    lines: list[str] = []
    for group in ("event_source", "enrichment", "catalyst_search", "llm", "unclassified"):
        items = grouped.get(group)
        if not items:
            continue
        lines.append(f"- {group}:")
        for provider, row in sorted(items)[:8]:
            disabled = row.get("disabled_until") or "none"
            lines.append(
                f"  - {provider}: failures={int(row.get('consecutive_failures') or 0)} "
                f"disabled_until={disabled} last_success={row.get('last_success_at') or 'never'}"
            )
    return lines or ["- No provider health rows found."]


def _llm_budget_lines(latest: Mapping[str, Any]) -> list[str]:
    if not latest:
        return ["- No latest run row; budget usage unknown."]
    return [
        f"- Cache hits/misses: {int(latest.get('llm_cache_hits') or 0)} / {int(latest.get('llm_cache_misses') or 0)}",
        f"- Calls attempted: {int(latest.get('llm_calls_attempted') or 0)}",
        f"- Skipped due budget: {int(latest.get('llm_skipped_due_budget') or 0)}",
    ]


def _new_since_last_run_lines(runs: list[dict[str, Any]]) -> list[str]:
    if not runs:
        return ["- No run history."]
    latest = runs[0]
    previous = runs[1] if len(runs) > 1 else {}
    fields = ("raw_events", "candidates", "alerts", "watchlist_entries", "alertable")
    lines = []
    for field in fields:
        delta = int(latest.get(field) or 0) - int(previous.get(field) or 0)
        lines.append(f"- {field}: {int(latest.get(field) or 0)} ({delta:+d} vs previous)")
    return lines


def _watchlist_hotter_lines(entries: list[event_watchlist.EventWatchlistEntry]) -> list[str]:
    hot = [
        entry for entry in entries
        if entry.score_jump > 0
        or entry.derivatives_crowding_upgraded
        or entry.cluster_confidence_upgraded
        or entry.event_time_upgraded
    ]
    if not hot:
        return ["- No hotter watchlist rows found."]
    lines = []
    for entry in sorted(hot, key=lambda item: (item.score_jump, item.latest_score), reverse=True)[:5]:
        reasons = ", ".join(entry.material_change_reasons) if entry.material_change_reasons else "material update"
        lines.append(f"- {entry.symbol}/{entry.coin_id}: score={entry.latest_score} jump={entry.score_jump} reasons={reasons}")
    return lines


def _suppression_lines(
    decisions: list[event_alpha_router.EventAlphaRouteDecision],
    entries: list[event_watchlist.EventWatchlistEntry],
) -> list[str]:
    counts: dict[str, int] = {}
    for decision in decisions:
        if event_alpha_router.alertable_after_quality_gate(decision):
            continue
        counts[decision.reason] = counts.get(decision.reason, 0) + 1
    for entry in entries:
        if entry.suppressed_reason:
            counts[entry.suppressed_reason] = counts.get(entry.suppressed_reason, 0) + 1
    if not counts:
        return ["- None."]
    return [f"- {reason}: {count}" for reason, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]]


def _field_counts(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _multi_field_counts(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        values = row.get(field) or []
        if isinstance(values, str):
            values = [values]
        for value in values:
            key = str(value or "").strip()
            if key:
                counts[key] = counts.get(key, 0) + 1
    return counts


def _format_counts(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none"


def _brief_hypothesis_labels(rows: Iterable[Mapping[str, Any]]) -> str:
    labels: list[str] = []
    for row in rows:
        candidates = row.get("validated_candidate_assets") or row.get("crypto_candidate_assets") or row.get("suggested_candidate_assets") or []
        candidate_label = "none"
        if candidates and isinstance(candidates[0], Mapping):
            candidate_label = str(candidates[0].get("symbol") or candidates[0].get("coin_id") or "asset")
        labels.append(
            f"{row.get('impact_category') or 'unknown'}"
            f"/{row.get('external_asset') or 'unknown'}"
            f"/candidate={candidate_label}"
            f"({row.get('validation_stage') or row.get('status') or 'unknown'}"
            f",score={_float(row.get('hypothesis_score') or _float(row.get('confidence')) * 100):.0f}"
            f",v2={_float(row.get('opportunity_score_v2')):.0f}"
            f",path={row.get('impact_path_type') or 'unknown'}"
            f",role={row.get('candidate_role') or 'unknown'})"
        )
    return "; ".join(labels)


def _brief_decisions(rows: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    labels = []
    for decision in rows:
        entry = decision.entry
        components = entry.latest_score_components or {}
        final_route = event_alpha_router.final_route_value(decision)
        labels.append(
            f"{entry.symbol}/{entry.coin_id}"
            f"({event_watchlist.final_state_value(entry)},score={entry.latest_score},v2={_float(components.get('opportunity_score_v2')):.0f},"
            f"final={_float(components.get('opportunity_score_final')):.0f},"
            f"level={components.get('opportunity_level') or 'unknown'},"
            f"path={components.get('impact_path_type') or 'unknown'},role={components.get('candidate_role') or 'unknown'},"
            f"route={final_route},requested={decision.requested_route_before_quality_gate or decision.route.value},reason={decision.reason})"
        )
    return "; ".join(labels)


def _brief_entries(rows: Iterable[event_watchlist.EventWatchlistEntry]) -> str:
    labels = []
    for entry in rows:
        components = entry.latest_score_components or {}
        labels.append(
            f"{entry.symbol}/{entry.coin_id}"
            f"({components.get('impact_category') or entry.latest_playbook_type or 'unknown'},"
            f"score={entry.latest_score},v2={_float(components.get('opportunity_score_v2')):.0f},"
            f"path={components.get('impact_path_type') or 'unknown'})"
        )
    return "; ".join(labels)


def _market_confirmation_by_playbook(rows: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    counts: dict[str, dict[str, int]] = {}
    for decision in rows:
        entry = decision.entry
        if entry.relationship_type != "impact_hypothesis":
            continue
        components = entry.latest_score_components or {}
        playbook = str(entry.latest_effective_playbook_type or entry.latest_playbook_type or "unknown")
        level = str(components.get("market_confirmation_level") or "unknown")
        counts.setdefault(playbook, {})[level] = counts.setdefault(playbook, {}).get(level, 0) + 1
    if not counts:
        return "none"
    parts: list[str] = []
    for playbook, levels in sorted(counts.items()):
        parts.append(playbook + "[" + ",".join(f"{key}={value}" for key, value in sorted(levels.items())) + "]")
    return "; ".join(parts)


def _quality_decision_counts(rows: Iterable[event_alpha_router.EventAlphaRouteDecision], key: str) -> str:
    counts: dict[str, int] = {}
    for decision in rows:
        if decision.entry.relationship_type != "impact_hypothesis":
            continue
        components = decision.entry.latest_score_components or {}
        value = str(components.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return _format_counts(counts)


def _quality_gate_downgrades(
    rows: Iterable[event_alpha_router.EventAlphaRouteDecision],
) -> list[event_alpha_router.EventAlphaRouteDecision]:
    return [
        decision for decision in rows
        if decision.quality_gate_block_reason
        or (
            decision.requested_route_before_quality_gate
            and decision.final_route_after_quality_gate
            and decision.requested_route_before_quality_gate != decision.final_route_after_quality_gate
        )
    ]


def _blocked_route_attempts_line(rows: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    labels: list[str] = []
    for decision in rows:
        labels.append(
            f"{decision.entry.symbol}/{decision.entry.coin_id}:"
            f"{decision.requested_route_before_quality_gate or 'unknown'}->"
            f"{decision.final_route_after_quality_gate or decision.route.value}"
        )
        if len(labels) >= 5:
            break
    return "; ".join(labels)


def _quality_gate_reason_counts(rows: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    counts: dict[str, int] = {}
    for decision in rows:
        reason = str(decision.quality_gate_block_reason or "route_capped")
        counts[reason] = counts.get(reason, 0) + 1
    return _format_counts(counts)


def _legacy_quality_conflicts(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    out = []
    for row in rows:
        classification = str(
            row.get("snapshot_quality_classification")
            or event_alpha_alert_store.classify_alert_snapshot(row)
        )
        if classification in event_alpha_alert_store.LEGACY_CONFLICT_CLASSIFICATIONS:
            out.append(row)
    return out


def _legacy_quality_conflict_lines(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    items = list(rows)
    if not items:
        return ["- none"]
    lines: list[str] = []
    for row in items:
        label = row.get("symbol") or row.get("validated_symbol") or row.get("coin_id") or row.get("alert_key") or "candidate"
        classification = str(row.get("snapshot_quality_classification") or event_alpha_alert_store.classify_alert_snapshot(row))
        lines.append(
            f"- {label}: classification={classification} "
            f"legacy_route={row.get('route') or 'unknown'} "
            f"final={row.get('final_route_after_quality_gate') or 'missing'} "
            f"level={row.get('opportunity_level') or 'unknown'} "
            f"score={row.get('opportunity_score_final') if row.get('opportunity_score_final') is not None else 'n/a'}"
        )
    return lines


def _candidate_discovery_funnel_line(rows: Iterable[Mapping[str, Any]]) -> str:
    generated = executed = raw_terms = candidate_like = accepted = rejected = validated = promoted = 0
    for row in rows:
        generated += len(row.get("generated_queries") or [])
        executed += len(row.get("executed_queries") or [])
        crypto = row.get("crypto_candidate_assets") or []
        rejects = row.get("rejected_candidate_assets") or []
        raw_terms += len(crypto) + len(rejects)
        candidate_like += sum(1 for item in [*crypto, *rejects] if isinstance(item, Mapping) and _candidate_like_term(item))
        accepted += sum(1 for item in crypto if isinstance(item, Mapping) and bool(item.get("accepted", item.get("validated", False))))
        rejected += len(rejects)
        if str(row.get("validation_stage") or "") in {"catalyst_link_validated", "impact_path_validated", "market_confirmed", "promoted_to_radar"}:
            validated += 1
        if str(row.get("opportunity_level") or "") in {"validated_digest", "watchlist", "high_priority"}:
            promoted += 1
    if not any((generated, executed, raw_terms, candidate_like, accepted, rejected, validated, promoted)):
        return "none"
    resolver_attempted = accepted + rejected
    return (
        f"generated={generated}, executed={executed}, raw_terms_extracted={raw_terms}, "
        f"candidate_like_terms={candidate_like}, resolver_accepted_candidates={accepted}, "
        f"resolver_attempted={resolver_attempted}, resolver_rejected_terms={rejected}, "
        f"context_validated_candidates={validated}, "
        f"promoted_candidates={promoted}"
    )


def _canonical_incident_lines(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    incidents = [dict(row) for row in rows if isinstance(row, Mapping)]
    if not incidents:
        return ["- Stored incidents: none loaded for this profile."]
    diagnostic_rows = [row for row in incidents if _incident_is_hidden(row)]
    visible = [row for row in incidents if not _incident_is_diagnostic(row)]
    if not visible:
        return [
            f"- Stored incidents: {len(incidents)}",
            f"- Diagnostic/raw/external-context observations hidden: {len(diagnostic_rows)}",
            "- Canonical incidents: none visible for this profile.",
        ]
    lines = [
        f"- Stored incidents: {len(incidents)}",
        f"- Diagnostic/raw/external-context observations hidden: {len(diagnostic_rows)}",
        "- Relevance statuses: " + _format_counts(_field_counts(incidents, "incident_relevance_status")),
        "- Event archetypes: " + _format_counts(_field_counts(visible, "event_archetype")),
        "- Cause statuses: " + _format_counts(_field_counts(visible, "current_cause_status")),
        "- Primary subjects: " + _format_counts(_field_counts(visible, "primary_subject")),
        "- New/updated: "
        f"multiple_source_updates={sum(1 for row in visible if int(row.get('source_update_count') or 0) > 1)}, "
        f"conflicting_claims={sum(1 for row in visible if row.get('conflicting_claims'))}",
        "- Market reaction but unknown/ruled-out cause: "
        + str(sum(
            1 for row in visible
            if (row.get("market_reaction_observed") or row.get("market_reaction_confirmed"))
            and str(row.get("current_cause_status") or "") in {"unknown", "ruled_out"}
        )),
        "- Confirmed cause missing market data: "
        + str(sum(
            1 for row in visible
            if str(row.get("current_cause_status") or "") == "confirmed"
            and not row.get("market_context_source")
        )),
        "- Weak unqualified incident links: "
        + str(sum(int(row.get("weak_link_count") or 0) for row in visible)),
    ]
    candidates = [row for row in visible if str(row.get("incident_relevance_status") or "") == "incident_candidate"]
    active = [
        row for row in visible
        if str(row.get("incident_relevance_status") or "") == "active_incident"
        and int(row.get("qualified_link_count") or 0) > 0
    ]
    linked = [
        row for row in visible
        if str(row.get("incident_relevance_status") or "") == "linked_incident"
        and int(row.get("qualified_link_count") or 0) > 0
    ]
    market_unknown = [
        row for row in visible
        if (row.get("market_reaction_observed") or row.get("market_reaction_confirmed"))
        and str(row.get("current_cause_status") or "") in {"unknown", "ruled_out"}
    ]
    lines.append(f"- Incident candidates: {len(candidates)}")
    lines.append(f"- Active incidents with qualified links: {len(active)}")
    lines.append(f"- Linked incidents with qualified links: {len(linked)}")
    lines.append(f"- Market reactions with unknown/ruled-out cause: {len(market_unknown)}")
    if candidates:
        labels = []
        for row in candidates[:5]:
            labels.append(
                f"{row.get('canonical_name') or row.get('incident_id')}: "
                f"reason={row.get('canonical_persistence_reason') or 'candidate'} "
                f"weak_links={int(row.get('weak_link_count') or 0)}"
            )
        lines.append("- Incident candidates awaiting qualified crypto link: " + " | ".join(labels))
    notable = sorted(
        visible,
        key=lambda row: (
            int(row.get("source_update_count") or 0),
            _float(row.get("incident_confidence")),
        ),
        reverse=True,
    )
    if notable:
        labels = []
        for row in notable[:5]:
            assets = row.get("linked_assets") or []
            asset_text = _incident_asset_summary(assets)
            labels.append(
                f"{row.get('canonical_name') or row.get('incident_id')}: "
                f"cause={row.get('current_cause_status') or 'unknown'} "
                f"archetype={row.get('event_archetype') or 'unknown'} "
                f"sources={int(row.get('source_update_count') or 0)}/"
                f"{int(row.get('independent_source_count') or 0)} "
                f"assets={asset_text}"
            )
        lines.append("- Notable incidents: " + " | ".join(labels))
    return lines


def _incident_is_hidden(row: Mapping[str, Any]) -> bool:
    status = str(row.get("incident_relevance_status") or "")
    return bool(row.get("diagnostic_only")) or status in {"raw_observation", "external_context_only", "diagnostic_only", "rejected_incident"}


def _incident_is_diagnostic(row: Mapping[str, Any]) -> bool:
    return _incident_is_hidden(row)


def _incident_asset_summary(value: Any) -> str:
    if not value:
        return "none"
    labels: list[str] = []
    for item in list(value)[:4]:
        if not isinstance(item, Mapping):
            continue
        labels.append(
            f"{item.get('symbol') or item.get('coin_id') or 'asset'}:"
            f"{item.get('role') or 'unknown'}"
        )
    return ", ".join(labels) or "none"


def _candidate_like_term(item: Mapping[str, Any]) -> bool:
    symbol = str(item.get("symbol") or "").strip()
    coin_id = str(item.get("coin_id") or "").strip()
    name = str(item.get("name") or item.get("project_name") or "").strip()
    source = str(item.get("source") or "").strip().casefold()
    mention_type = str(item.get("mention_type") or item.get("type") or "").strip().casefold()
    reason = str(item.get("reason") or item.get("rejection_reason") or item.get("identity_reason") or "").casefold()
    accepted = bool(item.get("accepted") or item.get("validated"))
    if any(token in reason for token in ("source_noise", "publisher", "word_collision", "url_only", "generic_symbol")):
        return False
    if any(token in mention_type for token in ("source_noise", "publisher", "navigation", "nav", "word_collision")):
        return False
    if source in {"taxonomy", "source_origin", "publisher", "nav", "navigation"} and not accepted:
        return False
    return bool(symbol or coin_id or name)


def _feedback_by_impact_path(alerts: Iterable[Mapping[str, Any]], feedback: Iterable[Mapping[str, Any]]) -> str:
    path_by_key: dict[str, str] = {}
    for row in alerts:
        key = str(row.get("alert_key") or row.get("alert_id") or "")
        if key:
            path_by_key[key] = str(row.get("impact_path_type") or "unknown")
    counts: dict[str, int] = {}
    for row in feedback:
        key = str(row.get("key") or row.get("alert_key") or row.get("alert_id") or "")
        path = str(row.get("impact_path_type") or path_by_key.get(key) or "unknown")
        label = str(row.get("label") or row.get("feedback") or "feedback")
        counts[f"{path}:{label}"] = counts.get(f"{path}:{label}", 0) + 1
    return _format_counts(counts)


def _upgrade_candidate_line(rows: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    labels: list[str] = []
    for decision in sorted(rows, key=lambda item: item.entry.latest_score, reverse=True):
        entry = decision.entry
        if event_alpha_router.alertable_after_quality_gate(decision) or entry.relationship_type != "impact_hypothesis":
            continue
        components = entry.latest_score_components or {}
        upgrade = event_opportunity_verdict.explain_upgrade_path(components=components)
        if not upgrade.upgrade_requirements:
            continue
        labels.append(
            f"{entry.symbol}/{entry.coin_id}: "
            + "; ".join(upgrade.upgrade_requirements[:2])
        )
        if len(labels) >= 5:
            break
    return " | ".join(labels)


def _downgrade_risk_line(rows: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> str:
    labels: list[str] = []
    for decision in sorted(rows, key=lambda item: item.entry.latest_score, reverse=True):
        entry = decision.entry
        if not event_alpha_router.alertable_after_quality_gate(decision) and event_watchlist.final_state_value(entry) not in {"WATCHLIST", "HIGH_PRIORITY"}:
            continue
        components = entry.latest_score_components or {}
        upgrade = event_opportunity_verdict.explain_upgrade_path(components=components)
        if not upgrade.downgrade_warnings:
            continue
        labels.append(
            f"{entry.symbol}/{entry.coin_id}: "
            + "; ".join(upgrade.downgrade_warnings[:2])
        )
        if len(labels) >= 5:
            break
    return " | ".join(labels)


def _float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _lane_count(row: Mapping[str, Any] | None, field: str, lane: str) -> int:
    if not row:
        return 0
    counts = row.get(field) or {}
    if not isinstance(counts, Mapping):
        return 0
    try:
        return int(counts.get(lane) or 0)
    except (TypeError, ValueError):
        return 0


def _format_clock_status(status: Mapping[str, Any]) -> str:
    age = status.get("fixed_clock_age_hours")
    age_text = "n/a" if age is None else f"{float(age):.2f}h"
    return (
        "Clock: "
        f"mode={status.get('clock_mode') or 'unknown'}; "
        f"research_now={status.get('research_now') or 'unknown'}; "
        f"wall_clock_now={status.get('wall_clock_now') or 'unknown'}; "
        f"fixed_clock_age_hours={age_text}"
    )


def _format_clock_warning_lines(status: Mapping[str, Any]) -> list[str]:
    warnings = [str(item) for item in status.get("warnings") or () if str(item)]
    return [f"Clock warning: {warning}" for warning in warnings]


def _strip_sensitive(text: str) -> str:
    return (
        text.replace("OPENAI_API_KEY", "[redacted]")
        .replace("TELEGRAM_BOT_TOKEN", "[redacted]")
        .replace(".env", "[env-file]")
    )
