"""Command-line adapter for Decision Radar Daily Operations v1."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from ... import config
from . import (
    daily_operations,
    daily_operations_current_status,
    daily_operations_publication,
    daily_operations_service,
    market_no_send,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the standalone Daily Operations command parser."""
    parser = argparse.ArgumentParser(description=daily_operations.__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in (
        "readiness",
        "status",
        "cycle",
        "reconcile-publication",
        "install",
        "uninstall",
    ):
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
        if name in {"readiness", "status"}:
            command.add_argument(
                "--output",
                choices=("json", "summary"),
                default="json",
                help="emit the full compatibility JSON or a concise operator summary",
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
            current = _build_current_readiness(args, deps)
            daily_operations_current_status.persist_current_status(
                args.artifact_base,
                current,
            )
            payload = daily_operations.daily_operations_status(
                artifact_base_dir=args.artifact_base,
                top_n=args.top_n,
                fetch_limit=args.fetch_limit,
                interval_seconds=args.interval_seconds,
                dependencies=deps,
            )
            payload["current_readiness"] = current.to_dict()
            payload.update(_current_report_values(current))
            _emit_readiness_output(
                payload,
                readiness=current,
                command="status",
                output=args.output,
            )
            return 0
        if args.command == "readiness":
            result = _build_current_readiness(args, deps)
            daily_operations_current_status.persist_current_status(
                args.artifact_base,
                result,
            )
            payload = result.to_dict()
            payload.update(_current_report_values(result))
            _emit_readiness_output(
                payload,
                readiness=result,
                command="readiness",
                output=args.output,
            )
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
        if args.command == "reconcile-publication":
            dashboard = deps.inspect_dashboard(artifact_base=args.artifact_base)
            validation = daily_operations_publication.reconcile_current_publication(
                args.artifact_base,
                dashboard=dashboard,
                recorded_at=deps.now(),
            )
            deps.refresh_campaign_report(
                daily_operations._read_only_base(args.artifact_base)
            )
            print(
                json.dumps(
                    {
                        "status": "reconciled",
                        "currently_authoritative": validation.currently_authoritative,
                        "publication_status": validation.publication_status,
                        "operations_status": validation.operations_status,
                        "errors": list(validation.errors),
                        "provider_calls": 0,
                        "dashboard_restarts": 0,
                        "no_send": True,
                        "research_only": True,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
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
    except (
        daily_operations.DailyOperationsError,
        daily_operations_publication.DailyOperationsPublicationError,
        ValueError,
        OSError,
    ) as exc:
        reason = (
            str(exc)
            if isinstance(
                exc,
                (
                    daily_operations.DailyOperationsError,
                    daily_operations_publication.DailyOperationsPublicationError,
                ),
            )
            else type(exc).__name__
        )
        print(f"radar_daily_operations_blocked: {reason}", file=sys.stderr)
        return 1


def _build_current_readiness(
    args: argparse.Namespace,
    dependencies: daily_operations.DailyOperationsDependencies,
) -> daily_operations.DailyOperationsReadiness:
    now = daily_operations._as_utc(dependencies.now())
    namespace = daily_operations.unique_namespace(now, dependencies.token_hex(8))
    return daily_operations.build_daily_operations_readiness(
        artifact_base_dir=args.artifact_base,
        artifact_namespace=namespace,
        top_n=args.top_n,
        fetch_limit=args.fetch_limit,
        interval_seconds=args.interval_seconds,
        dependencies=dependencies,
    )


def _current_report_values(
    readiness: daily_operations.DailyOperationsReadiness,
) -> dict[str, object]:
    current = daily_operations_current_status.current_status_values(readiness)
    fields = (
        "current_authorization_status",
        "current_authorization_checked_at",
        "current_provider_call_eligibility",
        "implications",
        "safe_manual_readiness_command",
        "installation_command",
        "rollback_disable_command",
        "installation_requires_confirmation",
        "authorization_boundary",
        "expected_provider_activity",
    )
    return {field: current[field] for field in fields}


def _emit_readiness_output(
    payload: dict[str, object],
    *,
    readiness: daily_operations.DailyOperationsReadiness,
    command: str,
    output: str,
) -> None:
    if output == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(_readiness_summary(payload, readiness=readiness, command=command))


def _readiness_summary(
    payload: dict[str, object],
    *,
    readiness: daily_operations.DailyOperationsReadiness,
    command: str,
) -> str:
    """Render a bounded, credential-free operator view of readiness truth."""

    market = readiness.market
    dashboard = readiness.dashboard
    scheduler = readiness.scheduler
    control_context = market.point_in_time_control_context_readiness
    if not isinstance(control_context, dict):
        control_context = {}
    coverage = control_context.get("field_coverage_counts")
    if not isinstance(coverage, dict):
        coverage = {}
    counted_rows = _summary_count(control_context.get("counted_observation_count"))
    lines: list[tuple[str, object]] = [
        ("report", "decision_radar_daily_operations"),
        ("command", command),
        ("status", readiness.status),
        ("reason", readiness.reason),
        ("checked_at", readiness.checked_at),
        ("proposed_namespace", readiness.artifact_namespace),
        ("current_authorization", payload["current_authorization_status"]),
        (
            "current_provider_call_eligibility",
            payload["current_provider_call_eligibility"],
        ),
        ("readiness_provider_calls", 0),
        ("cycle_would_call_provider", market.will_call_provider),
        ("cadence_status", market.cadence_status),
        ("next_eligible_observation_at", market.next_eligible_observation_at),
        ("baseline_status", market.baseline_status),
        ("baseline_observations", market.baseline_observation_count),
        (
            "baseline_counted_observations",
            market.baseline_counted_observation_count,
        ),
        (
            "baseline_too_close_observations",
            market.baseline_too_close_observation_count,
        ),
        (
            "historical_baseline_warm_assets",
            f"{market.baseline_warm_asset_count}/{market.baseline_asset_count}",
        ),
        ("control_context_status", control_context.get("status")),
        (
            "point_in_time_universe_context_rows",
            _coverage_ratio(
                control_context.get("point_in_time_universe_context_row_count"),
                counted_rows,
            ),
        ),
        (
            "market_regime_context_rows",
            _coverage_ratio(coverage.get("market_regime"), counted_rows),
        ),
        (
            "protocol_partition_context_rows",
            _coverage_ratio(coverage.get("protocol_partition"), counted_rows),
        ),
        (
            "complete_match_context_rows",
            _summary_count(control_context.get("complete_match_context_row_count")),
        ),
        ("spread_data_status", market.spread_data_status),
        ("calendar_snapshot_status", market.calendar_snapshot_status),
        ("dashboard_owned", dashboard.owned),
        ("scheduler_enabled", scheduler.enabled),
        ("scheduler_loaded", scheduler.loaded),
        ("scheduler_healthy", scheduler.healthy),
        ("next_safe_command", market.next_safe_command),
    ]
    if command == "status":
        state = payload.get("state")
        closed_state = state if isinstance(state, dict) else {}
        lines.extend(
            (
                ("cycle_rows_retained", payload.get("cycle_rows_retained")),
                ("last_cycle_status", closed_state.get("last_cycle_status")),
                ("last_cycle_reason", closed_state.get("last_cycle_reason")),
                (
                    "last_cycle_namespace",
                    closed_state.get("last_cycle_namespace"),
                ),
                (
                    "last_provider_attempt_status",
                    closed_state.get("last_provider_attempt_status"),
                ),
                (
                    "last_provider_attempted_at",
                    closed_state.get("last_provider_attempted_at"),
                ),
            )
        )
    lines.extend(
        (
            ("status_receipt_refreshed", True),
            ("telegram_sends", payload["telegram_sends"]),
            ("trades_created", payload["trades_created"]),
            ("orders_available", False),
            ("paper_trades_created", payload["paper_trades_created"]),
            (
                "normal_rsi_signal_rows_written",
                payload["normal_rsi_signal_rows_written"],
            ),
            ("triggered_fade_created", payload["triggered_fade_created"]),
            ("no_send", True),
            ("research_only", True),
            (
                "full_json_command",
                f"make radar-daily-ops-{command} "
                "RADAR_DAILY_OPS_OUTPUT=json PYTHON=.venv/bin/python",
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


def _summary_count(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _coverage_ratio(value: object, total: int | None) -> str | None:
    count = _summary_count(value)
    if count is None or total is None or count > total:
        return None
    return f"{count}/{total}"


__all__ = ("build_parser", "run_cli")
