"""Strict offline KuCoin announcement response contract.

KuCoin is the next selected official-announcement source for Decision Radar,
but it is not authorized or active. This module validates already-supplied
synthetic response bytes and builds a non-executable request plan. It has no
HTTP client, environment access, artifact persistence, notification, routing,
score, order, or trading path.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit


CONTRACT_VERSION = "crypto_radar_kucoin_announcements_v1"
SNAPSHOT_SCHEMA_VERSION = "crypto_radar.kucoin_announcements.v1"
PROVIDER_ID = "kucoin_announcements"
SOURCE_CLASS = "official_exchange"
PUBLIC_API_BASE = "https://api.kucoin.com"
ANNOUNCEMENTS_PATH = "/api/v3/announcements"
OFFICIAL_API_DOC = (
    "https://www.kucoin.com/docs-new/rest/spot-trading/market-data/"
    "get-announcements"
)
RESPONSE_CODE_OK = "200000"
DEFAULT_ANNOUNCEMENT_TYPE = "latest-announcements"
DEFAULT_LANGUAGE = "en_US"
MAX_REQUESTED_PAGE_SIZE = 50
MAX_RESPONSE_PAGES = 20
MAX_RESPONSE_ROWS = MAX_REQUESTED_PAGE_SIZE * MAX_RESPONSE_PAGES
MAX_RESPONSE_BYTES_PER_PAGE = 2_000_000
MAX_REQUEST_WINDOW_DAYS = 31
MAX_PROVIDER_CLOCK_SKEW_SECONDS = 60
MAX_TITLE_CHARS = 512
MAX_DESCRIPTION_CHARS = 8_192

ANNOUNCEMENT_TYPES = frozenset(
    {
        "latest-announcements",
        "futures-announcements",
        "activities",
        "product-updates",
        "vip",
        "maintenance-updates",
        "delistings",
        "others",
        "api-campaigns",
        "new-listings",
    }
)

_TOP_LEVEL_KEYS = frozenset({"code", "data"})
_DATA_KEYS = frozenset(
    {"totalNum", "totalPage", "currentPage", "pageSize", "items"}
)
_ITEM_KEYS = frozenset(
    {"annId", "annTitle", "annType", "annDesc", "cTime", "language", "annUrl"}
)
_LINEAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class KuCoinAnnouncementError(ValueError):
    """Raised when supplied bytes violate the closed KuCoin contract."""


@dataclass(frozen=True)
class _KuCoinAnnouncement:
    provider: str
    source_class: str
    announcement_id: int
    title: str
    announcement_types: tuple[str, ...]
    description: str
    description_completeness: str
    publication_at: str
    publication_time_unix_ms: int
    language: str
    source_url: str
    page_number: int
    response_sha256: str
    request_lineage_id: str
    event_time: None
    event_time_basis: str
    catalyst_context_only: bool
    directional_authority: bool
    decision_policy_applied: bool
    research_only: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _KuCoinAnnouncementSnapshot:
    schema_version: str
    contract_version: str
    provider: str
    source_class: str
    endpoint: str
    official_api_doc: str
    request_parameters: tuple[tuple[str, object], ...]
    request_count_observed: int
    maximum_request_count: int
    response_page_size: int
    requested_page_size: int
    provider_adjusted_page_size: bool
    total_announcements_reported: int
    total_pages_reported: int
    observed_pages: tuple[int, ...]
    accepted_announcement_count: int
    coverage_status: str
    coverage_complete: bool
    healthy_empty: bool
    missing_pages: tuple[int, ...]
    response_sha256_by_page: tuple[tuple[int, str], ...]
    acquired_at_by_page: tuple[tuple[int, str], ...]
    request_lineage_id_by_page: tuple[tuple[int, str], ...]
    announcements: tuple[KuCoinAnnouncement, ...]
    provider_calls: int
    writes: int
    credentials_read: bool
    authorization_created: bool
    route_or_score_effect: bool
    protocol_v2_annex_bound: bool
    protocol_v2_evidence_eligible: bool
    research_only: bool = True

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["request_parameters"] = dict(self.request_parameters)
        value["response_sha256_by_page"] = {
            str(page): digest for page, digest in self.response_sha256_by_page
        }
        value["acquired_at_by_page"] = {
            str(page): acquired for page, acquired in self.acquired_at_by_page
        }
        value["request_lineage_id_by_page"] = {
            str(page): lineage for page, lineage in self.request_lineage_id_by_page
        }
        value["announcements"] = [row.to_dict() for row in self.announcements]
        return value


KuCoinAnnouncement = _KuCoinAnnouncement
KuCoinAnnouncementSnapshot = _KuCoinAnnouncementSnapshot


@dataclass(frozen=True)
class _ParsedPage:
    current_page: int
    total_num: int
    total_page: int
    page_size: int
    items: tuple[Mapping[str, Any], ...]
    response_sha256: str
    acquired_at: datetime
    request_lineage_id: str


def _aware_utc(value: datetime | str, field: str) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise KuCoinAnnouncementError(f"{field}_invalid") from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise KuCoinAnnouncementError(f"{field}_invalid")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise KuCoinAnnouncementError(f"{field}_timezone_missing")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _integer(value: object, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise KuCoinAnnouncementError(f"{field}_invalid")
    return value


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], field: str) -> None:
    if set(value) != expected:
        raise KuCoinAnnouncementError(f"{field}_schema_invalid")


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise KuCoinAnnouncementError("response_duplicate_json_key")
        value[key] = item
    return value


def _decode_response(body: bytes, index: int) -> Mapping[str, Any]:
    if not isinstance(body, bytes) or not body:
        raise KuCoinAnnouncementError(f"response_{index}_bytes_invalid")
    if len(body) > MAX_RESPONSE_BYTES_PER_PAGE:
        raise KuCoinAnnouncementError(f"response_{index}_bytes_exceeded")
    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=_object_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise KuCoinAnnouncementError(f"response_{index}_json_invalid") from exc
    if not isinstance(value, Mapping):
        raise KuCoinAnnouncementError(f"response_{index}_object_invalid")
    return value


def _request_values(
    *,
    start_time: datetime | str,
    end_time: datetime | str,
    page_size: int,
    announcement_type: str,
    language: str,
) -> tuple[datetime, datetime, dict[str, object]]:
    start = _aware_utc(start_time, "request_start_time")
    end = _aware_utc(end_time, "request_end_time")
    if start >= end or end - start > timedelta(days=MAX_REQUEST_WINDOW_DAYS):
        raise KuCoinAnnouncementError("request_window_invalid")
    size = _integer(page_size, "requested_page_size", minimum=1)
    if size > MAX_REQUESTED_PAGE_SIZE:
        raise KuCoinAnnouncementError("requested_page_size_invalid")
    if announcement_type not in ANNOUNCEMENT_TYPES:
        raise KuCoinAnnouncementError("request_announcement_type_invalid")
    if language != DEFAULT_LANGUAGE:
        raise KuCoinAnnouncementError("request_language_invalid")
    return start, end, {
        "pageSize": size,
        "annType": announcement_type,
        "lang": language,
        "startTime": int(start.timestamp() * 1000),
        "endTime": int(end.timestamp() * 1000),
    }


def build_kucoin_announcement_request_plan(
    *,
    start_time: datetime | str,
    end_time: datetime | str,
    page_size: int = MAX_REQUESTED_PAGE_SIZE,
    announcement_type: str = DEFAULT_ANNOUNCEMENT_TYPE,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, object]:
    """Describe the bounded public contract without executing a request."""

    _start, _end, params = _request_values(
        start_time=start_time,
        end_time=end_time,
        page_size=page_size,
        announcement_type=announcement_type,
        language=language,
    )
    initial_query = {"currentPage": 1, **params}
    return {
        "contract_version": CONTRACT_VERSION,
        "provider": PROVIDER_ID,
        "method": "GET",
        "base_url": PUBLIC_API_BASE,
        "path": ANNOUNCEMENTS_PATH,
        "initial_query": initial_query,
        "initial_url": (
            f"{PUBLIC_API_BASE}{ANNOUNCEMENTS_PATH}?{urlencode(initial_query)}"
        ),
        "pagination_policy": "contiguous_pages_from_one_using_response_total_page",
        "maximum_request_count": MAX_RESPONSE_PAGES,
        "maximum_response_bytes_per_page": MAX_RESPONSE_BYTES_PER_PAGE,
        "api_channel": "public",
        "api_permission": "NULL",
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


def _parse_page(
    body: bytes,
    *,
    index: int,
    acquired_at: datetime,
    request_lineage_id: str,
) -> _ParsedPage:
    payload = _decode_response(body, index)
    _exact_keys(payload, _TOP_LEVEL_KEYS, f"response_{index}")
    if payload.get("code") != RESPONSE_CODE_OK:
        raise KuCoinAnnouncementError(f"response_{index}_code_not_ok")
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise KuCoinAnnouncementError(f"response_{index}_data_invalid")
    _exact_keys(data, _DATA_KEYS, f"response_{index}_data")
    total_num = _integer(data.get("totalNum"), "total_num")
    total_page = _integer(data.get("totalPage"), "total_page")
    current_page = _integer(data.get("currentPage"), "current_page", minimum=1)
    page_size = _integer(data.get("pageSize"), "response_page_size", minimum=1)
    if page_size > MAX_REQUESTED_PAGE_SIZE:
        raise KuCoinAnnouncementError("response_page_size_invalid")
    if total_page > MAX_RESPONSE_PAGES or total_num > MAX_RESPONSE_ROWS:
        raise KuCoinAnnouncementError("response_pagination_bound_exceeded")
    items = data.get("items")
    if not isinstance(items, list) or any(not isinstance(item, Mapping) for item in items):
        raise KuCoinAnnouncementError(f"response_{index}_items_invalid")
    if len(items) > page_size:
        raise KuCoinAnnouncementError(f"response_{index}_item_count_invalid")
    if not _LINEAGE_RE.fullmatch(request_lineage_id):
        raise KuCoinAnnouncementError(f"response_{index}_lineage_invalid")
    return _ParsedPage(
        current_page=current_page,
        total_num=total_num,
        total_page=total_page,
        page_size=page_size,
        items=tuple(items),
        response_sha256=hashlib.sha256(body).hexdigest(),
        acquired_at=acquired_at,
        request_lineage_id=request_lineage_id,
    )


def _validate_pagination(pages: Sequence[_ParsedPage]) -> tuple[int, int, int]:
    first = pages[0]
    expected = list(range(1, len(pages) + 1))
    observed = [page.current_page for page in pages]
    if observed != expected:
        raise KuCoinAnnouncementError("response_page_sequence_invalid")
    if any(
        (page.total_num, page.total_page, page.page_size)
        != (first.total_num, first.total_page, first.page_size)
        for page in pages
    ):
        raise KuCoinAnnouncementError("response_pagination_drift")
    if first.total_num == 0:
        if len(pages) != 1 or first.total_page not in {0, 1} or first.items:
            raise KuCoinAnnouncementError("response_empty_pagination_invalid")
        return first.total_num, first.total_page, first.page_size
    expected_pages = math.ceil(first.total_num / first.page_size)
    if first.total_page != expected_pages or first.total_page < 1:
        raise KuCoinAnnouncementError("response_total_page_invalid")
    if len(pages) > first.total_page:
        raise KuCoinAnnouncementError("response_page_sequence_invalid")
    for page in pages:
        expected_count = (
            first.total_num - first.page_size * (first.total_page - 1)
            if page.current_page == first.total_page
            else first.page_size
        )
        if len(page.items) != expected_count:
            raise KuCoinAnnouncementError("response_page_item_count_drift")
    return first.total_num, first.total_page, first.page_size


def _safe_source_url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 2_048:
        raise KuCoinAnnouncementError("announcement_url_invalid")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise KuCoinAnnouncementError("announcement_url_invalid") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.kucoin.com"
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path.startswith("/announcement/")
        or parsed.fragment
    ):
        raise KuCoinAnnouncementError("announcement_url_invalid")
    query = parse_qsl(parsed.query, keep_blank_values=True)
    if query not in ([], [("lang", DEFAULT_LANGUAGE)]):
        raise KuCoinAnnouncementError("announcement_url_query_invalid")
    return value


def _text(value: object, field: str, maximum: int, *, required: bool) -> str:
    if not isinstance(value, str):
        raise KuCoinAnnouncementError(f"{field}_invalid")
    text = value.strip()
    if (required and not text) or len(text) > maximum or "\x00" in text:
        raise KuCoinAnnouncementError(f"{field}_invalid")
    return text


def _normalize_item(
    item: Mapping[str, Any],
    *,
    page: _ParsedPage,
    request_start: datetime,
    request_end: datetime,
    request_type: str,
) -> KuCoinAnnouncement:
    _exact_keys(item, _ITEM_KEYS, "announcement_item")
    announcement_id = _integer(item.get("annId"), "announcement_id", minimum=1)
    title = _text(item.get("annTitle"), "announcement_title", MAX_TITLE_CHARS, required=True)
    description = _text(
        item.get("annDesc"),
        "announcement_description",
        MAX_DESCRIPTION_CHARS,
        required=False,
    )
    raw_types = item.get("annType")
    if (
        not isinstance(raw_types, list)
        or not raw_types
        or any(not isinstance(value, str) or value not in ANNOUNCEMENT_TYPES for value in raw_types)
        or len(set(raw_types)) != len(raw_types)
        or request_type not in raw_types
    ):
        raise KuCoinAnnouncementError("announcement_types_invalid")
    if item.get("language") != DEFAULT_LANGUAGE:
        raise KuCoinAnnouncementError("announcement_language_invalid")
    publication_ms = _integer(item.get("cTime"), "announcement_publication_time", minimum=1)
    try:
        publication = datetime.fromtimestamp(publication_ms / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise KuCoinAnnouncementError("announcement_publication_time_invalid") from exc
    if not request_start <= publication <= request_end:
        raise KuCoinAnnouncementError("announcement_publication_outside_request_window")
    if publication > page.acquired_at + timedelta(seconds=MAX_PROVIDER_CLOCK_SKEW_SECONDS):
        raise KuCoinAnnouncementError("announcement_publication_in_future")
    return KuCoinAnnouncement(
        provider=PROVIDER_ID,
        source_class=SOURCE_CLASS,
        announcement_id=announcement_id,
        title=title,
        announcement_types=tuple(raw_types),
        description=description,
        description_completeness="provider_summary_not_full_article",
        publication_at=_iso(publication),
        publication_time_unix_ms=publication_ms,
        language=DEFAULT_LANGUAGE,
        source_url=_safe_source_url(item.get("annUrl")),
        page_number=page.current_page,
        response_sha256=page.response_sha256,
        request_lineage_id=page.request_lineage_id,
        event_time=None,
        event_time_basis="not_inferred_from_publication",
        catalyst_context_only=True,
        directional_authority=False,
        decision_policy_applied=False,
        research_only=True,
    )


def normalize_kucoin_announcement_pages(
    response_bodies: Sequence[bytes],
    *,
    acquired_at_by_page: Sequence[datetime | str],
    request_lineage_ids: Sequence[str],
    start_time: datetime | str,
    end_time: datetime | str,
    requested_page_size: int = MAX_REQUESTED_PAGE_SIZE,
    announcement_type: str = DEFAULT_ANNOUNCEMENT_TYPE,
    language: str = DEFAULT_LANGUAGE,
) -> KuCoinAnnouncementSnapshot:
    """Normalize one contiguous response-page prefix without I/O or side effects."""

    if (
        not response_bodies
        or len(response_bodies) > MAX_RESPONSE_PAGES
        or len(response_bodies) != len(acquired_at_by_page)
        or len(response_bodies) != len(request_lineage_ids)
    ):
        raise KuCoinAnnouncementError("response_bundle_invalid")
    request_start, request_end, params = _request_values(
        start_time=start_time,
        end_time=end_time,
        page_size=requested_page_size,
        announcement_type=announcement_type,
        language=language,
    )
    acquired = [
        _aware_utc(value, f"page_{index}_acquired_at")
        for index, value in enumerate(acquired_at_by_page, start=1)
    ]
    if acquired != sorted(acquired) or request_end > acquired[0] + timedelta(
        seconds=MAX_PROVIDER_CLOCK_SKEW_SECONDS
    ):
        raise KuCoinAnnouncementError("response_acquisition_window_invalid")
    if len(set(request_lineage_ids)) != len(request_lineage_ids):
        raise KuCoinAnnouncementError("response_lineage_duplicate")
    pages = tuple(
        _parse_page(
            body,
            index=index,
            acquired_at=acquired[index - 1],
            request_lineage_id=request_lineage_ids[index - 1],
        )
        for index, body in enumerate(response_bodies, start=1)
    )
    total_num, total_page, response_page_size = _validate_pagination(pages)
    announcements = tuple(
        _normalize_item(
            item,
            page=page,
            request_start=request_start,
            request_end=request_end,
            request_type=announcement_type,
        )
        for page in pages
        for item in page.items
    )
    ids = [row.announcement_id for row in announcements]
    if len(set(ids)) != len(ids):
        raise KuCoinAnnouncementError("announcement_identity_duplicate")
    publication_times = [row.publication_time_unix_ms for row in announcements]
    if publication_times != sorted(publication_times, reverse=True):
        raise KuCoinAnnouncementError("announcement_publication_order_invalid")
    effective_total_pages = total_page if total_num else 1
    complete = len(pages) == effective_total_pages and len(announcements) == total_num
    missing_pages = tuple(range(len(pages) + 1, effective_total_pages + 1))
    request_params = {**params, "currentPagePolicy": "contiguous_from_one"}
    return KuCoinAnnouncementSnapshot(
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        contract_version=CONTRACT_VERSION,
        provider=PROVIDER_ID,
        source_class=SOURCE_CLASS,
        endpoint=f"GET {PUBLIC_API_BASE}{ANNOUNCEMENTS_PATH}",
        official_api_doc=OFFICIAL_API_DOC,
        request_parameters=tuple(request_params.items()),
        request_count_observed=len(pages),
        maximum_request_count=MAX_RESPONSE_PAGES,
        response_page_size=response_page_size,
        requested_page_size=requested_page_size,
        provider_adjusted_page_size=response_page_size != requested_page_size,
        total_announcements_reported=total_num,
        total_pages_reported=total_page,
        observed_pages=tuple(page.current_page for page in pages),
        accepted_announcement_count=len(announcements),
        coverage_status="complete" if complete else "partial",
        coverage_complete=complete,
        healthy_empty=complete and total_num == 0,
        missing_pages=missing_pages,
        response_sha256_by_page=tuple(
            (page.current_page, page.response_sha256) for page in pages
        ),
        acquired_at_by_page=tuple(
            (page.current_page, _iso(page.acquired_at)) for page in pages
        ),
        request_lineage_id_by_page=tuple(
            (page.current_page, page.request_lineage_id) for page in pages
        ),
        announcements=announcements,
        provider_calls=0,
        writes=0,
        credentials_read=False,
        authorization_created=False,
        route_or_score_effect=False,
        protocol_v2_annex_bound=False,
        protocol_v2_evidence_eligible=False,
        research_only=True,
    )


def run_fixture_smoke(fixture_dir: Path) -> dict[str, object]:
    bodies = tuple(
        path.read_bytes() for path in sorted(fixture_dir.glob("page_*.json"))
    )
    snapshot = normalize_kucoin_announcement_pages(
        bodies,
        acquired_at_by_page=(
            "2026-07-19T01:35:01Z",
            "2026-07-19T01:35:02Z",
        ),
        request_lineage_ids=(
            "fixture.kucoin.announcements.page1",
            "fixture.kucoin.announcements.page2",
        ),
        start_time="2026-07-19T00:00:00Z",
        end_time="2026-07-19T01:35:00Z",
    )
    return {
        "mode": "offline_fixture",
        "status": snapshot.coverage_status,
        "snapshot": snapshot.to_dict(),
        "request_plan": build_kucoin_announcement_request_plan(
            start_time="2026-07-19T00:00:00Z",
            end_time="2026-07-19T01:35:00Z",
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=(
            Path(__file__).resolve().parents[3]
            / "fixtures"
            / "kucoin_announcements"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_fixture_smoke(args.fixture_dir)
    except (KuCoinAnnouncementError, OSError, ValueError) as exc:
        print(f"radar_kucoin_announcements_smoke_blocked: {type(exc).__name__}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


__all__ = (
    "ANNOUNCEMENT_TYPES",
    "ANNOUNCEMENTS_PATH",
    "CONTRACT_VERSION",
    "MAX_REQUESTED_PAGE_SIZE",
    "MAX_RESPONSE_PAGES",
    "OFFICIAL_API_DOC",
    "PROVIDER_ID",
    "SNAPSHOT_SCHEMA_VERSION",
    "KuCoinAnnouncement",
    "KuCoinAnnouncementError",
    "KuCoinAnnouncementSnapshot",
    "build_kucoin_announcement_request_plan",
    "main",
    "normalize_kucoin_announcement_pages",
    "run_fixture_smoke",
)


if __name__ == "__main__":
    raise SystemExit(main())
