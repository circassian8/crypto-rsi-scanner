"""Exact latest-attempt receipts for safe Make orchestration."""

from __future__ import annotations

import fcntl
import os
import re
import stat
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from . import market_no_send_campaign_guard
from .market_no_send_io import (
    _open_verified_namespace_dir,
    read_json_object,
    read_jsonl,
    safe_existing_namespace_dir,
    write_json_atomic,
    write_jsonl,
)
from .market_no_send_models import MarketNoSendError, MarketNoSendGenerationResult


LATEST_ATTEMPT_FILENAME = "event_market_no_send_latest_attempt.json"
ATTEMPT_LEDGER_FILENAME = "event_market_no_send_attempts.jsonl"
ATTEMPT_LEDGER_MAX_ROWS = 2_048
_ATTEMPT_LOCK_FILENAME = ".event_market_no_send_attempts.lock"
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_SAFE_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SECRET_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "credential",
    "password",
    "secret",
    "token",
)


def record_attempt(base: Path, namespace: str, result: MarketNoSendGenerationResult) -> Path:
    """Persist one sanitized run row and replace the exact latest receipt.

    The bounded ledger is rewritten atomically while a root-scoped advisory
    lock is held.  This prevents simultaneous blocked/successful CLI results
    from losing one another during the read-modify-write operation.
    """

    root = Path(base).expanduser().absolute()
    canonical_namespace = _namespace_text(namespace)
    if canonical_namespace != _namespace_text(
        result.artifact_namespace,
    ):
        raise MarketNoSendError("market no-send attempt namespace mismatch")
    attempt_id = uuid.uuid4().hex
    common = {
        "contract_version": 1,
        "attempt_id": attempt_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "artifact_namespace": canonical_namespace,
        "status": _safe_token(result.status, fallback="unknown"),
        "observed_at": _timestamp_text(result.observed_at),
        "run_id": _optional_identity_text(result.run_id, field_name="run_id"),
        "provider": _safe_provider(result.provider),
        "data_mode": _safe_token(result.data_mode, fallback="unknown"),
        "data_acquisition_mode": _safe_token(
            result.data_acquisition_mode,
            fallback="preflight_only",
        ),
        "provider_call_attempted": result.provider_call_attempted is True,
        "provider_request_succeeded": result.provider_request_succeeded is True,
        "candidate_source_mode": _safe_token(
            result.candidate_source_mode,
            fallback="preflight_only",
        ),
        "failure_class": _safe_failure_class(result.failure_class),
        "measurement_program": _safe_token(result.measurement_program, fallback=""),
        "decision_radar_campaign_counted": result.decision_radar_campaign_counted is True,
        "burn_in_counted": result.burn_in_counted is True,
        "no_send": True,
        "research_only": True,
    }
    latest = {
        **common,
        "row_type": "event_market_no_send_latest_attempt",
    }
    ledger_row = {
        **common,
        "row_type": "event_market_no_send_attempt",
    }
    latest_path = root / LATEST_ATTEMPT_FILENAME
    ledger_path = root / ATTEMPT_LEDGER_FILENAME
    with _attempt_history_lock(root):
        try:
            rows = read_jsonl(ledger_path)
        except (UnicodeDecodeError, ValueError) as exc:
            raise MarketNoSendError("market no-send attempt ledger is invalid") from exc
        retained = [*rows, ledger_row][-ATTEMPT_LEDGER_MAX_ROWS:]
        # Write history first: a latest-receipt failure must never erase the
        # fact that this CLI result occurred.
        write_jsonl(ledger_path, retained)
        write_json_atomic(latest_path, latest)
    return latest_path


def record_boundary_failure(
    base: Path,
    namespace: str,
    *,
    failure: BaseException,
    manifest_filename: str,
) -> Path:
    """Record a sanitized CLI failure even when generation returned no result."""

    root = Path(base).expanduser().absolute()
    canonical_namespace = _namespace_text(namespace)
    manifest: dict[str, Any] = {}
    namespace_dir: Path | None = None
    try:
        namespace_dir = safe_existing_namespace_dir(root, canonical_namespace)
        manifest = read_json_object(namespace_dir / manifest_filename)
    except (MarketNoSendError, OSError, ValueError):
        manifest = {}
    provider_call_attempted = bool(
        manifest.get("provider_call_attempted") is True
        or market_no_send_campaign_guard.provider_call_may_have_been_reserved(
            root,
            artifact_namespace=canonical_namespace,
        )
    )
    observed_at = manifest.get("observed_at")
    try:
        observed_text = _timestamp_text(observed_at)
    except MarketNoSendError:
        observed_text = datetime.now(timezone.utc).isoformat()
    result = MarketNoSendGenerationResult(
        status="boundary_failed",
        profile=_safe_token(manifest.get("profile"), fallback="no_key_live"),
        artifact_namespace=canonical_namespace,
        namespace_dir=namespace_dir,
        data_mode=_safe_token(manifest.get("data_mode"), fallback="live"),
        provider=_safe_provider(manifest.get("provider") or "coingecko"),
        observed_at=observed_text,
        live_provider_authorized=manifest.get("live_provider_authorized") is True,
        provider_call_attempted=provider_call_attempted,
        provider_request_succeeded=manifest.get("provider_request_succeeded") is True,
        run_id=_optional_identity_text(manifest.get("run_id"), field_name="run_id"),
        failure_class=type(failure).__name__,
        measurement_program=_safe_token(manifest.get("measurement_program"), fallback=""),
        decision_radar_campaign_counted=False,
        burn_in_counted=False,
        data_acquisition_mode=(
            "live_provider" if provider_call_attempted else "preflight_only"
        ),
        candidate_source_mode="preflight_only",
    )
    return record_attempt(root, canonical_namespace, result)


