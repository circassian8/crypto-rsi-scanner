"""Process-local, mutation-aware source cache for static project-health scans.

Project-health reports intentionally inspect the same Python files several times
in one process. Re-reading and reparsing every file for each report adds no
coverage, so this module shares immutable text/AST snapshots while validating a
strong file signature before every reuse. New/deleted files are still detected
by each caller's normal directory inventory.
"""

from __future__ import annotations

import ast
import os
import stat
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from threading import RLock


_MAX_CACHE_ENTRIES = 4096
_UNPARSED = object()


@dataclass(frozen=True)
class FileSignature:
    device: int
    inode: int
    mode: int
    size: int
    mtime_ns: int
    ctime_ns: int


@dataclass
class _SourceRecord:
    signature: FileSignature
    text: str
    line_count: int
    tree: ast.AST | None | object = _UNPARSED


_CACHE: OrderedDict[str, _SourceRecord] = OrderedDict()
_LOCK = RLock()
_STATS = {
    "text_hits": 0,
    "text_misses": 0,
    "ast_hits": 0,
    "ast_misses": 0,
    "invalidations": 0,
}


def source_text(path: str | Path) -> str | None:
    """Return decoded source text, or ``None`` for missing/non-regular files."""

    record = _source_record(Path(path))
    return record.text if record is not None else None


def source_line_count(path: str | Path) -> int:
    """Return a cached ``splitlines`` count, preserving the old zero-on-error API."""

    record = _source_record(Path(path))
    return record.line_count if record is not None else 0


def source_ast(path: str | Path) -> ast.AST | None:
    """Return a cached AST; syntax/read failures remain fail-soft for inventories."""

    record = _source_record(Path(path))
    if record is None:
        return None
    key = _cache_key(Path(path))
    with _LOCK:
        if record.tree is not _UNPARSED:
            _STATS["ast_hits"] += 1
            return record.tree if isinstance(record.tree, ast.AST) else None
        _STATS["ast_misses"] += 1
        try:
            record.tree = ast.parse(record.text, filename=key)
        except SyntaxError:
            record.tree = None
        return record.tree if isinstance(record.tree, ast.AST) else None


def source_signature(path: str | Path) -> FileSignature | None:
    """Return the validated identity used for downstream per-file memoization."""

    record = _source_record(Path(path))
    return record.signature if record is not None else None


def cache_info() -> dict[str, int]:
    """Return bounded process-cache accounting for diagnostics and tests."""

    with _LOCK:
        return {**_STATS, "entries": len(_CACHE), "max_entries": _MAX_CACHE_ENTRIES}


def clear_source_cache(*, root: str | Path | None = None) -> None:
    """Clear all entries or only entries below ``root`` (primarily for tests)."""

    with _LOCK:
        if root is None:
            _CACHE.clear()
        else:
            root_path = Path(root).expanduser().absolute()
            for key in tuple(_CACHE):
                try:
                    Path(key).relative_to(root_path)
                except ValueError:
                    continue
                _CACHE.pop(key, None)
        for name in _STATS:
            _STATS[name] = 0


def _source_record(path: Path) -> _SourceRecord | None:
    absolute = path.expanduser().absolute()
    key = _cache_key(absolute)
    try:
        signature = _path_signature(absolute)
    except OSError:
        _discard(key)
        return None
    if not stat.S_ISREG(signature.mode):
        _discard(key)
        return None
    with _LOCK:
        cached = _CACHE.get(key)
        if cached is not None and cached.signature == signature:
            _STATS["text_hits"] += 1
            _CACHE.move_to_end(key)
            return cached
        if cached is not None:
            _STATS["invalidations"] += 1
        _STATS["text_misses"] += 1
    try:
        data, opened_signature = _read_regular_file(absolute, expected=signature)
    except OSError:
        _discard(key)
        return None
    text = data.decode("utf-8", errors="replace")
    record = _SourceRecord(
        signature=opened_signature,
        text=text,
        line_count=len(text.splitlines()),
    )
    with _LOCK:
        _CACHE[key] = record
        _CACHE.move_to_end(key)
        while len(_CACHE) > _MAX_CACHE_ENTRIES:
            _CACHE.popitem(last=False)
    return record


def _read_regular_file(path: Path, *, expected: FileSignature) -> tuple[bytes, FileSignature]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        before = _signature_from_stat(os.fstat(descriptor))
        if not stat.S_ISREG(before.mode) or (before.device, before.inode) != (expected.device, expected.inode):
            raise OSError("source file changed while opening")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = _signature_from_stat(os.fstat(descriptor))
        if after != before:
            raise OSError("source file changed while reading")
        return b"".join(chunks), after
    finally:
        os.close(descriptor)


def _path_signature(path: Path) -> FileSignature:
    return _signature_from_stat(path.lstat())


def _signature_from_stat(row: os.stat_result) -> FileSignature:
    return FileSignature(
        device=int(row.st_dev),
        inode=int(row.st_ino),
        mode=int(row.st_mode),
        size=int(row.st_size),
        mtime_ns=int(row.st_mtime_ns),
        ctime_ns=int(row.st_ctime_ns),
    )


def _cache_key(path: Path) -> str:
    return str(path.expanduser().absolute())


def _discard(key: str) -> None:
    with _LOCK:
        _CACHE.pop(key, None)


__all__ = [
    "cache_info",
    "clear_source_cache",
    "source_ast",
    "source_line_count",
    "source_signature",
    "source_text",
]
