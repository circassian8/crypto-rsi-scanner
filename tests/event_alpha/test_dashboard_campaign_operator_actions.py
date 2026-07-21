from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from crypto_rsi_scanner.event_alpha.dashboard.campaign_operator_actions import (
    MAX_CAMPAIGN_REPORT_BYTES,
    load_campaign_operator_actions,
)
from crypto_rsi_scanner.event_alpha.dashboard.operator_work_queue import (
    render_operator_work_queue,
)
from crypto_rsi_scanner.event_alpha.dashboard.campaign_page import (
    render_campaign_page,
)
from crypto_rsi_scanner.event_alpha.dashboard.system_pages import render_health_page
from crypto_rsi_scanner.event_alpha.dashboard.today_page import (
    _control_regime_generation_audit_detail,
    _control_regime_input_detail,
    render_today_page,
)
from crypto_rsi_scanner.event_alpha.operations import (
    market_no_send_features,
    market_observation_campaign_episode_frontier,
    market_observation_campaign_regime_audit,
    market_observation_campaign_shadow_surprise,
)
from tests.event_alpha.test_decision_episode_scorecard import (
    _candidate,
    _core,
    _episode,
    _outcome,
    _score,
)
from tests.event_alpha.test_dashboard_system_pages_v1 import _snapshot


_GENERATED_AT = "2026-07-18T20:43:03.720770+00:00"
_ASSET_IDS = tuple(f"asset-{index:02d}" for index in range(30))


@lru_cache(maxsize=1)
def _episode_contracts() -> tuple[dict[str, object], dict[str, object]]:
    observed = datetime.fromisoformat(_GENERATED_AT) - timedelta(days=2)
    evaluated = datetime.fromisoformat(_GENERATED_AT)
    candidate = _candidate("dashboard-frontier", observed)
    core = _core(candidate)
    outcome = _outcome(
        candidate,
        core,
        persisted_evaluated_at=evaluated,
        primary_price=110.0,
    )
    scorecard = _score(
        _episode([candidate], evaluated_at=evaluated),
        [candidate],
        [core],
        [outcome],
        evaluated_at=evaluated,
    )
    frontier = (
        market_observation_campaign_episode_frontier
        .build_protocol_v2_episode_coverage_frontier(scorecard)
    )
    return scorecard, frontier


def _current_regime_rows() -> list[dict[str, object]]:
    rows = []
    for rank in range(1, 31):
        observation_id = f"regime-current-{rank}"
        anchor_id = f"regime-anchor-{rank}"
        rows.append({
            "canonical_asset_id": "bitcoin" if rank == 1 else f"asset-{rank:02d}",
            "symbol": "BTC" if rank == 1 else f"A{rank:02d}",
            "observed_at": _GENERATED_AT,
            "point_in_time_universe_member": True,
            "point_in_time_volume_rank": rank,
            "point_in_time_universe_size": 30,
            "point_in_time_universe_limit": 30,
            "point_in_time_universe_policy": "bounded_top_liquid_by_total_volume",
            "market_history": {
                "baseline_counted": True,
                "observation_id": observation_id,
            },
            "temporal_return_24h": rank / 100.0,
            "return_units": {"temporal_return_24h": "percent_points"},
            "market_feature_evidence": {
                "temporal_return_24h": {
                    "basis": "temporal_baseline",
                    "status": "ready",
                    "calculation": "price_horizon_return",
                    "sample_count": 1,
                    "current_observation_id": observation_id,
                    "baseline_first_observation_id": anchor_id,
                    "baseline_last_observation_id": anchor_id,
                    "baseline_input_observation_count": 1,
                    "baseline_observation_ids_sha256": hashlib.sha256(
                        json.dumps([anchor_id], separators=(",", ":")).encode()
                    ).hexdigest(),
                    "providers": ["coingecko"],
                    "data_modes": ["live"],
                    "research_only": True,
                }
            },
        })
    return rows


def _current_regime_input() -> dict[str, object]:
    diagnostic = (
        market_no_send_features
        .point_in_time_control_market_regime_input_diagnostic(
            _current_regime_rows()
        )
    )
    return {
        "schema_id": "decision_radar.current_authority_control_market_regime_input",
        "schema_version": 1,
        "status": "ready",
        "artifact_namespace": "radar_market_no_send_current",
        "run_id": "2026-07-14T10:00:00+00:00|no_key_live",
        "revision": 7,
        "operator_state_sha256": "c" * 64,
        "source_artifact": "event_market_no_send_market_rows.json",
        "source_artifact_sha256": "d" * 64,
        "source_artifact_size_bytes": 1_024,
        "source_row_count": 30,
        "source_binding_source": "manifest_request_cache_sha256",
        "source_snapshot_verified": True,
        "diagnostic": diagnostic,
        "current_authority_only": True,
        "report_replay_only": True,
        "retained_history_mutated": False,
        "historical_context_backfilled": False,
        "provider_calls": 0,
        "writes": 0,
        "research_only": True,
    }


