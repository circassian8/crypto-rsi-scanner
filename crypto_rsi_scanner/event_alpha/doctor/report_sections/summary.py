"""Summary report renderer for the Event Alpha artifact doctor."""

from __future__ import annotations

from .. import artifact_doctor_core as _api


def render_section(result: object) -> list[str]:
    return _api.format_artifact_doctor_report(result).splitlines()


def format_artifact_doctor_report(result: object) -> str:
    return "\n".join(render_section(result))
