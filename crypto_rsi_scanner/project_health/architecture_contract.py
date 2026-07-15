"""Architecture finalization contract and static gate helpers.

This module is inventory-only. It reads source files and report dictionaries,
but it does not import scanner runtime modules, call providers, send messages,
or touch trading/paper/RSI/Event Alpha route behavior.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..event_alpha import shims as event_alpha_shims


CONTRACT_SCHEMA_VERSION = "architecture_contract_v1"
CONTRACT_JSON = "ARCHITECTURE_CONTRACT.json"
CONTRACT_MD = "ARCHITECTURE_CONTRACT.md"
PRODUCTION_TARGET_LINE_LIMIT = 1200
PRODUCTION_BLOCKER_LINE_LIMIT = 1500
FUNCTION_BLOCKER_LINE_LIMIT = 150
CLASS_BLOCKER_LINE_LIMIT = 75
ACCEPTED_PRODUCTION_OVER_1200_LINE_FILES: dict[str, dict[str, str]] = {
    "crypto_rsi_scanner/project_health/architecture_report.py": {
        "reason": "Static architecture report aggregator preserving compatibility aliases and existing gate counters.",
        "revisit_condition": "Split when adding a new architecture report family or when report schema v2 removes historical aliases.",
    },
    "crypto_rsi_scanner/cli/parser_event_alpha/event_alpha_args.py": {
        "reason": "Stable argparse flag bundle; splitting individual flag groups risks CLI default drift.",
        "revisit_condition": "Next parser feature addition or when event-alpha flag groups can be snapshot-tested per submodule.",
    },
    "crypto_rsi_scanner/cli/services/scanner_parts/config_reports.py": {
        "reason": "Historical CLI report compatibility binder with broad scanner-service monkeypatch expectations.",
        "revisit_condition": "When config/report command bodies move to focused service modules.",
    },
    "crypto_rsi_scanner/config.py": {
        "reason": "Central environment/config contract; splitting risks import-time default and env-var behavior drift.",
        "revisit_condition": "When a dedicated config-v2 migration freeze and env snapshot tests exist.",
    },
    "crypto_rsi_scanner/event_alpha/artifacts/opportunity_audit.py": {
        "reason": "Dense operator audit renderer with many cross-section helper dependencies.",
        "revisit_condition": "When audit sections are split with golden Markdown fixture comparison.",
    },
    "crypto_rsi_scanner/event_alpha/artifacts/operator_state.py": {
        "reason": "Canonical operator-state hashing and exact revision ownership remain centralized and fail closed.",
        "revisit_condition": "When operator-state schema v2 can split digest policy from revision persistence with byte-stable fixtures.",
    },
    "crypto_rsi_scanner/event_alpha/notifications/pipeline_parts/plan_builder.py": {
        "reason": "Legacy notification-plan compatibility core; no-send semantics are more important than churn.",
        "revisit_condition": "When notification plan rows are covered by schema-level golden fixtures.",
    },
    "crypto_rsi_scanner/event_alpha/notifications/router.py": {
        "reason": "Route-gate decision logic is dense and behavior-critical for no-send notification eligibility.",
        "revisit_condition": "When route-decision/gate snapshots cover every lane and quality-gate cap.",
    },
    "crypto_rsi_scanner/event_alpha/outcomes/integrated_radar_outcomes.py": {
        "reason": "Outcome maturation/report code is stable and below the blocker threshold.",
        "revisit_condition": "When outcome performance views gain new sections.",
    },
    "crypto_rsi_scanner/event_alpha/radar/derivatives_crowding.py": {
        "reason": "Deterministic derivatives crowding evaluator with tightly coupled fixture smoke coverage.",
        "revisit_condition": "When adding a new derivatives metric family or crowding class.",
    },
    "crypto_rsi_scanner/event_alpha/radar/market_history.py": {
        "reason": "Pure temporal baseline evaluator keeps cadence, return anchors, and feature evidence in one closed calculation path.",
        "revisit_condition": "When adding another baseline family or changing the observation-spacing contract.",
    },
    "crypto_rsi_scanner/event_alpha/radar/opportunity_verdict.py": {
        "reason": "Verdict scoring and live-confirmation policy share many ordered caps and guardrails.",
        "revisit_condition": "When verdict snapshots cover each opportunity level and cap reason.",
    },
    "crypto_rsi_scanner/event_alpha/radar/source_enrichment.py": {
        "reason": "Provider/cache enrichment flow is stable and below blocker threshold.",
        "revisit_condition": "When adding a new enrichment source or cache policy.",
    },
    "crypto_rsi_scanner/event_alpha/shims.py": {
        "reason": "Static deleted-shim/tombstone registry and report writer; large by design and non-behavioral.",
        "revisit_condition": "When deleted-shim reporting can be split from old-import linting without changing gate output.",
    },
    "crypto_rsi_scanner/event_alpha/operations/market_no_send.py": {
        "reason": "Safety-critical no-send generation orchestrator owns one bounded provider call and fail-closed publication assembly.",
        "revisit_condition": "When adding another live-safe market provider or changing the generation transaction boundary.",
    },
    "crypto_rsi_scanner/event_alpha/operations/official_macro_calendar.py": {
        "reason": "Closed official-calendar acquisition keeps per-source authorization, immutable bytes, partial-coverage receipts, and validation in one fail-closed boundary.",
        "revisit_condition": "Split before adding another source or status family, and before any growth crosses the 1,500-line blocker.",
    },
    "crypto_rsi_scanner/event_alpha/operations/market_no_send_calendar.py": {
        "reason": "Read-once calendar snapshot validation keeps provenance, source coverage, secret checks, freshness, and publication projection in one security boundary.",
        "revisit_condition": "When the live calendar container schema changes or a second publication format is introduced.",
    },
    "crypto_rsi_scanner/event_alpha/operations/market_observation_campaign.py": {
        "reason": "Canonical campaign aggregation reconciles attempts, generations, outcomes, publication receipts, and current authority without provider activity.",
        "revisit_condition": "When the campaign report schema changes or another campaign family needs the same aggregation primitives.",
    },
    "crypto_rsi_scanner/event_alpha/operations/daily_operations.py": {
        "reason": "Daily Operations is the single fail-closed transaction boundary for readiness, generation, doctor, publication, restart, rollback, and terminal receipts.",
        "revisit_condition": "Split before any further lifecycle phase or growth approaches the 1,500-line blocker, and before another scheduler shares the transaction phases.",
    },
    "crypto_rsi_scanner/event_alpha/dashboard/calendar_page.py": {
        "reason": "The read-only calendar page keeps coverage, receipt, temporal, filter, and event-card truth in one server-rendered surface.",
        "revisit_condition": "When the calendar page gains a new interaction family and has byte-stable page-section fixtures.",
    },
    "crypto_rsi_scanner/event_alpha/dashboard/system_pages.py": {
        "reason": "The read-only health surface reconciles exact authority, maintenance, provider, request-ledger, and evidence-layer status without runtime inspection.",
        "revisit_condition": "When health sections have independent golden render fixtures or the system-page contract reaches v2.",
    },
    "crypto_rsi_scanner/architecture_report.py": {
        "reason": "Static final-report aggregator tying size, class, shim, namespace, and legacy-retirement gates together.",
        "revisit_condition": "When final-report sections can be split with byte-stable JSON/Markdown fixture comparisons.",
    },
}
V3_GATE_NAMES = (
    "nonessential_shims_remaining",
    "old_path_internal_imports",
    "old_path_test_imports",
    "public_compatibility_shims",
    "shim_removal_blockers",
    "deleted_shims",
    "production_files_over_1200_lines",
    "production_files_over_1500_lines",
    "public_classes_not_in_own_module",
    "class_exceptions_remaining",
    "functions_over_150_lines",
    "old_path_docs_references",
    "old_path_import_allowed_exceptions",
)

V3_INFORMATIONAL_GATES = frozenset(
    {
        "public_compatibility_shims",
        "deleted_shims",
        "old_path_import_allowed_exceptions",
    }
)
V3_ACCEPTED_EXCEPTION_GATES = frozenset(
    {
        "production_files_over_1200_lines",
        "class_exceptions_remaining",
    }
)
V3_HARD_BLOCKER_GATES = frozenset(
    name
    for name in V3_GATE_NAMES
    if name not in V3_INFORMATIONAL_GATES and name not in V3_ACCEPTED_EXCEPTION_GATES
)


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def build_architecture_contract(*, generated_at: datetime | None = None) -> dict[str, Any]:
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "row_type": "architecture_contract",
        "historical_row_type_alias": "refactor_v3_finalization_contract",
        "generated_at": generated,
        "research_only": True,
        "no_live_provider_calls": True,
        "no_sends_trades_paper_rsi_or_triggered_fade": True,
        "purpose": "Move from accepted refactor v2 compatibility shims to fully finished refactor v3.",
        "feature_policy": "Behavior-preserving refactor only; do not add product features.",
        "shim_policy": {
            "old_event_alpha_shim_paths": (
                "Temporary compatibility paths. Remove old top-level Event Alpha shims unless "
                "explicitly retained as public compatibility entrypoints."
            ),
            "new_imports": "New code must import new package paths only.",
            "scanner_py": "scanner.py remains a public CLI entrypoint compatibility wrapper.",
            "event_fade_py": (
                "event_fade.py remains intentionally outside Event Alpha. TRIGGERED_FADE must "
                "only come from event_fade.py plus proxy_fade."
            ),
        },
        "size_policy": {
            "production_module_target_lines_lt": PRODUCTION_TARGET_LINE_LIMIT,
            "production_file_blocker_lines_gt": PRODUCTION_BLOCKER_LINE_LIMIT,
            "production_file_blocker_policy": "Production files over 1,500 lines are blockers unless explicitly accepted.",
            "function_blocker_lines_gt": FUNCTION_BLOCKER_LINE_LIMIT,
            "function_blocker_policy": "Functions over 150 lines are blockers unless explicitly accepted.",
            "class_blocker_lines_gt": CLASS_BLOCKER_LINE_LIMIT,
            "class_blocker_policy": "Classes over 75 lines should be split or explicitly accepted.",
        },
        "class_ownership_policy": {
            "public_classes": "Public classes should live in their own modules.",
            "multiple_public_classes": (
                "Modules with multiple public classes should be reduced to model bundles only, "
                "with explicit documentation."
            ),
        },
        "public_compatibility_entrypoints": [
            {
                "path": "crypto_rsi_scanner/scanner.py",
                "module": "crypto_rsi_scanner.scanner",
                "reason": "Historical CLI/module entrypoint compatibility.",
                "retention": "permanent_public_entrypoint",
            }
        ],
        "intentional_exceptions": [
            {
                "path": "crypto_rsi_scanner/event_fade.py",
                "module": "crypto_rsi_scanner.event_fade",
                "reason": (
                    "Safety boundary for event-fade research and TRIGGERED_FADE ownership; "
                    "do not move into Event Alpha."
                ),
                "retention": "intentional_external_boundary",
            }
        ],
        "v3_gate_names": list(V3_GATE_NAMES),
        "auto_accept_policy": (
            "v3 auto-accept requires all v3 gates and documented exceptions to be clear. "
            "Accepted/documented target gaps report accepted_with_documented_exceptions; "
            "nonessential shims or unaccepted exceptions keep v3 pending or blocked."
        ),
    }


def build_v3_gate_snapshot(
    *,
    root: str | Path | None = None,
    shim_dependency_report: Mapping[str, Any] | None = None,
    size_gate_report: Mapping[str, Any] | None = None,
    class_ownership_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    repo_root = Path(root).expanduser().resolve() if root is not None else repo_root_from_module()
    shim_report = (
        dict(shim_dependency_report)
        if shim_dependency_report is not None
        else event_alpha_shims.build_shim_dependency_report(root=repo_root)
    )
    size_report = dict(size_gate_report or {})
    class_report = dict(class_ownership_report or {})
    production_over_1200_rows = _production_files_over(repo_root, PRODUCTION_TARGET_LINE_LIMIT)
    production_over_1500_rows = _production_files_over(repo_root, PRODUCTION_BLOCKER_LINE_LIMIT)
    public_not_own_rows = _public_classes_not_in_own_module(class_report)
    nonessential_shims = _nonessential_shim_rows(shim_report)
    shim_blocker_rows = [
        row for row in nonessential_shims if isinstance(row.get("removal_blockers"), list) and row["removal_blockers"]
    ]
    old_path_docs_references = int(shim_report.get("old_path_docs_references") or 0)
    gate_values = {
        "nonessential_shims_remaining": len(nonessential_shims),
        "old_path_internal_imports": int(shim_report.get("old_path_internal_imports") or 0),
        "old_path_test_imports": int(shim_report.get("old_path_test_imports") or 0),
        "public_compatibility_shims": _public_compatibility_shim_count(shim_report),
        "shim_removal_blockers": len(shim_blocker_rows),
        "deleted_shims": int(shim_report.get("deleted_shims") or 0),
        "production_files_over_1200_lines": len(production_over_1200_rows),
        "production_files_over_1500_lines": int(
            size_report.get("production_files_over_1500_lines")
            if size_report.get("production_files_over_1500_lines") is not None
            else len(production_over_1500_rows)
        ),
        "public_classes_not_in_own_module": len(public_not_own_rows),
        "class_exceptions_remaining": int(class_report.get("accepted_class_exceptions_count") or 0),
        "functions_over_150_lines": int(class_report.get("functions_over_limit_count") or 0),
        "old_path_docs_references": old_path_docs_references,
        "old_path_import_allowed_exceptions": int(
            shim_report.get("old_path_import_allowed_exceptions") or 0
        ),
    }
    hard_blocker_names = [
        name
        for name in V3_GATE_NAMES
        if name in V3_HARD_BLOCKER_GATES
        and int(gate_values.get(name) or 0) > 0
    ]
    accepted_exception_rows = _accepted_exception_rows(
        size_report=size_report,
        class_report=class_report,
        production_over_1200_rows=production_over_1200_rows,
        gate_values=gate_values,
    )
    pending_exception_names = [
        name
        for name in V3_ACCEPTED_EXCEPTION_GATES
        if int(gate_values.get(name) or 0) > 0 and not accepted_exception_rows.get(name)
    ]
    if hard_blocker_names:
        status = "blocked"
    elif pending_exception_names:
        status = "pending"
    elif any(accepted_exception_rows.values()):
        status = "accepted_with_documented_exceptions"
    else:
        status = "pass"
    return {
        "schema_version": "architecture_gate_snapshot_v1",
        "row_type": "architecture_gate_snapshot",
        "historical_row_type_alias": "refactor_v3_gate_snapshot",
        "status": status,
        "v3_auto_accept_ready": status == "pass",
        "auto_accept_blockers": hard_blocker_names + pending_exception_names,
        "v3_blockers": hard_blocker_names,
        "v3_pending_exceptions": pending_exception_names,
        "v3_accepted_exceptions": accepted_exception_rows,
        "gate_values": gate_values,
        "gate_severity": {
            "nonessential_shims_remaining": "blocker",
            "old_path_internal_imports": "blocker",
            "old_path_test_imports": "blocker",
            "public_compatibility_shims": "informational",
            "shim_removal_blockers": "blocker",
            "deleted_shims": "informational",
            "production_files_over_1200_lines": "accepted_exception" if accepted_exception_rows.get("production_files_over_1200_lines") else "target_gap",
            "production_files_over_1500_lines": "blocker",
            "public_classes_not_in_own_module": "blocker",
            "class_exceptions_remaining": "accepted_exception" if accepted_exception_rows.get("class_exceptions_remaining") else "pending_exception",
            "functions_over_150_lines": "blocker",
            "old_path_docs_references": "blocker_unless_policy_scoped",
            "old_path_import_allowed_exceptions": "informational",
        },
        "nonessential_shim_rows": nonessential_shims[:200],
        "shim_removal_blocker_rows": shim_blocker_rows[:200],
        "production_files_over_1200_line_rows": production_over_1200_rows,
        "production_files_over_1500_line_rows": production_over_1500_rows,
        "public_classes_not_in_own_module_rows": public_not_own_rows[:200],
        "contract_path": "research/ARCHITECTURE_CONTRACT.md",
    }


def write_architecture_contract(
    *,
    out_dir: str | Path | None = None,
    root: str | Path | None = None,
    generated_at: datetime | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    repo_root = Path(root).expanduser().resolve() if root is not None else repo_root_from_module()
    target = Path(out_dir).expanduser() if out_dir is not None else repo_root / "research"
    target.mkdir(parents=True, exist_ok=True)
    payload = build_architecture_contract(generated_at=generated_at)
    json_path = target / CONTRACT_JSON
    md_path = target / CONTRACT_MD
    data = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    markdown = format_architecture_contract(payload)
    json_path.write_text(data, encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return json_path, md_path, payload


def format_architecture_contract(contract: Mapping[str, Any]) -> str:
    lines = [
        "# Architecture Contract",
        "",
        "Research-only, behavior-preserving finalization contract. This document does not authorize live provider calls, live Telegram sends, trading, paper trading, execution/order logic, Event Alpha RSI signal writes, or Event Alpha-created TRIGGERED_FADE.",
        "",
        f"- generated_at: `{contract.get('generated_at')}`",
        f"- schema_version: `{contract.get('schema_version')}`",
        f"- purpose: {contract.get('purpose')}",
        f"- feature_policy: {contract.get('feature_policy')}",
        "",
        "## Compatibility Boundaries",
        "",
    ]
    shim_policy = contract.get("shim_policy") if isinstance(contract.get("shim_policy"), Mapping) else {}
    for key in ("old_event_alpha_shim_paths", "new_imports", "scanner_py", "event_fade_py"):
        lines.append(f"- `{key}`: {shim_policy.get(key)}")
    lines.extend(["", "## Size And Ownership Gates", ""])
    size_policy = contract.get("size_policy") if isinstance(contract.get("size_policy"), Mapping) else {}
    for key, value in size_policy.items():
        lines.append(f"- `{key}`: {value}")
    class_policy = contract.get("class_ownership_policy") if isinstance(contract.get("class_ownership_policy"), Mapping) else {}
    for key, value in class_policy.items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## V3 Gate Names", ""])
    for name in contract.get("v3_gate_names", []):
        lines.append(f"- `{name}`")
    lines.extend(["", "## Public Entrypoints", ""])
    for row in contract.get("public_compatibility_entrypoints", []):
        if isinstance(row, Mapping):
            lines.append(f"- `{row.get('path')}`: {row.get('reason')}")
    lines.extend(["", "## Intentional Exceptions", ""])
    for row in contract.get("intentional_exceptions", []):
        if isinstance(row, Mapping):
            lines.append(f"- `{row.get('path')}`: {row.get('reason')}")
    lines.extend(["", "## Auto-Accept", "", f"- {contract.get('auto_accept_policy')}"])
    return "\n".join(lines).rstrip() + "\n"


def _production_files_over(repo_root: Path, threshold: int) -> list[dict[str, Any]]:
    package_root = repo_root / "crypto_rsi_scanner"
    rows: list[dict[str, Any]] = []
    if not package_root.exists():
        return rows
    for path in sorted(package_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            line_count = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            continue
        if line_count > threshold:
            rows.append(
                {
                    "path": path.relative_to(repo_root).as_posix(),
                    "line_count": line_count,
                    "threshold": threshold,
                }
            )
    return sorted(rows, key=lambda row: (-int(row["line_count"]), str(row["path"])))


def _nonessential_shim_rows(shim_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in shim_report.get("entries", []):
        if not isinstance(row, Mapping):
            continue
        if row.get("recommended_action") == "keep_public_entrypoint":
            continue
        rows.append(
            {
                "old_module": row.get("old_module"),
                "new_module": row.get("new_module"),
                "recommended_action": row.get("recommended_action"),
                "removal_blockers": list(row.get("removal_blockers") or []),
                "safe_to_remove": bool(row.get("safe_to_remove")),
            }
        )
    return rows


def _public_compatibility_shim_count(shim_report: Mapping[str, Any]) -> int:
    counts = shim_report.get("removal_candidate_counts")
    if isinstance(counts, Mapping):
        return int(counts.get("keep_public_compatibility") or 0)
    return sum(
        1
        for row in shim_report.get("entries", [])
        if isinstance(row, Mapping) and row.get("recommended_action") == "keep_public_entrypoint"
    )


def _public_classes_not_in_own_module(class_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    source_rows = class_report.get("unresolved_multi_class_modules")
    if not isinstance(source_rows, list):
        source_rows = class_report.get("modules_with_multiple_public_classes", [])
    for row in source_rows:
        if not isinstance(row, Mapping):
            continue
        module = str(row.get("module") or "")
        is_model_bundle = module.endswith(".models")
        documented_exception = bool(row.get("exception_reason"))
        rows.append(
            {
                "module": module,
                "public_class_count": int(row.get("public_class_count") or 0),
                "model_bundle_candidate": is_model_bundle,
                "documented_exception": documented_exception,
                "v3_resolution": (
                    "document_model_bundle"
                    if is_model_bundle and not documented_exception
                    else "accepted_exception"
                    if documented_exception
                    else "split_public_classes"
                ),
            }
        )
    return rows


def _accepted_exception_rows(
    *,
    size_report: Mapping[str, Any],
    class_report: Mapping[str, Any],
    production_over_1200_rows: list[dict[str, Any]],
    gate_values: Mapping[str, Any],
) -> dict[str, Any]:
    accepted: dict[str, Any] = {}
    production_count = int(gate_values.get("production_files_over_1200_lines") or 0)
    has_size_counts = (
        "unresolved_production_files_over_1200_lines" in size_report
        or "accepted_production_files_over_1200_lines" in size_report
    )
    if has_size_counts:
        unresolved_production_count = int(size_report.get("unresolved_production_files_over_1200_lines") or 0)
        accepted_production_count = int(size_report.get("accepted_production_files_over_1200_lines") or 0)
    else:
        accepted_production_count = sum(
            1
            for row in production_over_1200_rows
            if str(row.get("path") or "") in ACCEPTED_PRODUCTION_OVER_1200_LINE_FILES
        )
        unresolved_production_count = max(production_count - accepted_production_count, 0)
    if production_count and unresolved_production_count == 0 and accepted_production_count == production_count:
        rows = size_report.get("accepted_production_files_over_1200_line_rows")
        if not isinstance(rows, list):
            rows = [
                _accepted_production_over_1200_row(row)
                for row in production_over_1200_rows
                if str(row.get("path") or "") in ACCEPTED_PRODUCTION_OVER_1200_LINE_FILES
            ]
        accepted["production_files_over_1200_lines"] = {
            "count": production_count,
            "reason": "accepted/documented production files over the v3 1,200-line target",
            "rows": rows,
        }

    class_exception_count = int(gate_values.get("class_exceptions_remaining") or 0)
    remaining_debt = int(class_report.get("remaining_class_ownership_debt_count") or 0)
    accepted_class_count = int(class_report.get("accepted_class_exceptions_count") or 0)
    if class_exception_count and remaining_debt == 0 and accepted_class_count == class_exception_count:
        rows = class_report.get("accepted_class_exceptions")
        if not isinstance(rows, list):
            rows = []
        accepted["class_exceptions_remaining"] = {
            "count": class_exception_count,
            "reason": "accepted/documented storage mixin class exceptions",
            "rows": rows,
        }
    return accepted


def _accepted_production_over_1200_row(row: Mapping[str, Any]) -> dict[str, Any]:
    path = str(row.get("path") or "")
    meta = ACCEPTED_PRODUCTION_OVER_1200_LINE_FILES.get(path, {})
    return {
        **dict(row),
        "accepted": True,
        "reason": str(meta.get("reason") or "Accepted v3 over-1200-line warning."),
        "revisit_condition": str(meta.get("revisit_condition") or "Revisit on the next behavior-freeze split pass."),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the architecture finalization contract.")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args(argv)
    json_path, md_path, _payload = write_architecture_contract(out_dir=args.out_dir)
    print(json_path)
    print(md_path)
    return 0


write_architecture_v3_contract = write_architecture_contract
build_architecture_v3_contract = build_architecture_contract


if __name__ == "__main__":
    raise SystemExit(main())
