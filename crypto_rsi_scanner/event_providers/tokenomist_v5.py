"""Strict offline normalizer for Tokenomist unlock-events v5 fixtures.

The module intentionally has no HTTP client, credential lookup, provider
authorization, persistence, notification, or execution behavior.  It accepts
only the closed synthetic-fixture capture contract used to prove the current
provider response shape before any live or operator-import boundary exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


CAPTURE_CONTRACT = "tokenomist_unlock_events_v5_fixture_capture"
ENDPOINT_HOST = "api.tokenomist.ai"
ENDPOINT_PREFIX = "/v5/unlock/events/"
MAX_RESPONSE_ROWS = 500
MAX_PAGE_SIZE = 500
MAX_TOTAL_ROWS = 1_000_000

_SAFE_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
_SAFE_SYMBOL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,23}")
_SENSITIVE_KEYS = {
    "api-key",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "x-api-key",
}
_STANDARD_ALLOCATIONS = {
    "community",
    "founderTeam",
    "privateInvestors",
    "publicInvestors",
    "others",
    "reserve",
}
_PRECISIONS = {
    "second",
    "minute",
    "hour",
    "day",
    "week",
    "month",
    "quarter",
    "year",
    "unknown",
}


def is_tokenomist_v5_fixture_capture(value: object) -> bool:
    """Return whether *value* declares the exact v5 fixture contract."""

    return isinstance(value, Mapping) and value.get("capture_contract") == CAPTURE_CONTRACT


def load_tokenomist_v5_fixture_capture(path: str | Path) -> tuple[dict[str, Any], ...]:
    """Read one fixture capture and return strict legacy-compatible rows."""

    source = Path(path).expanduser()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("Tokenomist v5 fixture capture must be a JSON object")
    return normalize_tokenomist_v5_fixture_capture(payload)


def normalize_tokenomist_v5_fixture_capture(
    capture: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Normalize one closed, synthetic Tokenomist v5 fixture capture.

    The returned rows deliberately keep Tokenomist's ``valueToMarketCap`` as
    percent points.  It is not circulating-supply percentage and is never
    copied into the historical ``unlock_pct_circulating`` field.
    """

    _reject_sensitive_keys(capture)
    _require_exact_keys(
        capture,
        {
            "schema_version",
            "capture_contract",
            "capture_mode",
            "fixture_synthetic",
            "provider",
            "api_version",
            "acquired_at",
            "request",
            "response",
            "research_only",
        },
        "capture",
    )
    if capture.get("schema_version") != 1:
        raise ValueError("Tokenomist v5 fixture schema_version must be 1")
    if capture.get("capture_contract") != CAPTURE_CONTRACT:
        raise ValueError("Tokenomist v5 fixture capture_contract is invalid")
    if capture.get("capture_mode") != "fixture" or capture.get("fixture_synthetic") is not True:
        raise ValueError("Tokenomist v5 adapter accepts synthetic fixtures only")
    if capture.get("provider") != "tokenomist" or capture.get("api_version") != "v5":
        raise ValueError("Tokenomist v5 provider identity is invalid")
    if capture.get("research_only") is not True:
        raise ValueError("Tokenomist v5 fixture must be research_only=true")

    acquired_at = _utc_timestamp(capture.get("acquired_at"), "acquired_at")
    request = _request(capture.get("request"))
    response = _response(capture.get("response"), acquired_at=acquired_at)
    response_rows = response["data"]
    if request["page"] != response["metadata"]["page"]:
        raise ValueError("Tokenomist v5 response page does not match request")
    if request["page_size"] != response["metadata"]["pageSize"]:
        raise ValueError("Tokenomist v5 response pageSize does not match request")
    request_start = _date_value(request["start"], "request.start") if request["start"] else None
    request_end = _date_value(request["end"], "request.end") if request["end"] else None
    if request_start and request_end and request_start > request_end:
        raise ValueError("Tokenomist v5 request start must not follow end")

    request_digest = _digest(request)
    response_digest = _digest(capture["response"])
    capture_digest = _digest(capture)
    metadata = response["metadata"]
    rows: list[dict[str, Any]] = []
    for index, raw_row in enumerate(response_rows):
        row = _event_row(raw_row, index=index, query_at=metadata["queryDate"])
        unlock_day = _date_value(row["unlock_date"][:10], f"data[{index}].unlockDate")
        if request_start and unlock_day < request_start:
            raise ValueError(f"Tokenomist v5 data[{index}] predates request start")
        if request_end and unlock_day > request_end:
            raise ValueError(f"Tokenomist v5 data[{index}] follows request end")
        row.update(
            {
                "token_id": request["token_id"],
                "coin_id": request["canonical_asset_id"],
                "canonical_asset_id": request["canonical_asset_id"],
                "provider_token_id": request["token_id"],
                "provider": "tokenomist",
                "provider_api_version": "v5",
                "provider_query_at": metadata["queryDate"],
                "acquired_at": acquired_at,
                "provider_page": metadata["page"],
                "provider_page_size": metadata["pageSize"],
                "provider_total_pages": metadata["totalPages"],
                "provider_total_rows": metadata["total"],
                "provider_snapshot_status": (
                    "complete" if metadata["totalPages"] in {0, 1} else "partial_page"
                ),
                "source_coverage_complete": metadata["totalPages"] in {0, 1},
                "request_identity_sha256": request_digest,
                "provider_response_sha256": response_digest,
                "fixture_capture_sha256": capture_digest,
                "capture_mode": "fixture",
                "fixture_provenance": True,
                "fixture_synthetic": True,
                "provider_call_performed": False,
                "provider_authorization_created": False,
                "campaign_evidence_eligible": False,
                "protocol_v2_evidence_eligible": False,
                "authority_eligible": False,
                "first_public_at": None,
                "first_public_at_status": "unavailable",
                "query_date_is_publication_time": False,
                "research_only": True,
                "created_alert": False,
                "notification_send_enabled": False,
                "created_trade": False,
                "created_order": False,
                "created_paper_trade": False,
                "wrote_normal_rsi_row": False,
                "created_triggered_fade": False,
            }
        )
        row["source_url"] = f"https://tokenomist.ai/{request['token_id']}"
        rows.append(row)
    return tuple(rows)


