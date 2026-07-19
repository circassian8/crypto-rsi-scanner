"""Adversarial shared market-artifact writer regressions."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations import market_no_send_io
from crypto_rsi_scanner.event_alpha.operations.market_no_send_models import (
    MarketNoSendError,
)


def _namespace(tmp_path: Path) -> Path:
    path = tmp_path / "artifact_namespace"
    path.mkdir()
    return path


def _stages(namespace: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in namespace.iterdir()
            if path.name.startswith(".")
            and path.suffix in {".immutable", ".tmp"}
        ),
        key=lambda path: path.name,
    )


def test_shared_writers_publish_exact_bytes_without_normal_stage_debris(
    tmp_path: Path,
) -> None:
    namespace = _namespace(tmp_path)
    immutable = namespace / "receipt.json"
    mutable = namespace / "state.json"

    market_no_send_io.write_bytes_immutable(immutable, b"immutable\n")
    market_no_send_io.write_bytes_atomic(mutable, b"first\n")
    market_no_send_io.write_bytes_atomic(mutable, b"second\n")

    assert immutable.read_bytes() == b"immutable\n"
    assert mutable.read_bytes() == b"second\n"
    assert _stages(namespace) == []
    with pytest.raises(MarketNoSendError, match="already exists"):
        market_no_send_io.write_bytes_immutable(immutable, b"replacement\n")
    assert immutable.read_bytes() == b"immutable\n"
    assert _stages(namespace) == []


def test_immutable_stage_substitution_cannot_return_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace = _namespace(tmp_path)
    target = namespace / "receipt.json"
    original = market_no_send_io._rename_noreplace
    stolen_name: str | None = None

    def substitute(
        namespace_fd: int,
        source: str,
        destination: str,
    ) -> bool:
        nonlocal stolen_name
        stolen_name = f"{source}.owned"
        os.rename(
            source,
            stolen_name,
            src_dir_fd=namespace_fd,
            dst_dir_fd=namespace_fd,
        )
        replacement_fd = os.open(
            source,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=namespace_fd,
        )
        try:
            os.write(replacement_fd, b"attacker\n")
        finally:
            os.close(replacement_fd)
        return original(namespace_fd, source, destination)

    monkeypatch.setattr(market_no_send_io, "_rename_noreplace", substitute)

    with pytest.raises(MarketNoSendError, match="write failed"):
        market_no_send_io.write_bytes_immutable(target, b"expected\n")

    assert stolen_name is not None
    assert target.read_bytes() == b"attacker\n"
    assert (namespace / stolen_name).read_bytes() == b"expected\n"


def test_atomic_stage_substitution_cannot_return_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace = _namespace(tmp_path)
    target = namespace / "state.json"
    target.write_bytes(b"prior\n")
    original = market_no_send_io._rename_replace
    stolen_name: str | None = None

    def substitute(
        namespace_fd: int,
        source: str,
        destination: str,
    ) -> None:
        nonlocal stolen_name
        stolen_name = f"{source}.owned"
        os.rename(
            source,
            stolen_name,
            src_dir_fd=namespace_fd,
            dst_dir_fd=namespace_fd,
        )
        replacement_fd = os.open(
            source,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=namespace_fd,
        )
        try:
            os.write(replacement_fd, b"attacker\n")
        finally:
            os.close(replacement_fd)
        original(namespace_fd, source, destination)

    monkeypatch.setattr(market_no_send_io, "_rename_replace", substitute)

    with pytest.raises(MarketNoSendError, match="write failed"):
        market_no_send_io.write_bytes_atomic(target, b"expected\n")

    assert stolen_name is not None
    assert target.read_bytes() == b"attacker\n"
    assert (namespace / stolen_name).read_bytes() == b"expected\n"


def test_failed_atomic_publication_never_unlinks_a_replacement_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace = _namespace(tmp_path)
    target = namespace / "state.json"
    target.write_bytes(b"prior\n")
    replacement_identity: tuple[int, int] | None = None
    stolen_name: str | None = None

    def substitute_then_fail(
        namespace_fd: int,
        source: str,
        _destination: str,
    ) -> None:
        nonlocal replacement_identity, stolen_name
        stolen_name = f"{source}.owned"
        os.rename(
            source,
            stolen_name,
            src_dir_fd=namespace_fd,
            dst_dir_fd=namespace_fd,
        )
        replacement_fd = os.open(
            source,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=namespace_fd,
        )
        try:
            os.write(replacement_fd, b"replacement\n")
            replacement = os.fstat(replacement_fd)
            replacement_identity = (replacement.st_dev, replacement.st_ino)
        finally:
            os.close(replacement_fd)
        raise OSError("injected rename failure")

    monkeypatch.setattr(market_no_send_io, "_rename_replace", substitute_then_fail)

    with pytest.raises(MarketNoSendError, match="write failed"):
        market_no_send_io.write_bytes_atomic(target, b"expected\n")

    assert target.read_bytes() == b"prior\n"
    assert stolen_name is not None
    assert (namespace / stolen_name).read_bytes() == b"expected\n"
    replacement = next(
        path for path in _stages(namespace) if path.name != stolen_name
    )
    info = replacement.stat()
    assert replacement_identity == (info.st_dev, info.st_ino)
    assert replacement.read_bytes() == b"replacement\n"


def test_unsupported_native_immutable_publication_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace = _namespace(tmp_path)
    target = namespace / "receipt.json"
    monkeypatch.setattr(market_no_send_io.sys, "platform", "unsupported")

    with pytest.raises(MarketNoSendError, match="unsupported"):
        market_no_send_io.write_bytes_immutable(target, b"expected\n")

    assert not target.exists()
    stages = _stages(namespace)
    assert len(stages) == 1
    assert stages[0].read_bytes() == b"expected\n"
