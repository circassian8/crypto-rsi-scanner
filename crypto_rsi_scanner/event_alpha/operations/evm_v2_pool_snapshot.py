"""Strict offline normalizer for one EVM v2-compatible DEX pool snapshot.

The contract intentionally covers only Uniswap-v2-compatible pairs.  It accepts
an exact read-only JSON-RPC exchange bundle captured at one node-reported
``finalized`` block and emits point-in-time reserve context.  It does not make
network calls, estimate USD liquidity, infer direction, publish authority, or
attach evidence to Protocol v2.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping, Sequence

from .market_no_send_io import parse_json_object_bytes
from .market_no_send_models import MarketNoSendError


INPUT_SCHEMA_ID = "decision_radar.evm_v2_pool_rpc_bundle"
OUTPUT_SCHEMA_ID = "decision_radar.evm_v2_pool_snapshot"
CONTRACT_VERSION = "decision_radar_evm_v2_pool_snapshot_v1"
MAX_CAPTURE_BYTES = 512 * 1024
MAX_RPC_DURATION_MS = 120_000

CAPTURE_MODE_FIXTURE = "fixture"
CAPTURE_MODE_OPERATOR_IMPORT = "operator_local_import"
CAPTURE_MODES = frozenset({CAPTURE_MODE_FIXTURE, CAPTURE_MODE_OPERATOR_IMPORT})

ETH_CHAIN_ID = "eth_chainId"
ETH_GET_BLOCK_BY_NUMBER = "eth_getBlockByNumber"
ETH_CALL = "eth_call"

TOKEN0_SELECTOR = "0x0dfe1681"
TOKEN1_SELECTOR = "0xd21220a7"
GET_RESERVES_SELECTOR = "0x0902f1ac"
DECIMALS_SELECTOR = "0x313ce567"

_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_DATA_RE = re.compile(r"^0x(?:[0-9a-fA-F]{2})*$")
_QUANTITY_RE = re.compile(r"^(?:0x0|0x[1-9a-fA-F][0-9a-fA-F]*)$")
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}$")
_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,15}$")


class EvmV2PoolSnapshotError(ValueError):
    """Raised when an offline EVM pool bundle violates the closed contract."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _utc(value: object, field: str) -> tuple[str, datetime]:
    if not isinstance(value, str) or not value.strip():
        raise EvmV2PoolSnapshotError(f"{field}_missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvmV2PoolSnapshotError(f"{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EvmV2PoolSnapshotError(f"{field}_timezone_missing")
    utc = parsed.astimezone(timezone.utc)
    return utc.isoformat().replace("+00:00", "Z"), utc


def _address(value: object, field: str) -> str:
    if not isinstance(value, str) or not _ADDRESS_RE.fullmatch(value):
        raise EvmV2PoolSnapshotError(f"{field}_invalid")
    return value.casefold()


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise EvmV2PoolSnapshotError(f"{field}_invalid")
    return value


def _symbol(value: object, field: str) -> str:
    if not isinstance(value, str) or not _SYMBOL_RE.fullmatch(value):
        raise EvmV2PoolSnapshotError(f"{field}_invalid")
    return value


def _quantity(value: object, field: str) -> tuple[int, str]:
    if not isinstance(value, str) or not _QUANTITY_RE.fullmatch(value):
        raise EvmV2PoolSnapshotError(f"{field}_invalid")
    return int(value, 16), value.casefold()


def _data(value: object, field: str, *, byte_length: int | None = None) -> str:
    if not isinstance(value, str) or not _DATA_RE.fullmatch(value):
        raise EvmV2PoolSnapshotError(f"{field}_invalid")
    normalized = value.casefold()
    if byte_length is not None and len(normalized) != 2 + byte_length * 2:
        raise EvmV2PoolSnapshotError(f"{field}_length_invalid")
    return normalized


def _decode_abi_address(value: object, field: str) -> str:
    encoded = _data(value, field, byte_length=32)
    if encoded[2:26] != "0" * 24:
        raise EvmV2PoolSnapshotError(f"{field}_padding_invalid")
    return _address("0x" + encoded[-40:], field)


def _decode_abi_uint(value: object, field: str, *, bits: int = 256) -> int:
    encoded = _data(value, field, byte_length=32)
    decoded = int(encoded[2:], 16)
    if decoded >= 1 << bits:
        raise EvmV2PoolSnapshotError(f"{field}_range_invalid")
    return decoded


def _decode_reserves(value: object) -> tuple[int, int, int]:
    encoded = _data(value, "get_reserves_result", byte_length=96)[2:]
    reserve0 = int(encoded[0:64], 16)
    reserve1 = int(encoded[64:128], 16)
    timestamp_last = int(encoded[128:192], 16)
    if reserve0 >= 1 << 112 or reserve1 >= 1 << 112 or timestamp_last >= 1 << 32:
        raise EvmV2PoolSnapshotError("get_reserves_result_range_invalid")
    return reserve0, reserve1, timestamp_last


def _normalized_units(base_units: int, decimals: int) -> str:
    value = Decimal(base_units).scaleb(-decimals)
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _token(value: object, field: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != {
        "canonical_asset_id", "contract_address", "symbol"
    }:
        raise EvmV2PoolSnapshotError(f"{field}_schema_invalid")
    return {
        "canonical_asset_id": _identifier(
            value.get("canonical_asset_id"), f"{field}_canonical_asset_id"
        ),
        "contract_address": _address(
            value.get("contract_address"), f"{field}_contract_address"
        ),
        "symbol": _symbol(value.get("symbol"), f"{field}_symbol"),
    }


def _exchange(value: object, index: int) -> tuple[dict[str, Any], object, datetime]:
    if not isinstance(value, Mapping) or set(value) != {
        "duration_ms", "request", "request_started_at", "response",
        "response_received_at",
    }:
        raise EvmV2PoolSnapshotError(f"rpc_exchange_{index}_schema_invalid")
    started_text, started = _utc(
        value.get("request_started_at"), f"rpc_exchange_{index}_request_started_at"
    )
    received_text, received = _utc(
        value.get("response_received_at"),
        f"rpc_exchange_{index}_response_received_at",
    )
    duration = value.get("duration_ms")
    if (
        isinstance(duration, bool)
        or not isinstance(duration, int)
        or not 0 <= duration <= MAX_RPC_DURATION_MS
        or received < started
        or int((received - started).total_seconds() * 1000) < duration
    ):
        raise EvmV2PoolSnapshotError(f"rpc_exchange_{index}_timing_invalid")

    request = value.get("request")
    response = value.get("response")
    if not isinstance(request, Mapping) or set(request) != {
        "id", "jsonrpc", "method", "params"
    }:
        raise EvmV2PoolSnapshotError(f"rpc_exchange_{index}_request_invalid")
    request_id = request.get("id")
    if (
        request.get("jsonrpc") != "2.0"
        or isinstance(request_id, bool)
        or not isinstance(request_id, int)
        or not 1 <= request_id <= 10_000
        or not isinstance(request.get("method"), str)
        or not isinstance(request.get("params"), list)
    ):
        raise EvmV2PoolSnapshotError(f"rpc_exchange_{index}_request_invalid")
    if not isinstance(response, Mapping) or set(response) != {"id", "jsonrpc", "result"}:
        raise EvmV2PoolSnapshotError(f"rpc_exchange_{index}_response_invalid")
    if response.get("jsonrpc") != "2.0" or response.get("id") != request_id:
        raise EvmV2PoolSnapshotError(f"rpc_exchange_{index}_response_invalid")
    return (
        {
            "id": request_id,
            "jsonrpc": "2.0",
            "method": request["method"],
            "params": request["params"],
            "request_started_at": started_text,
            "response_received_at": received_text,
            "duration_ms": duration,
        },
        response.get("result"),
        received,
    )


def _require_request(
    request: Mapping[str, Any],
    *,
    method: str,
    params: Sequence[object],
    index: int,
) -> None:
    if request.get("method") != method or request.get("params") != list(params):
        raise EvmV2PoolSnapshotError(f"rpc_exchange_{index}_request_contract_invalid")


def _call_params(address: str, selector: str, block_number_hex: str) -> list[object]:
    return [{"to": address, "data": selector}, block_number_hex]


def _bundle_header(
    bundle: Mapping[str, object], expected_capture_mode: str | None
) -> dict[str, Any]:
    expected_keys = {
        "capture_mode", "chain_id", "dex_id", "network_name", "pool_address",
        "pool_contract_family", "provider_id", "research_only", "rpc_exchanges",
        "schema_id", "schema_version", "token0", "token1",
    }
    if set(bundle) != expected_keys:
        raise EvmV2PoolSnapshotError("capture_schema_invalid")
    capture_mode = bundle.get("capture_mode")
    if capture_mode not in CAPTURE_MODES or (
        expected_capture_mode is not None and capture_mode != expected_capture_mode
    ):
        raise EvmV2PoolSnapshotError("capture_mode_invalid")
    if (
        bundle.get("schema_id") != INPUT_SCHEMA_ID
        or bundle.get("schema_version") != 1
        or bundle.get("pool_contract_family") != "uniswap_v2_compatible"
        or bundle.get("research_only") is not True
    ):
        raise EvmV2PoolSnapshotError("capture_contract_invalid")

    provider_id = _identifier(bundle.get("provider_id"), "provider_id")
    network_name = _identifier(bundle.get("network_name"), "network_name")
    dex_id = _identifier(bundle.get("dex_id"), "dex_id")
    pool_address = _address(bundle.get("pool_address"), "pool_address")
    token0 = _token(bundle.get("token0"), "token0")
    token1 = _token(bundle.get("token1"), "token1")
    if token0["contract_address"] == token1["contract_address"]:
        raise EvmV2PoolSnapshotError("token_contracts_not_distinct")
    return {
        "capture_mode": capture_mode,
        "expected_chain_id": bundle.get("chain_id"),
        "provider_id": provider_id,
        "network_name": network_name,
        "dex_id": dex_id,
        "pool_address": pool_address,
        "token0": token0,
        "token1": token1,
    }


def _rpc_snapshot(bundle: Mapping[str, object], header: Mapping[str, Any]) -> dict[str, Any]:
    exchanges = bundle.get("rpc_exchanges")
    if not isinstance(exchanges, list) or len(exchanges) != 7:
        raise EvmV2PoolSnapshotError("rpc_exchange_count_invalid")
    parsed = [_exchange(value, index) for index, value in enumerate(exchanges, 1)]
    requests = [item[0] for item in parsed]
    results = [item[1] for item in parsed]
    received_times = [item[2] for item in parsed]
    request_ids = [request["id"] for request in requests]
    if len(set(request_ids)) != len(request_ids):
        raise EvmV2PoolSnapshotError("rpc_request_id_duplicate")
    if received_times != sorted(received_times):
        raise EvmV2PoolSnapshotError("rpc_exchange_order_invalid")

    _require_request(requests[0], method=ETH_CHAIN_ID, params=[], index=1)
    chain_number, _ = _quantity(results[0], "chain_id_result")
    chain_id = f"eip155:{chain_number}"
    if header["expected_chain_id"] != chain_id:
        raise EvmV2PoolSnapshotError("chain_id_mismatch")

    _require_request(
        requests[1], method=ETH_GET_BLOCK_BY_NUMBER, params=["finalized", False], index=2
    )
    block = results[1]
    if not isinstance(block, Mapping):
        raise EvmV2PoolSnapshotError("finalized_block_result_invalid")
    block_number, block_number_hex = _quantity(
        block.get("number"), "finalized_block_number"
    )
    block_timestamp, _ = _quantity(
        block.get("timestamp"), "finalized_block_timestamp"
    )
    block_hash = _data(block.get("hash"), "finalized_block_hash", byte_length=32)
    block_observed_at = datetime.fromtimestamp(
        block_timestamp, tz=timezone.utc
    ).isoformat().replace("+00:00", "Z")

    pool_address = header["pool_address"]
    token0 = header["token0"]
    token1 = header["token1"]
    expected_calls = (
        (pool_address, TOKEN0_SELECTOR),
        (pool_address, TOKEN1_SELECTOR),
        (pool_address, GET_RESERVES_SELECTOR),
        (token0["contract_address"], DECIMALS_SELECTOR),
        (token1["contract_address"], DECIMALS_SELECTOR),
    )
    for offset, (address, selector) in enumerate(expected_calls, 3):
        _require_request(
            requests[offset - 1],
            method=ETH_CALL,
            params=_call_params(address, selector, block_number_hex),
            index=offset,
        )

    if _decode_abi_address(results[2], "token0_result") != token0["contract_address"]:
        raise EvmV2PoolSnapshotError("token0_contract_mismatch")
    if _decode_abi_address(results[3], "token1_result") != token1["contract_address"]:
        raise EvmV2PoolSnapshotError("token1_contract_mismatch")
    reserve0, reserve1, reserve_timestamp = _decode_reserves(results[4])
    decimals0 = _decode_abi_uint(results[5], "token0_decimals_result", bits=8)
    decimals1 = _decode_abi_uint(results[6], "token1_decimals_result", bits=8)
    if decimals0 > 36 or decimals1 > 36:
        raise EvmV2PoolSnapshotError("token_decimals_unsupported")
    return {
        "chain_id": chain_id,
        "block_number": block_number,
        "block_number_hex": block_number_hex,
        "block_hash": block_hash,
        "block_timestamp": block_timestamp,
        "block_observed_at": block_observed_at,
        "acquired_at": requests[-1]["response_received_at"],
        "reserve0": reserve0,
        "reserve1": reserve1,
        "reserve_timestamp": reserve_timestamp,
        "decimals0": decimals0,
        "decimals1": decimals1,
    }


def _snapshot_projection(
    raw: bytes, header: Mapping[str, Any], rpc: Mapping[str, Any]
) -> dict[str, Any]:
    capture_mode = header["capture_mode"]
    provider_id = header["provider_id"]
    network_name = header["network_name"]
    dex_id = header["dex_id"]
    pool_address = header["pool_address"]
    chain_id = rpc["chain_id"]
    block_number = rpc["block_number"]
    block_observed_at = rpc["block_observed_at"]
    acquired_at = rpc["acquired_at"]
    lineage = f"sha256:{_sha256(raw)}"
    input_quality_eligible = capture_mode == CAPTURE_MODE_OPERATOR_IMPORT
    token0_out = {
        **header["token0"],
        "decimals": rpc["decimals0"],
        "reserve_base_units": str(rpc["reserve0"]),
        "reserve_token_units": _normalized_units(
            rpc["reserve0"], rpc["decimals0"]
        ),
    }
    token1_out = {
        **header["token1"],
        "decimals": rpc["decimals1"],
        "reserve_base_units": str(rpc["reserve1"]),
        "reserve_token_units": _normalized_units(
            rpc["reserve1"], rpc["decimals1"]
        ),
    }
    context_rows = []
    for token in (token0_out, token1_out):
        context_rows.append(
            {
                "chain_id": chain_id,
                "canonical_asset_id": token["canonical_asset_id"],
                "metric_name": "dex_pool_reserve_token_units",
                "metric_value": token["reserve_token_units"],
                "metric_unit": token["symbol"],
                "block_number_or_time": str(block_number),
                "provider_observed_at": block_observed_at,
                "acquired_at": acquired_at,
                "source_lineage_id": lineage,
                "pool_address": pool_address,
                "research_only": True,
                "directional_authority": False,
            }
        )

    return {
        "schema_id": OUTPUT_SCHEMA_ID,
        "schema_version": 1,
        "contract_version": CONTRACT_VERSION,
        "row_type": "decision_radar_dex_pool_point_in_time",
        "capture_mode": capture_mode,
        "provider_id": provider_id,
        "source_authority": (
            "operator_supplied_direct_evm_json_rpc"
            if capture_mode == CAPTURE_MODE_OPERATOR_IMPORT
            else "fixture_evm_json_rpc"
        ),
        "source_lineage_id": lineage,
        "raw_source_sha256": _sha256(raw),
        "raw_source_size_bytes": len(raw),
        "network_name": network_name,
        "chain_id": chain_id,
        "dex_id": dex_id,
        "venue_id": f"{dex_id}:{chain_id}:{pool_address}",
        "pool_contract_family": "uniswap_v2_compatible",
        "pool_address": pool_address,
        "block_number": block_number,
        "block_number_hex": rpc["block_number_hex"],
        "block_hash": rpc["block_hash"],
        "block_timestamp": rpc["block_timestamp"],
        "provider_observed_at": block_observed_at,
        "acquired_at": acquired_at,
        "finality_at_acquisition": "finalized",
        "pair_reserve_timestamp_seconds_mod_2_32": rpc["reserve_timestamp"],
        "token0": token0_out,
        "token1": token1_out,
        "onchain_context_rows": context_rows,
        "context_only": True,
        "directional_authority": False,
        "usd_liquidity_available": False,
        "usd_liquidity_estimated": False,
        "evidence_authority_eligible": False,
        "protocol_v2_input_quality_eligible": input_quality_eligible,
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        "campaign_attached": False,
        "research_only": True,
        "no_send": True,
        "provider_calls": 0,
        "credentials_read": 0,
        "private_data_read": 0,
        "orders": 0,
        "trades": 0,
        "paper_trades": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
    }


def normalize_evm_v2_pool_snapshot(
    raw: bytes,
    *,
    expected_capture_mode: str | None = None,
) -> dict[str, Any]:
    """Validate exact RPC exchanges and return one context-only projection."""

    if not raw or len(raw) > MAX_CAPTURE_BYTES:
        raise EvmV2PoolSnapshotError("capture_size_invalid")
    try:
        bundle = parse_json_object_bytes(raw)
    except MarketNoSendError as exc:
        raise EvmV2PoolSnapshotError("capture_json_invalid") from exc
    header = _bundle_header(bundle, expected_capture_mode)
    return _snapshot_projection(raw, header, _rpc_snapshot(bundle, header))


def read_capture_bytes(path: str | Path) -> bytes:
    """Read one explicit regular capture file without following its leaf."""

    capture_path = Path(path).expanduser()
    descriptor: int | None = None
    try:
        descriptor = os.open(
            capture_path,
            os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
        )
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise EvmV2PoolSnapshotError("capture_file_invalid")
        if not 0 < opened.st_size <= MAX_CAPTURE_BYTES:
            raise EvmV2PoolSnapshotError("capture_size_invalid")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            raw = handle.read(MAX_CAPTURE_BYTES + 1)
            completed = os.fstat(handle.fileno())
        if (
            len(raw) > MAX_CAPTURE_BYTES
            or len(raw) != completed.st_size
            or (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
            != (completed.st_dev, completed.st_ino, completed.st_size, completed.st_mtime_ns)
        ):
            raise EvmV2PoolSnapshotError("capture_file_changed_during_read")
        return raw
    except EvmV2PoolSnapshotError:
        raise
    except OSError as exc:
        raise EvmV2PoolSnapshotError("capture_file_unreadable") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize one exact, read-only EVM v2-compatible pool bundle."
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--capture-mode", choices=sorted(CAPTURE_MODES), required=True)
    args = parser.parse_args(argv)
    projection = normalize_evm_v2_pool_snapshot(
        read_capture_bytes(args.input), expected_capture_mode=args.capture_mode
    )
    print(json.dumps(projection, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by Make smoke
    raise SystemExit(main())


__all__ = (
    "CAPTURE_MODE_FIXTURE",
    "CAPTURE_MODE_OPERATOR_IMPORT",
    "CONTRACT_VERSION",
    "EvmV2PoolSnapshotError",
    "normalize_evm_v2_pool_snapshot",
    "read_capture_bytes",
)
