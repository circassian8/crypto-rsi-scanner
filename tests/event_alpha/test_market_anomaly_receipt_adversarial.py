"""Adversarial transaction tests for market-anomaly artifact bundles."""

from __future__ import annotations

import pytest

from crypto_rsi_scanner.event_alpha.radar import market_anomaly_receipt


def test_market_anomaly_enrichment_refuses_replaced_exact_namespace(tmp_path):
    namespace_dir = tmp_path / "market-anomaly-exact-rewrite"
    namespace_dir.mkdir()
    names = ("first.jsonl", "second.md")
    original = {names[0]: b'{"status":"original"}\n', names[1]: b"original\n"}
    identity = market_anomaly_receipt.write_artifacts_atomic(
        namespace_dir,
        payloads=original,
        expected_names=names,
    )
    retired = tmp_path / "retired-market-anomaly-exact-rewrite"
    namespace_dir.rename(retired)
    namespace_dir.mkdir()
    sentinel = namespace_dir / "sentinel.txt"
    sentinel.write_text("substitute-unchanged\n", encoding="utf-8")

    with pytest.raises(
        RuntimeError,
        match="market_anomaly_completion_receipt_invalid:namespace_identity",
    ):
        market_anomaly_receipt.write_artifacts_atomic(
            namespace_dir,
            payloads={names[0]: b"replacement\n", names[1]: b"replacement\n"},
            expected_names=names,
            expected_namespace_identity=identity,
            expected_existing_sha256={
                name: market_anomaly_receipt.sha256(payload)
                for name, payload in original.items()
            },
        )

    assert tuple(namespace_dir.iterdir()) == (sentinel,)
    assert sentinel.read_text(encoding="utf-8") == "substitute-unchanged\n"
    assert (retired / names[0]).read_bytes() == original[names[0]]
    assert (retired / names[1]).read_bytes() == original[names[1]]


def test_market_anomaly_enrichment_refuses_changed_existing_bundle(tmp_path):
    namespace_dir = tmp_path / "market-anomaly-exact-existing"
    namespace_dir.mkdir()
    names = ("first.jsonl", "second.md")
    original = {names[0]: b'{"status":"original"}\n', names[1]: b"original\n"}
    identity = market_anomaly_receipt.write_artifacts_atomic(
        namespace_dir,
        payloads=original,
        expected_names=names,
    )
    (namespace_dir / names[0]).write_bytes(b'{"status":"changed"}\n')

    with pytest.raises(
        RuntimeError,
        match="market_anomaly_completion_receipt_invalid:artifact_identity",
    ):
        market_anomaly_receipt.write_artifacts_atomic(
            namespace_dir,
            payloads={names[0]: b"replacement\n", names[1]: b"replacement\n"},
            expected_names=names,
            expected_namespace_identity=identity,
            expected_existing_sha256={
                name: market_anomaly_receipt.sha256(payload)
                for name, payload in original.items()
            },
        )

    assert (namespace_dir / names[0]).read_bytes() == b'{"status":"changed"}\n'
    assert (namespace_dir / names[1]).read_bytes() == original[names[1]]


def test_market_anomaly_bundle_rolls_back_earlier_leaf_when_later_replace_fails(
    tmp_path,
    monkeypatch,
):
    namespace_dir = tmp_path / "market-anomaly-transaction-rollback"
    namespace_dir.mkdir()
    names = ("first.jsonl", "second.md")
    original = {names[0]: b'{"status":"original"}\n', names[1]: b"original\n"}
    identity = market_anomaly_receipt.write_artifacts_atomic(
        namespace_dir,
        payloads=original,
        expected_names=names,
    )
    real_rename = market_anomaly_receipt.os.rename
    failed = False

    def fail_second_staged_replace(source, target, *args, **kwargs):
        nonlocal failed
        if (
            not failed
            and target == names[1]
            and isinstance(source, str)
            and source.endswith(".tmp")
            and kwargs.get("src_dir_fd") is not None
        ):
            failed = True
            raise OSError("adversarial later-leaf replacement failure")
        return real_rename(source, target, *args, **kwargs)

    monkeypatch.setattr(
        market_anomaly_receipt.os,
        "rename",
        fail_second_staged_replace,
    )
    with pytest.raises(
        RuntimeError,
        match="market_anomaly_completion_receipt_invalid:artifact_write",
    ):
        market_anomaly_receipt.write_artifacts_atomic(
            namespace_dir,
            payloads={names[0]: b"replacement\n", names[1]: b"replacement\n"},
            expected_names=names,
            expected_namespace_identity=identity,
            expected_existing_sha256={
                name: market_anomaly_receipt.sha256(payload)
                for name, payload in original.items()
            },
        )

    assert failed is True
    assert {
        path.name: path.read_bytes()
        for path in namespace_dir.iterdir()
    } == original


def test_market_anomaly_initial_bundle_rolls_back_when_rename_then_raises(
    tmp_path,
    monkeypatch,
):
    namespace_dir = tmp_path / "market-anomaly-post-rename-failure"
    namespace_dir.mkdir()
    names = ("first.jsonl", "second.md")
    real_rename = market_anomaly_receipt.os.rename
    failed = False

    def fail_after_first_staged_replace(source, target, *args, **kwargs):
        nonlocal failed
        if (
            not failed
            and target == names[0]
            and isinstance(source, str)
            and source.endswith(".tmp")
            and kwargs.get("src_dir_fd") is not None
        ):
            failed = True
            real_rename(source, target, *args, **kwargs)
            raise OSError("adversarial failure after successful rename")
        return real_rename(source, target, *args, **kwargs)

    monkeypatch.setattr(
        market_anomaly_receipt.os,
        "rename",
        fail_after_first_staged_replace,
    )
    with pytest.raises(
        RuntimeError,
        match="market_anomaly_completion_receipt_invalid:artifact_write",
    ):
        market_anomaly_receipt.write_artifacts_atomic(
            namespace_dir,
            payloads={names[0]: b"first\n", names[1]: b"second\n"},
            expected_names=names,
        )

    assert failed is True
    assert tuple(namespace_dir.iterdir()) == ()
