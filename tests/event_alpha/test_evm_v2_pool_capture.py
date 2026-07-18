from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations import evm_v2_pool_capture
from crypto_rsi_scanner.event_alpha.operations import evm_v2_pool_snapshot


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "event_dex_onchain"
    / "evm_v2_pool_rpc_bundle.json"
)


def _operator_source(tmp_path: Path) -> Path:
    bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bundle["capture_mode"] = "operator_local_import"
    bundle["provider_id"] = "operator_evm_rpc"
    path = tmp_path / "operator-rpc-bundle.json"
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_validate_local_is_no_write_and_remains_annex_detached(tmp_path: Path) -> None:
    source = _operator_source(tmp_path)
    before = {path.name: path.stat().st_mtime_ns for path in tmp_path.iterdir()}

    row = evm_v2_pool_capture.validate_local_import(source)

    after = {path.name: path.stat().st_mtime_ns for path in tmp_path.iterdir()}
    assert after == before
    assert row["source_authority"] == "operator_supplied_direct_evm_json_rpc"
    assert row["protocol_v2_input_quality_eligible"] is True
    assert row["evidence_authority_eligible"] is False
    assert row["protocol_v2_annex_bound"] is False
    assert row["protocol_v2_evidence_eligible"] is False
    assert row["campaign_attached"] is False
    assert row["provider_calls"] == 0


def test_checked_fixture_path_is_rejected_before_import() -> None:
    with pytest.raises(
        evm_v2_pool_capture.EvmV2PoolCaptureError,
        match="import_source_nonlive_path_rejected",
    ):
        evm_v2_pool_capture.validate_local_import(FIXTURE)


@pytest.mark.parametrize("provider_id", ["fixture_rpc", "mock_rpc", "replay_rpc", "test_rpc"])
def test_operator_mode_rejects_nonlive_provider_provenance(
    tmp_path: Path, provider_id: str
) -> None:
    source = _operator_source(tmp_path)
    bundle = json.loads(source.read_text(encoding="utf-8"))
    bundle["provider_id"] = provider_id
    source.write_text(json.dumps(bundle), encoding="utf-8")

    with pytest.raises(
        evm_v2_pool_capture.EvmV2PoolCaptureError,
        match="operator_provider_provenance_invalid",
    ):
        evm_v2_pool_capture.validate_local_import(source)


def test_import_requires_confirmation_before_namespace_write(tmp_path: Path) -> None:
    source = _operator_source(tmp_path)
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    before = tuple(artifact_base.iterdir())

    with pytest.raises(
        evm_v2_pool_capture.EvmV2PoolCaptureError,
        match="explicit_confirmation_required",
    ):
        evm_v2_pool_capture.persist_local_import(artifact_base, source)

    assert tuple(artifact_base.iterdir()) == before


def test_confirmed_import_seals_exact_bundle_projection_manifest_and_receipt(
    tmp_path: Path,
) -> None:
    source = _operator_source(tmp_path)
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()

    result = evm_v2_pool_capture.persist_local_import(
        artifact_base, source, confirm=True
    )

    assert result["status"] == "complete"
    assert result["created"] is True
    assert result["idempotent"] is False
    assert result["evidence_authority_eligible"] is True
    assert result["authority_basis"] == "operator_supplied_exact_rpc_bundle"
    assert result["transport_captured_by_project"] is False
    assert result["protocol_v2_input_quality_eligible"] is True
    assert result["protocol_v2_annex_bound"] is False
    assert result["protocol_v2_evidence_eligible"] is False
    assert result["campaign_attached"] is False
    assert result["directional_authority"] is False
    assert result["provider_calls"] == 0
    assert result["orders"] == result["trades"] == result["paper_trades"] == 0
    namespace = str(result["artifact_namespace"])
    namespace_dir = artifact_base / namespace
    assert set(path.name for path in namespace_dir.iterdir()) == {
        evm_v2_pool_capture.RAW_FILENAME,
        evm_v2_pool_capture.SNAPSHOT_FILENAME,
        evm_v2_pool_capture.MANIFEST_FILENAME,
        evm_v2_pool_capture.RECEIPT_FILENAME,
    }
    assert (namespace_dir / evm_v2_pool_capture.RAW_FILENAME).read_bytes() == source.read_bytes()
    assert not any("latest" in path.name for path in artifact_base.iterdir())

    validated = evm_v2_pool_capture.validate_capture(artifact_base, namespace)
    assert validated["capture_id"] == result["capture_id"]
    assert validated["raw_source"] == result["raw_source"]
    assert validated["receipt"] == result["receipt"]


def test_repeat_import_is_idempotent_and_does_not_rewrite_files(tmp_path: Path) -> None:
    source = _operator_source(tmp_path)
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    first = evm_v2_pool_capture.persist_local_import(
        artifact_base, source, confirm=True
    )
    namespace_dir = artifact_base / str(first["artifact_namespace"])
    before = {
        path.name: (path.stat().st_ino, path.stat().st_mtime_ns, path.read_bytes())
        for path in namespace_dir.iterdir()
    }

    second = evm_v2_pool_capture.persist_local_import(
        artifact_base, source, confirm=True
    )

    after = {
        path.name: (path.stat().st_ino, path.stat().st_mtime_ns, path.read_bytes())
        for path in namespace_dir.iterdir()
    }
    assert second["created"] is False
    assert second["idempotent"] is True
    assert second["capture_id"] == first["capture_id"]
    assert after == before


