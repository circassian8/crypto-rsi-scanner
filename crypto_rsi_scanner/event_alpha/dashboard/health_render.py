"""Provider, source-coverage, and exact operator-health dashboard rendering."""

from __future__ import annotations

import html
import math
from typing import Any, Iterable, Mapping

from .layer_diagnostics import source_coverage_rows
from .models import DashboardSnapshot


def render_health(snapshot: DashboardSnapshot) -> str:
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
            ("Authority reasons", "; ".join(snapshot.generation_authority_reasons) or "none"),
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
                    _h(_artifact_count(entry)),
                    _h(entry.get("path") or "not written"),
                    _h(entry.get("reason") or ""),
                )
            )
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
        + _section(
            "Artifact manifest",
            _table(
                ("Artifact", "Status", "Count", "Path", "Reason"),
                artifact_rows,
                caption="Artifact manifest compatibility diagnostics",
            ),
        )
        + _section(
            "Exact-generation source-pack coverage",
            _table(
                ("Source pack", "Status", "Accepted", "Configured", "Healthy", "Missing", "Gap"),
                source_coverage_rows(snapshot.source_coverage),
                empty="No per-pack coverage assessment is recorded for this exact generation.",
                caption="Exact-generation source-pack compatibility diagnostics",
            ),
        )
        + _section(
            "Exact-generation provider readiness",
            _table(
                ("Provider", "Status", "Detail"),
                _provider_rows(snapshot.provider_readiness),
                caption="Exact-generation provider readiness compatibility diagnostics",
            ),
        )
        + _section(
            "Cumulative provider health (non-authoritative)",
            cumulative_health_metadata
            + _table(
                ("Provider", "Status", "Detail"),
                _provider_rows(snapshot.provider_health),
                caption="Cumulative provider health compatibility diagnostics",
            ),
        )
    )


def _artifact_count(entry: Mapping[str, Any]) -> object:
    if entry.get("count") is not None:
        return entry.get("count")
    if entry.get("item_count") is not None:
        return entry.get("item_count")
    return "n/a"


def _provider_rows(payload: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    raw = payload.get("providers") if isinstance(payload, Mapping) else None
    if isinstance(raw, Mapping):
        values = [
            dict(value, provider=key)
            if isinstance(value, Mapping)
            else {"provider": key, "status": value}
            for key, value in raw.items()
        ]
    elif isinstance(raw, Iterable) and not isinstance(raw, (str, bytes, Mapping)):
        values = [item for item in raw if isinstance(item, Mapping)]
    else:
        values = []
    return [
        (
            _h(item.get("provider") or item.get("name") or item.get("provider_key") or "unknown"),
            _h(_provider_status(item)),
            _h(_provider_detail(item)),
        )
        for item in values
    ]


def _provider_status(item: Mapping[str, Any]) -> str:
    explicit = item.get("status") or item.get("readiness_status") or item.get("health_status")
    if explicit not in (None, ""):
        return str(explicit)
    if item.get("disabled_until") not in (None, ""):
        return "backoff"
    failures = _finite_number(item.get("consecutive_failures"))
    http_status = _finite_number(item.get("request_http_status") or item.get("http_status"))
    if failures is not None and failures > 0:
        return "degraded"
    if item.get("last_success_at") not in (None, "") or (
        http_status is not None and 200 <= http_status < 300
    ):
        return "observed_healthy"
    return str(
        item.get("activation_phase")
        or item.get("preflight_status")
        or item.get("latest_provider_health_status")
        or item.get("latest_rehearsal_status")
        or "not_observed"
    )


def _provider_detail(item: Mapping[str, Any]) -> str:
    values: list[str] = []
    fields = (
        ("configured", "configured"),
        ("configuration_scope", "configuration_scope"),
        ("fixture_input_configured", "fixture_input_configured"),
        ("live_transport_status", "live_transport_status"),
        ("live_authorization_status", "live_authorization_status"),
        ("live_mapping_status", "live_mapping_status"),
        ("live_rehearsal_eligible", "live_rehearsal_eligible"),
        ("live_call_allowed", "live_call_allowed"),
        ("activation_phase", "activation_phase"),
        ("preflight_status", "preflight"),
        ("latest_provider_health_status", "latest_health"),
        ("latest_rehearsal_status", "latest_rehearsal"),
        ("last_success_at", "last_success"),
        ("request_http_status", "HTTP"),
        ("http_status", "HTTP"),
        ("result_count", "result_count"),
        ("consecutive_failures", "consecutive_failures"),
        ("disabled_until", "disabled_until"),
    )
    seen_labels: set[str] = set()
    for field, label in fields:
        value = item.get(field)
        if value in (None, "") or label in seen_labels:
            continue
        if isinstance(value, bool):
            value = str(value).lower()
        values.append(f"{label}={value}")
        seen_labels.add(label)
    reason = item.get("reason") or item.get("status_detail") or item.get("skip_reason")
    if reason not in (None, ""):
        values.append(f"reason={reason}")
    return "; ".join(values) or "no status detail recorded"


def _section(title: str, body: str) -> str:
    return f"<section><h3>{_h(title)}</h3>{body}</section>"


def _table(
    headers: Iterable[str],
    rows: Iterable[Iterable[str]],
    *,
    empty: str = "No rows.",
    caption: str = "Compatibility diagnostics",
) -> str:
    materialized = [tuple(row) for row in rows]
    if not materialized:
        return f'<p class="muted">{_h(empty)}</p>'
    head = "".join(f'<th scope="col">{_h(value)}</th>' for value in headers)
    body_rows: list[str] = []
    for row in materialized:
        cells = "".join(
            (
                f'<th scope="row">{value}</th>'
                if index == 0
                else f"<td>{value}</td>"
            )
            for index, value in enumerate(row)
        )
        body_rows.append(f"<tr>{cells}</tr>")
    safe_caption = _h(caption)
    return (
        f'<div class="table-scroll" role="region" tabindex="0" aria-label="{safe_caption}">'
        '<table class="responsive-table compact-table">'
        f'<caption class="sr-only">{safe_caption}</caption>'
        f'<thead><tr>{head}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>'
    )


def _definition_list(items: Iterable[tuple[str, object]]) -> str:
    return "<dl>" + "".join(f"<dt>{_h(key)}</dt><dd>{_h(value)}</dd>" for key, value in items) + "</dl>"


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _h(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


__all__ = ("render_health",)
