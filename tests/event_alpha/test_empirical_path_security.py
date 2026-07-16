"""Portable descriptor-walk regressions for empirical replay and feedback."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations import (
    empirical_replay_data,
    empirical_review_feedback,
)
from crypto_rsi_scanner.event_alpha.operations.empirical_review import (
    build_targeted_review_queue,
)


_DAY_MS = 86_400_000
_START = datetime(2025, 1, 1, tzinfo=timezone.utc)
_RUN_FINGERPRINT = "a" * 64
_PROTOCOL_SHA256 = "b" * 64


def _kline_rows(*, quote_volume: float = 1_000_000.0) -> list[list[object]]:
    rows: list[list[object]] = []
    for offset in range(31):
        opened = _START + timedelta(days=offset)
        opened_ms = int(opened.timestamp() * 1000)
        close = 100.0 + offset
        rows.append(
            [
                opened_ms,
                f"{close:.8f}",
                f"{close * 1.01:.8f}",
                f"{close * 0.99:.8f}",
                f"{close:.8f}",
                f"{quote_volume / close:.8f}",
                opened_ms + _DAY_MS - 1,
                f"{quote_volume:.8f}",
                100,
                "0",
                "0",
                "0",
            ]
        )
    return rows


def _write_cache(directory: Path, *, quote_volume: float = 1_000_000.0) -> Path:
    directory.mkdir(parents=True)
    path = directory / "AAAUSDT-60d.json"
    path.write_text(
        json.dumps(_kline_rows(quote_volume=quote_volume), separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def _queue() -> dict[str, object]:
    missed = {
        "missed_move_id": "missed-move-v1:" + "d" * 64,
        "directional_bias": "long",
        "primary_endpoint_return_fraction": 0.20,
        "qualifies_as_missed_opportunity": True,
        "observation": {
            "canonical_asset_id": "bitcoin",
            "symbol": "BTC",
            "observed_at": "2022-01-01T00:00:00+00:00",
            "partition": "development",
            "data_quality_mode": "historical_ohlcv",
            "baseline_status": "warm",
            "liquidity_tier": "high",
            "observation_digest": "e" * 64,
        },
        "outcome": {
            "status": "matured",
            "primary_direction_adjusted_return": 0.20,
            "max_favorable_excursion": 0.25,
            "max_adverse_excursion": -0.03,
            "return_unit": "fraction",
        },
    }
    return build_targeted_review_queue(
        [],
        {"episodes": []},
        {"partitions": {}},
        {
            "protocol_version": "decision_radar_empirical_validation_v1",
            "protocol_sha256": _PROTOCOL_SHA256,
            "contract_digest": "c" * 64,
            "evidence_mode": "historical_replay",
            "missed_move_evaluation": {
                "missed_opportunity_count": 1,
                "missed_opportunities": [missed],
            },
        },
        run_fingerprint=_RUN_FINGERPRINT,
    )


def _feedback_event(
    queue: dict[str, object], *, event_id: str = "human-label-001"
) -> dict[str, object]:
    item = queue["items"][0]
    assert isinstance(item, dict)
    return empirical_review_feedback.build_feedback_event(
        queue,
        review_item_id=str(item["review_item_id"]),
        label="useful",
        observed_at="2026-07-16T12:00:00+00:00",
        reviewer_alias="owner",
        label_event_id=event_id,
    )


def test_empirical_paths_accept_safe_ordinary_directories(tmp_path: Path) -> None:
    cache = tmp_path / "safe" / "cache"
    _write_cache(cache)
    dataset = empirical_replay_data.load_binance_cache_dataset(cache)
    assert [row.symbol for row in dataset.series] == ["AAAUSDT"]

    queue = _queue()
    event = _feedback_event(queue)
    ledger = tmp_path / "safe" / "human" / "feedback.jsonl"
    ledger.parent.mkdir()
    result = empirical_review_feedback.append_feedback_event(
        ledger, queue, event, confirm=True
    )
    assert result["status"] == "appended"
    assert empirical_review_feedback.read_feedback_ledger(ledger, queue) == (event,)


def test_replay_rejects_root_and_intermediate_directory_symlinks(
    tmp_path: Path,
) -> None:
    real_root = tmp_path / "real"
    cache = real_root / "cache"
    _write_cache(cache)

    root_link = tmp_path / "cache-link"
    root_link.symlink_to(cache, target_is_directory=True)
    with pytest.raises(
        empirical_replay_data.ReplayDataError,
        match="input_directory_unavailable_or_unsafe",
    ):
        empirical_replay_data.load_binance_cache_dataset(root_link)

    intermediate_link = tmp_path / "root-link"
    intermediate_link.symlink_to(real_root, target_is_directory=True)
    with pytest.raises(
        empirical_replay_data.ReplayDataError,
        match="input_directory_unavailable_or_unsafe",
    ):
        empirical_replay_data.load_binance_cache_dataset(
            intermediate_link / "cache"
        )


def test_replay_directory_replacement_cannot_redirect_outside(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = tmp_path / "trusted" / "cache"
    _write_cache(cache)
    displaced = cache.with_name("cache.checked")
    outside = tmp_path / "outside"
    _write_cache(outside, quote_volume=9_000_000.0)
    original_open = empirical_replay_data.os.open
    swapped = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        is_target = (
            (dir_fd is None and Path(path) == cache)
            or (dir_fd is not None and path == cache.name)
        )
        if is_target and not swapped:
            cache.rename(displaced)
            cache.symlink_to(outside, target_is_directory=True)
            flags &= ~empirical_replay_data.os.O_NOFOLLOW
            swapped = True
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(empirical_replay_data.os, "open", racing_open)
    with pytest.raises(
        empirical_replay_data.ReplayDataError,
        match="input_directory_unavailable_or_unsafe",
    ):
        empirical_replay_data.load_binance_cache_dataset(cache)

    assert swapped is True
    assert (outside / "AAAUSDT-60d.json").is_file()


@pytest.mark.parametrize("replacement_kind", ("symlink", "regular"))
def test_replay_final_file_replacement_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replacement_kind: str,
) -> None:
    cache = tmp_path / "cache"
    target = _write_cache(cache)
    displaced = target.with_name("AAAUSDT-60d.checked")
    outside = tmp_path / "outside.json"
    outside.write_text(
        json.dumps(_kline_rows(quote_volume=9_000_000.0), separators=(",", ":")),
        encoding="utf-8",
    )
    original_open = empirical_replay_data.os.open
    swapped = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if dir_fd is not None and path == target.name and not swapped:
            target.rename(displaced)
            if replacement_kind == "symlink":
                target.symlink_to(outside)
                flags &= ~empirical_replay_data.os.O_NOFOLLOW
            else:
                outside.rename(target)
            swapped = True
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(empirical_replay_data.os, "open", racing_open)
    with pytest.raises(empirical_replay_data.ReplayDataError):
        empirical_replay_data.load_binance_cache_dataset(cache)

    assert swapped is True


def test_replay_named_file_replacement_during_read_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = tmp_path / "cache"
    target = _write_cache(cache)
    displaced = target.with_name("AAAUSDT-60d.checked")
    replacement = tmp_path / "replacement.json"
    replacement.write_text(
        json.dumps(_kline_rows(quote_volume=9_000_000.0), separators=(",", ":")),
        encoding="utf-8",
    )
    original_read = empirical_replay_data.os.read
    swapped = False

    def racing_read(descriptor: int, size: int) -> bytes:
        nonlocal swapped
        chunk = original_read(descriptor, size)
        if chunk and not swapped:
            target.rename(displaced)
            replacement.rename(target)
            swapped = True
        return chunk

    monkeypatch.setattr(empirical_replay_data.os, "read", racing_read)
    with pytest.raises(
        empirical_replay_data.ReplayDataError,
        match="input_file_changed_while_reading",
    ):
        empirical_replay_data.load_binance_cache_dataset(cache)

    assert swapped is True


def test_feedback_rejects_intermediate_parent_symlink_without_outside_write(
    tmp_path: Path,
) -> None:
    queue = _queue()
    event = _feedback_event(queue)
    outside_root = tmp_path / "outside"
    outside_parent = outside_root / "human"
    outside_parent.mkdir(parents=True)
    linked_root = tmp_path / "linked-root"
    linked_root.symlink_to(outside_root, target_is_directory=True)
    ledger = linked_root / "human" / "feedback.jsonl"

    with pytest.raises(RuntimeError, match="parent_unsafe"):
        empirical_review_feedback.append_feedback_event(
            ledger, queue, event, confirm=True
        )

    assert not (outside_parent / ledger.name).exists()


def test_feedback_parent_replacement_cannot_redirect_outside(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue = _queue()
    event = _feedback_event(queue)
    parent = tmp_path / "trusted" / "human"
    parent.mkdir(parents=True)
    displaced = parent.with_name("human.checked")
    outside = tmp_path / "outside"
    outside.mkdir()
    ledger = parent / "feedback.jsonl"
    original_open = empirical_review_feedback.os.open
    swapped = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        is_target = (
            (dir_fd is None and Path(path) == parent)
            or (dir_fd is not None and path == parent.name)
        )
        if is_target and not swapped:
            parent.rename(displaced)
            parent.symlink_to(outside, target_is_directory=True)
            flags &= ~empirical_review_feedback.os.O_NOFOLLOW
            swapped = True
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(empirical_review_feedback.os, "open", racing_open)
    with pytest.raises(RuntimeError, match="parent_unsafe"):
        empirical_review_feedback.append_feedback_event(
            ledger, queue, event, confirm=True
        )

    assert swapped is True
    assert not (outside / ledger.name).exists()
    assert not (displaced / ledger.name).exists()


def test_feedback_missing_leaf_symlink_race_never_appends_outside(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue = _queue()
    event = _feedback_event(queue)
    parent = tmp_path / "human"
    parent.mkdir()
    ledger = parent / "feedback.jsonl"
    outside = tmp_path / "outside.jsonl"
    outside.write_bytes(b"")
    original_open = empirical_review_feedback.os.open
    swapped = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if dir_fd is not None and path == ledger.name and not swapped:
            ledger.symlink_to(outside)
            flags &= ~empirical_review_feedback.os.O_NOFOLLOW
            swapped = True
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(empirical_review_feedback.os, "open", racing_open)
    with pytest.raises(RuntimeError, match="ledger_unsafe"):
        empirical_review_feedback.append_feedback_event(
            ledger, queue, event, confirm=True
        )

    assert swapped is True
    assert outside.read_bytes() == b""


def test_empirical_path_access_requires_descriptor_features(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = tmp_path / "cache"
    _write_cache(cache)
    monkeypatch.setattr(empirical_replay_data, "_OPEN_SUPPORTS_DIR_FD", False)
    with pytest.raises(
        empirical_replay_data.ReplayDataError,
        match="descriptor_relative_no_follow_access_unsupported",
    ):
        empirical_replay_data.load_binance_cache_dataset(cache)

    queue = _queue()
    event = _feedback_event(queue)
    ledger = tmp_path / "feedback.jsonl"
    monkeypatch.setattr(empirical_review_feedback, "_OPEN_SUPPORTS_DIR_FD", False)
    with pytest.raises(RuntimeError, match="descriptor_features_unavailable"):
        empirical_review_feedback.append_feedback_event(
            ledger, queue, event, confirm=True
        )
    assert not ledger.exists()
