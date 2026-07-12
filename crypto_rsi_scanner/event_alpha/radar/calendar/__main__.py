"""No-send CLI preview for the unified research calendar."""

from __future__ import annotations

import argparse

from .... import config
from .store import format_unified_calendar_preview, load_unified_calendar_fixture


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview fixture-backed Event Alpha calendar rows")
    parser.add_argument("--fixture", default=str(config.EVENT_ALPHA_UNIFIED_CALENDAR_FIXTURE_PATH))
    parser.add_argument("--profile", default="fixture")
    parser.add_argument("--namespace", default="unified_calendar_preview")
    parser.add_argument("--run-id", default="unified-calendar-preview")
    parser.add_argument("--observed-at", default="2026-06-15T16:00:00Z")
    args = parser.parse_args()
    rows = load_unified_calendar_fixture(
        args.fixture,
        profile=args.profile,
        artifact_namespace=args.namespace,
        run_mode="fixture_preview",
        run_id=args.run_id,
        observed_at=args.observed_at,
    )
    print(format_unified_calendar_preview(rows), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
