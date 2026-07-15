"""Pytest plugin that reports cumulative duration by test file.

Load explicitly with ``-p crypto_rsi_scanner.pytest_file_timing``. The plugin
adds negligible bookkeeping to the existing suite and does not rerun tests.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPORT_SCHEMA_VERSION = "pytest_file_timing_report_v1"


@dataclass(frozen=True)
class TimingSample:
    path: str
    nodeid: str
    phase: str
    duration_seconds: float


_SAMPLES: list[TimingSample] = []


def pytest_addoption(parser: Any) -> None:
    group = parser.getgroup("file timing")
    group.addoption(
        "--slowest-test-files",
        action="store",
        type=int,
        default=20,
        help="number of cumulative per-file durations to print",
    )
    group.addoption(
        "--test-file-timing-json",
        action="store",
        default=None,
        help="optional JSON report path",
    )
    group.addoption(
        "--test-file-timing-md",
        action="store",
        default=None,
        help="optional Markdown report path",
    )


def pytest_configure(config: Any) -> None:
    _SAMPLES.clear()


def pytest_runtest_logreport(report: Any) -> None:
    phase = str(getattr(report, "when", ""))
    if phase not in {"setup", "call", "teardown"}:
        return
    nodeid = str(getattr(report, "nodeid", ""))
    path = nodeid.split("::", 1)[0]
    if not path:
        return
    _SAMPLES.append(
        TimingSample(
            path=path,
            nodeid=nodeid,
            phase=phase,
            duration_seconds=max(0.0, float(getattr(report, "duration", 0.0) or 0.0)),
        )
    )


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    config = session.config
    report = build_file_timing_report(_SAMPLES, exitstatus=exitstatus)
    json_path = config.getoption("--test-file-timing-json")
    markdown_path = config.getoption("--test-file-timing-md")
    if json_path or markdown_path:
        write_file_timing_report(
            report,
            json_path=Path(json_path).expanduser() if json_path else None,
            markdown_path=Path(markdown_path).expanduser() if markdown_path else None,
        )


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: Any) -> None:
    limit = max(0, int(config.getoption("--slowest-test-files") or 0))
    if limit == 0:
        return
    rows = build_file_timing_report(_SAMPLES, exitstatus=exitstatus)["files"][:limit]
    terminalreporter.section(f"slowest {limit} test files (cumulative phases)")
    for row in rows:
        terminalreporter.write_line(
            f"{float(row['total_seconds']):8.3f}s  {int(row['test_count']):5d} tests  {row['path']}"
        )


def build_file_timing_report(
    samples: Iterable[TimingSample],
    *,
    exitstatus: int = 0,
) -> dict[str, Any]:
    phase_totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    nodeids: dict[str, set[str]] = defaultdict(set)
    for sample in samples:
        phase_totals[sample.path][sample.phase] += max(0.0, float(sample.duration_seconds))
        nodeids[sample.path].add(sample.nodeid)
    rows: list[dict[str, Any]] = []
    for path, phases in phase_totals.items():
        total = sum(phases.values())
        rows.append(
            {
                "path": path,
                "test_count": len(nodeids[path]),
                "total_seconds": round(total, 6),
                "setup_seconds": round(phases.get("setup", 0.0), 6),
                "call_seconds": round(phases.get("call", 0.0), 6),
                "teardown_seconds": round(phases.get("teardown", 0.0), 6),
            }
        )
    rows.sort(key=lambda row: (-float(row["total_seconds"]), str(row["path"])))
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "row_type": "pytest_file_timing_report",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "pass" if int(exitstatus) == 0 else "fail",
        "pytest_exit_status": int(exitstatus),
        "measurement": "sum_of_setup_call_teardown_durations_by_test_file",
        "reran_tests": False,
        "live_provider_calls_allowed": False,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "file_count": len(rows),
        "test_count": sum(int(row["test_count"]) for row in rows),
        "files": rows,
    }


def format_file_timing_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Pytest File Timing Report",
        "",
        "Cumulative pytest setup/call/teardown duration by file. This report reuses the existing suite run.",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- status: `{report.get('status')}`",
        f"- file_count: `{report.get('file_count')}`",
        f"- test_count: `{report.get('test_count')}`",
        "",
        "| file | tests | total seconds | call seconds | setup seconds | teardown seconds |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in report.get("files", []):
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"| `{row.get('path')}` | {row.get('test_count')} | {row.get('total_seconds')} | "
            f"{row.get('call_seconds')} | {row.get('setup_seconds')} | {row.get('teardown_seconds')} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_file_timing_report(
    report: Mapping[str, Any],
    *,
    json_path: Path | None,
    markdown_path: Path | None,
) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(dict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        paths["json"] = json_path
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(format_file_timing_markdown(report), encoding="utf-8")
        paths["markdown"] = markdown_path
    return paths


__all__ = [
    "TimingSample",
    "build_file_timing_report",
    "format_file_timing_markdown",
    "write_file_timing_report",
]
