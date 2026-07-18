from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations import evm_v2_pool_snapshot


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "event_dex_onchain"
    / "evm_v2_pool_rpc_bundle.json"
)


def _bundle() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _raw(value: dict[str, object]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def test_exact_finalized_pool_bundle_normalizes_without_inventing_usd_or_direction() -> None:
    raw = FIXTURE.read_bytes()

    row = evm_v2_pool_snapshot.normalize_evm_v2_pool_snapshot(
        raw,
        expected_capture_mode=evm_v2_pool_snapshot.CAPTURE_MODE_FIXTURE,
    )

    assert row["schema_id"] == "decision_radar.evm_v2_pool_snapshot"
    assert row["contract_version"] == "decision_radar_evm_v2_pool_snapshot_v1"
    assert row["chain_id"] == "eip155:1"
    assert row["block_number"] == 20_000_000
    assert row["block_number_hex"] == "0x1312d00"
    assert row["finality_at_acquisition"] == "finalized"
    assert row["provider_observed_at"] == "2024-06-01T00:00:00Z"
    assert row["acquired_at"] == "2026-07-18T12:00:00.700000Z"
    assert row["token0"]["reserve_base_units"] == "1234567890000"
    assert row["token0"]["reserve_token_units"] == "1234567.89"
    assert row["token0"]["decimals"] == 6
    assert row["token1"]["reserve_base_units"] == "987654321000000000000"
    assert row["token1"]["reserve_token_units"] == "987.654321"
    assert row["token1"]["decimals"] == 18
    assert row["usd_liquidity_available"] is False
    assert row["usd_liquidity_estimated"] is False
    assert row["directional_authority"] is False
    assert row["context_only"] is True
    assert row["evidence_authority_eligible"] is False
    assert row["protocol_v2_input_quality_eligible"] is False
    assert row["protocol_v2_annex_bound"] is False
    assert row["protocol_v2_evidence_eligible"] is False
    assert row["provider_calls"] == 0
    assert row["orders"] == row["trades"] == row["paper_trades"] == 0
    assert row["normal_rsi_writes"] == row["event_alpha_triggered_fade"] == 0
    assert row["source_lineage_id"] == f"sha256:{row['raw_source_sha256']}"
    assert len(row["onchain_context_rows"]) == 2
    for context in row["onchain_context_rows"]:
        assert {
            "chain_id",
            "canonical_asset_id",
            "metric_name",
            "metric_value",
            "block_number_or_time",
            "provider_observed_at",
            "acquired_at",
            "source_lineage_id",
        } <= set(context)
        assert context["directional_authority"] is False
        assert context["research_only"] is True


def test_operator_import_is_only_input_quality_eligible_until_immutable_capture_and_annex() -> None:
    bundle = _bundle()
    bundle["capture_mode"] = "operator_local_import"
    bundle["provider_id"] = "operator_evm_rpc"

    row = evm_v2_pool_snapshot.normalize_evm_v2_pool_snapshot(
        _raw(bundle), expected_capture_mode="operator_local_import"
    )

    assert row["protocol_v2_input_quality_eligible"] is True
    assert row["evidence_authority_eligible"] is False
    assert row["protocol_v2_annex_bound"] is False
    assert row["protocol_v2_evidence_eligible"] is False
    assert row["campaign_attached"] is False


def test_capture_mode_must_match_explicit_operator_intent() -> None:
    with pytest.raises(
        evm_v2_pool_snapshot.EvmV2PoolSnapshotError,
        match="capture_mode_invalid",
    ):
        evm_v2_pool_snapshot.normalize_evm_v2_pool_snapshot(
            FIXTURE.read_bytes(), expected_capture_mode="operator_local_import"
        )


@pytest.mark.parametrize("block_parameter", ["latest", "safe", "finalized", "0x1312d01"])
def test_all_contract_calls_must_use_the_exact_node_reported_finalized_block(
    block_parameter: str,
) -> None:
    bundle = _bundle()
    bundle["rpc_exchanges"][2]["request"]["params"][1] = block_parameter

    with pytest.raises(
        evm_v2_pool_snapshot.EvmV2PoolSnapshotError,
        match="rpc_exchange_3_request_contract_invalid",
    ):
        evm_v2_pool_snapshot.normalize_evm_v2_pool_snapshot(_raw(bundle))


def test_chain_and_pair_identity_are_cross_checked_against_rpc_results() -> None:
    chain_mismatch = _bundle()
    chain_mismatch["chain_id"] = "eip155:8453"
    with pytest.raises(
        evm_v2_pool_snapshot.EvmV2PoolSnapshotError, match="chain_id_mismatch"
    ):
        evm_v2_pool_snapshot.normalize_evm_v2_pool_snapshot(_raw(chain_mismatch))

    token_mismatch = _bundle()
    token_mismatch["token0"]["contract_address"] = (
        "0x4444444444444444444444444444444444444444"
    )
    token_mismatch["rpc_exchanges"][5]["request"]["params"][0]["to"] = (
        "0x4444444444444444444444444444444444444444"
    )
    with pytest.raises(
        evm_v2_pool_snapshot.EvmV2PoolSnapshotError,
        match="token0_contract_mismatch",
    ):
        evm_v2_pool_snapshot.normalize_evm_v2_pool_snapshot(_raw(token_mismatch))


def test_malformed_abi_result_and_rpc_error_fail_closed() -> None:
    malformed = _bundle()
    malformed["rpc_exchanges"][4]["response"]["result"] = "0x01"
    with pytest.raises(
        evm_v2_pool_snapshot.EvmV2PoolSnapshotError,
        match="get_reserves_result_length_invalid",
    ):
        evm_v2_pool_snapshot.normalize_evm_v2_pool_snapshot(_raw(malformed))

    rpc_error = _bundle()
    rpc_error["rpc_exchanges"][4]["response"] = {
        "jsonrpc": "2.0",
        "id": 5,
        "error": {"code": -32000, "message": "execution reverted"},
    }
    with pytest.raises(
        evm_v2_pool_snapshot.EvmV2PoolSnapshotError,
        match="rpc_exchange_5_response_invalid",
    ):
        evm_v2_pool_snapshot.normalize_evm_v2_pool_snapshot(_raw(rpc_error))


def test_duplicate_json_keys_are_rejected() -> None:
    raw = FIXTURE.read_bytes().replace(
        b'"schema_version": 1,',
        b'"schema_version": 1, "schema_version": 1,',
        1,
    )

    with pytest.raises(
        evm_v2_pool_snapshot.EvmV2PoolSnapshotError, match="capture_json_invalid"
    ):
        evm_v2_pool_snapshot.normalize_evm_v2_pool_snapshot(raw)


def test_bounded_reader_rejects_symlink_leaf(tmp_path: Path) -> None:
    target = tmp_path / "capture.json"
    target.write_bytes(FIXTURE.read_bytes())
    link = tmp_path / "capture-link.json"
    link.symlink_to(target)

    with pytest.raises(
        evm_v2_pool_snapshot.EvmV2PoolSnapshotError,
        match="capture_file_unreadable",
    ):
        evm_v2_pool_snapshot.read_capture_bytes(link)


def test_response_order_and_request_ids_are_closed() -> None:
    reordered = _bundle()
    reordered["rpc_exchanges"][0], reordered["rpc_exchanges"][1] = (
        reordered["rpc_exchanges"][1],
        reordered["rpc_exchanges"][0],
    )
    with pytest.raises(
        evm_v2_pool_snapshot.EvmV2PoolSnapshotError,
        match="rpc_exchange_order_invalid|rpc_exchange_1_request_contract_invalid",
    ):
        evm_v2_pool_snapshot.normalize_evm_v2_pool_snapshot(_raw(reordered))

    duplicate_id = deepcopy(_bundle())
    duplicate_id["rpc_exchanges"][1]["request"]["id"] = 1
    duplicate_id["rpc_exchanges"][1]["response"]["id"] = 1
    with pytest.raises(
        evm_v2_pool_snapshot.EvmV2PoolSnapshotError,
        match="rpc_request_id_duplicate",
    ):
        evm_v2_pool_snapshot.normalize_evm_v2_pool_snapshot(_raw(duplicate_id))
