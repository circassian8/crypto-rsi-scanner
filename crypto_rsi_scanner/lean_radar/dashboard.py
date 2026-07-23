"""Read-only local WSGI dashboard for Lean Crypto Radar."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Callable, Iterable, Mapping, Sequence
from urllib.parse import parse_qs, unquote
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from .config import load_settings
from .dashboard_data import (
    LeanDashboardDataError,
    load_dashboard_state,
    load_idea_detail,
)
from .dashboard_render import render_dashboard_page, render_unavailable
from .store import LeanRadarStore


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766
_ALLOWED_HOSTS = {"127.0.0.1", "::1", "localhost"}


@dataclass(frozen=True)
class _DashboardHttpResponse:
    status_code: int
    body: bytes
    headers: tuple[tuple[str, str], ...]


class LeanRadarDashboardApp:
    """GET/HEAD-only WSGI application with no provider or write path."""

    def __init__(self, store: LeanRadarStore) -> None:
        self.store = store

    def response(
        self,
        *,
        method: str,
        path: str,
        query_string: str = "",
    ) -> _DashboardHttpResponse:
        if method not in {"GET", "HEAD"}:
            return self._response(
                405,
                b"Method not allowed",
                extra_headers=(("Allow", "GET, HEAD"),),
                content_type="text/plain; charset=utf-8",
                head=method == "HEAD",
            )
        try:
            state = load_dashboard_state(self.store)
            detail = None
            clean_path = path if path.startswith("/") else "/"
            if clean_path.startswith("/ideas/"):
                idea_id = unquote(clean_path.removeprefix("/ideas/"))
                detail = load_idea_detail(self.store, idea_id)
            query = _query_values(query_string)
            rendered = render_dashboard_page(
                state,
                clean_path,
                query=query,
                detail=detail,
            )
        except (LeanDashboardDataError, TypeError, ValueError):
            rendered = render_unavailable(
                "The local runtime could not be validated. Run the health command for exact setup guidance."
            )
        body = rendered.body.encode("utf-8")
        return self._response(rendered.status_code, body, head=method == "HEAD")

    def __call__(
        self,
        environ: Mapping[str, object],
        start_response: Callable[[str, list[tuple[str, str]]], object],
    ) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        query = str(environ.get("QUERY_STRING", ""))
        response = self.response(method=method, path=path, query_string=query)
        start_response(_status_line(response.status_code), list(response.headers))
        return (response.body,)

    @staticmethod
    def _response(
        status_code: int,
        body: bytes,
        *,
        content_type: str = "text/html; charset=utf-8",
        extra_headers: tuple[tuple[str, str], ...] = (),
        head: bool = False,
    ) -> _DashboardHttpResponse:
        headers = (
            ("Content-Type", content_type),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("Referrer-Policy", "no-referrer"),
            ("X-Frame-Options", "DENY"),
            (
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
                "form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
            ),
            ("X-Lean-Radar-Read-Only", "true"),
            *extra_headers,
        )
        return _DashboardHttpResponse(status_code, b"" if head else body, headers)


class _ThreadingDashboardServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True
    allow_reuse_address = True


class _QuietRequestHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return None


def serve_dashboard(
    store: LeanRadarStore,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> None:
    if host not in _ALLOWED_HOSTS:
        raise LeanDashboardDataError("Lean Radar dashboard must remain loopback-only")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65_535:
        raise LeanDashboardDataError("Lean Radar dashboard port is invalid")
    load_dashboard_state(store)
    app = LeanRadarDashboardApp(store)
    with make_server(
        host,
        port,
        app,
        server_class=_ThreadingDashboardServer,
        handler_class=_QuietRequestHandler,
    ) as server:
        print(f"Lean Crypto Radar: http://{host}:{port}/")
        print("Read only · research only · no send · no trading")
        server.serve_forever()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lean Crypto Radar dashboard")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.smoke:
        from .dashboard_smoke import run_dashboard_smoke

        result = run_dashboard_smoke()
        print(json.dumps(result, indent=2, sort_keys=True) if args.json else _summary(result))
        return 0 if result["status"] == "passed" else 2
    settings = load_settings()
    store = LeanRadarStore(args.db or settings.db_path)
    if args.validate:
        try:
            state = load_dashboard_state(store)
        except LeanDashboardDataError as exc:
            result = {
                "status": "blocked",
                "reason": str(exc),
                "provider_call_attempted": False,
                "telegram_send_attempted": False,
                "research_only": True,
            }
            print(json.dumps(result, indent=2, sort_keys=True) if args.json else _summary(result))
            return 2
        result = {
            "status": "ready",
            "active_idea_count": len(state.active_ideas),
            "market_count": len(state.latest_snapshots),
            "calendar_event_count": len(state.calendar_events),
            "outcome_count": len(state.outcomes),
            "health_status": (
                state.health_status.get("status") if state.health_status else "not_run"
            ),
            "provider_call_attempted": False,
            "telegram_send_attempted": False,
            "database_write_attempted": False,
            "research_only": True,
        }
        print(json.dumps(result, indent=2, sort_keys=True) if args.json else _summary(result))
        return 0
    try:
        serve_dashboard(store, host=args.host, port=args.port)
    except (LeanDashboardDataError, OSError) as exc:
        print(f"Lean Crypto Radar dashboard blocked: {exc}")
        return 2
    return 0


def _query_values(query_string: str) -> dict[str, str]:
    parsed = parse_qs(query_string, keep_blank_values=False, max_num_fields=20)
    return {
        key: values[0][:100]
        for key, values in parsed.items()
        if isinstance(key, str) and values
    }


def _status_line(code: int) -> str:
    return {
        200: "200 OK",
        404: "404 Not Found",
        405: "405 Method Not Allowed",
        503: "503 Service Unavailable",
    }.get(code, f"{code} Error")


def _summary(result: Mapping[str, object]) -> str:
    lines = ["Lean Crypto Radar dashboard", f"Status: {result.get('status', 'unknown')}"]
    if result.get("reason"):
        lines.append(f"Reason: {result['reason']}")
    if "page_count" in result:
        lines.append(f"Pages rendered: {result['page_count']}")
    if "active_idea_count" in result:
        lines.append(
            f"Ideas: {result['active_idea_count']} · markets: {result.get('market_count', 0)} · "
            f"outcomes: {result.get('outcome_count', 0)}"
        )
    lines.append("Research only · read only · no send · no trading")
    return "\n".join(lines)


__all__ = (
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "LeanRadarDashboardApp",
    "serve_dashboard",
)


if __name__ == "__main__":
    raise SystemExit(main())
