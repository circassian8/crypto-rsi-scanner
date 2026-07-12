"""CLI entrypoint for the local read-only radar dashboard."""

from __future__ import annotations

import argparse
from pathlib import Path

from .app import serve_dashboard
from .loader import candidate_identifier, load_dashboard_snapshot
from .render import render_dashboard_page


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the local read-only Event Alpha radar dashboard.")
    parser.add_argument("--artifact-base", default="event_fade_cache")
    parser.add_argument("--namespace", default="no_key_live")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--smoke", action="store_true", help="Render every page without starting a server or writing files.")
    args = parser.parse_args(argv)
    if args.smoke:
        return _smoke(Path(args.artifact_base), args.namespace)
    serve_dashboard(args.artifact_base, args.namespace, host=args.host, port=args.port)
    return 0


def _smoke(artifact_base: Path, namespace: str) -> int:
    snapshot = load_dashboard_snapshot(artifact_base, namespace)
    routes = ["/", "/anomalies", "/catalysts", "/fade-risk", "/calendar", "/health", "/feedback-outcomes"]
    first_id = next((candidate_identifier(row) for row in snapshot.current_candidates if candidate_identifier(row)), "")
    if first_id:
        routes.append(f"/candidate/{first_id}")
    for route in routes:
        response = render_dashboard_page(snapshot, route, include_diagnostics=True)
        if response.status_code != 200 or "Research idea, not a trade instruction" not in response.body:
            raise SystemExit(f"dashboard smoke failed: {route} status={response.status_code}")
        if snapshot.run_id not in response.body or f"revision {snapshot.revision}" not in response.body:
            raise SystemExit(f"dashboard smoke lost operator identity: {route}")
    print(
        "radar_dashboard_smoke: "
        f"pages={len(routes)} run_id={snapshot.run_id} revision={snapshot.revision} "
        f"current_candidates={snapshot.current_generation_count} writes=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
