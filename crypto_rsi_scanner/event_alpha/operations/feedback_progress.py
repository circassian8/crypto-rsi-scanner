"""Feedback progress report for Event Alpha burn-in."""

from __future__ import annotations

import argparse
from datetime import timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from . import common
from .review_inbox import INBOX_JSON


PROGRESS_JSON = "event_alpha_feedback_progress.json"
PROGRESS_MD = "event_alpha_feedback_progress.md"


def build_feedback_progress(
    *,
    profile: str,
    artifact_namespace: str | None = None,
    base_dir: str | Path | None = None,
    days: int = 7,
    now=None,
) -> dict[str, Any]:
    generated = now or common.utc_now()
    context = common.context_for(profile=profile, artifact_namespace=artifact_namespace or profile, base_dir=base_dir)
    feedback = common.read_jsonl(context.feedback_path)
    inbox = common.read_json(context.namespace_dir / INBOX_JSON)
    generated = generated.astimezone(timezone.utc)
    today_cutoff = generated - timedelta(days=1)
    week_cutoff = generated - timedelta(days=max(1, int(days or 7)))
    today = [row for row in feedback if (common.timestamp_for_row(row) or generated) >= today_cutoff]
    week = [row for row in feedback if (common.timestamp_for_row(row) or generated) >= week_cutoff]
    inbox_items = inbox.get("items") if isinstance(inbox.get("items"), list) else []
    feedback_targets = {
        str(row.get("feedback_target") or row.get("target") or "")
        for row in feedback
        if str(row.get("feedback_target") or row.get("target") or "").strip()
    }
    inbox_targets = {
        str(row.get("feedback_target") or "")
        for row in inbox_items
        if isinstance(row, Mapping) and str(row.get("feedback_target") or "").strip()
    }
    stale_targets = [
        target
        for target in sorted(feedback_targets)
        if target and target not in inbox_targets and not _target_has_lineage(target, feedback)
    ]
    coverage = (100.0 * len(feedback_targets & inbox_targets) / len(inbox_targets)) if inbox_targets else 0.0
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_feedback_progress_v1",
            "row_type": "event_alpha_feedback_progress",
            "generated_at": generated.isoformat(),
            "profile": profile,
            "artifact_namespace": context.artifact_namespace,
            "namespace_dir": common.rel_path(context.namespace_dir),
            "labels_today": len(today),
            "labels_this_week": len(week),
            "window_days": max(1, int(days or 7)),
            "labels_total": len(feedback),
            "labels_by_type": common.count_by(feedback, "label"),
            "labels_by_opportunity_type": common.count_by(feedback, "opportunity_type", "lane"),
            "labels_by_source_pack": common.count_by(feedback, "source_pack"),
            "labels_by_provider": common.count_by(feedback, "source_provider", "provider"),
            "labels_by_candidate_family": common.count_by(feedback, "core_opportunity_id", "coin_id", "symbol"),
            "unlabeled_review_items": max(0, len(inbox_targets - feedback_targets)),
            "label_coverage_pct": round(coverage, 2),
            "stale_unresolved_feedback_targets": stale_targets,
        }
    )
    common.write_json(context.namespace_dir / PROGRESS_JSON, payload)
    common.write_text(context.namespace_dir / PROGRESS_MD, format_feedback_progress(payload))
    return payload


def format_feedback_progress(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Event Alpha Feedback Progress",
        "",
        "Research-only feedback progress. Feedback rows are labels only and do not mutate candidates, core opportunities, paper trades, live DB rows, or alert routes.",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- profile: `{payload.get('profile')}`",
        f"- artifact_namespace: `{payload.get('artifact_namespace')}`",
        f"- labels_today: `{payload.get('labels_today')}`",
        f"- labels_this_week: `{payload.get('labels_this_week')}`",
        f"- labels_total: `{payload.get('labels_total')}`",
        f"- unlabeled_review_items: `{payload.get('unlabeled_review_items')}`",
        f"- label_coverage_pct: `{payload.get('label_coverage_pct')}`",
        "",
        "## Breakdowns",
        "",
        common.table_line("labels_by_type", payload.get("labels_by_type") or {}),
        common.table_line("labels_by_opportunity_type", payload.get("labels_by_opportunity_type") or {}),
        common.table_line("labels_by_source_pack", payload.get("labels_by_source_pack") or {}),
        common.table_line("labels_by_provider", payload.get("labels_by_provider") or {}),
    ]
    stale = payload.get("stale_unresolved_feedback_targets") or []
    if stale:
        lines.extend(["", "## Stale / Unresolved Feedback Targets", ""])
        lines.extend(f"- `{target}`" for target in stale[:50])
    lines.append("")
    lines.append("No thresholds were changed.")
    return "\n".join(lines).rstrip()


def _target_has_lineage(target: str, rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        if target not in {str(row.get("feedback_target") or ""), str(row.get("target") or "")}:
            continue
        if row.get("core_opportunity_id") or row.get("card_path"):
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write Event Alpha feedback progress artifacts.")
    parser.add_argument("--profile", default="notify_llm_deep")
    parser.add_argument("--artifact-namespace", default=None)
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args(argv)
    payload = build_feedback_progress(profile=args.profile, artifact_namespace=args.artifact_namespace, base_dir=args.base_dir, days=args.days)
    print(f"event_alpha_feedback_progress: {payload['namespace_dir']}/{PROGRESS_MD}")
    print(f"labels_today={payload['labels_today']} label_coverage_pct={payload['label_coverage_pct']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
