"""Accessible product shell for the local Decision Radar dashboard."""

from __future__ import annotations

from collections.abc import Mapping

from ..operations import market_provenance
from .components import badge, escape_html, time_element
from .models import DashboardSnapshot
from .presentation import humanize_enum, humanize_reason, present_time
from .styles import DASHBOARD_CSS


PRIMARY_NAV = (
    ("/", "Today"),
    ("/market-radar", "Market Radar"),
    ("/ideas", "Ideas"),
    ("/calendar", "Calendar"),
    ("/health", "System Health"),
    ("/outcomes", "Outcomes & Learning"),
    ("/campaign-history", "Campaign History"),
)


def render_shell(
    snapshot: DashboardSnapshot,
    *,
    title: str,
    path: str,
    body: str,
) -> str:
    """Wrap escaped/trusted page content in one responsive operator shell."""

    nav = "".join(_nav_link(href, label, path) for href, label in PRIMARY_NAV)
    trust = _trust_strip(snapshot)
    authority = _authority_banner(snapshot)
    identity = _identity_disclosure(snapshot)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="dark"><title>{escape_html(title)} · Crypto Decision Radar</title>
<style>{DASHBOARD_CSS}</style></head>
<body><a class="skip-link" href="#main-content">Skip to decision workspace</a>
<div class="app-shell">
<aside class="app-rail" aria-label="Decision Radar navigation">
  <a class="brand" href="/" aria-label="Crypto Decision Radar home">
    <span class="brand-mark" aria-hidden="true">CR</span>
    <span><strong>Crypto Radar</strong><small>Decision support</small></span>
  </a>
  <nav class="primary-nav" aria-label="Primary">{nav}</nav>
  <p class="rail-safety">Research only<br>No execution</p>
</aside>
<div class="app-workspace">
  <header class="topbar"><div><p class="eyebrow">Operator workspace</p><h1>{escape_html(title)}</h1></div>
  <div class="topbar-state">{trust}</div></header>
  <main id="main-content" tabindex="-1">
    {authority}
    <div class="research-banner" role="note"><strong>Human decision required.</strong>
      Research idea, not a trade instruction. No orders, execution, paper trades, normal RSI writes,
      or Event Alpha triggered-fade creation.</div>
    {identity}
    {body}
  </main>
