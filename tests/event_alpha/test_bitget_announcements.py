"""Closed Bitget announcement response contract regressions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import socket

import pytest

from crypto_rsi_scanner.event_alpha.operations.bitget_announcements import (
    ANNOUNCEMENTS_PATH,
    BitgetAnnouncementError,
    build_bitget_announcement_request_plan,
    main,
    normalize_bitget_announcement_pages,
    run_fixture_smoke,
)


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "bitget_announcements"
START = "2026-07-19T00:00:00Z"
END = "2026-07-19T01:35:00Z"
ACQUIRED = ("2026-07-19T01:35:01Z", "2026-07-19T01:35:02Z")
LINEAGES = ("fixture.bitget.page1", "fixture.bitget.page2")
CURSORS = (None, "900002")


def _bodies() -> tuple[bytes, bytes]:
    return (
        (FIXTURE_DIR / "page_1.json").read_bytes(),
        (FIXTURE_DIR / "page_2.json").read_bytes(),
    )


def _payloads() -> list[dict[str, object]]:
    return [json.loads(body) for body in _bodies()]


def _encode(values) -> tuple[bytes, ...]:
    return tuple(
        (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
        for value in values
    )


def _normalize(
    bodies=None,
    *,
    cursors=CURSORS,
    acquired=ACQUIRED,
    lineages=LINEAGES,
    limit=2,
    announcement_type=None,
):
    selected = _bodies() if bodies is None else tuple(bodies)
    return normalize_bitget_announcement_pages(
        selected,
        acquired_at_by_page=acquired[: len(selected)],
        request_lineage_ids=lineages[: len(selected)],
        request_cursors=cursors[: len(selected)],
        start_time=START,
        end_time=END,
        limit=limit,
        announcement_type=announcement_type,
    )


def test_request_plan_preserves_official_path_and_no_call_boundary() -> None:
    plan = build_bitget_announcement_request_plan(
        start_time=START,
        end_time=END,
        limit=2,
    )

    assert ANNOUNCEMENTS_PATH == "/api/v2/public/annoucements"
    assert plan["path"] == ANNOUNCEMENTS_PATH
    assert plan["path_spelling_verified"] == "annoucements"
    assert plan["initial_query"] == {
        "startTime": "1784419200000",
        "endTime": "1784424900000",
        "limit": "2",
        "language": "en_US",
    }
    assert plan["maximum_request_count"] == 20
    assert plan["maximum_response_rows"] == 200
    assert plan["credentials_required"] is False
    assert plan["provider_call_authorized"] is False
    assert plan["provider_call_attempted"] is False
    assert plan["writes"] == 0


def test_complete_cursor_prefix_preserves_exact_lineage_and_semantics() -> None:
    value = _normalize()

    assert value["coverage_status"] == "complete"
    assert value["coverage_complete"] is True
    assert value["healthy_empty"] is False
    assert value["accepted_announcement_count"] == 3
    assert value["request_cursors"] == [None, "900002"]
    assert value["next_cursor"] is None
    assert value["response_row_count_by_page"] == {"1": 2, "2": 1}
    assert value["provider_request_time_by_page"] == {
        "1": "2026-07-19T01:35:00.500000Z",
        "2": "2026-07-19T01:35:01.500000Z",
    }
    rows = value["announcements"]
    assert [row["announcement_id"] for row in rows] == ["900003", "900002", "900001"]
    assert rows[0]["announcement_type"] == "coin_listings"
    assert rows[0]["announcement_subtype"] == "spot"
    assert rows[0]["publication_at"] == "2026-07-19T01:32:00Z"
    assert rows[0]["event_time"] is None
    assert rows[0]["event_time_basis"] == "not_inferred_from_publication"
    assert rows[0]["description_status"] == (
        "deprecated_provider_field_not_complete_article"
    )
    assert all(row["directional_authority"] is False for row in rows)
    assert value["provider_calls"] == 0
    assert value["writes"] == 0
    assert value["protocol_v2_evidence_eligible"] is False


def test_full_last_page_is_partial_and_exposes_next_cursor() -> None:
    value = _normalize(_bodies()[:1], cursors=(None,))

    assert value["coverage_status"] == "partial"
    assert value["coverage_complete"] is False
    assert value["healthy_empty"] is False
    assert value["next_cursor"] == "900002"


def test_empty_first_page_is_complete_healthy_empty() -> None:
    payload = _payloads()[0]
    payload["data"] = []
    value = _normalize(_encode([payload]), cursors=(None,))

    assert value["coverage_status"] == "complete"
    assert value["healthy_empty"] is True
    assert value["accepted_announcement_count"] == 0


def test_cursor_must_equal_last_prior_announcement_id() -> None:
    with pytest.raises(BitgetAnnouncementError, match="response_cursor_chain_invalid"):
        _normalize(cursors=(None, "wrong"))


def test_opaque_safe_string_ids_survive_the_cursor_chain() -> None:
    payloads = _payloads()
    payloads[0]["data"][0]["annId"] = "notice-A_3"
    payloads[0]["data"][1]["annId"] = "notice-A_2"
    payloads[1]["data"][0]["annId"] = "notice-A_1"
    value = _normalize(_encode(payloads), cursors=(None, "notice-A_2"))

    assert [row["announcement_id"] for row in value["announcements"]] == [
        "notice-A_3",
        "notice-A_2",
        "notice-A_1",
    ]


def test_nonterminal_short_page_cannot_be_followed() -> None:
    payloads = _payloads()
    payloads[0]["data"] = payloads[0]["data"][:1]
    with pytest.raises(
        BitgetAnnouncementError, match="response_pagination_after_terminal_page"
    ):
        _normalize(_encode(payloads), cursors=(None, "900003"))


def test_provider_rows_cannot_exceed_requested_limit() -> None:
    with pytest.raises(
        BitgetAnnouncementError, match="response_requested_limit_exceeded"
    ):
        _normalize(limit=1)


def test_filtered_request_rejects_other_announcement_types() -> None:
    with pytest.raises(
        BitgetAnnouncementError,
        match="response_announcement_type_filter_mismatch",
    ):
        _normalize(announcement_type="coin_listings")


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda values: values[0].update({"extra": True}), "response_1_schema_invalid"),
        (lambda values: values[0].update({"code": "40001"}), "response_1_status_not_ok"),
        (lambda values: values[0]["data"][0].update({"annSubType": "futures_maintenance"}), "announcement_type_subtype_invalid"),
        (lambda values: values[0]["data"][0].update({"language": "zh_CN"}), "announcement_language_invalid"),
        (lambda values: values[0]["data"][0].update({"annUrl": "https://example.com/support/articles/900003"}), "announcement_url_invalid"),
        (lambda values: values[1]["data"][0].update({"annId": "900003"}), "announcement_identity_duplicate"),
        (lambda values: values[1]["data"][0].update({"cTime": "1784424780000"}), "announcement_publication_order_invalid"),
        (lambda values: values[0].update({"requestTime": 1784426000000}), "response_request_time_outside_acquisition_window"),
    ],
)
def test_contract_drift_fails_closed(mutate, reason: str) -> None:
    values = deepcopy(_payloads())
    mutate(values)
    with pytest.raises(BitgetAnnouncementError, match=reason):
        _normalize(_encode(values))


def test_duplicate_json_keys_fail_before_projection() -> None:
    raw = _bodies()[0].replace(b'"code": "00000",', b'"code": "00000", "code": "00000",', 1)
    with pytest.raises(BitgetAnnouncementError, match="response_duplicate_json_key"):
        _normalize((raw,), cursors=(None,))


def test_fixture_smoke_and_cli_are_offline(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Bitget fixture smoke must not use network")
        ),
    )
    result = run_fixture_smoke(FIXTURE_DIR)
    assert result["status"] == "complete"
    assert result["provider_calls"] == 0
    assert result["writes"] == 0
    assert main(["--fixture-dir", str(FIXTURE_DIR)]) == 0
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["provider_calls"] == 0
    assert rendered["protocol_v2_evidence_eligible"] is False


def test_request_window_timezone_is_required() -> None:
    with pytest.raises(BitgetAnnouncementError, match="request_start_time_timezone_missing"):
        build_bitget_announcement_request_plan(
            start_time=datetime(2026, 7, 19),
            end_time=datetime(2026, 7, 19, 1, tzinfo=timezone.utc),
        )
