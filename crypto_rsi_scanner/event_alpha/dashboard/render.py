"""Escaped server-rendered HTML for the local radar dashboard."""

from __future__ import annotations

import html
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import quote, urlsplit

from .loader import candidate_identifier
from .models import DashboardResponse, DashboardSnapshot


_NAV = (
    ("/", "Today"),
    ("/anomalies", "Market Anomalies"),
    ("/catalysts", "Catalyst Ideas"),
    ("/fade-risk", "Fade / Risk"),
    ("/calendar", "Calendar"),
    ("/health", "Provider / System Health"),
    ("/feedback-outcomes", "Feedback / Outcomes"),
)
_ACTIONABLE_ROUTES = {"actionable_watch", "high_confidence_watch"}


def render_dashboard_page(
    snapshot: DashboardSnapshot,
    path: str,
    *,
    include_diagnostics: bool = False,
) -> DashboardResponse:
    current_generation_page = path in {"/", "/anomalies", "/catalysts", "/fade-risk", "/calendar"}
    if current_generation_page and not snapshot.generation_authoritative:
        title = {
            "/": "Today",
            "/anomalies": "Market Anomalies",
            "/catalysts": "Catalyst Ideas",
            "/fade-risk": "Fade / Risk",
            "/calendar": "Calendar",
        }[path]
        return _ok(snapshot, title, _authority_unavailable(snapshot))
    if path == "/":
        body = _today(snapshot, include_diagnostics=include_diagnostics)
        return _ok(snapshot, "Today", body)
    if path == "/anomalies":
        return _ok(snapshot, "Market Anomalies", _anomalies(snapshot, include_diagnostics=include_diagnostics))
    if path == "/catalysts":
        return _ok(snapshot, "Catalyst Ideas", _catalysts(snapshot, include_diagnostics=include_diagnostics))
    if path == "/fade-risk":
        return _ok(snapshot, "Fade / Risk", _fade_risk(snapshot, include_diagnostics=include_diagnostics))
    if path == "/calendar":
        return _ok(snapshot, "Calendar", _calendar(snapshot))
    if path == "/health":
        return _ok(snapshot, "Provider / System Health", _health(snapshot))
    if path == "/feedback-outcomes":
        return _ok(snapshot, "Feedback / Outcomes", _feedback_outcomes(snapshot))
    if path.startswith("/candidate/"):
        identifier = path.removeprefix("/candidate/")
        return _candidate_detail(snapshot, identifier, include_diagnostics=include_diagnostics)
    return DashboardResponse(404, "Not Found", _standalone_error("Not Found", "Unknown dashboard page."))


def _today(snapshot: DashboardSnapshot, *, include_diagnostics: bool) -> str:
    rows = tuple(
        row
        for row in snapshot.visible_current_candidates
        if row.get("_dashboard_route") in _ACTIONABLE_ROUTES
        and row.get("radar_actionable") is True
    )
    sections = [
        _section("Actionable research ideas", _candidate_table(rows)),
        _section(
            "Rapid anomalies",
            _candidate_table(
                row
                for row in snapshot.visible_current_candidates
                if row.get("_dashboard_route") == "rapid_market_anomaly"
            ),
        ),
        _section(
            "Review queues",
            _candidate_table(
                row
                for row in snapshot.visible_current_candidates
                if row.get("_dashboard_route") in {"fade_exhaustion_review", "calendar_risk"}
            ),
        ),
    ]
    if include_diagnostics:
        sections.append(_section("Diagnostics", _candidate_table(snapshot.diagnostic_candidates)))
    else:
        sections.append(
            '<p class="muted">Diagnostics are hidden by default. '
            '<a href="/?include_diagnostics=1">Show current-generation diagnostics</a>.</p>'
        )
    return "".join(sections)