def test_import_reads_explicit_source_once_before_sealing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _operator_source(tmp_path)
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    original = evm_v2_pool_capture.read_capture_bytes
    calls = 0

    def counted(path: str | Path) -> bytes:
        nonlocal calls
        calls += 1
        return original(path)

    monkeypatch.setattr(evm_v2_pool_capture, "read_capture_bytes", counted)

    result = evm_v2_pool_capture.persist_local_import(
        artifact_base, source, confirm=True
    )

    assert result["status"] == "complete"
    assert calls == 1


def test_validation_rederives_raw_bytes_and_rejects_snapshot_drift(tmp_path: Path) -> None:
    source = _operator_source(tmp_path)
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    result = evm_v2_pool_capture.persist_local_import(
        artifact_base, source, confirm=True
    )
    namespace = str(result["artifact_namespace"])
    snapshot_path = artifact_base / namespace / evm_v2_pool_capture.SNAPSHOT_FILENAME
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["block_number"] += 1
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    with pytest.raises(
        evm_v2_pool_capture.EvmV2PoolCaptureError,
        match="capture_snapshot_drift",
    ):
        evm_v2_pool_capture.validate_capture(artifact_base, namespace)


def test_validation_rejects_unmanifested_or_symlink_artifacts(tmp_path: Path) -> None:
    source = _operator_source(tmp_path)
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    result = evm_v2_pool_capture.persist_local_import(
        artifact_base, source, confirm=True
    )
    namespace = str(result["artifact_namespace"])
    namespace_dir = artifact_base / namespace
    extra = namespace_dir / "extra.json"
    extra.write_text("{}\n", encoding="utf-8")
    with pytest.raises(
        evm_v2_pool_capture.EvmV2PoolCaptureError,
        match="capture_artifact_set_invalid",
    ):
        evm_v2_pool_capture.validate_capture(artifact_base, namespace)
    extra.unlink()

    snapshot = namespace_dir / evm_v2_pool_capture.SNAPSHOT_FILENAME
    snapshot_bytes = snapshot.read_bytes()
    external = tmp_path / "external-snapshot.json"
    external.write_bytes(snapshot_bytes)
    snapshot.unlink()
    snapshot.symlink_to(external)
    with pytest.raises(
        evm_v2_pool_capture.EvmV2PoolCaptureError,
        match="capture_artifact_unreadable",
    ):
        evm_v2_pool_capture.validate_capture(artifact_base, namespace)


def test_receipt_and_manifest_drift_fail_closed(tmp_path: Path) -> None:
    source = _operator_source(tmp_path)
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    result = evm_v2_pool_capture.persist_local_import(
        artifact_base, source, confirm=True
    )
    namespace = str(result["artifact_namespace"])
    manifest_path = artifact_base / namespace / evm_v2_pool_capture.MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["provider_id"] = "changed_provider"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(
        evm_v2_pool_capture.EvmV2PoolCaptureError,
        match="capture_common_contract_invalid",
    ):
        evm_v2_pool_capture.validate_capture(artifact_base, namespace)


def test_secret_like_bundle_content_is_rejected_before_write(tmp_path: Path) -> None:
    source = _operator_source(tmp_path)
    bundle = json.loads(source.read_text(encoding="utf-8"))
    bundle["rpc_exchanges"][1]["response"]["result"]["api_key"] = "should-not-persist"
    source.write_text(json.dumps(bundle), encoding="utf-8")
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()

    with pytest.raises(
        evm_v2_pool_capture.EvmV2PoolCaptureError,
        match="import_source_secret_like_value_rejected",
    ):
        evm_v2_pool_capture.persist_local_import(
            artifact_base, source, confirm=True
        )

    assert tuple(artifact_base.iterdir()) == ()


def test_finalized_block_time_cannot_postdate_acquisition() -> None:
    bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bundle["rpc_exchanges"][1]["response"]["result"]["timestamp"] = "0xffffffff"

    with pytest.raises(
        evm_v2_pool_snapshot.EvmV2PoolSnapshotError,
        match="finalized_block_time_after_acquisition",
    ):
        evm_v2_pool_snapshot.normalize_evm_v2_pool_snapshot(
            json.dumps(bundle).encode()
        )


def test_rpc_exchanges_must_be_sequential_not_overlapping() -> None:
    bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bundle["rpc_exchanges"][2]["request_started_at"] = "2026-07-18T12:00:00.150Z"

    with pytest.raises(
        evm_v2_pool_snapshot.EvmV2PoolSnapshotError,
        match="rpc_exchange_overlap_invalid",
    ):
        evm_v2_pool_snapshot.normalize_evm_v2_pool_snapshot(
            json.dumps(bundle).encode()
        )


def test_make_targets_keep_validation_no_write_and_import_confirmation_gated() -> None:
    makefile = (Path(__file__).resolve().parents[2] / "Makefile").read_text(
        encoding="utf-8"
    )

    assert "radar-dex-onchain-evm-v2-validate-local:" in makefile
    assert "radar-dex-onchain-evm-v2-import-local:" in makefile
    assert "radar-dex-onchain-evm-v2-status:" in makefile
    assert "$(if $(filter 1,$(CONFIRM)),--confirm,)" in makefile
    assert "EVM_POOL_RPC_BUNDLE is required" in makefile
    assert "EVM_POOL_CAPTURE_NAMESPACE is required" in makefile
