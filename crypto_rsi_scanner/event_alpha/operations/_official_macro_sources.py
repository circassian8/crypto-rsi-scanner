"""Closed source contracts and secure I/O for official macro acquisition.

This private support module keeps provider transport and operator-file handling
separate from acquisition orchestration.  It deliberately exposes no CLI and
performs no artifact publication.
"""

from __future__ import annotations

import hashlib
import os
import re
import socket
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..radar.calendar.official_macro import (
    BEA_RELEASE_DATES_URL,
    BLS_RELEASE_CALENDAR_URL,
    FEDERAL_RESERVE_FOMC_URL,
)
from .common import (
    OPENAI_KEY_RE,
    PROVIDER_TOKEN_VALUE_RE,
    TELEGRAM_BOT_TOKEN_VALUE_RE,
)


_SENSITIVE_TEXT_RE = re.compile(
    r"(?:authorization\s*:\s*bearer|(?:api[_-]?key|access[_-]?token|password|passwd|secret|credential)\s*[:=]|-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----)",
    re.IGNORECASE,
)
_STANDALONE_BEARER_RE = re.compile(
    r"\bBearer\s+[A-Za-z0-9._~+/-]{8,}\b", re.IGNORECASE
)
_CHECKED_IN_NONLIVE_PATH_RE = re.compile(
    r"(?:^|[._-])(?:fixtures?|tests?|mocks?|replays?)(?:[._-]|$)",
    re.IGNORECASE,
)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CHECKED_IN_FIXTURE_SHA256 = {
    "bea": frozenset(
        {"322d9adb4f181d50193d2c104a2fc4c1a2c455f3370d6195c1e8d67a80c5bdc5"}
    ),
    "bls": frozenset(
        {"4bf5e5f5079f5be19c0e68f52b3b80a78e0caa38d0429f892efbfc90e4e7a4a8"}
    ),
    "federal_reserve": frozenset(
        {"7dabe7e08a1ef1b7c866f8bf459188247ecf23a583bb03a2f4593bef13f8ce43"}
    ),
}


@dataclass(frozen=True)
class _OfficialMacroSourceSpec:
    name: str
    url: str
    raw_filename: str
    maximum_bytes: int
    accepted_content_types: frozenset[str]


OfficialMacroSourceSpec = _OfficialMacroSourceSpec


OFFICIAL_MACRO_SOURCES = (
    OfficialMacroSourceSpec(
        name="bls",
        url=BLS_RELEASE_CALENDAR_URL,
        raw_filename="bls_release_calendar.ics",
        maximum_bytes=512 * 1024,
        accepted_content_types=frozenset(
            {"text/calendar", "text/plain", "application/octet-stream"}
        ),
    ),
    OfficialMacroSourceSpec(
        name="federal_reserve",
        url=FEDERAL_RESERVE_FOMC_URL,
        raw_filename="federal_reserve_fomc.html",
        maximum_bytes=1024 * 1024,
        accepted_content_types=frozenset({"text/html", "application/xhtml+xml"}),
    ),
    OfficialMacroSourceSpec(
        name="bea",
        url=BEA_RELEASE_DATES_URL,
        raw_filename="bea_release_dates.json",
        maximum_bytes=256 * 1024,
        accepted_content_types=frozenset(
            {"application/json", "text/json", "text/plain"}
        ),
    ),
)
_SOURCE_BY_NAME = {source.name: source for source in OFFICIAL_MACRO_SOURCES}


@dataclass(frozen=True)
class _OfficialMacroHTTPResponse:
    body: bytes
    status: int
    content_type: str
    final_url: str


OfficialMacroHTTPResponse = _OfficialMacroHTTPResponse
OfficialMacroFetcher = Callable[
    [OfficialMacroSourceSpec, str], OfficialMacroHTTPResponse
]


class _OfficialMacroAcquisitionError(RuntimeError):
    """Closed acquisition failure carrying only safe diagnostic fields."""

    def __init__(
        self,
        reason_code: str,
        *,
        source: str | None = None,
        http_status: int | None = None,
    ) -> None:
        self.reason_code = safe_code(reason_code)
        self.source = source if source in _SOURCE_BY_NAME else None
        self.http_status = (
            int(http_status)
            if isinstance(http_status, int) and 100 <= http_status <= 599
            else None
        )
        super().__init__(self.reason_code)


OfficialMacroAcquisitionError = _OfficialMacroAcquisitionError


def validate_response(
    spec: OfficialMacroSourceSpec,
    response: OfficialMacroHTTPResponse,
) -> bytes:
    if not isinstance(response, OfficialMacroHTTPResponse):
        raise OfficialMacroAcquisitionError("source_response_invalid", source=spec.name)
    if response.status != 200:
        raise OfficialMacroAcquisitionError(
            "source_http_status", source=spec.name, http_status=response.status
        )
    if response.final_url != spec.url:
        raise OfficialMacroAcquisitionError("source_redirect_rejected", source=spec.name)
    content_type = normalized_content_type(response.content_type)
    if content_type not in spec.accepted_content_types:
        raise OfficialMacroAcquisitionError(
            "source_content_type_rejected", source=spec.name
        )
    if not isinstance(response.body, bytes) or not response.body:
        raise OfficialMacroAcquisitionError("source_body_empty", source=spec.name)
    if len(response.body) > spec.maximum_bytes:
        raise OfficialMacroAcquisitionError("source_body_too_large", source=spec.name)
    if _contains_sensitive_bytes(response.body):
        raise OfficialMacroAcquisitionError("source_body_sensitive", source=spec.name)
    return response.body


