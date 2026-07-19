"""Source-with-artifacts export behavior isolated from generic Make tests."""

from __future__ import annotations

from tests.rsi import _api_helpers as _api

globals().update(
    {name: getattr(_api, name) for name in dir(_api) if not name.startswith("__")}
)


def test_export_source_with_artifacts_fallback_and_archive_validation():
    import importlib.util
    import subprocess
    import time
    import zipfile
    from datetime import datetime

    root = REPO_ROOT
    spec = importlib.util.spec_from_file_location(
        "export_source_with_artifacts",
        root / "scripts" / "export_source_with_artifacts.py",
    )
    assert spec and spec.loader
    export_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(export_module)
    with TemporaryDirectory() as tmp:
        tree = Path(tmp) / "tree"
        tree.mkdir()
        makefile = tree / "Makefile"
        makefile.write_text("verify:\n\t@true\n", encoding="utf-8")
        (tree / "crypto_rsi_scanner").mkdir()
        (tree / "crypto_rsi_scanner" / "unit.py").write_text(
            "VALUE = 1\n", encoding="utf-8"
        )
        (tree / ".env").write_text("SECRET=1\n", encoding="utf-8")
        (tree / "local.db").write_text("db\n", encoding="utf-8")
        (tree / "backtest_cache").mkdir()
        (tree / "backtest_cache" / "cached.json").write_text(
            "{}\n", encoding="utf-8"
        )
        outside = Path(tmp) / "outside-private-material.txt"
        outside.write_text("unconfigured private material\n", encoding="utf-8")
        outside_future_ts = time.time() + 172800
        os.utime(outside, (outside_future_ts, outside_future_ts))
        outside_mtime_ns = outside.stat().st_mtime_ns
        artifact_dir = tree / "backtest_cache" / "unit"
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "linked-evidence.txt").symlink_to(outside)
        future_ts = time.time() + 86400
        os.utime(makefile, (future_ts, future_ts))
        out = Path(tmp) / "out.zip"
        assert export_module.main(root=tree, out=out) == 0
        with zipfile.ZipFile(out) as zf:
            names = set(zf.namelist())
            makefile_ts = datetime(*zf.getinfo("Makefile").date_time).timestamp()
        assert "Makefile" in names
        assert "crypto_rsi_scanner/unit.py" in names
        assert ".env" not in names
        assert "local.db" not in names
        assert "backtest_cache/cached.json" not in names
        assert "backtest_cache/unit/linked-evidence.txt" not in names
        assert outside.stat().st_mtime_ns == outside_mtime_ns
        assert outside.read_text(encoding="utf-8") == "unconfigured private material\n"
        assert makefile_ts <= time.time()
        safe_archive = out.read_bytes()

        configured_secret = "123456789:configured-secret"
        (tree / ".env").write_text(
            f"TELEGRAM_BOT_TOKEN={configured_secret}\n",
            encoding="utf-8",
        )
        (tree / "crypto_rsi_scanner" / "unit.py").write_text(
            f"VALUE = {configured_secret!r}\n",
            encoding="utf-8",
        )
        assert export_module.main(root=tree, out=out) == 1
        assert out.read_bytes() == safe_archive
        assert not out.with_name(f"{out.name}.tmp").exists()

        extract_dir = Path(tmp) / "extract"
        with zipfile.ZipFile(out) as zf:
            zf.extractall(extract_dir)
        make_dry = subprocess.run(
            ["make", "-n", "verify"],
            cwd=extract_dir,
            text=True,
            capture_output=True,
            check=True,
        )
        make_output = make_dry.stdout + make_dry.stderr
        assert "Clock skew detected" not in make_output
        assert "modification time" not in make_output

        future_zip = Path(tmp) / "future.zip"
        now_ts = time.time()
        future = datetime.fromtimestamp(now_ts + 86400).timetuple()[:6]
        with zipfile.ZipFile(future_zip, "w") as zf:
            info = zipfile.ZipInfo("Makefile", future)
            zf.writestr(info, "all:\n\t@true\n")
        bad = export_module._validate_archive_entries(
            future_zip, safe_export_timestamp=now_ts
        )
        assert any(item.startswith("future_mtime:Makefile") for item in bad)
