"""Pure measured-history rendering for Decision Radar idea details."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .charts import render_activity_chart, render_price_chart, render_relative_chart
from .components import escape_html
from .presentation import humanize_enum, present_turnover_series
from .view_data import finite_number


def render_market_history_charts(
    history: tuple[Mapping[str, Any], ...],
    *,
    chart_state: str,
    baseline_state: str,
    turnover_basis: object = None,
) -> str:
    """Render measured series and consolidate unavailable chart evidence."""

    turnover = present_turnover_series(history, metric_basis=turnover_basis)
    chart_specs = (
        (
            "Price history",
            "price",
            lambda: render_price_chart(
                history,
                state=chart_state,
                state_detail="Exact-generation bounded history",
            ),
        ),
        (
            "Volume history",
            "volume_24h",
            lambda: render_activity_chart(
                history,
                activity="volume",
                value_key="volume_24h",
                state=chart_state,
                proxy=False,
            ),
        ),
        (
            turnover.title,
            "turnover_24h",
            lambda: render_activity_chart(
                turnover.rows,
                activity="turnover",
                title=turnover.title,
                summary=turnover.summary,
                value_key=turnover.value_key,
                state=chart_state,
                state_detail=turnover.state_detail,
                value_format="percent",
                proxy=turnover.proxy,
            ),
        ),
        (
            "Relative performance vs BTC",
            "relative_return_vs_btc_4h",
            lambda: render_relative_chart(
                history,
                benchmark="BTC",
                state=chart_state,
                state_detail=(
                    "Relative history may be unavailable until baseline warms"
                ),
            ),
        ),
    )
    rendered: list[str] = []
    unavailable: list[str] = []
    for label, value_key, renderer in chart_specs:
        if any(finite_number(item.get(value_key)) is not None for item in history):
            rendered.append(renderer())
        else:
            unavailable.append(label)

    unavailable_summary = _unavailable_history_summary(
        unavailable,
        baseline_state=baseline_state,
        partial=bool(rendered),
    )
    if not rendered:
        return unavailable_summary
    return '<div class="chart-grid">' + "".join(rendered) + unavailable_summary + "</div>"


def _unavailable_history_summary(
    labels: Iterable[str],
    *,
    baseline_state: str,
    partial: bool,
) -> str:
    materialized = tuple(labels)
    if not materialized:
        return ""
    count = len(materialized)
    state_label = humanize_enum(baseline_state)
    classes = (
        "history-empty-state history-empty-state--partial"
        if partial
        else "history-empty-state"
    )
    items = "".join(f"<li>{escape_html(label)}</li>" for label in materialized)
    return (
        f'<div class="{classes}" role="status" '
        f'aria-label="{count} market history series unavailable">'
        '<div><p class="eyebrow">Measured context gap</p><h3>History unavailable</h3>'
        '<p>No usable exact-generation observations are attached for the listed series. '
        f'Baseline status remains {escape_html(state_label)}; no values are inferred.</p></div>'
        f'<ul class="history-empty-series" aria-label="Unavailable market history series">{items}</ul>'
        "</div>"
    )


__all__ = ("render_market_history_charts",)
