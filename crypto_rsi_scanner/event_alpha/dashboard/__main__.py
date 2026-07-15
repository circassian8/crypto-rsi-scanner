"""CLI entrypoint for the local read-only radar dashboard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .app import serve_dashboard
from .loader import candidate_identifier, load_dashboard_snapshot
from .models import DashboardGenerationBinding, DashboardLoadError
from .readiness import (
    DashboardReadinessError,
    _resolve_dashboard_startup,
    publish_current_namespace_pointer,
    read_current_namespace_pointer,
    resolve_authoritative_dashboard,
)
from .render import render_dashboard_page


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the local read-only Event Alpha radar dashboard.")
    parser.add_argument("--artifact-base", default="event_fade_cache")
    parser.add_argument("--namespace", default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--smoke", action="store_true", help="Render every page without starting a server or writing files.")
    parser.add_argument(
        "--readiness",
        action="store_true",
        help="Validate one exact authoritative generation and atomically update the current pointer.",
    )
    parser.add_argument(
        "--smoke-now",
        default=None,
        help="Deterministic as-of timestamp for smoke/readiness tests only; serving uses wall UTC.",
    )
    args = parser.parse_args(argv)
    try:
        if args.readiness:
            if args.smoke_now is not None:
                raise DashboardReadinessError("--smoke-now is allowed only with --smoke")
            result = publish_current_namespace_pointer(
                args.artifact_base,
                args.namespace,
            )
            snapshot = result.snapshot
            print(
                "radar_dashboard_readiness: READY "
                f"namespace={snapshot.artifact_namespace} run_id={snapshot.run_id} "
                f"revision={snapshot.revision} pointer={result.pointer_path.name}"
            )
            return 0
        effective_smoke_now = args.smoke_now
        if args.smoke and effective_smoke_now is None:
            namespace_hint = str(args.namespace or "").strip()
            if not namespace_hint:
                namespace_hint = str(
                    read_current_namespace_pointer(args.artifact_base)["artifact_namespace"]
                )
            effective_smoke_now = _fixture_smoke_now(
                Path(args.artifact_base),
                namespace_hint,
            )
        if not args.smoke and not str(args.namespace or "").strip():
            result = _resolve_dashboard_startup(args.artifact_base)
        else:
            result = resolve_authoritative_dashboard(
                args.artifact_base,
                args.namespace,
                now=effective_smoke_now if args.smoke else None,
            )
        namespace = result.snapshot.artifact_namespace
        if args.smoke:
            try:
                return _smoke(Path(args.artifact_base), namespace, now=effective_smoke_now)
            except SystemExit as exc:
                raise DashboardReadinessError(str(exc)) from exc
        generation_binding = (
            DashboardGenerationBinding.from_snapshot(result.snapshot)
            if result.namespace_source == "pointer"
            else None
        )
        serve_dashboard(
            args.artifact_base,
            namespace,
            host=args.host,
            port=args.port,
            generation_binding=generation_binding,
        )
        return 0
    except (DashboardReadinessError, DashboardLoadError, OSError, ValueError) as exc:
        reason = " ".join(str(exc).split()) or type(exc).__name__
        print(f"radar_dashboard_readiness: NOT_READY reason={reason}", file=sys.stderr)
        return 1


def _smoke(artifact_base: Path, namespace: str, *, now: str | None = None) -> int:
    smoke_now = now or _fixture_smoke_now(artifact_base, namespace)
    snapshot = load_dashboard_snapshot(artifact_base, namespace, now=smoke_now)
    if not snapshot.generation_authoritative:
        reasons = ",".join(snapshot.generation_authority_reasons) or "unknown"
        raise SystemExit(f"dashboard smoke failed: generation is not authoritative ({reasons})")
    routes = [
        "/",
        "/market-radar",
        "/ideas",
        "/calendar",
        "/health",
        "/outcomes",
        "/campaign-history",
        "/anomalies",
        "/catalysts",
        "/fade-risk",
        "/feedback-outcomes",
    ]
    first_id = next((candidate_identifier(row) for row in snapshot.current_candidates if candidate_identifier(row)), "")
    if first_id:
        routes.append(f"/ideas/{first_id}")
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
