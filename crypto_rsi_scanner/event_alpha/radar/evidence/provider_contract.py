"""Closed provider-hint contract for Event Alpha evidence acquisition.

The deterministic evidence planner emits these logical provider hints. Runtime
dispatch and read-only readiness use the same catalog so a newly introduced
hint cannot quietly fall through to a fixture-backed default provider.
"""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping, Sequence

from ...providers import provider_health_core


PLANNER_PROVIDER_HINTS = (
    "coinmarketcal",
    "coinalyze",
    "cryptopanic",
    "gdelt",
    "official_exchange",
    "polymarket",
    "project_blog_rss",
    "sports_fixtures",
    "tokenomist",
)

RUNTIME_PROVIDER_ALIASES = (
    "binance_announcements",
    "bybit_announcements",
    "rss",
)

FIXTURE_DISPATCH_HINTS = (
    "default",
    "fixture",
    *PLANNER_PROVIDER_HINTS,
    *RUNTIME_PROVIDER_ALIASES,
)


CURRENT_AUTHORIZATION_ENV_BY_SETTING: Mapping[str, str] = {
    "EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE": (
        "RSI_EVENT_DISCOVERY_BINANCE_ANNOUNCEMENTS_LIVE"
    ),
    "EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE": (
        "RSI_EVENT_DISCOVERY_BYBIT_ANNOUNCEMENTS_LIVE"
    ),
    "EVENT_DISCOVERY_CRYPTOPANIC_LIVE": "RSI_EVENT_DISCOVERY_CRYPTOPANIC_LIVE",
    "EVENT_DISCOVERY_COINALYZE_LIVE": "RSI_EVENT_DISCOVERY_COINALYZE_LIVE",
    "EVENT_DISCOVERY_GDELT_LIVE": "RSI_EVENT_DISCOVERY_GDELT_LIVE",
    "EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE": (
        "RSI_EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE"
    ),
    "EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE": (
        "RSI_EVENT_DISCOVERY_PROJECT_BLOG_RSS_LIVE"
    ),
    "EVENT_DISCOVERY_UNIVERSE_LIVE": "RSI_EVENT_DISCOVERY_UNIVERSE_LIVE",
    "EVENT_LLM_ENABLED": "RSI_EVENT_LLM_ENABLED",
    "EVENT_LLM_EXTRACTOR_ENABLED": "RSI_EVENT_LLM_EXTRACTOR_ENABLED",
    "EVENT_LLM_CATALYST_FRAMES_ENABLED": (
        "RSI_EVENT_LLM_CATALYST_FRAMES_ENABLED"
    ),
}

_NONLIVE_PATH_MARKERS = frozenset({"fixture", "fixtures", "mock", "mocks", "replay", "replays", "test", "tests"})


def explicit_live_authorizations(
    environ: Mapping[str, str] | None = None,
) -> dict[str, bool]:
    """Return current opt-in flags without treating profile defaults as consent."""

    source = os.environ if environ is None else environ
    return {
        setting: _truthy(source.get(env_name))
        for setting, env_name in CURRENT_AUTHORIZATION_ENV_BY_SETTING.items()
    }


def configured_local_path_status(path_value: object) -> str:
    """Classify one local evidence path for non-fixture runtime use.

    Fixture-like paths are rejected before existence checks so a checked-in
    replay cannot become production evidence merely because it is a regular
    file. The filename and exact directory components are inspected; arbitrary
    temporary parent names such as ``test_run0`` are deliberately not matched.
    """

    if path_value in (None, ""):
        return "not_configured"
    path = Path(path_value).expanduser()
    directory_parts = tuple(part.casefold() for part in path.parts[:-1])
    filename_tokens = frozenset(
        token for token in re.split(r"[^a-z0-9]+", path.stem.casefold()) if token
    )
    if any(part in _NONLIVE_PATH_MARKERS for part in directory_parts) or (
        filename_tokens & _NONLIVE_PATH_MARKERS
    ):
        return "fixture_or_test_path_rejected"
    try:
        info = path.lstat()
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "unreadable"
    if stat.S_ISLNK(info.st_mode):
        return "symlink_rejected"
    return "regular_file" if stat.S_ISREG(info.st_mode) else "not_regular_file"


def matching_provider_health_status(
    aliases: Sequence[str],
    health_rows: Mapping[str, Mapping[str, Any]],
    *,
    now: datetime,
) -> tuple[str, str | None]:
    """Project persisted health with the same alias matching in all surfaces."""

    matched: list[Mapping[str, Any]] = []
    folded = {alias.casefold() for alias in aliases}
    for key, row in health_rows.items():
        values = " ".join(
            str(value or "").casefold()
            for value in (
                key,
                row.get("provider"),
                row.get("provider_key"),
                row.get("provider_service"),
            )
        )
        if any(alias in values for alias in folded):
            matched.append(row)
    if not matched:
        return "not_observed", None
    statuses = [
        provider_health_core.provider_health_status(row, now=now) for row in matched
    ]
    disabled = [
        str(row.get("disabled_until"))
        for row in matched
        if row.get("disabled_until")
    ]
    if "backoff" in statuses:
        return "backoff", max(disabled) if disabled else None
    if "degraded" in statuses:
        return "degraded", max(disabled) if disabled else None
    return "healthy", max(disabled) if disabled else None


def persisted_health_blocks_provider(
    status: str,
    *,
    ignore_backoff: bool,
) -> bool:
    """Fail closed on degraded/backoff unless the explicit override is active."""

    return status in {"backoff", "degraded"} and not ignore_backoff


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


__all__ = (
    "CURRENT_AUTHORIZATION_ENV_BY_SETTING",
    "FIXTURE_DISPATCH_HINTS",
    "PLANNER_PROVIDER_HINTS",
    "RUNTIME_PROVIDER_ALIASES",
    "configured_local_path_status",
    "explicit_live_authorizations",
    "matching_provider_health_status",
    "persisted_health_blocks_provider",
)
