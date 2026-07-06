"""Declarative Event Alpha doctor check registry.

New artifact-doctor checks should be added here before they are wired into the
imperative compatibility doctor. The registry records the schema fields each
check depends on, which keeps doctor behavior tied to the schema contract rather
than hidden assumptions in the monolith.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..artifacts import schema_v1

CATEGORY_SCHEMA = "schema"
CATEGORY_SAFETY = "safety"
CATEGORY_NOTIFICATION = "notification"
CATEGORY_INTEGRATED_RADAR = "integrated_radar"
CATEGORY_SOURCE_COVERAGE = "source_coverage"
CATEGORY_PROVIDER_READINESS = "provider_readiness"
CATEGORY_OUTCOMES = "outcomes"
CATEGORY_NAMESPACE = "namespace"
CATEGORY_STALE_ARTIFACTS = "stale_artifacts"
CATEGORY_PATHS = "paths"
CATEGORY_SECRETS = "secrets"

CATEGORIES: tuple[str, ...] = (
    CATEGORY_SCHEMA,
    CATEGORY_SAFETY,
    CATEGORY_NOTIFICATION,
    CATEGORY_INTEGRATED_RADAR,
    CATEGORY_SOURCE_COVERAGE,
    CATEGORY_PROVIDER_READINESS,
    CATEGORY_OUTCOMES,
    CATEGORY_NAMESPACE,
    CATEGORY_STALE_ARTIFACTS,
    CATEGORY_PATHS,
    CATEGORY_SECRETS,
)
SEVERITIES: tuple[str, ...] = ("blocker", "warning", "info")

# Public artifact_doctor.py is now an orchestrator. The check-registry target
# still allows a tiny temporary ceiling for compatibility glue, but new checks
# must declare a registry entry before emitting output.
LEGACY_UNREGISTERED_BASELINE = 2


@dataclass(frozen=True)
class DoctorCheck:
    check_id: str
    category: str
    severity: str
    schema_dependencies: tuple[str, ...]
    description: str
    introduced_in_schema_version: str


def _check(
    check_id: str,
    category: str,
    severity: str,
    schema_dependencies: Iterable[str],
    description: str,
) -> DoctorCheck:
    return DoctorCheck(
        check_id=check_id,
        category=category,
        severity=severity,
        schema_dependencies=tuple(dict.fromkeys(schema_dependencies)),
        description=description,
        introduced_in_schema_version=schema_v1.EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION,
    )


CHECKS: tuple[DoctorCheck, ...] = (
    _check(
        "schema.validation_errors",
        CATEGORY_SCHEMA,
        "blocker",
        ("schema_id", "schema_version", "row_type"),
        "Schema validation errors must be visible before legacy checks run.",
    ),
    _check(
        "schema.missing_required_fields",
        CATEGORY_SCHEMA,
        "blocker",
        ("row_type", "schema_id"),
        "Rows must include schema-required fields before higher-order validation.",
    ),
    _check(
        "schema.invalid_enum_fields",
        CATEGORY_SCHEMA,
        "blocker",
        ("opportunity_type", "final_level", "delivery_status", "status"),
        "Enum-like fields must stay inside schema-declared value sets.",
    ),
    _check(
        "schema.invalid_path_fields",
        CATEGORY_SCHEMA,
        "blocker",
        ("path", "artifact_path", "card_path", "research_card_path", "notification_preview_path"),
        "Operator artifact path fields must be relative unless explicitly marked debug absolute.",
    ),
    _check(
        "schema.invalid_safety_fields",
        CATEGORY_SCHEMA,
        "blocker",
        (
            "research_only",
            "no_send_rehearsal",
            "sent",
            "normal_rsi_signal_written",
            "triggered_fade_created",
            "trades_created",
            "paper_trades_created",
            "trade_created",
            "paper_trade_created",
        ),
        "Schema safety fields must not claim sends or trading-side effects in guarded paths.",
    ),
    _check(
        "schema.deprecated_field_usage",
        CATEGORY_SCHEMA,
        "warning",
        ("schema_version",),
        "Deprecated schema fields are counted so migrations stay explicit.",
    ),
    _check(
        "safety.invalid_safety_fields",
        CATEGORY_SAFETY,
        "blocker",
        (
            "research_only",
            "no_send_rehearsal",
            "sent",
            "normal_rsi_signal_written",
            "triggered_fade_created",
            "trades_created",
            "paper_trades_created",
            "trade_created",
            "paper_trade_created",
        ),
        "Research artifact rows must not claim sends, trades, paper rows, RSI rows, or triggered fades.",
    ),
    _check(
        "safety.no_send_side_effects",
        CATEGORY_SAFETY,
        "blocker",
        ("no_send_rehearsal", "sent", "telegram_sends", "strict_alerts_created"),
        "No-send rehearsals must not create strict alerts or Telegram sends.",
    ),
    _check(
        "safety.no_trade_side_effects",
        CATEGORY_SAFETY,
        "blocker",
        ("trades_created", "paper_trades_created", "normal_rsi_signal_written", "triggered_fade_created"),
        "Event Alpha doctor guards all research paths from trading, paper trading, RSI, and triggered-fade side effects.",
    ),
    _check(
        "safety.research_only_required",
        CATEGORY_SAFETY,
        "blocker",
        ("research_only",),
        "Artifact rows in research namespaces must remain explicitly research-only.",
    ),
    _check(
        "safety.auto_apply_disabled",
        CATEGORY_SAFETY,
        "blocker",
        ("auto_apply", "eligible_for_auto_apply"),
        "Recommendation and performance artifacts must not auto-apply threshold changes.",
    ),
    _check(
        "secrets.provider_key_leakage",
        CATEGORY_SECRETS,
        "blocker",
        ("api_key", "authorization", "token", "raw_payload_redacted"),
        "Provider keys, auth headers, and raw secret payloads must be redacted.",
    ),
    _check(
        "secrets.telegram_token_leakage",
        CATEGORY_SECRETS,
        "blocker",
        ("token", "message_text", "message_html"),
        "Notification artifacts must not expose Telegram tokens or raw debug dumps.",
    ),
    _check(
        "secrets.signed_listener_secret_leakage",
        CATEGORY_SECRETS,
        "blocker",
        ("api_secret", "redacted_headers", "provider"),
        "Signed-listener readiness artifacts must not leak provider secrets.",
    ),
    _check(
        "notification.delivery_status_fields",
        CATEGORY_NOTIFICATION,
        "blocker",
        ("delivery_id", "status", "status_detail", "delivery_status"),
        "Notification delivery rows must keep explicit status and status_detail telemetry.",
    ),
    _check(
        "notification.no_send_delivery_guard",
        CATEGORY_NOTIFICATION,
        "blocker",
        ("sent", "would_send", "send_guard_enabled", "no_send_rehearsal"),
        "No-send delivery rows must remain guarded and internally consistent.",
    ),
    _check(
        "notification.preview_path_portable",
        CATEGORY_NOTIFICATION,
        "blocker",
        ("notification_preview_path", "notification_preview_relpath", "path"),
        "Notification preview paths must be portable and resolvable from artifacts.",
    ),
    _check(
        "notification.card_identity",
        CATEGORY_NOTIFICATION,
        "blocker",
        ("core_opportunity_id", "card_path", "feedback_target"),
        "Notification rows must point at canonical core opportunity cards and feedback targets.",
    ),
    _check(
        "notification.research_review_skip_telemetry",
        CATEGORY_NOTIFICATION,
        "warning",
        ("skipped_items", "skip_reason", "reason_codes"),
        "Research-review previews must explain skipped candidates without making them alertable.",
    ),
    _check(
        "notification.body_canonical_identity",
        CATEGORY_NOTIFICATION,
        "blocker",
        ("message_text", "message_html", "core_opportunity_id"),
        "Rendered notification bodies must match canonical core opportunity identity.",
    ),
    _check(
        "integrated_radar.candidate_required_lane",
        CATEGORY_INTEGRATED_RADAR,
        "blocker",
        ("candidate_id", "symbol", "opportunity_type"),
        "Integrated radar candidates must carry a symbol and declared opportunity lane.",
    ),
    _check(
        "integrated_radar.core_candidate_consistency",
        CATEGORY_INTEGRATED_RADAR,
        "blocker",
        ("candidate_id", "core_opportunity_id", "opportunity_type", "final_level"),
        "Integrated candidates, CoreOpportunity rows, and route levels must agree.",
    ),
    _check(
        "integrated_radar.market_source_confirmation",
        CATEGORY_INTEGRATED_RADAR,
        "blocker",
        ("market_state_snapshot", "source_url", "source_strength"),
        "Confirmed research lanes require source and market evidence.",
    ),
    _check(
        "integrated_radar.fade_requires_crowding_exhaustion",
        CATEGORY_INTEGRATED_RADAR,
        "blocker",
        ("crowding_class", "fade_readiness", "derivatives_state_snapshot"),
        "FADE_SHORT_REVIEW rows require completed-move crowding/exhaustion evidence.",
    ),
    _check(
        "integrated_radar.no_triggered_fade_or_rsi",
        CATEGORY_INTEGRATED_RADAR,
        "blocker",
        ("triggered_fade_created", "normal_rsi_signal_written"),
        "Integrated radar must not create Event Alpha TRIGGERED_FADE or normal RSI rows.",
    ),
    _check(
        "integrated_radar.coinalyze_evidence_display",
        CATEGORY_INTEGRATED_RADAR,
        "blocker",
        ("coinalyze_freshness_status", "crowding_class", "card_path"),
        "Attached Coinalyze crowding evidence must be visible in cards and freshness-aware.",
    ),
    _check(
        "integrated_radar.dex_low_liquidity_gate",
        CATEGORY_INTEGRATED_RADAR,
        "blocker",
        ("liquidity_tier", "market_state_class", "opportunity_type"),
        "Low-liquidity DEX moves cannot be promoted to confirmed research without liquidity sanity.",
    ),
    _check(
        "source_coverage.provider_status_known",
        CATEGORY_SOURCE_COVERAGE,
        "warning",
        ("provider", "provider_health_status", "status"),
        "Source coverage provider rows must not silently report unknown health.",
    ),
    _check(
        "source_coverage.readiness_links",
        CATEGORY_SOURCE_COVERAGE,
        "warning",
        (
            "source_coverage_path",
            "live_provider_readiness_json_path",
            "live_provider_readiness_report_path",
            "fixture_artifacts",
        ),
        "Source coverage must link relevant readiness/preflight artifacts when they exist.",
    ),
    _check(
        "source_coverage.category_priority",
        CATEGORY_SOURCE_COVERAGE,
        "warning",
        ("category", "source_pack", "provider"),
        "Source coverage categories should preserve provider/source-pack priority semantics.",
    ),
    _check(
        "source_coverage.accepted_evidence_card_visibility",
        CATEGORY_SOURCE_COVERAGE,
        "blocker",
        ("evidence", "card_path", "source_url"),
        "Accepted evidence must be visible on the corresponding research card.",
    ),
    _check(
        "provider_readiness.live_calls_blocked_in_smoke",
        CATEGORY_PROVIDER_READINESS,
        "blocker",
        ("live_call_allowed", "mode"),
        "Fixture and smoke readiness paths must not allow live provider calls.",
    ),
    _check(
        "provider_readiness.config_env_redacted",
        CATEGORY_PROVIDER_READINESS,
        "blocker",
        ("configured", "required_env_vars", "env_vars_required"),
        "Provider readiness may list required env var names but must not print secrets.",
    ),
    _check(
        "provider_readiness.request_ledger_required",
        CATEGORY_PROVIDER_READINESS,
        "blocker",
        ("live_call_allowed", "request_ledger_path"),
        "Any live-call-allowed provider path must write or reference a request ledger.",
    ),
    _check(
        "provider_readiness.fixture_parser_status",
        CATEGORY_PROVIDER_READINESS,
        "warning",
        ("fixture_parser_status", "provider"),
        "Provider preflight reports must expose fixture/parser status by provider.",
    ),
    _check(
        "provider_readiness.provider_health_observation",
        CATEGORY_PROVIDER_READINESS,
        "blocker",
        ("provider_health_status", "success", "status"),
        "Provider health cannot be marked healthy without the required successful observations.",
    ),
    _check(
        "provider_readiness.supported_params_guard",
        CATEGORY_PROVIDER_READINESS,
        "blocker",
        ("supported_params", "endpoint"),
        "Provider rehearsals must not issue unsupported request parameters.",
    ),
    _check(
        "outcomes.candidate_identity",
        CATEGORY_OUTCOMES,
        "blocker",
        ("candidate_id", "core_opportunity_id", "opportunity_type"),
        "Outcome rows must retain candidate/core identity and opportunity type.",
    ),
    _check(
        "outcomes.price_data_labeling",
        CATEGORY_OUTCOMES,
        "blocker",
        ("price_data_status", "return_by_horizon", "outcome_status"),
        "Return fields must not be populated as real outcomes when price data is missing.",
    ),
    _check(
        "outcomes.no_diagnostic_main_aggregate",
        CATEGORY_OUTCOMES,
        "blocker",
        ("opportunity_type", "maturation_state"),
        "DIAGNOSTIC rows must stay out of main performance aggregates.",
    ),
    _check(
        "outcomes.no_auto_apply",
        CATEGORY_OUTCOMES,
        "blocker",
        ("auto_apply", "eligible_for_auto_apply"),
        "Outcome/calibration suggestions remain recommendations-only and cannot auto-apply.",
    ),
    _check(
        "outcomes.min_sample_warning",
        CATEGORY_OUTCOMES,
        "warning",
        ("sample_count", "min_sample_warning"),
        "Low-sample performance suggestions must carry an explicit min_sample_warning.",
    ),
    _check(
        "outcomes.no_trade_pnl_wording",
        CATEGORY_OUTCOMES,
        "blocker",
        ("message_text", "report_path"),
        "Outcome and performance reports must avoid trade/PnL wording.",
    ),
    _check(
        "outcomes.burn_in_scorecard_contract_count",
        CATEGORY_OUTCOMES,
        "blocker",
        (),
        "Burn-in scorecards must not count support rows above real burn-in candidate evidence.",
    ),
    _check(
        "outcomes.burn_in_scorecard_real_scope",
        CATEGORY_OUTCOMES,
        "blocker",
        (),
        "Burn-in scorecards must not claim real burn-in evidence when no contract-counted candidates exist.",
    ),
    _check(
        "outcomes.source_yield_real_candidate_rows",
        CATEGORY_OUTCOMES,
        "blocker",
        (),
        "Source-yield provider candidate counts must not exceed real burn-in candidate rows.",
    ),
    _check(
        "outcomes.source_yield_preflight_candidate_yield",
        CATEGORY_OUTCOMES,
        "blocker",
        (),
        "Source-yield reports must not count readiness or preflight rows as provider candidate yield.",
    ),
    _check(
        "outcomes.review_inbox_selected_provenance",
        CATEGORY_OUTCOMES,
        "blocker",
        (),
        "Daily review inbox selected rows must carry candidate provenance and source artifact metadata.",
    ),
    _check(
        "outcomes.review_inbox_hidden_default",
        CATEGORY_OUTCOMES,
        "blocker",
        (),
        "Daily review inbox must not surface diagnostic or preflight-only rows as default selected review items.",
    ),
    _check(
        "outcomes.review_inbox_generic_context_priority",
        CATEGORY_OUTCOMES,
        "warning",
        (),
        "Generic context rows should not outrank accepted-evidence review work without an explicit reason.",
    ),
    _check(
        "namespace.stale_send_readiness",
        CATEGORY_NAMESPACE,
        "blocker",
        ("namespace", "status", "safe_for_send_readiness"),
        "Stale namespaces cannot be used as send-readiness sources.",
    ),
    _check(
        "namespace.lifecycle_marker",
        CATEGORY_NAMESPACE,
        "blocker",
        ("namespace", "status", "superseded_by", "marker_path"),
        "Namespace lifecycle markers must be explicit and readable before artifact checks run.",
    ),
    _check(
        "namespace.include_stale_artifacts_guard",
        CATEGORY_NAMESPACE,
        "warning",
        ("status", "safe_for_send_readiness"),
        "Stale artifacts require explicit inclusion and must remain unsafe for send readiness.",
    ),
    _check(
        "stale_artifacts.snapshot_lineage",
        CATEGORY_STALE_ARTIFACTS,
        "warning",
        ("run_id", "artifact_namespace", "path"),
        "Snapshot artifacts should reconcile to the selected run and namespace.",
    ),
    _check(
        "stale_artifacts.selected_run_consistency",
        CATEGORY_STALE_ARTIFACTS,
        "blocker",
        ("run_id", "daily_brief_path"),
        "Daily briefs and operator reports must reference the selected run.",
    ),
    _check(
        "stale_artifacts.legacy_delivery_scope",
        CATEGORY_STALE_ARTIFACTS,
        "warning",
        ("delivered_at", "run_id", "status"),
        "Legacy delivery rows must be scoped so stale rows cannot masquerade as current delivery state.",
    ),
    _check(
        "paths.operator_relative",
        CATEGORY_PATHS,
        "blocker",
        ("path", "artifact_path", "report_path", "card_path"),
        "Operator-facing artifact paths must be portable relative paths.",
    ),
    _check(
        "paths.debug_abs_only",
        CATEGORY_PATHS,
        "blocker",
        ("path", "artifact_path"),
        "Absolute paths are allowed only in explicit *_abs_debug fields.",
    ),
    _check(
        "paths.card_path_rendered",
        CATEGORY_PATHS,
        "blocker",
        ("card_path", "research_card_path"),
        "Card path references must resolve to rendered research-card artifacts.",
    ),
    _check(
        "paths.active_shim_contains_logic",
        CATEGORY_PATHS,
        "warning",
        (),
        "Old top-level modules marked active_shim must not accumulate implementation logic.",
    ),
    _check(
        "paths.old_shim_internal_import",
        CATEGORY_PATHS,
        "warning",
        (),
        "Internal implementation code should import new Event Alpha package paths instead of old top-level shim paths.",
    ),
    _check(
        "paths.safe_to_remove_shim_retained",
        CATEGORY_PATHS,
        "warning",
        (),
        "A shim marked safe_to_remove should either be removed in a removal phase or carry an explicit retention reason.",
    ),
    _check(
        "paths.deleted_shim_reintroduced",
        CATEGORY_PATHS,
        "warning",
        (),
        "Deleted old Event Alpha shim paths must not be reintroduced.",
    ),
    _check(
        "paths.shim_scan_runtime_artifacts",
        CATEGORY_PATHS,
        "warning",
        (),
        "Shim dependency scans should stay source-scoped by default and avoid runtime artifact directories.",
    ),
    _check(
        "paths.shim_scan_slow",
        CATEGORY_PATHS,
        "warning",
        (),
        "Shim dependency scans should use fresh cache/source scopes when scan duration crosses the warning threshold.",
    ),
    _check(
        "paths.shim_scan_incomplete_accounting",
        CATEGORY_PATHS,
        "warning",
        (),
        "Shim dependency reports must include scan accounting before they can support old-import finalization gates.",
    ),
)

CHECK_BY_ID: dict[str, DoctorCheck] = {check.check_id: check for check in CHECKS}


def registry_rows() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "check_id": check.check_id,
            "category": check.category,
            "severity": check.severity,
            "schema_dependencies": list(check.schema_dependencies),
            "description": check.description,
            "introduced_in_schema_version": check.introduced_in_schema_version,
        }
        for check in CHECKS
    )


def counts_by_category() -> dict[str, int]:
    counts = Counter(check.category for check in CHECKS)
    return {category: int(counts.get(category, 0)) for category in CATEGORIES}


def counts_by_severity() -> dict[str, int]:
    counts = Counter(check.severity for check in CHECKS)
    return {severity: int(counts.get(severity, 0)) for severity in SEVERITIES}


def format_check_message(check_id: str, detail: str) -> str:
    """Prefix a legacy-compatible detail string with a registered check id."""
    return f"{check_id}: {detail}"


def legacy_unregistered_count(source_path: str | Path | None = None) -> int:
    """Count unmigrated blocker/warning append sites in the legacy doctor body."""
    path = Path(source_path) if source_path is not None else _artifact_doctor_source_path()
    if not path.exists():
        return LEGACY_UNREGISTERED_BASELINE
    text = path.read_text(encoding="utf-8", errors="replace")
    append_sites = sum(
        len(re.findall(pattern, text))
        for pattern in (
            r"\bblockers\.append\(",
            r"\bwarnings\.append\(",
            r"\(blockers if .*? else warnings\)\.append\(",
        )
    )
    registered_output_sites = text.count("check_registry.format_check_message(")
    return max(0, append_sites - registered_output_sites)


def registry_summary() -> dict[str, object]:
    legacy_count = legacy_unregistered_count()
    return {
        "registered_checks": len(CHECKS),
        "legacy_unregistered": legacy_count,
        "legacy_unregistered_baseline": LEGACY_UNREGISTERED_BASELINE,
        "counts_by_category": counts_by_category(),
        "counts_by_severity": counts_by_severity(),
    }


def registry_report_lines() -> list[str]:
    summary = registry_summary()
    category_counts = summary["counts_by_category"]
    severity_counts = summary["counts_by_severity"]
    assert isinstance(category_counts, dict)
    assert isinstance(severity_counts, dict)
    return [
        "Doctor Check Registry:",
        (
            f"- registered_checks={summary['registered_checks']} "
            f"legacy_unregistered={summary['legacy_unregistered']} "
            f"legacy_unregistered_baseline={summary['legacy_unregistered_baseline']}"
        ),
        "- categories: " + " ".join(f"{category}={category_counts.get(category, 0)}" for category in CATEGORIES),
        "- severities: " + " ".join(f"{severity}={severity_counts.get(severity, 0)}" for severity in SEVERITIES),
    ]


def schema_dependency_errors() -> tuple[str, ...]:
    fields = schema_v1.all_schema_fields()
    errors: list[str] = []
    for check in CHECKS:
        for field_name in check.schema_dependencies:
            if field_name not in fields:
                errors.append(f"{check.check_id}:{field_name}")
    return tuple(errors)


def registry_errors() -> tuple[str, ...]:
    errors: list[str] = []
    seen: set[str] = set()
    for check in CHECKS:
        if check.check_id in seen:
            errors.append(f"duplicate_check_id:{check.check_id}")
        seen.add(check.check_id)
        if check.category not in CATEGORIES:
            errors.append(f"invalid_category:{check.check_id}:{check.category}")
        if check.severity not in SEVERITIES:
            errors.append(f"invalid_severity:{check.check_id}:{check.severity}")
        if not check.description.strip():
            errors.append(f"missing_description:{check.check_id}")
        if check.introduced_in_schema_version != schema_v1.EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION:
            errors.append(f"invalid_schema_version:{check.check_id}:{check.introduced_in_schema_version}")
    errors.extend(f"missing_schema_dependency:{item}" for item in schema_dependency_errors())
    legacy_count = legacy_unregistered_count()
    if legacy_count > LEGACY_UNREGISTERED_BASELINE:
        errors.append(
            "legacy_unregistered_count_grew:"
            f"{legacy_count}>{LEGACY_UNREGISTERED_BASELINE}"
        )
    return tuple(errors)


def _artifact_doctor_source_path() -> Path:
    return Path(__file__).resolve().parent / "artifact_doctor.py"


def main(argv: list[str] | None = None) -> int:
    _ = argv
    for line in registry_report_lines():
        print(line)
    errors = registry_errors()
    if errors:
        print("registry_errors:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("registry_errors: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
