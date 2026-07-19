"""Closed offline KuCoin UTA official-announcement contract regressions."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket

import pytest

from crypto_rsi_scanner.event_alpha.operations.kucoin_announcements import (
    KuCoinAnnouncementError,
)
from crypto_rsi_scanner.event_alpha.operations.kucoin_uta_announcements import (
    CONTRACT_VERSION,
    SNAPSHOT_SCHEMA_VERSION,
    build_kucoin_uta_announcement_request_plan,
    main,
    normalize_kucoin_uta_announcement_pages,
    run_uta_fixture_smoke,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "fixtures/kucoin_uta_announcements"


def _payload(page: int) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / f"page_{page}.json").read_text())


def _body(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()


def _snapshot(*, payloads: list[object] | None = None):
    rows = payloads or [_payload(1), _payload(2)]
    return normalize_kucoin_uta_announcement_pages(
        [_body(row) for row in rows],
        acquired_at_by_page=[
            "2026-07-19T01:35:01Z",
            "2026-07-19T01:35:02Z",
        ][: len(rows)],
        request_lineage_ids=[
            "test.kucoin.uta.page1",
            "test.kucoin.uta.page2",
        ][: len(rows)],
        start_time="2026-07-19T00:00:00Z",
        end_time="2026-07-19T01:35:00Z",
    )


def test_request_plan_uses_current_uta_contract_and_is_non_executable() -> None:
    plan = build_kucoin_uta_announcement_request_plan(
        start_time="2026-07-19T00:00:00Z",
        end_time="2026-07-19T01:35:00Z",
    )

    assert plan["contract_version"] == CONTRACT_VERSION
    assert plan["path"] == "/api/ua/v1/market/announcement"
    assert plan["initial_query"] == {
        "language": "en_US",
        "type": "latest-announcements",
        "pageNumber": 1,
        "pageSize": 50,
        "startTime": 1784419200000,
        "endTime": 1784424900000,
    }
    assert plan["replaces_historical_path"] == "/api/v3/announcements"
    assert plan["maximum_request_count"] == 20
    assert plan["api_rate_limit_weight"] == 20
    assert plan["provider_call_authorized"] is False
    assert plan["provider_call_planned"] is False
    assert plan["provider_call_attempted"] is False
    assert plan["redirects_allowed"] is False
    assert plan["retries_allowed"] is False


def test_projection_preserves_current_schema_raw_hashes_and_safety() -> None:
    bodies = [_body(_payload(1)), _body(_payload(2))]
    value = normalize_kucoin_uta_announcement_pages(
        bodies,
        acquired_at_by_page=[
            "2026-07-19T01:35:01Z",
            "2026-07-19T01:35:02Z",
        ],
        request_lineage_ids=["test.kucoin.uta.page1", "test.kucoin.uta.page2"],
        start_time="2026-07-19T00:00:00Z",
        end_time="2026-07-19T01:35:00Z",
    ).to_dict()

    assert value["schema_version"] == SNAPSHOT_SCHEMA_VERSION
    assert value["contract_version"] == CONTRACT_VERSION
    assert value["endpoint"].endswith("/api/ua/v1/market/announcement")
    assert value["coverage_status"] == "complete"
    assert value["accepted_announcement_count"] == 3
    assert value["response_sha256_by_page"]["1"] == hashlib.sha256(bodies[0]).hexdigest()
    listing = value["announcements"][0]
    assert listing["response_sha256"] == value["response_sha256_by_page"]["1"]
    assert listing["announcement_id"] == 200003
    assert listing["announcement_types"] == (
        "latest-announcements",
        "new-listings",
    )
    assert listing["publication_at"] == "2026-07-19T01:32:00Z"
    assert listing["event_time"] is None
    assert listing["directional_authority"] is False
    assert value["provider_calls"] == 0
    assert value["writes"] == 0
    assert value["protocol_v2_evidence_eligible"] is False


def test_prefix_is_partial_and_zero_is_healthy_only_when_complete() -> None:
    partial = _snapshot(payloads=[_payload(1)]).to_dict()
    assert partial["coverage_status"] == "partial"
    assert partial["healthy_empty"] is False
    assert partial["missing_pages"] == (2,)

    empty = {
        "code": "200000",
        "data": {
            "totalNumber": 0,
            "totalPage": 0,
            "pageNumber": 1,
            "pageSize": 50,
            "list": [],
        },
    }
    complete = _snapshot(payloads=[empty]).to_dict()
    assert complete["coverage_status"] == "complete"
    assert complete["healthy_empty"] is True


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
            lambda pages: pages[1]["data"].update(pageNumber=1),
            "response_page_sequence_invalid",
        ),
        (
            lambda pages: pages[1]["data"]["list"][0].update(id=200003),
            "announcement_identity_duplicate",
        ),
        (
            lambda pages: pages[0]["data"]["list"][0].update(
                type=["latest-announcements", "invented-listing"]
            ),
            "announcement_types_invalid",
        ),
        (
            lambda pages: pages[0]["data"]["list"][0].update(extra="drift"),
            "announcement_item_schema_invalid",
        ),
    ),
)
def test_schema_pagination_identity_and_category_drift_fail_closed(
    mutation: object,
    error: str,
) -> None:
    pages = [deepcopy(_payload(1)), deepcopy(_payload(2))]
    mutation(pages)
    with pytest.raises(KuCoinAnnouncementError, match=error):
        _snapshot(payloads=pages)


def test_duplicate_uta_keys_fail_before_semantic_projection() -> None:
    duplicate = b'{"code":"200000","code":"200000","data":{}}'
    with pytest.raises(KuCoinAnnouncementError, match="duplicate_json_key"):
        normalize_kucoin_uta_announcement_pages(
            [duplicate],
            acquired_at_by_page=["2026-07-19T01:35:01Z"],
            request_lineage_ids=["test.kucoin.uta.page1"],
            start_time="2026-07-19T00:00:00Z",
            end_time="2026-07-19T01:35:00Z",
        )


def test_fixture_smoke_has_no_network_or_side_effects(
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
    value = run_uta_fixture_smoke(FIXTURE_DIR)
    assert value["status"] == "complete"
    assert value["provider_calls"] == 0
    assert value["writes"] == 0
    assert value["authorization_created"] is False
    assert value["orders"] == 0
    assert value["trades"] == 0
    assert value["paper_trades"] == 0
    assert value["telegram_sends"] == 0
    assert value["normal_rsi_writes"] == 0
    assert value["event_alpha_triggered_fade"] == 0
    assert main(["--fixture-dir", str(FIXTURE_DIR)]) == 0
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["snapshot"]["contract_version"] == CONTRACT_VERSION
