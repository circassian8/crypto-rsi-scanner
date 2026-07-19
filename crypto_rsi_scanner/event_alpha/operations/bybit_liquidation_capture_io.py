"""Capture-local path, secret, and atomic publication guards.

This is deliberately not a general provider or artifact framework.  It exists
only to keep the detached Bybit liquidation transcript boundary small enough
to audit while holding directory descriptors across source reads and bundle
publication.
"""

from __future__ import annotations

from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
import errno
import fcntl
import os
from pathlib import Path
import stat
import sys
import time
from typing import Iterator, Sequence

from . import common


_FORBIDDEN_SOURCE_PARTS = frozenset(
    {"fixture", "fixtures", "mock", "mocks", "replay", "replays", "test", "tests"}
)
_RENAME_EXCL = 0x00000004
_RENAME_NOREPLACE = 0x00000001


class BybitLiquidationCaptureIOError(RuntimeError):
    """Fail-closed local I/O or secret-classification error."""


@dataclass(frozen=True)
class _AnchoredCaptureBase:
    path: Path
    descriptor: int
    identity: os.stat_result
    exclusive: bool


def _directory_flags() -> int:
    return (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        _same_identity(left, right)
        and left.st_mode == right.st_mode
        and left.st_nlink == right.st_nlink
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
        and left.st_ctime_ns == right.st_ctime_ns
    )


def _absolute(path: str | Path) -> Path:
    raw = os.fspath(path)
    if raw == "~" or raw.startswith("~/"):
        raise BybitLiquidationCaptureIOError("tilde_path_rejected")
    return Path(os.path.abspath(raw))


def _require_canonical(path: str | Path, *, reason: str) -> Path:
    candidate = _absolute(path)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise BybitLiquidationCaptureIOError(reason) from exc
    if resolved != candidate:
        raise BybitLiquidationCaptureIOError("symlinked_ancestry_rejected")
    return candidate


def _open_directory_chain(directory: Path) -> int:
    """Open every absolute path component with no-follow and identity checks."""

    if not directory.is_absolute() or directory.anchor != os.sep:
        raise BybitLiquidationCaptureIOError("anchored_directory_required")
    descriptor: int | None = None
    try:
        descriptor = os.open(os.sep, _directory_flags())
        for part in directory.parts[1:]:
            before = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
            if not stat.S_ISDIR(before.st_mode):
                raise BybitLiquidationCaptureIOError("symlinked_ancestry_rejected")
            next_descriptor = os.open(part, _directory_flags(), dir_fd=descriptor)
            opened = os.fstat(next_descriptor)
            if not stat.S_ISDIR(opened.st_mode) or not _same_identity(before, opened):
                os.close(next_descriptor)
                raise BybitLiquidationCaptureIOError("symlinked_ancestry_rejected")
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except BybitLiquidationCaptureIOError:
        if descriptor is not None:
            os.close(descriptor)
        raise
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        raise BybitLiquidationCaptureIOError("anchored_directory_unavailable") from exc


def canonical_existing_directory(path: str | Path) -> Path:
    with hold_anchored_base(path, exclusive=False) as anchored:
        return anchored.path


