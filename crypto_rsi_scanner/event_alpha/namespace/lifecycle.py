"""Event Alpha artifact namespace lifecycle inventory.

The lifecycle layer is intentionally read-mostly. It classifies namespaces,
writes operator inventory reports, and returns dry-run archive plans without
deleting or moving artifacts.
"""

from __future__ import annotations

import json
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

from ..artifacts import paths as event_artifact_paths
from ..artifacts import locks as event_alpha_locks
from ..artifacts import operator_state as event_alpha_operator_state
from . import status as event_alpha_namespace_status


REGISTRY_FILENAME = "event_alpha_namespace_registry.json"
REPORT_FILENAME = "event_alpha_namespace_lifecycle_report.md"

STATUS_ACTIVE_LIVE_REHEARSAL = "active_live_rehearsal"
STATUS_ACTIVE_FIXTURE_SMOKE = "active_fixture_smoke"
STATUS_ACTIVE_PROVIDER_PREFLIGHT = "active_provider_preflight"
STATUS_ACTIVE_PROVIDER_REHEARSAL = "active_provider_rehearsal"
STATUS_ACTIVE_INTEGRATED_SMOKE = "active_integrated_smoke"
STATUS_ACTIVE_ARCHITECTURE_REPORT = "active_architecture_report"
STATUS_MANUAL_REVIEW = "manual_review"
STATUS_STALE_DEPRECATED = "stale_deprecated"
STATUS_ARCHIVED = "archived"
STATUS_QUARANTINE = "quarantine"
STATUS_UNKNOWN = "unknown"

KNOWN_STALE_NAMESPACES = {
    "notify_llm_deep": {
        "reason": "pre-canonical notify_llm_deep artifacts; superseded by current rehearsal namespaces",
        "superseded_by": "notify_llm_deep_cryptopanic_rehearsal, notify_llm_deep_fixture_rehearsal, integrated_radar_smoke",
    },
}

# Root-local support stores can sit beside generation namespaces when a legacy
# or unscoped artifact path is in use.  They are retained research evidence,
# never operator generations, and therefore must not be treated as an unknown
# namespace or as eligible authority.
NON_GENERATION_ARTIFACT_ROOTS = {
    "decision_radar_research_lab": (
        "immutable Decision Radar empirical replay and report store; not an operator generation"
    ),
    "event_source_independence_contracts": (
        "immutable digest-addressed source-independence store; not an operator generation"
    ),
}


@dataclass(frozen=True)
class NamespaceLifecycleRow:
    namespace: str
    status: str
    profile: str
    created_at: str | None
    last_updated_at: str | None
    last_verified_at: str | None
    safe_for_send_readiness: bool
    safe_for_burn_in_measurement: bool
    safe_for_calibration: bool
    superseded_by: str | None
    retention_policy: str
    archive_after_days: int | None
    prune_after_days: int | None
    reason: str | None
    owner_note: str | None
    current_doctor_status: str
    latest_run_id: str | None
    artifact_counts: dict[str, int]
    key_artifacts_present: list[str]
    missing_key_artifacts: list[str]
    readiness_required: bool
    readiness_present: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_type": "event_alpha_namespace_lifecycle",
            "namespace": self.namespace,
            "status": self.status,
            "profile": self.profile,
            "created_at": self.created_at,
            "last_updated_at": self.last_updated_at,
            "last_verified_at": self.last_verified_at,
            "safe_for_send_readiness": self.safe_for_send_readiness,
            "safe_for_burn_in_measurement": self.safe_for_burn_in_measurement,
            "safe_for_calibration": self.safe_for_calibration,
            "superseded_by": self.superseded_by,
            "retention_policy": self.retention_policy,
            "archive_after_days": self.archive_after_days,
            "prune_after_days": self.prune_after_days,
            "reason": self.reason,
            "owner_note": self.owner_note,
            "current_doctor_status": self.current_doctor_status,
            "latest_run_id": self.latest_run_id,
            "artifact_counts": self.artifact_counts,
            "key_artifacts_present": self.key_artifacts_present,
            "missing_key_artifacts": self.missing_key_artifacts,
            "readiness_required": self.readiness_required,
            "readiness_present": self.readiness_present,
        }