def _control_regime_generation_audit() -> dict[str, object]:
    rows = _current_regime_rows()
    return (
        market_observation_campaign_regime_audit
        .build_control_regime_generation_audit([{
            "artifact_namespace": "radar_market_no_send_current",
            "run_id": "2026-07-14T10:00:00+00:00|no_key_live",
            "observed_at": _GENERATED_AT,
            "campaign_counted": True,
            "_market_source_snapshot_rows": rows,
            "_market_source_snapshot_sha256": "d" * 64,
            "_market_source_snapshot_row_count": len(rows),
            "_market_source_snapshot_verified": True,
        }])
    )


@lru_cache(maxsize=1)
def _shadow_surprise_audit() -> dict[str, object]:
    end = datetime.fromisoformat(_GENERATED_AT)
    rows: list[dict[str, object]] = []
    for asset_index, asset_id in enumerate(("asset-a", "bitcoin", "ethereum")):
        for index in range(12):
            volume = float(
                1_000_000
                + asset_index * 200_000
                + index * 17_000
                + (index % 3) * 3_000
            )
            market_cap = float(10_000_000 + asset_index * 2_000_000 + index * 9_000)
            rows.append({
                "observation_id": f"shadow-{asset_id}-{index}",
                "canonical_asset_id": asset_id,
                "observed_at": (end - timedelta(hours=11 - index)).isoformat(),
                "price": float(
                    100 * (asset_index + 1)
                    + index * (0.37 + asset_index * 0.11)
                    + (index % 4) * 0.07
                ),
                "volume_24h": volume,
                "market_cap": market_cap,
                "turnover_24h": volume / market_cap,
                "feature_basis": {
                    "price": "provider_observed",
                    "volume_24h": "provider_observed",
                    "market_cap": "provider_observed",
                    "turnover_24h": "derived_provider_ratio",
                },
                "baseline_counted": True,
                "research_only": True,
            })
    return (
        market_observation_campaign_shadow_surprise
        .build_campaign_shadow_surprise_audit(
            {
                "rows": tuple(rows),
                "status": "observed",
                "artifact": "event_market_history.jsonl",
                "sha256": "e" * 64,
                "size_bytes": 4_096,
                "row_count": len(rows),
                "binding_source": "campaign_market_history_exact_bytes",
            },
            minimum_sample_count=4,
        )
    )


