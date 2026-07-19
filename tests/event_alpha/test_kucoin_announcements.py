"""Closed offline KuCoin official-announcement contract regressions."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import socket

import pytest

from crypto_rsi_scanner.event_alpha.operations.kucoin_announcements import (
    MAX_RESPONSE_PAGES,
    KuCoinAnnouncementError,
    build_kucoin_announcement_request_plan,
    main,
    normalize_kucoin_announcement_pages,
    run_fixture_smoke,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "fixtures/kucoin_announcements"


def _payload(page: int) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / f"page_{page}.json").read_text(encoding="utf-8"))


def _body(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _snapshot(*, payloads: list[object] | None = None) -> object:
    rows = payloads or [_payload(1), _payload(2)]
    return normalize_kucoin_announcement_pages(
        [_body(row) for row in rows],
        acquired_at_by_page=[
            "2026-07-19T01:35:01Z",
            "2026-07-19T01:35:02Z",
        ][: len(rows)],
        request_lineage_ids=[
            "test.kucoin.page1",
            "test.kucoin.page2",
        ][: len(rows)],
        start_time="2026-07-19T00:00:00Z",
        end_time="2026-07-19T01:35:00Z",
    )


def test_request_plan_is_exact_bounded_public_and_non_executable() -> None:
    plan = build_kucoin_announcement_request_plan(
        start_time="2026-07-19T00:00:00Z",
        end_time="2026-07-19T01:35:00Z",
    )

    assert plan["provider"] == "kucoin_announcements"
    assert plan["method"] == "GET"
    assert plan["path"] == "/api/v3/announcements"
    assert plan["initial_query"] == {
        "currentPage": 1,
        "annType": "latest-announcements",
        "lang": "en_US",
        "pageSize": 50,
        "startTime": 1784419200000,
        "endTime": 1784424900000,
    }
    assert plan["maximum_request_count"] == MAX_RESPONSE_PAGES == 20
    assert plan["api_channel"] == "public"
    assert plan["api_permission"] == "NULL"
    assert plan["credentials_required"] is False
    assert plan["provider_call_authorized"] is False
    assert plan["provider_call_planned"] is False
    assert plan["provider_call_attempted"] is False
    assert plan["redirects_allowed"] is False
    assert plan["retries_allowed"] is False
    assert plan["directional_authority"] is False


def test_complete_projection_preserves_identity_types_clocks_bytes_and_safety() -> None:
    value = _snapshot().to_dict()

    assert value["schema_version"] == "crypto_radar.kucoin_announcements.v1"
    assert value["provider"] == "kucoin_announcements"
    assert value["source_class"] == "official_exchange"
    assert value["coverage_status"] == "complete"
    assert value["coverage_complete"] is True
    assert value["healthy_empty"] is False
    assert value["observed_pages"] == (1, 2)
    assert value["missing_pages"] == ()
    assert value["total_announcements_reported"] == 3
    assert value["accepted_announcement_count"] == 3
    assert value["requested_page_size"] == 50
    assert value["response_page_size"] == 2
    assert value["provider_adjusted_page_size"] is True
    assert len(value["response_sha256_by_page"]["1"]) == 64
    listing = value["announcements"][0]
    assert listing["announcement_id"] == 200003
    assert listing["announcement_types"] == (
        "latest-announcements",
        "new-listings",
    )
    assert listing["publication_at"] == "2026-07-19T01:32:00Z"
    assert listing["event_time"] is None
    assert listing["event_time_basis"] == "not_inferred_from_publication"
    assert listing["description_completeness"] == "provider_summary_not_full_article"
    assert listing["directional_authority"] is False
    assert value["provider_calls"] == 0
    assert value["writes"] == 0
    assert value["authorization_created"] is False
    assert value["route_or_score_effect"] is False
    assert value["protocol_v2_annex_bound"] is False
    assert value["protocol_v2_evidence_eligible"] is False
    assert value["research_only"] is True


def test_contiguous_prefix_is_partial_and_never_healthy_empty() -> None:
    value = _snapshot(payloads=[_payload(1)]).to_dict()

    assert value["coverage_status"] == "partial"
    assert value["coverage_complete"] is False
    assert value["healthy_empty"] is False
    assert value["missing_pages"] == (2,)
    assert value["accepted_announcement_count"] == 2
    assert value["total_announcements_reported"] == 3


def test_zero_rows_are_healthy_empty_only_with_complete_pagination() -> None:
    payload = {
        "code": "200000",
        "data": {
            "totalNum": 0,
            "totalPage": 0,
            "currentPage": 1,
            "pageSize": 15,
            "items": [],
        },
    }

    value = _snapshot(payloads=[payload]).to_dict()

    assert value["coverage_status"] == "complete"
    assert value["coverage_complete"] is True
    assert value["healthy_empty"] is True
    assert value["accepted_announcement_count"] == 0


@pytest.mark.parametrize(
    ("mutation", "error"),
    (
        (lambda pages: pages[0].update(code=200000), "response_1_code_not_ok"),
        (lambda pages: pages[0].update(message="ok"), "response_1_schema_invalid"),
        (
            lambda pages: pages[0]["data"].update(totalPage=3),
            "response_pagination_drift",
        ),
        (
            lambda pages: pages[1]["data"].update(currentPage=1),
            "response_page_sequence_invalid",
        ),
        (
            lambda pages: pages[1]["data"]["items"][0].update(annId=200003),
            "announcement_identity_duplicate",
        ),
        (
            lambda pages: pages[0]["data"]["items"][0].update(annId=True),
            "announcement_id_invalid",
        ),
        (
            lambda pages: pages[0]["data"]["items"][0].update(
                annType=["latest-announcements", "invented-listing"]
            ),
            "announcement_types_invalid",
        ),
        (
            lambda pages: pages[0]["data"]["items"][0].update(language="en-US"),
            "announcement_language_invalid",
        ),
        (
            lambda pages: pages[0]["data"]["items"][0].update(
                annUrl="http://www.kucoin.com/announcement/alpha?foo=bar"
            ),
            "announcement_url_invalid",
        ),
        (
            lambda pages: pages[0]["data"]["items"][0].update(
                annUrl="https://www.kucoin.com/announcement/alpha?foo=bar"
            ),
            "announcement_url_query_invalid",
        ),
        (
            lambda pages: pages[0]["data"]["items"][0].update(
                cTime=1784424962000
            ),
            "announcement_publication_outside_request_window",
        ),
        (
            lambda pages: pages[0]["data"]["items"][0].update(
                annTitle="x" * 513
            ),
            "announcement_title_invalid",
        ),
        (
            lambda pages: pages[0]["data"]["items"][0].update(extra="drift"),
            "announcement_item_schema_invalid",
        ),
    ),
)
def test_schema_identity_category_clock_and_url_drift_fail_closed(
    mutation: object,
    error: str,
) -> None:
    pages = [deepcopy(_payload(1)), deepcopy(_payload(2))]
    mutation(pages)

    with pytest.raises(KuCoinAnnouncementError, match=error):
        _snapshot(payloads=pages)


def test_duplicate_json_keys_and_non_monotonic_acquisition_fail_closed() -> None:
    duplicate = b'{"code":"200000","code":"200000","data":{}}'
    with pytest.raises(KuCoinAnnouncementError, match="duplicate_json_key"):
        normalize_kucoin_announcement_pages(
            [duplicate],
            acquired_at_by_page=["2026-07-19T01:35:01Z"],
            request_lineage_ids=["test.kucoin.page1"],
            start_time="2026-07-19T00:00:00Z",
            end_time="2026-07-19T01:35:00Z",
        )

    with pytest.raises(KuCoinAnnouncementError, match="acquisition_window"):
        normalize_kucoin_announcement_pages(
            [_body(_payload(1)), _body(_payload(2))],
            acquired_at_by_page=[
                "2026-07-19T01:35:02Z",
                "2026-07-19T01:35:01Z",
            ],
            request_lineage_ids=["test.kucoin.page1", "test.kucoin.page2"],
            start_time="2026-07-19T00:00:00Z",
            end_time="2026-07-19T01:35:00Z",
        )

    with pytest.raises(KuCoinAnnouncementError, match="lineage_duplicate"):
        normalize_kucoin_announcement_pages(
            [_body(_payload(1)), _body(_payload(2))],
            acquired_at_by_page=[
                "2026-07-19T01:35:01Z",
                "2026-07-19T01:35:02Z",
            ],
            request_lineage_ids=["test.kucoin.same", "test.kucoin.same"],
            start_time="2026-07-19T00:00:00Z",
            end_time="2026-07-19T01:35:00Z",
        )


def test_fixture_smoke_has_no_network_writes_or_policy_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("network must remain unused")
        ),
    )

    result = run_fixture_smoke(FIXTURE_DIR)
    assert result["status"] == "complete"
    assert result["provider_calls"] == 0
    assert result["writes"] == 0
    assert result["authorization_created"] is False
    assert result["orders"] == 0
    assert result["trades"] == 0
    assert result["paper_trades"] == 0
    assert result["telegram_sends"] == 0
    assert result["normal_rsi_writes"] == 0
    assert result["event_alpha_triggered_fade"] == 0
    assert result["route_or_score_effect"] is False
    assert result["protocol_v2_evidence_eligible"] is False
    assert main(["--fixture-dir", str(FIXTURE_DIR)]) == 0
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["mode"] == "offline_fixture"
    assert rendered["provider_calls"] == 0