def build_namespace_registry(
    base_dir: str | Path | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    base = _resolve_base_dir(base_dir)
    generated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    rows = [row.to_dict() for row in _namespace_rows(base)]
    return {
        "schema_version": "event_alpha_namespace_lifecycle_v1",
        "row_type": "event_alpha_namespace_registry",
        "generated_at": generated_at,
        "base_dir": event_artifact_paths.artifact_display_path(base),
        "namespace_count": len(rows),
        "status_counts": _status_counts(rows),
        "safe_for_send_readiness_count": sum(1 for row in rows if row.get("safe_for_send_readiness")),
        "namespaces": rows,
    }


def write_namespace_lifecycle_report(
    base_dir: str | Path | None = None,
    *,
    out_dir: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    base = _resolve_base_dir(base_dir)
    target_dir = Path(out_dir).expanduser() if out_dir is not None else base
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = now or datetime.now(timezone.utc)
    with ExitStack() as stack:
        base_lock = stack.enter_context(
            event_alpha_locks.artifact_mutation_guard(
                SimpleNamespace(namespace_dir=base),
                namespace=base.name,
                command="namespace-lifecycle-report",
                now=timestamp,
            )
        )
        if not base_lock.owned:
            raise RuntimeError(f"namespace lifecycle report blocked for {base.name}: {base_lock.status.message}")
        child_dirs = _lifecycle_child_dirs(base)
        for namespace_dir in child_dirs:
            mutation_lock = stack.enter_context(
                event_alpha_locks.artifact_mutation_guard(
                    SimpleNamespace(namespace_dir=namespace_dir),
                    namespace=namespace_dir.name,
                    command="namespace-lifecycle-report",
                    now=timestamp,
                )
            )
            if not mutation_lock.owned:
                raise RuntimeError(
                    f"namespace lifecycle report blocked for {namespace_dir.name}: "
                    f"{mutation_lock.status.message}"
                )
        if _lifecycle_child_dirs(base) != child_dirs:
            raise RuntimeError("namespace lifecycle report blocked: namespace set changed while locks were acquired")
        registry = build_namespace_registry(base, now=timestamp)
        _write_namespace_status_markers(base, registry, now=timestamp)
        registry = build_namespace_registry(base, now=timestamp)
        registry_path = target_dir / REGISTRY_FILENAME
        report_path = target_dir / REPORT_FILENAME
        registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report_path.write_text(format_namespace_lifecycle_report(registry), encoding="utf-8")
    out = dict(registry)
    out["registry_path"] = event_artifact_paths.artifact_display_path(registry_path)
    out["report_path"] = event_artifact_paths.artifact_display_path(report_path)
    return out


def _lifecycle_child_dirs(base: Path) -> tuple[Path, ...]:
    return tuple(sorted(path for path in base.iterdir() if path.is_dir())) if base.exists() else ()


def format_namespace_lifecycle_report(registry: dict[str, Any]) -> str:
    lines = [
        "# Event Alpha Namespace Lifecycle",
        "",
        "Research artifact inventory only. This report does not send alerts, call providers, write RSI signal rows, or create TRIGGERED_FADE.",
        "",
        f"- generated_at: {registry.get('generated_at')}",
        f"- base_dir: {registry.get('base_dir')}",
        f"- namespace_count: {registry.get('namespace_count', 0)}",
        f"- status_counts: {json.dumps(registry.get('status_counts', {}), sort_keys=True)}",
        "",
        "## Namespaces",
        "",
        "| namespace | status | send-ready | key artifacts | missing | reason |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in sorted(registry.get("namespaces", []), key=lambda item: str(item.get("namespace") or "")):
        present = len(row.get("key_artifacts_present") or [])
        missing = len(row.get("missing_key_artifacts") or [])
        lines.append(
            "| "
            f"{row.get('namespace')} | "
            f"{row.get('status')} | "
            f"{str(bool(row.get('safe_for_send_readiness'))).lower()} | "
            f"{present} | "
            f"{missing} | "
            f"{row.get('reason') or ''} |"
        )
    lines.extend(
        [
            "",
            "## Active Doctor Status",
            "",
            "| namespace | status | current doctor | last verified | retention |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for row in sorted(registry.get("namespaces", []), key=lambda item: str(item.get("namespace") or "")):
        lines.append(
            "| "
            f"{row.get('namespace')} | "
            f"{row.get('status')} | "
            f"{row.get('current_doctor_status') or 'unknown'} | "
            f"{row.get('last_verified_at') or 'unknown'} | "
            f"{row.get('retention_policy') or 'manual_review'} |"
        )
    lines.extend(
        [
            "",
            "## Policy",
            "",
            "- Stale namespaces are never safe for send readiness.",
            "- Fixture smoke namespaces are local validation artifacts, not burn-in or calibration sources.",
            "- Provider preflight and rehearsal namespaces are no-send/provider-readiness artifacts.",
            "- Archive actions are dry-run plans until a future explicit retention pass implements movement/deletion.",
            "",
        ]
    )
    return "\n".join(lines)


def list_active_namespaces(base_dir: str | Path | None = None) -> tuple[dict[str, Any], ...]:
    registry = build_namespace_registry(base_dir)
    return tuple(
        row
        for row in registry["namespaces"]
        if str(row.get("status") or "") not in {STATUS_STALE_DEPRECATED, STATUS_ARCHIVED, STATUS_QUARANTINE}
    )


def archive_stale_namespaces_plan(
    base_dir: str | Path | None = None,
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    base = _resolve_base_dir(base_dir)
    registry = build_namespace_registry(base)
    stale_rows = [row for row in registry["namespaces"] if row.get("status") == STATUS_STALE_DEPRECATED]
    plans = []
    for row in stale_rows:
        namespace_dir = base / str(row["namespace"])
        plans.append(event_alpha_namespace_status.stale_namespace_plan(namespace_dir, archive=True))
    return {
        "schema_version": "event_alpha_namespace_archive_plan_v1",
        "base_dir": event_artifact_paths.artifact_display_path(base),
        "dry_run": True,
        "requested_dry_run": bool(dry_run),
        "archive_performed": False,
        "stale_namespace_count": len(stale_rows),
        "plans": plans,
    }


def _namespace_rows(base: Path) -> tuple[NamespaceLifecycleRow, ...]:
    if not base.exists():
        return ()
    rows: list[NamespaceLifecycleRow] = []
    for namespace_dir in sorted(path for path in base.iterdir() if path.is_dir()):
        rows.append(_namespace_row(namespace_dir))
    return tuple(rows)


def _namespace_row(namespace_dir: Path) -> NamespaceLifecycleRow:
    namespace = namespace_dir.name
    marker = event_alpha_namespace_status.load_namespace_status(namespace_dir)
    status, reason, superseded_by = _classify_namespace(namespace, marker)
    artifact_counts = _artifact_counts(namespace_dir)
    operator_state = event_alpha_operator_state.load_operator_state(namespace_dir)
    key_artifacts = _key_artifacts_for_status(namespace, status, current_generation=operator_state.exists)
    present = [name for name in key_artifacts if (namespace_dir / name).exists()]
    missing = [name for name in key_artifacts if not (namespace_dir / name).exists()]
    readiness_required = status in {
        STATUS_ACTIVE_LIVE_REHEARSAL,
        STATUS_ACTIVE_PROVIDER_PREFLIGHT,
        STATUS_ACTIVE_PROVIDER_REHEARSAL,
        STATUS_ACTIVE_INTEGRATED_SMOKE,
    }
    readiness_present = any(
        (namespace_dir / name).exists()
        for name in (
            "event_live_provider_activation_readiness.json",
            "event_coinalyze_preflight.json",
            "event_bybit_announcements_preflight.json",
            "event_alpha_source_coverage.json",
        )
    )
    created_at, updated_at = _mtime_window(namespace_dir)
    stale = status in {STATUS_STALE_DEPRECATED, STATUS_ARCHIVED, STATUS_QUARANTINE}
    current_doctor_status = _current_doctor_status(namespace_dir, marker)
    doctor_current = current_doctor_status in {"OK", "WARN"}
    active_live = status == STATUS_ACTIVE_LIVE_REHEARSAL
    safe_for_send = bool(marker and marker.safe_for_send_readiness) and active_live and doctor_current
    safe_for_burn_in = bool(marker and marker.safe_for_burn_in_measurement) and active_live and doctor_current
    safe_for_calibration = bool(marker and marker.safe_for_calibration) and active_live and doctor_current
    return NamespaceLifecycleRow(
        namespace=namespace,
        status=status,
        profile=_profile_for_namespace(namespace, status),
        created_at=created_at,
        last_updated_at=updated_at,
        last_verified_at=(marker.last_verified_at if marker else None) or (marker.marked_at if marker else None),
        safe_for_send_readiness=safe_for_send,
        safe_for_burn_in_measurement=safe_for_burn_in,
        safe_for_calibration=safe_for_calibration,
        superseded_by=superseded_by,
        retention_policy=_retention_policy(status),
        archive_after_days=30 if stale else 90,
        prune_after_days=None if not stale else 180,
        reason=reason,
        owner_note="research-only namespace lifecycle inventory",
        current_doctor_status=current_doctor_status,
        latest_run_id=_latest_run_id(namespace_dir),
        artifact_counts=artifact_counts,
        key_artifacts_present=present,
        missing_key_artifacts=missing,
        readiness_required=readiness_required,
        readiness_present=readiness_present,
    )


def _classify_namespace(
    namespace: str,
    marker: event_alpha_namespace_status.EventAlphaNamespaceStatus | None,
) -> tuple[str, str | None, str | None]:
    if marker and marker.status in {
        STATUS_ACTIVE_LIVE_REHEARSAL,
        STATUS_ACTIVE_FIXTURE_SMOKE,
        STATUS_ACTIVE_PROVIDER_PREFLIGHT,
        STATUS_ACTIVE_PROVIDER_REHEARSAL,
        STATUS_ACTIVE_INTEGRATED_SMOKE,
        STATUS_ACTIVE_ARCHITECTURE_REPORT,
        STATUS_MANUAL_REVIEW,
        STATUS_STALE_DEPRECATED,
        STATUS_ARCHIVED,
        STATUS_QUARANTINE,
    }:
        return marker.status, marker.reason, marker.superseded_by
    if namespace in KNOWN_STALE_NAMESPACES:
        known = KNOWN_STALE_NAMESPACES[namespace]
        return STATUS_STALE_DEPRECATED, known["reason"], known["superseded_by"]
    if namespace in NON_GENERATION_ARTIFACT_ROOTS:
        return STATUS_MANUAL_REVIEW, NON_GENERATION_ARTIFACT_ROOTS[namespace], None
    if namespace in {"shim_report", "architecture_final_report", "architecture_baseline"}:
        return STATUS_ACTIVE_ARCHITECTURE_REPORT, "architecture/report namespace", None
    if namespace in {
        "catalyst_frame_e2e",
        "catalyst_frame_validation",
        "quality_validation",
        "research_send",
        "source_enrichment",
    }:
        return STATUS_MANUAL_REVIEW, "manual review or validation namespace", None
    if namespace.startswith("tmp_") or namespace.endswith("_cli_test"):
        return STATUS_QUARANTINE, "temporary test namespace; not part of active lifecycle", None
    if namespace == "integrated_radar_smoke":
        return STATUS_ACTIVE_INTEGRATED_SMOKE, "integrated fixture smoke namespace", None
    if namespace.endswith("_smoke") or "_smoke" in namespace:
        return STATUS_ACTIVE_FIXTURE_SMOKE, "fixture smoke namespace", None
    if "preflight" in namespace and "rehearsal" not in namespace:
        return STATUS_ACTIVE_PROVIDER_PREFLIGHT, "provider preflight namespace", None
    if "rehearsal" in namespace:
        return STATUS_ACTIVE_PROVIDER_REHEARSAL, "provider no-send rehearsal namespace", None
    if namespace == "radar_market_history_cache":
        return STATUS_ACTIVE_LIVE_REHEARSAL, "shared live/no-send market observation history", None
    if namespace.startswith("radar_bybit_liquidation_transcript_"):
        return (
            STATUS_MANUAL_REVIEW,
            "detached operator liquidation application-payload transcript",
            None,
        )
    if namespace.startswith("radar_tokenomist_v5_"):
        return (
            STATUS_MANUAL_REVIEW,
            "detached synthetic Tokenomist v5 fixture capture",
            None,
        )
    if namespace.startswith("radar_market_no_send"):
        return STATUS_ACTIVE_LIVE_REHEARSAL, "Decision Radar live/no-send observation generation", None
    if "burn_in" in namespace or namespace.startswith("notify_") or namespace.endswith("_live"):
        return STATUS_ACTIVE_LIVE_REHEARSAL, "active no-send live rehearsal namespace", None
    return STATUS_UNKNOWN, "namespace does not match a known lifecycle pattern", None


def _profile_for_namespace(namespace: str, status: str) -> str:
    if status in {STATUS_ACTIVE_FIXTURE_SMOKE, STATUS_ACTIVE_INTEGRATED_SMOKE}:
        return "fixture"
    if status == STATUS_ACTIVE_ARCHITECTURE_REPORT:
        return "architecture"
    if status == STATUS_MANUAL_REVIEW:
        return "manual_review"
    if namespace.startswith("notify_llm_deep"):
        return "notify_llm_deep"
    if namespace.startswith("notify_llm"):
        return "notify_llm"
    if namespace.startswith("notify_no_key"):
        return "notify_no_key"
    return namespace


def _retention_policy(status: str) -> str:
    if status == STATUS_STALE_DEPRECATED:
        return "audit_then_archive"
    if status in {STATUS_ACTIVE_FIXTURE_SMOKE, STATUS_ACTIVE_INTEGRATED_SMOKE}:
        return "keep_latest_fixture_artifacts"
    if status == STATUS_ACTIVE_ARCHITECTURE_REPORT:
        return "keep_latest_architecture_reports"
    if status == STATUS_MANUAL_REVIEW:
        return "manual_review"
    if status in {STATUS_ACTIVE_PROVIDER_PREFLIGHT, STATUS_ACTIVE_PROVIDER_REHEARSAL}:
        return "keep_recent_provider_artifacts"
    if status == STATUS_ACTIVE_LIVE_REHEARSAL:
        return "retain_for_burn_in_review"
    return "manual_review"


def _key_artifacts_for_status(
    namespace: str,
    status: str,
    *,
    current_generation: bool = False,
) -> tuple[str, ...]:
    if status == STATUS_ACTIVE_INTEGRATED_SMOKE:
        legacy = (
            "event_integrated_radar_candidates.jsonl",
            "event_core_opportunities.jsonl",
            "event_alpha_source_coverage.json",
        )
        if not current_generation:
            return legacy
        return (
            event_alpha_operator_state.OPERATOR_STATE_FILENAME,
            *legacy,
            "event_live_provider_activation_readiness.json",
            "event_alpha_daily_brief.md",
            "event_alpha_notification_preview.md",
            "research_cards/index.md",
        )
    if status == STATUS_ACTIVE_PROVIDER_PREFLIGHT:
        if "coinalyze" in namespace:
            return ("event_coinalyze_preflight.json",)
        if "bybit" in namespace:
            return ("event_bybit_announcements_preflight.json",)
        return ()
    if status == STATUS_ACTIVE_PROVIDER_REHEARSAL:
        if "coinalyze" in namespace:
            return ("event_coinalyze_preflight.json", "event_coinalyze_rehearsal_report.json")
        if "bybit" in namespace:
            return ("event_bybit_announcements_rehearsal_report.json",)
        return ()
    if status == STATUS_STALE_DEPRECATED:
        return (event_alpha_namespace_status.NAMESPACE_STATUS_FILENAME,)
    if status == STATUS_ACTIVE_ARCHITECTURE_REPORT:
        return ()
    if status == STATUS_MANUAL_REVIEW:
        return ()
    if status == STATUS_ACTIVE_LIVE_REHEARSAL:
        legacy = (
            "event_alpha_runs.jsonl",
            "event_alpha_notification_runs.jsonl",
            "event_alpha_notification_preview.md",
            "event_alpha_notification_deliveries.jsonl",
        )
        if not current_generation:
            return legacy
        return (
            event_alpha_operator_state.OPERATOR_STATE_FILENAME,
            *legacy,
            "event_alpha_daily_brief.md",
            "event_alpha_source_coverage.json",
            "research_cards/index.md",
        )
    return ()


def _artifact_counts(namespace_dir: Path) -> dict[str, int]:
    files = [path for path in namespace_dir.rglob("*") if path.is_file() and path.suffix != ".lock"]
    return {
        "files": len(files),
        "json": sum(1 for path in files if path.suffix == ".json"),
        "jsonl": sum(1 for path in files if path.suffix == ".jsonl"),
        "md": sum(1 for path in files if path.suffix == ".md"),
        "research_cards": sum(
            1
            for path in files
            if "research_cards" in path.parts and path.suffix == ".md" and path.name != "index.md"
        ),
    }


def _mtime_window(namespace_dir: Path) -> tuple[str | None, str | None]:
    files = [path for path in namespace_dir.rglob("*") if path.is_file() and path.suffix != ".lock"]
    if not files:
        return None, None
    mtimes = [path.stat().st_mtime for path in files]
    return _format_ts(min(mtimes)), _format_ts(max(mtimes))


def _latest_run_id(namespace_dir: Path) -> str | None:
    operator_state = event_alpha_operator_state.load_operator_state(namespace_dir)
    if operator_state.valid and operator_state.state and operator_state.state.get("run_id"):
        return str(operator_state.state["run_id"])
    run_path = namespace_dir / "event_alpha_runs.jsonl"
    if not run_path.exists():
        return None
    latest: str | None = None
    for line in run_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("run_id"):
            latest = str(row["run_id"])
    return latest


def _current_doctor_status(
    namespace_dir: Path,
    marker: event_alpha_namespace_status.EventAlphaNamespaceStatus | None,
) -> str:
    operator_state = event_alpha_operator_state.load_operator_state(namespace_dir)
    if operator_state.exists and not operator_state.valid:
        return "BLOCKED"
    if operator_state.valid and operator_state.state:
        state = operator_state.state
        doctor = state.get("doctor") if isinstance(state.get("doctor"), dict) else {}
        if (
            str(doctor.get("run_id") or "") == str(state.get("run_id") or "")
            and _int_or_none(doctor.get("verified_revision")) == _int_or_none(state.get("revision"))
            and doctor.get("authoritative") is True
            and doctor.get("strict") is True
            and doctor.get("schema_only") is False
            and doctor.get("skip_api_checks") is False
            and str(doctor.get("status") or "") in {"OK", "WARN", "BLOCKED"}
        ):
            return str(doctor["status"])
        if str(doctor.get("status") or "") in {"not_run", "stale", "STALE"}:
            return str(doctor.get("status"))
        return "stale"
    if marker and marker.current_doctor_status:
        if marker.latest_run_id and marker.latest_run_id != _latest_run_id(namespace_dir):
            return "stale"
        return str(marker.current_doctor_status)
    run_path = namespace_dir / "event_alpha_runs.jsonl"
    if run_path.exists():
        latest: str | None = None
        for line in run_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            for key in ("artifact_doctor_status", "doctor_status", "current_doctor_status"):
                if row.get(key):
                    latest = str(row[key])
        if latest:
            return latest
    return "not_run"


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _write_namespace_status_markers(base: Path, registry: dict[str, Any], *, now: datetime) -> None:
    for row in registry.get("namespaces", []):
        if not isinstance(row, dict):
            continue
        namespace = str(row.get("namespace") or "")
        if not namespace:
            continue
        if row.get("status") == STATUS_QUARANTINE or namespace.startswith(
            ("radar_bybit_liquidation_transcript_", "radar_tokenomist_v5_")
        ):
            # Detached captures and retained quarantine have exact inventories.
            # Project lifecycle state from the root registry; never inject an
            # unmanifested leaf into either tree.
            continue
        event_alpha_namespace_status.write_namespace_status(base / namespace, row, now=now)
        event_alpha_namespace_status.refresh_namespace_status(
            base / namespace,
            profile=str(row.get("profile") or "") or None,
            artifact_namespace=namespace,
            now=now,
        )


def _status_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or STATUS_UNKNOWN)
        counts[status] = counts.get(status, 0) + 1
    return counts


def _format_ts(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()


def _resolve_base_dir(base_dir: str | Path | None) -> Path:
    if base_dir is not None:
        return Path(base_dir).expanduser()
    try:
        from ... import config

        raw = getattr(config, "EVENT_ALPHA_ARTIFACT_BASE_DIR", None) or getattr(
            config,
            "EVENT_DISCOVERY_CACHE_DIR",
            "event_fade_cache",
        )
    except Exception:
        raw = "event_fade_cache"
    return Path(raw).expanduser()
