#!/usr/bin/env python3
"""Write the fixed Pro-review source archive with local research artifacts.

The archive intentionally overwrites the same filename every run:
``crypto_rsi_scanner_source_with_artifacts.zip``.
"""

from __future__ import annotations

import errno
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import stat
import time
import zipfile
from datetime import datetime


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "crypto_rsi_scanner_source_with_artifacts.zip"
_OPEN_SUPPORTS_DIR_FD = os.open in os.supports_dir_fd
_STAT_SUPPORTS_DIR_FD = os.stat in os.supports_dir_fd
_STAT_SUPPORTS_FOLLOW_SYMLINKS = os.stat in os.supports_follow_symlinks
_UTIME_SUPPORTS_FD = os.utime in os.supports_fd
_IDENTITY_CHANGED_ERRNO = getattr(errno, "ESTALE", errno.EIO)

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
_GENERIC_SECRET_ENV_NAME_RE = re.compile(
    r"(?:API_KEY|API_SECRET|AUTH_TOKEN|ACCESS_TOKEN|CLIENT_SECRET|"
    r"SECRET_ACCESS_KEY|PRIVATE_KEY|PASSWORD|SMTP_PASS|BOT_TOKEN|WEBHOOK_URL|"
    r"(?:^|_)(?:TOKEN|SECRET|PASS|WEBHOOK))$",
    re.IGNORECASE,
)

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
    ".lock",
    ".tmp",
    ".swp",
    ".zip",
)
ARTIFACT_ROOTS = {"event_fade_cache"}
MIN_ZIP_TIMESTAMP = 315532800.0  # 1980-01-01, earliest timestamp ZipInfo can represent.
DEFAULT_EXPORT_MTIME_SAFETY_MARGIN_SECONDS = 300.0
_ARTIFACT_SECRET_VALUE_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(?P<label>(?:api[_-]?(?:key|secret)|api\s+(?:key|secret)|"
    r"auth[_-]?token|api[_-]?token|access[_-]?token|client[_-]?secret|private[_-]?key|"
    r"smtp[_-]?(?:pass|password)|telegram[_-]?(?:bot[_-]?token|chat[_-]?id)|"
    r"discord[_-]?webhook(?:[_-]?url)?|provider[_-]?token)\b)\s*[\"']?\s*[:=]\s*"
    r"(?P<value>\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,}\]]+)",
    re.IGNORECASE,
)
_ARTIFACT_AUTH_BEARER_RE = re.compile(
    r"\bAuthorization[\"']?\s*[:=]\s*[\"']?\s*Bearer\s+(?P<value>[A-Za-z0-9._-]+)",
    re.IGNORECASE,
)
_ARTIFACT_AUTH_BASIC_RE = re.compile(
    r"\b(?:Proxy-)?Authorization[\"']?\s*[:=]\s*[\"']?\s*Basic\s+"
    r"(?P<value>[A-Za-z0-9+/=]{8,})",
    re.IGNORECASE,
)
_ARTIFACT_X_API_KEY_RE = re.compile(
    r"\bX-API-Key[\"']?\s*[:=]\s*[\"']?\s*(?P<value>[A-Za-z0-9._-]+)",
    re.IGNORECASE,
)
_ARTIFACT_OPENAI_KEY_RE = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b")
_ARTIFACT_PROVIDER_TOKEN_RE = re.compile(
    r"\b(?:(?:ghp|gho|ghu|github_pat)_[A-Za-z0-9_]{16,}|"
    r"(?:xoxb|xoxp|xoxa|xoxr|xoxs)-[A-Za-z0-9-]{16,}|"
    r"glpat-[A-Za-z0-9_-]{16,}|sk_live_[A-Za-z0-9]{16,})\b",
    re.IGNORECASE,
)
_ARTIFACT_AWS_ACCESS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
_ARTIFACT_GOOGLE_API_KEY_RE = re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b")
_ARTIFACT_PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
_ARTIFACT_DISCORD_WEBHOOK_RE = re.compile(
    r"https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/[0-9]+/[A-Za-z0-9._-]+",
    re.IGNORECASE,
)
_SAFE_ARTIFACT_SECRET_VALUES = frozenset(
    {
        "",
        "0",
        "false",
        "fixture",
        "configured",
        "disabled",
        "missing",
        "missing_api_key",
        "missing_config",
        "no",
        "none",
        "null",
        "n/a",
        "not available",
        "not_available",
        "not configured",
        "not_configured",
        "not-set",
        "placeholder",
        "present",
        "redacted",
        "test",
        "true",
        "unavailable",
        "unknown",
        "***",
        "<missing>",
        "<not-set>",
        "<redacted>",
        "[redacted]",
    }
)
_SAFE_ARTIFACT_SECRET_PREFIXES = (
    "dummy-",
    "example-",
    "fixture-",
    "placeholder-",
    "test-",
)
_SAFE_ARTIFACT_SECRET_PLACEHOLDER_SUFFIXES = frozenset(
    {
        "api-key",
        "api-secret",
        "api-token",
        "credential",
        "credentials",
        "dummy",
        "example",
        "fixture",
        "key",
        "not-a-secret",
        "placeholder",
        "secret",
        "test",
        "token",
        "value",
    }
)


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
        if _safe_regular_file(path, root=root) and not _skip(path, root=root):
            paths.add(path)
    return paths


def _artifact_paths(root: Path = ROOT) -> set[Path]:
    paths: set[Path] = set()
    for name in ARTIFACT_ROOTS:
        artifact_root = root / name
        if artifact_root.is_symlink() or not artifact_root.exists():
            continue
        for path in artifact_root.rglob("*"):
            if _safe_regular_file(path, root=root):
                paths.add(path)
    return paths


def _skip(path: Path, root: Path = ROOT) -> bool:
    if path.is_symlink():
        return True
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


def _safe_regular_file(path: Path, *, root: Path) -> bool:
    """Return true only for a regular file reached without an in-root symlink."""

    root_abs = Path(root).expanduser().absolute()
    path_abs = Path(path).expanduser().absolute()
    try:
        rel = path_abs.relative_to(root_abs)
    except ValueError:
        return False
    current = root_abs
    try:
        for part in rel.parts:
            current = current / part
            mode = current.lstat().st_mode
            if stat.S_ISLNK(mode):
                return False
        return bool(rel.parts) and stat.S_ISREG(mode)
    except (FileNotFoundError, OSError):
        return False


def _open_verified_regular_file(path: Path, *, root: Path) -> tuple[int, os.stat_result]:
    """Open one root-relative regular file without following any path symlink."""

    if (
        not _OPEN_SUPPORTS_DIR_FD
        or not _STAT_SUPPORTS_DIR_FD
        or not _STAT_SUPPORTS_FOLLOW_SYMLINKS
        or not hasattr(os, "O_DIRECTORY")
        or not hasattr(os, "O_NOFOLLOW")
    ):
        raise OSError(errno.ENOTSUP, "descriptor-relative no-follow export is unsupported")
    root_abs = Path(root).expanduser().absolute()
    path_abs = Path(path).expanduser().absolute()
    try:
        parts = path_abs.relative_to(root_abs).parts
    except ValueError as exc:
        raise OSError(errno.EPERM, "export input is outside the trusted root") from exc
    if not parts:
        raise OSError(errno.EISDIR, "export input is the trusted root")
    if any(part in {"", ".", ".."} for part in parts):
        raise OSError(errno.EPERM, "export input contains an unsafe path component")

    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    root_stat = os.stat(root_abs, follow_symlinks=False)
    if not stat.S_ISDIR(root_stat.st_mode):
        raise OSError(errno.ENOTDIR, "trusted export root is not a directory")
    root_fd = os.open(root_abs, directory_flags)
    try:
        opened_root_stat = os.fstat(root_fd)
        if (
            not stat.S_ISDIR(opened_root_stat.st_mode)
            or (root_stat.st_dev, root_stat.st_ino)
            != (opened_root_stat.st_dev, opened_root_stat.st_ino)
        ):
            raise OSError(_IDENTITY_CHANGED_ERRNO, "trusted export root changed during validation")
    except BaseException:
        os.close(root_fd)
        raise
    directory_fd = root_fd
    try:
        for part in parts[:-1]:
            component_stat = os.stat(
                part,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
            if not stat.S_ISDIR(component_stat.st_mode):
                raise OSError(errno.ENOTDIR, "export path component is not a directory")
            next_fd = os.open(part, directory_flags, dir_fd=directory_fd)
            try:
                opened_component_stat = os.fstat(next_fd)
                if (
                    not stat.S_ISDIR(opened_component_stat.st_mode)
                    or (component_stat.st_dev, component_stat.st_ino)
                    != (opened_component_stat.st_dev, opened_component_stat.st_ino)
                ):
                    raise OSError(
                        _IDENTITY_CHANGED_ERRNO,
                        "export path component changed during validation",
                    )
            except BaseException:
                os.close(next_fd)
                raise
            if directory_fd != root_fd:
                os.close(directory_fd)
            directory_fd = next_fd
        file_pre_stat = os.stat(
            parts[-1],
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        if not stat.S_ISREG(file_pre_stat.st_mode):
            raise OSError(errno.EINVAL, "export input is not a regular file")
        file_fd = os.open(parts[-1], file_flags, dir_fd=directory_fd)
        try:
            file_stat = os.fstat(file_fd)
            if (
                not stat.S_ISREG(file_stat.st_mode)
                or (file_pre_stat.st_dev, file_pre_stat.st_ino)
                != (file_stat.st_dev, file_stat.st_ino)
            ):
                raise OSError(_IDENTITY_CHANGED_ERRNO, "export input changed during validation")
        except BaseException:
            os.close(file_fd)
            raise
        return file_fd, file_stat
    finally:
        if directory_fd != root_fd:
            os.close(directory_fd)
        os.close(root_fd)


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


def _unsafe_archive_name(name: str) -> str | None:
    if not name or "\x00" in name:
        return "empty_or_nul_name"
    if "\\" in name:
        return "backslash_path"
    path = PurePosixPath(name)
    if path.is_absolute() or name.startswith("/"):
        return "absolute_path"
    if any(part in {"", ".", ".."} for part in name.rstrip("/").split("/")):
        return "relative_traversal"
    if path.parts and path.parts[0].endswith(":"):
        return "drive_path"
    return None


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
    configured = {**dotenv, **os.environ}
    for key, raw in configured.items():
        if key in SECRET_ENV_FIELDS or not _GENERIC_SECRET_ENV_NAME_RE.search(str(key)):
            continue
        value = str(raw or "").strip()
        if len(value) >= 8:
            found.add(("configured_secret", value.encode()))
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
        for label, value in sensitive_values:
            if value in zf.comment:
                bad.append(f"sensitive_value:{label}:archive_comment")
        seen_names: set[str] = set()
        for info in zf.infolist():
            issue = _unsafe_archive_name(info.filename)
            if issue:
                bad.append(f"unsafe_archive_name:{issue}:{info.filename}")
            if info.filename in seen_names:
                bad.append(f"duplicate_archive_name:{info.filename}")
            seen_names.add(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if mode and stat.S_ISLNK(mode):
                bad.append(f"symlink_archive_entry:{info.filename}")
            metadata = info.filename.encode("utf-8", errors="ignore") + info.comment + info.extra
            for label, value in sensitive_values:
                if value in metadata:
                    bad.append(f"sensitive_value:{label}:entry_metadata:{info.filename}")
            entry_ts = datetime(*info.date_time).timestamp()
            artifact_entry = _is_artifact_archive_entry(info.filename)
            # Zip timestamps have two-second granularity.
            if entry_ts > safe_export_timestamp + 2:
                bad.append(f"future_mtime:{info.filename}:{entry_ts:.0f}>{safe_export_timestamp:.0f}")
            data = b""
            if not info.is_dir() and (sensitive_values or artifact_entry):
                data = zf.read(info)
            if data and sensitive_values:
                for label, value in sensitive_values:
                    if value in data:
                        bad.append(f"sensitive_value:{label}:{info.filename}")
            if data and artifact_entry:
                for label in _artifact_secret_labels(data):
                    bad.append(f"artifact_secret:{label}:{info.filename}")
            if artifact_entry:
                for label in _artifact_secret_labels(metadata):
                    bad.append(f"artifact_secret:{label}:entry_metadata:{info.filename}")
        makefile = next((info for info in zf.infolist() if info.filename == "Makefile"), None)
        if makefile is not None:
            makefile_ts = datetime(*makefile.date_time).timestamp()
            if makefile_ts > safe_export_timestamp + 2:
                bad.append(f"future_makefile_mtime:{makefile_ts:.0f}>{safe_export_timestamp:.0f}")
    return bad


def _is_artifact_archive_entry(name: str) -> bool:
    return any(name == root or name.startswith(f"{root}/") for root in ARTIFACT_ROOTS)


def _artifact_secret_labels(data: bytes) -> list[str]:
    """Return redacted labels for non-placeholder secret values in artifacts."""

    text = data.decode("utf-8", errors="ignore")
    labels: set[str] = set()
    for match in _ARTIFACT_SECRET_VALUE_RE.finditer(text):
        value = _normalized_artifact_secret_value(match.group("value"))
        if not _safe_artifact_secret_value(value):
            labels.add(_normalized_artifact_secret_label(match.group("label")))
    for pattern, label in (
        (_ARTIFACT_AUTH_BEARER_RE, "authorization_bearer"),
        (_ARTIFACT_AUTH_BASIC_RE, "authorization_basic"),
        (_ARTIFACT_X_API_KEY_RE, "x_api_key"),
    ):
        for match in pattern.finditer(text):
            if not _safe_artifact_secret_value(
                _normalized_artifact_secret_value(match.group("value"))
            ):
                labels.add(label)
    if any(
        not _natural_language_sk_phrase(match.group(0))
        for match in _ARTIFACT_OPENAI_KEY_RE.finditer(text)
    ):
        labels.add("openai_key")
    if _ARTIFACT_PROVIDER_TOKEN_RE.search(text):
        labels.add("provider_token")
    if _ARTIFACT_AWS_ACCESS_KEY_RE.search(text):
        labels.add("aws_access_key")
    if _ARTIFACT_GOOGLE_API_KEY_RE.search(text):
        labels.add("google_api_key")
    if _ARTIFACT_PRIVATE_KEY_RE.search(text):
        labels.add("private_key")
    if _ARTIFACT_DISCORD_WEBHOOK_RE.search(text):
        labels.add("discord_webhook")
    return sorted(labels)


def _normalized_artifact_secret_value(value: str) -> str:
    return str(value or "").strip().strip("\"'").strip().casefold()


def _normalized_artifact_secret_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(label or "").strip().casefold()).strip("_")


def _safe_artifact_secret_value(value: str) -> bool:
    if value in _SAFE_ARTIFACT_SECRET_VALUES:
        return True
    if re.fullmatch(r"\$\{[a-z0-9_]+\}?", value):
        return True
    if value.startswith(("<redacted>", "[redacted]", r"\u003credacted\u003e", "%3credacted%3e")):
        return True
    return any(
        value.startswith(prefix)
        and value[len(prefix):] in _SAFE_ARTIFACT_SECRET_PLACEHOLDER_SUFFIXES
        for prefix in _SAFE_ARTIFACT_SECRET_PREFIXES
    )


def _natural_language_sk_phrase(token: str) -> bool:
    """Distinguish lowercase headline/URL slugs from OpenAI key shapes."""

    if not token.lower().startswith("sk-"):
        return False
    rest = token[3:]
    slug_part = rest.split("_", 1)[0]
    if (
        "_" in rest
        and slug_part.count("-") >= 3
        and slug_part == slug_part.lower()
        and all(char.isalnum() or char == "-" for char in slug_part)
    ):
        return True
    if not rest or rest != rest.lower() or "_" in rest or not any(char == "-" for char in rest):
        return False
    if not any(char.isdigit() for char in rest):
        return True
    return rest.count("-") >= 3 and all(char.isalnum() or char == "-" for char in rest)


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


def _zipinfo_for_path(
    path: Path,
    arcname: str,
    *,
    now_ts: float,
    root: Path | None = None,
) -> zipfile.ZipInfo:
    """Create a zip entry while clamping future mtimes to export time."""

    safety_root = Path(root) if root is not None else path.parent
    descriptor, file_stat = _open_verified_regular_file(path, root=safety_root)
    os.close(descriptor)
    return _zipinfo_for_stat(file_stat, arcname, now_ts=now_ts)


def _zipinfo_for_stat(
    file_stat: os.stat_result,
    arcname: str,
    *,
    now_ts: float,
) -> zipfile.ZipInfo:
    # Zip timestamps cannot represent dates before 1980. More importantly for
    # review zips, do not preserve future-dated mtimes from host/archive clock
    # skew because extracted Makefiles can make every `make` command warn.
    mtime = min(max(file_stat.st_mtime, MIN_ZIP_TIMESTAMP), now_ts)
    info = zipfile.ZipInfo(arcname, datetime.fromtimestamp(mtime).timetuple()[:6])
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (file_stat.st_mode & 0xFFFF) << 16
    return info


def _write_file_to_zip(
    zf: zipfile.ZipFile,
    path: Path,
    arcname: str,
    *,
    now_ts: float,
    root: Path | None = None,
) -> None:
    safety_root = Path(root) if root is not None else path.parent
    descriptor, file_stat = _open_verified_regular_file(path, root=safety_root)
    info = _zipinfo_for_stat(file_stat, arcname, now_ts=now_ts)
    with os.fdopen(descriptor, "rb") as src, zf.open(info, "w") as dst:
        dst.write(src.read())


def _normalize_input_timestamps(
    paths: list[Path],
    *,
    safe_export_timestamp: float,
    root: Path | None = None,
) -> int:
    """Clamp source mtimes before archiving so later fallback exports stay safe."""

    changed = 0
    if not _UTIME_SUPPORTS_FD:
        raise OSError(errno.ENOTSUP, "descriptor timestamp updates are unsupported")
    for path in paths:
        safety_root = Path(root) if root is not None else path.parent
        try:
            descriptor, file_stat = _open_verified_regular_file(path, root=safety_root)
        except OSError:
            continue
        try:
            if file_stat.st_mtime <= safe_export_timestamp + 2:
                continue
            os.utime(
                descriptor,
                (min(file_stat.st_atime, safe_export_timestamp), safe_export_timestamp),
            )
            changed += 1
        finally:
            os.close(descriptor)
    return changed


def main(root: Path = ROOT, out: Path = OUT) -> int:
    paths = _tracked_paths(root) | _artifact_paths(root)
    entries = [
        path
        for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix())
        if _safe_regular_file(path, root=root) and not _skip(path, root=root)
    ]

    now_ts = _safe_export_timestamp()
    try:
        normalized_mtimes = _normalize_input_timestamps(
            entries,
            safe_export_timestamp=now_ts,
            root=root,
        )
    except OSError as exc:
        print(f"export_failed_closed={type(exc).__name__}")
        return 1
    candidate = out.with_name(f"{out.name}.tmp")
    candidate.unlink(missing_ok=True)
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(candidate, flags, 0o600)
        with os.fdopen(descriptor, "w+b") as candidate_file:
            with zipfile.ZipFile(
                candidate_file,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            ) as zf:
                for path in entries:
                    _write_file_to_zip(
                        zf,
                        path,
                        path.relative_to(root).as_posix(),
                        now_ts=now_ts,
                        root=root,
                    )
    except (OSError, ValueError) as exc:
        print(f"export_failed_closed={type(exc).__name__}")
        candidate.unlink(missing_ok=True)
        return 1

    try:
        with zipfile.ZipFile(candidate) as zf:
            names = zf.namelist()
        bad = _validate_archive_entries(
            candidate,
            safe_export_timestamp=now_ts,
            sensitive_values=_configured_sensitive_values(root),
        )
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        print(f"export_failed_closed={type(exc).__name__}")
        candidate.unlink(missing_ok=True)
        return 1
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
    try:
        candidate.replace(out)
    except OSError as exc:
        print(f"export_failed_closed={type(exc).__name__}")
        candidate.unlink(missing_ok=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