def _campaign_report() -> dict[str, object]:
    scorecard, frontier = _episode_contracts()
    return {
        "schema_id": "decision_radar_live_observation_campaign_report_v2",
        "schema_version": "decision_radar_live_observation_campaign_report_v2",
        "row_type": "decision_radar_live_observation_campaign_report",
        "contract_version": 2,
        "measurement_program": "decision_radar_live_observation_campaign_v2",
        "generated_at": _GENERATED_AT,
        "campaign_status": "in_progress_baseline_warming",
        "pointer": {
            "artifact_namespace": "radar_market_no_send_current",
            "run_id": "2026-07-14T10:00:00+00:00|no_key_live",
            "revision": 7,
            "status": "authoritative",
            "generation_authority_status": "authoritative",
            "readiness_validation": "passed",
            "exact_operator_binding": True,
            "readiness_error": None,
            "authority_checked_at": _GENERATED_AT,
        },
        "campaign_metrics": {
            "real_cycles": 21,
            "real_observations": 630,
            "retained_observation_count": 630,
            "baseline_counted_observation_count": 600,
            "baseline_warm_asset_count": 0,
            "historical_ideas": 5,
            "matured_outcomes": 1,
            "pending_outcomes": 3,
            "review_timing_action_required": 3,
            "spread_available_count": 0,
        },
        "authoritative_generations": [
            {
                "artifact_namespace": "radar_market_no_send_current",
                "run_id": "2026-07-14T10:00:00+00:00|no_key_live",
                "data_quality": {
                    "baseline_status_counts": {"warming": 30},
                },
                "publication": {"currently_authoritative": True},
                "current_authority_control_market_regime_input": (
                    _current_regime_input()
                ),
            }
        ],
        "control_market_regime_generation_audit": (
            _control_regime_generation_audit()
        ),
        "shadow_temporal_surprise_campaign_audit": deepcopy(
            _shadow_surprise_audit()
        ),
        "baseline_maturity": {
            "next_eligible_observation_at": (
                "2026-07-18T21:43:03.720770+00:00"
            ),
            "current_universe_maturity": {
                "status": "warming",
                "expected_asset_count": 30,
                "observed_asset_count": 30,
                "observed_asset_ids": list(_ASSET_IDS),
                "missing_asset_count": 0,
                "missing_asset_ids": [],
                "non_warm_asset_ids": list(_ASSET_IDS),
                "baseline_warm_asset_count": 0,
                "next_cycle_point_in_time_eligible_at": (
                    "2026-07-18T21:43:03.720770+00:00"
                ),
                "next_cycle_point_in_time_eligible_asset_count": 0,
                "next_cycle_point_in_time_basis": (
                    "same_asset_retained_history_before_future_observation"
                ),
                "baseline_feature_readiness": _baseline_feature_groups(),
            }
        },
        "human_review_queue": {
            "schema_id": "decision_radar.idea_review_timing_queue_summary",
            "schema_version": 1,
            "row_type": "decision_radar_idea_review_timing_queue_summary",
            "status": "action_required",
            "eligible_idea_count": 3,
            "action_required_count": 3,
            "not_viewed_count": 3,
            "in_review_count": 0,
            "complete_count": 0,
            "skipped_candidate_count": 2,
            "operator_queue_command": (
                "make radar-review-timing-queue PYTHON=.venv/bin/python"
            ),
            "commands_require_explicit_confirmation": True,
            "absolute_paths_or_action_commands_embedded": False,
            "dashboard_reads_recorded_as_human_actions": False,
            "automatic_policy_effect": "none",
            "provider_calls": 0,
            "writes": 0,
            "research_only": True,
            "safety": _zero_safety(),
            "records": [
                {
                    "artifact_namespace": f"published-{index}",
                    "idea_id": "iar:634eae4a52fb",
                    "radar_route": route,
                    "review_status": "not_viewed",
                    "idea_available_at": f"2026-07-18T0{index}:00:00+00:00",
                    "ignored_absolute_path": "/private/outside/generation",
                }
                for index, route in enumerate(
                    ("dashboard_watch", "diagnostic", "dashboard_watch"),
                    start=2,
                )
            ],
        },
        "decision_v2_episode_outcome_scorecard": deepcopy(scorecard),
        "protocol_v2_episode_coverage_frontier": deepcopy(frontier),
        "outcomes": {
            "matured": 1,
            "pending": 3,
            "due_missing_price": 1,
            "due_missing_price_details": [
                {
                    "symbol": "DEXE",
                    "historical_point_in_time_evidence_required": True,
                    "interpolation_permitted": False,
                    "automatic_threshold_change_permitted": False,
                    "research_only": True,
                }
            ],
        },
        "data_quality_limitations": [
            {
                "category": "execution_quality_spread",
                "provider_selection": "selected_bybit_usdt_linear_perpetuals",
                "evidence_status": "awaiting_authorized_immutable_capture",
                "next_safe_command": (
                    "make radar-execution-quality-bybit-readiness "
                    "PYTHON=.venv/bin/python"
                ),
            },
            {"category": "temporal_baseline_maturity"},
        ],
        "safety": {
            "research_only": True,
            "no_trade_recommendation": True,
            "provider_authorization_modified": False,
            "automatic_route_changes": False,
            "automatic_threshold_changes": False,
            "normal_rsi_signal_rows_written": 0,
            "paper_trades_created": 0,
            "provider_calls_made_by_report": 0,
            "telegram_sends": 0,
            "trades_created": 0,
            "triggered_fade_created": 0,
        },
        "ignored_absolute_path": "/private/outside/report",
    }


def _zero_safety() -> dict[str, int]:
    return {
        "authorization_mutations": 0,
        "dashboard_authority_mutations": 0,
        "event_alpha_paper_trades": 0,
        "event_alpha_triggered_fade": 0,
        "normal_rsi_writes": 0,
        "orders": 0,
        "production_policy_mutations": 0,
        "provider_calls": 0,
        "telegram_sends": 0,
        "trades": 0,
    }


