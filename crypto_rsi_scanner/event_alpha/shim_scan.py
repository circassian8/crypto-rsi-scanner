"""Fast source-scoped scanning for Event Alpha shim references."""

from __future__ import annotations

import ast
import hashlib
import os
import re
import stat
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .artifacts import paths as event_artifact_paths

DEFAULT_SHIM_SCAN_EXCLUDE_DIRS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "backups",
        "backtest_cache",
        "build",
        "cache",
        "dist",
        "event_fade_cache",
        "htmlcov",
        "logs",
        "venv",
    }
)
DEFAULT_SHIM_SCAN_EXCLUDE_SUFFIXES = frozenset(
    {
        ".db",
        ".gz",
        ".log",
        ".pyc",
        ".pyo",
        ".sqlite",
        ".sqlite3",
        ".zip",
    }
)
DEFAULT_SHIM_SCAN_MAX_FILE_BYTES = 1_000_000
SHIM_SCAN_DURATION_WARNING_SECONDS = 10.0
SHIM_SCAN_INPUT_FINGERPRINT_SCHEMA = "event_alpha_shim_scan_inputs_v1"
_SOURCE_SNAPSHOT_CACHE_LIMIT = 8

_REFERENCE_PREFIX = "crypto_rsi_scanner.event_"
_RUNTIME_ARTIFACT_ROOTS = ("event_fade_cache",)
_SOURCE_ROOTS = ("crypto_rsi_scanner", "tests", "scripts", "research")
_TOP_LEVEL_DOCS = ("AGENTS.md", "DECISIONS.md", "DEVLOG.md", "ROADMAP.md", "README.md")
_EXCLUDED_REL_PATHS = frozenset(
    {
        "crypto_rsi_scanner/event_alpha/SHIM_REGISTRY.json",
        "research/EVENT_ALPHA_DELETED_SHIMS.json",
        "research/EVENT_ALPHA_DELETED_SHIMS.md",
        "research/EVENT_ALPHA_FINAL_SHIM_STATUS.json",
        "research/EVENT_ALPHA_FINAL_SHIM_STATUS.md",
        "research/EVENT_ALPHA_OLD_IMPORT_CHECK.json",
        "research/EVENT_ALPHA_OLD_IMPORT_CHECK.md",
        "research/EVENT_ALPHA_SHIM_DEPENDENCY_REPORT.json",
        "research/EVENT_ALPHA_SHIM_DEPENDENCY_REPORT.md",
        "research/EVENT_ALPHA_SHIM_REMOVAL_CANDIDATES.json",
        "research/EVENT_ALPHA_SHIM_REMOVAL_CANDIDATES.md",
        "research/REMAINING_EVENT_MODULE_CLASSIFICATION.json",
        "research/REMAINING_EVENT_MODULE_CLASSIFICATION.md",
    }
)
_FINGERPRINT_ONLY_REL_PATHS = ("research/EVENT_ALPHA_DELETED_SHIMS.json",)
_HISTORICAL_REPORT_PREFIXES = ("RE" + "FACTOR_", "FINAL_" + "RE" + "FACTOR_")


