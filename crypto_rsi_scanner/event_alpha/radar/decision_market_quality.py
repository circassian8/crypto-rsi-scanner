"""Pure market-evidence quality caps for Decision Model v2.

This module interprets already-normalized quality metadata.  It does not fetch
providers, mutate candidates, or choose a final Decision Radar route.
"""

from __future__ import annotations

from typing import Any, Mapping

from .decision_models import SpreadStatus


_PROXY_BASIS_TERMS = (
    "proxy",
    "cross_sectional",
    "market_cap",
    "24h_volume",
    "unavailable",
    "unknown",
)

_MARKET_ROUTE_CAPS = frozenset({"dashboard_watch", "diagnostic"})
_TEMPORAL_BASELINE_STATUSES = frozenset({
    "warm",
    "warming",
    "cold",
    "unavailable",
    "stale",
    "not_evaluated",
    "insufficient_history",
})
_LIMITED_BASELINE_STATUSES = _TEMPORAL_BASELINE_STATUSES - {"warm"}


def _market_quality_metadata(market: Mapping[str, Any]) -> dict[str, Any]:
    raw_quality = market.get("market_data_quality")
    quality_claimed = "market_data_quality" in market
    quality = dict(raw_quality) if isinstance(raw_quality, Mapping) else {}
    invalid: list[str] = []
    if quality_claimed and not isinstance(raw_quality, Mapping):
        invalid.append("market_data_quality")

    raw_basis, basis_claimed = _first_claim(
        (market, "market_feature_basis"),
        (quality, "feature_basis"),
    )
    basis: dict[str, str] = {}
    if basis_claimed:
        if isinstance(raw_basis, Mapping):
            for key, value in raw_basis.items():
                if (
                    not isinstance(key, str)
                    or not key.strip()
                    or not isinstance(value, str)
                    or not value.strip()
                ):
                    invalid.append("market_feature_basis")
                    basis = {}
                    break
                basis[key.strip()] = value.strip().casefold()
        else:
            invalid.append("market_feature_basis")

    raw_route_cap, route_cap_claimed = _first_claim(
        (market, "market_route_cap"),
        (quality, "market_route_cap"),
    )
    route_cap = _typed_enum(raw_route_cap, _MARKET_ROUTE_CAPS)
    if route_cap_claimed and not route_cap:
        invalid.append("market_route_cap")

    raw_baseline_status, baseline_status_claimed = _first_claim(
        (market, "temporal_baseline_status"),
        (market, "baseline_status"),
        (quality, "temporal_baseline_status"),
        (quality, "baseline_status"),
    )
    baseline_status = _typed_enum(
        raw_baseline_status,
        _TEMPORAL_BASELINE_STATUSES,
    )
    if baseline_status_claimed and not baseline_status:
        invalid.append("temporal_baseline_status")

    explicit_proxy_only, proxy_only_claimed = _first_claim(
        (market, "proxy_only_market_features"),
        (quality, "proxy_only"),
    )
    if proxy_only_claimed and not isinstance(explicit_proxy_only, bool):
        invalid.append("proxy_only_market_features")
        explicit_proxy_only = None

    explicit = bool(
        quality_claimed
        or basis_claimed
        or route_cap_claimed
        or baseline_status_claimed
        or proxy_only_claimed
    )
    basis_values = tuple(basis.values())
    direct_values = tuple(
        value
        for value in basis_values
        if value and not any(term in value for term in _PROXY_BASIS_TERMS)
    )
    proxy_values = tuple(
        value
        for value in basis_values
        if value and any(term in value for term in _PROXY_BASIS_TERMS)
    )
    proxy_only = bool(
        explicit_proxy_only is True
        or basis_values and proxy_values and not direct_values
    )
    return {
        "explicit": explicit,
        "basis": basis,
        "route_cap": route_cap,
        "baseline_status": baseline_status,
        "proxy_only": proxy_only,
        "direct_feature_count": len(direct_values),
        "proxy_feature_count": len(proxy_values),
        "invalid_claims": tuple(dict.fromkeys(invalid)),
    }