def _baseline_feature_groups() -> dict[str, dict[str, object]]:
    specs = (
        ("btc_eth_relative", 0, 3, 3, 68_150, 111_600),
        ("returns_1h", 0, 7, 7, 455_181, 28_800),
        ("returns_24h", 0, 0, 3, 68_150, 111_600),
        ("returns_4h", 0, 7, 7, 455_181, 39_600),
        ("turnover", 30, 21, 21, 455_181, 25_200),
        ("volatility", 0, 3, 3, 68_150, 111_600),
        ("volume", 30, 21, 21, 455_181, 25_200),
    )
    groups: dict[str, dict[str, object]] = {}
    for name, warm, minimum, maximum, minimum_coverage, required_coverage in specs:
        deficit_rows = []
        for index, asset_id in enumerate(_ASSET_IDS[warm:]):
            sample_count = minimum if index == 0 else maximum
            coverage_seconds = minimum_coverage if index == 0 else 455_181
            deficit_rows.append(
                {
                    "canonical_asset_id": asset_id,
                    "status": "warming",
                    "sample_count": sample_count,
                    "required_sample_count": 8,
                    "sample_deficit": max(0, 8 - sample_count),
                    "coverage_seconds": coverage_seconds,
                    "required_coverage_seconds": required_coverage,
                    "coverage_deficit_seconds": max(
                        0, required_coverage - coverage_seconds
                    ),
                }
            )
        groups[name] = {
            "warm_asset_count": warm,
            "warming_asset_count": 30 - warm,
            "cold_asset_count": 0,
            "other_asset_count": 0,
            "asset_count": 30,
            "minimum_sample_count": minimum,
            "maximum_sample_count": maximum,
            "required_sample_count": 8,
            "sample_count_deficit_asset_count": 0 if minimum >= 8 else 30,
            "minimum_coverage_seconds": minimum_coverage,
            "maximum_coverage_seconds": 455_181,
            "required_coverage_seconds": required_coverage,
            "coverage_deficit_asset_count": (
                1 if minimum_coverage < required_coverage else 0
            ),
            "next_cycle_point_in_time_eligible_asset_count": warm,
            "deficit_assets": deficit_rows,
        }
    return groups


def _partial_feature_groups() -> dict[str, dict[str, object]]:
    required_coverage = {
        "btc_eth_relative": 111_600,
        "returns_1h": 28_800,
        "returns_24h": 111_600,
        "returns_4h": 39_600,
        "turnover": 25_200,
        "volatility": 111_600,
        "volume": 25_200,
    }
    return {
        name: {
            "warm_asset_count": 1,
            "warming_asset_count": 1,
            "cold_asset_count": 0,
            "other_asset_count": 0,
            "asset_count": 2,
            "minimum_sample_count": 7,
            "maximum_sample_count": 8,
            "required_sample_count": 8,
            "sample_count_deficit_asset_count": 1,
            "minimum_coverage_seconds": required + 3_600,
            "maximum_coverage_seconds": required + 3_600,
            "required_coverage_seconds": required,
            "coverage_deficit_asset_count": 0,
            "next_cycle_point_in_time_eligible_asset_count": 1,
            "deficit_assets": [
                {
                    "canonical_asset_id": "asset-b",
                    "status": "warming",
                    "sample_count": 7,
                    "required_sample_count": 8,
                    "sample_deficit": 1,
                    "coverage_seconds": required + 3_600,
                    "required_coverage_seconds": required,
                    "coverage_deficit_seconds": 0,
                }
            ],
        }
        for name, required in required_coverage.items()
    }


def _write_report(root: Path, report: dict[str, object]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "RADAR_LIVE_OBSERVATION_CAMPAIGN_REPORT.json").write_text(
        json.dumps(report, sort_keys=True),
        encoding="utf-8",
    )


def _load(root: Path) -> dict[str, object]:
    return load_campaign_operator_actions(
        root,
        artifact_namespace="radar_market_no_send_current",
        run_id="2026-07-14T10:00:00+00:00|no_key_live",
        revision=7,
        operator_state_sha256="c" * 64,
        current_market_observations=tuple(
            {"temporal_baseline_status": "warming"} for _index in range(30)
        ),
    )


