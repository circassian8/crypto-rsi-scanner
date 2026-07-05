"""Source-pack/provider yield report for Event Alpha burn-in artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from . import common


SOURCE_YIELD_JSON = "event_alpha_source_yield_report.json"
SOURCE_YIELD_MD = "event_alpha_source_yield_report.md"


def build_source_yield_report(
    *,
    profile: str = "live_burn_in_no_send",
    artifact_namespace: str | None = None,
    base_dir: str | Path | None = None,
    days: int = 30,
) -> dict[str, Any]:
    context = common.context_for(profile=profile, artifact_namespace=artifact_namespace or profile, base_dir=base_dir)
    base = context.base_dir
    cutoff = common.date_window(days)
    candidates = _rows(base, "event_integrated_radar_candidates.jsonl", cutoff=cutoff)
    cores = _rows(base, "event_core_opportunities.jsonl", cutoff=cutoff)
    feedback = _rows(base, "event_alpha_feedback.jsonl", cutoff=cutoff)
    outcomes = _rows(base, "event_integrated_radar_outcomes.jsonl", cutoff=cutoff) + _rows(base, "event_alpha_outcomes.jsonl", cutoff=cutoff)
    rows = [*candidates, *cores]
    providers = sorted({_provider(row) for row in [*rows, *feedback]})
    source_packs = sorted({_source_pack(row) for row in [*rows, *feedback]})
    provider_rows = {
        provider: _summary_for(provider, "provider", rows=rows, feedback=feedback, outcomes=outcomes)
        for provider in providers
    }
    source_pack_rows = {
        pack: _summary_for(pack, "source_pack", rows=rows, feedback=feedback, outcomes=outcomes)
        for pack in source_packs
    }
    payload = common.with_safety(
        {
            "schema_version": "event_alpha_source_yield_report_v1",
            "row_type": "event_alpha_source_yield_report",
            "generated_at": common.utc_now().isoformat(),
            "profile": profile,
            "artifact_namespace": context.artifact_namespace,
            "namespace_dir": common.rel_path(context.namespace_dir),
            "window_days": days,
            "providers": provider_rows,
            "source_packs": source_pack_rows,
            "candidate_count": len(candidates),
            "core_opportunity_count": len(cores),
            "feedback_count": len(feedback),
            "outcome_count": len(outcomes),
            "recommendations_only": True,
            "auto_apply": False,
            "auto_apply_thresholds": False,
            "warnings": _warnings(provider_rows, source_pack_rows),
        }
    )
    common.write_json(context.namespace_dir / SOURCE_YIELD_JSON, payload)
    common.write_text(context.namespace_dir / SOURCE_YIELD_MD, format_source_yield_report(payload))
    return payload


def format_source_yield_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Event Alpha Source Yield Report",
        "",
        "Research-only source/provider usefulness report. Recommendations are advisory and never auto-apply thresholds.",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- profile: `{payload.get('profile')}`",
        f"- artifact_namespace: `{payload.get('artifact_namespace')}`",
        f"- recommendations_only: `{payload.get('recommendations_only')}`",
        f"- auto_apply: `{payload.get('auto_apply')}`",
        "",
        "## Providers",
        "",
    ]
    for provider, row in sorted((payload.get("providers") or {}).items()):
        lines.append(
            f"- {provider}: candidates={row.get('candidate_count')} labels={row.get('label_count')} "
            f"useful={row.get('useful_label_count')} noise={row.get('noise_label_count')} "
            f"recommendation=`{row.get('recommended_action')}`"
        )
    lines.extend(["", "## Source Packs", ""])
    for pack, row in sorted((payload.get("source_packs") or {}).items()):
        lines.append(
            f"- {pack}: candidates={row.get('candidate_count')} labels={row.get('label_count')} "
            f"useful={row.get('useful_label_count')} noise={row.get('noise_label_count')} "
            f"recommendation=`{row.get('recommended_action')}`"
        )
    warnings = payload.get("warnings") or []
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines).rstrip()


def _rows(base: Path, filename: str, *, cutoff) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in base.glob("*/" + filename):
        for row in common.read_jsonl(path):
            if (common.timestamp_for_row(row) or common.utc_now()) >= cutoff:
                out.append(row)
    return out


def _provider(row: Mapping[str, Any]) -> str:
    return str(row.get("provider") or row.get("source_provider") or row.get("source_origin") or "unknown")


def _source_pack(row: Mapping[str, Any]) -> str:
    return str(row.get("source_pack") or row.get("source_pack_id") or row.get("source_class") or "unknown")


def _summary_for(
    name: str,
    kind: str,
    *,
    rows: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    key_fn = _provider if kind == "provider" else _source_pack
    candidate_rows = [row for row in rows if key_fn(row) == name]
    label_rows = [row for row in feedback if key_fn(row) == name]
    useful = [row for row in label_rows if str(row.get("label") or "") in {"useful", "watch", "promising_source_type"}]
    noisy = [row for row in label_rows if str(row.get("label") or "") in {"junk", "source_noise", "false_positive", "duplicate"}]
    late = [row for row in label_rows if str(row.get("label") or "") == "late"]
    outcome_rows = [row for row in outcomes if key_fn(row) == name]
    return {
        "name": name,
        "kind": kind,
        "candidate_count": len(candidate_rows),
        "label_count": len(label_rows),
        "useful_label_count": len(useful),
        "noise_label_count": len(noisy),
        "late_label_count": len(late),
        "outcome_count": len(outcome_rows),
        "source_noise_rate_pct": round(100.0 * len(noisy) / len(label_rows), 2) if label_rows else 0.0,
        "usefulness_rate_pct": round(100.0 * len(useful) / len(label_rows), 2) if label_rows else 0.0,
        "recommended_action": _recommend_action(name, candidate_rows, label_rows, noisy, useful),
        "auto_apply": False,
    }


def _recommend_action(
    name: str,
    candidate_rows: list[dict[str, Any]],
    label_rows: list[dict[str, Any]],
    noisy: list[dict[str, Any]],
    useful: list[dict[str, Any]],
) -> str:
    lowered = name.casefold()
    if "coinalyze" in lowered and not label_rows:
        return "activate_next"
    if any(token in lowered for token in ("gdelt", "rss")) and label_rows and len(noisy) >= max(2, len(useful) * 2):
        return "context_only_or_quarantine"
    if label_rows and len(useful) > len(noisy):
        return "keep_and_measure"
    if candidate_rows and not label_rows:
        return "needs_labels"
    return "hold_no_threshold_change"


def _warnings(provider_rows: Mapping[str, Mapping[str, Any]], source_pack_rows: Mapping[str, Mapping[str, Any]]) -> list[str]:
    warnings: list[str] = []
    if not provider_rows and not source_pack_rows:
        warnings.append("no source yield rows found")
    for name, row in provider_rows.items():
        if row.get("candidate_count") and not row.get("label_count"):
            warnings.append(f"provider needs labels: {name}")
    return warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write Event Alpha source-yield report.")
    parser.add_argument("--profile", default="live_burn_in_no_send")
    parser.add_argument("--artifact-namespace", default=None)
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args(argv)
    payload = build_source_yield_report(profile=args.profile, artifact_namespace=args.artifact_namespace, base_dir=args.base_dir, days=args.days)
    print(f"event_alpha_source_yield_report: {payload['namespace_dir']}/{SOURCE_YIELD_MD}")
    print(f"providers={len(payload['providers'])} source_packs={len(payload['source_packs'])} auto_apply={payload['auto_apply']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
