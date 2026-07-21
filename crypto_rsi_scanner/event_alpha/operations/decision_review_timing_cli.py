"""CLI for explicit Decision Radar human-review timing actions."""

from __future__ import annotations

import argparse
import json
from typing import Any, Mapping

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
    if output == "summary":
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
            "skipped_candidate_count",
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
        for index, raw in enumerate(records, start=1):
            if not isinstance(raw, Mapping):
                continue
            prefix = f"record[{index}]"
            for field in (
                "review_status",
                "radar_route",
                "directional_bias",
                "artifact_namespace",
                "idea_id",
                "idea_observed_at",
                "idea_available_at",
                "next_action",
                "next_safe_command",
            ):
                lines.append((f"{prefix}.{field}", raw.get(field)))
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
    lines.extend(
        (
            ("research_only", result.get("research_only")),
            (
                "full_json_command",
                f"make radar-review-timing-{command} "
                "RADAR_REVIEW_TIMING_OUTPUT=json PYTHON=.venv/bin/python",
            ),
        )
    )
    return "\n".join(f"{key}={_summary_value(value)}" for key, value in lines)


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