def fetch_official_source(
    spec: OfficialMacroSourceSpec,
    user_agent: str,
) -> OfficialMacroHTTPResponse:
    """Perform exactly one non-redirecting request for one fixed official URL."""

    if spec not in OFFICIAL_MACRO_SOURCES:
        raise OfficialMacroAcquisitionError("unsupported_source", source=None)
    request = Request(
        spec.url,
        headers={
            "User-Agent": user_agent,
            "Accept": ", ".join(sorted(spec.accepted_content_types)),
        },
        method="GET",
    )
    opener = build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=15.0) as response:
            status = int(response.getcode())
            content_type = response.headers.get_content_type()
            final_url = response.geturl()
            body = response.read(spec.maximum_bytes + 1)
    except HTTPError as exc:
        raise OfficialMacroAcquisitionError(
            "source_http_status", source=spec.name, http_status=int(exc.code)
        ) from None
    except (URLError, TimeoutError, socket.timeout, OSError):
        raise OfficialMacroAcquisitionError(
            "source_request_failed", source=spec.name
        ) from None
    return OfficialMacroHTTPResponse(
        body=body,
        status=status,
        content_type=content_type,
        final_url=final_url,
    )


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def read_local_source(path: Path, *, maximum_bytes: int) -> bytes:
    """Read one unchanged regular local file without following its leaf symlink."""

    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    descriptor: int | None = None
    parent_descriptor: int | None = None
    try:
        parent = path.parent
        if parent.resolve(strict=True) != parent:
            raise OSError("local source parent contains a symlink")
        parent_path_before = os.stat(parent, follow_symlinks=False)
        if not stat.S_ISDIR(parent_path_before.st_mode):
            raise OSError("local source parent is not a directory")
        parent_descriptor = os.open(
            parent,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0),
        )
        parent_before = os.fstat(parent_descriptor)
        if (parent_path_before.st_dev, parent_path_before.st_ino) != (
            parent_before.st_dev,
            parent_before.st_ino,
        ):
            raise OSError("local source parent changed")
        before = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise OSError("local source is not a regular file")
        if before.st_size <= 0 or before.st_size > maximum_bytes:
            raise OfficialMacroAcquisitionError("source_body_size_invalid")
        descriptor = os.open(path.name, flags, dir_fd=parent_descriptor)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or not _same_snapshot(before, opened):
            raise OSError("local source changed before read")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            body = handle.read(maximum_bytes + 1)
            completed = os.fstat(handle.fileno())
        after = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
        parent_path_after = os.stat(parent, follow_symlinks=False)
        if (
            len(body) != completed.st_size
            or not _same_snapshot(opened, completed)
            or not _same_snapshot(completed, after)
            or (parent_before.st_dev, parent_before.st_ino)
            != (parent_path_after.st_dev, parent_path_after.st_ino)
        ):
            raise OSError("local source changed during read")
        if not body or len(body) > maximum_bytes:
            raise OfficialMacroAcquisitionError("source_body_size_invalid")
        if _contains_sensitive_bytes(body):
            raise OfficialMacroAcquisitionError("source_body_sensitive")
        return body
    except OfficialMacroAcquisitionError:
        raise
    except (FileNotFoundError, OSError):
        raise OfficialMacroAcquisitionError("local_source_unavailable") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if parent_descriptor is not None:
            os.close(parent_descriptor)


def is_checked_in_fixture_content(source: str, body: bytes) -> bool:
    """Identify exact checked-in fixture bytes even after a copy or rename."""

    return hashlib.sha256(body).hexdigest() in _CHECKED_IN_FIXTURE_SHA256.get(
        source, frozenset()
    )


def checked_in_nonlive_source_path(path: Path) -> bool:
    """Reject checked-in fixture/test/mock/replay evidence before any write."""

    candidates = (path, path.resolve(strict=False))
    for candidate in candidates:
        try:
            relative = candidate.relative_to(_PROJECT_ROOT)
        except ValueError:
            continue
        if any(_CHECKED_IN_NONLIVE_PATH_RE.search(part) for part in relative.parts):
            return True
    return False


def normalized_content_type(value: Any) -> str:
    return str(value or "").split(";", 1)[0].strip().casefold()


def local_content_type(source: str) -> str:
    return {
        "bls": "text/calendar",
        "federal_reserve": "text/html",
        "bea": "application/json",
    }[source]


def safe_code(value: Any) -> str:
    text = re.sub(r"[^a-z0-9_.:-]+", "_", str(value or "unknown").casefold())
    return text[:120] or "unknown"


def _contains_sensitive_bytes(body: bytes) -> bool:
    text = body.decode("utf-8", errors="replace")
    return any(
        pattern.search(text) is not None
        for pattern in (
            _SENSITIVE_TEXT_RE,
            OPENAI_KEY_RE,
            PROVIDER_TOKEN_VALUE_RE,
            TELEGRAM_BOT_TOKEN_VALUE_RE,
            _STANDALONE_BEARER_RE,
        )
    )


def _same_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
        and left.st_ctime_ns == right.st_ctime_ns
    )


__all__ = (
    "OFFICIAL_MACRO_SOURCES",
    "OfficialMacroAcquisitionError",
    "OfficialMacroFetcher",
    "OfficialMacroHTTPResponse",
    "OfficialMacroSourceSpec",
    "checked_in_nonlive_source_path",
    "fetch_official_source",
    "is_checked_in_fixture_content",
    "local_content_type",
    "normalized_content_type",
    "read_local_source",
    "safe_code",
    "validate_response",
)