def _anomalies(snapshot: DashboardSnapshot, *, include_diagnostics: bool) -> str:
    raw_by_asset = {
        _asset_key(row): row
        for row in snapshot.current_market_anomalies
        if _asset_key(row)
    }
    market_led = []
    for candidate in snapshot.current_candidates:
        if candidate.get("_decision_model_status") != "v2":
            continue
        if not (
            str(candidate.get("thesis_origin") or "") == "market_led"
            or candidate.get("anomaly_type")
            or candidate.get("market_anomaly_type")
        ):
            continue
        row = dict(candidate)
        raw = raw_by_asset.get(_asset_key(candidate), {})
        if isinstance(raw, Mapping):
            for field in ("anomaly_type", "market_anomaly_type", "market_state_class", "market_state_snapshot"):
                if row.get(field) in (None, "", {}, ()) and raw.get(field) not in (None, "", {}, ()):
                    row[field] = raw.get(field)
        if include_diagnostics or row.get("_dashboard_route") != "diagnostic":
            market_led.append(row)
    if include_diagnostics:
        market_led.extend(
            row
            for row in snapshot.current_market_anomalies
            if row.get("_decision_model_status") != "v2" or row.get("_dashboard_route") == "diagnostic"
        )
    rows = tuple(market_led)
    text = (
        "Market-led rows may be actionable without a known catalyst when identity, freshness, liquidity, "
        "spread, turnover, and manipulation-risk gates pass. Unknown catalyst remains a warning, not a trade instruction."
    )
    return f"<p>{_h(text)}</p>" + _candidate_table(rows)


def _catalysts(snapshot: DashboardSnapshot, *, include_diagnostics: bool) -> str:
    rows = tuple(
        row
        for row in snapshot.current_candidates
        if str(row.get("thesis_origin") or "") in {"catalyst_led", "mixed"}
        and str(row.get("catalyst_status") or "") in {"confirmed", "plausible"}
        and (include_diagnostics or row.get("_dashboard_route") != "diagnostic")
        and row.get("_decision_model_status") == "v2"
    )
    return _candidate_table(rows)


def _fade_risk(snapshot: DashboardSnapshot, *, include_diagnostics: bool) -> str:
    rows = tuple(
        row
        for row in snapshot.current_candidates
        if (
            str(row.get("directional_bias") or "") in {"fade_short_review", "risk"}
            or row.get("_dashboard_route") in {"fade_exhaustion_review", "calendar_risk"}
        )
        and (include_diagnostics or row.get("_dashboard_route") != "diagnostic")
        and row.get("_decision_model_status") == "v2"
    )
    return (
        "<p>Fade and risk rows are manual research reviews after a completed or scheduled risk condition. "
        "They never create <code>TRIGGERED_FADE</code>.</p>"
        + _candidate_table(rows)
    )


def _calendar(snapshot: DashboardSnapshot) -> str:
    headers = ("Event", "When", "Window", "Kind", "Importance", "Assets", "Tracking", "Source")
    body_rows = []
    for row in sorted(
        snapshot.current_calendar_events,
        key=lambda item: str(item.get("scheduled_at") or item.get("window_start") or "~"),
    ):
        scheduled = _h(row.get("scheduled_at") or "date window")
        window = _h(_window_label(row))
        body_rows.append(
            (
                _h(row.get("title") or "Untitled event"),
                scheduled,
                window,
                _h(row.get("event_kind") or "unknown"),
                _h(row.get("importance") or "unknown"),
                _h(", ".join(str(item) for item in row.get("affected_assets") or ()) or "market-wide"),
                _h(row.get("post_event_tracking_status") or "unknown"),
                _source_link(row),
            )
        )
    intro = (
        "<p>Fixture-first unified calendar. Dates may be exact, estimated, or bounded windows; "
        "reminders are display metadata only and do not send notifications.</p>"
    )
    return intro + _table(headers, body_rows, empty="No current-generation calendar rows.")


