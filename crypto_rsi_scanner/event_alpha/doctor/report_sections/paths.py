"""Path hygiene report section placeholder."""

from __future__ import annotations


def render_section(result: object) -> list[str]:
    count = getattr(result, "operator_structured_abs_paths", 0)
    return [f"operator_structured_abs_paths={count}"] if count else []
