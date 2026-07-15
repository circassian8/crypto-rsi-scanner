"""Exact read-once snapshots for the Decision Radar campaign report."""

from __future__ import annotations

import hashlib
import stat
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..radar.integrated import api as integrated_radar
from . import market_no_send_publication
from .market_no_send_io import (
    parse_jsonl_bytes,
    read_json_object,
    read_regular_bytes,
)
from .market_no_send_models import MarketNoSendError


def capture_candidate_snapshot(
    namespace_dir: Path,
    *,
    manifest: Mapping[str, Any],
    validation: market_no_send_publication.CampaignGenerationValidation,
    operator_state_filename: str,
) -> dict[str, Any]:
    """Read and bind a validated candidate artifact into one immutable snapshot."""

    artifact = integrated_radar.INTEGRATED_CANDIDATES_FILENAME
    raw = read_regular_bytes(namespace_dir / artifact)
    if raw is None:
        raise MarketNoSendError("candidate_snapshot_missing")
    digest = hashlib.sha256(raw).hexdigest()
    rows = parse_jsonl_bytes(raw)
    if len(rows) != validation.candidate_count:
        raise MarketNoSendError("candidate_snapshot_row_count_mismatch")
    expected = manifest.get("candidate_artifact_sha256")
    binding_source = "manifest_candidate_artifact_sha256"
    if validation.legacy_adapter and expected in (None, ""):
        operator = _read_json(namespace_dir / operator_state_filename)
        if any((
            operator.get("artifact_namespace") != namespace_dir.name,
            operator.get("run_id") != manifest.get("run_id"),
            operator.get("profile") != manifest.get("profile"),
            operator.get("run_mode") != manifest.get("run_mode"),
            operator.get("market_no_send_provenance")
            != manifest.get("market_provenance"),
        )):
            raise MarketNoSendError(
                "candidate_snapshot_legacy_operator_identity_mismatch"
            )
        binding = _mapping(
            _mapping(operator.get("artifacts")).get("integrated_candidates")
        )
        expected = binding.get("sha256")
        binding_source = "legacy_operator_candidate_binding"
        if (
            binding.get("status") != "current"
            or binding.get("path") != artifact
            or binding.get("run_id") != manifest.get("run_id")
            or binding.get("count") != len(rows)
            or binding.get("item_count") != len(rows)
            or binding.get("size_bytes") != len(raw)
        ):
            raise MarketNoSendError("candidate_snapshot_legacy_binding_mismatch")
    elif manifest.get("candidate_artifact") != artifact:
        raise MarketNoSendError("candidate_snapshot_artifact_mismatch")
    if not _sha256_digest(expected) or expected != digest:
        raise MarketNoSendError("candidate_snapshot_digest_mismatch")
    return {
        "artifact": artifact,
        "sha256": digest,
        "size_bytes": len(raw),
        "binding_source": binding_source,
        "rows": tuple(dict(row) for row in rows),
    }


def campaign_outcome_ledger_snapshot(
    base: Path,
    *,
    history_namespace: str,
    filename: str,
) -> dict[str, Any]:
    """Read the mutable campaign outcome ledger into one exact byte snapshot."""

    path = base / history_namespace / filename
    try:
        parent = path.parent.lstat()
    except FileNotFoundError:
        return {"rows": (), "status": "missing", "sha256": None}
    except OSError:
        return {"rows": (), "status": "unavailable", "sha256": None}
    if not stat.S_ISDIR(parent.st_mode) or stat.S_ISLNK(parent.st_mode):
        return {"rows": (), "status": "unavailable", "sha256": None}
    try:
        raw = read_regular_bytes(path, missing_ok=True)
        if raw is None:
            return {"rows": (), "status": "missing", "sha256": None}
        rows = parse_jsonl_bytes(raw)
    except (MarketNoSendError, OSError, TypeError, ValueError):
        return {"rows": (), "status": "unavailable", "sha256": None}
    return {
        "rows": tuple(dict(row) for row in rows),
        "status": "observed" if rows else "observed_empty",
        "sha256": hashlib.sha256(raw).hexdigest(),
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


def public_generation_rows(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Remove exact-snapshot implementation fields from persisted reports."""

    return [
        {
            key: value
            for key, value in row.items()
            if not (type(key) is str and key.startswith("_candidate_snapshot_"))
        }
        for row in rows
    ]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return read_json_object(path)
    except (MarketNoSendError, OSError):
        return {}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sha256_digest(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


__all__ = (
    "campaign_outcome_ledger_snapshot",
    "capture_candidate_snapshot",
    "generation_candidate_rows",
    "public_generation_rows",
)