@dataclass
class ShimScanAccounting:
    include_runtime_artifacts: bool
    max_file_bytes: int
    scanned_source_files: int = 0
    scanned_doc_files: int = 0
    scanned_test_files: int = 0
    scanned_script_files: int = 0
    scanned_makefile_files: int = 0
    scanned_artifact_files: int = 0
    skipped_artifact_files: int = 0
    skipped_large_files: int = 0
    skipped_suffix_files: int = 0
    skipped_binary_files: int = 0
    skipped_symlink_files: int = 0
    skipped_dirs: int = 0
    regex_compile_count: int = 0
    scan_duration_seconds: float = 0.0
    skipped_large_file_samples: list[str] = field(default_factory=list)
    skipped_dir_samples: list[str] = field(default_factory=list)

    def count_scanned(self, rel_path: str, category: str) -> None:
        if category == "test_import_references":
            self.scanned_test_files += 1
        elif category == "script_references":
            self.scanned_script_files += 1
        elif category == "makefile_references":
            self.scanned_makefile_files += 1
        elif category == "artifact_doc_references":
            if rel_path.startswith("event_fade_cache/"):
                self.scanned_artifact_files += 1
            else:
                self.scanned_doc_files += 1
        elif rel_path.endswith(".md") or rel_path in _TOP_LEVEL_DOCS:
            self.scanned_doc_files += 1
        else:
            self.scanned_source_files += 1

    def to_dict(self) -> dict[str, object]:
        return {
            "include_runtime_artifacts": self.include_runtime_artifacts,
            "max_file_bytes": self.max_file_bytes,
            "scanned_source_files": self.scanned_source_files,
            "scanned_doc_files": self.scanned_doc_files,
            "scanned_test_files": self.scanned_test_files,
            "scanned_script_files": self.scanned_script_files,
            "scanned_makefile_files": self.scanned_makefile_files,
            "scanned_artifact_files": self.scanned_artifact_files,
            "skipped_artifact_files": self.skipped_artifact_files,
            "skipped_large_files": self.skipped_large_files,
            "skipped_suffix_files": self.skipped_suffix_files,
            "skipped_binary_files": self.skipped_binary_files,
            "skipped_symlink_files": self.skipped_symlink_files,
            "skipped_dirs": self.skipped_dirs,
            "regex_compile_count": self.regex_compile_count,
            "scan_duration_seconds": round(self.scan_duration_seconds, 4),
            "skipped_large_file_samples": self.skipped_large_file_samples[:10],
            "skipped_dir_samples": self.skipped_dir_samples[:10],
        }


@dataclass(frozen=True)
class _ScanPath:
    path: Path
    rel_path: str
    category: str


@dataclass(frozen=True)
class _PathSignature:
    device: int
    inode: int
    mode: int
    size: int
    mtime_ns: int
    ctime_ns: int


@dataclass(frozen=True)
class _SnapshotEntry:
    scan_path: _ScanPath
    text: str
    content_sha256: str
    signature: _PathSignature


@dataclass(frozen=True)
class _ShimSourceSnapshot:
    """One immutable, content-identified view of shim scan inputs.

    The process cache validates inode/size/mtime/ctime metadata before reuse.
    ``ctime`` is intentionally included so rewriting a source file and then
    restoring or clamping its mtime cannot make changed content look unchanged.
    Directory signatures detect additions, deletions, and renames without
    re-walking every source tree on each artifact-doctor invocation.
    """

    repo_root: Path
    include_runtime_artifacts: bool
    max_file_bytes: int
    entries: tuple[_SnapshotEntry, ...]
    fingerprint_dependencies: tuple[tuple[Path, _PathSignature], ...]
    ignored_file_signatures: tuple[tuple[Path, _PathSignature], ...]
    directory_signatures: tuple[tuple[Path, _PathSignature], ...]
    accounting: dict[str, object]
    input_fingerprint: str
    cache_status: str

    @property
    def paths(self) -> tuple[_ScanPath, ...]:
        return tuple(entry.scan_path for entry in self.entries)

    @property
    def input_file_count(self) -> int:
        return len(self.entries) + len(self.fingerprint_dependencies)


_SOURCE_SNAPSHOT_CACHE: OrderedDict[tuple[str, bool, int], _ShimSourceSnapshot] = OrderedDict()


@dataclass(frozen=True)
class _Matcher:
    old_modules: dict[str, Any]
    old_by_leaf: dict[str, str]
    regexes: dict[str, re.Pattern[str]]


def scan_dependency_references(
    entries: Iterable[Any],
    *,
    repo_root: Path,
    include_runtime_artifacts: bool = False,
    max_file_bytes: int = DEFAULT_SHIM_SCAN_MAX_FILE_BYTES,
) -> dict[str, dict[str, list[dict[str, object]]]]:
    refs, _accounting = scan_dependency_references_with_accounting(
        entries,
        repo_root=repo_root,
        include_runtime_artifacts=include_runtime_artifacts,
        max_file_bytes=max_file_bytes,
    )
    return refs


