"""Small escaped helpers retained by secondary dashboard routes."""

from __future__ import annotations

import html
from collections.abc import Iterable, Mapping
from typing import Any

from .components import safe_external_href


def escape_html(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def table(
    headers: Iterable[str],
    rows: Iterable[Iterable[str]],
    *,
    empty: str = "No rows.",
) -> str:
    materialized = [tuple(row) for row in rows]
    if not materialized:
        return f'<p class="muted">{escape_html(empty)}</p>'
    head = "".join(f"<th>{escape_html(value)}</th>" for value in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>"
        for row in materialized
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def definition_list(items: Iterable[tuple[str, object]]) -> str:
    return "<dl>" + "".join(
        f"<dt>{escape_html(key)}</dt><dd>{escape_html(value)}</dd>"
        for key, value in items
    ) + "</dl>"


def text_list(title: str, items: Iterable[str]) -> str:
    materialized = tuple(str(value) for value in items if str(value).strip())
    if not materialized:
        return f'<h3>{escape_html(title)}</h3><p class="muted">None recorded.</p>'
    return f"<h3>{escape_html(title)}</h3><ul>" + "".join(
        f"<li>{escape_html(value)}</li>" for value in materialized
    ) + "</ul>"


def score_components(title: str, value: object) -> str:
    if not isinstance(value, Mapping) or not value:
        return (
            f'<h3>{escape_html(title)}</h3>'
            '<p class="muted">No component detail recorded.</p>'
        )
    rows = [
        (escape_html(key), escape_html(component))
        for key, component in sorted(value.items())
        if not isinstance(component, (Mapping, list, tuple, set))
    ]
    return f"<h3>{escape_html(title)}</h3>" + table(("Component", "Value"), rows)


def values(row: Mapping[str, Any], *fields: str) -> tuple[str, ...]:
    output: list[str] = []
    for field in fields:
        value = row.get(field)
        if isinstance(value, str):
            if value.strip():
                output.append(value.strip())
        elif isinstance(value, Iterable) and not isinstance(value, (bytes, Mapping)):
            output.extend(str(item).strip() for item in value if str(item).strip())
    return tuple(dict.fromkeys(output))


def asset_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("symbol") or row.get("validated_symbol") or "").strip().upper(),
        str(row.get("coin_id") or row.get("validated_coin_id") or "").strip().casefold(),
    )


def source_link(row: Mapping[str, Any]) -> str:
    raw = str(
        row.get("source_url") or row.get("latest_source_url") or row.get("url") or ""
    ).strip()
    if not raw:
        return ""
    safe_url = safe_external_href(raw)
    if safe_url is None:
        return '<span class="muted">unsafe or unavailable source URL</span>'
    label = str(row.get("source") or row.get("latest_source") or "Source")
    return (
        f'<a href="{escape_html(safe_url)}" rel="noreferrer" target="_blank">'
        f"{escape_html(label)}</a>"
    )


def score(value: object) -> str:
    try:
        return f"{float(value):.0f}/100"
    except (TypeError, ValueError):
        return "n/a"


__all__ = (
    "asset_key",
    "definition_list",
    "escape_html",
    "score",
    "score_components",
    "source_link",
    "table",
    "text_list",
    "values",
)