def _health(snapshot: DashboardSnapshot) -> str:
    doctor_verified = snapshot.doctor_verified_revision
    doctor_revision = "none" if doctor_verified is None else str(doctor_verified)
    summary = _definition_list(
        (
            ("Run", snapshot.run_id),
            ("Operator revision", snapshot.revision),
            ("Manifest", snapshot.manifest_status),
            ("Doctor", snapshot.doctor_status),
            ("Doctor verified revision", doctor_revision),
            ("Generation authority", snapshot.generation_authority_status),
            ("Authority checked at", snapshot.generation_authority_checked_at),
            ("Operator-state SHA-256", snapshot.operator_state_sha256),
            (
                "Authority reasons",
                "; ".join(snapshot.generation_authority_reasons) or "none",
            ),
            ("Research only", snapshot.operator_state.get("research_only")),
            ("Send attempted", snapshot.operator_state.get("send_attempted")),
            ("Trades / paper / RSI / triggered fade", "0 / 0 / 0 / 0"),
        )
    )
    artifacts = snapshot.operator_state.get("artifacts")
    artifact_rows = []
    if isinstance(artifacts, Mapping):
        for name, entry in sorted(artifacts.items()):
            if not isinstance(entry, Mapping):
                continue
            artifact_rows.append(
                (
                    _h(name),
                    _h(entry.get("status") or "unknown"),
                    _h(entry.get("path") or "not written"),
                    _h(entry.get("reason") or ""),
                )
            )
    current_providers = _provider_rows(snapshot.provider_readiness)
    cumulative_providers = _provider_rows(snapshot.provider_health)
    cumulative_health_metadata = _definition_list(
        (
            ("Authority", "cumulative / non-authoritative"),
            ("Read at", snapshot.provider_health_read_at or "not read"),
            ("SHA-256", snapshot.provider_health_sha256 or "unavailable"),
            ("Read error", snapshot.provider_health_error or "none"),
        )
    )
    return (
        _section("Current operator generation", summary)
        + _section("Artifact manifest", _table(("Artifact", "Status", "Path", "Reason"), artifact_rows))
        + _section(
            "Exact-generation provider readiness",
            _table(("Provider", "Status", "Detail"), current_providers),
        )
        + _section(
            "Cumulative provider health (non-authoritative)",
            cumulative_health_metadata
            + _table(("Provider", "Status", "Detail"), cumulative_providers),
        )
    )


def _feedback_outcomes(snapshot: DashboardSnapshot) -> str:
    feedback_rows = []
    for row in snapshot.cumulative_feedback:
        feedback_rows.append(
            (
                _h(row.get("core_opportunity_id") or row.get("target") or row.get("alert_id") or "unknown"),
                _h(row.get("label") or row.get("feedback_label") or row.get("status") or "unlabeled"),
                _h(row.get("thesis_origin") or "unclassified"),
                _h(row.get("catalyst_status") or "unclassified"),
            )
        )
    outcome_rows = []
    for row in snapshot.cumulative_outcomes:
        outcome_rows.append(
            (
                _h(row.get("core_opportunity_id") or row.get("candidate_id") or "unknown"),
                _h(row.get("outcome_status") or row.get("maturation_state") or "unknown"),
                _h(row.get("thesis_origin") or "unclassified"),
                _h(row.get("confidence_band") or "unclassified"),
                _h(row.get("actionability_score") if row.get("actionability_score") is not None else "n/a"),
            )
        )
    history_rows = []
    for artifact_name, metadata in sorted(snapshot.cumulative_history_metadata.items()):
        history_rows.append(
            (
                _h(artifact_name),
                _h(metadata.get("authority") or "cumulative_non_authoritative"),
                _h(metadata.get("read_at") or "not read"),
                _h(metadata.get("sha256") or "unavailable"),
                _h(metadata.get("error") or "none"),
            )
        )
    return (
        '<p class="scope"><strong>Cumulative research history.</strong> These rows are intentionally not '
        "presented as current-generation candidate counts.</p>"
        + _section(
            "Cumulative artifact reads (non-authoritative)",
            _table(("Artifact", "Authority", "Read at", "SHA-256", "Read error"), history_rows),
        )
        + _section(
            f"Feedback labels ({len(feedback_rows)})",
            _table(("Target", "Label", "Thesis origin", "Catalyst status"), feedback_rows),
        )
        + _section(
            f"Outcome rows ({len(outcome_rows)})",
            _table(("Target", "State", "Thesis origin", "Confidence", "Actionability"), outcome_rows),
        )
    )


