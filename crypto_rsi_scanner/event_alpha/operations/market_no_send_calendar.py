"""Safe local-calendar snapshot boundary for Decision Radar market cycles.

This module is the read-only boundary used before generation integration.  It
reads one explicitly configured local snapshot without network access, validates
that the snapshot is current and relevant to a bounded calendar window, and
returns raw rows plus credential-free copy/fingerprint metadata.  It never
writes an artifact, mutates provider authorization, sends, trades, paper trades,
writes normal RSI state, or creates ``TRIGGERED_FADE``.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .common import (
    OPENAI_KEY_RE,
    PROVIDER_TOKEN_VALUE_RE,
    TELEGRAM_BOT_TOKEN_VALUE_RE,
)
from .market_no_send_models import MarketNoSendError


CALENDAR_SNAPSHOT_PATH_ENV = "RSI_DECISION_RADAR_CALENDAR_SNAPSHOT_PATH"
CALENDAR_SOURCE_COPY_FILENAME = "event_market_no_send_calendar_source.json"
CALENDAR_SNAPSHOT_CONTRACT_VERSION = 1
CALENDAR_SNAPSHOT_STATUSES = frozenset(
    {
        "not_configured",
        "healthy_empty",
        "healthy_nonempty",
        "stale",
        "unavailable",
        "fixture_rejected_live",
    }
)
LIVE_CALENDAR_SOURCE_MODES = frozenset(
    {"live_provider_snapshot", "operator_verified_calendar_snapshot"}
)
LIVE_CALENDAR_ACQUISITION_MODES = frozenset(
    {"live_provider", "operator_verified_export"}
)

DEFAULT_MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_SNAPSHOT_ROWS = 1_000
DEFAULT_MAX_SNAPSHOT_AGE = timedelta(hours=36)
DEFAULT_CALENDAR_LOOKAHEAD = timedelta(days=90)
DEFAULT_CALENDAR_PAST_GRACE = timedelta(hours=24)
DEFAULT_FUTURE_TOLERANCE = timedelta(minutes=5)
MAX_CALENDAR_TEXT_LENGTH = 4_096
MAX_CALENDAR_SEQUENCE_ITEMS = 100

_STANDALONE_BEARER_RE = re.compile(
    r"\bBearer\s+[A-Za-z0-9._~+/-]{8,}\b",
    re.IGNORECASE,
)

_CONTAINER_KEYS = ("events", "data", "items")
_SNAPSHOT_TIME_KEYS = (
    "snapshot_observed_at",
    "observed_at",
    "fetched_at",
    "generated_at",
    "updated_at",
)
_EVENT_TIME_KEYS = (
    "scheduled_at",
    "event_start_time",
    "event_time",
    "date_event",
    "unlock_time",
    "unlock_date",
    "start_time",
    "start_date",
    "date",
)
_WINDOW_START_KEYS = ("window_start", "window_start_at", "date_window_start")
_WINDOW_END_KEYS = (
    "window_end",
    "window_end_at",
    "date_window_end",
    "event_end_time",
    "end_time",
    "end_date",
)
_PROVENANCE_FIELDS = frozenset(
    {
        "profile",
        "run_mode",
        "data_mode",
        "source_mode",
        "candidate_source_mode",
        "acquisition_mode",
        "data_acquisition_mode",
        "artifact_namespace",
        "provenance_type",
    }
)
_EVENT_PROVENANCE_FIELDS = frozenset({"provider", "source", "source_class"})
_TRUE_SAFETY_FIELDS = frozenset({"research_only", "no_send", "no_send_rehearsal"})
_PROVENANCE_CONTAINERS = frozenset(
    {
        "provenance",
        "source_provenance",
        "calendar_provenance",
        "market_provenance",
    }
)
_FIXTURE_BOOLEAN_FIELDS = frozenset(
    {
        "fixture",
        "fixture_mode",
        "is_fixture",
        "test",
        "test_mode",
        "is_test",
        "replay",
        "replay_mode",
        "is_replay",
        "mock",
        "mock_mode",
        "is_mock",
    }
)
_FIXTURE_TOKENS = frozenset(
    {
        "fixture",
        "fixtures",
        "fixture_preview",
        "fixture_only",
        "test",
        "testing",
        "replay",
        "mock",
        "mocked_fixture",
    }
)
_FIXTURE_FILENAME_RE = re.compile(r"(?:^|[._-])fixtures?(?:[._-]|$)", re.IGNORECASE)
_SENSITIVE_TEXT_RE = re.compile(
    r"(?:authorization\s*:\s*bearer|(?:api[_-]?key|access[_-]?token|password|passwd|secret|credential)\s*[:=]|-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----)",
    re.IGNORECASE,
)
_LIVE_CONTAINER_FIELDS = frozenset(
    {
        "contract_version",
        "schema_version",
        "events",
        "source_provider",
        "provider",
        *_SNAPSHOT_TIME_KEYS,
        *_PROVENANCE_FIELDS,
        *_PROVENANCE_CONTAINERS,
        *_FIXTURE_BOOLEAN_FIELDS,
    }
)
_SAFE_EVENT_FIELDS = frozenset(
    {
        "calendar_event_id", "event_id", "id",
        "title", "event_name", "name", "description", "summary",
        "event_kind", "event_type", "type", "category",
        *_EVENT_TIME_KEYS, *_WINDOW_START_KEYS, *_WINDOW_END_KEYS,
        "time_certainty", "date_certainty", "certainty",
        "importance", "affected_assets", "symbols", "assets", "symbol", "coin_id",
        "source", "provider", "source_class", "source_url", "url", "link",
        "reminder_windows", "post_event_tracking_status", "timezone", "source_timezone",
        "forecast_value", "forecast", "previous_value", "previous",
        "actual_value", "actual", "surprise_value", "surprise",
        "impact_window_before", "impact_window_after", "event_status", "status",
        "published_at", "created_at", "updated_at", "fetched_at",
        "tokens_unlocked", "unlock_amount", "amount", "unlock_usd",
        "unlock_value_usd", "value_usd", "unlock_pct_circulating_supply",
        "unlock_pct_circulating", "percent_of_circulating_supply",
        "unlock_pct_total_supply", "percent_of_total_supply", "unlock_vs_30d_adv",
        "unlock_to_adv", "unlock_vs_adv", "unlock_type", "cliff_or_linear",
        "vesting_category", "event_timestamp_confidence", "research_only",
        "no_send_rehearsal", "no_send",
    }
)
_SAFE_AFFECTED_ASSET_FIELDS = frozenset({"symbol", "coin_id", "id"})
_URL_FIELDS = frozenset({"source_url", "url", "link"})
_STRING_SEQUENCE_FIELDS = frozenset(
    {"symbols", "assets", "reminder_windows"}
)


class _SnapshotReadError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("calendar snapshot is unavailable")


class _DuplicateJsonKey(ValueError):
    pass


@dataclass(frozen=True)
class MarketNoSendCalendarSnapshot:
    """Closed result returned by the no-network calendar snapshot boundary."""

    status: str
    raw_rows: tuple[dict[str, Any], ...] = ()
    configured: bool = False
    source_mode: str = "not_configured"
    upstream_source_mode: str | None = None
    upstream_acquisition_mode: str | None = None
    source_provider: str | None = None
    source_filename: str | None = None
    source_sha256: str | None = None
    source_size_bytes: int = 0
    source_modified_at: str | None = None
    snapshot_observed_at: str | None = None
    freshness_basis: str | None = None
    source_row_count: int = 0
    retained_row_count: int = 0
    dropped_before_window_count: int = 0
    dropped_after_window_count: int = 0
    canonical_rows_sha256: str | None = None
    copy_artifact_filename: str = CALENDAR_SOURCE_COPY_FILENAME
    error_class: str | None = None
    network_call_attempted: bool = False
    provider_call_attempted: bool = False
    provider_authorization_mutated: bool = False
    created_alert: bool = False
    notification_send_enabled: bool = False
    execution_enabled: bool = False
    paper_trading_enabled: bool = False
    normal_rsi_routing_enabled: bool = False
    no_send: bool = True
    research_only: bool = True
    strict_alerts_created: int = 0
    trades_created: int = 0
    paper_trades_created: int = 0
    normal_rsi_signal_rows_written: int = 0
    triggered_fade_created: int = 0
    telegram_sends: int = 0

    def __post_init__(self) -> None:
        _validate_snapshot_result(self)

    @property
    def rows(self) -> tuple[dict[str, Any], ...]:
        """Compatibility-friendly alias for the retained raw rows."""

        return self.raw_rows

    @property
    def usable(self) -> bool:
        return self.status in {"healthy_empty", "healthy_nonempty"}

    @property
    def copy_digest_metadata(self) -> dict[str, Any]:
        """Return only bounded metadata needed to attest a later exact copy."""

        return {
            "copy_artifact_filename": self.copy_artifact_filename,
            "source_sha256": self.source_sha256,
            "canonical_rows_sha256": self.canonical_rows_sha256,
            "source_size_bytes": self.source_size_bytes,
            "source_row_count": self.source_row_count,
            "retained_row_count": self.retained_row_count,
        }

    def to_dict(self, *, include_rows: bool = False) -> dict[str, Any]:
        return _snapshot_result_dict(self, include_rows=include_rows)


def _validate_snapshot_result(snapshot: MarketNoSendCalendarSnapshot) -> None:
    if snapshot.status not in CALENDAR_SNAPSHOT_STATUSES:
        raise ValueError("unsupported calendar snapshot status")
    if snapshot.retained_row_count != len(snapshot.raw_rows):
        raise ValueError("calendar retained row count is inconsistent")
    if snapshot.status == "healthy_empty" and snapshot.retained_row_count != 0:
        raise ValueError("healthy-empty calendar snapshot contains rows")
    if snapshot.status == "healthy_nonempty" and snapshot.retained_row_count == 0:
        raise ValueError("healthy-nonempty calendar snapshot contains no rows")
    if snapshot.configured != (snapshot.status != "not_configured"):
        raise ValueError("calendar configured status is inconsistent")
    if not snapshot.usable and snapshot.raw_rows:
        raise ValueError("unusable calendar snapshot cannot expose rows")
    side_effect_counts = (
        snapshot.strict_alerts_created,
        snapshot.trades_created,
        snapshot.paper_trades_created,
        snapshot.normal_rsi_signal_rows_written,
        snapshot.triggered_fade_created,
        snapshot.telegram_sends,
    )
    if any(value != 0 for value in side_effect_counts):
        raise ValueError("calendar snapshot cannot report side effects")
    if not snapshot.no_send or not snapshot.research_only:
        raise ValueError("calendar snapshot must remain research-only and no-send")
    side_effect_switches = (
        snapshot.network_call_attempted,
        snapshot.provider_call_attempted,
        snapshot.provider_authorization_mutated,
        snapshot.created_alert,
        snapshot.notification_send_enabled,
        snapshot.execution_enabled,
        snapshot.paper_trading_enabled,
        snapshot.normal_rsi_routing_enabled,
    )
    if any(side_effect_switches):
        raise ValueError(
            "calendar snapshot boundary cannot enable external side effects"
        )


def _snapshot_result_dict(
    snapshot: MarketNoSendCalendarSnapshot,
    *,
    include_rows: bool,
) -> dict[str, Any]:
    payload = {
        "contract_version": CALENDAR_SNAPSHOT_CONTRACT_VERSION,
        "status": snapshot.status,
        "configured": snapshot.configured,
        "source_mode": snapshot.source_mode,
        "upstream_source_mode": snapshot.upstream_source_mode,
        "upstream_acquisition_mode": snapshot.upstream_acquisition_mode,
        "source_provider": snapshot.source_provider,
        "source_filename": snapshot.source_filename,
        "source_sha256": snapshot.source_sha256,
        "source_size_bytes": snapshot.source_size_bytes,
        "source_modified_at": snapshot.source_modified_at,
        "snapshot_observed_at": snapshot.snapshot_observed_at,
        "freshness_basis": snapshot.freshness_basis,
        "source_row_count": snapshot.source_row_count,
        "retained_row_count": snapshot.retained_row_count,
        "dropped_before_window_count": snapshot.dropped_before_window_count,
        "dropped_after_window_count": snapshot.dropped_after_window_count,
        "canonical_rows_sha256": snapshot.canonical_rows_sha256,
        "copy_artifact_filename": snapshot.copy_artifact_filename,
        "error_class": snapshot.error_class,
        **_snapshot_safety_values(snapshot),
    }
    if include_rows:
        payload["rows"] = [dict(row) for row in snapshot.raw_rows]
    return payload


def _snapshot_safety_values(
    snapshot: MarketNoSendCalendarSnapshot,
) -> dict[str, Any]:
    return {
        "network_call_attempted": snapshot.network_call_attempted,
        "provider_call_attempted": snapshot.provider_call_attempted,
        "provider_authorization_mutated": snapshot.provider_authorization_mutated,
        "created_alert": snapshot.created_alert,
        "notification_send_enabled": snapshot.notification_send_enabled,
        "execution_enabled": snapshot.execution_enabled,
        "paper_trading_enabled": snapshot.paper_trading_enabled,
        "normal_rsi_routing_enabled": snapshot.normal_rsi_routing_enabled,
        "no_send": snapshot.no_send,
        "research_only": snapshot.research_only,
        "strict_alerts_created": snapshot.strict_alerts_created,
        "trades_created": snapshot.trades_created,
        "paper_trades_created": snapshot.paper_trades_created,
        "normal_rsi_signal_rows_written": snapshot.normal_rsi_signal_rows_written,
        "triggered_fade_created": snapshot.triggered_fade_created,
        "telegram_sends": snapshot.telegram_sends,
    }


@dataclass(frozen=True)
class _SecureSnapshotBytes:
    data: bytes
    size: int
    modified_at: datetime


def load_market_no_send_calendar_snapshot(
    *,
    environ: Mapping[str, str] | None = None,
    now: datetime | str | None = None,
    data_mode: str = "live",
    run_mode: str = "operational",
    max_bytes: int = DEFAULT_MAX_SNAPSHOT_BYTES,
    max_rows: int = DEFAULT_MAX_SNAPSHOT_ROWS,
    max_age: timedelta = DEFAULT_MAX_SNAPSHOT_AGE,
    lookahead: timedelta = DEFAULT_CALENDAR_LOOKAHEAD,
    past_grace: timedelta = DEFAULT_CALENDAR_PAST_GRACE,
    future_tolerance: timedelta = DEFAULT_FUTURE_TOLERANCE,
) -> MarketNoSendCalendarSnapshot:
    """Load one explicit local snapshot without providers, writes, or sends."""

    _validate_limits(
        max_bytes=max_bytes,
        max_rows=max_rows,
        max_age=max_age,
        lookahead=lookahead,
        past_grace=past_grace,
        future_tolerance=future_tolerance,
    )
    evaluated_at = _as_utc(_parse_datetime(now) if now is not None else datetime.now(timezone.utc))
    env = os.environ if environ is None else environ
    configured_path = str(env.get(CALENDAR_SNAPSHOT_PATH_ENV) or "").strip()
    if not configured_path:
        return MarketNoSendCalendarSnapshot(status="not_configured")

    path = Path(configured_path).expanduser().absolute()
    live_operational = (
        str(data_mode or "").strip().casefold() == "live"
        and str(run_mode or "").strip().casefold() == "operational"
    )
    if live_operational and _fixture_path(path):
        return MarketNoSendCalendarSnapshot(
            status="fixture_rejected_live",
            configured=True,
            source_mode="explicit_local_snapshot",
            source_filename=_safe_source_label(path),
            error_class="fixture_path",
        )

    try:
        snapshot = _read_regular_snapshot(path, max_bytes=max_bytes)
        parsed = _parse_snapshot_json(snapshot.data)
        raw_rows, container_metadata = _extract_rows(parsed, max_rows=max_rows)
    except _SnapshotReadError as exc:
        return MarketNoSendCalendarSnapshot(
            status="unavailable",
            configured=True,
            source_mode="explicit_local_snapshot",
            source_filename=_safe_source_label(path),
            error_class=exc.code,
        )

    return _evaluate_loaded_snapshot(
        path=path,
        snapshot=snapshot,
        parsed=parsed,
        raw_rows=raw_rows,
        metadata=container_metadata,
        live_operational=live_operational,
        evaluated_at=evaluated_at,
        max_age=max_age,
        lookahead=lookahead,
        past_grace=past_grace,
        future_tolerance=future_tolerance,
    )


def _evaluate_loaded_snapshot(
    *,
    path: Path,
    snapshot: _SecureSnapshotBytes,
    parsed: Any,
    raw_rows: tuple[dict[str, Any], ...],
    metadata: Mapping[str, Any],
    live_operational: bool,
    evaluated_at: datetime,
    max_age: timedelta,
    lookahead: timedelta,
    past_grace: timedelta,
    future_tolerance: timedelta,
) -> MarketNoSendCalendarSnapshot:
    source_digest = hashlib.sha256(snapshot.data).hexdigest()
    if live_operational and _has_fixture_provenance(metadata, raw_rows):
        return _fixture_provenance_result(
            path, snapshot=snapshot, source_digest=source_digest,
            source_row_count=len(raw_rows),
        )
    invalid = _validated_rows_result(
        path=path, snapshot=snapshot, source_digest=source_digest,
        parsed=parsed, metadata=metadata, raw_rows=raw_rows,
        live_operational=live_operational,
    )
    if isinstance(invalid, MarketNoSendCalendarSnapshot):
        return invalid
    safe_rows = invalid
    try:
        observed, freshness_basis = _snapshot_observed_at(
            metadata, fallback=snapshot.modified_at
        )
    except _SnapshotReadError as exc:
        return _metadata_result(
            status="unavailable", path=path, snapshot=snapshot,
            source_digest=source_digest, source_row_count=len(raw_rows),
            error_class=exc.code,
        )
    freshness_error = _snapshot_freshness_error(
        observed, evaluated_at=evaluated_at, max_age=max_age,
        future_tolerance=future_tolerance,
    )
    if freshness_error:
        return _metadata_result(
            status="stale" if freshness_error == "snapshot_too_old" else "unavailable",
            path=path, snapshot=snapshot, source_digest=source_digest,
            source_row_count=len(raw_rows), snapshot_observed=observed,
            freshness_basis=freshness_basis, error_class=freshness_error,
        )
    try:
        retained, before_count, after_count = _rows_in_window(
            safe_rows, now=evaluated_at, lookahead=lookahead, past_grace=past_grace,
        )
    except _SnapshotReadError as exc:
        return _metadata_result(
            status="unavailable", path=path, snapshot=snapshot,
            source_digest=source_digest, source_row_count=len(raw_rows),
            snapshot_observed=observed, freshness_basis=freshness_basis,
            error_class=exc.code,
        )
    return _healthy_snapshot_result(
        path=path, snapshot=snapshot, source_digest=source_digest,
        source_row_count=len(raw_rows), retained=retained,
        before_count=before_count, after_count=after_count,
        observed=observed, freshness_basis=freshness_basis, metadata=metadata,
    )


def _fixture_provenance_result(
    path: Path,
    *,
    snapshot: _SecureSnapshotBytes,
    source_digest: str,
    source_row_count: int,
) -> MarketNoSendCalendarSnapshot:
    return MarketNoSendCalendarSnapshot(
        status="fixture_rejected_live",
        configured=True,
        source_mode="explicit_local_snapshot",
        source_filename=_safe_source_label(path),
        source_sha256=source_digest,
        source_size_bytes=snapshot.size,
        source_modified_at=snapshot.modified_at.isoformat(),
        source_row_count=source_row_count,
        error_class="fixture_provenance",
    )


def _validated_rows_result(
    *,
    path: Path,
    snapshot: _SecureSnapshotBytes,
    source_digest: str,
    parsed: Any,
    metadata: Mapping[str, Any],
    raw_rows: tuple[dict[str, Any], ...],
    live_operational: bool,
) -> tuple[dict[str, Any], ...] | MarketNoSendCalendarSnapshot:
    try:
        if live_operational:
            _validate_live_container(parsed, metadata)
        return _safe_calendar_rows(raw_rows)
    except _SnapshotReadError as exc:
        return _metadata_result(
            status="unavailable",
            path=path,
            snapshot=snapshot,
            source_digest=source_digest,
            source_row_count=len(raw_rows),
            error_class=exc.code,
        )


def _snapshot_freshness_error(
    observed: datetime,
    *,
    evaluated_at: datetime,
    max_age: timedelta,
    future_tolerance: timedelta,
) -> str | None:
    if observed > evaluated_at + future_tolerance:
        return "snapshot_time_future"
    if observed < evaluated_at - max_age:
        return "snapshot_too_old"
    return None


def _healthy_snapshot_result(
    *,
    path: Path,
    snapshot: _SecureSnapshotBytes,
    source_digest: str,
    source_row_count: int,
    retained: tuple[dict[str, Any], ...],
    before_count: int,
    after_count: int,
    observed: datetime,
    freshness_basis: str,
    metadata: Mapping[str, Any],
) -> MarketNoSendCalendarSnapshot:
    return MarketNoSendCalendarSnapshot(
        status="healthy_nonempty" if retained else "healthy_empty",
        raw_rows=retained,
        configured=True,
        source_mode="explicit_local_snapshot",
        upstream_source_mode=_allowlisted_value(
            metadata.get("source_mode"), LIVE_CALENDAR_SOURCE_MODES
        ),
        upstream_acquisition_mode=_allowlisted_value(
            metadata.get("data_acquisition_mode") or metadata.get("acquisition_mode"),
            LIVE_CALENDAR_ACQUISITION_MODES,
        ),
        source_provider=_safe_provider_value(
            metadata.get("source_provider") or metadata.get("provider")
        ),
        source_filename=_safe_source_label(path),
        source_sha256=source_digest,
        source_size_bytes=snapshot.size,
        source_modified_at=snapshot.modified_at.isoformat(),
        snapshot_observed_at=observed.isoformat(),
        freshness_basis=freshness_basis,
        source_row_count=source_row_count,
        retained_row_count=len(retained),
        dropped_before_window_count=before_count,
        dropped_after_window_count=after_count,
        canonical_rows_sha256=_canonical_rows_sha256(retained),
    )


def _metadata_result(
    *,
    status: str,
    path: Path,
    snapshot: _SecureSnapshotBytes,
    source_digest: str,
    source_row_count: int,
    snapshot_observed: datetime | None = None,
    freshness_basis: str | None = None,
    error_class: str | None = None,
) -> MarketNoSendCalendarSnapshot:
    return MarketNoSendCalendarSnapshot(
        status=status,
        configured=True,
        source_mode="explicit_local_snapshot",
        source_filename=_safe_source_label(path),
        source_sha256=source_digest,
        source_size_bytes=snapshot.size,
        source_modified_at=snapshot.modified_at.isoformat(),
        snapshot_observed_at=snapshot_observed.isoformat() if snapshot_observed else None,
        freshness_basis=freshness_basis,
        source_row_count=source_row_count,
        error_class=error_class,
    )


def _allowlisted_value(value: Any, allowed: frozenset[str]) -> str | None:
    text = str(value or "").strip()
    return text if text in allowed else None


def _safe_provider_value(value: Any) -> str | None:
    text = str(value or "").strip().casefold()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,63}", text):
        return None
    return None if _fixture_token(text) else text


def _read_regular_snapshot(path: Path, *, max_bytes: int) -> _SecureSnapshotBytes:
    descriptor: int | None = None
    parent_descriptor: int | None = None
    try:
        parent = path.parent
        if parent.resolve(strict=True) != parent:
            raise _SnapshotReadError("snapshot_parent_symlink")
        parent_path_before = os.stat(parent, follow_symlinks=False)
        if not stat.S_ISDIR(parent_path_before.st_mode):
            raise _SnapshotReadError("snapshot_parent_invalid")
        parent_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        parent_descriptor = os.open(parent, parent_flags)
        parent_before = os.fstat(parent_descriptor)
        if not _same_file(parent_path_before, parent_before):
            raise _SnapshotReadError("snapshot_parent_changed")
        before = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise _SnapshotReadError("snapshot_not_regular")
        if before.st_size > max_bytes:
            raise _SnapshotReadError("snapshot_too_large")
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        descriptor = os.open(path.name, flags, dir_fd=parent_descriptor)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or not _same_snapshot(before, opened):
            raise _SnapshotReadError("snapshot_changed")
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        if len(data) > max_bytes:
            raise _SnapshotReadError("snapshot_too_large")
        after = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
        parent_path_after = os.stat(parent, follow_symlinks=False)
        if not _same_snapshot(opened, after) or not _same_file(parent_before, parent_path_after):
            raise _SnapshotReadError("snapshot_changed")
        return _SecureSnapshotBytes(
            data=data,
            size=len(data),
            modified_at=datetime.fromtimestamp(opened.st_mtime, tz=timezone.utc),
        )
    except _SnapshotReadError:
        raise
    except FileNotFoundError:
        raise _SnapshotReadError("snapshot_missing") from None
    except OSError:
        raise _SnapshotReadError("snapshot_unreadable") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if parent_descriptor is not None:
            os.close(parent_descriptor)


def _parse_snapshot_json(data: bytes) -> Any:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise _SnapshotReadError("snapshot_invalid_utf8") from None
    try:
        return json.loads(text, object_pairs_hook=_object_without_duplicate_keys)
    except _DuplicateJsonKey:
        raise _SnapshotReadError("snapshot_duplicate_json_key") from None
    except json.JSONDecodeError:
        raise _SnapshotReadError("snapshot_invalid_json") from None


def _object_without_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey
        result[key] = value
    return result


def _extract_rows(parsed: Any, *, max_rows: int) -> tuple[tuple[dict[str, Any], ...], Mapping[str, Any]]:
    metadata: Mapping[str, Any] = {}
    if isinstance(parsed, list):
        values = parsed
    elif isinstance(parsed, Mapping):
        metadata = parsed
        selected = next((key for key in _CONTAINER_KEYS if key in parsed), None)
        if selected is None:
            raise _SnapshotReadError("snapshot_container_missing")
        values = parsed.get(selected)
    else:
        raise _SnapshotReadError("snapshot_container_invalid")
    if not isinstance(values, list):
        raise _SnapshotReadError("snapshot_rows_invalid")
    if len(values) > max_rows:
        raise _SnapshotReadError("snapshot_too_many_rows")
    rows: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, Mapping):
            raise _SnapshotReadError("snapshot_non_mapping_row")
        rows.append(dict(value))
    return tuple(rows), metadata


def _validate_live_container(
    parsed: Any,
    metadata: Mapping[str, Any],
) -> None:
    if not isinstance(parsed, Mapping) or not isinstance(parsed.get("events"), list):
        raise _SnapshotReadError("live_snapshot_versioned_container_required")
    if metadata.get("contract_version") != CALENDAR_SNAPSHOT_CONTRACT_VERSION:
        raise _SnapshotReadError("live_snapshot_contract_version_invalid")
    unknown = set(metadata).difference(_LIVE_CONTAINER_FIELDS)
    if unknown:
        raise _SnapshotReadError("live_snapshot_container_field_unsupported")
    if not any(metadata.get(key) not in (None, "") for key in _SNAPSHOT_TIME_KEYS):
        raise _SnapshotReadError("live_snapshot_observed_at_required")
    source_mode = metadata.get("source_mode")
    acquisition_mode = metadata.get("data_acquisition_mode") or metadata.get(
        "acquisition_mode"
    )
    source_provider = str(
        metadata.get("source_provider") or metadata.get("provider") or ""
    ).strip().casefold()
    if source_mode not in LIVE_CALENDAR_SOURCE_MODES:
        raise _SnapshotReadError("live_snapshot_source_mode_invalid")
    if acquisition_mode not in LIVE_CALENDAR_ACQUISITION_MODES:
        raise _SnapshotReadError("live_snapshot_acquisition_mode_invalid")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,63}", source_provider):
        raise _SnapshotReadError("live_snapshot_source_provider_invalid")
    if _fixture_token(source_provider):
        raise _SnapshotReadError("live_snapshot_source_provider_invalid")


def _safe_calendar_rows(
    rows: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    return tuple(_safe_calendar_row(row) for row in rows)


def validate_calendar_artifact_rows(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Revalidate copied rows before publication without echoing payload data."""

    if len(rows) > DEFAULT_MAX_SNAPSHOT_ROWS:
        raise MarketNoSendError("campaign_calendar_snapshot_rows_unsafe")
    try:
        return _safe_calendar_rows(tuple(dict(row) for row in rows))
    except _SnapshotReadError as exc:
        raise MarketNoSendError(
            f"campaign_calendar_snapshot_rows_unsafe:{exc.code}"
        ) from None


