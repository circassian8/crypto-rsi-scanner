"""CLI artifact-context and v1-readiness authority regressions."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


NOW = datetime(2026, 7, 12, 4, 0, tzinfo=timezone.utc)


def _context(root: Path) -> SimpleNamespace:
    return SimpleNamespace(
        base_dir=root.parent,
        profile="fixture",
        artifact_namespace="authority_contract",
        run_mode="burn_in",
        namespace_dir=root,
        run_ledger_path=root / "event_alpha_runs.jsonl",
        alert_store_path=root / "event_alpha_alerts.jsonl",
        feedback_path=root / "event_alpha_feedback.jsonl",
        missed_path=root / "event_alpha_missed.jsonl",
        provider_health_path=root / "event_provider_health.json",
        llm_budget_ledger_path=root / "event_llm_budget.json",
        watchlist_state_path=root / "event_watchlist_state.jsonl",
        impact_hypothesis_store_path=root / "event_impact_hypotheses.jsonl",
        core_opportunity_store_path=root / "event_core_opportunities.jsonl",
        incident_store_path=root / "event_incidents.jsonl",
        outcomes_path=root / "event_alpha_outcomes.jsonl",
        notification_runs_path=root / "event_alpha_notification_runs.jsonl",
        evidence_acquisition_path=root / "event_evidence_acquisition.jsonl",
        research_cards_dir=root / "research_cards",
        daily_brief_path=root / "event_alpha_daily_brief.md",
        proposed_eval_cases_dir=root / "proposed_eval_cases",
    )


def test_local_artifacts_use_only_supplied_context_and_canonical_outcome_families(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from crypto_rsi_scanner.cli.services.scanner_parts import utility_calibration_exports

    context = _context(tmp_path / "authority-contract")
    raw_alert_return = {"alert_id": "raw-alias", "return_24h": 0.45}
    candidate = {"candidate_id": "candidate-1"}
    integrated_core = {"core_opportunity_id": "core-integrated"}
    integrated_outcome = {"candidate_id": "candidate-1", "row_type": "event_integrated_radar_outcome"}
    alpha_outcome = {"candidate_id": "candidate-2", "row_type": "event_alpha_outcome"}
    sentinels = {
        "runs": SimpleNamespace(rows=[{"run_id": "run-1"}]),
        "alerts": SimpleNamespace(rows=[raw_alert_return]),
        "feedback": SimpleNamespace(records=[SimpleNamespace(label="useful")]),
        "missed": [{"missed_id": "missed-1"}],
        "provider": {"rss": {"status": "ok"}},
        "budget": [{"run_id": "run-1"}],
        "watchlist": SimpleNamespace(entries=[]),
        "hypotheses": SimpleNamespace(rows=[{"hypothesis_id": "h1"}]),
        "cores": SimpleNamespace(rows=[{"core_opportunity_id": "core-1"}]),
        "incidents": SimpleNamespace(rows=[{"incident_id": "i1"}]),
    }
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        utility_calibration_exports.event_alpha_run_ledger,
        "load_run_records",
        lambda path, **kwargs: calls.update(run=(path, kwargs)) or sentinels["runs"],
    )
    monkeypatch.setattr(
        utility_calibration_exports.event_alpha_alert_store,
        "load_alert_snapshots",
        lambda path, **kwargs: calls.update(alert=(path, kwargs)) or sentinels["alerts"],
    )
    monkeypatch.setattr(
        utility_calibration_exports.event_feedback,
        "load_feedback",
        lambda path: calls.update(feedback=path) or sentinels["feedback"],
    )
    monkeypatch.setattr(
        utility_calibration_exports.event_alpha_missed,
        "load_missed_rows",
        lambda path: calls.update(missed=path) or sentinels["missed"],
    )
    monkeypatch.setattr(
        utility_calibration_exports.event_provider_health,
        "load_provider_health",
        lambda path: calls.update(provider=path) or sentinels["provider"],
    )
    monkeypatch.setattr(
        utility_calibration_exports.event_alpha_burn_in,
        "load_llm_budget_rows",
        lambda path: calls.update(budget=path) or sentinels["budget"],
    )
    monkeypatch.setattr(
        utility_calibration_exports.event_watchlist,
        "load_watchlist",
        lambda path: calls.update(watchlist=path) or sentinels["watchlist"],
    )
    monkeypatch.setattr(
        utility_calibration_exports.event_impact_hypothesis_store,
        "load_impact_hypotheses",
        lambda path, **kwargs: calls.update(hypotheses=(path, kwargs))
        or sentinels["hypotheses"],
    )
    monkeypatch.setattr(
        utility_calibration_exports.event_core_opportunity_store,
        "load_core_opportunities",
        lambda path, **kwargs: calls.update(cores=(path, kwargs)) or sentinels["cores"],
    )
    monkeypatch.setattr(
        utility_calibration_exports.event_incident_store,
        "load_incidents",
        lambda path, **kwargs: calls.update(incidents=(path, kwargs))
        or sentinels["incidents"],
    )
    monkeypatch.setattr(
        utility_calibration_exports.event_integrated_radar_outcomes,
        "load_integrated_radar_outcome_authority",
        lambda path: calls.update(authority=path) or ([candidate], [integrated_core]),
    )
    monkeypatch.setattr(
        utility_calibration_exports.event_integrated_radar_outcomes,
        "load_integrated_radar_outcomes",
        lambda path: calls.update(integrated_outcomes=path) or [integrated_outcome],
    )
    monkeypatch.setattr(
        utility_calibration_exports.event_alpha_outcome_artifact_io,
        "read_jsonl",
        lambda path: calls.update(alpha_outcomes=path) or [alpha_outcome],
    )

    result = utility_calibration_exports._event_alpha_local_artifacts(
        context=context,
        run_limit=17,
        latest_alerts=True,
    )

    assert calls["run"] == (context.run_ledger_path, {"limit": 17})
    assert calls["alert"] == (
        context.alert_store_path,
        {
            "latest_only": True,
            "core_opportunity_store_path": context.core_opportunity_store_path,
        },
    )
    assert calls["feedback"] == context.feedback_path
    assert calls["missed"] == context.missed_path
    assert calls["provider"] == context.provider_health_path
    assert calls["budget"] == context.llm_budget_ledger_path
    assert calls["watchlist"] == context.watchlist_state_path
    assert calls["hypotheses"][0] == context.impact_hypothesis_store_path
    assert calls["cores"][0] == context.core_opportunity_store_path
    assert calls["incidents"][0] == context.incident_store_path
    assert calls["authority"] == context.namespace_dir
    assert calls["integrated_outcomes"] == context.namespace_dir
    assert calls["alpha_outcomes"] == context.outcomes_path
    assert result["candidate_rows"] == [candidate]
    assert result["integrated_core_rows"] == [integrated_core]
    assert result["outcome_rows"] == [alpha_outcome, integrated_outcome]
    assert raw_alert_return not in result["outcome_rows"]
    assert result["diagnostic_alert_outcome_rows"] == [raw_alert_return]


def test_v1_readiness_passes_exact_authority_and_one_research_clock(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from crypto_rsi_scanner.cli.services.scanner_parts import reports
    from crypto_rsi_scanner.event_alpha.operations import scorecard as contract_scorecard

    context = _context(tmp_path / "v1-readiness")
    candidate_rows = [{"candidate_id": "candidate-authority"}]
    core_rows = [{"core_opportunity_id": "core-authority"}]
    outcome_rows = [{"outcome_identity_key": "outcome-authority"}]
    artifacts = {
        "runs": SimpleNamespace(rows=[{"run_id": "run-authority"}]),
        "alerts": SimpleNamespace(rows=[]),
        "feedback_rows": [{"feedback_id": "feedback-authority"}],
        "missed_rows": [],
        "provider_rows": {},
        "budget_rows": [],
        "outcome_rows": outcome_rows,
        "candidate_rows": candidate_rows,
        "core_opportunities": SimpleNamespace(rows=core_rows),
    }
    captured: dict[str, object] = {}
    clock_calls = 0

    def _clock() -> datetime:
        nonlocal clock_calls
        clock_calls += 1
        return NOW

    monkeypatch.setattr(reports, "_setup_event_discovery_logging", lambda _verbose: None)
    monkeypatch.setattr(
        reports,
        "resolve_event_alpha_artifact_context_for_report",
        lambda *_args, **_kwargs: context,
    )
    monkeypatch.setattr(
        reports,
        "_event_alpha_local_artifacts",
        lambda **kwargs: captured.update(loader_kwargs=kwargs) or artifacts,
    )
    monkeypatch.setattr(
        reports,
        "_ensure_operator_state_from_latest_run",
        lambda selected_context, rows: captured.update(operator=(selected_context, rows)),
    )
    monkeypatch.setattr(reports, "_event_research_now", _clock)
    monkeypatch.setattr(
        contract_scorecard,
        "build_authoritative_scorecard",
        lambda **kwargs: captured.update(contract_scorecard=kwargs)
        or {"enough_data": False},
    )

    def _readiness(**kwargs):
        captured["readiness"] = kwargs
        return SimpleNamespace()

    monkeypatch.setattr(reports.event_alpha_v1_readiness, "build_v1_readiness", _readiness)
    monkeypatch.setattr(
        reports.event_alpha_v1_readiness,
        "format_v1_readiness_report",
        lambda _result: "readiness",
    )
    monkeypatch.setattr(reports, "_event_alpha_context_block", lambda _context: "context")

    reports.event_alpha_v1_readiness_report(
        days=30,
        profile_name=context.profile,
        artifact_namespace=context.artifact_namespace,
        include_test_artifacts=True,
    )

    assert captured["loader_kwargs"] == {
        "context": context,
        "run_limit": 500,
        "latest_alerts": False,
    }
    readiness = captured["readiness"]
    assert isinstance(readiness, dict)
    assert readiness["candidate_rows"] is candidate_rows
    assert readiness["core_rows"] is core_rows
    assert readiness["outcome_rows"] is outcome_rows
    assert readiness["now"] is NOW
    contract_kwargs = captured["contract_scorecard"]
    assert isinstance(contract_kwargs, dict)
    assert contract_kwargs["now"] is NOW
    assert clock_calls == 1
    assert capsys.readouterr().out.strip().endswith("readiness")


def test_burn_in_readiness_passes_one_fixed_clock_to_authoritative_scorecard(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from crypto_rsi_scanner.cli.services import event_alpha_outcomes
    from crypto_rsi_scanner.event_alpha.operations import scorecard as contract_scorecard

    event_alpha_outcomes._refresh_scanner_globals()
    context = _context(tmp_path / "burn-in-readiness")
    captured: dict[str, object] = {}
    clock_calls = 0

    def _clock() -> datetime:
        nonlocal clock_calls
        clock_calls += 1
        return NOW

    monkeypatch.setattr(event_alpha_outcomes, "_refresh_scanner_globals", lambda: None)
    monkeypatch.setattr(event_alpha_outcomes, "_setup_event_discovery_logging", lambda _verbose: None)
    monkeypatch.setattr(
        event_alpha_outcomes,
        "resolve_event_alpha_artifact_context_for_report",
        lambda *_args, **_kwargs: context,
    )
    monkeypatch.setattr(event_alpha_outcomes, "_event_research_now", _clock)
    monkeypatch.setattr(
        event_alpha_outcomes.event_provider_status,
        "build_event_discovery_provider_status",
        lambda _config: SimpleNamespace(),
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_alpha_run_ledger,
        "load_run_records",
        lambda *_args, **_kwargs: SimpleNamespace(rows=[]),
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_alpha_alert_store,
        "load_alert_snapshots",
        lambda *_args, **_kwargs: SimpleNamespace(rows=[]),
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_core_opportunity_store,
        "load_core_opportunities",
        lambda *_args, **_kwargs: SimpleNamespace(rows=[]),
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_feedback,
        "load_feedback",
        lambda *_args, **_kwargs: SimpleNamespace(records=[]),
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_alpha_notification_delivery,
        "deliveries_path_for_context",
        lambda _context: tmp_path / "deliveries.jsonl",
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_alpha_notification_delivery,
        "load_delivery_records",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_watchlist,
        "load_watchlist",
        lambda *_args, **_kwargs: SimpleNamespace(entries=[]),
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_alpha_notification_runs,
        "load_notification_runs",
        lambda *_args, **_kwargs: SimpleNamespace(rows=[]),
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_alpha_notification_inbox,
        "build_notification_inbox",
        lambda **_kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_alpha_feedback_readiness,
        "build_feedback_readiness",
        lambda **_kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_alpha_outcome_artifact_io,
        "read_jsonl",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_integrated_radar_outcomes,
        "load_integrated_radar_outcomes",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_alpha_artifact_doctor,
        "diagnose_artifacts",
        lambda **_kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_impact_hypothesis_store,
        "load_impact_hypotheses",
        lambda *_args, **_kwargs: SimpleNamespace(rows=[]),
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_evidence_acquisition,
        "load_acquisition_results",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(event_alpha_outcomes, "_research_card_markdown_paths", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        event_alpha_outcomes.event_provider_health,
        "load_provider_health",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_alpha_burn_in,
        "load_llm_budget_rows",
        lambda *_args, **_kwargs: [],
    )
    scorecard_payload = {"enough_data": False}
    monkeypatch.setattr(
        contract_scorecard,
        "build_authoritative_scorecard",
        lambda **kwargs: captured.update(scorecard=kwargs) or scorecard_payload,
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_alpha_burn_in_readiness,
        "build_burn_in_readiness",
        lambda **kwargs: captured.update(readiness=kwargs) or SimpleNamespace(),
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_provider_status,
        "format_event_discovery_provider_status",
        lambda _result: "provider",
    )
    monkeypatch.setattr(
        event_alpha_outcomes.event_alpha_burn_in_readiness,
        "format_burn_in_readiness",
        lambda _result: "readiness",
    )
    monkeypatch.setattr(event_alpha_outcomes, "_event_alpha_context_block", lambda _context: "context")

    event_alpha_outcomes.event_alpha_burn_in_readiness_report(
        profile_name=context.profile,
        artifact_namespace=context.artifact_namespace,
    )

    scorecard_kwargs = captured["scorecard"]
    readiness_kwargs = captured["readiness"]
    assert isinstance(scorecard_kwargs, dict)
    assert isinstance(readiness_kwargs, dict)
    assert scorecard_kwargs["now"] is NOW
    assert readiness_kwargs["burn_in_contract_scorecard"] is scorecard_payload
    assert clock_calls == 1
    assert capsys.readouterr().out.strip().endswith("readiness")


def test_burn_in_export_captures_fixed_clock_before_contract_sections(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from crypto_rsi_scanner.cli.services import event_alpha_outcomes

    class ContractSectionsReached(RuntimeError):
        pass

    event_alpha_outcomes._refresh_scanner_globals()
    context = _context(tmp_path / "burn-in-export")
    captured: dict[str, object] = {}
    clock_calls = 0

    def _clock() -> datetime:
        nonlocal clock_calls
        clock_calls += 1
        return NOW

    def _contract_sections(base_dir, *, now):
        captured["base_dir"] = base_dir
        captured["now"] = now
        raise ContractSectionsReached

    monkeypatch.setattr(event_alpha_outcomes, "_refresh_scanner_globals", lambda: None)
    monkeypatch.setattr(event_alpha_outcomes, "_setup_event_discovery_logging", lambda _verbose: None)
    monkeypatch.setattr(
        event_alpha_outcomes,
        "resolve_event_alpha_artifact_context_for_report",
        lambda *_args, **_kwargs: context,
    )
    monkeypatch.setattr(
        event_alpha_outcomes,
        "_event_alpha_local_artifacts",
        lambda **_kwargs: {},
    )
    monkeypatch.setattr(event_alpha_outcomes, "_event_research_now", _clock)
    monkeypatch.setattr(event_alpha_outcomes, "_burn_in_pack_contract_sections", _contract_sections)

    with pytest.raises(ContractSectionsReached):
        event_alpha_outcomes.event_alpha_export_burn_in_pack(
            str(tmp_path / "burn-in.zip"),
            profile_name=context.profile,
            artifact_namespace=context.artifact_namespace,
        )

    assert captured == {"base_dir": context.base_dir, "now": NOW}
    assert clock_calls == 1
