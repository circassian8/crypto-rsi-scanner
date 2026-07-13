"""Fail-soft, non-authoritative history reads for the local dashboard."""

from __future__ import annotations

import hashlib
import json
import stat
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from ..operations import market_no_send_io
from ..operations.market_no_send_models import MarketNoSendError


_CAMPAIGN_LEDGER = "event_decision_radar_campaign_outcomes.jsonl"


def load_dashboard_history(
    namespace_dir: Path,
    *,
    integrated_outcomes_data: bytes | None,
    now: datetime,
    namespace_reader: Callable[[Path], tuple[bytes | None, str | None]] | None = None,
) -> dict[str, Any]:
    """Load namespace-local and shared history without granting generation authority."""

    feedback_path = namespace_dir / "event_alpha_feedback.jsonl"
    integrated_path = namespace_dir / "event_integrated_radar_outcomes.jsonl"
    legacy_path = namespace_dir / "event_alpha_outcomes.jsonl"
    feedback, feedback_digest, feedback_error = _read_namespace_jsonl(
        feedback_path,
        namespace_reader=namespace_reader,
    )
    if integrated_outcomes_data is not None:
        integrated, integrated_digest, integrated_error = _read_jsonl_bytes(
            integrated_outcomes_data
        )
        integrated_authority = (
            "current_generation_fingerprint_verified"
            if integrated_error is None
            else "current_generation_invalid"
        )
        if integrated_error is not None:
            integrated_error = "invalid_verified_jsonl"
    else:
        integrated, integrated_digest, integrated_error = _read_namespace_jsonl(
            integrated_path,
            namespace_reader=namespace_reader,
        )
        integrated_authority = "cumulative_non_authoritative"
    legacy, legacy_digest, legacy_error = _read_namespace_jsonl(
        legacy_path,
        namespace_reader=namespace_reader,
    )
    campaign, campaign_digest, campaign_error = _read_shared_campaign_ledger(
        namespace_dir.parent
    )
    metadata = {
        feedback_path.name: _history_metadata(now, feedback_digest, feedback_error),
        integrated_path.name: _history_metadata(
            now,
            integrated_digest,
            integrated_error,
            authority=integrated_authority,
        ),
        legacy_path.name: _history_metadata(now, legacy_digest, legacy_error),
        f"radar_market_history_cache/{_CAMPAIGN_LEDGER}": _history_metadata(
            now,
            campaign_digest,
            campaign_error,
            authority="shared_campaign_non_authoritative",
        ),
    }
    return {
        "feedback": feedback,
        "outcomes": (*integrated, *legacy),
        "campaign_outcomes": campaign,
        "metadata": metadata,
    }


def read_unverified_json_object(
    path: Path,
) -> tuple[Mapping[str, Any], str | None, str | None]:
    data, read_error = _read_regular_file_once(path)
    return read_unverified_json_object_bytes(data, read_error=read_error)


def read_unverified_json_object_bytes(
    data: bytes | None,
    *,
    read_error: str | None,
) -> tuple[Mapping[str, Any], str | None, str | None]:
    """Parse one already-read non-authoritative JSON object."""

    if read_error == "artifact_missing":
        return {}, None, None
    if read_error or data is None:
        return {}, None, read_error or "unreadable"
    digest = hashlib.sha256(data).hexdigest()
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}, digest, "invalid_json"
    if not isinstance(payload, Mapping):
        return {}, digest, "json_not_object"
    return dict(payload), digest, None


def _read_namespace_jsonl(
    path: Path,
    *,
    namespace_reader: Callable[[Path], tuple[bytes | None, str | None]] | None,
) -> tuple[tuple[dict[str, Any], ...], str | None, str | None]:
    if namespace_reader is None:
        return read_unverified_jsonl(path)
    data, read_error = namespace_reader(path)
    if read_error == "artifact_missing":
        return (), None, None
    if read_error or data is None:
        return (), None, read_error or "unreadable"
    return _read_jsonl_bytes(data)


def read_unverified_jsonl(
    path: Path,
) -> tuple[tuple[dict[str, Any], ...], str | None, str | None]:
    data, read_error = _read_regular_file_once(path)
    if read_error == "artifact_missing":
        return (), None, None
    if read_error or data is None:
        return (), None, read_error or "unreadable"
    return _read_jsonl_bytes(data)


def _read_shared_campaign_ledger(
    artifact_base: Path,
) -> tuple[tuple[dict[str, Any], ...], str | None, str | None]:
    path = artifact_base / "radar_market_history_cache" / _CAMPAIGN_LEDGER
    if path_error := _path_symlink_error(artifact_base, path):
        return (), None, path_error
    try:
        parent_info = path.parent.lstat()
    except FileNotFoundError:
        return (), None, None
    except OSError:
        return (), None, "artifact_parent_unreadable_or_unsafe"
    if not stat.S_ISDIR(parent_info.st_mode):
        return (), None, "artifact_parent_unreadable_or_unsafe"
    try:
        data = market_no_send_io.read_regular_bytes(path, missing_ok=True)
    except MarketNoSendError:
        return (), None, "artifact_unreadable_or_symlink"
    return _read_jsonl_bytes(data)


def _read_regular_file_once(path: Path) -> tuple[bytes | None, str | None]:
    """Reuse the no-follow leaf reader without importing dashboard loader internals."""

    try:
        return market_no_send_io.read_regular_bytes(path, missing_ok=True), None
    except MarketNoSendError:
        return None, "artifact_unreadable_or_symlink"


def _read_jsonl_bytes(
    data: bytes | None,
) -> tuple[tuple[dict[str, Any], ...], str | None, str | None]:
    if data is None:
        return (), None, None
    digest = hashlib.sha256(data).hexdigest()
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return (), digest, "invalid_utf8"
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return (), digest, f"invalid_jsonl:{line_number}"
        if not isinstance(payload, Mapping):
            return (), digest, f"non_object_jsonl:{line_number}"
        rows.append(dict(payload))
    return tuple(rows), digest, None


def _history_metadata(
    now: datetime,
    digest: str | None,
    error: str | None,
    *,
    authority: str = "cumulative_non_authoritative",
) -> dict[str, Any]:
    return {
        "authority": authority,
        "read_at": now.isoformat() if digest else None,
        "sha256": digest,
        "error": error,
    }


def _path_symlink_error(base: Path, target: Path) -> str | None:
    try:
        relative = target.relative_to(base)
    except ValueError:
        return "artifact_path_escape"
    current = base
    for part in relative.parts:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            return None
        except OSError:
            return "artifact_path_unreadable"
        if stat.S_ISLNK(info.st_mode):
            return "artifact_symlink_not_allowed"
    return None


__all__ = (
    "load_dashboard_history",
    "read_unverified_json_object",
    "read_unverified_json_object_bytes",
    "read_unverified_jsonl",
)
