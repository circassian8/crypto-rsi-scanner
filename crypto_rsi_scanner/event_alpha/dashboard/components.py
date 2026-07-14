"""Escaped, accessible HTML primitives for server-rendered dashboard pages."""

from __future__ import annotations

import html
from collections.abc import Iterable, Mapping, Sequence
from urllib.parse import urlsplit

from .presentation import (
    TimePresentation,
    UNAVAILABLE,
    format_score,
    humanize_enum,
    score_band,
    semantic_status,
)


_TONES = {"positive", "info", "warning", "danger", "neutral", "muted"}


class HtmlFragment(str):
    """HTML produced by this module and therefore safe to compose unescaped."""


def escape_html(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def link(
    label: object,
    href: object,
    *,
    aria_label: object | None = None,
    css_class: str = "",
) -> HtmlFragment:
    safe_href = _safe_href(href)
    label_html = _content(label)
    aria = (
        f' aria-label="{escape_html(aria_label)}"'
        if aria_label not in (None, "")
        else ""
    )
    class_attr = f' class="{_safe_classes(css_class)}"' if _safe_classes(css_class) else ""
    return HtmlFragment(
        f'<a href="{escape_html(safe_href)}"{class_attr}{aria}>{label_html}</a>'
    )


def badge(
    value: object,
    *,
    tone: str | None = None,
    label: object | None = None,
    title: object | None = None,
    icon: str | None = None,
) -> HtmlFragment:
    status = semantic_status(value)
    resolved_tone = _tone(tone or status.tone)
    resolved_label = status.label if label is None else str(label)
    title_attr = (
        f' title="{escape_html(title)}"' if title not in (None, "") else ""
    )
    icon_html = ""
    if icon:
        icon_token = _safe_classes(icon).split(" ")[0] if _safe_classes(icon) else "status"
        symbols = {"shield": "✓", "data": "◆", "clock": "◷", "warning": "!"}
        icon_html = (
            f'<span class="status-badge__icon status-badge__icon--{icon_token}" '
            f'aria-hidden="true">{symbols.get(icon_token, "●")}</span>'
        )
    return HtmlFragment(
        f'<span class="status-badge status-badge--{resolved_tone}"{title_attr}>'
        f"{icon_html}{escape_html(resolved_label)}</span>"
    )


def chips(
    values: Iterable[object] | object,
    *,
    aria_label: object = "Tags",
    tone: str = "neutral",
    empty: object = UNAVAILABLE,
) -> HtmlFragment:
    if isinstance(values, (str, bytes)) or values is None:
        materialized = [values] if values not in (None, "") else []
    else:
        try:
            materialized = [value for value in values if value not in (None, "")]
        except TypeError:
            materialized = [values]
    if not materialized:
        return HtmlFragment(
            f'<span class="unavailable">{escape_html(empty)}</span>'
        )
    items = "".join(
        f'<li><span class="chip chip--{_tone(tone)}">{escape_html(humanize_enum(value))}</span></li>'
        for value in materialized
    )
    return HtmlFragment(
        f'<ul class="chip-list" aria-label="{escape_html(aria_label)}">{items}</ul>'
    )


def score(
    value: object,
    *,
    label: object = "Score",
    dimension: str = "quality",
) -> HtmlFragment:
    formatted = format_score(value)
    band = score_band(value, dimension=dimension)
    label_text = str(label)
    if formatted == UNAVAILABLE:
        aria = f"{label_text}: {UNAVAILABLE}"
        value_html = f'<span class="score-value">{UNAVAILABLE}</span>'
    else:
        aria = f"{label_text}: {formatted} out of 100, {band.label}"
        value_html = (
            f'<span class="score-value">{escape_html(formatted)}</span>'
            '<span class="score-denominator" aria-hidden="true">/100</span>'
        )
    return HtmlFragment(
        f'<span class="score score--{_tone(band.tone)}" role="img" '
        f'aria-label="{escape_html(aria)}">{value_html}'
        f'<span class="score-band">{escape_html(band.label)}</span></span>'
    )


def time_element(
    value: TimePresentation,
    *,
    primary: str = "combined",
    css_class: str = "",
) -> HtmlFragment:
    if not value.available:
        return HtmlFragment(f'<span class="unavailable">{UNAVAILABLE}</span>')
    labels = {
        "combined": value.primary_label,
        "local": value.local_label,
        "relative": value.relative_label,
        "utc": value.utc_label,
    }
    if primary not in labels:
        raise ValueError(f"unsupported time presentation: {primary!r}")
    classes = " ".join(
        part for part in ("timestamp", _safe_classes(css_class)) if part
    )
    return HtmlFragment(
        f'<time class="{classes}" datetime="{escape_html(value.iso_utc)}" '
        f'title="{escape_html(value.utc_label)}">{escape_html(labels[primary])}</time>'
    )


def data_table(
    headers: Sequence[object],
    rows: Iterable[Sequence[object] | Mapping[object, object]],
    *,
    caption: object | None = None,
    label: object | None = None,
    empty: object = "No rows to show.",
    first_column_header: bool = True,
    compact: bool = False,
) -> HtmlFragment:
    """Render an escaped table with a contained desktop scroll/mobile-card view."""

    header_values = tuple(str(header) for header in headers)
    if not header_values:
        raise ValueError("data_table requires at least one header")
    materialized: list[tuple[object, ...]] = []
    for row in rows:
        if isinstance(row, Mapping):
            values = tuple(row.get(header) for header in headers)
        else:
            values = tuple(row)
        if len(values) != len(header_values):
            raise ValueError("data_table row width does not match headers")
        materialized.append(values)
    if not materialized:
        return empty_state("Nothing here yet", empty)

    table_label = label if label not in (None, "") else caption or "Data table"
    head = "".join(
        f'<th scope="col">{escape_html(header)}</th>' for header in header_values
    )
    body_rows: list[str] = []
    for row in materialized:
        cells: list[str] = []
        for index, value in enumerate(row):
            tag = "th" if first_column_header and index == 0 else "td"
            scope = ' scope="row"' if tag == "th" else ""
            cells.append(
                f'<{tag}{scope} data-label="{escape_html(header_values[index])}">'
                f"{_content(value)}</{tag}>"
            )
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    caption_html = (
        f"<caption>{escape_html(caption)}</caption>"
        if caption not in (None, "")
        else ""
    )
    compact_class = " data-table--compact" if compact else ""
    return HtmlFragment(
        f'<div class="table-scroll" role="region" tabindex="0" '
        f'aria-label="{escape_html(table_label)}">'
        f'<table class="data-table mobile-cards{compact_class}">{caption_html}'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"
        "</div>"
    )


def empty_state(
    title: object,
    message: object,
    *,
    action_label: object | None = None,
    action_href: object | None = None,
) -> HtmlFragment:
    action = ""
    if action_label not in (None, "") and action_href not in (None, ""):
        action = f'<p class="empty-state__action">{link(action_label, action_href)}</p>'
    return HtmlFragment(
        '<div class="empty-state" role="status">'
        f'<p class="empty-state__title">{escape_html(title)}</p>'
        f'<p class="empty-state__message">{escape_html(message)}</p>{action}</div>'
    )


def disclosure(
    label: object,
    body: object,
    *,
    summary: object | None = None,
    open: bool = False,
    css_class: str = "",
) -> HtmlFragment:
    open_attr = " open" if open else ""
    classes = " ".join(
        part for part in ("disclosure", _safe_classes(css_class)) if part
    )
    secondary = (
        f'<span class="disclosure__summary">{escape_html(summary)}</span>'
        if summary not in (None, "")
        else ""
    )
    return HtmlFragment(
        f'<details class="{classes}"{open_attr}>'
        f"<summary><span>{escape_html(label)}</span>{secondary}</summary>"
        f'<div class="disclosure__body">{_content(body)}</div></details>'
    )


def definition_list(
    items: Iterable[tuple[object, object]],
    *,
    css_class: str = "",
) -> HtmlFragment:
    pairs = "".join(
        f"<dt>{escape_html(term)}</dt><dd>{_content(description)}</dd>"
        for term, description in items
    )
    classes = " ".join(
        part for part in ("definition-list", _safe_classes(css_class)) if part
    )
    return HtmlFragment(f'<dl class="{classes}">{pairs}</dl>')


def section(
    title: object,
    body: object,
    *,
    level: int = 2,
    css_class: str = "",
    eyebrow: object | None = None,
) -> HtmlFragment:
    if level not in {2, 3, 4}:
        raise ValueError("section heading level must be 2, 3, or 4")
    classes = " ".join(
        part for part in ("panel", _safe_classes(css_class)) if part
    )
    eyebrow_html = (
        f'<p class="eyebrow">{escape_html(eyebrow)}</p>'
        if eyebrow not in (None, "")
        else ""
    )
    return HtmlFragment(
        f'<section class="{classes}">{eyebrow_html}'
        f"<h{level}>{escape_html(title)}</h{level}>{_content(body)}</section>"
    )


def _content(value: object) -> str:
    if isinstance(value, HtmlFragment):
        return str(value)
    return escape_html(value)


def _tone(value: object) -> str:
    token = str(value or "neutral").strip().casefold()
    token = {"success": "positive", "fixture": "warning"}.get(token, token)
    return token if token in _TONES else "neutral"


def _safe_classes(value: str) -> str:
    return " ".join(
        token
        for token in str(value or "").split()
        if token.replace("-", "").replace("_", "").isalnum()
    )


def _safe_href(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "#"
    if raw.startswith(("/", "#", "?")):
        return raw
    return safe_external_href(raw) or "#"


def safe_external_href(value: object) -> str | None:
    """Return a credential-free absolute HTTP(S) URL or ``None``."""

    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = urlsplit(raw)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return raw


__all__ = (
    "HtmlFragment",
    "badge",
    "chips",
    "data_table",
    "definition_list",
    "disclosure",
    "empty_state",
    "escape_html",
    "link",
    "safe_external_href",
    "score",
    "section",
    "time_element",
)