def scan_dependency_references_with_accounting(
    entries: Iterable[Any],
    *,
    repo_root: Path,
    include_runtime_artifacts: bool = False,
    max_file_bytes: int = DEFAULT_SHIM_SCAN_MAX_FILE_BYTES,
    source_snapshot: _ShimSourceSnapshot | None = None,
) -> tuple[dict[str, dict[str, list[dict[str, object]]]], dict[str, object]]:
    started = time.monotonic()
    entries_tuple = tuple(entries)
    old_modules = {str(entry.old_module): entry for entry in entries_tuple}
    refs: dict[str, dict[str, list[dict[str, object]]]] = {
        old_module: {
            "internal_import_references": [],
            "test_import_references": [],
            "makefile_references": [],
            "docs_references": [],
            "script_references": [],
            "dynamic_import_references": [],
            "artifact_doc_references": [],
        }
        for old_module in old_modules
    }
    matcher = _Matcher(
        old_modules=old_modules,
        old_by_leaf={old_module.rsplit(".", 1)[1]: old_module for old_module in old_modules},
        regexes={
            old_module: re.compile(rf"(?<![\w.]){re.escape(old_module)}(?![\w.])")
            for old_module in old_modules
        },
    )
    snapshot = source_snapshot or get_source_snapshot(
        repo_root,
        include_runtime_artifacts=include_runtime_artifacts,
        max_file_bytes=max_file_bytes,
    )
    if (
        snapshot.repo_root != repo_root.resolve()
        or snapshot.include_runtime_artifacts != include_runtime_artifacts
        or snapshot.max_file_bytes != max_file_bytes
    ):
        raise ValueError("shim source snapshot does not match scan options")
    accounting = _accounting_from_snapshot(snapshot)
    accounting.regex_compile_count = len(matcher.regexes)
    for entry in snapshot.entries:
        scan_path = entry.scan_path
        accounting.count_scanned(scan_path.rel_path, scan_path.category)
        text = entry.text
        if scan_path.path.suffix == ".py":
            _scan_python_import_references(
                text,
                rel_path=scan_path.rel_path,
                category=scan_path.category,
                matcher=matcher,
                refs=refs,
            )
        _scan_text_references(
            text,
            path=scan_path.path,
            rel_path=scan_path.rel_path,
            category=scan_path.category,
            matcher=matcher,
            refs=refs,
        )
    accounting.scan_duration_seconds = time.monotonic() - started
    result_accounting = accounting.to_dict()
    result_accounting.update(
        {
            "source_snapshot_cache_status": snapshot.cache_status,
            "input_fingerprint_schema": SHIM_SCAN_INPUT_FINGERPRINT_SCHEMA,
            "input_fingerprint": snapshot.input_fingerprint,
            "input_file_count": snapshot.input_file_count,
        }
    )
    return refs, result_accounting


def get_source_snapshot(
    repo_root: Path,
    *,
    include_runtime_artifacts: bool = False,
    max_file_bytes: int = DEFAULT_SHIM_SCAN_MAX_FILE_BYTES,
    force_refresh: bool = False,
) -> _ShimSourceSnapshot:
    """Return a validated process-local content snapshot for shim scans."""

    root = Path(repo_root).expanduser().resolve()
    key = (str(root), bool(include_runtime_artifacts), int(max_file_bytes))
    cached = _SOURCE_SNAPSHOT_CACHE.get(key)
    if not force_refresh and cached is not None and _snapshot_is_unchanged(cached):
        _SOURCE_SNAPSHOT_CACHE.move_to_end(key)
        return _snapshot_with_cache_status(cached, "hit")

    snapshot = _build_source_snapshot(
        root,
        include_runtime_artifacts=include_runtime_artifacts,
        max_file_bytes=max_file_bytes,
        cache_status="force_refresh" if force_refresh else "miss",
    )
    _SOURCE_SNAPSHOT_CACHE[key] = snapshot
    _SOURCE_SNAPSHOT_CACHE.move_to_end(key)
    while len(_SOURCE_SNAPSHOT_CACHE) > _SOURCE_SNAPSHOT_CACHE_LIMIT:
        _SOURCE_SNAPSHOT_CACHE.popitem(last=False)
    return snapshot


def clear_source_snapshot_cache(*, root: str | Path | None = None) -> None:
    """Clear process snapshots, primarily for explicit report regeneration/tests."""

    if root is None:
        _SOURCE_SNAPSHOT_CACHE.clear()
        return
    resolved = str(Path(root).expanduser().resolve())
    for key in tuple(_SOURCE_SNAPSHOT_CACHE):
        if key[0] == resolved:
            _SOURCE_SNAPSHOT_CACHE.pop(key, None)


