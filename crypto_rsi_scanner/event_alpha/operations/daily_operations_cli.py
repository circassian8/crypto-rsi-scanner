"""Command-line adapter for Decision Radar Daily Operations v1."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from ... import config
from . import daily_operations, daily_operations_service, market_no_send


def build_parser() -> argparse.ArgumentParser:
    """Build the standalone Daily Operations command parser."""
    parser = argparse.ArgumentParser(description=daily_operations.__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("readiness", "status", "cycle", "install", "uninstall"):
        command = commands.add_parser(name)
        command.add_argument(
            "--artifact-base",
            default=str(config.EVENT_ALPHA_ARTIFACT_BASE_DIR),
        )
        command.add_argument("--top-n", type=int, default=market_no_send.DEFAULT_TOP_N)
        command.add_argument("--fetch-limit", type=int, default=None)
        command.add_argument(
            "--interval-seconds",
            type=int,
            default=daily_operations_service.DEFAULT_INTERVAL_SECONDS,
        )
        if name == "cycle":
            command.add_argument("--dry-run", action="store_true")
        if name in {"install", "uninstall"}:
            command.add_argument("--confirm", action="store_true")
    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    dependencies: daily_operations.DailyOperationsDependencies | None = None,
    service_dependencies: daily_operations_service.ServiceDependencies | None = None,
) -> int:
    """Parse and dispatch one Daily Operations command."""
    args = build_parser().parse_args(argv)
    deps = dependencies or daily_operations.DailyOperationsDependencies()
    try:
        if args.command == "status":
            payload = daily_operations.daily_operations_status(
                artifact_base_dir=args.artifact_base,
                top_n=args.top_n,
                fetch_limit=args.fetch_limit,
                interval_seconds=args.interval_seconds,
                dependencies=deps,
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.command == "readiness":
            now = daily_operations._as_utc(deps.now())
            namespace = daily_operations.unique_namespace(now, deps.token_hex(8))
            result = daily_operations.build_daily_operations_readiness(
                artifact_base_dir=args.artifact_base,
                artifact_namespace=namespace,
                top_n=args.top_n,
                fetch_limit=args.fetch_limit,
                interval_seconds=args.interval_seconds,
                dependencies=deps,
            )
            print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
            return 0
        if args.command == "cycle":
            result = daily_operations.run_daily_operations_cycle(
                artifact_base_dir=args.artifact_base,
                top_n=args.top_n,
                fetch_limit=args.fetch_limit,
                interval_seconds=args.interval_seconds,
                dry_run=args.dry_run,
                dependencies=deps,
            )
            print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
            return 0 if result.ok else 1
        operation_args = dict(
            confirm=args.confirm,
            artifact_base=args.artifact_base,
            top_n=args.top_n,
            fetch_limit=args.fetch_limit,
            interval_seconds=args.interval_seconds,
            dependencies=service_dependencies,
        )
        operation = (
            daily_operations_service.install_service(**operation_args)
            if args.command == "install"
            else daily_operations_service.uninstall_service(**operation_args)
        )
        print(json.dumps(operation.to_dict(), indent=2, sort_keys=True))
        return 0 if operation.ok else 1
    except (daily_operations.DailyOperationsError, ValueError, OSError) as exc:
        reason = (
            str(exc)
            if isinstance(exc, daily_operations.DailyOperationsError)
            else type(exc).__name__
        )
        print(f"radar_daily_operations_blocked: {reason}", file=sys.stderr)
        return 1


__all__ = ("build_parser", "run_cli")
