"""Fail-closed configuration checks for the market-anomaly engine."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from crypto_rsi_scanner.event_alpha.radar import market_anomaly_scanner as scanner


@pytest.mark.parametrize(
    "changes",
    (
        {"max_assets": 0},
        {"max_assets": -1},
        {"max_assets": True},
        {"confirmed_return_24h": float("nan")},
        {"confirmed_volume_zscore": float("inf")},
        {"confirmed_relative_btc_4h": "5"},
        {"post_event_fade_return_4h": 0.0},
        {"risk_off_return_24h": 12.0},
        {"stealth_return_4h_min": 8.0, "stealth_return_4h_max": 8.0},
        {
            "stealth_volume_zscore_min": 3.0,
            "stealth_volume_zscore_max": 2.0,
        },
        {"suspicious_liquidity_usd": 6_000_000.0},
        {"search_deadline_hours": 0.49},
    ),
)
def test_market_anomaly_scanner_rejects_malformed_configuration_before_iteration(
    changes: dict[str, object],
) -> None:
    class ExplodingRows:
        def __iter__(self):
            raise AssertionError("invalid configuration must fail before row iteration")

    cfg = replace(scanner.MarketAnomalyScannerConfig(), **changes)
    with pytest.raises(ValueError, match="market_anomaly_scanner_config_invalid"):
        scanner.scan_market_rows(ExplodingRows(), cfg=cfg)


def test_market_anomaly_scanner_rejects_wrong_config_type_on_every_public_surface(
    tmp_path,
) -> None:
    invalid = object()
    with pytest.raises(ValueError, match="config_invalid:type"):
        scanner.scan_market_rows((), cfg=invalid)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="config_invalid:type"):
        scanner.classify_market_state({}, cfg=invalid)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="config_invalid:type"):
        scanner.build_catalyst_search_queue((), cfg=invalid)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="config_invalid:type"):
        scanner.format_market_anomaly_report((), cfg=invalid)  # type: ignore[arg-type]

    namespace = tmp_path / "invalid_config_must_not_write"
    with pytest.raises(ValueError, match="config_invalid:type"):
        scanner.run_market_anomaly_scan(
            market_rows=(),
            namespace_dir=namespace,
            cfg=invalid,  # type: ignore[arg-type]
        )
    assert not namespace.exists()


def test_valid_minimum_deadline_and_positive_asset_cap_remain_exact() -> None:
    observed_at = datetime(2026, 7, 22, 2, 0, tzinfo=timezone.utc)
    cfg = scanner.MarketAnomalyScannerConfig(
        max_assets=1,
        search_deadline_hours=0.5,
    )
    anomalies = [
        {
            "market_anomaly_id": "anomaly:one",
            "canonical_asset_id": "asset:one",
            "symbol": "ONE",
            "priority": 10.0,
            "needs_catalyst_search": True,
            "suggested_source_packs_to_search": ["market_anomaly_pack"],
        }
    ]

    queue = scanner.build_catalyst_search_queue(
        anomalies,
        cfg=cfg,
        observed_at=observed_at,
    )

    assert len(queue) == 1
    assert queue[0]["search_deadline"] == "2026-07-22T02:30:00+00:00"