def _market_quality_allows_actionable(market: Mapping[str, Any]) -> bool:
    quality = _market_quality_metadata(market)
    if not quality["explicit"]:
        return True
    if quality["invalid_claims"]:
        return False
    if quality["proxy_only"]:
        return False
    if quality["route_cap"] in {"dashboard_watch", "diagnostic"}:
        return False
    volume_basis = str(
        quality["basis"].get("volume_zscore_24h")
        or market.get("volume_zscore_basis")
        or ""
    ).casefold()
    if quality["baseline_status"] in _LIMITED_BASELINE_STATUSES and (
        not volume_basis or any(term in volume_basis for term in _PROXY_BASIS_TERMS)
    ):
        return False
    return True


def _quality_adjusted_urgency(
    urgency: float,
    *,
    market: Mapping[str, Any],
    spread_status: str,
) -> float:
    adjusted = float(urgency)
    quality = _market_quality_metadata(market)
    if spread_status in {SpreadStatus.UNAVAILABLE.value, SpreadStatus.STALE.value}:
        adjusted = min(adjusted, 55.0)
    if quality["explicit"] and (
        quality["invalid_claims"]
        or quality["proxy_only"]
        or quality["route_cap"] in {"dashboard_watch", "diagnostic"}
        or quality["baseline_status"] in _LIMITED_BASELINE_STATUSES
    ):
        adjusted = min(adjusted, 45.0)
    return round(_clamp(adjusted), 2)


def _apply_market_quality_score_caps(
    market: Mapping[str, Any],
    *,
    actionability: float,
    evidence_confidence: float,
    risk: float,
    action_components: dict[str, float],
    evidence_components: dict[str, float],
    risk_components: dict[str, float],
    penalties: tuple[str, ...],
    penalty_points: dict[str, float],
) -> tuple[float, float, float, tuple[str, ...]]:
    quality = _market_quality_metadata(market)
    if not quality["explicit"]:
        return actionability, evidence_confidence, risk, penalties
    labels = list(penalties)
    if quality["proxy_only"]:
        actionability = min(actionability, 64.0)
        evidence_confidence = min(evidence_confidence, 55.0)
        risk = max(risk, 55.0)
        action_components["market_data_basis_cap"] = 40.0
        evidence_components["market_data_quality"] = min(
            float(evidence_components.get("market_data_quality", 100.0)),
            45.0,
        )
        risk_components["proxy_market_data_risk"] = 70.0
        penalty_points["proxy_only_market_evidence"] = 16.0
        labels.append("proxy_only_market_evidence_dashboard_only")
    if quality["baseline_status"] in _LIMITED_BASELINE_STATUSES:
        evidence_confidence = min(evidence_confidence, 62.0)
        risk = max(risk, 48.0)
        penalty_points["temporal_baseline_not_warm"] = 10.0
        labels.append("temporal_market_baseline_not_warm")
    if quality["route_cap"] in {"dashboard_watch", "diagnostic"}:
        actionability = min(actionability, 64.0)
    return (
        round(_clamp(actionability), 2),
        round(_clamp(evidence_confidence), 2),
        round(_clamp(risk), 2),
        tuple(dict.fromkeys(labels)),
    )


def _market_quality_warnings(
    market: Mapping[str, Any],
    *,
    spread_status: str,
) -> tuple[str, ...]:
    quality = _market_quality_metadata(market)
    warnings: list[str] = []
    if quality["invalid_claims"]:
        warnings.append(
            "Explicit market-data-quality metadata is malformed; the idea is retained only as diagnostic research evidence."
        )
    if quality["proxy_only"]:
        warnings.append(
            "Market evidence is proxy-only; the idea is capped to dashboard review and cannot receive urgent/actionable routing."
        )
    if quality["baseline_status"] in _LIMITED_BASELINE_STATUSES:
        warnings.append(
            "The rolling temporal market baseline is not warm; cross-sectional context remains review-only."
        )
    if spread_status in {SpreadStatus.UNAVAILABLE.value, SpreadStatus.STALE.value}:
        warnings.append(
            "Spread or execution-quality evidence is unavailable; notification urgency is capped."
        )
    return tuple(warnings)


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _first_claim(*claims: tuple[Mapping[str, Any], str]) -> tuple[object, bool]:
    for owner, field in claims:
        if field in owner:
            return owner.get(field), True
    return None, False


def _typed_enum(value: object, allowed: frozenset[str]) -> str:
    if not isinstance(value, str):
        return ""
    normalized = value.strip().casefold()
    return normalized if normalized in allowed else ""


__all__: tuple[str, ...] = ()
