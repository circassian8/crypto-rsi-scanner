"""CLI for explicit Decision Radar human-review timing actions."""

from __future__ import annotations

import argparse
import json
from typing import Any

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
    queue = subparsers.add_parser(
        "queue",
        help=(
            "Discover receipt-backed campaign ideas awaiting an explicit human "
            "view or completion action"
        ),
    )
    queue.add_argument("--evaluated-at")

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
        campaign = market_observation_campaign.build_campaign_report(
            args.artifact_base,
            evaluated_at=evaluated_at,
        )
        generations = (
            *campaign.get("authoritative_generations", ()),
            *campaign.get("non_authoritative_complete_generations", ()),
        )
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
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ("main",)
