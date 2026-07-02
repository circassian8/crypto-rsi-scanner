"""Command classification helpers for the CLI consolidation layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class CommandSnapshot:
    command_name: str
    flag: str
    command_group: str


COMMAND_FLAG_TO_SNAPSHOT: dict[str, CommandSnapshot] = {
    "--event-alpha-integrated-radar-smoke": CommandSnapshot(
        "event_alpha_integrated_radar_smoke",
        "--event-alpha-integrated-radar-smoke",
        "event_alpha",
    ),
    "--event-alpha-integrated-radar-doctor": CommandSnapshot(
        "event_alpha_integrated_radar_doctor",
        "--event-alpha-integrated-radar-doctor",
        "event_alpha",
    ),
    "--event-alpha-coinalyze-preflight": CommandSnapshot(
        "event_alpha_coinalyze_preflight",
        "--event-alpha-coinalyze-preflight",
        "provider_readiness",
    ),
    "--event-alpha-coinalyze-no-send-rehearsal": CommandSnapshot(
        "event_alpha_coinalyze_no_send_rehearsal",
        "--event-alpha-coinalyze-no-send-rehearsal",
        "provider_readiness",
    ),
    "--event-alpha-namespace-lifecycle-report": CommandSnapshot(
        "event_alpha_namespace_lifecycle_report",
        "--event-alpha-namespace-lifecycle-report",
        "event_alpha",
    ),
    "--export-src": CommandSnapshot("export_src", "--export-src", "export"),
    "--dry-run": CommandSnapshot("dry_run", "--dry-run", "rsi"),
    "--report": CommandSnapshot("report", "--report", "rsi"),
    "--score": CommandSnapshot("score", "--score", "paper"),
    "--backup-db": CommandSnapshot("backup_db", "--backup-db", "maintenance"),
}


def classify_command(argv: Sequence[str]) -> CommandSnapshot:
    for item in argv:
        if item in COMMAND_FLAG_TO_SNAPSHOT:
            return COMMAND_FLAG_TO_SNAPSHOT[item]
    return CommandSnapshot("run_scan", "default", "rsi")


def parse_command_snapshot(argv: Sequence[str]) -> dict[str, str]:
    snapshot = classify_command(argv)
    return {
        "command_name": snapshot.command_name,
        "flag": snapshot.flag,
        "command_group": snapshot.command_group,
    }
