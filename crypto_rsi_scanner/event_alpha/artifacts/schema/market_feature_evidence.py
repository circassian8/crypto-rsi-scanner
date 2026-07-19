"""Closed projection and validation for canonical market-feature evidence."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any


_FEATURE_NAME = re.compile(r"[a-z][a-z0-9_]{0,95}")
_HEX_SHA256 = re.compile(r"[0-9a-f]{64}")
_TEMPORAL_RELATIVE = re.compile(
    r"temporal_relative_return_vs_(btc|eth)_([1-9][0-9]*)h(_zscore)?"
)
_TEMPORAL_RETURN = re.compile(r"temporal_return_([1-9][0-9]*)h")
_TEMPORAL_RETURN_ZSCORE = re.compile(r"temporal_return_zscore_([1-9][0-9]*)h")
_TEMPORAL_RETURN_VOLATILITY = re.compile(
    r"temporal_return_volatility_([1-9][0-9]*)h"
)
_TEMPORAL_VOLATILITY_ZSCORE = re.compile(
    r"temporal_volatility_zscore_([1-9][0-9]*)h"
)
_TEMPORAL_KEYS = frozenset(
    {
        "basis",
        "status",
        "calculation",
        "sample_count",
        "current_observation_id",
        "baseline_first_observation_id",
        "baseline_last_observation_id",
        "baseline_input_observation_count",
        "baseline_observation_ids_sha256",
        "providers",
        "data_modes",
        "research_only",
        "benchmark_asset_id",
    }
)
_TEMPORAL_REQUIRED_KEYS = _TEMPORAL_KEYS - {"benchmark_asset_id"}
_TEMPORAL_STATUSES = frozenset(
    {
        "ready",
        "warming",
        "warming_time_coverage",
        "missing_current",
        "constant_baseline",
        "not_applicable",
    }
)
_MAX_FEATURES = 128
_MAX_MAPPING_KEYS = 128
_MAX_SEQUENCE_ITEMS = 256
_MAX_DEPTH = 8
_MAX_STRING_LENGTH = 4096


def canonical_projection(
    value: object,
    *,
    expected_current_observation_id: str | None = None,
) -> dict[str, Any]:
    """Return one bounded JSON projection or fail before artifact creation."""

    if value in (None, ""):
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("market_feature_evidence_invalid:value:dict")
    if len(value) > _MAX_FEATURES:
        raise ValueError("market_feature_evidence_invalid:value:too_many_features")

    projected = _canonical_json(value, path="value", depth=0)
    assert isinstance(projected, dict)
    common_current_id = expected_current_observation_id
    for feature, details in projected.items():
        if _FEATURE_NAME.fullmatch(feature) is None:
            raise ValueError(
                f"market_feature_evidence_invalid:feature_name:{feature}"
            )
        if not isinstance(details, dict):
            raise ValueError(
                f"market_feature_evidence_invalid:{feature}:dict"
            )
        if not feature.startswith("temporal_"):
            continue
        _validate_temporal_entry(feature, details)
        current_id = str(details["current_observation_id"])
        if common_current_id is None:
            common_current_id = current_id
        elif current_id != common_current_id:
            raise ValueError(
                f"market_feature_evidence_invalid:{feature}:current_observation_id_mismatch"
            )
    return projected


def validate_contract(
    row: Mapping[str, Any],
    *,
    nested_market_snapshot: bool = False,
) -> list[str]:
    """Validate evidence on a snapshot row or an anomaly's nested snapshot."""

    container: object = row.get("market_state_snapshot") if nested_market_snapshot else row
    if container is None:
        return []
    if not isinstance(container, Mapping):
        return []
    if "market_feature_evidence" not in container:
        return []
    expected = container.get("market_history_observation_id")
    expected_id = expected if isinstance(expected, str) and expected else None
    try:
        canonical_projection(
            container.get("market_feature_evidence"),
            expected_current_observation_id=expected_id,
        )
    except ValueError as exc:
        return [str(exc)]
    return []