def _build_source_snapshot(
    repo_root: Path,
    *,
    include_runtime_artifacts: bool,
    max_file_bytes: int,
    cache_status: str,
) -> _ShimSourceSnapshot:
    paths, accounting, visited_dirs, ignored_paths = _dependency_scan_inventory(
        repo_root,
        include_runtime_artifacts=include_runtime_artifacts,
        max_file_bytes=max_file_bytes,
    )
    entries: list[_SnapshotEntry] = []
    ignored_file_signatures: list[tuple[Path, _PathSignature]] = []
    fingerprint = hashlib.sha256()
    fingerprint.update(SHIM_SCAN_INPUT_FINGERPRINT_SCHEMA.encode("ascii"))
    fingerprint.update(b"\0")
    for scan_path in paths:
        try:
            data, signature = _read_snapshot_path(scan_path.path, repo_root=repo_root)
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            accounting.skipped_binary_files += 1
            try:
                ignored_file_signatures.append(
                    (scan_path.path, _path_signature(scan_path.path))
                )
            except OSError:
                pass
            continue
        except OSError:
            continue
        content_sha256 = hashlib.sha256(data).hexdigest()
        fingerprint.update(scan_path.rel_path.encode("utf-8"))
        fingerprint.update(b"\0")
        fingerprint.update(scan_path.category.encode("utf-8"))
        fingerprint.update(b"\0")
        fingerprint.update(content_sha256.encode("ascii"))
        fingerprint.update(b"\0")
        entries.append(
            _SnapshotEntry(
                scan_path=scan_path,
                text=text,
                content_sha256=content_sha256,
                signature=signature,
            )
        )
    fingerprint_dependencies: list[tuple[Path, _PathSignature]] = []
    for rel_path in _FINGERPRINT_ONLY_REL_PATHS:
        path = repo_root / rel_path
        try:
            data, signature = _read_snapshot_path(path, repo_root=repo_root)
        except OSError:
            continue
        fingerprint.update(b"fingerprint_dependency\0")
        fingerprint.update(rel_path.encode("utf-8"))
        fingerprint.update(b"\0")
        fingerprint.update(hashlib.sha256(data).hexdigest().encode("ascii"))
        fingerprint.update(b"\0")
        fingerprint_dependencies.append((path, signature))
    for path in sorted(ignored_paths, key=lambda item: item.as_posix()):
        try:
            ignored_file_signatures.append((path, _path_signature(path)))
        except OSError:
            continue
    directory_signatures = tuple(
        (path, _path_signature(path))
        for path in sorted(visited_dirs, key=lambda item: item.as_posix())
        if path.exists()
    )
    snapshot_accounting = accounting.to_dict()
    snapshot_accounting.update(
        {
            "source_snapshot_cache_status": cache_status,
            "input_fingerprint_schema": SHIM_SCAN_INPUT_FINGERPRINT_SCHEMA,
            "input_file_count": len(entries) + len(fingerprint_dependencies),
        }
    )
    return _ShimSourceSnapshot(
        repo_root=repo_root,
        include_runtime_artifacts=include_runtime_artifacts,
        max_file_bytes=max_file_bytes,
        entries=tuple(entries),
        fingerprint_dependencies=tuple(fingerprint_dependencies),
        ignored_file_signatures=tuple(ignored_file_signatures),
        directory_signatures=directory_signatures,
        accounting=snapshot_accounting,
        input_fingerprint=fingerprint.hexdigest(),
        cache_status=cache_status,
    )


def _snapshot_is_unchanged(snapshot: _ShimSourceSnapshot) -> bool:
    for entry in snapshot.entries:
        try:
            if _path_signature(entry.scan_path.path) != entry.signature:
                return False
        except OSError:
            return False
    for path, signature in snapshot.fingerprint_dependencies:
        try:
            if _path_signature(path) != signature:
                return False
        except OSError:
            return False
    for path, signature in snapshot.ignored_file_signatures:
        try:
            if _path_signature(path) != signature:
                return False
        except OSError:
            return False
    for path, signature in snapshot.directory_signatures:
        try:
            if _path_signature(path) != signature:
                return False
        except OSError:
            return False
    return True


