"""Descriptor-anchored local paths for the small Lean Radar runtime.

The Lean product accepts a handful of operator-supplied local files and one
SQLite runtime.  Every component is walked from the filesystem root with
``openat``-style operations so a symlinked or replaced parent can never redirect
the read or write to a different tree.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
from typing import Iterator, Sequence
from uuid import uuid4


class _LeanPathSecurityError(RuntimeError):
    """Raised when a local path cannot be held to one verified identity."""


LeanPathSecurityError = _LeanPathSecurityError


@dataclass(frozen=True)
class _SecureBytes:
    data: bytes
    sha256: str
    size_bytes: int
    device: int
    inode: int


@dataclass(frozen=True)
class _DirectoryBinding:
    parent_fd: int
    name: str
    device: int
    inode: int


class AnchoredPath:
    """One absolute leaf plus a descriptor-held, verified parent chain."""

    def __init__(
        self,
        *,
        path: Path,
        leaf: str,
        descriptors: Sequence[int],
        root_identity: tuple[int, int],
        bindings: Sequence[_DirectoryBinding],
    ) -> None:
        self.path = path
        self.leaf = leaf
        self._descriptors = tuple(descriptors)
        self._root_identity = root_identity
        self._bindings = tuple(bindings)
        self._closed = False

    @property
    def parent_fd(self) -> int:
        if self._closed:
            raise LeanPathSecurityError("anchored path is already closed")
        return self._descriptors[-1]

    def verify_parent_chain(self) -> None:
        """Prove that every named parent still resolves to the held inode."""

        if self._closed:
            raise LeanPathSecurityError("anchored path is already closed")
        root_now = os.stat(self.path.anchor, follow_symlinks=False)
        root_open = os.fstat(self._descriptors[0])
        if (
            not stat.S_ISDIR(root_now.st_mode)
            or not stat.S_ISDIR(root_open.st_mode)
            or (root_now.st_dev, root_now.st_ino) != self._root_identity
            or (root_open.st_dev, root_open.st_ino) != self._root_identity
        ):
            raise LeanPathSecurityError("path root identity changed")
        for binding in self._bindings:
            try:
                named = os.stat(
                    binding.name,
                    dir_fd=binding.parent_fd,
                    follow_symlinks=False,
                )
            except OSError as exc:
                raise LeanPathSecurityError(
                    "path parent component became unavailable"
                ) from exc
            if (
                not stat.S_ISDIR(named.st_mode)
                or (named.st_dev, named.st_ino)
                != (binding.device, binding.inode)
            ):
                raise LeanPathSecurityError("path parent component identity changed")

    def stat_leaf(self, *, missing_ok: bool = False) -> os.stat_result | None:
        self.verify_parent_chain()
        try:
            info = os.stat(
                self.leaf,
                dir_fd=self.parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            if missing_ok:
                return None
            raise LeanPathSecurityError("path leaf is unavailable") from None
        except OSError as exc:
            raise LeanPathSecurityError("path leaf is unavailable") from exc
        return info

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for descriptor in reversed(self._descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass


@contextmanager
def anchored_path(
    path: Path,
    *,
    rejected_components: frozenset[str] = frozenset(),
) -> Iterator[AnchoredPath]:
    """Walk one absolute path without following any named symlink component."""

    candidate = Path(path).expanduser()
    if not candidate.is_absolute() or candidate.anchor != "/":
        raise LeanPathSecurityError("local path must be absolute")
    parts = candidate.parts
    if len(parts) < 2:
        raise LeanPathSecurityError("local path must name a leaf")
    relative_parts = parts[1:]
    if any(part in {"", ".", ".."} for part in relative_parts):
        raise LeanPathSecurityError("local path contains an unsafe component")
    if rejected_components and any(
        part.casefold() in rejected_components for part in relative_parts
    ):
        raise LeanPathSecurityError(
            "fixture/test/mock/replay path cannot be used as genuine input"
        )

    directory_flags = (
        os.O_RDONLY
        | _required_flag("O_DIRECTORY")
        | _required_flag("O_NOFOLLOW")
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptors: list[int] = []
    bindings: list[_DirectoryBinding] = []
    try:
        root_before = os.stat(candidate.anchor, follow_symlinks=False)
        if not stat.S_ISDIR(root_before.st_mode):
            raise LeanPathSecurityError("path root is not a directory")
        root_fd = os.open(candidate.anchor, directory_flags)
        descriptors.append(root_fd)
        root_open = os.fstat(root_fd)
        root_identity = (root_before.st_dev, root_before.st_ino)
        if (
            not stat.S_ISDIR(root_open.st_mode)
            or (root_open.st_dev, root_open.st_ino) != root_identity
        ):
            raise LeanPathSecurityError("path root changed during open")

        current_fd = root_fd
        for component in relative_parts[:-1]:
            try:
                before = os.stat(
                    component,
                    dir_fd=current_fd,
                    follow_symlinks=False,
                )
            except OSError as exc:
                raise LeanPathSecurityError(
                    "path parent component is unavailable"
                ) from exc
            if not stat.S_ISDIR(before.st_mode):
                raise LeanPathSecurityError(
                    "path parent component is not a real directory"
                )
            try:
                opened_fd = os.open(component, directory_flags, dir_fd=current_fd)
            except OSError as exc:
                raise LeanPathSecurityError(
                    "path parent component could not be opened safely"
                ) from exc
            opened = os.fstat(opened_fd)
            try:
                named = os.stat(
                    component,
                    dir_fd=current_fd,
                    follow_symlinks=False,
                )
            except OSError as exc:
                os.close(opened_fd)
                raise LeanPathSecurityError(
                    "path parent component changed during open"
                ) from exc
            identity = (before.st_dev, before.st_ino)
            if (
                not stat.S_ISDIR(opened.st_mode)
                or not stat.S_ISDIR(named.st_mode)
                or (opened.st_dev, opened.st_ino) != identity
                or (named.st_dev, named.st_ino) != identity
            ):
                os.close(opened_fd)
                raise LeanPathSecurityError(
                    "path parent component changed during open"
                )
            bindings.append(
                _DirectoryBinding(
                    parent_fd=current_fd,
                    name=component,
                    device=opened.st_dev,
                    inode=opened.st_ino,
                )
            )
            descriptors.append(opened_fd)
            current_fd = opened_fd

        result = AnchoredPath(
            path=candidate,
            leaf=relative_parts[-1],
            descriptors=descriptors,
            root_identity=root_identity,
            bindings=bindings,
        )
        result.verify_parent_chain()
        yield result
        result.verify_parent_chain()
    finally:
        if "result" in locals():
            result.close()
        else:
            for descriptor in reversed(descriptors):
                try:
                    os.close(descriptor)
                except OSError:
                    pass


def read_regular_bytes(
    path: Path,
    *,
    maximum_bytes: int,
    rejected_components: frozenset[str] = frozenset(),
) -> _SecureBytes:
    with anchored_path(path, rejected_components=rejected_components) as anchored:
        return read_regular_bytes_at(anchored, maximum_bytes=maximum_bytes)


def atomic_write_regular_bytes(
    path: Path,
    data: bytes,
    *,
    maximum_bytes: int,
    mode: int = 0o600,
    expected_sha256: str | None = None,
    refuse_existing: bool = False,
) -> _SecureBytes:
    """Publish one file relative to a held parent directory descriptor."""

    if not isinstance(data, bytes) or len(data) > maximum_bytes:
        raise LeanPathSecurityError("publication bytes exceed the size bound")
    with anchored_path(path) as anchored:
        original = read_regular_bytes_at(
            anchored,
            maximum_bytes=maximum_bytes,
            missing_ok=True,
        )
        if refuse_existing and original is not None:
            raise LeanPathSecurityError("path leaf already exists")
        if expected_sha256 is not None and (
            original is None or original.sha256 != expected_sha256
        ):
            raise LeanPathSecurityError("path leaf does not match the expected owner")
        temporary = f".{anchored.leaf}.tmp-{uuid4().hex}"
        descriptor = os.open(
            temporary,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | _required_flag("O_NOFOLLOW")
            | getattr(os, "O_CLOEXEC", 0),
            mode,
            dir_fd=anchored.parent_fd,
        )
        staged: os.stat_result | None = None
        published = False
        try:
            view = memoryview(data)
            offset = 0
            while offset < len(view):
                written = os.write(descriptor, view[offset:])
                if written <= 0:
                    raise LeanPathSecurityError(
                        "path leaf publication made no progress"
                    )
                offset += written
            os.fchmod(descriptor, mode)
            os.fsync(descriptor)
            staged = os.fstat(descriptor)
            _require_regular_single_link(staged, maximum_bytes=maximum_bytes)
            if staged.st_size != len(data):
                raise LeanPathSecurityError("path leaf staging is incomplete")
            named_stage = os.stat(
                temporary,
                dir_fd=anchored.parent_fd,
                follow_symlinks=False,
            )
            _require_unchanged_file(staged, named_stage)
            anchored.verify_parent_chain()
            latest = read_regular_bytes_at(
                anchored,
                maximum_bytes=maximum_bytes,
                missing_ok=True,
            )
            if original is None:
                if latest is not None:
                    raise LeanPathSecurityError(
                        "path leaf appeared before publication"
                    )
            elif (
                latest is None
                or latest.device != original.device
                or latest.inode != original.inode
                or latest.sha256 != original.sha256
            ):
                raise LeanPathSecurityError(
                    "path leaf changed before publication"
                )
            os.replace(
                temporary,
                anchored.leaf,
                src_dir_fd=anchored.parent_fd,
                dst_dir_fd=anchored.parent_fd,
            )
            published = True
            final_named = os.stat(
                anchored.leaf,
                dir_fd=anchored.parent_fd,
                follow_symlinks=False,
            )
            if (final_named.st_dev, final_named.st_ino) != (
                staged.st_dev,
                staged.st_ino,
            ):
                raise LeanPathSecurityError(
                    "path leaf publication identity changed"
                )
            anchored.verify_parent_chain()
            os.fsync(anchored.parent_fd)
        finally:
            os.close(descriptor)
            if not published and staged is not None:
                _unlink_if_same(
                    anchored,
                    temporary,
                    expected=staged,
                )
        verified = read_regular_bytes_at(
            anchored,
            maximum_bytes=maximum_bytes,
        )
        assert verified is not None
        if (
            verified.size_bytes != len(data)
            or verified.sha256 != hashlib.sha256(data).hexdigest()
        ):
            raise LeanPathSecurityError(
                "path leaf publication verification failed"
            )
        return verified


def unlink_regular_file(
    path: Path,
    *,
    maximum_bytes: int,
    expected_sha256: str,
) -> bool:
    """Remove only the exact regular single-link leaf owned by its digest."""

    with anchored_path(path) as anchored:
        current = read_regular_bytes_at(
            anchored,
            maximum_bytes=maximum_bytes,
            missing_ok=True,
        )
        if current is None:
            return False
        if current.sha256 != expected_sha256:
            raise LeanPathSecurityError("path leaf does not match the expected owner")
        anchored.verify_parent_chain()
        named = anchored.stat_leaf()
        assert named is not None
        if (named.st_dev, named.st_ino) != (current.device, current.inode):
            raise LeanPathSecurityError("path leaf changed before removal")
        os.unlink(anchored.leaf, dir_fd=anchored.parent_fd)
        anchored.verify_parent_chain()
        os.fsync(anchored.parent_fd)
        return True


def read_regular_bytes_at(
    anchored: AnchoredPath,
    *,
    maximum_bytes: int,
    missing_ok: bool = False,
) -> _SecureBytes | None:
    if (
        isinstance(maximum_bytes, bool)
        or not isinstance(maximum_bytes, int)
        or maximum_bytes <= 0
    ):
        raise LeanPathSecurityError("file size bound is invalid")
    before = anchored.stat_leaf(missing_ok=missing_ok)
    if before is None:
        return None
    _require_regular_single_link(before, maximum_bytes=maximum_bytes)
    flags = os.O_RDONLY | _required_flag("O_NOFOLLOW") | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(
            anchored.leaf,
            flags,
            dir_fd=anchored.parent_fd,
        )
    except OSError as exc:
        raise LeanPathSecurityError("path leaf could not be opened safely") from exc
    try:
        opened = os.fstat(descriptor)
        _require_regular_single_link(opened, maximum_bytes=maximum_bytes)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise LeanPathSecurityError("path leaf changed before read")
        chunks: list[bytes] = []
        remaining = maximum_bytes + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if len(data) > maximum_bytes:
        raise LeanPathSecurityError("path leaf exceeds the size bound")
    _require_unchanged_file(opened, after)
    named_after = anchored.stat_leaf()
    assert named_after is not None
    _require_unchanged_file(opened, named_after)
    anchored.verify_parent_chain()
    return _SecureBytes(
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        device=opened.st_dev,
        inode=opened.st_ino,
    )


def require_regular_single_link(
    info: os.stat_result,
    *,
    maximum_bytes: int,
) -> None:
    _require_regular_single_link(info, maximum_bytes=maximum_bytes)


def require_same_file(
    expected: os.stat_result,
    current: os.stat_result,
) -> None:
    _require_unchanged_file(expected, current)


def _require_regular_single_link(
    info: os.stat_result,
    *,
    maximum_bytes: int,
) -> None:
    if not stat.S_ISREG(info.st_mode):
        raise LeanPathSecurityError("path leaf must be a regular file")
    if info.st_nlink != 1:
        raise LeanPathSecurityError("path leaf must have exactly one hard link")
    if info.st_size < 0 or info.st_size > maximum_bytes:
        raise LeanPathSecurityError("path leaf exceeds the size bound")


def _require_unchanged_file(
    expected: os.stat_result,
    current: os.stat_result,
) -> None:
    expected_values = (
        expected.st_dev,
        expected.st_ino,
        expected.st_mode,
        expected.st_nlink,
        expected.st_size,
        expected.st_mtime_ns,
    )
    current_values = (
        current.st_dev,
        current.st_ino,
        current.st_mode,
        current.st_nlink,
        current.st_size,
        current.st_mtime_ns,
    )
    if current_values != expected_values:
        raise LeanPathSecurityError("path leaf changed during operation")


def _required_flag(name: str) -> int:
    value = getattr(os, name, 0)
    if not isinstance(value, int) or value == 0:
        raise LeanPathSecurityError(f"platform lacks required {name} support")
    return value


def _unlink_if_same(
    anchored: AnchoredPath,
    name: str,
    *,
    expected: os.stat_result,
) -> None:
    try:
        current = os.stat(
            name,
            dir_fd=anchored.parent_fd,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return
    if (current.st_dev, current.st_ino) == (expected.st_dev, expected.st_ino):
        os.unlink(name, dir_fd=anchored.parent_fd)


__all__ = (
    "AnchoredPath",
    "LeanPathSecurityError",
    "anchored_path",
    "atomic_write_regular_bytes",
    "read_regular_bytes",
    "read_regular_bytes_at",
    "require_regular_single_link",
    "require_same_file",
    "unlink_regular_file",
)
