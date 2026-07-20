"""Exact read-once snapshots for the Decision Radar campaign report."""

from __future__ import annotations

import hashlib
import stat
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import market_no_send_publication
from .market_no_send_io import (
    parse_json_object_bytes,
    parse_jsonl_bytes,
    read_regular_bytes,
)
from .market_no_send_models import MarketNoSendError


def capture_bound_jsonl_snapshot(
    namespace_dir: Path,
    *,
    manifest: Mapping[str, Any],
    operator_state: Mapping[str, Any],
    use_legacy_operator_binding: bool,
    artifact: str,
    manifest_prefix: str,
    manifest_row_count_field: str,
    operator_artifact_name: str,
    expected_row_count: int,
    snapshot_label: str,
    require_legacy_count: bool = False,
) -> dict[str, Any]:
    """Capture one exact JSONL buffer and revalidate its declared binding."""

    if (
        isinstance(expected_row_count, bool)
        or not isinstance(expected_row_count, int)
        or expected_row_count < 0
    ):
        raise MarketNoSendError(f"{snapshot_label}_snapshot_row_count_invalid")
    raw = read_regular_bytes(namespace_dir / artifact)
    if raw is None:
        raise MarketNoSendError(f"{snapshot_label}_snapshot_missing")
    digest = hashlib.sha256(raw).hexdigest()
    rows = parse_jsonl_bytes(raw)
    if len(rows) != expected_row_count:
        raise MarketNoSendError(f"{snapshot_label}_snapshot_row_count_mismatch")

    if use_legacy_operator_binding:
        _validate_legacy_operator_identity(
            operator_state,
            namespace_dir=namespace_dir,
            manifest=manifest,
            snapshot_label=snapshot_label,
        )
        binding = _mapping(
            _mapping(operator_state.get("artifacts")).get(operator_artifact_name)
        )
        expected_digest = binding.get("sha256")
        binding_source = f"legacy_operator_{snapshot_label}_binding"
        if any((
            binding.get("status") != "current",
            binding.get("path") != artifact,
            binding.get("run_id") != manifest.get("run_id"),
            (
                binding.get("count") != len(rows)
                if require_legacy_count or binding.get("count") is not None
                else False
            ),
            binding.get("item_count") != len(rows),
            binding.get("size_bytes") != len(raw),
        )):
            raise MarketNoSendError(
                f"{snapshot_label}_snapshot_legacy_binding_mismatch"
            )
    else:
        expected_digest = manifest.get(f"{manifest_prefix}_artifact_sha256")
        binding_source = f"manifest_{manifest_prefix}_artifact_sha256"
        if manifest.get(f"{manifest_prefix}_artifact") != artifact:
            raise MarketNoSendError(f"{snapshot_label}_snapshot_artifact_mismatch")
        if manifest.get(manifest_row_count_field) != len(rows):
            raise MarketNoSendError(
                f"{snapshot_label}_snapshot_manifest_row_count_mismatch"
            )
    if not _sha256_digest(expected_digest) or expected_digest != digest:
        raise MarketNoSendError(f"{snapshot_label}_snapshot_digest_mismatch")
    return {
        "artifact": artifact,
        "sha256": digest,
        "size_bytes": len(raw),
        "row_count": len(rows),
        "binding_source": binding_source,
        "rows": tuple(dict(row) for row in rows),
        "verified": True,
    }


def capture_candidate_snapshot(
    namespace_dir: Path,
    *,
    manifest: Mapping[str, Any],
    validation: market_no_send_publication.CampaignGenerationValidation,
    operator_state: Mapping[str, Any],
) -> dict[str, Any]:
    """Read and bind a validated candidate artifact into one immutable snapshot."""

    return capture_bound_jsonl_snapshot(
        namespace_dir,
        manifest=manifest,
        operator_state=operator_state,
        use_legacy_operator_binding=(
            validation.legacy_adapter
            and manifest.get("candidate_artifact_sha256") in (None, "")
        ),
        artifact=market_no_send_publication.INTEGRATED_CANDIDATES_FILENAME,
        manifest_prefix="candidate",
        manifest_row_count_field="candidate_count",
        operator_artifact_name="integrated_candidates",
        expected_row_count=validation.candidate_count,
        snapshot_label="candidate",
        require_legacy_count=True,
    )