@contextmanager
def _attempt_history_lock(base: Path) -> Iterator[None]:
    """Serialize root-level latest/ledger updates through a verified fd."""

    descriptor: int | None = None
    locked = False
    try:
        with _open_verified_namespace_dir(base) as anchored:
            _base_fd, namespace_fd, _namespace, _identity = anchored
            flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
            descriptor = os.open(_ATTEMPT_LOCK_FILENAME, flags, 0o600, dir_fd=namespace_fd)
            opened = os.fstat(descriptor)
            current = os.stat(
                _ATTEMPT_LOCK_FILENAME,
                dir_fd=namespace_fd,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
            ):
                raise MarketNoSendError("market no-send attempt lock identity changed")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            locked = True
            yield
    except MarketNoSendError:
        raise
    except OSError as exc:
        raise MarketNoSendError("market no-send attempt history is unavailable") from exc
    finally:
        if locked and descriptor is not None:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        if descriptor is not None:
            os.close(descriptor)


def _safe_token(value: object, *, fallback: str) -> str:
    text = str(value or "").strip()
    return text if _SAFE_TOKEN_RE.fullmatch(text) else fallback


def _safe_failure_class(value: object) -> str | None:
    if value in (None, ""):
        return None
    supplied = str(value).strip()
    text = (
        "redacted_provider_error"
        if _contains_secret_marker(supplied)
        else _safe_token(supplied, fallback="redacted_provider_error")
    )
    return text or None


def _safe_provider(value: object) -> str:
    supplied = str(value or "").strip()
    if _contains_secret_marker(supplied):
        return "unknown"
    return _safe_token(supplied, fallback="unknown")


def _contains_secret_marker(value: str) -> bool:
    normalized = value.casefold()
    return any(marker in normalized for marker in _SECRET_MARKERS)


def _namespace_text(value: object) -> str:
    text = str(value or "").strip()
    if not _SAFE_NAMESPACE_RE.fullmatch(text) or text in {".", ".."}:
        raise MarketNoSendError("market no-send attempt artifact namespace is invalid")
    return text


def _timestamp_text(value: object) -> str:
    text = _identity_text(value, field_name="observed_at")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MarketNoSendError("market no-send attempt observed_at is invalid") from exc
    if parsed.tzinfo is None:
        raise MarketNoSendError("market no-send attempt observed_at is invalid")
    return text


def _identity_text(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 240 or any(ord(character) < 32 for character in text):
        raise MarketNoSendError(f"market no-send attempt {field_name} is invalid")
    return text


def _optional_identity_text(value: object, *, field_name: str) -> str | None:
    if value in (None, ""):
        return None
    return _identity_text(value, field_name=field_name)


def exact_generation_status(
    base: Path,
    namespace: str,
    *,
    manifest_filename: str,
) -> dict[str, Any]:
    """Return complete only when the latest CLI receipt matches the manifest."""

    try:
        receipt = read_json_object(base / LATEST_ATTEMPT_FILENAME)
    except MarketNoSendError:
        receipt = {}
    manifest: dict[str, Any] = {}
    if receipt.get("artifact_namespace") == namespace and receipt.get("status") == "complete":
        try:
            namespace_dir = safe_existing_namespace_dir(base, namespace)
            manifest = read_json_object(namespace_dir / manifest_filename)
        except MarketNoSendError:
            manifest = {}
    exact = bool(
        receipt.get("contract_version") == 1
        and receipt.get("row_type") == "event_market_no_send_latest_attempt"
        and receipt.get("artifact_namespace") == namespace
        and receipt.get("status") == "complete"
        and manifest.get("status") == "complete"
        and receipt.get("run_id") == manifest.get("run_id")
        and receipt.get("observed_at") == manifest.get("observed_at")
        and receipt.get("provider_call_attempted") is True
        and receipt.get("provider_request_succeeded") is True
    )
    source = manifest if exact else receipt
    return {
        "artifact_namespace": namespace,
        "status": str(source.get("status") or "not_generated"),
        "complete": exact,
        "exact_latest_attempt": exact,
        "provider_call_attempted": source.get("provider_call_attempted") is True,
        "provider_request_succeeded": source.get("provider_request_succeeded") is True,
        "candidate_source_mode": str(source.get("candidate_source_mode") or "preflight_only"),
        "measurement_program": str(source.get("measurement_program") or ""),
        "decision_radar_campaign_counted": (
            manifest.get("decision_radar_campaign_counted") is True if exact else False
        ),
        "burn_in_counted": manifest.get("burn_in_counted") is True if exact else False,
    }


__all__ = (
    "ATTEMPT_LEDGER_FILENAME",
    "ATTEMPT_LEDGER_MAX_ROWS",
    "LATEST_ATTEMPT_FILENAME",
    "exact_generation_status",
    "record_boundary_failure",
    "record_attempt",
)
