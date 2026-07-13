"""Closed Decision-v2 authority consistency across operator artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


def _candidate(**overrides):
    from crypto_rsi_scanner.event_alpha.radar import decision_model

    row = {
        "schema_version": 1,
        "row_type": "event_integrated_radar_candidate",
        "candidate_id": "candidate-consistency",
        "core_opportunity_id": "core-consistency",
        "run_id": "run-consistency",
        "profile": "fixture",
        "artifact_namespace": "decision-consistency",
        "observed_at": "2026-06-15T16:00:00+00:00",
        "symbol": "CONSIST",
        "coin_id": "consistency-token",
        "canonical_asset_id": "consistency-token",
        "instrument_resolver_status": "resolved",
        "instrument_resolver_confidence": 0.99,
        "instrument_identity_trusted": True,
        "is_tradable_asset": True,
        "opportunity_type": "UNCONFIRMED_RESEARCH",
        "market_state_class": "confirmed_breakout",
        "market_anomaly_bucket": "high_liquidity_breakout",
        "source_origin": "market_anomaly",
        "source_origins": ["market_anomaly"],
        "source_pack": "market_anomaly_pack",
        "market_state_snapshot": {
            "return_unit": "percent_points",
            "return_4h": 12.0,
            "return_24h": 20.0,
            "relative_return_vs_btc_4h": 9.0,
            "volume_zscore_24h": 3.5,
            "volume_to_market_cap": 0.30,
            "liquidity_usd": 12_000_000,
            "spread_bps": 22.0,
            "freshness_status": "fresh",
        },
        "research_only": True,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
    }
    row.update(overrides)
    return {**row, **decision_model.evaluate_radar_decision(row).to_dict()}


def _core(candidate):
    return {
        **candidate,
        "row_type": "event_core_opportunity",
        "decision_projection_source": "integrated_candidate",
        "decision_projection_drift_detected": False,
    }


def test_doctor_blocks_candidate_core_score_context_and_dashboard_drift():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as artifact_doctor

    candidate = _candidate()
    core = _core(candidate)
    clean = artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
        [candidate], core_rows=[core]
    )
    assert clean["integrated_candidate_core_decision_context_mismatch"] == 0
    assert clean["integrated_candidate_core_decision_score_mismatch"] == 0
    assert clean["integrated_dashboard_decision_authority_invalid"] == 0

    drifted = {
        **core,
        "radar_route": "dashboard_watch",
        "radar_actionable": False,
        "confidence_band": "exploratory",
        "actionability_score": core["actionability_score"] - 1.0,
        "decision_projection_source": "downstream_reevaluation",
        "decision_projection_drift_detected": True,
    }
    conflicts = artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
        [candidate], core_rows=[drifted]
    )
    assert conflicts["integrated_candidate_core_decision_context_mismatch"] == 1
    assert conflicts["integrated_candidate_core_decision_score_mismatch"] == 1
    assert conflicts["integrated_dashboard_decision_authority_invalid"] == 1


def test_doctor_blocks_card_decision_drift(tmp_path: Path):
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as artifact_doctor
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
        decision_model_markdown_lines,
    )

    candidate = _candidate()
    card = tmp_path / "card.md"
    card.write_text(
        "\n".join(
            [
                "# CONSIST Event Research Card",
                "",
                "## Opportunity Lane",
                "- Opportunity type: UNCONFIRMED_RESEARCH",
                "",
                "## Crypto Radar Decision",
                *decision_model_markdown_lines(candidate),
                "",
                "## Artifact Lineage",
                "- Core opportunity ID: core-consistency",
            ]
        ),
        encoding="utf-8",
    )
    clean = artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
        [candidate], core_rows=[_core(candidate)], research_card_paths=(card,)
    )
    assert clean["integrated_candidate_card_decision_mismatch"] == 0

    card.write_text(
        card.read_text(encoding="utf-8").replace(
            "- Radar route: actionable_watch",
            "- Radar route: dashboard_watch",
        ),
        encoding="utf-8",
    )
    drifted = artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
        [candidate], core_rows=[_core(candidate)], research_card_paths=(card,)
    )
    assert drifted["integrated_candidate_card_decision_mismatch"] == 1


def test_doctor_reconciles_preview_lane_identity_and_count():
    from crypto_rsi_scanner.event_alpha.doctor.artifact_doctor_parts.provider_readiness_checks import (
        _decision_preview_mismatch_count,
    )
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
        PREVIEW_LANE_TITLES,
        decision_preview_lane,
    )

    candidate = _candidate()
    lane = decision_preview_lane(candidate)
    sections = []
    for item_lane, title in PREVIEW_LANE_TITLES.items():
        if item_lane == "decision_diagnostic":
            continue
        identity = "\n1. CONSIST/consistency-token\n" if item_lane == lane else "\n"
        sections.append(
            f"## Lane: {title}\n- rendered_items: {1 if item_lane == lane else 0}{identity}"
        )
    preview = "\n".join(sections)
    assert _decision_preview_mismatch_count(preview, (candidate,)) == 0
    assert _decision_preview_mismatch_count(
        preview.replace("CONSIST/consistency-token", "WRONG/identity"),
        (candidate,),
    ) > 0


def test_doctor_blocks_expired_current_actionable_surfaces(tmp_path: Path):
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as artifact_doctor
    from crypto_rsi_scanner.event_alpha.doctor.checks import integrated_radar
    from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
        PREVIEW_LANE_TITLES,
        decision_preview_lane,
    )

    candidate = _candidate(expires_at="2026-06-15T16:30:00+00:00")
    lane = decision_preview_lane(candidate)
    preview_sections = []
    for item_lane, title in PREVIEW_LANE_TITLES.items():
        if item_lane == "decision_diagnostic":
            continue
        identity = "\n1. CONSIST/consistency-token\n" if item_lane == lane else "\n"
        preview_sections.append(
            f"## Lane: {title}\n- rendered_items: "
            f"{1 if item_lane == lane else 0}{identity}"
        )
    preview = tmp_path / "decision-preview.md"
    preview.write_text("\n".join(preview_sections), encoding="utf-8")

    conflicts = artifact_doctor._integrated_radar_artifact_conflicts(  # noqa: SLF001
        [candidate],
        core_rows=[_core(candidate)],
        decision_preview_path=preview,
        evaluated_at=datetime(2026, 6, 15, 16, 30, tzinfo=timezone.utc),
    )

    for field in (
        "integrated_candidate_expired_actionable",
        "integrated_core_expired_actionable",
        "integrated_preview_expired_actionable",
        "integrated_dashboard_expired_actionable",
    ):
        assert conflicts[field] == 1

    blockers: list[str] = []
    warnings: list[str] = []
    integrated_radar.apply_integrated_artifact_checks(
        SimpleNamespace(strict=True, integrated_conflicts=conflicts),
        blockers,
        warnings,
    )
    for field in (
        "integrated_candidate_expired_actionable",
        "integrated_core_expired_actionable",
        "integrated_preview_expired_actionable",
        "integrated_dashboard_expired_actionable",
    ):
        assert f"{field}=1" in blockers


def test_doctor_blocks_outcome_projection_and_cohort_drift():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as artifact_doctor
    from crypto_rsi_scanner.event_alpha.outcomes.integrated_radar_outcome_rows import (
        _outcome_placeholder_row,
    )

    candidate = _candidate()
    outcome = _outcome_placeholder_row(
        candidate,
        now="2026-06-15T16:01:00+00:00",
    )
    clean = artifact_doctor._integrated_outcome_conflicts(  # noqa: SLF001
        [candidate], [outcome], core_rows=[_core(candidate)]
    )
    assert clean["integrated_outcome_decision_projection_mismatch"] == 0

    drifted = {
        **outcome,
        "risk_score": outcome["risk_score"] + 1.0,
        "risk_score_cohort": "80_100",
    }
    conflicts = artifact_doctor._integrated_outcome_conflicts(  # noqa: SLF001
        [candidate], [drifted], core_rows=[_core(candidate)]
    )
    assert conflicts["integrated_outcome_decision_projection_mismatch"] == 1
