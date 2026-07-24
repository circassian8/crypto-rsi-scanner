from __future__ import annotations

import os
from pathlib import Path

import pytest

from crypto_rsi_scanner.lean_radar import path_security
from crypto_rsi_scanner.lean_radar.path_security import (
    LeanPathSecurityError,
    read_regular_bytes,
)
from crypto_rsi_scanner.lean_radar.store import LeanRadarStore, LeanRadarStoreError


def test_descriptor_reader_accepts_an_ordinary_absolute_path(tmp_path: Path) -> None:
    source = tmp_path / "input.json"
    source.write_bytes(b'{"ok":true}')

    secured = read_regular_bytes(source, maximum_bytes=1_024)

    assert secured.data == b'{"ok":true}'
    assert secured.size_bytes == 11
    assert len(secured.sha256) == 64


def test_descriptor_reader_rejects_a_symlinked_root_parent(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "input.json").write_text("{}", encoding="utf-8")
    redirected = tmp_path / "redirected"
    redirected.symlink_to(outside, target_is_directory=True)

    with pytest.raises(LeanPathSecurityError, match="parent component"):
        read_regular_bytes(redirected / "input.json", maximum_bytes=1_024)


def test_descriptor_reader_rejects_an_intermediate_symlink(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "input.json").write_text("{}", encoding="utf-8")
    (root / "nested").symlink_to(outside, target_is_directory=True)

    with pytest.raises(LeanPathSecurityError, match="parent component"):
        read_regular_bytes(root / "nested" / "input.json", maximum_bytes=1_024)


def test_descriptor_reader_rejects_a_final_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "input.json"
    link.symlink_to(target)

    with pytest.raises(LeanPathSecurityError, match="regular file"):
        read_regular_bytes(link, maximum_bytes=1_024)


def test_descriptor_reader_rejects_file_replacement_before_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "input.json"
    source.write_text('{"version":1}', encoding="utf-8")
    replacement = tmp_path / "replacement.json"
    replacement.write_text('{"version":2}', encoding="utf-8")
    original_open = path_security.os.open
    swapped = False

    def racing_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        if path == "input.json" and dir_fd is not None and not swapped:
            swapped = True
            os.replace(replacement, source)
        if dir_fd is None:
            return original_open(path, flags, mode)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(path_security.os, "open", racing_open)

    with pytest.raises(LeanPathSecurityError, match="changed before read"):
        read_regular_bytes(source, maximum_bytes=1_024)


def test_descriptor_reader_rejects_directory_replacement_during_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "root"
    safe = root / "safe"
    safe.mkdir(parents=True)
    source = safe / "input.json"
    source.write_text('{"trusted":true}', encoding="utf-8")
    moved = root / "moved"
    original_open = path_security.os.open
    swapped = False

    def racing_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        if path == "input.json" and dir_fd is not None and not swapped:
            swapped = True
            safe.rename(moved)
            safe.mkdir()
            (safe / "input.json").write_text('{"redirected":true}', encoding="utf-8")
        if dir_fd is None:
            return original_open(path, flags, mode)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(path_security.os, "open", racing_open)

    with pytest.raises(LeanPathSecurityError, match="parent component identity"):
        read_regular_bytes(source, maximum_bytes=1_024)


def test_database_rejects_a_symlinked_parent_and_outside_redirection(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    redirected = tmp_path / "runtime"
    redirected.symlink_to(outside, target_is_directory=True)
    store = LeanRadarStore(redirected / "lean.db")

    with pytest.raises(LeanRadarStoreError, match="unavailable"):
        with store.connect(write=True):
            pass
    assert not (outside / "lean.db").exists()


def test_database_rejects_a_final_symlink(tmp_path: Path) -> None:
    outside = tmp_path / "outside.db"
    outside.write_bytes(b"not a database")
    database = tmp_path / "lean.db"
    database.symlink_to(outside)
    store = LeanRadarStore(database)

    with pytest.raises(LeanRadarStoreError, match="unavailable"):
        with store.connect(write=True):
            pass


def test_database_uses_one_regular_image_and_stable_lock(tmp_path: Path) -> None:
    database = tmp_path / "lean.db"
    store = LeanRadarStore(database)

    with store.connect(write=True) as connection:
        connection.execute(
            "INSERT INTO meta (key, value) VALUES ('test_key', 'test_value')"
        )
        connection.commit()
    with store.connect() as connection:
        assert connection.execute(
            "SELECT value FROM meta WHERE key = 'test_key'"
        ).fetchone()[0] == "test_value"

    assert database.is_file()
    assert database.stat().st_nlink == 1
    assert database.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / ".lean.db.lock").is_file()
    assert not (tmp_path / "lean.db-wal").exists()
    assert not (tmp_path / "lean.db-shm").exists()


def test_database_rejects_file_replacement_while_acquiring_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "lean.db"
    store = LeanRadarStore(database)
    with store.connect(write=True) as connection:
        connection.execute(
            "INSERT INTO meta (key, value) VALUES ('owner', 'original')"
        )
    replacement = tmp_path / "replacement.db"
    replacement_store = LeanRadarStore(replacement)
    with replacement_store.connect(write=True) as connection:
        connection.execute(
            "INSERT INTO meta (key, value) VALUES ('owner', 'replacement')"
        )
    original_open = path_security.os.open
    swapped = False

    def racing_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        if path == "lean.db" and dir_fd is not None and not swapped:
            swapped = True
            os.replace(replacement, database)
        if dir_fd is None:
            return original_open(path, flags, mode)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(path_security.os, "open", racing_open)

    with pytest.raises(LeanRadarStoreError, match="unavailable"):
        with store.connect():
            pass


def test_database_rejects_parent_directory_replacement_during_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    moved = tmp_path / "moved"
    store = LeanRadarStore(runtime / "lean.db")
    original_open = path_security.os.open
    swapped = False

    def racing_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        if path == ".lean.db.lock" and dir_fd is not None and not swapped:
            swapped = True
            runtime.rename(moved)
            runtime.mkdir()
        if dir_fd is None:
            return original_open(path, flags, mode)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(path_security.os, "open", racing_open)

    with pytest.raises(LeanRadarStoreError, match="unavailable"):
        with store.connect(write=True):
            pass
    assert not (runtime / "lean.db").exists()
    assert not (moved / "lean.db").exists()


def test_database_rejects_a_symlinked_lock(tmp_path: Path) -> None:
    database = tmp_path / "lean.db"
    store = LeanRadarStore(database)
    outside = tmp_path / "outside.lock"
    outside.write_bytes(b"")
    (tmp_path / ".lean.db.lock").symlink_to(outside)

    with pytest.raises(LeanRadarStoreError, match="lock"):
        with store.connect(write=True):
            pass
