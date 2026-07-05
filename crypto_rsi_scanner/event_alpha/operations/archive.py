"""Archive Event Alpha burn-in evidence artifacts without secrets."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from . import common


ARCHIVE_NAME = "event_alpha_burn_in_evidence_archive.zip"
MANIFEST_JSON = "event_alpha_burn_in_archive_manifest.json"
CHECKSUMS_JSON = "event_alpha_burn_in_archive_checksums.json"


def build_burn_in_archive(
    *,
    base_dir: str | Path = "event_fade_cache",
    out_dir: str | Path = "research",
    pattern: str = "live_burn_in*",
) -> dict[str, Any]:
    base = Path(base_dir).expanduser()
    out = Path(out_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    archive_path = out / ARCHIVE_NAME
    manifest_path = out / MANIFEST_JSON
    checksums_path = out / CHECKSUMS_JSON
    files = _collect_files(base, pattern)
    secret_hits: dict[str, list[str]] = {}
    checksums: dict[str, str] = {}
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            rel = path.relative_to(base).as_posix()
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if path.suffix.lower() in {".json", ".jsonl", ".md", ".txt", ".csv"}:
                hits = common.secret_hits_in_text(data.decode("utf-8", errors="ignore"))
                if hits:
                    secret_hits[rel] = hits
                    continue
            zf.writestr(rel, data)
            checksums[rel] = hashlib.sha256(data).hexdigest()
    archive_checksum = hashlib.sha256(archive_path.read_bytes()).hexdigest() if archive_path.exists() else ""
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_burn_in_archive_manifest_v1",
            "row_type": "event_alpha_burn_in_archive_manifest",
            "generated_at": common.utc_now().isoformat(),
            "base_dir": common.rel_path(base),
            "archive_path": common.rel_path(archive_path),
            "manifest_path": common.rel_path(manifest_path),
            "checksums_path": common.rel_path(checksums_path),
            "files_considered": len(files),
            "files_archived": len(checksums),
            "secret_hits": secret_hits,
            "secret_hit_count": sum(len(values) for values in secret_hits.values()),
            "archive_sha256": archive_checksum,
            "include_patterns": [pattern],
            "excluded_suffixes": sorted(_excluded_suffixes()),
        }
    )
    common.write_json(manifest_path, payload)
    common.write_json(checksums_path, {"archive_sha256": archive_checksum, "files": checksums})
    return payload


def _collect_files(base: Path, pattern: str) -> list[Path]:
    if not base.exists():
        return []
    files: list[Path] = []
    for namespace in base.glob(pattern):
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archive burn-in evidence artifacts without secrets.")
    parser.add_argument("--base-dir", default="event_fade_cache")
    parser.add_argument("--out-dir", default="research")
    parser.add_argument("--pattern", default="live_burn_in*")
    args = parser.parse_args(argv)
    payload = build_burn_in_archive(base_dir=args.base_dir, out_dir=args.out_dir, pattern=args.pattern)
    print(f"event_alpha_burn_in_archive: {payload['archive_path']}")
    print(f"files_archived={payload['files_archived']} secret_hit_count={payload['secret_hit_count']}")
    return 1 if payload.get("secret_hit_count") else 0


if __name__ == "__main__":
    raise SystemExit(main())
