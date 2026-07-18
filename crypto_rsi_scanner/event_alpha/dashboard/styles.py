"""Composed responsive stylesheet for the local Decision Radar dashboard."""

from __future__ import annotations

from .style_decision_detail import DECISION_DETAIL_CSS
from .style_foundation import FOUNDATION_CSS
from .style_operator import OPERATOR_CSS
from .style_operator_work import OPERATOR_WORK_CSS
from .style_records import RECORDS_CSS
from .style_responsive import RESPONSIVE_CSS


DASHBOARD_CSS = "\n\n".join(
    (
        FOUNDATION_CSS,
        OPERATOR_CSS,
        OPERATOR_WORK_CSS,
        DECISION_DETAIL_CSS,
        RECORDS_CSS,
        RESPONSIVE_CSS,
    )
)


def dashboard_css() -> str:
    """Return the immutable in-document stylesheet used by dashboard pages."""

    return DASHBOARD_CSS


__all__ = ("DASHBOARD_CSS", "dashboard_css")
