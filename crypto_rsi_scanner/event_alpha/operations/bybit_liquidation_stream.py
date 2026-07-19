"""Offline contract for Bybit public all-liquidation WebSocket messages.

Bybit exposes venue-native liquidation events for linear perpetuals through the
public ``allLiquidation.{symbol}`` WebSocket topic rather than a V5 REST market
endpoint.  This module normalizes already-supplied exact message bytes for one
execution-quality instrument.  It does not open a socket, read authorization,
persist artifacts, choose a route, send, trade, or place an order.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .bybit_execution_quality import (
    BYBIT_CATEGORY,
    CONTRACT_TYPE,
    EXECUTION_MODE,
    INSTRUMENT_STATUS,
    QUOTE_ASSET,
    VENUE_ID,
    BybitEligibleInstrument,
    select_bybit_usdt_perpetual_instruments,
)


CONTRACT_VERSION = "crypto_radar_bybit_liquidation_stream_v1"
EVENT_SCHEMA_VERSION = "crypto_radar.bybit_liquidation_event.v1"
PUBLIC_WEBSOCKET_URL = "wss://stream.bybit.com/v5/public/linear"
OFFICIAL_ALL_LIQUIDATION_DOC = (
    "https://bybit-exchange.github.io/docs/v5/websocket/public/all-liquidation"
)
TOPIC_PREFIX = "allLiquidation."
MESSAGE_TYPE = "snapshot"
PUSH_FREQUENCY_MILLISECONDS = 500
DEFAULT_FRESHNESS_SECONDS = 15.0
MAX_MESSAGE_BYTES = 1_000_000
MAX_EVENTS_PER_MESSAGE = 1_000
_LINEAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class _BybitLiquidationStreamError(ValueError):
    """Raised when exact public liquidation bytes violate the closed contract."""


@dataclass(frozen=True)
class BybitLiquidationEvent:
    """One venue-native liquidation event with explicit side and USDT units."""

    schema_version: str
    contract_version: str
    venue_id: str
    execution_mode: str
    category: str
    instrument_id: str
    canonical_asset_id: str
    base_asset: str
    quote_asset: str
    settle_asset: str
    contract_type: str
    instrument_status: str
    topic: str
    message_type: str
    message_emitted_at: str
    liquidation_observed_at: str
    received_at: str
    message_age_seconds: float
    event_age_seconds: float
    freshness_status: str
    provider_event_index: int
    provider_side: str
    liquidated_position_side: str
    size_base_asset: float
    bankruptcy_price_usdt: float
    liquidation_notional_usdt: float
    source_message_sha256: str
    source_lineage_id: str
    event_id: str
    public_websocket_url: str
    source_contract_url: str
    websocket_authentication_required: bool
    credentials_required: bool
    future_data_used: bool
    context_only: bool
    directional_authority: bool
    decision_policy_applied: bool
    protocol_v2_annex_bound: bool
    protocol_v2_evidence_eligible: bool
    research_only: bool = True

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["units"] = {
            "size": self.base_asset,
            "bankruptcy_price": "USDT_per_base_asset",
            "liquidation_notional": "USDT",
            "timestamps": "UTC",
        }
        value["side_semantics"] = (
            "Bybit provider_side Buy means a long position was liquidated; "
            "Sell means a short position was liquidated"
        )
        return value


BybitLiquidationStreamError = _BybitLiquidationStreamError


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise BybitLiquidationStreamError("source_message_duplicate_json_key")
        value[key] = item
    return value


def _reject_constant(_value: str) -> None:
    raise BybitLiquidationStreamError("source_message_non_finite_json")


def _decode_message(payload: bytes) -> Mapping[str, Any]:
    if not isinstance(payload, bytes) or not payload or len(payload) > MAX_MESSAGE_BYTES:
        raise BybitLiquidationStreamError("source_message_bytes_invalid")
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BybitLiquidationStreamError("source_message_utf8_invalid") from exc
    try:
        value = json.loads(
            decoded,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except BybitLiquidationStreamError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise BybitLiquidationStreamError("source_message_json_invalid") from exc
    if not isinstance(value, Mapping):
        raise BybitLiquidationStreamError("source_message_object_required")
    return value


def _aware_utc(value: datetime | str, field: str) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise BybitLiquidationStreamError(f"{field}_invalid") from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise BybitLiquidationStreamError(f"{field}_invalid")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BybitLiquidationStreamError(f"{field}_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _milliseconds(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise BybitLiquidationStreamError(f"{field}_invalid")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise BybitLiquidationStreamError(f"{field}_invalid") from exc
    if parsed <= 0 or (not isinstance(value, int) and str(value).strip() != str(parsed)):
        raise BybitLiquidationStreamError(f"{field}_invalid")
    return parsed


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool):
        raise BybitLiquidationStreamError(f"{field}_invalid")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BybitLiquidationStreamError(f"{field}_invalid") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise BybitLiquidationStreamError(f"{field}_invalid")
    return parsed


def _finite_float(value: Decimal, field: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise BybitLiquidationStreamError(f"{field}_invalid")
    return parsed


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _at(milliseconds: int) -> datetime:
    try:
        return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise BybitLiquidationStreamError("provider_timestamp_invalid") from exc


def _validate_instrument(instrument: BybitEligibleInstrument) -> None:
    if (
        instrument.instrument_id != f"{instrument.base_asset}{QUOTE_ASSET}"
        or instrument.radar_symbol != instrument.base_asset
        or instrument.quote_asset != QUOTE_ASSET
        or instrument.settle_asset != QUOTE_ASSET
        or instrument.contract_type != CONTRACT_TYPE
        or instrument.status != INSTRUMENT_STATUS
    ):
        raise BybitLiquidationStreamError("eligible_instrument_contract_invalid")


def _event_id(
    *, source_sha256: str, lineage_id: str, provider_event_index: int
) -> str:
    identity = f"{source_sha256}|{lineage_id}|{provider_event_index}".encode("utf-8")
    return f"bybit_liquidation:{hashlib.sha256(identity).hexdigest()[:24]}"


def normalize_bybit_liquidation_message(
    payload: bytes,
    *,
    instrument: BybitEligibleInstrument,
    received_at: datetime | str,
    source_lineage_id: str,
    freshness_seconds: float = DEFAULT_FRESHNESS_SECONDS,
) -> tuple[BybitLiquidationEvent, ...]:
    """Normalize one exact public message without opening a provider boundary."""

    _validate_instrument(instrument)
    received = _aware_utc(received_at, "received_at")
    if not isinstance(freshness_seconds, (int, float)) or isinstance(
        freshness_seconds, bool
    ):
        raise BybitLiquidationStreamError("freshness_seconds_invalid")
    if not (0 < float(freshness_seconds) < float("inf")):
        raise BybitLiquidationStreamError("freshness_seconds_invalid")
    if not isinstance(source_lineage_id, str) or not _LINEAGE_RE.fullmatch(
        source_lineage_id
    ):
        raise BybitLiquidationStreamError("source_lineage_id_invalid")

    message = _decode_message(payload)
    if set(message) != {"topic", "type", "ts", "data"}:
        raise BybitLiquidationStreamError("source_message_schema_mismatch")
    topic = f"{TOPIC_PREFIX}{instrument.instrument_id}"
    if message.get("topic") != topic:
        raise BybitLiquidationStreamError("source_message_topic_mismatch")
    if message.get("type") != MESSAGE_TYPE:
        raise BybitLiquidationStreamError("source_message_type_mismatch")
    message_at = _at(_milliseconds(message.get("ts"), "message_timestamp"))
    if message_at > received:
        raise BybitLiquidationStreamError("message_received_before_emission")
    rows = message.get("data")
    if (
        not isinstance(rows, list)
        or not rows
        or len(rows) > MAX_EVENTS_PER_MESSAGE
    ):
        raise BybitLiquidationStreamError("source_message_events_invalid")

    source_sha256 = hashlib.sha256(payload).hexdigest()
    message_age = (received - message_at).total_seconds()
    events: list[BybitLiquidationEvent] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or set(row) != {"T", "s", "S", "v", "p"}:
            raise BybitLiquidationStreamError("liquidation_event_schema_mismatch")
        if row.get("s") != instrument.instrument_id:
            raise BybitLiquidationStreamError("liquidation_event_identity_mismatch")
        provider_side = row.get("S")
        if provider_side not in {"Buy", "Sell"}:
            raise BybitLiquidationStreamError("liquidation_event_side_invalid")
        event_at = _at(_milliseconds(row.get("T"), "liquidation_timestamp"))
        if event_at > message_at:
            raise BybitLiquidationStreamError("liquidation_event_after_message")
        size = _decimal(row.get("v"), "liquidation_size")
        price = _decimal(row.get("p"), "bankruptcy_price")
        size_float = _finite_float(size, "liquidation_size")
        price_float = _finite_float(price, "bankruptcy_price")
        notional_float = _finite_float(
            size * price, "liquidation_notional_usdt"
        )
        event_age = (received - event_at).total_seconds()
        events.append(
            BybitLiquidationEvent(
                schema_version=EVENT_SCHEMA_VERSION,
                contract_version=CONTRACT_VERSION,
                venue_id=VENUE_ID,
                execution_mode=EXECUTION_MODE,
                category=BYBIT_CATEGORY,
                instrument_id=instrument.instrument_id,
                canonical_asset_id=instrument.canonical_asset_id,
                base_asset=instrument.base_asset,
                quote_asset=instrument.quote_asset,
                settle_asset=instrument.settle_asset,
                contract_type=instrument.contract_type,
                instrument_status=instrument.status,
                topic=topic,
                message_type=MESSAGE_TYPE,
                message_emitted_at=_iso(message_at),
                liquidation_observed_at=_iso(event_at),
                received_at=_iso(received),
                message_age_seconds=round(message_age, 6),
                event_age_seconds=round(event_age, 6),
                freshness_status=(
                    "fresh" if event_age <= float(freshness_seconds) else "stale"
                ),
                provider_event_index=index,
                provider_side=provider_side,
                liquidated_position_side=(
                    "long" if provider_side == "Buy" else "short"
                ),
                size_base_asset=size_float,
                bankruptcy_price_usdt=price_float,
                liquidation_notional_usdt=notional_float,
                source_message_sha256=source_sha256,
                source_lineage_id=source_lineage_id,
                event_id=_event_id(
                    source_sha256=source_sha256,
                    lineage_id=source_lineage_id,
                    provider_event_index=index,
                ),
                public_websocket_url=PUBLIC_WEBSOCKET_URL,
                source_contract_url=OFFICIAL_ALL_LIQUIDATION_DOC,
                websocket_authentication_required=False,
                credentials_required=False,
                future_data_used=False,
                context_only=True,
                directional_authority=False,
                decision_policy_applied=False,
                protocol_v2_annex_bound=False,
                protocol_v2_evidence_eligible=False,
            )
        )
    return tuple(events)


def run_fixture_smoke(
    fixture_dir: str | Path,
    *,
    execution_fixture_dir: str | Path,
) -> dict[str, object]:
    """Exercise the normalizer from checked-in bytes; no network or writes."""

    fixture_root = Path(fixture_dir)
    execution_root = Path(execution_fixture_dir)
    radar_assets = json.loads((execution_root / "radar_assets.json").read_text())
    catalog = json.loads((execution_root / "instruments_info.json").read_text())
    instrument = next(
        row
        for row in select_bybit_usdt_perpetual_instruments(radar_assets, catalog)
        if row.instrument_id == "BTCUSDT"
    )
    events = normalize_bybit_liquidation_message(
        (fixture_root / "all_liquidation_btcusdt.json").read_bytes(),
        instrument=instrument,
        received_at="2026-07-18T07:44:00.250Z",
        source_lineage_id="fixture.bybit.all_liquidation.btcusdt",
    )
    return {
        "status": "ok",
        "contract_version": CONTRACT_VERSION,
        "event_count": len(events),
        "events": [event.to_dict() for event in events],
        "provider_calls": 0,
        "websocket_connections": 0,
        "file_writes": 0,
        "credentials_read": False,
        "orders_available": False,
        "research_only": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize checked-in Bybit public liquidation bytes offline."
    )
    parser.add_argument("--fixture-dir", required=True)
    parser.add_argument("--execution-fixture-dir", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    print(
        json.dumps(
            run_fixture_smoke(
                args.fixture_dir,
                execution_fixture_dir=args.execution_fixture_dir,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


__all__ = (
    "BybitLiquidationEvent",
    "BybitLiquidationStreamError",
    "CONTRACT_VERSION",
    "EVENT_SCHEMA_VERSION",
    "OFFICIAL_ALL_LIQUIDATION_DOC",
    "PUBLIC_WEBSOCKET_URL",
    "normalize_bybit_liquidation_message",
    "run_fixture_smoke",
)


if __name__ == "__main__":
    raise SystemExit(main())
