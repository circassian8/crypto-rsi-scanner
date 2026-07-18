"""CLI for explicit Decision Radar human-review timing actions."""

from __future__ import annotations

import argparse
import json
from typing import Any

from . import decision_review_timing


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
        "status", help="Read the bounded point-in-time review-timing report"
    )
    status.add_argument("--evaluated-at")

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
