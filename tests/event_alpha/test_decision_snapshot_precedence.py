"""Decision snapshot precedence must preserve explicit invalidity."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.radar import decision_policy


def test_invalid_later_snapshot_returns_mask_older_values():
    invalid_values = (True, "not-a-number", float("nan"), float("inf"), 10.0)
    for invalid in invalid_values:
        merged = decision_policy.market_snapshot({
            "market_snapshot": {
                "return_unit": "percent_points",
                "return_4h": 12.0,
                "freshness_status": "fresh",
            },
            "market_state_snapshot": {
                "return_unit": "fraction",
                "return_4h": invalid,
                "freshness_status": "fresh",
            },
        })

        assert "return_4h" not in merged
        assert any(
            warning.endswith(":return_4h")
            for warning in merged["unit_warnings"]
        )


def test_absent_later_snapshot_return_preserves_earlier_observation():
    merged = decision_policy.market_snapshot({
        "market_snapshot": {
            "return_unit": "percent_points",
            "return_4h": 12.0,
            "freshness_status": "fresh",
        },
        "market_state_snapshot": {
            "return_unit": "percent_points",
            "freshness_status": "fresh",
        },
    })

    assert merged["return_4h"] == 12.0
    assert merged.get("unit_warnings") is None