def _canonical_json(value: object, *, path: str, depth: int) -> Any:
    if depth > _MAX_DEPTH:
        raise ValueError(f"market_feature_evidence_invalid:{path}:max_depth")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        if len(value) > _MAX_STRING_LENGTH or "\x00" in value:
            raise ValueError(f"market_feature_evidence_invalid:{path}:string")
        return value
    if isinstance(value, Real):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"market_feature_evidence_invalid:{path}:finite_number")
        return int(value) if isinstance(value, int) else float(value)
    if isinstance(value, Mapping):
        if len(value) > _MAX_MAPPING_KEYS:
            raise ValueError(f"market_feature_evidence_invalid:{path}:mapping_size")
        keys = tuple(value.keys())
        if any(not isinstance(key, str) or not key for key in keys):
            raise ValueError(f"market_feature_evidence_invalid:{path}:string_keys")
        return {
            key: _canonical_json(value[key], path=f"{path}.{key}", depth=depth + 1)
            for key in sorted(keys)
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if len(value) > _MAX_SEQUENCE_ITEMS:
            raise ValueError(f"market_feature_evidence_invalid:{path}:sequence_size")
        return [
            _canonical_json(item, path=f"{path}[{index}]", depth=depth + 1)
            for index, item in enumerate(value)
        ]
    raise ValueError(f"market_feature_evidence_invalid:{path}:json_value")


def _validate_temporal_entry(feature: str, details: Mapping[str, Any]) -> None:
    unknown = sorted(set(details) - _TEMPORAL_KEYS)
    missing = sorted(_TEMPORAL_REQUIRED_KEYS - set(details))
    if unknown:
        raise ValueError(
            f"market_feature_evidence_invalid:{feature}:unknown_keys={','.join(unknown)}"
        )
    if missing:
        raise ValueError(
            f"market_feature_evidence_invalid:{feature}:missing_keys={','.join(missing)}"
        )
    if details.get("basis") != "temporal_baseline":
        raise ValueError(f"market_feature_evidence_invalid:{feature}:basis")
    if details.get("status") not in _TEMPORAL_STATUSES:
        raise ValueError(f"market_feature_evidence_invalid:{feature}:status")
    if details.get("calculation") != _expected_calculation(feature):
        raise ValueError(f"market_feature_evidence_invalid:{feature}:calculation")
    if details.get("research_only") is not True:
        raise ValueError(f"market_feature_evidence_invalid:{feature}:research_only")

    sample_count = _nonnegative_int(details.get("sample_count"), feature, "sample_count")
    input_count = _nonnegative_int(
        details.get("baseline_input_observation_count"),
        feature,
        "baseline_input_observation_count",
    )
    if sample_count > input_count:
        raise ValueError(f"market_feature_evidence_invalid:{feature}:sample_count")
    _nonempty_string(details.get("current_observation_id"), feature, "current_observation_id")
    providers = _sorted_unique_strings(details.get("providers"), feature, "providers")
    modes = _sorted_unique_strings(details.get("data_modes"), feature, "data_modes")

    first = details.get("baseline_first_observation_id")
    last = details.get("baseline_last_observation_id")
    digest = details.get("baseline_observation_ids_sha256")
    if input_count == 0:
        if first is not None or last is not None or digest is not None or providers or modes:
            raise ValueError(f"market_feature_evidence_invalid:{feature}:empty_baseline")
    else:
        _nonempty_string(first, feature, "baseline_first_observation_id")
        _nonempty_string(last, feature, "baseline_last_observation_id")
        if not isinstance(digest, str) or _HEX_SHA256.fullmatch(digest) is None:
            raise ValueError(f"market_feature_evidence_invalid:{feature}:baseline_digest")

    relative = _TEMPORAL_RELATIVE.fullmatch(feature)
    benchmark = details.get("benchmark_asset_id")
    if relative:
        _nonempty_string(benchmark, feature, "benchmark_asset_id")
    elif "benchmark_asset_id" in details:
        raise ValueError(f"market_feature_evidence_invalid:{feature}:benchmark_asset_id")


def _expected_calculation(feature: str) -> str:
    relative = _TEMPORAL_RELATIVE.fullmatch(feature)
    if relative:
        benchmark, hours, zscore = relative.groups()
        if zscore:
            return f"relative_return_vs_{benchmark}_{hours}h_zscore"
        return f"asset_return_minus_{benchmark}_return"
    match = _TEMPORAL_RETURN.fullmatch(feature)
    if match:
        return "price_horizon_return"
    match = _TEMPORAL_RETURN_ZSCORE.fullmatch(feature)
    if match:
        return f"return_zscore_{match.group(1)}h"
    match = _TEMPORAL_RETURN_VOLATILITY.fullmatch(feature)
    if match:
        return f"return_volatility_{match.group(1)}h"
    match = _TEMPORAL_VOLATILITY_ZSCORE.fullmatch(feature)
    if match:
        return f"volatility_zscore_{match.group(1)}h"
    if feature == "temporal_volume_zscore_24h":
        return "volume_zscore_24h"
    if feature == "temporal_turnover_zscore":
        return "turnover_zscore"
    raise ValueError(f"market_feature_evidence_invalid:{feature}:unsupported_feature")


def _nonnegative_int(value: object, feature: str, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"market_feature_evidence_invalid:{feature}:{field}")
    return value


def _nonempty_string(value: object, feature: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"market_feature_evidence_invalid:{feature}:{field}")
    return value


def _sorted_unique_strings(value: object, feature: str, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ValueError(f"market_feature_evidence_invalid:{feature}:{field}")
    items = tuple(value)
    if items != tuple(sorted(set(items))):
        raise ValueError(f"market_feature_evidence_invalid:{feature}:{field}")
    return items
