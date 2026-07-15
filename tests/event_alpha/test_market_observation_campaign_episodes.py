"""Campaign integration for fixed-window shadow anomaly episodes."""

from __future__ import annotations

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
        not key.startswith("_candidate_snapshot_")
        for group in (
            report["authoritative_generations"],
            report["non_authoritative_complete_generations"],
        )
        for row in group
        for key in row
    )
    markdown = market_observation_campaign.format_campaign_report(report)
    assert "## Anomaly episodes (shadow)" in markdown
    assert "Primary 24h episodes: `1`" in markdown
    assert "Outcome ledger status: `missing`" in markdown
    assert "Structural membership status: `ready`" in markdown
    assert "Duplicate outcome identities: groups=`0`, rows=`0`" in markdown
    assert (
        "Cross-candidate outcome collisions: groups=`0`, candidates=`0`, rows=`0`"
        in markdown
    )
    assert before == {path: path.read_bytes() for path in immutable_paths}


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
    candidate = _generation(tmp_path, "episode_exact_snapshot", _START)
    candidate_path = (
        tmp_path
        / str(candidate["artifact_namespace"])
        / "event_integrated_radar_candidates.jsonl"
    )
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
    read_counts = {candidate_path: 0, ledger_path: 0}

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
    assert read_counts == {candidate_path: 1, ledger_path: 1}
    assert market_no_send_io.read_jsonl(candidate_path) == []
    assert market_no_send_io.read_jsonl(ledger_path) == []
    assert report["campaign_metrics"]["real_candidates"] == 1
    assert report["outcomes"]["pending"] == 1
    assert report["shadow_anomaly_episodes"]["records_eligible"] == 1
    assert audit["raw_outcome_row_count"] == 2
    assert audit["ambiguous_outcome_join_count"] == 1
    assert audit["outcome_ledger_status"] == "observed"


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
        f"candidate_snapshot:{expected_error}"
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
