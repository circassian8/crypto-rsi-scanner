"""Warning section renderer."""

from __future__ import annotations


def render_section(result: object) -> list[str]:
    return [f"- {item}" for item in tuple(getattr(result, "warnings", ()) or ())]
