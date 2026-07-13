"""Command-line surface for guarded market/no-send generation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from ... import config
from ..dashboard.readiness import DashboardReadinessError
from . import market_no_send
from . import market_no_send_attempt
from . import market_observation_campaign


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=market_no_send.__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("readiness", "run", "smoke", "publish", "status", "audit"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--artifact-base", default=str(config.EVENT_ALPHA_ARTIFACT_BASE_DIR))
        sub.add_argument(
            "--namespace",
            default=(
                market_no_send.DEFAULT_SMOKE_NAMESPACE
                if command == "smoke"
                else market_no_send.DEFAULT_NAMESPACE
            ),
        )
        sub.add_argument("--top-n", type=int, default=market_no_send.DEFAULT_TOP_N)
        sub.add_argument("--fetch-limit", type=int, default=None)
        if command in {"smoke", "audit"}:
            sub.add_argument("--observed-at", default=None)
    campaign = subparsers.add_parser(
        "campaign-report",
        help="build the artifact-derived Decision Radar campaign report without providers",
    )
    campaign.add_argument(
        "--artifact-base",
        default=str(config.EVENT_ALPHA_ARTIFACT_BASE_DIR),
    )
    campaign.add_argument("--output-dir", default="research")
    campaign.add_argument("--evaluated-at", default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "campaign-report":
            json_path, markdown_path, report = (
                market_observation_campaign.write_campaign_report(
                    args.artifact_base,
                    args.output_dir,
                    evaluated_at=args.evaluated_at,
                )
            )
            metrics = report["campaign_metrics"]
            print(
                "radar_market_campaign_report: "
                f"status={report['campaign_status']} "
                f"real_cycles={metrics['real_cycles']} "
                f"real_candidates={metrics['real_candidates']} "
                f"json={json_path} markdown={markdown_path} provider_calls=0"
            )
            return 0
        if args.command == "readiness":
            result = market_no_send.build_market_no_send_readiness(
                artifact_base_dir=args.artifact_base,
                artifact_namespace=args.namespace,
                top_n=args.top_n,
                fetch_limit=args.fetch_limit,
            )
            print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
            return 0
        if args.command == "publish":
            published = market_no_send.publish_market_no_send_generation(
                args.artifact_base,
                args.namespace,
            )
            snapshot = published.snapshot
            print(
                "radar_market_no_send_published: "
                f"namespace={snapshot.artifact_namespace} run_id={snapshot.run_id} "
                f"revision={snapshot.revision} pointer={published.pointer_path.name}"
            )
            return 0
        if args.command == "status":
            status = market_no_send.market_no_send_generation_status(
                args.artifact_base,
                args.namespace,
            )
            print(json.dumps(status, indent=2, sort_keys=True))
            return 0 if status["complete"] else 1
        if args.command == "audit":
            json_path, markdown_path, audit = market_no_send.write_market_no_send_pilot_audit(
                args.artifact_base,
                args.namespace,
                now=args.observed_at,
            )
            print(
                "radar_market_no_send_audit: "
                f"status={audit['attempt_status']} publication={audit['publication']['status']} "
                f"json={json_path} markdown={markdown_path}"
            )
            return 0
        if args.command == "smoke":
            rows = market_no_send._smoke_rows()
            result = market_no_send.run_market_no_send_generation(
                artifact_base_dir=args.artifact_base,
                artifact_namespace=args.namespace,
                profile="fixture",
                run_mode="fixture",
                top_n=min(args.top_n, len(rows)),
                fetch_limit=args.fetch_limit,
                provider=lambda _limit: rows,
                observed_at=args.observed_at or "2026-06-15T16:00:00Z",
                environ={},
                fixture_dir=None,
                data_mode="mock",
                allow_non_live=True,
            )
        else:
            result = market_no_send.run_market_no_send_generation(
                artifact_base_dir=args.artifact_base,
                artifact_namespace=args.namespace,
                top_n=args.top_n,
                fetch_limit=args.fetch_limit,
            )
            base = market_no_send._validated_artifact_base(args.artifact_base)
            market_no_send_attempt.record_attempt(base, args.namespace, result)
        json_path, markdown_path, _audit = market_no_send.write_market_no_send_pilot_audit(
            args.artifact_base,
            args.namespace,
            result=result,
            now=getattr(args, "observed_at", None),
        )
        payload = result.to_dict()
        payload["audit_json_path"] = str(json_path)
        payload["audit_markdown_path"] = str(markdown_path)
        print(json.dumps(payload, indent=2, sort_keys=True))
        if result.complete or result.status == "blocked":
            return 0
        return 1
    except Exception as exc:  # fail closed and retain one sanitized run-attempt row
        if args.command == "run":
            try:
                requested = Path(args.artifact_base).expanduser().resolve()
                canonical = Path(config.EVENT_ALPHA_ARTIFACT_BASE_DIR).expanduser().resolve()
                if requested == canonical:
                    base = market_no_send._validated_artifact_base(requested)
                    market_no_send_attempt.record_boundary_failure(
                        base, args.namespace, failure=exc,
                        manifest_filename=market_no_send.RUN_MANIFEST_FILENAME,
                    )
            except Exception:
                pass
        detail = (
            str(exc)
            if isinstance(exc, (market_no_send.MarketNoSendError, DashboardReadinessError))
            else type(exc).__name__
        )
        print(f"radar_market_no_send_blocked: {detail}", file=sys.stderr)
        return 1


__all__ = ("main",)
