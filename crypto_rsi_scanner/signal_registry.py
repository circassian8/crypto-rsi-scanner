"""Canonical signal/setup registry.

An RSI flag only becomes useful after we state its hypothesis: what setup it is,
which way it expects price to move, when the broader market favors it, and how
much prior edge the backtest gives it. Keep those definitions here so scanner,
backtest, outcomes, paper trading, and formatting all speak the same language.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SignalDefinition:
    flag_direction: str
    coin_regime: str
    setup_type: str
    expected_dir: str
    regime_note: str


@dataclass(frozen=True)
class SetupDefinition:
    setup_type: str
    label: str
    favorable_markets: tuple[str, ...]
    adverse_markets: tuple[str, ...]
    has_edge: bool
    edge_priors: dict[str, int]


_MARKET_ALIASES = {
    "BULL": "UPTREND",
    "BEAR": "DOWNTREND",
    "CHOP": "RANGE",
}

_DEFAULT_EDGE_PRIORS = {
    # Conviction baseline by measured setup edge. These are not probabilities;
    # they are attention priors around which severity/confluence/live history
    # can move. Favorable > neutral > adverse, no-edge stays context-only.
    "favorable": 62,
    "neutral": 42,
    "adverse": 24,
    "no_edge": 16,
}

_PRIOR_OVERRIDE_ENV = "RSI_REGISTRY_PRIORS"
_PRIOR_KEYS = frozenset(_DEFAULT_EDGE_PRIORS)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

SETUPS: dict[str, SetupDefinition] = {
    "mean_reversion": SetupDefinition(
        setup_type="mean_reversion",
        label="Mean Reversion",
        favorable_markets=("RANGE",),
        adverse_markets=("UPTREND",),
        has_edge=True,
        edge_priors={**_DEFAULT_EDGE_PRIORS, "favorable": 58},
    ),
    "dip_buy": SetupDefinition(
        setup_type="dip_buy",
        label="Dip Buy",
        favorable_markets=("UPTREND",),
        adverse_markets=("DOWNTREND",),
        has_edge=True,
        edge_priors={**_DEFAULT_EDGE_PRIORS, "favorable": 64},
    ),
    "trend_continuation": SetupDefinition(
        setup_type="trend_continuation",
        label="Trend Continuation",
        favorable_markets=("UPTREND",),
        adverse_markets=("RANGE",),
        has_edge=True,
        edge_priors={**_DEFAULT_EDGE_PRIORS, "favorable": 64},
    ),
    "breakdown_risk": SetupDefinition(
        setup_type="breakdown_risk",
        label="Breakdown Risk",
        favorable_markets=(),
        adverse_markets=("UPTREND", "DOWNTREND", "RANGE"),
        has_edge=False,
        edge_priors={**_DEFAULT_EDGE_PRIORS},
    ),
}


_SIGNALS: dict[tuple[str, str], SignalDefinition] = {
    ("OB", "UPTREND"): SignalDefinition(
        "OB", "UPTREND", "trend_continuation", "up", "continuation"
    ),
    ("OB", "RANGE"): SignalDefinition(
        "OB", "RANGE", "mean_reversion", "down", "range-top"
    ),
    ("OB", "DOWNTREND"): SignalDefinition(
        "OB", "DOWNTREND", "mean_reversion", "down", "reversal?"
    ),
    ("OS", "UPTREND"): SignalDefinition(
        "OS", "UPTREND", "dip_buy", "up", "dip?"
    ),
    ("OS", "RANGE"): SignalDefinition(
        "OS", "RANGE", "mean_reversion", "up", "range-bottom"
    ),
    ("OS", "DOWNTREND"): SignalDefinition(
        "OS", "DOWNTREND", "breakdown_risk", "down", "continuation"
    ),
}


def flag_direction(flag: str) -> str:
    if not flag:
        return ""
    return "OB" if flag in ("OB", "PRE_OB") else "OS"


def canonical_market_regime(regime: str | None) -> str:
    if not regime:
        return ""
    r = str(regime).upper()
    return _MARKET_ALIASES.get(r, r)


def signal_for(flag: str, coin_regime: str) -> SignalDefinition | None:
    direction = flag_direction(flag)
    if not direction:
        return None
    regime = canonical_market_regime(coin_regime)
    mapped = _SIGNALS.get((direction, regime))
    if mapped:
        return mapped
    # With no reliable coin regime, fall back to the base mean-reversion read.
    return SignalDefinition(
        direction,
        regime or "UNKNOWN",
        "mean_reversion",
        "down" if direction == "OB" else "up",
        "",
    )


def setup_for(flag: str, coin_regime: str) -> tuple[str, str]:
    sig = signal_for(flag, coin_regime)
    if sig is None:
        return "", ""
    return sig.setup_type, sig.expected_dir


def regime_note(flag: str, coin_regime: str) -> str:
    sig = signal_for(flag, coin_regime)
    if sig is None:
        return ""
    if canonical_market_regime(coin_regime) in ("", "UNKNOWN"):
        return ""
    return sig.regime_note


def setup_definition(setup_type: str | None) -> SetupDefinition | None:
    if not setup_type:
        return None
    return SETUPS.get(str(setup_type))


def setup_has_edge(setup_type: str | None) -> bool:
    setup = setup_definition(setup_type)
    return bool(setup and setup.has_edge)


def _validate_prior_overrides(doc: dict) -> dict[str, dict[str, int]]:
    if not isinstance(doc, dict):
        raise ValueError("calibration document must be a JSON object")
    schema = doc.get("schema", 1)
    if schema != 1:
        raise ValueError(f"unsupported calibration schema: {schema!r}")
    setups = doc.get("setups", {})
    if not isinstance(setups, dict):
        raise ValueError("calibration document must contain a setups object")

    overrides: dict[str, dict[str, int]] = {}
    for setup_type, setup_payload in setups.items():
        if setup_type not in SETUPS:
            continue
        if not isinstance(setup_payload, dict):
            raise ValueError(f"{setup_type}: setup payload must be an object")
        priors = setup_payload.get("edge_priors", {})
        if not isinstance(priors, dict):
            raise ValueError(f"{setup_type}: edge_priors must be an object")

        valid: dict[str, int] = {}
        for key, value in priors.items():
            if key not in _PRIOR_KEYS:
                raise ValueError(f"{setup_type}: unknown prior key {key!r}")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{setup_type}.{key}: prior must be numeric")
            rounded = int(round(value))
            if rounded < 0 or rounded > 100:
                raise ValueError(f"{setup_type}.{key}: prior outside 0..100")
            valid[key] = rounded
        if valid:
            overrides[setup_type] = valid
    return overrides


def load_prior_overrides(path: str | os.PathLike | None, *, strict: bool = False) -> dict[str, dict[str, int]]:
    """Load explicit backtest-calibrated prior overrides.

    The live registry only uses this when `RSI_REGISTRY_PRIORS` points at a JSON
    file. Missing or invalid files fail soft and leave checked-in defaults live.
    """
    if not path:
        return {}
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    try:
        with p.open("r", encoding="utf-8") as fh:
            return _validate_prior_overrides(json.load(fh))
    except Exception as exc:  # noqa: BLE001
        if strict:
            raise
        log.warning("Ignoring registry prior calibration %s: %s", p, exc)
        return {}


def _load_env_prior_overrides() -> tuple[dict[str, dict[str, int]], str | None]:
    path = os.getenv(_PRIOR_OVERRIDE_ENV)
    if not path:
        return {}, None
    overrides = load_prior_overrides(path)
    return overrides, str(Path(path).expanduser()) if overrides else None


_CALIBRATED_EDGE_PRIORS, _CALIBRATED_PRIOR_SOURCE = _load_env_prior_overrides()


def calibrated_prior_source() -> str | None:
    return _CALIBRATED_PRIOR_SOURCE


def market_alignment(setup_type: str | None, market_regime: str | None) -> str:
    setup = setup_definition(setup_type)
    regime = canonical_market_regime(market_regime)
    if setup is None or regime in ("", "UNKNOWN", "NA"):
        return "neutral"
    if not setup.has_edge:
        return "adverse"
    if regime in setup.favorable_markets:
        return "favorable"
    if regime in setup.adverse_markets:
        return "adverse"
    return "neutral"


def edge_conviction_prior(
    setup_type: str | None,
    alignment: str,
    overrides: dict[str, dict[str, int]] | None = None,
) -> int | None:
    setup = setup_definition(setup_type)
    if setup is None:
        return None
    priors = dict(setup.edge_priors)
    priors.update((overrides if overrides is not None else _CALIBRATED_EDGE_PRIORS).get(setup.setup_type, {}))
    if not setup.has_edge:
        return priors["no_edge"]
    key = alignment if alignment in ("favorable", "neutral", "adverse") else "neutral"
    return priors[key]


def market_conviction_adjustment(base: int, alignment: str, swing: int = 12) -> int:
    """Legacy additive market nudge retained for callers/tests that need it.

    The live scanner now uses `edge_conviction_prior` as its baseline instead of
    applying this as a second additive step.
    """
    if alignment == "favorable":
        return int(min(100, base + swing))
    if alignment == "adverse":
        return int(max(0, base - swing))
    return base
