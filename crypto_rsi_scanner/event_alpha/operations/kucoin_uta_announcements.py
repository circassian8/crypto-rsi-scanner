"""Strict offline KuCoin UTA announcement response contract.

KuCoin documents this public UTA endpoint as the replacement for the historical
``/api/v3/announcements`` path.  This module validates supplied synthetic bytes
only.  It has no HTTP client, environment access, persistence, routing, score,
notification, order, or trading path.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode

from .kucoin_announcements import (
    ANNOUNCEMENT_TYPES,
    DEFAULT_ANNOUNCEMENT_TYPE,
    DEFAULT_LANGUAGE,
    MAX_REQUESTED_PAGE_SIZE,
    MAX_RESPONSE_BYTES_PER_PAGE,
    MAX_RESPONSE_PAGES,
    MAX_RESPONSE_ROWS,
    PROVIDER_ID,
    PUBLIC_API_BASE,
    KuCoinAnnouncementError,
    KuCoinAnnouncementSnapshot,
    normalize_kucoin_announcement_pages,
)


CONTRACT_VERSION = "crypto_radar_kucoin_uta_announcements_v1"
SNAPSHOT_SCHEMA_VERSION = "crypto_radar.kucoin_uta_announcements.v1"
ANNOUNCEMENTS_PATH = "/api/ua/v1/market/announcement"
OFFICIAL_API_DOC = "https://www.kucoin.com/docs-new/rest/ua/get-announcements"
OFFICIAL_MIGRATION_SOURCE = "https://www.kucoin.com/docs-new/change-log"
MAX_REQUEST_WINDOW_DAYS = 31
RESPONSE_CODE_OK = "200000"

_TOP_LEVEL_KEYS = frozenset({"code", "data"})
_DATA_KEYS = frozenset(
    {"totalNumber", "totalPage", "pageNumber", "pageSize", "list"}
)
_ITEM_KEYS = frozenset(
    {"id", "title", "type", "description", "releaseTime", "language", "url"}
)


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise KuCoinAnnouncementError("response_duplicate_json_key")
        value[key] = item
    return value


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


def _integer(value: object, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise KuCoinAnnouncementError(f"{field}_invalid")
    return value


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], field: str) -> None:
    if set(value) != expected:
        raise KuCoinAnnouncementError(f"{field}_schema_invalid")


def _decode_uta_response(body: bytes, page: int) -> Mapping[str, Any]:
    if (
        not isinstance(body, bytes)
        or not body
        or len(body) > MAX_RESPONSE_BYTES_PER_PAGE
    ):
        raise KuCoinAnnouncementError(f"response_{page}_bytes_invalid")
    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=_object_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise KuCoinAnnouncementError(f"response_{page}_json_invalid") from exc
    if not isinstance(value, Mapping):
        raise KuCoinAnnouncementError(f"response_{page}_object_invalid")
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
        "language": language,
        "type": announcement_type,
        "pageSize": size,
        "startTime": int(start.timestamp() * 1000),
        "endTime": int(end.timestamp() * 1000),
    }


def build_kucoin_uta_announcement_request_plan(
    *,
    start_time: datetime | str,
    end_time: datetime | str,
    page_size: int = MAX_REQUESTED_PAGE_SIZE,
    announcement_type: str = DEFAULT_ANNOUNCEMENT_TYPE,
    language: str = DEFAULT_LANGUAGE,
) -> dict[str, object]:
    """Describe the bounded current public contract without executing it."""

    _start, _end, params = _request_values(
        start_time=start_time,
        end_time=end_time,
        page_size=page_size,
        announcement_type=announcement_type,
        language=language,
    )
    initial_query = {
        "language": params["language"],
        "type": params["type"],
        "pageNumber": 1,
        "pageSize": params["pageSize"],
        "startTime": params["startTime"],
        "endTime": params["endTime"],
    }
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
        "pagination_policy": "contiguous_pageNumber_from_one_using_response_totalPage",
        "maximum_request_count": MAX_RESPONSE_PAGES,
        "maximum_response_rows": MAX_RESPONSE_ROWS,
        "maximum_response_bytes_per_page": MAX_RESPONSE_BYTES_PER_PAGE,
        "requested_page_size_policy": "conservative_local_max_50_from_official_example",
        "api_channel": "public",
        "api_permission": "NULL",
        "api_rate_limit_pool": "Public",
        "api_rate_limit_weight": 20,
        "official_api_doc": OFFICIAL_API_DOC,
        "official_migration_source": OFFICIAL_MIGRATION_SOURCE,
        "replaces_historical_path": "/api/v3/announcements",
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


def _uta_to_legacy_payload(body: bytes, page: int) -> bytes:
    payload = _decode_uta_response(body, page)
    _exact_keys(payload, _TOP_LEVEL_KEYS, f"response_{page}")
    if payload.get("code") != RESPONSE_CODE_OK:
        raise KuCoinAnnouncementError(f"response_{page}_code_not_ok")
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise KuCoinAnnouncementError(f"response_{page}_data_invalid")
    _exact_keys(data, _DATA_KEYS, f"response_{page}_data")
    rows = data.get("list")
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise KuCoinAnnouncementError(f"response_{page}_list_invalid")
    legacy_rows: list[dict[str, object]] = []
    for row in rows:
        _exact_keys(row, _ITEM_KEYS, "announcement_item")
        legacy_rows.append(
            {
                "annId": row["id"],
                "annTitle": row["title"],
                "annType": row["type"],
                "annDesc": row["description"],
                "cTime": row["releaseTime"],
                "language": row["language"],
                "annUrl": row["url"],
            }
        )
    legacy = {
        "code": RESPONSE_CODE_OK,
        "data": {
            "totalNum": data["totalNumber"],
            "totalPage": data["totalPage"],
            "currentPage": data["pageNumber"],
            "pageSize": data["pageSize"],
            "items": legacy_rows,
        },
    }
    return json.dumps(legacy, separators=(",", ":"), ensure_ascii=False).encode()


def normalize_kucoin_uta_announcement_pages(
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
    """Normalize one exact UTA page prefix without I/O or side effects."""

    original_hashes = tuple(
        (index, hashlib.sha256(body).hexdigest())
        for index, body in enumerate(response_bodies, start=1)
    )
    legacy_bodies = tuple(
        _uta_to_legacy_payload(body, page)
        for page, body in enumerate(response_bodies, start=1)
    )
    snapshot = normalize_kucoin_announcement_pages(
        legacy_bodies,
        acquired_at_by_page=acquired_at_by_page,
        request_lineage_ids=request_lineage_ids,
        start_time=start_time,
        end_time=end_time,
        requested_page_size=requested_page_size,
        announcement_type=announcement_type,
        language=language,
    )
    hash_by_page = dict(original_hashes)
    announcements = tuple(
        replace(row, response_sha256=hash_by_page[row.page_number])
        for row in snapshot.announcements
    )
    _start, _end, params = _request_values(
        start_time=start_time,
        end_time=end_time,
        page_size=requested_page_size,
        announcement_type=announcement_type,
        language=language,
    )
    request_parameters = {
        "language": params["language"],
        "type": params["type"],
        "pageSize": params["pageSize"],
        "startTime": params["startTime"],
        "endTime": params["endTime"],
        "pageNumberPolicy": "contiguous_from_one",
    }
    return replace(
        snapshot,
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        contract_version=CONTRACT_VERSION,
        endpoint=f"GET {PUBLIC_API_BASE}{ANNOUNCEMENTS_PATH}",
        official_api_doc=OFFICIAL_API_DOC,
        request_parameters=tuple(request_parameters.items()),
        response_sha256_by_page=original_hashes,
        announcements=announcements,
    )


def run_uta_fixture_smoke(fixture_dir: Path) -> dict[str, object]:
    bodies = tuple(path.read_bytes() for path in sorted(fixture_dir.glob("page_*.json")))
    snapshot = normalize_kucoin_uta_announcement_pages(
        bodies,
        acquired_at_by_page=(
            "2026-07-19T01:35:01Z",
            "2026-07-19T01:35:02Z",
        ),
        request_lineage_ids=(
            "fixture.kucoin.uta.announcements.page1",
            "fixture.kucoin.uta.announcements.page2",
        ),
        start_time="2026-07-19T00:00:00Z",
        end_time="2026-07-19T01:35:00Z",
    )
    return {
        "mode": "offline_fixture",
        "status": snapshot.coverage_status,
        "snapshot": snapshot.to_dict(),
        "request_plan": build_kucoin_uta_announcement_request_plan(
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=(
            Path(__file__).resolve().parents[3]
            / "fixtures"
            / "kucoin_uta_announcements"
        ),
    )
    args = parser.parse_args(argv)
    try:
        result = run_uta_fixture_smoke(args.fixture_dir)
    except (KuCoinAnnouncementError, OSError, ValueError) as exc:
        print(f"radar_kucoin_uta_announcements_smoke_blocked: {type(exc).__name__}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


__all__ = (
    "ANNOUNCEMENTS_PATH",
    "CONTRACT_VERSION",
    "OFFICIAL_API_DOC",
    "OFFICIAL_MIGRATION_SOURCE",
    "SNAPSHOT_SCHEMA_VERSION",
    "build_kucoin_uta_announcement_request_plan",
    "main",
    "normalize_kucoin_uta_announcement_pages",
    "run_uta_fixture_smoke",
)


if __name__ == "__main__":
    raise SystemExit(main())
