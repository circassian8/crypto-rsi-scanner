"""Parser and command classification helpers for the CLI consolidation layer.

Runtime dispatch still lives in :mod:`crypto_rsi_scanner.scanner` during this
compatibility phase. ``build_parser`` mirrors the current scanner parser without
calling ``parse_args`` or executing any command branch.
"""

from __future__ import annotations

import argparse
import textwrap
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class CommandSnapshot:
    command_name: str
    flag: str
    command_group: str

    @property
    def dispatch_key(self) -> str:
        return self.command_name


COMMAND_FLAG_TO_SNAPSHOT: dict[str, CommandSnapshot] = {
    "--dry-run": CommandSnapshot("dry_run", "--dry-run", "rsi"),
    "--report": CommandSnapshot("report", "--report", "rsi"),
    "--score": CommandSnapshot("score", "--score", "paper"),
    "--refresh-paper": CommandSnapshot("refresh_paper", "--refresh-paper", "paper"),
    "--backup-db": CommandSnapshot("backup_db", "--backup-db", "maintenance"),
    "--maintenance": CommandSnapshot("maintenance", "--maintenance", "maintenance"),
    "--status": CommandSnapshot("status", "--status", "maintenance"),
    "--export-src": CommandSnapshot("export_src", "--export-src", "export"),
    "--export-src-with-artifacts": CommandSnapshot(
        "export_src_with_artifacts",
        "--export-src-with-artifacts",
        "export",
    ),
    "--event-alpha-integrated-radar-smoke": CommandSnapshot(
        "event_alpha_integrated_radar_smoke",
        "--event-alpha-integrated-radar-smoke",
        "event_alpha",
    ),
    "--event-alpha-integrated-radar-cycle": CommandSnapshot(
        "event_alpha_integrated_radar_cycle",
        "--event-alpha-integrated-radar-cycle",
        "event_alpha_integrated_radar",
    ),
    "--event-alpha-integrated-radar-doctor": CommandSnapshot(
        "event_alpha_integrated_radar_doctor",
        "--event-alpha-integrated-radar-doctor",
        "event_alpha_artifact_doctor",
    ),
    "--event-alpha-integrated-radar-fill-outcomes": CommandSnapshot(
        "event_alpha_integrated_radar_fill_outcomes",
        "--event-alpha-integrated-radar-fill-outcomes",
        "event_alpha_integrated_radar",
    ),
    "--event-alpha-integrated-radar-outcome-report": CommandSnapshot(
        "event_alpha_integrated_radar_outcome_report",
        "--event-alpha-integrated-radar-outcome-report",
        "event_alpha_integrated_radar",
    ),
    "--event-alpha-integrated-radar-calibration-report": CommandSnapshot(
        "event_alpha_integrated_radar_calibration_report",
        "--event-alpha-integrated-radar-calibration-report",
        "event_alpha_integrated_radar",
    ),
    "--event-alpha-artifact-doctor": CommandSnapshot(
        "event_alpha_artifact_doctor",
        "--event-alpha-artifact-doctor",
        "event_alpha_artifact_doctor",
    ),
    "--event-alpha-notify-preview": CommandSnapshot(
        "event_alpha_notify_preview",
        "--event-alpha-notify-preview",
        "event_alpha_notification",
    ),
    "--event-alpha-notify-preview-from-artifacts": CommandSnapshot(
        "event_alpha_notify_preview_from_artifacts",
        "--event-alpha-notify-preview-from-artifacts",
        "event_alpha_notification",
    ),
    "--event-alpha-notify-go-no-go": CommandSnapshot(
        "event_alpha_notify_go_no_go",
        "--event-alpha-notify-go-no-go",
        "event_alpha_notification",
    ),
    "--event-alpha-live-provider-readiness": CommandSnapshot(
        "event_alpha_live_provider_readiness",
        "--event-alpha-live-provider-readiness",
        "event_alpha_provider_readiness",
    ),
    "--event-alpha-live-provider-readiness-smoke": CommandSnapshot(
        "event_alpha_live_provider_readiness_smoke",
        "--event-alpha-live-provider-readiness-smoke",
        "event_alpha_provider_readiness",
    ),
    "--event-alpha-coinalyze-preflight": CommandSnapshot(
        "event_alpha_coinalyze_preflight",
        "--event-alpha-coinalyze-preflight",
        "event_alpha_coinalyze",
    ),
    "--event-alpha-coinalyze-preflight-smoke": CommandSnapshot(
        "event_alpha_coinalyze_preflight_smoke",
        "--event-alpha-coinalyze-preflight-smoke",
        "event_alpha_coinalyze",
    ),
    "--event-alpha-coinalyze-no-send-rehearsal": CommandSnapshot(
        "event_alpha_coinalyze_no_send_rehearsal",
        "--event-alpha-coinalyze-no-send-rehearsal",
        "event_alpha_coinalyze",
    ),
    "--event-alpha-bybit-announcements-preflight": CommandSnapshot(
        "event_alpha_bybit_announcements_preflight",
        "--event-alpha-bybit-announcements-preflight",
        "event_alpha_official_exchange",
    ),
    "--event-alpha-bybit-announcements-preflight-smoke": CommandSnapshot(
        "event_alpha_bybit_announcements_preflight_smoke",
        "--event-alpha-bybit-announcements-preflight-smoke",
        "event_alpha_official_exchange",
    ),
    "--event-alpha-bybit-announcements-no-send-rehearsal": CommandSnapshot(
        "event_alpha_bybit_announcements_no_send_rehearsal",
        "--event-alpha-bybit-announcements-no-send-rehearsal",
        "event_alpha_official_exchange",
    ),
    "--event-alpha-official-exchange-report": CommandSnapshot(
        "event_alpha_official_exchange_report",
        "--event-alpha-official-exchange-report",
        "event_alpha_official_exchange",
    ),
    "--event-alpha-namespace-lifecycle-report": CommandSnapshot(
        "event_alpha_namespace_lifecycle_report",
        "--event-alpha-namespace-lifecycle-report",
        "event_alpha",
    ),
}

