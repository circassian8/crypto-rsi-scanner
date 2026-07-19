"""Detached immutable Bybit liquidation transcript-capture regressions."""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest

from crypto_rsi_scanner.event_alpha.operations import bybit_liquidation_capture as capture


def _transcript() -> dict[str, object]:
    value = json.loads(capture._smoke_transcript())
    value["capture_mode"] = "operator_import"
    return value


def _source(
    root: Path,
    value: dict[str, object] | None = None,
    *,
    raw: bytes | None = None,
    directory: str = "operator_inputs",
) -> Path:
    source_dir = root / directory
    source_dir.mkdir(exist_ok=True)
    path = source_dir / "transcript.json"
    path.write_bytes(
        raw
        if raw is not None
        else (json.dumps(value or _transcript(), indent=2, sort_keys=True) + "\n").encode()
    )
    return path


def _import(
    root: Path,
    value: dict[str, object] | None = None,
) -> tuple[Path, Path, dict[str, object]]:
    artifact_base = root / "artifacts"
    artifact_base.mkdir()
    source = _source(root, value)
    result = capture.import_bybit_liquidation_transcript(
        artifact_base,
        transcript_path=source,
        confirm=True,
    )
    return artifact_base, source, result


def _decode_message(value: dict[str, object], index: int) -> dict[str, object]:
    messages = value["messages"]
    assert isinstance(messages, list)
    row = messages[index]
    assert isinstance(row, dict)
    return json.loads(base64.b64decode(row["payload_base64"]))


def _replace_message(value: dict[str, object], index: int, payload: dict[str, object]) -> None:
    messages = value["messages"]
    assert isinstance(messages, list)
    row = messages[index]
    assert isinstance(row, dict)
    row["payload_base64"] = base64.b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode()


def _assert_closed_provenance(
    value: dict[str, object], *, source_authority: str
) -> None:
    assert value["source_authority"] == source_authority
    assert value["transport_scope"] == "application_payloads_only"
    for field in (
        "transport_captured_by_project",
        "provider_connection_verified_by_project",
        "websocket_frame_bytes_preserved",
        "tls_upgrade_evidence_included",
        "input_authority",
        "pointer_authority",
        "campaign_authority",
        "dashboard_authority",
        "policy_authority",
        "directional_authority",
        "protocol_v2_authority",
        "protocol_v2_input_quality_eligible",
    ):
        assert value[field] is False
    assert value["provider_calls_by_radar"] == 0
    assert value["websocket_connections_by_radar"] == 0
    assert value["provider_authorization_reads_by_radar"] == 0
    assert value["credential_reads_by_radar"] == 0
    assert value["environment_reads_by_radar"] == 0
    assert value["no_send"] is True
    for counter in (
        "orders",
        "trades",
        "paper_trades",
        "normal_rsi_writes",
        "event_alpha_triggered_fade",
    ):
        assert value[counter] == 0
    for misleading in (
        "provider_call_attempted",
        "provider_calls",
        "websocket_connection_opened",
        "websocket_connections",
        "provider_authorization_read",
        "credentials_read",
    ):
        assert misleading not in value


def test_import_preserves_exact_payloads_rederives_events_and_is_idempotent(
    tmp_path: Path,
) -> None:
    artifact_base, source, first = _import(tmp_path)
    namespace = str(first["artifact_namespace"])
    namespace_dir = artifact_base / namespace

    assert first["status"] == "complete"
    assert namespace.startswith("radar_bybit_liquidation_transcript_")
    assert first["writes_performed"] is True
    assert first["idempotent_reuse"] is False
    assert first["coverage_status"] == "observed_messages_only"
    assert first["coverage_complete"] is False
    assert first["message_count"] == 3
    assert first["data_message_count"] == 1
    assert first["event_count"] == 1
    assert first["duplicate_occurrence_policy"] == (
        "reject_canonical_provider_occurrence_within_or_across_data_messages"
    )
    assert (namespace_dir / capture.SOURCE_FILENAME).read_bytes() == source.read_bytes()
    transcript = _transcript()
    messages = transcript["messages"]
    assert isinstance(messages, list)
    for sequence, message in enumerate(messages, start=1):
        assert isinstance(message, dict)
        assert (namespace_dir / f"application_payload_{sequence:03d}.bin").read_bytes() == (
            base64.b64decode(message["payload_base64"])
        )
    events = json.loads((namespace_dir / capture.EVENTS_FILENAME).read_text())
    assert events["event_count"] == 1
    assert events["events"][0]["instrument_id"] == "BTCUSDT"
    assert events["events"][0]["liquidated_position_side"] == "long"
    assert events["events"][0]["liquidation_notional_usdt"] == 60_000.0
    assert events["context_only"] is True
    assert events["directional_authority"] is False
    assert events["stream_continuity_claimed"] is False
    assert events["silent_intervals_observed_as_zero_liquidations"] is False
    for filename in (
        capture.LEDGER_FILENAME,
        capture.EVENTS_FILENAME,
        capture.MANIFEST_FILENAME,
        capture.RECEIPT_FILENAME,
    ):
        _assert_closed_provenance(
            json.loads((namespace_dir / filename).read_text()),
            source_authority="operator_attested_unverified_application_payloads",
        )
    manifest = json.loads((namespace_dir / capture.MANIFEST_FILENAME).read_text())
    assert manifest["artifacts"][0]["role"] == "exact_source_transcript"

    second = capture.import_bybit_liquidation_transcript(
        artifact_base,
        transcript_path=source,
        confirm=True,
    )
    validated = capture.validate_bybit_liquidation_capture(
        artifact_base,
        namespace=namespace,
    )

    assert second["capture_id"] == first["capture_id"] == validated["capture_id"]
    assert second["idempotent_reuse"] is True
    assert second["writes_performed"] is False
    assert not any("latest" in path.name for path in artifact_base.iterdir())
    assert set(namespace_dir.iterdir()) == {
        namespace_dir / capture.SOURCE_FILENAME,
        namespace_dir / "application_payload_001.bin",
        namespace_dir / "application_payload_002.bin",
        namespace_dir / "application_payload_003.bin",
        namespace_dir / capture.LEDGER_FILENAME,
        namespace_dir / capture.EVENTS_FILENAME,
        namespace_dir / capture.MANIFEST_FILENAME,
        namespace_dir / capture.RECEIPT_FILENAME,
    }
    for result in (first, second, validated):
        rendered = json.dumps(result)
        assert "payload_base64" not in rendered
        assert "source_path" not in rendered
        _assert_closed_provenance(
            result,
            source_authority="operator_attested_unverified_application_payloads",
        )
        assert result["evidence_authority_eligible"] is False
        assert result["protocol_v2_input_quality_eligible"] is False
        assert result["protocol_v2_evidence_eligible"] is False
        assert result["protocol_v2_annex_bound"] is False
        assert result["dashboard_authority_eligible"] is False
        assert result["campaign_attached"] is False


