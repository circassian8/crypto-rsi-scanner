"""Stale artifact report section placeholder."""

from __future__ import annotations


def render_section(result: object) -> list[str]:
    if getattr(result, "namespace_stale_deprecated", 0):
        return ["stale namespace artifacts present"]
    return []
