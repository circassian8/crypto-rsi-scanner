"""Command-line surface for guarded market/no-send generation."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from ... import config
from ..dashboard.readiness import DashboardReadinessError
from . import market_no_send


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=market_no_send.__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("readiness", "run", "smoke", "publish"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--artifact-base", default=str(config.EVENT_ALPHA_ARTIFACT_BASE_DIR))
        sub.add_argument(
            "--namespace",
            default=(
                market_no_send.DEFAULT_SMOKE_NAMESPACE
                if command == "smoke"
                else market_no_send.DEFAULT_NAMESPACE
            ),
        )
        sub.add_argument("--top-n", type=int, default=market_no_send.DEFAULT_TOP_N)
        sub.add_argument("--fetch-limit", type=int, default=None)
        sub.add_argument("--observed-at", default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "readiness":
            result = market_no_send.build_market_no_send_readiness(
                artifact_namespace=args.namespace,
                top_n=args.top_n,
                fetch_limit=args.fetch_limit,
            )
            print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
            return 0
        if args.command == "publish":
            published = market_no_send.publish_market_no_send_generation(
                args.artifact_base,
                args.namespace,
                now=args.observed_at,
            )
            snapshot = published.snapshot
            print(
                "radar_market_no_send_published: "
                f"namespace={snapshot.artifact_namespace} run_id={snapshot.run_id} "
                f"revision={snapshot.revision} pointer={published.pointer_path.name}"
            )
            return 0
        if args.command == "smoke":
            rows = market_no_send._smoke_rows()
            result = market_no_send.run_market_no_send_generation(
                artifact_base_dir=args.artifact_base,
                artifact_namespace=args.namespace,
                profile="fixture",
                run_mode="fixture",
                top_n=min(args.top_n, len(rows)),
                fetch_limit=args.fetch_limit,
                provider=lambda _limit: rows,
                observed_at=args.observed_at or "2026-06-15T16:00:00Z",
                environ={},
                fixture_dir=None,
                data_mode="mock",
                allow_non_live=True,
            )
        else:
            result = market_no_send.run_market_no_send_generation(
                artifact_base_dir=args.artifact_base,
                artifact_namespace=args.namespace,
                top_n=args.top_n,
                fetch_limit=args.fetch_limit,
                observed_at=args.observed_at,
            )
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0 if result.complete else 1
    except (market_no_send.MarketNoSendError, DashboardReadinessError) as exc:
        print(f"radar_market_no_send_blocked: {exc}", file=sys.stderr)
        return 1


__all__ = ("main",)
