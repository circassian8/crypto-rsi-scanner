"""Campaign integration for fixed-window shadow anomaly episodes."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations import market_no_send_io
from crypto_rsi_scanner.event_alpha.operations import market_no_send_publication
from crypto_rsi_scanner.event_alpha.operations import market_observation_campaign
from crypto_rsi_scanner.event_alpha.operations import market_observation_campaign_episodes
from crypto_rsi_scanner.event_alpha.operations import market_observation_campaign_snapshots
from crypto_rsi_scanner.event_alpha.operations import market_observation_outcomes
from crypto_rsi_scanner.event_alpha.operations.market_no_send_history_cache import (
    LIVE_HISTORY_CACHE_NAMESPACE,
)
from crypto_rsi_scanner.event_alpha.operations.market_no_send_models import (
    MarketNoSendError,
)
from crypto_rsi_scanner.event_alpha.outcomes import outcome_eligibility
from crypto_rsi_scanner.project_health import radar_north_star
from crypto_rsi_scanner.event_alpha.radar import decision_model
from crypto_rsi_scanner.event_alpha.radar.decision_model_surfaces import (
    decision_model_values,
)
from tests.event_alpha.campaign_test_support import write_countable_generation
from tests.event_alpha.test_decision_episode_scorecard import (
    _outcome as _scorecard_outcome,
)


_START = datetime(2026, 7, 13, 15, tzinfo=timezone.utc)


def _candidate(
    namespace: str,
    observed: datetime,
    *,
    anomaly_id: str,
) -> dict[str, object]:
    observed_at = observed.isoformat()
    row: dict[str, object] = {
        "row_type": "event_integrated_radar_candidate",
        "schema_id": "integrated_radar_candidate_v1",
        "schema_version": "event_alpha_schema_v1",
        "run_id": f"{observed_at}|no_key_live",
        "profile": "no_key_live",
        "artifact_namespace": namespace,
        "candidate_id": "candidate-episode",
        "core_opportunity_id": "core-episode",
        "observed_at": observed_at,
        "symbol": "EPISODE",
        "coin_id": "episode-token",
        "canonical_asset_id": "episode-token",
        "instrument_resolver_status": "resolved",
        "instrument_resolver_confidence": 0.99,
        "instrument_identity_trusted": True,
        "is_tradable_asset": True,
        "opportunity_type": "DIAGNOSTIC",
        "market_state_class": "confirmed_breakout",
        "anomaly_type": "confirmed_breakout",
        "market_anomaly_id": anomaly_id,
        "market_anomaly_bucket": "high_liquidity_breakout",
        "source_origin": "market_anomaly",
        "source_origins": ["market_anomaly"],
        "source_pack": "market_anomaly_pack",
        "market_snapshot": {
            "market_data_source": "coingecko",
            "observed_at": observed_at,
            "freshness_status": "fresh",
            "market_snapshot_id": f"snapshot-{anomaly_id}",
        },
        "market_state_snapshot": {
            "return_unit": "percent_points",
            "return_4h": 12.0,
            "return_24h": 20.0,
            "relative_return_vs_btc_4h": 9.0,
            "volume_zscore_24h": 3.5,
            "volume_to_market_cap": 0.30,
            "liquidity_usd": 12_000_000.0,
            "spread_bps": 22.0,
            "freshness_status": "fresh",
        },
        "research_only": True,
        "sent": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
    }
    row.update(decision_model.evaluate_radar_decision(row).to_dict())
    row["decision_projection"] = decision_model_values(row)
    return row


def _generation(base: Path, namespace: str, observed: datetime) -> dict[str, object]:
    candidate = _candidate(
        namespace,
        observed,
        anomaly_id=f"mkt:episode:{namespace}",
    )
    write_countable_generation(
        base,
        namespace,
        observed.isoformat(),
        candidates=[candidate],
    )
    return candidate


def _resign_input_audit(audit: dict[str, object]) -> None:
    audit["audit_digest"] = market_observation_campaign_episodes._digest(  # noqa: SLF001
        {key: value for key, value in audit.items() if key != "audit_digest"}
    )


def _historically_recovered(outcome: dict[str, object]) -> dict[str, object]:
    recovered = deepcopy(outcome)
    recovered.update({
        "historical_price_recovery": True,
        "historical_price_recovery_point_in_time": False,
        "calibration_eligible": False,
        "include_in_performance": False,
    })
    recovered["calibration_ineligible_reasons"] = list(
        outcome_eligibility.calibration_ineligibility_reasons(recovered)
    )
    assert outcome_eligibility.validate_contract(recovered) == []
    return recovered


def test_campaign_report_adds_episode_shadow_without_changing_headline_counts(
    tmp_path: Path,
):
    first = _generation(tmp_path, "episode_generation_a", _START)
    second = _generation(
        tmp_path,
        "episode_generation_b",
        _START + timedelta(hours=9),
    )
    immutable_paths = [
        tmp_path / str(row["artifact_namespace"]) / "event_integrated_radar_candidates.jsonl"
        for row in (first, second)
    ]
    before = {path: path.read_bytes() for path in immutable_paths}

    report = market_observation_campaign.build_campaign_report(
        tmp_path,
        evaluated_at=_START + timedelta(days=2),
    )

    shadow = report["shadow_anomaly_episodes"]
    audit = report["shadow_anomaly_episode_input_audit"]
    assert report["campaign_metrics"]["real_candidates"] == 2
    assert report["outcomes"]["pending"] == 2
    assert shadow["records_eligible"] == 2
    assert shadow["primary_episode_count"] == 1
    assert shadow["primary_repeat_member_count"] == 1
    assert shadow["sensitivity_counts"] == {
        "12h": {"episode_count": 1, "repeat_member_count": 1},
        "24h": {"episode_count": 1, "repeat_member_count": 1},
        "48h": {"episode_count": 1, "repeat_member_count": 1},
    }
    assert shadow["episodes"][0]["representative"]["artifact_namespace"] == (
        "episode_generation_a"
    )
    scorecard = report["decision_v2_episode_outcome_scorecard"]
    assert scorecard["representative_count"] == 1
    assert scorecard["outcome_state_counts"]["contract_excluded"] == 1
    assert scorecard["policy_conclusion"] == "insufficient_for_policy_change"
    frontier = report["protocol_v2_episode_coverage_frontier"]
    assert frontier["schema_id"] == (
        "decision_radar.protocol_v2_episode_coverage_frontier"
    )
    assert frontier["episode_count"] == 1
    assert frontier["observed_route_count"] == 1
    assert frontier["zero_episode_route_count"] == 7
    assert frontier["observed_primary_origin_count"] == 1
    assert frontier["zero_episode_primary_origin_count"] == 6
    assert frontier["minimum_sample_policy_sealed"] is False
    assert frontier["statistical_independence_claim"] is False
    assert frontier["protocol_v2_evidence_eligible"] is False
    assert frontier["provider_calls"] == frontier["writes"] == 0
    assert audit["schema_id"] == (
        "event_alpha.shadow_anomaly_episode_input_audit"
    )
    assert audit["status"] == "partial"
    assert audit["candidate_input_status"] == "ready"
    assert audit["outcome_input_status"] == "unavailable"
    assert audit["outcome_ledger_status"] == "missing"
    assert audit["missing_outcome_join_count"] == 2
    assert audit["provider_calls"] == audit["writes"] == 0
    assert market_observation_campaign_episodes.validate_input_audit(
        audit,
        episode_value=shadow,
    ) == []
    assert all(
        not key.startswith("_")
        for group in (
            report["authoritative_generations"],
            report["non_authoritative_complete_generations"],
            report["excluded_invalid_generations"],
        )
        for row in group
        for key in row
    )
    markdown = market_observation_campaign.format_campaign_report(report)
    assert "## Anomaly episodes (shadow)" in markdown
    assert "Primary 24h episodes: `1`" in markdown
    assert "Outcome ledger status: `missing`" in markdown
    assert "Structural membership status: `ready`" in markdown
    assert "## Decision-v2 episode outcomes (shadow)" in markdown
    assert "Policy conclusion: `insufficient_for_policy_change`" in markdown
    assert "## Protocol-v2 episode coverage frontier" in markdown
    assert "Observed routes: `1`/`8`" in markdown
    assert "Observed primary origins: `1`/`7`" in markdown
    assert "| calendar_risk | unobserved | 0 |" in markdown
    assert "Duplicate outcome identities: groups=`0`, rows=`0`" in markdown
    assert (
        "Cross-candidate outcome collisions: groups=`0`, candidates=`0`, rows=`0`"
        in markdown
    )
    assert before == {path: path.read_bytes() for path in immutable_paths}
    serialized = repr(report)
    assert "_candidate_snapshot_" not in serialized
    assert "_core_snapshot_" not in serialized
    assert "_integrated_outcome_snapshot_" not in serialized


def test_campaign_report_scores_one_exact_primary_representative(tmp_path: Path):
    namespace = "episode_scorecard_exact"
    candidate = _candidate(
        namespace,
        _START,
        anomaly_id=f"mkt:episode:{namespace}",
    )
    core = market_observation_outcomes._candidate_projection_core(  # noqa: SLF001
        candidate,
        projection=decision_model_values(candidate),
    )
    assert core is not None
    core["integrated_candidate_id"] = candidate["candidate_id"]
    evaluated = _START + timedelta(days=2)
    outcome = _scorecard_outcome(
        candidate,
        core,
        persisted_evaluated_at=evaluated,
        primary_price=110.0,
    )
    write_countable_generation(
        tmp_path,
        namespace,
        _START.isoformat(),
        candidates=[candidate],
        core_rows=[core],
    )
    history_dir = tmp_path / LIVE_HISTORY_CACHE_NAMESPACE
    history_dir.mkdir()
    market_no_send_io.write_jsonl(
        history_dir / market_observation_outcomes.CAMPAIGN_OUTCOMES_FILENAME,
        [outcome],
    )

    report = market_observation_campaign.build_campaign_report(
        tmp_path,
        evaluated_at=evaluated,
    )

    scorecard = report["decision_v2_episode_outcome_scorecard"]
    representative = scorecard["representatives"][0]
    assert scorecard["matured_episode_count"] == 1
    assert scorecard["scoreable_directional_episode_count"] == 1
    assert representative["candidate_id"] == candidate["candidate_id"]
    assert representative["outcome_state"] == "matured"
    assert representative["direction_alignment"] == "aligned"
    assert representative["primary_horizon_return"] == pytest.approx(0.10)
    assert {row["source_role"] for row in scorecard["source_artifact_bindings"]} == {
        "candidate",
        "core",
        "outcome",
    }
    assert scorecard["provider_calls"] == scorecard["writes"] == 0
    markdown = market_observation_campaign.format_campaign_report(report)
    assert "| episode-token |" in markdown
    assert "| matured | aligned | 0.10000000 |" in markdown


def test_campaign_report_keeps_recovery_mature_but_excludes_episode_evidence(
    tmp_path: Path,
):
    namespace = "episode_historical_recovery"
    candidate = _candidate(
        namespace,
        _START,
        anomaly_id=f"mkt:episode:{namespace}",
    )
    core = market_observation_outcomes._candidate_projection_core(  # noqa: SLF001
        candidate,
        projection=decision_model_values(candidate),
    )
    assert core is not None
    core["integrated_candidate_id"] = candidate["candidate_id"]
    evaluated = _START + timedelta(days=2)
    outcome = _historically_recovered(
        _scorecard_outcome(
            candidate,
            core,
            persisted_evaluated_at=evaluated,
            primary_price=110.0,
        )
    )
    write_countable_generation(
        tmp_path,
        namespace,
        _START.isoformat(),
        candidates=[candidate],
        core_rows=[core],
    )
    history_dir = tmp_path / LIVE_HISTORY_CACHE_NAMESPACE
    history_dir.mkdir()
    ledger_path = history_dir / market_observation_outcomes.CAMPAIGN_OUTCOMES_FILENAME
    market_no_send_io.write_jsonl(ledger_path, [outcome])
    ledger_before = ledger_path.read_bytes()

    report = market_observation_campaign.build_campaign_report(
        tmp_path,
        evaluated_at=evaluated,
    )

    episode_record = report["shadow_anomaly_episodes"]["episodes"][0][
        "representative"
    ]
    audit = report["shadow_anomaly_episode_input_audit"]
    scorecard = report["decision_v2_episode_outcome_scorecard"]
    representative = scorecard["representatives"][0]
    assert report["outcomes"]["matured"] == 1
    assert outcome["maturation_state"] == "matured"
    assert outcome["primary_horizon_return"] == pytest.approx(0.10)
    assert episode_record["outcome_evidence_status"] == "unavailable"
    assert episode_record["outcome_evidence_reasons"] == [
        "historical_price_recovery_not_point_in_time"
    ]
    assert episode_record["primary_horizon_return"] is None
    assert audit["exact_outcome_join_count"] == 1
    assert audit["outcome_evidence_status_counts"] == {"unavailable": 1}
    assert representative["outcome_state"] == "contract_excluded"
    assert representative["contract_exclusion_reasons"] == [
        "historical_price_recovery_not_point_in_time"
    ]
    assert representative["primary_horizon_return"] is None
    assert scorecard["matured_episode_count"] == 0
    assert scorecard["scoreable_directional_episode_count"] == 0
    assert ledger_path.read_bytes() == ledger_before


def test_raw_duplicate_outcome_identity_is_explicit_before_legacy_dedup(
    tmp_path: Path,
):
    candidate = _generation(tmp_path, "episode_duplicate_outcome", _START)
    identity_key = outcome_eligibility.build_outcome_identity_fields(candidate)[
        "outcome_identity_key"
    ]
    history_dir = tmp_path / LIVE_HISTORY_CACHE_NAMESPACE
    history_dir.mkdir()
    shared = {
        "source_artifact_namespace": candidate["artifact_namespace"],
        "candidate_id": candidate["candidate_id"],
        "outcome_identity_key": identity_key,
        "campaign_outcome_ledger": True,
    }
    market_no_send_io.write_jsonl(
        history_dir / market_observation_outcomes.CAMPAIGN_OUTCOMES_FILENAME,
        [
            {**shared, "maturation_state": "pending"},
            {**shared, "maturation_state": "matured"},
        ],
    )

    report = market_observation_campaign.build_campaign_report(
        tmp_path,
        evaluated_at=_START + timedelta(days=2),
    )

    shadow = report["shadow_anomaly_episodes"]
    audit = report["shadow_anomaly_episode_input_audit"]
    assert report["outcomes"]["pending"] == 1
    assert shadow["records_eligible"] == 1
    assert shadow["episodes"][0]["representative"][
        "outcome_evidence_status"
    ] == "ambiguous"
    assert "duplicate_outcome_identity" in shadow["episodes"][0]["representative"][
        "outcome_evidence_reasons"
    ]
    assert audit["ambiguous_outcome_join_count"] == 1
    assert audit["duplicate_outcome_identity_group_count"] == 1
    assert audit["conflicting_outcome_identity_group_count"] == 1


def test_shared_outcome_row_is_a_cross_candidate_collision_not_a_duplicate(
    tmp_path: Path,
):
    first = _generation(tmp_path, "episode_collision_a", _START)
    second = _generation(
        tmp_path,
        "episode_collision_b",
        _START + timedelta(hours=1),
    )
    history_dir = tmp_path / LIVE_HISTORY_CACHE_NAMESPACE
    history_dir.mkdir()
    second_key = outcome_eligibility.build_outcome_identity_fields(second)[
        "outcome_identity_key"
    ]
    market_no_send_io.write_jsonl(
        history_dir / market_observation_outcomes.CAMPAIGN_OUTCOMES_FILENAME,
        [{
            "source_artifact_namespace": first["artifact_namespace"],
            "candidate_id": first["candidate_id"],
            "outcome_identity_key": second_key,
            "campaign_outcome_ledger": True,
        }],
    )

    report = market_observation_campaign.build_campaign_report(
        tmp_path,
        evaluated_at=_START + timedelta(days=2),
    )

    shadow = report["shadow_anomaly_episodes"]
    audit = report["shadow_anomaly_episode_input_audit"]
    assert audit["ambiguous_outcome_join_count"] == 2
    assert audit["duplicate_outcome_identity_group_count"] == 0
    assert audit["duplicate_outcome_row_count"] == 0
    assert audit["cross_candidate_outcome_collision_group_count"] == 1
    assert audit["cross_candidate_outcome_collision_candidate_count"] == 2
    assert audit["cross_candidate_outcome_collision_row_count"] == 1
    assert audit["joined_outcome_row_count"] == 1
    assert all(
        representative["outcome_evidence_reasons"]
        == ["outcome_row_claimed_by_multiple_candidates"]
        for representative in (
            episode["representative"] for episode in shadow["episodes"]
        )
    )
    assert market_observation_campaign_episodes.validate_input_audit(
        audit,
        episode_value=shadow,
    ) == []


def test_duplicate_candidate_and_outcome_counters_cannot_be_forged(
    tmp_path: Path,
):
    duplicate = _candidate(
        "episode_duplicate_candidate",
        _START,
        anomaly_id="mkt:episode:duplicate-candidate",
    )
    write_countable_generation(
        tmp_path,
        "episode_duplicate_candidate",
        _START.isoformat(),
        candidates=[duplicate, deepcopy(duplicate)],
    )
    report = market_observation_campaign.build_campaign_report(
        tmp_path,
        evaluated_at=_START + timedelta(days=2),
    )
    audit = report["shadow_anomaly_episode_input_audit"]
    assert audit["duplicate_candidate_group_count"] == 1
    assert audit["duplicate_candidate_row_count"] == 2

    forged_candidate = deepcopy(audit)
    forged_candidate["duplicate_candidate_group_count"] = 999
    _resign_input_audit(forged_candidate)
    assert market_observation_campaign_episodes.validate_input_audit(
        forged_candidate,
        episode_value=report["shadow_anomaly_episodes"],
    )

    candidate = _generation(tmp_path, "episode_duplicate_outcome_forge", _START)
    identity_key = outcome_eligibility.build_outcome_identity_fields(candidate)[
        "outcome_identity_key"
    ]
    history_dir = tmp_path / LIVE_HISTORY_CACHE_NAMESPACE
    history_dir.mkdir(exist_ok=True)
    shared = {
        "source_artifact_namespace": candidate["artifact_namespace"],
        "candidate_id": candidate["candidate_id"],
        "outcome_identity_key": identity_key,
        "campaign_outcome_ledger": True,
    }
    market_no_send_io.write_jsonl(
        history_dir / market_observation_outcomes.CAMPAIGN_OUTCOMES_FILENAME,
        [{**shared, "maturation_state": "pending"}, {**shared, "maturation_state": "matured"}],
    )
    outcome_report = market_observation_campaign.build_campaign_report(
        tmp_path,
        evaluated_at=_START + timedelta(days=2),
    )
    forged_outcome = deepcopy(
        outcome_report["shadow_anomaly_episode_input_audit"]
    )
    forged_outcome["duplicate_outcome_row_count"] = 999
    _resign_input_audit(forged_outcome)
    errors = market_observation_campaign_episodes.validate_input_audit(
        forged_outcome,
        episode_value=outcome_report["shadow_anomaly_episodes"],
    )
    assert "joined_outcome_population_not_closed" in errors
    assert "duplicate_outcome_rows_exceed_joined_population" in errors


def test_campaign_renderer_rejects_tampered_episode_shadow(tmp_path: Path):
    _generation(tmp_path, "episode_tamper", _START)
    report = market_observation_campaign.build_campaign_report(
        tmp_path,
        evaluated_at=_START + timedelta(days=2),
    )
    tampered = deepcopy(report)
    tampered["shadow_anomaly_episodes"]["primary_episode_count"] = 0

    with pytest.raises(
        MarketNoSendError,
        match="shadow anomaly episode report contract invalid",
    ):
        market_observation_campaign.format_campaign_report(tampered)

    tampered_audit = deepcopy(report)
    tampered_audit["shadow_anomaly_episode_input_audit"][
        "outcome_ledger_status"
    ] = "observed"
    with pytest.raises(
        MarketNoSendError,
        match="shadow anomaly episode input audit invalid",
    ):
        market_observation_campaign.format_campaign_report(tampered_audit)

    forged_reasons = deepcopy(report)
    forged_audit = forged_reasons["shadow_anomaly_episode_input_audit"]
    forged_audit["input_status_reason_counts"] = {"invented_reason": 1}
    forged_audit["audit_digest"] = market_observation_campaign_episodes._digest(  # noqa: SLF001
        {
            key: value
            for key, value in forged_audit.items()
            if key != "audit_digest"
        }
    )
    assert "input_status_reason_counts_mismatch" in (
        market_observation_campaign_episodes.validate_input_audit(
            forged_audit,
            episode_value=forged_reasons["shadow_anomaly_episodes"],
        )
    )

    missing_audit = deepcopy(report)
    missing_audit.pop("shadow_anomaly_episode_input_audit")
    with pytest.raises(
        MarketNoSendError,
        match="shadow anomaly episode input audit invalid",
    ):
        market_observation_campaign.format_campaign_report(missing_audit)

    tampered_scorecard = deepcopy(report)
    tampered_scorecard["decision_v2_episode_outcome_scorecard"][
        "matured_episode_count"
    ] += 1
    with pytest.raises(
        MarketNoSendError,
        match="decision episode scorecard report contract invalid",
    ):
        market_observation_campaign.format_campaign_report(tampered_scorecard)

    tampered_frontier = deepcopy(report)
    tampered_frontier["protocol_v2_episode_coverage_frontier"][
        "observed_route_count"
    ] += 1
    with pytest.raises(
        MarketNoSendError,
        match="Protocol-v2 episode coverage frontier invalid",
    ):
        market_observation_campaign.format_campaign_report(tampered_frontier)


def test_campaign_distinguishes_observed_empty_outcome_ledger(tmp_path: Path):
    _generation(tmp_path, "episode_empty_ledger", _START)
    history_dir = tmp_path / LIVE_HISTORY_CACHE_NAMESPACE
    history_dir.mkdir()
    market_no_send_io.write_jsonl(
        history_dir / market_observation_outcomes.CAMPAIGN_OUTCOMES_FILENAME,
        [],
    )

    report = market_observation_campaign.build_campaign_report(
        tmp_path,
        evaluated_at=_START + timedelta(days=2),
    )

    audit = report["shadow_anomaly_episode_input_audit"]
    assert audit["outcome_ledger_status"] == "observed_empty"
    assert audit["outcome_ledger_sha256"] is not None
    assert audit["outcome_input_status"] == "partial"
    assert audit["status"] == "partial"


def test_campaign_reuses_one_candidate_and_ledger_snapshot_across_surfaces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    namespace = "episode_exact_snapshot"
    candidate = _candidate(
        namespace,
        _START,
        anomaly_id=f"mkt:episode:{namespace}",
    )
    core = market_observation_outcomes._candidate_projection_core(  # noqa: SLF001
        candidate,
        projection=decision_model_values(candidate),
    )
    assert core is not None
    core["integrated_candidate_id"] = candidate["candidate_id"]
    integrated_outcome = {
        "candidate_id": candidate["candidate_id"],
        "maturation_state": "matured",
    }
    manifest_path, _manifest, materialized = write_countable_generation(
        tmp_path,
        namespace,
        _START.isoformat(),
        candidates=[candidate],
        core_rows=[core],
        integrated_outcome_rows=[integrated_outcome],
    )
    candidate = materialized[0]
    namespace_dir = manifest_path.parent
    candidate_path = namespace_dir / "event_integrated_radar_candidates.jsonl"
    core_path = namespace_dir / "event_core_opportunities.jsonl"
    integrated_outcome_path = namespace_dir / "event_integrated_radar_outcomes.jsonl"
    history_dir = tmp_path / LIVE_HISTORY_CACHE_NAMESPACE
    history_dir.mkdir()
    ledger_path = (
        history_dir / market_observation_outcomes.CAMPAIGN_OUTCOMES_FILENAME
    )
    identity_key = outcome_eligibility.build_outcome_identity_fields(candidate)[
        "outcome_identity_key"
    ]
    shared = {
        "source_artifact_namespace": candidate["artifact_namespace"],
        "candidate_id": candidate["candidate_id"],
        "outcome_identity_key": identity_key,
        "campaign_outcome_ledger": True,
    }
    market_no_send_io.write_jsonl(
        ledger_path,
        [
            {**shared, "maturation_state": "pending"},
            {**shared, "maturation_state": "matured"},
        ],
    )
    original_read = market_observation_campaign_snapshots.read_regular_bytes
    read_counts = {
        candidate_path: 0,
        core_path: 0,
        integrated_outcome_path: 0,
        ledger_path: 0,
    }

    def mutate_after_snapshot(path: Path, *, missing_ok: bool = False):
        raw = original_read(path, missing_ok=missing_ok)
        if path in read_counts:
            read_counts[path] += 1
            market_no_send_io.write_jsonl(path, [])
        return raw

    monkeypatch.setattr(
        market_observation_campaign_snapshots,
        "read_regular_bytes",
        mutate_after_snapshot,
    )

    report = market_observation_campaign.build_campaign_report(
        tmp_path,
        evaluated_at=_START + timedelta(days=2),
    )

    audit = report["shadow_anomaly_episode_input_audit"]
    assert all(count == 1 for count in read_counts.values())
    assert all(market_no_send_io.read_jsonl(path) == [] for path in read_counts)
    assert report["campaign_metrics"]["real_candidates"] == 1
    generation = report["non_authoritative_complete_generations"][0]
    assert generation["artifact_authority"] == {
        "core_bound": True,
        "core_row_count": 1,
        "integrated_outcomes_bound": True,
        "integrated_outcome_row_count": 1,
    }
    assert generation["outcomes"]["matured"] == 1
    assert report["outcomes"]["pending"] == 1
    assert report["shadow_anomaly_episodes"]["records_eligible"] == 1
    assert audit["raw_outcome_row_count"] == 2
    assert audit["ambiguous_outcome_join_count"] == 1
    assert audit["outcome_ledger_status"] == "observed"
    scorecard = report["decision_v2_episode_outcome_scorecard"]
    assert scorecard["representatives"][0]["outcome_state"] == (
        "contract_excluded"
    )
    bindings = {row["source_role"]: row for row in scorecard["source_artifact_bindings"]}
    assert bindings["candidate"]["artifact_sha256"] is not None
    assert bindings["core"]["artifact_sha256"] is not None
    assert bindings["outcome"]["artifact_sha256"] is not None


def test_current_generation_snapshots_retain_exact_private_bindings(tmp_path: Path):
    namespace = "episode_current_snapshot_bindings"
    candidate = _candidate(
        namespace,
        _START,
        anomaly_id=f"mkt:episode:{namespace}",
    )
    core = market_observation_outcomes._candidate_projection_core(  # noqa: SLF001
        candidate,
        projection=decision_model_values(candidate),
    )
    assert core is not None
    core["integrated_candidate_id"] = candidate["candidate_id"]
    write_countable_generation(
        tmp_path,
        namespace,
        _START.isoformat(),
        candidates=[candidate],
        core_rows=[core],
        integrated_outcome_rows=[{
            "candidate_id": candidate["candidate_id"],
            "maturation_state": "pending",
        }],
    )

    generations, _attempts, excluded = market_observation_campaign._load_generations(  # noqa: SLF001
        tmp_path,
        current_authority={},
    )

    assert excluded == []
    generation = generations[0]
    for label, source in (
        ("candidate", "manifest_candidate_artifact_sha256"),
        ("core", "manifest_core_artifact_sha256"),
        ("integrated_outcome", "manifest_integrated_outcome_artifact_sha256"),
    ):
        assert generation[f"_{label}_snapshot_verified"] is True
        assert generation[f"_{label}_snapshot_binding_source"] == source
        assert generation[f"_{label}_snapshot_row_count"] == 1
        assert generation[f"_{label}_snapshot_size_bytes"] > 0
        assert len(generation[f"_{label}_snapshot_sha256"]) == 64
        assert len(generation[f"_{label}_snapshot_rows"]) == 1
    public = market_observation_campaign_snapshots.public_generation_rows(
        generations
    )
    assert all(not key.startswith("_") for key in public[0])


def test_legacy_support_snapshots_share_one_operator_view_and_allow_missing_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    namespace = "episode_legacy_support_snapshots"
    candidate = _candidate(
        namespace,
        _START,
        anomaly_id=f"mkt:episode:{namespace}",
    )
    core = market_observation_outcomes._candidate_projection_core(  # noqa: SLF001
        candidate,
        projection=decision_model_values(candidate),
    )
    assert core is not None
    core["integrated_candidate_id"] = candidate["candidate_id"]
    manifest_path, _manifest, _rows = write_countable_generation(
        tmp_path,
        namespace,
        _START.isoformat(),
        candidates=[candidate],
        legacy=True,
        core_rows=[core],
        integrated_outcome_rows=[{
            "candidate_id": candidate["candidate_id"],
            "maturation_state": "pending",
        }],
    )
    operator_path = manifest_path.parent / market_observation_campaign.OPERATOR_STATE_FILENAME
    operator = market_no_send_io.read_json_object(operator_path)
    operator["artifacts"]["core_opportunities"].pop("count")
    operator["artifacts"]["integrated_outcomes"].pop("count")
    market_no_send_io.write_json_atomic(operator_path, operator)
    original_read_json = market_observation_campaign._read_json  # noqa: SLF001
    operator_reads = 0

    def counted_read_json(path: Path):
        nonlocal operator_reads
        if path == operator_path:
            operator_reads += 1
        return original_read_json(path)

    monkeypatch.setattr(
        market_observation_campaign,
        "_read_json",
        counted_read_json,
    )

    generations, _attempts, excluded = market_observation_campaign._load_generations(  # noqa: SLF001
        tmp_path,
        current_authority={},
    )

    assert excluded == []
    assert operator_reads == 1
    generation = generations[0]
    assert generation["_candidate_snapshot_binding_source"] == (
        "legacy_operator_candidate_binding"
    )
    assert generation["_core_snapshot_binding_source"] == (
        "legacy_operator_core_binding"
    )
    assert generation["_integrated_outcome_snapshot_binding_source"] == (
        "legacy_operator_integrated_outcome_binding"
    )


def test_legacy_adapter_candidate_with_manifest_digest_uses_manifest_binding(
    tmp_path: Path,
):
    namespace = "episode_legacy_manifest_candidate_binding"
    candidate = _candidate(
        namespace,
        _START,
        anomaly_id=f"mkt:episode:{namespace}",
    )
    manifest_path, manifest, _rows = write_countable_generation(
        tmp_path,
        namespace,
        _START.isoformat(),
        candidates=[candidate],
        legacy=True,
    )
    candidate_path = manifest_path.parent / "event_integrated_radar_candidates.jsonl"
    manifest.update({
        "candidate_artifact": candidate_path.name,
        "candidate_artifact_sha256": hashlib.sha256(
            candidate_path.read_bytes()
        ).hexdigest(),
    })
    market_no_send_io.write_json_atomic(manifest_path, manifest)
    operator_path = manifest_path.parent / market_observation_campaign.OPERATOR_STATE_FILENAME
    operator = market_no_send_io.read_json_object(operator_path)
    operator["artifacts"]["integrated_candidates"]["status"] = "stale"
    market_no_send_io.write_json_atomic(operator_path, operator)

    generations, _attempts, excluded = market_observation_campaign._load_generations(  # noqa: SLF001
        tmp_path,
        current_authority={},
    )

    assert excluded == []
    assert generations[0]["_candidate_snapshot_binding_source"] == (
        "manifest_candidate_artifact_sha256"
    )


def test_current_core_snapshot_detects_post_validation_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    namespace = "episode_current_core_snapshot_drift"
    candidate = _candidate(
        namespace,
        _START,
        anomaly_id=f"mkt:episode:{namespace}",
    )
    core = market_observation_outcomes._candidate_projection_core(  # noqa: SLF001
        candidate,
        projection=decision_model_values(candidate),
    )
    assert core is not None
    core["integrated_candidate_id"] = candidate["candidate_id"]
    manifest_path, _manifest, _rows = write_countable_generation(
        tmp_path,
        namespace,
        _START.isoformat(),
        candidates=[candidate],
        core_rows=[core],
    )
    core_path = manifest_path.parent / "event_core_opportunities.jsonl"
    original_validate = (
        market_no_send_publication.validate_countable_campaign_generation
    )
    mutated = False

    def validate_then_mutate(*args, **kwargs):
        nonlocal mutated
        validation = original_validate(*args, **kwargs)
        assert validation.valid is True
        if not mutated:
            market_no_send_io.write_jsonl(
                core_path,
                [{"core_opportunity_id": "post-validation-drift"}],
            )
            mutated = True
        return validation

    monkeypatch.setattr(
        market_no_send_publication,
        "validate_countable_campaign_generation",
        validate_then_mutate,
    )

    report = market_observation_campaign.build_campaign_report(
        tmp_path,
        evaluated_at=_START + timedelta(days=2),
    )

    assert report["campaign_metrics"]["real_cycles"] == 0
    assert report["excluded_invalid_generations"][0]["validation_errors"] == [
        "generation_snapshot:core_snapshot_digest_mismatch"
    ]


def test_campaign_outcome_ledger_snapshot_exposes_exact_binding_metadata(
    tmp_path: Path,
):
    history_dir = tmp_path / LIVE_HISTORY_CACHE_NAMESPACE
    history_dir.mkdir()
    ledger_path = (
        history_dir / market_observation_outcomes.CAMPAIGN_OUTCOMES_FILENAME
    )
    market_no_send_io.write_jsonl(
        ledger_path,
        [{"candidate_id": "one"}, {"candidate_id": "two"}],
    )

    snapshot = market_observation_campaign_snapshots.campaign_outcome_ledger_snapshot(
        tmp_path,
        history_namespace=LIVE_HISTORY_CACHE_NAMESPACE,
        filename=market_observation_outcomes.CAMPAIGN_OUTCOMES_FILENAME,
    )

    assert snapshot["artifact"] == ledger_path.name
    assert snapshot["status"] == "observed"
    assert snapshot["size_bytes"] == len(ledger_path.read_bytes())
    assert snapshot["row_count"] == 2
    assert snapshot["binding_source"] == "campaign_outcome_ledger_exact_bytes"
    assert len(snapshot["sha256"]) == 64


def test_campaign_market_history_snapshot_exposes_exact_binding_metadata(
    tmp_path: Path,
):
    history_dir = tmp_path / LIVE_HISTORY_CACHE_NAMESPACE
    history_dir.mkdir()
    history_path = history_dir / market_observation_campaign.HISTORY_FILENAME
    market_no_send_io.write_jsonl(
        history_path,
        [{"coin_id": "one", "price": 1.0}, {"coin_id": "two", "price": 2.0}],
    )

    snapshot = market_observation_campaign_snapshots.campaign_market_history_snapshot(
        tmp_path,
        history_namespace=LIVE_HISTORY_CACHE_NAMESPACE,
        filename=market_observation_campaign.HISTORY_FILENAME,
    )

    assert snapshot["artifact"] == history_path.name
    assert snapshot["status"] == "observed"
    assert snapshot["size_bytes"] == len(history_path.read_bytes())
    assert snapshot["row_count"] == 2
    assert snapshot["binding_source"] == "campaign_market_history_exact_bytes"
    assert len(snapshot["sha256"]) == 64


def test_campaign_market_history_snapshot_rejects_parent_symlink(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    market_no_send_io.write_jsonl(
        outside / market_observation_campaign.HISTORY_FILENAME,
        [{"coin_id": "outside", "price": 999.0}],
    )
    (tmp_path / LIVE_HISTORY_CACHE_NAMESPACE).symlink_to(outside, target_is_directory=True)

    snapshot = market_observation_campaign_snapshots.campaign_market_history_snapshot(
        tmp_path,
        history_namespace=LIVE_HISTORY_CACHE_NAMESPACE,
        filename=market_observation_campaign.HISTORY_FILENAME,
    )

    assert snapshot["status"] == "unavailable"
    assert snapshot["rows"] == ()
    assert snapshot["sha256"] is None
    assert snapshot["binding_source"] == "campaign_market_history_path"


def test_post_validation_snapshot_failure_remains_explicit_in_episode_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _generation(tmp_path, "episode_snapshot_failure", _START)

    def fail_after_validation(*args, **kwargs):
        validation = kwargs["validation"]
        assert validation.valid is True
        assert validation.campaign_counted is True
        raise MarketNoSendError("candidate_snapshot_digest_mismatch")

    monkeypatch.setattr(
        market_observation_campaign_snapshots,
        "capture_candidate_snapshot",
        fail_after_validation,
    )

    report = market_observation_campaign.build_campaign_report(
        tmp_path,
        evaluated_at=_START + timedelta(days=2),
    )

    audit = report["shadow_anomaly_episode_input_audit"]
    assert report["campaign_metrics"]["real_cycles"] == 0
    assert report["campaign_metrics"]["real_candidates"] == 0
    assert len(report["excluded_invalid_generations"]) == 1
    assert not any(
        key.startswith("_candidate_snapshot_")
        for key in report["excluded_invalid_generations"][0]
    )
    assert audit["counted_generation_count"] == 1
    assert audit["candidate_snapshot_generation_count"] == 0
    assert audit["generation_rejection_count"] == 1
    assert audit["generation_rejection_reason_counts"] == {
        "candidate_snapshot_missing": 1
    }
    assert audit["candidate_input_status"] == "unavailable"
    assert audit["status"] == "unavailable"


@pytest.mark.parametrize(
    ("drift", "expected_error"),
    (
        ("operator_namespace", "candidate_snapshot_legacy_operator_identity_mismatch"),
        ("operator_run_id", "candidate_snapshot_legacy_operator_identity_mismatch"),
        ("operator_profile", "candidate_snapshot_legacy_operator_identity_mismatch"),
        ("operator_run_mode", "candidate_snapshot_legacy_operator_identity_mismatch"),
        ("operator_provenance", "candidate_snapshot_legacy_operator_identity_mismatch"),
        ("binding_status", "candidate_snapshot_legacy_binding_mismatch"),
        ("binding_run_id", "candidate_snapshot_legacy_binding_mismatch"),
    ),
)
def test_legacy_snapshot_revalidates_operator_after_initial_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
    expected_error: str,
):
    namespace = f"episode_legacy_{drift}"
    candidate = _candidate(
        namespace,
        _START,
        anomaly_id=f"mkt:episode:{namespace}",
    )
    manifest_path, _manifest, _rows = write_countable_generation(
        tmp_path,
        namespace,
        _START.isoformat(),
        candidates=[candidate],
        legacy=True,
    )
    operator_path = manifest_path.parent / market_observation_campaign.OPERATOR_STATE_FILENAME
    original_validate = (
        market_no_send_publication.validate_countable_campaign_generation
    )
    mutated = False

    def validate_then_mutate(*args, **kwargs):
        nonlocal mutated
        validation = original_validate(*args, **kwargs)
        assert validation.valid is True
        assert validation.legacy_adapter is True
        if not mutated:
            operator = market_no_send_io.read_json_object(operator_path)
            binding = operator["artifacts"]["integrated_candidates"]
            if drift == "operator_namespace":
                operator["artifact_namespace"] = "drifted-namespace"
            elif drift == "operator_run_id":
                operator["run_id"] = "drifted-run"
            elif drift == "operator_profile":
                operator["profile"] = "drifted-profile"
            elif drift == "operator_run_mode":
                operator["run_mode"] = "drifted-mode"
            elif drift == "operator_provenance":
                operator["market_no_send_provenance"] = {
                    **operator["market_no_send_provenance"],
                    "provider": "drifted-provider",
                }
            elif drift == "binding_status":
                binding["status"] = "stale"
            else:
                binding["run_id"] = "drifted-run"
            market_no_send_io.write_json_atomic(operator_path, operator)
            mutated = True
        return validation

    monkeypatch.setattr(
        market_no_send_publication,
        "validate_countable_campaign_generation",
        validate_then_mutate,
    )

    report = market_observation_campaign.build_campaign_report(
        tmp_path,
        evaluated_at=_START + timedelta(days=2),
    )

    assert report["campaign_metrics"]["real_cycles"] == 0
    excluded = report["excluded_invalid_generations"]
    assert len(excluded) == 1
    assert excluded[0]["validation_errors"] == [
        f"generation_snapshot:{expected_error}"
    ]
    audit = report["shadow_anomaly_episode_input_audit"]
    assert audit["counted_generation_count"] == 1
    assert audit["generation_rejection_reason_counts"] == {
        "candidate_snapshot_missing": 1
    }
    assert audit["candidate_input_status"] == "unavailable"


def test_non_authoritative_pointer_is_not_reported_as_current_authority(
    tmp_path: Path,
):
    candidate = _generation(tmp_path, "episode_pointer_target", _START)
    market_no_send_io.write_json_atomic(
        tmp_path / market_observation_campaign.CURRENT_NAMESPACE_POINTER,
        {
            "artifact_namespace": candidate["artifact_namespace"],
            "run_id": candidate["run_id"],
            "revision": 1,
        },
    )

    report = market_observation_campaign.build_campaign_report(
        tmp_path,
        evaluated_at=_START + timedelta(days=2),
    )

    conclusion = report["campaign_v2_conclusion"]
    assert report["pointer"]["status"] != "authoritative"
    assert conclusion["current_authority"] is None
    assert conclusion["pointer_target"]["artifact_namespace"] == (
        "episode_pointer_target"
    )
    assert "but no current authority is proven" in conclusion["summary"]
    markdown = market_observation_campaign.format_campaign_report(report)
    assert "Current authority namespace: `none`" in markdown
    assert "Pointer target namespace: `episode_pointer_target`" in markdown


def test_north_star_freezes_shadow_episode_measurement_policy():
    policy = radar_north_star.build_north_star()["shadow_anomaly_episode_policy"]

    assert policy["schema_id"] == "event_alpha.shadow_anomaly_episodes"
    assert policy["method"] == "fixed_start_window_declustering"
    assert policy["primary_window_hours"] == 24
    assert policy["sensitivity_window_hours"] == [12, 24, 48]
    assert policy["routing_eligible"] is False
    assert policy["decision_score_eligible"] is False
    assert policy["statistical_independence_claim"] is False
    assert policy["auto_apply"] is False
    assert "## Shadow Anomaly Episodes" in radar_north_star.format_north_star(
        radar_north_star.build_north_star()
    )
