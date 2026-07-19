#!/usr/bin/env python3
"""Write the fixed Pro-review source archive with local research artifacts.

The archive intentionally overwrites the same filename every run:
``crypto_rsi_scanner_source_with_artifacts.zip``.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import stat
import sys
import time
import zipfile
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "crypto_rsi_scanner_source_with_artifacts.zip"
EMPIRICAL_POLICY_RELATIVE_PATH = Path(
    "research/DECISION_RADAR_EMPIRICAL_ARTIFACT_POLICY.json"
)
EMPIRICAL_LAB_RELATIVE_PATH = Path("event_fade_cache/decision_radar_research_lab")
EMPIRICAL_FEEDBACK_RELATIVE_PATH = (
    EMPIRICAL_LAB_RELATIVE_PATH / "empirical_review_feedback.jsonl"
)
EMPIRICAL_STANDARD_MANIFEST_ARCHIVE_PATH = (
    EMPIRICAL_LAB_RELATIVE_PATH / "EMPIRICAL_ARTIFACT_EXPORT_MANIFEST.json"
)
EMPIRICAL_HISTORY_OUTPUT_FILENAME = (
    "crypto_rsi_scanner_empirical_artifact_history.zip"
)
EMPIRICAL_HISTORY_MANIFEST_ARCHIVE_PATH = (
    "EMPIRICAL_ARTIFACT_HISTORY_MANIFEST.json"
)
EMPIRICAL_HISTORY_CHECKSUMS_ARCHIVE_PATH = (
    "EMPIRICAL_ARTIFACT_HISTORY_SHA256SUMS.txt"
)
PROJECT_ARTIFACT_POLICY_RELATIVE_PATH = Path(
    "research/DECISION_RADAR_PROJECT_ARTIFACT_POLICY.json"
)
PROJECT_ARTIFACT_ROOT_RELATIVE_PATH = Path("event_fade_cache")
PROJECT_STANDARD_MANIFEST_ARCHIVE_PATH = (
    "event_fade_cache/PROJECT_ARTIFACT_EXPORT_MANIFEST.json"
)
PROJECT_HISTORY_OUTPUT_FILENAME = "crypto_rsi_scanner_artifact_history.zip"
PROJECT_HISTORY_MANIFEST_ARCHIVE_PATH = "PROJECT_ARTIFACT_HISTORY_MANIFEST.json"
PROJECT_HISTORY_CHECKSUMS_ARCHIVE_PATH = "PROJECT_ARTIFACT_HISTORY_SHA256SUMS.txt"
EMPIRICAL_PROTOCOL_V2_DOCUMENT_PATH = Path(
    "research/DECISION_RADAR_EMPIRICAL_PROTOCOL_V2_READINESS.md"
)
EMPIRICAL_PROTOCOL_V2_IMPLEMENTATION_PATH = Path(
    "crypto_rsi_scanner/event_alpha/operations/empirical_validation_protocol_v2.py"
)
EMPIRICAL_HARDENING_SUPPLEMENT_PATH = Path(
    "research/DECISION_RADAR_EMPIRICAL_HARDENING_SUPPLEMENT.json"
)
EMPIRICAL_REPORT_FILENAMES = (
    "DECISION_RADAR_EMPIRICAL_VALIDATION_REPORT.md",
    "DECISION_RADAR_EMPIRICAL_VALIDATION_REPORT.json",
    "DECISION_RADAR_WALK_FORWARD_REPORT.md",
    "DECISION_RADAR_WALK_FORWARD_REPORT.json",
    "DECISION_RADAR_POLICY_SIMULATION_REPORT.md",
    "DECISION_RADAR_POLICY_SIMULATION_REPORT.json",
    "DECISION_RADAR_RESEARCH_LIMITATIONS.md",
)
EMPIRICAL_MAX_REPORT_BYTES = 4 * 1024 * 1024
EMPIRICAL_MAX_SUPPLEMENT_BYTES = 4 * 1024 * 1024
EMPIRICAL_PROTOCOL_ARTIFACT_PATHS = frozenset(
    {
        Path("research/DECISION_RADAR_EMPIRICAL_VALIDATION_PROTOCOL.json"),
        Path("research/DECISION_RADAR_EMPIRICAL_VALIDATION_PROTOCOL.md"),
        EMPIRICAL_PROTOCOL_V2_DOCUMENT_PATH,
        EMPIRICAL_PROTOCOL_V2_IMPLEMENTATION_PATH,
    }
)
EMPIRICAL_REPORT_PATHS = frozenset(
    Path("research") / name for name in EMPIRICAL_REPORT_FILENAMES
)
EMPIRICAL_LIMITS = {
    "max_canonical_lab_file_count": 96,
    "max_canonical_lab_total_bytes": 220_200_960,
    "max_feedback_event_bytes": 8_192,
    "max_feedback_event_count": 4_096,
    "max_feedback_total_bytes": 4_194_304,
    "max_history_file_count": 1_024,
    "max_history_total_bytes": 1_610_612_736,
    "max_lab_file_count": 1_152,
    "max_lab_total_bytes": 1_879_048_192,
    "max_single_empirical_file_bytes": 67_108_864,
    "max_standard_empirical_file_count": 128,
    "max_standard_empirical_total_bytes": 268_435_456,
}
PROJECT_ARTIFACT_LIMITS = {
    "max_artifact_file_count": 4_096,
    "max_artifact_total_bytes": 1_610_612_736,
    "max_history_file_count": 4_096,
    "max_history_total_bytes": 1_610_612_736,
    "max_single_artifact_file_bytes": 134_217_728,
    "max_standard_artifact_file_count": 512,
    "max_standard_artifact_total_bytes": 402_653_184,
    "max_review_timing_source_namespaces": 64,
}
PROJECT_CANONICAL_ROOT_FILES = (
    "event_alpha_namespace_registry.json",
    "event_market_no_send_attempts.jsonl",
    "event_market_no_send_latest_attempt.json",
    "event_market_no_send_pilot_audit.json",
    "event_market_no_send_pilot_audit.md",
    "event_provider_health.json",
    "event_radar_daily_operations_current_status.json",
    "event_radar_daily_operations_cycles.jsonl",
    "event_radar_daily_operations_state.json",
    "event_decision_radar_outcome_price_recovery_latest.json",
    "radar_bybit_execution_quality_latest.json",
    "radar_bybit_derivatives_context_latest.json",
    "radar_bybit_intraday_latest.json",
    "radar_current_namespace.json",
)
PROJECT_CANONICAL_SHARED_DIRECTORIES = (
    "event_source_independence_contracts",
    "official_macro_calendar",
    "radar_market_history_cache",
)
PROJECT_DYNAMIC_NAMESPACE_SELECTORS = (
    {
        "kind": "dashboard_pointer_namespace",
        "path": "radar_current_namespace.json",
    },
    {
        "kind": "latest_live_no_send_attempt_namespace",
        "path": "event_market_no_send_latest_attempt.json",
    },
    {
        "kind": "latest_bybit_execution_quality_namespace",
        "path": "radar_bybit_execution_quality_latest.json",
    },
    {
        "kind": "latest_bybit_intraday_namespace",
        "path": "radar_bybit_intraday_latest.json",
    },
    {
        "kind": "latest_bybit_derivatives_namespace",
        "path": "radar_bybit_derivatives_context_latest.json",
    },
    {
        "kind": "latest_outcome_price_recovery_namespace",
        "path": "event_decision_radar_outcome_price_recovery_latest.json",
    },
    {
        "kind": "review_timing_source_namespaces",
        "path": (
            "radar_market_history_cache/"
            "event_decision_radar_review_timing_events.jsonl"
        ),
    },
)
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
DEFAULT_EXPORT_MTIME_SAFETY_MARGIN_SECONDS = 36 * 60 * 60.0
DEFAULT_REPRODUCIBLE_EXPORT_TIMESTAMP = MIN_ZIP_TIMESTAMP
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
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in ARTIFACT_ROOTS:
            continue
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


def _canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _verified_file_bytes(path: Path, *, root: Path) -> bytes:
    descriptor, _ = _open_verified_regular_file(path, root=root)
    with os.fdopen(descriptor, "rb") as source:
        return source.read()


def _verified_file_bytes_bounded(
    path: Path,
    *,
    root: Path,
    maximum: int,
) -> bytes:
    descriptor, before = _open_verified_regular_file(path, root=root)
    if before.st_size < 1 or before.st_size > maximum:
        os.close(descriptor)
        raise ValueError("bounded empirical artifact size is invalid")
    with os.fdopen(descriptor, "rb") as source:
        payload = source.read(maximum + 1)
        after = os.fstat(source.fileno())
    before_snapshot = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_snapshot = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if (
        len(payload) != before.st_size
        or len(payload) > maximum
        or before_snapshot != after_snapshot
    ):
        raise OSError(
            _IDENTITY_CHANGED_ERRNO,
            "bounded empirical artifact changed while reading",
        )
    return payload


def _verified_file_fingerprint(path: Path, *, root: Path) -> dict[str, object]:
    descriptor, file_stat = _open_verified_regular_file(path, root=root)
    digest = hashlib.sha256()
    size = 0
    with os.fdopen(descriptor, "rb") as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    if size != file_stat.st_size:
        raise OSError(_IDENTITY_CHANGED_ERRNO, "export input size changed while hashing")
    return {"sha256": digest.hexdigest(), "size_bytes": size}


def _validate_empirical_hardening_supplement(
    *,
    payload: bytes,
    report_payloads: dict[str, bytes],
) -> dict[str, object]:
    """Apply the closed supplement validator to the exact seven report bytes."""

    source_root = str(Path(__file__).resolve().parents[1])
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    from crypto_rsi_scanner.event_alpha.operations import (
        empirical_hardening_supplement,
        empirical_research_reports,
    )

    if (
        EMPIRICAL_REPORT_FILENAMES != empirical_research_reports.REPORT_FILENAMES
        or EMPIRICAL_MAX_REPORT_BYTES != empirical_research_reports.MAX_REPORT_BYTES
        or EMPIRICAL_MAX_SUPPLEMENT_BYTES
        != empirical_hardening_supplement.MAX_SUPPLEMENT_BYTES
        or tuple(report_payloads) != EMPIRICAL_REPORT_FILENAMES
    ):
        raise ValueError("empirical hardening validator contract drifted")
    try:
        return empirical_hardening_supplement.parse_and_validate_hardening_supplement(
            payload,
            report_payloads=report_payloads,
        )
    except (RuntimeError, ValueError) as exc:
        raise ValueError("empirical hardening supplement validation failed") from exc


def _policy_relative_path(value: object, *, field: str) -> Path:
    text = str(value or "")
    issue = _unsafe_archive_name(text)
    if issue or text.endswith("/"):
        raise ValueError(f"invalid empirical artifact policy path: {field}")
    return Path(*PurePosixPath(text).parts)


def _validate_empirical_policy(policy: object) -> dict[str, object]:
    if not isinstance(policy, dict):
        raise ValueError("empirical artifact policy must be an object")
    if (
        policy.get("schema_id") != "decision_radar.empirical_artifact_export_policy"
        or policy.get("schema_version") != 1
    ):
        raise ValueError("unsupported empirical artifact policy")
    policy_flags = policy.get("policy")
    if not isinstance(policy_flags, dict) or any(
        policy_flags.get(key) is not True
        for key in (
            "canonical_evidence_is_immutable",
            "history_export_is_optional",
            "local_artifacts_are_never_deleted_or_moved",
            "standard_export_excludes_superseded_runs",
        )
    ):
        raise ValueError("empirical artifact policy safety flags are incomplete")
    fixed_paths = {
        "lab_root": EMPIRICAL_LAB_RELATIVE_PATH,
        "optional_feedback_path": EMPIRICAL_FEEDBACK_RELATIVE_PATH,
        "standard_manifest_archive_path": EMPIRICAL_STANDARD_MANIFEST_ARCHIVE_PATH,
    }
    for field, expected in fixed_paths.items():
        actual = _policy_relative_path(policy.get(field), field=field)
        if actual != expected:
            raise ValueError(f"empirical artifact policy {field} is not fixed")
    raw_limits = policy.get("limits")
    if (
        not isinstance(raw_limits, dict)
        or set(raw_limits) != set(EMPIRICAL_LIMITS)
        or any(type(raw_limits.get(key)) is not int for key in EMPIRICAL_LIMITS)
        or raw_limits != EMPIRICAL_LIMITS
    ):
        raise ValueError("empirical artifact policy limits are not fixed and bounded")
    runs = policy.get("canonical_runs")
    if not isinstance(runs, list) or len(runs) != 4:
        raise ValueError("empirical artifact policy must name four canonical runs")
    seen_runs: set[str] = set()
    seen_roles: set[str] = set()
    for row in runs:
        if not isinstance(row, dict):
            raise ValueError("canonical run policy row must be an object")
        run_id = str(row.get("run_fingerprint") or "")
        role = str(row.get("role") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", run_id) or not role:
            raise ValueError("canonical run policy identity is invalid")
        if run_id in seen_runs or role in seen_roles:
            raise ValueError("canonical run policy identity is duplicated")
        seen_runs.add(run_id)
        seen_roles.add(role)
        required = row.get("required_files")
        if not isinstance(required, list) or "replay_run_manifest.json" not in required:
            raise ValueError("canonical run policy lacks its manifest")
        for name in required:
            path = _policy_relative_path(name, field="canonical required file")
            if len(path.parts) != 1:
                raise ValueError("canonical required file must be a basename")
        expected_seal = row.get("expected_recommendation_seal_sha256")
        if expected_seal is not None and not re.fullmatch(
            r"[0-9a-f]{64}", str(expected_seal)
        ):
            raise ValueError("canonical recommendation seal hash is invalid")
        if not re.fullmatch(
            r"[0-9a-f]{64}", str(row.get("expected_manifest_sha256") or "")
        ):
            raise ValueError("canonical manifest hash is missing or invalid")
    semantics = policy.get("canonical_semantics")
    if not isinstance(semantics, dict):
        raise ValueError("canonical empirical semantics are missing")
    role_to_run = {str(row["role"]): str(row["run_fingerprint"]) for row in runs}
    if set(role_to_run) != {
        "canonical_fixture_smoke",
        "canonical_medium",
        "current_selection",
        "current_final_test",
    }:
        raise ValueError("canonical empirical run roles are incomplete")
    if (
        semantics.get("current_selection_run_fingerprint")
        != role_to_run.get("current_selection")
        or semantics.get("current_final_test_run_fingerprint")
        != role_to_run.get("current_final_test")
        or not re.fullmatch(r"[0-9a-f]{64}", str(semantics.get("protocol_sha256") or ""))
        or not re.fullmatch(
            r"[0-9a-f]{64}",
            str(semantics.get("recommendation_seal_sha256") or ""),
        )
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(semantics.get("v1_bundle_id") or "")
        )
        or not str(semantics.get("protocol_version") or "")
    ):
        raise ValueError("canonical empirical semantics contradict run policy")
    for role in ("current_selection", "current_final_test"):
        row = next(item for item in runs if item["role"] == role)
        expected = row.get(
            "expected_recommendation_seal_sha256",
            semantics["recommendation_seal_sha256"],
        )
        if expected != semantics["recommendation_seal_sha256"]:
            raise ValueError("current recommendation seal contradicts canonical semantics")
    for collection in ("protocol_artifacts", "reports"):
        rows = policy.get(collection)
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"empirical artifact policy {collection} are missing")
        seen_paths: set[Path] = set()
        for row in rows:
            if not isinstance(row, dict) or not row.get("role") or not row.get("semantic_id"):
                raise ValueError(f"invalid empirical artifact policy {collection} row")
            relative_path = _policy_relative_path(
                row.get("path"), field=f"{collection} path"
            )
            if relative_path in seen_paths:
                raise ValueError(f"duplicate empirical artifact policy {collection} path")
            seen_paths.add(relative_path)
            expected_sha = row.get("sha256")
            if not re.fullmatch(r"[0-9a-f]{64}", str(expected_sha or "")):
                raise ValueError(
                    f"missing or invalid empirical artifact policy {collection} hash"
                )
        expected_paths = (
            EMPIRICAL_PROTOCOL_ARTIFACT_PATHS
            if collection == "protocol_artifacts"
            else EMPIRICAL_REPORT_PATHS
        )
        if seen_paths != expected_paths:
            raise ValueError(
                f"empirical artifact policy {collection} paths are not exact"
            )
    protocol_v2 = policy.get("protocol_v2_readiness")
    if not isinstance(protocol_v2, dict):
        raise ValueError("empirical Protocol-v2 readiness binding is missing")
    if (
        _policy_relative_path(
            protocol_v2.get("document_path"), field="protocol_v2_readiness.document_path"
        )
        != EMPIRICAL_PROTOCOL_V2_DOCUMENT_PATH
        or _policy_relative_path(
            protocol_v2.get("implementation_path"),
            field="protocol_v2_readiness.implementation_path",
        )
        != EMPIRICAL_PROTOCOL_V2_IMPLEMENTATION_PATH
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(protocol_v2.get("contract_sha256") or "")
        )
    ):
        raise ValueError("empirical Protocol-v2 readiness binding is invalid")
    supplement = policy.get("hardening_supplement")
    if (
        not isinstance(supplement, dict)
        or _policy_relative_path(
            supplement.get("path"), field="hardening_supplement.path"
        )
        != EMPIRICAL_HARDENING_SUPPLEMENT_PATH
        or supplement.get("role") != "current_empirical_hardening_supplement"
        or supplement.get("semantic_id")
        != "decision_radar_empirical_hardening_supplement_v1"
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(supplement.get("sha256") or "")
        )
        or type(supplement.get("size_bytes")) is not int
        or not 1
        <= supplement["size_bytes"]
        <= EMPIRICAL_LIMITS["max_single_empirical_file_bytes"]
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(supplement.get("supplement_id") or "")
        )
        or supplement.get("v1_report_bundle_member") is not False
    ):
        raise ValueError("empirical hardening supplement binding is invalid")
    history = policy.get("history_archive")
    if not isinstance(history, dict):
        raise ValueError("empirical history archive policy is missing")
    expected_history = {
        "checksums_archive_path": EMPIRICAL_HISTORY_CHECKSUMS_ARCHIVE_PATH,
        "manifest_archive_path": EMPIRICAL_HISTORY_MANIFEST_ARCHIVE_PATH,
        "output_filename": EMPIRICAL_HISTORY_OUTPUT_FILENAME,
    }
    for key, expected in expected_history.items():
        path = _policy_relative_path(history.get(key), field=f"history_archive.{key}")
        if len(path.parts) != 1 or path.as_posix() != expected:
            raise ValueError("empirical history synthetic paths are not fixed")
    if len(set(expected_history.values())) != len(expected_history):
        raise ValueError("empirical history synthetic paths collide")
    return policy


def _load_empirical_policy(root: Path) -> tuple[dict[str, object], bytes] | None:
    policy_path = root / EMPIRICAL_POLICY_RELATIVE_PATH
    default_lab_root = root / "event_fade_cache" / "decision_radar_research_lab"
    try:
        policy_lstat = policy_path.lstat()
    except FileNotFoundError:
        try:
            default_lab_root.lstat()
        except FileNotFoundError:
            return None
        raise ValueError("empirical artifact policy is missing")
    if not stat.S_ISREG(policy_lstat.st_mode):
        raise ValueError("empirical artifact policy is not a regular file")
    raw = _verified_file_bytes(policy_path, root=root)
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("empirical artifact policy is invalid JSON") from exc
    return _validate_empirical_policy(parsed), raw


def _open_verified_directory(path: Path, *, root: Path) -> tuple[int, os.stat_result]:
    """Open one root-relative directory through descriptor-anchored components."""

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
        raise OSError(errno.EPERM, "empirical artifact directory is outside root") from exc
    if any(part in {"", ".", ".."} for part in parts):
        raise OSError(errno.EPERM, "empirical artifact directory path is unsafe")

    flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )
    root_before = os.stat(root_abs, follow_symlinks=False)
    if not stat.S_ISDIR(root_before.st_mode):
        raise OSError(errno.ENOTDIR, "trusted export root is not a directory")
    descriptor = os.open(root_abs, flags)
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or (root_before.st_dev, root_before.st_ino)
            != (opened.st_dev, opened.st_ino)
        ):
            raise OSError(
                _IDENTITY_CHANGED_ERRNO,
                "trusted export root changed during validation",
            )
        for part in parts:
            before = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
            if not stat.S_ISDIR(before.st_mode):
                raise OSError(errno.ENOTDIR, "empirical artifact path is not a directory")
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            try:
                next_opened = os.fstat(next_descriptor)
                if (
                    not stat.S_ISDIR(next_opened.st_mode)
                    or (before.st_dev, before.st_ino)
                    != (next_opened.st_dev, next_opened.st_ino)
                ):
                    raise OSError(
                        _IDENTITY_CHANGED_ERRNO,
                        "empirical artifact directory changed during validation",
                    )
            except BaseException:
                os.close(next_descriptor)
                raise
            os.close(descriptor)
            descriptor = next_descriptor
            opened = next_opened
        return descriptor, opened
    except BaseException:
        os.close(descriptor)
        raise


def _strict_regular_files_under(
    directory: Path,
    *,
    root: Path,
    max_file_count: int | None = None,
    max_total_bytes: int | None = None,
    max_single_file_bytes: int | None = None,
) -> set[Path]:
    """Enumerate a bounded regular-file tree without following or racing links."""

    directory_abs = directory.expanduser().absolute()
    directory_fd, directory_stat = _open_verified_directory(directory_abs, root=root)
    files: set[Path] = set()
    total_bytes = 0
    directory_flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )

    def check_bounds(file_stat: os.stat_result) -> None:
        nonlocal total_bytes
        if (
            max_single_file_bytes is not None
            and file_stat.st_size > max_single_file_bytes
        ):
            raise ValueError("empirical artifact file exceeds size bound")
        total_bytes += file_stat.st_size
        if max_file_count is not None and len(files) + 1 > max_file_count:
            raise ValueError("empirical artifact tree exceeds file-count bound")
        if max_total_bytes is not None and total_bytes > max_total_bytes:
            raise ValueError("empirical artifact tree exceeds total-size bound")

    def walk(parent_fd: int, relative_parts: tuple[str, ...]) -> None:
        try:
            names_before = sorted(os.listdir(parent_fd))
        except OSError as exc:
            raise OSError(errno.EIO, "empirical artifact directory is unreadable") from exc
        if any(
            name in {"", ".", ".."}
            or "/" in name
            or any(ord(character) < 32 or ord(character) == 127 for character in name)
            for name in names_before
        ):
            raise OSError(errno.EINVAL, "empirical artifact tree name is unsafe")
        for name in names_before:
            before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if stat.S_ISDIR(before.st_mode):
                child_fd = os.open(name, directory_flags, dir_fd=parent_fd)
                try:
                    opened = os.fstat(child_fd)
                    if (
                        not stat.S_ISDIR(opened.st_mode)
                        or (before.st_dev, before.st_ino)
                        != (opened.st_dev, opened.st_ino)
                    ):
                        raise OSError(
                            _IDENTITY_CHANGED_ERRNO,
                            "empirical artifact directory changed during walk",
                        )
                    walk(child_fd, (*relative_parts, name))
                finally:
                    os.close(child_fd)
                after = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                if (
                    not stat.S_ISDIR(after.st_mode)
                    or (before.st_dev, before.st_ino)
                    != (after.st_dev, after.st_ino)
                ):
                    raise OSError(
                        _IDENTITY_CHANGED_ERRNO,
                        "empirical artifact directory changed after walk",
                    )
            elif stat.S_ISREG(before.st_mode):
                check_bounds(before)
                files.add(directory_abs.joinpath(*relative_parts, name))
                after = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                if (
                    not stat.S_ISREG(after.st_mode)
                    or (before.st_dev, before.st_ino, before.st_size)
                    != (after.st_dev, after.st_ino, after.st_size)
                ):
                    raise OSError(
                        _IDENTITY_CHANGED_ERRNO,
                        "empirical artifact file changed during walk",
                    )
            else:
                raise OSError(errno.EINVAL, "empirical artifact tree is unsafe")
        if sorted(os.listdir(parent_fd)) != names_before:
            raise OSError(
                _IDENTITY_CHANGED_ERRNO,
                "empirical artifact directory entries changed during walk",
            )

    try:
        walk(directory_fd, ())
        reopened_fd, reopened_stat = _open_verified_directory(directory_abs, root=root)
        try:
            if (
                (directory_stat.st_dev, directory_stat.st_ino)
                != (reopened_stat.st_dev, reopened_stat.st_ino)
                or (directory_stat.st_dev, directory_stat.st_ino)
                != (os.fstat(directory_fd).st_dev, os.fstat(directory_fd).st_ino)
            ):
                raise OSError(
                    _IDENTITY_CHANGED_ERRNO,
                    "empirical artifact root changed during walk",
                )
        finally:
            os.close(reopened_fd)
    finally:
        os.close(directory_fd)
    return files


def _verify_canonical_empirical_run(
    *,
    run_directory: Path,
    run_policy: dict[str, object],
    semantics: dict[str, object],
    root: Path,
) -> tuple[
    set[Path],
    dict[str, object],
    dict[Path, dict[str, object]],
]:
    run_id = str(run_policy["run_fingerprint"])
    manifest_path = run_directory / "replay_run_manifest.json"
    manifest_raw = _verified_file_bytes(manifest_path, root=root)
    if (
        hashlib.sha256(manifest_raw).hexdigest()
        != run_policy["expected_manifest_sha256"]
    ):
        raise ValueError(f"canonical empirical manifest fingerprint drifted: {run_id}")
    try:
        manifest = json.loads(manifest_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"canonical empirical manifest is invalid: {run_id}") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("run_fingerprint") != run_id
        or manifest.get("immutable") is not True
        or manifest.get("research_only") is not True
        or manifest.get("auto_apply") is not False
        or manifest.get("protocol_sha256") != semantics.get("protocol_sha256")
        or manifest.get("protocol_version") != semantics.get("protocol_version")
    ):
        raise ValueError(f"canonical empirical manifest semantics drifted: {run_id}")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError(f"canonical empirical manifest has no artifacts: {run_id}")
    expected_files = {manifest_path}
    verified_fingerprints = {
        manifest_path: {
            "sha256": hashlib.sha256(manifest_raw).hexdigest(),
            "size_bytes": len(manifest_raw),
        }
    }
    for name, expected in artifacts.items():
        relative = _policy_relative_path(name, field="manifest artifact")
        if len(relative.parts) != 1 or not isinstance(expected, dict):
            raise ValueError(f"canonical empirical manifest artifact is invalid: {run_id}")
        path = run_directory / relative
        actual = _verified_file_fingerprint(path, root=root)
        if (
            expected.get("sha256") != actual["sha256"]
            or expected.get("size_bytes") != actual["size_bytes"]
        ):
            raise ValueError(f"canonical empirical artifact fingerprint drifted: {run_id}")
        expected_files.add(path)
        verified_fingerprints[path] = actual
    actual_files = _strict_regular_files_under(run_directory, root=root)
    if actual_files != expected_files:
        raise ValueError(f"canonical empirical run is incomplete or unmanifested: {run_id}")
    for required_name in run_policy["required_files"]:
        if run_directory / str(required_name) not in expected_files:
            raise ValueError(f"canonical empirical required file is missing: {run_id}")
    if "recommendation_seal.json" in run_policy["required_files"]:
        seal_path = run_directory / "recommendation_seal.json"
        seal_raw = _verified_file_bytes_bounded(
            seal_path,
            root=root,
            maximum=EMPIRICAL_LIMITS["max_single_empirical_file_bytes"],
        )
        seal_fingerprint = {
            "sha256": hashlib.sha256(seal_raw).hexdigest(),
            "size_bytes": len(seal_raw),
        }
        if seal_fingerprint != verified_fingerprints.get(seal_path):
            raise ValueError(
                f"canonical recommendation seal changed during validation: {run_id}"
            )
        try:
            seal = json.loads(seal_raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"canonical recommendation seal is invalid: {run_id}") from exc
        if (
            not isinstance(seal, dict)
            or seal.get("seal_sha256")
            != run_policy.get(
                "expected_recommendation_seal_sha256",
                semantics.get("recommendation_seal_sha256"),
            )
            or seal.get("protocol_sha256") != semantics.get("protocol_sha256")
            or seal.get("research_only") is not True
            or seal.get("auto_apply") is not False
        ):
            raise ValueError(f"canonical recommendation seal semantics drifted: {run_id}")
    return expected_files, manifest, verified_fingerprints


def _validate_empirical_feedback(
    *,
    payload: bytes,
    queue_payload: bytes,
    policy: dict[str, object],
) -> dict[str, object]:
    """Validate optional feedback against its exact canonical selection queue."""

    limits = policy["limits"]
    if len(payload) > limits["max_feedback_total_bytes"]:
        raise ValueError("empirical feedback exceeds total-size bound")
    try:
        queue = json.loads(queue_payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("empirical feedback queue is invalid JSON") from exc
    if not isinstance(queue, dict):
        raise ValueError("empirical feedback queue is invalid")
    semantics = policy["canonical_semantics"]
    if (
        queue.get("run_fingerprint")
        != semantics.get("current_selection_run_fingerprint")
        or queue.get("protocol_sha256") != semantics.get("protocol_sha256")
        or queue.get("protocol_version") != semantics.get("protocol_version")
    ):
        raise ValueError("empirical feedback queue contradicts canonical selection")
    source_root = str(Path(__file__).resolve().parents[1])
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    from crypto_rsi_scanner.event_alpha.operations import empirical_review_feedback

    if (
        limits["max_feedback_event_bytes"]
        != empirical_review_feedback.MAX_EVENT_BYTES
        or limits["max_feedback_event_count"]
        != empirical_review_feedback.MAX_LEDGER_EVENTS
        or limits["max_feedback_total_bytes"]
        != empirical_review_feedback.MAX_LEDGER_BYTES
    ):
        raise ValueError("empirical feedback bounds contradict validator contract")
    try:
        rows, _row_payloads = empirical_review_feedback._parse_ledger(payload, queue)
    except (RuntimeError, ValueError) as exc:
        raise ValueError("empirical feedback ledger is invalid") from exc
    return {
        "event_count": len(rows),
        "optional_feedback": True,
        "queue_digest": queue["queue_digest"],
        "run_fingerprint": queue["run_fingerprint"],
    }


def _empirical_export_plan(
    root: Path,
) -> dict[str, object] | None:
    loaded = _load_empirical_policy(root)
    if loaded is None:
        return None
    policy, policy_raw = loaded
    lab_relative = _policy_relative_path(policy["lab_root"], field="lab_root")
    lab_root = root / lab_relative
    try:
        lab_root.lstat()
    except FileNotFoundError as exc:
        raise ValueError("empirical artifact policy requires its lab tree") from exc
    limits = policy["limits"]
    all_lab_paths = _strict_regular_files_under(
        lab_root,
        root=root,
        max_file_count=limits["max_lab_file_count"],
        max_total_bytes=limits["max_lab_total_bytes"],
        max_single_file_bytes=limits["max_single_empirical_file_bytes"],
    )
    if not all_lab_paths:
        raise ValueError("empirical artifact lab tree is empty")
    skipped = sorted(
        path.relative_to(root).as_posix()
        for path in all_lab_paths
        if _skip(path, root=root)
    )
    if skipped:
        raise ValueError("empirical artifact lab contains excluded noise")
    manifest_archive_path = root / _policy_relative_path(
        policy["standard_manifest_archive_path"],
        field="standard_manifest_archive_path",
    )
    if manifest_archive_path in all_lab_paths:
        raise ValueError("empirical artifact tree collides with synthetic manifest")
    semantics = policy["canonical_semantics"]
    selected_lab_paths: set[Path] = set()
    entry_semantics: dict[Path, tuple[str, dict[str, object]]] = {}
    verified_fingerprints: dict[Path, dict[str, object]] = {}
    for run_policy in policy["canonical_runs"]:
        run_id = str(run_policy["run_fingerprint"])
        run_directory = lab_root / "runs" / run_id
        run_paths, manifest, run_fingerprints = _verify_canonical_empirical_run(
            run_directory=run_directory,
            run_policy=run_policy,
            semantics=semantics,
            root=root,
        )
        selected_lab_paths.update(run_paths)
        if verified_fingerprints.keys() & run_fingerprints.keys():
            raise ValueError("canonical empirical run paths overlap")
        verified_fingerprints.update(run_fingerprints)
        semantic_ids = {
            "protocol_sha256": manifest["protocol_sha256"],
            "protocol_version": manifest["protocol_version"],
            "run_fingerprint": run_id,
            "run_role": str(run_policy["role"]),
        }
        for path in run_paths:
            entry_semantics[path] = ("canonical_run_artifact", semantic_ids)

    feedback_path = root / _policy_relative_path(
        policy["optional_feedback_path"], field="optional_feedback_path"
    )
    try:
        feedback_path.lstat()
    except FileNotFoundError:
        pass
    else:
        feedback_raw = _verified_file_bytes_bounded(
            feedback_path,
            root=root,
            maximum=limits["max_feedback_total_bytes"],
        )
        selection_run = next(
            row for row in policy["canonical_runs"] if row["role"] == "current_selection"
        )
        queue_path = (
            lab_root
            / "runs"
            / str(selection_run["run_fingerprint"])
            / "targeted_review_queue.json"
        )
        if queue_path not in selected_lab_paths:
            raise ValueError("canonical selection does not bind its feedback queue")
        queue_payload = _verified_file_bytes_bounded(
            queue_path,
            root=root,
            maximum=limits["max_single_empirical_file_bytes"],
        )
        queue_fingerprint = {
            "sha256": hashlib.sha256(queue_payload).hexdigest(),
            "size_bytes": len(queue_payload),
        }
        if queue_fingerprint != verified_fingerprints.get(queue_path):
            raise ValueError("canonical feedback queue changed during validation")
        feedback_semantics = _validate_empirical_feedback(
            payload=feedback_raw,
            queue_payload=queue_payload,
            policy=policy,
        )
        selected_lab_paths.add(feedback_path)
        verified_fingerprints[feedback_path] = {
            "sha256": hashlib.sha256(feedback_raw).hexdigest(),
            "size_bytes": len(feedback_raw),
        }
        entry_semantics[feedback_path] = (
            "current_optional_feedback",
            feedback_semantics,
        )

    if not selected_lab_paths <= all_lab_paths:
        raise ValueError("canonical empirical selection is outside the lab snapshot")

    tracked_rows = [
        *policy["protocol_artifacts"],
        *policy["reports"],
        policy["hardening_supplement"],
        {
            "path": EMPIRICAL_POLICY_RELATIVE_PATH.as_posix(),
            "role": "empirical_artifact_export_policy",
            "semantic_id": policy["schema_id"],
        },
    ]
    tracked_paths: set[Path] = set()
    tracked_payloads: dict[Path, bytes] = {}
    policy_path = root / EMPIRICAL_POLICY_RELATIVE_PATH
    for row in tracked_rows:
        relative_path = _policy_relative_path(row["path"], field="tracked artifact")
        path = root / relative_path
        if path == policy_path:
            payload = policy_raw
        else:
            maximum = limits["max_single_empirical_file_bytes"]
            if relative_path in EMPIRICAL_REPORT_PATHS:
                maximum = EMPIRICAL_MAX_REPORT_BYTES
            elif path == root / EMPIRICAL_HARDENING_SUPPLEMENT_PATH:
                maximum = EMPIRICAL_MAX_SUPPLEMENT_BYTES
            payload = _verified_file_bytes_bounded(
                path,
                root=root,
                maximum=maximum,
            )
        actual = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
        }
        expected_sha = row.get("sha256")
        if expected_sha is not None and expected_sha != actual["sha256"]:
            raise ValueError(f"frozen empirical protocol drifted: {row['path']}")
        expected_size = row.get("size_bytes")
        if expected_size is not None and expected_size != actual["size_bytes"]:
            raise ValueError(f"frozen empirical artifact size drifted: {row['path']}")
        tracked_paths.add(path)
        tracked_payloads[path] = payload
        verified_fingerprints[path] = actual
        semantic_ids = {"semantic_id": str(row["semantic_id"])}
        if path == root / EMPIRICAL_PROTOCOL_V2_DOCUMENT_PATH:
            contract_sha = policy["protocol_v2_readiness"]["contract_sha256"]
            if contract_sha.encode("ascii") not in payload:
                raise ValueError("Protocol-v2 readiness digest is absent from its document")
            semantic_ids["contract_sha256"] = contract_sha
        elif path == root / EMPIRICAL_PROTOCOL_V2_IMPLEMENTATION_PATH:
            semantic_ids["contract_sha256"] = policy["protocol_v2_readiness"][
                "contract_sha256"
            ]
        entry_semantics[path] = (
            str(row["role"]),
            semantic_ids,
        )

    report_payloads = {
        name: tracked_payloads[root / "research" / name]
        for name in EMPIRICAL_REPORT_FILENAMES
    }
    supplement_path = root / EMPIRICAL_HARDENING_SUPPLEMENT_PATH
    supplement_value = _validate_empirical_hardening_supplement(
        payload=tracked_payloads[supplement_path],
        report_payloads=report_payloads,
    )
    if (
        supplement_value.get("supplement_id")
        != policy["hardening_supplement"]["supplement_id"]
        or supplement_value["v1_report_bundle"].get("bundle_id")
        != policy["canonical_semantics"]["v1_bundle_id"]
        or supplement_value["v1_report_bundle"].get("protocol_sha256")
        != policy["canonical_semantics"]["protocol_sha256"]
        or supplement_value["v1_report_bundle"].get("protocol_version")
        != policy["canonical_semantics"]["protocol_version"]
    ):
        raise ValueError("empirical hardening supplement semantics drifted")
    supplement_role, supplement_semantics = entry_semantics[supplement_path]
    supplement_semantics.update(
        {
            "supplement_id": policy["hardening_supplement"]["supplement_id"],
            "v1_report_bundle_member": False,
        }
    )
    entry_semantics[supplement_path] = (
        supplement_role,
        supplement_semantics,
    )

    manifest_entries: list[dict[str, object]] = []
    for path in sorted(selected_lab_paths | tracked_paths, key=lambda item: item.relative_to(root).as_posix()):
        try:
            fingerprint = verified_fingerprints[path]
        except KeyError as exc:
            raise ValueError("empirical artifact was not verified exactly once") from exc
        role, semantic_ids = entry_semantics[path]
        manifest_entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "role": role,
                "semantic_ids": semantic_ids,
                **fingerprint,
            }
        )
    canonical_entries = [
        row
        for row in manifest_entries
        if root / Path(*PurePosixPath(str(row["path"])).parts) in selected_lab_paths
    ]
    if (
        len(canonical_entries) > limits["max_canonical_lab_file_count"]
        or sum(int(row["size_bytes"]) for row in canonical_entries)
        > limits["max_canonical_lab_total_bytes"]
        or len(manifest_entries) > limits["max_standard_empirical_file_count"]
        or sum(int(row["size_bytes"]) for row in manifest_entries)
        > limits["max_standard_empirical_total_bytes"]
    ):
        raise ValueError("canonical empirical export selection exceeds policy bounds")
    return {
        "all_lab_paths": all_lab_paths,
        "manifest_entries": manifest_entries,
        "policy": policy,
        "policy_sha256": hashlib.sha256(policy_raw).hexdigest(),
        "selected_lab_paths": selected_lab_paths,
        "tracked_paths": tracked_paths,
    }


def _standard_empirical_manifest(plan: dict[str, object]) -> dict[str, object]:
    policy = plan["policy"]
    entries = plan["manifest_entries"]
    return {
        "canonical_semantics": policy["canonical_semantics"],
        "entries": entries,
        "entry_count": len(entries),
        "hardening_supplement": policy["hardening_supplement"],
        "history_archive": {
            "available_via_separate_optional_export": True,
            "included_in_standard_export": False,
            "output_filename": policy["history_archive"]["output_filename"],
        },
        "immutable_evidence": True,
        "local_artifacts_deleted_or_moved": False,
        "policy_sha256": plan["policy_sha256"],
        "protocol_v2_readiness": policy["protocol_v2_readiness"],
        "research_only": True,
        "schema_id": "decision_radar.empirical_artifact_export_manifest",
        "schema_version": 1,
    }


def _validate_project_artifact_policy(policy: object) -> dict[str, object]:
    """Validate the one checked-in authority for non-empirical artifact export."""

    if not isinstance(policy, dict):
        raise ValueError("project artifact policy must be an object")
    if (
        policy.get("schema_id") != "decision_radar.project_artifact_export_policy"
        or policy.get("schema_version") != 2
    ):
        raise ValueError("unsupported project artifact policy")
    expected_keys = {
        "artifact_root",
        "canonical_root_files",
        "canonical_shared_directories",
        "delegated_empirical_subtree",
        "dynamic_namespace_selectors",
        "history_archive",
        "limits",
        "policy",
        "schema_id",
        "schema_version",
        "standard_manifest_archive_path",
    }
    if set(policy) != expected_keys:
        raise ValueError("project artifact policy schema is not closed")
    if (
        _policy_relative_path(policy.get("artifact_root"), field="artifact_root")
        != PROJECT_ARTIFACT_ROOT_RELATIVE_PATH
        or _policy_relative_path(
            policy.get("delegated_empirical_subtree"),
            field="delegated_empirical_subtree",
        )
        != Path("decision_radar_research_lab")
        or _policy_relative_path(
            policy.get("standard_manifest_archive_path"),
            field="standard_manifest_archive_path",
        ).as_posix()
        != PROJECT_STANDARD_MANIFEST_ARCHIVE_PATH
    ):
        raise ValueError("project artifact policy paths are not fixed")
    if tuple(policy.get("canonical_root_files") or ()) != PROJECT_CANONICAL_ROOT_FILES:
        raise ValueError("project canonical root-file policy drifted")
    if (
        tuple(policy.get("canonical_shared_directories") or ())
        != PROJECT_CANONICAL_SHARED_DIRECTORIES
    ):
        raise ValueError("project canonical shared-directory policy drifted")
    if tuple(policy.get("dynamic_namespace_selectors") or ()) != (
        PROJECT_DYNAMIC_NAMESPACE_SELECTORS
    ):
        raise ValueError("project dynamic selector policy drifted")
    limits = policy.get("limits")
    if (
        not isinstance(limits, dict)
        or limits != PROJECT_ARTIFACT_LIMITS
        or any(type(value) is not int or value < 1 for value in limits.values())
    ):
        raise ValueError("project artifact limits are not fixed and bounded")
    policy_flags = policy.get("policy")
    required_flags = {
        "canonical_selection_is_manifested",
        "delegated_empirical_policy_remains_authoritative",
        "history_export_is_optional",
        "local_artifacts_are_never_deleted_or_moved",
        "standard_export_excludes_noncanonical_artifacts",
    }
    if (
        not isinstance(policy_flags, dict)
        or set(policy_flags) != required_flags
        or any(policy_flags.get(key) is not True for key in required_flags)
    ):
        raise ValueError("project artifact policy safety flags are incomplete")
    history = policy.get("history_archive")
    expected_history = {
        "checksums_archive_path": PROJECT_HISTORY_CHECKSUMS_ARCHIVE_PATH,
        "manifest_archive_path": PROJECT_HISTORY_MANIFEST_ARCHIVE_PATH,
        "output_filename": PROJECT_HISTORY_OUTPUT_FILENAME,
    }
    if not isinstance(history, dict) or history != expected_history:
        raise ValueError("project artifact history policy drifted")
    for field, value in expected_history.items():
        path = _policy_relative_path(value, field=f"history_archive.{field}")
        if len(path.parts) != 1:
            raise ValueError("project artifact history paths must be basenames")
    return policy


def _load_project_artifact_policy(
    root: Path,
) -> tuple[dict[str, object], bytes] | None:
    artifact_root = root / PROJECT_ARTIFACT_ROOT_RELATIVE_PATH
    try:
        artifact_identity = artifact_root.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISDIR(artifact_identity.st_mode) or stat.S_ISLNK(
        artifact_identity.st_mode
    ):
        raise ValueError("project artifact root is not a safe directory")
    policy_path = root / PROJECT_ARTIFACT_POLICY_RELATIVE_PATH
    policy_raw = _verified_file_bytes_bounded(
        policy_path,
        root=root,
        maximum=64 * 1024,
    )
    try:
        parsed = json.loads(policy_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("project artifact policy is invalid JSON") from exc
    return _validate_project_artifact_policy(parsed), policy_raw


def _project_namespace_component(value: object, *, field: str) -> str:
    path = _policy_relative_path(value, field=field)
    if len(path.parts) != 1 or not re.fullmatch(
        r"radar_market_no_send_[A-Za-z0-9_]+", path.name
    ):
        raise ValueError(f"invalid project artifact namespace: {field}")
    return path.name


def _dashboard_pointer_namespace(payload: bytes) -> tuple[str, dict[str, object]]:
    from crypto_rsi_scanner.event_alpha.dashboard.readiness import (
        validate_current_namespace_pointer_bytes,
    )

    pointer = validate_current_namespace_pointer_bytes(payload)
    namespace = _project_namespace_component(
        pointer.get("artifact_namespace"), field="dashboard pointer namespace"
    )
    return namespace, {
        "artifact_namespace": namespace,
        "revision": pointer["revision"],
        "run_id": pointer["run_id"],
        "status": "selected",
    }


def _latest_attempt_namespace(payload: bytes) -> tuple[str, dict[str, object]]:
    try:
        row = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("latest market attempt is invalid JSON") from exc
    if not isinstance(row, dict):
        raise ValueError("latest market attempt must be an object")
    required_truth = {
        "candidate_source_mode": "live_no_send",
        "data_acquisition_mode": "live_provider",
        "data_mode": "live",
        "no_send": True,
        "research_only": True,
        "row_type": "event_market_no_send_latest_attempt",
    }
    if any(row.get(key) != value for key, value in required_truth.items()):
        raise ValueError("latest market attempt is not canonical live/no-send evidence")
    status = row.get("status")
    if status not in {
        "blocked",
        "complete",
        "failed",
        "provider_unavailable",
        "skipped",
    }:
        raise ValueError("latest market attempt status is invalid")
    if status == "provider_unavailable" and (
        row.get("provider_call_attempted") is not True
        or row.get("provider_request_succeeded") is not False
        or row.get("decision_radar_campaign_counted") is not False
    ):
        raise ValueError("latest provider-unavailable attempt truth is invalid")
    namespace = _project_namespace_component(
        row.get("artifact_namespace"), field="latest attempt namespace"
    )
    return namespace, {
        "artifact_namespace": namespace,
        "attempt_id": row.get("attempt_id"),
        "provider_call_attempted": row.get("provider_call_attempted"),
        "status": "selected",
        "terminal_status": status,
    }


def _latest_bybit_execution_quality_namespace(
    payload: bytes,
) -> tuple[str, dict[str, object]]:
    from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality_capture import (
        BybitExecutionQualityCaptureError,
        validate_bybit_execution_quality_pointer_bytes,
    )

    try:
        pointer = validate_bybit_execution_quality_pointer_bytes(payload)
    except BybitExecutionQualityCaptureError as exc:
        raise ValueError("latest Bybit execution-quality pointer is invalid") from exc
    namespace = str(pointer["artifact_namespace"])
    return namespace, {
        "artifact_namespace": namespace,
        "capture_id": pointer["capture_id"],
        "evidence_authority_eligible": pointer["evidence_authority_eligible"],
        "protocol_v2_evidence_eligible": pointer[
            "protocol_v2_evidence_eligible"
        ],
        "protocol_v2_input_quality_eligible": pointer[
            "protocol_v2_input_quality_eligible"
        ],
        "protocol_v2_annex_bound": pointer["protocol_v2_annex_bound"],
        "status": "selected",
    }


def _latest_bybit_intraday_namespace(
    payload: bytes,
) -> tuple[str, dict[str, object]]:
    from crypto_rsi_scanner.event_alpha.operations.bybit_intraday_capture import (
        BybitIntradayCaptureError,
        validate_bybit_intraday_pointer_bytes,
    )

    try:
        pointer = validate_bybit_intraday_pointer_bytes(payload)
    except BybitIntradayCaptureError as exc:
        raise ValueError("latest Bybit intraday pointer is invalid") from exc
    namespace = str(pointer["artifact_namespace"])
    return namespace, {
        "artifact_namespace": namespace,
        "capture_id": pointer["capture_id"],
        "source_execution_quality_capture_id": pointer[
            "source_execution_quality_capture_id"
        ],
        "all_bars_fresh": pointer["all_bars_fresh"],
        "all_bars_fresh_at_acquisition": pointer[
            "all_bars_fresh_at_acquisition"
        ],
        "all_bars_fresh_at_completion": pointer[
            "all_bars_fresh_at_completion"
        ],
        "intraday_set_freshness_policy": pointer[
            "intraday_set_freshness_policy"
        ],
        "maximum_provider_response_age_at_completion_seconds": pointer[
            "maximum_provider_response_age_at_completion_seconds"
        ],
        "maximum_provider_response_age_policy_seconds": pointer[
            "maximum_provider_response_age_policy_seconds"
        ],
        "minimum_bar_recency_remaining_at_completion_seconds": pointer[
            "minimum_bar_recency_remaining_at_completion_seconds"
        ],
        "bar_recency_policy": pointer["bar_recency_policy"],
        "protocol_v2_input_quality_eligible": pointer[
            "protocol_v2_input_quality_eligible"
        ],
        "protocol_v2_evidence_eligible": pointer[
            "protocol_v2_evidence_eligible"
        ],
        "protocol_v2_annex_bound": pointer["protocol_v2_annex_bound"],
        "status": "selected",
    }


def _latest_bybit_derivatives_namespace(
    payload: bytes,
) -> tuple[str, dict[str, object]]:
    from crypto_rsi_scanner.event_alpha.operations.bybit_derivatives_context_capture import (
        BybitDerivativesContextCaptureError,
        validate_bybit_derivatives_context_pointer_bytes,
    )

    try:
        pointer = validate_bybit_derivatives_context_pointer_bytes(payload)
    except BybitDerivativesContextCaptureError as exc:
        raise ValueError("latest Bybit derivatives pointer is invalid") from exc
    namespace = str(pointer["artifact_namespace"])
    return namespace, {
        "artifact_namespace": namespace,
        "capture_id": pointer["capture_id"],
        "source_execution_quality_capture_id": pointer[
            "source_execution_quality_capture_id"
        ],
        "all_context_fresh": pointer["all_context_fresh"],
        "all_context_fresh_at_acquisition": pointer[
            "all_context_fresh_at_acquisition"
        ],
        "all_context_fresh_at_completion": pointer[
            "all_context_fresh_at_completion"
        ],
        "derivatives_set_freshness_policy": pointer[
            "derivatives_set_freshness_policy"
        ],
        "maximum_context_age_at_completion_seconds": pointer[
            "maximum_context_age_at_completion_seconds"
        ],
        "maximum_context_age_policy_seconds": pointer[
            "maximum_context_age_policy_seconds"
        ],
        "protocol_v2_input_quality_eligible": pointer[
            "protocol_v2_input_quality_eligible"
        ],
        "protocol_v2_evidence_eligible": pointer[
            "protocol_v2_evidence_eligible"
        ],
        "protocol_v2_annex_bound": pointer["protocol_v2_annex_bound"],
        "status": "selected",
    }


def _latest_outcome_price_recovery_namespace(
    payload: bytes,
) -> tuple[str, dict[str, object]]:
    from crypto_rsi_scanner.event_alpha.operations.outcome_price_recovery_capture import (
        OutcomePriceRecoveryError,
        validate_outcome_price_recovery_pointer_bytes,
    )

    try:
        pointer = validate_outcome_price_recovery_pointer_bytes(payload)
    except OutcomePriceRecoveryError as exc:
        raise ValueError("latest outcome-price recovery pointer is invalid") from exc
    namespace = str(pointer["artifact_namespace"])
    return namespace, {
        "artifact_namespace": namespace,
        "capture_id": pointer["capture_id"],
        "request_count": pointer["request_count"],
        "qualifying_price_count": pointer["qualifying_price_count"],
        "protocol_v2_evidence_eligible": False,
        "status": "selected",
    }


def _project_artifact_export_plan(
    root: Path,
    *,
    empirical_plan: dict[str, object] | None,
) -> dict[str, object] | None:
    """Select current operator evidence while preserving history in place."""

    loaded = _load_project_artifact_policy(root)
    if loaded is None:
        return None
    policy, policy_raw = loaded
    limits = policy["limits"]
    artifact_root = root / PROJECT_ARTIFACT_ROOT_RELATIVE_PATH
    inventoried = _strict_regular_files_under(
        artifact_root,
        root=root,
        max_file_count=limits["max_artifact_file_count"],
        max_total_bytes=limits["max_artifact_total_bytes"],
        max_single_file_bytes=limits["max_single_artifact_file_bytes"],
    )
    eligible = {path for path in inventoried if not _skip(path, root=root)}
    excluded_noise = sorted(
        path.relative_to(root).as_posix() for path in inventoried - eligible
    )
    synthetic_manifest = root / Path(
        *PurePosixPath(PROJECT_STANDARD_MANIFEST_ARCHIVE_PATH).parts
    )
    if synthetic_manifest in inventoried:
        raise ValueError("project artifact tree collides with synthetic manifest")

    selected: set[Path] = set()
    roles: dict[Path, str] = {}
    present_root_files: list[str] = []
    missing_root_files: list[str] = []
    for name in policy["canonical_root_files"]:
        path = artifact_root / str(name)
        if path in eligible:
            selected.add(path)
            roles[path] = "canonical_operator_control"
            present_root_files.append(str(name))
        else:
            missing_root_files.append(str(name))

    present_shared_directories: list[str] = []
    missing_shared_directories: list[str] = []
    for name in policy["canonical_shared_directories"]:
        directory = artifact_root / str(name)
        try:
            identity = directory.lstat()
        except FileNotFoundError:
            missing_shared_directories.append(str(name))
            continue
        if not stat.S_ISDIR(identity.st_mode) or stat.S_ISLNK(identity.st_mode):
            raise ValueError("canonical shared artifact path is not a safe directory")
        directory_inventory = _strict_regular_files_under(
            directory,
            root=root,
            max_file_count=limits["max_standard_artifact_file_count"],
            max_total_bytes=limits["max_standard_artifact_total_bytes"],
            max_single_file_bytes=limits["max_single_artifact_file_bytes"],
        )
        directory_paths = {
            path for path in directory_inventory if not _skip(path, root=root)
        }
        if not directory_paths <= eligible:
            raise ValueError("canonical shared artifact directory escaped inventory")
        selected.update(directory_paths)
        for path in directory_paths:
            roles[path] = "canonical_shared_state"
        present_shared_directories.append(str(name))

    selector_results: list[dict[str, object]] = []
    selector_roles = {
        "dashboard_pointer_namespace": "current_dashboard_authority_generation",
        "latest_live_no_send_attempt_namespace": "latest_live_no_send_attempt_generation",
        "latest_bybit_execution_quality_namespace": "latest_bybit_execution_quality_capture",
        "latest_bybit_intraday_namespace": "latest_bybit_intraday_capture",
        "latest_bybit_derivatives_namespace": "latest_bybit_derivatives_capture",
        "latest_outcome_price_recovery_namespace": "latest_outcome_price_recovery_capture",
        "review_timing_source_namespaces": "human_review_timing_source_generation",
    }
    selector_loaders = {
        "dashboard_pointer_namespace": _dashboard_pointer_namespace,
        "latest_live_no_send_attempt_namespace": _latest_attempt_namespace,
        "latest_bybit_execution_quality_namespace": _latest_bybit_execution_quality_namespace,
        "latest_bybit_intraday_namespace": _latest_bybit_intraday_namespace,
        "latest_bybit_derivatives_namespace": _latest_bybit_derivatives_namespace,
        "latest_outcome_price_recovery_namespace": _latest_outcome_price_recovery_namespace,
    }
    for selector in policy["dynamic_namespace_selectors"]:
        kind = str(selector["kind"])
        control_name = str(selector["path"])
        control_path = artifact_root / control_name
        if control_path not in eligible:
            selector_results.append(
                {"kind": kind, "path": control_name, "status": "control_missing"}
            )
            continue
        payload = _verified_file_bytes_bounded(
            control_path,
            root=root,
            maximum=4 * 1024 * 1024,
        )
        if kind == "review_timing_source_namespaces":
            from crypto_rsi_scanner.event_alpha.operations.decision_review_timing import (
                DecisionReviewTimingError,
                validate_review_timing_sources,
            )

            try:
                validation = validate_review_timing_sources(artifact_root)
            except DecisionReviewTimingError as exc:
                raise ValueError("Decision review-timing evidence is invalid") from exc
            if validation.get("ledger_sha256") != hashlib.sha256(payload).hexdigest():
                raise ValueError("Decision review-timing ledger changed during export")
            namespaces = validation.get("source_namespaces")
            if (
                not isinstance(namespaces, list)
                or len(namespaces)
                > limits["max_review_timing_source_namespaces"]
                or any(
                    not isinstance(namespace, str) or not namespace
                    for namespace in namespaces
                )
            ):
                raise ValueError("Decision review-timing source namespace bound invalid")
            for namespace in namespaces:
                directory = artifact_root / namespace
                directory_inventory = _strict_regular_files_under(
                    directory,
                    root=root,
                    max_file_count=limits["max_standard_artifact_file_count"],
                    max_total_bytes=limits["max_standard_artifact_total_bytes"],
                    max_single_file_bytes=limits["max_single_artifact_file_bytes"],
                )
                directory_paths = {
                    path for path in directory_inventory if not _skip(path, root=root)
                }
                if not directory_paths or not directory_paths <= eligible:
                    raise ValueError(
                        "Decision review-timing source namespace is incomplete or unsafe"
                    )
                selected.update(directory_paths)
                for path in directory_paths:
                    roles[path] = selector_roles[kind]
            validation_result = dict(validation)
            validation_status = validation_result.pop("status", None)
            selector_results.append(
                {
                    "kind": kind,
                    "path": control_name,
                    **validation_result,
                    "source_validation_status": validation_status,
                    "status": (
                        "selected" if namespaces else "selected_empty"
                    ),
                }
            )
            continue
        namespace, result = selector_loaders[kind](payload)
        if kind == "latest_bybit_execution_quality_namespace":
            from crypto_rsi_scanner.event_alpha.operations.bybit_execution_quality_capture import (
                BybitExecutionQualityCaptureError,
                load_latest_bybit_execution_quality_capture,
            )

            try:
                validated_capture = load_latest_bybit_execution_quality_capture(
                    artifact_root
                )
            except BybitExecutionQualityCaptureError as exc:
                raise ValueError(
                    "latest Bybit execution-quality capture is invalid"
                ) from exc
            if validated_capture.get("artifact_namespace") != namespace:
                raise ValueError(
                    "latest Bybit execution-quality pointer/capture mismatch"
                )
        elif kind == "latest_bybit_intraday_namespace":
            from crypto_rsi_scanner.event_alpha.operations.bybit_intraday_capture import (
                BybitIntradayCaptureError,
                load_latest_bybit_intraday_capture,
            )

            try:
                validated_capture = load_latest_bybit_intraday_capture(
                    artifact_root
                )
            except BybitIntradayCaptureError as exc:
                raise ValueError("latest Bybit intraday capture is invalid") from exc
            if validated_capture.get("artifact_namespace") != namespace:
                raise ValueError("latest Bybit intraday pointer/capture mismatch")
        elif kind == "latest_bybit_derivatives_namespace":
            from crypto_rsi_scanner.event_alpha.operations.bybit_derivatives_context_capture import (
                BybitDerivativesContextCaptureError,
            )
            from crypto_rsi_scanner.event_alpha.operations.bybit_derivatives_context_capture_status import (
                load_latest_bybit_derivatives_context_capture,
            )

            try:
                validated_capture = load_latest_bybit_derivatives_context_capture(
                    artifact_root
                )
            except BybitDerivativesContextCaptureError as exc:
                raise ValueError("latest Bybit derivatives capture is invalid") from exc
            if validated_capture.get("artifact_namespace") != namespace:
                raise ValueError("latest Bybit derivatives pointer/capture mismatch")
        elif kind == "latest_outcome_price_recovery_namespace":
            from crypto_rsi_scanner.event_alpha.operations.outcome_price_recovery_capture import (
                OutcomePriceRecoveryError,
                load_latest_outcome_price_recovery_capture,
            )

            try:
                validated_capture = load_latest_outcome_price_recovery_capture(
                    artifact_root
                )
            except OutcomePriceRecoveryError as exc:
                raise ValueError(
                    "latest outcome-price recovery capture is invalid"
                ) from exc
            if validated_capture.get("artifact_namespace") != namespace:
                raise ValueError(
                    "latest outcome-price recovery pointer/capture mismatch"
                )
        directory = artifact_root / namespace
        directory_inventory = _strict_regular_files_under(
            directory,
            root=root,
            max_file_count=limits["max_standard_artifact_file_count"],
            max_total_bytes=limits["max_standard_artifact_total_bytes"],
            max_single_file_bytes=limits["max_single_artifact_file_bytes"],
        )
        directory_paths = {
            path for path in directory_inventory if not _skip(path, root=root)
        }
        if not directory_paths or not directory_paths <= eligible:
            raise ValueError("dynamic canonical artifact namespace is incomplete or unsafe")
        selected.update(directory_paths)
        for path in directory_paths:
            roles[path] = selector_roles[kind]
        selector_results.append({"kind": kind, "path": control_name, **result})

    delegated_paths: set[Path] = set()
    delegated_root = artifact_root / str(policy["delegated_empirical_subtree"])
    try:
        delegated_root.lstat()
    except FileNotFoundError:
        if empirical_plan is not None:
            raise ValueError("empirical export plan exists without delegated subtree")
    else:
        if empirical_plan is None:
            raise ValueError("delegated empirical subtree lacks its canonical policy")
        delegated_paths = set(empirical_plan["selected_lab_paths"])
        if not delegated_paths <= eligible:
            raise ValueError("delegated empirical selection is outside project inventory")
        selected.update(delegated_paths)
        for path in delegated_paths:
            roles[path] = "delegated_empirical_current"

    if not selected <= eligible:
        raise ValueError("project artifact selection is outside the eligible inventory")
    entries = []
    for path in sorted(selected, key=lambda item: item.relative_to(root).as_posix()):
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "role": roles[path],
                **_verified_file_fingerprint(path, root=root),
            }
        )
    if (
        len(entries) > limits["max_standard_artifact_file_count"]
        or sum(int(row["size_bytes"]) for row in entries)
        > limits["max_standard_artifact_total_bytes"]
    ):
        raise ValueError("canonical project artifact selection exceeds policy bounds")
    return {
        "all_artifact_paths": eligible,
        "delegated_empirical_path_count": len(delegated_paths),
        "entries": entries,
        "excluded_noise": excluded_noise,
        "missing_root_files": missing_root_files,
        "missing_shared_directories": missing_shared_directories,
        "policy": policy,
        "policy_sha256": hashlib.sha256(policy_raw).hexdigest(),
        "present_root_files": present_root_files,
        "present_shared_directories": present_shared_directories,
        "selected_artifact_paths": selected,
        "selector_results": selector_results,
    }


def _standard_project_artifact_manifest(plan: dict[str, object]) -> dict[str, object]:
    policy = plan["policy"]
    entries = plan["entries"]
    missing_root_files = plan["missing_root_files"]
    missing_shared_directories = plan["missing_shared_directories"]
    return {
        "all_eligible_artifact_count": len(plan["all_artifact_paths"]),
        "canonical_selection_is_closed": True,
        "canonical_source_coverage_status": (
            "complete"
            if not missing_root_files and not missing_shared_directories
            else "partial"
        ),
        "delegated_empirical_path_count": plan["delegated_empirical_path_count"],
        "entries": entries,
        "entry_count": len(entries),
        "excluded_history_count": len(plan["all_artifact_paths"])
        - len(plan["selected_artifact_paths"]),
        "excluded_noise": plan["excluded_noise"],
        "history_archive": {
            "available_via_separate_optional_export": True,
            "included_in_standard_export": False,
            "output_filename": policy["history_archive"]["output_filename"],
        },
        "local_artifacts_deleted_or_moved": False,
        "missing_canonical_root_files": missing_root_files,
        "missing_canonical_shared_directories": missing_shared_directories,
        "policy_sha256": plan["policy_sha256"],
        "present_canonical_root_files": plan["present_root_files"],
        "present_canonical_shared_directories": plan[
            "present_shared_directories"
        ],
        "research_only": True,
        "schema_id": "decision_radar.project_artifact_export_manifest",
        "schema_version": 1,
        "selector_results": plan["selector_results"],
    }


def _write_bytes_to_zip(
    zf: zipfile.ZipFile,
    data: bytes,
    arcname: str,
    *,
    now_ts: float,
) -> None:
    synthetic_stat = os.stat_result((stat.S_IFREG | 0o644, 0, 0, 0, 0, 0, len(data), 0, 0, 0))
    info = _zipinfo_for_stat(synthetic_stat, arcname, now_ts=now_ts)
    zf.writestr(info, data)


def _validate_fingerprinted_manifest(
    zip_path: Path,
    manifest: dict[str, object],
    *,
    manifest_archive_path: str,
) -> list[str]:
    bad: list[str] = []
    with zipfile.ZipFile(zip_path) as archive:
        try:
            actual_manifest = json.loads(archive.read(manifest_archive_path))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
            return [f"empirical_manifest_invalid:{manifest_archive_path}"]
        if actual_manifest != manifest:
            bad.append(f"empirical_manifest_drift:{manifest_archive_path}")
        for row in manifest.get("entries", []):
            if not isinstance(row, dict):
                bad.append("empirical_manifest_entry_invalid")
                continue
            name = str(row.get("path") or "")
            try:
                data = archive.read(name)
            except KeyError:
                bad.append(f"empirical_manifest_entry_missing:{name}")
                continue
            if len(data) != row.get("size_bytes"):
                bad.append(f"empirical_manifest_size_mismatch:{name}")
            if hashlib.sha256(data).hexdigest() != row.get("sha256"):
                bad.append(f"empirical_manifest_sha256_mismatch:{name}")
    return bad


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
    if not name:
        return "empty_name"
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        return "control_character_path"
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
    the conservative wall-clock-safe timestamp.  Without it, every entry uses
    the fixed ZIP epoch.  ZIP timestamps do not carry a timezone, so the large
    safety margin also keeps explicitly selected epochs safe when an archive
    created in Moscow is extracted on a UTC or UTC-12 review host.
    """

    current = time.time() if now_ts is None else float(now_ts)
    wall_clock_safe = max(current - DEFAULT_EXPORT_MTIME_SAFETY_MARGIN_SECONDS, MIN_ZIP_TIMESTAMP)
    raw_epoch = os.getenv("SOURCE_DATE_EPOCH", "").strip()
    if raw_epoch:
        try:
            return min(max(float(raw_epoch), MIN_ZIP_TIMESTAMP), wall_clock_safe)
        except ValueError:
            pass
    return min(DEFAULT_REPRODUCIBLE_EXPORT_TIMESTAMP, wall_clock_safe)


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
    # ZIP timestamps are timezone-less.  Use one UTC, reproducible timestamp for
    # every entry instead of leaking host mtimes into archive bytes or allowing
    # timezone reinterpretation to make extracted Makefiles appear future-dated.
    mtime = max(MIN_ZIP_TIMESTAMP, now_ts)
    info = zipfile.ZipInfo(
        arcname,
        datetime.fromtimestamp(mtime, timezone.utc).timetuple()[:6],
    )
    info.compress_type = zipfile.ZIP_DEFLATED
    # Source permissions are host/worktree metadata, not empirical evidence.
    # Normalize every regular entry so chmod and platform defaults cannot alter
    # otherwise identical review archives.
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
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


