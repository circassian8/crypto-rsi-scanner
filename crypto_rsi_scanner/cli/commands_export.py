"""Export CLI command handlers."""

from __future__ import annotations

import subprocess
from pathlib import Path

EXPORT_COMMAND_GROUP = "export"


def handle(args) -> bool:
    if getattr(args, "export_src", False):
        root = Path(__file__).resolve().parents[2]
        out = root / "crypto-rsi-scanner-source.zip"
        subprocess.check_call(["git", "archive", "--format=zip", "-o", str(out), "HEAD"], cwd=root)
        print(out)
        return True
    if getattr(args, "export_src_with_artifacts", False):
        from scripts import export_source_with_artifacts

        raise SystemExit(export_source_with_artifacts.main())
    return False