def test_campaign_operator_actions_projects_exact_safe_human_work(tmp_path: Path) -> None:
    _write_report(tmp_path, _campaign_report())

    result = _load(tmp_path)

    assert result["status"] == "ready"
    assert result["authority"] == "pointer_matched_campaign_context"
    assert result["provider_calls"] == result["writes"] == 0
    assert result["campaign_metrics"]["real_cycles"] == 21
    assert result["human_review"]["action_required_count"] == 3
    assert result["human_review"]["next_safe_command"] == (
        "make radar-review-timing-queue PYTHON=.venv/bin/python"
    )
    assert result["outcome_recovery"]["symbols"] == ("DEXE",)
    assert result["execution_quality"]["venue"] == "bybit"
    assert result["episode_coverage"]["episode_count"] == 1
    assert result["episode_coverage"]["observed_route_count"] == 1
    assert result["episode_coverage"]["route_population_count"] == 8
    assert result["episode_coverage"]["observed_primary_origin_count"] == 1
    assert result["episode_coverage"]["primary_origin_population_count"] == 7
    assert len(result["episode_coverage"]["unobserved_route_names"]) == 7
    assert result["temporal_baseline"]["feature_groups"]["turnover"][
        "warm_asset_count"
    ] == 30
    assert result["temporal_baseline"]["feature_groups"]["returns_24h"][
        "warm_asset_count"
    ] == 0
    assert result["temporal_baseline"]["feature_groups"]["returns_1h"][
        "minimum_sample_count"
    ] == 7
    assert result["temporal_baseline"]["feature_groups"]["returns_24h"][
        "maximum_sample_count"
    ] == 3
    assert result["temporal_baseline"]["current_exact_generation_status_counts"] == {
        "warming": 30
    }
    regime_input = result["temporal_baseline"]["control_market_regime_input"]
    assert regime_input["status"] == "ready"
    assert regime_input["eligible_input_count"] == 30
    assert regime_input["missing_input_count"] == 0
    assert regime_input["replay_regime"] == "risk_on"
    assert regime_input["source_snapshot_verified"] is True
    assert regime_input["provider_calls"] == regime_input["writes"] == 0
    regime_history = result["temporal_baseline"][
        "control_market_regime_generation_audit"
    ]
    assert regime_history["status"] == "ready"
    assert regime_history["verified_source_generation_count"] == 1
    assert regime_history["complete_universe_generation_count"] == 1
    assert regime_history["ready_generation_count"] == 1
    assert regime_history["incomplete_generation_count"] == 0
    assert regime_history["latest_complete_generation"][
        "eligible_input_count"
    ] == 30
    assert regime_history["provider_calls"] == regime_history["writes"] == 0
    shadow = result["shadow_temporal_surprise"]
    assert shadow["schema_version"] == 2
    assert shadow["evaluated_observation_count"] == 36
    assert shadow["provider_calls"] == shadow["writes"] == 0
    volume_shadow = shadow["feature_coverage"]["volume_24h"]
    assert volume_shadow["ready_count"] > 0
    assert volume_shadow["robust_z_median"] is not None
    assert volume_shadow["descriptive_tail_rank_kind"] == "upper"
    assert volume_shadow["tail_ranks_are_p_values"] is False
    assert result["temporal_baseline"][
        "next_cycle_point_in_time_eligible_asset_count"
    ] == 0
    assert result["temporal_baseline"]["non_warm_asset_ids"] == _ASSET_IDS
    first_deficit = result["temporal_baseline"]["feature_groups"][
        "returns_24h"
    ]["deficit_assets"][0]
    assert first_deficit == {
        "canonical_asset_id": "asset-00",
        "status": "warming",
        "sample_count": 0,
        "required_sample_count": 8,
        "sample_deficit": 8,
        "coverage_seconds": 68_150,
        "required_coverage_seconds": 111_600,
        "coverage_deficit_seconds": 43_450,
    }
    assert "/private/" not in repr(result)


def test_today_detail_names_exact_current_regime_input_gaps() -> None:
    value = {
        "status": "incomplete",
        "universe_expected_count": 30,
        "eligible_input_count": 28,
        "missing_input_count": 2,
        "missing_inputs": [
            {
                "canonical_asset_id": "pump-fun",
                "symbol": "PUMP",
                "point_in_time_volume_rank": 16,
                "reasons": [
                    "temporal_return_value_missing_or_invalid",
                    "temporal_return_unit_invalid",
                    "temporal_return_evidence_invalid",
                ],
            },
            {
                "canonical_asset_id": "whitebit",
                "symbol": "WBT",
                "point_in_time_volume_rank": 28,
                "reasons": [
                    "temporal_return_value_missing_or_invalid",
                    "temporal_return_unit_invalid",
                    "temporal_return_evidence_invalid",
                ],
            },
        ],
        "replay_status": "unavailable",
        "replay_reason": "temporal_return_24h_incomplete",
        "replay_regime": None,
    }

    detail = _control_regime_input_detail({
        "control_market_regime_input": value,
    })

    assert "28/30 eligible causal 24-hour inputs" in detail
    assert "pump-fun (PUMP), rank 16" in detail
    assert "whitebit (WBT), rank 28" in detail
    assert "does not backfill history or feed routing" in detail


