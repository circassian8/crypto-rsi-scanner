"""Live-style no-send burn-in readiness checks for Event Alpha."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import (
    event_alpha_artifact_doctor,
    event_alpha_feedback_readiness,
    event_alpha_run_ledger,
    event_provider_status,
)


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
