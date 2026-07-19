"""Strict offline Bitget announcement response contract.

The module validates supplied synthetic bytes against Bitget's documented
public announcement endpoint.  It has no HTTP client, environment access,
artifact persistence, routing, score, notification, order, or trading path.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit


CONTRACT_VERSION = "crypto_radar_bitget_announcements_v2"
SNAPSHOT_SCHEMA_VERSION = "crypto_radar.bitget_announcements.v2"
PROVIDER_ID = "bitget_announcements"
SOURCE_CLASS = "official_exchange"
PUBLIC_API_BASE = "https://api.bitget.com"
ANNOUNCEMENTS_PATH = "/api/v2/public/annoucements"
OFFICIAL_API_DOC = "https://www.bitget.com/api-doc/common/notice/Get-All-Notices"
RESPONSE_CODE_OK = "00000"
RESPONSE_MESSAGE_OK = "success"
DEFAULT_LANGUAGE = "en_US"
MAX_PAGE_SIZE = 10
MAX_RESPONSE_PAGES = 20
MAX_RESPONSE_ROWS = MAX_PAGE_SIZE * MAX_RESPONSE_PAGES
MAX_RESPONSE_BYTES_PER_PAGE = 2_000_000
MAX_REQUEST_WINDOW_DAYS = 31
MAX_PROVIDER_CLOCK_SKEW_SECONDS = 60
MAX_TITLE_CHARS = 512
MAX_DESCRIPTION_CHARS = 8_192

ANNOUNCEMENT_SUBTYPES = {
    "latest_news": frozenset({"announcements", "news"}),
    "coin_listings": frozenset({"spot", "futures", "margin", "copy_trading"}),
    "product_updates": frozenset({"spot", "futures", "margin", "copy_trading"}),
    "security": frozenset({"security_information"}),
    "api_trading": frozenset({"api_announcement"}),
    "symbol_delisting": frozenset({"trading_pair_delisting"}),
    "maintenance_system_updates": frozenset(
        {"asset_maintenance", "system_updates", "spot_maintenance", "futures_maintenance"}
    ),
}
ANNOUNCEMENT_TYPES = frozenset(ANNOUNCEMENT_SUBTYPES)

_TOP_LEVEL_KEYS = frozenset({"code", "msg", "requestTime", "data"})
_ITEM_KEYS = frozenset(
    {
        "annId", "annTitle", "annDesc", "cTime", "language", "annUrl",
        "annType", "annSubType",
    }
)
_LINEAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ANNOUNCEMENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class BitgetAnnouncementError(ValueError):
    """Raised when supplied bytes violate the closed Bitget contract."""


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise BitgetAnnouncementError("response_duplicate_json_key")
        value[key] = item
    return value


def _aware_utc(value: datetime | str, field: str) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise BitgetAnnouncementError(f"{field}_invalid") from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise BitgetAnnouncementError(f"{field}_invalid")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BitgetAnnouncementError(f"{field}_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _integer(value: object, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise BitgetAnnouncementError(f"{field}_invalid")
    return value


def _integer_string(value: object, field: str, *, minimum: int = 0) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        raise BitgetAnnouncementError(f"{field}_invalid")
    number = int(value)
    if number < minimum:
        raise BitgetAnnouncementError(f"{field}_invalid")
    return number


def _text(value: object, field: str, maximum: int, *, required: bool) -> str:
    if not isinstance(value, str):
        raise BitgetAnnouncementError(f"{field}_invalid")
    text = value.strip()
    if (required and not text) or len(text) > maximum or "\x00" in text:
        raise BitgetAnnouncementError(f"{field}_invalid")
    return text


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], field: str) -> None:
    if set(value) != expected:
        raise BitgetAnnouncementError(f"{field}_schema_invalid")


def _request_values(
    *,
    start_time: datetime | str,
    end_time: datetime | str,
    limit: int,
    language: str,
    announcement_type: str | None,
) -> tuple[datetime, datetime, dict[str, str]]:
    start = _aware_utc(start_time, "request_start_time")
    end = _aware_utc(end_time, "request_end_time")
    if start >= end or end - start > timedelta(days=MAX_REQUEST_WINDOW_DAYS):
        raise BitgetAnnouncementError("request_window_invalid")
    size = _integer(limit, "requested_limit", minimum=1)
    if size > MAX_PAGE_SIZE:
        raise BitgetAnnouncementError("requested_limit_invalid")
    if language != DEFAULT_LANGUAGE:
        raise BitgetAnnouncementError("request_language_invalid")
    if announcement_type is not None and announcement_type not in ANNOUNCEMENT_TYPES:
        raise BitgetAnnouncementError("request_announcement_type_invalid")
    params = {
        "startTime": str(int(start.timestamp() * 1000)),
        "endTime": str(int(end.timestamp() * 1000)),
        "limit": str(size),
        "language": language,
    }
    if announcement_type is not None:
        params = {"annType": announcement_type, **params}
    return start, end, params


def build_bitget_announcement_request_plan(
    *,
    start_time: datetime | str,
    end_time: datetime | str,
    limit: int = MAX_PAGE_SIZE,
    language: str = DEFAULT_LANGUAGE,
    announcement_type: str | None = None,
) -> dict[str, object]:
    """Describe the bounded public cursor contract without executing it."""

    _start, _end, params = _request_values(
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        language=language,
        announcement_type=announcement_type,
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "provider": PROVIDER_ID,
        "method": "GET",
        "base_url": PUBLIC_API_BASE,
        "path": ANNOUNCEMENTS_PATH,
        "path_spelling_verified": "annoucements",
        "initial_query": params,
        "initial_url": f"{PUBLIC_API_BASE}{ANNOUNCEMENTS_PATH}?{urlencode(params)}",
        "pagination_policy": "next_cursor_is_last_annId_from_previous_response",
        "pagination_completion_policy": "explicit_empty_response_required",
        "maximum_request_count": MAX_RESPONSE_PAGES,
        "maximum_response_rows": MAX_RESPONSE_ROWS,
        "maximum_response_bytes_per_page": MAX_RESPONSE_BYTES_PER_PAGE,
        "credentials_required": False,
        "provider_call_authorized": False,
        "provider_call_planned": False,
        "provider_call_attempted": False,
        "redirects_allowed": False,
        "retries_allowed": False,
        "writes": 0,
        "directional_authority": False,
        "research_only": True,
    }


def _decode_response(body: bytes, page: int) -> Mapping[str, Any]:
    if not isinstance(body, bytes) or not body or len(body) > MAX_RESPONSE_BYTES_PER_PAGE:
        raise BitgetAnnouncementError(f"response_{page}_bytes_invalid")
    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=_object_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BitgetAnnouncementError(f"response_{page}_json_invalid") from exc
    if not isinstance(value, Mapping):
        raise BitgetAnnouncementError(f"response_{page}_object_invalid")
    return value


def _safe_source_url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 2_048:
        raise BitgetAnnouncementError("announcement_url_invalid")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise BitgetAnnouncementError("announcement_url_invalid") from exc
    prefixes = ("/support/articles/", "/en/support/articles/", "/en_US/support/articles/")
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.bitget.com"
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path.startswith(prefixes)
        or parsed.query
        or parsed.fragment
        or parse_qsl(parsed.query, keep_blank_values=True)
    ):
        raise BitgetAnnouncementError("announcement_url_invalid")
    return value


def _parse_page(
    body: bytes,
    *,
    page: int,
    acquired_at: datetime,
    lineage: str,
) -> tuple[list[Mapping[str, Any]], int, str]:
    value = _decode_response(body, page)
    _exact_keys(value, _TOP_LEVEL_KEYS, f"response_{page}")
    if value.get("code") != RESPONSE_CODE_OK or value.get("msg") != RESPONSE_MESSAGE_OK:
        raise BitgetAnnouncementError(f"response_{page}_status_not_ok")
    provider_clock_ms = _integer(value.get("requestTime"), "response_request_time", minimum=1)
    try:
        provider_clock = datetime.fromtimestamp(provider_clock_ms / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise BitgetAnnouncementError("response_request_time_invalid") from exc
    if abs((provider_clock - acquired_at).total_seconds()) > MAX_PROVIDER_CLOCK_SKEW_SECONDS:
        raise BitgetAnnouncementError("response_request_time_outside_acquisition_window")
    rows = value.get("data")
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise BitgetAnnouncementError(f"response_{page}_data_invalid")
    if len(rows) > MAX_PAGE_SIZE:
        raise BitgetAnnouncementError(f"response_{page}_row_count_invalid")
    if not isinstance(lineage, str) or not _LINEAGE_RE.fullmatch(lineage):
        raise BitgetAnnouncementError(f"response_{page}_lineage_invalid")
    return rows, provider_clock_ms, _iso(provider_clock)


def _normalize_item(
    row: Mapping[str, Any],
    *,
    page: int,
    acquired_at: datetime,
    lineage: str,
    response_sha256: str,
    request_start: datetime,
    request_end: datetime,
) -> dict[str, object]:
    _exact_keys(row, _ITEM_KEYS, "announcement_item")
    announcement_id = row.get("annId")
    if not isinstance(announcement_id, str) or not _ANNOUNCEMENT_ID_RE.fullmatch(
        announcement_id
    ):
        raise BitgetAnnouncementError("announcement_id_invalid")
    publication_ms = _integer_string(row.get("cTime"), "announcement_publication_time", minimum=1)
    try:
        publication = datetime.fromtimestamp(publication_ms / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise BitgetAnnouncementError("announcement_publication_time_invalid") from exc
    if not request_start <= publication <= request_end:
        raise BitgetAnnouncementError("announcement_publication_outside_request_window")
    if publication > acquired_at + timedelta(seconds=MAX_PROVIDER_CLOCK_SKEW_SECONDS):
        raise BitgetAnnouncementError("announcement_publication_in_future")
    announcement_type = row.get("annType")
    subtype = row.get("annSubType")
    if (
        announcement_type not in ANNOUNCEMENT_SUBTYPES
        or subtype not in ANNOUNCEMENT_SUBTYPES[announcement_type]
    ):
        raise BitgetAnnouncementError("announcement_type_subtype_invalid")
    if row.get("language") != DEFAULT_LANGUAGE:
        raise BitgetAnnouncementError("announcement_language_invalid")
    return {
        "provider": PROVIDER_ID,
        "source_class": SOURCE_CLASS,
        "announcement_id": announcement_id,
        "title": _text(row.get("annTitle"), "announcement_title", MAX_TITLE_CHARS, required=True),
        "description": _text(
            row.get("annDesc"), "announcement_description", MAX_DESCRIPTION_CHARS, required=False
        ),
        "description_status": "deprecated_provider_field_not_complete_article",
        "announcement_type": announcement_type,
        "announcement_subtype": subtype,
        "publication_at": _iso(publication),
        "publication_time_unix_ms": publication_ms,
        "language": DEFAULT_LANGUAGE,
        "source_url": _safe_source_url(row.get("annUrl")),
        "page_number": page,
        "response_sha256": response_sha256,
        "request_lineage_id": lineage,
        "event_time": None,
        "event_time_basis": "not_inferred_from_publication",
        "catalyst_context_only": True,
        "directional_authority": False,
        "decision_policy_applied": False,
        "research_only": True,
    }


def normalize_bitget_announcement_pages(
    response_bodies: Sequence[bytes],
    *,
    acquired_at_by_page: Sequence[datetime | str],
    request_lineage_ids: Sequence[str],
    request_cursors: Sequence[str | None],
    start_time: datetime | str,
    end_time: datetime | str,
    limit: int = MAX_PAGE_SIZE,
    language: str = DEFAULT_LANGUAGE,
    announcement_type: str | None = None,
) -> dict[str, object]:
    """Normalize a bounded cursor prefix without I/O or side effects."""

    count = len(response_bodies)
    if (
        count == 0
        or count > MAX_RESPONSE_PAGES
        or len(acquired_at_by_page) != count
        or len(request_lineage_ids) != count
        or len(request_cursors) != count
        or request_cursors[0] is not None
    ):
        raise BitgetAnnouncementError("response_bundle_invalid")
    request_start, request_end, params = _request_values(
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        language=language,
        announcement_type=announcement_type,
    )
    acquired = [
        _aware_utc(value, f"page_{page}_acquired_at")
        for page, value in enumerate(acquired_at_by_page, start=1)
    ]
    if acquired != sorted(acquired) or request_end > acquired[0] + timedelta(
        seconds=MAX_PROVIDER_CLOCK_SKEW_SECONDS
    ):
        raise BitgetAnnouncementError("response_acquisition_window_invalid")
    if len(set(request_lineage_ids)) != count:
        raise BitgetAnnouncementError("response_lineage_duplicate")
    announcements: list[dict[str, object]] = []
    response_hashes: dict[str, str] = {}
    provider_clocks: dict[str, str] = {}
    row_counts: dict[str, int] = {}
    prior_last_id: str | None = None
    for page, body in enumerate(response_bodies, start=1):
        cursor = request_cursors[page - 1]
        if page > 1 and cursor != prior_last_id:
            raise BitgetAnnouncementError("response_cursor_chain_invalid")
        rows, _clock_ms, provider_clock = _parse_page(
            body,
            page=page,
            acquired_at=acquired[page - 1],
            lineage=request_lineage_ids[page - 1],
        )
        if len(rows) > limit:
            raise BitgetAnnouncementError("response_requested_limit_exceeded")
        if page < count and not rows:
            raise BitgetAnnouncementError("response_pagination_after_terminal_page")
        digest = hashlib.sha256(body).hexdigest()
        normalized = [
            _normalize_item(
                row,
                page=page,
                acquired_at=acquired[page - 1],
                lineage=request_lineage_ids[page - 1],
                response_sha256=digest,
                request_start=request_start,
                request_end=request_end,
            )
            for row in rows
        ]
        if announcement_type is not None and any(
            row["announcement_type"] != announcement_type for row in normalized
        ):
            raise BitgetAnnouncementError("response_announcement_type_filter_mismatch")
        announcements.extend(normalized)
        response_hashes[str(page)] = digest
        provider_clocks[str(page)] = provider_clock
        row_counts[str(page)] = len(rows)
        prior_last_id = normalized[-1]["announcement_id"] if normalized else prior_last_id
    identities = [row["announcement_id"] for row in announcements]
    if len(set(identities)) != len(identities):
        raise BitgetAnnouncementError("announcement_identity_duplicate")
    publication_times = [row["publication_time_unix_ms"] for row in announcements]
    if publication_times != sorted(publication_times, reverse=True):
        raise BitgetAnnouncementError("announcement_publication_order_invalid")
    complete = row_counts[str(count)] == 0
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "provider": PROVIDER_ID,
        "source_class": SOURCE_CLASS,
        "endpoint": f"GET {PUBLIC_API_BASE}{ANNOUNCEMENTS_PATH}",
        "path_spelling_verified": "annoucements",
        "official_api_doc": OFFICIAL_API_DOC,
        "request_parameters": {
            **params,
            "cursorPolicy": "last_annId",
            "terminalPolicy": "explicitEmptyResponse",
        },
        "request_cursors": [cursor for cursor in request_cursors],
        "request_count_observed": count,
        "maximum_request_count": MAX_RESPONSE_PAGES,
        "maximum_response_rows": MAX_RESPONSE_ROWS,
        "requested_limit": limit,
        "accepted_announcement_count": len(announcements),
        "coverage_status": "complete" if complete else "partial",
        "coverage_complete": complete,
        "healthy_empty": complete and not announcements,
        "completion_evidence": (
            "explicit_empty_terminal_response" if complete else "not_observed"
        ),
        "terminal_empty_page_number": count if complete else None,
        "next_cursor": None if complete else prior_last_id,
        "response_row_count_by_page": row_counts,
        "response_sha256_by_page": response_hashes,
        "provider_request_time_by_page": provider_clocks,
        "acquired_at_by_page": {
            str(page): _iso(value) for page, value in enumerate(acquired, start=1)
        },
        "request_lineage_id_by_page": {
            str(page): value for page, value in enumerate(request_lineage_ids, start=1)
        },
        "announcements": announcements,
        "provider_calls": 0,
        "writes": 0,
        "credentials_read": False,
        "authorization_created": False,
        "route_or_score_effect": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        "directional_authority": False,
        "research_only": True,
    }


def run_fixture_smoke(fixture_dir: Path) -> dict[str, object]:
    bodies = tuple(path.read_bytes() for path in sorted(fixture_dir.glob("page_*.json")))
    snapshot = normalize_bitget_announcement_pages(
        bodies,
        acquired_at_by_page=(
            "2026-07-19T01:35:01Z",
            "2026-07-19T01:35:02Z",
            "2026-07-19T01:35:03Z",
        ),
        request_lineage_ids=(
            "fixture.bitget.page1",
            "fixture.bitget.page2",
            "fixture.bitget.page3",
        ),
        request_cursors=(None, "900002", "900001"),
        start_time="2026-07-19T00:00:00Z",
        end_time="2026-07-19T01:35:00Z",
        limit=2,
    )
    return {
        "mode": "offline_fixture",
        "status": snapshot["coverage_status"],
        "snapshot": snapshot,
        "request_plan": build_bitget_announcement_request_plan(
            start_time="2026-07-19T00:00:00Z",
            end_time="2026-07-19T01:35:00Z",
            limit=2,
        ),
        "provider_calls": 0,
        "writes": 0,
        "credentials_read": False,
        "authorization_created": False,
        "orders": 0,
        "trades": 0,
        "paper_trades": 0,
        "telegram_sends": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
        "route_or_score_effect": False,
        "protocol_v2_evidence_eligible": False,
        "research_only": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=(Path(__file__).resolve().parents[3] / "fixtures" / "bitget_announcements"),
    )
    args = parser.parse_args(argv)
    try:
        result = run_fixture_smoke(args.fixture_dir)
    except (BitgetAnnouncementError, OSError, ValueError) as exc:
        print(f"radar_bitget_announcements_smoke_blocked: {type(exc).__name__}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


__all__ = (
    "ANNOUNCEMENT_SUBTYPES",
    "ANNOUNCEMENT_TYPES",
    "ANNOUNCEMENTS_PATH",
    "BitgetAnnouncementError",
    "CONTRACT_VERSION",
    "MAX_PAGE_SIZE",
    "MAX_RESPONSE_PAGES",
    "OFFICIAL_API_DOC",
    "PROVIDER_ID",
    "build_bitget_announcement_request_plan",
    "main",
    "normalize_bitget_announcement_pages",
    "run_fixture_smoke",
)


if __name__ == "__main__":
    raise SystemExit(main())