def test_today_detail_separates_regime_history_churn_from_other_gaps() -> None:
    detail = _control_regime_generation_audit_detail({
        "control_market_regime_generation_audit": {
            "input_generation_count": 58,
            "verified_source_generation_count": 58,
            "complete_universe_generation_count": 16,
            "ready_generation_count": 0,
            "incomplete_generation_count": 16,
            "transition_count": 15,
            "universe_change_transition_count": 4,
            "incomplete_with_recent_entry_count": 12,
            "incomplete_without_recent_entry_count": 4,
            "latest_complete_generation": {
                "eligible_input_count": 29,
                "universe_expected_count": 30,
                "missing_asset_ids": ("hedera-hashgraph",),
                "recent_entry_missing_asset_ids": ("hedera-hashgraph",),
            },
        }
    })

    assert "58/58 source envelopes verify" in detail
    assert "0/16 complete universes" in detail
    assert "membership changed 4 times" in detail
    assert "12 incomplete cycles overlap" in detail
    assert "4 do not" in detail
    assert "descriptive overlap, not causal attribution" in detail


def test_campaign_operator_actions_fail_closed_on_pointer_or_command_drift(
    tmp_path: Path,
) -> None:
    mismatched = _campaign_report()
    mismatched["pointer"]["revision"] = 8
    _write_report(tmp_path, mismatched)
    assert _load(tmp_path)["status"] == "unavailable"

    unsafe = _campaign_report()
    unsafe["human_review_queue"]["operator_queue_command"] = (
        "CONFIRM=1 make radar-review-timing-view"
    )
    _write_report(tmp_path, unsafe)
    result = _load(tmp_path)
    assert result["status"] == "unavailable"
    assert result["human_review"] == {}

    path_like = _campaign_report()
    path_like["human_review_queue"]["records"][0]["artifact_namespace"] = (
        "/private/outside/generation"
    )
    _write_report(tmp_path, path_like)
    assert _load(tmp_path)["status"] == "unavailable"

    contradictory_baseline = _campaign_report()
    contradictory_baseline["baseline_maturity"]["current_universe_maturity"][
        "baseline_feature_readiness"
    ]["returns_24h"]["warm_asset_count"] = 31
    _write_report(tmp_path, contradictory_baseline)
    assert _load(tmp_path)["status"] == "unavailable"

    impossible_progress = _campaign_report()
    impossible_progress["baseline_maturity"]["current_universe_maturity"][
        "baseline_feature_readiness"
    ]["returns_1h"]["minimum_sample_count"] = 9
    _write_report(tmp_path, impossible_progress)
    assert _load(tmp_path)["status"] == "unavailable"

    hidden_coverage_deficit = _campaign_report()
    hidden_coverage_deficit["baseline_maturity"]["current_universe_maturity"][
        "baseline_feature_readiness"
    ]["returns_24h"]["coverage_deficit_asset_count"] = 0
    _write_report(tmp_path, hidden_coverage_deficit)
    assert _load(tmp_path)["status"] == "unavailable"

    unknown_deficit_status = _campaign_report()
    unknown_deficit_status["baseline_maturity"]["current_universe_maturity"][
        "baseline_feature_readiness"
    ]["returns_24h"]["deficit_assets"][0]["status"] = "unknown"
    _write_report(tmp_path, unknown_deficit_status)
    assert _load(tmp_path)["status"] == "unavailable"

    missing_union_identity = _campaign_report()
    missing_union_identity["baseline_maturity"]["current_universe_maturity"][
        "non_warm_asset_ids"
    ] = list(_ASSET_IDS[:-1])
    _write_report(tmp_path, missing_union_identity)
    assert _load(tmp_path)["status"] == "unavailable"

    wrong_basis = _campaign_report()
    wrong_basis["baseline_maturity"]["current_universe_maturity"][
        "next_cycle_point_in_time_basis"
    ] = "future_values_assumed"
    _write_report(tmp_path, wrong_basis)
    assert _load(tmp_path)["status"] == "unavailable"

    timestamp_drift = _campaign_report()
    timestamp_drift["baseline_maturity"]["current_universe_maturity"][
        "next_cycle_point_in_time_eligible_at"
    ] = "2026-07-18T22:43:03.720770+00:00"
    _write_report(tmp_path, timestamp_drift)
    assert _load(tmp_path)["status"] == "unavailable"

    exact_status_drift = _campaign_report()
    exact_status_drift["authoritative_generations"][0]["data_quality"][
        "baseline_status_counts"
    ] = {"warm": 30}
    _write_report(tmp_path, exact_status_drift)
    assert _load(tmp_path)["status"] == "unavailable"

    regime_binding_drift = _campaign_report()
    regime_binding_drift["authoritative_generations"][0][
        "current_authority_control_market_regime_input"
    ]["source_artifact_sha256"] = "unbound"
    _write_report(tmp_path, regime_binding_drift)
    assert _load(tmp_path)["status"] == "unavailable"

    regime_policy_drift = _campaign_report()
    regime_policy_drift["authoritative_generations"][0][
        "current_authority_control_market_regime_input"
    ]["diagnostic"]["routing_eligible"] = True
    _write_report(tmp_path, regime_policy_drift)
    assert _load(tmp_path)["status"] == "unavailable"

    regime_history_drift = _campaign_report()
    regime_history_drift["control_market_regime_generation_audit"][
        "routing_eligible"
    ] = True
    _write_report(tmp_path, regime_history_drift)
    assert _load(tmp_path)["status"] == "unavailable"

    episode_coverage_drift = _campaign_report()
    episode_coverage_drift["protocol_v2_episode_coverage_frontier"][
        "episode_count"
    ] += 1
    _write_report(tmp_path, episode_coverage_drift)
    assert _load(tmp_path)["status"] == "unavailable"

    shadow_drift = deepcopy(_campaign_report())
    shadow_drift["shadow_temporal_surprise_campaign_audit"]["feature_coverage"][
        "volume_24h"
    ]["tail_ranks_are_p_values"] = True
    _write_report(tmp_path, shadow_drift)
    assert _load(tmp_path)["status"] == "unavailable"


