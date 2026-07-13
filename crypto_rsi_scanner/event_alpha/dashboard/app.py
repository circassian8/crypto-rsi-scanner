"""GET-only WSGI application for the local Event Alpha radar dashboard."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Callable, Iterable
from urllib.parse import parse_qs, unquote
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from .loader import load_dashboard_snapshot
from .models import DashboardGenerationBinding, DashboardLoadError, DashboardSnapshot
from .render import render_dashboard_page


StartResponse = Callable[[str, list[tuple[str, str]]], object]


class _ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    """Loopback WSGI server that cannot be monopolized by one stalled client."""

    daemon_threads = True
    block_on_close = False
    allow_reuse_address = True


class RadarDashboardApp:
    """Small read-only WSGI app backed by exact operator generations."""

    def __init__(
        self,
        artifact_base_dir: str | Path,
        artifact_namespace: str,
        *,
        now: datetime | str | None = None,
        max_generation_age_hours: float | None = None,
        max_doctor_age_hours: float | None = None,
        generation_binding: DashboardGenerationBinding | None = None,
    ) -> None:
        self.artifact_base_dir = Path(artifact_base_dir).expanduser()
        self.artifact_namespace = str(artifact_namespace)
        if (
            generation_binding is not None
            and generation_binding.artifact_namespace != self.artifact_namespace
        ):
            raise ValueError("dashboard generation binding does not match the artifact namespace")
        self.now = now
        self.max_generation_age_hours = max_generation_age_hours
        self.max_doctor_age_hours = max_doctor_age_hours
        self.generation_binding = generation_binding

    def __call__(self, environ: dict[str, object], start_response: StartResponse) -> Iterable[bytes]:
        return _handle_dashboard_request(self, environ, start_response)


def _handle_dashboard_request(
    app: RadarDashboardApp,
    environ: dict[str, object],
    start_response: StartResponse,
) -> Iterable[bytes]:
    method = str(environ.get("REQUEST_METHOD") or "GET").upper()
    if method not in {"GET", "HEAD"}:
        return _method_not_allowed(method, start_response)
    try:
        status, payload = _render_dashboard_request(app, environ)
    except DashboardLoadError as exc:
        status, payload = _dashboard_unavailable(exc)
    start_response(status, _dashboard_headers(payload))
    return [b"" if method == "HEAD" else payload]


def _method_not_allowed(method: str, start_response: StartResponse) -> Iterable[bytes]:
    body = b"Method Not Allowed\n"
    start_response(
        "405 Method Not Allowed",
        [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Allow", "GET, HEAD"),
            ("Cache-Control", "no-store"),
        ],
    )
    return [b"" if method == "HEAD" else body]


def _render_dashboard_request(
    app: RadarDashboardApp,
    environ: dict[str, object],
) -> tuple[str, bytes]:
    snapshot = load_dashboard_snapshot(
        app.artifact_base_dir,
        app.artifact_namespace,
        now=app.now,
        max_generation_age_hours=app.max_generation_age_hours,
        max_doctor_age_hours=app.max_doctor_age_hours,
    )
    _require_generation_binding(snapshot, app.generation_binding)
    path = unquote(str(environ.get("PATH_INFO") or "/"))
    query = parse_qs(str(environ.get("QUERY_STRING") or ""), keep_blank_values=True)
    include_diagnostics = str((query.get("include_diagnostics") or [""])[0]).casefold() in {
        "1",
        "true",
        "yes",
    }
    rendered = render_dashboard_page(
        snapshot,
        path,
        include_diagnostics=include_diagnostics,
        query={key: str(values[0]) for key, values in query.items() if values},
    )
    return f"{rendered.status_code} {rendered.reason}", rendered.body.encode("utf-8")


def _dashboard_unavailable(exc: DashboardLoadError) -> tuple[str, bytes]:
    safe = _escape_text(str(exc))
    payload = (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>Dashboard unavailable</title></head>"
        f"<body><h1>Dashboard unavailable</h1><p>{safe}</p></body></html>"
    ).encode("utf-8")
    return "503 Service Unavailable", payload


def _dashboard_headers(payload: bytes) -> list[tuple[str, str]]:
    return [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(payload))),
        ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
        (
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; "
            "base-uri 'none'; frame-ancestors 'none'",
        ),
    ]


def serve_dashboard(
    artifact_base_dir: str | Path,
    artifact_namespace: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    generation_binding: DashboardGenerationBinding | None = None,
) -> None:
    """Serve the local dashboard until interrupted."""

    if str(host).strip().casefold() not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("radar dashboard only binds to a loopback host")
    app = RadarDashboardApp(
        artifact_base_dir,
        artifact_namespace,
        generation_binding=generation_binding,
    )
    with _make_dashboard_server(host, int(port), app) as server:
        print(f"Crypto Radar dashboard: http://{host}:{int(port)}/")
        print(f"Artifact namespace: {artifact_namespace} (read-only)")
        server.serve_forever()


def _make_dashboard_server(
    host: str,
    port: int,
    app: RadarDashboardApp,
    *,
    handler_class: type[WSGIRequestHandler] = WSGIRequestHandler,
) -> WSGIServer:
    return make_server(
        host,
        int(port),
        app,
        server_class=_ThreadingWSGIServer,
        handler_class=handler_class,
    )


def _escape_text(value: str) -> str:
    import html

    return html.escape(value, quote=True)


def _require_generation_binding(
    snapshot: DashboardSnapshot,
    binding: DashboardGenerationBinding | None,
) -> None:
    if binding is None:
        return
    observed = {
        "artifact_namespace": snapshot.artifact_namespace,
        "run_id": snapshot.run_id,
        "revision": snapshot.revision,
        "operator_state_sha256": snapshot.operator_state_sha256,
    }
    expected = {
        "artifact_namespace": binding.artifact_namespace,
        "run_id": binding.run_id,
        "revision": binding.revision,
        "operator_state_sha256": binding.operator_state_sha256,
    }
    mismatches = tuple(field for field, value in expected.items() if observed[field] != value)
    if mismatches:
        fields = ",".join(mismatches)
        raise DashboardLoadError(
            "dashboard pointer generation changed after startup; "
            f"refusing request (mismatched {fields})"
        )
    if not snapshot.generation_authoritative:
        reasons = ",".join(snapshot.generation_authority_reasons[:6]) or "unknown"
        raise DashboardLoadError(
            "dashboard pointer generation is no longer authoritative; "
            f"refusing request ({reasons})"
        )


__all__ = ("DashboardGenerationBinding", "RadarDashboardApp", "serve_dashboard")
