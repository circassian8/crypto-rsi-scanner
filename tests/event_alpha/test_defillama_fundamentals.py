from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.providers import dex_onchain_readiness
from crypto_rsi_scanner.event_providers import defillama_fundamentals


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "event_dex_onchain"
    / "defillama_fundamentals_official_capture.json"
)


def _capture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _raw(value: dict[str, object]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def test_official_free_fixture_preserves_distinct_metric_semantics() -> None:
    row = defillama_fundamentals.load_defillama_fundamentals_fixture_capture(FIXTURE)[0]

    assert row["schema_id"] == "decision_radar.defillama_protocol_fundamentals"
    assert row["protocol_id"] == "2269"
    assert row["protocol_slug"] == "aave"
    assert row["canonical_asset_id"] == "aave"
    assert row["coingecko_asset_id"] == "aave"
    assert row["symbol"] == "AAVE"
    assert row["tvl_usd"] == 12_500_000_000.0
    assert row["tvl_change_24h_pct"] == 2.1
    assert row["metric_units"]["tvl_change_24h_pct"] == "percent_points"
    assert row["fees_24h"] == 2_800_000.0
    assert row["revenue_24h"] == 900_000.0
    assert row["holders_revenue_24h"] == 125_000.0
    assert row["fees_7d_total_usd"] == 18_500_000.0
    assert row["revenue_7d_total_usd"] == 6_100_000.0
    assert row["holders_revenue_7d_total_usd"] == 840_000.0
    assert row["fees_revenue_interchangeable"] is False
    assert row["tvl_change_is_net_flow"] is False
    assert row["provider_value_timestamp"] is None
    assert row["provider_value_timestamp_status"] == (
        "unavailable_in_free_overview_response"
    )
    assert row["metric_semantics"] == {
        "tvl": "usd_value_locked_snapshot_includes_asset_price_effects",
        "fees": "user_paid_top_line_fees",
        "revenue": "fees_retained_by_protocol",
        "holders_revenue": "revenue_returned_to_token_holders",
    }


def test_fixture_contract_is_no_call_no_authority_and_idempotent(tmp_path: Path) -> None:
    raw = FIXTURE.read_bytes()
    before = set(tmp_path.iterdir())

    first = defillama_fundamentals.normalize_defillama_fundamentals_fixture_capture(raw)
    second = defillama_fundamentals.normalize_defillama_fundamentals_fixture_capture(raw)

    assert first == second
    assert set(tmp_path.iterdir()) == before
    assert all(row["capture_mode"] == "fixture" for row in first)
    assert all(row["provider_call_performed"] is False for row in first)
    assert all(row["provider_authorization_created"] is False for row in first)
    assert all(row["authority_eligible"] is False for row in first)
    assert all(row["protocol_v2_evidence_eligible"] is False for row in first)
    assert all(row["directional_authority"] is False for row in first)
    assert all(row["created_alert"] is False for row in first)
    assert all(row["created_order"] is False for row in first)
    assert all(row["created_paper_trade"] is False for row in first)
    assert all(row["normal_rsi_signal_written"] is False for row in first)
    assert all(row["triggered_fade_created"] is False for row in first)


def test_closed_fixture_flows_through_existing_readiness_without_projection_loss(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    result = dex_onchain_readiness.run_dex_onchain_readiness(
        namespace_dir=tmp_path,
        profile="fixture",
        artifact_namespace="defillama_official_contract",
        geckoterminal_path=root / "fixtures/event_dex_onchain/geckoterminal_pools.json",
        coingecko_dex_path=root / "fixtures/event_dex_onchain/coingecko_dex_pools.json",
        defillama_path=FIXTURE,
        smoke_mode=True,
    )

    assert result.report.live_call_allowed is False
    assert result.report.protocol_fundamental_rows == 1
    row = result.protocol_fundamental_rows[0]
    assert row["schema_id"] == defillama_fundamentals.OUTPUT_SCHEMA_ID
    assert row["profile"] == "fixture"
    assert row["artifact_namespace"] == "defillama_official_contract"
    assert row["holders_revenue_24h"] == 125_000.0
    assert row["metric_semantics"]["fees"] == "user_paid_top_line_fees"
    assert row["tvl_change_is_net_flow"] is False
    assert row["protocol_v2_evidence_eligible"] is False


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (
            lambda value: value["exchanges"][1]["request"]["query"].__setitem__(
                "dataType", "dailyRevenue"
            ),
            "daily_fees_request_identity_invalid",
        ),
        (
            lambda value: value["mappings"][0].__setitem__("token_symbol", "WRONG"),
            "protocol_symbol_mapping_mismatch",
        ),
        (
            lambda value: value["exchanges"][0]["response"]["body"][0].__setitem__(
                "change_1d", 1_000_001
            ),
            "tvl_change_1d_outside_plausible_bounds",
        ),
        (
            lambda value: value["exchanges"][3].__setitem__(
                "response_received_at", "2026-07-18T12:00:02Z"
            ),
            "exchange_3_timing_invalid",
        ),
        (
            lambda value: value.__setitem__("api_key", "forbidden"),
            "sensitive_key_forbidden",
        ),
    ],
)
def test_closed_fixture_rejects_semantic_identity_and_timing_drift(
    mutate,
    match: str,
) -> None:
    capture = deepcopy(_capture())
    mutate(capture)

    with pytest.raises(defillama_fundamentals.DefiLlamaFundamentalsError, match=match):
        defillama_fundamentals.normalize_defillama_fundamentals_fixture_capture(
            _raw(capture)
        )


def test_missing_metric_is_unavailable_not_zero() -> None:
    capture = _capture()
    holders = capture["exchanges"][3]["response"]["body"]["protocols"][0]
    holders.update(
        {
            "total24h": None,
            "total7d": None,
            "total30d": None,
            "change_1d": None,
        }
    )

    row = defillama_fundamentals.normalize_defillama_fundamentals_fixture_capture(
        _raw(capture)
    )[0]

    assert row["holders_revenue_24h"] is None
    assert row["metric_availability"]["holders_revenue"] == "unavailable"
