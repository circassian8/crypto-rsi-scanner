"""Exact alert-authority regressions for feedback learning consumers."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from crypto_rsi_scanner.event_alpha.outcomes import feedback_eligibility
from crypto_rsi_scanner.event_alpha.outcomes import outcome_eligibility


NOW = datetime(2026, 7, 12, 3, 0, tzinfo=timezone.utc)
OBSERVED_AT = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)


def _core() -> dict[str, object]:
    return {
        "schema_id": "core_opportunity_v1",
        "schema_version": "event_core_opportunity_store_v1",
        "row_type": "event_core_opportunity",
        "run_id": "run-feedback-authority",
        "profile": "fixture",
        "artifact_namespace": "feedback_authority",
        "run_mode": "fixture",
        "core_opportunity_id": "core:velvet:listing",
        "feedback_target": "core:velvet:listing",
        "feedback_target_type": "core_opportunity_id",
        "generated_at": (OBSERVED_AT + timedelta(minutes=1)).isoformat(),
        "research_only": True,
        "symbol": "VELVET",
        "coin_id": "velvet",
        "opportunity_type": "CONFIRMED_LONG_RESEARCH",
        "source_provider": "official_exchange",
        "source_provider_domain": "exchange.example",
        "source_domain": "exchange.example",
        "source_pack": "official_listing_pack",
        "source_class": "official_exchange",
        "lane": "CONFIRMED_LONG_RESEARCH",
        "playbook_type": "listing",
        "effective_playbook_type": "listing",
        "impact_path_type": "listing",
        "candidate_role": "direct_beneficiary",
        "opportunity_level": "high_priority",
        "final_opportunity_level": "high_priority",
        "final_route_after_quality_gate": "HIGH_PRIORITY_RESEARCH",
        "thesis_origin": "catalyst_led",
        "directional_bias": "long",
        "catalyst_status": "confirmed",
        "confidence_band": "high_confidence",
        "timing_state": "early",
        "tradability_status": "acceptable",
        "radar_route": "high_confidence_watch",
        "actionability_score_cohort": "80_89",
        "anomaly_type": "none",
    }


def _feedback() -> dict[str, object]:
    row: dict[str, object] = {
        "schema_version": "event_alpha_feedback_v1",
        "row_type": "event_alpha_feedback",
        "feedback_id": "feedback:useful:velvet",
        "run_id": "run-feedback-authority",
        "profile": "fixture",
        "artifact_namespace": "feedback_authority",
        "run_mode": "fixture",
        "core_opportunity_id": "core:velvet:listing",
        "target": "core:velvet:listing",
        "feedback_target": "core:velvet:listing",
        "feedback_target_type": "core_opportunity_id",
        "label": "useful",
        "marked_at": "2026-07-12T02:00:00+00:00",
        "marked_by": "human-reviewer",
        "source": "manual_cli",
        "research_only": True,
    }
    row.update(feedback_eligibility.build_feedback_eligibility_fields(row))
    return row


def _alert(*, suffix: str = "one") -> dict[str, object]:
    return {
        "schema_version": "event_alpha_alert_snapshot_v1",
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-feedback-authority",
        "profile": "fixture",
        "artifact_namespace": "feedback_authority",
        "core_opportunity_id": "core:velvet:listing",
        "feedback_target": "core:velvet:listing",
        "feedback_target_type": "core_opportunity_id",
        "alert_id": f"alert:velvet:{suffix}",
        "alert_key": f"alert:velvet:{suffix}",
        "observed_at": OBSERVED_AT.isoformat(),
        "symbol": "VELVET",
        "coin_id": "velvet",
        "asset_symbol": "VELVET",
        "asset_coin_id": "velvet",
        "event_name": "VELVET listing",
        "playbook_type": "listing",
        "source_provider": "official_exchange",
        "opportunity_level": "high_priority",
        "opportunity_score_final": 88,
        "impact_path_type": "listing",
        "impact_path_strength": "strong",
        "candidate_role": "direct_beneficiary",
        "market_confirmation_level": "strong",
        "evidence_quality_score": 90,
        "validation_stage": "impact_path_validated",
        "tier": "HIGH_PRIORITY_WATCH",
        "route": "HIGH_PRIORITY_RESEARCH",
        "final_route_after_quality_gate": "HIGH_PRIORITY_RESEARCH",
        "alertable_after_quality_gate": True,
        "research_only": True,
    }


def _candidate() -> dict[str, object]:
    return {
        "row_type": "event_integrated_radar_candidate",
        "schema_id": "integrated_radar_candidate_v1",
        "schema_version": "event_alpha_schema_v1",
        "run_id": "run-feedback-authority",
        "profile": "fixture",
        "artifact_namespace": "feedback_authority",
        "run_mode": "fixture",
        "candidate_id": "candidate:velvet:listing",
        "core_opportunity_id": "core:velvet:listing",
        "observed_at": OBSERVED_AT.isoformat(),
        "symbol": "VELVET",
        "coin_id": "velvet",
        "opportunity_type": "CONFIRMED_LONG_RESEARCH",
        "provider": "official_exchange",
        "source_pack": "official_listing_pack",
        "playbook_type": "listing",
        "research_only": True,
        "sent": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
    }


def _outcome() -> dict[str, object]:
    identity = {
        "run_id": "run-feedback-authority",
        "profile": "fixture",
        "artifact_namespace": "feedback_authority",
        "candidate_id": "candidate:velvet:listing",
        "core_opportunity_id": "core:velvet:listing",
        "observed_at": OBSERVED_AT.isoformat(),
    }
    metadata: dict[str, dict[str, object]] = {}
    returns: dict[str, float] = {}
    for horizon in outcome_eligibility.OUTCOME_HORIZONS:
        due = OBSERVED_AT + timedelta(
            seconds=outcome_eligibility.OUTCOME_HORIZON_SECONDS[horizon]
        )
        metadata[horizon] = {
            "due_at": due.isoformat(),
            "price_observed_at": (due + timedelta(minutes=1)).isoformat(),
            "price_at_horizon": 101.0,
            "price_source": "fixture_ohlcv",
            "price_observation_id": f"fixture:velvet:{horizon}",
            "maturity_status": "matured",
            "provenance_status": "observed_market_prices",
        }
        returns[horizon] = 0.01
    row: dict[str, object] = {
        "schema_id": "outcome_row_v1",
        "schema_version": "event_alpha_schema_v1",
        "row_type": "event_integrated_radar_outcome",
        **identity,
        "outcome_identity": dict(identity),
        "outcome_identity_key": outcome_eligibility.canonical_outcome_identity_key(identity),
        "outcome_eligibility_contract_version": 1,
        "outcome_data_source": "observed_market_prices",
        "outcome_evaluated_at": NOW.isoformat(),
        "observation_price_provenance_status": "observed_market_prices",
        "price_at_observation": 100.0,
        "observation_price_source": "fixture_ohlcv",
        "observation_price_id": "fixture:velvet:entry",
        "observation_price_observed_at": OBSERVED_AT.isoformat(),
        "primary_horizon": "24h",
        "primary_horizon_return": returns["24h"],
        "return_by_horizon": returns,
        "horizons": dict(returns),
        "horizon_metadata": metadata,
        "outcome_status": "matured",
        "validation_status": "validated",
        "opportunity_type": "CONFIRMED_LONG_RESEARCH",
        "symbol": "FORGED",
        "coin_id": "forged",
        "playbook_type": "forged_playbook",
        "feedback_label": "junk",
        "research_only": True,
        "no_send_rehearsal": True,
        "sent": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
    }
    reasons = outcome_eligibility.calibration_ineligibility_reasons(row)
    row["calibration_ineligible_reasons"] = list(reasons)
    row["calibration_eligible"] = not reasons
    assert reasons == ()
    return row


def _consumer_summary(alerts: list[dict[str, object]], root: Path) -> dict[str, object]:
    from crypto_rsi_scanner.event_alpha.outcomes import feedback as eval_export
    from crypto_rsi_scanner.event_alpha.outcomes import policy_simulator
    from crypto_rsi_scanner.event_alpha.outcomes.quality import exports, scoring

    feedback = _feedback()
    core = _core()
    eval_result = eval_export.export_cases_from_feedback(
        alerts,
        [feedback],
        root / "eval",
        core_rows=[core],
        now=NOW,
    )
    eval_payload = json.loads(
        (root / "eval" / "proposed_llm_golden_cases.json").read_text(encoding="utf-8")
    )
    quality_path = root / "quality.json"
    quality_result = exports.export_signal_quality_cases(
        quality_path,
        alert_rows=alerts,
        feedback_rows=[feedback],
        core_rows=[core],
        generated_at=NOW,
        now=NOW,
    )
    quality_payload = json.loads(quality_path.read_text(encoding="utf-8"))
    worksheet = scoring.build_tuning_worksheet(
        alert_rows=alerts,
        feedback_rows=[feedback],
        core_rows=[core],
        now=NOW,
    )
    simulation = policy_simulator.simulate_policy(
        alerts,
        profile="fixture",
        feedback_rows=[feedback],
        core_rows=[core],
        include_api=True,
        now=NOW,
    )
    current = next(row for row in simulation.scenarios if row["scenario"] == "current")
    return {
        "partition": feedback_eligibility.partition_joined_alert_feedback(
            [feedback], [core], alerts, now=NOW
        ),
        "eval": (
            eval_result.proposed_cases,
            eval_result.feedback_rows_eligible,
            eval_result.feedback_rows_excluded,
            eval_result.feedback_exclusion_reason_counts,
            eval_payload["cases"],
        ),
        "quality": (
            quality_result.feedback_rows_eligible,
            quality_result.feedback_rows_excluded,
            quality_result.feedback_exclusion_reason_counts,
            tuple(
                case["reason_to_add_case"]
                for case in quality_payload["cases"]
                if "feedback" in case["reason_to_add_case"]
            ),
        ),
        "worksheet": (
            worksheet.feedback_rows,
            worksheet.feedback_rows_excluded,
            worksheet.feedback_exclusion_reason_counts,
        ),
        "policy": (
            simulation.feedback_rows_eligible,
            simulation.feedback_rows_excluded,
            simulation.feedback_exclusion_reason_counts,
            current["known_useful_count"],
            current["known_junk_count"],
        ),
    }


def test_duplicate_alert_authority_is_order_invariant_and_never_amplifies_feedback(
    tmp_path: Path,
) -> None:
    alerts = [_alert(suffix="one"), _alert(suffix="two")]
    forward = _consumer_summary(alerts, tmp_path / "forward")
    reverse = _consumer_summary(list(reversed(alerts)), tmp_path / "reverse")

    assert forward == reverse
    eligible, excluded, reasons = forward["partition"]
    assert eligible == ()
    assert len(excluded) == 1
    assert reasons == {"duplicate_alert_authority": 1}
    assert forward["eval"][:4] == (
        0,
        0,
        1,
        {"duplicate_alert_authority": 1},
    )
    assert forward["quality"] == (
        0,
        1,
        {"duplicate_alert_authority": 1},
        (),
    )
    assert forward["worksheet"] == (
        0,
        1,
        {"duplicate_alert_authority": 1},
    )
    assert forward["policy"] == (
        0,
        1,
        {"duplicate_alert_authority": 1},
        0,
        0,
    )


def test_one_exact_alert_authority_drives_each_feedback_consumer_once(
    tmp_path: Path,
) -> None:
    summary = _consumer_summary([_alert()], tmp_path / "unique")

    eligible, excluded, reasons = summary["partition"]
    assert len(eligible) == 1
    assert excluded == ()
    assert reasons == {}
    assert summary["eval"][:4] == (1, 1, 0, {})
    assert summary["quality"] == (1, 0, {}, ("useful_feedback_positive_case",))
    assert summary["worksheet"] == (1, 0, {})
    assert summary["policy"] == (1, 0, {}, 1, 0)


def test_alert_report_counts_only_exact_feedback_and_outcome_projections() -> None:
    from crypto_rsi_scanner.event_alpha.artifacts import alert_store

    alert = {
        **_alert(),
        "feedback_label": "junk",
        "feedback_status": "reviewed",
        "primary_horizon_return": 99.0,
        "return_24h": 99.0,
    }
    result = alert_store.EventAlphaAlertStoreReadResult(
        path=Path("event_alpha_alerts.jsonl"),
        rows_read=1,
        rows=[alert],
    )
    text = alert_store.format_alert_snapshot_report(
        result,
        feedback_rows=[_feedback()],
        core_rows=[_core()],
        candidate_rows=[_candidate()],
        outcome_rows=[_outcome()],
        evaluated_at=NOW,
    )

    assert "feedback authority: supplied=1 eligible=1 excluded=0" in text
    assert "outcome authority: supplied=1 eligible=1 excluded=0" in text
    assert "snapshot feedback aliases (non-authoritative diagnostics only): 1" in text
    assert "snapshot outcome aliases (non-authoritative diagnostics only): 1" in text
    assert "by feedback label: useful=1" in text
    assert "by feedback label: junk=1" not in text
    assert "Outcome metrics by playbook: listing: n=1" in text
    assert "med_primary=+1.0%" in text
    assert "forged_playbook" not in text
    assert "9900.0%" not in text


def test_alert_report_renders_legacy_aliases_as_diagnostics_only() -> None:
    from crypto_rsi_scanner.event_alpha.artifacts import alert_store

    alert = {
        **_alert(),
        "feedback_label": "useful",
        "feedback_status": "reviewed",
        "return_24h": 0.5,
    }
    result = alert_store.EventAlphaAlertStoreReadResult(
        path=Path("legacy_alerts.jsonl"),
        rows_read=1,
        rows=[alert],
    )
    text = alert_store.format_alert_snapshot_report(
        result,
        feedback_rows=[{"target": "VELVET", "label": "useful"}],
        evaluated_at=NOW,
    )

    assert "feedback authority: supplied=1 eligible=0 excluded=1" in text
    assert "legacy_feedback_contract=1" in text
    assert "outcome authority: supplied=0 eligible=0 excluded=0" in text
    assert "by feedback label: unknown=1" in text
    assert "Outcome metrics by playbook:" not in text
    assert "outcomes:" not in text


def test_cli_authority_loader_reads_candidate_core_and_both_outcome_families(
    tmp_path: Path,
) -> None:
    from crypto_rsi_scanner.cli.services.scanner_parts import utility_commands

    namespace = tmp_path / "authority"
    namespace.mkdir()
    candidate = {"row_type": "event_integrated_radar_candidate", "candidate_id": "c1"}
    core = {"row_type": "event_core_opportunity", "core_opportunity_id": "o1"}
    integrated_outcome = {"row_type": "event_integrated_radar_outcome", "candidate_id": "c1"}
    alpha_outcome = {"row_type": "event_alpha_outcome", "candidate_id": "c2"}
    (namespace / "event_integrated_radar_candidates.jsonl").write_text(
        json.dumps(candidate) + "\n",
        encoding="utf-8",
    )
    core_path = namespace / "event_core_opportunities.jsonl"
    core_path.write_text(json.dumps(core) + "\n", encoding="utf-8")
    (namespace / "event_integrated_radar_outcomes.jsonl").write_text(
        json.dumps(integrated_outcome) + "\n",
        encoding="utf-8",
    )
    alpha_path = namespace / "event_alpha_outcomes.jsonl"
    alpha_path.write_text(json.dumps(alpha_outcome) + "\n", encoding="utf-8")
    context = SimpleNamespace(
        namespace_dir=namespace,
        core_opportunity_store_path=core_path,
        outcomes_path=alpha_path,
    )

    candidates, cores, outcomes = utility_commands._event_alpha_exact_outcome_authority(
        context
    )

    assert candidates == [candidate]
    assert cores == [core]
    assert outcomes == [integrated_outcome, alpha_outcome]


def test_burn_in_scorecard_command_passes_exact_authority_and_one_clock(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from crypto_rsi_scanner.cli.services import scanner_api
    from crypto_rsi_scanner.cli.services.scanner_parts import utility_commands

    context = SimpleNamespace(
        profile="fixture",
        artifact_namespace="feedback_authority",
        run_ledger_path=tmp_path / "event_alpha_runs.jsonl",
        alert_store_path=tmp_path / "event_alpha_alerts.jsonl",
        core_opportunity_store_path=tmp_path / "event_core_opportunities.jsonl",
        feedback_path=tmp_path / "event_alpha_feedback.jsonl",
        missed_path=tmp_path / "event_alpha_missed.jsonl",
        provider_health_path=tmp_path / "event_provider_health.json",
        llm_budget_ledger_path=tmp_path / "event_llm_budget.json",
    )
    candidate_rows = [{"candidate_id": "candidate-authority"}]
    core_rows = [{"core_opportunity_id": "core-authority"}]
    outcome_rows = [{"outcome_identity_key": "outcome-authority"}]
    captured: dict[str, object] = {}

    monkeypatch.setattr(scanner_api, "_setup_event_discovery_logging", lambda _verbose: None)
    monkeypatch.setattr(
        scanner_api,
        "resolve_event_alpha_artifact_context_for_report",
        lambda *_args, **_kwargs: context,
    )
    monkeypatch.setattr(
        scanner_api.event_alpha_run_ledger,
        "load_run_records",
        lambda path, **_kwargs: captured.update(run_path=path)
        or SimpleNamespace(rows=[]),
    )
    monkeypatch.setattr(
        scanner_api.event_alpha_alert_store,
        "load_alert_snapshots",
        lambda path, **_kwargs: captured.update(alert_path=path)
        or SimpleNamespace(rows=[]),
    )
    monkeypatch.setattr(
        scanner_api.event_feedback,
        "load_feedback",
        lambda path, **_kwargs: captured.update(feedback_path=path)
        or SimpleNamespace(records=[]),
    )
    monkeypatch.setattr(
        scanner_api.event_alpha_missed,
        "load_missed_rows",
        lambda path, **_kwargs: captured.update(missed_path=path) or [],
    )
    monkeypatch.setattr(
        scanner_api.event_provider_health,
        "load_provider_health",
        lambda path, **_kwargs: captured.update(provider_path=path) or {},
    )
    monkeypatch.setattr(
        scanner_api.event_alpha_burn_in,
        "load_llm_budget_rows",
        lambda path, **_kwargs: captured.update(budget_path=path) or [],
    )
    monkeypatch.setattr(
        utility_commands,
        "_event_alpha_exact_outcome_authority",
        lambda _context: (candidate_rows, core_rows, outcome_rows),
    )
    monkeypatch.setattr(scanner_api, "_event_research_now", lambda: NOW)

    def _capture_scorecard(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(
        scanner_api.event_alpha_burn_in,
        "build_burn_in_scorecard",
        _capture_scorecard,
    )
    monkeypatch.setattr(
        scanner_api.event_alpha_burn_in,
        "format_burn_in_scorecard",
        lambda _scorecard: "scorecard",
    )
    monkeypatch.setattr(
        scanner_api,
        "_event_alpha_context_block",
        lambda _context: "context",
    )

    scanner_api.event_alpha_burn_in_scorecard(
        profile_name="fixture",
        artifact_namespace="feedback_authority",
        include_test_artifacts=True,
    )

    assert captured["candidate_rows"] is candidate_rows
    assert captured["core_rows"] is core_rows
    assert captured["outcome_rows"] is outcome_rows
    assert captured["now"] is NOW
    assert captured["run_path"] == context.run_ledger_path
    assert captured["alert_path"] == context.alert_store_path
    assert captured["feedback_path"] == context.feedback_path
    assert captured["missed_path"] == context.missed_path
    assert captured["provider_path"] == context.provider_health_path
    assert captured["budget_path"] == context.llm_budget_ledger_path


def test_research_card_report_uses_context_outcome_authority_and_one_clock(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from crypto_rsi_scanner.cli.services.scanner_parts import utility_research_cards

    namespace = tmp_path / "card-authority"
    context = SimpleNamespace(
        namespace_dir=namespace,
        watchlist_state_path=namespace / "event_watchlist_state.jsonl",
        alert_store_path=namespace / "event_alpha_alerts.jsonl",
        core_opportunity_store_path=namespace / "event_core_opportunities.jsonl",
        feedback_path=namespace / "event_alpha_feedback.jsonl",
        outcomes_path=namespace / "event_alpha_outcomes.jsonl",
    )
    raw_alert_alias = {"alert_id": "raw-alert", "return_24h": 0.99}
    core_row = {"row_type": "event_core_opportunity", "core_opportunity_id": "core-1"}
    candidate_row = {"row_type": "event_integrated_radar_candidate", "candidate_id": "candidate-1"}
    integrated_outcome = {"row_type": "event_integrated_radar_outcome", "candidate_id": "candidate-1"}
    alpha_outcome = {"row_type": "event_alpha_outcome", "candidate_id": "candidate-2"}
    captured: dict[str, object] = {}
    clock_calls = 0

    def _clock() -> datetime:
        nonlocal clock_calls
        clock_calls += 1
        return NOW

    monkeypatch.setattr(utility_research_cards, "_setup_event_discovery_logging", lambda _verbose: None)
    monkeypatch.setattr(
        utility_research_cards,
        "resolve_event_alpha_artifact_context_for_report",
        lambda *_args, **_kwargs: context,
    )
    monkeypatch.setattr(utility_research_cards, "_event_research_now", _clock)
    monkeypatch.setattr(
        utility_research_cards.event_watchlist,
        "load_watchlist",
        lambda path: captured.update(watchlist_path=path) or SimpleNamespace(entries=[]),
    )
    monkeypatch.setattr(
        utility_research_cards.event_alpha_alert_store,
        "load_alert_snapshots",
        lambda path, **_kwargs: captured.update(alert_path=path) or SimpleNamespace(rows=[raw_alert_alias]),
    )
    monkeypatch.setattr(
        utility_research_cards.event_core_opportunity_store,
        "load_core_opportunities",
        lambda path, **_kwargs: captured.update(core_path=path) or SimpleNamespace(rows=[core_row]),
    )
    monkeypatch.setattr(
        utility_research_cards.event_feedback,
        "load_feedback",
        lambda path: captured.update(feedback_path=path) or SimpleNamespace(records=[]),
    )
    monkeypatch.setattr(
        utility_research_cards.event_integrated_radar,
        "load_integrated_candidates",
        lambda path: captured.update(candidate_path=path) or [candidate_row],
    )
    monkeypatch.setattr(
        utility_research_cards.event_integrated_radar_outcomes,
        "load_integrated_radar_outcomes",
        lambda path: captured.update(integrated_outcome_path=path) or [integrated_outcome],
    )
    monkeypatch.setattr(
        utility_research_cards.event_alpha_outcome_artifact_io,
        "read_jsonl",
        lambda path: captured.update(alpha_outcome_path=path) or [alpha_outcome],
    )
    monkeypatch.setattr(
        utility_research_cards,
        "_event_alpha_router_config_from_runtime",
        lambda: object(),
    )
    monkeypatch.setattr(
        utility_research_cards.event_alpha_router,
        "route_watchlist",
        lambda *_args, **_kwargs: SimpleNamespace(decisions=[]),
    )
    monkeypatch.setattr(
        utility_research_cards,
        "_event_watchlist_monitor_result_from_runtime",
        lambda _watchlist, **kwargs: captured.update(monitor_now=kwargs.get("now"))
        or SimpleNamespace(rows=[]),
    )

    def _render(_target: str, **kwargs):
        captured["render"] = kwargs
        return SimpleNamespace(markdown="card")

    monkeypatch.setattr(
        utility_research_cards.event_research_cards,
        "render_research_card",
        _render,
    )

    utility_research_cards.event_research_card_report("core-1")

    render = captured["render"]
    assert isinstance(render, dict)
    assert captured["watchlist_path"] == context.watchlist_state_path
    assert captured["alert_path"] == context.alert_store_path
    assert captured["core_path"] == context.core_opportunity_store_path
    assert captured["feedback_path"] == context.feedback_path
    assert captured["candidate_path"] == context.namespace_dir
    assert captured["integrated_outcome_path"] == context.namespace_dir
    assert captured["alpha_outcome_path"] == context.outcomes_path
    assert render["candidate_rows"] == [candidate_row]
    assert render["outcome_rows"] == [integrated_outcome, alpha_outcome]
    assert raw_alert_alias not in render["outcome_rows"]
    assert render["generated_at"] is NOW
    assert captured["monitor_now"] is NOW
    assert clock_calls == 1
    assert capsys.readouterr().out.strip() == "card"


def test_research_cards_write_uses_context_outcome_authority_and_one_clock(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from crypto_rsi_scanner.cli.services.scanner_parts import utility_research_cards

    namespace = tmp_path / "card-write-authority"
    context = SimpleNamespace(
        profile="fixture",
        artifact_namespace="card_write_authority",
        run_mode="fixture",
        namespace_dir=namespace,
        run_ledger_path=namespace / "event_alpha_runs.jsonl",
        watchlist_state_path=namespace / "event_watchlist_state.jsonl",
        alert_store_path=namespace / "event_alpha_alerts.jsonl",
        core_opportunity_store_path=namespace / "event_core_opportunities.jsonl",
        feedback_path=namespace / "event_alpha_feedback.jsonl",
        outcomes_path=namespace / "event_alpha_outcomes.jsonl",
        research_cards_dir=namespace / "research_cards",
    )
    run_row = {
        "run_id": "run-card-write",
        "profile": context.profile,
        "artifact_namespace": context.artifact_namespace,
        "run_mode": context.run_mode,
    }
    raw_alert_alias = {"alert_id": "raw-alert", "return_72h": -0.75}
    core_row = {"row_type": "event_core_opportunity", "core_opportunity_id": "core-1"}
    candidate_row = {"row_type": "event_integrated_radar_candidate", "candidate_id": "candidate-1"}
    integrated_outcome = {"row_type": "event_integrated_radar_outcome", "candidate_id": "candidate-1"}
    alpha_outcome = {"row_type": "event_alpha_outcome", "candidate_id": "candidate-2"}
    captured: dict[str, object] = {}
    clock_calls = 0

    def _clock() -> datetime:
        nonlocal clock_calls
        clock_calls += 1
        return NOW

    monkeypatch.setattr(utility_research_cards, "_apply_event_alpha_context_to_config", lambda _context: None)
    monkeypatch.setattr(utility_research_cards, "_event_research_now", _clock)
    monkeypatch.setattr(
        utility_research_cards.event_alpha_run_ledger,
        "load_run_records",
        lambda path, **_kwargs: captured.update(run_path=path) or SimpleNamespace(rows=[run_row]),
    )
    monkeypatch.setattr(
        utility_research_cards.event_alpha_operator_state,
        "latest_matching_run",
        lambda *_args, **_kwargs: run_row,
    )
    monkeypatch.setattr(
        utility_research_cards.event_alpha_operator_state,
        "load_operator_state",
        lambda _path: SimpleNamespace(exists=False),
    )
    monkeypatch.setattr(
        utility_research_cards.event_watchlist,
        "load_watchlist",
        lambda path: captured.update(watchlist_path=path) or SimpleNamespace(entries=[]),
    )
    monkeypatch.setattr(
        utility_research_cards.event_alpha_alert_store,
        "load_alert_snapshots",
        lambda path, **_kwargs: captured.update(alert_path=path) or SimpleNamespace(rows=[raw_alert_alias]),
    )
    monkeypatch.setattr(
        utility_research_cards.event_core_opportunity_store,
        "load_core_opportunities",
        lambda path, **_kwargs: captured.update(core_path=path) or SimpleNamespace(rows=[core_row]),
    )
    monkeypatch.setattr(
        utility_research_cards.event_feedback,
        "load_feedback",
        lambda path: captured.update(feedback_path=path) or SimpleNamespace(records=[]),
    )
    monkeypatch.setattr(
        utility_research_cards.event_integrated_radar,
        "load_integrated_candidates",
        lambda path: captured.update(candidate_path=path) or [candidate_row],
    )
    monkeypatch.setattr(
        utility_research_cards.event_integrated_radar_outcomes,
        "load_integrated_radar_outcomes",
        lambda path: captured.update(integrated_outcome_path=path) or [integrated_outcome],
    )
    monkeypatch.setattr(
        utility_research_cards.event_alpha_outcome_artifact_io,
        "read_jsonl",
        lambda path: captured.update(alpha_outcome_path=path) or [alpha_outcome],
    )
    monkeypatch.setattr(
        utility_research_cards,
        "_event_alpha_router_config_from_runtime",
        lambda: object(),
    )
    monkeypatch.setattr(
        utility_research_cards.event_alpha_router,
        "route_watchlist",
        lambda *_args, **_kwargs: SimpleNamespace(decisions=[]),
    )
    monkeypatch.setattr(
        utility_research_cards,
        "_event_watchlist_monitor_result_from_runtime",
        lambda _watchlist, **kwargs: captured.update(monitor_now=kwargs.get("now"))
        or SimpleNamespace(rows=[]),
    )

    def _write(out_dir: Path, **kwargs):
        captured["write_dir"] = out_dir
        captured["write"] = kwargs
        return SimpleNamespace()

    monkeypatch.setattr(
        utility_research_cards.event_research_cards,
        "write_research_cards",
        _write,
    )
    monkeypatch.setattr(
        utility_research_cards.event_research_cards,
        "format_card_write_result",
        lambda _result: "written",
    )
    monkeypatch.setattr(
        utility_research_cards,
        "_event_alpha_context_block",
        lambda _context: "context",
    )

    utility_research_cards._event_research_cards_write_locked(context)

    write = captured["write"]
    assert isinstance(write, dict)
    assert captured["run_path"] == context.run_ledger_path
    assert captured["watchlist_path"] == context.watchlist_state_path
    assert captured["alert_path"] == context.alert_store_path
    assert captured["core_path"] == context.core_opportunity_store_path
    assert captured["feedback_path"] == context.feedback_path
    assert captured["candidate_path"] == context.namespace_dir
    assert captured["integrated_outcome_path"] == context.namespace_dir
    assert captured["alpha_outcome_path"] == context.outcomes_path
    assert captured["write_dir"] == context.research_cards_dir
    assert write["candidate_rows"] == [candidate_row]
    assert write["outcome_rows"] == [integrated_outcome, alpha_outcome]
    assert raw_alert_alias not in write["outcome_rows"]
    assert write["now"] is NOW
    assert captured["monitor_now"] is NOW
    assert clock_calls == 1
