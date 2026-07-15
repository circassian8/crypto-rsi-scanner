"""Pure identity partition helpers for shadow anomaly episodes."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence


def identity_ref_sort_key(ref: Mapping[str, Any]) -> tuple[Any, ...]:
    """Return the deterministic time-and-identity ordering key."""

    return (
        aware_time(ref.get("observed_at"))
        or datetime.min.replace(tzinfo=timezone.utc),
        str(ref.get("canonical_asset_id") or ""),
        str(ref.get("artifact_namespace") or ""),
        str(ref.get("run_id") or ""),
        str(ref.get("candidate_id") or ""),
        str(ref.get("outcome_identity_key") or ""),
        str(ref.get("market_anomaly_id") or ""),
    )


def identity_collision_errors(
    identities: Iterable[Mapping[str, str]],
) -> list[str]:
    """Return builder-impossible canonical identity collisions."""

    rows = list(identities)
    contracts = (
        (
            "ambiguous_candidate_binding",
            lambda row: (
                row["artifact_namespace"],
                row["run_id"],
                row["candidate_id"],
            ),
        ),
        (
            "ambiguous_outcome_binding",
            lambda row: (
                row["artifact_namespace"],
                row["run_id"],
                row["outcome_identity_key"],
            ),
        ),
        (
            "ambiguous_anomaly_binding",
            lambda row: (
                row["artifact_namespace"],
                row["run_id"],
                row["market_anomaly_id"],
            ),
        ),
    )
    errors: list[str] = []
    for reason, key_for in contracts:
        counts = Counter(key_for(row) for row in rows)
        if any(count > 1 for count in counts.values()):
            errors.append(reason)
    return errors


def decluster_identity_refs(
    identities: Iterable[Mapping[str, str]],
    *,
    gap_hours: int,
) -> list[list[dict[str, str]]]:
    """Form deterministic fixed-start, half-open identity groups."""

    by_asset: dict[str, list[dict[str, str]]] = defaultdict(list)
    for identity in identities:
        by_asset[identity["canonical_asset_id"]].append(dict(identity))
    groups: list[list[dict[str, str]]] = []
    for asset_id in sorted(by_asset):
        ordered = sorted(by_asset[asset_id], key=identity_ref_sort_key)
        current: list[dict[str, str]] = []
        episode_end: datetime | None = None
        for identity in ordered:
            observed = aware_time(identity["observed_at"])
            if observed is None:
                continue
            if episode_end is None or observed >= episode_end:
                if current:
                    groups.append(current)
                current = [identity]
                episode_end = safe_window_end(observed, gap_hours=gap_hours)
            else:
                current.append(identity)
        if current:
            groups.append(current)
    return sorted(groups, key=lambda group: identity_ref_sort_key(group[0]))


def identity_sensitivity_counts(
    identities: Iterable[Mapping[str, str]],
    *,
    gap_hours: Sequence[int],
) -> dict[str, dict[str, int]]:
    """Recompute every sensitivity count from the complete member set."""

    rows = list(identities)
    counts: dict[str, dict[str, int]] = {}
    for gap in gap_hours:
        episode_count = len(decluster_identity_refs(rows, gap_hours=gap))
        counts[f"{gap}h"] = {
            "episode_count": episode_count,
            "repeat_member_count": len(rows) - episode_count,
        }
    return counts


def aware_time(value: object) -> datetime | None:
    """Parse an exact timezone-aware timestamp and normalize it to UTC."""

    if type(value) is not str or value != value.strip() or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def safe_window_end(value: datetime, *, gap_hours: int) -> datetime | None:
    """Return the fixed window end, or null when datetime would overflow."""

    try:
        return value + timedelta(hours=gap_hours)
    except OverflowError:
        return None


def required_window_end(value: datetime, *, gap_hours: int) -> datetime:
    """Return the fixed window end or fail closed on datetime overflow."""

    result = safe_window_end(value, gap_hours=gap_hours)
    if result is None:
        raise ValueError("shadow anomaly episode window exceeds datetime range")
    return result


__all__ = (
    "aware_time",
    "decluster_identity_refs",
    "identity_collision_errors",
    "identity_ref_sort_key",
    "identity_sensitivity_counts",
    "required_window_end",
    "safe_window_end",
)
