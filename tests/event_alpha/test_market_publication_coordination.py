"""Single-coordinator market publication contract tests."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.dashboard.readiness import (
    CURRENT_NAMESPACE_POINTER,
)
from crypto_rsi_scanner.event_alpha.operations import market_no_send_cli
from crypto_rsi_scanner.project_health import radar_north_star


def test_direct_market_publication_cli_is_disabled_and_preserves_pointer(
    tmp_path,
    capsys,
):
    pointer = tmp_path / CURRENT_NAMESPACE_POINTER
    pointer_before = b"prior-receipt-backed-authority\n"
    pointer.write_bytes(pointer_before)

    status = market_no_send_cli.main([
        "publish",
        "--artifact-base", str(tmp_path),
        "--namespace", "uncoordinated_generation",
    ])

    assert status == 1
    assert "direct market generation publication is disabled" in capsys.readouterr().err
    assert pointer.read_bytes() == pointer_before


def test_north_star_assigns_market_publication_to_daily_operations():
    generation = radar_north_star.build_north_star()["market_no_send_generation"]

    assert generation["operator_cycle_target"] == "radar-daily-ops-cycle"
    assert generation["compatibility_alias"] == {
        "radar-market-no-send": "radar-daily-ops-cycle",
    }
    assert generation["publication_owner"] == (
        "decision_radar_daily_operations_v1_1"
    )
    assert generation["direct_low_level_publication"] == "disabled"
