"""No-network DefiLlama protocol/asset mapping review contract.

This module can build a deterministic review template from exact market rows
and validate an operator-completed registry.  It never infers a protocol from
an asset name or symbol, performs a provider call, writes an artifact, or grants
evidence authority by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


REVIEW_SCHEMA_ID = "decision_radar.defillama_mapping_review"
REGISTRY_SCHEMA_ID = "decision_radar.defillama_mapping_registry"
SCHEMA_VERSION = 1
MAX_ASSETS = 100
MAPPED = "mapped"
NOT_APPLICABLE = "not_applicable"
PENDING = "pending"
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:#-]{0,127}$")
_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,31}$")
_REGISTRY_ID_RE = re.compile(r"^defillama-map-v1:[a-z0-9][a-z0-9._-]{0,63}$")
_SENSITIVE_KEYS = {
    "api-key",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "x-api-key",
}


class DefiLlamaMappingRegistryError(ValueError):
    """Raised when mapping review input violates the closed contract."""


def build_mapping_review(market_rows: Sequence[Mapping[str, object]]) -> dict[str, Any]:
    """Return a deterministic pending review without guessing any mapping."""

    assets = _market_assets(market_rows)
    digest = _digest(assets)
    return {
        "schema_id": REVIEW_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "provider": "defillama",
        "market_universe_sha256": digest,
        "asset_count": len(assets),
        "assets": [
            {
                **asset,
                "mapping_status": PENDING,
                "protocol_list_id": None,
                "protocol_slug": None,
                "protocol_name": None,
                "review_note": "",
            }
            for asset in assets
        ],
        "automatic_identity_inference": False,
        "provider_calls": 0,
        "research_only": True,
    }


def build_operator_registry_template(
    review: Mapping[str, object],
) -> dict[str, Any]:
    """Return a deliberately incomplete, directly fillable operator registry.

    The template carries the exact reviewed identities and universe digest but
    cannot pass ``normalize_mapping_registry`` until a human replaces every
    placeholder, chooses ``mapped`` or ``not_applicable`` for every row, adds
    an explicit note, and confirms each decision.
    """

    assets = _review_assets(review)
    return {
        "schema_id": REGISTRY_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "provider": "defillama",
        "registry_id": "REPLACE_WITH_DEFILLAMA_MAP_V1_REGISTRY_ID",
        "registry_mode": "operator",
        "reviewed_at": "REPLACE_WITH_UTC_TIMESTAMP",
        "reviewed_by": "REPLACE_WITH_REVIEWER_ALIAS",
        "market_universe_sha256": review["market_universe_sha256"],
        "mappings": [
            {
                "canonical_asset_id": asset["canonical_asset_id"],
                "coingecko_asset_id": asset["coingecko_asset_id"],
                "symbol": asset["symbol"],
                "mapping_status": PENDING,
                "protocol_list_id": None,
                "protocol_slug": None,
                "protocol_name": None,
                "review_note": "",
                "reviewer_confirmed": False,
            }
            for asset in assets
        ],
        "research_only": True,
    }


def normalize_mapping_registry(
    raw: bytes,
    *,
    allow_fixture: bool = False,
) -> dict[str, Any]:
    """Validate exact operator decisions and return a canonical projection."""

    if not isinstance(raw, bytes) or not raw or len(raw) > 256 * 1024:
        raise DefiLlamaMappingRegistryError("registry_size_invalid")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DefiLlamaMappingRegistryError("registry_json_invalid") from exc
    if not isinstance(value, Mapping):
        raise DefiLlamaMappingRegistryError("registry_schema_invalid")
    _reject_sensitive_keys(value)
    _exact_keys(
        value,
        {
            "mappings",
            "market_universe_sha256",
            "provider",
            "registry_id",
            "registry_mode",
            "research_only",
            "reviewed_at",
            "reviewed_by",
            "schema_id",
            "schema_version",
        },
        "registry",
    )
    mode = value.get("registry_mode")
    if (
        value.get("schema_id") != REGISTRY_SCHEMA_ID
        or value.get("schema_version") != SCHEMA_VERSION
        or value.get("provider") != "defillama"
        or value.get("research_only") is not True
        or mode not in {"operator", "fixture"}
    ):
        raise DefiLlamaMappingRegistryError("registry_boundary_invalid")
    if mode == "fixture" and not allow_fixture:
        raise DefiLlamaMappingRegistryError("fixture_registry_not_allowed")
    registry_id = _text(value.get("registry_id"), "registry_id", 96)
    if not _REGISTRY_ID_RE.fullmatch(registry_id):
        raise DefiLlamaMappingRegistryError("registry_id_invalid")
    reviewed_at = _utc(value.get("reviewed_at"), "reviewed_at")
    reviewed_by = _text(value.get("reviewed_by"), "reviewed_by", 96)
    if mode == "operator" and reviewed_by.casefold() in {
        "fixture",
        "mock",
        "test",
        "unknown",
    }:
        raise DefiLlamaMappingRegistryError("operator_reviewer_invalid")
    universe_digest = value.get("market_universe_sha256")
    if not isinstance(universe_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", universe_digest):
        raise DefiLlamaMappingRegistryError("market_universe_sha256_invalid")
    mappings = _mapping_rows(value.get("mappings"), mode=mode)
    projection = {
        "schema_id": REGISTRY_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "provider": "defillama",
        "registry_id": registry_id,
        "registry_mode": mode,
        "reviewed_at": reviewed_at,
        "reviewed_by": reviewed_by,
        "market_universe_sha256": universe_digest,
        "mapping_count": len(mappings),
        "mappings": list(mappings),
        "automatic_identity_inference": False,
        "provider_calls": 0,
        "research_only": True,
    }
    projection["registry_sha256"] = _digest(projection)
    return projection


def assess_mapping_coverage(
    review: Mapping[str, object],
    registry: Mapping[str, object] | None,
) -> dict[str, Any]:
    """Compare one canonical registry with the exact reviewed universe."""

    assets = _review_assets(review)
    canonical_registry = (
        _canonical_registry_projection(registry) if registry is not None else None
    )
    universe_digest = str(review.get("market_universe_sha256") or "")
    mapping_rows = canonical_registry.get("mappings") if canonical_registry else ()
    mappings = {
        str(row.get("canonical_asset_id")): row
        for row in mapping_rows or ()
        if isinstance(row, Mapping)
    }
    results: list[dict[str, Any]] = []
    for asset in assets:
        mapping = mappings.get(asset["canonical_asset_id"])
        if mapping is None:
            status = "unreviewed"
        elif (
            mapping.get("coingecko_asset_id") != asset["coingecko_asset_id"]
            or mapping.get("symbol") != asset["symbol"]
        ):
            status = "identity_conflict"
        else:
            status = str(mapping.get("mapping_status") or "invalid")
        results.append({**asset, "coverage_status": status})
    counts = {
        status: sum(1 for row in results if row["coverage_status"] == status)
        for status in (MAPPED, NOT_APPLICABLE, "unreviewed", "identity_conflict")
    }
    registry_mode = (
        str(canonical_registry.get("registry_mode") or "missing")
        if canonical_registry
        else "missing"
    )
    digest_matches = bool(
        canonical_registry
        and canonical_registry.get("market_universe_sha256") == universe_digest
    )
    complete = (
        bool(results)
        and counts["unreviewed"] == 0
        and counts["identity_conflict"] == 0
        and len(mappings) == len(results)
        and digest_matches
    )
    blockers: list[str] = []
    if canonical_registry is None:
        blockers.append("operator_registry_missing")
    elif registry_mode != "operator":
        blockers.append("operator_registry_required")
    if not digest_matches:
        blockers.append("registry_universe_digest_mismatch")
    if len(mappings) != len(results):
        blockers.append("mapping_cardinality_mismatch")
    if counts["unreviewed"]:
        blockers.append("unreviewed_assets_present")
    if counts["identity_conflict"]:
        blockers.append("asset_identity_conflicts_present")
    return {
        "schema_id": "decision_radar.defillama_mapping_coverage",
        "schema_version": SCHEMA_VERSION,
        "market_universe_sha256": universe_digest,
        "registry_id": canonical_registry.get("registry_id") if canonical_registry else None,
        "registry_mode": registry_mode,
        "registry_digest_matches_universe": digest_matches,
        "asset_count": len(results),
        "coverage_counts": counts,
        "assets": results,
        "coverage_complete": complete,
        "live_capture_mapping_eligible": complete and registry_mode == "operator",
        "live_capture_mapping_blockers": blockers,
        "automatic_identity_inference": False,
        "provider_calls": 0,
        "research_only": True,
    }


def _market_assets(rows: Sequence[Mapping[str, object]]) -> tuple[dict[str, Any], ...]:
    if not isinstance(rows, Sequence) or not rows or len(rows) > MAX_ASSETS:
        raise DefiLlamaMappingRegistryError("market_rows_invalid")
    assets: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_coingecko: set[str] = set()
    for expected_rank, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            raise DefiLlamaMappingRegistryError("market_row_schema_invalid")
        canonical_id = _identifier(row.get("canonical_asset_id"), "canonical_asset_id")
        coin_id = _identifier(
            row.get("coingecko_asset_id") or row.get("coin_id"),
            "coingecko_asset_id",
        )
        symbol = _symbol(row.get("symbol"), "symbol")
        name = _text(row.get("name") or symbol, "name", 128)
        rank = row.get("liquidity_rank")
        if rank is None:
            rank = expected_rank
        if type(rank) is not int or rank != expected_rank:
            raise DefiLlamaMappingRegistryError("liquidity_rank_invalid")
        if canonical_id in seen_ids or coin_id in seen_coingecko:
            raise DefiLlamaMappingRegistryError("market_identity_duplicate")
        seen_ids.add(canonical_id)
        seen_coingecko.add(coin_id)
        assets.append(
            {
                "canonical_asset_id": canonical_id,
                "coingecko_asset_id": coin_id,
                "symbol": symbol,
                "name": name,
                "liquidity_rank": rank,
            }
        )
    return tuple(assets)


def _mapping_rows(value: object, *, mode: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list) or not value or len(value) > MAX_ASSETS:
        raise DefiLlamaMappingRegistryError("mappings_invalid")
    rows = tuple(_mapping_row(raw, index=index, mode=mode) for index, raw in enumerate(value))
    _validate_mapping_uniqueness(rows)
    return rows


def _validate_mapping_uniqueness(rows: Sequence[Mapping[str, object]]) -> None:
    for key in ("canonical_asset_id", "coingecko_asset_id"):
        values = [str(row[key]) for row in rows]
        if len(values) != len(set(values)):
            raise DefiLlamaMappingRegistryError(f"mapping_{key}_duplicate")
    mapped = [row for row in rows if row["mapping_status"] == MAPPED]
    for key in ("protocol_list_id", "protocol_slug"):
        values = [str(row[key]) for row in mapped]
        if len(values) != len(set(values)):
            raise DefiLlamaMappingRegistryError(f"mapping_{key}_duplicate")


def _mapping_row(value: object, *, index: int, mode: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DefiLlamaMappingRegistryError(f"mapping_{index}_schema_invalid")
    _exact_keys(
        value,
        {
            "canonical_asset_id",
            "coingecko_asset_id",
            "mapping_status",
            "protocol_list_id",
            "protocol_name",
            "protocol_slug",
            "review_note",
            "reviewer_confirmed",
            "symbol",
        },
        f"mapping_{index}",
    )
    if value.get("reviewer_confirmed") is not True:
        raise DefiLlamaMappingRegistryError(f"mapping_{index}_not_confirmed")
    status = value.get("mapping_status")
    if status not in {MAPPED, NOT_APPLICABLE}:
        raise DefiLlamaMappingRegistryError(f"mapping_{index}_status_invalid")
    row = {
        "canonical_asset_id": _identifier(
            value.get("canonical_asset_id"), f"mapping_{index}_canonical_asset_id"
        ),
        "coingecko_asset_id": _identifier(
            value.get("coingecko_asset_id"), f"mapping_{index}_coingecko_asset_id"
        ),
        "symbol": _symbol(value.get("symbol"), f"mapping_{index}_symbol"),
        "mapping_status": status,
        "protocol_list_id": _optional_identifier(
            value.get("protocol_list_id"), f"mapping_{index}_protocol_list_id"
        ),
        "protocol_slug": _optional_identifier(
            value.get("protocol_slug"), f"mapping_{index}_protocol_slug"
        ),
        "protocol_name": _optional_text(
            value.get("protocol_name"), f"mapping_{index}_protocol_name", 128
        ),
        "review_note": _text(value.get("review_note"), f"mapping_{index}_review_note", 512),
        "reviewer_confirmed": True,
        "mapping_authority": (
            "operator_confirmed_registry" if mode == "operator" else "operator_confirmed_fixture"
        ),
    }
    protocol_values = (
        row["protocol_list_id"],
        row["protocol_slug"],
        row["protocol_name"],
    )
    if status == MAPPED and any(item is None for item in protocol_values):
        raise DefiLlamaMappingRegistryError(f"mapping_{index}_protocol_identity_missing")
    if status == NOT_APPLICABLE and any(item is not None for item in protocol_values):
        raise DefiLlamaMappingRegistryError(f"mapping_{index}_not_applicable_has_protocol")
    return row


def _review_assets(review: Mapping[str, object]) -> tuple[dict[str, Any], ...]:
    _exact_keys(
        review,
        {
            "asset_count",
            "assets",
            "automatic_identity_inference",
            "market_universe_sha256",
            "provider",
            "provider_calls",
            "research_only",
            "schema_id",
            "schema_version",
        },
        "review",
    )
    if (
        review.get("schema_id") != REVIEW_SCHEMA_ID
        or review.get("schema_version") != SCHEMA_VERSION
        or review.get("provider") != "defillama"
        or review.get("automatic_identity_inference") is not False
        or review.get("provider_calls") != 0
        or review.get("research_only") is not True
    ):
        raise DefiLlamaMappingRegistryError("review_schema_invalid")
    assets = review.get("assets")
    if not isinstance(assets, list) or not assets or len(assets) > MAX_ASSETS:
        raise DefiLlamaMappingRegistryError("review_assets_invalid")
    projected: list[dict[str, Any]] = []
    for expected_rank, row in enumerate(assets, start=1):
        if not isinstance(row, Mapping):
            raise DefiLlamaMappingRegistryError("review_assets_invalid")
        _exact_keys(
            row,
            {
                "canonical_asset_id",
                "coingecko_asset_id",
                "liquidity_rank",
                "mapping_status",
                "name",
                "protocol_list_id",
                "protocol_name",
                "protocol_slug",
                "review_note",
                "symbol",
            },
            f"review_asset_{expected_rank - 1}",
        )
        if (
            row.get("liquidity_rank") != expected_rank
            or row.get("mapping_status") != PENDING
            or row.get("protocol_list_id") is not None
            or row.get("protocol_slug") is not None
            or row.get("protocol_name") is not None
            or row.get("review_note") != ""
        ):
            raise DefiLlamaMappingRegistryError("review_asset_boundary_invalid")
        projected.append(
            {
                "canonical_asset_id": _identifier(
                    row.get("canonical_asset_id"), "canonical_asset_id"
                ),
                "coingecko_asset_id": _identifier(
                    row.get("coingecko_asset_id"), "coingecko_asset_id"
                ),
                "symbol": _symbol(row.get("symbol"), "symbol"),
                "name": _text(row.get("name"), "name", 128),
                "liquidity_rank": expected_rank,
            }
        )
    asset_count = review.get("asset_count")
    universe_digest = review.get("market_universe_sha256")
    if (
        type(asset_count) is not int
        or asset_count != len(projected)
        or not isinstance(universe_digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", universe_digest)
        or _digest(projected) != universe_digest
    ):
        raise DefiLlamaMappingRegistryError("review_universe_digest_invalid")
    canonical_ids = [row["canonical_asset_id"] for row in projected]
    coingecko_ids = [row["coingecko_asset_id"] for row in projected]
    if len(canonical_ids) != len(set(canonical_ids)) or len(coingecko_ids) != len(
        set(coingecko_ids)
    ):
        raise DefiLlamaMappingRegistryError("review_identity_duplicate")
    return tuple(projected)


def _canonical_registry_projection(registry: Mapping[str, object]) -> dict[str, Any]:
    """Fail closed unless ``registry`` is the exact normalized projection."""

    _exact_keys(
        registry,
        {
            "automatic_identity_inference",
            "mapping_count",
            "mappings",
            "market_universe_sha256",
            "provider",
            "provider_calls",
            "registry_id",
            "registry_mode",
            "registry_sha256",
            "research_only",
            "reviewed_at",
            "reviewed_by",
            "schema_id",
            "schema_version",
        },
        "canonical_registry",
    )
    mode = registry.get("registry_mode")
    if (
        registry.get("schema_id") != REGISTRY_SCHEMA_ID
        or registry.get("schema_version") != SCHEMA_VERSION
        or registry.get("provider") != "defillama"
        or mode not in {"operator", "fixture"}
        or registry.get("automatic_identity_inference") is not False
        or registry.get("provider_calls") != 0
        or registry.get("research_only") is not True
    ):
        raise DefiLlamaMappingRegistryError("canonical_registry_boundary_invalid")
    registry_id = _text(registry.get("registry_id"), "registry_id", 96)
    if not _REGISTRY_ID_RE.fullmatch(registry_id):
        raise DefiLlamaMappingRegistryError("registry_id_invalid")
    reviewed_at = _utc(registry.get("reviewed_at"), "reviewed_at")
    reviewed_by = _text(registry.get("reviewed_by"), "reviewed_by", 96)
    if mode == "operator" and reviewed_by.casefold() in {
        "fixture",
        "mock",
        "test",
        "unknown",
    }:
        raise DefiLlamaMappingRegistryError("operator_reviewer_invalid")
    universe_digest = registry.get("market_universe_sha256")
    if not isinstance(universe_digest, str) or not re.fullmatch(
        r"[0-9a-f]{64}", universe_digest
    ):
        raise DefiLlamaMappingRegistryError("market_universe_sha256_invalid")
    raw_rows = registry.get("mappings")
    if not isinstance(raw_rows, list) or not raw_rows or len(raw_rows) > MAX_ASSETS:
        raise DefiLlamaMappingRegistryError("canonical_mappings_invalid")
    mappings: list[dict[str, Any]] = []
    for index, row in enumerate(raw_rows):
        if not isinstance(row, Mapping):
            raise DefiLlamaMappingRegistryError(f"canonical_mapping_{index}_invalid")
        raw_row = dict(row)
        authority = raw_row.pop("mapping_authority", None)
        canonical = _mapping_row(raw_row, index=index, mode=str(mode))
        if authority != canonical["mapping_authority"] or dict(row) != canonical:
            raise DefiLlamaMappingRegistryError(f"canonical_mapping_{index}_invalid")
        mappings.append(canonical)
    _validate_mapping_uniqueness(mappings)
    if type(registry.get("mapping_count")) is not int or registry.get(
        "mapping_count"
    ) != len(mappings):
        raise DefiLlamaMappingRegistryError("canonical_mapping_count_invalid")
    projection = {
        "schema_id": REGISTRY_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "provider": "defillama",
        "registry_id": registry_id,
        "registry_mode": mode,
        "reviewed_at": reviewed_at,
        "reviewed_by": reviewed_by,
        "market_universe_sha256": universe_digest,
        "mapping_count": len(mappings),
        "mappings": mappings,
        "automatic_identity_inference": False,
        "provider_calls": 0,
        "research_only": True,
    }
    registry_digest = registry.get("registry_sha256")
    if (
        not isinstance(registry_digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", registry_digest)
        or registry_digest != _digest(projection)
    ):
        raise DefiLlamaMappingRegistryError("canonical_registry_digest_invalid")
    projection["registry_sha256"] = registry_digest
    return projection


def _exact_keys(value: Mapping[str, object], expected: set[str], field: str) -> None:
    if set(value) != expected:
        raise DefiLlamaMappingRegistryError(f"{field}_keys_invalid")


def _identifier(value: object, field: str) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not _ID_RE.fullmatch(text):
        raise DefiLlamaMappingRegistryError(f"{field}_invalid")
    return text


def _optional_identifier(value: object, field: str) -> str | None:
    return None if value is None else _identifier(value, field)


def _symbol(value: object, field: str) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not _SYMBOL_RE.fullmatch(text):
        raise DefiLlamaMappingRegistryError(f"{field}_invalid")
    return text


def _text(value: object, field: str, limit: int) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not text or len(text) > limit or any(ord(char) < 32 for char in text):
        raise DefiLlamaMappingRegistryError(f"{field}_invalid")
    return text


def _optional_text(value: object, field: str, limit: int) -> str | None:
    return None if value is None else _text(value, field, limit)


def _utc(value: object, field: str) -> str:
    text = _text(value, field, 64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DefiLlamaMappingRegistryError(f"{field}_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DefiLlamaMappingRegistryError(f"{field}_invalid")
    return parsed.isoformat()


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _reject_sensitive_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() in _SENSITIVE_KEYS:
                raise DefiLlamaMappingRegistryError("sensitive_key_forbidden")
            _reject_sensitive_keys(item)
    elif isinstance(value, list):
        for item in value:
            _reject_sensitive_keys(item)


def _load_market_rows(path: Path) -> list[Mapping[str, object]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    rows = value.get("rows") if isinstance(value, Mapping) else value
    if not isinstance(rows, list):
        raise DefiLlamaMappingRegistryError("market_rows_invalid")
    return [row for row in rows if isinstance(row, Mapping)]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("market_rows", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--allow-fixture-registry", action="store_true")
    args = parser.parse_args(argv)
    review = build_mapping_review(_load_market_rows(args.market_rows))
    registry = None
    if args.registry is not None:
        registry = normalize_mapping_registry(
            args.registry.read_bytes(),
            allow_fixture=args.allow_fixture_registry,
        )
    print(json.dumps(assess_mapping_coverage(review, registry), sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
