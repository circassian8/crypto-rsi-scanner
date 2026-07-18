from __future__ import annotations

from pathlib import Path

from crypto_rsi_scanner.project_health import terminology_check


def test_architecture_terminology_scan_file_order_is_deterministic(
    tmp_path: Path,
) -> None:
    files = (
        "crypto_rsi_scanner/z.py",
        "crypto_rsi_scanner/a.py",
        "tests/z.py",
        "research/ARCHITECTURE_Z.md",
        "ROADMAP.md",
        "DEVLOG.md",
        "AGENTS.md",
    )
    for relative in files:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("legacy compatibility\n", encoding="utf-8")

    observed = [
        path.relative_to(tmp_path).as_posix()
        for path in terminology_check._iter_scan_files(tmp_path)
    ]

    assert observed == [
        "crypto_rsi_scanner/a.py",
        "crypto_rsi_scanner/z.py",
        "tests/z.py",
        "research/ARCHITECTURE_Z.md",
        "AGENTS.md",
        "DEVLOG.md",
        "ROADMAP.md",
    ]
