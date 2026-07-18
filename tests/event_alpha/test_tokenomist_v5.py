from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.radar import scheduled_catalysts
from crypto_rsi_scanner.event_providers import tokenomist_v5


FIXTURE = Path("fixtures/event_discovery/tokenomist_unlock_events_v5_capture.json")


def _capture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_tokenomist_v5_fixture_normalizes_exact_units_and_provenance():
    rows = tokenomist_v5.load_tokenomist_v5_fixture_capture(FIXTURE)

    assert len(rows) == 1
    row = rows[0]
    assert row["symbol"] == "TESTV5"
    assert row["coin_id"] == "test-unlock-v5"
    assert row["unlock_date"] == "2026-06-16T13:00:00+00:00"
    assert row["unlock_amount"] == 10_000_000.0
    assert row["unlock_usd"] == 2_500_000.0
    assert row["unlock_value_to_market_cap_pct"] == 2.5
    assert row["unlock_value_to_market_cap_unit"] == "percent_points"
    assert row["unlock_pct_circulating"] is None
    assert row["unlock_pct_circulating_supply"] is None
    assert row["event_timestamp_confidence"] == "estimated"
    assert row["first_public_at"] is None
    assert row["query_date_is_publication_time"] is False
    assert row["authority_eligible"] is False
    assert row["protocol_v2_evidence_eligible"] is False
    assert row["provider_call_performed"] is False
    assert row["provider_authorization_created"] is False
    assert row["research_only"] is True
    assert row["created_trade"] is False
    assert row["created_triggered_fade"] is False


def test_tokenomist_v5_fixture_flows_to_scheduled_calendar_without_unit_reinterpretation(tmp_path):
    result = scheduled_catalysts.run_scheduled_catalyst_scan(
        namespace_dir=tmp_path,
        provider_paths={"tokenomist": FIXTURE, "coinmarketcal": None},
        profile="fixture",
        artifact_namespace="tokenomist_v5_fixture",
        run_mode="fixture",
        run_id="run-tokenomist-v5-fixture",
        observed_at="2026-06-15T16:00:00Z",
    )

    assert result.scheduled_count == 1
    assert result.unlock_count == 1
    event = result.scheduled_events[0]
    unlock = result.unlock_candidates[0]
    assert event["event_start_time"] == "2026-06-16T13:00:00+00:00"
    assert event["unlock_value_to_market_cap_pct"] == 2.5
    assert event["unlock_value_to_market_cap_unit"] == "percent_points"
    assert event["unlock_pct_circulating"] is None
    assert unlock["unlock_value_to_market_cap_pct"] == 2.5
    assert unlock["unlock_value_to_market_cap_unit"] == "percent_points"
    assert unlock["unlock_pct_circulating"] is None
    assert unlock["structured_unlock_evidence"] is True
    assert unlock["opportunity_type"] == "RISK_ONLY"
    assert "unlock_size_metrics_missing" not in unlock["why_not_alertable"]
    assert unlock["research_only"] is True
    assert unlock["created_alert"] is False


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (
            lambda row: row["response"]["metadata"].__setitem__(
                "queryDate", "2026-06-15T16:00:00Z"
            ),
            "queryDate must not follow",
        ),
        (
            lambda row: row["response"]["data"][0]["cliffUnlocks"].__setitem__(
                "cliffAmount", float("nan")
            ),
            "outside plausible bounds",
        ),
        (
            lambda row: row["response"]["data"][0]["cliffUnlocks"].__setitem__(
                "cliffValue", -1
            ),
            "outside plausible bounds",
        ),
        (lambda row: row["response"]["metadata"].__setitem__("total", 2), "row count is inconsistent"),
        (lambda row: row["response"]["data"][0].__setitem__("unexpected", True), "unknown keys"),
        (lambda row: row.__setitem__("api_key", "forbidden"), "sensitive key"),
    ],
)
def test_tokenomist_v5_fixture_rejects_inconsistent_or_sensitive_input(mutate, match):
    capture = copy.deepcopy(_capture())
    mutate(capture)

    with pytest.raises(ValueError, match=match):
        tokenomist_v5.normalize_tokenomist_v5_fixture_capture(capture)


def test_tokenomist_v5_fixture_preserves_partial_page_coverage():
    capture = _capture()
    capture["request"]["page_size"] = 1
    capture["response"]["metadata"].update(
        {"page": 1, "pageSize": 1, "totalPages": 2, "total": 2}
    )

    row = tokenomist_v5.normalize_tokenomist_v5_fixture_capture(capture)[0]

    assert row["provider_snapshot_status"] == "partial_page"
    assert row["source_coverage_complete"] is False


def test_tokenomist_v5_fixture_rejects_request_response_pagination_drift():
    capture = _capture()
    capture["request"]["page_size"] = 25

    with pytest.raises(ValueError, match="pageSize does not match request"):
        tokenomist_v5.normalize_tokenomist_v5_fixture_capture(capture)


@pytest.mark.parametrize("total_pages", [0, 1])
def test_tokenomist_v5_fixture_accepts_explicit_empty_coverage(total_pages):
    capture = _capture()
    capture["response"]["metadata"].update(
        {"totalPages": total_pages, "total": 0}
    )
    capture["response"]["data"] = []

    assert tokenomist_v5.normalize_tokenomist_v5_fixture_capture(capture) == ()


def test_tokenomist_v5_fixture_day_precision_is_confirmed():
    capture = _capture()
    for allocation in capture["response"]["data"][0]["cliffUnlocks"]["allocationBreakdown"]:
        allocation["unlockPrecision"] = "day"

    row = tokenomist_v5.normalize_tokenomist_v5_fixture_capture(capture)[0]

    assert row["event_timestamp_confidence"] == "confirmed"


def test_tokenomist_v5_fixture_contract_is_idempotent_and_no_write(tmp_path):
    capture = _capture()
    before = set(tmp_path.iterdir())
    first = tokenomist_v5.normalize_tokenomist_v5_fixture_capture(capture)
    second = tokenomist_v5.normalize_tokenomist_v5_fixture_capture(capture)

    assert first == second
    assert set(tmp_path.iterdir()) == before
    assert all(row["notification_send_enabled"] is False for row in first)
    assert all(row["created_order"] is False for row in first)
    assert all(row["created_paper_trade"] is False for row in first)
    assert all(row["wrote_normal_rsi_row"] is False for row in first)
