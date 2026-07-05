"""Every relative import in the package must resolve to a real module.

Regression guard for the 2026-07-03 refactor outage: moving
``cli/services/scanner_parts/rsi_scan.py`` one directory deeper left nine
function-local ``from ...X import`` statements pointing at
``crypto_rsi_scanner.cli.X`` instead of the package root, which broke
``--status``/``--backup-db``/``--maintenance`` (and with them the nightly
backup LaunchAgent) while ``make verify`` stayed green, because function-local
imports only fail when the command is actually dispatched.

This test resolves every ``ImportFrom`` with ``level > 0`` statically, so a
wrong-depth relative import anywhere in the package fails the suite even if no
test executes the surrounding function. Intentional optional imports (guarded
by try/except ImportError) can be exempted via ``_ALLOWED_UNRESOLVED``.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGE_DIR = REPO_ROOT / "crypto_rsi_scanner"

# "path/to/file.py:lineno" entries for intentional optional relative imports.
_ALLOWED_UNRESOLVED: frozenset[str] = frozenset()


def _relative_import_targets() -> list[tuple[str, str]]:
    """Return (location, absolute_module_name) for every relative import."""
    targets: list[tuple[str, str]] = []
    for path in sorted(PACKAGE_DIR.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT)
        # The package containing this module (same for foo/bar.py and
        # foo/__init__.py: relative level 1 resolves against foo).
        package_parts = list(rel.parts[:-1])
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:  # pragma: no cover - compileall covers this
            raise AssertionError(f"{rel} does not parse: {exc}") from exc
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level == 0:
                continue
            location = f"{rel}:{node.lineno}"
            if node.level > len(package_parts):
                targets.append((location, f"<level {node.level} escapes package root>"))
                continue
            base = package_parts[: len(package_parts) - (node.level - 1)]
            full = ".".join(base + ([node.module] if node.module else []))
            targets.append((location, full))
    return targets


def test_all_relative_imports_resolve():
    unresolved: list[str] = []
    for location, module_name in _relative_import_targets():
        if location in _ALLOWED_UNRESOLVED:
            continue
        if module_name.startswith("<"):
            unresolved.append(f"{location} -> {module_name}")
            continue
        try:
            spec = importlib.util.find_spec(module_name)
        except (ImportError, ValueError):
            spec = None
        if spec is None:
            unresolved.append(f"{location} -> {module_name}")
    assert not unresolved, (
        "Relative imports that do not resolve (wrong dot depth after a module "
        "move?):\n  " + "\n  ".join(unresolved)
    )


def test_ops_command_imports_resolve():
    # Anchor the specific modules behind --status/--backup-db/--maintenance.
    for module_name in (
        "crypto_rsi_scanner.status_report",
        "crypto_rsi_scanner.backups",
        "crypto_rsi_scanner.ops",
    ):
        assert importlib.util.find_spec(module_name) is not None, module_name


if __name__ == "__main__":  # standalone-compatible like the other suites
    test_all_relative_imports_resolve()
    test_ops_command_imports_resolve()
    print("ok")