def test_campaign_page_renders_complete_episode_coverage_taxonomy(
    tmp_path: Path,
) -> None:
    _write_report(tmp_path, _campaign_report())
    projection = _load(tmp_path)
    snapshot = replace(_snapshot(), campaign_operator_actions=projection)

    html = render_campaign_page(snapshot, query={})

    assert "Protocol-v2 episode coverage" in html
    assert "Causal 24-hour input history" in html
    assert "Shadow anomaly distributions" in html
    assert "Robust z p05 / med / p95" in html
    assert "The ranks are not p-values" in html
    assert "Canonical causal shadow replay distributions" in html
    assert "Observed history, not a policy input" in html
    assert "Verified source envelopes" in html
    assert "Frozen episodes cover 1/8 routes and 1/7 primary origins" in html
    assert "High-confidence idea" in html
    assert "Calendar / scheduled risk" in html
    assert "Primary-origin coverage" in html
    assert "Market-led" in html
    assert "Fundamental-led" in html
    assert "Minimum samples" in html
    assert "remain unsealed" in html


def test_campaign_operator_actions_rejects_oversized_report(tmp_path: Path) -> None:
    path = tmp_path / "RADAR_LIVE_OBSERVATION_CAMPAIGN_REPORT.json"
    path.write_bytes(b"{" + b" " * MAX_CAMPAIGN_REPORT_BYTES + b"}")

    result = _load(tmp_path)

    assert result["status"] == "unavailable"
    assert result["reason"] == "campaign_report_oversized"