def test_validate_local_rederives_without_creating_an_artifact_namespace(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _source(tmp_path)

    result = capture.validate_local_transcript(source)

    assert result["status"] == "complete"
    assert result["artifact_persisted"] is False
    assert result["writes_performed"] is False
    assert result["artifact_namespace"].startswith(
        "radar_bybit_liquidation_transcript_"
    )
    assert set(tmp_path.iterdir()) == {source.parent}
    assert capture.main(["validate-local", "--input", str(source)]) == 0
    cli_result = json.loads(capsys.readouterr().out)
    assert cli_result["capture_id"] == result["capture_id"]
    assert cli_result["artifact_persisted"] is False


def test_optional_request_id_and_empty_or_absent_ack_id_are_accepted(tmp_path: Path) -> None:
    for index, ack_mode in enumerate(("absent", "empty"), start=1):
        value = _transcript()
        subscribe = _decode_message(value, 0)
        subscribe.pop("req_id")
        _replace_message(value, 0, subscribe)
        ack = _decode_message(value, 1)
        if ack_mode == "absent":
            ack.pop("req_id")
        else:
            ack["req_id"] = ""
        _replace_message(value, 1, ack)
        case_root = tmp_path / f"operator_case_{index}"
        case_root.mkdir()

        _base, _path, result = _import(case_root, value)

        assert result["status"] == "complete"


@pytest.mark.parametrize("ack_mode", ("absent", "empty"))
def test_nonempty_request_id_requires_exact_nonempty_ack_id(
    tmp_path: Path,
    ack_mode: str,
) -> None:
    value = _transcript()
    ack = _decode_message(value, 1)
    if ack_mode == "absent":
        ack.pop("req_id")
    else:
        ack["req_id"] = ""
    _replace_message(value, 1, ack)
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    source = _source(tmp_path, value)

    with pytest.raises(capture.BybitLiquidationCaptureError, match="ack_invalid"):
        capture.import_bybit_liquidation_transcript(
            artifact_base,
            transcript_path=source,
            confirm=True,
        )


def test_confirmation_path_and_source_file_identity_are_fail_closed(tmp_path: Path) -> None:
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    source = _source(tmp_path)
    with pytest.raises(capture.BybitLiquidationCaptureError, match="confirmation"):
        capture.import_bybit_liquidation_transcript(
            artifact_base,
            transcript_path=source,
            confirm=False,
        )
    assert list(artifact_base.iterdir()) == []

    rejected_source = _source(tmp_path, directory="fixtures")
    with pytest.raises(capture.BybitLiquidationCaptureError, match="path_rejected"):
        capture.import_bybit_liquidation_transcript(
            artifact_base,
            transcript_path=rejected_source,
            confirm=True,
        )

    outside_link = tmp_path / "operator_source_hardlink.json"
    os.link(source, outside_link)
    with pytest.raises(capture.BybitLiquidationCaptureError, match="unreadable"):
        capture.import_bybit_liquidation_transcript(
            artifact_base,
            transcript_path=source,
            confirm=True,
        )


def test_symlinked_ancestry_and_source_inside_artifact_base_are_rejected(
    tmp_path: Path,
) -> None:
    real_fixture_dir = tmp_path / "fixtures"
    real_fixture_dir.mkdir()
    fixture_source = _source(real_fixture_dir)
    alias = tmp_path / "operator_alias"
    alias.symlink_to(fixture_source.parent, target_is_directory=True)
    with pytest.raises(capture.BybitLiquidationCaptureError, match="symlinked"):
        capture.validate_local_transcript(alias / fixture_source.name)

    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    inside_source = _source(artifact_base)
    with pytest.raises(
        capture.BybitLiquidationCaptureError,
        match="inside_artifact_base",
    ):
        capture.import_bybit_liquidation_transcript(
            artifact_base,
            transcript_path=inside_source,
            confirm=True,
        )

    base_alias = tmp_path / "artifact_alias"
    base_alias.symlink_to(artifact_base, target_is_directory=True)
    outside_source = _source(tmp_path, directory="outside_operator_input")
    with pytest.raises(capture.BybitLiquidationCaptureError, match="symlinked"):
        capture.import_bybit_liquidation_transcript(
            base_alias,
            transcript_path=outside_source,
            confirm=True,
        )


def test_import_rejects_source_from_renamed_held_artifact_base_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    inside_source = _source(artifact_base)
    renamed_base = tmp_path / "temporarily_renamed_artifacts"
    renamed_source = renamed_base / "operator_inputs" / inside_source.name
    original_read = capture.capture_io.read_operator_file
    restored = False

    def rename_read_restore(*args: object, **kwargs: object) -> tuple[Path, bytes]:
        nonlocal restored
        artifact_base.rename(renamed_base)
        try:
            return original_read(*args, **kwargs)
        finally:
            renamed_base.rename(artifact_base)
            restored = True

    monkeypatch.setattr(
        capture.capture_io,
        "read_operator_file",
        rename_read_restore,
    )
    with pytest.raises(
        capture.BybitLiquidationCaptureError,
        match="inside_artifact_base",
    ):
        capture.import_bybit_liquidation_transcript(
            artifact_base,
            transcript_path=renamed_source,
            confirm=True,
        )

    assert restored is True
    monkeypatch.setattr(capture.capture_io, "read_operator_file", original_read)
    assert capture.validate_local_transcript(inside_source)["status"] == "complete"
    assert [entry.name for entry in artifact_base.iterdir()] == ["operator_inputs"]


def test_tilde_paths_are_rejected_without_home_expansion(tmp_path: Path) -> None:
    source = _source(tmp_path)
    with pytest.raises(capture.BybitLiquidationCaptureError, match="tilde"):
        capture.validate_local_transcript("~/operator_transcript.json")
    with pytest.raises(capture.BybitLiquidationCaptureError, match="tilde"):
        capture.import_bybit_liquidation_transcript(
            "~/artifact_base",
            transcript_path=source,
            confirm=True,
        )


@pytest.mark.parametrize(
    "secret_value",
    (
        "sk-proj-abcdefghijklmnop",
        "ghp_abcdefghijklmnopqrstuvwxyz123456",
        "12345678:abcdefghijklmnopqrstuvwxyzABCDEFGH",
    ),
)
def test_central_secret_values_are_rejected_in_source_and_decoded_payloads(
    tmp_path: Path,
    secret_value: str,
) -> None:
    source_secret = _transcript()
    source_secret["source_lineage_id"] = secret_value
    source = _source(tmp_path, source_secret)
    with pytest.raises(capture.BybitLiquidationCaptureError, match="secret"):
        capture.validate_local_transcript(source)

    payload_secret = _transcript()
    subscribe = _decode_message(payload_secret, 0)
    subscribe["req_id"] = secret_value
    _replace_message(payload_secret, 0, subscribe)
    payload_source = _source(
        tmp_path,
        payload_secret,
        directory="operator_payload_input",
    )
    with pytest.raises(capture.BybitLiquidationCaptureError, match="secret"):
        capture.validate_local_transcript(payload_source)


@pytest.mark.parametrize(
    "secret_value",
    (
        "sk-proj-abcdefghijklmnop",
        "ghp_abcdefghijklmnopqrstuvwxyz123456",
        "12345678:abcdefghijklmnopqrstuvwxyzABCDEFGH",
    ),
)
def test_json_escaped_secrets_are_rejected_after_strict_decode(
    tmp_path: Path,
    secret_value: str,
) -> None:
    separator = max(secret_value.rfind("-"), secret_value.rfind("_"), secret_value.rfind(":"))
    escaped = (
        secret_value[: separator + 1]
        + f"\\u{ord(secret_value[separator + 1]):04x}"
        + secret_value[separator + 2 :]
    )
    source_value = _transcript()
    source_value["source_lineage_id"] = secret_value
    source_raw = json.dumps(source_value, separators=(",", ":")).replace(
        secret_value, escaped
    ).encode()
    source = _source(tmp_path, raw=source_raw)
    with pytest.raises(capture.BybitLiquidationCaptureError, match="secret") as caught:
        capture.validate_local_transcript(source)
    assert secret_value not in str(caught.value)

    payload_value = _transcript()
    subscribe = _decode_message(payload_value, 0)
    subscribe["req_id"] = secret_value
    payload_raw = json.dumps(subscribe, separators=(",", ":")).replace(
        secret_value, escaped
    ).encode()
    payload_value["messages"][0]["payload_base64"] = base64.b64encode(
        payload_raw
    ).decode()
    payload_source = _source(
        tmp_path, payload_value, directory="operator_escaped_payload_input"
    )
    with pytest.raises(capture.BybitLiquidationCaptureError, match="secret") as caught:
        capture.validate_local_transcript(payload_source)
    assert secret_value not in str(caught.value)

    ack_value = _transcript()
    ack = _decode_message(ack_value, 1)
    ack["conn_id"] = secret_value
    ack_raw = json.dumps(ack, separators=(",", ":")).replace(
        secret_value, escaped
    ).encode()
    ack_value["messages"][1]["payload_base64"] = base64.b64encode(ack_raw).decode()
    ack_source = _source(
        tmp_path, ack_value, directory="operator_escaped_ack_input"
    )
    with pytest.raises(capture.BybitLiquidationCaptureError, match="secret") as caught:
        capture.validate_local_transcript(ack_source)
    assert secret_value not in str(caught.value)


@pytest.mark.parametrize("lineage", ("operator.fixture.capture", "test:operator"))
def test_fixture_and_test_lineage_provenance_is_rejected(
    tmp_path: Path,
    lineage: str,
) -> None:
    value = _transcript()
    value["source_lineage_id"] = lineage
    source = _source(tmp_path, value)

    with pytest.raises(capture.BybitLiquidationCaptureError, match="lineage_rejected"):
        capture.validate_local_transcript(source)


@pytest.mark.parametrize(
    ("mutate", "reason"),
    (
        (lambda row: row.update(coverage_complete=True), "contract_invalid"),
        (lambda row: row.update(transport_claims_included=True), "contract_invalid"),
        (lambda row: row.update(tls_claims_included=True), "contract_invalid"),
        (lambda row: row.update(stream_continuity_claimed=True), "contract_invalid"),
        (lambda row: row.update(schema_version=True), "contract_invalid"),
        (
            lambda row: row["instrument"].update(liquidity_rank=True),
            "instrument_schema_invalid",
        ),
        (
            lambda row: row["messages"][0].update(sequence=True),
            "message_order_invalid",
        ),
        (
            lambda row: row["messages"][0].update(payload_base64="not base64"),
            "base64_invalid",
        ),
        (
            lambda row: row["messages"][2].update(
                observed_at="2026-07-18T07:45:00Z"
            ),
            "message_clock_invalid",
        ),
        (
            lambda row: row["instrument"].update(launch_time_ms=1784360639500),
            "instrument_clock_invalid",
        ),
    ),
)
def test_transcript_schema_units_clocks_and_claims_fail_closed(
    tmp_path: Path,
    mutate: object,
    reason: str,
) -> None:
    value = _transcript()
    mutate(value)
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    source = _source(tmp_path, value)

    with pytest.raises(capture.BybitLiquidationCaptureError, match=reason):
        capture.import_bybit_liquidation_transcript(
            artifact_base,
            transcript_path=source,
            confirm=True,
        )
    assert list(artifact_base.iterdir()) == []


def test_auth_identity_ack_and_empty_event_payloads_are_rejected(tmp_path: Path) -> None:
    cases: list[tuple[dict[str, object], str]] = []

    auth = _transcript()
    _replace_message(auth, 0, {"op": "auth", "args": ["key", "signature"]})
    cases.append((auth, "secret_or_auth_material_rejected"))

    mismatch = _transcript()
    ack = _decode_message(mismatch, 1)
    ack["req_id"] = "different-request"
    _replace_message(mismatch, 1, ack)
    cases.append((mismatch, "subscribe_ack_invalid"))

    wrong_identity = _transcript()
    data = _decode_message(wrong_identity, 2)
    data["topic"] = "allLiquidation.ETHUSDT"
    _replace_message(wrong_identity, 2, data)
    cases.append((wrong_identity, "liquidation_data_invalid"))

    empty = _transcript()
    data = _decode_message(empty, 2)
    data["data"] = []
    _replace_message(empty, 2, data)
    cases.append((empty, "liquidation_data_invalid"))

    for index, (value, reason) in enumerate(cases, start=1):
        case_root = tmp_path / f"operator_case_{index}"
        case_root.mkdir()
        artifact_base = case_root / "artifacts"
        artifact_base.mkdir()
        source = _source(case_root, value)
        with pytest.raises(capture.BybitLiquidationCaptureError, match=reason):
            capture.import_bybit_liquidation_transcript(
                artifact_base,
                transcript_path=source,
                confirm=True,
            )


def test_duplicate_data_payload_and_provider_clock_regression_are_rejected(
    tmp_path: Path,
) -> None:
    duplicate = _transcript()
    messages = duplicate["messages"]
    assert isinstance(messages, list)
    fourth = deepcopy(messages[2])
    fourth["sequence"] = 4
    fourth["observed_at"] = "2026-07-18T07:44:00.275Z"
    messages.append(fourth)

    within_message = _transcript()
    payload = _decode_message(within_message, 2)
    payload["data"].append(deepcopy(payload["data"][0]))
    _replace_message(within_message, 2, payload)

    regression = _transcript()
    messages = regression["messages"]
    assert isinstance(messages, list)
    prior = _decode_message(regression, 2)
    prior["ts"] = 1784360639000
    prior["data"][0]["T"] = 1784360638500
    fourth = {
        "sequence": 4,
        "direction": "server_to_client",
        "observed_at": "2026-07-18T07:44:00.275Z",
        "payload_base64": base64.b64encode(
            json.dumps(prior, separators=(",", ":")).encode()
        ).decode(),
    }
    messages.append(fourth)

    for index, (value, reason) in enumerate(
        (
            (duplicate, "duplicate_data_payload_rejected"),
            (within_message, "duplicate_provider_occurrence_rejected"),
            (regression, "provider_message_clock_regression"),
        ),
        start=1,
    ):
        case_root = tmp_path / f"operator_case_{index}"
        case_root.mkdir()
        artifact_base = case_root / "artifacts"
        artifact_base.mkdir()
        source = _source(case_root, value)
        with pytest.raises(capture.BybitLiquidationCaptureError, match=reason):
            capture.import_bybit_liquidation_transcript(
                artifact_base,
                transcript_path=source,
                confirm=True,
            )


def test_type_and_decimal_changed_duplicate_provider_occurrence_is_rejected(
    tmp_path: Path,
) -> None:
    value = _transcript()
    messages = value["messages"]
    assert isinstance(messages, list)
    repeated = _decode_message(value, 2)
    repeated["ts"] = str(repeated["ts"])
    repeated["data"][0]["T"] = str(repeated["data"][0]["T"])
    repeated["data"][0]["v"] = "0.50"
    messages.append(
        {
            "sequence": 4,
            "direction": "server_to_client",
            "observed_at": "2026-07-18T07:44:00.275Z",
            "payload_base64": base64.b64encode(
                json.dumps(repeated, indent=2, sort_keys=True).encode()
            ).decode(),
        }
    )
    source = _source(tmp_path, value)

    with pytest.raises(
        capture.BybitLiquidationCaptureError,
        match="duplicate_provider_occurrence",
    ):
        capture.validate_local_transcript(source)


def test_nonfinite_exponent_fails_as_closed_capture_error(tmp_path: Path) -> None:
    value = _transcript()
    data = base64.b64decode(value["messages"][2]["payload_base64"])
    data = data.replace(b'"ts":1784360640000', b'"ts":1e9999')
    value["messages"][2]["payload_base64"] = base64.b64encode(data).decode()
    source = _source(tmp_path, value)

    with pytest.raises(capture.BybitLiquidationCaptureError, match="non_finite"):
        capture.validate_local_transcript(source)


def test_deeply_nested_json_fails_as_closed_capture_error(tmp_path: Path) -> None:
    raw = b'{"nested":' + (b"[" * 10_000) + b"0" + (b"]" * 10_000) + b"}"
    source = _source(tmp_path, raw=raw)

    with pytest.raises(
        capture.BybitLiquidationCaptureError,
        match="source_transcript_json_invalid",
    ):
        capture.validate_local_transcript(source)


def _large_event_transcript(total_events: int) -> dict[str, object]:
    assert 1 <= total_events <= capture.MAX_TOTAL_EVENTS + 1
    value = _transcript()
    messages = value["messages"]
    assert isinstance(messages, list)
    template = _decode_message(value, 2)
    first_count = min(total_events, 1_000)
    first_row = template["data"][0]
    template["data"] = []
    for index in range(first_count):
        row = deepcopy(first_row)
        row["p"] = str(120_000 + index)
        template["data"].append(row)
    _replace_message(value, 2, template)
    remaining = total_events - first_count
    if remaining:
        later = deepcopy(template)
        later["ts"] += 100
        later["data"] = []
        for index in range(first_count, total_events):
            row = deepcopy(first_row)
            row["p"] = str(120_000 + index)
            later["data"].append(row)
        messages.append(
            {
                "sequence": 4,
                "direction": "server_to_client",
                "observed_at": "2026-07-18T07:44:00.290Z",
                "payload_base64": base64.b64encode(
                    json.dumps(later, separators=(",", ":")).encode()
                ).decode(),
            }
        )
    return value


def test_total_event_and_every_derived_artifact_size_are_bounded(tmp_path: Path) -> None:
    bounded = _large_event_transcript(capture.MAX_TOTAL_EVENTS)
    bounded_source = _source(tmp_path, bounded)
    _path, raw = capture._read_operator_source(bounded_source)
    prepared = capture._prepare_transcript(raw)
    payloads = capture._capture_payloads(prepared)

    assert len(prepared["events"]) == capture.MAX_TOTAL_EVENTS
    assert all(
        len(payload) <= (
            capture.MAX_PAYLOAD_BYTES
            if name.startswith("application_payload_")
            else capture.MAX_SOURCE_BYTES
        )
        for name, _role, payload in payloads
    )

    over_root = tmp_path / "operator_over_bound"
    over_root.mkdir()
    over_source = _source(
        over_root,
        _large_event_transcript(capture.MAX_TOTAL_EVENTS + 1),
    )
    with pytest.raises(capture.BybitLiquidationCaptureError, match="event_bound"):
        capture.validate_local_transcript(over_source)


def test_duplicate_json_and_nonfinite_numbers_are_rejected(tmp_path: Path) -> None:
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    original = capture._smoke_transcript()
    duplicate = original.replace(
        b'"schema_id": "decision_radar.bybit_liquidation_operator_transcript",',
        (
            b'"schema_id": "decision_radar.bybit_liquidation_operator_transcript",'
            b'\n  "schema_id": "duplicate",'
        ),
        1,
    )
    for index, (raw, reason) in enumerate(
        (
            (duplicate, "json_duplicate_key"),
            (original.replace(b'"liquidity_rank": 1', b'"liquidity_rank": NaN'), "non_finite"),
        ),
        start=1,
    ):
        source = _source(tmp_path, raw=raw, directory=f"operator_input_{index}")
        with pytest.raises(capture.BybitLiquidationCaptureError, match=reason):
            capture.import_bybit_liquidation_transcript(
                artifact_base,
                transcript_path=source,
                confirm=True,
            )


def test_bundle_fingerprint_inventory_symlink_and_hardlink_checks_fail_closed(
    tmp_path: Path,
) -> None:
    roots = [tmp_path / f"operator_case_{index}" for index in range(1, 5)]
    for root in roots:
        root.mkdir()

    base, _source_path, result = _import(roots[0])
    namespace = str(result["artifact_namespace"])
    payload = base / namespace / "application_payload_003.bin"
    payload.write_bytes(payload.read_bytes() + b" ")
    with pytest.raises(capture.BybitLiquidationCaptureError, match="fingerprint"):
        capture.validate_bybit_liquidation_capture(base, namespace=namespace)

    base, _source_path, result = _import(roots[1])
    namespace = str(result["artifact_namespace"])
    payload = base / namespace / "application_payload_003.bin"
    os.link(payload, roots[1] / "outside_payload.bin")
    with pytest.raises(capture.BybitLiquidationCaptureError, match="unreadable"):
        capture.validate_bybit_liquidation_capture(base, namespace=namespace)

    base, _source_path, result = _import(roots[2])
    namespace = str(result["artifact_namespace"])
    (base / namespace / "unmanifested.bin").write_bytes(b"unexpected")
    with pytest.raises(capture.BybitLiquidationCaptureError, match="unmanifested"):
        capture.validate_bybit_liquidation_capture(base, namespace=namespace)

    base, _source_path, result = _import(roots[3])
    namespace = str(result["artifact_namespace"])
    payload = base / namespace / "application_payload_003.bin"
    outside = roots[3] / "outside_payload.bin"
    outside.write_bytes(payload.read_bytes())
    payload.unlink()
    payload.symlink_to(outside)
    with pytest.raises(capture.BybitLiquidationCaptureError, match="unreadable"):
        capture.validate_bybit_liquidation_capture(base, namespace=namespace)


def test_operator_canonical_asset_claim_remains_explicitly_unverified(
    tmp_path: Path,
) -> None:
    value = _transcript()
    value["instrument"]["canonical_asset_id"] = "ethereum"
    artifact_base, _source_path, result = _import(tmp_path, value)
    namespace_dir = artifact_base / str(result["artifact_namespace"])
    artifacts = [
        json.loads((namespace_dir / name).read_text())
        for name in (
            capture.LEDGER_FILENAME,
            capture.EVENTS_FILENAME,
            capture.MANIFEST_FILENAME,
            capture.RECEIPT_FILENAME,
        )
    ]

    assert result["canonical_identity_status"] == "operator_attested_unverified"
    assert result["canonical_identity_verified"] is False
    assert result["operator_supplied"] is True
    assert result["genuine_capture"] is False
    for artifact in artifacts:
        assert artifact["canonical_asset_id"] == "ethereum"
        assert artifact["canonical_identity_status"] == (
            "operator_attested_unverified"
        )
        assert artifact["canonical_identity_verified"] is False
        assert artifact["evidence_authority_eligible"] is False
        assert artifact["directional_authority"] is False
    event = artifacts[1]["events"][0]
    assert event["canonical_asset_id"] == "ethereum"
    assert event["canonical_identity_status"] == "operator_attested_unverified"
    assert event["canonical_identity_verified"] is False
    assert event["economic_dedupe_authority"] is False


def test_interrupted_staging_write_does_not_poison_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    source = _source(tmp_path)
    prospective = capture.validate_local_transcript(source)
    original = capture.capture_io._write_leaf
    calls = 0

    def interrupted(directory_fd: int, name: str, raw: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("injected interruption")
        original(directory_fd, name, raw)

    monkeypatch.setattr(capture.capture_io, "_write_leaf", interrupted)
    with pytest.raises(capture.BybitLiquidationCaptureError, match="publication_failed"):
        capture.import_bybit_liquidation_transcript(
            artifact_base,
            transcript_path=source,
            confirm=True,
        )
    assert not (artifact_base / str(prospective["artifact_namespace"])).exists()
    quarantines = list(artifact_base.glob("tmp_bybit_liquidation_stage_*"))
    assert len(quarantines) == 1
    assert quarantines[0].is_dir()
    assert len(list(quarantines[0].iterdir())) == 2

    monkeypatch.setattr(capture.capture_io, "_write_leaf", original)
    retried = capture.import_bybit_liquidation_transcript(
        artifact_base,
        transcript_path=source,
        confirm=True,
    )
    assert retried["status"] == "complete"
    assert retried["writes_performed"] is True
    assert quarantines[0].is_dir()


def test_staging_path_swap_fails_without_mutating_attacker_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    source = _source(tmp_path)
    prospective = capture.validate_local_transcript(source)
    final_name = str(prospective["artifact_namespace"])
    original_noreplace = capture.capture_io._rename_directory_noreplace
    swapped = False
    stolen_name: str | None = None

    def swapping_noreplace(
        base_fd: int,
        source_name: str,
        destination_name: str,
    ) -> bool:
        nonlocal stolen_name, swapped
        if destination_name == final_name and not swapped:
            swapped = True
            stolen_name = f"{source_name}.stolen"
            os.rename(
                source_name,
                stolen_name,
                src_dir_fd=base_fd,
                dst_dir_fd=base_fd,
            )
            os.mkdir(source_name, 0o700, dir_fd=base_fd)
            replacement_fd = os.open(
                source_name,
                os.O_RDONLY | os.O_DIRECTORY,
                dir_fd=base_fd,
            )
            try:
                poison_fd = os.open(
                    "poison.bin",
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=replacement_fd,
                )
                os.close(poison_fd)
            finally:
                os.close(replacement_fd)
        return original_noreplace(base_fd, source_name, destination_name)

    monkeypatch.setattr(
        capture.capture_io,
        "_rename_directory_noreplace",
        swapping_noreplace,
    )
    with pytest.raises(capture.BybitLiquidationCaptureError, match="identity_drift"):
        capture.import_bybit_liquidation_transcript(
            artifact_base,
            transcript_path=source,
            confirm=True,
        )
    assert swapped is True
    assert stolen_name is not None
    assert (artifact_base / stolen_name).is_dir()
    assert (artifact_base / final_name / "poison.bin").is_file()

    shutil.rmtree(artifact_base / final_name)
    monkeypatch.setattr(
        capture.capture_io,
        "_rename_directory_noreplace",
        original_noreplace,
    )
    retried = capture.import_bybit_liquidation_transcript(
        artifact_base,
        transcript_path=source,
        confirm=True,
    )
    assert retried["status"] == "complete"
    assert retried["artifact_namespace"] == final_name
    assert (artifact_base / stolen_name).is_dir()


def test_native_no_replace_preserves_concurrent_empty_final(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    original_noreplace = capture.capture_io._rename_directory_noreplace
    raced_identity: tuple[int, int] | None = None

    def create_peer_then_publish(
        base_fd: int,
        source_name: str,
        destination_name: str,
    ) -> bool:
        nonlocal raced_identity
        os.mkdir(destination_name, 0o700, dir_fd=base_fd)
        peer = os.stat(destination_name, dir_fd=base_fd, follow_symlinks=False)
        raced_identity = (peer.st_dev, peer.st_ino)
        return original_noreplace(base_fd, source_name, destination_name)

    monkeypatch.setattr(
        capture.capture_io,
        "_rename_directory_noreplace",
        create_peer_then_publish,
    )
    with capture.capture_io.hold_anchored_base(
        artifact_base,
        exclusive=True,
    ) as anchored:
        created = capture.capture_io.publish_bundle_atomically(
            anchored,
            namespace="final_capture",
            files=(("payload.bin", b"owned"),),
        )

    peer = (artifact_base / "final_capture").stat()
    assert created is False
    assert raced_identity == (peer.st_dev, peer.st_ino)
    assert list((artifact_base / "final_capture").iterdir()) == []
    quarantines = list(artifact_base.glob("tmp_bybit_liquidation_stage_*"))
    assert len(quarantines) == 1
    assert (quarantines[0] / "payload.bin").read_bytes() == b"owned"


def test_replaced_staging_directory_is_never_removed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    replacement_identity: tuple[int, int] | None = None
    stolen_name: str | None = None

    def replace_stage_then_interrupt(
        base_fd: int,
        source_name: str,
        _destination_name: str,
    ) -> bool:
        nonlocal replacement_identity, stolen_name
        stolen_name = f"{source_name}.stolen"
        os.rename(
            source_name,
            stolen_name,
            src_dir_fd=base_fd,
            dst_dir_fd=base_fd,
        )
        os.mkdir(source_name, 0o700, dir_fd=base_fd)
        replacement = os.stat(
            source_name,
            dir_fd=base_fd,
            follow_symlinks=False,
        )
        replacement_identity = (replacement.st_dev, replacement.st_ino)
        raise RuntimeError("injected stage substitution")

    monkeypatch.setattr(
        capture.capture_io,
        "_rename_directory_noreplace",
        replace_stage_then_interrupt,
    )
    with pytest.raises(
        capture.capture_io.BybitLiquidationCaptureIOError,
        match="staging_quarantine_identity_drift",
    ):
        with capture.capture_io.hold_anchored_base(
            artifact_base,
            exclusive=True,
        ) as anchored:
            capture.capture_io.publish_bundle_atomically(
                anchored,
                namespace="final_capture",
                files=(("payload.bin", b"owned"),),
            )

    assert stolen_name is not None
    assert (artifact_base / stolen_name / "payload.bin").read_bytes() == b"owned"
    replacements = [
        path
        for path in artifact_base.glob("tmp_bybit_liquidation_stage_*")
        if path.name != stolen_name
    ]
    assert len(replacements) == 1
    replacement = replacements[0].stat()
    assert replacement_identity == (replacement.st_dev, replacement.st_ino)
    assert list(replacements[0].iterdir()) == []


def test_replaced_staging_leaf_is_never_unlinked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    original_write = capture.capture_io._write_leaf

    def replace_leaf_then_interrupt(
        directory_fd: int,
        name: str,
        raw: bytes,
    ) -> None:
        original_write(directory_fd, name, raw)
        os.rename(
            name,
            "owned_original.bin",
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        replacement_fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=directory_fd,
        )
        try:
            os.write(replacement_fd, b"replacement")
        finally:
            os.close(replacement_fd)
        raise RuntimeError("injected leaf substitution")

    monkeypatch.setattr(capture.capture_io, "_write_leaf", replace_leaf_then_interrupt)
    with pytest.raises(
        capture.capture_io.BybitLiquidationCaptureIOError,
        match="directory_inventory_bound_exceeded",
    ):
        with capture.capture_io.hold_anchored_base(
            artifact_base,
            exclusive=True,
        ) as anchored:
            capture.capture_io.publish_bundle_atomically(
                anchored,
                namespace="final_capture",
                files=(("payload.bin", b"owned"),),
            )

    quarantines = list(artifact_base.glob("tmp_bybit_liquidation_stage_*"))
    assert len(quarantines) == 1
    assert (quarantines[0] / "payload.bin").read_bytes() == b"replacement"
    assert (quarantines[0] / "owned_original.bin").read_bytes() == b"owned"


def test_unsupported_native_no_replace_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    monkeypatch.setattr(capture.capture_io.sys, "platform", "unsupported")

    with pytest.raises(
        capture.capture_io.BybitLiquidationCaptureIOError,
        match="bundle_no_replace_rename_unsupported",
    ):
        with capture.capture_io.hold_anchored_base(
            artifact_base,
            exclusive=True,
        ) as anchored:
            capture.capture_io.publish_bundle_atomically(
                anchored,
                namespace="final_capture",
                files=(("payload.bin", b"owned"),),
            )

    assert not (artifact_base / "final_capture").exists()
    quarantines = list(artifact_base.glob("tmp_bybit_liquidation_stage_*"))
    assert len(quarantines) == 1
    assert (quarantines[0] / "payload.bin").read_bytes() == b"owned"


def test_validation_rejects_ancestor_swap_instead_of_following_evil_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holder = tmp_path / "holder"
    holder.mkdir()
    artifact_base, _source_path, result = _import(holder)
    namespace = str(result["artifact_namespace"])
    evil_holder = tmp_path / "evilholder"
    evil_base = evil_holder / "artifacts"
    evil_base.mkdir(parents=True)
    shutil.copytree(artifact_base / namespace, evil_base / namespace)
    original_open_chain = capture.capture_io._open_directory_chain
    swapped = False

    def swapping_open_chain(directory: Path) -> int:
        nonlocal swapped
        if directory == artifact_base and not swapped:
            swapped = True
            holder.rename(tmp_path / "holder_original")
            holder.symlink_to(evil_holder, target_is_directory=True)
        return original_open_chain(directory)

    monkeypatch.setattr(
        capture.capture_io,
        "_open_directory_chain",
        swapping_open_chain,
    )
    with pytest.raises(capture.BybitLiquidationCaptureError, match="unreadable"):
        capture.validate_bybit_liquidation_capture(
            artifact_base,
            namespace=namespace,
        )
    assert swapped is True


def test_existing_namespace_reuse_requires_full_capture_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    source = _source(tmp_path)

    monkeypatch.setattr(
        capture.capture_io,
        "publish_bundle_atomically",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        capture,
        "_validate_bybit_liquidation_capture_at",
        lambda *_args, **_kwargs: {
            "capture_id": "0" * 64,
            "source_transcript_sha256": "0" * 64,
        },
    )

    with pytest.raises(capture.BybitLiquidationCaptureError, match="identity_collision"):
        capture.import_bybit_liquidation_transcript(
            artifact_base,
            transcript_path=source,
            confirm=True,
        )


@pytest.mark.parametrize("swap_after_publish", [False, True])
def test_import_holds_one_base_across_publish_and_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    swap_after_publish: bool,
) -> None:
    holder = tmp_path / "holder"
    artifact_base = holder / "artifacts"
    artifact_base.mkdir(parents=True)
    evil_holder = tmp_path / "evilholder"
    evil_base = evil_holder / "artifacts"
    evil_base.mkdir(parents=True)
    source = _source(tmp_path)
    original_publish = capture.capture_io.publish_bundle_atomically
    swapped = False

    def swapping_publish(*args: object, **kwargs: object) -> bool:
        nonlocal swapped
        if not swap_after_publish:
            holder.rename(tmp_path / "holder_original")
            holder.symlink_to(evil_holder, target_is_directory=True)
            swapped = True
        created = original_publish(*args, **kwargs)
        if swap_after_publish:
            holder.rename(tmp_path / "holder_original")
            holder.symlink_to(evil_holder, target_is_directory=True)
            swapped = True
        return created

    monkeypatch.setattr(
        capture.capture_io,
        "publish_bundle_atomically",
        swapping_publish,
    )
    with pytest.raises(capture.BybitLiquidationCaptureError, match="identity_drift"):
        capture.import_bybit_liquidation_transcript(
            artifact_base,
            transcript_path=source,
            confirm=True,
        )
    assert swapped is True
    assert list(evil_base.iterdir()) == []


def test_concurrent_same_capture_import_is_one_write_and_one_reuse(
    tmp_path: Path,
) -> None:
    artifact_base = tmp_path / "artifacts"
    artifact_base.mkdir()
    source = _source(tmp_path)

    def import_once() -> dict[str, object]:
        return capture.import_bybit_liquidation_transcript(
            artifact_base,
            transcript_path=source,
            confirm=True,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: import_once(), range(2)))

    assert len({str(row["capture_id"]) for row in results}) == 1
    assert sorted(bool(row["writes_performed"]) for row in results) == [False, True]
    assert sorted(bool(row["idempotent_reuse"]) for row in results) == [False, True]
    assert len(list(artifact_base.iterdir())) == 1


def test_status_never_guesses_latest_and_smoke_is_offline_and_disposable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_base, _source_path, result = _import(tmp_path)

    missing = capture.bybit_liquidation_capture_status(
        artifact_base,
        namespace=None,
    )
    exact = capture.bybit_liquidation_capture_status(
        artifact_base,
        namespace=str(result["artifact_namespace"]),
    )

    assert missing["status"] == "unavailable"
    assert missing["reason"] == "capture_namespace_required"
    assert missing["operator_supplied"] is None
    _assert_closed_provenance(missing, source_authority="unavailable")
    assert exact["status"] == "complete"
    assert exact["capture_mode"] == "operator_import"
    assert exact["operator_supplied"] is True
    assert exact["genuine_capture"] is False
    assert exact["project_transport_capture"] is False
    assert exact["project_websocket_listener"] is False
    assert exact["latest_pointer_published"] is False
    _assert_closed_provenance(
        exact,
        source_authority="operator_attested_unverified_application_payloads",
    )

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("offline capture smoke must not open a socket")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    report = capture.run_capture_smoke()

    assert report["status"] == "ok"
    assert report["capture_mode"] == "synthetic_smoke"
    assert report["operator_supplied"] is False
    assert report["genuine_capture"] is False
    assert report["idempotence_validated"] is True
    assert report["smoke_namespace_retained"] is False
    assert report["artifact_persisted"] is False
    assert report["disposable_artifact_write_count"] == 8
    assert report["writes_performed"] is True
    _assert_closed_provenance(
        report,
        source_authority="synthetic_smoke_unverified_application_payloads",
    )
    assert report["coverage_status"] == "observed_messages_only"
    assert report["coverage_complete"] is False

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "crypto_rsi_scanner.event_alpha.operations.bybit_liquidation_capture",
            "capture-smoke",
        ],
        cwd=Path(__file__).resolve().parents[2],
        check=True,
        capture_output=True,
        text=True,
    )
    cli_report = json.loads(completed.stdout)
    assert cli_report["status"] == "ok"
    assert cli_report["capture_mode"] == "synthetic_smoke"
    assert cli_report["operator_supplied"] is False
