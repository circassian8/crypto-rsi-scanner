"""Cache helpers for Event Alpha shim source scans."""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from . import shim_scan


_PROCESS_REPORT_CACHE_LIMIT = 24
_PROCESS_REPORT_CACHE: OrderedDict[
    tuple[str, str, str, bool, int], tuple[str, dict[str, object]]
] = OrderedDict()


def load_fresh_report_cache(
    *,
    repo_root: Path,
    report_name: str,
    expected_schema: str,
    include_runtime_artifacts: bool,
    force_rescan_shims: bool,
    use_cache: bool,
    max_file_bytes: int,
    source_snapshot: shim_scan._ShimSourceSnapshot | None = None,
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
    snapshot = source_snapshot or shim_scan.get_source_snapshot(
        repo_root,
        include_runtime_artifacts=False,
        max_file_bytes=max_file_bytes,
    )
    newest_source_mtime, newer_paths, future_paths = scan_input_mtime_diagnostics(
        repo_root,
        report_mtime=report_mtime,
        max_file_bytes=max_file_bytes,
        source_snapshot=snapshot,
    )
    cached_fingerprint = str(payload.get("input_fingerprint") or "")
    current_fingerprint = snapshot.input_fingerprint
    diagnostics.update(
        {
            "report_mtime": report_mtime,
            "newest_source_mtime": newest_source_mtime,
            "newer_source_mtime_paths": newer_paths,
            "future_mtime_paths": future_paths,
            "input_fingerprint_schema": shim_scan.SHIM_SCAN_INPUT_FINGERPRINT_SCHEMA,
            "cached_input_fingerprint": cached_fingerprint,
            "input_fingerprint": current_fingerprint,
            "input_fingerprint_match": bool(cached_fingerprint)
            and cached_fingerprint == current_fingerprint,
            "source_snapshot_cache_status": snapshot.cache_status,
        }
    )
    if not cached_fingerprint:
        diagnostics["cache_status"] = "miss"
        diagnostics["cache_miss_reason"] = "missing_input_fingerprint"
        return None, diagnostics
    if cached_fingerprint != current_fingerprint:
        diagnostics["cache_status"] = "miss"
        diagnostics["cache_miss_reason"] = "input_fingerprint_mismatch"
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
    if status == "hit":
        payload.pop("cache_miss_reason", None)
        accounting.pop("cache_miss_reason", None)
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
    for key in (
        "newest_source_mtime",
        "report_mtime",
        "newer_source_mtime_paths",
        "future_mtime_paths",
        "input_fingerprint_schema",
        "input_fingerprint",
        "input_fingerprint_match",
        "source_snapshot_cache_status",
        "cache_miss_reason",
    ):
        if key in cache_diagnostics:
            fields[key] = cache_diagnostics[key]
    return fields


def scan_input_mtime_diagnostics(
    repo_root: Path,
    *,
    report_mtime: float,
    max_file_bytes: int,
    sample_limit: int = 5,
    source_snapshot: shim_scan._ShimSourceSnapshot | None = None,
) -> tuple[float, list[str], list[str]]:
    snapshot = source_snapshot or shim_scan.get_source_snapshot(
        repo_root,
        include_runtime_artifacts=False,
        max_file_bytes=max_file_bytes,
    )
    newest = 0.0
    newer_paths: list[str] = []
    future_paths: list[str] = []
    now_ts = datetime.now(timezone.utc).timestamp()
    for entry in snapshot.entries:
        row = entry.scan_path
        mtime = entry.signature.mtime_ns / 1_000_000_000
        newest = max(newest, mtime)
        if mtime > report_mtime and len(newer_paths) < sample_limit:
            newer_paths.append(f"{row.rel_path}:{mtime:.0f}")
        if mtime > now_ts + 2 and len(future_paths) < sample_limit:
            future_paths.append(f"{row.rel_path}:{mtime:.0f}")
    return newest, newer_paths, future_paths


def load_process_report(
    *,
    repo_root: Path,
    report_name: str,
    expected_schema: str,
    include_runtime_artifacts: bool,
    max_file_bytes: int,
    input_fingerprint: str,
) -> dict[str, object] | None:
    key = _process_report_key(
        repo_root=repo_root,
        report_name=report_name,
        expected_schema=expected_schema,
        include_runtime_artifacts=include_runtime_artifacts,
        max_file_bytes=max_file_bytes,
    )
    cached = _PROCESS_REPORT_CACHE.get(key)
    if cached is None or cached[0] != input_fingerprint:
        return None
    _PROCESS_REPORT_CACHE.move_to_end(key)
    return with_cache_status(
        cached[1],
        "hit",
        cache_diagnostics={
            "input_fingerprint_schema": shim_scan.SHIM_SCAN_INPUT_FINGERPRINT_SCHEMA,
            "input_fingerprint": input_fingerprint,
            "input_fingerprint_match": True,
            "source_snapshot_cache_status": "hit",
        },
    )


def store_process_report(
    report: Mapping[str, object],
    *,
    repo_root: Path,
    report_name: str,
    expected_schema: str,
    include_runtime_artifacts: bool,
    max_file_bytes: int,
    input_fingerprint: str,
) -> None:
    key = _process_report_key(
        repo_root=repo_root,
        report_name=report_name,
        expected_schema=expected_schema,
        include_runtime_artifacts=include_runtime_artifacts,
        max_file_bytes=max_file_bytes,
    )
    _PROCESS_REPORT_CACHE[key] = (input_fingerprint, dict(report))
    _PROCESS_REPORT_CACHE.move_to_end(key)
    while len(_PROCESS_REPORT_CACHE) > _PROCESS_REPORT_CACHE_LIMIT:
        _PROCESS_REPORT_CACHE.popitem(last=False)


def clear_process_report_cache(*, root: str | Path | None = None) -> None:
    if root is None:
        _PROCESS_REPORT_CACHE.clear()
        return
    resolved = str(Path(root).expanduser().resolve())
    for key in tuple(_PROCESS_REPORT_CACHE):
        if key[0] == resolved:
            _PROCESS_REPORT_CACHE.pop(key, None)


def _process_report_key(
    *,
    repo_root: Path,
    report_name: str,
    expected_schema: str,
    include_runtime_artifacts: bool,
    max_file_bytes: int,
) -> tuple[str, str, str, bool, int]:
    return (
        str(Path(repo_root).expanduser().resolve()),
        report_name,
        expected_schema,
        bool(include_runtime_artifacts),
        int(max_file_bytes),
    )


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