def _candidate_detail(
    snapshot: DashboardSnapshot,
    identifier: str,
    *,
    include_diagnostics: bool,
) -> DashboardResponse:
    if not snapshot.generation_authoritative:
        return DashboardResponse(
            409,
            "Conflict",
            _layout(snapshot, "Candidate unavailable", _authority_unavailable(snapshot)),
        )
    row = next(
        (
            item
            for item in (*snapshot.current_candidates, *snapshot.current_market_anomalies)
            if candidate_identifier(item) == identifier
        ),
        None,
    )
    if row is None or (
        not include_diagnostics
        and (
            row.get("_decision_model_status") != "v2"
            or row.get("_dashboard_route") == "diagnostic"
        )
    ):
        return DashboardResponse(
            404,
            "Not Found",
            _layout(snapshot, "Candidate not found", "<p>No visible current-generation candidate has that ID.</p>"),
        )
    dimensions = _definition_list(
        (
            ("ID", candidate_identifier(row)),
            ("Asset", f"{row.get('symbol') or 'unknown'} / {row.get('coin_id') or 'unknown'}"),
            ("Research route", row.get("_dashboard_route") or "diagnostic"),
            ("Legacy opportunity type", row.get("opportunity_type") or "unknown"),
            ("Thesis origin", row.get("thesis_origin") or "unclassified"),
            ("Directional bias", row.get("directional_bias") or "unclassified"),
            ("Catalyst status", row.get("catalyst_status") or "unclassified"),
            ("Confidence", row.get("confidence_band") or "unclassified"),
            ("Timing", row.get("timing_state") or "unclassified"),
            ("Tradability", row.get("tradability_status") or "unclassified"),
            ("Actionability", _score(row.get("actionability_score"))),
            ("Evidence confidence", _score(row.get("evidence_confidence_score"))),
            ("Risk", _score(row.get("risk_score"))),
            ("Catalyst warning", "Catalyst unknown" if row.get("catalyst_status") == "unknown" else "none"),
        )
    )
    source = _source_link(row)
    source_block = f"<p><strong>Source:</strong> {source}</p>" if source else ""
    body = (
        dimensions
        + source_block
        + _text_list(
            "Why still worth reviewing",
            _values(row, "why_still_worth_reviewing", "why_review_worthy", "why_now"),
        )
        + _text_list(
            "Missing data",
            _values(row, "decision_missing_data", "missing_data", "missing_data_fields"),
        )
        + _text_list("Hard blockers", _values(row, "decision_hard_blockers"))
        + _text_list("Soft penalties", _values(row, "decision_soft_penalties"))
        + _text_list("Decision warnings", _values(row, "decision_warnings"))
        + _text_list("What confirms", _values(row, "radar_what_confirms", "what_confirms"))
        + _text_list("What invalidates", _values(row, "radar_what_invalidates", "what_invalidates"))
        + _score_components("Actionability score components", row.get("actionability_score_components"))
        + _score_components("Actionability penalty components", row.get("actionability_penalty_components"))
        + _score_components(
            "Evidence-confidence score components",
            row.get("evidence_confidence_score_components"),
        )
        + _score_components("Risk score components", row.get("risk_score_components"))
    )
    return _ok(snapshot, f"Candidate {row.get('symbol') or identifier}", body)


def _candidate_table(rows: Iterable[Mapping[str, Any]]) -> str:
    body_rows = []
    seen = set()
    for row in rows:
        identifier = candidate_identifier(row)
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)
        link = f'<a href="/candidate/{quote(identifier, safe="")}">{_h(row.get("symbol") or identifier)}</a>'
        warning = "Catalyst unknown" if row.get("catalyst_status") == "unknown" else ""
        if _higher_manipulation_risk(row):
            warning = (warning + "; " if warning else "") + "Higher manipulation/tradability risk"
        body_rows.append(
            (
                link,
                _h(row.get("_dashboard_route") or "diagnostic"),
                _h(row.get("thesis_origin") or "legacy unclassified"),
                _h(row.get("directional_bias") or "unclassified"),
                _h(row.get("confidence_band") or "unclassified"),
                _h(_score(row.get("actionability_score"))),
                _h(_score(row.get("evidence_confidence_score"))),
                _h(_score(row.get("risk_score"))),
                _h(warning),
            )
        )
    return _table(
        ("Asset", "Route", "Thesis", "Bias", "Confidence", "Actionability", "Evidence", "Risk", "Warning"),
        body_rows,
        empty="No rows in this current-generation lane.",
    )