def _candidate_identity(file_stat: os.stat_result) -> tuple[int, int]:
    return file_stat.st_dev, file_stat.st_ino


def _open_output_parent(
    output: Path,
) -> tuple[Path, Path, int, os.stat_result]:
    """Open an existing output parent through its resolved descriptor path."""

    output_abs = Path(output).expanduser().absolute()
    if _unsafe_archive_name(output_abs.name) is not None:
        raise OSError(errno.EINVAL, "export output filename is unsafe")
    parent = output_abs.parent
    before = os.stat(parent, follow_symlinks=False)
    if not stat.S_ISDIR(before.st_mode):
        raise OSError(errno.ENOTDIR, "export output parent is not a directory")
    resolved = parent.resolve(strict=True)
    anchor = Path(resolved.anchor)
    descriptor, opened = _open_verified_directory(resolved, root=anchor)
    if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
        os.close(descriptor)
        raise OSError(_IDENTITY_CHANGED_ERRNO, "export output parent changed")
    return output_abs, resolved, descriptor, opened


def _recheck_output_parent(
    *,
    output: Path,
    resolved_parent: Path,
    parent_fd: int,
    parent_stat: os.stat_result,
) -> None:
    parent = output.parent
    current = os.stat(parent, follow_symlinks=False)
    opened = os.fstat(parent_fd)
    expected = (parent_stat.st_dev, parent_stat.st_ino)
    if (
        not stat.S_ISDIR(current.st_mode)
        or not stat.S_ISDIR(opened.st_mode)
        or (current.st_dev, current.st_ino) != expected
        or (opened.st_dev, opened.st_ino) != expected
        or parent.resolve(strict=True) != resolved_parent
    ):
        raise OSError(_IDENTITY_CHANGED_ERRNO, "export output parent identity drifted")
    reopened_fd, reopened = _open_verified_directory(
        resolved_parent, root=Path(resolved_parent.anchor)
    )
    try:
        if (reopened.st_dev, reopened.st_ino) != expected:
            raise OSError(
                _IDENTITY_CHANGED_ERRNO,
                "export output parent changed during recheck",
            )
    finally:
        os.close(reopened_fd)


