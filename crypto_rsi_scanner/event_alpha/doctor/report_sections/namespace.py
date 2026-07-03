"""Namespace report section placeholder."""

from __future__ import annotations


def render_section(result: object) -> list[str]:
    status = getattr(result, "namespace_status", None)
    if not status:
        return []
    return [f"namespace_status: {status}"]
