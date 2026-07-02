"""Measured local test runtime report for refactor gates."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping


REPORT_JSON = "test_runtime_report.json"
REPORT_MD = "test_runtime_report.md"


@dataclass(frozen=True)
class RuntimeCommandResult:
    name: str
    command: tuple[str, ...]
    returncode: int
    runtime_seconds: float

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "command": list(self.command),
            "returncode": self.returncode,
            "runtime_seconds": round(self.runtime_seconds, 3),
            "status": "pass" if self.returncode == 0 else "fail",
        }


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[1]


def run_runtime_commands(
    *,
    python: str,
    root: Path,
    commands: Iterable[tuple[str, tuple[str, ...], Mapping[str, str] | None]] | None = None,
) -> tuple[RuntimeCommandResult, ...]:
    specs = tuple(commands or _default_commands(python))
    rows: list[RuntimeCommandResult] = []
    for name, command, env_updates in specs:
        env = os.environ.copy()
        if env_updates:
            env.update(dict(env_updates))
        started = time.monotonic()
        proc = subprocess.run(command, cwd=root, env=env, check=False)
        elapsed = time.monotonic() - started
        rows.append(RuntimeCommandResult(name=name, command=command, returncode=proc.returncode, runtime_seconds=elapsed))
    return tuple(rows)


def build_runtime_report(results: Iterable[RuntimeCommandResult]) -> dict[str, object]:
    rows = [row.to_dict() for row in results]
    by_name = {str(row["name"]): row for row in rows}
    failed = [row for row in rows if int(row.get("returncode") or 0) != 0]
    return {
        "schema_version": "test_runtime_report_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "research_only": True,
        "no_send_rehearsal": True,
        "live_provider_calls_allowed": False,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "status": "fail" if failed else "pass",
        "standalone_runner_runtime_seconds": _runtime_for(by_name, "standalone_runner"),
        "pytest_runtime_seconds": _runtime_for(by_name, "pytest_safe"),
        "commands": rows,
    }


def format_runtime_report(report: Mapping[str, object]) -> str:
    lines = [
        "# Test Runtime Report",
        "",
        "Research-only timing report. Commands run with no provider live-call or send flags.",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- status: `{report.get('status')}`",
        f"- standalone_runner_runtime_seconds: `{report.get('standalone_runner_runtime_seconds')}`",
        f"- pytest_runtime_seconds: `{report.get('pytest_runtime_seconds')}`",
        "",
        "## Commands",
        "",
        "| name | status | seconds | command |",
        "|---|---:|---:|---|",
    ]
    for row in report.get("commands", []):
        if not isinstance(row, Mapping):
            continue
        command = " ".join(str(part) for part in row.get("command", []))
        lines.append(
            f"| `{row.get('name')}` | `{row.get('status')}` | `{row.get('runtime_seconds')}` | `{command}` |"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_runtime_report(
    *,
    root: Path | None = None,
    out_dir: Path | None = None,
    python: str = "python3",
    results: Iterable[RuntimeCommandResult] | None = None,
) -> dict[str, Path]:
    root = (root or repo_root_from_module()).resolve()
    output_dir = out_dir or root / "research"
    output_dir.mkdir(parents=True, exist_ok=True)
    measured = tuple(results) if results is not None else run_runtime_commands(python=python, root=root)
    report = build_runtime_report(measured)
    json_path = output_dir / REPORT_JSON
    md_path = output_dir / REPORT_MD
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_runtime_report(report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def _default_commands(python: str) -> tuple[tuple[str, tuple[str, ...], Mapping[str, str] | None], ...]:
    return (
        ("standalone_runner", (python, "tests/test_indicators.py"), None),
        (
            "pytest_safe",
            (python, "-m", "pytest", "tests/event_alpha", "tests/rsi", "tests/cli", "tests/test_indicators.py"),
            {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        ),
    )


def _runtime_for(rows: Mapping[str, Mapping[str, object]], name: str) -> float | None:
    row = rows.get(name)
    value = row.get("runtime_seconds") if row else None
    return float(value) if isinstance(value, (int, float)) else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write pytest/standalone runtime report artifacts.")
    parser.add_argument("--python", default="python3")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args(argv)
    paths = write_runtime_report(
        python=args.python,
        out_dir=Path(args.out_dir).expanduser() if args.out_dir else None,
    )
    print(paths["markdown"])
    print(paths["json"])
    report = json.loads(paths["json"].read_text(encoding="utf-8"))
    print(f"status={report.get('status')}")
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