def _owned_candidate_matches_at(
    parent_fd: int,
    candidate_name: str,
    identity: tuple[int, int] | None,
) -> bool:
    if identity is None:
        return False
    try:
        current = os.stat(candidate_name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return stat.S_ISREG(current.st_mode) and _candidate_identity(current) == identity


def _unlink_owned_candidate_at(
    parent_fd: int,
    candidate_name: str,
    identity: tuple[int, int] | None,
) -> None:
    if _owned_candidate_matches_at(parent_fd, candidate_name, identity):
        os.unlink(candidate_name, dir_fd=parent_fd)


def _start_output_transaction(
    output: Path,
) -> tuple[Path, Path, int, os.stat_result, str, int, int, tuple[int, int]]:
    output_abs, resolved_parent, parent_fd, parent_stat = _open_output_parent(output)
    candidate_name = f"{output_abs.name}.tmp"
    if _unsafe_archive_name(candidate_name) is not None:
        os.close(parent_fd)
        raise OSError(errno.EINVAL, "export candidate filename is unsafe")
    flags = (
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(candidate_name, flags, 0o600, dir_fd=parent_fd)
    except BaseException:
        os.close(parent_fd)
        raise
    candidate_identity: tuple[int, int] | None = None
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise OSError(errno.EINVAL, "export candidate is not a regular file")
        candidate_identity = _candidate_identity(opened)
        validation_fd = os.dup(descriptor)
    except BaseException:
        os.close(descriptor)
        _unlink_owned_candidate_at(parent_fd, candidate_name, candidate_identity)
        os.close(parent_fd)
        raise
    return (
        output_abs,
        resolved_parent,
        parent_fd,
        parent_stat,
        candidate_name,
        descriptor,
        validation_fd,
        candidate_identity,
    )


def _publish_output_transaction(
    *,
    output: Path,
    resolved_parent: Path,
    parent_fd: int,
    parent_stat: os.stat_result,
    candidate_name: str,
    candidate_identity: tuple[int, int],
) -> None:
    _recheck_output_parent(
        output=output,
        resolved_parent=resolved_parent,
        parent_fd=parent_fd,
        parent_stat=parent_stat,
    )
    if not _owned_candidate_matches_at(
        parent_fd, candidate_name, candidate_identity
    ):
        raise OSError(_IDENTITY_CHANGED_ERRNO, "export candidate changed")
    os.rename(
        candidate_name,
        output.name,
        src_dir_fd=parent_fd,
        dst_dir_fd=parent_fd,
    )
    published = os.stat(output.name, dir_fd=parent_fd, follow_symlinks=False)
    if (
        not stat.S_ISREG(published.st_mode)
        or _candidate_identity(published) != candidate_identity
    ):
        raise OSError(_IDENTITY_CHANGED_ERRNO, "published export identity drifted")


def _fingerprinted_sources_drift(
    root: Path, entries: list[dict[str, object]], *, label: str
) -> list[str]:
    bad: list[str] = []
    for row in entries:
        name = str(row.get("path") or "")
        try:
            relative = _policy_relative_path(name, field="fingerprinted source")
            actual = _verified_file_fingerprint(root / relative, root=root)
        except (OSError, ValueError):
            bad.append(f"{label}_source_unavailable:{name}")
            continue
        if actual.get("size_bytes") != row.get("size_bytes"):
            bad.append(f"{label}_source_size_drift:{name}")
        if actual.get("sha256") != row.get("sha256"):
            bad.append(f"{label}_source_sha256_drift:{name}")
    return bad


def empirical_history_main(
    root: Path = ROOT,
    out: Path | None = None,
) -> int:
    """Write the fixed optional archive of non-canonical empirical history."""

    output = Path(root).expanduser().absolute() / EMPIRICAL_HISTORY_OUTPUT_FILENAME
    resolved_parent = output.parent
    parent_fd = -1
    parent_stat: os.stat_result | None = None
    candidate_name = f"{output.name}.tmp"
    candidate_identity: tuple[int, int] | None = None
    validation_fd = -1
    try:
        plan = _empirical_export_plan(root)
        if plan is None or not plan["all_lab_paths"]:
            raise ValueError("empirical artifact history is unavailable")
        policy = plan["policy"]
        history_policy = policy["history_archive"]
        fixed_output = (
            Path(root).expanduser().absolute()
            / str(history_policy["output_filename"])
        )
        output = (
            Path(out).expanduser().absolute() if out is not None else fixed_output
        )
        if output != fixed_output:
            raise ValueError("empirical history output path is not fixed")
        history_paths = set(plan["all_lab_paths"]) - set(plan["selected_lab_paths"])
        entries: list[dict[str, object]] = []
        for path in sorted(history_paths, key=lambda item: item.relative_to(root).as_posix()):
            relative = path.relative_to(root).as_posix()
            lab_parts = PurePosixPath(relative).parts
            semantic_ids: dict[str, object] = {"historical": True}
            role = "superseded_empirical_artifact"
            try:
                runs_index = lab_parts.index("runs")
            except ValueError:
                runs_index = -1
            if runs_index >= 0 and len(lab_parts) > runs_index + 1:
                semantic_ids["run_fingerprint"] = lab_parts[runs_index + 1]
                role = "superseded_run_artifact"
            if "superseded_reports" in lab_parts:
                role = "superseded_report_artifact"
            entries.append(
                {
                    "path": relative,
                    "role": role,
                    "semantic_ids": semantic_ids,
                    **_verified_file_fingerprint(path, root=root),
                }
            )
        limits = policy["limits"]
        if (
            len(entries) > limits["max_history_file_count"]
            or sum(int(row["size_bytes"]) for row in entries)
            > limits["max_history_total_bytes"]
            or set(plan["selected_lab_paths"]) & history_paths
            or set(plan["selected_lab_paths"]) | history_paths
            != set(plan["all_lab_paths"])
        ):
            raise ValueError("empirical history complement exceeds or violates policy")
        history_manifest = {
            "canonical_evidence_included": False,
            "canonical_refs": policy["canonical_semantics"],
            "canonical_runs": [
                {
                    "role": row["role"],
                    "run_fingerprint": row["run_fingerprint"],
                }
                for row in policy["canonical_runs"]
            ],
            "complement_of_standard_empirical_selection": True,
            "entries": entries,
            "entry_count": len(entries),
            "immutable_history": True,
            "local_artifacts_deleted_or_moved": False,
            "policy_sha256": plan["policy_sha256"],
            "research_only": True,
            "schema_id": "decision_radar.empirical_artifact_history_manifest",
            "schema_version": 1,
            "standard_manifest_archive_path": policy[
                "standard_manifest_archive_path"
            ],
        }
        checksums = "".join(
            f"{row['sha256']}  {row['path']}\n" for row in entries
        ).encode("utf-8")
        manifest_archive_path = str(history_policy["manifest_archive_path"])
        checksums_archive_path = str(history_policy["checksums_archive_path"])
        source_archive_names = {str(row["path"]) for row in entries}
        if (
            manifest_archive_path in source_archive_names
            or checksums_archive_path in source_archive_names
            or manifest_archive_path == checksums_archive_path
        ):
            raise ValueError("empirical history synthetic archive paths collide")
        now_ts = _safe_export_timestamp()
        (
            output,
            resolved_parent,
            parent_fd,
            parent_stat,
            candidate_name,
            descriptor,
            validation_fd,
            candidate_identity,
        ) = _start_output_transaction(output)
        with os.fdopen(descriptor, "w+b") as candidate_file:
            with zipfile.ZipFile(
                candidate_file,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            ) as archive:
                for path in sorted(
                    history_paths, key=lambda item: item.relative_to(root).as_posix()
                ):
                    _write_file_to_zip(
                        archive,
                        path,
                        path.relative_to(root).as_posix(),
                        now_ts=now_ts,
                        root=root,
                    )
                _write_bytes_to_zip(
                    archive,
                    _canonical_json_bytes(history_manifest),
                    manifest_archive_path,
                    now_ts=now_ts,
                )
                _write_bytes_to_zip(
                    archive,
                    checksums,
                    checksums_archive_path,
                    now_ts=now_ts,
                )
            candidate_file.flush()
            os.fsync(candidate_file.fileno())

        with os.fdopen(os.dup(validation_fd), "rb") as candidate_reader:
            bad = _validate_archive_entries(
                candidate_reader,
                safe_export_timestamp=now_ts,
                sensitive_values=_configured_sensitive_values(root),
            )
        with os.fdopen(os.dup(validation_fd), "rb") as candidate_reader:
            bad.extend(
                _validate_fingerprinted_manifest(
                    candidate_reader,
                    history_manifest,
                    manifest_archive_path=manifest_archive_path,
                )
            )
        with os.fdopen(os.dup(validation_fd), "rb") as candidate_reader:
            with zipfile.ZipFile(candidate_reader) as archive:
                names = archive.namelist()
                expected_names = {
                    *(path.relative_to(root).as_posix() for path in history_paths),
                    manifest_archive_path,
                    checksums_archive_path,
                }
                if set(names) != expected_names:
                    bad.append("empirical_history_not_exact_complement")
                if archive.read(checksums_archive_path) != checksums:
                    bad.append("empirical_history_checksums_drift")
        if parent_stat is None:
            raise OSError(errno.EIO, "empirical history parent state is missing")
        _recheck_output_parent(
            output=output,
            resolved_parent=resolved_parent,
            parent_fd=parent_fd,
            parent_stat=parent_stat,
        )
        lab_root = root / _policy_relative_path(policy["lab_root"], field="lab_root")
        if _strict_regular_files_under(
            lab_root,
            root=root,
            max_file_count=limits["max_lab_file_count"],
            max_total_bytes=limits["max_lab_total_bytes"],
            max_single_file_bytes=limits["max_single_empirical_file_bytes"],
        ) != set(plan["all_lab_paths"]):
            bad.append("empirical_history_source_tree_drift")
        bad.extend(
            _fingerprinted_sources_drift(
                root, entries, label="empirical_history"
            )
        )
        canonical_prefixes = {
            (
                f"{policy['lab_root']}/runs/"
                f"{run_policy['run_fingerprint']}/"
            )
            for run_policy in policy["canonical_runs"]
        }
        if any(
            name.startswith(prefix)
            for name in names
            for prefix in canonical_prefixes
        ):
            bad.append("empirical_history_contains_canonical_run")
        print(output)
        print(f"size_bytes={os.fstat(validation_fd).st_size}")
        print(f"history_entries={len(entries)}")
        print(
            "history_source_bytes="
            f"{sum(int(row['size_bytes']) for row in entries)}"
        )
        print(
            "history_manifest_sha256="
            f"{hashlib.sha256(_canonical_json_bytes(history_manifest)).hexdigest()}"
        )
        print(f"bad_entries={len(bad)}")
        if bad:
            print("\n".join(bad[:50]))
            _unlink_owned_candidate_at(parent_fd, candidate_name, candidate_identity)
            return 1
        _publish_output_transaction(
            output=output,
            resolved_parent=resolved_parent,
            parent_fd=parent_fd,
            parent_stat=parent_stat,
            candidate_name=candidate_name,
            candidate_identity=candidate_identity,
        )
        return 0
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        print(f"empirical_history_export_failed_closed={type(exc).__name__}")
        if parent_fd >= 0:
            _unlink_owned_candidate_at(parent_fd, candidate_name, candidate_identity)
        return 1
    finally:
        if validation_fd >= 0:
            os.close(validation_fd)
        if parent_fd >= 0:
            os.close(parent_fd)


def project_history_main(
    root: Path = ROOT,
    out: Path | None = None,
) -> int:
    """Write the fixed optional archive of all non-canonical project artifacts."""

    output = Path(root).expanduser().absolute() / PROJECT_HISTORY_OUTPUT_FILENAME
    resolved_parent = output.parent
    parent_fd = -1
    parent_stat: os.stat_result | None = None
    candidate_name = f"{output.name}.tmp"
    candidate_identity: tuple[int, int] | None = None
    validation_fd = -1
    try:
        empirical_plan = _empirical_export_plan(root)
        plan = _project_artifact_export_plan(
            root,
            empirical_plan=empirical_plan,
        )
        if plan is None or not plan["all_artifact_paths"]:
            raise ValueError("project artifact history is unavailable")
        policy = plan["policy"]
        history_policy = policy["history_archive"]
        fixed_output = (
            Path(root).expanduser().absolute()
            / str(history_policy["output_filename"])
        )
        output = Path(out).expanduser().absolute() if out is not None else fixed_output
        if output != fixed_output:
            raise ValueError("project artifact history output path is not fixed")
        selected_paths = set(plan["selected_artifact_paths"])
        history_paths = set(plan["all_artifact_paths"]) - selected_paths
        entries: list[dict[str, object]] = []
        for path in sorted(
            history_paths, key=lambda item: item.relative_to(root).as_posix()
        ):
            relative = path.relative_to(root)
            artifact_relative = relative.relative_to(
                PROJECT_ARTIFACT_ROOT_RELATIVE_PATH
            )
            if str(artifact_relative).startswith("decision_radar_research_lab/"):
                role = "delegated_empirical_history"
            elif len(artifact_relative.parts) == 1:
                role = "historical_or_noncanonical_root_artifact"
            else:
                role = "noncanonical_namespace_artifact"
            entries.append(
                {
                    "path": relative.as_posix(),
                    "role": role,
                    "semantic_ids": {"historical_or_noncanonical": True},
                    **_verified_file_fingerprint(path, root=root),
                }
            )
        limits = policy["limits"]
        if (
            len(entries) > limits["max_history_file_count"]
            or sum(int(row["size_bytes"]) for row in entries)
            > limits["max_history_total_bytes"]
            or selected_paths & history_paths
            or selected_paths | history_paths != set(plan["all_artifact_paths"])
        ):
            raise ValueError("project artifact history complement violates policy")
        standard_manifest = _standard_project_artifact_manifest(plan)
        history_manifest = {
            "canonical_artifacts_included": False,
            "canonical_entry_count": len(plan["entries"]),
            "canonical_manifest_sha256": hashlib.sha256(
                _canonical_json_bytes(standard_manifest)
            ).hexdigest(),
            "complement_of_standard_project_selection": True,
            "entries": entries,
            "entry_count": len(entries),
            "excluded_noise": plan["excluded_noise"],
            "immutable_history": True,
            "local_artifacts_deleted_or_moved": False,
            "policy_sha256": plan["policy_sha256"],
            "research_only": True,
            "schema_id": "decision_radar.project_artifact_history_manifest",
            "schema_version": 1,
            "standard_manifest_archive_path": policy[
                "standard_manifest_archive_path"
            ],
        }
        checksums = "".join(
            f"{row['sha256']}  {row['path']}\n" for row in entries
        ).encode("utf-8")
        manifest_archive_path = str(history_policy["manifest_archive_path"])
        checksums_archive_path = str(history_policy["checksums_archive_path"])
        source_names = {str(row["path"]) for row in entries}
        if (
            manifest_archive_path in source_names
            or checksums_archive_path in source_names
            or manifest_archive_path == checksums_archive_path
        ):
            raise ValueError("project history synthetic archive paths collide")
        now_ts = _safe_export_timestamp()
        (
            output,
            resolved_parent,
            parent_fd,
            parent_stat,
            candidate_name,
            descriptor,
            validation_fd,
            candidate_identity,
        ) = _start_output_transaction(output)
        with os.fdopen(descriptor, "w+b") as candidate_file:
            with zipfile.ZipFile(
                candidate_file,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            ) as archive:
                for path in sorted(
                    history_paths,
                    key=lambda item: item.relative_to(root).as_posix(),
                ):
                    _write_file_to_zip(
                        archive,
                        path,
                        path.relative_to(root).as_posix(),
                        now_ts=now_ts,
                        root=root,
                    )
                _write_bytes_to_zip(
                    archive,
                    _canonical_json_bytes(history_manifest),
                    manifest_archive_path,
                    now_ts=now_ts,
                )
                _write_bytes_to_zip(
                    archive,
                    checksums,
                    checksums_archive_path,
                    now_ts=now_ts,
                )
            candidate_file.flush()
            os.fsync(candidate_file.fileno())

        with os.fdopen(os.dup(validation_fd), "rb") as candidate_reader:
            bad = _validate_archive_entries(
                candidate_reader,
                safe_export_timestamp=now_ts,
                sensitive_values=_configured_sensitive_values(root),
            )
        with os.fdopen(os.dup(validation_fd), "rb") as candidate_reader:
            bad.extend(
                _validate_fingerprinted_manifest(
                    candidate_reader,
                    history_manifest,
                    manifest_archive_path=manifest_archive_path,
                )
            )
        with os.fdopen(os.dup(validation_fd), "rb") as candidate_reader:
            with zipfile.ZipFile(candidate_reader) as archive:
                names = archive.namelist()
                expected_names = {
                    *(path.relative_to(root).as_posix() for path in history_paths),
                    manifest_archive_path,
                    checksums_archive_path,
                }
                if set(names) != expected_names:
                    bad.append("project_history_not_exact_complement")
                if archive.read(checksums_archive_path) != checksums:
                    bad.append("project_history_checksums_drift")
        if parent_stat is None:
            raise OSError(errno.EIO, "project history parent state is missing")
        _recheck_output_parent(
            output=output,
            resolved_parent=resolved_parent,
            parent_fd=parent_fd,
            parent_stat=parent_stat,
        )
        current_inventory = {
            path
            for path in _strict_regular_files_under(
                root / PROJECT_ARTIFACT_ROOT_RELATIVE_PATH,
                root=root,
                max_file_count=limits["max_artifact_file_count"],
                max_total_bytes=limits["max_artifact_total_bytes"],
                max_single_file_bytes=limits["max_single_artifact_file_bytes"],
            )
            if not _skip(path, root=root)
        }
        if current_inventory != set(plan["all_artifact_paths"]):
            bad.append("project_history_source_tree_drift")
        bad.extend(
            _fingerprinted_sources_drift(root, entries, label="project_history")
        )
        canonical_names = {
            path.relative_to(root).as_posix() for path in selected_paths
        }
        if canonical_names & set(names):
            bad.append("project_history_contains_canonical_artifact")
        print(output)
        print(f"size_bytes={os.fstat(validation_fd).st_size}")
        print(f"history_entries={len(entries)}")
        print(
            "history_source_bytes="
            f"{sum(int(row['size_bytes']) for row in entries)}"
        )
        print(
            "history_manifest_sha256="
            f"{hashlib.sha256(_canonical_json_bytes(history_manifest)).hexdigest()}"
        )
        print(f"bad_entries={len(bad)}")
        if bad:
            print("\n".join(bad[:50]))
            _unlink_owned_candidate_at(parent_fd, candidate_name, candidate_identity)
            return 1
        _publish_output_transaction(
            output=output,
            resolved_parent=resolved_parent,
            parent_fd=parent_fd,
            parent_stat=parent_stat,
            candidate_name=candidate_name,
            candidate_identity=candidate_identity,
        )
        return 0
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        print(f"project_history_export_failed_closed={type(exc).__name__}")
        if parent_fd >= 0:
            _unlink_owned_candidate_at(parent_fd, candidate_name, candidate_identity)
        return 1
    finally:
        if validation_fd >= 0:
            os.close(validation_fd)
        if parent_fd >= 0:
            os.close(parent_fd)


def main(root: Path = ROOT, out: Path = OUT) -> int:
    try:
        paths = _tracked_paths(root)
        empirical_plan = _empirical_export_plan(root)
        project_plan = _project_artifact_export_plan(
            root,
            empirical_plan=empirical_plan,
        )
        if project_plan is not None:
            paths |= set(project_plan["selected_artifact_paths"])
        else:
            paths |= _artifact_paths(root)
        if empirical_plan is not None:
            paths |= set(empirical_plan.get("tracked_paths", set()))
    except (OSError, ValueError) as exc:
        print(f"export_failed_closed={type(exc).__name__}")
        return 1
    entries = [
        path
        for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix())
        if _safe_regular_file(path, root=root) and not _skip(path, root=root)
    ]

    now_ts = _safe_export_timestamp()
    # Export must be read-only with respect to source and research artifacts.
    # Archive timestamps are normalized in ZipInfo, not by mutating inputs.
    normalized_mtimes = 0
    output = Path(out).expanduser().absolute()
    resolved_parent = output.parent
    parent_fd = -1
    parent_stat: os.stat_result | None = None
    candidate_name = f"{output.name}.tmp"
    candidate_identity: tuple[int, int] | None = None
    validation_fd = -1
    try:
        (
            output,
            resolved_parent,
            parent_fd,
            parent_stat,
            candidate_name,
            descriptor,
            validation_fd,
            candidate_identity,
        ) = _start_output_transaction(output)
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
                if empirical_plan is not None and empirical_plan["all_lab_paths"]:
                    empirical_manifest = _standard_empirical_manifest(empirical_plan)
                    _write_bytes_to_zip(
                        zf,
                        _canonical_json_bytes(empirical_manifest),
                        str(
                            empirical_plan["policy"][
                                "standard_manifest_archive_path"
                            ]
                        ),
                        now_ts=now_ts,
                    )
                if project_plan is not None:
                    project_manifest = _standard_project_artifact_manifest(
                        project_plan
                    )
                    _write_bytes_to_zip(
                        zf,
                        _canonical_json_bytes(project_manifest),
                        str(
                            project_plan["policy"][
                                "standard_manifest_archive_path"
                            ]
                        ),
                        now_ts=now_ts,
                    )
            candidate_file.flush()
            os.fsync(candidate_file.fileno())
    except (OSError, ValueError) as exc:
        print(f"export_failed_closed={type(exc).__name__}")
        if parent_fd >= 0:
            _unlink_owned_candidate_at(parent_fd, candidate_name, candidate_identity)
            os.close(parent_fd)
        if validation_fd >= 0:
            os.close(validation_fd)
        return 1

    try:
        with os.fdopen(os.dup(validation_fd), "rb") as candidate_reader:
            with zipfile.ZipFile(candidate_reader) as zf:
                names = zf.namelist()
        with os.fdopen(os.dup(validation_fd), "rb") as candidate_reader:
            bad = _validate_archive_entries(
                candidate_reader,
                safe_export_timestamp=now_ts,
                sensitive_values=_configured_sensitive_values(root),
            )
        if empirical_plan is not None and empirical_plan["all_lab_paths"]:
            empirical_manifest = _standard_empirical_manifest(empirical_plan)
            with os.fdopen(os.dup(validation_fd), "rb") as candidate_reader:
                bad.extend(
                    _validate_fingerprinted_manifest(
                        candidate_reader,
                        empirical_manifest,
                        manifest_archive_path=str(
                            empirical_plan["policy"]["standard_manifest_archive_path"]
                        ),
                    )
                )
            bad.extend(
                _fingerprinted_sources_drift(
                    root, empirical_manifest["entries"], label="empirical_standard"
                )
            )
        if project_plan is not None:
            project_manifest = _standard_project_artifact_manifest(project_plan)
            project_manifest_path = str(
                project_plan["policy"]["standard_manifest_archive_path"]
            )
            with os.fdopen(os.dup(validation_fd), "rb") as candidate_reader:
                bad.extend(
                    _validate_fingerprinted_manifest(
                        candidate_reader,
                        project_manifest,
                        manifest_archive_path=project_manifest_path,
                    )
                )
            bad.extend(
                _fingerprinted_sources_drift(
                    root, project_manifest["entries"], label="project_standard"
                )
            )
            limits = project_plan["policy"]["limits"]
            current_inventory = {
                path
                for path in _strict_regular_files_under(
                    root / PROJECT_ARTIFACT_ROOT_RELATIVE_PATH,
                    root=root,
                    max_file_count=limits["max_artifact_file_count"],
                    max_total_bytes=limits["max_artifact_total_bytes"],
                    max_single_file_bytes=limits[
                        "max_single_artifact_file_bytes"
                    ],
                )
                if not _skip(path, root=root)
            }
            if current_inventory != set(project_plan["all_artifact_paths"]):
                bad.append("project_standard_source_tree_drift")
            expected_project_names = {
                str(row["path"]) for row in project_manifest["entries"]
            }
            actual_project_names = {
                name
                for name in names
                if name.startswith("event_fade_cache/")
                and name
                not in {
                    project_manifest_path,
                    EMPIRICAL_STANDARD_MANIFEST_ARCHIVE_PATH.as_posix(),
                }
            }
            if actual_project_names != expected_project_names:
                bad.append("project_standard_selection_drift")
        if parent_stat is None:
            raise OSError(errno.EIO, "export output parent state is missing")
        _recheck_output_parent(
            output=output,
            resolved_parent=resolved_parent,
            parent_fd=parent_fd,
            parent_stat=parent_stat,
        )
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        print(f"export_failed_closed={type(exc).__name__}")
        _unlink_owned_candidate_at(parent_fd, candidate_name, candidate_identity)
        os.close(validation_fd)
        os.close(parent_fd)
        return 1
    artifact_entries = [name for name in names if name.startswith("event_fade_cache/")]
    research_cards = [
        name
        for name in artifact_entries
        if "/research_cards/" in name and name.endswith(".md") and not name.endswith("/index.md")
    ]

    print(output)
    print(f"size_bytes={os.fstat(validation_fd).st_size}")
    print(f"entries={len(names)}")
    print(f"artifact_entries={len(artifact_entries)}")
    print(f"research_card_files={len(research_cards)}")
    print(f"normalized_mtimes={normalized_mtimes}")
    if empirical_plan is not None and empirical_plan["all_lab_paths"]:
        print(f"empirical_canonical_entries={len(empirical_plan['manifest_entries'])}")
        print(
            "empirical_history_entries_excluded="
            f"{len(empirical_plan['all_lab_paths'] - empirical_plan['selected_lab_paths'])}"
        )
        print(
            "empirical_manifest_sha256="
            f"{hashlib.sha256(_canonical_json_bytes(_standard_empirical_manifest(empirical_plan))).hexdigest()}"
        )
    if project_plan is not None:
        project_manifest = _standard_project_artifact_manifest(project_plan)
        print(f"project_canonical_entries={len(project_plan['entries'])}")
        print(
            "project_history_entries_excluded="
            f"{project_manifest['excluded_history_count']}"
        )
        print(
            "project_manifest_sha256="
            f"{hashlib.sha256(_canonical_json_bytes(project_manifest)).hexdigest()}"
        )
    print(f"bad_entries={len(bad)}")
    if bad:
        print("\n".join(bad[:50]))
        _unlink_owned_candidate_at(parent_fd, candidate_name, candidate_identity)
        os.close(validation_fd)
        os.close(parent_fd)
        return 1
    try:
        if parent_stat is None or candidate_identity is None:
            raise OSError(errno.EIO, "export transaction state is incomplete")
        _publish_output_transaction(
            output=output,
            resolved_parent=resolved_parent,
            parent_fd=parent_fd,
            parent_stat=parent_stat,
            candidate_name=candidate_name,
            candidate_identity=candidate_identity,
        )
    except OSError as exc:
        print(f"export_failed_closed={type(exc).__name__}")
        _unlink_owned_candidate_at(parent_fd, candidate_name, candidate_identity)
        os.close(validation_fd)
        os.close(parent_fd)
        return 1
    os.close(validation_fd)
    os.close(parent_fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
