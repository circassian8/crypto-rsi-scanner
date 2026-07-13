"""One local reservation for the shared Decision Radar market campaign state."""

from __future__ import annotations

import errno
import fcntl
import json
import os
import re
import stat
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from . import market_no_send_io
from .market_no_send_models import (
    MarketNoSendError,
    MarketNoSendGenerationResult,
    MarketNoSendReadiness,
)


CAMPAIGN_STATE_NAMESPACE = "radar_market_history_cache"
CAMPAIGN_LOCK_FILENAME = ".decision_radar_campaign.lock"
CAMPAIGN_RESERVATION_FILENAME = "event_decision_radar_campaign_reservation.json"
_DEFAULT_STALE_AFTER = timedelta(minutes=15)
_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class _CampaignReservationBusy(MarketNoSendError):
    """Raised without waiting when another campaign operation owns the lock."""


CampaignReservationBusy = _CampaignReservationBusy


@dataclass
class CampaignReservation:
    artifact_base_dir: Path
    state_dir: Path
    artifact_namespace: str
    reservation_id: str
    acquired_at: datetime
    expires_at: datetime
    previous_reservation_status: str
    next_provider_call_at: datetime | None
    _base_fd: int
    _state_dir_fd: int
    _base_dir_identity: tuple[int, int]
    _state_dir_identity: tuple[int, int]
    _lock_identity: tuple[int, int]
    _lock_fd: int
    provider_call_reserved_at: datetime | None = None
    _active: bool = True

    def assert_active(self, artifact_base_dir: Path) -> None:
        """Fail closed unless this exact reservation still owns a regular lock."""

        supplied_base = Path(artifact_base_dir).expanduser().absolute()
        if not self._active or supplied_base != self.artifact_base_dir:
            raise MarketNoSendError("Decision Radar campaign reservation is not active")
        try:
            anchored_base = os.fstat(self._base_fd)
            current_base = os.stat(self.artifact_base_dir, follow_symlinks=False)
            anchored_state_dir = os.fstat(self._state_dir_fd)
            current_state_dir = os.stat(
                CAMPAIGN_STATE_NAMESPACE,
                dir_fd=self._base_fd,
                follow_symlinks=False,
            )
            anchored_lock = os.fstat(self._lock_fd)
            current_lock = os.stat(
                CAMPAIGN_LOCK_FILENAME,
                dir_fd=self._base_fd,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise MarketNoSendError("Decision Radar campaign reservation was lost") from exc
        if (
            not stat.S_ISDIR(anchored_base.st_mode)
            or not stat.S_ISDIR(current_base.st_mode)
            or _identity(anchored_base) != self._base_dir_identity
            or _identity(current_base) != self._base_dir_identity
        ):
            raise MarketNoSendError("Decision Radar campaign base identity changed")
        if (
            not stat.S_ISDIR(anchored_state_dir.st_mode)
            or not stat.S_ISDIR(current_state_dir.st_mode)
            or _identity(anchored_state_dir) != self._state_dir_identity
            or _identity(current_state_dir) != self._state_dir_identity
        ):
            raise MarketNoSendError(
                "Decision Radar campaign state directory identity changed"
            )
        if not stat.S_ISREG(anchored_lock.st_mode):
            raise MarketNoSendError("Decision Radar campaign lock is not a regular file")
        if (
            not stat.S_ISREG(current_lock.st_mode)
            or _identity(anchored_lock) != self._lock_identity
            or _identity(current_lock) != self._lock_identity
        ):
            raise MarketNoSendError("Decision Radar campaign lock identity changed")


def campaign_state_dir(artifact_base_dir: Path) -> Path:
    return Path(artifact_base_dir).expanduser().absolute() / CAMPAIGN_STATE_NAMESPACE


def campaign_reservation_path(artifact_base_dir: Path) -> Path:
    """Return the stable root-scoped cadence receipt path."""

    return (
        Path(artifact_base_dir).expanduser().absolute()
        / CAMPAIGN_RESERVATION_FILENAME
    )


@contextmanager
def acquire_campaign_reservation(
    artifact_base_dir: Path,
    *,
    artifact_namespace: str,
    acquired_at: datetime | None = None,
) -> Iterator[CampaignReservation]:
    """Acquire without waiting; an OS lock, never lease age, owns exclusivity.

    An ``active`` JSON row left by a crashed process is reclaimed only after the
    advisory lock is acquired.  Time alone can never steal a live reservation.
    """

    base = Path(artifact_base_dir).expanduser().absolute()
    namespace = str(artifact_namespace or "").strip()
    if not _NAMESPACE_RE.fullmatch(namespace) or namespace in {".", ".."}:
        raise MarketNoSendError("invalid Decision Radar campaign namespace")
    now = _utc(acquired_at or datetime.now(timezone.utc))
    state_dir = campaign_state_dir(base)
    market_no_send_io.ensure_safe_namespace_dir(state_dir)
    lock_fd: int | None = None
    locked = False
    body_failed = False
    release_error: BaseException | None = None
    # The verified base and state directory remain descriptor-anchored for the
    # whole provider call and shared-history commit.  The lock is deliberately
    # a child of the stable base, not of the replaceable campaign state
    # directory, so replacing that directory cannot create a second lock realm.
    # This package-private helper is the same no-follow boundary used by the
    # public artifact I/O functions.
    with market_no_send_io._open_verified_namespace_dir(state_dir) as anchored:  # noqa: SLF001
        base_fd, namespace_fd, _name, state_dir_info = anchored
        base_info = os.fstat(base_fd)
        flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        try:
            lock_fd = os.open(CAMPAIGN_LOCK_FILENAME, flags, 0o600, dir_fd=base_fd)
            opened = os.fstat(lock_fd)
            current = os.stat(
                CAMPAIGN_LOCK_FILENAME,
                dir_fd=base_fd,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
            ):
                raise MarketNoSendError("Decision Radar campaign lock identity changed")
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except OSError as exc:
                if exc.errno in {errno.EACCES, errno.EAGAIN}:
                    raise CampaignReservationBusy(
                        "another Decision Radar campaign operation is active"
                    ) from exc
                raise MarketNoSendError("Decision Radar campaign lock is unavailable") from exc

            previous_status, next_provider_call_at = _previous_reservation_state(
                base,
                checked_at=now,
            )
            reservation = CampaignReservation(
                artifact_base_dir=base,
                state_dir=state_dir,
                artifact_namespace=namespace,
                reservation_id=uuid.uuid4().hex,
                acquired_at=now,
                expires_at=now + _DEFAULT_STALE_AFTER,
                previous_reservation_status=previous_status,
                next_provider_call_at=next_provider_call_at,
                _base_fd=base_fd,
                _state_dir_fd=namespace_fd,
                _base_dir_identity=_identity(base_info),
                _state_dir_identity=_identity(state_dir_info),
                _lock_identity=_identity(opened),
                _lock_fd=lock_fd,
            )
            _write_reservation(reservation, status="active")
            try:
                yield reservation
            except BaseException:
                body_failed = True
                raise
            finally:
                try:
                    _write_reservation(
                        reservation,
                        status="released",
                        released_at=datetime.now(timezone.utc),
                    )
                except BaseException as exc:  # lock release must still happen
                    release_error = exc
                finally:
                    reservation._active = False  # noqa: SLF001 - owned lifecycle field
        finally:
            if locked and lock_fd is not None:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            if lock_fd is not None:
                os.close(lock_fd)
        if release_error is not None and not body_failed:
            raise release_error


def blocked_generation_result(
    *,
    readiness: MarketNoSendReadiness,
    profile: str,
    artifact_namespace: str,
    data_mode: str,
    observed_at: datetime,
    failure_class: str,
) -> MarketNoSendGenerationResult:
    """Build the common no-call result for preflight or reservation blockers."""

    return MarketNoSendGenerationResult(
        status="blocked",
        profile=profile,
        artifact_namespace=artifact_namespace,
        namespace_dir=None,
        data_mode=data_mode,
        provider="coingecko",
        observed_at=_utc(observed_at).isoformat(),
        live_provider_authorized=readiness.live_provider_authorized,
        provider_call_attempted=False,
        provider_request_succeeded=False,
        failure_class=failure_class,
        data_acquisition_mode="preflight_only",
        candidate_source_mode="preflight_only",
    )


def assess_campaign_reservation(
    artifact_base_dir: Path,
    *,
    checked_at: datetime,
    owner_reservation_id: str | None = None,
) -> dict[str, object]:
    """Read one call-spacing/stale reservation without acquiring or writing."""

    try:
        payload = _read_reservation_payload(artifact_base_dir)
        if payload is None:
            return {"allowed": True, "reason": None, "next_provider_call_at": None}
        state = _validated_reservation_payload(payload)
    except (MarketNoSendError, OSError):
        return {
            "allowed": False,
            "reason": "Decision Radar campaign reservation state is invalid",
            "next_provider_call_at": None,
        }
    now = _utc(checked_at)
    if payload.get("reservation_id") == owner_reservation_id:
        return {"allowed": True, "reason": None, "next_provider_call_at": None}
    next_call = state["next_provider_call_at"]
    if isinstance(next_call, datetime) and next_call > now:
        return {
            "allowed": False,
            "reason": f"Decision Radar provider call is reserved until {next_call.isoformat()}",
            "next_provider_call_at": next_call.isoformat(),
        }
    if payload.get("status") == "active" and state["expires_at"] > now:
        return {
            "allowed": False,
            "reason": (
                "Decision Radar campaign reservation is active until "
                f"{state['expires_at'].isoformat()}"
            ),
            "next_provider_call_at": None,
        }
    return {"allowed": True, "reason": None, "next_provider_call_at": None}


def mark_provider_call_reserved(
    reservation: CampaignReservation,
    *,
    attempted_at: datetime,
    minimum_spacing: timedelta,
) -> None:
    """Persist call spacing before entering the provider network boundary."""

    attempted = _utc(attempted_at)
    if minimum_spacing <= timedelta(0):
        raise MarketNoSendError("Decision Radar provider call spacing must be positive")
    reservation.assert_active(reservation.artifact_base_dir)
    reservation.provider_call_reserved_at = attempted
    reservation.next_provider_call_at = attempted + minimum_spacing
    _write_reservation(reservation, status="active")


def _previous_reservation_state(
    artifact_base_dir: Path,
    *,
    checked_at: datetime,
) -> tuple[str, datetime | None]:
    payload = _read_reservation_payload(artifact_base_dir)
    if payload is None:
        return "none", None
    state = _validated_reservation_payload(payload)
    now = _utc(checked_at)
    next_call = state["next_provider_call_at"]
    if isinstance(next_call, datetime) and next_call > now:
        raise CampaignReservationBusy(
            f"Decision Radar provider call is reserved until {next_call.isoformat()}"
        )
    if payload.get("status") == "active" and state["expires_at"] > now:
        raise CampaignReservationBusy(
            "an orphaned Decision Radar campaign reservation has not expired"
        )
    previous = "stale_active_reclaimed" if payload.get("status") == "active" else "released"
    return previous, next_call if isinstance(next_call, datetime) else None


def provider_call_may_have_been_reserved(
    artifact_base_dir: Path,
    *,
    artifact_namespace: str,
) -> bool:
    """Conservatively identify a pre-network reservation for one namespace.

    An unreadable or malformed cadence receipt is treated as possible call
    evidence.  Readiness already fails closed on the same condition, so the
    attempt ledger must not under-report a request or encourage an immediate
    retry after a boundary failure.
    """

    namespace = str(artifact_namespace or "").strip()
    if not _NAMESPACE_RE.fullmatch(namespace) or namespace in {".", ".."}:
        raise MarketNoSendError("invalid Decision Radar campaign namespace")
    try:
        payload = _read_reservation_payload(artifact_base_dir)
        if payload is None:
            return False
        state = _validated_reservation_payload(payload)
    except (MarketNoSendError, OSError):
        return True
    return bool(
        payload.get("artifact_namespace") == namespace
        and isinstance(state["provider_call_reserved_at"], datetime)
    )


def _read_reservation_payload(
    artifact_base_dir: Path,
) -> dict[str, object] | None:
    """Read the stable receipt, falling back to the pre-v2 location once."""

    base = Path(artifact_base_dir).expanduser().absolute()
    paths = (
        campaign_reservation_path(base),
        campaign_state_dir(base) / CAMPAIGN_RESERVATION_FILENAME,
    )
    for path in paths:
        try:
            raw = market_no_send_io.read_regular_bytes(path, missing_ok=True)
        except MarketNoSendError:
            if path == paths[1] and not path.parent.exists():
                continue
            raise
        if raw is not None:
            return market_no_send_io.read_json_object(path)
    return None


def _validated_reservation_payload(payload: dict[str, object]) -> dict[str, datetime | None]:
    artifact_namespace = payload.get("artifact_namespace")
    if (
        payload.get("contract_version") != 1
        or payload.get("row_type") != "decision_radar_campaign_reservation"
        or payload.get("status") not in {"active", "released"}
        or not isinstance(payload.get("reservation_id"), str)
        or not isinstance(artifact_namespace, str)
        or not _NAMESPACE_RE.fullmatch(artifact_namespace)
        or artifact_namespace in {".", ".."}
    ):
        raise MarketNoSendError("Decision Radar campaign reservation state is invalid")
    acquired_at = _parse_aware(payload.get("acquired_at"))
    expires_at = _parse_aware(payload.get("expires_at"))
    next_call_raw = payload.get("next_provider_call_at")
    next_call = _parse_aware(next_call_raw) if next_call_raw not in (None, "") else None
    reserved_raw = payload.get("provider_call_reserved_at")
    reserved_at = _parse_aware(reserved_raw) if reserved_raw not in (None, "") else None
    if acquired_at is None or expires_at is None or expires_at <= acquired_at:
        raise MarketNoSendError("Decision Radar campaign reservation clock is invalid")
    if next_call_raw not in (None, "") and next_call is None:
        raise MarketNoSendError("Decision Radar provider call reservation clock is invalid")
    if reserved_raw not in (None, "") and reserved_at is None:
        raise MarketNoSendError("Decision Radar provider call reservation clock is invalid")
    if reserved_at is not None and (
        next_call is None or next_call <= reserved_at
    ):
        raise MarketNoSendError("Decision Radar provider call reservation clock is invalid")
    return {
        "acquired_at": acquired_at,
        "expires_at": expires_at,
        "next_provider_call_at": next_call,
        "provider_call_reserved_at": reserved_at,
    }


def _write_reservation(
    reservation: CampaignReservation,
    *,
    status: str,
    released_at: datetime | None = None,
) -> None:
    reservation.assert_active(reservation.artifact_base_dir)
    payload = {
        "contract_version": 1,
        "row_type": "decision_radar_campaign_reservation",
        "status": status,
        "reservation_id": reservation.reservation_id,
        "artifact_namespace": reservation.artifact_namespace,
        "acquired_at": reservation.acquired_at.isoformat(),
        "expires_at": reservation.expires_at.isoformat(),
        "next_provider_call_at": (
            reservation.next_provider_call_at.isoformat()
            if reservation.next_provider_call_at else None
        ),
        "provider_call_reserved_at": (
            reservation.provider_call_reserved_at.isoformat()
            if reservation.provider_call_reserved_at else None
        ),
        "released_at": _utc(released_at).isoformat() if released_at else None,
        "process_id": os.getpid(),
        "previous_reservation_status": reservation.previous_reservation_status,
        "stale_policy": "active_os_lock_never_stolen;orphan_reclaim_after_expiry",
        "no_send": True,
        "research_only": True,
    }
    _write_stable_reservation(reservation, payload)
    reservation.assert_active(reservation.artifact_base_dir)


def _write_stable_reservation(
    reservation: CampaignReservation,
    payload: dict[str, object],
) -> None:
    """Atomically write through the reservation's anchored artifact-base fd."""

    leaf = CAMPAIGN_RESERVATION_FILENAME
    temporary = f".{leaf}.{os.getpid()}.{time.time_ns()}.tmp"
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptor: int | None = None
    temporary_exists = False
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        try:
            existing = os.stat(
                leaf,
                dir_fd=reservation._base_fd,  # noqa: SLF001 - anchored owner fd
                follow_symlinks=False,
            )
        except FileNotFoundError:
            existing = None
        if existing is not None and not stat.S_ISREG(existing.st_mode):
            raise MarketNoSendError(
                "Decision Radar campaign reservation target is not a regular file"
            )
        descriptor = os.open(
            temporary,
            flags,
            0o600,
            dir_fd=reservation._base_fd,  # noqa: SLF001 - anchored owner fd
        )
        temporary_exists = True
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        reservation.assert_active(reservation.artifact_base_dir)
        os.rename(
            temporary,
            leaf,
            src_dir_fd=reservation._base_fd,  # noqa: SLF001 - anchored owner fd
            dst_dir_fd=reservation._base_fd,  # noqa: SLF001 - anchored owner fd
        )
        temporary_exists = False
        written = os.stat(
            leaf,
            dir_fd=reservation._base_fd,  # noqa: SLF001 - anchored owner fd
            follow_symlinks=False,
        )
        if not stat.S_ISREG(written.st_mode):
            raise OSError(errno.EINVAL, "campaign reservation replacement is not regular")
        os.fsync(reservation._base_fd)  # noqa: SLF001 - anchored owner fd
    except MarketNoSendError:
        raise
    except OSError as exc:
        raise MarketNoSendError("Decision Radar campaign reservation write failed") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary_exists:
            try:
                os.unlink(
                    temporary,
                    dir_fd=reservation._base_fd,  # noqa: SLF001 - anchored owner fd
                )
            except FileNotFoundError:
                pass


def _identity(info: os.stat_result) -> tuple[int, int]:
    return info.st_dev, info.st_ino


def _parse_aware(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _utc(parsed) if parsed.tzinfo is not None else None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise MarketNoSendError("Decision Radar campaign lock clock must be timezone-aware")
    return value.astimezone(timezone.utc)


__all__ = (
    "CAMPAIGN_LOCK_FILENAME",
    "CAMPAIGN_RESERVATION_FILENAME",
    "CAMPAIGN_STATE_NAMESPACE",
    "CampaignReservation",
    "CampaignReservationBusy",
    "acquire_campaign_reservation",
    "assess_campaign_reservation",
    "blocked_generation_result",
    "campaign_reservation_path",
    "campaign_state_dir",
    "mark_provider_call_reserved",
    "provider_call_may_have_been_reserved",
)
