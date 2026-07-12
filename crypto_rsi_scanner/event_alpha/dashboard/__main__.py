"""CLI entrypoint for the local read-only radar dashboard."""

from __future__ import annotations

import argparse
import json
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
    parser.add_argument(
        "--smoke-now",
        default=None,
        help="Deterministic as-of timestamp for smoke loading only; serving always uses wall UTC.",
    )
    args = parser.parse_args(argv)
    if args.smoke:
        return _smoke(Path(args.artifact_base), args.namespace, now=args.smoke_now)
    serve_dashboard(args.artifact_base, args.namespace, host=args.host, port=args.port)
    return 0


def _smoke(artifact_base: Path, namespace: str, *, now: str | None = None) -> int:
    smoke_now = now or _fixture_smoke_now(artifact_base, namespace)
    snapshot = load_dashboard_snapshot(artifact_base, namespace, now=smoke_now)
    if not snapshot.generation_authoritative:
        reasons = ",".join(snapshot.generation_authority_reasons) or "unknown"
        raise SystemExit(f"dashboard smoke failed: generation is not authoritative ({reasons})")
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


def _fixture_smoke_now(artifact_base: Path, namespace: str) -> str | None:
    state_path = artifact_base / namespace / "event_alpha_operator_state.json"
    try:
        parsed = json.loads(state_path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    state = parsed if isinstance(parsed, dict) else {}
    if str(state.get("run_mode") or "").casefold() != "fixture":
        return None
    doctor = state.get("doctor") if isinstance(state.get("doctor"), dict) else {}
    return str(doctor.get("verified_at") or state.get("updated_at") or "") or None


if __name__ == "__main__":
    raise SystemExit(main())