@contextmanager
def hold_anchored_base(
    artifact_base: str | Path,
    *,
    exclusive: bool,
) -> Iterator[_AnchoredCaptureBase]:
    """Hold one fully anchored base and a cooperating-reader/writer flock."""

    base = _absolute(artifact_base)
    descriptor: int | None = None
    verification_descriptor: int | None = None
    locked = False
    try:
        initial = os.stat(base, follow_symlinks=False)
        descriptor = _open_directory_chain(base)
        opened = os.fstat(descriptor)
        resolved = base.resolve(strict=True)
        current = os.stat(base, follow_symlinks=False)
        if resolved != base:
            raise BybitLiquidationCaptureIOError("symlinked_ancestry_rejected")
        if (
            not stat.S_ISDIR(opened.st_mode)
            or not _same_identity(initial, opened)
            or not _same_identity(opened, current)
        ):
            raise BybitLiquidationCaptureIOError("artifact_base_identity_drift")
        fcntl.flock(descriptor, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        locked = True
        yield _AnchoredCaptureBase(base, descriptor, opened, exclusive)
        try:
            completed = os.fstat(descriptor)
            resolved_before_rewalk = base.resolve(strict=True)
            path_before_rewalk = os.stat(base, follow_symlinks=False)
            verification_descriptor = _open_directory_chain(base)
            verified = os.fstat(verification_descriptor)
            path_after_rewalk = os.stat(base, follow_symlinks=False)
            resolved_after_rewalk = base.resolve(strict=True)
            if (
                resolved_before_rewalk != base
                or resolved_after_rewalk != base
                or not _same_identity(opened, completed)
                or not _same_identity(completed, path_before_rewalk)
                or not _same_identity(completed, verified)
                or not _same_identity(completed, path_after_rewalk)
            ):
                raise BybitLiquidationCaptureIOError(
                    "artifact_base_identity_drift"
                )
        except (BybitLiquidationCaptureIOError, OSError) as exc:
            raise BybitLiquidationCaptureIOError(
                "artifact_base_identity_drift"
            ) from exc
    except BybitLiquidationCaptureIOError:
        raise
    except OSError as exc:
        raise BybitLiquidationCaptureIOError("artifact_base_unavailable") from exc
    finally:
        if verification_descriptor is not None:
            os.close(verification_descriptor)
        if locked and descriptor is not None:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        if descriptor is not None:
            os.close(descriptor)


@contextmanager
def open_namespace_at(
    anchored: _AnchoredCaptureBase,
    namespace: str,
) -> Iterator[int]:
    """Open one child relative to a base descriptor held by the caller."""

    child = _safe_leaf(namespace)
    namespace_fd: int | None = None
    try:
        if not _same_identity(anchored.identity, os.fstat(anchored.descriptor)):
            raise BybitLiquidationCaptureIOError("artifact_base_identity_drift")
        before = os.stat(
            child,
            dir_fd=anchored.descriptor,
            follow_symlinks=False,
        )
        if not stat.S_ISDIR(before.st_mode):
            raise BybitLiquidationCaptureIOError("capture_artifact_unreadable")
        namespace_fd = os.open(
            child,
            _directory_flags(),
            dir_fd=anchored.descriptor,
        )
        opened = os.fstat(namespace_fd)
        if not _same_identity(before, opened):
            raise BybitLiquidationCaptureIOError("capture_namespace_identity_drift")
        yield namespace_fd
        after = os.stat(
            child,
            dir_fd=anchored.descriptor,
            follow_symlinks=False,
        )
        if not _same_identity(opened, after):
            raise BybitLiquidationCaptureIOError("capture_namespace_identity_drift")
    except BybitLiquidationCaptureIOError:
        raise
    except OSError as exc:
        raise BybitLiquidationCaptureIOError("capture_artifact_unreadable") from exc
    finally:
        if namespace_fd is not None:
            os.close(namespace_fd)


@contextmanager
def open_anchored_namespace(
    artifact_base: str | Path,
    namespace: str,
) -> Iterator[int]:
    """Hold the full no-follow base ancestry and one exact child directory."""

    with hold_anchored_base(artifact_base, exclusive=False) as anchored:
        with open_namespace_at(anchored, namespace) as namespace_fd:
            yield namespace_fd


def _directory_descends_from(
    directory_fd: int,
    ancestor: _AnchoredCaptureBase,
) -> bool:
    """Compare real directory ancestry using held descriptors, not path text."""

    if not _same_identity(ancestor.identity, os.fstat(ancestor.descriptor)):
        raise BybitLiquidationCaptureIOError("artifact_base_identity_drift")
    current_fd: int | None = None
    try:
        current_fd = os.dup(directory_fd)
        for _depth in range(256):
            current = os.fstat(current_fd)
            if _same_identity(current, ancestor.identity):
                return True
            parent_fd = os.open("..", _directory_flags(), dir_fd=current_fd)
            try:
                parent = os.fstat(parent_fd)
            except OSError:
                os.close(parent_fd)
                raise
            if _same_identity(current, parent):
                os.close(parent_fd)
                return False
            os.close(current_fd)
            current_fd = parent_fd
        raise BybitLiquidationCaptureIOError("source_parent_ancestry_unbounded")
    except BybitLiquidationCaptureIOError:
        raise
    except OSError as exc:
        raise BybitLiquidationCaptureIOError(
            "source_parent_ancestry_unavailable"
        ) from exc
    finally:
        if current_fd is not None:
            os.close(current_fd)


def read_operator_file(
    path: str | Path,
    *,
    maximum_bytes: int,
    forbidden_ancestor: _AnchoredCaptureBase | None = None,
) -> tuple[Path, bytes]:
    """Read one canonical, single-link file through its fully anchored ancestry."""

    source = _require_canonical(path, reason="source_transcript_unreadable")
    if any(
        part.casefold() in _FORBIDDEN_SOURCE_PARTS
        or Path(part.casefold()).stem in _FORBIDDEN_SOURCE_PARTS
        for part in source.parts
    ):
        raise BybitLiquidationCaptureIOError("operator_source_path_rejected")
    parent_fd: int | None = None
    descriptor: int | None = None
    try:
        parent_before = os.stat(source.parent, follow_symlinks=False)
        if not stat.S_ISDIR(parent_before.st_mode):
            raise BybitLiquidationCaptureIOError("source_transcript_unreadable")
        parent_fd = _open_directory_chain(source.parent)
        parent_opened = os.fstat(parent_fd)
        if not _same_identity(parent_before, parent_opened):
            raise BybitLiquidationCaptureIOError("source_transcript_unreadable")
        if forbidden_ancestor is not None and _directory_descends_from(
            parent_fd, forbidden_ancestor
        ):
            raise BybitLiquidationCaptureIOError(
                "source_transcript_inside_artifact_base"
            )
        before = os.stat(source.name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise BybitLiquidationCaptureIOError("source_transcript_unreadable")
        descriptor = os.open(
            source.name,
            os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent_fd,
        )
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or not _same_file(before, opened):
            raise BybitLiquidationCaptureIOError("source_transcript_unreadable")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            raw = handle.read(maximum_bytes + 1)
            completed = os.fstat(handle.fileno())
        after = os.stat(source.name, dir_fd=parent_fd, follow_symlinks=False)
        parent_after = os.stat(source.parent, follow_symlinks=False)
        if (
            len(raw) > maximum_bytes
            or len(raw) != after.st_size
            or not _same_file(opened, completed)
            or not _same_file(completed, after)
            or not _same_identity(parent_opened, parent_after)
        ):
            raise BybitLiquidationCaptureIOError("source_transcript_unreadable")
        if forbidden_ancestor is not None and _directory_descends_from(
            parent_fd, forbidden_ancestor
        ):
            raise BybitLiquidationCaptureIOError(
                "source_transcript_inside_artifact_base"
            )
        return source, raw
    except BybitLiquidationCaptureIOError:
        raise
    except OSError as exc:
        raise BybitLiquidationCaptureIOError("source_transcript_unreadable") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if parent_fd is not None:
            os.close(parent_fd)


def reject_secret_bytes(raw: bytes) -> None:
    """Apply the central secret-value classifier without returning secret text."""

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BybitLiquidationCaptureIOError("secret_scan_utf8_invalid") from exc
    direct_value_hit = any(
        pattern.search(text)
        for pattern in (
            common.OPENAI_KEY_RE,
            common.PROVIDER_TOKEN_VALUE_RE,
            common.TELEGRAM_BOT_TOKEN_VALUE_RE,
        )
    ) or "-----BEGIN PRIVATE KEY-----" in text.upper()
    if direct_value_hit or any(
        detail.get("status") == "blocker"
        for detail in common.classify_secret_hits_in_text(text)
    ):
        raise BybitLiquidationCaptureIOError("secret_or_auth_material_rejected")


def _safe_leaf(name: str) -> str:
    if (
        not isinstance(name, str)
        or not name
        or "\x00" in name
        or Path(name).name != name
        or name in {".", ".."}
    ):
        raise BybitLiquidationCaptureIOError("bundle_artifact_name_invalid")
    return name


def _rename_directory_noreplace(
    base_fd: int,
    source: str,
    destination: str,
) -> bool:
    """Atomically publish one directory without replacing a peer's leaf."""

    source = _safe_leaf(source)
    destination = _safe_leaf(destination)
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        rename = getattr(library, "renameatx_np", None)
        flags = _RENAME_EXCL
    elif sys.platform.startswith("linux"):
        rename = getattr(library, "renameat2", None)
        flags = _RENAME_NOREPLACE
    else:
        rename = None
        flags = 0
    if rename is None:
        raise BybitLiquidationCaptureIOError(
            "bundle_no_replace_rename_unsupported"
        )
    rename.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    rename.restype = ctypes.c_int
    ctypes.set_errno(0)
    result = rename(
        base_fd,
        os.fsencode(source),
        base_fd,
        os.fsencode(destination),
        flags,
    )
    if result == 0:
        return True
    error = ctypes.get_errno()
    if error in {errno.EEXIST, errno.ENOTEMPTY}:
        return False
    if error in {errno.ENOSYS, errno.ENOTSUP, errno.EINVAL}:
        raise BybitLiquidationCaptureIOError(
            "bundle_no_replace_rename_unsupported"
        )
    raise OSError(error, os.strerror(error))


def bounded_entry_names(directory_fd: int, *, maximum: int) -> frozenset[str]:
    if type(maximum) is not int or maximum < 0:
        raise BybitLiquidationCaptureIOError("directory_inventory_bound_invalid")
    names: set[str] = set()
    try:
        with os.scandir(directory_fd) as entries:
            for entry in entries:
                names.add(entry.name)
                if len(names) > maximum:
                    raise BybitLiquidationCaptureIOError(
                        "directory_inventory_bound_exceeded"
                    )
    except BybitLiquidationCaptureIOError:
        raise
    except OSError as exc:
        raise BybitLiquidationCaptureIOError("directory_inventory_unavailable") from exc
    return frozenset(names)


def _write_leaf(directory_fd: int, name: str, raw: bytes) -> None:
    """Injection seam used by the interruption/retry regression."""

    leaf = _safe_leaf(name)
    descriptor: int | None = None
    try:
        descriptor = os.open(
            leaf,
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=directory_fd,
        )
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise BybitLiquidationCaptureIOError("bundle_artifact_write_failed")
        with os.fdopen(descriptor, "w+b") as handle:
            descriptor = None
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
            handle.seek(0)
            persisted = handle.read(len(raw) + 1)
            completed = os.fstat(handle.fileno())
        after = os.stat(leaf, dir_fd=directory_fd, follow_symlinks=False)
        if (
            persisted != raw
            or len(raw) != completed.st_size
            or not stat.S_ISREG(completed.st_mode)
            or completed.st_nlink != 1
            or not _same_identity(opened, completed)
            or not _same_file(completed, after)
        ):
            raise BybitLiquidationCaptureIOError("bundle_artifact_write_failed")
    except BybitLiquidationCaptureIOError:
        raise
    except OSError as exc:
        raise BybitLiquidationCaptureIOError("bundle_artifact_write_failed") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def read_regular_at(directory_fd: int, name: str, *, maximum_bytes: int) -> bytes:
    """Read one unchanged, single-link bundle leaf through a held namespace fd."""

    leaf = _safe_leaf(name)
    descriptor: int | None = None
    try:
        before = os.stat(leaf, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise BybitLiquidationCaptureIOError("capture_artifact_unreadable")
        descriptor = os.open(
            leaf,
            os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
            dir_fd=directory_fd,
        )
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or not _same_file(before, opened):
            raise BybitLiquidationCaptureIOError("capture_artifact_unreadable")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            raw = handle.read(maximum_bytes + 1)
            completed = os.fstat(handle.fileno())
        after = os.stat(leaf, dir_fd=directory_fd, follow_symlinks=False)
        if (
            len(raw) > maximum_bytes
            or len(raw) != after.st_size
            or not _same_file(opened, completed)
            or not _same_file(completed, after)
        ):
            raise BybitLiquidationCaptureIOError("capture_artifact_unreadable")
        return raw
    except BybitLiquidationCaptureIOError:
        raise
    except OSError as exc:
        raise BybitLiquidationCaptureIOError("capture_artifact_unreadable") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _retain_staging_quarantine(
    base_fd: int,
    staging: str,
    staging_fd: int,
    expected_identity: os.stat_result,
    allowed_names: frozenset[str],
) -> tuple[str, ...]:
    """Verify and retain an interrupted stage without name-based deletion."""

    try:
        opened = os.fstat(staging_fd)
        current = os.stat(staging, dir_fd=base_fd, follow_symlinks=False)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or not stat.S_ISDIR(current.st_mode)
            or not _same_identity(expected_identity, opened)
            or not _same_identity(opened, current)
        ):
            raise BybitLiquidationCaptureIOError(
                "staging_quarantine_identity_drift"
            )
        actual = bounded_entry_names(staging_fd, maximum=len(allowed_names))
        if not actual <= allowed_names:
            raise BybitLiquidationCaptureIOError("staging_quarantine_unsafe")
        for name in actual:
            info = os.stat(name, dir_fd=staging_fd, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise BybitLiquidationCaptureIOError(
                    "staging_quarantine_unsafe"
                )
        current_after = os.stat(staging, dir_fd=base_fd, follow_symlinks=False)
        if not _same_identity(opened, current_after):
            raise BybitLiquidationCaptureIOError(
                "staging_quarantine_identity_drift"
            )
        # There is no portable conditional unlink-by-inode operation. Never
        # unlink a leaf or directory by name after a separate identity check:
        # an unowned replacement could win that gap. The unique tmp_ stage is
        # retained as explicit quarantine, and a retry uses a fresh name.
        return tuple(sorted(actual))
    except BybitLiquidationCaptureIOError:
        raise
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise BybitLiquidationCaptureIOError(
            "staging_quarantine_identity_drift"
        ) from exc
    except OSError as exc:
        raise BybitLiquidationCaptureIOError(
            "staging_quarantine_failed"
        ) from exc


def publish_bundle_atomically(
    anchored: _AnchoredCaptureBase,
    *,
    namespace: str,
    files: Sequence[tuple[str, bytes]],
) -> bool:
    """Publish a complete directory by one native no-replace rename.

    Returns ``False`` when a concurrent writer already published ``namespace``.
    Any interrupted sequential write remains private to a uniquely named
    ``tmp_`` quarantine directory. Nothing is unlinked or renamed through a
    mutable pathname during failure handling.
    """

    if not anchored.exclusive:
        raise BybitLiquidationCaptureIOError("exclusive_base_lock_required")
    base = anchored.path
    final = _safe_leaf(namespace)
    if not files or len({name for name, _raw in files}) != len(files):
        raise BybitLiquidationCaptureIOError("bundle_file_set_invalid")
    allowed = frozenset(_safe_leaf(name) for name, _raw in files)
    staging = f"tmp_bybit_liquidation_stage_{os.getpid()}_{time.time_ns()}"
    base_fd = anchored.descriptor
    staging_fd: int | None = None
    staging_identity: os.stat_result | None = None
    created_staging = False
    try:
        base_identity = os.fstat(base_fd)
        if not _same_identity(anchored.identity, base_identity):
            raise BybitLiquidationCaptureIOError("artifact_base_identity_drift")
        try:
            os.stat(final, dir_fd=base_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            return False
        os.mkdir(staging, 0o700, dir_fd=base_fd)
        created_staging = True
        staging_fd = os.open(staging, _directory_flags(), dir_fd=base_fd)
        staging_identity = os.fstat(staging_fd)
        named_staging = os.stat(
            staging,
            dir_fd=base_fd,
            follow_symlinks=False,
        )
        if not stat.S_ISDIR(staging_identity.st_mode) or not _same_identity(
            staging_identity, named_staging
        ):
            raise BybitLiquidationCaptureIOError("staging_identity_drift")
        for name, raw in files:
            _write_leaf(staging_fd, name, raw)
        if bounded_entry_names(staging_fd, maximum=len(allowed)) != allowed:
            raise BybitLiquidationCaptureIOError("bundle_file_set_invalid")
        os.fsync(staging_fd)
        staging_current = os.stat(staging, dir_fd=base_fd, follow_symlinks=False)
        if not _same_identity(staging_identity, staging_current):
            created_staging = False
            raise BybitLiquidationCaptureIOError("staging_identity_drift")
        try:
            os.stat(final, dir_fd=base_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            _retain_staging_quarantine(
                base_fd,
                staging,
                staging_fd,
                staging_identity,
                allowed,
            )
            created_staging = False
            return False
        renamed = _rename_directory_noreplace(base_fd, staging, final)
        if not renamed:
            _retain_staging_quarantine(
                base_fd,
                staging,
                staging_fd,
                staging_identity,
                allowed,
            )
            created_staging = False
            return False
        created_staging = False
        published = os.stat(final, dir_fd=base_fd, follow_symlinks=False)
        if not stat.S_ISDIR(published.st_mode) or not _same_identity(
            staging_identity, published
        ):
            raise BybitLiquidationCaptureIOError("bundle_publish_identity_drift")
        base_after = os.stat(base, follow_symlinks=False)
        if not _same_identity(base_identity, base_after):
            raise BybitLiquidationCaptureIOError("artifact_base_identity_drift")
        os.fsync(base_fd)
        return True
    except BaseException as exc:
        if (
            created_staging
            and staging_fd is not None
            and staging_identity is not None
        ):
            try:
                _retain_staging_quarantine(
                    base_fd,
                    staging,
                    staging_fd,
                    staging_identity,
                    allowed,
                )
            except BybitLiquidationCaptureIOError as quarantine_exc:
                raise quarantine_exc from exc
        if isinstance(exc, BybitLiquidationCaptureIOError):
            raise
        if not isinstance(exc, Exception):
            raise
        raise BybitLiquidationCaptureIOError(
            "atomic_bundle_publication_failed"
        ) from exc
    finally:
        if staging_fd is not None:
            os.close(staging_fd)


__all__ = (
    "BybitLiquidationCaptureIOError",
    "bounded_entry_names",
    "canonical_existing_directory",
    "hold_anchored_base",
    "open_namespace_at",
    "open_anchored_namespace",
    "publish_bundle_atomically",
    "read_operator_file",
    "read_regular_at",
    "reject_secret_bytes",
)