def _snapshot_with_cache_status(snapshot: _ShimSourceSnapshot, status: str) -> _ShimSourceSnapshot:
    accounting = dict(snapshot.accounting)
    accounting["source_snapshot_cache_status"] = status
    return _ShimSourceSnapshot(
        repo_root=snapshot.repo_root,
        include_runtime_artifacts=snapshot.include_runtime_artifacts,
        max_file_bytes=snapshot.max_file_bytes,
        entries=snapshot.entries,
        fingerprint_dependencies=snapshot.fingerprint_dependencies,
        ignored_file_signatures=snapshot.ignored_file_signatures,
        directory_signatures=snapshot.directory_signatures,
        accounting=accounting,
        input_fingerprint=snapshot.input_fingerprint,
        cache_status=status,
    )


def _path_signature(path: Path) -> _PathSignature:
    return _path_signature_from_stat(path.lstat())


def _path_signature_from_stat(row: os.stat_result) -> _PathSignature:
    return _PathSignature(
        device=int(row.st_dev),
        inode=int(row.st_ino),
        mode=int(row.st_mode),
        size=int(row.st_size),
        mtime_ns=int(row.st_mtime_ns),
        ctime_ns=int(row.st_ctime_ns),
    )


def _read_snapshot_path(path: Path, *, repo_root: Path) -> tuple[bytes, _PathSignature]:
    """Read one regular in-root file without following a final symlink."""

    root = Path(repo_root).expanduser().resolve()
    candidate = Path(path).expanduser().absolute()
    try:
        candidate.relative_to(root)
        candidate.resolve(strict=True).relative_to(root)
    except (OSError, ValueError) as exc:
        raise OSError("shim scan input is outside the repository") from exc
    before = candidate.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise OSError("shim scan input is not a regular file")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(candidate, flags)
    try:
        opened_before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened_before.st_mode)
            or (before.st_dev, before.st_ino) != (opened_before.st_dev, opened_before.st_ino)
        ):
            raise OSError("shim scan input changed during open")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        opened_after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    after = candidate.lstat()
    opened_signature = _path_signature_from_stat(opened_before)
    if (
        opened_signature != _path_signature_from_stat(opened_after)
        or (after.st_dev, after.st_ino) != (opened_after.st_dev, opened_after.st_ino)
        or not stat.S_ISREG(after.st_mode)
    ):
        raise OSError("shim scan input changed during read")
    try:
        candidate.resolve(strict=True).relative_to(root)
    except (OSError, ValueError) as exc:
        raise OSError("shim scan input escaped the repository during read") from exc
    return b"".join(chunks), opened_signature


def _accounting_from_snapshot(snapshot: _ShimSourceSnapshot) -> ShimScanAccounting:
    source = snapshot.accounting
    accounting = ShimScanAccounting(
        include_runtime_artifacts=snapshot.include_runtime_artifacts,
        max_file_bytes=snapshot.max_file_bytes,
    )
    for name in (
        "skipped_artifact_files",
        "skipped_large_files",
        "skipped_suffix_files",
        "skipped_binary_files",
        "skipped_symlink_files",
        "skipped_dirs",
    ):
        setattr(accounting, name, int(source.get(name) or 0))
    accounting.skipped_large_file_samples = list(source.get("skipped_large_file_samples") or [])
    accounting.skipped_dir_samples = list(source.get("skipped_dir_samples") or [])
    return accounting


def dependency_scan_paths_with_accounting(
    repo_root: Path,
    *,
    include_runtime_artifacts: bool = False,
    max_file_bytes: int = DEFAULT_SHIM_SCAN_MAX_FILE_BYTES,
) -> tuple[tuple[_ScanPath, ...], ShimScanAccounting]:
    paths, accounting, _visited_dirs, _ignored_paths = _dependency_scan_inventory(
        Path(repo_root).expanduser().resolve(),
        include_runtime_artifacts=include_runtime_artifacts,
        max_file_bytes=max_file_bytes,
    )
    return paths, accounting


