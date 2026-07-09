#!/usr/bin/env python3
"""Write the fixed Pro-review source archive with local research artifacts.

The archive intentionally overwrites the same filename every run:
``crypto_rsi_scanner_source_with_artifacts.zip``.
"""

from __future__ import annotations

import subprocess
import time
import zipfile
from datetime import datetime
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "crypto_rsi_scanner_source_with_artifacts.zip"

SECRET_ENV_FIELDS = {
    "TELEGRAM_BOT_TOKEN": "telegram_bot_token",
    "COINGECKO_API_KEY": "coingecko_api_key",
    "OPENAI_API_KEY": "openai_api_key",
    "DISCORD_WEBHOOK_URL": "discord_webhook",
    "SMTP_PASS": "smtp_password",
    "RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_KEY": "binance_api_key",
    "RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_API_SECRET": "binance_api_secret",
    "RSI_EVENT_DISCOVERY_CRYPTOPANIC_API_TOKEN": "cryptopanic_token",
    "RSI_EVENT_DISCOVERY_CRYPTOPANIC_AUTH_TOKEN": "cryptopanic_token",
    "CRYPTOPANIC_AUTH_TOKEN": "cryptopanic_token",
    "CRYPTOPANIC_API_KEY": "cryptopanic_token",
    "CRYPTOPANIC_TOKEN": "cryptopanic_token",
    "RSI_EVENT_DISCOVERY_COINALYZE_API_KEY": "coinalyze_api_key",
}
IDENTIFIER_ENV_FIELDS = {
    "TELEGRAM_CHAT_ID": "telegram_chat_id",
    "SMTP_USER": "email_account",
    "EMAIL_TO": "email_recipient",
}

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    ".cache",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "node_modules",
    "backups",
    "backtest_cache",
}
EXCLUDE_FILE_NAMES = {
    ".env",
    ".DS_Store",
    ".claude/settings.local.json",
}
EXCLUDE_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".db",
    ".db-wal",
    ".db-shm",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".tmp",
    ".swp",
    ".zip",
)
ARTIFACT_ROOTS = {"event_fade_cache"}
MIN_ZIP_TIMESTAMP = 315532800.0  # 1980-01-01, earliest timestamp ZipInfo can represent.
DEFAULT_EXPORT_MTIME_SAFETY_MARGIN_SECONDS = 300.0


def _tracked_paths(root: Path = ROOT) -> set[Path]:
    try:
        output = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return _walk_source_paths(root)
    return {root / line for line in output.splitlines() if line.strip()}


def _walk_source_paths(root: Path = ROOT) -> set[Path]:
    paths: set[Path] = set()
    for path in root.rglob("*"):
        if path.is_file() and not _skip(path, root=root):
            paths.add(path)
    return paths


def _artifact_paths(root: Path = ROOT) -> set[Path]:
    paths: set[Path] = set()
    for name in ARTIFACT_ROOTS:
        artifact_root = root / name
        if not artifact_root.exists():
            continue
        for path in artifact_root.rglob("*"):
            if path.is_file():
                paths.add(path)
    return paths


def _skip(path: Path, root: Path = ROOT) -> bool:
    rel = path.relative_to(root)
    parts = rel.parts
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    rel_text = rel.as_posix()
    if rel_text in EXCLUDE_FILE_NAMES or path.name in EXCLUDE_FILE_NAMES:
        return True
    if path.name.startswith(".env"):
        return True
    if path.suffix in EXCLUDE_SUFFIXES or any(path.name.endswith(suffix) for suffix in EXCLUDE_SUFFIXES):
        return True
    return False


def _validate(names: list[str]) -> list[str]:
    bad: list[str] = []
    for name in names:
        lower = name.lower()
        if (
            lower == ".env"
            or lower.endswith("/.env")
            or "/.env" in lower
            or lower.startswith(".git/")
            or "/.git/" in lower
            or lower.startswith(".venv/")
            or "/.venv/" in lower
            or "__pycache__/" in lower
            or ".pytest_cache/" in lower
            or ".cache/" in lower
            or lower.startswith("backtest_cache/")
            or "/backtest_cache/" in lower
            or lower.endswith((".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3", ".log", ".zip", ".pyc"))
        ):
            bad.append(name)
    return bad


def _dotenv_values(path: Path) -> dict[str, str]:
    """Read the simple KEY=VALUE subset used by this project's local .env."""

    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _configured_sensitive_values(root: Path) -> tuple[tuple[str, bytes], ...]:
    """Return exact configured secrets/identifiers without exposing them."""

    dotenv = _dotenv_values(root / ".env")
    found: set[tuple[str, bytes]] = set()
    for key, label in SECRET_ENV_FIELDS.items():
        for raw in (dotenv.get(key, ""), os.environ.get(key, "")):
            value = raw.strip()
            if len(value) >= 8:
                found.add((label, value.encode()))
    for key, label in IDENTIFIER_ENV_FIELDS.items():
        for raw in (dotenv.get(key, ""), os.environ.get(key, "")):
            for value in (part.strip() for part in raw.split(",")):
                if len(value) >= 5:
                    found.add((label, value.encode()))
    return tuple(sorted(found, key=lambda item: (item[0], item[1])))


