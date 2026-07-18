"""Campaign-wide human work surfaced without creating side effects."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .components import badge, escape_html, time_element
from .models import DashboardSnapshot
from .presentation import humanize_enum, present_time


_Action = tuple[str, str, str, str, str, str]


def render_operator_work_queue(snapshot: DashboardSnapshot) -> str:
    """Render exact open campaign work when its report matches the pointer."""

    actions = operator_work_actions(snapshot)
    if not actions:
        return ""
    state = snapshot.campaign_operator_actions
    cards = "".join(_action_card(*action) for action in actions)
    generated = time_element(
        present_time(
            state.get("report_generated_at"),
            now=snapshot.generation_authority_checked_at,
        ),
        primary="combined",
    )
    return (
        '<section class="panel operator-work-panel" id="human-work-queue">'
        '<div class="section-heading"><div><p class="eyebrow">Campaign-wide · human input</p>'
        '<h2>Open operator work</h2></div>'
        f'{badge(f"{len(actions)} open", tone="warning")}</div>'
        '<p class="operator-work-intro">These are genuine campaign actions, separate from '
        'the current zero-idea generation. Dashboard reads never count as a review, and every '
        'shown command is readiness-only or read-only.</p>'
        f'<div class="operator-work-grid">{cards}</div>'
        '<p class="operator-work-source">Source: pointer-matched campaign report · '
        f'{escape_html(humanize_enum(state.get("campaign_status")))} · generated '
        f'{generated}</p></section>'
    )


def operator_work_actions(snapshot: DashboardSnapshot) -> tuple[_Action, ...]:
    """Return safe display actions from the closed campaign projection."""

    state = snapshot.campaign_operator_actions
    if state.get("status") != "ready":
        return ()
    actions: list[_Action] = []
    review = _mapping(state.get("human_review"))
    review_count = _count(review.get("action_required_count"))
    if review_count:
        not_viewed = _count(review.get("not_viewed_count"))
        in_review = _count(review.get("in_review_count"))
        review_verb = "needs" if review_count == 1 else "need"
        actions.append((
            "Human review timing",
            f"{review_count} published idea record{'s' if review_count != 1 else ''} {review_verb} explicit review",
            f"{not_viewed} not viewed · {in_review} in review. Merely opening this dashboard records nothing.",
            str(review.get("next_safe_command") or ""),
            "Open run history",
            "/campaign-history",
        ))
    recovery = _mapping(state.get("outcome_recovery"))
    gap_count = _count(recovery.get("due_missing_price_count"))
    if gap_count:
        gap_verb = "needs" if gap_count == 1 else "need"
        symbols = tuple(
            str(value) for value in recovery.get("symbols") or () if str(value)
        )
        affected = ", ".join(symbols) if symbols else "affected campaign ideas"
        actions.append((
            "Outcome completeness",
            f"{gap_count} outcome price gap{'s' if gap_count != 1 else ''} {gap_verb} point-in-time evidence",
            f"Affected: {affected}. Interpolation remains forbidden; readiness makes no provider call.",
            str(recovery.get("next_safe_command") or ""),
            "Open outcomes",
            "/outcomes",
        ))
    execution = _mapping(state.get("execution_quality"))
    retained = _count(execution.get("retained_observation_count"))
    spread = _count(execution.get("spread_available_count"))
    if execution.get("status") == "awaiting_authorized_immutable_capture" and spread < retained:
        actions.append((
            "Execution quality",
            "Bybit USDT-perpetual spread evidence is still absent",
            f"Trusted spread coverage is {spread}/{retained}. The selected venue is known; authorization and genuine capture remain separate.",
            str(execution.get("next_safe_command") or ""),
            "Open market quality",
            "/health#market-quality",
        ))
    return tuple(actions)


def health_operator_action_items(
    snapshot: DashboardSnapshot,
) -> tuple[tuple[str, str, str, str], ...]:
    """Summarize the same queue inside System Health navigation."""

    rows = []
    for _category, title, detail, _command, _link_label, _href in operator_work_actions(
        snapshot
    ):
        rows.append((title, detail, "warning", "#human-work-queue"))
    return tuple(rows)


def _action_card(
    category: str,
    title: str,
    detail: str,
    command: str,
    link_label: str,
    href: str,
) -> str:
    command_html = (
        '<div class="operator-work-command"><span>Safe next step</span>'
        f'<code>{escape_html(command)}</code></div>'
        if command
        else ""
    )
    return (
        '<article class="operator-work-card">'
        f'<p class="eyebrow">{escape_html(category)}</p>'
        f'<h3>{escape_html(title)}</h3><p>{escape_html(detail)}</p>{command_html}'
        f'<a class="button button-quiet" href="{escape_html(href)}">'
        f'{escape_html(link_label)} →</a></article>'
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _count(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


__all__ = (
    "health_operator_action_items",
    "operator_work_actions",
    "render_operator_work_queue",
)