def _dependency_scan_inventory(
    repo_root: Path,
    *,
    include_runtime_artifacts: bool,
    max_file_bytes: int,
) -> tuple[tuple[_ScanPath, ...], ShimScanAccounting, set[Path], set[Path]]:
    accounting = ShimScanAccounting(
        include_runtime_artifacts=include_runtime_artifacts,
        max_file_bytes=max_file_bytes,
    )
    paths: list[_ScanPath] = []
    visited_dirs: set[Path] = {repo_root}
    ignored_paths: set[Path] = set()
    for name in _SOURCE_ROOTS:
        base = repo_root / name
        if not base.exists() or base.is_symlink() or not base.is_dir():
            continue
        for path in _walk_scan_root(
            base,
            repo_root=repo_root,
            include_runtime_artifacts=include_runtime_artifacts,
            max_file_bytes=max_file_bytes,
            accounting=accounting,
            visited_dirs=visited_dirs,
            ignored_paths=ignored_paths,
        ):
            rel_path = event_artifact_paths.artifact_display_path(path, repo_root=repo_root)
            if rel_path in _EXCLUDED_REL_PATHS or _is_historical_report_artifact(rel_path):
                continue
            if name == "research" and path.suffix != ".md":
                continue
            if _allowed_scan_file(path, rel_path=rel_path, include_runtime_artifacts=include_runtime_artifacts):
                paths.append(_ScanPath(path=path, rel_path=rel_path, category=_reference_category(rel_path)))
    for path in _top_level_scan_files(repo_root):
        rel_path = event_artifact_paths.artifact_display_path(path, repo_root=repo_root)
        if rel_path in _EXCLUDED_REL_PATHS or _is_historical_report_artifact(rel_path):
            continue
        paths.append(_ScanPath(path=path, rel_path=rel_path, category=_reference_category(rel_path)))
    if include_runtime_artifacts:
        for root_name in _RUNTIME_ARTIFACT_ROOTS:
            base = repo_root / root_name
            if not base.exists() or base.is_symlink() or not base.is_dir():
                continue
            for path in _walk_scan_root(
                base,
                repo_root=repo_root,
                include_runtime_artifacts=include_runtime_artifacts,
                max_file_bytes=max_file_bytes,
                accounting=accounting,
                visited_dirs=visited_dirs,
                ignored_paths=ignored_paths,
            ):
                rel_path = event_artifact_paths.artifact_display_path(path, repo_root=repo_root)
                if rel_path in _EXCLUDED_REL_PATHS or _is_historical_report_artifact(rel_path):
                    continue
                if _allowed_scan_file(path, rel_path=rel_path, include_runtime_artifacts=True):
                    paths.append(_ScanPath(path=path, rel_path=rel_path, category=_reference_category(rel_path)))
    else:
        for root_name in _RUNTIME_ARTIFACT_ROOTS:
            base = repo_root / root_name
            if base.exists():
                accounting.skipped_artifact_files += _count_files(base)
    deduped = sorted({row.path: row for row in paths}.values(), key=lambda row: row.rel_path)
    return tuple(deduped), accounting, visited_dirs, ignored_paths


def newest_scan_input_mtime(
    repo_root: Path,
    *,
    include_runtime_artifacts: bool = False,
    max_file_bytes: int = DEFAULT_SHIM_SCAN_MAX_FILE_BYTES,
) -> float:
    paths, _accounting = dependency_scan_paths_with_accounting(
        repo_root,
        include_runtime_artifacts=include_runtime_artifacts,
        max_file_bytes=max_file_bytes,
    )
    newest = 0.0
    for row in paths:
        try:
            newest = max(newest, row.path.stat().st_mtime)
        except OSError:
            continue
    return newest


def _walk_scan_root(
    base: Path,
    *,
    repo_root: Path,
    include_runtime_artifacts: bool,
    max_file_bytes: int,
    accounting: ShimScanAccounting,
    visited_dirs: set[Path] | None = None,
    ignored_paths: set[Path] | None = None,
) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(base):
        current = Path(dirpath)
        if visited_dirs is not None:
            visited_dirs.add(current)
        kept_dirs: list[str] = []
        for name in dirnames:
            child = current / name
            rel_parts = child.relative_to(repo_root).parts if child.is_relative_to(repo_root) else child.parts
            if child.is_symlink() or _skip_dir(
                name,
                rel_parts=rel_parts,
                include_runtime_artifacts=include_runtime_artifacts,
            ):
                accounting.skipped_dirs += 1
                _append_sample(accounting.skipped_dir_samples, event_artifact_paths.artifact_display_path(child, repo_root=repo_root))
            else:
                kept_dirs.append(name)
        dirnames[:] = kept_dirs
        for filename in filenames:
            path = current / filename
            if path.is_symlink():
                accounting.skipped_symlink_files += 1
                continue
            if _skip_file(path, repo_root=repo_root, max_file_bytes=max_file_bytes, accounting=accounting):
                if (
                    ignored_paths is not None
                    and path.suffix not in DEFAULT_SHIM_SCAN_EXCLUDE_SUFFIXES
                    and path.suffix in {".json", ".jsonl", ".md", ".txt", ".yml", ".yaml"}
                ):
                    ignored_paths.add(path)
                continue
            yield path


