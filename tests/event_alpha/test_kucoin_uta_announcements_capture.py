"""Current KuCoin UTA immutable capture-boundary regressions."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil

import pytest

from crypto_rsi_scanner.event_alpha.operations.kucoin_uta_announcements_capture import (
    CAPTURE_MODE_FIXTURE,
    CAPTURE_MODE_LIVE,
    CONTRACT_VERSION,
    KuCoinUtaAnnouncementCaptureError,
    KuCoinUtaAnnouncementPageCapture,
    persist_capture,
    prepare_capture,
    run_fixture_capture_smoke,
    validate_capture,
)


START = "2026-07-19T00:00:00Z"
END = "2026-07-19T01:35:00Z"
FIXTURE_DIR = (
    Path(__file__).resolve().parents[2] / "fixtures" / "kucoin_uta_announcements"
)


def _url(page: int) -> str:
    return (
        "https://api.kucoin.com/api/ua/v1/market/announcement?"
        f"language=en_US&type=latest-announcements&pageNumber={page}&pageSize=50&"
        "startTime=1784419200000&endTime=1784424900000"
    )


def _pages() -> tuple[KuCoinUtaAnnouncementPageCapture, ...]:
    return (
        KuCoinUtaAnnouncementPageCapture(
            page_number=1,
            request_url=_url(1),
            request_started_at="2026-07-19T01:35:00.100000Z",
            response_headers_at="2026-07-19T01:35:00.500000Z",
            response_body_read_at="2026-07-19T01:35:01Z",
            request_lineage_id="fixture.kucoin.uta.capture.page1",
            status_code=200,
            content_type="application/json; charset=utf-8",
            redirect_count=0,
            retry_count=0,
            body=(FIXTURE_DIR / "page_1.json").read_bytes(),
        ),
        KuCoinUtaAnnouncementPageCapture(
            page_number=2,
            request_url=_url(2),
            request_started_at="2026-07-19T01:35:01.100000Z",
            response_headers_at="2026-07-19T01:35:01.500000Z",
            response_body_read_at="2026-07-19T01:35:02Z",
            request_lineage_id="fixture.kucoin.uta.capture.page2",
            status_code=200,
            content_type="application/json",
            redirect_count=0,
            retry_count=0,
            body=(FIXTURE_DIR / "page_2.json").read_bytes(),
        ),
    )


def _persist(base: Path, pages=None):
    return persist_capture(
        base,
        _pages() if pages is None else pages,
        start_time=START,
        end_time=END,
        capture_mode=CAPTURE_MODE_FIXTURE,
        confirm=True,
    )


def test_prepare_is_pure_complete_current_uta_and_never_authoritative() -> None:
    prepared = prepare_capture(
        _pages(),
        start_time=START,
        end_time=END,
        capture_mode=CAPTURE_MODE_FIXTURE,
    )

    assert prepared.summary["status"] == "complete"
    assert prepared.summary["contract_version"] == CONTRACT_VERSION
    assert prepared.summary["response_contract_version"] == (
        "crypto_radar_kucoin_uta_announcements_v1"
    )
    assert prepared.summary["endpoint"] == (
        "GET https://api.kucoin.com/api/ua/v1/market/announcement"
    )
    assert prepared.summary["coverage_complete"] is True
    assert prepared.summary["completion_evidence"] == "all_reported_pages_observed"
    assert prepared.summary["accepted_announcement_count"] == 3
    assert prepared.summary["request_count"] == 2
    assert prepared.summary["requested_page_size"] == 50
    assert prepared.summary["response_page_size"] == 2
    assert prepared.summary["provider_adjusted_page_size"] is True
    assert prepared.summary["transport_captured_by_project"] is False
    assert prepared.summary["runtime_provider_authorized_at_capture"] is False
    assert prepared.summary["provider_calls_recorded"] == 0
    assert prepared.summary["input_quality_eligible"] is False
    assert prepared.summary["evidence_authority_eligible"] is False
    assert prepared.summary["protocol_v2_evidence_eligible"] is False
    assert prepared.summary["pointer_publication_available"] is False
    assert prepared.summary["writes_performed"] is False


def test_current_uta_namespace_is_distinct_from_historical_capture() -> None:
    prepared = prepare_capture(
        _pages(),
        start_time=START,
        end_time=END,
        capture_mode=CAPTURE_MODE_FIXTURE,
    )

    assert prepared.namespace.startswith("radar_kucoin_uta_announcements_")
    assert not prepared.namespace.startswith("radar_kucoin_announcements_")


def test_live_mode_is_unavailable_until_transport_is_implemented() -> None:
    with pytest.raises(
        KuCoinUtaAnnouncementCaptureError,
        match="live_capture_transport_not_implemented",
    ):
        prepare_capture(
            _pages(),
            start_time=START,
            end_time=END,
            capture_mode=CAPTURE_MODE_LIVE,
        )


def test_persistence_requires_explicit_confirmation(tmp_path: Path) -> None:
    with pytest.raises(
        KuCoinUtaAnnouncementCaptureError,
        match="explicit_confirmation_required",
    ):
        persist_capture(
            tmp_path,
            _pages(),
            start_time=START,
            end_time=END,
            capture_mode=CAPTURE_MODE_FIXTURE,
        )
    assert list(tmp_path.iterdir()) == []


def test_persist_and_strict_doctor_rederive_exact_current_uta_artifacts(
    tmp_path: Path,
) -> None:
    result = _persist(tmp_path)
    namespace = result["artifact_namespace"]
    directory = tmp_path / namespace

    assert result["created"] is True
    assert result["writes_performed"] is True
    assert result["strict_doctor_status"] == "pass"
    assert set(path.name for path in directory.iterdir()) == {
        "response_page_001.json",
        "response_page_002.json",
        "request_ledger.json",
        "normalized_snapshot.json",
        "capture_manifest.json",
        "capture_completion_receipt.json",
    }
    ledger = json.loads((directory / "request_ledger.json").read_text())
    snapshot = json.loads((directory / "normalized_snapshot.json").read_text())
    assert ledger["schema_id"] == (
        "decision_radar.kucoin_uta_announcement_request_ledger"
    )
    assert ledger["path"] == "/api/ua/v1/market/announcement"
    assert ledger["response_contract_version"] == (
        "crypto_radar_kucoin_uta_announcements_v1"
    )
    assert ledger["pagination_policy"] == (
        "contiguous_pageNumber_from_one_using_response_totalPage"
    )
    assert ledger["requests"][0]["request_url"] == _url(1)
    assert ledger["requests"][1]["redirect_count"] == 0
    assert ledger["requests"][1]["retry_count"] == 0
    assert ledger["proxy_or_vpn_bypass_allowed"] is False
    assert snapshot["requested_page_size"] == 50
    assert snapshot["response_page_size"] == 2
    assert snapshot["provider_adjusted_page_size"] is True
    assert snapshot["response_sha256_by_page"] == {
        "1": hashlib.sha256(_pages()[0].body).hexdigest(),
        "2": hashlib.sha256(_pages()[1].body).hexdigest(),
    }
    assert validate_capture(tmp_path, namespace)["capture_id"] == result["capture_id"]


def test_identical_capture_is_idempotent(tmp_path: Path) -> None:
    first = _persist(tmp_path)
    second = _persist(tmp_path)

    assert second["artifact_namespace"] == first["artifact_namespace"]
    assert second["created"] is False
    assert second["idempotent"] is True
    assert second["writes_performed"] is False


def test_partial_prefix_remains_explicit_and_ineligible(tmp_path: Path) -> None:
    result = _persist(tmp_path, _pages()[:1])

    assert result["status"] == "partial"
    assert result["coverage_complete"] is False
    assert result["completion_evidence"] == "missing_reported_pages"
    assert result["accepted_announcement_count"] == 2
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
        (
            "content_type",
            "application/json;\nsecret",
            "capture_transport_contract_invalid",
        ),
        (
            "request_url",
            "https://api.kucoin.com/api/v3/announcements",
            "capture_request_url_invalid",
        ),
    ],
)
def test_transport_drift_fails_before_write(
    tmp_path: Path,
    field: str,
    value: object,
    reason: str,
) -> None:
    pages = list(_pages())
    row = pages[0]
    pages[0] = KuCoinUtaAnnouncementPageCapture(**{**row.__dict__, field: value})

    with pytest.raises(KuCoinUtaAnnouncementCaptureError, match=reason):
        _persist(tmp_path, tuple(pages))
    assert list(tmp_path.iterdir()) == []


def test_page_identity_drift_fails_before_write(tmp_path: Path) -> None:
    pages = list(_pages())
    row = pages[1]
    pages[1] = KuCoinUtaAnnouncementPageCapture(
        **{**row.__dict__, "page_number": 3, "request_url": _url(3)}
    )

    with pytest.raises(
        KuCoinUtaAnnouncementCaptureError,
        match="capture_page_sequence_invalid",
    ):
        _persist(tmp_path, tuple(pages))
    assert list(tmp_path.iterdir()) == []


def test_response_mutation_fails_strict_doctor(tmp_path: Path) -> None:
    result = _persist(tmp_path)
    path = tmp_path / result["artifact_namespace"] / "response_page_001.json"
    path.write_bytes(path.read_bytes().replace(b"ALPHA", b"OMEGA", 1))

    with pytest.raises(
        KuCoinUtaAnnouncementCaptureError,
        match="capture_ledger_response_invalid",
    ):
        validate_capture(tmp_path, result["artifact_namespace"])


def test_extra_leaf_fails_strict_doctor(tmp_path: Path) -> None:
    result = _persist(tmp_path)
    directory = tmp_path / result["artifact_namespace"]
    (directory / "unexpected.json").write_text("{}\n")

    with pytest.raises(
        KuCoinUtaAnnouncementCaptureError,
        match="capture_artifact_set_invalid",
    ):
        validate_capture(tmp_path, result["artifact_namespace"])


def test_symlinked_capture_leaf_fails_closed(tmp_path: Path) -> None:
    result = _persist(tmp_path)
    directory = tmp_path / result["artifact_namespace"]
    target = directory / "response_page_001.json"
    outside = tmp_path / "outside.json"
    outside.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(outside)

    with pytest.raises(
        KuCoinUtaAnnouncementCaptureError,
        match="capture_artifact_leaf_invalid",
    ):
        validate_capture(tmp_path, result["artifact_namespace"])


def test_hardlinked_capture_leaf_fails_closed(tmp_path: Path) -> None:
    result = _persist(tmp_path)
    directory = tmp_path / result["artifact_namespace"]
    target = directory / "response_page_001.json"
    outside = tmp_path / "outside.json"
    shutil.copyfile(target, outside)
    target.unlink()
    os.link(outside, target)

    with pytest.raises(
        KuCoinUtaAnnouncementCaptureError,
        match="capture_artifact_leaf_invalid",
    ):
        validate_capture(tmp_path, result["artifact_namespace"])


def test_disposable_fixture_smoke_retains_no_artifacts() -> None:
    result = run_fixture_capture_smoke(FIXTURE_DIR)

    assert result["strict_doctor_status"] == "pass"
    assert result["fixture_artifacts_retained"] is False
    assert result["disposable_artifact_write_count"] == 6
    assert result["provider_calls_performed_by_smoke"] == 0
    assert result["writes_performed"] is True
    assert "artifact_path" not in result