def test_today_and_health_surface_campaign_actions_separate_from_current_truth() -> None:
    state = _campaign_report()
    root_projection = {
        "status": "ready",
        "authority": "pointer_matched_campaign_context",
        "campaign_status": state["campaign_status"],
        "campaign_metrics": state["campaign_metrics"],
        "human_review": {
            **state["human_review_queue"],
            "next_safe_command": state["human_review_queue"]["operator_queue_command"],
        },
        "outcome_recovery": {
            "due_missing_price_count": 1,
            "matured_count": 1,
            "pending_count": 3,
            "symbols": ("DEXE",),
            "next_safe_command": (
                "make radar-outcome-price-recovery-readiness "
                "PYTHON=.venv/bin/python"
            ),
        },
        "execution_quality": {
            "status": "awaiting_authorized_immutable_capture",
            "retained_observation_count": 630,
            "spread_available_count": 0,
            "next_safe_command": (
                "make radar-execution-quality-bybit-readiness "
                "PYTHON=.venv/bin/python"
            ),
        },
        "temporal_baseline": {
            "status": "warming",
            "expected_asset_count": 30,
            "observed_asset_count": 30,
            "observed_asset_ids": _ASSET_IDS,
            "missing_asset_count": 0,
            "missing_asset_ids": (),
            "non_warm_asset_ids": _ASSET_IDS,
            "fully_warm_asset_count": 0,
            "next_cycle_point_in_time_eligible_at": (
                "2026-07-18T21:43:03.720770+00:00"
            ),
            "next_cycle_point_in_time_eligible_asset_count": 0,
            "next_cycle_point_in_time_basis": (
                "same_asset_retained_history_before_future_observation"
            ),
            "current_exact_generation_status_counts": {"warming": 30},
            "feature_groups": _baseline_feature_groups(),
            "control_market_regime_generation_audit": {
                "input_generation_count": 58,
                "verified_source_generation_count": 58,
                "complete_universe_generation_count": 16,
                "ready_generation_count": 0,
                "incomplete_generation_count": 16,
                "transition_count": 15,
                "universe_change_transition_count": 4,
                "incomplete_with_recent_entry_count": 12,
                "incomplete_without_recent_entry_count": 4,
                "latest_complete_generation": {
                    "eligible_input_count": 29,
                    "universe_expected_count": 30,
                    "missing_asset_ids": ("hedera-hashgraph",),
                    "recent_entry_missing_asset_ids": (
                        "hedera-hashgraph",
                    ),
                },
            },
        },
    }
    snapshot = replace(_snapshot(), campaign_operator_actions=root_projection)

    today = render_today_page(snapshot, query={})
    health = render_health_page(snapshot)
    panel = render_operator_work_queue(snapshot)

    for page in (today, health, panel):
        assert "Open operator work" in page
        assert "3 published idea records need explicit review" in page
        assert "1 outcome price gap needs point-in-time evidence" in page
        assert "DEXE" in page
        assert "Bybit USDT-perpetual spread evidence is still absent" in page
        assert "Trusted spread coverage is 0/630" in page
        assert "Dashboard reads never count as a review" in page
        assert "CONFIRM=1" not in page
    assert today.index("Open operator work") < today.index("Decision constraints")
    assert today.count("Execution spread unavailable") == 0
    assert "Current exact-generation row readiness: Warming 30" in today
    assert "future same-asset point-in-time evaluation for 0/30" in today
    assert "not provider-call eligibility" in today
    assert "Immutable-generation audit: 58/58 source envelopes verify" in today
    assert "12 incomplete cycles overlap a recent observed entry" in today
    assert "4 do not" in today
    assert "turnover 30/30 (21/8 samples)" in today
    assert "1h returns 0/30 (7/8 samples)" in today
    assert (
        "24h returns 0/30 (0-3/8 samples; 1 below elapsed coverage)"
        in today
    )
    assert health.count('id="human-work-queue"') == 1
    assert health.count("Spread evidence is unavailable") == 0


def test_operator_work_queue_stays_hidden_without_pointer_matched_context() -> None:
    snapshot = replace(
        _snapshot(),
        campaign_operator_actions={
            "status": "unavailable",
            "reason": "campaign_report_pointer_mismatch",
        },
    )

    assert render_operator_work_queue(snapshot) == ""
    assert "Open operator work" not in render_today_page(snapshot, query={})


def test_partial_current_row_readiness_keeps_baseline_constraint_visible() -> None:
    source = _snapshot()
    observations = (
        {
            **source.current_market_observations[0],
            "market_data_quality": {"baseline_status": "warm"},
        },
        {
            **source.current_market_observations[1],
            "market_data_quality": {"baseline_status": "warming"},
        },
    )
    temporal_baseline = {
        "status": "warming",
        "expected_asset_count": 2,
        "observed_asset_count": 2,
        "observed_asset_ids": ("asset-a", "asset-b"),
        "missing_asset_count": 0,
        "missing_asset_ids": (),
        "non_warm_asset_ids": ("asset-b",),
        "fully_warm_asset_count": 1,
        "next_cycle_point_in_time_eligible_at": "2026-07-18T21:43:03+00:00",
        "next_cycle_point_in_time_eligible_asset_count": 1,
        "next_cycle_point_in_time_basis": (
            "same_asset_retained_history_before_future_observation"
        ),
        "current_exact_generation_status_counts": {"warm": 1, "warming": 1},
        "feature_groups": _partial_feature_groups(),
    }
    snapshot = replace(
        source,
        current_market_observations=observations,
        campaign_operator_actions={
            "status": "ready",
            "temporal_baseline": temporal_baseline,
        },
    )

    today = render_today_page(snapshot, query={})

    assert "Temporal baseline still warming" in today
    assert "Current exact-generation row readiness: Warm 1 · Warming 1" in today
    assert "future same-asset point-in-time evaluation for 1/2" in today
    assert "Observed non-warm assets: asset-b" in today