def _skip_dir(name: str, *, rel_parts: tuple[str, ...], include_runtime_artifacts: bool) -> bool:
    if include_runtime_artifacts and name in _RUNTIME_ARTIFACT_ROOTS:
        return False
    return name in DEFAULT_SHIM_SCAN_EXCLUDE_DIRS or any(part in DEFAULT_SHIM_SCAN_EXCLUDE_DIRS for part in rel_parts[:-1])


def _skip_file(
    path: Path,
    *,
    repo_root: Path,
    max_file_bytes: int,
    accounting: ShimScanAccounting,
) -> bool:
    rel_path = event_artifact_paths.artifact_display_path(path, repo_root=repo_root)
    if path.suffix in DEFAULT_SHIM_SCAN_EXCLUDE_SUFFIXES:
        accounting.skipped_suffix_files += 1
        return True
    try:
        size = path.stat().st_size
    except OSError:
        return True
    if path.suffix != ".py" and size > max_file_bytes:
        accounting.skipped_large_files += 1
        _append_sample(accounting.skipped_large_file_samples, rel_path)
        if rel_path.startswith("event_fade_cache/"):
            accounting.skipped_artifact_files += 1
        return True
    return False


def _is_historical_report_artifact(rel_path: str) -> bool:
    name = Path(rel_path).name
    if not any(name.startswith(prefix) for prefix in _HISTORICAL_REPORT_PREFIXES):
        return False
    return rel_path == name or rel_path.startswith("research/")


def _allowed_scan_file(path: Path, *, rel_path: str, include_runtime_artifacts: bool) -> bool:
    if rel_path == "Makefile":
        return True
    if rel_path.startswith("event_fade_cache/"):
        return include_runtime_artifacts and path.suffix in {".json", ".jsonl", ".md", ".txt", ".yml", ".yaml"}
    return path.suffix in {".py", ".md", ".json", ".txt", ".yml", ".yaml"}


def _top_level_scan_files(repo_root: Path) -> tuple[Path, ...]:
    rows = [repo_root / "Makefile"]
    rows.extend(repo_root / name for name in _TOP_LEVEL_DOCS)
    rows.extend(path for path in repo_root.glob("*.md") if path.name not in _TOP_LEVEL_DOCS)
    return tuple(
        path
        for path in rows
        if path.exists() and path.is_file() and not path.is_symlink()
    )


def _count_files(base: Path) -> int:
    count = 0
    for _dirpath, _dirnames, filenames in os.walk(base):
        count += len(filenames)
    return count


def _reference_category(rel_path: str) -> str:
    if rel_path == "Makefile":
        return "makefile_references"
    if rel_path.startswith("tests/"):
        return "test_import_references"
    if rel_path.startswith("scripts/"):
        return "script_references"
    if rel_path.startswith("research/") or rel_path.startswith("event_fade_cache/"):
        return "artifact_doc_references"
    if rel_path.endswith(".md") or rel_path in _TOP_LEVEL_DOCS:
        return "docs_references"
    return "internal_import_references"


