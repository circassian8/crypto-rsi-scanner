"""Scoped doctor for a single daily burn-in namespace."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from ..doctor.checks import operations as operation_doctor_checks
from . import common

SCOPED_DOCTOR_JSON = "event_alpha_daily_burn_in_doctor_status.json"
SCOPED_DOCTOR_MD = "event_alpha_daily_burn_in_doctor_status.md"


def run_scoped_doctor(
    *,
    profile: str,
    artifact_namespace: str,
    base_dir: str | Path | None = None,
) -> dict[str, Any]:
    from . import daily_burn_in

    context = common.context_for(profile=profile, artifact_namespace=artifact_namespace, base_dir=base_dir)
    blockers: list[str] = []
    warnings: list[str] = []
    ctx = SimpleNamespace(
        profile=profile,
        artifact_namespace=artifact_namespace,
        namespace_dir=context.namespace_dir,
        namespace_status=None,
        daily_burn_in_run=common.read_json(context.namespace_dir / daily_burn_in.RUN_JSON),
        candidate_mode_manifest=common.read_json(context.namespace_dir / daily_burn_in.CANDIDATE_MODE_MANIFEST_JSON),
        burn_in_scorecard=common.read_json(context.namespace_dir / "event_alpha_burn_in_scorecard.json"),
        source_yield_report=common.read_json(context.namespace_dir / "event_alpha_source_yield_report.json"),
        daily_review_inbox=common.read_json(context.namespace_dir / "event_alpha_daily_review_inbox.json"),
        burn_in_archive_manifest=common.read_json(context.namespace_dir / "event_alpha_burn_in_archive_manifest.json"),
        integrated_candidates=common.read_jsonl(context.namespace_dir / "event_integrated_radar_candidates.jsonl"),
        integrated_conflicts={},
    )
    operation_doctor_checks.apply_checks(ctx, blockers, warnings)
    status = "BLOCK" if blockers else ("WARN" if warnings else "OK")
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_daily_burn_in_doctor_status_v1",
            "row_type": "event_alpha_daily_burn_in_doctor_status",
            "generated_at": common.utc_now().isoformat(),
            "profile": profile,
            "artifact_namespace": artifact_namespace,
            "namespace_dir": common.rel_path(context.namespace_dir),
            "doctor_mode": "scoped_burn_in",
            "scoped_to_current_namespace": True,
            "status": status,
            "blockers": blockers,
            "warnings": warnings,
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
        }
    )
    write_doctor_status(context, payload)
    return payload


def write_doctor_status(context: Any, payload: Mapping[str, Any]) -> None:
    common.write_json(context.namespace_dir / SCOPED_DOCTOR_JSON, payload)
    lines = [
        "# Event Alpha Daily Burn-In Scoped Doctor",
        "",
        f"- status: `{payload.get('status')}`",
        f"- doctor_mode: `{payload.get('doctor_mode')}`",
        f"- scoped_to_current_namespace: `{payload.get('scoped_to_current_namespace')}`",
        f"- blockers: `{len(payload.get('blockers') or [])}`",
        f"- warnings: `{len(payload.get('warnings') or [])}`",
    ]
    if payload.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {item}" for item in payload.get("blockers") or [])
    if payload.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in payload.get("warnings") or [])
    common.write_text(context.namespace_dir / SCOPED_DOCTOR_MD, "\n".join(lines))
