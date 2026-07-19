"""Immutable Bitget announcement capture boundary regressions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations.bitget_announcements_capture import (
    CAPTURE_MODE_FIXTURE,
    CAPTURE_MODE_LIVE,
    BitgetAnnouncementCaptureError,
    BitgetAnnouncementPageCapture,
    persist_capture,
    prepare_capture,
    run_fixture_capture_smoke,
    validate_capture,
)


START = "2026-07-19T00:00:00Z"
END = "2026-07-19T01:35:00Z"
FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "bitget_announcements"
CURSORS = (None, "900002", "900001")


def _url(cursor: str | None) -> str:
    value = (
        "https://api.bitget.com/api/v2/public/annoucements?"
        "startTime=1784419200000&endTime=1784424900000&limit=2&language=en_US"
    )
    return value if cursor is None else f"{value}&cursor={cursor}"


def _pages() -> tuple[BitgetAnnouncementPageCapture, ...]:
    bodies = tuple(path.read_bytes() for path in sorted(FIXTURE_DIR.glob("page_*.json")))
    return tuple(
        BitgetAnnouncementPageCapture(
            page_number=index,
            request_cursor=CURSORS[index - 1],
            request_url=_url(CURSORS[index - 1]),
            request_started_at=f"2026-07-19T01:35:0{index - 1}.100000Z",
            response_headers_at=f"2026-07-19T01:35:0{index - 1}.500000Z",
            response_body_read_at=f"2026-07-19T01:35:0{index}Z",
            request_lineage_id=f"fixture.bitget.capture.page{index}",
            status_code=200,
            content_type="application/json; charset=utf-8",
            redirect_count=0,
            retry_count=0,
            body=body,
        )
        for index, body in enumerate(bodies, start=1)
    )


def _persist(base: Path, pages=None):
    return persist_capture(
        base,
        _pages() if pages is None else pages,
        start_time=START,
        end_time=END,
        capture_mode=CAPTURE_MODE_FIXTURE,
        confirm=True,
        limit=2,
    )


def test_prepare_is_pure_complete_and_never_authoritative() -> None:
    prepared = prepare_capture(
        _pages(),
        start_time=START,
        end_time=END,
        capture_mode=CAPTURE_MODE_FIXTURE,
        limit=2,
    )

    assert prepared.summary["status"] == "complete"
    assert prepared.summary["coverage_complete"] is True
    assert prepared.summary["completion_evidence"] == (
        "explicit_empty_terminal_response"
    )
    assert prepared.summary["accepted_announcement_count"] == 3
    assert prepared.summary["request_count"] == 3
    assert prepared.summary["transport_captured_by_project"] is False
    assert prepared.summary["runtime_provider_authorized_at_capture"] is False
    assert prepared.summary["provider_calls_recorded"] == 0
    assert prepared.summary["input_quality_eligible"] is False
    assert prepared.summary["evidence_authority_eligible"] is False
    assert prepared.summary["protocol_v2_evidence_eligible"] is False
    assert prepared.summary["writes_performed"] is False


def test_live_mode_is_unavailable_until_transport_is_implemented() -> None:
    with pytest.raises(
        BitgetAnnouncementCaptureError,
        match="live_capture_transport_not_implemented",
    ):
        prepare_capture(
            _pages(),
            start_time=START,
            end_time=END,
            capture_mode=CAPTURE_MODE_LIVE,
            limit=2,
        )


def test_persistence_requires_explicit_confirmation(tmp_path: Path) -> None:
    with pytest.raises(
        BitgetAnnouncementCaptureError, match="explicit_confirmation_required"
    ):
        persist_capture(
            tmp_path,
            _pages(),
            start_time=START,
            end_time=END,
            capture_mode=CAPTURE_MODE_FIXTURE,
            limit=2,
        )
    assert list(tmp_path.iterdir()) == []


def test_persist_and_strict_doctor_rederive_exact_artifacts(tmp_path: Path) -> None:
    result = _persist(tmp_path)
    namespace = str(result["artifact_namespace"])
    directory = tmp_path / namespace

    assert result["created"] is True
    assert result["writes_performed"] is True
    assert result["strict_doctor_status"] == "pass"
    assert set(path.name for path in directory.iterdir()) == {
        "response_page_001.json",
        "response_page_002.json",
        "response_page_003.json",
        "request_ledger.json",
        "normalized_snapshot.json",
        "capture_manifest.json",
        "capture_completion_receipt.json",
    }
    ledger = json.loads((directory / "request_ledger.json").read_text())
    assert ledger["pagination_policy"] == (
        "last_annId_cursor_until_explicit_empty_response"
    )
    assert ledger["requests"][0]["request_cursor"] is None
    assert ledger["requests"][2]["request_cursor"] == "900001"
    assert ledger["requests"][2]["redirect_count"] == 0
    assert ledger["requests"][2]["retry_count"] == 0
    assert ledger["proxy_or_vpn_bypass_allowed"] is False
    assert validate_capture(tmp_path, namespace)["capture_id"] == result["capture_id"]


def test_identical_capture_is_idempotent(tmp_path: Path) -> None:
    first = _persist(tmp_path)
    second = _persist(tmp_path)

    assert second["artifact_namespace"] == first["artifact_namespace"]
    assert second["created"] is False
    assert second["idempotent"] is True
    assert second["writes_performed"] is False


def test_short_nonempty_prefix_remains_partial_and_ineligible(tmp_path: Path) -> None:
    result = _persist(tmp_path, _pages()[:2])

    assert result["status"] == "partial"
    assert result["coverage_complete"] is False
    assert result["completion_evidence"] == "not_observed"
    assert result["accepted_announcement_count"] == 3
    assert result["input_quality_eligible"] is False
    assert result["evidence_authority_eligible"] is False
    assert result["strict_doctor_status"] == "pass"


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("status_code", 429, "capture_transport_contract_invalid"),
        ("redirect_count", 1, "capture_transport_contract_invalid"),
        ("retry_count", 1, "capture_transport_contract_invalid"),
        ("redirect_count", False, "capture_transport_contract_invalid"),
        ("content_type", "text/html", "capture_transport_contract_invalid"),
        ("content_type", "application/json;\nsecret", "capture_transport_contract_invalid"),
        ("request_url", "https://example.com/api/v2/public/annoucements", "capture_request_url_invalid"),
    ],
)
def test_transport_drift_fails_before_write(
    tmp_path: Path, field: str, value: object, reason: str
) -> None:
    pages = list(_pages())
    row = pages[0]
    pages[0] = BitgetAnnouncementPageCapture(**{**row.__dict__, field: value})

    with pytest.raises(BitgetAnnouncementCaptureError, match=reason):
        _persist(tmp_path, tuple(pages))
    assert list(tmp_path.iterdir()) == []


def test_cursor_or_request_identity_drift_fails_before_write(tmp_path: Path) -> None:
    pages = list(_pages())
    row = pages[1]
    pages[1] = BitgetAnnouncementPageCapture(
        **{**row.__dict__, "request_cursor": "wrong"}
    )

    with pytest.raises(BitgetAnnouncementCaptureError, match="capture_request_url_invalid"):
        _persist(tmp_path, tuple(pages))
    assert list(tmp_path.iterdir()) == []


def test_response_mutation_fails_strict_doctor(tmp_path: Path) -> None:
    result = _persist(tmp_path)
    path = tmp_path / str(result["artifact_namespace"]) / "response_page_001.json"
    path.write_bytes(path.read_bytes().replace(b"ALPHA", b"OMEGA", 1))

    with pytest.raises(
        BitgetAnnouncementCaptureError, match="capture_ledger_response_invalid"
    ):
        validate_capture(tmp_path, str(result["artifact_namespace"]))


def test_extra_leaf_fails_strict_doctor(tmp_path: Path) -> None:
    result = _persist(tmp_path)
    directory = tmp_path / str(result["artifact_namespace"])
    (directory / "unexpected.json").write_text("{}\n")

    with pytest.raises(
        BitgetAnnouncementCaptureError, match="capture_artifact_set_invalid"
    ):
        validate_capture(tmp_path, str(result["artifact_namespace"]))


def test_symlink_leaf_fails_strict_doctor(tmp_path: Path) -> None:
    result = _persist(tmp_path)
    directory = tmp_path / str(result["artifact_namespace"])
    path = directory / "normalized_snapshot.json"
    path.unlink()
    path.symlink_to(FIXTURE_DIR / "page_1.json")

    with pytest.raises(
        BitgetAnnouncementCaptureError, match="capture_artifact_leaf_invalid"
    ):
        validate_capture(tmp_path, str(result["artifact_namespace"]))


def test_disposable_fixture_smoke_retains_no_artifacts() -> None:
    result = run_fixture_capture_smoke(FIXTURE_DIR)

    assert result["strict_doctor_status"] == "pass"
    assert result["fixture_artifacts_retained"] is False
    assert result["disposable_artifact_write_count"] == 7
    assert result["provider_calls_performed_by_smoke"] == 0
    assert result["writes_performed"] is True
    assert "artifact_path" not in result
