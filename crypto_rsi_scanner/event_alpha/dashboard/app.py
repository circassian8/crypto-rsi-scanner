"""GET-only WSGI application for the local Event Alpha radar dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import parse_qs, unquote
from wsgiref.simple_server import make_server

from .loader import load_dashboard_snapshot
from .models import DashboardLoadError
from .render import render_dashboard_page


StartResponse = Callable[[str, list[tuple[str, str]]], object]


class RadarDashboardApp:
    """Small read-only WSGI app backed by exact operator generations."""

    def __init__(self, artifact_base_dir: str | Path, artifact_namespace: str) -> None:
        self.artifact_base_dir = Path(artifact_base_dir).expanduser()
        self.artifact_namespace = str(artifact_namespace)

    def __call__(self, environ: dict[str, object], start_response: StartResponse) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD") or "GET").upper()
        if method not in {"GET", "HEAD"}:
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
        try:
            snapshot = load_dashboard_snapshot(self.artifact_base_dir, self.artifact_namespace)
            path = unquote(str(environ.get("PATH_INFO") or "/"))
            query = parse_qs(str(environ.get("QUERY_STRING") or ""), keep_blank_values=True)
            include_diagnostics = str((query.get("include_diagnostics") or [""])[0]).casefold() in {
                "1",
                "true",
                "yes",
            }
            rendered = render_dashboard_page(snapshot, path, include_diagnostics=include_diagnostics)
            payload = rendered.body.encode("utf-8")
            status = f"{rendered.status_code} {rendered.reason}"
        except DashboardLoadError as exc:
            safe = _escape_text(str(exc))
            payload = (
                "<!doctype html><html><head><meta charset=\"utf-8\"><title>Dashboard unavailable</title></head>"
                f"<body><h1>Dashboard unavailable</h1><p>{safe}</p></body></html>"
            ).encode("utf-8")
            status = "503 Service Unavailable"
        start_response(
            status,
            [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(payload))),
                ("Cache-Control", "no-store"),
                ("X-Content-Type-Options", "nosniff"),
                ("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'"),
            ],
        )
        return [b"" if method == "HEAD" else payload]


def serve_dashboard(
    artifact_base_dir: str | Path,
    artifact_namespace: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    """Serve the local dashboard until interrupted."""

    if str(host).strip().casefold() not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("radar dashboard only binds to a loopback host")
    app = RadarDashboardApp(artifact_base_dir, artifact_namespace)
    with make_server(host, int(port), app) as server:
        print(f"Crypto Radar dashboard: http://{host}:{int(port)}/")
        print(f"Artifact namespace: {artifact_namespace} (read-only)")
        server.serve_forever()


def _escape_text(value: str) -> str:
    import html

    return html.escape(value, quote=True)


__all__ = ("RadarDashboardApp", "serve_dashboard")
