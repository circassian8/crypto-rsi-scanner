"""Doctor report for Event Alpha local research artifact consistency."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_alpha_artifacts


@dataclass(frozen=True)
class EventAlphaArtifactDoctorResult:
    status: str
    profile: str | None
    artifact_namespace: str | None
    run_rows: int
    alert_rows: int
    feedback_rows: int
    outcome_rows: int
    card_files: int
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def diagnose_artifacts(
    *,
    run_rows: Iterable[Mapping[str, Any]] = (),
    alert_rows: Iterable[Mapping[str, Any]] = (),
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    outcome_rows: Iterable[Mapping[str, Any]] = (),
    card_paths: Iterable[str | Path] = (),
    provider_health_rows: Mapping[str, Mapping[str, Any]] | None = None,
    llm_budget_rows: Iterable[Mapping[str, Any]] = (),
    profile: str | None = None,
    artifact_namespace: str | None = None,
    include_test_artifacts: bool = False,
) -> EventAlphaArtifactDoctorResult:
    """Diagnose cross-artifact lineage, mode, and profile/namespace cleanliness."""
    runs = event_alpha_artifacts.filter_artifact_rows(
        run_rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
    )
    alerts = event_alpha_artifacts.filter_artifact_rows(
        alert_rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
    )
    feedback = event_alpha_artifacts.filter_artifact_rows(
        feedback_rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
    )
    outcomes = event_alpha_artifacts.filter_artifact_rows(
        outcome_rows,
        profile=profile,
        artifact_namespace=artifact_namespace,
        include_test_artifacts=include_test_artifacts,
    )
    blockers: list[str] = []
    warnings: list[str] = []
    if not runs:
        blockers.append("no matching operational/burn-in run rows found")
    run_ids = {str(row.get("run_id") or "") for row in runs if row.get("run_id")}
    alert_run_ids = {str(row.get("run_id") or "") for row in alerts if row.get("run_id")}
    for row in runs:
        if event_alpha_artifacts.is_non_operational_row(row) and not include_test_artifacts:
            continue
        if int(row.get("alertable") or 0) > 0 and not bool(row.get("snapshot_write_success")):
            if str(row.get("snapshot_write_block_reason") or "") == "test_or_fixture_run":
                warnings.append(f"run {row.get('run_id') or 'unknown'} is test/fixture and skipped snapshots")
            else:
                blockers.append(f"alertable run {row.get('run_id') or 'unknown'} has no successful snapshot write")
        elif int(row.get("alertable") or 0) > 0 and int(row.get("snapshot_rows_written") or 0) <= 0:
            blockers.append(f"alertable run {row.get('run_id') or 'unknown'} wrote zero alert snapshots")
    orphan_alerts = sorted(alert_run_ids - run_ids)
    if orphan_alerts:
        warnings.append(f"alert snapshots reference unknown run_id(s): {', '.join(orphan_alerts[:5])}")
    if any(row.get("run_id") in (None, "") for row in alerts):
        warnings.append("legacy alert snapshots without run_id lineage are present")
    alert_keys = {str(row.get("alert_key") or "") for row in alerts if row.get("alert_key")}
    feedback_keys = {str(row.get("key") or row.get("alert_key") or "") for row in feedback}
    outcome_keys = {str(row.get("alert_key") or "") for row in outcomes}
    unknown_feedback = sorted(key for key in feedback_keys if key and key not in alert_keys)
    unknown_outcomes = sorted(key for key in outcome_keys if key and key not in alert_keys)
    if unknown_feedback:
        warnings.append(f"feedback without matching alert snapshot: {', '.join(unknown_feedback[:5])}")
    if unknown_outcomes:
        warnings.append(f"outcomes without matching alert snapshot: {', '.join(unknown_outcomes[:5])}")
    namespaces = {
        event_alpha_artifacts.row_namespace(row)
        for row in (*runs, *alerts, *feedback, *outcomes)
    }
    profiles = {
        event_alpha_artifacts.row_profile(row)
        for row in (*runs, *alerts, *feedback, *outcomes)
    }
    if artifact_namespace and any(ns not in {artifact_namespace, "legacy"} for ns in namespaces):
        blockers.append("mixed artifact namespaces after filtering")
    elif len(namespaces - {"legacy"}) > 1:
        warnings.append("multiple artifact namespaces present")
    if profile and any(item not in {profile, "default"} for item in profiles):
        warnings.append("rows from multiple profiles are present")
    if provider_health_rows is not None and profile in {"no_key_live", "api_live", "full_llm_live", "research_send"}:
        if not provider_health_rows:
            warnings.append("provider health rows missing for live/burn-in profile")
    if profile in {"full_llm_live", "no_key_llm"} and not list(llm_budget_rows):
        warnings.append("LLM budget rows missing for LLM profile")
    card_count = len([Path(path) for path in card_paths])
    if alerts and not card_count and any(str(row.get("tier") or "") in {"HIGH_PRIORITY_WATCH", "TRIGGERED_FADE"} for row in alerts):
        warnings.append("high-priority/triggered snapshots exist but no research cards were found")
    status = "BLOCKED" if blockers else ("WARN" if warnings else "OK")
    return EventAlphaArtifactDoctorResult(
        status=status,
        profile=profile,
        artifact_namespace=artifact_namespace,
        run_rows=len(runs),
        alert_rows=len(alerts),
        feedback_rows=len(feedback),
        outcome_rows=len(outcomes),
        card_files=card_count,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def format_artifact_doctor_report(result: EventAlphaArtifactDoctorResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA ARTIFACT DOCTOR (research artifact only)",
        "=" * 76,
        f"status: {result.status}",
        f"profile: {result.profile or 'any'}",
        f"namespace: {result.artifact_namespace or 'any'}",
        (
            "rows: "
            f"runs={result.run_rows} alerts={result.alert_rows} "
            f"feedback={result.feedback_rows} outcomes={result.outcome_rows} cards={result.card_files}"
        ),
        "",
        "blockers:",
    ]
    lines.extend(f"- {item}" for item in result.blockers) if result.blockers else lines.append("- none")
    lines.extend(["", "warnings:"])
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- none")
    lines.append("Doctor reports artifact hygiene only; it does not send, trade, paper trade, or alter tiers.")
    return "\n".join(lines).rstrip()