def capture_market_source_snapshot(
    namespace_dir: Path,
    *,
    manifest: Mapping[str, Any],
    artifact: str,
) -> dict[str, Any]:
    """Read and bind the exact normalized market-source envelope once.

    The countable-generation validator has already established the full
    publication contract.  This second, read-once boundary exists so campaign
    diagnostics are derived from the same bytes whose digest is stored in the
    immutable generation manifest, rather than from a later directory scan or
    the dashboard's intentionally smaller market projection.
    """

    if manifest.get("request_cache_artifact") != artifact:
        raise MarketNoSendError("market_source_snapshot_artifact_mismatch")
    raw = read_regular_bytes(namespace_dir / artifact)
    if raw is None:
        raise MarketNoSendError("market_source_snapshot_missing")
    digest = hashlib.sha256(raw).hexdigest()
    if not _sha256_digest(manifest.get("request_cache_sha256")) or (
        manifest.get("request_cache_sha256") != digest
    ):
        raise MarketNoSendError("market_source_snapshot_digest_mismatch")
    source = parse_json_object_bytes(raw)
    rows = source.get("rows")
    expected_row_count = manifest.get("selected_market_row_count")
    if (
        isinstance(expected_row_count, bool)
        or not isinstance(expected_row_count, int)
        or expected_row_count < 0
        or not isinstance(rows, list)
        or len(rows) != expected_row_count
        or not all(isinstance(row, Mapping) for row in rows)
    ):
        raise MarketNoSendError("market_source_snapshot_row_count_mismatch")
    identity_fields = (
        "artifact_namespace",
        "run_id",
        "profile",
        "run_mode",
        "data_mode",
        "provider",
        "observed_at",
        "selected_market_row_count",
    )
    if (
        source.get("row_type") != "event_market_no_send_source_cache"
        or any(source.get(field) != manifest.get(field) for field in identity_fields)
        or source.get("no_send") is not True
        or source.get("research_only") is not True
    ):
        raise MarketNoSendError("market_source_snapshot_identity_mismatch")
    return {
        "artifact": artifact,
        "sha256": digest,
        "size_bytes": len(raw),
        "row_count": len(rows),
        "binding_source": "manifest_request_cache_sha256",
        "rows": tuple(dict(row) for row in rows),
        "verified": True,
    }


