"""Adversarial descriptor-walk tests for the source review exporter."""

from __future__ import annotations

import errno
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import zipfile

import pytest

from tests.rsi._api_helpers import REPO_ROOT


def _load_export_module(name: str):
    spec = importlib.util.spec_from_file_location(
        name,
        REPO_ROOT / "scripts" / "export_source_with_artifacts.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_archive_write_fails_without_entry(
    module,
    *,
    trusted_root: Path,
    safe_file: Path,
    archive: Path,
    outside_marker: bytes,
) -> OSError:
    failure: OSError | None = None
    with zipfile.ZipFile(archive, "w") as zf:
        try:
            module._write_file_to_zip(
                zf,
                safe_file,
                "event_fade_cache/level_one/level_two/evidence.txt",
                now_ts=time.time(),
                root=trusted_root,
            )
        except OSError as exc:
            failure = exc
    assert failure is not None
    with zipfile.ZipFile(archive) as zf:
        assert zf.namelist() == []
        assert all(outside_marker not in zf.read(name) for name in zf.namelist())
    return failure


def test_export_verified_open_writes_an_ordinary_safe_file():
    module = _load_export_module("export_source_with_artifacts_safe_file")
    with TemporaryDirectory() as tmp:
        trusted_root = Path(tmp) / "trusted"
        safe_file = trusted_root / "event_fade_cache" / "unit" / "evidence.txt"
        safe_file.parent.mkdir(parents=True)
        safe_file.write_bytes(b"ordinary safe evidence\n")
        archive = Path(tmp) / "safe.zip"

        with zipfile.ZipFile(archive, "w") as zf:
            module._write_file_to_zip(
                zf,
                safe_file,
                "event_fade_cache/unit/evidence.txt",
                now_ts=time.time(),
                root=trusted_root,
            )

        with zipfile.ZipFile(archive) as zf:
            assert zf.namelist() == ["event_fade_cache/unit/evidence.txt"]
            assert zf.read("event_fade_cache/unit/evidence.txt") == b"ordinary safe evidence\n"


def test_export_verified_open_rejects_outside_root_path():
    module = _load_export_module("export_source_with_artifacts_outside_root")
    with TemporaryDirectory() as tmp:
        trusted_root = Path(tmp) / "trusted"
        trusted_root.mkdir()
        outside = Path(tmp) / "outside.txt"
        outside.write_bytes(b"outside private material\n")

        with pytest.raises(OSError) as exc_info:
            module._open_verified_regular_file(outside, root=trusted_root)

        assert exc_info.value.errno == errno.EPERM
        assert outside.read_bytes() == b"outside private material\n"


