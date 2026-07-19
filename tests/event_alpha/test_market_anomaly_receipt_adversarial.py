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


def test_market_anomaly_bundle_refuses_existing_hard_link(tmp_path):
    namespace_dir = tmp_path / "market-anomaly-hard-link"
    namespace_dir.mkdir()
    names = ("first.jsonl", "second.md")
    original = b'{"status":"hard-linked"}\n'
    first = namespace_dir / names[0]
    linked = tmp_path / "outside-hard-link.jsonl"
    first.write_bytes(original)
    linked.hardlink_to(first)

    with pytest.raises(
        RuntimeError,
        match="market_anomaly_completion_receipt_invalid:artifact_identity",
    ):
        market_anomaly_receipt.write_artifacts_atomic(
            namespace_dir,
            payloads={names[0]: b"replacement\n", names[1]: b"replacement\n"},
            expected_names=names,
        )

    assert first.read_bytes() == original
    assert linked.read_bytes() == original
    assert not (namespace_dir / names[1]).exists()
    assert tuple(namespace_dir.iterdir()) == (first,)


def test_market_anomaly_bundle_failure_retains_partial_prefix_and_stage(
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
    assert (namespace_dir / names[0]).read_bytes() == b"replacement\n"
    assert (namespace_dir / names[1]).read_bytes() == original[names[1]]
    retained = tuple(
        path for path in namespace_dir.iterdir() if path.name.endswith(".tmp")
    )
    assert len(retained) == 1
    assert retained[0].read_bytes() == b"replacement\n"


def test_market_anomaly_initial_bundle_failure_never_rolls_back_by_pathname(
    tmp_path,
    monkeypatch,
):
    namespace_dir = tmp_path / "market-anomaly-post-rename-failure"
    namespace_dir.mkdir()
    names = ("first.jsonl", "second.md")
    real_noreplace = market_anomaly_receipt._rename_noreplace
    failed = False

    def fail_after_first_staged_replace(namespace_fd, source, target):
        nonlocal failed
        if (
            not failed
            and target == names[0]
            and isinstance(source, str)
            and source.endswith(".tmp")
        ):
            failed = True
            assert real_noreplace(namespace_fd, source, target) is True
            raise OSError("adversarial failure after successful rename")
        return real_noreplace(namespace_fd, source, target)

    monkeypatch.setattr(
        market_anomaly_receipt,
        "_rename_noreplace",
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
    assert (namespace_dir / names[0]).read_bytes() == b"first\n"
    assert not (namespace_dir / names[1]).exists()
    retained = tuple(
        path for path in namespace_dir.iterdir() if path.name.endswith(".tmp")
    )
    assert len(retained) == 1
    assert retained[0].read_bytes() == b"second\n"


def test_market_anomaly_stage_substitution_fails_without_deleting_replacement(
    tmp_path,
    monkeypatch,
):
    namespace_dir = tmp_path / "market-anomaly-stage-substitution"
    namespace_dir.mkdir()
    names = ("first.jsonl", "second.md")
    real_install = market_anomaly_receipt._install_staged_leaf
    substituted: dict[str, object] = {}

    def substitute_stage(namespace_fd, **kwargs):
        if not substituted:
            staged_name = kwargs["staged_name"]
            staged_path = namespace_dir / staged_name
            displaced = namespace_dir / ".descriptor-bound-original-stage"
            staged_path.rename(displaced)
            staged_path.write_bytes(b"raced-stage-must-survive\n")
            substituted.update(staged_name=staged_name, displaced=displaced)
        return real_install(namespace_fd, **kwargs)

    monkeypatch.setattr(
        market_anomaly_receipt,
        "_install_staged_leaf",
        substitute_stage,
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

    assert not (namespace_dir / names[0]).exists()
    assert not (namespace_dir / names[1]).exists()
    assert (namespace_dir / str(substituted["staged_name"])).read_bytes() == (
        b"raced-stage-must-survive\n"
    )
    assert substituted["displaced"].read_bytes() == b"first\n"


def test_market_anomaly_new_leaf_race_uses_native_noreplace(tmp_path, monkeypatch):
    namespace_dir = tmp_path / "market-anomaly-destination-race"
    namespace_dir.mkdir()
    names = ("first.jsonl", "second.md")
    real_noreplace = market_anomaly_receipt._rename_noreplace
    competitor = b"concurrent-owner-must-survive\n"
    raced = False

    def race_destination(namespace_fd, source, destination):
        nonlocal raced
        if not raced and destination == names[0]:
            raced = True
            (namespace_dir / destination).write_bytes(competitor)
        return real_noreplace(namespace_fd, source, destination)

    monkeypatch.setattr(
        market_anomaly_receipt,
        "_rename_noreplace",
        race_destination,
    )
    with pytest.raises(
        RuntimeError,
        match="market_anomaly_completion_receipt_invalid:artifact_identity",
    ):
        market_anomaly_receipt.write_artifacts_atomic(
            namespace_dir,
            payloads={names[0]: b"first\n", names[1]: b"second\n"},
            expected_names=names,
        )

    assert raced is True
    assert (namespace_dir / names[0]).read_bytes() == competitor
    assert not (namespace_dir / names[1]).exists()
    assert sorted(
        path.read_bytes()
        for path in namespace_dir.iterdir()
        if path.name.endswith(".tmp")
    ) == [b"first\n", b"second\n"]


def test_market_anomaly_post_publish_substitution_never_returns_success(
    tmp_path,
    monkeypatch,
):
    namespace_dir = tmp_path / "market-anomaly-post-publish-substitution"
    namespace_dir.mkdir()
    names = ("first.jsonl", "second.md")
    real_noreplace = market_anomaly_receipt._rename_noreplace
    attacker = b"post-publish-replacement-must-survive\n"
    displaced = namespace_dir / ".published-descriptor-bound-leaf"
    substituted = False

    def substitute_published(namespace_fd, source, destination):
        nonlocal substituted
        published = real_noreplace(namespace_fd, source, destination)
        if published and not substituted and destination == names[0]:
            substituted = True
            (namespace_dir / destination).rename(displaced)
            (namespace_dir / destination).write_bytes(attacker)
        return published

    monkeypatch.setattr(
        market_anomaly_receipt,
        "_rename_noreplace",
        substitute_published,
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

    assert substituted is True
    assert (namespace_dir / names[0]).read_bytes() == attacker
    assert displaced.read_bytes() == b"first\n"
    assert not (namespace_dir / names[1]).exists()


def test_market_anomaly_payload_read_rejects_named_leaf_substitution(
    tmp_path,
    monkeypatch,
):
    namespace_dir = tmp_path / "market-anomaly-read-substitution"
    namespace_dir.mkdir()
    names = ("first.jsonl", "second.md")
    payloads = {names[0]: b"first\n", names[1]: b"second\n"}
    identity = market_anomaly_receipt.write_artifacts_atomic(
        namespace_dir,
        payloads=payloads,
        expected_names=names,
    )
    real_open = market_anomaly_receipt.os.open
    displaced = namespace_dir / ".read-descriptor-bound-leaf"
    attacker = b"read-path-replacement-must-survive\n"
    substituted = False

    def substitute_after_open(path, flags, *args, **kwargs):
        nonlocal substituted
        descriptor = real_open(path, flags, *args, **kwargs)
        if path == names[0] and kwargs.get("dir_fd") is not None and not substituted:
            substituted = True
            (namespace_dir / names[0]).rename(displaced)
            (namespace_dir / names[0]).write_bytes(attacker)
        return descriptor

    monkeypatch.setattr(market_anomaly_receipt.os, "open", substitute_after_open)
    with pytest.raises(
        RuntimeError,
        match="market_anomaly_completion_receipt_invalid:artifact_identity",
    ):
        market_anomaly_receipt.artifact_payloads(
            namespace_dir,
            namespace_identity=identity,
            paths=tuple(namespace_dir / name for name in names),
            expected_names=names,
        )

    assert substituted is True
    assert (namespace_dir / names[0]).read_bytes() == attacker
    assert displaced.read_bytes() == payloads[names[0]]


def test_market_anomaly_payload_read_rejects_namespace_substitution(
    tmp_path,
    monkeypatch,
):
    namespace_dir = tmp_path / "market-anomaly-read-namespace-substitution"
    namespace_dir.mkdir()
    names = ("first.jsonl", "second.md")
    payloads = {names[0]: b"first\n", names[1]: b"second\n"}
    identity = market_anomaly_receipt.write_artifacts_atomic(
        namespace_dir,
        payloads=payloads,
        expected_names=names,
    )
    displaced = tmp_path / "market-anomaly-read-namespace-displaced"
    replacement = tmp_path / "market-anomaly-read-namespace-replacement"
    replacement.mkdir()
    for name in names:
        (replacement / name).write_bytes(b"replacement-namespace\n")
    real_read = market_anomaly_receipt._read_regular_leaf
    substituted = False

    def substitute_namespace(namespace_fd, name):
        nonlocal substituted
        payload = real_read(namespace_fd, name)
        if not substituted:
            substituted = True
            namespace_dir.rename(displaced)
            replacement.rename(namespace_dir)
        return payload

    monkeypatch.setattr(
        market_anomaly_receipt,
        "_read_regular_leaf",
        substitute_namespace,
    )
    with pytest.raises(
        RuntimeError,
        match="market_anomaly_completion_receipt_invalid:namespace_identity",
    ):
        market_anomaly_receipt.artifact_payloads(
            namespace_dir,
            namespace_identity=identity,
            paths=tuple(namespace_dir / name for name in names),
            expected_names=names,
        )

    assert substituted is True
    assert (namespace_dir / names[0]).read_bytes() == b"replacement-namespace\n"
    assert (displaced / names[0]).read_bytes() == payloads[names[0]]