COMMAND_ALIAS_TO_SNAPSHOT: dict[str, CommandSnapshot] = {
    "backtest": CommandSnapshot("backtest", "backtest", "backtest"),
    "crypto_rsi_scanner.backtest": CommandSnapshot(
        "backtest",
        "crypto_rsi_scanner.backtest",
        "backtest",
    ),
}


@lru_cache(maxsize=1)
def _scanner_parser_source() -> str:
    scanner_path = Path(__file__).resolve().parents[1] / "scanner.py"
    text = scanner_path.read_text(encoding="utf-8")
    try:
        cli_block = text[text.index("def cli()"):]
        start = cli_block.index("    import argparse")
        end = cli_block.index("    args = parser.parse_args()")
    except ValueError as exc:  # pragma: no cover - defensive compatibility guard
        raise RuntimeError("Unable to locate scanner.cli parser construction block") from exc
    return textwrap.dedent(cli_block[start:end])


def build_parser() -> argparse.ArgumentParser:
    """Build the current scanner parser without executing scanner dispatch.

    This intentionally mirrors the existing parser block in ``scanner.cli`` so
    the new CLI package can snapshot compatibility before command groups are
    physically moved.
    """

    from .. import event_alpha_profiles, event_feedback

    namespace = {
        "event_alpha_profiles": event_alpha_profiles,
        "event_feedback": event_feedback,
    }
    exec(_scanner_parser_source(), namespace)  # noqa: S102 - trusted local source mirror.
    parser = namespace.get("parser")
    if not isinstance(parser, argparse.ArgumentParser):  # pragma: no cover - defensive guard
        raise RuntimeError("scanner.cli parser construction did not produce an ArgumentParser")
    return parser


def classify_command(argv: Sequence[str]) -> CommandSnapshot:
    for item in argv:
        if item in COMMAND_FLAG_TO_SNAPSHOT:
            return COMMAND_FLAG_TO_SNAPSHOT[item]
        if item in COMMAND_ALIAS_TO_SNAPSHOT:
            return COMMAND_ALIAS_TO_SNAPSHOT[item]
    return CommandSnapshot("run_scan", "default", "rsi")


def command_group(argv: Sequence[str]) -> str:
    return classify_command(argv).command_group


def _dest_from_flag(flag: str) -> str:
    return flag.lstrip("-").replace("-", "_")


def dispatch_key_from_args(args: argparse.Namespace) -> str:
    for flag, snapshot in COMMAND_FLAG_TO_SNAPSHOT.items():
        dest = _dest_from_flag(flag)
        if not hasattr(args, dest):
            continue
        value = getattr(args, dest)
        if isinstance(value, bool):
            if value:
                return snapshot.dispatch_key
            continue
        if value not in (None, "", False):
            return snapshot.dispatch_key
    return "run_scan"


def parse_command_snapshot(argv: Sequence[str]) -> dict[str, str]:
    snapshot = classify_command(argv)
    return {
        "command_name": snapshot.command_name,
        "flag": snapshot.flag,
        "command_group": snapshot.command_group,
    }


__all__ = (
    "CommandSnapshot",
    "build_parser",
    "classify_command",
    "command_group",
    "dispatch_key_from_args",
    "parse_command_snapshot",
)