def test_export_parent_directory_swap_fails_when_nofollow_is_ineffective():
    module = _load_export_module("export_source_with_artifacts_parent_identity_race")
    marker = b"outside parent private material\n"
    with TemporaryDirectory() as tmp:
        trusted_root = Path(tmp) / "trusted"
        artifact_root = trusted_root / "event_fade_cache"
        safe_file = artifact_root / "level_one" / "level_two" / "evidence.txt"
        safe_file.parent.mkdir(parents=True)
        safe_file.write_bytes(b"safe evidence\n")
        outside_root = Path(tmp) / "outside"
        outside_file = outside_root / "level_one" / "level_two" / "evidence.txt"
        outside_file.parent.mkdir(parents=True)
        outside_file.write_bytes(marker)
        displaced = trusted_root / "event_fade_cache.checked"
        archive = Path(tmp) / "parent-race.zip"
        original_open = module.os.open
        swapped = False

        def racing_open(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal swapped
            if path == "event_fade_cache" and dir_fd is not None and not swapped:
                artifact_root.rename(displaced)
                artifact_root.symlink_to(outside_root, target_is_directory=True)
                flags &= ~module.os.O_NOFOLLOW
                swapped = True
            return original_open(path, flags, mode, dir_fd=dir_fd)

        module.os.open = racing_open
        try:
            _assert_archive_write_fails_without_entry(
                module,
                trusted_root=trusted_root,
                safe_file=safe_file,
                archive=archive,
                outside_marker=marker,
            )
        finally:
            module.os.open = original_open

        assert swapped is True
        assert outside_file.read_bytes() == marker


def test_export_intermediate_directory_swap_fails_when_nofollow_is_ineffective():
    module = _load_export_module("export_source_with_artifacts_intermediate_identity_race")
    marker = b"outside intermediate private material\n"
    with TemporaryDirectory() as tmp:
        trusted_root = Path(tmp) / "trusted"
        intermediate = trusted_root / "event_fade_cache" / "level_one" / "level_two"
        safe_file = intermediate / "evidence.txt"
        safe_file.parent.mkdir(parents=True)
        safe_file.write_bytes(b"safe evidence\n")
        outside_dir = Path(tmp) / "outside-level-two"
        outside_dir.mkdir()
        outside_file = outside_dir / "evidence.txt"
        outside_file.write_bytes(marker)
        displaced = intermediate.with_name("level_two.checked")
        archive = Path(tmp) / "intermediate-race.zip"
        original_open = module.os.open
        swapped = False

        def racing_open(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal swapped
            if path == "level_two" and dir_fd is not None and not swapped:
                intermediate.rename(displaced)
                intermediate.symlink_to(outside_dir, target_is_directory=True)
                flags &= ~module.os.O_NOFOLLOW
                swapped = True
            return original_open(path, flags, mode, dir_fd=dir_fd)

        module.os.open = racing_open
        try:
            _assert_archive_write_fails_without_entry(
                module,
                trusted_root=trusted_root,
                safe_file=safe_file,
                archive=archive,
                outside_marker=marker,
            )
        finally:
            module.os.open = original_open

        assert swapped is True
        assert outside_file.read_bytes() == marker


def test_export_final_file_symlink_swap_fails_when_nofollow_is_ineffective():
    module = _load_export_module("export_source_with_artifacts_final_symlink_race")
    marker = b"outside final symlink private material\n"
    with TemporaryDirectory() as tmp:
        trusted_root = Path(tmp) / "trusted"
        safe_file = trusted_root / "event_fade_cache" / "level_one" / "level_two" / "evidence.txt"
        safe_file.parent.mkdir(parents=True)
        safe_file.write_bytes(b"safe evidence\n")
        outside_file = Path(tmp) / "outside-evidence.txt"
        outside_file.write_bytes(marker)
        displaced = safe_file.with_name("evidence.checked")
        archive = Path(tmp) / "final-symlink-race.zip"
        original_open = module.os.open
        swapped = False

        def racing_open(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal swapped
            if path == "evidence.txt" and dir_fd is not None and not swapped:
                safe_file.rename(displaced)
                safe_file.symlink_to(outside_file)
                flags &= ~module.os.O_NOFOLLOW
                swapped = True
            return original_open(path, flags, mode, dir_fd=dir_fd)

        module.os.open = racing_open
        try:
            _assert_archive_write_fails_without_entry(
                module,
                trusted_root=trusted_root,
                safe_file=safe_file,
                archive=archive,
                outside_marker=marker,
            )
        finally:
            module.os.open = original_open

        assert swapped is True
        assert outside_file.read_bytes() == marker


def test_export_final_regular_file_replacement_between_stat_and_open_fails():
    module = _load_export_module("export_source_with_artifacts_final_regular_race")
    marker = b"outside replacement private material\n"
    with TemporaryDirectory() as tmp:
        trusted_root = Path(tmp) / "trusted"
        safe_file = trusted_root / "event_fade_cache" / "level_one" / "level_two" / "evidence.txt"
        safe_file.parent.mkdir(parents=True)
        safe_file.write_bytes(b"safe evidence\n")
        outside_file = Path(tmp) / "outside-replacement.txt"
        outside_file.write_bytes(marker)
        displaced = safe_file.with_name("evidence.checked")
        archive = Path(tmp) / "final-regular-race.zip"
        original_open = module.os.open
        swapped = False

        def racing_open(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal swapped
            if path == "evidence.txt" and dir_fd is not None and not swapped:
                safe_file.rename(displaced)
                outside_file.rename(safe_file)
                swapped = True
            return original_open(path, flags, mode, dir_fd=dir_fd)

        module.os.open = racing_open
        try:
            _assert_archive_write_fails_without_entry(
                module,
                trusted_root=trusted_root,
                safe_file=safe_file,
                archive=archive,
                outside_marker=marker,
            )
        finally:
            module.os.open = original_open

        assert swapped is True
        assert safe_file.read_bytes() == marker


def test_export_verified_open_fails_enotsup_without_required_descriptor_features():
    module = _load_export_module("export_source_with_artifacts_unsupported")
    with TemporaryDirectory() as tmp:
        trusted_root = Path(tmp) / "trusted"
        safe_file = trusted_root / "evidence.txt"
        trusted_root.mkdir()
        safe_file.write_bytes(b"safe evidence\n")

        for attribute in (
            "_OPEN_SUPPORTS_DIR_FD",
            "_STAT_SUPPORTS_DIR_FD",
            "_STAT_SUPPORTS_FOLLOW_SYMLINKS",
        ):
            original = getattr(module, attribute)
            setattr(module, attribute, False)
            try:
                with pytest.raises(OSError) as exc_info:
                    module._open_verified_regular_file(safe_file, root=trusted_root)
            finally:
                setattr(module, attribute, original)
            assert exc_info.value.errno == errno.ENOTSUP