def _scan_python_import_references(
    text: str,
    *,
    rel_path: str,
    category: str,
    matcher: _Matcher,
    refs: dict[str, dict[str, list[dict[str, object]]]],
) -> None:
    try:
        tree = ast.parse(text, filename=rel_path)
    except SyntaxError:
        return
    lines = text.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                old_module = _old_module_for_import_name(alias.name, matcher.old_modules)
                if old_module:
                    _add_ref(refs, old_module, category, rel_path, node.lineno, "import", alias.name, lines)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                for alias in node.names:
                    import_name = _resolve_relative_import_name(
                        rel_path,
                        level=node.level,
                        module=node.module,
                        alias_name=alias.name,
                    )
                    old_module = _old_module_for_import_name(import_name, matcher.old_modules)
                    if old_module:
                        detail = f"relative_from:{'.' * node.level}{node.module or ''}:{alias.name}"
                        _add_ref(refs, old_module, category, rel_path, node.lineno, "relative_import", detail, lines)
            else:
                if node.module == "crypto_rsi_scanner":
                    for alias in node.names:
                        old_module = matcher.old_by_leaf.get(alias.name)
                        if old_module:
                            detail = f"from_package:{node.module}:{alias.name}"
                            _add_ref(refs, old_module, category, rel_path, node.lineno, "from_package_import", detail, lines)
                old_module = _old_module_for_import_name(node.module or "", matcher.old_modules)
                if old_module:
                    _add_ref(refs, old_module, category, rel_path, node.lineno, "from_import", node.module or "", lines)


def _scan_text_references(
    text: str,
    *,
    path: Path,
    rel_path: str,
    category: str,
    matcher: _Matcher,
    refs: dict[str, dict[str, list[dict[str, object]]]],
) -> None:
    if _REFERENCE_PREFIX not in text:
        return
    if (
        path.suffix == ".py"
        and category != "test_import_references"
        and "import_module" not in text
        and "__import__" not in text
    ):
        return
    lines = text.splitlines()
    for lineno, line in enumerate(lines, start=1):
        if _REFERENCE_PREFIX not in line:
            continue
        for old_module, regex in matcher.regexes.items():
            if old_module not in line or not regex.search(line):
                continue
            if path.suffix == ".py" and _line_is_static_import(line, old_module):
                continue
            ref_category = category
            ref_type = "text_reference"
            if path.suffix == ".py" and _line_looks_dynamic_import(line, old_module):
                ref_category = "dynamic_import_references"
                ref_type = "dynamic_import"
            elif path.suffix == ".py" and category != "test_import_references":
                continue
            _add_ref(refs, old_module, ref_category, rel_path, lineno, ref_type, old_module, lines)


def _old_module_for_import_name(name: str, old_modules: dict[str, Any]) -> str | None:
    for old_module in old_modules:
        if name == old_module or name.startswith(f"{old_module}."):
            return old_module
    return None


def _resolve_relative_import_name(
    rel_path: str,
    *,
    level: int,
    module: str | None,
    alias_name: str,
) -> str:
    current_module = rel_path[:-3].replace("/", ".") if rel_path.endswith(".py") else rel_path.replace("/", ".")
    package_parts = current_module.split(".")[:-1]
    if level > 1:
        package_parts = package_parts[: max(0, len(package_parts) - (level - 1))]
    if module:
        return ".".join([*package_parts, *module.split(".")])
    return ".".join([*package_parts, alias_name])


def _add_ref(
    refs: dict[str, dict[str, list[dict[str, object]]]],
    old_module: str,
    category: str,
    path: str,
    line: int,
    reference_type: str,
    detail: str,
    lines: list[str],
) -> None:
    if old_module not in refs or category not in refs[old_module]:
        return
    snippet = lines[line - 1].strip() if 0 <= line - 1 < len(lines) else ""
    payload = {
        "path": path,
        "line": line,
        "reference_type": reference_type,
        "detail": detail,
        "snippet": snippet[:220],
    }
    bucket = refs[old_module][category]
    dedupe_key = (payload["path"], payload["line"], payload["reference_type"], payload["detail"])
    if not any((row["path"], row["line"], row["reference_type"], row["detail"]) == dedupe_key for row in bucket):
        bucket.append(payload)


def _line_is_static_import(line: str, old_module: str) -> bool:
    stripped = line.strip()
    return bool(
        re.match(rf"from\s+{re.escape(old_module)}(\s+|\.)", stripped)
        or re.match(rf"import\s+{re.escape(old_module)}(\s|$|,|\.)", stripped)
    )


def _line_looks_dynamic_import(line: str, old_module: str) -> bool:
    return old_module in line and ("import_module" in line or "__import__" in line)


def _append_sample(samples: list[str], value: str) -> None:
    if len(samples) < 10:
        samples.append(value)
