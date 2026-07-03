"""Check registry report section."""

from __future__ import annotations

from .. import check_registry


def render_section(result: object) -> list[str]:
    _ = result
    return check_registry.registry_report_lines()
