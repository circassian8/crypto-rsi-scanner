"""Pytest isolation for split Event Alpha tests."""

from __future__ import annotations

import copy

import pytest


_ARTIFACT_STORAGE_PATHS = (
    ("RSI_EVENT_ALPHA_RUN_LEDGER_PATH", "EVENT_ALPHA_RUN_LEDGER_PATH", "event_alpha_runs.jsonl", False),
    ("RSI_EVENT_ALPHA_ALERT_STORE_PATH", "EVENT_ALPHA_ALERT_STORE_PATH", "event_alpha_alerts.jsonl", False),
    (
        "RSI_EVENT_ALPHA_NOTIFICATION_RUNS_PATH",
        "EVENT_ALPHA_NOTIFICATION_RUNS_PATH",
        "event_alpha_notification_runs.jsonl",
        False,
    ),
    ("RSI_EVENT_WATCHLIST_STATE_PATH", "EVENT_WATCHLIST_STATE_PATH", "event_watchlist_state.jsonl", False),
    ("RSI_EVENT_ALPHA_FEEDBACK_PATH", "EVENT_ALPHA_FEEDBACK_PATH", "event_alpha_feedback.jsonl", False),
    ("RSI_EVENT_ALPHA_MISSED_PATH", "EVENT_ALPHA_MISSED_PATH", "event_alpha_missed.jsonl", False),
    ("RSI_EVENT_ALPHA_PRIORS_PATH", "EVENT_ALPHA_PRIORS_PATH", "event_alpha_priors.json", False),
    ("RSI_EVENT_PROVIDER_HEALTH_PATH", "EVENT_PROVIDER_HEALTH_PATH", "event_provider_health.json", False),
    ("RSI_EVENT_ALPHA_DAILY_BRIEF_PATH", "EVENT_ALPHA_DAILY_BRIEF_PATH", "event_alpha_daily_brief.md", False),
    (
        "RSI_EVENT_IMPACT_HYPOTHESIS_STORE_PATH",
        "EVENT_IMPACT_HYPOTHESIS_STORE_PATH",
        "event_impact_hypotheses.jsonl",
        False,
    ),
    (
        "RSI_EVENT_CORE_OPPORTUNITY_STORE_PATH",
        "EVENT_CORE_OPPORTUNITY_STORE_PATH",
        "event_core_opportunities.jsonl",
        False,
    ),
    ("RSI_EVENT_INCIDENT_STORE_PATH", "EVENT_INCIDENT_STORE_PATH", "event_incidents.jsonl", False),
    (
        "RSI_EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH",
        "EVENT_ALPHA_EVIDENCE_ACQUISITION_PATH",
        "event_evidence_acquisition.jsonl",
        False,
    ),
    (
        "RSI_EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR",
        "EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR",
        "proposed_eval_cases",
        False,
    ),
    ("RSI_EVENT_RESEARCH_CARDS_DIR", "EVENT_RESEARCH_CARDS_DIR", "research_cards", False),
    ("RSI_EVENT_LLM_BUDGET_LEDGER_PATH", "EVENT_LLM_BUDGET_LEDGER_PATH", "event_llm_budget.json", False),
    ("RSI_EVENT_ALPHA_OUTCOMES_PATH", "EVENT_ALPHA_OUTCOMES_PATH", "event_alpha_outcomes.jsonl", False),
    (
        "RSI_EVENT_DISCOVERY_CRYPTOPANIC_REQUEST_LEDGER_PATH",
        "EVENT_DISCOVERY_CRYPTOPANIC_REQUEST_LEDGER_PATH",
        "cryptopanic_request_ledger.jsonl",
        False,
    ),
    (
        "RSI_EVENT_SOURCE_ENRICHMENT_CACHE_DIR",
        "EVENT_SOURCE_ENRICHMENT_CACHE_DIR",
        "source_enrichment",
        False,
    ),
    ("RSI_EVENT_LLM_CACHE_PATH", "EVENT_LLM_CACHE_PATH", "event_llm_cache.json", True),
    (
        "RSI_EVENT_LLM_EXTRACTOR_CACHE_PATH",
        "EVENT_LLM_EXTRACTOR_CACHE_PATH",
        "event_llm_extractor_cache.json",
        True,
    ),
)


@pytest.fixture(autouse=True)
def restore_event_alpha_config_state(tmp_path, monkeypatch):
    from crypto_rsi_scanner import config

    original = {}
    for name in dir(config):
        if not name.isupper():
            continue
        value = getattr(config, name)
        try:
            original[name] = copy.deepcopy(value)
        except Exception:  # noqa: BLE001
            original[name] = value

    artifact_base = tmp_path / "event-alpha-artifacts"
    discovery_cache = tmp_path / "event-discovery-cache"
    monkeypatch.setenv("RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR", str(artifact_base))
    monkeypatch.setenv("RSI_EVENT_DISCOVERY_CACHE_DIR", str(discovery_cache))
    config.EVENT_ALPHA_ARTIFACT_BASE_DIR = artifact_base
    config.EVENT_DISCOVERY_CACHE_DIR = discovery_cache
    for env_name, config_name, relative_path, optional in _ARTIFACT_STORAGE_PATHS:
        monkeypatch.delenv(env_name, raising=False)
        isolated_path = discovery_cache / relative_path
        if not optional or getattr(config, config_name, None) is not None:
            setattr(config, config_name, isolated_path)
    monkeypatch.delenv("RSI_EVENT_ALPHA_NOTIFICATION_DELIVERIES_PATH", raising=False)

    yield

    for name in tuple(dir(config)):
        if name.isupper() and name not in original:
            delattr(config, name)
    for name, value in original.items():
        setattr(config, name, value)
