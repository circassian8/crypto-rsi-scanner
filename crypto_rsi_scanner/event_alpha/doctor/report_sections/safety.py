"""Safety report section placeholder."""

from __future__ import annotations


def render_section(result: object) -> list[str]:
    if getattr(result, "invalid_safety_fields", 0):
        return [f"invalid_safety_fields={getattr(result, 'invalid_safety_fields')}"]
    return []
