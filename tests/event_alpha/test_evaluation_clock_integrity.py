"""Fail-closed evaluation-clock regressions across Radar context layers."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize("clock", ("not-a-time", True, 1.5))
def test_integrated_candidates_reject_malformed_explicit_clock(clock):
    import crypto_rsi_scanner.event_alpha.radar.integrated_radar as integrated_radar

    with pytest.raises(ValueError, match="integrated candidate observed_at is invalid"):
        integrated_radar.build_integrated_candidates(
            sidecar_rows={},
            profile="fixture",
            artifact_namespace="clock-integrity",
            run_mode="fixture",
            run_id="clock-integrity-run",
            observed_at=clock,
        )


@pytest.mark.parametrize("clock", ("not-a-time", True, 1.5))
def test_integrated_deliveries_reject_malformed_explicit_clock(clock):
    from crypto_rsi_scanner.event_alpha.radar.integrated_radar import (
        build_integrated_notification_delivery_rows,
    )

    with pytest.raises(ValueError, match="integrated delivery generated_at is invalid"):
        build_integrated_notification_delivery_rows((), generated_at=clock)


@pytest.mark.parametrize("clock", ("not-a-time", True, 1.5))
def test_market_confirmation_rejects_malformed_evaluation_clock(clock):
    from crypto_rsi_scanner.event_alpha.radar import market_confirmation

    with pytest.raises(ValueError, match="market confirmation evaluation clock is invalid"):
        market_confirmation.evaluate_market_confirmation({
            "now": clock,
            "market": {
                "return_24h": 4.0,
                "market_context_observed_at": "2026-07-19T08:00:00Z",
            },
        })


def test_calendar_and_derivatives_adapters_reject_boolean_clocks():
    from crypto_rsi_scanner.event_alpha.radar import derivatives_crowding
    from crypto_rsi_scanner.event_alpha.radar import scheduled_catalysts

    with pytest.raises(ValueError, match="invalid datetime True"):
        scheduled_catalysts.normalize_scheduled_catalyst_event(
            {"title": "Test event"},
            provider="test_provider",
            observed_at=True,
        )

    with pytest.raises(ValueError, match="invalid datetime True"):
        derivatives_crowding.normalize_derivatives_state(
            {"symbol": "TESTUSDT_PERP"},
            observed_at=True,
        )

    with pytest.raises(ValueError, match="invalid datetime True"):
        scheduled_catalysts.normalize_scheduled_catalyst_event(
            {"title": "Test event", "event_start_time": True},
            provider="test_provider",
            observed_at="2026-07-19T08:00:00Z",
        )

    with pytest.raises(ValueError, match="invalid datetime True"):
        derivatives_crowding.normalize_derivatives_state(
            {"symbol": "TESTUSDT_PERP", "observed_at": True},
            observed_at="2026-07-19T08:00:00Z",
        )