</div></div></body></html>"""


def _nav_link(href: str, label: str, current_path: str) -> str:
    aliases = {
        "/market-radar": {"/market-radar", "/anomalies"},
        "/ideas": {"/ideas", "/catalysts", "/fade-risk"},
        "/outcomes": {"/outcomes", "/feedback-outcomes"},
    }
    active = current_path == href or current_path.startswith("/ideas/") and href == "/ideas"
    active = active or current_path.startswith("/candidate/") and href == "/ideas"
    active = active or current_path in aliases.get(href, set())
    current = ' aria-current="page"' if active else ""
    return f'<a href="{escape_html(href)}"{current}>{escape_html(label)}</a>'


def _trust_strip(snapshot: DashboardSnapshot) -> str:
    mode, mode_tone, provenance = _generation_mode(snapshot)
    stale = any(
        "stale" in str(reason).casefold() or "age" in str(reason).casefold()
        for reason in snapshot.generation_authority_reasons
    )
    authority = "STALE" if stale else "CURRENT" if snapshot.generation_authoritative else "UNTRUSTED"
    authority_tone = "positive" if snapshot.generation_authoritative else "danger"
    doctor_ok = snapshot.doctor_status.casefold() == "ok"
    no_send = snapshot.operator_state.get("send_attempted") is False
    source_mode = str(
        provenance.get("candidate_source_mode")
        or provenance.get("data_acquisition_mode")
        or ""
    ).casefold()
    campaign_counted = bool(
        provenance.get("provenance_contract_valid") is True
        and provenance.get("decision_radar_campaign_counted") is True
        and source_mode in {"live_no_send", "live_provider", "live"}
    )
    values = (
        badge(authority, label=authority, tone=authority_tone),
        badge(mode, label=mode, tone=mode_tone),
        badge(
            "NO-SEND" if no_send else "SEND STATE UNKNOWN",
            label="NO-SEND" if no_send else "SEND STATE UNKNOWN",
            tone="positive" if no_send else "warning",
        ),
        badge(
            "CAMPAIGN COUNTED" if campaign_counted else "CAMPAIGN EXCLUDED",
            label="CAMPAIGN COUNTED" if campaign_counted else "CAMPAIGN EXCLUDED",
            tone="positive" if campaign_counted else "warning",
        ),
        badge(
            "Doctor clean" if doctor_ok else f"Doctor {humanize_enum(snapshot.doctor_status)}",
            tone="positive" if doctor_ok else "danger",
        ),
    )
    return '<div class="trust-strip" aria-label="Generation trust status">' + "".join(values) + "</div>"


def _generation_mode(snapshot: DashboardSnapshot) -> tuple[str, str, Mapping[str, object]]:
    state = snapshot.operator_state
    raw = state.get("market_no_send_provenance") or state.get("market_data_provenance")
    provenance: Mapping[str, object] = {}
    if isinstance(raw, Mapping) and raw:
        normalized = market_provenance.normalize_market_provenance(raw)
        if (
            normalized.get("provenance_contract_valid") is True
            and all(normalized.get(key) == value for key, value in raw.items())
        ):
            provenance = normalized
    source_mode = str(
        provenance.get("candidate_source_mode")
        or provenance.get("data_acquisition_mode")
        or state.get("data_mode")
        or next(
            (
                row.get("data_mode")
                for row in snapshot.current_candidates
                if isinstance(row, Mapping) and row.get("data_mode")
            ),
            None,
        )
        or state.get("run_mode")
        or "unknown"
    ).strip().casefold()
    if not provenance and source_mode in {"live_no_send", "live_provider", "live"}:
        source_mode = "unverified_live_claim"
    modes = {
        "live_no_send": ("LIVE / REAL DATA", "info"),
        "live_provider": ("LIVE / REAL DATA", "info"),
        "live": ("LIVE / REAL DATA", "info"),
        "mocked_fixture": ("MOCKED FIXTURE", "warning"),
        "mock_fixture": ("MOCKED FIXTURE", "warning"),
        "mock": ("MOCKED FIXTURE", "warning"),
        "fixture": ("FIXTURE", "warning"),
        "artifact_replay": ("ARTIFACT REPLAY", "warning"),
        "cached": ("CACHED DATA", "warning"),
        "preflight_only": ("PREFLIGHT ONLY", "warning"),
        "unverified_live_claim": ("UNVERIFIED LIVE CLAIM", "danger"),
    }
    label, tone = modes.get(source_mode, (humanize_enum(source_mode).upper(), "neutral"))
    return label, tone, provenance


def _authority_banner(snapshot: DashboardSnapshot) -> str:
    if snapshot.generation_authoritative:
        return ""
    reasons = "".join(f"<li>{escape_html(humanize_reason(value))}</li>" for value in snapshot.generation_authority_reasons)
    return (
        '<section class="alert alert-danger" role="alert"><div class="alert-icon" aria-hidden="true">!</div>'
        '<div><p><strong>UNTRUSTED CURRENT GENERATION.</strong></p>'
        '<h2>Current-generation content is suppressed</h2>'
        '<p>The exact generation no longer satisfies authority checks. Ideas, market rows, and calendar '
        'data are not presented as current; current candidates suppressed (untrusted).</p>'
        f'<ul>{reasons}</ul></div></section>'
    )


def _identity_disclosure(snapshot: DashboardSnapshot) -> str:
    checked = present_time(snapshot.generation_authority_checked_at)
    if snapshot.generation_authoritative:
        row_summary = (
            f"{escape_html(str(snapshot.current_generation_count))} candidate rows · "
            f"{escape_html(str(len(snapshot.visible_current_candidates)))} operator-visible"
        )
    else:
        row_summary = "current rows suppressed"
    summary = (
        f"{escape_html(snapshot.artifact_namespace)} · revision {snapshot.revision} · "
        f"{row_summary}"
    )
    detail = (
        '<dl class="technical-grid">'
        f'<dt>Namespace</dt><dd><code>{escape_html(snapshot.artifact_namespace)}</code></dd>'
        f'<dt>Run</dt><dd><code>{escape_html(snapshot.run_id)}</code></dd>'
        f'<dt>Revision</dt><dd>{snapshot.revision}</dd>'
        f'<dt>Authority checked</dt><dd>{time_element(checked)}</dd>'
        f'<dt>Operator state</dt><dd><code>{escape_html(snapshot.operator_state_sha256)}</code></dd>'
        '</dl>'
    )
    return (
        '<details class="disclosure generation-disclosure"><summary>Exact generation · '
        + summary
        + '</summary><div class="disclosure__body">'
        + detail
        + '</div></details>'
    )


__all__ = ("PRIMARY_NAV", "render_shell")
