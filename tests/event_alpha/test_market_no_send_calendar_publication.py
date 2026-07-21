"""Read-once publication bindings for market/no-send calendar artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations import market_no_send
from crypto_rsi_scanner.event_alpha.operations import market_no_send_calendar
from crypto_rsi_scanner.event_alpha.operations import (
    market_no_send_calendar_materialization,
    market_no_send_calendar_publication,
)
from crypto_rsi_scanner.event_alpha.operations import market_no_send_generation
from crypto_rsi_scanner.event_alpha.operations import market_no_send_io


_OBSERVED = "2026-07-12T12:00:00+00:00"


def _run_bound_calendar_generation(tmp_path, monkeypatch, *, namespace, events=None):
    monkeypatch.setenv("RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR", str(tmp_path))
    monkeypatch.delenv(
        market_no_send_calendar.CALENDAR_SNAPSHOT_PATH_ENV,
        raising=False,
    )
    calendar_path = tmp_path / f"{namespace}-source.json"
    calendar_path.write_text(
        json.dumps(
            {
                "contract_version": 1,
                "observed_at": _OBSERVED,
                "source_mode": "operator_verified_calendar_snapshot",
                "data_acquisition_mode": "operator_verified_export",
                "source_provider": "operator_calendar",
                "events": (
                    events
                    if events is not None
                    else [
                        {
                            "id": "calendar-read-once",
                            "title": "Calendar read-once boundary",
                            "event_kind": "protocol",
                            "scheduled_at": "2026-07-20T12:00:00Z",
                            "time_certainty": "exact",
                            "importance": "high",
                            "affected_assets": ["MKTFLOW"],
                            "source": "operator_calendar",
                            "source_url": "https://example.com/calendar/read-once",
                            "research_only": True,
                        }
                    ]
                ),
            }
        ),
        encoding="utf-8",
    )
    return market_no_send.run_market_no_send_generation(
        artifact_base_dir=tmp_path,
        artifact_namespace=namespace,
        profile="fixture",
        run_mode="fixture",
        top_n=5,
        provider=lambda _limit: market_no_send._smoke_rows(),
        observed_at=_OBSERVED,
        environ={
            market_no_send_calendar.CALENDAR_SNAPSHOT_PATH_ENV: str(calendar_path)
        },
        fixture_dir=None,
        data_mode="mock",
        allow_non_live=True,
    )


def test_calendar_derivation_separates_asset_linked_and_global_context(
    tmp_path,
    monkeypatch,
):
    asset_event = {
        "id": "asset-event",
        "title": "Asset-linked event",
        "event_kind": "protocol",
        "scheduled_at": "2026-07-20T12:00:00Z",
        "time_certainty": "exact",
        "importance": "high",
        "affected_assets": [{"coin_id": "market-flow"}, "MKTFLOW"],
        "source": "operator_calendar",
        "source_url": "https://example.com/calendar/asset-event",
        "research_only": True,
    }
    global_event = {
        "id": "global-event",
        "title": "Global macro event",
        "event_kind": "macro",
        "scheduled_at": "2026-07-20T14:00:00Z",
        "time_certainty": "exact",
        "importance": "critical",
        "affected_assets": ["CRYPTO_MARKET"],
        "source": "operator_calendar",
        "source_url": "https://example.com/calendar/global-event",
        "research_only": True,
    }
    result = _run_bound_calendar_generation(
        tmp_path,
        monkeypatch,
        namespace="calendar_asset_and_global_context",
        events=[asset_event, global_event],
    )
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    metadata = manifest["calendar_snapshot"]

    assert metadata["retained_row_count"] == 2
    assert metadata["scheduled_catalyst_count"] == 1
    assert metadata["scheduled_context_only_count"] == 1
    assert metadata["scheduled_derivation_scope"] == "asset_linked_events_only"
    scheduled_rows = market_no_send_io.parse_jsonl_bytes(
        (result.namespace_dir / "event_scheduled_catalysts.jsonl").read_bytes()
    )
    unified_rows = market_no_send_io.parse_jsonl_bytes(
        (result.namespace_dir / "event_unified_calendar_events.jsonl").read_bytes()
    )
    assert [row["symbol"] for row in scheduled_rows] == ["MKTFLOW"]
    assert scheduled_rows[0]["coin_id"] == "market-flow"
    assert len(unified_rows) == 2
    market_no_send_calendar_publication.validate_optional_calendar_snapshot(
        manifest,
        namespace_dir=result.namespace_dir,
        run_id=result.run_id,
        safety_counters=market_no_send._SAFETY_COUNTERS,
    )

    drifted_manifest = json.loads(json.dumps(manifest))
    drifted_manifest["calendar_snapshot"]["scheduled_context_only_count"] = 0
    with pytest.raises(
        market_no_send.MarketNoSendError,
        match="campaign_calendar_scheduled_count_mismatch",
    ):
        market_no_send_calendar_publication.validate_optional_calendar_snapshot(
            drifted_manifest,
            namespace_dir=result.namespace_dir,
            run_id=result.run_id,
            safety_counters=market_no_send._SAFETY_COUNTERS,
        )


@pytest.mark.parametrize("symbol", [True, 123, {"ticker": "BTC"}, "CRYPTO_MARKET"])
def test_calendar_derivation_never_stringifies_non_asset_symbols(symbol):
    scheduled, unlocks = (
        market_no_send_calendar_materialization.canonical_calendar_derivation_rows(
            [
                {
                    "id": "global-context",
                    "title": "Global context",
                    "event_kind": "macro",
                    "scheduled_at": "2026-07-20T14:00:00Z",
                    "symbol": symbol,
                    "affected_assets": ["CRYPTO_MARKET"],
                    "source_url": "https://example.com/calendar/global-context",
                }
            ],
            profile="fixture",
            artifact_namespace="calendar_typed_identity",
            run_mode="fixture",
            run_id="calendar-typed-identity-run",
            observed_at=_OBSERVED,
        )
    )

    assert scheduled == ()
    assert unlocks == ()


def test_calendar_source_publication_parses_the_exact_hashed_read_buffer(
    tmp_path,
    monkeypatch,
):
    result = _run_bound_calendar_generation(
        tmp_path,
        monkeypatch,
        namespace="calendar_source_read_once",
    )
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    source_path = (
        result.namespace_dir
        / market_no_send_calendar.CALENDAR_SOURCE_COPY_FILENAME
    )
    original_read = market_no_send_calendar_publication.read_regular_bytes
    swapped = False

    def swap_after_read(path, *, missing_ok=False):
        nonlocal swapped
        raw = original_read(path, missing_ok=missing_ok)
        if Path(path) == source_path and not swapped:
            source_path.write_bytes(b'{"events":"replacement-after-read"}\n')
            swapped = True
        return raw

    monkeypatch.setattr(
        market_no_send_calendar_publication,
        "read_regular_bytes",
        swap_after_read,
    )

    market_no_send_calendar_publication.validate_optional_calendar_snapshot(
        manifest,
        namespace_dir=result.namespace_dir,
        run_id=result.run_id,
        safety_counters=market_no_send._SAFETY_COUNTERS,
    )

    assert swapped is True
    assert source_path.read_bytes() == b'{"events":"replacement-after-read"}\n'
    with pytest.raises(
        market_no_send.MarketNoSendError,
        match="operator state identity",
    ):
        market_no_send.market_no_send_publication._validate_operator_market_provenance(
            result.namespace_dir,
            manifest=manifest,
            default_profile="fixture",
        )


def test_calendar_source_rejects_cross_buffer_digest_content_disagreement(
    tmp_path,
    monkeypatch,
):
    result = _run_bound_calendar_generation(
        tmp_path,
        monkeypatch,
        namespace="calendar_source_cross_buffer",
    )
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    metadata = json.loads(json.dumps(manifest["calendar_snapshot"]))
    source_path = (
        result.namespace_dir
        / market_no_send_calendar.CALENDAR_SOURCE_COPY_FILENAME
    )
    original = source_path.read_bytes()
    replacement = json.loads(original)
    replacement["events"][0]["title"] = "Replacement semantic buffer"
    safe_replacement = list(
        market_no_send_calendar.validate_calendar_artifact_rows(
            replacement["events"]
        )
    )
    replacement_canonical = hashlib.sha256(
        json.dumps(
            safe_replacement,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    replacement["canonical_rows_sha256"] = replacement_canonical
    metadata["canonical_rows_sha256"] = replacement_canonical
    source_path.write_text(
        json.dumps(replacement, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    original_reader = market_no_send_calendar_publication.read_regular_bytes

    def split_buffers(path, *, missing_ok=False):
        if Path(path) == source_path:
            return original
        return original_reader(path, missing_ok=missing_ok)

    monkeypatch.setattr(
        market_no_send_calendar_publication,
        "read_regular_bytes",
        split_buffers,
    )

    with pytest.raises(
        market_no_send.MarketNoSendError,
        match="binding_mismatch",
    ):
        market_no_send_calendar_publication._validate_source_copy(
            manifest,
            metadata=metadata,
            namespace_dir=result.namespace_dir,
            run_id=result.run_id,
            safety_counters=market_no_send._SAFETY_COUNTERS,
        )


@pytest.mark.parametrize(
    "filename",
    ["event_scheduled_catalysts.jsonl", "event_unified_calendar_events.jsonl"],
)
def test_calendar_jsonl_publication_parses_the_exact_hashed_read_buffer(
    tmp_path,
    monkeypatch,
    filename,
):
    result = _run_bound_calendar_generation(
        tmp_path,
        monkeypatch,
        namespace=f"calendar_jsonl_read_once_{filename.split('.')[0]}",
    )
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    target = result.namespace_dir / filename
    original_read = market_no_send_calendar_publication.read_regular_bytes
    swapped = False

    def swap_after_read(path, *, missing_ok=False):
        nonlocal swapped
        raw = original_read(path, missing_ok=missing_ok)
        if Path(path) == target and not swapped:
            target.write_bytes(b"not-json-after-read\n")
            swapped = True
        return raw

    monkeypatch.setattr(
        market_no_send_calendar_publication,
        "read_regular_bytes",
        swap_after_read,
    )

    market_no_send_calendar_publication.validate_optional_calendar_snapshot(
        manifest,
        namespace_dir=result.namespace_dir,
        run_id=result.run_id,
        safety_counters=market_no_send._SAFETY_COUNTERS,
    )

    assert swapped is True
    assert target.read_bytes() == b"not-json-after-read\n"


def test_unified_calendar_binding_hash_and_count_share_one_read_buffer(
    tmp_path,
    monkeypatch,
):
    namespace_dir = tmp_path / "calendar_generation_read_once"
    namespace_dir.mkdir()
    target = namespace_dir / "event_unified_calendar_events.jsonl"
    original = b'{"id":"one"}\n{"id":"two"}\n'
    target.write_bytes(original)
    original_read = market_no_send_generation.read_regular_bytes
    swapped = False

    def swap_after_read(path, *, missing_ok=False):
        nonlocal swapped
        raw = original_read(path, missing_ok=missing_ok)
        if Path(path) == target and not swapped:
            target.write_bytes(b'{"id":"replacement"}\n')
            swapped = True
        return raw

    monkeypatch.setattr(
        market_no_send_generation,
        "read_regular_bytes",
        swap_after_read,
    )
    metadata = {}

    market_no_send_generation._bind_unified_calendar_artifact(
        metadata,
        namespace_dir=namespace_dir,
    )

    assert swapped is True
    assert metadata["unified_calendar_artifact_sha256"] == hashlib.sha256(
        original
    ).hexdigest()
    assert metadata["unified_calendar_artifact_row_count"] == 2


@pytest.mark.parametrize(
    ("parser", "raw"),
    [
        (market_no_send_io.parse_json_object_bytes, b'{"id":1,"id":2}'),
        (market_no_send_io.parse_jsonl_bytes, b'{"id":1,"id":2}\n'),
    ],
)
def test_market_exact_buffer_parsers_reject_duplicate_json_keys(parser, raw):
    with pytest.raises(market_no_send.MarketNoSendError, match="invalid JSON"):
        parser(raw)
