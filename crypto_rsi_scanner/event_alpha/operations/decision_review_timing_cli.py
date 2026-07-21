"""CLI for explicit Decision Radar human-review timing actions."""

from __future__ import annotations

import argparse
import json
from typing import Any, Mapping

from . import decision_review_card_inspection
from . import decision_review_timing
from . import decision_review_timing_queue


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect or explicitly record human review timing for one exact "
            "receipt-backed Decision Radar idea."
        )
    )
    parser.add_argument("--artifact-base", required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser(
        "status",
        help=(
            "Read recorded human-action timing only; use queue to discover "
            "eligible ideas"
        ),
    )
    status.add_argument("--evaluated-at")
    status.add_argument("--output", choices=("json", "summary"), default="json")
    queue = subparsers.add_parser(
        "queue",
        help=(
            "Discover receipt-backed campaign ideas awaiting an explicit human "
            "view or completion action"
        ),
    )
    queue.add_argument("--evaluated-at")
    queue.add_argument("--output", choices=("json", "summary"), default="json")
    inspect = subparsers.add_parser(
        "inspect",
        help=(
            "Render one exact verified historical card without recording a "
            "human timing event"
        ),
    )
    inspect.add_argument("--namespace", required=True)
    inspect.add_argument("--idea-id", required=True)
    inspect.add_argument("--evaluated-at")
    inspect.add_argument(
        "--output",
        choices=("card", "json", "summary"),
        default="card",
    )

    for command, help_text in (
        ("view", "Record the first explicit operator view"),
        ("complete", "Record explicit review completion"),
    ):
        action = subparsers.add_parser(command, help=help_text)
        action.add_argument("--namespace", required=True)
        action.add_argument("--idea-id", required=True)
        action.add_argument("--reviewer-alias", required=True)
        action.add_argument("--confirm", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "status":
        result: dict[str, Any] = decision_review_timing.build_review_timing_report(
            args.artifact_base,
            evaluated_at=args.evaluated_at or _utc_now(),
        )
    elif args.command == "queue":
        from . import market_observation_campaign

        evaluated_at = args.evaluated_at or _utc_now()
        projection = (
            market_observation_campaign.build_review_timing_generation_projection(
                args.artifact_base,
                evaluated_at=evaluated_at,
            )
        )
        generations = projection["generation_summaries"]
        result = decision_review_timing_queue.build_review_timing_queue(
            args.artifact_base,
            generations,
            evaluated_at=evaluated_at,
        )
    elif args.command == "inspect":
        result = decision_review_card_inspection.inspect_review_card(
            args.artifact_base,
            args.namespace,
            args.idea_id,
            evaluated_at=args.evaluated_at or _utc_now(),
        )
    else:
        result = decision_review_timing.record_review_timing_event(
            args.artifact_base,
            artifact_namespace=args.namespace,
            idea_id=args.idea_id,
            event_type=(
                "first_viewed" if args.command == "view" else "review_completed"
            ),
            reviewer_alias=args.reviewer_alias,
            confirm=args.confirm,
        )
    output = getattr(args, "output", "json")
    if output == "card":
        print(_render_card_inspection(result))
    elif output == "summary":
        print(_render_summary(args.command, result))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _render_summary(command: str, result: Mapping[str, Any]) -> str:
    """Render bounded human-action truth without changing queue evaluation."""

    lines: list[tuple[str, object]] = [
        ("report", "decision_radar_review_timing"),
        ("command", command),
        ("status", result.get("status")),
        ("generated_at", result.get("generated_at") or result.get("evaluated_at")),
    ]
    if command == "queue":
        for field in (
            "eligible_generation_count",
            "eligible_idea_count",
            "action_required_count",
            "not_viewed_count",
            "in_review_count",
            "complete_count",
            "expired_idea_count",
            "unexpired_idea_count",
            "skipped_candidate_count",
        ):
            lines.append((field, result.get(field)))
    elif command == "inspect":
        for field in (
            "artifact_namespace",
            "idea_id",
            "core_opportunity_id",
            "radar_route",
            "generation_role",
            "current_dashboard_authority",
            "expires_at",
            "idea_temporal_status",
            "operator_warning",
            "card_display_path",
            "card_sha256",
            "card_size_bytes",
            "research_cards_tree_sha256",
            "inspection_records_human_timing_event",
            "confirmed_view_still_required_for_timing_evidence",
        ):
            lines.append((field, result.get(field)))
    else:
        for field in (
            "ledger_event_count",
            "idea_record_count",
            "first_viewed_count",
            "review_completed_count",
            "report_scope",
            "zero_idea_records_meaning",
            "eligible_idea_discovery_command",
        ):
            lines.append((field, result.get(field)))
    lines.extend(
        (
            ("provider_calls", result.get("provider_calls")),
            ("writes", result.get("writes")),
            (
                "commands_require_explicit_confirmation",
                result.get("commands_require_explicit_confirmation"),
            ),
            (
                "dashboard_reads_recorded_as_human_actions",
                result.get("dashboard_reads_recorded_as_human_actions"),
            ),
            (
                "protocol_v2_evidence_eligible",
                result.get("protocol_v2_evidence_eligible"),
            ),
        )
    )
    records = result.get("records")
    if type(records) is list:
        lines.extend(_queue_recurrence_summary(records))
        for index, raw in enumerate(records, start=1):
            if not isinstance(raw, Mapping):
                continue
            prefix = f"record[{index}]"
            context = raw.get("operator_review_context")
            if not isinstance(context, Mapping):
                context = {}
            for field in (
                "review_status",
                "radar_route",
                "artifact_namespace",
                "idea_id",
                "expires_at",
                "idea_temporal_status",
                "timing_action_warning",
            ):
                lines.append((f"{prefix}.{field}", raw.get(field)))
            for field in (
                "symbol",
                "canonical_asset_id",
                "anomaly_type",
                "actionability_score",
                "evidence_confidence_score",
                "risk_score",
                "urgency_score",
            ):
                lines.append((f"{prefix}.{field}", context.get(field)))
            lines.append(
                (f"{prefix}.inspection_command", raw.get("inspection_command"))
            )
            lines.append((f"{prefix}.next_safe_command", raw.get("next_safe_command")))
    safety = result.get("safety")
    if isinstance(safety, Mapping):
        for field in (
            "provider_calls",
            "telegram_sends",
            "trades",
            "orders",
            "event_alpha_paper_trades",
            "normal_rsi_writes",
            "event_alpha_triggered_fade",
            "production_policy_mutations",
        ):
            lines.append((f"safety.{field}", safety.get(field)))
    full_json_command = (
        "make radar-review-timing-inspect "
        f"RADAR_REVIEW_NAMESPACE={_summary_value(result.get('artifact_namespace'))} "
        f"RADAR_REVIEW_IDEA_ID={_summary_value(result.get('idea_id'))} "
        "RADAR_REVIEW_INSPECTION_OUTPUT=json PYTHON=.venv/bin/python"
        if command == "inspect"
        else f"make radar-review-timing-{command} "
        "RADAR_REVIEW_TIMING_OUTPUT=json PYTHON=.venv/bin/python"
    )
    lines.extend(
        (
            ("research_only", result.get("research_only")),
            ("full_json_command", full_json_command),
        )
    )
    return "\n".join(f"{key}={_summary_value(value)}" for key, value in lines)


def _render_card_inspection(result: Mapping[str, Any]) -> str:
    """Lead exact card bytes with unavoidable historical/timing truth."""

    markdown = result.get("card_markdown")
    if not isinstance(markdown, str):
        raise ValueError("review_card_markdown_missing")
    header = [
        "# Exact Decision Radar Review Card Inspection",
        "",
        f"- Status: {_summary_value(result.get('status'))}",
        f"- Generation role: {_summary_value(result.get('generation_role'))}",
        f"- Idea temporal status: {_summary_value(result.get('idea_temporal_status'))}",
        f"- Expires at: {_summary_value(result.get('expires_at'))}",
        f"- Warning: {_summary_value(result.get('operator_warning'))}",
        f"- Exact card SHA-256: {_summary_value(result.get('card_sha256'))}",
        "- This read-only inspection did not record a human timing event.",
        "- Run the separate confirmed view command only when you intend to record timing evidence.",
        "",
        "---",
        "",
    ]
    return "\n".join(header) + markdown.rstrip("\n")


def _queue_recurrence_summary(
    records: list[object],
) -> list[tuple[str, object]]:
    """Group repeated idea ids for display without collapsing exact actions."""

    groups: dict[str, dict[str, object]] = {}
    valid_record_count = 0
    for raw in records:
        if not isinstance(raw, Mapping):
            continue
        valid_record_count += 1
        idea_id = _summary_value(raw.get("idea_id"))
        group = groups.setdefault(
            idea_id,
            {
                "core_opportunity_ids": set(),
                "symbols": set(),
                "canonical_asset_ids": set(),
                "anomaly_types": set(),
                "routes": set(),
                "review_statuses": set(),
                "available_at": [],
                "actionability_scores": [],
                "evidence_confidence_scores": [],
                "risk_scores": [],
                "urgency_scores": [],
                "occurrence_count": 0,
            },
        )
        group["occurrence_count"] = int(group["occurrence_count"]) + 1
        for field, target in (
            ("core_opportunity_id", "core_opportunity_ids"),
            ("radar_route", "routes"),
            ("review_status", "review_statuses"),
        ):
            value = raw.get(field)
            if value is not None:
                cast_set = group[target]
                if isinstance(cast_set, set):
                    cast_set.add(_summary_value(value))
        context = raw.get("operator_review_context")
        if isinstance(context, Mapping):
            for field, target in (
                ("symbol", "symbols"),
                ("canonical_asset_id", "canonical_asset_ids"),
                ("anomaly_type", "anomaly_types"),
            ):
                value = context.get(field)
                if value is not None:
                    cast_set = group[target]
                    if isinstance(cast_set, set):
                        cast_set.add(_summary_value(value))
            for field, target in (
                ("actionability_score", "actionability_scores"),
                ("evidence_confidence_score", "evidence_confidence_scores"),
                ("risk_score", "risk_scores"),
                ("urgency_score", "urgency_scores"),
            ):
                value = context.get(field)
                if type(value) in (int, float):
                    cast_values = group[target]
                    if isinstance(cast_values, list):
                        cast_values.append(value)
        available_at = raw.get("idea_available_at")
        if available_at is not None:
            cast_times = group["available_at"]
            if isinstance(cast_times, list):
                cast_times.append(_summary_value(available_at))

    ordered = sorted(
        groups.items(),
        key=lambda item: (
            min(item[1]["available_at"]) if item[1]["available_at"] else "",
            item[0],
        ),
    )
    lines: list[tuple[str, object]] = [
        ("generation_specific_review_record_count", valid_record_count),
        ("unique_idea_id_count", len(ordered)),
        (
            "recurring_idea_id_count",
            sum(int(group["occurrence_count"]) > 1 for _, group in ordered),
        ),
        (
            "review_scope",
            "one_explicit_timing_action_per_generation_and_idea;recurrence_is_presentation_only",
        ),
    ]
    for index, (idea_id, group) in enumerate(ordered, start=1):
        prefix = f"idea_group[{index}]"
        available = group["available_at"]
        lines.extend(
            (
                (f"{prefix}.idea_id", idea_id),
                (
                    f"{prefix}.core_opportunity_ids",
                    ",".join(sorted(group["core_opportunity_ids"])),
                ),
                (f"{prefix}.symbols", ",".join(sorted(group["symbols"]))),
                (
                    f"{prefix}.canonical_asset_ids",
                    ",".join(sorted(group["canonical_asset_ids"])),
                ),
                (
                    f"{prefix}.anomaly_types",
                    ",".join(sorted(group["anomaly_types"])),
                ),
                (f"{prefix}.generation_count", group["occurrence_count"]),
                (f"{prefix}.routes", ",".join(sorted(group["routes"]))),
                (
                    f"{prefix}.review_statuses",
                    ",".join(sorted(group["review_statuses"])),
                ),
                (
                    f"{prefix}.first_available_at",
                    min(available) if available else None,
                ),
                (
                    f"{prefix}.latest_available_at",
                    max(available) if available else None,
                ),
            )
        )
        for output_field, storage_field in (
            ("actionability_score", "actionability_scores"),
            ("evidence_confidence_score", "evidence_confidence_scores"),
            ("risk_score", "risk_scores"),
            ("urgency_score", "urgency_scores"),
        ):
            lines.append(
                (
                    f"{prefix}.{output_field}_range",
                    _score_range(group[storage_field]),
                )
            )
    return lines


def _score_range(values: object) -> str:
    if not isinstance(values, list) or not values:
        return "unavailable"
    return f"{min(values):g}..{max(values):g}"


def _summary_value(value: object) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).replace("\r", " ").replace("\n", " ")


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ("main",)
