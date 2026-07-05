"""Progressive static size gates for refactor work.

This module only reads source files and ASTs. It does not import scanner,
provider, notification, storage, or backtest runtime modules.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import refactor_class_ownership_report as ownership
from . import refactor_legacy_inventory
from . import refactor_v3_contract


BASELINE_SCHEMA_VERSION = "refactor_size_baseline_v1"
REPORT_SCHEMA_VERSION = "refactor_size_gate_report_v1"
BASELINE_JSON = "REFACTOR_SIZE_BASELINE.json"
REPORT_JSON = "REFACTOR_SIZE_GATES.json"
REPORT_MD = "REFACTOR_SIZE_GATES.md"
DEFAULT_FILE_LINE_LIMIT = 1500
PRODUCTION_WARNING_LINE_LIMIT = refactor_v3_contract.PRODUCTION_TARGET_LINE_LIMIT
PRODUCTION_BLOCKER_LINE_LIMIT = refactor_v3_contract.PRODUCTION_BLOCKER_LINE_LIMIT
PRODUCTION_LEGACY_BLOCKER_LINE_LIMIT = 2000
PRODUCTION_HARD_BLOCKER_LINE_LIMIT = 3000
TEST_WARNING_LINE_LIMIT = 1500
DEFAULT_CLASS_LINE_LIMIT = ownership.DEFAULT_CLASS_LINE_LIMIT
DEFAULT_FUNCTION_LINE_LIMIT = ownership.DEFAULT_FUNCTION_LINE_LIMIT
ACCEPTED_PRODUCTION_OVER_1200_LINE_FILES = refactor_v3_contract.ACCEPTED_PRODUCTION_OVER_1200_LINE_FILES
MOVED_VIOLATION_ALIASES = {
    "file:crypto_rsi_scanner/cli/services/scanner_legacy.py": "file:crypto_rsi_scanner/scanner.py",
    "class:crypto_rsi_scanner/event_alpha/doctor/legacy/result_models.py:EventAlphaArtifactDoctorResult": "class:crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py:EventAlphaArtifactDoctorResult",
    "class:crypto_rsi_scanner/event_alpha/notifications/legacy/delivery_writer.py:_DeliveryWriter": "class:crypto_rsi_scanner/event_alpha/notifications/pipeline_legacy.py:_DeliveryWriter",
    "class:crypto_rsi_scanner/event_alpha/radar/integrated/legacy_parts/models.py:EventIntegratedRadarResult": "class:crypto_rsi_scanner/event_alpha/radar/integrated/legacy.py:EventIntegratedRadarResult",
    "function:crypto_rsi_scanner/event_alpha/artifacts/daily_brief/legacy_parts/builder.py:build_daily_brief": "function:crypto_rsi_scanner/event_alpha/artifacts/daily_brief/legacy.py:build_daily_brief",
    "function:crypto_rsi_scanner/event_alpha/artifacts/research_cards/legacy_parts/evidence.py:_core_score_components": "function:crypto_rsi_scanner/event_alpha/artifacts/research_cards/legacy.py:_core_score_components",
    "function:crypto_rsi_scanner/event_alpha/artifacts/research_cards/legacy_parts/outcomes.py:_impact_hypothesis_lines": "function:crypto_rsi_scanner/event_alpha/artifacts/research_cards/legacy.py:_impact_hypothesis_lines",
    "function:crypto_rsi_scanner/event_alpha/artifacts/research_cards/legacy_parts/renderer.py:render_research_card": "function:crypto_rsi_scanner/event_alpha/artifacts/research_cards/legacy.py:render_research_card",
    "function:crypto_rsi_scanner/event_alpha/doctor/legacy/context_loading.py:diagnose_artifacts": "function:crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py:diagnose_artifacts",
    "function:crypto_rsi_scanner/event_alpha/doctor/legacy/notification_delivery_checks.py:_notification_delivery_conflicts": "function:crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py:_notification_delivery_conflicts",
    "function:crypto_rsi_scanner/event_alpha/doctor/legacy/provider_readiness_checks.py:_integrated_radar_artifact_conflicts": "function:crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py:_integrated_radar_artifact_conflicts",
    "function:crypto_rsi_scanner/event_alpha/doctor/legacy/reporting.py:format_artifact_doctor_report": "function:crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py:format_artifact_doctor_report",
    "function:crypto_rsi_scanner/event_alpha/notifications/legacy/preview_writer.py:write_notification_plan_preview": "function:crypto_rsi_scanner/event_alpha/notifications/pipeline_legacy.py:write_notification_plan_preview",
    "function:crypto_rsi_scanner/event_alpha/notifications/legacy/research_review_selection.py:select_research_review_candidates_with_diagnostics": "function:crypto_rsi_scanner/event_alpha/notifications/pipeline_legacy.py:select_research_review_candidates_with_diagnostics",
    "function:crypto_rsi_scanner/event_alpha/notifications/legacy/send_plan.py:send_notifications": "function:crypto_rsi_scanner/event_alpha/notifications/pipeline_legacy.py:send_notifications",
    "function:crypto_rsi_scanner/event_alpha/radar/integrated/legacy_parts/cycle.py:run_integrated_radar_cycle": "function:crypto_rsi_scanner/event_alpha/radar/integrated/legacy.py:run_integrated_radar_cycle",
    "function:crypto_rsi_scanner/event_alpha/radar/integrated/legacy_parts/merge.py:_merge_family": "function:crypto_rsi_scanner/event_alpha/radar/integrated/legacy.py:_merge_family",
    "function:crypto_rsi_scanner/event_alpha/radar/integrated/legacy_parts/report.py:format_integrated_daily_brief": "function:crypto_rsi_scanner/event_alpha/radar/integrated/legacy.py:format_integrated_daily_brief",
    "class:crypto_rsi_scanner/event_alpha/radar/evidence/models.py:EvidenceAcquisitionResult": "class:crypto_rsi_scanner/event_alpha/radar/evidence/legacy_acquisition.py:EvidenceAcquisitionResult",
    "class:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/models.py:EventImpactHypothesis": "class:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py:EventImpactHypothesis",
    "class:crypto_rsi_scanner/event_alpha/radar/watchlist/models.py:EventWatchlistEntry": "class:crypto_rsi_scanner/event_alpha/radar/watchlist/legacy.py:EventWatchlistEntry",
    "function:crypto_rsi_scanner/event_alpha/radar/core/serialization.py:_row_from_core_opportunity": "function:crypto_rsi_scanner/event_alpha/radar/core/legacy_store.py:_row_from_core_opportunity",
    "function:crypto_rsi_scanner/event_alpha/radar/discovery/manual.py:load_discovery_events": "function:crypto_rsi_scanner/event_alpha/radar/discovery/legacy.py:load_discovery_events",
    "function:crypto_rsi_scanner/event_alpha/radar/discovery/manual.py:run_manual_discovery": "function:crypto_rsi_scanner/event_alpha/radar/discovery/legacy.py:run_manual_discovery",
    "function:crypto_rsi_scanner/event_alpha/radar/evidence/executor.py:_execute_request": "function:crypto_rsi_scanner/event_alpha/radar/evidence/legacy_acquisition.py:_execute_request",
    "function:crypto_rsi_scanner/event_alpha/radar/evidence/executor.py:_validate_raw_result": "function:crypto_rsi_scanner/event_alpha/radar/evidence/legacy_acquisition.py:_validate_raw_result",
    "function:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/builder.py:_hypothesis_from_rule": "function:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py:_hypothesis_from_rule",
    "function:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/generation.py:validate_hypotheses_with_raw_events": "function:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py:validate_hypotheses_with_raw_events",
    "function:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/report.py:format_impact_hypothesis_report": "function:crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py:format_impact_hypothesis_report",
    "function:crypto_rsi_scanner/event_alpha/radar/near_miss/candidates.py:_candidate_from_row": "function:crypto_rsi_scanner/event_alpha/radar/near_miss/legacy.py:_candidate_from_row",
    "function:crypto_rsi_scanner/event_alpha/radar/near_miss/refresh.py:_refresh_one_hypothesis": "function:crypto_rsi_scanner/event_alpha/radar/near_miss/legacy.py:_refresh_one_hypothesis",
    "function:crypto_rsi_scanner/event_alpha/radar/validation/review.py:review_validation_sample": "function:crypto_rsi_scanner/event_alpha/radar/validation/legacy.py:review_validation_sample",
    "function:crypto_rsi_scanner/event_alpha/radar/watchlist/entries.py:_entry_from_alert": "function:crypto_rsi_scanner/event_alpha/radar/watchlist/legacy.py:_entry_from_alert",
    "function:crypto_rsi_scanner/event_alpha/radar/watchlist/entries.py:_entry_from_hypothesis": "function:crypto_rsi_scanner/event_alpha/radar/watchlist/legacy.py:_entry_from_hypothesis",
    "function:crypto_rsi_scanner/event_alpha/radar/watchlist/entries.py:_entry_from_row": "function:crypto_rsi_scanner/event_alpha/radar/watchlist/legacy.py:_entry_from_row",
    "class:crypto_rsi_scanner/event_alpha/radar/catalyst_search/providers.py:FixtureCatalystSearchProvider": "class:crypto_rsi_scanner/event_alpha/radar/catalyst_search.py:FixtureCatalystSearchProvider",
    "class:crypto_rsi_scanner/event_alpha/radar/catalyst_search/providers.py:EventProviderCatalystSearchProvider": "class:crypto_rsi_scanner/event_alpha/radar/catalyst_search.py:EventProviderCatalystSearchProvider",
    "class:crypto_rsi_scanner/event_alpha/radar/source_coverage/models.py:EventAlphaSourceCoverageReport": "class:crypto_rsi_scanner/event_alpha/radar/source_coverage.py:EventAlphaSourceCoverageReport",
    "function:crypto_rsi_scanner/backtest_parts/legacy_parts/cli.py:main": "function:crypto_rsi_scanner/backtest_parts/legacy.py:main",
    "function:crypto_rsi_scanner/backtest_parts/legacy_parts/walk.py:walk_coin": "function:crypto_rsi_scanner/backtest_parts/legacy.py:walk_coin",
    "function:crypto_rsi_scanner/cli/services/event_alpha_notifications/fixture_smoke.py:event_alpha_notify_fixture_smoke": "function:crypto_rsi_scanner/cli/services/event_alpha_notifications.py:event_alpha_notify_fixture_smoke",
    "function:crypto_rsi_scanner/cli/services/event_alpha_notifications/preview.py:_event_alpha_notify_cycle_body": "function:crypto_rsi_scanner/cli/services/event_alpha_notifications.py:_event_alpha_notify_cycle_body",
    "function:crypto_rsi_scanner/event_alpha/artifacts/alert_store/reconciliation.py:_snapshot_from_route_decision": "function:crypto_rsi_scanner/event_alpha/artifacts/alert_store.py:_snapshot_from_route_decision",
    "function:crypto_rsi_scanner/event_alpha/notifications/inbox/builder.py:build_notification_inbox": "function:crypto_rsi_scanner/event_alpha/notifications/inbox.py:build_notification_inbox",
    "function:crypto_rsi_scanner/event_alpha/outcomes/quality/case_eval.py:evaluate_signal_quality_case": "function:crypto_rsi_scanner/event_alpha/outcomes/quality.py:evaluate_signal_quality_case",
    "function:crypto_rsi_scanner/event_alpha/radar/source_coverage/builder.py:build_source_coverage_report": "function:crypto_rsi_scanner/event_alpha/radar/source_coverage.py:build_source_coverage_report",
    "function:crypto_rsi_scanner/event_alpha/radar/source_coverage/provider_status.py:format_source_coverage_report": "function:crypto_rsi_scanner/event_alpha/radar/source_coverage.py:format_source_coverage_report",
    "function:crypto_rsi_scanner/refactor_final_report.py:format_refactor_final_markdown": "function:crypto_rsi_scanner/refactor_final_report.py:format_refactor_final_markdown",
    "public_classes:crypto_rsi_scanner.event_alpha.artifacts.research_cards.legacy_parts.models": "public_classes:crypto_rsi_scanner.event_alpha.artifacts.research_cards.legacy",
    "public_classes:crypto_rsi_scanner.event_alpha.notifications.legacy.delivery_models": "public_classes:crypto_rsi_scanner.event_alpha.notifications.pipeline_legacy",
    "public_classes:crypto_rsi_scanner.event_alpha.artifacts.alert_store.models": "public_classes:crypto_rsi_scanner.event_alpha.artifacts.alert_store",
    "public_classes:crypto_rsi_scanner.event_alpha.notifications.inbox.models": "public_classes:crypto_rsi_scanner.event_alpha.notifications.inbox",
    "public_classes:crypto_rsi_scanner.event_alpha.outcomes.quality.models": "public_classes:crypto_rsi_scanner.event_alpha.outcomes.quality",
    "public_classes:crypto_rsi_scanner.event_alpha.radar.catalyst_search.models": "public_classes:crypto_rsi_scanner.event_alpha.radar.catalyst_search",
    "public_classes:crypto_rsi_scanner.event_alpha.radar.catalyst_search.providers": "public_classes:crypto_rsi_scanner.event_alpha.radar.catalyst_search",
    "public_classes:crypto_rsi_scanner.event_alpha.radar.incidents.models": "public_classes:crypto_rsi_scanner.event_alpha.radar.incidents",
    "public_classes:crypto_rsi_scanner.event_alpha.radar.source_coverage.models": "public_classes:crypto_rsi_scanner.event_alpha.radar.source_coverage",
    "public_classes:crypto_rsi_scanner.event_alpha.radar.core.models": "public_classes:crypto_rsi_scanner.event_alpha.radar.core.legacy_store",
    "public_classes:crypto_rsi_scanner.event_alpha.radar.evidence.models": "public_classes:crypto_rsi_scanner.event_alpha.radar.evidence.legacy_acquisition",
    "public_classes:crypto_rsi_scanner.event_alpha.radar.impact_hypotheses.models": "public_classes:crypto_rsi_scanner.event_alpha.radar.impact_hypotheses.legacy",
    "public_classes:crypto_rsi_scanner.event_alpha.radar.near_miss.models": "public_classes:crypto_rsi_scanner.event_alpha.radar.near_miss.legacy",
    "public_classes:crypto_rsi_scanner.event_alpha.radar.validation.models": "public_classes:crypto_rsi_scanner.event_alpha.radar.validation.legacy",
    "public_classes:crypto_rsi_scanner.event_alpha.radar.watchlist.models": "public_classes:crypto_rsi_scanner.event_alpha.radar.watchlist.legacy",
}


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[1]


def build_inventory(
    *,
    root: str | Path | None = None,
    file_line_limit: int = DEFAULT_FILE_LINE_LIMIT,
    class_line_limit: int = DEFAULT_CLASS_LINE_LIMIT,
    function_line_limit: int = DEFAULT_FUNCTION_LINE_LIMIT,
) -> dict[str, Any]:
    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    class_report = ownership.build_report(
        root=repo_root,
        class_line_limit=class_line_limit,
        function_line_limit=function_line_limit,
    )
    legacy_inventory = refactor_legacy_inventory.build_legacy_inventory(
        root=repo_root,
        class_line_limit=class_line_limit,
        function_line_limit=function_line_limit,
    )
    file_rows = _file_line_rows(repo_root, file_line_limit=file_line_limit)
    long_files = [row for row in file_rows if row["line_count"] > file_line_limit]
    production_file_rows = [row for row in file_rows if row.get("source_kind") == "production"]
    test_file_rows = [row for row in file_rows if row.get("source_kind") == "test"]
    production_files_over_1200 = [
        row for row in production_file_rows if row["line_count"] > refactor_v3_contract.PRODUCTION_TARGET_LINE_LIMIT
    ]
    accepted_production_files_over_1200 = [
        _accepted_over_1200_row(row)
        for row in production_files_over_1200
        if str(row.get("path") or "") in ACCEPTED_PRODUCTION_OVER_1200_LINE_FILES
    ]
    unresolved_production_files_over_1200 = [
        row
        for row in production_files_over_1200
        if str(row.get("path") or "") not in ACCEPTED_PRODUCTION_OVER_1200_LINE_FILES
    ]
    production_files_over_1500 = [
        row for row in production_file_rows if row["line_count"] > PRODUCTION_BLOCKER_LINE_LIMIT
    ]
    production_files_over_2000 = [
        row for row in production_file_rows if row["line_count"] > PRODUCTION_LEGACY_BLOCKER_LINE_LIMIT
    ]
    production_files_over_3000 = [
        row for row in production_file_rows if row["line_count"] > PRODUCTION_HARD_BLOCKER_LINE_LIMIT
    ]
    test_files_over_1500 = [
        row for row in test_file_rows if row["line_count"] > TEST_WARNING_LINE_LIMIT
    ]
    test_files_over_2000 = [
        row for row in test_file_rows if row["line_count"] > PRODUCTION_BLOCKER_LINE_LIMIT
    ]
    production_classes_over_limit = [
        row
        for row in class_report.get("classes_over_limit", [])
        if isinstance(row, dict) and str(row.get("source_path") or "").startswith("crypto_rsi_scanner/")
    ]
    production_functions_over_limit = [
        row
        for row in class_report.get("functions_over_limit", [])
        if isinstance(row, dict) and str(row.get("source_path") or "").startswith("crypto_rsi_scanner/")
    ]
    production_size_gate_status = (
        "blocked"
        if production_files_over_1500 or production_files_over_2000 or production_files_over_3000
        else ("warning" if production_files_over_1200 else "pass")
    )
    test_size_gate_status = "warning" if test_files_over_1500 else "pass"
    violations = _ownership_violation_rows(long_files, class_report)
    violation_ids = sorted({row["violation_id"] for row in violations})
    return {
        "file_line_limit": file_line_limit,
        "class_line_limit": class_line_limit,
        "function_line_limit": function_line_limit,
        "file_count": len(file_rows),
        "files_over_limit_count": len(long_files),
        "production_files_over_1200_lines": len(production_files_over_1200),
        "production_files_over_1200_line_rows": sorted(
            production_files_over_1200,
            key=lambda row: (-int(row.get("line_count") or 0), str(row.get("path") or "")),
        ),
        "accepted_production_files_over_1200_lines": len(accepted_production_files_over_1200),
        "accepted_production_files_over_1200_line_rows": sorted(
            accepted_production_files_over_1200,
            key=lambda row: (-int(row.get("line_count") or 0), str(row.get("path") or "")),
        ),
        "unresolved_production_files_over_1200_lines": len(unresolved_production_files_over_1200),
        "unresolved_production_files_over_1200_line_rows": sorted(
            unresolved_production_files_over_1200,
            key=lambda row: (-int(row.get("line_count") or 0), str(row.get("path") or "")),
        ),
        "production_files_over_1500_lines": len(production_files_over_1500),
        "production_files_over_2000_lines": len(production_files_over_2000),
        "production_files_over_3000_lines": len(production_files_over_3000),
        "largest_production_files": sorted(
            production_file_rows,
            key=lambda row: (-int(row.get("line_count") or 0), str(row.get("path") or "")),
        )[:40],
        "production_classes_over_limit": len(production_classes_over_limit),
        "production_functions_over_limit": len(production_functions_over_limit),
        "production_classes_over_limit_rows": production_classes_over_limit,
        "production_functions_over_limit_rows": production_functions_over_limit,
        "accepted_class_exceptions": class_report.get("accepted_class_exceptions", []),
        "accepted_class_exceptions_count": int(class_report.get("accepted_class_exceptions_count", 0)),
        "remaining_class_ownership_debt": class_report.get("remaining_class_ownership_debt", []),
        "remaining_class_ownership_debt_count": int(class_report.get("remaining_class_ownership_debt_count", 0)),
        "provider_class_split_status": class_report.get("provider_class_split_status", []),
        "storage_mixin_exception_status": class_report.get("storage_mixin_exception_status", []),
        "near_threshold_file_status": class_report.get("near_threshold_file_status", []),
        "modules_with_multiple_public_classes_status": class_report.get(
            "modules_with_multiple_public_classes_status"
        ),
        "production_size_gate_status": production_size_gate_status,
        "test_files_over_1500_lines": len(test_files_over_1500),
        "test_files_over_2000_lines": len(test_files_over_2000),
        "largest_test_files": sorted(
            test_file_rows,
            key=lambda row: (-int(row.get("line_count") or 0), str(row.get("path") or "")),
        )[:40],
        "test_size_gate_status": test_size_gate_status,
        "classes_over_limit_count": int(class_report.get("classes_over_limit_count", 0)),
        "functions_over_limit_count": int(class_report.get("functions_over_limit_count", 0)),
        "modules_with_multiple_public_classes_count": int(
            class_report.get("modules_with_multiple_public_classes_count", 0)
        ),
        "multi_public_class_modules_count": int(class_report.get("multi_public_class_modules_count", 0)),
        "accepted_model_bundles_count": int(class_report.get("accepted_model_bundles_count", 0)),
        "unresolved_multi_class_modules_count": int(class_report.get("unresolved_multi_class_modules_count", 0)),
        "files_over_limit": long_files,
        "classes_over_limit": class_report.get("classes_over_limit", []),
        "functions_over_limit": class_report.get("functions_over_limit", []),
        "multi_public_class_modules": class_report.get("multi_public_class_modules", []),
        "accepted_model_bundles": class_report.get("accepted_model_bundles", []),
        "unresolved_multi_class_modules": class_report.get("unresolved_multi_class_modules", []),
        "modules_with_multiple_public_classes": class_report.get("modules_with_multiple_public_classes", []),
        **legacy_inventory,
        "violations": violations,
        "violation_ids": violation_ids,
    }


def _ownership_violation_rows(long_files: Iterable[Mapping[str, Any]], class_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    violations.extend(
        {
            "violation_id": f"file:{row['path']}",
            "category": "file_over_1500_lines",
            "severity": "warning",
            **row,
        }
        for row in long_files
    )
    violations.extend(
        {
            "violation_id": f"class:{row['source_path']}:{row['qualname']}",
            "category": "class_over_75_lines",
            "severity": "warning",
            **row,
        }
        for row in class_report.get("classes_over_limit", [])
        if isinstance(row, dict)
    )
    violations.extend(
        {
            "violation_id": f"function:{row['source_path']}:{row['qualname']}",
            "category": "function_over_150_lines",
            "severity": "warning",
            **row,
        }
        for row in class_report.get("functions_over_limit", [])
        if isinstance(row, dict)
    )
    unresolved = class_report.get("unresolved_multi_class_modules", class_report.get("modules_with_multiple_public_classes", []))
    violations.extend(
        {
            "violation_id": f"public_classes:{row['module']}",
            "category": "public_classes_sharing_module",
            "severity": "warning",
            **row,
        }
        for row in unresolved
        if isinstance(row, dict)
    )
    return violations


def _accepted_over_1200_row(row: Mapping[str, Any]) -> dict[str, Any]:
    path = str(row.get("path") or "")
    meta = ACCEPTED_PRODUCTION_OVER_1200_LINE_FILES.get(path, {})
    return {
        **dict(row),
        "accepted": True,
        "reason": str(meta.get("reason") or "Accepted v3 over-1200-line warning."),
        "revisit_condition": str(meta.get("revisit_condition") or "Revisit on the next behavior-freeze split pass."),
    }


def build_baseline(*, root: str | Path | None = None) -> dict[str, Any]:
    inventory = build_inventory(root=root)
    return {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "row_type": "refactor_size_baseline",
        "generated_at": _generated_at(),
        "research_only": True,
        "no_live_provider_calls": True,
        "no_sends_trades_paper_rsi_or_triggered_fade": True,
        **inventory,
    }


def build_gate_report(*, root: str | Path | None = None) -> dict[str, Any]:
    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    inventory = build_inventory(root=repo_root)
    v3_gate_snapshot = refactor_v3_contract.build_v3_gate_snapshot(
        root=repo_root,
        size_gate_report=inventory,
        class_ownership_report=inventory,
    )
    baseline_path = repo_root / "research" / BASELINE_JSON
    baseline = _read_json(baseline_path)
    baseline_ids = set(baseline.get("violation_ids", [])) if isinstance(baseline, dict) else set()
    current_ids = set(inventory["violation_ids"])
    aliased_current_ids = {_baseline_violation_id(value) for value in current_ids}
    new_ids = sorted(value for value in current_ids if _baseline_violation_id(value) not in baseline_ids)
    resolved_ids = sorted(baseline_ids - aliased_current_ids)
    new_rows = [row for row in inventory["violations"] if row["violation_id"] in set(new_ids)]
    existing_rows = [
        row
        for row in inventory["violations"]
        if _baseline_violation_id(str(row.get("violation_id") or "")) in baseline_ids
    ]
    moved_existing = [
        {
            "current_violation_id": current_id,
            "baseline_violation_id": baseline_id,
        }
        for current_id, baseline_id in sorted(MOVED_VIOLATION_ALIASES.items())
        if current_id in current_ids and baseline_id in baseline_ids
    ]
    gate_status = "pass" if not new_rows else "blocked"
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "row_type": "refactor_size_gate_report",
        "generated_at": _generated_at(),
        "research_only": True,
        "no_live_provider_calls": True,
        "no_sends_trades_paper_rsi_or_triggered_fade": True,
        "gate_status": gate_status,
        "legacy_decomposition_gate_status": inventory.get("legacy_decomposition_gate_status"),
        "baseline_path": f"research/{BASELINE_JSON}",
        "baseline_present": baseline_path.exists(),
        "policy": {
            "existing_violations": "warning",
            "new_violations_compared_to_baseline": "blocker",
            "v3_production_file_under_1200_lines": "target",
            "v3_production_file_over_1500_lines": "blocker unless explicitly accepted",
            "production_file_over_1200_lines": "warning",
            "production_file_over_1500_lines": "blocker unless explicitly accepted",
            "production_file_over_2000_lines": "legacy blocker threshold retained for continuity",
            "production_file_over_3000_lines": "blocker",
            "test_file_size_debt": "tracked separately from production completion",
            "baseline_update": "explicit make refactor-size-baseline-update only",
        },
        "new_violation_count": len(new_rows),
        "v3_gate_status": v3_gate_snapshot["status"],
        "v3_auto_accept_ready": v3_gate_snapshot["v3_auto_accept_ready"],
        "v3_auto_accept_blockers": v3_gate_snapshot.get("auto_accept_blockers", []),
        "v3_blockers": v3_gate_snapshot.get("v3_blockers", []),
        "v3_pending_exceptions": v3_gate_snapshot.get("v3_pending_exceptions", []),
        "v3_accepted_exceptions": v3_gate_snapshot.get("v3_accepted_exceptions", {}),
        "v3_gates": v3_gate_snapshot["gate_values"],
        "v3_gate_snapshot": v3_gate_snapshot,
        "existing_violation_count": len(existing_rows),
        "resolved_violation_count": len(resolved_ids),
        "moved_existing_violation_count": len(moved_existing),
        "moved_existing_violation_aliases": moved_existing,
        "new_violations": new_rows,
        "resolved_violation_ids": resolved_ids,
        "existing_violations": existing_rows,
        **inventory,
    }


def write_baseline(*, root: str | Path | None = None, out_dir: str | Path | None = None) -> tuple[Path, dict[str, Any]]:
    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    target = Path(out_dir).expanduser() if out_dir is not None else repo_root / "research"
    target.mkdir(parents=True, exist_ok=True)
    payload = build_baseline(root=repo_root)
    path = target / BASELINE_JSON
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, payload


def write_gate_report(
    *,
    root: str | Path | None = None,
    out_dir: str | Path | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    target = Path(out_dir).expanduser() if out_dir is not None else repo_root / "research"
    target.mkdir(parents=True, exist_ok=True)
    payload = build_gate_report(root=repo_root)
    json_path = target / REPORT_JSON
    md_path = target / REPORT_MD
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_gate_report(payload), encoding="utf-8")
    return json_path, md_path, payload


def format_gate_report(report: dict[str, Any]) -> str:
    lines = [
        "# Refactor Size Gates",
        "",
        "Static source inventory only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- gate_status: `{report.get('gate_status')}`",
        f"- baseline_present: `{str(bool(report.get('baseline_present'))).lower()}`",
        f"- files_over_limit_count: `{report.get('files_over_limit_count', 0)}`",
        f"- v3_gate_status: `{report.get('v3_gate_status')}`",
        f"- v3_auto_accept_ready: `{report.get('v3_auto_accept_ready')}`",
        f"- v3_blockers: `{json.dumps(report.get('v3_blockers', []), sort_keys=True)}`",
        f"- production_files_over_1200_lines: `{report.get('production_files_over_1200_lines', 0)}`",
        f"- accepted_production_files_over_1200_lines: `{report.get('accepted_production_files_over_1200_lines', 0)}`",
        f"- unresolved_production_files_over_1200_lines: `{report.get('unresolved_production_files_over_1200_lines', 0)}`",
        f"- production_size_gate_status: `{report.get('production_size_gate_status')}`",
        f"- production_files_over_1500_lines: `{report.get('production_files_over_1500_lines', 0)}`",
        f"- production_files_over_2000_lines: `{report.get('production_files_over_2000_lines', 0)}`",
        f"- production_files_over_3000_lines: `{report.get('production_files_over_3000_lines', 0)}`",
        f"- production_classes_over_limit: `{report.get('production_classes_over_limit', 0)}`",
        f"- production_functions_over_limit: `{report.get('production_functions_over_limit', 0)}`",
        f"- test_size_gate_status: `{report.get('test_size_gate_status')}`",
        f"- test_files_over_1500_lines: `{report.get('test_files_over_1500_lines', 0)}`",
        f"- classes_over_limit_count: `{report.get('classes_over_limit_count', 0)}`",
        f"- functions_over_limit_count: `{report.get('functions_over_limit_count', 0)}`",
        f"- accepted_class_exceptions_count: `{report.get('accepted_class_exceptions_count', 0)}`",
        f"- remaining_class_ownership_debt_count: `{report.get('remaining_class_ownership_debt_count', 0)}`",
        f"- modules_with_multiple_public_classes_count: `{report.get('modules_with_multiple_public_classes_count', 0)}`",
        f"- modules_with_multiple_public_classes_status: `{report.get('modules_with_multiple_public_classes_status')}`",
        f"- multi_public_class_modules_count: `{report.get('multi_public_class_modules_count', 0)}`",
        f"- accepted_model_bundles_count: `{report.get('accepted_model_bundles_count', 0)}`",
        f"- unresolved_multi_class_modules_count: `{report.get('unresolved_multi_class_modules_count', 0)}`",
        f"- new_violation_count: `{report.get('new_violation_count', 0)}`",
        f"- moved_existing_violation_count: `{report.get('moved_existing_violation_count', 0)}`",
        f"- legacy_decomposition_gate_status: `{report.get('legacy_decomposition_gate_status')}`",
        f"- legacy_files_over_1500_lines: `{report.get('legacy_files_over_1500_lines', 0)}`",
        f"- legacy_files_over_3000_lines: `{report.get('legacy_files_over_3000_lines', 0)}`",
        f"- legacy_total_lines: `{report.get('legacy_total_lines', 0)}`",
        f"- legacy_classes_over_limit: `{report.get('legacy_classes_over_limit', 0)}`",
        f"- legacy_functions_over_limit: `{report.get('legacy_functions_over_limit', 0)}`",
        f"- legacy_modules_with_multiple_public_classes: `{report.get('legacy_modules_with_multiple_public_classes', 0)}`",
        "",
        "## Policy",
        "",
        "- Existing violations from `research/REFACTOR_SIZE_BASELINE.json` are warnings.",
        "- New file/function/class/module ownership violations are blockers.",
        "- Refactor v3 targets production files below 1,200 lines.",
        "- Production files over 1,200 lines are warnings and must either be split or documented.",
        "- Refactor v3 treats production files over 1,500 lines as blockers unless explicitly accepted.",
        "- Production files over 1,500 lines block refactor-complete status unless explicitly accepted.",
        "- Production files over 2,000 lines remain a legacy continuity threshold.",
        "- Production files over 3,000 lines are blockers.",
        "- Test file size debt is tracked separately and does not block production refactor completion.",
        "- Legacy implementation files over 1,500 lines are warnings.",
        "- Legacy implementation files over 3,000 lines block refactor-complete status.",
        "- New production modules with multiple public classes are blockers unless registered as accepted model bundles.",
        "- Baseline updates require the explicit `make refactor-size-baseline-update` target.",
        "",
        "## New Violations",
        "",
        "| category | id | lines/count |",
        "|---|---|---:|",
    ]
    for row in _limit_rows(report.get("new_violations"), 120):
        lines.append(_violation_row(row))
    lines.extend([
        "",
        "## Refactor V3 Gates",
        "",
        "| gate | value | severity |",
        "|---|---:|---|",
    ])
    v3_snapshot = report.get("v3_gate_snapshot") if isinstance(report.get("v3_gate_snapshot"), dict) else {}
    v3_values = v3_snapshot.get("gate_values") if isinstance(v3_snapshot.get("gate_values"), dict) else {}
    v3_severity = v3_snapshot.get("gate_severity") if isinstance(v3_snapshot.get("gate_severity"), dict) else {}
    for name in refactor_v3_contract.V3_GATE_NAMES:
        lines.append(f"| `{name}` | {v3_values.get(name, 0)} | {v3_severity.get(name, '')} |")
    lines.extend([
        "",
        "## Moved Existing Violations",
        "",
        "| current id | baseline id |",
        "|---|---|",
    ])
    for row in _limit_rows(report.get("moved_existing_violation_aliases"), 40):
        lines.append(f"| `{row.get('current_violation_id')}` | `{row.get('baseline_violation_id')}` |")
    lines.extend([
        "",
        "## Legacy Decomposition Gate",
        "",
        "| path | lines |",
        "|---|---:|",
    ])
    for row in _limit_rows(report.get("largest_legacy_files"), 40):
        lines.append(f"| `{row.get('path')}` | {row.get('line_count', 0)} |")
    lines.extend([
        "",
        "## Largest Production Files",
        "",
        "| path | lines |",
        "|---|---:|",
    ])
    for row in _limit_rows(report.get("largest_production_files"), 40):
        lines.append(f"| `{row.get('path')}` | {row.get('line_count', 0)} |")
    _append_production_over_target_sections(lines, report)
    lines.extend([
        "",
        "## Largest Test Files",
        "",
        "| path | lines |",
        "|---|---:|",
    ])
    for row in _limit_rows(report.get("largest_test_files"), 40):
        lines.append(f"| `{row.get('path')}` | {row.get('line_count', 0)} |")
    lines.extend([
        "",
        "## Files Over 1500 Lines",
        "",
        "| path | lines |",
        "|---|---:|",
    ])
    for row in _limit_rows(report.get("files_over_limit"), 120):
        lines.append(f"| `{row.get('path')}` | {row.get('line_count', 0)} |")
    lines.extend([
        "",
        "## Existing Violations",
        "",
        "| category | id | lines/count |",
        "|---|---|---:|",
    ])
    for row in _limit_rows(report.get("existing_violations"), 200):
        lines.append(_violation_row(row))
    return "\n".join(lines).rstrip() + "\n"


def _append_production_over_target_sections(lines: list[str], report: dict[str, Any]) -> None:
    lines.extend(["", "## Accepted Production Files Over 1200 Lines", "", "| path | lines | reason | revisit |", "|---|---:|---|---|"])
    for row in _limit_rows(report.get("accepted_production_files_over_1200_line_rows"), 120):
        lines.append(
            f"| `{row.get('path')}` | {row.get('line_count', 0)} | "
            f"{row.get('reason') or ''} | {row.get('revisit_condition') or ''} |"
        )
    lines.extend(["", "## Unresolved Production Files Over 1200 Lines", "", "| path | lines |", "|---|---:|"])
    unresolved_over_1200 = list(_limit_rows(report.get("unresolved_production_files_over_1200_line_rows"), 120))
    if unresolved_over_1200:
        for row in unresolved_over_1200:
            lines.append(f"| `{row.get('path')}` | {row.get('line_count', 0)} |")
    else:
        lines.append("| none | 0 |")


def _file_line_rows(repo_root: Path, *, file_line_limit: int) -> list[dict[str, Any]]:
    roots = (repo_root / "crypto_rsi_scanner", repo_root / "tests")
    rows: list[dict[str, Any]] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(repo_root).as_posix()
            line_count = _line_count(path)
            rows.append(
                {
                    "path": rel,
                    "line_count": line_count,
                    "limit": file_line_limit,
                    "source_kind": "production" if root.name == "crypto_rsi_scanner" else "test",
                }
            )
    return rows


def _line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return 0


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _limit_rows(rows: object, limit: int) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [row for row in rows[:limit] if isinstance(row, dict)]


def _baseline_violation_id(violation_id: str) -> str:
    return MOVED_VIOLATION_ALIASES.get(violation_id, violation_id)


def _violation_row(row: dict[str, Any]) -> str:
    amount = row.get("line_count") or row.get("public_class_count") or ""
    return f"| `{row.get('category')}` | `{row.get('violation_id')}` | {amount} |"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write static refactor size gate reports.")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args(argv)
    if args.update_baseline:
        baseline_path, baseline = write_baseline(out_dir=args.out_dir)
        print(baseline_path)
        print(f"baseline_violation_count={len(baseline.get('violation_ids', []))}")
        return 0
    json_path, md_path, report = write_gate_report(out_dir=args.out_dir)
    print(json_path)
    print(md_path)
    print(f"gate_status={report.get('gate_status')}")
    print(f"new_violation_count={report.get('new_violation_count', 0)}")
    return 0 if report.get("gate_status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
