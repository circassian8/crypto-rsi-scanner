"""Tombstone tests for deleted flat Event Alpha import paths."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


def _deleted_old_modules() -> tuple[str, ...]:
    manifest = json.loads(Path("research/EVENT_ALPHA_DELETED_SHIMS.json").read_text(encoding="utf-8"))
    rows = manifest.get("deleted_shims")
    assert isinstance(rows, list)
    modules = tuple(
        str(row.get("old_path"))
        for row in rows
        if isinstance(row, dict) and str(row.get("old_path") or "").startswith("crypto_rsi_scanner.")
    )
    assert modules
    return modules


def test_deleted_old_event_alpha_import_paths_fail():
    for old_path in _deleted_old_modules():
        sys.modules.pop(old_path, None)
        try:
            importlib.import_module(old_path)
        except ModuleNotFoundError as exc:
            assert exc.name == old_path
        else:  # pragma: no cover - failure path
            raise AssertionError(f"deleted shim unexpectedly imported: {old_path}")


def test_no_public_flat_event_alpha_compatibility_shims_remain():
    from crypto_rsi_scanner.event_alpha import shims

    assert shims.PUBLIC_COMPATIBILITY_SHIMS == set()
    assert shims.registry_entries() == ()
