"""Exact two-capture Bybit visible-book round-trip regressions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import socket
import subprocess
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

from crypto_rsi_scanner.event_alpha.operations import (
    bybit_execution_quality_capture_validation as capture_validation,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality import (
    PUBLIC_API_BASE,
    BybitPublicRequest,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality_capture import (
    BybitCapturedJSONResponse,
    BybitExecutionQualityCaptureError,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality_capture_pair import (
    SCHEMA_VERSION,
    BybitExecutionQualityCapturePairError,
    main,
    model_bybit_capture_pair_target_notional_round_trip,
)
from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality_live import (
    LIVE_AUTH_ENV,
    capture_authoritative_bybit_execution_quality,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "fixtures/bybit_execution_quality"
ENTRY_PROVIDER_AT = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
EXIT_PROVIDER_AT = datetime(2026, 7, 17, 13, 0, tzinfo=timezone.utc)


def _fixture(name: str) -> dict[str, object]:
    value = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _observation() -> dict[str, object]:
    return {
        "canonical_asset_id": "bitcoin",
        "symbol": "BTC",
        "liquidity_usd": 3_000.0,
        "data_mode": "live",
        "candidate_source_mode": "live_no_send",
        "decision_radar_campaign_counted": True,
        "provenance_contract_valid": True,
        "research_only": True,
        "no_send": True,
        "freshness_status": "fresh",
    }


def _captured(
    request: BybitPublicRequest,
    payload: dict[str, object],
    *,
    received_at: datetime,
) -> BybitCapturedJSONResponse:
    received = received_at.isoformat().replace("+00:00", "Z")
    return BybitCapturedJSONResponse(
        request=request,
        request_started_at=received,
        response_received_at=received,
        duration_ms=0,
        response_url=(
            f"{PUBLIC_API_BASE}{request.path}?{urlencode(request.query)}"
        ),
        http_status=200,
        content_type="application/json",
        raw_bytes=(
            json.dumps(payload, separators=(",", ":")) + "\n"
        ).encode("utf-8"),
    )


def _capture(
    artifact_base: Path,
    *,
    provider_at: datetime,
    orderbook_fixture: str,
    authority_suffix: str,
    catalog_changes: dict[str, str] | None = None,
    completion_delay_seconds: float = 1.2,
) -> dict[str, object]:
    started = provider_at - timedelta(seconds=2)
    catalog_received = provider_at - timedelta(seconds=1)
    book_received = provider_at + timedelta(seconds=1)
    completed = provider_at + timedelta(seconds=completion_delay_seconds)
    rechecked = completed + timedelta(milliseconds=100)
    snapshot = SimpleNamespace(
        artifact_namespace=f"radar_market_no_send_{authority_suffix}",
        run_id=f"{provider_at.isoformat()}|{authority_suffix}",
        revision=12,
        operator_state_sha256="a" * 64,
        generation_authority_checked_at=started.isoformat().replace(
            "+00:00", "Z"
        ),
        current_market_observations=(_observation(),),
    )

    def resolver(_base: object, *, now: object) -> object:
        assert now in {started, rechecked}
        return SimpleNamespace(snapshot=snapshot)

    def fetch(
        request: BybitPublicRequest,
        _timeout: float,
    ) -> BybitCapturedJSONResponse:
        if request.path.endswith("instruments-info"):
            payload = deepcopy(_fixture("instruments_info.json"))
            if catalog_changes:
                result = payload["result"]
                assert isinstance(result, dict)
                rows = result["list"]
                assert isinstance(rows, list)
                lot = rows[0]["lotSizeFilter"]
                assert isinstance(lot, dict)
                lot.update(catalog_changes)
            return _captured(
                request,
                payload,
                received_at=catalog_received,
            )
        return _captured(
            request,
            deepcopy(_fixture(orderbook_fixture)),
            received_at=book_received,
        )

    clocks = iter((started, completed, rechecked))
    return capture_authoritative_bybit_execution_quality(
        artifact_base_dir=artifact_base,
        environ={LIVE_AUTH_ENV: "1"},
        now=lambda: next(clocks),
        resolver=resolver,
        fetch_json=fetch,
    )


def _capture_pair(
    tmp_path: Path,
    *,
    exit_catalog_changes: dict[str, str] | None = None,
    entry_completion_delay_seconds: float = 1.2,
) -> tuple[dict[str, object], dict[str, object]]:
    entry = _capture(
        tmp_path,
        provider_at=ENTRY_PROVIDER_AT,
        orderbook_fixture="orderbook_btcusdt.json",
        authority_suffix="entry",
        completion_delay_seconds=entry_completion_delay_seconds,
    )
    exit_capture = _capture(
        tmp_path,
        provider_at=EXIT_PROVIDER_AT,
        orderbook_fixture="orderbook_btcusdt_exit.json",
        authority_suffix="exit",
        catalog_changes=(
            exit_catalog_changes
            if exit_catalog_changes is not None
            else {
                "qtyStep": "0.002",
                "minOrderQty": "0.002",
                "maxMktOrderQty": "10",
            }
        ),
    )
    return entry, exit_capture


def _tree_fingerprints(root: Path) -> dict[str, tuple[int, int, str]]:
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_size,
            path.stat().st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize("position_side", ("long", "short"))
def test_pair_rederives_two_exact_captures_without_pointer_or_writes(
    tmp_path: Path,
    position_side: str,
) -> None:
    entry, exit_capture = _capture_pair(tmp_path)
    before = _tree_fingerprints(tmp_path)

    result = model_bybit_capture_pair_target_notional_round_trip(
        tmp_path,
        entry_namespace=str(entry["artifact_namespace"]),
        exit_namespace=str(exit_capture["artifact_namespace"]),
        instrument_id="BTCUSDT",
        position_side=position_side,
        target_entry_mid_notional_usdt="1500.75",
    ).to_dict()

    assert _tree_fingerprints(tmp_path) == before
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["position_side"] == position_side
    assert result["entry_capture"]["capture_id"] == entry["capture_id"]
    assert result["exit_capture"]["capture_id"] == exit_capture["capture_id"]
    assert result["entry_capture"]["artifact_namespace"] == entry[
        "artifact_namespace"
    ]
    assert result["exit_capture"]["artifact_namespace"] == exit_capture[
        "artifact_namespace"
    ]
    assert result["entry_capture"]["source_authority"] == entry[
        "source_authority"
    ]
    assert result["exit_capture"]["source_authority"] == exit_capture[
        "source_authority"
    ]
    for role, capture in (("entry", entry), ("exit", exit_capture)):
        namespace = tmp_path / str(capture["artifact_namespace"])
        for field, name in (
            ("catalog_response", "raw_001_instrument_catalog.json"),
            ("orderbook_response", "raw_002_orderbook_BTCUSDT.json"),
        ):
            raw = (namespace / name).read_bytes()
            assert result[f"{role}_capture"][f"{field}_sha256"] == (
                hashlib.sha256(raw).hexdigest()
            )
            assert result[f"{role}_capture"][f"{field}_size_bytes"] == len(raw)
    assert result["captures_distinct"] is True
    assert result["capture_windows_ordered_non_overlapping"] is True
    assert result["exact_raw_responses_rederived"] is True
    assert result["exact_namespaces_required"] is True
    assert result["latest_pointer_used"] is False
    assert result["both_capture_sets_fresh_at_completion"] is True
    assert result["capture_evidence_authority_eligible"] is True
    assert result["protocol_v2_annex_bound"] is False
    assert result["protocol_v2_evidence_eligible"] is False
    assert result["provider_calls"] == 0
    assert result["writes_performed"] is False
    assert result["orders"] == result["trades"] == 0
    nested = result["target_notional_round_trip"]
    assert nested["schema_version"].endswith("round_trip.v2")
    assert nested["round_trip"]["schema_version"].endswith("round_trip.v3")
    assert nested["round_trip"]["constraint_values_changed_between_legs"] is True
    assert nested["round_trip"]["entry_instrument_constraints"][
        "quantity_step"
    ] == "0.001"
    assert nested["round_trip"]["exit_instrument_constraints"][
        "quantity_step"
    ] == "0.002"
    assert nested["round_trip"]["round_trip_quantity_eligible_order_styles"] == [
        "marketable_limit"
    ]
    assert nested["round_trip"]["entry_instrument_constraints"][
        "lineage_id"
    ] == f"capture:{entry['capture_id']}:catalog"
    assert nested["round_trip"]["exit_instrument_constraints"][
        "lineage_id"
    ] == f"capture:{exit_capture['capture_id']}:catalog"


def test_pair_rejects_same_reversed_missing_and_step_incompatible_inputs(
    tmp_path: Path,
) -> None:
    entry, exit_capture = _capture_pair(tmp_path)
    common = {
        "artifact_base_dir": tmp_path,
        "instrument_id": "BTCUSDT",
        "position_side": "long",
        "target_entry_mid_notional_usdt": "1500.75",
    }
    with pytest.raises(
        BybitExecutionQualityCapturePairError,
        match="capture_namespaces_not_distinct",
    ):
        model_bybit_capture_pair_target_notional_round_trip(
            entry_namespace=str(entry["artifact_namespace"]),
            exit_namespace=str(entry["artifact_namespace"]),
            **common,
        )
    with pytest.raises(
        BybitExecutionQualityCapturePairError,
        match="capture_windows_not_ordered_non_overlapping",
    ):
        model_bybit_capture_pair_target_notional_round_trip(
            entry_namespace=str(exit_capture["artifact_namespace"]),
            exit_namespace=str(entry["artifact_namespace"]),
            **common,
        )
    with pytest.raises(
        BybitExecutionQualityCapturePairError,
        match="entry_instrument_not_unique_or_absent",
    ):
        model_bybit_capture_pair_target_notional_round_trip(
            entry_namespace=str(entry["artifact_namespace"]),
            exit_namespace=str(exit_capture["artifact_namespace"]),
            **dict(common, instrument_id="ETHUSDT"),
        )
    with pytest.raises(
        BybitExecutionQualityCapturePairError,
        match="exit_base_quantity_not_aligned_to_quantity_step",
    ):
        model_bybit_capture_pair_target_notional_round_trip(
            entry_namespace=str(entry["artifact_namespace"]),
            exit_namespace=str(exit_capture["artifact_namespace"]),
            **dict(
                common,
                target_entry_mid_notional_usdt="1500.85005",
            ),
        )


def test_pair_rejects_capture_level_staleness_and_raw_drift(tmp_path: Path) -> None:
    stale_entry, exit_capture = _capture_pair(
        tmp_path,
        entry_completion_delay_seconds=16.2,
    )
    with pytest.raises(
        BybitExecutionQualityCapturePairError,
        match="entry_capture_not_input_quality_eligible",
    ):
        model_bybit_capture_pair_target_notional_round_trip(
            tmp_path,
            entry_namespace=str(stale_entry["artifact_namespace"]),
            exit_namespace=str(exit_capture["artifact_namespace"]),
            instrument_id="BTCUSDT",
            position_side="long",
            target_entry_mid_notional_usdt="1500.75",
        )

    clean_root = tmp_path / "clean"
    clean_root.mkdir()
    entry, clean_exit = _capture_pair(clean_root)
    raw = (
        clean_root
        / str(entry["artifact_namespace"])
        / "raw_002_orderbook_BTCUSDT.json"
    )
    raw.write_bytes(raw.read_bytes() + b" ")
    with pytest.raises(
        BybitExecutionQualityCaptureError,
        match="capture_fingerprint_mismatch",
    ):
        model_bybit_capture_pair_target_notional_round_trip(
            clean_root,
            entry_namespace=str(entry["artifact_namespace"]),
            exit_namespace=str(clean_exit["artifact_namespace"]),
            instrument_id="BTCUSDT",
            position_side="long",
            target_entry_mid_notional_usdt="1500.75",
        )


def test_cli_is_read_only_secret_free_and_never_opens_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    entry, exit_capture = _capture_pair(tmp_path)
    before = _tree_fingerprints(tmp_path)

    def forbidden_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("capture-pair projection must not open network")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setenv("BYBIT_API_SECRET", "must-not-print")
    assert main(
        [
            "--artifact-base",
            str(tmp_path),
            "--entry-namespace",
            str(entry["artifact_namespace"]),
            "--exit-namespace",
            str(exit_capture["artifact_namespace"]),
            "--instrument-id",
            "BTCUSDT",
            "--position-side",
            "long",
            "--target-entry-mid-notional-usdt",
            "1500.75",
        ]
    ) == 0
    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert output.err == ""
    assert payload["provider_calls"] == 0
    assert payload["writes_performed"] is False
    assert "must-not-print" not in output.out
    assert _tree_fingerprints(tmp_path) == before


def test_pair_holds_one_artifact_root_across_both_capture_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry, exit_capture = _capture_pair(tmp_path)
    original = capture_validation._read_capture_bundle_from_namespace_fd
    moved = tmp_path.with_name(f"{tmp_path.name}_moved")
    call_count = 0

    def swap_root_after_entry(descriptor: int):
        nonlocal call_count
        result = original(descriptor)
        call_count += 1
        if call_count == 1:
            tmp_path.rename(moved)
            tmp_path.mkdir()
        return result

    monkeypatch.setattr(
        capture_validation,
        "_read_capture_bundle_from_namespace_fd",
        swap_root_after_entry,
    )
    try:
        with pytest.raises(
            BybitExecutionQualityCaptureError,
            match="capture_artifact_base_changed_during_pair",
        ):
            model_bybit_capture_pair_target_notional_round_trip(
                tmp_path,
                entry_namespace=str(entry["artifact_namespace"]),
                exit_namespace=str(exit_capture["artifact_namespace"]),
                instrument_id="BTCUSDT",
                position_side="long",
                target_entry_mid_notional_usdt="1500.75",
            )
    finally:
        if tmp_path.is_dir() and moved.is_dir():
            tmp_path.rmdir()
            moved.rename(tmp_path)


def test_pair_holds_both_named_namespaces_across_complete_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry, exit_capture = _capture_pair(tmp_path)
    original = capture_validation._read_capture_bundle_from_namespace_fd
    exit_path = tmp_path / str(exit_capture["artifact_namespace"])
    moved = tmp_path / f"{exit_path.name}_moved"
    call_count = 0

    def swap_exit_namespace_after_entry(descriptor: int):
        nonlocal call_count
        result = original(descriptor)
        call_count += 1
        if call_count == 1:
            exit_path.rename(moved)
            exit_path.mkdir()
        return result

    monkeypatch.setattr(
        capture_validation,
        "_read_capture_bundle_from_namespace_fd",
        swap_exit_namespace_after_entry,
    )
    try:
        with pytest.raises(
            BybitExecutionQualityCaptureError,
            match="capture_namespace_changed_during_pair",
        ):
            model_bybit_capture_pair_target_notional_round_trip(
                tmp_path,
                entry_namespace=str(entry["artifact_namespace"]),
                exit_namespace=str(exit_capture["artifact_namespace"]),
                instrument_id="BTCUSDT",
                position_side="long",
                target_entry_mid_notional_usdt="1500.75",
            )
    finally:
        if exit_path.is_dir() and moved.is_dir():
            exit_path.rmdir()
            moved.rename(exit_path)


def test_make_target_requires_exact_namespaces_and_stays_read_only() -> None:
    completed = subprocess.run(
        [
            "make",
            "-n",
            "radar-execution-quality-bybit-round-trip",
            "BYBIT_ENTRY_EXECUTION_CAPTURE_NAMESPACE=entry_exact",
            "BYBIT_EXIT_EXECUTION_CAPTURE_NAMESPACE=exit_exact",
            "BYBIT_EXECUTION_INSTRUMENT_ID=BTCUSDT",
            "BYBIT_EXECUTION_POSITION_SIDE=long",
            "BYBIT_EXECUTION_TARGET_NOTIONAL_USDT=1500",
            "PYTHON=python3",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "operations.bybit_execution_quality_capture_pair" in completed.stdout
    assert '--entry-namespace "entry_exact"' in completed.stdout
    assert '--exit-namespace "exit_exact"' in completed.stdout
    assert '--instrument-id "BTCUSDT"' in completed.stdout
    assert '--position-side "long"' in completed.stdout
    assert '--target-entry-mid-notional-usdt "1500"' in completed.stdout
    lowered = completed.stdout.casefold()
    assert "curl" not in lowered
    assert "confirm=1" not in lowered
