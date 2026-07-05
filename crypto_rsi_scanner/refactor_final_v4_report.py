"""Refactor v4 final report writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


V4_FINAL_JSON = "REFACTOR_V4_FINAL_REPORT.json"
V4_FINAL_MD = "REFACTOR_V4_FINAL_REPORT.md"


def build_v4_final_report(*, v3_report: Mapping[str, Any], final_report: Mapping[str, Any]) -> dict[str, Any]:
    report = dict(v3_report)
    report.update(
        {
            "schema_version": "refactor_v4_final_report_v1",
            "row_type": "refactor_v4_final_report",
            "final_refactor_status": report.get("acceptance_status"),
            "final_refactor_contract": "no legacy files, no old flat Event Alpha imports, canonical module architecture only",
            "public_compatibility_entrypoints_manifest": final_report.get("public_compatibility_entrypoints_path"),
            "event_alpha_public_compatibility_entrypoints_manifest": "research/EVENT_ALPHA_PUBLIC_COMPATIBILITY_ENTRYPOINTS.json",
        }
    )
    return report


def format_v4_final_markdown(report: Mapping[str, Any], *, v3_markdown: str) -> str:
    text = v3_markdown.replace("# Refactor V3 Release Candidate Report", "# Refactor V4 Final Report", 1)
    text = text.replace("Research-only release-candidate report.", "Research-only final refactor report.", 1)
    lines = text.rstrip().splitlines()
    insert_at = 7 if len(lines) > 7 else len(lines)
    lines[insert_at:insert_at] = [
        f"- final_refactor_status: `{report.get('final_refactor_status')}`",
        f"- final_refactor_contract: `{report.get('final_refactor_contract')}`",
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
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_v4_final_markdown(report, v3_markdown=v3_markdown), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
