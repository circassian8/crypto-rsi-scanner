"""Cache helpers for Event Alpha shim source scans."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from . import shim_scan


def load_fresh_report_cache(
    *,
    repo_root: Path,
    report_name: str,
    expected_schema: str,
    include_runtime_artifacts: bool,
    force_rescan_shims: bool,
    use_cache: bool,
    max_file_bytes: int,
) -> tuple[dict[str, object] | None, dict[str, object]]:
    diagnostics: dict[str, object] = {
        "cache_status": scan_cache_status(
            include_runtime_artifacts=include_runtime_artifacts,
            force_rescan_shims=force_rescan_shims,
            use_cache=use_cache,
        )
    }
    if force_rescan_shims or include_runtime_artifacts or not use_cache:
        return None, diagnostics
    path = repo_root / "research" / report_name
    try:
        report_mtime = path.stat().st_mtime
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, diagnostics
    if not isinstance(payload, dict) or payload.get("schema_version") != expected_schema:
        return None, diagnostics
    if not isinstance(payload.get("scan_accounting"), dict):
        return None, diagnostics
    if bool(payload.get("include_runtime_artifacts")):
        return None, diagnostics
    newest_source_mtime, newer_paths, future_paths = scan_input_mtime_diagnostics(
        repo_root,
        report_mtime=report_mtime,
        max_file_bytes=max_file_bytes,
    )
    diagnostics.update(
        {
            "report_mtime": report_mtime,
            "newest_source_mtime": newest_source_mtime,
            "newer_source_mtime_paths": newer_paths,
            "future_mtime_paths": future_paths,
        }
    )
    if newest_source_mtime > report_mtime:
        diagnostics["cache_status"] = "miss_due_future_mtime" if future_paths else "miss"
        return None, diagnostics
    return payload, diagnostics


def with_cache_status(
    report: dict[str, object],
    status: str,
    *,
    cache_diagnostics: Mapping[str, object] | None = None,
) -> dict[str, object]:
    payload = dict(report)
    accounting = dict(payload.get("scan_accounting") or {})
    accounting["cache_status"] = status
    accounting.update(cache_accounting_fields(cache_diagnostics or {}))
    payload["scan_accounting"] = accounting
    payload["cache_status"] = status
    payload.update(cache_accounting_fields(cache_diagnostics or {}))
    if payload.get("row_type") == "event_alpha_shim_dependency_report":
        payload["shim_dependency_report_cache_status"] = status
    if payload.get("row_type") == "event_alpha_old_import_check":
        payload["old_import_check_cache_status"] = status
    return payload


def cache_accounting_fields(cache_diagnostics: Mapping[str, object]) -> dict[str, object]:
    fields: dict[str, object] = {}
    for key in ("newest_source_mtime", "report_mtime", "newer_source_mtime_paths", "future_mtime_paths"):
        if key in cache_diagnostics:
            fields[key] = cache_diagnostics[key]
    return fields


def scan_input_mtime_diagnostics(
    repo_root: Path,
    *,
    report_mtime: float,
    max_file_bytes: int,
    sample_limit: int = 5,
) -> tuple[float, list[str], list[str]]:
    paths, _accounting = shim_scan.dependency_scan_paths_with_accounting(
        repo_root,
        include_runtime_artifacts=False,
        max_file_bytes=max_file_bytes,
    )
    newest = 0.0
    newer_paths: list[str] = []
    future_paths: list[str] = []
    now_ts = datetime.now(timezone.utc).timestamp()
    for row in paths:
        try:
            mtime = row.path.stat().st_mtime
        except OSError:
            continue
        newest = max(newest, mtime)
        if mtime > report_mtime and len(newer_paths) < sample_limit:
            newer_paths.append(f"{row.rel_path}:{mtime:.0f}")
        if mtime > now_ts + 2 and len(future_paths) < sample_limit:
            future_paths.append(f"{row.rel_path}:{mtime:.0f}")
    return newest, newer_paths, future_paths


def scan_cache_status(
    *,
    include_runtime_artifacts: bool,
    force_rescan_shims: bool,
    use_cache: bool,
) -> str:
    if include_runtime_artifacts:
        return "runtime_artifacts_scan"
    if force_rescan_shims:
        return "force_rescan"
    if not use_cache:
        return "disabled"
    return "miss"
