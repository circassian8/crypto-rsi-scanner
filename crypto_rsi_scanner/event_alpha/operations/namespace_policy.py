"""Namespace selection policy for Event Alpha burn-in measurement."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..namespace import status as namespace_status
from . import common
from .daily_burn_in import RUN_JSON


POLICY_JSON = "event_alpha_burn_in_namespace_policy.json"
POLICY_MD = "event_alpha_burn_in_namespace_policy.md"
POLICY_VERSION = "burn_in_namespace_policy_v2"

ACTIVE_BURN_IN_STATUSES = {
    "active_burn_in",
    "active_no_send_burn_in",
}
DEFAULT_EXCLUDED_STATUSES = {
    namespace_status.STATUS_ACTIVE_FIXTURE_SMOKE,
    namespace_status.STATUS_STALE_DEPRECATED,
    namespace_status.STATUS_ARCHIVED,
    namespace_status.STATUS_QUARANTINE,
}
PROVIDER_REHEARSAL_STATUSES = {
    namespace_status.STATUS_ACTIVE_PROVIDER_PREFLIGHT,
    namespace_status.STATUS_ACTIVE_PROVIDER_REHEARSAL,
}
KEY_ARTIFACTS = (
    RUN_JSON,
    "event_alpha_runs.jsonl",
    "event_integrated_radar_candidates.jsonl",
    "event_core_opportunities.jsonl",
    "event_alpha_feedback.jsonl",
    "event_integrated_radar_outcomes.jsonl",
    "event_alpha_outcomes.jsonl",
)


@dataclass(frozen=True)
class NamespaceSelection:
    namespace: str
    path: Path
    status: str
    include: bool
    include_reason: str
    exclusion_reasons: tuple[str, ...]
    latest_doctor_status: str
    latest_run_id: str
    artifact_counts: Mapping[str, int]


def build_namespace_policy(
    *,
    profile: str = "live_burn_in_no_send",
    artifact_namespace: str | None = None,
    base_dir: str | Path | None = None,
    include_notification_rehearsals: bool = False,
    include_no_key_namespaces: bool = False,
    include_provider_rehearsals: bool = False,
    include_fixture_namespaces: bool = False,
    include_stale_namespaces: bool = False,
    include_namespaces: Iterable[str] = (),
    write: bool = True,
) -> dict[str, Any]:
    """Resolve namespaces that are valid burn-in evidence inputs."""

    output_namespace = artifact_namespace or profile
    context = common.context_for(profile=profile, artifact_namespace=output_namespace, base_dir=base_dir)
    selections = select_namespaces(
        context.base_dir,
        include_notification_rehearsals=include_notification_rehearsals,
        include_no_key_namespaces=include_no_key_namespaces,
        include_provider_rehearsals=include_provider_rehearsals,
        include_fixture_namespaces=include_fixture_namespaces,
        include_stale_namespaces=include_stale_namespaces,
        include_namespaces=include_namespaces,
    )
    included = [item for item in selections if item.include]
    excluded = [item for item in selections if not item.include]
    fixture_included = [item.namespace for item in included if _is_fixture_namespace(item.namespace, item.status)]
    live_included = [item.namespace for item in included if not _is_fixture_namespace(item.namespace, item.status)]
    policy = common.with_safety(
        {
            "schema_version": "event_alpha_burn_in_namespace_policy_v1",
            "row_type": "event_alpha_burn_in_namespace_policy",
            "namespace_policy_version": POLICY_VERSION,
            "generated_at": common.utc_now().isoformat(),
            "profile": profile,
            "artifact_namespace": context.artifact_namespace,
            "namespace_dir": common.rel_path(context.namespace_dir),
            "base_dir": common.rel_path(context.base_dir),
            "default_include_statuses": sorted(ACTIVE_BURN_IN_STATUSES),
            "default_exclude_statuses": sorted(DEFAULT_EXCLUDED_STATUSES),
            "include_notification_rehearsals": bool(include_notification_rehearsals),
            "include_no_key_namespaces": bool(include_no_key_namespaces),
            "include_provider_rehearsals": bool(include_provider_rehearsals),
            "include_fixture_namespaces": bool(include_fixture_namespaces),
            "include_stale_namespaces": bool(include_stale_namespaces),
            "explicit_inclusion_flags": {
                "include_notification_rehearsals": bool(include_notification_rehearsals),
                "include_no_key_namespaces": bool(include_no_key_namespaces),
                "include_provider_rehearsals": bool(include_provider_rehearsals),
                "include_fixture_namespaces": bool(include_fixture_namespaces),
                "include_stale_namespaces": bool(include_stale_namespaces),
                "include_namespace": sorted(str(item) for item in include_namespaces if str(item).strip()),
            },
            "explicit_include_namespaces": sorted(str(item) for item in include_namespaces if str(item).strip()),
            "included_namespaces": [item.namespace for item in included],
            "excluded_namespaces": [item.namespace for item in excluded],
            "exclusion_reasons": {item.namespace: list(item.exclusion_reasons) for item in excluded},
            "excluded_reasons": {item.namespace: list(item.exclusion_reasons) for item in excluded},
            "include_reasons": {item.namespace: item.include_reason for item in included},
            "namespace_status": {item.namespace: item.status for item in selections},
            "latest_doctor_status": {item.namespace: item.latest_doctor_status for item in selections},
            "latest_run_id": {item.namespace: item.latest_run_id for item in selections if item.latest_run_id},
            "artifact_counts": {item.namespace: dict(item.artifact_counts) for item in selections},
            "included_namespace_details": [_selection_row(item) for item in included],
            "excluded_namespace_details": [_selection_row(item) for item in excluded],
            "no_active_burn_in_namespaces": len(included) == 0,
            "active_live_rehearsal_excluded_count": _excluded_count(excluded, "active_live_rehearsal"),
            "notification_rehearsal_excluded_count": _excluded_count(excluded, "notification_rehearsal"),
            "no_key_excluded_count": _excluded_count(excluded, "no_key"),
            "fixture_excluded_count": _excluded_count(excluded, "fixture"),
            "provider_rehearsal_excluded_count": _excluded_count(excluded, "provider_rehearsal"),
            "fixture_live_mix_blocker": bool(fixture_included and live_included),
            "fixture_namespaces_included": fixture_included,
            "live_namespaces_included": live_included,
        }
    )
    if write:
        common.write_json(context.namespace_dir / POLICY_JSON, policy)
        common.write_text(context.namespace_dir / POLICY_MD, format_namespace_policy(policy))
    return policy


def select_namespaces(
    base_dir: str | Path,
    *,
    include_notification_rehearsals: bool = False,
    include_no_key_namespaces: bool = False,
    include_provider_rehearsals: bool = False,
    include_fixture_namespaces: bool = False,
    include_stale_namespaces: bool = False,
    include_namespaces: Iterable[str] = (),
) -> list[NamespaceSelection]:
    base = Path(base_dir).expanduser()
    explicit = {str(item).strip() for item in include_namespaces if str(item).strip()}
    namespace_paths: dict[str, Path] = {
        path.name: path
        for path in sorted(base.iterdir() if base.exists() else [], key=lambda item: item.name)
        if path.is_dir()
    }
    for name in explicit:
        namespace_paths.setdefault(name, base / name)
    selections = [
        _selection_for(
            namespace,
            path,
            explicit=explicit,
            include_notification_rehearsals=include_notification_rehearsals,
            include_no_key_namespaces=include_no_key_namespaces,
            include_provider_rehearsals=include_provider_rehearsals,
            include_fixture_namespaces=include_fixture_namespaces,
            include_stale_namespaces=include_stale_namespaces,
        )
        for namespace, path in sorted(namespace_paths.items())
    ]
    return selections


def included_namespace_names(policy: Mapping[str, Any]) -> list[str]:
    return [str(item) for item in policy.get("included_namespaces") or [] if str(item)]


def format_namespace_policy(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Event Alpha Burn-In Namespace Policy",
        "",
        "Research-only namespace scope for burn-in measurement and archives.",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- profile: `{payload.get('profile')}`",
        f"- artifact_namespace: `{payload.get('artifact_namespace')}`",
        f"- namespace_policy_version: `{payload.get('namespace_policy_version')}`",
        f"- included_namespaces: `{', '.join(payload.get('included_namespaces') or []) or 'none'}`",
        f"- excluded_namespaces: `{len(payload.get('excluded_namespaces') or [])}`",
        f"- include_notification_rehearsals: `{payload.get('include_notification_rehearsals')}`",
        f"- include_no_key_namespaces: `{payload.get('include_no_key_namespaces')}`",
        f"- include_provider_rehearsals: `{payload.get('include_provider_rehearsals')}`",
        f"- include_fixture_namespaces: `{payload.get('include_fixture_namespaces')}`",
        f"- include_stale_namespaces: `{payload.get('include_stale_namespaces')}`",
        f"- active_live_rehearsal_excluded_count: `{payload.get('active_live_rehearsal_excluded_count')}`",
        f"- no_key_excluded_count: `{payload.get('no_key_excluded_count')}`",
        f"- fixture_excluded_count: `{payload.get('fixture_excluded_count')}`",
        f"- provider_rehearsal_excluded_count: `{payload.get('provider_rehearsal_excluded_count')}`",
        f"- fixture_live_mix_blocker: `{payload.get('fixture_live_mix_blocker')}`",
        "",
        "## Included",
        "",
    ]
    for row in payload.get("included_namespace_details") or []:
        if isinstance(row, Mapping):
            lines.append(
                f"- {row.get('namespace')}: status=`{row.get('status')}` reason=`{row.get('include_reason')}` "
                f"latest_doctor_status=`{row.get('latest_doctor_status')}` latest_run_id=`{row.get('latest_run_id') or 'none'}`"
            )
    if not payload.get("included_namespace_details"):
        lines.append("- none")
    lines.extend(["", "## Excluded", ""])
    for row in payload.get("excluded_namespace_details") or []:
        if isinstance(row, Mapping):
            lines.append(
                f"- {row.get('namespace')}: status=`{row.get('status')}` reasons=`{', '.join(row.get('exclusion_reasons') or [])}`"
            )
    if not payload.get("excluded_namespace_details"):
        lines.append("- none")
    return "\n".join(lines).rstrip()


def _selection_for(
    namespace: str,
    path: Path,
    *,
    explicit: set[str],
    include_notification_rehearsals: bool,
    include_no_key_namespaces: bool,
    include_provider_rehearsals: bool,
    include_fixture_namespaces: bool,
    include_stale_namespaces: bool,
) -> NamespaceSelection:
    marker = namespace_status.load_namespace_status(path)
    status = _status_for(namespace, path, marker)
    counts = _artifact_counts(path)
    latest_run_id = _latest_run_id(path, marker)
    latest_doctor_status = (marker.current_doctor_status if marker else None) or "unknown"
    has_daily_burn_in_artifact = counts.get(RUN_JSON, 0) > 0
    has_run_ledger = counts.get("event_alpha_runs.jsonl", 0) > 0
    has_burn_in_evidence = has_daily_burn_in_artifact or has_run_ledger
    categories = _namespace_categories(namespace, status, path, has_burn_in_evidence)
    reasons: list[str] = []
    include = False
    include_reason = ""

    if namespace in explicit:
        if _is_stale_status(status) and not include_stale_namespaces:
            reasons.append("explicit_namespace_is_stale_requires_include_stale")
        else:
            include = True
            include_reason = "explicit_user_namespace"
    elif _category_allowed_by_explicit_flag(
        categories,
        include_notification_rehearsals=include_notification_rehearsals,
        include_no_key_namespaces=include_no_key_namespaces,
        include_provider_rehearsals=include_provider_rehearsals,
        include_fixture_namespaces=include_fixture_namespaces,
        include_stale_namespaces=include_stale_namespaces,
    ):
        include = True
        include_reason = _category_include_reason(
            categories,
            include_notification_rehearsals=include_notification_rehearsals,
            include_no_key_namespaces=include_no_key_namespaces,
            include_provider_rehearsals=include_provider_rehearsals,
            include_fixture_namespaces=include_fixture_namespaces,
            include_stale_namespaces=include_stale_namespaces,
        )
    elif _blocked_default_categories(
        categories,
        include_notification_rehearsals=include_notification_rehearsals,
        include_no_key_namespaces=include_no_key_namespaces,
        include_provider_rehearsals=include_provider_rehearsals,
        include_fixture_namespaces=include_fixture_namespaces,
        include_stale_namespaces=include_stale_namespaces,
    ):
        reasons.extend(_default_exclusion_reasons(namespace, status, path, has_burn_in_evidence, categories))
    elif has_daily_burn_in_artifact:
        include = True
        include_reason = "daily_burn_in_run_artifact"
    elif status in ACTIVE_BURN_IN_STATUSES:
        include = True
        include_reason = f"status:{status}"
    elif namespace.startswith("live_burn_in_") and has_burn_in_evidence:
        include = True
        include_reason = "live_burn_in_namespace_with_run_evidence"

    if not include:
        reasons.extend(_default_exclusion_reasons(namespace, status, path, has_burn_in_evidence, categories))
    if include and "no_key" in categories and namespace not in explicit and not include_no_key_namespaces:
        include = False
        reasons.append("no_key_namespace_excluded_from_default_burn_in_measurement")
    if include and "notification_rehearsal" in categories and namespace not in explicit and not include_notification_rehearsals and not ("no_key" in categories and include_no_key_namespaces):
        include = False
        reasons.append("notification_rehearsal_excluded_from_default_burn_in_measurement")
    if include and "provider_rehearsal" in categories and namespace not in explicit and not include_provider_rehearsals:
        include = False
        reasons.append("provider_rehearsal_excluded_from_default_burn_in_measurement")
    if include and _is_stale_status(status) and not include_stale_namespaces:
        include = False
        reasons.append("stale_namespace_excluded_without_include_stale")
    if include and _is_fixture_namespace(namespace, status) and namespace not in explicit and not include_fixture_namespaces:
        include = False
        reasons.append("fixture_namespace_excluded_without_include_fixture")

    return NamespaceSelection(
        namespace=namespace,
        path=path,
        status=status,
        include=include,
        include_reason=include_reason if include else "",
        exclusion_reasons=tuple(dict.fromkeys(reasons)),
        latest_doctor_status=latest_doctor_status,
        latest_run_id=latest_run_id,
        artifact_counts=counts,
    )


def _selection_row(item: NamespaceSelection) -> dict[str, Any]:
    categories = sorted(_namespace_categories(item.namespace, item.status, item.path, _has_burn_in_evidence(item.artifact_counts)))
    return {
        "namespace": item.namespace,
        "path": common.rel_path(item.path),
        "status": item.status,
        "categories": categories,
        "include_reason": item.include_reason,
        "exclusion_reasons": list(item.exclusion_reasons),
        "latest_doctor_status": item.latest_doctor_status,
        "latest_run_id": item.latest_run_id,
        "artifact_counts": dict(item.artifact_counts),
    }


def _status_for(namespace: str, path: Path, marker: namespace_status.EventAlphaNamespaceStatus | None) -> str:
    if marker is not None:
        return marker.status
    lowered = namespace.casefold()
    if "stale" in lowered or lowered == "notify_llm_deep":
        return namespace_status.STATUS_STALE_DEPRECATED
    if "quarantine" in lowered:
        return namespace_status.STATUS_QUARANTINE
    if "archiv" in lowered:
        return namespace_status.STATUS_ARCHIVED
    if "fixture" in lowered or "smoke" in lowered:
        return namespace_status.STATUS_ACTIVE_FIXTURE_SMOKE
    if "provider_preflight" in lowered or lowered.endswith("_preflight") or "coinalyze_preflight" in lowered:
        return namespace_status.STATUS_ACTIVE_PROVIDER_PREFLIGHT
    if "provider_rehearsal" in lowered or "no_send_rehearsal" in lowered or lowered.endswith("_rehearsal"):
        return namespace_status.STATUS_ACTIVE_PROVIDER_REHEARSAL
    if namespace.startswith("live_burn_in_") and ((path / RUN_JSON).exists() or (path / "event_alpha_runs.jsonl").exists()):
        return "active_no_send_burn_in"
    if namespace == "no_key_live":
        return "no_key_live"
    return namespace_status.STATUS_UNKNOWN


def _artifact_counts(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name in KEY_ARTIFACTS:
        target = path / name
        if not target.exists():
            counts[name] = 0
        elif target.suffix == ".jsonl":
            counts[name] = len(common.read_jsonl(target))
        else:
            counts[name] = 1
    return counts


def _latest_run_id(path: Path, marker: namespace_status.EventAlphaNamespaceStatus | None) -> str:
    if marker and marker.latest_run_id:
        return marker.latest_run_id
    runs = common.read_jsonl(path / "event_alpha_runs.jsonl")
    for row in reversed(runs):
        value = row.get("run_id") or row.get("id") or row.get("started_at") or row.get("generated_at")
        if value:
            return str(value)
    daily = common.read_json(path / RUN_JSON)
    return str(daily.get("run_id") or daily.get("generated_at") or "")


def _default_exclusion_reasons(namespace: str, status: str, path: Path, has_burn_in_evidence: bool, categories: set[str] | None = None) -> list[str]:
    reasons: list[str] = []
    categories = categories or _namespace_categories(namespace, status, path, has_burn_in_evidence)
    lowered = namespace.casefold()
    if "active_live_rehearsal" in categories:
        reasons.append("active_live_rehearsal_not_burn_in")
    if "notification_rehearsal" in categories:
        reasons.append("notification_rehearsal_excluded_from_default_burn_in_measurement")
    if "no_key" in categories:
        reasons.append("no_key_namespace_excluded_from_default_burn_in_measurement")
    if namespace == "no_key_live":
        reasons.append("no_key_live_excluded_from_default_burn_in_measurement")
    if "provider_rehearsal" in categories:
        reasons.append("provider_rehearsal_excluded_from_default_burn_in_measurement")
    if "fixture" in categories or "fixture" in lowered or "smoke" in lowered or status == namespace_status.STATUS_ACTIVE_FIXTURE_SMOKE:
        reasons.append("fixture_or_smoke_namespace_excluded_by_default")
    if _is_stale_status(status) or lowered == "notify_llm_deep":
        reasons.append("stale_or_historical_namespace_excluded_by_default")
    if status in {namespace_status.STATUS_ARCHIVED, namespace_status.STATUS_QUARANTINE}:
        reasons.append(f"inactive_namespace_status:{status}")
    if namespace.startswith("live_burn_in_") and not has_burn_in_evidence:
        reasons.append("live_burn_in_namespace_without_run_evidence")
    if not reasons and path.exists():
        reasons.append(f"status_not_in_burn_in_policy:{status}")
    if not path.exists():
        reasons.append("namespace_path_missing")
    return reasons or ["not_selected_by_burn_in_policy"]


def _namespace_categories(namespace: str, status: str, path: Path, has_burn_in_evidence: bool) -> set[str]:
    lowered = namespace.casefold()
    categories: set[str] = set()
    if lowered.startswith("notify_") or lowered == "notify":
        categories.add("notification_rehearsal")
    if "no_key" in lowered:
        categories.add("no_key")
    if _is_fixture_namespace(namespace, status) or status == namespace_status.STATUS_ACTIVE_INTEGRATED_SMOKE or lowered == "integrated_radar_smoke":
        categories.add("fixture")
    if _is_stale_status(status):
        categories.add("stale")
    if status in PROVIDER_REHEARSAL_STATUSES:
        categories.add("provider_rehearsal")
    if status == namespace_status.STATUS_ACTIVE_LIVE_REHEARSAL and not has_burn_in_evidence:
        categories.add("active_live_rehearsal")
    return categories


def _has_burn_in_evidence(counts: Mapping[str, int]) -> bool:
    return int(counts.get(RUN_JSON, 0) or 0) > 0 or int(counts.get("event_alpha_runs.jsonl", 0) or 0) > 0


def _blocked_default_categories(
    categories: set[str],
    *,
    include_notification_rehearsals: bool,
    include_no_key_namespaces: bool,
    include_provider_rehearsals: bool,
    include_fixture_namespaces: bool,
    include_stale_namespaces: bool,
) -> set[str]:
    blocked: set[str] = set()
    if "notification_rehearsal" in categories and not include_notification_rehearsals:
        blocked.add("notification_rehearsal")
    if "no_key" in categories and not include_no_key_namespaces:
        blocked.add("no_key")
    if "provider_rehearsal" in categories and not include_provider_rehearsals:
        blocked.add("provider_rehearsal")
    if "fixture" in categories and not include_fixture_namespaces:
        blocked.add("fixture")
    if "stale" in categories and not include_stale_namespaces:
        blocked.add("stale")
    if "active_live_rehearsal" in categories:
        blocked.add("active_live_rehearsal")
    return blocked


def _category_allowed_by_explicit_flag(
    categories: set[str],
    *,
    include_notification_rehearsals: bool,
    include_no_key_namespaces: bool,
    include_provider_rehearsals: bool,
    include_fixture_namespaces: bool,
    include_stale_namespaces: bool,
) -> bool:
    return bool(
        ("notification_rehearsal" in categories and include_notification_rehearsals)
        or ("no_key" in categories and include_no_key_namespaces)
        or ("provider_rehearsal" in categories and include_provider_rehearsals)
        or ("fixture" in categories and include_fixture_namespaces)
        or ("stale" in categories and include_stale_namespaces)
    )


def _category_include_reason(
    categories: set[str],
    *,
    include_notification_rehearsals: bool,
    include_no_key_namespaces: bool,
    include_provider_rehearsals: bool,
    include_fixture_namespaces: bool,
    include_stale_namespaces: bool,
) -> str:
    if "notification_rehearsal" in categories and include_notification_rehearsals:
        return "explicit_flag:include_notification_rehearsals"
    if "no_key" in categories and include_no_key_namespaces:
        return "explicit_flag:include_no_key_namespaces"
    if "provider_rehearsal" in categories and include_provider_rehearsals:
        return "explicit_flag:include_provider_rehearsals"
    if "fixture" in categories and include_fixture_namespaces:
        return "explicit_flag:include_fixture_namespaces"
    if "stale" in categories and include_stale_namespaces:
        return "explicit_flag:include_stale_namespaces"
    return "explicit_flag:include_namespace"


def _excluded_count(items: Iterable[NamespaceSelection], category: str) -> int:
    count = 0
    for item in items:
        categories = _namespace_categories(item.namespace, item.status, item.path, _has_burn_in_evidence(item.artifact_counts))
        if category in categories:
            count += 1
    return count


def _is_stale_status(status: str) -> bool:
    return status in {namespace_status.STATUS_STALE_DEPRECATED, namespace_status.STATUS_ARCHIVED, namespace_status.STATUS_QUARANTINE}


def _is_fixture_namespace(namespace: str, status: str) -> bool:
    lowered = namespace.casefold()
    return status in {namespace_status.STATUS_ACTIVE_FIXTURE_SMOKE, namespace_status.STATUS_ACTIVE_INTEGRATED_SMOKE} or "fixture" in lowered or "smoke" in lowered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write Event Alpha burn-in namespace policy artifacts.")
    parser.add_argument("--profile", default="live_burn_in_no_send")
    parser.add_argument("--artifact-namespace", default=None)
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--include-notification-rehearsals", action="store_true")
    parser.add_argument("--include-no-key-namespaces", action="store_true")
    parser.add_argument("--include-provider-rehearsals", action="store_true")
    parser.add_argument("--include-fixture-namespaces", action="store_true")
    parser.add_argument("--include-stale-namespaces", action="store_true")
    parser.add_argument("--include-namespace", action="append", default=[])
    args = parser.parse_args(argv)
    payload = build_namespace_policy(
        profile=args.profile,
        artifact_namespace=args.artifact_namespace,
        base_dir=args.base_dir,
        include_notification_rehearsals=args.include_notification_rehearsals,
        include_no_key_namespaces=args.include_no_key_namespaces,
        include_provider_rehearsals=args.include_provider_rehearsals,
        include_fixture_namespaces=args.include_fixture_namespaces,
        include_stale_namespaces=args.include_stale_namespaces,
        include_namespaces=args.include_namespace,
    )
    print(f"event_alpha_burn_in_namespace_policy: {payload['namespace_dir']}/{POLICY_MD}")
    print(f"included={len(payload['included_namespaces'])} excluded={len(payload['excluded_namespaces'])}")
    return 1 if payload.get("fixture_live_mix_blocker") else 0


if __name__ == "__main__":
    raise SystemExit(main())
