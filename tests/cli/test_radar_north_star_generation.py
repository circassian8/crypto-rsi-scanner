"""Exact checked-artifact regressions for the generated Radar North Star."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from crypto_rsi_scanner.project_health import radar_north_star

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_event_alpha_radar_north_star_checked_artifacts_are_reproducible():
    research = REPO_ROOT / "research"
    checked_payload = json.loads(
        (research / radar_north_star.REPORT_JSON).read_text(encoding="utf-8")
    )
    rebuilt_payload = radar_north_star.build_north_star(
        generated_at=datetime.fromisoformat(checked_payload["generated_at"])
    )
    assert rebuilt_payload == checked_payload
    assert radar_north_star.format_north_star(rebuilt_payload) == (
        research / radar_north_star.REPORT_MD
    ).read_text(encoding="utf-8")
    decision_payload = json.loads(
        (research / "CRYPTO_DECISION_RADAR_NORTH_STAR.json").read_text(
            encoding="utf-8"
        )
    )
    assert decision_payload["shadow_temporal_surprise_policy"] == (
        rebuilt_payload["shadow_temporal_surprise_policy"]
    )

    checked_burn_in = json.loads(
        (research / radar_north_star.BURN_IN_CONTRACT_JSON).read_text(encoding="utf-8")
    )
    rebuilt_burn_in = radar_north_star.build_burn_in_contract(
        generated_at=datetime.fromisoformat(checked_burn_in["generated_at"])
    )
    assert rebuilt_burn_in == checked_burn_in
    assert radar_north_star.format_burn_in_contract(rebuilt_burn_in) == (
        research / radar_north_star.BURN_IN_CONTRACT_MD
    ).read_text(encoding="utf-8")
