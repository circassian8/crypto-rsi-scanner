# ---------------------------------------------------------------------------
# Moved from crypto_rsi_scanner/event_alpha_burn_in.py
# ---------------------------------------------------------------------------
"""Burn-in scorecard for Event Alpha research artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..artifacts import context as event_alpha_artifacts


@dataclass(frozen=True)
class EventAlphaBurnInScorecard:
    days: int
    run_rows: list[dict[str, Any]]
    alert_rows: list[dict[str, Any]]
    feedback_rows: list[dict[str, Any]]
    missed_rows: list[dict[str, Any]]
    provider_health_rows: dict[str, dict[str, Any]]
    llm_budget_rows: list[dict[str, Any]]
    outcome_rows: list[dict[str, Any]]
    profile: str | None = None
    runs_with_alertable: int = 0
    alert_snapshot_rows: int = 0
    runs_with_alertable_but_no_alert_snapshots: int = 0
    feedback_row_count: int = 0
    outcome_row_count: int = 0
    missed_row_count: int = 0
    provider_health_row_count: int = 0
    llm_budget_row_count: int = 0
    artifact_namespace: str | None = None
    include_test_artifacts: bool = False
    include_legacy_artifacts: bool = False
    legacy_rows_skipped: int = 0
    test_rows_skipped: int = 0
    coverage_warnings: tuple[str, ...] = ()


def build_burn_in_scorecard(
    *,
    run_rows: Iterable[Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    llm_budget_rows: Iterable[Mapping[str, Any]] = (),
    outcome_rows: Iterable[Mapping[str, Any]] = (),
    profile: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
    days: int = 7,
    now: datetime | None = None,
) -> EventAlphaBurnInScorecard:
    cutoff = (now or datetime.now(timezone.utc)).astimezone(timezone.utc) - timedelta(days=max(1, int(days or 1)))
    raw_run_data = _filter_rows(run_rows, cutoff, ("started_at", "observed_at", "marked_at"))
    raw_alert_data = _filter_rows(alert_rows, cutoff, ("observed_at", "started_at"))
    raw_feedback_data = _filter_rows(feedback_rows, cutoff, ("marked_at", "observed_at"))
    raw_missed_data = _filter_rows(missed_rows, cutoff, ("observed_at", "detected_at", "created_at"))
    raw_budget_data = _filter_rows(llm_budget_rows, cutoff, ("date", "updated_at"))
    raw_outcomes = _filter_rows(outcome_rows, cutoff, ("observed_at", "started_at"))
    raw_all = [*raw_run_data, *raw_alert_data, *raw_feedback_data, *raw_missed_data, *raw_budget_data, *raw_outcomes]
    legacy_skipped = 0 if include_legacy_artifacts else sum(1 for row in raw_all if event_alpha_artifacts.is_legacy_row(row))
    test_skipped = 0 if include_test_artifacts else sum(1 for row in raw_all if event_alpha_artifacts.is_non_operational_row(row))
    run_data = _artifact_filter(raw_run_data, profile, artifact_namespace, include_test_artifacts, include_legacy_artifacts)
    alert_data = _artifact_filter(raw_alert_data, profile, artifact_namespace, include_test_artifacts, include_legacy_artifacts)
    feedback_data = _artifact_filter(raw_feedback_data, profile, artifact_namespace, include_test_artifacts, include_legacy_artifacts)
    missed_data = _artifact_filter(raw_missed_data, profile, artifact_namespace, include_test_artifacts, include_legacy_artifacts)
    budget_data = _artifact_filter(raw_budget_data, profile, artifact_namespace, include_test_artifacts, include_legacy_artifacts)
    supplied_outcomes = _artifact_filter(raw_outcomes, profile, artifact_namespace, include_test_artifacts, include_legacy_artifacts)
    outcome_data = supplied_outcomes or _rows_with_outcomes(alert_data)
    health_data = {str(key): dict(value) for key, value in (provider_health_rows or {}).items()}
    runs_with_alertable = sum(1 for row in run_data if _int(row.get("alertable")) > 0)
    alert_counts_by_run_id: dict[str, int] = {}
    for row in alert_data:
        run_id = str(row.get("run_id") or "").strip()
        if run_id:
            alert_counts_by_run_id[run_id] = alert_counts_by_run_id.get(run_id, 0) + 1
    alertable_without_snapshots = sum(
        1 for row in run_data
        if _int(row.get("alertable")) > 0
        and event_alpha_artifacts.classify_snapshot_availability(
            row,
            None,
            alert_counts_by_run_id.get(str(row.get("run_id") or "").strip(), 0),
        ) not in {
            event_alpha_artifacts.SNAPSHOT_AVAILABLE,
            event_alpha_artifacts.SNAPSHOT_UNKNOWN_LEGACY,
        }
    )
    coverage = _coverage_warnings(
        run_data,
        alert_data,
        feedback_data,
        outcome_data,
        missed_data,
        health_data,
        profile=profile,
    )
    return EventAlphaBurnInScorecard(
        days=max(1, int(days or 1)),
        run_rows=run_data,
        alert_rows=alert_data,
        feedback_rows=feedback_data,
        missed_rows=missed_data,
        provider_health_rows=health_data,
        llm_budget_rows=budget_data,
        outcome_rows=outcome_data,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
        legacy_rows_skipped=legacy_skipped,
        test_rows_skipped=test_skipped,
        runs_with_alertable=runs_with_alertable,
        alert_snapshot_rows=len(alert_data),
        runs_with_alertable_but_no_alert_snapshots=alertable_without_snapshots,
        feedback_row_count=len(feedback_data),
        outcome_row_count=len(outcome_data),
        missed_row_count=len(missed_data),
        provider_health_row_count=len(health_data),
        llm_budget_row_count=len(budget_data),
        coverage_warnings=coverage,
    )


def load_llm_budget_rows(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    p = Path(path).expanduser()
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = raw.get("entries") if isinstance(raw, Mapping) else raw
    return [dict(row) for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def format_burn_in_scorecard(scorecard: EventAlphaBurnInScorecard) -> str:
    runs = scorecard.run_rows
    alerts = scorecard.alert_rows
    feedback = scorecard.feedback_rows
    missed = scorecard.missed_rows
    health = scorecard.provider_health_rows
    budget = scorecard.llm_budget_rows
    successful = sum(1 for row in runs if bool(row.get("success")))
    lines = [
        "=" * 76,
        "EVENT ALPHA BURN-IN SCORECARD (research-only)",
        "=" * 76,
        f"window_days={scorecard.days}",
        f"profile={scorecard.profile or 'any'} namespace={scorecard.artifact_namespace or 'any'} "
        f"include_test_artifacts={str(scorecard.include_test_artifacts).lower()} "
        f"include_legacy_artifacts={str(scorecard.include_legacy_artifacts).lower()}",
        f"runs={len(runs)} successful={successful} failed={len(runs) - successful}",
        (
            "events/candidates/alertable: "
            f"{sum(_int(row.get('raw_events')) for row in runs)} / "
            f"{sum(_int(row.get('candidates')) for row in runs)} / "
            f"{sum(_int(row.get('alertable')) for row in runs)}"
        ),
        "alerts by tier: " + _count_line(alerts, "tier"),
        "alerts by playbook: " + _count_line(alerts, "playbook_type"),
        "feedback: " + _count_line(feedback, "label"),
        "missed by stage: " + _count_line(missed, "failure_stage"),
        "provider failures/backoffs: " + _provider_line(health),
        "LLM budget: " + _budget_line(budget),
        "artifact coverage: "
        f"runs_with_alertable={scorecard.runs_with_alertable} · "
        f"alert_snapshots={scorecard.alert_snapshot_rows} · "
        f"alertable_without_snapshots={scorecard.runs_with_alertable_but_no_alert_snapshots} · "
        f"feedback={scorecard.feedback_row_count} · outcomes={scorecard.outcome_row_count} · "
        f"missed={scorecard.missed_row_count} · provider_health={scorecard.provider_health_row_count} · "
        f"llm_budget={scorecard.llm_budget_row_count} · "
        f"legacy_skipped={scorecard.legacy_rows_skipped} · test_skipped={scorecard.test_rows_skipped}",
        "top playbooks: " + _top_line(alerts, "playbook_type"),
        "worst sources: " + _worst_source_line(alerts, feedback),
    ]
    if scorecard.coverage_warnings:
        lines.extend(["", "coverage warnings:"])
        lines.extend(f"- {warning}" for warning in scorecard.coverage_warnings)
    lines.extend(["", "recommendations:"])
    lines.extend(f"- {item}" for item in _recommendations(runs, alerts, feedback, missed, health))
    lines.append("No thresholds, alert tiers, paper trades, live DB rows, or execution were changed.")
    return "\n".join(lines).rstrip()


def _filter_rows(
    rows: Iterable[Mapping[str, Any]],
    cutoff: datetime,
    fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        parsed = None
        for field in fields:
            parsed = _dt(row.get(field))
            if parsed is not None:
                break
        if parsed is None or parsed >= cutoff:
            out.append(dict(row))
    return out


def _artifact_filter(
    rows: Iterable[Mapping[str, Any]],
    profile: str | None,
    artifact_namespace: str | None,
    include_test_artifacts: bool,
    include_legacy_artifacts: bool,
) -> list[dict[str, Any]]:
    return event_alpha_artifacts.filter_artifact_rows(
        rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )


def _count_line(rows: Iterable[Mapping[str, Any]], field: str) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) if counts else "none"


def _top_line(rows: Iterable[Mapping[str, Any]], field: str) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return ", ".join(f"{key}={count}" for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]) if counts else "none"


def _provider_line(rows: Mapping[str, Mapping[str, Any]]) -> str:
    bad = [
        f"{row.get('provider_key') or key}({int(row.get('consecutive_failures') or 0)})"
        for key, row in rows.items()
        if int(row.get("consecutive_failures") or 0) > 0 or row.get("disabled_until")
    ]
    return ", ".join(bad[:8]) if bad else "none"


def _budget_line(rows: Iterable[Mapping[str, Any]]) -> str:
    data = list(rows)
    calls = sum(_int(row.get("extractor_calls_attempted")) + _int(row.get("relationship_calls_attempted")) for row in data)
    hits = sum(_int(row.get("cache_hits")) for row in data)
    misses = sum(_int(row.get("cache_misses")) for row in data)
    skipped = sum(_int(row.get("skipped_due_budget")) for row in data)
    cost = sum(_float(row.get("estimated_cost_usd")) for row in data)
    return f"calls={calls} cache={hits}/{misses} skipped={skipped} estimated_cost=${cost:.4f}"


def _rows_with_outcomes(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    outcome_fields = (
        "primary_horizon_return",
        "return_1h",
        "return_4h",
        "return_24h",
        "return_72h",
        "return_7d",
        "max_favorable_excursion",
        "max_adverse_excursion",
        "mfe_mae_ratio",
        "direction_hit",
        "volatility_hit",
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        if any(row.get(field) not in (None, "") for field in outcome_fields):
            out.append(dict(row))
    return out


def _coverage_warnings(
    runs: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    missed: list[dict[str, Any]],
    health: Mapping[str, Mapping[str, Any]],
    *,
    profile: str | None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if not runs:
        if profile:
            warnings.append(f"no operational burn-in rows found for profile {profile}")
        else:
            warnings.append("no operational burn-in rows found")
    if any(_int(row.get("alertable")) > 0 for row in runs) and not alerts:
        warnings.append("alert snapshots missing for alertable runs")
    if alerts and not feedback:
        warnings.append("no feedback labels for routed alerts")
    if _matured_alerts(alerts) and not outcomes:
        warnings.append("no outcomes filled for matured alerts")
    if not missed:
        warnings.append("no missed-opportunity rows for burn-in window")
    live_profiles = {"no_key_live", "no_key_llm", "api_live", "full_llm_live", "research_send"}
    row_profiles = {str(row.get("profile") or "") for row in runs}
    profile_name = str(profile or "").strip()
    live_context = profile_name in live_profiles or bool(row_profiles & live_profiles)
    if live_context and not health:
        warnings.append("provider health missing for live profiles")
    return tuple(dict.fromkeys(warnings))


def _matured_alerts(alerts: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    matured: list[dict[str, Any]] = []
    for row in alerts:
        tier = str(row.get("tier") or row.get("latest_tier") or "")
        route = str(row.get("route") or "")
        if tier in {"WATCHLIST", "HIGH_PRIORITY_WATCH", "TRIGGERED_FADE"} or route in {
            "RESEARCH_DIGEST",
            "HIGH_PRIORITY_RESEARCH",
            "TRIGGERED_FADE_RESEARCH",
        }:
            matured.append(dict(row))
    return matured


def _worst_source_line(alerts: list[dict[str, Any]], feedback: list[dict[str, Any]]) -> str:
    junk_targets = {str(row.get("key") or row.get("target") or "") for row in feedback if row.get("label") == "junk"}
    counts: dict[str, int] = {}
    for row in alerts:
        key = str(row.get("alert_key") or "")
        if key not in junk_targets:
            continue
        source = str(row.get("source") or row.get("source_provider") or "unknown")
        counts[source] = counts.get(source, 0) + 1
    return ", ".join(f"{source}={count}" for source, count in sorted(counts.items())) if counts else "none"


def _recommendations(
    runs: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
    missed: list[dict[str, Any]],
    health: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    recs: list[str] = []
    if not runs:
        recs.append("run the no_key_live burn-in cycle daily before calibrating thresholds")
    if any(int(row.get("consecutive_failures") or 0) > 0 or row.get("disabled_until") for row in health.values()):
        recs.append("inspect degraded provider health before judging alert recall")
    junk = sum(1 for row in feedback if row.get("label") == "junk")
    useful = sum(1 for row in feedback if row.get("label") == "useful")
    if junk > useful and junk >= 2:
        recs.append("tighten source/resolver gates for playbooks producing junk feedback")
    if missed:
        recs.append("review missed-opportunity stages and add resolver/source coverage where repeated")
    if alerts and not feedback:
        recs.append("mark useful/junk/watch feedback for routed alerts to make calibration actionable")
    if not recs:
        recs.append("continue burn-in until feedback and outcomes cover multiple playbooks")
    return tuple(dict.fromkeys(recs))


def _dt(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value)
    if len(text) == 10 and text.count("-") == 2:
        text = text + "T00:00:00+00:00"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _int(value: object) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# Moved from crypto_rsi_scanner/event_alpha_burn_in_readiness.py
# ---------------------------------------------------------------------------
"""Live-style no-send burn-in readiness checks for Event Alpha."""


from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from ... import event_alpha_artifact_doctor, event_provider_status
from ..artifacts import run_ledger as event_alpha_run_ledger
from . import feedback as event_alpha_feedback_readiness


@dataclass(frozen=True)
class EventAlphaBurnInReadinessResult:
    profile: str
    artifact_namespace: str
    ready: bool
    latest_run_id: str | None
    run_completed: bool
    no_send_confirmed: bool
    provider_configured: int
    provider_not_configured: int
    provider_ready_event_sources: int
    provider_ready_enrichment_sources: int
    core_opportunities: int
    cards_checked: int
    feedback_targets: int
    evidence_acquisition_rows: int
    evidence_acquisition_attempted: int
    market_freshness_visible: bool
    artifact_doctor_status: str
    artifact_doctor_blockers: tuple[str, ...]
    feedback_readiness_ready: bool
    feedback_readiness_blockers: tuple[str, ...]
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    review_commands: tuple[str, ...] = ()


def build_burn_in_readiness(
    *,
    profile: str,
    artifact_namespace: str,
    run_rows: Iterable[Mapping[str, Any]] = (),
    provider_status: event_provider_status.EventDiscoveryProviderStatus,
    artifact_doctor: event_alpha_artifact_doctor.EventAlphaArtifactDoctorResult,
    feedback_readiness: event_alpha_feedback_readiness.EventAlphaFeedbackReadinessResult,
    core_opportunity_rows: Iterable[Mapping[str, Any]] = (),
    evidence_acquisition_rows: Iterable[Mapping[str, Any]] = (),
    daily_brief_path: str | Path | None = None,
) -> EventAlphaBurnInReadinessResult:
    """Summarize whether a fresh live-style no-send burn-in is reviewable."""
    runs = [dict(row) for row in run_rows if isinstance(row, Mapping)]
    latest = event_alpha_run_ledger.latest_run(runs, profile)
    core_rows = [dict(row) for row in core_opportunity_rows if isinstance(row, Mapping)]
    acquisition_rows = [dict(row) for row in evidence_acquisition_rows if isinstance(row, Mapping)]
    configured_count = sum(1 for item in (*provider_status.sources, *provider_status.enrichment) if item.ready)
    not_configured_count = sum(1 for item in (*provider_status.sources, *provider_status.enrichment) if not item.ready)

    blockers: list[str] = []
    warnings: list[str] = []
    run_completed = bool(latest and latest.get("success"))
    if not latest:
        blockers.append("no matching burn-in run ledger row")
    elif not run_completed:
        blockers.append("latest burn-in run did not complete successfully")

    send_requested = bool(latest and latest.get("send_requested"))
    sent = bool(latest and latest.get("sent"))
    delivered = int((latest or {}).get("send_items_delivered") or 0)
    no_send = bool(latest) and not send_requested and not sent and delivered <= 0
    if latest and not no_send:
        blockers.append("latest run is not confirmed no-send")

    if provider_status.ready_event_source_count <= 0:
        warnings.append("no ready event source; burn-in may be a no-op")
    if provider_status.ready_enrichment_count <= 0:
        warnings.append("no ready enrichment source; market/resolver evidence may be weak")
    warnings.extend(provider_status.warnings)

    raw_count = int((latest or {}).get("raw_events") or 0)
    candidate_count = int((latest or {}).get("candidates") or 0)
    if not core_rows:
        if raw_count or candidate_count:
            blockers.append("non-empty run produced no core opportunity rows")
        else:
            warnings.append("no core opportunities generated; no-op run is acceptable only after provider gaps are reviewed")

    if artifact_doctor.blockers:
        blockers.append("strict artifact doctor has blockers")
    feedback_ready = _feedback_readiness_visible_core_ready(feedback_readiness)
    if not feedback_ready and core_rows:
        blockers.append("feedback readiness has blockers for visible core opportunities")

    evidence_attempted = int((latest or {}).get("evidence_acquisition_attempted") or 0)
    evidence_enabled = int((latest or {}).get("evidence_acquisition_rows_written") or 0) > 0 or bool(acquisition_rows)
    if not evidence_enabled and evidence_attempted <= 0:
        if candidate_count or core_rows:
            warnings.append("source-pack evidence acquisition did not record attempts for candidate/core rows")
        else:
            warnings.append("source-pack evidence acquisition had no eligible candidates")

    daily_path = Path(daily_brief_path).expanduser() if daily_brief_path else None
    market_visible = bool(daily_path and daily_path.exists() and "Market Freshness Readiness" in daily_path.read_text(encoding="utf-8", errors="ignore"))
    if not market_visible:
        warnings.append("market freshness readiness section was not found in the daily brief")

    if artifact_doctor.deliveries_failed:
        blockers.append("notification delivery failures are present in burn-in namespace")
    if artifact_doctor.delivery_rows and no_send:
        blockers.append("delivery ledger rows exist in no-send burn-in namespace")

    commands = (
        f"make event-alpha-daily-brief PROFILE={profile}",
        f"make event-alpha-feedback-readiness PROFILE={profile}",
        f"make event-alpha-artifact-doctor PROFILE={profile} STRICT=1",
        f"make event-alpha-quality-review PROFILE={profile}",
    )
    clean_blockers = tuple(dict.fromkeys(blockers))
    return EventAlphaBurnInReadinessResult(
        profile=profile,
        artifact_namespace=artifact_namespace,
        ready=not clean_blockers,
        latest_run_id=str((latest or {}).get("run_id") or "") or None,
        run_completed=run_completed,
        no_send_confirmed=no_send,
        provider_configured=configured_count,
        provider_not_configured=not_configured_count,
        provider_ready_event_sources=provider_status.ready_event_source_count,
        provider_ready_enrichment_sources=provider_status.ready_enrichment_count,
        core_opportunities=len(core_rows),
        cards_checked=feedback_readiness.cards_checked,
        feedback_targets=feedback_readiness.cards_with_feedback_target,
        evidence_acquisition_rows=len(acquisition_rows),
        evidence_acquisition_attempted=evidence_attempted,
        market_freshness_visible=market_visible,
        artifact_doctor_status=artifact_doctor.status,
        artifact_doctor_blockers=tuple(artifact_doctor.blockers),
        feedback_readiness_ready=feedback_ready,
        feedback_readiness_blockers=() if feedback_ready else tuple(feedback_readiness.blockers),
        blockers=clean_blockers,
        warnings=tuple(dict.fromkeys(str(item) for item in warnings if str(item))),
        review_commands=commands,
    )


def _feedback_readiness_visible_core_ready(
    result: event_alpha_feedback_readiness.EventAlphaFeedbackReadinessResult,
) -> bool:
    """Treat current visible core coverage as the burn-in reviewability source."""
    if result.ready:
        return True
    if result.cards_checked and result.cards_with_lineage < result.cards_checked:
        return False
    if result.cards_checked and result.cards_with_feedback_target < result.cards_checked:
        return False
    if result.alert_rows_checked and result.alert_rows_with_feedback_targets < result.alert_rows_checked:
        return False
    if result.visible_core_opportunities:
        return (
            result.visible_core_opportunities_missing_cards <= 0
            and result.visible_core_opportunities_missing_feedback_targets <= 0
            and result.visible_core_opportunities_with_cards >= result.visible_core_opportunities
            and result.visible_core_opportunities_with_feedback_targets >= result.visible_core_opportunities
        )
    return False


def format_burn_in_readiness(result: EventAlphaBurnInReadinessResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA LIVE-STYLE BURN-IN READINESS (research-only; no-send)",
        "=" * 76,
        f"READY_FOR_NO_SEND_BURN_IN_REVIEW: {'yes' if result.ready else 'no'}",
        f"profile: {result.profile}",
        f"artifact_namespace: {result.artifact_namespace}",
        f"latest_run_id: {result.latest_run_id or 'none'}",
        f"run_completed: {str(result.run_completed).lower()}",
        f"no_send_confirmed: {str(result.no_send_confirmed).lower()}",
        (
            "provider_coverage: "
            f"configured={result.provider_configured} not_configured={result.provider_not_configured} "
            f"event_sources_ready={result.provider_ready_event_sources} "
            f"enrichment_ready={result.provider_ready_enrichment_sources}"
        ),
        (
            "artifacts: "
            f"core_opportunities={result.core_opportunities} "
            f"cards={result.cards_checked} feedback_targets={result.feedback_targets} "
            f"evidence_acquisition_rows={result.evidence_acquisition_rows} "
            f"evidence_acquisition_attempted={result.evidence_acquisition_attempted} "
            f"market_freshness_visible={str(result.market_freshness_visible).lower()}"
        ),
        (
            "checks: "
            f"artifact_doctor={result.artifact_doctor_status} "
            f"feedback_readiness={str(result.feedback_readiness_ready).lower()}"
        ),
        "",
        "blockers:",
    ]
    lines.extend(f"- {item}" for item in result.blockers) if result.blockers else lines.append("- none")
    lines.append("")
    lines.append("warnings:")
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- none")
    lines.append("")
    lines.append("manual review checklist:")
    lines.append("- inspect provider gaps and decide whether missing sources make absence evidence meaningful")
    lines.append("- review daily brief Strong/Validated/Watchlist/Near-Miss sections")
    lines.append("- open research cards and mark useful/junk/watch feedback")
    lines.append("- keep sends disabled until the no-send run has reviewable cards and no strict doctor blockers")
    lines.append("")
    lines.append("review commands:")
    lines.extend(f"- {command}" for command in result.review_commands)
    lines.append("Readiness report is artifact-only; it sends nothing and changes no alert/trading state.")
    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# Moved from crypto_rsi_scanner/event_alpha_burn_in_pack.py
# ---------------------------------------------------------------------------
"""Clean burn-in export pack for Event Alpha research review."""


import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..artifacts import context as event_alpha_artifacts


@dataclass(frozen=True)
class EventAlphaBurnInPackResult:
    path: Path
    files_written: int
    warnings: tuple[str, ...] = ()


REPORTS = {
    "daily_brief": "reports/daily_brief.md",
    "burn_in_scorecard": "reports/burn_in_scorecard.txt",
    "burn_in_checklist": "reports/burn_in_checklist.txt",
    "v1_readiness": "reports/v1_readiness.txt",
    "health_guard": "reports/health_guard.txt",
    "artifact_doctor": "reports/artifact_doctor.txt",
    "source_reliability": "reports/source_reliability.txt",
    "calibration": "reports/calibration.txt",
    "missed": "reports/missed_opportunities.txt",
    "tuning": "reports/tuning_worksheet.txt",
    "priors_shadow": "reports/priors_shadow.txt",
}


def export_burn_in_pack(
    out_path: str | Path,
    *,
    daily_brief: str = "",
    burn_in_scorecard: str = "",
    burn_in_checklist: str = "",
    v1_readiness: str = "",
    health_guard: str = "",
    artifact_doctor: str = "",
    source_reliability: str = "",
    calibration: str = "",
    missed: str = "",
    tuning: str = "",
    priors_shadow: str = "",
    run_rows: Iterable[Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
    outcome_rows: Iterable[Mapping[str, Any]] = (),
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    llm_budget_rows: Iterable[Mapping[str, Any]] = (),
    cards_dir: str | Path | None = None,
    proposed_eval_dir: str | Path | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
    include_legacy_artifacts: bool = False,
    date_range: str | None = None,
) -> EventAlphaBurnInPackResult:
    """Write a clean zip for Pro-model/local review without secrets or caches."""
    target = Path(out_path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    files = 0
    run_data = _filtered(run_rows, profile, artifact_namespace, include_test_artifacts, include_legacy_artifacts)
    alert_data = _filtered(alert_rows, profile, artifact_namespace, include_test_artifacts, include_legacy_artifacts)
    feedback_data = _filtered(feedback_rows, profile, artifact_namespace, include_test_artifacts, include_legacy_artifacts)
    missed_data = _filtered(missed_rows, profile, artifact_namespace, include_test_artifacts, include_legacy_artifacts)
    outcome_data = _filtered(outcome_rows, profile, artifact_namespace, include_test_artifacts, include_legacy_artifacts)
    budget_data = _filtered(llm_budget_rows, profile, artifact_namespace, include_test_artifacts, include_legacy_artifacts)
    manifest = {
        "profile": profile or "any",
        "artifact_namespace": artifact_namespace or "any",
        "date_range": date_range or "unspecified",
        "include_test_artifacts": bool(include_test_artifacts),
        "include_legacy_artifacts": bool(include_legacy_artifacts),
        "run_rows": len(run_data),
        "alert_rows": len(alert_data),
        "feedback_rows": len(feedback_data),
        "missed_rows": len(missed_data),
        "outcome_rows": len(outcome_data),
    }
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        _writestr(zf, "manifest.json", json.dumps(_json_ready(manifest), indent=2, sort_keys=True) + "\n")
        files += 1
        for name, arcname in REPORTS.items():
            text = locals().get(name) or f"{name} report not available in this export.\n"
            _writestr(zf, arcname, _strip_sensitive(str(text).rstrip() + "\n"))
            files += 1
        artifacts = {
            "artifacts/run_rows.jsonl": run_data,
            "artifacts/alert_rows.jsonl": alert_data,
            "artifacts/feedback_rows.jsonl": feedback_data,
            "artifacts/missed_rows.jsonl": missed_data,
            "artifacts/outcome_rows.jsonl": outcome_data,
            "artifacts/llm_budget_rows.jsonl": budget_data,
        }
        for arcname, rows in artifacts.items():
            _write_jsonl(zf, arcname, rows)
            files += 1
        _writestr(
            zf,
            "artifacts/provider_health.json",
            json.dumps(_json_ready(provider_health_rows or {}), indent=2, sort_keys=True) + "\n",
        )
        files += 1
        files += _write_tree(zf, cards_dir, root_arc="cards", warnings=warnings)
        files += _write_tree(zf, proposed_eval_dir, root_arc="proposed_eval_cases", warnings=warnings)
        _writestr(zf, "README.md", _readme())
        files += 1
    return EventAlphaBurnInPackResult(path=target, files_written=files, warnings=tuple(dict.fromkeys(warnings)))


def _filtered(
    rows: Iterable[Mapping[str, Any]],
    profile: str | None,
    artifact_namespace: str | None,
    include_test_artifacts: bool,
    include_legacy_artifacts: bool,
) -> list[dict[str, Any]]:
    return event_alpha_artifacts.filter_artifact_rows(
        rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
        include_legacy_artifacts=include_legacy_artifacts,
    )


def format_burn_in_pack_result(result: EventAlphaBurnInPackResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA BURN-IN PACK WRITTEN (research artifact only)",
        "=" * 76,
        f"path: {result.path}",
        f"files_written: {result.files_written}",
    ]
    if result.warnings:
        lines.extend(["warnings:", *(f"- {warning}" for warning in result.warnings)])
    lines.append("Export excludes secrets, DB files, logs, caches, virtualenvs, and raw ignored artifacts.")
    return "\n".join(lines).rstrip()


def _write_tree(
    zf: zipfile.ZipFile,
    root: str | Path | None,
    *,
    root_arc: str,
    warnings: list[str],
) -> int:
    if not root:
        return 0
    base = Path(root).expanduser()
    if not base.exists():
        warnings.append(f"{root_arc} source not found: {base}")
        return 0
    count = 0
    for path in sorted(base.rglob("*")):
        if not path.is_file() or not _safe_file(path):
            continue
        try:
            data = _strip_sensitive(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            warnings.append(f"skipped non-text artifact: {path.name}")
            continue
        rel = path.relative_to(base)
        _writestr(zf, str(Path(root_arc) / rel), data)
        count += 1
    return count


def _safe_file(path: Path) -> bool:
    parts = set(path.parts)
    if parts & {".git", ".venv", "__pycache__", ".pytest_cache", "event_fade_cache", "backups"}:
        return False
    name = path.name
    if name.startswith(".env") or name == ".DS_Store":
        return False
    if name.endswith((".db", ".db-wal", ".db-shm", ".log", ".pyc", ".zip")):
        return False
    return path.suffix.lower() in {".md", ".txt", ".json", ".jsonl", ".csv"}


def _write_jsonl(zf: zipfile.ZipFile, arcname: str, rows: Iterable[Mapping[str, Any]]) -> None:
    lines = [
        json.dumps(_json_ready(dict(row)), sort_keys=True, separators=(",", ":"))
        for row in rows
        if isinstance(row, Mapping)
    ]
    _writestr(zf, arcname, "\n".join(lines) + ("\n" if lines else ""))


def _writestr(zf: zipfile.ZipFile, arcname: str, text: str) -> None:
    info = zipfile.ZipInfo(arcname)
    info.date_time = (2026, 1, 1, 0, 0, 0)
    info.compress_type = zipfile.ZIP_DEFLATED
    zf.writestr(info, _strip_sensitive(text))


def _strip_sensitive(text: str) -> str:
    out = str(text)
    replacements = {
        "OPENAI_API_KEY": "[redacted-openai-key-name]",
        "TELEGRAM_BOT_TOKEN": "[redacted-telegram-token-name]",
        "DISCORD_WEBHOOK_URL": "[redacted-discord-webhook-name]",
        ".env": "[env-file]",
    }
    for old, new in replacements.items():
        out = out.replace(old, new)
    return out


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _readme() -> str:
    return (
        "# Event Alpha Burn-In Pack\n\n"
        "This zip contains clean Event Alpha research reports and small local "
        "artifact excerpts for review. It is research-only: no live RSI signal "
        "rows, paper trades, execution state, secrets, local DBs, logs, caches, "
        "or virtualenv files are included.\n"
    )
