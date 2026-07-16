"""Deterministic descriptive statistics for empirical replay analysis.

This private sibling keeps the replay analysis assembler focused on cohort
semantics.  It is pure, performs no I/O, and retains the protocol's frozen
bootstrap seed and fraction-return contract.
"""

from __future__ import annotations

import hashlib
import math
import random
import statistics
from typing import Any, Sequence

from . import empirical_validation_protocol


def _robust_summary(values: Sequence[float]) -> dict[str, float | None]:
    ordered = sorted(values)
    return {
        "mean": _mean(ordered),
        "median": statistics.median(ordered) if ordered else None,
        "trimmed_mean_10pct": _trimmed_mean(ordered, 0.10),
        "downside_5pct": _quantile(ordered, 0.05),
    }


def _bootstrap_mean_ci(
    values: Sequence[float], *, resamples: int, label: str
) -> dict[str, Any]:
    if not values:
        return {
            "status": "not_estimable_no_sample",
            "method": "deterministic_episode_bootstrap_mean_percentile",
            "confidence_level": 0.95,
            "resamples": resamples,
            "sample_size": 0,
            "lower_fraction": None,
            "upper_fraction": None,
            "return_unit": "fraction",
        }
    if len(values) == 1:
        value = float(values[0])
        return {
            "status": "degenerate_single_episode",
            "method": "deterministic_episode_bootstrap_mean_percentile",
            "confidence_level": 0.95,
            "resamples": resamples,
            "sample_size": 1,
            "lower_fraction": value,
            "upper_fraction": value,
            "return_unit": "fraction",
        }
    seed_material = (
        f"{empirical_validation_protocol.DETERMINISTIC_SEED}\0{label}"
    ).encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big")
    rng = random.Random(seed)
    n = len(values)
    means = sorted(
        sum(values[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(resamples)
    )
    return {
        "status": "estimated_exploratory",
        "method": "deterministic_episode_bootstrap_mean_percentile",
        "confidence_level": 0.95,
        "resamples": resamples,
        "sample_size": n,
        "lower_fraction": _quantile(means, 0.025),
        "upper_fraction": _quantile(means, 0.975),
        "return_unit": "fraction",
    }


def _trimmed_mean(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    trim = math.floor(len(values) * fraction)
    retained = values[trim:len(values) - trim] if trim else values
    return _mean(retained)


def _quantile(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(values[lower])
    weight = position - lower
    return float(values[lower] * (1.0 - weight) + values[upper] * weight)


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None