def _request(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("Tokenomist v5 request must be an object")
    _require_exact_keys(
        value,
        {
            "method",
            "host",
            "path",
            "token_id",
            "canonical_asset_id",
            "start",
            "end",
            "standard_allocation",
            "page",
            "page_size",
        },
        "request",
    )
    token_id = _safe_id(value.get("token_id"), "request.token_id")
    canonical_asset_id = _safe_id(
        value.get("canonical_asset_id"), "request.canonical_asset_id"
    )
    if value.get("method") != "GET" or value.get("host") != ENDPOINT_HOST:
        raise ValueError("Tokenomist v5 request must be GET api.tokenomist.ai")
    if value.get("path") != f"{ENDPOINT_PREFIX}{token_id}":
        raise ValueError("Tokenomist v5 request path does not match token_id")
    start = _optional_text(value.get("start"), "request.start", max_length=10)
    end = _optional_text(value.get("end"), "request.end", max_length=10)
    if start:
        _date_value(start, "request.start")
    if end:
        _date_value(end, "request.end")
    allocation = value.get("standard_allocation")
    if allocation is not None:
        if not isinstance(allocation, list) or not allocation:
            raise ValueError("Tokenomist v5 standard_allocation must be null or a non-empty list")
        if any(item not in _STANDARD_ALLOCATIONS for item in allocation):
            raise ValueError("Tokenomist v5 standard_allocation contains an unknown value")
        if len(set(allocation)) != len(allocation):
            raise ValueError("Tokenomist v5 standard_allocation contains duplicates")
    page = _integer(value.get("page"), "request.page", minimum=1, maximum=MAX_TOTAL_ROWS)
    page_size = _integer(
        value.get("page_size"), "request.page_size", minimum=1, maximum=MAX_PAGE_SIZE
    )
    return {
        "method": "GET",
        "host": ENDPOINT_HOST,
        "path": f"{ENDPOINT_PREFIX}{token_id}",
        "token_id": token_id,
        "canonical_asset_id": canonical_asset_id,
        "start": start,
        "end": end,
        "standard_allocation": list(allocation) if allocation is not None else None,
        "page": page,
        "page_size": page_size,
    }


def _response(value: object, *, acquired_at: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("Tokenomist v5 response must be an object")
    _require_exact_keys(value, {"metadata", "status", "data"}, "response")
    if value.get("status") is not True:
        raise ValueError("Tokenomist v5 response status must be true")
    metadata = value.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("Tokenomist v5 response metadata must be an object")
    _require_exact_keys(
        metadata, {"queryDate", "page", "pageSize", "totalPages", "total"}, "metadata"
    )
    query_at = _utc_timestamp(metadata.get("queryDate"), "metadata.queryDate")
    if _parse_utc(query_at) > _parse_utc(acquired_at):
        raise ValueError("Tokenomist v5 queryDate must not follow acquired_at")
    page = _integer(metadata.get("page"), "metadata.page", minimum=1, maximum=MAX_TOTAL_ROWS)
    page_size = _integer(
        metadata.get("pageSize"), "metadata.pageSize", minimum=1, maximum=MAX_PAGE_SIZE
    )
    total_pages = _integer(
        metadata.get("totalPages"), "metadata.totalPages", minimum=0, maximum=MAX_TOTAL_ROWS
    )
    total = _integer(metadata.get("total"), "metadata.total", minimum=0, maximum=MAX_TOTAL_ROWS)
    data = value.get("data")
    if not isinstance(data, list):
        raise ValueError("Tokenomist v5 response data must be a list")
    if len(data) > min(page_size, MAX_RESPONSE_ROWS):
        raise ValueError("Tokenomist v5 response page exceeds its declared bound")
    expected_pages = math.ceil(total / page_size) if total else 0
    if total and total_pages != expected_pages:
        raise ValueError("Tokenomist v5 pagination totals are inconsistent")
    if not total:
        if total_pages not in {0, 1}:
            raise ValueError("Tokenomist v5 empty pagination is inconsistent")
        if page != 1 or data:
            raise ValueError("Tokenomist v5 empty pagination is inconsistent")
    else:
        if page > total_pages:
            raise ValueError("Tokenomist v5 response page exceeds totalPages")
        expected_rows = min(page_size, total - ((page - 1) * page_size))
        if len(data) != expected_rows:
            raise ValueError("Tokenomist v5 page row count is inconsistent with metadata")
    for index, row in enumerate(data):
        if not isinstance(row, Mapping):
            raise ValueError(f"Tokenomist v5 data[{index}] must be an object")
    return {
        "metadata": {
            "queryDate": query_at,
            "page": page,
            "pageSize": page_size,
            "totalPages": total_pages,
            "total": total,
        },
        "status": True,
        "data": data,
    }


def _event_row(value: Mapping[str, Any], *, index: int, query_at: str) -> dict[str, Any]:
    label = f"data[{index}]"
    _require_exact_keys(
        value,
        {
            "unlockDate",
            "tokenName",
            "tokenSymbol",
            "listedMethod",
            "dataSource",
            "cliffUnlocks",
            "latestUpdateDate",
        },
        label,
    )
    unlock_at = _utc_timestamp(value.get("unlockDate"), f"{label}.unlockDate")
    token_name = _text(value.get("tokenName"), f"{label}.tokenName", max_length=160)
    token_symbol = _text(value.get("tokenSymbol"), f"{label}.tokenSymbol", max_length=24)
    if not _SAFE_SYMBOL_RE.fullmatch(token_symbol):
        raise ValueError(f"Tokenomist v5 {label}.tokenSymbol is invalid")
    listed_method = _text(value.get("listedMethod"), f"{label}.listedMethod", max_length=80)
    data_source = _text(value.get("dataSource"), f"{label}.dataSource", max_length=160)
    latest_update = _utc_timestamp(
        value.get("latestUpdateDate"), f"{label}.latestUpdateDate"
    )
    if _parse_utc(latest_update) > _parse_utc(query_at):
        raise ValueError(f"Tokenomist v5 {label}.latestUpdateDate follows queryDate")
    cliff = value.get("cliffUnlocks")
    if not isinstance(cliff, Mapping):
        raise ValueError(f"Tokenomist v5 {label}.cliffUnlocks must be an object")
    _require_exact_keys(
        cliff,
        {"cliffAmount", "cliffValue", "valueToMarketCap", "allocationBreakdown"},
        f"{label}.cliffUnlocks",
    )
    amount = _finite_number(
        cliff.get("cliffAmount"), f"{label}.cliffUnlocks.cliffAmount", maximum=1e30
    )
    usd_value = _finite_number(
        cliff.get("cliffValue"), f"{label}.cliffUnlocks.cliffValue", maximum=1e18
    )
    value_to_market_cap = _finite_number(
        cliff.get("valueToMarketCap"),
        f"{label}.cliffUnlocks.valueToMarketCap",
        maximum=1_000_000.0,
    )
    allocations_raw = cliff.get("allocationBreakdown")
    if not isinstance(allocations_raw, list) or not allocations_raw:
        raise ValueError(f"Tokenomist v5 {label}.allocationBreakdown must be non-empty")
    if len(allocations_raw) > 256:
        raise ValueError(f"Tokenomist v5 {label}.allocationBreakdown exceeds 256 rows")
    allocations = tuple(
        _allocation_row(
            item,
            label=f"{label}.allocationBreakdown[{allocation_index}]",
            parent_unlock_at=unlock_at,
            query_at=query_at,
        )
        for allocation_index, item in enumerate(allocations_raw)
    )
    _assert_breakdown_bound(amount, [item["cliff_amount"] for item in allocations], f"{label}.cliffAmount")
    _assert_breakdown_bound(usd_value, [item["cliff_value_usd"] for item in allocations], f"{label}.cliffValue")
    precisions = {str(item["unlock_precision"]) for item in allocations}
    timestamp_confidence = "confirmed" if precisions <= {"second", "minute", "hour", "day"} else "estimated"
    row_source_digest = _digest(value)
    event_identity = f"{token_symbol}|{unlock_at}|{row_source_digest}"
    event_id = f"tokenomist-v5:{hashlib.sha256(event_identity.encode('utf-8')).hexdigest()[:24]}"
    source_url = f"https://tokenomist.ai/{token_symbol.casefold()}"
    allocation_names = tuple(
        dict.fromkeys(
            str(item["standard_allocation_name"] or item["allocation_name"])
            for item in allocations
        )
    )
    return {
        "id": event_id,
        "event_id": event_id,
        "event_type": "token_unlock",
        "unlock_type": "cliff",
        "token_name": token_name,
        "token_symbol": token_symbol.upper(),
        "symbol": token_symbol.upper(),
        "title": f"{token_name} ({token_symbol.upper()}) cliff unlock",
        "description": f"Tokenomist v5 cliff unlock for {token_name} ({token_symbol.upper()}).",
        "unlock_date": unlock_at,
        "source_updated_at": latest_update,
        "listed_method": listed_method,
        "data_source": data_source,
        "unlock_amount": amount,
        "tokens_unlocked": amount,
        "unlock_amount_unit": "token_units",
        "unlock_usd": usd_value,
        "unlock_usd_unit": "usd",
        "unlock_value_to_market_cap_pct": value_to_market_cap,
        "unlock_value_to_market_cap_unit": "percent_points",
        "unlock_pct_circulating": None,
        "unlock_pct_circulating_supply": None,
        "allocation_breakdown": allocations,
        "allocation_categories": allocation_names,
        "vesting_category": allocation_names[0] if len(allocation_names) == 1 else "multiple",
        "unlock_precision_values": tuple(sorted(precisions)),
        "event_timestamp_confidence": timestamp_confidence,
        "source_url": source_url,
        "source_class": "structured_unlock",
        "source_row_sha256": row_source_digest,
        "field_units": {
            "unlock_amount": "token_units",
            "tokens_unlocked": "token_units",
            "unlock_usd": "usd",
            "unlock_value_to_market_cap_pct": "percent_points",
        },
        "supply_snapshot": {
            "unlock_amount": amount,
            "unlock_usd": usd_value,
            "unlock_value_to_market_cap_pct": value_to_market_cap,
            "field_units": {
                "unlock_amount": "token_units",
                "unlock_usd": "usd",
                "unlock_value_to_market_cap_pct": "percent_points",
            },
        },
    }


def _allocation_row(
    value: object,
    *,
    label: str,
    parent_unlock_at: str,
    query_at: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"Tokenomist v5 {label} must be an object")
    required = {
        "unlockDate",
        "allocationName",
        "standardAllocationName",
        "cliffAmount",
        "cliffValue",
        "referencePrice",
        "referencePriceUpdatedTime",
        "unlockPrecision",
    }
    allowed = required | {"committedClaim"}
    _require_exact_keys(value, allowed, label, required=required)
    unlock_at = _utc_timestamp(value.get("unlockDate"), f"{label}.unlockDate")
    if unlock_at != parent_unlock_at:
        raise ValueError(f"Tokenomist v5 {label}.unlockDate differs from parent event")
    allocation_name = _text(value.get("allocationName"), f"{label}.allocationName", max_length=160)
    standard_name = _text(
        value.get("standardAllocationName"), f"{label}.standardAllocationName", max_length=160
    )
    amount = _finite_number(value.get("cliffAmount"), f"{label}.cliffAmount", maximum=1e30)
    usd_value = _finite_number(value.get("cliffValue"), f"{label}.cliffValue", maximum=1e18)
    reference_price = _finite_number(
        value.get("referencePrice"), f"{label}.referencePrice", maximum=1e15
    )
    price_updated_at = _utc_timestamp(
        value.get("referencePriceUpdatedTime"), f"{label}.referencePriceUpdatedTime"
    )
    if _parse_utc(price_updated_at) > _parse_utc(query_at):
        raise ValueError(f"Tokenomist v5 {label}.referencePriceUpdatedTime follows queryDate")
    precision = _text(value.get("unlockPrecision"), f"{label}.unlockPrecision", max_length=16).casefold()
    if precision not in _PRECISIONS:
        raise ValueError(f"Tokenomist v5 {label}.unlockPrecision is unsupported")
    committed_claim = _committed_claim(value.get("committedClaim"), label=f"{label}.committedClaim")
    return {
        "unlock_date": unlock_at,
        "allocation_name": allocation_name,
        "standard_allocation_name": standard_name,
        "cliff_amount": amount,
        "cliff_amount_unit": "token_units",
        "cliff_value_usd": usd_value,
        "cliff_value_unit": "usd",
        "reference_price": reference_price,
        "reference_price_unit": "usd_per_token",
        "reference_price_updated_at": price_updated_at,
        "reference_price_is_current": False,
        "unlock_precision": precision,
        "committed_claim": committed_claim,
    }


def _committed_claim(value: object, *, label: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(f"Tokenomist v5 {label} must be an object or null")
    _require_exact_keys(value, {"amount", "value", "timestamp"}, label)
    amount = _finite_number(value.get("amount"), f"{label}.amount", maximum=1e30)
    usd_value = _finite_number(value.get("value"), f"{label}.value", maximum=1e18)
    timestamp = value.get("timestamp")
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
        raise ValueError(f"Tokenomist v5 {label}.timestamp must be a Unix timestamp")
    timestamp_float = float(timestamp)
    if not math.isfinite(timestamp_float) or timestamp_float < 0 or timestamp_float > 32_503_680_000:
        raise ValueError(f"Tokenomist v5 {label}.timestamp is implausible")
    return {
        "amount": amount,
        "amount_unit": "token_units",
        "value_usd": usd_value,
        "value_unit": "usd",
        "timestamp": datetime.fromtimestamp(timestamp_float, tz=timezone.utc).isoformat(),
        "used_as_unlock_size": False,
    }


def _assert_breakdown_bound(total: float, parts: Sequence[float], label: str) -> None:
    tolerance = max(1e-8, abs(total) * 1e-6)
    if sum(parts) > total + tolerance:
        raise ValueError(f"Tokenomist v5 {label} is smaller than its allocation breakdown")


def _require_exact_keys(
    value: Mapping[str, Any],
    allowed: set[str],
    label: str,
    *,
    required: set[str] | None = None,
) -> None:
    keys = {str(key) for key in value}
    missing = (required if required is not None else allowed) - keys
    extra = keys - allowed
    if missing:
        raise ValueError(f"Tokenomist v5 {label} is missing keys: {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"Tokenomist v5 {label} has unknown keys: {', '.join(sorted(extra))}")


def _reject_sensitive_keys(value: object, *, path: str = "capture") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            clean = str(key).strip().casefold().replace("_", "-")
            if clean in _SENSITIVE_KEYS:
                raise ValueError(f"Tokenomist v5 fixture contains forbidden sensitive key at {path}.{key}")
            _reject_sensitive_keys(item, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_sensitive_keys(item, path=f"{path}[{index}]")


def _safe_id(value: object, label: str) -> str:
    text = _text(value, label, max_length=128).casefold()
    if not _SAFE_ID_RE.fullmatch(text):
        raise ValueError(f"Tokenomist v5 {label} is invalid")
    return text


def _text(value: object, label: str, *, max_length: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Tokenomist v5 {label} must be text")
    text = value.strip()
    if not text or len(text) > max_length or any(ord(char) < 32 for char in text):
        raise ValueError(f"Tokenomist v5 {label} is invalid")
    return text


def _optional_text(value: object, label: str, *, max_length: int) -> str | None:
    if value is None:
        return None
    return _text(value, label, max_length=max_length)


def _integer(value: object, label: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Tokenomist v5 {label} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"Tokenomist v5 {label} is outside the accepted range")
    return value


def _finite_number(value: object, label: str, *, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Tokenomist v5 {label} must be numeric")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0 or parsed > maximum:
        raise ValueError(f"Tokenomist v5 {label} is outside plausible bounds")
    return parsed


def _utc_timestamp(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Tokenomist v5 {label} must be an ISO-8601 UTC timestamp")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Tokenomist v5 {label} must be an ISO-8601 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"Tokenomist v5 {label} must use UTC")
    return parsed.astimezone(timezone.utc).isoformat()


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _date_value(value: object, label: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"Tokenomist v5 {label} must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Tokenomist v5 {label} is not a valid date") from exc


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "contract": CAPTURE_CONTRACT,
        "status": "fixture_valid",
        "row_count": len(rows),
        "symbols": [row.get("symbol") for row in rows],
        "source_coverage": sorted({str(row.get("provider_snapshot_status")) for row in rows}),
        "live_provider_calls": 0,
        "provider_authorization_created": False,
        "sends": 0,
        "trades": 0,
        "orders": 0,
        "paper_trades": 0,
        "normal_rsi_writes": 0,
        "triggered_fades": 0,
        "research_only": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a synthetic Tokenomist v5 fixture capture")
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args(argv)
    rows = load_tokenomist_v5_fixture_capture(args.fixture)
    print(json.dumps(_summary(rows), sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI boundary
    raise SystemExit(main())
