"""Descriptor-anchored bounded I/O for the empirical hardening supplement."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import re
import stat
import time
from typing import Callable, Iterator


_SAFE_LEAF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


@dataclass(frozen=True)
class DirectoryAnchor:
    path: Path
    descriptors: tuple[int, ...]
    component_names: tuple[str, ...]
    identities: tuple[tuple[int, int], ...]

    @property
    def fd(self) -> int:
        return self.descriptors[-1]


@contextmanager
def anchored_directory(path: str | Path) -> Iterator[DirectoryAnchor]:
    """Open every directory component no-follow and retain the full chain."""

    _require_descriptor_features()
    absolute = absolute_path(path)
    flags = (
        os.O_RDONLY
        | _required_flag("O_DIRECTORY")
        | _required_flag("O_NOFOLLOW")
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptors: list[int] = []
    identities: list[tuple[int, int]] = []
    component_names = tuple(absolute.parts[1:])
    try:
        root_before = os.stat(absolute.anchor, follow_symlinks=False)
        if not stat.S_ISDIR(root_before.st_mode):
            raise OSError("filesystem root is not a directory")
        root_fd = os.open(absolute.anchor, flags)
        descriptors.append(root_fd)
        root_opened = os.fstat(root_fd)
        if (
            not stat.S_ISDIR(root_opened.st_mode)
            or not _same_identity(root_before, root_opened)
        ):
            raise OSError("filesystem root changed while opening")
        identities.append(_identity(root_opened))
        for component in component_names:
            before = os.stat(
                component,
                dir_fd=descriptors[-1],
                follow_symlinks=False,
            )
            if not stat.S_ISDIR(before.st_mode):
                raise OSError("path component is not a directory")
            child_fd = os.open(component, flags, dir_fd=descriptors[-1])
            descriptors.append(child_fd)
            opened = os.fstat(child_fd)
            named = os.stat(
                component,
                dir_fd=descriptors[-2],
                follow_symlinks=False,
            )
            if (
                not stat.S_ISDIR(opened.st_mode)
                or not _same_identity(before, opened)
                or not _same_identity(opened, named)
            ):
                raise OSError("path component changed while opening")
            identities.append(_identity(opened))
        anchor = DirectoryAnchor(
            path=absolute,
            descriptors=tuple(descriptors),
            component_names=component_names,
            identities=tuple(identities),
        )
        assert_anchor_current(anchor)
    except (OSError, RuntimeError) as exc:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise RuntimeError(
            "empirical_hardening_supplement_directory_unsafe"
        ) from exc
    try:
        yield anchor
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def assert_anchor_current(anchor: DirectoryAnchor) -> None:
    """Verify every retained descriptor and its parent-relative name."""

    try:
        for index, descriptor in enumerate(anchor.descriptors):
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(opened.st_mode)
                or _identity(opened) != anchor.identities[index]
            ):
                raise OSError("opened directory identity drifted")
            if index:
                named = os.stat(
                    anchor.component_names[index - 1],
                    dir_fd=anchor.descriptors[index - 1],
                    follow_symlinks=False,
                )
                if (
                    not stat.S_ISDIR(named.st_mode)
                    or _identity(named) != anchor.identities[index]
                ):
                    raise OSError("named directory identity drifted")
    except OSError as exc:
        raise RuntimeError(
            "empirical_hardening_supplement_directory_drift"
        ) from exc


def read_regular_leaf(directory_fd: int, name: str, *, maximum: int) -> bytes:
    """Read one bounded leaf while binding its path and descriptor snapshots."""

    if not safe_leaf_name(name) or type(maximum) is not int or maximum < 0:
        raise RuntimeError("empirical_hardening_supplement_leaf_unsafe")
    descriptor = -1
    try:
        before_path = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(before_path.st_mode)
            or before_path.st_size < 0
            or before_path.st_size > maximum
        ):
            raise RuntimeError(
                f"empirical_hardening_supplement_leaf_size_or_type_invalid:{name}"
            )
        descriptor = os.open(
            name,
            os.O_RDONLY
            | _required_flag("O_NOFOLLOW")
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=directory_fd,
        )
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or not _same_snapshot(
            before_path, opened
        ):
            raise RuntimeError(
                f"empirical_hardening_supplement_leaf_identity_invalid:{name}"
            )
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise RuntimeError(
                    f"empirical_hardening_supplement_leaf_size_invalid:{name}"
                )
        after = os.fstat(descriptor)
        after_path = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            total != opened.st_size
            or not _same_snapshot(opened, after)
            or not _same_snapshot(after, after_path)
        ):
            raise RuntimeError(
                f"empirical_hardening_supplement_leaf_drift:{name}"
            )
        return b"".join(chunks)
    except RuntimeError:
        raise
    except OSError as exc:
        raise RuntimeError(
            f"empirical_hardening_supplement_leaf_unavailable:{name}"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def read_absolute_regular_file(path: Path, *, maximum: int) -> bytes:
    absolute = absolute_path(path)
    with anchored_directory(absolute.parent) as anchor:
        payload = read_regular_leaf(anchor.fd, absolute.name, maximum=maximum)
        assert_anchor_current(anchor)
        return payload


def directory_names(directory_fd: int, *, maximum: int) -> tuple[str, ...]:
    try:
        names = tuple(sorted(os.listdir(directory_fd)))
    except OSError as exc:
        raise RuntimeError(
            "empirical_hardening_supplement_directory_inventory_invalid"
        ) from exc
    if len(names) > maximum or any(not safe_leaf_name(name) for name in names):
        raise RuntimeError(
            "empirical_hardening_supplement_directory_inventory_invalid"
        )
    return names


def publish_regular_leaf_no_clobber(
    anchor: DirectoryAnchor,
    *,
    name: str,
    payload: bytes,
    maximum: int,
    guard: Callable[[], None],
) -> None:
    """Publish by exclusive hard-link; never replace an existing leaf."""

    _require_publish_features()
    if not safe_leaf_name(name) or not isinstance(payload, bytes) or len(payload) > maximum:
        raise RuntimeError("empirical_hardening_supplement_output_unsafe")
    temp_name = f"{name}.tmp.{os.getpid()}.{time.time_ns()}"
    if not safe_leaf_name(temp_name):
        raise RuntimeError("empirical_hardening_supplement_temp_name_invalid")
    descriptor = -1
    staged_identity: tuple[int, int] | None = None
    published = False
    completed = False
    try:
        descriptor = os.open(
            temp_name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | _required_flag("O_NOFOLLOW")
            | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=anchor.fd,
        )
        opened_stage = os.fstat(descriptor)
        if not stat.S_ISREG(opened_stage.st_mode):
            raise RuntimeError("empirical_hardening_supplement_stage_invalid")
        staged_identity = _identity(opened_stage)
        _write_all(descriptor, payload)
        os.fsync(descriptor)
        staged = os.fstat(descriptor)
        if (
            not stat.S_ISREG(staged.st_mode)
            or staged.st_size != len(payload)
            or _identity(staged) != staged_identity
        ):
            raise RuntimeError("empirical_hardening_supplement_stage_drift")
        os.close(descriptor)
        descriptor = -1
        named_stage = os.stat(temp_name, dir_fd=anchor.fd, follow_symlinks=False)
        if _identity(named_stage) != staged_identity:
            raise RuntimeError("empirical_hardening_supplement_stage_drift")
        guard()
        assert_anchor_current(anchor)
        os.link(
            temp_name,
            name,
            src_dir_fd=anchor.fd,
            dst_dir_fd=anchor.fd,
            follow_symlinks=False,
        )
        published = True
        os.fsync(anchor.fd)
        guard()
        if read_regular_leaf(anchor.fd, name, maximum=maximum) != payload:
            raise RuntimeError("empirical_hardening_supplement_post_write_drift")
        completed = True
    except FileExistsError as exc:
        raise RuntimeError(
            "empirical_hardening_supplement_no_clobber_conflict"
        ) from exc
    except OSError as exc:
        raise RuntimeError("empirical_hardening_supplement_publish_failed") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if published and not completed and staged_identity is not None:
            _unlink_if_identity(anchor.fd, name, staged_identity)
        if staged_identity is not None:
            _unlink_if_identity(anchor.fd, temp_name, staged_identity)
        try:
            os.fsync(anchor.fd)
        except OSError:
            pass
    if not completed:
        raise RuntimeError("empirical_hardening_supplement_publish_failed")


def entry_stat(directory_fd: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RuntimeError(
            "empirical_hardening_supplement_output_unsafe"
        ) from exc


def absolute_path(path: str | Path) -> Path:
    supplied = Path(path).expanduser()
    if any(part in {"", ".", ".."} for part in supplied.parts if part != supplied.anchor):
        raise RuntimeError("empirical_hardening_supplement_path_unsafe")
    absolute = Path(os.path.abspath(os.fspath(supplied)))
    if not absolute.is_absolute() or not absolute.anchor:
        raise RuntimeError("empirical_hardening_supplement_path_unsafe")
    return absolute


def safe_leaf_name(value: object) -> bool:
    return isinstance(value, str) and _SAFE_LEAF.fullmatch(value) is not None


def _unlink_if_identity(
    directory_fd: int,
    name: str,
    expected_identity: tuple[int, int],
) -> None:
    try:
        observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if _identity(observed) == expected_identity:
            os.unlink(name, dir_fd=directory_fd)
    except FileNotFoundError:
        return


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise RuntimeError("empirical_hardening_supplement_write_failed")
        offset += written


def _require_descriptor_features() -> None:
    if not (
        os.open in os.supports_dir_fd
        and os.stat in os.supports_dir_fd
        and os.stat in os.supports_follow_symlinks
        and os.listdir in os.supports_fd
        and hasattr(os, "O_DIRECTORY")
        and hasattr(os, "O_NOFOLLOW")
        and getattr(os, "O_DIRECTORY", 0)
        and getattr(os, "O_NOFOLLOW", 0)
    ):
        raise RuntimeError(
            "empirical_hardening_supplement_descriptor_features_unavailable"
        )


def _require_publish_features() -> None:
    if not (
        os.link in os.supports_dir_fd
        and os.link in os.supports_follow_symlinks
        and os.unlink in os.supports_dir_fd
    ):
        raise RuntimeError(
            "empirical_hardening_supplement_publish_features_unavailable"
        )


def _required_flag(name: str) -> int:
    value = getattr(os, name, 0)
    if not value:
        raise RuntimeError(
            "empirical_hardening_supplement_descriptor_features_unavailable"
        )
    return value


def _identity(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return _identity(left) == _identity(right)


def _same_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        _same_identity(left, right)
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
        and left.st_ctime_ns == right.st_ctime_ns
    )


__all__ = (
    "DirectoryAnchor",
    "absolute_path",
    "anchored_directory",
    "assert_anchor_current",
    "directory_names",
    "entry_stat",
    "publish_regular_leaf_no_clobber",
    "read_absolute_regular_file",
    "read_regular_leaf",
    "safe_leaf_name",
)
