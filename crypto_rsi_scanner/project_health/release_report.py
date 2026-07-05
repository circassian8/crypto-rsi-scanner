"""Architecture acceptance report writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


V4_FINAL_JSON = "ARCHITECTURE_ACCEPTANCE_REPORT.json"
V4_FINAL_MD = "ARCHITECTURE_ACCEPTANCE_REPORT.md"
LEGACY_V4_FINAL_JSON = "REFACTOR_V4_FINAL_REPORT.json"
LEGACY_V4_FINAL_MD = "REFACTOR_V4_FINAL_REPORT.md"


def build_v4_final_report(*, v3_report: Mapping[str, Any], final_report: Mapping[str, Any]) -> dict[str, Any]:
    report = dict(v3_report)
    report.update(
        {
            "schema_version": "architecture_acceptance_report_v1",
            "row_type": "architecture_acceptance_report",
            "historical_row_type_alias": "refactor_v4_final_report",
            "architecture_status": report.get("acceptance_status"),
            "architecture_contract": "no legacy files, no old flat Event Alpha imports, canonical module architecture only",
            "final_refactor_status": report.get("acceptance_status"),
            "final_refactor_contract": "historical alias for architecture_contract",
            "public_compatibility_entrypoints_manifest": final_report.get("public_compatibility_entrypoints_path"),
            "event_alpha_public_compatibility_entrypoints_manifest": "research/EVENT_ALPHA_PUBLIC_COMPATIBILITY_ENTRYPOINTS.json",
        }
    )
    return report


def format_v4_final_markdown(report: Mapping[str, Any], *, v3_markdown: str) -> str:
    text = v3_markdown.replace("# Refactor V3 Release Candidate Report", "# Architecture Acceptance Report", 1)
    text = text.replace("Research-only release-candidate report.", "Research-only architecture acceptance report.", 1)
    lines = text.rstrip().splitlines()
    insert_at = 7 if len(lines) > 7 else len(lines)
    lines[insert_at:insert_at] = [
        f"- architecture_status: `{report.get('architecture_status')}`",
        f"- architecture_contract: `{report.get('architecture_contract')}`",
        f"- public_compatibility_entrypoints_manifest: `{report.get('public_compatibility_entrypoints_manifest')}`",
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_v4_final_report(
    *,
    output_dir: Path,
    v3_report: Mapping[str, Any],
    v3_markdown: str,
    final_report: Mapping[str, Any],
) -> dict[str, Path]:
    report = build_v4_final_report(v3_report=v3_report, final_report=final_report)
    json_path = output_dir / V4_FINAL_JSON
    md_path = output_dir / V4_FINAL_MD
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    markdown = format_v4_final_markdown(report, v3_markdown=v3_markdown)
    json_path.write_text(payload, encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    (output_dir / LEGACY_V4_FINAL_JSON).write_text(payload, encoding="utf-8")
    (output_dir / LEGACY_V4_FINAL_MD).write_text(markdown, encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
