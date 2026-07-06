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

ACTIVE_BURN_IN_STATUSES = {
    namespace_status.STATUS_ACTIVE_LIVE_REHEARSAL,
    "active_burn_in",
    "active_no_send_burn_in",
}
DEFAULT_EXCLUDED_STATUSES = {
    namespace_status.STATUS_ACTIVE_FIXTURE_SMOKE,
    namespace_status.STATUS_STALE_DEPRECATED,
    namespace_status.STATUS_ARCHIVED,
    namespace_status.STATUS_QUARANTINE,
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
            "generated_at": common.utc_now().isoformat(),
            "profile": profile,
            "artifact_namespace": context.artifact_namespace,
            "namespace_dir": common.rel_path(context.namespace_dir),
            "base_dir": common.rel_path(context.base_dir),
            "default_include_statuses": sorted(ACTIVE_BURN_IN_STATUSES),
            "default_exclude_statuses": sorted(DEFAULT_EXCLUDED_STATUSES),
            "include_fixture_namespaces": bool(include_fixture_namespaces),
            "include_stale_namespaces": bool(include_stale_namespaces),
            "explicit_include_namespaces": sorted(str(item) for item in include_namespaces if str(item).strip()),
            "included_namespaces": [item.namespace for item in included],
            "excluded_namespaces": [item.namespace for item in excluded],
            "exclusion_reasons": {item.namespace: list(item.exclusion_reasons) for item in excluded},
            "include_reasons": {item.namespace: item.include_reason for item in included},
            "namespace_status": {item.namespace: item.status for item in selections},
            "latest_doctor_status": {item.namespace: item.latest_doctor_status for item in selections},
            "latest_run_id": {item.namespace: item.latest_run_id for item in selections if item.latest_run_id},
            "artifact_counts": {item.namespace: dict(item.artifact_counts) for item in selections},
            "included_namespace_details": [_selection_row(item) for item in included],
            "excluded_namespace_details": [_selection_row(item) for item in excluded],
            "no_active_burn_in_namespaces": len(included) == 0,
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
        f"- included_namespaces: `{', '.join(payload.get('included_namespaces') or []) or 'none'}`",
        f"- excluded_namespaces: `{len(payload.get('excluded_namespaces') or [])}`",
        f"- include_fixture_namespaces: `{payload.get('include_fixture_namespaces')}`",
        f"- include_stale_namespaces: `{payload.get('include_stale_namespaces')}`",
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
    include_fixture_namespaces: bool,
    include_stale_namespaces: bool,
) -> NamespaceSelection:
    marker = namespace_status.load_namespace_status(path)
    status = _status_for(namespace, path, marker)
    counts = _artifact_counts(path)
    latest_run_id = _latest_run_id(path, marker)
    latest_doctor_status = (marker.current_doctor_status if marker else None) or "unknown"
    has_burn_in_evidence = counts.get(RUN_JSON, 0) > 0 or counts.get("event_alpha_runs.jsonl", 0) > 0
    reasons: list[str] = []
    include = False
    include_reason = ""

    if namespace in explicit:
        if _is_stale_status(status) and not include_stale_namespaces:
            reasons.append("explicit_namespace_is_stale_requires_include_stale")
        elif _is_fixture_namespace(namespace, status) and not include_fixture_namespaces:
            reasons.append("explicit_fixture_namespace_requires_include_fixture")
        else:
            include = True
            include_reason = "explicit_user_namespace"
    elif status in ACTIVE_BURN_IN_STATUSES:
        include = True
        include_reason = f"status:{status}"
    elif namespace.startswith("live_burn_in_") and has_burn_in_evidence:
        include = True
        include_reason = "live_burn_in_namespace_with_run_evidence"

    if not include:
        reasons.extend(_default_exclusion_reasons(namespace, status, path, has_burn_in_evidence))
    if include and namespace == "no_key_live" and namespace not in explicit:
        include = False
        reasons.append("no_key_live_excluded_from_default_burn_in_measurement")
    if include and _is_stale_status(status) and not include_stale_namespaces:
        include = False
        reasons.append("stale_namespace_excluded_without_include_stale")
    if include and _is_fixture_namespace(namespace, status) and not include_fixture_namespaces:
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
    return {
        "namespace": item.namespace,
        "path": common.rel_path(item.path),
        "status": item.status,
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
    if "stale" in lowered or lowered.startswith("notify_llm_deep"):
        return namespace_status.STATUS_STALE_DEPRECATED
    if "quarantine" in lowered:
        return namespace_status.STATUS_QUARANTINE
    if "archiv" in lowered:
        return namespace_status.STATUS_ARCHIVED
    if "fixture" in lowered or "smoke" in lowered:
        return namespace_status.STATUS_ACTIVE_FIXTURE_SMOKE
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


def _default_exclusion_reasons(namespace: str, status: str, path: Path, has_burn_in_evidence: bool) -> list[str]:
    reasons: list[str] = []
    lowered = namespace.casefold()
    if namespace == "no_key_live":
        reasons.append("no_key_live_excluded_from_default_burn_in_measurement")
    if "fixture" in lowered or "smoke" in lowered or status == namespace_status.STATUS_ACTIVE_FIXTURE_SMOKE:
        reasons.append("fixture_or_smoke_namespace_excluded_by_default")
    if _is_stale_status(status) or lowered.startswith("notify_llm_deep"):
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


def _is_stale_status(status: str) -> bool:
    return status in {namespace_status.STATUS_STALE_DEPRECATED, namespace_status.STATUS_ARCHIVED, namespace_status.STATUS_QUARANTINE}


def _is_fixture_namespace(namespace: str, status: str) -> bool:
    lowered = namespace.casefold()
    return status == namespace_status.STATUS_ACTIVE_FIXTURE_SMOKE or "fixture" in lowered or "smoke" in lowered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write Event Alpha burn-in namespace policy artifacts.")
    parser.add_argument("--profile", default="live_burn_in_no_send")
    parser.add_argument("--artifact-namespace", default=None)
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--include-fixture-namespaces", action="store_true")
    parser.add_argument("--include-stale-namespaces", action="store_true")
    parser.add_argument("--include-namespace", action="append", default=[])
    args = parser.parse_args(argv)
    payload = build_namespace_policy(
        profile=args.profile,
        artifact_namespace=args.artifact_namespace,
        base_dir=args.base_dir,
        include_fixture_namespaces=args.include_fixture_namespaces,
        include_stale_namespaces=args.include_stale_namespaces,
        include_namespaces=args.include_namespace,
    )
    print(f"event_alpha_burn_in_namespace_policy: {payload['namespace_dir']}/{POLICY_MD}")
    print(f"included={len(payload['included_namespaces'])} excluded={len(payload['excluded_namespaces'])}")
    return 1 if payload.get("fixture_live_mix_blocker") else 0


if __name__ == "__main__":
    raise SystemExit(main())