def _safe_calendar_row(row: Mapping[str, Any]) -> dict[str, Any]:
    unknown = set(row).difference(_SAFE_EVENT_FIELDS)
    if unknown:
        raise _SnapshotReadError("calendar_event_field_unsupported")
    safe: dict[str, Any] = {}
    for key, value in row.items():
        if key in _TRUE_SAFETY_FIELDS and value is not True:
            raise _SnapshotReadError("calendar_event_safety_flag_invalid")
        if key in _URL_FIELDS and value not in (None, ""):
            _validate_public_url(value)
        if key == "affected_assets":
            safe[key] = _safe_affected_assets(value)
        elif key in _STRING_SEQUENCE_FIELDS:
            safe[key] = _safe_string_sequence(value)
        else:
            _validate_safe_scalar(value)
            safe[key] = value
    return safe


def _safe_affected_assets(value: Any) -> Any:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _SnapshotReadError("calendar_affected_assets_invalid")
    if len(value) > MAX_CALENDAR_SEQUENCE_ITEMS:
        raise _SnapshotReadError("calendar_affected_assets_too_many")
    safe: list[Any] = []
    for asset in value:
        if isinstance(asset, Mapping):
            if set(asset).difference(_SAFE_AFFECTED_ASSET_FIELDS):
                raise _SnapshotReadError("calendar_affected_asset_field_unsupported")
            if any(
                isinstance(item, (Mapping, Sequence)) and not isinstance(item, str)
                for item in asset.values()
            ):
                raise _SnapshotReadError("calendar_affected_asset_value_invalid")
            for item in asset.values():
                _validate_safe_scalar(item)
            safe.append(dict(asset))
        elif isinstance(asset, str):
            _validate_safe_scalar(asset)
            safe.append(asset)
        else:
            raise _SnapshotReadError("calendar_affected_asset_value_invalid")
    return safe