def _higher_manipulation_risk(row: Mapping[str, Any]) -> bool:
    components = row.get("risk_score_components")
    try:
        manipulation = float(components.get("manipulation_risk") or 0.0) if isinstance(components, Mapping) else 0.0
    except (TypeError, ValueError):
        manipulation = 0.0
    warnings = " ".join(str(item) for item in row.get("decision_warnings") or ())
    return bool(
        row.get("tradability_status") in {"poor", "blocked"}
        or manipulation >= 50.0
        or "manipulation" in warnings.casefold()
    )


def _provider_rows(*payloads: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for payload in payloads:
        raw = payload.get("providers") if isinstance(payload, Mapping) else None
        if isinstance(raw, Mapping):
            values = [dict(value, provider=key) if isinstance(value, Mapping) else {"provider": key, "status": value} for key, value in raw.items()]
        elif isinstance(raw, Iterable) and not isinstance(raw, (str, bytes, Mapping)):
            values = [item for item in raw if isinstance(item, Mapping)]
        else:
            values = []
        for item in values:
            out.append(
                (
                    _h(item.get("provider") or item.get("name") or item.get("provider_key") or "unknown"),
                    _h(item.get("status") or item.get("readiness_status") or item.get("health_status") or "unknown"),
                    _h(item.get("reason") or item.get("status_detail") or item.get("skip_reason") or ""),
                )
            )
    return out


def _ok(snapshot: DashboardSnapshot, title: str, body: str) -> DashboardResponse:
    return DashboardResponse(200, "OK", _layout(snapshot, title, body))


def _layout(snapshot: DashboardSnapshot, title: str, body: str) -> str:
    nav = "".join(f'<a href="{path}">{_h(label)}</a>' for path, label in _NAV)
    current_count = (
        str(snapshot.current_generation_count)
        if snapshot.generation_authoritative
        else "suppressed (untrusted)"
    )
    cumulative_count = (
        str(snapshot.cumulative_store_count)
        if snapshot.generation_authoritative
        else "see Feedback / Outcomes"
    )
    scope = (
        f"Current generation: {_h(snapshot.run_id)} · revision {snapshot.revision} · "
        f"current candidates {current_count} · cumulative core history {cumulative_count}"
    )
    authority_banner = ""
    if not snapshot.generation_authoritative:
        reasons = "".join(f"<li>{_h(reason)}</li>" for reason in snapshot.generation_authority_reasons)
        authority_banner = (
            '<div class="authority-untrusted"><strong>UNTRUSTED CURRENT GENERATION.</strong> '
            "Current actionable, anomaly, catalyst, fade/risk, calendar, diagnostic, and candidate-detail "
            f"content is suppressed.<ul>{reasons}</ul></div>"
        )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_h(title)} · Crypto Radar</title><style>
