"""Shared presentation helpers for dashboard system pages."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from .components import escape_html


def render_page_intro(title: str, description: str, eyebrow: str) -> str:
    """Render the common introductory block for an operator system page."""

    return (
        '<section class="page-intro"><div>'
        f'<p class="eyebrow">{escape_html(eyebrow)}</p>'
        f"<h2>{escape_html(title)}</h2><p>{escape_html(description)}</p>"
        "</div></section>"
    )


def render_metric_grid(values: tuple[tuple[str, str, str], ...]) -> str:
    """Render operator metrics with semantic tone classes."""

    return '<div class="metric-grid">' + "".join(
        f'<article class="metric-card tone-{escape_html(tone)}">'
        f"<span>{escape_html(label)}</span><strong>{escape_html(value)}</strong>"
        "</article>"
        for label, value, tone in values
    ) + "</div>"


def render_panel(title: str, body: str, *, eyebrow: str) -> str:
    """Render the common titled panel used by system pages."""

    return (
        '<section class="panel"><div class="section-heading"><div>'
        f'<p class="eyebrow">{escape_html(eyebrow)}</p>'
        f"<h2>{escape_html(title)}</h2></div></div>{body}</section>"
    )


def as_mapping(value: object) -> Mapping[str, Any]:
    """Return mapping values unchanged and fail closed for other inputs."""

    return value if isinstance(value, Mapping) else {}


def as_number(value: object) -> float | None:
    """Return a finite numeric representation without treating booleans as counts."""

    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def display_count(value: object) -> str:
    """Render a non-negative integral count, defaulting invalid values to zero."""

    number = as_number(value)
    return str(max(0, int(number))) if number is not None else "0"


def summarize_market_quality(
    rows: Iterable[Mapping[str, Any]],
    generation: Mapping[str, Any],
) -> dict[str, int]:
    """Summarize baseline maturity and verified spread coverage."""

    del generation  # Reserved for generation-level quality evidence.
    counts = Counter(_baseline_status(row) for row in rows)
    spread = sum(1 for row in rows if _spread_verified(row))
    return {
        "warm": counts.get("warm", 0),
        "warming": counts.get("warming", 0),
        "cold": counts.get("cold", 0),
        "unknown": counts.get("unknown", 0),
        "spread": spread,
    }


def _baseline_status(row: Mapping[str, Any]) -> str:
    quality = as_mapping(row.get("market_data_quality") or row.get("data_quality"))
    return str(
        row.get("temporal_baseline_status")
        or quality.get("baseline_status")
        or "unknown"
    ).strip().casefold()


def _spread_verified(row: Mapping[str, Any]) -> bool:
    quality = as_mapping(row.get("market_data_quality") or row.get("data_quality"))
    return (
        quality.get("spread_available") is True
        or str(row.get("spread_status") or quality.get("spread_basis") or "").casefold()
        in {
            "available",
            "provider_observed",
            "verified",
            "verified_acceptable",
            "verified_good",
        }
    )


__all__ = (
    "as_mapping",
    "as_number",
    "display_count",
    "render_metric_grid",
    "render_page_intro",
    "render_panel",
    "summarize_market_quality",
)