def capture_generation_snapshots(
    namespace_dir: Path,
    *,
    manifest: Mapping[str, Any],
    validation: market_no_send_publication.CampaignGenerationValidation,
    operator_state: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Capture every bound generation JSONL from one operator-state view."""

    candidate = capture_candidate_snapshot(
        namespace_dir,
        manifest=manifest,
        validation=validation,
        operator_state=operator_state,
    )
    core = _supporting_snapshot(
        namespace_dir,
        manifest=manifest,
        operator_state=operator_state,
        use_legacy_operator_binding=validation.legacy_adapter,
        bound=validation.core_artifact_bound,
        expected_row_count=validation.core_artifact_row_count,
        artifact=market_no_send_publication.CORE_OPPORTUNITIES_FILENAME,
        manifest_prefix="core",
        operator_artifact_name="core_opportunities",
        snapshot_label="core",
    )
    integrated_outcome = _supporting_snapshot(
        namespace_dir,
        manifest=manifest,
        operator_state=operator_state,
        use_legacy_operator_binding=validation.legacy_adapter,
        bound=validation.integrated_outcome_artifact_bound,
        expected_row_count=validation.integrated_outcome_artifact_row_count,
        artifact=market_no_send_publication.INTEGRATED_OUTCOMES_FILENAME,
        manifest_prefix="integrated_outcome",
        operator_artifact_name="integrated_outcomes",
        snapshot_label="integrated_outcome",
    )
    return {
        "candidate": candidate,
        "core": core,
        "integrated_outcome": integrated_outcome,
    }


def campaign_outcome_ledger_snapshot(
    base: Path,
    *,
    history_namespace: str,
    filename: str,
) -> dict[str, Any]:
    """Read the mutable campaign outcome ledger into one exact byte snapshot."""

    return _campaign_jsonl_snapshot(
        base,
        history_namespace=history_namespace,
        filename=filename,
        binding_source="campaign_outcome_ledger_exact_bytes",
        missing_binding_source="campaign_outcome_ledger_path",
    )


def campaign_market_history_snapshot(
    base: Path,
    *,
    history_namespace: str,
    filename: str,
) -> dict[str, Any]:
    """Read retained campaign prices into one exact byte snapshot."""

    return _campaign_jsonl_snapshot(
        base,
        history_namespace=history_namespace,
        filename=filename,
        binding_source="campaign_market_history_exact_bytes",
        missing_binding_source="campaign_market_history_path",
    )


def _campaign_jsonl_snapshot(
    base: Path,
    *,
    history_namespace: str,
    filename: str,
    binding_source: str,
    missing_binding_source: str,
) -> dict[str, Any]:
    """Read one mutable campaign JSONL artifact exactly once and fail closed."""

    if not _safe_path_segment(history_namespace) or not _safe_path_segment(filename):
        return _campaign_snapshot_metadata(
            filename=None,
            status="unavailable",
            binding_source=missing_binding_source,
        )
    path = base / history_namespace / filename
    try:
        parent = path.parent.lstat()
    except FileNotFoundError:
        return _campaign_snapshot_metadata(
            filename=filename,
            status="missing",
            binding_source=missing_binding_source,
        )
    except OSError:
        return _campaign_snapshot_metadata(
            filename=filename,
            status="unavailable",
            binding_source=missing_binding_source,
        )
    if not stat.S_ISDIR(parent.st_mode) or stat.S_ISLNK(parent.st_mode):
        return _campaign_snapshot_metadata(
            filename=filename,
            status="unavailable",
            binding_source=missing_binding_source,
        )
    try:
        raw = read_regular_bytes(path, missing_ok=True)
        if raw is None:
            return _campaign_snapshot_metadata(
                filename=filename,
                status="missing",
                binding_source=missing_binding_source,
            )
        rows = parse_jsonl_bytes(raw)
    except (MarketNoSendError, OSError, TypeError, ValueError):
        return _campaign_snapshot_metadata(
            filename=filename,
            status="unavailable",
            binding_source=missing_binding_source,
        )
    return {
        "rows": tuple(dict(row) for row in rows),
        "status": "observed" if rows else "observed_empty",
        "artifact": filename,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "row_count": len(rows),
        "binding_source": binding_source,
    }


def generation_candidate_rows(
    generation: Mapping[str, Any],
) -> tuple[dict[str, Any], ...] | None:
    """Return an already-verified private candidate snapshot when present."""

    rows = generation.get("_candidate_snapshot_rows")
    if not isinstance(rows, (list, tuple)) or generation.get(
        "_candidate_snapshot_verified"
    ) is not True:
        return None
    if not all(isinstance(row, Mapping) for row in rows):
        return None
    return tuple(dict(row) for row in rows)


def private_generation_snapshot_fields(
    snapshots: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Project exact snapshots into private report-construction fields."""

    fields: dict[str, Any] = {}
    for label in ("candidate", "core", "integrated_outcome"):
        snapshot = _mapping(snapshots.get(label))
        rows = snapshot.get("rows")
        fields.update({
            f"_{label}_snapshot_rows": tuple(
                dict(row) for row in rows
            ) if isinstance(rows, (list, tuple)) else (),
            f"_{label}_snapshot_artifact": snapshot.get("artifact"),
            f"_{label}_snapshot_sha256": snapshot.get("sha256"),
            f"_{label}_snapshot_size_bytes": snapshot.get("size_bytes"),
            f"_{label}_snapshot_row_count": snapshot.get("row_count"),
            f"_{label}_snapshot_binding_source": snapshot.get("binding_source"),
            f"_{label}_snapshot_verified": snapshot.get("verified") is True,
        })
    return fields


def public_generation_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Remove exact-snapshot implementation fields from persisted reports."""

    return [
        {
            key: value
            for key, value in row.items()
            if not (type(key) is str and key.startswith("_"))
        }
        for row in rows
    ]


def _supporting_snapshot(
    namespace_dir: Path,
    *,
    manifest: Mapping[str, Any],
    operator_state: Mapping[str, Any],
    use_legacy_operator_binding: bool,
    bound: bool,
    expected_row_count: int,
    artifact: str,
    manifest_prefix: str,
    operator_artifact_name: str,
    snapshot_label: str,
) -> dict[str, Any]:
    if not bound:
        return {
            "artifact": artifact,
            "sha256": None,
            "size_bytes": None,
            "row_count": 0,
            "binding_source": "not_bound",
            "rows": (),
            "verified": False,
        }
    return capture_bound_jsonl_snapshot(
        namespace_dir,
        manifest=manifest,
        operator_state=operator_state,
        use_legacy_operator_binding=use_legacy_operator_binding,
        artifact=artifact,
        manifest_prefix=manifest_prefix,
        manifest_row_count_field=f"{manifest_prefix}_artifact_row_count",
        operator_artifact_name=operator_artifact_name,
        expected_row_count=expected_row_count,
        snapshot_label=snapshot_label,
    )


def _validate_legacy_operator_identity(
    operator_state: Mapping[str, Any],
    *,
    namespace_dir: Path,
    manifest: Mapping[str, Any],
    snapshot_label: str,
) -> None:
    if any((
        operator_state.get("artifact_namespace") != namespace_dir.name,
        operator_state.get("run_id") != manifest.get("run_id"),
        operator_state.get("profile") != manifest.get("profile"),
        operator_state.get("run_mode") != manifest.get("run_mode"),
        operator_state.get("market_no_send_provenance")
        != manifest.get("market_provenance"),
    )):
        raise MarketNoSendError(
            f"{snapshot_label}_snapshot_legacy_operator_identity_mismatch"
        )


def _campaign_snapshot_metadata(
    *,
    filename: str | None,
    status: str,
    binding_source: str,
) -> dict[str, Any]:
    return {
        "rows": (),
        "status": status,
        "artifact": filename,
        "sha256": None,
        "size_bytes": None,
        "row_count": 0,
        "binding_source": binding_source,
    }


def _safe_path_segment(value: object) -> bool:
    return (
        type(value) is str
        and value not in {"", ".", ".."}
        and Path(value).name == value
    )


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sha256_digest(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


__all__ = (
    "campaign_market_history_snapshot",
    "campaign_outcome_ledger_snapshot",
    "capture_bound_jsonl_snapshot",
    "capture_candidate_snapshot",
    "capture_generation_snapshots",
    "capture_market_source_snapshot",
    "generation_candidate_rows",
    "private_generation_snapshot_fields",
    "public_generation_rows",
)
