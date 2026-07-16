"""Read-only evidence-cycle readiness and dispatch-contract regressions."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import socket

import pytest

from crypto_rsi_scanner.event_alpha.operations.evidence_cycle_readiness import (
    CONTRACT_VERSION,
    build_evidence_cycle_readiness,
    format_evidence_cycle_readiness,
    main,
)
from crypto_rsi_scanner.event_alpha.radar.evidence.provider_contract import (
    CURRENT_AUTHORIZATION_ENV_BY_SETTING,
    PLANNER_PROVIDER_HINTS,
)


NOW = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
REPO_ROOT = Path(__file__).resolve().parents[2]
GDELT_RSS_AUTHORIZATION = {
    "RSI_EVENT_DISCOVERY_GDELT_LIVE": "1",
    "RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": "true",
}


def _offline_settings(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "EVENT_ALPHA_EVIDENCE_ACQUISITION_ENABLED": True,
        "EVENT_ALPHA_EVIDENCE_ACQUISITION_FIXTURE_ONLY": False,
        "EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_CANDIDATES": 10,
        "EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_QUERIES": 20,
        "EVENT_ALPHA_EVIDENCE_ACQUISITION_TIMEOUT_SECONDS": 8.0,
        "EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF": False,
        "EVENT_CATALYST_SEARCH_MAX_RESULTS_PER_QUERY": 5,
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE": False,
        "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_PATH": None,
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE": False,
        "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_PATH": None,
        "EVENT_DISCOVERY_COINMARKETCAL_PATH": None,
        "EVENT_DISCOVERY_CRYPTOPANIC_LIVE": False,
        "EVENT_DISCOVERY_CRYPTOPANIC_PATH": None,
        "EVENT_DISCOVERY_GDELT_LIVE": False,
        "EVENT_DISCOVERY_GDELT_PATH": None,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": False,
        "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_PATH": None,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": False,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_PATH": None,
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS": (),
        "EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS_PATH": None,
        "EVENT_DISCOVERY_TOKENOMIST_PATH": None,
    }
    values.update(overrides)
    return values


def _write_single_provider_plan(path: Path, provider_hint: str = "gdelt") -> None:
    path.write_text(
        json.dumps(
            {
                "run_id": "run:current",
                "hypothesis_id": "hyp:one",
                "score_components": {
                    "evidence_acquisition_plan": {
                        "evidence_plan_id": "plan:one",
                        "evidence_query_plan": [
                            {
                                "query": "ASSET catalyst second source",
                                "provider_hint": provider_hint,
                                "purpose": "second_source_confirmation",
                            }
                        ],
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_readiness_is_observational_and_unknown_plan_is_not_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("readiness must not open a network connection")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    before = tuple(tmp_path.iterdir())
    report = build_evidence_cycle_readiness(
        profile="notify_llm_quality",
        artifact_base_dir=tmp_path,
        artifact_namespace="readiness",
        persisted_plan_path=tmp_path / "missing-plans.jsonl",
        provider_health_path=tmp_path / "missing-health.json",
        setting_overrides=_offline_settings(),
        authorization_environ={},
        now=NOW,
    )

    assert tuple(tmp_path.iterdir()) == before == ()
    assert report.contract_version == CONTRACT_VERSION
    assert report.persisted_current_plan.status == "not_materialized_no_persisted_store"
    assert report.persisted_current_plan.logical_query_count is None
    assert report.persisted_current_plan.provider_hint_counts is None
    assert "not zero" in report.persisted_current_plan.note
    assert report.selected_provider_hints_status == "not_materialized_candidate_dependent"
    assert report.selected_provider_hints is None
    assert report.llm_profile_capability_enabled is True
    assert report.llm_current_explicit_authorization is False
    assert report.llm_provider == "openai"
    assert report.llm_availability_status == "profile_capable_not_currently_authorized"
    assert set(report.llm_stage_readiness) == {
        "relationship",
        "extractor",
        "catalyst_frame",
    }
    assert all(
        row["current_explicit_authorization"] is False
        for row in report.llm_stage_readiness.values()
    )
    assert report.llm_required_for_readiness is False
    assert report.llm_required_for_evidence_execution is False
    assert report.no_send_state == "enforced_readiness_no_send"
    assert report.send_requested_by_readiness is False
    assert report.telegram_configuration_inspected is False
    assert report.readiness_contract_artifacts_produced is False
    assert "candidate_dependent" in report.source_independence_contract_production
    assert "candidate_dependent" in report.catalyst_attribution_contract_production
    assert report.credential_values_read is False
    assert report.credential_presence_inspected is True
    assert report.provider_call_planned_by_readiness is False
    assert report.provider_call_attempted_by_readiness is False
    assert report.authorization_created_or_mutated is False
    assert report.telegram_send_attempted is False
    assert report.network_called is False
    assert report.writes_performed is False
    assert report.research_only is True


def test_catalog_and_http_fanout_are_separate_and_complete(tmp_path: Path) -> None:
    report = build_evidence_cycle_readiness(
        artifact_base_dir=tmp_path,
        artifact_namespace="readiness",
        persisted_plan_path=tmp_path / "missing.jsonl",
        provider_health_path=tmp_path / "missing-health.json",
        setting_overrides=_offline_settings(
            EVENT_DISCOVERY_GDELT_LIVE=True,
            EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE=True,
            EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS=(
                "https://example.test/feed-one",
                "https://example.test/feed-two",
            ),
        ),
        authorization_environ=GDELT_RSS_AUTHORIZATION,
        now=NOW,
    )

    assert set(report.deterministic_catalog_provider_hint_counts) == set(
        PLANNER_PROVIDER_HINTS
    )
    assert report.deterministic_catalog_provider_hint_counts["gdelt"] > 0
    assert report.logical_queries_are_http_requests is False
    by_hint = {row.provider_hint: row for row in report.provider_mapping}
    assert by_hint["gdelt"].runtime_mapping == "GdeltCatalystSearchProvider"
    assert by_hint["gdelt"].http_request_fanout_max_per_logical_query == 1
    assert by_hint["project_blog_rss"].http_request_fanout_max_per_logical_query == 2
    assert (
        report.evidence_acquisition_http_request_upper_bound
        > report.max_logical_queries
    )
    rendered = format_evidence_cycle_readiness(report)
    assert "evidence-acquisition HTTP-request upper bound" in rendered
    assert "this excludes discovery, market, enrichment, and LLM stages" in rendered
    assert report.source_configuration_summary["selected_live_http_authorized"] == (
        "gdelt",
        "project_blog_rss",
    )
    assert report.mapping_missing_hints == ()
    assert report.mapping_fixture_fallback_hints == ()
    assert report.gdelt_runtime_mapping_status == "explicit_gated_gdelt_adapter"
    assert report.gdelt_runtime_mapping_defect_fixed is True
    assert report.fresh_validation_cycle_permitted is True
    assert report.fresh_validation_cycle_status == (
        "permitted_catalog_bound_authorization_health_and_cadence_ready"
    )
    assert report.next_safe_command.startswith(
        "CONFIRM=1 make event-alpha-evidence-validation-cycle"
    )


def test_profile_capability_and_setting_overrides_do_not_create_authorization(
    tmp_path: Path,
) -> None:
    report = build_evidence_cycle_readiness(
        artifact_base_dir=tmp_path,
        artifact_namespace="readiness",
        persisted_plan_path=tmp_path / "missing.jsonl",
        provider_health_path=tmp_path / "missing-health.json",
        setting_overrides=_offline_settings(EVENT_DISCOVERY_GDELT_LIVE=True),
        authorization_environ={},
        now=NOW,
    )

    gdelt = next(row for row in report.provider_mapping if row.provider_hint == "gdelt")
    assert gdelt.profile_live_capability is True
    assert gdelt.current_explicit_authorization is False
    assert gdelt.current_provider_call_eligibility is False
    assert gdelt.acquisition_mode == "profile_capable_not_currently_authorized"
    assert gdelt.http_request_fanout_max_per_logical_query == 0
    assert report.source_configuration_summary[
        "profile_capable_not_currently_authorized"
    ] == ("gdelt",)
    assert report.fresh_validation_cycle_permitted is False
    assert "no_current_evidence_provider_eligible" in report.blockers
    assert report.next_safe_command.startswith("make event-alpha-notify-preview")
    assert "zero provider requests" in report.expected_provider_activity_for_next_command


def test_exact_latest_persisted_plans_report_hint_counts_and_budgeted_http_bound(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "event_impact_hypotheses.jsonl"
    plan = {
        "evidence_plan_id": "plan:one",
        "evidence_query_plan": [
            {
                "query": "ASSET catalyst second source",
                "provider_hint": "gdelt",
                "purpose": "second_source_confirmation",
            },
            {
                "query": "ASSET official",
                "provider_hint": "project_blog_rss",
                "purpose": "official_confirmation",
            },
        ],
        # This duplicates the official query exactly and must not be counted twice.
        "evidence_official_searches": [
            {
                "query": "ASSET official",
                "provider_hint": "project_blog_rss",
                "purpose": "official_confirmation",
            }
        ],
        "evidence_denial_searches": [
            {
                "query": "ASSET catalyst denied",
                "provider_hint": "gdelt",
                "purpose": "denial_search",
                "must_validate_asset": False,
            }
        ],
    }
    plan_path.write_text(
        json.dumps(
            {
                "run_id": "run:current",
                "hypothesis_id": "hyp:one",
                "score_components": {"evidence_acquisition_plan": plan},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    report = build_evidence_cycle_readiness(
        artifact_base_dir=tmp_path,
        artifact_namespace="readiness",
        persisted_plan_path=plan_path,
        provider_health_path=tmp_path / "missing-health.json",
        setting_overrides=_offline_settings(
            EVENT_DISCOVERY_GDELT_LIVE=True,
            EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE=True,
            EVENT_DISCOVERY_PROJECT_BLOG_RSS_URLS=(
                "https://example.test/a",
                "https://example.test/b",
            ),
        ),
        authorization_environ=GDELT_RSS_AUTHORIZATION,
        now=NOW,
    )

    persisted = report.persisted_current_plan
    assert persisted.status == "exact_latest_persisted_run"
    assert persisted.latest_run_id == "run:current"
    assert persisted.plan_count == 1
    assert persisted.logical_query_count == 3
    assert persisted.provider_hint_counts == {"gdelt": 2, "project_blog_rss": 1}
    assert persisted.budgeted_http_request_upper_bound == 4
    assert persisted.applies_to_next_cycle == "candidate_selection_and_replanning_may_change"
    assert report.selected_provider_hints_status == "exact_latest_persisted_plan"
    assert report.selected_provider_hints == ("gdelt", "project_blog_rss")
    assert report.fresh_validation_cycle_permitted is True
    assert report.fresh_validation_cycle_status == (
        "permitted_exact_plan_authorization_health_and_cadence_ready"
    )
    assert report.next_safe_command.startswith(
        "CONFIRM=1 make event-alpha-evidence-validation-cycle"
    )


def test_secret_values_are_never_rendered(tmp_path: Path) -> None:
    secret = "cryptopanic-secret-must-not-render"
    report = build_evidence_cycle_readiness(
        artifact_base_dir=tmp_path,
        artifact_namespace="readiness",
        persisted_plan_path=tmp_path / "missing.jsonl",
        provider_health_path=tmp_path / "missing-health.json",
        setting_overrides=_offline_settings(
            EVENT_DISCOVERY_CRYPTOPANIC_LIVE=True,
            EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN=secret,
        ),
        authorization_environ={"RSI_EVENT_DISCOVERY_CRYPTOPANIC_LIVE": "yes"},
        now=NOW,
    )
    rendered = json.dumps(report.to_dict(), sort_keys=True) + format_evidence_cycle_readiness(report)

    assert secret not in rendered
    cryptopanic = next(
        row for row in report.provider_mapping if row.provider_hint == "cryptopanic"
    )
    assert cryptopanic.credential_present is True
    assert cryptopanic.current_provider_call_eligibility is True


def test_llm_readiness_separates_capability_authorization_and_credential(
    tmp_path: Path,
) -> None:
    common = dict(
        artifact_base_dir=tmp_path,
        artifact_namespace="readiness",
        persisted_plan_path=tmp_path / "missing.jsonl",
        provider_health_path=tmp_path / "missing-health.json",
        now=NOW,
    )
    capable_only = build_evidence_cycle_readiness(
        **common,
        setting_overrides=_offline_settings(
            EVENT_LLM_ENABLED=True,
            EVENT_LLM_PROVIDER="openai",
            OPENAI_API_KEY="credential-present-but-not-authorized",
        ),
        authorization_environ={},
    )
    authorized_missing_credential = build_evidence_cycle_readiness(
        **common,
        setting_overrides=_offline_settings(
            EVENT_LLM_ENABLED=True,
            EVENT_LLM_PROVIDER="openai",
            OPENAI_API_KEY=False,
        ),
        authorization_environ={
            "RSI_EVENT_LLM_ENABLED": "1",
            "RSI_EVENT_LLM_EXTRACTOR_ENABLED": "1",
            "RSI_EVENT_LLM_CATALYST_FRAMES_ENABLED": "1",
        },
    )
    secret = "llm-secret-must-not-render"
    available = build_evidence_cycle_readiness(
        **common,
        setting_overrides=_offline_settings(
            EVENT_LLM_ENABLED=True,
            EVENT_LLM_PROVIDER="openai",
            OPENAI_API_KEY=secret,
        ),
        authorization_environ={
            "RSI_EVENT_LLM_ENABLED": "true",
            "RSI_EVENT_LLM_EXTRACTOR_ENABLED": "true",
            "RSI_EVENT_LLM_CATALYST_FRAMES_ENABLED": "true",
        },
    )

    assert capable_only.llm_profile_capability_enabled is True
    assert capable_only.llm_current_explicit_authorization is False
    assert capable_only.llm_credential_present is True
    assert capable_only.llm_availability_status == (
        "profile_capable_not_currently_authorized"
    )
    assert authorized_missing_credential.llm_current_explicit_authorization is True
    assert authorized_missing_credential.llm_credential_present is False
    assert authorized_missing_credential.llm_availability_status == (
        "explicitly_authorized_missing_credential"
    )
    assert available.llm_current_explicit_authorization is True
    assert available.llm_credential_present is True
    assert available.llm_availability_status == "available_authorized_bounded"
    assert all(
        row["status"] == "available_authorized_bounded"
        for row in available.llm_stage_readiness.values()
    )
    assert secret not in json.dumps(available.to_dict(), sort_keys=True)


def test_llm_readiness_reports_stage_specific_authorization_without_broadening_it(
    tmp_path: Path,
) -> None:
    report = build_evidence_cycle_readiness(
        artifact_base_dir=tmp_path,
        artifact_namespace="readiness",
        persisted_plan_path=tmp_path / "missing.jsonl",
        provider_health_path=tmp_path / "missing-health.json",
        setting_overrides=_offline_settings(
            EVENT_LLM_ENABLED=True,
            EVENT_LLM_PROVIDER="openai",
            EVENT_LLM_EXTRACTOR_ENABLED=True,
            EVENT_LLM_EXTRACTOR_PROVIDER="openai",
            EVENT_LLM_CATALYST_FRAMES_ENABLED=True,
            EVENT_LLM_CATALYST_FRAMES_PROVIDER="openai",
            OPENAI_API_KEY="present",
        ),
        authorization_environ={"RSI_EVENT_LLM_EXTRACTOR_ENABLED": "1"},
        now=NOW,
    )

    stages = report.llm_stage_readiness
    assert report.llm_availability_status == "partially_available_live_stages"
    assert stages["extractor"]["status"] == "available_authorized_bounded"
    assert stages["relationship"]["status"] == (
        "profile_capable_not_currently_authorized"
    )
    assert stages["catalyst_frame"]["status"] == (
        "profile_capable_not_currently_authorized"
    )


def test_fixture_like_local_source_path_cannot_make_guarded_cycle_ready(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "event_impact_hypotheses.jsonl"
    _write_single_provider_plan(plan_path)
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    fixture_path = fixture_dir / "gdelt.json"
    fixture_path.write_text("{}\n", encoding="utf-8")

    report = build_evidence_cycle_readiness(
        artifact_base_dir=tmp_path,
        artifact_namespace="readiness",
        persisted_plan_path=plan_path,
        provider_health_path=tmp_path / "missing-health.json",
        setting_overrides=_offline_settings(
            EVENT_DISCOVERY_GDELT_LIVE=True,
            EVENT_DISCOVERY_GDELT_PATH=fixture_path,
        ),
        authorization_environ={"RSI_EVENT_DISCOVERY_GDELT_LIVE": "1"},
        now=NOW,
    )

    gdelt = next(row for row in report.provider_mapping if row.provider_hint == "gdelt")
    assert gdelt.configured_local_source_status == "fixture_or_test_path_rejected"
    assert gdelt.evidence_query_eligible is False
    assert gdelt.current_provider_call_eligibility is False
    assert report.fresh_validation_cycle_permitted is False
    assert "selected_provider_not_ready:gdelt" in report.blockers
    assert report.next_safe_command.startswith("make event-alpha-notify-preview")


def test_persisted_provider_backoff_blocks_current_cycle_eligibility(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "event_impact_hypotheses.jsonl"
    _write_single_provider_plan(plan_path)
    health_path = tmp_path / "provider-health.json"
    health_path.write_text(
        json.dumps(
            {
                "providers": {
                    "gdelt:catalyst_search": {
                        "provider": "gdelt",
                        "provider_service": "gdelt",
                        "consecutive_failures": 3,
                        "disabled_until": "2026-07-16T13:00:00+00:00",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    report = build_evidence_cycle_readiness(
        artifact_base_dir=tmp_path,
        artifact_namespace="readiness",
        persisted_plan_path=plan_path,
        provider_health_path=health_path,
        setting_overrides=_offline_settings(EVENT_DISCOVERY_GDELT_LIVE=True),
        authorization_environ={"RSI_EVENT_DISCOVERY_GDELT_LIVE": "1"},
        now=NOW,
    )

    gdelt = next(row for row in report.provider_mapping if row.provider_hint == "gdelt")
    assert gdelt.persisted_health_status == "backoff"
    assert gdelt.current_explicit_authorization is True
    assert gdelt.current_provider_call_eligibility is False
    assert "gdelt_persisted_health_backoff" in gdelt.blockers
    assert "selected_provider_not_ready:gdelt" in report.blockers
    assert report.fresh_validation_cycle_permitted is False
    assert report.next_safe_command.startswith("make event-alpha-notify-preview")


def test_runtime_dispatch_maps_gdelt_explicitly_and_has_no_live_fixture_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from crypto_rsi_scanner import config
    from crypto_rsi_scanner.cli.services import event_alpha_research
    from crypto_rsi_scanner.event_alpha.radar.evidence.models import (
        EvidenceAcquisitionConfig,
    )

    monkeypatch.setattr(config, "EVENT_DISCOVERY_GDELT_PATH", None)
    monkeypatch.setattr(config, "EVENT_DISCOVERY_GDELT_LIVE", False)
    providers = event_alpha_research._event_evidence_acquisition_providers_from_runtime(
        EvidenceAcquisitionConfig(enabled=True, fixture_only=False)
    )

    assert providers["default"] is None
    assert providers["gdelt"] is None
    assert set(PLANNER_PROVIDER_HINTS) <= set(providers)

    monkeypatch.setattr(config, "EVENT_DISCOVERY_GDELT_LIVE", True)
    monkeypatch.setenv("RSI_EVENT_DISCOVERY_GDELT_LIVE", "1")
    providers = event_alpha_research._event_evidence_acquisition_providers_from_runtime(
        EvidenceAcquisitionConfig(enabled=True, fixture_only=False)
    )

    assert getattr(providers["gdelt"], "name", None) == "gdelt"
    assert getattr(providers["gdelt"], "name", None) != "fixture"


def test_fixture_dispatch_maps_every_planner_hint_explicitly() -> None:
    from crypto_rsi_scanner.cli.services import event_alpha_research
    from crypto_rsi_scanner.event_alpha.radar.evidence.models import (
        EvidenceAcquisitionConfig,
    )

    providers = event_alpha_research._event_evidence_acquisition_providers_from_runtime(
        EvidenceAcquisitionConfig(enabled=True, fixture_only=True)
    )

    assert set(PLANNER_PROVIDER_HINTS) <= set(providers)
    assert all(getattr(providers[hint], "name", None) == "fixture" for hint in PLANNER_PROVIDER_HINTS)


def test_cli_json_is_read_only_and_structured(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for env_name in CURRENT_AUTHORIZATION_ENV_BY_SETTING.values():
        monkeypatch.delenv(env_name, raising=False)
    assert main(
        [
            "--profile",
            "notify_llm_quality",
            "--artifact-base-dir",
            str(tmp_path),
            "--artifact-namespace",
            "readiness",
            "--persisted-plan-path",
            str(tmp_path / "missing.jsonl"),
            "--provider-health-path",
            str(tmp_path / "missing-health.json"),
            "--json",
        ]
    ) == 0
    output = capsys.readouterr()
    payload = json.loads(output.out)

    assert output.err == ""
    assert payload["provider_call_attempted_by_readiness"] is False
    assert payload["network_called"] is False
    assert payload["writes_performed"] is False
    assert payload["authorization_created_or_mutated"] is False
    assert payload["persisted_current_plan"]["logical_query_count"] is None
    assert payload["selected_provider_hints"] is None
    assert payload["llm_profile_capability_enabled"] is True
    assert payload["llm_current_explicit_authorization"] is False
    assert payload["llm_availability_status"] == "profile_capable_not_currently_authorized"
    assert all(
        row["current_explicit_authorization"] is False
        for row in payload["llm_stage_readiness"].values()
    )
    assert payload["llm_required_for_evidence_execution"] is False
    assert payload["no_send_state"] == "enforced_readiness_no_send"
    assert payload["gdelt_runtime_mapping_defect_fixed"] is True


def test_cli_guard_is_nonzero_until_exact_safe_cycle_is_permitted(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for env_name in CURRENT_AUTHORIZATION_ENV_BY_SETTING.values():
        monkeypatch.delenv(env_name, raising=False)
    common_args = [
        "--profile",
        "notify_llm_quality",
        "--artifact-base-dir",
        str(tmp_path),
        "--artifact-namespace",
        "readiness",
        "--provider-health-path",
        str(tmp_path / "missing-health.json"),
        "--require-cycle-ready",
        "--json",
    ]

    assert main(
        [*common_args, "--persisted-plan-path", str(tmp_path / "missing.jsonl")]
    ) == 2
    blocked = json.loads(capsys.readouterr().out)
    assert blocked["fresh_validation_cycle_permitted"] is False
    assert blocked["next_safe_command"].startswith("make event-alpha-notify-preview")

    plan_path = tmp_path / "event_impact_hypotheses.jsonl"
    _write_single_provider_plan(plan_path)
    monkeypatch.setenv("RSI_EVENT_DISCOVERY_GDELT_LIVE", "1")
    assert main(
        [*common_args, "--persisted-plan-path", str(plan_path)]
    ) == 0
    permitted = json.loads(capsys.readouterr().out)
    assert permitted["fresh_validation_cycle_permitted"] is True
    assert permitted["next_safe_command"].startswith(
        "CONFIRM=1 make event-alpha-evidence-validation-cycle"
    )


def test_human_contract_and_make_target_expose_read_only_operator_truth(
    tmp_path: Path,
) -> None:
    report = build_evidence_cycle_readiness(
        artifact_base_dir=tmp_path,
        artifact_namespace="readiness",
        persisted_plan_path=tmp_path / "missing.jsonl",
        provider_health_path=tmp_path / "missing-health.json",
        setting_overrides=_offline_settings(EVENT_DISCOVERY_GDELT_LIVE=True),
        authorization_environ={},
        now=NOW,
    )
    rendered = format_evidence_cycle_readiness(report)
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "selected_provider_hints_status=not_materialized_candidate_dependent" in rendered
    assert "source configuration summary:" in rendered
    assert "gdelt_runtime_mapping_status=explicit_gated_gdelt_adapter defect_fixed=true" in rendered
    assert "llm_availability=profile_capable_not_currently_authorized" in rendered
    assert "no_send_state=enforced_readiness_no_send" in rendered
    assert "source_independence_contract=" in rendered
    assert "catalyst_attribution_contract=" in rendered
    assert "event-alpha-evidence-cycle-readiness:" in makefile
    assert "operations.evidence_cycle_readiness" in makefile
