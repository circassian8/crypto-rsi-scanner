"""Pure, dependency-free inline SVG charts for the local operator dashboard.

The helpers in this module render presentation only.  They do not read
artifacts, call providers, write files, or infer missing evidence.  Callers pass
an already-bounded history and an explicit evidence state; the renderer applies
an additional output bound so a chart cannot make a dashboard page unbounded.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from itertools import islice
import math
from typing import Literal


ChartState = Literal["ready", "warming", "cold", "missing"]
ChartKind = Literal["line", "bar"]
ValueFormat = Literal["number", "price", "compact", "percent", "score"]

_VIEWBOX_WIDTH = 640.0
_VIEWBOX_HEIGHT = 180.0
_PLOT_LEFT = 76.0
_PLOT_RIGHT = 622.0
_PLOT_TOP = 32.0
_PLOT_BOTTOM = 142.0
_DEFAULT_MAX_POINTS = 48
_HARD_MAX_POINTS = 120
_HARD_ITERABLE_INPUT_LIMIT = 512


@dataclass(frozen=True, slots=True)
class ChartPoint:
    """One labeled chart observation.

    ``value=None`` represents an explicit gap.  Gaps are retained so a line is
    not drawn across missing observations.
    """

    label: str
    value: float | None


@dataclass(frozen=True, slots=True)
class _BoundedPoints:
    points: tuple[ChartPoint, ...]
    source_count: int
    input_capped: bool


def render_history_chart(
    history: Iterable[object],
    *,
    title: object,
    summary: object = "",
    value_key: str = "value",
    label_key: str = "label",
    value_format: ValueFormat = "number",
    kind: ChartKind = "line",
    state: ChartState | str = "ready",
    state_detail: object = "",
    proxy: bool = False,
    max_points: int = _DEFAULT_MAX_POINTS,
) -> str:
    """Render a bounded, responsive inline SVG chart.

    History items may be :class:`ChartPoint` objects, ``(label, value)`` pairs,
    mappings addressed by ``label_key`` / ``value_key``, or bare numbers.  The
    first and last source observations are preserved during downsampling.
    Non-finite values become explicit gaps rather than SVG coordinates.

    ``percent`` inputs are expected to be normalized percent-points already;
    this presentation helper deliberately performs no unit reinterpretation.
    """

    safe_title = _plain_text(title, fallback="Untitled history", limit=96)
    safe_summary = _plain_text(summary, limit=240)
    safe_detail = _plain_text(state_detail, limit=120)
    bounded = _bounded_points(
        history,
        value_key=value_key,
        label_key=label_key,
        max_points=max_points,
    )
    usable = [point for point in bounded.points if point.value is not None]
    normalized_state = _normalized_state(state)
    if not usable:
        normalized_state = "missing"
    elif len(usable) == 1 and normalized_state in {"ready", "warming"}:
        normalized_state = "cold"

    accessible_summary = _chart_summary(
        supplied=safe_summary,
        state=normalized_state,
        state_detail=safe_detail,
        usable_count=len(usable),
        plotted_count=len(bounded.points),
        source_count=bounded.source_count,
        input_capped=bounded.input_capped,
        proxy=proxy,
    )
    heading = _svg_text(safe_title)
    description = _svg_text(accessible_summary)
    state_label = _STATE_LABELS[normalized_state]

    prefix = (
        '<svg class="radar-inline-chart" viewBox="0 0 640 180" '
        'width="100%" preserveAspectRatio="xMidYMid meet" role="img" '
        'style="display:block;width:100%;height:auto" '
        f'aria-label="{_svg_attr(safe_title)}" '
        f'aria-description="{_svg_attr(accessible_summary)}">'
        f"<title>{heading}</title><desc>{description}</desc>"
        '<rect class="chart-background" x="0" y="0" width="640" height="180" '
        'rx="10" fill="var(--panel,#151d31)"></rect>'
    )
    status = _status_markup(
        state_label,
        proxy=proxy,
        input_capped=bounded.input_capped or bounded.source_count > len(bounded.points),
    )

    if normalized_state == "missing":
        detail = safe_detail or "No usable observations were supplied"
        return (
            prefix
            + status
            + '<text class="chart-empty" x="320" y="88" text-anchor="middle" '
            'fill="var(--muted,#a9b6d3)" font-size="15">History unavailable</text>'
            + '<text class="chart-empty-detail" x="320" y="111" text-anchor="middle" '
            'fill="var(--muted,#a9b6d3)" font-size="12">'
            + _svg_text(detail)
            + "</text>"
            + _axis_edge_labels(None, None)
            + "</svg>"
        )

    low, high = _value_extent(usable, value_format=value_format, kind=kind)
    markup = [prefix, status, _grid_markup(low, high, value_format=value_format)]
    if kind == "bar":
        markup.append(
            _bar_markup(
                bounded.points,
                low=low,
                high=high,
            )
        )
    else:
        markup.append(
            _line_markup(
                bounded.points,
                low=low,
                high=high,
            )
        )

    first = usable[0]
    last = usable[-1]
    if len(usable) == 1:
        only_label = _trim_label(first.label, fallback="Only observation")
        markup.append(
            '<text class="chart-only-label" x="320" y="166" text-anchor="middle" '
            'fill="var(--muted,#a9b6d3)" font-size="11">'
            f"{_svg_text(only_label)} · {_svg_text(_format_value(first.value, value_format))}"
            "</text>"
        )
    else:
        markup.append(
            _axis_edge_labels(
                f"{_trim_label(first.label, fallback='Start')} · {_format_value(first.value, value_format)}",
                f"{_trim_label(last.label, fallback='Latest')} · {_format_value(last.value, value_format)}",
            )
        )
    markup.append("</svg>")
    return "".join(markup)


def render_price_chart(
    history: Iterable[object],
    *,
    title: object = "Price history",
    summary: object = "",
    value_key: str = "price",
    label_key: str = "observed_at",
    state: ChartState | str = "ready",
    state_detail: object = "",
    proxy: bool = False,
    max_points: int = _DEFAULT_MAX_POINTS,
) -> str:
    """Render a price history without inventing or converting price evidence."""

    return render_history_chart(
        history,
        title=title,
        summary=summary,
        value_key=value_key,
        label_key=label_key,
        value_format="price",
        state=state,
        state_detail=state_detail,
        proxy=proxy,
        max_points=max_points,
    )


def render_activity_chart(
    history: Iterable[object],
    *,
    activity: Literal["volume", "turnover"] = "volume",
    title: object | None = None,
    summary: object = "",
    value_key: str | None = None,
    label_key: str = "observed_at",
    state: ChartState | str = "ready",
    state_detail: object = "",
    proxy: bool = False,
    value_format: ValueFormat = "compact",
    max_points: int = _DEFAULT_MAX_POINTS,
) -> str:
    """Render normalized USD volume or turnover history as bounded bars."""

    normalized_activity = activity if activity in {"volume", "turnover"} else "volume"
    return render_history_chart(
        history,
        title=title or f"{normalized_activity.title()} history",
        summary=summary,
        value_key=value_key or f"{normalized_activity}_24h_usd",
        label_key=label_key,
        value_format=value_format,
        kind="bar",
        state=state,
        state_detail=state_detail,
        proxy=proxy,
        max_points=max_points,
    )


def render_relative_chart(
    history: Iterable[object],
    *,
    benchmark: Literal["BTC", "ETH"] | str = "BTC",
    title: object | None = None,
    summary: object = "",
    value_key: str | None = None,
    label_key: str = "observed_at",
    state: ChartState | str = "ready",
    state_detail: object = "",
    proxy: bool = False,
    max_points: int = _DEFAULT_MAX_POINTS,
) -> str:
    """Render percent-point relative performance versus BTC or ETH."""

    normalized_benchmark = str(benchmark).upper()
    if normalized_benchmark not in {"BTC", "ETH"}:
        normalized_benchmark = "BTC"
    return render_history_chart(
        history,
        title=title or f"Relative performance vs {normalized_benchmark}",
        summary=summary,
        value_key=value_key or f"relative_return_vs_{normalized_benchmark.lower()}_4h",
        label_key=label_key,
        value_format="percent",
        state=state,
        state_detail=state_detail,
        proxy=proxy,
        max_points=max_points,
    )


def render_progress_chart(
    history: Iterable[object],
    *,
    progress: Literal["score", "baseline"] = "score",
    title: object | None = None,
    summary: object = "",
    value_key: str | None = None,
    label_key: str = "observed_at",
    state: ChartState | str = "ready",
    state_detail: object = "",
    proxy: bool = False,
    max_points: int = _DEFAULT_MAX_POINTS,
) -> str:
    """Render actionability/quality score or baseline-observation progression."""

    normalized_progress = progress if progress in {"score", "baseline"} else "score"
    defaults: dict[str, tuple[str, str, ValueFormat]] = {
        "score": ("Score progression", "actionability_score", "score"),
        "baseline": ("Baseline progression", "baseline_samples", "number"),
    }
    default_title, default_key, value_format = defaults[normalized_progress]
    return render_history_chart(
        history,
        title=title or default_title,
        summary=summary,
        value_key=value_key or default_key,
        label_key=label_key,
        value_format=value_format,
        state=state,
        state_detail=state_detail,
        proxy=proxy,
        max_points=max_points,
    )


_STATE_LABELS: dict[ChartState, str] = {
    "ready": "Current history",
    "warming": "Warming baseline",
    "cold": "Cold baseline",
    "missing": "History unavailable",
}


def _normalized_state(value: object) -> ChartState:
    token = str(value or "").strip().lower().replace("-", "_")
    aliases: dict[str, ChartState] = {
        "ready": "ready",
        "current": "ready",
        "warm": "ready",
        "warming": "warming",
        "partial": "warming",
        "cold": "cold",
        "cold_start": "cold",
        "missing": "missing",
        "unavailable": "missing",
        "not_configured": "missing",
    }
    return aliases.get(token, "missing")


def _bounded_points(
    history: Iterable[object],
    *,
    value_key: str,
    label_key: str,
    max_points: int,
) -> _BoundedPoints:
    limit = min(_HARD_MAX_POINTS, max(2, int(max_points)))
    input_capped = False
    if isinstance(history, Sequence) and not isinstance(history, (str, bytes, bytearray)):
        source_count = len(history)
        selected = _even_indices(source_count, min(source_count, limit))
        raw_points = [history[index] for index in selected]
    else:
        raw = list(islice(history, _HARD_ITERABLE_INPUT_LIMIT + 1))
        source_count = len(raw)
        if len(raw) > _HARD_ITERABLE_INPUT_LIMIT:
            raw = raw[:_HARD_ITERABLE_INPUT_LIMIT]
            input_capped = True
        retained_count = len(raw)
        selected = _even_indices(retained_count, min(retained_count, limit))
        raw_points = [raw[index] for index in selected]
    return _BoundedPoints(
        points=tuple(
            _coerce_point(item, index=index, value_key=value_key, label_key=label_key)
            for index, item in enumerate(raw_points)
        ),
        source_count=source_count,
        input_capped=input_capped,
    )


def _even_indices(source_count: int, target_count: int) -> tuple[int, ...]:
    if source_count <= 0 or target_count <= 0:
        return ()
    if target_count >= source_count:
        return tuple(range(source_count))
    if target_count == 1:
        return (source_count - 1,)
    return tuple(
        round(index * (source_count - 1) / (target_count - 1))
        for index in range(target_count)
    )


def _coerce_point(item: object, *, index: int, value_key: str, label_key: str) -> ChartPoint:
    if isinstance(item, ChartPoint):
        return ChartPoint(_plain_text(item.label, limit=64), _finite_number(item.value))
    if isinstance(item, Mapping):
        label = item.get(label_key)
        value = item.get(value_key)
    elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)) and len(item) >= 2:
        label, value = item[0], item[1]
    else:
        label, value = f"Observation {index + 1}", item
    return ChartPoint(_plain_text(label, limit=64), _finite_number(value))


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _value_extent(
    usable: Sequence[ChartPoint],
    *,
    value_format: ValueFormat,
    kind: ChartKind,
) -> tuple[float, float]:
    values = [point.value for point in usable if point.value is not None]
    nonnegative_bars = kind == "bar" and min(values) >= 0.0
    low = min(values)
    high = max(values)
    if value_format == "score":
        low = min(0.0, low)
        high = max(100.0, high)
    elif value_format == "percent" or kind == "bar":
        low = min(0.0, low)
        high = max(0.0, high)
    if math.isclose(low, high):
        padding = max(abs(low) * 0.05, 1.0)
    else:
        padding = (high - low) * 0.06
    if value_format != "score":
        if not nonnegative_bars:
            low -= padding
        high += padding
    return low, high


def _x_for(index: int, count: int) -> float:
    if count <= 1:
        return (_PLOT_LEFT + _PLOT_RIGHT) / 2
    return _PLOT_LEFT + (_PLOT_RIGHT - _PLOT_LEFT) * index / (count - 1)


def _y_for(value: float, *, low: float, high: float) -> float:
    if math.isclose(low, high):
        return (_PLOT_TOP + _PLOT_BOTTOM) / 2
    return _PLOT_TOP + (_PLOT_BOTTOM - _PLOT_TOP) * (high - value) / (high - low)


def _line_markup(points: Sequence[ChartPoint], *, low: float, high: float) -> str:
    segments: list[list[str]] = []
    current: list[str] = []
    singletons: list[str] = []
    for index, point in enumerate(points):
        if point.value is None:
            if current:
                segments.append(current)
                current = []
            continue
        coordinate = f"{_x_for(index, len(points)):.1f},{_y_for(point.value, low=low, high=high):.1f}"
        current.append(coordinate)
    if current:
        segments.append(current)
    markup: list[str] = []
    for segment in segments:
        if len(segment) == 1:
            singletons.append(segment[0])
            continue
        markup.append(
            '<polyline class="chart-line" points="'
            + " ".join(segment)
            + '" fill="none" stroke="var(--accent,#7dd3fc)" stroke-width="2.5" '
            'stroke-linecap="round" stroke-linejoin="round" '
            'vector-effect="non-scaling-stroke"></polyline>'
        )
    for coordinate in singletons:
        x, y = coordinate.split(",", 1)
        markup.append(
            f'<circle class="chart-point" cx="{x}" cy="{y}" r="3.5" '
            'fill="var(--accent,#7dd3fc)"></circle>'
        )
    return "".join(markup)


def _bar_markup(points: Sequence[ChartPoint], *, low: float, high: float) -> str:
    count = max(1, len(points))
    available_width = _PLOT_RIGHT - _PLOT_LEFT
    bar_width = max(2.0, min(18.0, available_width / count * 0.64))
    baseline_value = 0.0 if low <= 0.0 <= high else low
    baseline_y = _y_for(baseline_value, low=low, high=high)
    markup: list[str] = []
    for index, point in enumerate(points):
        if point.value is None:
            continue
        value_y = _y_for(point.value, low=low, high=high)
        y = min(value_y, baseline_y)
        height = max(1.0, abs(value_y - baseline_y))
        markup.append(
            f'<rect class="chart-bar" x="{_x_for(index, count) - bar_width / 2:.1f}" '
            f'y="{y:.1f}" width="{bar_width:.1f}" height="{height:.1f}" '
            'rx="1.5" fill="var(--accent,#7dd3fc)" opacity="0.82"></rect>'
        )
    return "".join(markup)


def _grid_markup(low: float, high: float, *, value_format: ValueFormat) -> str:
    middle = (low + high) / 2
    lines: list[str] = []
    for y in (_PLOT_TOP, (_PLOT_TOP + _PLOT_BOTTOM) / 2, _PLOT_BOTTOM):
        lines.append(
            f'<line class="chart-grid" x1="{_PLOT_LEFT:.0f}" y1="{y:.1f}" '
            f'x2="{_PLOT_RIGHT:.0f}" y2="{y:.1f}" '
            'stroke="var(--line,#2d3956)" stroke-width="1" '
            'vector-effect="non-scaling-stroke"></line>'
        )
    if low < 0.0 < high:
        zero_y = _y_for(0.0, low=low, high=high)
        lines.append(
            f'<line class="chart-zero" x1="{_PLOT_LEFT:.0f}" y1="{zero_y:.1f}" '
            f'x2="{_PLOT_RIGHT:.0f}" y2="{zero_y:.1f}" '
            'stroke="var(--muted,#a9b6d3)" stroke-width="1.5" stroke-dasharray="4 4" '
            'vector-effect="non-scaling-stroke"></line>'
        )
    labels = ((high, _PLOT_TOP + 4), (middle, (_PLOT_TOP + _PLOT_BOTTOM) / 2 + 4), (low, _PLOT_BOTTOM + 4))
    for value, y in labels:
        lines.append(
            f'<text class="chart-y-label" x="69" y="{y:.1f}" text-anchor="end" '
            'fill="var(--muted,#a9b6d3)" font-size="10">'
            + _svg_text(_format_value(value, value_format))
            + "</text>"
        )
    return "".join(lines)


def _status_markup(state_label: str, *, proxy: bool, input_capped: bool) -> str:
    parts = [state_label]
    if proxy:
        parts.append("Proxy evidence")
    if input_capped:
        parts.append("Bounded view")
    return (
        '<text class="chart-status" x="76" y="19" '
        'fill="var(--muted,#a9b6d3)" font-size="11">'
        + _svg_text(" · ".join(parts))
        + "</text>"
    )


def _axis_edge_labels(start: str | None, end: str | None) -> str:
    start_text = start or "Start · unavailable"
    end_text = end or "Latest · unavailable"
    return (
        '<text class="chart-x-label chart-x-start" x="76" y="166" text-anchor="start" '
        'fill="var(--muted,#a9b6d3)" font-size="11">'
        + _svg_text(start_text)
        + "</text>"
        '<text class="chart-x-label chart-x-end" x="622" y="166" text-anchor="end" '
        'fill="var(--muted,#a9b6d3)" font-size="11">'
        + _svg_text(end_text)
        + "</text>"
    )


def _chart_summary(
    *,
    supplied: str,
    state: ChartState,
    state_detail: str,
    usable_count: int,
    plotted_count: int,
    source_count: int,
    input_capped: bool,
    proxy: bool,
) -> str:
    parts = [supplied] if supplied else []
    parts.append(f"Evidence state: {_STATE_LABELS[state].lower()}.")
    if state_detail:
        parts.append(f"{state_detail}.")
    if input_capped:
        parts.append(
            f"{usable_count} usable observations; {plotted_count} plotted after inspecting "
            f"at least {source_count} supplied."
        )
    else:
        parts.append(f"{usable_count} usable observations; {plotted_count} plotted from {source_count} supplied.")
    if proxy:
        parts.append("This is explicitly proxy-derived evidence.")
    if input_capped:
        parts.append("The generic iterable input was capped before plotting.")
    elif source_count > plotted_count:
        parts.append("The visual is an evenly downsampled bounded view preserving its first and last observations.")
    return " ".join(part.strip() for part in parts if part.strip())


def _format_value(value: float | None, value_format: ValueFormat) -> str:
    if value is None:
        return "Unavailable"
    if value_format == "price":
        if abs(value) >= 1_000:
            return f"${_compact_number(value)}"
        if abs(value) >= 1:
            return f"${value:,.2f}"
        return f"${value:,.4f}"
    if value_format == "compact":
        return _compact_number(value)
    if value_format == "percent":
        return f"{value:+.1f}%"
    if value_format == "score":
        return f"{value:.0f}/100"
    if abs(value) >= 1_000:
        return _compact_number(value)
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _compact_number(value: float) -> str:
    for threshold, suffix in ((1_000_000_000_000, "T"), (1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(value) >= threshold:
            return f"{value / threshold:.1f}{suffix}"
    return f"{value:,.1f}".rstrip("0").rstrip(".")


def _trim_label(value: object, *, fallback: str) -> str:
    raw = str(value or "").strip()
    if raw:
        normalized = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            utc = parsed.astimezone(timezone.utc)
            return f"{utc:%b} {utc.day} {utc:%H:%M}Z"
    return _plain_text(value, fallback=fallback, limit=14)


def _plain_text(value: object, *, fallback: str = "", limit: int) -> str:
    if value is None:
        return fallback
    text = " ".join(str(value).split())
    text = "".join(character for character in text if ord(character) >= 32)
    if not text:
        return fallback
    if len(text) > limit:
        return text[: max(1, limit - 1)].rstrip() + "…"
    return text


def _svg_text(value: object) -> str:
    return escape(str(value), quote=False)


def _svg_attr(value: object) -> str:
    return escape(str(value), quote=True)


__all__ = [
    "ChartPoint",
    "render_activity_chart",
    "render_history_chart",
    "render_price_chart",
    "render_progress_chart",
    "render_relative_chart",
]
