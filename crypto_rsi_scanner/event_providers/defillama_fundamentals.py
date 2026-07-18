"""Strict offline normalizer for DefiLlama protocol-fundamental fixtures.

The closed fixture contract mirrors four currently documented free API reads:
one protocol-TVL inventory and three fee overviews whose ``dataType`` values
keep fees, protocol revenue, and token-holder revenue separate.  This module
has no HTTP client, environment lookup, authorization, persistence, routing,
notification, or execution behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


INPUT_SCHEMA_ID = "decision_radar.defillama_fundamentals_fixture_capture"
OUTPUT_SCHEMA_ID = "decision_radar.defillama_protocol_fundamentals"
CONTRACT_VERSION = "decision_radar_defillama_fundamentals_v1"
CAPTURE_CONTRACT = "defillama_free_protocol_fundamentals_fixture_capture"
API_CONTRACT = "defillama_free_api_v1"
CAPTURE_MODE = "fixture"
PROVIDER_HOST = "api.llama.fi"
MAX_CAPTURE_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_ROWS = 10_000
MAX_EXCHANGE_DURATION_MS = 120_000

PROTOCOLS_REQUEST_ID = "protocols"
DAILY_FEES_REQUEST_ID = "daily_fees"
DAILY_REVENUE_REQUEST_ID = "daily_revenue"
DAILY_HOLDERS_REVENUE_REQUEST_ID = "daily_holders_revenue"

_REQUEST_SPECS: dict[str, tuple[str, Mapping[str, object]]] = {
    PROTOCOLS_REQUEST_ID: ("/protocols", {}),
    DAILY_FEES_REQUEST_ID: (
        "/overview/fees",
        {
            "dataType": "dailyFees",
            "excludeTotalDataChart": True,
            "excludeTotalDataChartBreakdown": True,
        },
    ),
    DAILY_REVENUE_REQUEST_ID: (
        "/overview/fees",
        {
            "dataType": "dailyRevenue",
            "excludeTotalDataChart": True,
            "excludeTotalDataChartBreakdown": True,
        },
    ),
    DAILY_HOLDERS_REVENUE_REQUEST_ID: (
        "/overview/fees",
        {
            "dataType": "dailyHoldersRevenue",
            "excludeTotalDataChart": True,
            "excludeTotalDataChartBreakdown": True,
        },
    ),
}

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:#-]{0,127}$")
_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,23}$")
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


class DefiLlamaFundamentalsError(ValueError):
    """Raised when an offline DefiLlama fixture violates the closed contract."""


def is_defillama_fundamentals_fixture_capture(value: object) -> bool:
    """Return whether *value* declares the closed DefiLlama fixture contract."""

    return (
        isinstance(value, Mapping)
        and value.get("schema_id") == INPUT_SCHEMA_ID
        and value.get("capture_contract") == CAPTURE_CONTRACT
    )


def load_defillama_fundamentals_fixture_capture(
    path: str | Path,
) -> tuple[dict[str, Any], ...]:
    """Read and normalize one exact fixture capture without writing anything."""

    raw = Path(path).expanduser().read_bytes()
    return normalize_defillama_fundamentals_fixture_capture(raw)


def normalize_defillama_fundamentals_fixture_capture(
    raw: bytes,
) -> tuple[dict[str, Any], ...]:
    """Normalize one synthetic, no-call DefiLlama response bundle.

    The capture is deliberately ineligible for authority and Protocol v2.  It
    proves response semantics and mapping checks only; a future genuine source
    requires a separately authorized immutable transport and annex selection.
    """

    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_CAPTURE_BYTES:
        raise DefiLlamaFundamentalsError("capture_size_invalid")
    try:
        capture = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DefiLlamaFundamentalsError("capture_json_invalid") from exc
    if not isinstance(capture, Mapping):
        raise DefiLlamaFundamentalsError("capture_schema_invalid")
    _reject_sensitive_keys(capture)
    _exact_keys(
        capture,
        {
            "api_contract",
            "capture_completed_at",
            "capture_contract",
            "capture_mode",
            "capture_started_at",
            "exchanges",
            "fixture_synthetic",
            "mappings",
            "provider",
            "research_only",
            "schema_id",
            "schema_version",
        },
        "capture",
    )
    if capture.get("schema_id") != INPUT_SCHEMA_ID or capture.get("schema_version") != 1:
        raise DefiLlamaFundamentalsError("capture_version_invalid")
    if capture.get("capture_contract") != CAPTURE_CONTRACT:
        raise DefiLlamaFundamentalsError("capture_contract_invalid")
    if capture.get("api_contract") != API_CONTRACT:
        raise DefiLlamaFundamentalsError("api_contract_invalid")
    if (
        capture.get("capture_mode") != CAPTURE_MODE
        or capture.get("fixture_synthetic") is not True
        or capture.get("provider") != "defillama"
        or capture.get("research_only") is not True
    ):
        raise DefiLlamaFundamentalsError("fixture_boundary_invalid")

    capture_started_text, capture_started = _utc(
        capture.get("capture_started_at"), "capture_started_at"
    )
    capture_completed_text, capture_completed = _utc(
        capture.get("capture_completed_at"), "capture_completed_at"
    )
    if capture_completed < capture_started:
        raise DefiLlamaFundamentalsError("capture_timing_invalid")

    mappings = _mappings(capture.get("mappings"))
    exchanges = _exchanges(
        capture.get("exchanges"),
        capture_started=capture_started,
        capture_completed=capture_completed,
    )
    raw_sha256 = hashlib.sha256(raw).hexdigest()
    response_sha256 = {
        request_id: _digest(exchange["response_body"])
        for request_id, exchange in exchanges.items()
    }
    request_identity_sha256 = {
        request_id: _digest(exchange["request"])
        for request_id, exchange in exchanges.items()
    }

    protocol_rows = _protocol_rows(exchanges[PROTOCOLS_REQUEST_ID]["response_body"])
    metric_rows = {
        request_id: _overview_rows(exchanges[request_id]["response_body"], request_id)
        for request_id in (
            DAILY_FEES_REQUEST_ID,
            DAILY_REVENUE_REQUEST_ID,
            DAILY_HOLDERS_REVENUE_REQUEST_ID,
        )
    }
    output: list[dict[str, Any]] = []
    for mapping in mappings:
        protocol = _unique_match(
            protocol_rows,
            "id",
            mapping["protocol_list_id"],
            "protocols_response",
        )
        if protocol.get("name") != mapping["protocol_name"]:
            raise DefiLlamaFundamentalsError("protocol_name_mapping_mismatch")
        if protocol.get("symbol") != mapping["token_symbol"]:
            raise DefiLlamaFundamentalsError("protocol_symbol_mapping_mismatch")
        by_metric = {
            request_id: _unique_match(
                rows,
                "slug",
                mapping["protocol_slug"],
                request_id,
            )
            for request_id, rows in metric_rows.items()
        }
        output.append(
            _normalized_row(
                mapping=mapping,
                protocol=protocol,
                by_metric=by_metric,
                exchanges=exchanges,
                capture_started_at=capture_started_text,
                capture_completed_at=capture_completed_text,
                raw_sha256=raw_sha256,
                response_sha256=response_sha256,
                request_identity_sha256=request_identity_sha256,
            )
        )
    return tuple(output)


def _mappings(value: object) -> tuple[dict[str, str], ...]:
    if not isinstance(value, list) or not value or len(value) > 100:
        raise DefiLlamaFundamentalsError("mappings_invalid")
    rows: list[dict[str, str]] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise DefiLlamaFundamentalsError(f"mapping_{index}_schema_invalid")
        _exact_keys(
            raw,
            {
                "canonical_asset_id",
                "coingecko_asset_id",
                "mapping_authority",
                "protocol_list_id",
                "protocol_name",
                "protocol_slug",
                "token_symbol",
            },
            f"mapping_{index}",
        )
        if raw.get("mapping_authority") != "operator_confirmed_fixture":
            raise DefiLlamaFundamentalsError(f"mapping_{index}_authority_invalid")
        protocol_name = raw.get("protocol_name")
        if not isinstance(protocol_name, str) or not protocol_name.strip() or len(protocol_name) > 128:
            raise DefiLlamaFundamentalsError(f"mapping_{index}_protocol_name_invalid")
        rows.append(
            {
                "canonical_asset_id": _identifier(
                    raw.get("canonical_asset_id"), f"mapping_{index}_canonical_asset_id"
                ),
                "coingecko_asset_id": _identifier(
                    raw.get("coingecko_asset_id"), f"mapping_{index}_coingecko_asset_id"
                ),
                "mapping_authority": "operator_confirmed_fixture",
                "protocol_list_id": _identifier(
                    raw.get("protocol_list_id"), f"mapping_{index}_protocol_list_id"
                ),
                "protocol_name": protocol_name.strip(),
                "protocol_slug": _identifier(
                    raw.get("protocol_slug"), f"mapping_{index}_protocol_slug"
                ),
                "token_symbol": _symbol(
                    raw.get("token_symbol"), f"mapping_{index}_token_symbol"
                ),
            }
        )
    for key in (
        "canonical_asset_id",
        "coingecko_asset_id",
        "protocol_list_id",
        "protocol_slug",
    ):
        values = [row[key] for row in rows]
        if len(values) != len(set(values)):
            raise DefiLlamaFundamentalsError(f"mapping_{key}_duplicate")
    return tuple(rows)


def _exchanges(
    value: object,
    *,
    capture_started: datetime,
    capture_completed: datetime,
) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list) or len(value) != len(_REQUEST_SPECS):
        raise DefiLlamaFundamentalsError("exchange_count_invalid")
    rows: dict[str, dict[str, Any]] = {}
    prior_started: datetime | None = None
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise DefiLlamaFundamentalsError(f"exchange_{index}_schema_invalid")
        _exact_keys(
            raw,
            {
                "duration_ms",
                "request",
                "request_id",
                "request_started_at",
                "response",
                "response_received_at",
            },
            f"exchange_{index}",
        )
        request_id = raw.get("request_id")
        if request_id not in _REQUEST_SPECS or request_id in rows:
            raise DefiLlamaFundamentalsError(f"exchange_{index}_request_id_invalid")
        started_text, started = _utc(
            raw.get("request_started_at"), f"exchange_{index}_request_started_at"
        )
        received_text, received = _utc(
            raw.get("response_received_at"), f"exchange_{index}_response_received_at"
        )
        duration = raw.get("duration_ms")
        if (
            isinstance(duration, bool)
            or not isinstance(duration, int)
            or not 0 <= duration <= MAX_EXCHANGE_DURATION_MS
            or started < capture_started
            or received < started
            or received > capture_completed
            or int((received - started).total_seconds() * 1000) < duration
            or (prior_started is not None and started < prior_started)
        ):
            raise DefiLlamaFundamentalsError(f"exchange_{index}_timing_invalid")
        prior_started = started
        request = _request(raw.get("request"), request_id)
        response_body = _response(raw.get("response"), request_id)
        rows[request_id] = {
            "duration_ms": duration,
            "request": request,
            "request_started_at": started_text,
            "response_body": response_body,
            "response_received_at": received_text,
        }
    if set(rows) != set(_REQUEST_SPECS):
        raise DefiLlamaFundamentalsError("exchange_request_set_invalid")
    return rows


def _request(value: object, request_id: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DefiLlamaFundamentalsError(f"{request_id}_request_schema_invalid")
    _exact_keys(value, {"host", "method", "path", "query"}, f"{request_id}_request")
    path, query = _REQUEST_SPECS[request_id]
    if (
        value.get("method") != "GET"
        or value.get("host") != PROVIDER_HOST
        or value.get("path") != path
        or value.get("query") != query
    ):
        raise DefiLlamaFundamentalsError(f"{request_id}_request_identity_invalid")
    return {"host": PROVIDER_HOST, "method": "GET", "path": path, "query": dict(query)}


def _response(value: object, request_id: str) -> object:
    if not isinstance(value, Mapping):
        raise DefiLlamaFundamentalsError(f"{request_id}_response_schema_invalid")
    _exact_keys(value, {"body", "content_type", "status_code"}, f"{request_id}_response")
    if value.get("status_code") != 200:
        raise DefiLlamaFundamentalsError(f"{request_id}_response_status_invalid")
    content_type = value.get("content_type")
    if not isinstance(content_type, str) or not content_type.casefold().startswith(
        "application/json"
    ):
        raise DefiLlamaFundamentalsError(f"{request_id}_response_content_type_invalid")
    return value.get("body")


def _protocol_rows(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list) or len(value) > MAX_RESPONSE_ROWS:
        raise DefiLlamaFundamentalsError("protocols_response_rows_invalid")
    return tuple(_mapping_row(row, "protocols_response") for row in value)


def _overview_rows(value: object, request_id: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Mapping):
        raise DefiLlamaFundamentalsError(f"{request_id}_response_body_invalid")
    raw = value.get("protocols")
    if not isinstance(raw, list) or len(raw) > MAX_RESPONSE_ROWS:
        raise DefiLlamaFundamentalsError(f"{request_id}_response_rows_invalid")
    return tuple(_mapping_row(row, request_id) for row in raw)


def _mapping_row(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DefiLlamaFundamentalsError(f"{field}_row_invalid")
    return value


def _unique_match(
    rows: tuple[Mapping[str, Any], ...],
    key: str,
    expected: str,
    field: str,
) -> Mapping[str, Any]:
    matches = [row for row in rows if row.get(key) == expected]
    if len(matches) != 1:
        raise DefiLlamaFundamentalsError(f"{field}_{key}_match_invalid")
    return matches[0]


def _normalized_row(
    *,
    mapping: Mapping[str, str],
    protocol: Mapping[str, Any],
    by_metric: Mapping[str, Mapping[str, Any]],
    exchanges: Mapping[str, Mapping[str, Any]],
    capture_started_at: str,
    capture_completed_at: str,
    raw_sha256: str,
    response_sha256: Mapping[str, str],
    request_identity_sha256: Mapping[str, str],
) -> dict[str, Any]:
    tvl = _amount(protocol.get("tvl"), "tvl", required=True)
    tvl_change_1d = _percent(protocol.get("change_1d"), "tvl_change_1d")
    tvl_change_7d = _percent(protocol.get("change_7d"), "tvl_change_7d")
    fees = _metric_values(by_metric[DAILY_FEES_REQUEST_ID], "fees")
    revenue = _metric_values(by_metric[DAILY_REVENUE_REQUEST_ID], "revenue")
    holders = _metric_values(
        by_metric[DAILY_HOLDERS_REVENUE_REQUEST_ID], "holders_revenue"
    )
    row: dict[str, Any] = {
        "schema_id": OUTPUT_SCHEMA_ID,
        "schema_version": 1,
        "contract_version": CONTRACT_VERSION,
        "row_type": "event_protocol_fundamentals",
        "provider": "defillama_tvl_fees_revenue",
        "source_provider": "defillama",
        "latest_source": "defillama",
        "source_family": "protocol_fundamentals",
        "source_class": "market_data",
        "source_pack": "protocol_fundamentals_pack",
        "impact_path_type": "protocol_fundamentals",
        "source_strength": "market_data",
        "accepted_evidence_count": 1,
        "protocol_id": mapping["protocol_list_id"],
        "protocol_slug": mapping["protocol_slug"],
        "protocol_name": mapping["protocol_name"],
        "symbol": mapping["token_symbol"],
        "coin_id": mapping["coingecko_asset_id"],
        "coingecko_asset_id": mapping["coingecko_asset_id"],
        "canonical_asset_id": mapping["canonical_asset_id"],
        "protocol_asset_mapping_status": "operator_confirmed_fixture",
        "protocol_asset_mapping_authority": mapping["mapping_authority"],
        "tvl_usd": tvl,
        "tvl": tvl,
        "tvl_change_24h_pct": tvl_change_1d,
        "tvl_change_7d_pct": tvl_change_7d,
        "fees_24h": fees["total_24h"],
        "fees_7d_total_usd": fees["total_7d"],
        "fees_30d_total_usd": fees["total_30d"],
        "fees_change_24h_pct": fees["change_1d"],
        "revenue_24h": revenue["total_24h"],
        "protocol_revenue_24h": revenue["total_24h"],
        "revenue_7d_total_usd": revenue["total_7d"],
        "revenue_30d_total_usd": revenue["total_30d"],
        "revenue_change_24h_pct": revenue["change_1d"],
        "holders_revenue_24h": holders["total_24h"],
        "holders_revenue_7d_total_usd": holders["total_7d"],
        "holders_revenue_30d_total_usd": holders["total_30d"],
        "holders_revenue_change_24h_pct": holders["change_1d"],
        "metric_units": {
            "tvl_usd": "usd",
            "tvl_change_24h_pct": "percent_points",
            "tvl_change_7d_pct": "percent_points",
            "fees_24h": "usd_24h_total",
            "fees_7d_total_usd": "usd_7d_total",
            "fees_30d_total_usd": "usd_30d_total",
            "fees_change_24h_pct": "percent_points",
            "revenue_24h": "usd_24h_total",
            "revenue_7d_total_usd": "usd_7d_total",
            "revenue_30d_total_usd": "usd_30d_total",
            "revenue_change_24h_pct": "percent_points",
            "holders_revenue_24h": "usd_24h_total",
            "holders_revenue_7d_total_usd": "usd_7d_total",
            "holders_revenue_30d_total_usd": "usd_30d_total",
            "holders_revenue_change_24h_pct": "percent_points",
        },
        "metric_availability": {
            "tvl": "observed",
            "fees": _availability(fees),
            "revenue": _availability(revenue),
            "holders_revenue": _availability(holders),
        },
        "metric_semantics": {
            "tvl": "usd_value_locked_snapshot_includes_asset_price_effects",
            "fees": "user_paid_top_line_fees",
            "revenue": "fees_retained_by_protocol",
            "holders_revenue": "revenue_returned_to_token_holders",
        },
        "tvl_change_is_net_flow": False,
        "fees_revenue_interchangeable": False,
        **_lineage_and_safety_fields(
            mapping=mapping,
            by_metric=by_metric,
            exchanges=exchanges,
            capture_started_at=capture_started_at,
            capture_completed_at=capture_completed_at,
            raw_sha256=raw_sha256,
            response_sha256=response_sha256,
            request_identity_sha256=request_identity_sha256,
        ),
    }
    row["protocol_metrics_snapshot"] = {
        key: value
        for key, value in row.items()
        if key
        in {
            "fees_24h",
            "fees_30d_total_usd",
            "fees_7d_total_usd",
            "fees_change_24h_pct",
            "holders_revenue_24h",
            "holders_revenue_30d_total_usd",
            "holders_revenue_7d_total_usd",
            "holders_revenue_change_24h_pct",
            "observed_at",
            "provider",
            "revenue_24h",
            "revenue_30d_total_usd",
            "revenue_7d_total_usd",
            "revenue_change_24h_pct",
            "source_url",
            "tvl_change_24h_pct",
            "tvl_change_7d_pct",
            "tvl_usd",
        }
        and value is not None
    }
    return row


def _lineage_and_safety_fields(
    *,
    mapping: Mapping[str, str],
    by_metric: Mapping[str, Mapping[str, Any]],
    exchanges: Mapping[str, Mapping[str, Any]],
    capture_started_at: str,
    capture_completed_at: str,
    raw_sha256: str,
    response_sha256: Mapping[str, str],
    request_identity_sha256: Mapping[str, str],
) -> dict[str, Any]:
    source_url = f"https://defillama.com/protocol/{mapping['protocol_slug']}"
    methodology_rows = {
        "fees": by_metric[DAILY_FEES_REQUEST_ID],
        "revenue": by_metric[DAILY_REVENUE_REQUEST_ID],
        "holders_revenue": by_metric[DAILY_HOLDERS_REVENUE_REQUEST_ID],
    }
    return {
        "provider_value_timestamp": None,
        "provider_value_timestamp_status": "unavailable_in_free_overview_response",
        "capture_started_at": capture_started_at,
        "capture_completed_at": capture_completed_at,
        "observed_at": capture_completed_at,
        "response_received_at_by_request": {
            request_id: exchange["response_received_at"]
            for request_id, exchange in exchanges.items()
        },
        "source_url": source_url,
        "latest_source_url": source_url,
        "source_title": f"{mapping['protocol_name']} DefiLlama fundamentals",
        "latest_source_title": f"{mapping['protocol_name']} DefiLlama fundamentals",
        "methodology_url_by_metric": {
            name: _optional_url(row.get("methodologyURL"))
            for name, row in methodology_rows.items()
        },
        "methodology_by_metric": {
            name: _methodology(row.get("methodology"))
            for name, row in methodology_rows.items()
        },
        "source_request_urls": {
            "protocols": f"https://{PROVIDER_HOST}/protocols",
            "fees": f"https://{PROVIDER_HOST}/overview/fees?dataType=dailyFees",
            "revenue": f"https://{PROVIDER_HOST}/overview/fees?dataType=dailyRevenue",
            "holders_revenue": (
                f"https://{PROVIDER_HOST}/overview/fees?dataType=dailyHoldersRevenue"
            ),
        },
        "request_identity_sha256_by_request": dict(request_identity_sha256),
        "provider_response_sha256_by_request": dict(response_sha256),
        "raw_fixture_capture_sha256": raw_sha256,
        "source_lineage_id": f"sha256:{raw_sha256}",
        "source_coverage_status": "complete_four_response_fixture",
        "freshness_status": "fixture",
        "market_context_freshness_status": "fixture",
        "capture_mode": CAPTURE_MODE,
        "fixture_provenance": True,
        "fixture_synthetic": True,
        "provider_call_performed": False,
        "provider_authorization_created": False,
        "authority_eligible": False,
        "campaign_evidence_eligible": False,
        "protocol_v2_input_quality_eligible": False,
        "protocol_v2_annex_bound": False,
        "protocol_v2_evidence_eligible": False,
        "directional_authority": False,
        "context_only": True,
        "research_only": True,
        "created_alert": False,
        "notification_send_enabled": False,
        "created_trade": False,
        "created_order": False,
        "created_paper_trade": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
    }


def _metric_values(row: Mapping[str, Any], field: str) -> dict[str, float | None]:
    return {
        "total_24h": _amount(row.get("total24h"), f"{field}_total24h"),
        "total_7d": _amount(row.get("total7d"), f"{field}_total7d"),
        "total_30d": _amount(row.get("total30d"), f"{field}_total30d"),
        "change_1d": _percent(row.get("change_1d"), f"{field}_change_1d"),
    }


def _availability(values: Mapping[str, float | None]) -> str:
    present = sum(value is not None for value in values.values())
    if present == len(values):
        return "observed"
    if present:
        return "partial"
    return "unavailable"


def _amount(value: object, field: str, *, required: bool = False) -> float | None:
    if value is None and not required:
        return None
    number = _finite_number(value, field)
    if number < 0 or number > 1e18:
        raise DefiLlamaFundamentalsError(f"{field}_outside_plausible_bounds")
    return number


def _percent(value: object, field: str) -> float | None:
    if value is None:
        return None
    number = _finite_number(value, field)
    if number < -100 or number > 1_000_000:
        raise DefiLlamaFundamentalsError(f"{field}_outside_plausible_bounds")
    return number


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DefiLlamaFundamentalsError(f"{field}_invalid")
    number = float(value)
    if not math.isfinite(number):
        raise DefiLlamaFundamentalsError(f"{field}_invalid")
    return number


def _methodology(value: object) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise DefiLlamaFundamentalsError("methodology_invalid")
    output: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise DefiLlamaFundamentalsError("methodology_invalid")
        if len(key) > 128 or len(item) > 4_096:
            raise DefiLlamaFundamentalsError("methodology_too_large")
        output[key] = item
    return output or None


def _optional_url(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 2_048:
        raise DefiLlamaFundamentalsError("methodology_url_invalid")
    if not value.startswith("https://"):
        raise DefiLlamaFundamentalsError("methodology_url_invalid")
    return value


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise DefiLlamaFundamentalsError(f"{field}_invalid")
    return value


def _symbol(value: object, field: str) -> str:
    if not isinstance(value, str) or not _SYMBOL_RE.fullmatch(value):
        raise DefiLlamaFundamentalsError(f"{field}_invalid")
    return value


def _utc(value: object, field: str) -> tuple[str, datetime]:
    if not isinstance(value, str) or not value.strip():
        raise DefiLlamaFundamentalsError(f"{field}_missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DefiLlamaFundamentalsError(f"{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DefiLlamaFundamentalsError(f"{field}_timezone_missing")
    utc = parsed.astimezone(timezone.utc)
    return utc.isoformat().replace("+00:00", "Z"), utc


def _exact_keys(value: Mapping[str, Any], expected: set[str], field: str) -> None:
    if set(value) != expected:
        raise DefiLlamaFundamentalsError(f"{field}_keys_invalid")


def _digest(value: object) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _reject_sensitive_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().casefold().replace(" ", "_")
            if normalized in _SENSITIVE_KEYS:
                raise DefiLlamaFundamentalsError("sensitive_key_forbidden")
            _reject_sensitive_keys(item)
    elif isinstance(value, list):
        for item in value:
            _reject_sensitive_keys(item)


def _summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "contract": CAPTURE_CONTRACT,
        "status": "fixture_valid",
        "row_count": len(rows),
        "canonical_asset_ids": [row.get("canonical_asset_id") for row in rows],
        "metric_availability": [row.get("metric_availability") for row in rows],
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
    parser = argparse.ArgumentParser(
        description="Validate a synthetic DefiLlama fundamentals fixture capture"
    )
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args(argv)
    rows = load_defillama_fundamentals_fixture_capture(args.fixture)
    print(json.dumps(_summary(rows), sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI boundary
    raise SystemExit(main())