def _validate_archive_entries(
    zip_path: Path,
    *,
    safe_export_timestamp: float,
    sensitive_values: tuple[tuple[str, bytes], ...] = (),
) -> list[str]:
    bad = []
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        bad.extend(_validate(names))
        for info in zf.infolist():
            entry_ts = datetime(*info.date_time).timestamp()
            # Zip timestamps have two-second granularity.
            if entry_ts > safe_export_timestamp + 2:
                bad.append(f"future_mtime:{info.filename}:{entry_ts:.0f}>{safe_export_timestamp:.0f}")
            if not info.is_dir() and sensitive_values:
                data = zf.read(info)
                for label, value in sensitive_values:
                    if value in data:
                        bad.append(f"sensitive_value:{label}:{info.filename}")
        makefile = next((info for info in zf.infolist() if info.filename == "Makefile"), None)
        if makefile is not None:
            makefile_ts = datetime(*makefile.date_time).timestamp()
            if makefile_ts > safe_export_timestamp + 2:
                bad.append(f"future_makefile_mtime:{makefile_ts:.0f}>{safe_export_timestamp:.0f}")
    return bad


def _safe_export_timestamp(*, now_ts: float | None = None) -> float:
    """Return the latest mtime allowed in the review archive.

    ``SOURCE_DATE_EPOCH`` is honored for reproducible exports, but never beyond
    the conservative wall-clock-safe timestamp. Without it, clamp all archive
    entries to a slightly old timestamp so review machines whose clocks lag the
    export host do not see future-dated files and emit Make clock skew warnings
    immediately after unzip.
    """

    current = time.time() if now_ts is None else float(now_ts)
    wall_clock_safe = max(current - DEFAULT_EXPORT_MTIME_SAFETY_MARGIN_SECONDS, MIN_ZIP_TIMESTAMP)
    raw_epoch = os.getenv("SOURCE_DATE_EPOCH", "").strip()
    if raw_epoch:
        try:
            return min(max(float(raw_epoch), MIN_ZIP_TIMESTAMP), wall_clock_safe)
        except ValueError:
            pass
    return wall_clock_safe


def _zipinfo_for_path(path: Path, arcname: str, *, now_ts: float) -> zipfile.ZipInfo:
    """Create a zip entry while clamping future mtimes to export time."""

    stat = path.stat()
    # Zip timestamps cannot represent dates before 1980. More importantly for
    # review zips, do not preserve future-dated mtimes from host/archive clock
    # skew because extracted Makefiles can make every `make` command warn.
    mtime = min(max(stat.st_mtime, MIN_ZIP_TIMESTAMP), now_ts)
    info = zipfile.ZipInfo(arcname, datetime.fromtimestamp(mtime).timetuple()[:6])
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (stat.st_mode & 0xFFFF) << 16
    return info


def _write_file_to_zip(zf: zipfile.ZipFile, path: Path, arcname: str, *, now_ts: float) -> None:
    info = _zipinfo_for_path(path, arcname, now_ts=now_ts)
    with path.open("rb") as src, zf.open(info, "w") as dst:
        dst.write(src.read())


def _normalize_input_timestamps(paths: list[Path], *, safe_export_timestamp: float) -> int:
    """Clamp source mtimes before archiving so later fallback exports stay safe."""

    changed = 0
    for path in paths:
        try:
            stat = path.stat()
        except OSError:
            continue
        if stat.st_mtime <= safe_export_timestamp + 2:
            continue
        os.utime(path, (min(stat.st_atime, safe_export_timestamp), safe_export_timestamp))
        changed += 1
    return changed


def main(root: Path = ROOT, out: Path = OUT) -> int:
    paths = _tracked_paths(root) | _artifact_paths(root)
    entries = [
        path
        for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix())
        if path.exists() and path.is_file() and not _skip(path, root=root)
    ]

    now_ts = _safe_export_timestamp()
    normalized_mtimes = _normalize_input_timestamps(entries, safe_export_timestamp=now_ts)
    candidate = out.with_name(f"{out.name}.tmp")
    candidate.unlink(missing_ok=True)
    with zipfile.ZipFile(candidate, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in entries:
            _write_file_to_zip(zf, path, path.relative_to(root).as_posix(), now_ts=now_ts)

    with zipfile.ZipFile(candidate) as zf:
        names = zf.namelist()
    bad = _validate_archive_entries(
        candidate,
        safe_export_timestamp=now_ts,
        sensitive_values=_configured_sensitive_values(root),
    )
    artifact_entries = [name for name in names if name.startswith("event_fade_cache/")]
    research_cards = [
        name
        for name in artifact_entries
        if "/research_cards/" in name and name.endswith(".md") and not name.endswith("/index.md")
    ]

    print(out)
    print(f"size_bytes={candidate.stat().st_size}")
    print(f"entries={len(names)}")
    print(f"artifact_entries={len(artifact_entries)}")
    print(f"research_card_files={len(research_cards)}")
    print(f"normalized_mtimes={normalized_mtimes}")
    print(f"bad_entries={len(bad)}")
    if bad:
        print("\n".join(bad[:50]))
        candidate.unlink(missing_ok=True)
        return 1
    candidate.replace(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