:root{{--bg:#0b1020;--panel:#151d31;--ink:#eef3ff;--muted:#a9b6d3;--line:#2d3956;--accent:#7dd3fc;--warn:#fbbf24;--danger:#f87171}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,sans-serif}}
header,main{{max-width:1280px;margin:auto;padding:18px}}nav{{display:flex;gap:14px;flex-wrap:wrap}}a{{color:var(--accent)}}
.banner,.scope,.authority-untrusted,section{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:14px 0}}
.banner{{border-color:#725b16;color:#fde68a}}.muted{{color:var(--muted)}}table{{width:100%;border-collapse:collapse;overflow:auto}}
.authority-untrusted{{border:3px solid var(--danger);color:#fecaca;background:#3f1219}}.authority-untrusted strong{{font-size:1.08em}}
th,td{{border-bottom:1px solid var(--line);padding:8px;text-align:left;vertical-align:top}}th{{color:var(--muted)}}
dl{{display:grid;grid-template-columns:minmax(150px,260px) 1fr;gap:6px 14px}}dt{{color:var(--muted)}}dd{{margin:0;overflow-wrap:anywhere}}
code{{color:#bae6fd}}@media(max-width:760px){{table{{display:block;overflow-x:auto}}dl{{grid-template-columns:1fr}}}}
</style></head><body><header><h1>Crypto Radar</h1><nav>{nav}</nav></header><main>
<div class="banner"><strong>Research idea, not a trade instruction.</strong> No execution, Event Alpha paper trading, normal RSI writes, or Event Alpha <code>TRIGGERED_FADE</code> creation.</div>
{authority_banner}
<div class="scope">{scope}<br>Doctor: {_h(snapshot.doctor_status)} at revision {_h(snapshot.doctor_verified_revision if snapshot.doctor_verified_revision is not None else 'not verified')}</div>
<h2>{_h(title)}</h2>{body}</main></body></html>"""


def _standalone_error(title: str, detail: str) -> str:
    return f"<!doctype html><html><head><meta charset=\"utf-8\"><title>{_h(title)}</title></head><body><h1>{_h(title)}</h1><p>{_h(detail)}</p></body></html>"


def _authority_unavailable(snapshot: DashboardSnapshot) -> str:
    reasons = _text_list("Authority failures", snapshot.generation_authority_reasons)
    return (
        "<p><strong>Current-generation research content is unavailable because generation authority "
        "did not pass.</strong> Provider/system health and explicitly cumulative feedback/outcomes remain visible.</p>"
        + reasons
    )


def _section(title: str, body: str) -> str:
    return f"<section><h3>{_h(title)}</h3>{body}</section>"


def _table(headers: Iterable[str], rows: Iterable[Iterable[str]], *, empty: str = "No rows.") -> str:
    materialized = [tuple(row) for row in rows]
    if not materialized:
        return f'<p class="muted">{_h(empty)}</p>'
    head = "".join(f"<th>{_h(value)}</th>" for value in headers)
    body = "".join("<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>" for row in materialized)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _definition_list(items: Iterable[tuple[str, object]]) -> str:
    return "<dl>" + "".join(f"<dt>{_h(key)}</dt><dd>{_h(value)}</dd>" for key, value in items) + "</dl>"


def _text_list(title: str, values: Iterable[str]) -> str:
    materialized = tuple(str(value) for value in values if str(value).strip())
    if not materialized:
        return f"<h3>{_h(title)}</h3><p class=\"muted\">None recorded.</p>"
    return f"<h3>{_h(title)}</h3><ul>" + "".join(f"<li>{_h(value)}</li>" for value in materialized) + "</ul>"


def _score_components(title: str, value: object) -> str:
    if not isinstance(value, Mapping) or not value:
        return f'<h3>{_h(title)}</h3><p class="muted">No component detail recorded.</p>'
    rows = [(_h(key), _h(component)) for key, component in sorted(value.items()) if not isinstance(component, (Mapping, list, tuple, set))]
    return f"<h3>{_h(title)}</h3>" + _table(("Component", "Value"), rows)


def _values(row: Mapping[str, Any], *fields: str) -> tuple[str, ...]:
    out = []
    for field in fields:
        value = row.get(field)
        if isinstance(value, str):
            if value.strip():
                out.append(value.strip())
        elif isinstance(value, Iterable) and not isinstance(value, (bytes, Mapping)):
            out.extend(str(item).strip() for item in value if str(item).strip())
    return tuple(dict.fromkeys(out))


def _window_label(row: Mapping[str, Any]) -> str:
    start = str(row.get("window_start") or "").strip()
    end = str(row.get("window_end") or "").strip()
    certainty = str(row.get("time_certainty") or "unknown")
    if start or end:
        return f"{start or 'unknown'} → {end or 'unknown'} ({certainty})"
    return certainty


def _asset_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("symbol") or row.get("validated_symbol") or "").strip().upper(),
        str(row.get("coin_id") or row.get("validated_coin_id") or "").strip().casefold(),
    )


def _source_link(row: Mapping[str, Any]) -> str:
    raw = str(row.get("source_url") or row.get("latest_source_url") or row.get("url") or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return '<span class="muted">unsafe or unavailable source URL</span>'
    label = str(row.get("source") or row.get("latest_source") or parsed.netloc)
    return f'<a href="{_h(raw)}" rel="noreferrer" target="_blank">{_h(label)}</a>'


def _score(value: object) -> str:
    try:
        return f"{float(value):.0f}/100"
    except (TypeError, ValueError):
        return "n/a"


def _h(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


__all__ = ("render_dashboard_page",)