def _safe_string_sequence(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _SnapshotReadError("calendar_event_sequence_invalid")
    if len(value) > MAX_CALENDAR_SEQUENCE_ITEMS:
        raise _SnapshotReadError("calendar_event_sequence_too_many")
    safe: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise _SnapshotReadError("calendar_event_sequence_invalid")
        _validate_safe_scalar(item)
        safe.append(item)
    return safe


def _validate_safe_scalar(value: Any) -> None:
    if not isinstance(value, (str, int, float, bool, type(None))):
        raise _SnapshotReadError("calendar_event_value_unsupported")
    if isinstance(value, float) and not math.isfinite(value):
        raise _SnapshotReadError("calendar_event_value_nonfinite")
    if isinstance(value, str):
        if len(value) > MAX_CALENDAR_TEXT_LENGTH:
            raise _SnapshotReadError("calendar_event_text_too_long")
        if _contains_sensitive_text(value):
            raise _SnapshotReadError("calendar_event_sensitive_value")


def _validate_public_url(value: Any) -> None:
    text = str(value or "").strip()
    if len(text) > 2_048 or _contains_sensitive_text(text):
        raise _SnapshotReadError("calendar_source_url_unsafe")
    parsed = urlsplit(text)
    if any(
        (
            parsed.scheme != "https",
            not parsed.hostname,
            parsed.username is not None,
            parsed.password is not None,
            bool(parsed.query),
            bool(parsed.fragment),
        )
    ):
        raise _SnapshotReadError("calendar_source_url_unsafe")


def _contains_sensitive_text(value: str) -> bool:
    return any(
        pattern.search(value) is not None
        for pattern in (
            _SENSITIVE_TEXT_RE,
            OPENAI_KEY_RE,
            PROVIDER_TOKEN_VALUE_RE,
            TELEGRAM_BOT_TOKEN_VALUE_RE,
            _STANDALONE_BEARER_RE,
        )
    )


def _snapshot_observed_at(
    metadata: Mapping[str, Any],
    *,
    fallback: datetime,
) -> tuple[datetime, str]:
    for key in _SNAPSHOT_TIME_KEYS:
        value = metadata.get(key)
        if value not in (None, ""):
            try:
                return _as_utc(_parse_datetime(value)), f"container:{key}"
            except (TypeError, ValueError):
                raise _SnapshotReadError("snapshot_time_invalid") from None
    return _as_utc(fallback), "file_mtime"


def _rows_in_window(
    rows: tuple[dict[str, Any], ...],
    *,
    now: datetime,
    lookahead: timedelta,
    past_grace: timedelta,
) -> tuple[tuple[dict[str, Any], ...], int, int]:
    earliest = now - past_grace
    latest = now + lookahead
    retained: list[dict[str, Any]] = []
    before_count = 0
    after_count = 0
    for row in rows:
        start, end = _event_bounds(row)
        if end < earliest:
            before_count += 1
        elif start > latest:
            after_count += 1
        else:
            retained.append(dict(row))
    return tuple(retained), before_count, after_count


def _event_bounds(row: Mapping[str, Any]) -> tuple[datetime, datetime]:
    exact_value = _first_nonempty(row, _EVENT_TIME_KEYS)
    start_value = exact_value if exact_value is not None else _first_nonempty(row, _WINDOW_START_KEYS)
    end_value = exact_value if exact_value is not None else _first_nonempty(row, _WINDOW_END_KEYS)
    if start_value is None and end_value is None:
        raise _SnapshotReadError("calendar_event_time_missing")
    if start_value is None:
        start_value = end_value
    if end_value is None:
        end_value = start_value
    try:
        start = _as_utc(_parse_datetime(start_value))
        end = _as_utc(_parse_datetime(end_value))
    except (TypeError, ValueError):
        raise _SnapshotReadError("calendar_event_time_invalid") from None
    if end < start:
        raise _SnapshotReadError("calendar_event_window_invalid")
    return start, end


def _first_nonempty(row: Mapping[str, Any], keys: Sequence[str]) -> Any:
    return next((row.get(key) for key in keys if row.get(key) not in (None, "")), None)


def _has_fixture_provenance(
    metadata: Mapping[str, Any],
    rows: tuple[dict[str, Any], ...],
) -> bool:
    return _mapping_has_fixture_provenance(metadata) or any(
        _mapping_has_fixture_provenance(row) for row in rows
    )


def _mapping_has_fixture_provenance(value: Mapping[str, Any]) -> bool:
    for key, raw in value.items():
        normalized_key = str(key).strip().casefold()
        if normalized_key in _FIXTURE_BOOLEAN_FIELDS and _truthy(raw):
            return True
        if normalized_key in (
            _PROVENANCE_FIELDS | _EVENT_PROVENANCE_FIELDS
        ) and _fixture_token(raw):
            return True
        if normalized_key in _PROVENANCE_CONTAINERS and isinstance(raw, Mapping):
            if _mapping_has_fixture_provenance(raw):
                return True
    return False


def _fixture_token(value: Any) -> bool:
    text = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    if not text:
        return False
    tokens = tuple(part for part in re.split(r"[^a-z0-9]+", text) if part)
    return text in _FIXTURE_TOKENS or any(token in _FIXTURE_TOKENS for token in tokens)


def _fixture_path(path: Path) -> bool:
    parts = {part.casefold() for part in path.parts}
    return bool(parts.intersection({"fixture", "fixtures"}) or _FIXTURE_FILENAME_RE.search(path.name))


def _canonical_rows_sha256(rows: tuple[dict[str, Any], ...]) -> str:
    encoded = json.dumps(
        [dict(row) for row in rows],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _same_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        _same_file(left, right)
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
        and left.st_ctime_ns == right.st_ctime_ns
    )


def _safe_source_label(path: Path) -> str:
    """Return a stable non-secret label rather than an operator-local basename."""

    return "configured_calendar_snapshot.json"


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise ValueError("calendar snapshot timestamp is missing")
    if parsed.tzinfo is None:
        raise ValueError("calendar snapshot timestamp must include a timezone")
    return parsed


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("calendar snapshot clock must be timezone-aware")
    return value.astimezone(timezone.utc)


def _validate_limits(
    *,
    max_bytes: int,
    max_rows: int,
    max_age: timedelta,
    lookahead: timedelta,
    past_grace: timedelta,
    future_tolerance: timedelta,
) -> None:
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 1:
        raise ValueError("calendar max_bytes must be a positive integer")
    if not isinstance(max_rows, int) or isinstance(max_rows, bool) or max_rows < 1:
        raise ValueError("calendar max_rows must be a positive integer")
    for name, value in (
        ("max_age", max_age),
        ("lookahead", lookahead),
        ("past_grace", past_grace),
        ("future_tolerance", future_tolerance),
    ):
        if not isinstance(value, timedelta) or value < timedelta(0):
            raise ValueError(f"calendar {name} must be a nonnegative timedelta")
    if max_age == timedelta(0) or lookahead == timedelta(0):
        raise ValueError("calendar max_age and lookahead must be positive")


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def materialize_market_calendar_snapshot(
    context: Any,
    *,
    calendar_snapshot: MarketNoSendCalendarSnapshot,
    observed: datetime,
    run_id: str,
    manifest: dict[str, Any],
    safety_counters: Mapping[str, int],
) -> tuple[dict[str, Any], ...] | None:
    from . import market_no_send_calendar_materialization

    return market_no_send_calendar_materialization.materialize_market_calendar_snapshot(
        context,
        calendar_snapshot=calendar_snapshot,
        observed=observed,
        run_id=run_id,
        manifest=manifest,
        safety_counters=safety_counters,
        source_copy_filename=CALENDAR_SOURCE_COPY_FILENAME,
        snapshot_contract_version=CALENDAR_SNAPSHOT_CONTRACT_VERSION,
    )


__all__ = (
    "CALENDAR_SNAPSHOT_CONTRACT_VERSION",
    "CALENDAR_SNAPSHOT_PATH_ENV",
    "CALENDAR_SNAPSHOT_STATUSES",
    "CALENDAR_SOURCE_COPY_FILENAME",
    "LIVE_CALENDAR_ACQUISITION_MODES",
    "LIVE_CALENDAR_SOURCE_MODES",
    "MarketNoSendCalendarSnapshot",
    "load_market_no_send_calendar_snapshot",
    "materialize_market_calendar_snapshot",
    "validate_calendar_artifact_rows",
)
