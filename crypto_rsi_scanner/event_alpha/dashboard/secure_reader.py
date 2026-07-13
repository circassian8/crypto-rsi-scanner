"""Descriptor-anchored, read-once access to one dashboard namespace."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Mapping

from ..artifacts import fingerprints


_CHANGED_ERRNO = getattr(errno, "ESTALE", errno.EIO)


class _DashboardNamespaceReadError(RuntimeError):
    """Raised when the configured artifact namespace cannot remain anchored."""


@dataclass(frozen=True)
class AnchoredNamespaceReader:
    """Read immutable buffers relative to one already-open namespace directory."""

    namespace_dir: Path
    base_fd: int
    namespace_fd: int
    namespace_name: str
    namespace_identity: os.stat_result

    def assert_current(self) -> None:
        _assert_namespace_identity(
            self.base_fd,
            self.namespace_name,
            self.namespace_identity,
        )

    def read_bytes(self, relative: str | Path) -> tuple[bytes | None, str | None]:
        return _read_relative_bytes(self, relative)

    def fingerprint_directory(
        self,
        relative: str | Path,
    ) -> tuple[dict[str, object] | None, str | None]:
        return _fingerprint_relative_directory(self, relative)


@contextmanager
def open_anchored_namespace(namespace_dir: Path) -> Iterator[AnchoredNamespaceReader]:
    """Anchor the artifact base and namespace for one coherent load attempt."""

    base_fd: int | None = None
    namespace_fd: int | None = None
    reader: AnchoredNamespaceReader | None = None
    target = Path(namespace_dir).expanduser().absolute()
    try:
        _require_descriptor_support()
        base_fd, _base_identity = _open_directory_path(target.parent)
        before = os.stat(target.name, dir_fd=base_fd, follow_symlinks=False)
        if not stat.S_ISDIR(before.st_mode):
            raise OSError(errno.ENOTDIR, "dashboard namespace is not a directory")
        namespace_fd = os.open(target.name, _directory_flags(), dir_fd=base_fd)
        opened = os.fstat(namespace_fd)
        if not stat.S_ISDIR(opened.st_mode) or not _same_file(before, opened):
            raise OSError(_CHANGED_ERRNO, "dashboard namespace changed while opening")
        reader = AnchoredNamespaceReader(
            namespace_dir=target,
            base_fd=base_fd,
            namespace_fd=namespace_fd,
            namespace_name=target.name,
            namespace_identity=opened,
        )
        reader.assert_current()
        yield reader
        reader.assert_current()
    except _DashboardNamespaceReadError:
        raise
    except OSError as exc:
        raise _DashboardNamespaceReadError(
            "dashboard artifact namespace changed or is unsafe"
        ) from exc
    finally:
        if namespace_fd is not None:
            os.close(namespace_fd)
        if base_fd is not None:
            os.close(base_fd)


def _read_relative_bytes(
    reader: AnchoredNamespaceReader,
    relative: str | Path,
) -> tuple[bytes | None, str | None]:
    parts, path_error = _relative_parts(relative)
    if path_error:
        return None, path_error
    parent_fd: int | None = None
    try:
        reader.assert_current()
        parent_fd, parent_error = _open_relative_parent(reader.namespace_fd, parts[:-1])
        if parent_error or parent_fd is None:
            return None, parent_error
        data, read_error = _read_file_at(parent_fd, parts[-1])
        reader.assert_current()
        return data, read_error
    except OSError:
        return None, "artifact_changed_during_read"
    finally:
        if parent_fd is not None:
            os.close(parent_fd)


def _fingerprint_relative_directory(
    reader: AnchoredNamespaceReader,
    relative: str | Path,
) -> tuple[dict[str, object] | None, str | None]:
    parts, path_error = _relative_parts(relative)
    if path_error:
        return None, path_error
    root_fd: int | None = None
    try:
        reader.assert_current()
        root_fd, directory_error = _open_relative_directory(reader.namespace_fd, parts)
        if directory_error:
            return None, directory_error
        before = _directory_snapshot(root_fd)
        digest = hashlib.sha256(b"event-alpha-directory-tree-v1\0")
        total_size = 0
        file_count = 0
        for relative_name, kind, _identity in before:
            if kind == "directory":
                continue
            data, read_error = _read_file_below(root_fd, PurePosixPath(relative_name))
            if read_error or data is None:
                return None, read_error or "artifact_unreadable"
            path_bytes = relative_name.encode("utf-8")
            digest.update(len(path_bytes).to_bytes(8, "big"))
            digest.update(path_bytes)
            digest.update(len(data).to_bytes(8, "big"))
            digest.update(data)
            total_size += len(data)
            file_count += 1
        if before != _directory_snapshot(root_fd):
            return None, "directory_changed_during_fingerprint"
        reader.assert_current()
        return {
            "sha256": digest.hexdigest(),
            "size_bytes": total_size,
            "item_count": file_count,
            "fingerprint_kind": fingerprints.DIRECTORY_TREE_KIND,
            "fingerprint_contract_version": fingerprints.FINGERPRINT_CONTRACT_VERSION,
        }, None
    except OSError:
        return None, "directory_changed_during_fingerprint"
    finally:
        if root_fd is not None:
            os.close(root_fd)


def verify_run_ledger_bytes(
    data: bytes,
    expected: Mapping[str, Any],
) -> tuple[bool, str | None]:
    """Verify one canonical run row from an already-read ledger buffer."""

    identity = expected.get("run_row_identity")
    if not isinstance(identity, Mapping):
        return False, "run_row_identity_incomplete"
    wanted = _run_identity(identity)
    if not all(wanted.values()):
        return False, "run_row_identity_incomplete"
    if expected.get("run_row_match_count") != 1:
        return False, "run_row_match_count_invalid"
    matches: list[dict[str, Any]] = []
    try:
        for line_number, line in enumerate(data.decode("utf-8").splitlines(), 1):
            if not line.strip():
                continue
            parsed = json.loads(line, object_pairs_hook=_unique_json_object)
            if not isinstance(parsed, Mapping):
                return False, f"run_ledger_row_not_object:{line_number}"
            row = dict(parsed)
            if _run_identity(row) == wanted:
                matches.append(row)
    except UnicodeDecodeError:
        return False, "run_ledger_invalid_utf8"
    except ValueError:
        return False, "run_ledger_invalid_jsonl"
    if len(matches) != 1:
        return False, f"run_row_match_count_mismatch:{len(matches)}"
    try:
        actual = fingerprints.canonical_run_row_fingerprint(matches[0])
    except fingerprints.FingerprintError as exc:
        return False, str(exc)
    return compare_fingerprint_values(actual, expected)


def compare_fingerprint_values(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> tuple[bool, str | None]:
    for field in fingerprints.FINGERPRINT_FIELDS:
        if actual.get(field) != expected.get(field):
            return False, f"fingerprint_content_mismatch:{field}"
    return True, None


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


def _run_identity(value: Mapping[str, Any]) -> dict[str, str]:
    return {
        field: str(value.get(field) or "").strip()
        for field in ("run_id", "profile", "artifact_namespace")
    }


def _read_file_below(
    root_fd: int,
    relative: PurePosixPath,
) -> tuple[bytes | None, str | None]:
    parent_fd, error = _open_relative_parent(root_fd, relative.parts[:-1])
    if error or parent_fd is None:
        return None, error
    try:
        return _read_file_at(parent_fd, relative.parts[-1])
    finally:
        os.close(parent_fd)


def _open_relative_parent(
    root_fd: int,
    parts: tuple[str, ...],
) -> tuple[int | None, str | None]:
    current = os.dup(root_fd)
    for part in parts:
        next_fd, error = _open_directory_at(current, part)
        os.close(current)
        if error or next_fd is None:
            return None, error or "artifact_path_unreadable"
        current = next_fd
    return current, None


def _open_relative_directory(
    root_fd: int,
    parts: tuple[str, ...],
) -> tuple[int | None, str | None]:
    parent_fd, error = _open_relative_parent(root_fd, parts[:-1])
    if error or parent_fd is None:
        return None, error
    try:
        return _open_directory_at(parent_fd, parts[-1])
    finally:
        os.close(parent_fd)


def _open_directory_at(parent_fd: int, name: str) -> tuple[int | None, str | None]:
    try:
        before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None, "artifact_missing"
    except OSError:
        return None, "artifact_path_unreadable"
    if stat.S_ISLNK(before.st_mode):
        return None, "artifact_symlink_not_allowed"
    if not stat.S_ISDIR(before.st_mode):
        return None, "artifact_kind_mismatch"
    try:
        descriptor = os.open(name, _directory_flags(), dir_fd=parent_fd)
        opened = os.fstat(descriptor)
    except OSError:
        return None, "artifact_path_unreadable"
    if not stat.S_ISDIR(opened.st_mode) or not _same_snapshot(before, opened):
        os.close(descriptor)
        return None, "artifact_changed_during_read"
    return descriptor, None


def _read_file_at(parent_fd: int, leaf: str) -> tuple[bytes | None, str | None]:
    descriptor: int | None = None
    try:
        before = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
        if stat.S_ISLNK(before.st_mode):
            return None, "artifact_symlink_not_allowed"
        if not stat.S_ISREG(before.st_mode):
            return None, "artifact_kind_mismatch"
        descriptor = os.open(leaf, _file_flags(), dir_fd=parent_fd)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or not _same_snapshot(before, opened):
            return None, "artifact_changed_during_read"
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after_fd = os.fstat(descriptor)
        after_path = os.stat(leaf, dir_fd=parent_fd, follow_symlinks=False)
        data = b"".join(chunks)
        if (
            not _same_snapshot(opened, after_fd)
            or not _same_snapshot(opened, after_path)
            or len(data) != after_fd.st_size
        ):
            return None, "artifact_changed_during_read"
        return data, None
    except FileNotFoundError:
        return None, "artifact_missing"
    except OSError:
        return None, "artifact_unreadable_or_symlink"
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _directory_snapshot(root_fd: int) -> tuple[tuple[str, str, tuple[int, ...]], ...]:
    rows: list[tuple[str, str, tuple[int, ...]]] = []

    def visit(directory_fd: int, prefix: PurePosixPath) -> None:
        for name in sorted(os.listdir(directory_fd)):
            info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            relative = (prefix / name).as_posix()
            if stat.S_ISLNK(info.st_mode):
                raise OSError(errno.ELOOP, "directory symlink is not allowed")
            if stat.S_ISDIR(info.st_mode):
                kind = "directory"
            elif stat.S_ISREG(info.st_mode):
                kind = "file"
            else:
                raise OSError(errno.EINVAL, "non-regular directory entry")
            rows.append((relative, kind, _snapshot_identity(info)))
            if kind == "directory":
                child_fd, error = _open_directory_at(directory_fd, name)
                if error or child_fd is None:
                    raise OSError(_CHANGED_ERRNO, error or "directory changed")
                try:
                    visit(child_fd, prefix / name)
                finally:
                    os.close(child_fd)

    visit(root_fd, PurePosixPath())
    return tuple(sorted(rows, key=lambda row: row[0]))


def _relative_parts(relative: str | Path) -> tuple[tuple[str, ...], str | None]:
    raw = Path(relative)
    if raw.is_absolute() or not raw.parts or any(part in {"", ".", ".."} for part in raw.parts):
        return (), "artifact_path_escape"
    return tuple(raw.parts), None


def _open_directory_path(path: Path) -> tuple[int, os.stat_result]:
    before = os.stat(path, follow_symlinks=False)
    if not stat.S_ISDIR(before.st_mode):
        raise OSError(errno.ENOTDIR, "dashboard artifact base is not a directory")
    descriptor = os.open(path, _directory_flags())
    opened = os.fstat(descriptor)
    if not stat.S_ISDIR(opened.st_mode) or not _same_file(before, opened):
        os.close(descriptor)
        raise OSError(_CHANGED_ERRNO, "dashboard artifact base changed while opening")
    return descriptor, opened


def _assert_namespace_identity(
    base_fd: int,
    namespace: str,
    expected: os.stat_result,
) -> None:
    current = os.stat(namespace, dir_fd=base_fd, follow_symlinks=False)
    if not stat.S_ISDIR(current.st_mode) or not _same_file(current, expected):
        raise OSError(_CHANGED_ERRNO, "dashboard namespace changed during access")


def _require_descriptor_support() -> None:
    if not (
        os.open in os.supports_dir_fd
        and os.stat in os.supports_dir_fd
        and os.stat in os.supports_follow_symlinks
        and hasattr(os, "O_DIRECTORY")
        and hasattr(os, "O_NOFOLLOW")
    ):
        raise _DashboardNamespaceReadError(
            "descriptor-relative no-follow dashboard access is unsupported"
        )


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


def _file_flags() -> int:
    return os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _snapshot_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _same_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    return _snapshot_identity(left) == _snapshot_identity(right)


__all__ = (
    "AnchoredNamespaceReader",
    "compare_fingerprint_values",
    "open_anchored_namespace",
    "verify_run_ledger_bytes",
)
