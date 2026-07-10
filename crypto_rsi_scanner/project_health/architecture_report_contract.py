"""Static contract data for the architecture final-report generator."""

from __future__ import annotations

from . import release_report


REPORT_SCHEMA_VERSION = "architecture_final_report_v1"
REPORT_JSON = "ARCHITECTURE_FINAL_REPORT.json"
REPORT_MD = "ARCHITECTURE_FINAL_REPORT.md"
V3_RELEASE_CANDIDATE_JSON = "ARCHITECTURE_RELEASE_REPORT.json"
V3_RELEASE_CANDIDATE_MD = "ARCHITECTURE_RELEASE_REPORT.md"
V4_FINAL_JSON = release_report.V4_FINAL_JSON
V4_FINAL_MD = release_report.V4_FINAL_MD
MAJOR_TARGETS = {
    "crypto_rsi_scanner/scanner.py": {
        "target_lines_lt": 2000,
        "next_migration_module": "crypto_rsi_scanner/cli/services/scanner_api.py",
        "risk": "Burning down the transitional compatibility core can change CLI defaults, Make target behavior, provider guardrails, or research-only side-effect gates if moved without command snapshots.",
        "blocker_reason": "scanner.py should be a small compatibility facade; command bodies must live under crypto_rsi_scanner.cli.",
    },
    "tests/test_indicators.py": {
        "target_lines_lt": 2000,
        "next_migration_module": "tests/rsi, tests/cli, and tests/event_alpha for any remaining umbrella-only cases",
        "risk": "Over-aggressive removal could break the standalone compatibility runner expected by Make and AGENTS.md.",
        "blocker_reason": "No current blocker; the file is now an umbrella runner below the target.",
    },
    "crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py": {
        "target_lines_lt": 300,
        "next_migration_module": "crypto_rsi_scanner/event_alpha/doctor/checks/safety.py, namespace.py, stale_artifacts.py, and focused historical-row counter plugins",
        "risk": "Doctor extraction can silently change strict/WARN semantics, report counter names, or stale namespace handling if compatibility tests do not pin output.",
        "blocker_reason": "artifact_doctor.py should remain a small public orchestrator/export surface.",
    },
}
TRACKED_LINE_COUNT_PATHS = tuple(
    dict.fromkeys(
        (
            *MAJOR_TARGETS,
            "crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_core.py",
            "crypto_rsi_scanner/cli/services/event_alpha.py",
            "crypto_rsi_scanner/cli/services/scanner_api.py",
            "crypto_rsi_scanner/cli/parser.py",
            "crypto_rsi_scanner/cli/commands_event_alpha.py",
        )
    )
)
LARGE_EVENT_ALPHA_SPLIT_PATHS = {
    "notifications_pipeline_wrapper": "crypto_rsi_scanner/event_alpha/notifications/pipeline.py",
    "notifications_pipeline_core": "crypto_rsi_scanner/event_alpha/notifications/pipeline_core.py",
    "research_cards_wrapper": "crypto_rsi_scanner/event_alpha/artifacts/research_cards/__init__.py",
    "research_cards_api": "crypto_rsi_scanner/event_alpha/artifacts/research_cards/api.py",
    "daily_brief_wrapper": "crypto_rsi_scanner/event_alpha/artifacts/daily_brief/__init__.py",
    "daily_brief_api": "crypto_rsi_scanner/event_alpha/artifacts/daily_brief/api.py",
    "integrated_radar_wrapper": "crypto_rsi_scanner/event_alpha/radar/integrated_radar.py",
    "integrated_radar_api": "crypto_rsi_scanner/event_alpha/radar/integrated/api.py",
    "impact_hypotheses_wrapper": "crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/__init__.py",
    "impact_hypotheses_api": "crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/api.py",
    "core_opportunity_store_wrapper": "crypto_rsi_scanner/event_alpha/radar/core_opportunity_store.py",
    "core_opportunity_store_api": "crypto_rsi_scanner/event_alpha/radar/core/store_api.py",
    "evidence_acquisition_wrapper": "crypto_rsi_scanner/event_alpha/radar/evidence_acquisition.py",
    "evidence_acquisition_api": "crypto_rsi_scanner/event_alpha/radar/evidence/acquisition_api.py",
}
MIGRATED_MODULES_THIS_RUN = (
    "crypto_rsi_scanner.event_incident_graph",
    "crypto_rsi_scanner.event_identity",
    "crypto_rsi_scanner.event_graph",
    "crypto_rsi_scanner.event_resolver",
    "crypto_rsi_scanner.event_price_history",
    "crypto_rsi_scanner.event_catalyst_frame_validator",
    "crypto_rsi_scanner.event_anomaly_state",
    "crypto_rsi_scanner.event_anomaly_scanner",
    "crypto_rsi_scanner.event_market_units",
    "crypto_rsi_scanner.event_llm_budget",
    "crypto_rsi_scanner.event_llm_catalyst_frames_eval",
    "crypto_rsi_scanner.event_source_reliability",
    "crypto_rsi_scanner.event_cache",
    "crypto_rsi_scanner.event_alpha_explain",
    "crypto_rsi_scanner.event_alpha_quality_fields",
    "crypto_rsi_scanner.event_alpha_outcomes",
    "crypto_rsi_scanner.event_alpha_eval",
    "crypto_rsi_scanner.event_alpha_burn_in_checklist",
    "crypto_rsi_scanner.event_alpha_profiles",
    "crypto_rsi_scanner.event_alpha_v1_readiness",
    "crypto_rsi_scanner.event_alpha_preflight",
    "crypto_rsi_scanner.event_alpha_health_guard",
    "crypto_rsi_scanner.event_alpha_scheduler",
    "crypto_rsi_scanner.event_alpha_environment_doctor",
    "crypto_rsi_scanner.event_provider_status",
    "crypto_rsi_scanner.event_alpha_missed",
    "crypto_rsi_scanner.event_alpha_reason_text",
    "crypto_rsi_scanner.event_clock",
    "crypto_rsi_scanner.event_models",
)
