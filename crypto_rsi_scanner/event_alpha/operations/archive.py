"""Archive Event Alpha burn-in evidence artifacts without secrets."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from . import common
from . import evidence_semantics
from . import namespace_policy


ARCHIVE_NAME = "event_alpha_burn_in_evidence_archive.zip"
MANIFEST_JSON = "event_alpha_burn_in_archive_manifest.json"
CHECKSUMS_JSON = "event_alpha_burn_in_archive_checksums.json"


def build_burn_in_archive(
    *,
    base_dir: str | Path = "event_fade_cache",
    out_dir: str | Path = "research",
    pattern: str | None = None,
    dry_run: bool = False,
    include_notification_rehearsals: bool = False,
    include_no_key_namespaces: bool = False,
    include_provider_rehearsals: bool = False,
    include_fixture_namespaces: bool = False,
    include_stale_namespaces: bool = False,
    include_live_rehearsals_without_burn_in_run: bool = False,
    include_namespaces: tuple[str, ...] = (),
) -> dict[str, Any]:
    base = Path(base_dir).expanduser()
    out = Path(out_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    archive_path = out / ARCHIVE_NAME
    manifest_path = out / MANIFEST_JSON
    checksums_path = out / CHECKSUMS_JSON
    policy = namespace_policy.build_namespace_policy(
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        base_dir=base,
        include_notification_rehearsals=include_notification_rehearsals,
        include_no_key_namespaces=include_no_key_namespaces,
        include_provider_rehearsals=include_provider_rehearsals,
        include_fixture_namespaces=include_fixture_namespaces,
        include_stale_namespaces=include_stale_namespaces,
        include_live_rehearsals_without_burn_in_run=include_live_rehearsals_without_burn_in_run,
        include_namespaces=include_namespaces,
    )
    namespaces = namespace_policy.included_namespace_names(policy)
    if pattern:
        namespaces = [name for name in namespaces if (base / name).match(pattern) or name.startswith(pattern.rstrip("*"))]
    files = _collect_files(base, namespaces)
    scan = _scan_archive_files(base, files)
    if not dry_run:
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for rel, data in scan["safe_payloads"]:
                zf.writestr(rel, data)
    archive_checksum = hashlib.sha256(archive_path.read_bytes()).hexdigest() if archive_path.exists() and not dry_run else ""
    explicit_flags = policy.get("explicit_inclusion_flags") if isinstance(policy.get("explicit_inclusion_flags"), dict) else {}
    explicit_scope = bool(include_namespaces) or any(
        bool(value) for key, value in explicit_flags.items() if key != "include_namespace"
    )
    payload = _build_archive_manifest_payload(
        base=base,
        archive_path=archive_path,
        manifest_path=manifest_path,
        checksums_path=checksums_path,
        dry_run=dry_run,
        explicit_scope=explicit_scope,
        namespaces=namespaces,
        files=files,
        policy=policy,
        scan=scan,
        pattern=pattern,
        archive_checksum=archive_checksum,
    )
    common.write_json(manifest_path, payload)
    common.write_json(checksums_path, {"archive_sha256": archive_checksum, "files": scan["checksums"]})
    return payload


def _scan_archive_files(base: Path, files: list[Path]) -> dict[str, Any]:
    secret_hits: dict[str, list[str]] = {}
    secret_hit_details: list[dict[str, Any]] = []
    secret_allowed_status_count = 0
    secret_false_positive_count = 0
    secret_blocker_count = 0
    checksums: dict[str, str] = {}
    safe_payloads: list[tuple[str, bytes]] = []
    artifact_category_counts: dict[str, int] = {
        "burn_in_run_artifacts": 0,
        "candidate_artifacts": 0,
        "readiness_artifacts": 0,
        "source_coverage_artifacts": 0,
        "review_inbox_artifacts": 0,
        "feedback_artifacts": 0,
    }
    for path in files:
        rel = path.relative_to(base).as_posix()
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if path.suffix.lower() in {".json", ".jsonl", ".md", ".txt", ".csv"}:
            details = _archive_secret_hit_details(data.decode("utf-8", errors="ignore"), rel)
            blocker_details = [detail for detail in details if detail.get("status") == "blocker"]
            allowed_details = [detail for detail in details if detail.get("status") == "allowed_status"]
            false_positive_details = [detail for detail in details if detail.get("status") == "false_positive"]
            secret_hit_details.extend(details)
            secret_allowed_status_count += len(allowed_details)
            secret_false_positive_count += len(false_positive_details)
            secret_blocker_count += len(blocker_details)
            if blocker_details:
                secret_hits[rel] = [
                    str(detail.get("token") or detail.get("reason") or "secret_like_value")
                    for detail in blocker_details
                ]
                continue
        checksums[rel] = hashlib.sha256(data).hexdigest()
        for category, matched in evidence_semantics.archive_artifact_categories(rel).items():
            if matched:
                artifact_category_counts[category] += 1
        safe_payloads.append((rel, data))
    return {
        "secret_hits": secret_hits,
        "secret_hit_details": secret_hit_details,
        "secret_allowed_status_count": secret_allowed_status_count,
        "secret_false_positive_count": secret_false_positive_count,
        "secret_blocker_count": secret_blocker_count,
        "checksums": checksums,
        "safe_payloads": safe_payloads,
        "artifact_category_counts": artifact_category_counts,
    }


def _build_archive_manifest_payload(
    *,
    base: Path,
    archive_path: Path,
    manifest_path: Path,
    checksums_path: Path,
    dry_run: bool,
    explicit_scope: bool,
    namespaces: list[str],
    files: list[Path],
    policy: dict[str, Any],
    scan: dict[str, Any],
    pattern: str | None,
    archive_checksum: str,
) -> dict[str, Any]:
    checksums = scan["checksums"]
    artifact_category_counts = scan["artifact_category_counts"]
    file_count_by_namespace = {
        namespace: sum(1 for path in files if path.relative_to(base).parts[:1] == (namespace,))
        for namespace in namespaces
    }
    return common.with_safety(
        {
            "schema_version": "event_alpha_burn_in_archive_manifest_v1",
            "row_type": "event_alpha_burn_in_archive_manifest",
            "generated_at": common.utc_now().isoformat(),
            "base_dir": common.rel_path(base),
            "archive_path": common.rel_path(archive_path),
            "manifest_path": common.rel_path(manifest_path),
            "checksums_path": common.rel_path(checksums_path),
            "dry_run": bool(dry_run),
            "archive_created": bool(not dry_run and archive_path.exists()),
            "archive_scope": "explicit_namespace_diagnostic" if explicit_scope else "active_burn_in_namespaces",
            "namespace_policy_version": policy.get("namespace_policy_version"),
            "explicit_include_flags": policy.get("explicit_inclusion_flags") or {},
            "no_active_burn_in_namespaces": not bool(namespaces),
            "enough_data": bool(namespaces),
            "enough_data_reasons": [] if namespaces else ["no_active_burn_in_namespaces"],
            "namespace_policy": {
                "namespace_policy_version": policy.get("namespace_policy_version"),
                "included_namespaces": policy.get("included_namespaces") or [],
                "excluded_namespaces": policy.get("excluded_namespaces") or [],
                "exclusion_reasons": policy.get("exclusion_reasons") or {},
                "excluded_reasons": policy.get("excluded_reasons") or policy.get("exclusion_reasons") or {},
                "explicit_inclusion_flags": policy.get("explicit_inclusion_flags") or {},
                "namespace_status": policy.get("namespace_status") or {},
                "latest_doctor_status": policy.get("latest_doctor_status") or {},
                "latest_run_id": policy.get("latest_run_id") or {},
                "artifact_counts": policy.get("artifact_counts") or {},
            },
            "included_namespaces": namespaces,
            "excluded_namespaces": policy.get("excluded_namespaces") or [],
            "exclusion_reasons": policy.get("exclusion_reasons") or {},
            "excluded_reasons": policy.get("excluded_reasons") or policy.get("exclusion_reasons") or {},
            "included_without_burn_in_run_count": policy.get("included_without_burn_in_run_count", 0),
            "active_live_rehearsal_excluded_count": policy.get("active_live_rehearsal_excluded_count", 0),
            "no_key_excluded_count": policy.get("no_key_excluded_count", 0),
            "notification_rehearsal_excluded_count": policy.get("notification_rehearsal_excluded_count", 0),
            "provider_rehearsal_excluded_count": policy.get("provider_rehearsal_excluded_count", 0),
            "fixture_excluded_count": policy.get("fixture_excluded_count", 0),
            "namespace_status": policy.get("namespace_status") or {},
            "latest_doctor_status": policy.get("latest_doctor_status") or {},
            "latest_run_id": policy.get("latest_run_id") or {},
            "artifact_counts": policy.get("artifact_counts") or {},
            "files_considered": len(files),
            "files_archived": len(checksums),
            "file_count_by_namespace": file_count_by_namespace,
            **artifact_category_counts,
            "support_artifacts": {
                "readiness_artifacts": artifact_category_counts["readiness_artifacts"],
                "source_coverage_artifacts": artifact_category_counts["source_coverage_artifacts"],
                "review_inbox_artifacts": artifact_category_counts["review_inbox_artifacts"],
                "feedback_artifacts": artifact_category_counts["feedback_artifacts"],
            },
            "candidate_evidence_artifacts": artifact_category_counts["candidate_artifacts"],
            "secret_hits": scan["secret_hits"],
            "secret_hit_count": scan["secret_blocker_count"],
            "secret_false_positive_count": scan["secret_false_positive_count"],
            "secret_allowed_status_count": scan["secret_allowed_status_count"],
            "secret_blocker_count": scan["secret_blocker_count"],
            "secret_hit_details": scan["secret_hit_details"],
            "secret_scan_summary": {
                "files_scanned": len(files),
                "files_with_hits": len(scan["secret_hits"]),
                "secret_hit_count": scan["secret_blocker_count"],
                "secret_false_positive_count": scan["secret_false_positive_count"],
                "secret_allowed_status_count": scan["secret_allowed_status_count"],
                "secret_blocker_count": scan["secret_blocker_count"],
            },
            "archive_sha256": archive_checksum,
            "checksum_manifest": {
                "path": common.rel_path(checksums_path),
                "file_count": len(checksums),
                "archive_sha256": archive_checksum,
            },
            "include_patterns": [pattern] if pattern else [],
            "excluded_suffixes": sorted(_excluded_suffixes()),
        }
    )


def _collect_files(base: Path, namespaces: list[str] | tuple[str, ...]) -> list[Path]:
    if not base.exists():
        return []
    files: list[Path] = []
    for namespace_name in namespaces:
        namespace = base / namespace_name
        if not namespace.is_dir():
            continue
        for path in namespace.rglob("*"):
            if path.is_file() and not _excluded(path):
                files.append(path)
    return sorted(files)


def _excluded_suffixes() -> set[str]:
    return {".db", ".sqlite", ".log", ".pyc", ".zip"}


def _excluded(path: Path) -> bool:
    parts = set(path.parts)
    if parts & {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache"}:
        return True
    if path.name in {".env", ".DS_Store"}:
        return True
    return path.suffix.lower() in _excluded_suffixes()


def _archive_secret_hits(text: str) -> list[str]:
    return [str(detail.get("token") or detail.get("reason")) for detail in _archive_secret_hit_details(text, "") if detail.get("status") == "blocker"]


def _archive_secret_hit_details(text: str, rel_path: str) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for detail in common.classify_secret_hits_in_text(text):
        row = dict(detail)
        if rel_path:
            row["path"] = rel_path
        details.append(row)
    return details


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archive burn-in evidence artifacts without secrets.")
    parser.add_argument("--base-dir", default="event_fade_cache")
    parser.add_argument("--out-dir", default="research")
    parser.add_argument("--artifact-namespace", default=None)
    parser.add_argument("--pattern", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include-notification-rehearsals", action="store_true")
    parser.add_argument("--include-no-key-namespaces", action="store_true")
    parser.add_argument("--include-provider-rehearsals", action="store_true")
    parser.add_argument("--include-fixture-namespaces", action="store_true")
    parser.add_argument("--include-stale-namespaces", action="store_true")
    parser.add_argument("--include-live-rehearsals-without-burn-in-run", action="store_true")
    parser.add_argument("--include-namespace", action="append", default=[])
    args = parser.parse_args(argv)
    explicit_namespaces = tuple([*(args.include_namespace or []), *([args.artifact_namespace] if args.artifact_namespace else [])])
    payload = build_burn_in_archive(
        base_dir=args.base_dir,
        out_dir=args.out_dir,
        pattern=args.pattern,
        dry_run=args.dry_run,
        include_notification_rehearsals=args.include_notification_rehearsals,
        include_no_key_namespaces=args.include_no_key_namespaces,
        include_provider_rehearsals=args.include_provider_rehearsals,
        include_fixture_namespaces=args.include_fixture_namespaces,
        include_stale_namespaces=args.include_stale_namespaces,
        include_live_rehearsals_without_burn_in_run=args.include_live_rehearsals_without_burn_in_run,
        include_namespaces=explicit_namespaces,
    )
    print(f"event_alpha_burn_in_archive: {payload['archive_path']}")
    print(
        f"dry_run={payload['dry_run']} files_archived={payload['files_archived']} "
        f"secret_hit_count={payload['secret_hit_count']} secret_allowed_status_count={payload.get('secret_allowed_status_count', 0)}"
    )
    return 1 if payload.get("secret_blocker_count") else 0


if __name__ == "__main__":
    raise SystemExit(main())
