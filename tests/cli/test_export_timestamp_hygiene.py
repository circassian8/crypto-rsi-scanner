"""Reproducible, timezone-safe source-with-artifacts timestamps."""

from __future__ import annotations

import importlib.util
import os
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _export_module():
    path = REPO_ROOT / "scripts" / "export_source_with_artifacts.py"
    spec = importlib.util.spec_from_file_location("export_timestamp_hygiene", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_timestamp_is_timezone_safe_reproducible_and_does_not_mutate_sources(
    tmp_path,
):
    export = _export_module()
    tree = tmp_path / "tree"
    tree.mkdir()
    makefile = tree / "Makefile"
    makefile.write_text("verify:\n\t@true\n", encoding="utf-8")
    package = tree / "crypto_rsi_scanner"
    package.mkdir()
    source = package / "unit.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    future = time.time() + 86_400
    os.utime(makefile, (future, future))
    os.utime(source, (future + 60, future + 60))
    source_mtimes = (makefile.stat().st_mtime_ns, source.stat().st_mtime_ns)
    output = tmp_path / "review.zip"

    assert export.main(root=tree, out=output) == 0
    first = output.read_bytes()
    assert (makefile.stat().st_mtime_ns, source.stat().st_mtime_ns) == source_mtimes
    with zipfile.ZipFile(output) as archive:
        stored = archive.getinfo("Makefile").date_time
    utc_minus_twelve = datetime(
        *stored,
        tzinfo=timezone(-timedelta(hours=12)),
    ).timestamp()
    assert utc_minus_twelve <= time.time()

    os.utime(makefile, (future + 3600, future + 3600))
    os.utime(source, (future + 7200, future + 7200))
    assert export.main(root=tree, out=output) == 0
    assert output.read_bytes() == first
