"""CLI refactor inventory helpers."""

from __future__ import annotations

import ast
import re
from pathlib import Path


COMMAND_BODY_PREFIXES = ("event_alpha_", "event_", "paper_", "backtest_", "export_", "refresh_", "run_")


def scanner_bind_scanner_globals_call_sites(root: str | Path) -> int:
    repo_root = Path(root)
    total = 0
    for path in (repo_root / "crypto_rsi_scanner" / "cli").glob("*.py"):
        if path.name == "_scanner_bindings.py":
            continue
        total += len(re.findall(r"\bbind_scanner_globals\(", path.read_text(encoding="utf-8", errors="replace")))
    return total


def scanner_command_body_function_names(root: str | Path) -> tuple[str, ...]:
    path = Path(root) / "crypto_rsi_scanner" / "scanner.py"
    if not path.exists():
        return ()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=path.as_posix())
    except SyntaxError:
        return ()
    return tuple(
        sorted(
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name.startswith(COMMAND_BODY_PREFIXES)
            and not _scanner_function_is_service_wrapper(node)
        )
    )


def _scanner_function_is_service_wrapper(node: ast.FunctionDef) -> bool:
    return any(
        isinstance(child, ast.ImportFrom)
        and child.module is not None
        and child.module.endswith("cli.services")
        for child in node.body
    )
