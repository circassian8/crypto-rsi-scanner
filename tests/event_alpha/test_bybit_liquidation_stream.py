"""Offline Bybit all-liquidation message-contract regressions."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import socket
import subprocess

import pytest

from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality import (
    select_bybit_usdt_perpetual_instruments,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_liquidation_stream import (
    BybitLiquidationStreamError,
    normalize_bybit_liquidation_message,
    run_fixture_smoke,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "fixtures/bybit_liquidation_stream"
QUALITY_DIR = REPO_ROOT / "fixtures/bybit_execution_quality"


def _json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _instrument() -> object:
    instruments = select_bybit_usdt_perpetual_instruments(
        _json(QUALITY_DIR / "radar_assets.json"),
        _json(QUALITY_DIR / "instruments_info.json"),
    )
    return next(row for row in instruments if row.instrument_id == "BTCUSDT")


def _bytes() -> bytes:
    return (FIXTURE_DIR / "all_liquidation_btcusdt.json").read_bytes()


def _normalize(payload: bytes | None = None, **overrides: object) -> tuple[object, ...]:
    values = {
        "instrument": _instrument(),
        "received_at": "2026-07-18T07:44:00.250Z",
        "source_lineage_id": "fixture.bybit.all_liquidation.btcusdt",
    }
    values.update(overrides)
    return normalize_bybit_liquidation_message(payload or _bytes(), **values)


def _changed(change: object) -> bytes:
    payload = _json(FIXTURE_DIR / "all_liquidation_btcusdt.json")
    change(payload)
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def test_exact_message_preserves_identity_sides_clocks_units_and_source_bytes() -> None:
    events = [event.to_dict() for event in _normalize()]

    assert len(events) == 2
    assert {event["instrument_id"] for event in events} == {"BTCUSDT"}
    assert {event["canonical_asset_id"] for event in events} == {"bitcoin"}
    assert {event["contract_type"] for event in events} == {"LinearPerpetual"}
    assert [event["provider_side"] for event in events] == ["Buy", "Sell"]
    assert [event["liquidated_position_side"] for event in events] == [
        "long",
        "short",
    ]
    assert [event["liquidation_notional_usdt"] for event in events] == [
        60_000.0,
        29_975.0,
    ]
    assert events[0]["units"] == {
        "size": "BTC",
        "bankruptcy_price": "USDT_per_base_asset",
        "liquidation_notional": "USDT",
        "timestamps": "UTC",
    }
    assert events[0]["message_emitted_at"] == "2026-07-18T07:44:00Z"
    assert events[0]["liquidation_observed_at"] == (
        "2026-07-18T07:43:59.500000Z"
    )
    assert events[0]["message_age_seconds"] == 0.25
    assert events[0]["event_age_seconds"] == 0.75
    assert events[0]["freshness_status"] == "fresh"
    assert events[0]["source_message_sha256"] == hashlib.sha256(_bytes()).hexdigest()
    assert events[0]["source_lineage_id"] == (
        "fixture.bybit.all_liquidation.btcusdt"
    )
    assert events[0]["event_id"] != events[1]["event_id"]
    assert all(event["context_only"] is True for event in events)
    assert all(event["directional_authority"] is False for event in events)
    assert all(event["decision_policy_applied"] is False for event in events)
    assert all(event["protocol_v2_annex_bound"] is False for event in events)
    assert all(event["protocol_v2_evidence_eligible"] is False for event in events)
    assert all(event["research_only"] is True for event in events)
    assert all("directional_bias" not in event for event in events)
    assert all("radar_route" not in event for event in events)


def test_event_identity_is_deterministic_and_duplicate_values_remain_distinct() -> None:
    first = [event.to_dict() for event in _normalize()]
    second = [event.to_dict() for event in _normalize()]
    payload = _json(FIXTURE_DIR / "all_liquidation_btcusdt.json")
    payload["data"][1] = deepcopy(payload["data"][0])
    duplicates = [
        event.to_dict()
        for event in _normalize(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )
    ]

    assert first == second
    assert duplicates[0]["event_id"] != duplicates[1]["event_id"]
    assert duplicates[0]["provider_event_index"] == 0
    assert duplicates[1]["provider_event_index"] == 1


def test_old_event_remains_stale_without_weakening_freshness() -> None:
    events = _normalize(received_at="2026-07-18T07:45:00Z")

    assert [event.freshness_status for event in events] == ["stale", "stale"]
    assert events[0].event_age_seconds == 60.5


@pytest.mark.parametrize(
    ("mutation", "error"),
    (
        (lambda row: row.update(extra="x"), "source_message_schema_mismatch"),
        (lambda row: row.update(topic="allLiquidation.ETHUSDT"), "topic_mismatch"),
        (lambda row: row.update(type="delta"), "type_mismatch"),
        (lambda row: row.update(ts=True), "message_timestamp_invalid"),
        (
            lambda row: row["data"][0].update(extra="x"),
            "liquidation_event_schema_mismatch",
        ),
        (
            lambda row: row["data"][0].update(s="ETHUSDT"),
            "liquidation_event_identity_mismatch",
        ),
        (
            lambda row: row["data"][0].update(S="unknown"),
            "liquidation_event_side_invalid",
        ),
        (
            lambda row: row["data"][0].update(T=1784360640001),
            "liquidation_event_after_message",
        ),
        (
            lambda row: row["data"][0].update(v="0"),
            "liquidation_size_invalid",
        ),
        (
            lambda row: row["data"][0].update(v="1e10000"),
            "liquidation_size_invalid",
        ),
        (
            lambda row: row["data"][0].update(p=float("inf")),
            "source_message_non_finite_json",
        ),
    ),
)
def test_malformed_messages_fail_closed(mutation: object, error: str) -> None:
    with pytest.raises(BybitLiquidationStreamError, match=error):
        _normalize(_changed(mutation))


def test_causal_and_exact_instrument_boundaries_fail_closed() -> None:
    with pytest.raises(
        BybitLiquidationStreamError, match="message_received_before_emission"
    ):
        _normalize(received_at="2026-07-18T07:43:59.999Z")
    with pytest.raises(
        BybitLiquidationStreamError, match="eligible_instrument_contract_invalid"
    ):
        _normalize(instrument=replace(_instrument(), settle_asset="USDC"))
    with pytest.raises(BybitLiquidationStreamError, match="source_lineage_id_invalid"):
        _normalize(source_lineage_id="contains a space")
    with pytest.raises(
        BybitLiquidationStreamError, match="source_message_duplicate_json_key"
    ):
        _normalize(
            b'{"topic":"allLiquidation.BTCUSDT","topic":"x",'
            b'"type":"snapshot","ts":1784360640000,"data":[]}'
        )


def test_fixture_smoke_and_make_target_are_offline_and_non_mutating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("offline liquidation smoke must not open a socket")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    report = run_fixture_smoke(
        FIXTURE_DIR,
        execution_fixture_dir=QUALITY_DIR,
    )

    assert report["status"] == "ok"
    assert report["event_count"] == 2
    assert report["provider_calls"] == 0
    assert report["websocket_connections"] == 0
    assert report["file_writes"] == 0
    assert report["credentials_read"] is False
    assert report["orders_available"] is False
    assert report["research_only"] is True

    completed = subprocess.run(
        [
            "make",
            "radar-derivatives-bybit-liquidation-smoke",
            "PYTHON=python3",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    rendered = json.loads(completed.stdout[completed.stdout.index("{") :])
    assert rendered["status"] == "ok"
    assert rendered["provider_calls"] == 0
    assert rendered["websocket_connections"] == 0
