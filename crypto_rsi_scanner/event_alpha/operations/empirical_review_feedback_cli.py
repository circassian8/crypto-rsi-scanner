"""Explicit CLI boundary for optional empirical review feedback."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from ..artifacts.json_lines import loads_no_duplicate_keys
from . import empirical_replay_store, empirical_review_feedback


QUEUE_ARTIFACT = "targeted_review_queue.json"
MAX_QUEUE_BYTES = 2 * 1024 * 1024


def load_verified_queue(run_dir: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load a queue only through its complete immutable replay run."""

    manifest, payloads = empirical_replay_store.load_verified_run(run_dir)
    payload = payloads.get(QUEUE_ARTIFACT)
    if payload is None or len(payload) > MAX_QUEUE_BYTES:
        raise RuntimeError("empirical_review_queue_missing_or_oversized")
    try:
        raw = loads_no_duplicate_keys(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("empirical_review_queue_invalid") from exc
    if not isinstance(raw, Mapping):
        raise RuntimeError("empirical_review_queue_invalid")
    queue = dict(raw)
    if payload != empirical_replay_store.canonical_json_bytes(queue):
        raise RuntimeError("empirical_review_queue_noncanonical")
    if queue.get("run_fingerprint") != manifest.get("run_fingerprint"):
        raise RuntimeError("empirical_review_queue_run_mismatch")
    if queue.get("protocol_sha256") != manifest.get("protocol_sha256"):
        raise RuntimeError("empirical_review_queue_protocol_mismatch")
    return queue, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect or explicitly append optional Decision Radar empirical review feedback."
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--ledger", required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    report = subparsers.add_parser("report", help="Read a bounded descriptive feedback report")
    report.add_argument("--maximum-events", type=int, default=256)

    mark = subparsers.add_parser("mark", help="Append one human-supplied review label")
    mark.add_argument("--review-item-id", required=True)
    mark.add_argument("--label", required=True)
    mark.add_argument("--observed-at", required=True)
    mark.add_argument("--reviewer-alias", required=True)
    mark.add_argument("--label-event-id")
    mark.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)

    queue, manifest = load_verified_queue(args.run_dir)
    if args.command == "report":
        events = empirical_review_feedback.read_feedback_ledger(args.ledger, queue)
        result = empirical_review_feedback.build_feedback_report(
            queue,
            events,
            maximum_events=args.maximum_events,
        )
    else:
        event = empirical_review_feedback.build_feedback_event(
            queue,
            review_item_id=args.review_item_id,
            label=args.label,
            observed_at=args.observed_at,
            reviewer_alias=args.reviewer_alias,
            label_event_id=args.label_event_id,
        )
        result = empirical_review_feedback.append_feedback_event(
            args.ledger,
            queue,
            event,
            confirm=args.confirm,
        )
    output = {
        **result,
        "immutable_run_fingerprint": manifest["run_fingerprint"],
        "provider_calls": 0,
        "dashboard_authority_mutations": 0,
        "production_policy_mutations": 0,
        "research_only": True,
        "auto_apply": False,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["load_verified_queue", "main"]
