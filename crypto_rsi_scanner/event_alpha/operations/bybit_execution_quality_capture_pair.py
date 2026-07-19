"""Read-only round-trip projection from two exact immutable Bybit captures."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .bybit_execution_quality import (
    BybitEligibleInstrument,
    BybitExecutionQualityError,
    BybitTargetNotionalRoundTrip,
    model_bybit_target_notional_visible_book_round_trip,
    select_bybit_usdt_perpetual_instruments,
)
from .bybit_execution_quality_capture import (
    _validated_bybit_execution_quality_loaded_bundle,
)
from .bybit_execution_quality_capture_errors import (
    BybitExecutionQualityCaptureError,
)
from .bybit_execution_quality_capture_models import BybitCapturedJSONResponse
from .bybit_execution_quality_capture_validation import (
    CaptureBundle,
    read_capture_bundle_pair,
)


SCHEMA_VERSION = "crypto_radar.bybit_capture_pair_target_notional_round_trip.v1"
_INSTRUMENT_RE = re.compile(r"^[A-Z0-9]{4,32}$")


class BybitExecutionQualityCapturePairError(ValueError):
    """Raised when two immutable captures cannot form one causal round trip."""


@dataclass(frozen=True)
class _CaptureLegReference:
    role: str
    artifact_namespace: str
    capture_id: str
    started_at: str
    completed_at: str
    source_authority: dict[str, object]
    instrument_id: str
    catalog_response_received_at: str
    catalog_response_sha256: str
    catalog_response_size_bytes: int
    orderbook_response_received_at: str
    orderbook_response_sha256: str
    orderbook_response_size_bytes: int
    orderbook_request_lineage_id: str
    protocol_v2_input_quality_eligible: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _CaptureLegMaterial:
    reference: _CaptureLegReference
    instrument: BybitEligibleInstrument
    catalog_response: BybitCapturedJSONResponse
    orderbook_response: BybitCapturedJSONResponse


@dataclass(frozen=True)
class _BybitCapturePairTargetNotionalRoundTrip:
    schema_version: str
    venue_id: str
    execution_mode: str
    instrument_id: str
    position_side: str
    entry_capture: _CaptureLegReference
    exit_capture: _CaptureLegReference
    target_notional_round_trip: BybitTargetNotionalRoundTrip
    captures_distinct: bool
    capture_windows_ordered_non_overlapping: bool
    exact_raw_responses_rederived: bool
    exact_namespaces_required: bool
    latest_pointer_used: bool
    both_capture_sets_fresh_at_completion: bool
    capture_evidence_authority_eligible: bool
    protocol_v2_annex_bound: bool
    protocol_v2_evidence_eligible: bool
    campaign_attached: bool
    provider_calls: int
    credentials_read: bool
    private_data_read: bool
    writes_performed: bool
    no_send: bool
    orders: int
    trades: int
    paper_trades: int
    normal_rsi_writes: int
    event_alpha_triggered_fade: int
    research_only: bool

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["entry_capture"] = self.entry_capture.to_dict()
        value["exit_capture"] = self.exit_capture.to_dict()
        value["target_notional_round_trip"] = (
            self.target_notional_round_trip.to_dict()
        )
        return value


BybitCapturePairTargetNotionalRoundTrip = (
    _BybitCapturePairTargetNotionalRoundTrip
)


def _utc(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise BybitExecutionQualityCapturePairError(f"{field}_missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BybitExecutionQualityCapturePairError(f"{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BybitExecutionQualityCapturePairError(f"{field}_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise BybitExecutionQualityCapturePairError(f"{field}_invalid")
    return value


def _list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise BybitExecutionQualityCapturePairError(f"{field}_invalid")
    return value


def _response_row(
    value: object,
    *,
    field: str,
) -> Mapping[str, object]:
    row = _mapping(value, field)
    if (
        not isinstance(row.get("sha256"), str)
        or len(row["sha256"]) != 64
        or type(row.get("size_bytes")) is not int
        or row["size_bytes"] < 1
    ):
        raise BybitExecutionQualityCapturePairError(f"{field}_invalid")
    return row


def _capture_leg_material(
    *,
    bundle: CaptureBundle,
    namespace: str,
    instrument_id: str,
    role: str,
) -> _CaptureLegMaterial:
    validated, projections = _validated_bybit_execution_quality_loaded_bundle(
        bundle=bundle,
        namespace=namespace,
    )
    if validated.get("protocol_v2_input_quality_eligible") is not True:
        raise BybitExecutionQualityCapturePairError(
            f"{role}_capture_not_input_quality_eligible"
        )
    summary = _mapping(projections.get("summary"), f"{role}_summary")
    responses = _list(projections.get("responses"), f"{role}_responses")
    request_rows = _list(
        projections.get("request_rows"),
        f"{role}_request_rows",
    )
    if (
        len(responses) < 2
        or len(request_rows) != len(responses)
        or not all(isinstance(row, BybitCapturedJSONResponse) for row in responses)
    ):
        raise BybitExecutionQualityCapturePairError(
            f"{role}_capture_responses_invalid"
        )
    catalog_response = responses[0]
    if not isinstance(catalog_response, BybitCapturedJSONResponse):
        raise BybitExecutionQualityCapturePairError(
            f"{role}_catalog_response_invalid"
        )
    provider_query_assets = _list(
        summary.get("provider_query_assets"),
        f"{role}_provider_query_assets",
    )
    try:
        instruments = select_bybit_usdt_perpetual_instruments(
            provider_query_assets,  # type: ignore[arg-type]
            catalog_response.payload(),
        )
    except BybitExecutionQualityError as exc:
        raise BybitExecutionQualityCapturePairError(
            f"{role}_instrument_catalog_invalid"
        ) from exc
    matches = [
        (index, instrument)
        for index, instrument in enumerate(instruments)
        if instrument.instrument_id == instrument_id
    ]
    if len(matches) != 1:
        raise BybitExecutionQualityCapturePairError(
            f"{role}_instrument_not_unique_or_absent"
        )
    instrument_index, instrument = matches[0]
    response_index = instrument_index + 1
    if response_index >= len(responses):
        raise BybitExecutionQualityCapturePairError(
            f"{role}_orderbook_response_missing"
        )
    orderbook_response = responses[response_index]
    if not isinstance(orderbook_response, BybitCapturedJSONResponse):
        raise BybitExecutionQualityCapturePairError(
            f"{role}_orderbook_response_invalid"
        )
    snapshots = _list(
        summary.get("execution_quality_snapshots"),
        f"{role}_snapshots",
    )
    if instrument_index >= len(snapshots):
        raise BybitExecutionQualityCapturePairError(f"{role}_snapshot_missing")
    snapshot = _mapping(snapshots[instrument_index], f"{role}_snapshot")
    if (
        snapshot.get("instrument_id") != instrument_id
        or snapshot.get("acquired_at") != orderbook_response.response_received_at
        or not isinstance(snapshot.get("request_lineage_id"), str)
        or not snapshot["request_lineage_id"]
    ):
        raise BybitExecutionQualityCapturePairError(
            f"{role}_snapshot_identity_invalid"
        )
    catalog_row = _response_row(
        request_rows[0],
        field=f"{role}_catalog_request_row",
    )
    orderbook_row = _response_row(
        request_rows[response_index],
        field=f"{role}_orderbook_request_row",
    )
    capture_id = str(validated.get("capture_id") or "")
    source_authority = _mapping(
        validated.get("source_authority"),
        f"{role}_source_authority",
    )
    reference = _CaptureLegReference(
        role=role,
        artifact_namespace=namespace,
        capture_id=capture_id,
        started_at=str(summary.get("started_at") or ""),
        completed_at=str(summary.get("completed_at") or ""),
        source_authority=dict(source_authority),
        instrument_id=instrument_id,
        catalog_response_received_at=catalog_response.response_received_at,
        catalog_response_sha256=str(catalog_row["sha256"]),
        catalog_response_size_bytes=int(catalog_row["size_bytes"]),
        orderbook_response_received_at=orderbook_response.response_received_at,
        orderbook_response_sha256=str(orderbook_row["sha256"]),
        orderbook_response_size_bytes=int(orderbook_row["size_bytes"]),
        orderbook_request_lineage_id=str(snapshot["request_lineage_id"]),
        protocol_v2_input_quality_eligible=True,
    )
    _utc(reference.started_at, f"{role}_started_at")
    _utc(reference.completed_at, f"{role}_completed_at")
    return _CaptureLegMaterial(
        reference=reference,
        instrument=instrument,
        catalog_response=catalog_response,
        orderbook_response=orderbook_response,
    )


def model_bybit_capture_pair_target_notional_round_trip(
    artifact_base_dir: str | Path,
    *,
    entry_namespace: str,
    exit_namespace: str,
    instrument_id: str,
    position_side: str,
    target_entry_mid_notional_usdt: object,
) -> BybitCapturePairTargetNotionalRoundTrip:
    """Model one read-only round trip from two exact strict-clean captures."""

    if entry_namespace == exit_namespace:
        raise BybitExecutionQualityCapturePairError("capture_namespaces_not_distinct")
    if not _INSTRUMENT_RE.fullmatch(instrument_id):
        raise BybitExecutionQualityCapturePairError("instrument_id_invalid")
    if position_side not in {"long", "short"}:
        raise BybitExecutionQualityCapturePairError("position_side_invalid")
    entry_bundle, exit_bundle = read_capture_bundle_pair(
        artifact_base_dir,
        entry_namespace=entry_namespace,
        exit_namespace=exit_namespace,
    )
    entry = _capture_leg_material(
        bundle=entry_bundle,
        namespace=entry_namespace,
        instrument_id=instrument_id,
        role="entry",
    )
    exit_leg = _capture_leg_material(
        bundle=exit_bundle,
        namespace=exit_namespace,
        instrument_id=instrument_id,
        role="exit",
    )
    if entry.reference.capture_id == exit_leg.reference.capture_id:
        raise BybitExecutionQualityCapturePairError("capture_ids_not_distinct")
    if _utc(entry.reference.completed_at, "entry_completed_at") >= _utc(
        exit_leg.reference.started_at,
        "exit_started_at",
    ):
        raise BybitExecutionQualityCapturePairError(
            "capture_windows_not_ordered_non_overlapping"
        )
    try:
        round_trip = model_bybit_target_notional_visible_book_round_trip(
            entry.orderbook_response.payload(),
            exit_leg.orderbook_response.payload(),
            instrument=entry.instrument,
            exit_instrument=exit_leg.instrument,
            position_side=position_side,
            target_entry_mid_notional_usdt=target_entry_mid_notional_usdt,
            entry_acquired_at=entry.orderbook_response.response_received_at,
            exit_acquired_at=exit_leg.orderbook_response.response_received_at,
            entry_request_lineage_id=(
                entry.reference.orderbook_request_lineage_id
            ),
            exit_request_lineage_id=(
                exit_leg.reference.orderbook_request_lineage_id
            ),
            entry_instrument_constraints_observed_at=(
                entry.reference.catalog_response_received_at
            ),
            entry_instrument_constraints_lineage_id=(
                f"capture:{entry.reference.capture_id}:catalog"
            ),
            exit_instrument_constraints_observed_at=(
                exit_leg.reference.catalog_response_received_at
            ),
            exit_instrument_constraints_lineage_id=(
                f"capture:{exit_leg.reference.capture_id}:catalog"
            ),
        )
    except BybitExecutionQualityError as exc:
        raise BybitExecutionQualityCapturePairError(
            f"round_trip_invalid:{exc}"
        ) from exc
    return BybitCapturePairTargetNotionalRoundTrip(
        schema_version=SCHEMA_VERSION,
        venue_id="bybit",
        execution_mode="perpetual",
        instrument_id=instrument_id,
        position_side=position_side,
        entry_capture=entry.reference,
        exit_capture=exit_leg.reference,
        target_notional_round_trip=round_trip,
        captures_distinct=True,
        capture_windows_ordered_non_overlapping=True,
        exact_raw_responses_rederived=True,
        exact_namespaces_required=True,
        latest_pointer_used=False,
        both_capture_sets_fresh_at_completion=True,
        capture_evidence_authority_eligible=True,
        protocol_v2_annex_bound=False,
        protocol_v2_evidence_eligible=False,
        campaign_attached=False,
        provider_calls=0,
        credentials_read=False,
        private_data_read=False,
        writes_performed=False,
        no_send=True,
        orders=0,
        trades=0,
        paper_trades=0,
        normal_rsi_writes=0,
        event_alpha_triggered_fade=0,
        research_only=True,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Model one read-only round trip from two exact Bybit captures."
    )
    parser.add_argument("--artifact-base", default="event_fade_cache")
    parser.add_argument("--entry-namespace", required=True)
    parser.add_argument("--exit-namespace", required=True)
    parser.add_argument("--instrument-id", required=True)
    parser.add_argument("--position-side", choices=("long", "short"), required=True)
    parser.add_argument("--target-entry-mid-notional-usdt", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = model_bybit_capture_pair_target_notional_round_trip(
            args.artifact_base,
            entry_namespace=args.entry_namespace,
            exit_namespace=args.exit_namespace,
            instrument_id=args.instrument_id,
            position_side=args.position_side,
            target_entry_mid_notional_usdt=(
                args.target_entry_mid_notional_usdt
            ),
        )
    except (
        BybitExecutionQualityCaptureError,
        BybitExecutionQualityCapturePairError,
    ) as exc:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "status": "blocked",
                    "reason": str(exc),
                    "provider_calls": 0,
                    "writes_performed": False,
                    "research_only": True,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "SCHEMA_VERSION",
    "BybitCapturePairTargetNotionalRoundTrip",
    "BybitExecutionQualityCapturePairError",
    "main",
    "model_bybit_capture_pair_target_notional_round_trip",
)
