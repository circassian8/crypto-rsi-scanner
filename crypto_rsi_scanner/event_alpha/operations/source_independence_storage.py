"""Read-only measurements for digest-addressed source-independence storage."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from io import BytesIO
import json
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Iterable, Mapping, Sequence
import zipfile
import zlib

from ..artifacts import fingerprints
from ..radar import source_independence_store
from . import market_no_send_io
from .market_no_send_models import MarketNoSendError


ARTIFACT_FILENAMES = (
    "event_integrated_radar_candidates.jsonl",
    "event_integrated_radar_outcomes.jsonl",
    "event_core_opportunities.jsonl",
    "event_integrated_radar_notification_deliveries.jsonl",
    "event_alpha_alerts.jsonl",
    "event_evidence_acquisition.jsonl",
    "event_impact_hypotheses.jsonl",
    "event_incidents.jsonl",
    "event_watchlist_state.jsonl",
    "candidate_snapshots.jsonl",
)
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_REFERENCES = 10_000
MAX_NODES = 500_000
MAX_STORE_ITEMS = 10_000
MAX_STORE_BYTES = 256 * 1024 * 1024
NAMESPACE_ZIP_MEASUREMENT_SCOPE = (
    "standalone_selected_namespace_artifacts_and_complete_source_store_v1"
)
_NAMESPACE_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_NAMESPACE_ZIP_COMPRESSION_LEVEL = 6


class _SourceIndependenceStorageReportError(RuntimeError):
    """Raised when a bounded read-only measurement cannot be trusted."""


# Public compatibility alias without adding a second public ownership class.
SourceIndependenceStorageReportError = _SourceIndependenceStorageReportError


@dataclass(frozen=True)
class SourceIndependenceStorageReport:
    namespace: str
    artifacts_scanned: int
    artifact_bytes_with_references: int
    inline_equivalent_artifact_bytes: int
    reference_occurrences: int
    unique_contracts: int
    source_store_items: int
    source_store_bytes: int
    unreferenced_store_items: int
    total_bytes_with_store: int
    inline_equivalent_total_bytes: int
    storage_reduction_bytes: int
    storage_reduction_percent: float
    referenced_contract_read_ms: float
    referenced_contract_reads_per_second: float
    estimated_export_deflate_bytes_with_store: int
    estimated_export_deflate_bytes_inline: int
    estimated_export_deflate_reduction_bytes: int
    namespace_zip_measurement_scope: str
    measured_namespace_zip_members_with_store: int
    measured_namespace_zip_members_inline: int
    measured_namespace_zip_bytes_with_store: int
    measured_namespace_zip_bytes_inline: int
    measured_namespace_zip_reduction_bytes: int
    measured_namespace_zip_reduction_percent: float
    measurement_status: str
    research_only: bool = True
    provider_calls: int = 0
    writes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_namespace(
    namespace_dir: str | Path,
) -> SourceIndependenceStorageReport:
    """Measure JSONL amplification and a deterministic namespace-only ZIP."""

    base = Path(namespace_dir).expanduser().absolute()
    if not base.is_dir():
        raise SourceIndependenceStorageReportError("namespace_missing")
    raw_files, references, artifacts_scanned = _scan_namespace_artifacts(base)
    unique_references, resolved, elapsed_ns = _resolve_unique_references(
        base,
        references,
    )
    hydrated_files = _hydrate_artifact_files(raw_files, resolved)
    source_store_items, source_store_bytes, store_blobs = _measure_store(
        base,
        referenced_contract_count=len(unique_references),
    )
    return _build_storage_report(
        base=base,
        raw_files=raw_files,
        hydrated_files=hydrated_files,
        references=references,
        unique_reference_count=len(unique_references),
        artifacts_scanned=artifacts_scanned,
        elapsed_ns=elapsed_ns,
        source_store_items=source_store_items,
        source_store_bytes=source_store_bytes,
        store_blobs=store_blobs,
    )


def _scan_namespace_artifacts(
    base: Path,
) -> tuple[list[tuple[str, bytes]], list[dict[str, Any]], int]:
    raw_files: list[tuple[str, bytes]] = []
    references: list[dict[str, Any]] = []
    total_input_bytes = 0
    for filename in ARTIFACT_FILENAMES:
        path = base / filename
        try:
            raw = market_no_send_io.read_regular_bytes(path, missing_ok=True)
        except MarketNoSendError as exc:
            raise SourceIndependenceStorageReportError(
                f"artifact_unreadable:{filename}"
            ) from exc
        if raw is None:
            continue
        if len(raw) > MAX_ARTIFACT_BYTES:
            raise SourceIndependenceStorageReportError(
                f"artifact_size_limit_exceeded:{filename}"
            )
        total_input_bytes += len(raw)
        if total_input_bytes > MAX_TOTAL_BYTES:
            raise SourceIndependenceStorageReportError("total_size_limit_exceeded")
        try:
            rows = market_no_send_io.parse_jsonl_bytes(raw)
        except MarketNoSendError as exc:
            raise SourceIndependenceStorageReportError(
                f"artifact_jsonl_invalid:{filename}"
            ) from exc
        for row in rows:
            references.extend(_references_in(row))
            if len(references) > MAX_REFERENCES:
                raise SourceIndependenceStorageReportError(
                    "reference_limit_exceeded"
                )
        raw_files.append((filename, raw))
    return raw_files, references, len(raw_files)


def _resolve_unique_references(
    base: Path,
    references: Sequence[Mapping[str, Any]],
) -> tuple[
    dict[tuple[str, str], dict[str, Any]],
    dict[tuple[str, str], dict[str, Any]],
    int,
]:
    unique_references: dict[tuple[str, str], dict[str, Any]] = {}
    for reference in references:
        errors = source_independence_store.validate_reference(reference)
        if errors:
            raise SourceIndependenceStorageReportError(
                "reference_invalid:" + ",".join(errors)
            )
        fingerprint = reference["blob_fingerprint"]
        key = (reference["contract_digest"], fingerprint["sha256"])
        existing = unique_references.get(key)
        if existing is not None and existing != reference:
            raise SourceIndependenceStorageReportError(
                "reference_summary_ambiguous"
            )
        unique_references[key] = reference

    started = perf_counter_ns()
    try:
        resolved = {
            key: source_independence_store.resolve(base, reference)
            for key, reference in unique_references.items()
        }
    except source_independence_store.SourceIndependenceStoreError as exc:
        raise SourceIndependenceStorageReportError(str(exc)) from exc
    elapsed_ns = max(0, perf_counter_ns() - started)
    return unique_references, resolved, elapsed_ns


def _hydrate_artifact_files(
    raw_files: Sequence[tuple[str, bytes]],
    resolved: Mapping[tuple[str, str], Mapping[str, Any]],
) -> list[tuple[str, bytes]]:
    hydrated_files: list[tuple[str, bytes]] = []
    for filename, raw in raw_files:
        rows = market_no_send_io.parse_jsonl_bytes(raw)
        hydrated = [_hydrate_from_cache(row, resolved) for row in rows]
        hydrated_files.append(
            (
                filename,
                (
                    ("\n".join(_compact_json(row) for row in hydrated) + "\n")
                    if hydrated
                    else ""
                ).encode("utf-8"),
            )
        )
    return hydrated_files


def _measure_store(
    base: Path,
    *,
    referenced_contract_count: int,
) -> tuple[int, int, tuple[tuple[str, bytes], ...]]:
    store_dir = base / source_independence_store.STORE_DIRECTORY
    if store_dir.exists():
        try:
            store_fingerprint = fingerprints.fingerprint_path(store_dir)
        except fingerprints.FingerprintError as exc:
            raise SourceIndependenceStorageReportError(
                "store_fingerprint_failed"
            ) from exc
        source_store_items = int(store_fingerprint["item_count"])
        source_store_bytes = int(store_fingerprint["size_bytes"])
        store_blobs = _read_store_blobs(store_dir)
        if (
            len(store_blobs) != source_store_items
            or sum(len(raw) for _name, raw in store_blobs) != source_store_bytes
        ):
            raise SourceIndependenceStorageReportError(
                "store_changed_during_measurement"
            )
    else:
        source_store_items = 0
        source_store_bytes = 0
        store_blobs = ()
    if referenced_contract_count and source_store_items == 0:
        raise SourceIndependenceStorageReportError("referenced_store_missing")
    if source_store_items < referenced_contract_count:
        raise SourceIndependenceStorageReportError("store_item_count_incomplete")
    return source_store_items, source_store_bytes, tuple(store_blobs)


def _build_storage_report(
    *,
    base: Path,
    raw_files: Sequence[tuple[str, bytes]],
    hydrated_files: Sequence[tuple[str, bytes]],
    references: Sequence[Mapping[str, Any]],
    unique_reference_count: int,
    artifacts_scanned: int,
    elapsed_ns: int,
    source_store_items: int,
    source_store_bytes: int,
    store_blobs: Sequence[tuple[str, bytes]],
) -> SourceIndependenceStorageReport:
    artifact_bytes = sum(len(raw) for _name, raw in raw_files)
    inline_bytes = sum(len(raw) for _name, raw in hydrated_files)
    total_with_store = artifact_bytes + source_store_bytes
    reduction = inline_bytes - total_with_store
    reduction_percent = (
        round((reduction / inline_bytes) * 100.0, 3) if inline_bytes else 0.0
    )
    elapsed_ms = elapsed_ns / 1_000_000.0
    reads_per_second = (
        round(unique_reference_count / (elapsed_ns / 1_000_000_000.0), 3)
        if elapsed_ns and unique_reference_count
        else 0.0
    )
    compressed_with_store = sum(
        _deflate_size(raw) for _name, raw in raw_files
    ) + sum(
        _deflate_size(raw) for _name, raw in store_blobs
    )
    compressed_inline = sum(
        _deflate_size(raw) for _name, raw in hydrated_files
    )
    referenced_zip_members = tuple(raw_files) + tuple(
        (f"{source_independence_store.STORE_DIRECTORY}/{name}", raw)
        for name, raw in store_blobs
    )
    inline_zip_members = tuple(hydrated_files)
    measured_zip_with_store = _deterministic_namespace_zip_size(
        referenced_zip_members
    )
    measured_zip_inline = _deterministic_namespace_zip_size(inline_zip_members)
    measured_zip_reduction = measured_zip_inline - measured_zip_with_store
    measured_zip_reduction_percent = (
        round((measured_zip_reduction / measured_zip_inline) * 100.0, 3)
        if measured_zip_inline
        else 0.0
    )
    return SourceIndependenceStorageReport(
        namespace=base.name,
        artifacts_scanned=artifacts_scanned,
        artifact_bytes_with_references=artifact_bytes,
        inline_equivalent_artifact_bytes=inline_bytes,
        reference_occurrences=len(references),
        unique_contracts=unique_reference_count,
        source_store_items=source_store_items,
        source_store_bytes=source_store_bytes,
        unreferenced_store_items=max(0, source_store_items - unique_reference_count),
        total_bytes_with_store=total_with_store,
        inline_equivalent_total_bytes=inline_bytes,
        storage_reduction_bytes=reduction,
        storage_reduction_percent=reduction_percent,
        referenced_contract_read_ms=round(elapsed_ms, 3),
        referenced_contract_reads_per_second=reads_per_second,
        estimated_export_deflate_bytes_with_store=compressed_with_store,
        estimated_export_deflate_bytes_inline=compressed_inline,
        estimated_export_deflate_reduction_bytes=(
            compressed_inline - compressed_with_store
        ),
        namespace_zip_measurement_scope=NAMESPACE_ZIP_MEASUREMENT_SCOPE,
        measured_namespace_zip_members_with_store=len(referenced_zip_members),
        measured_namespace_zip_members_inline=len(inline_zip_members),
        measured_namespace_zip_bytes_with_store=measured_zip_with_store,
        measured_namespace_zip_bytes_inline=measured_zip_inline,
        measured_namespace_zip_reduction_bytes=measured_zip_reduction,
        measured_namespace_zip_reduction_percent=(
            measured_zip_reduction_percent
        ),
        measurement_status="measured_read_only",
    )


def format_report(report: SourceIndependenceStorageReport) -> str:
    return "\n".join(
        (
            "Source-independence storage (read-only)",
            f"namespace: {report.namespace}",
            f"artifacts_scanned: {report.artifacts_scanned}",
            f"reference_occurrences: {report.reference_occurrences}",
            f"unique_contracts: {report.unique_contracts}",
            f"bytes_inline_equivalent: {report.inline_equivalent_total_bytes}",
            f"bytes_referenced_artifacts_plus_store: {report.total_bytes_with_store}",
            f"storage_reduction_bytes: {report.storage_reduction_bytes}",
            f"storage_reduction_percent: {report.storage_reduction_percent:.3f}",
            f"store_growth: items={report.source_store_items} bytes={report.source_store_bytes}",
            f"unreferenced_store_items: {report.unreferenced_store_items}",
            f"read_performance_ms: {report.referenced_contract_read_ms:.3f}",
            f"namespace_zip_measurement_scope: {report.namespace_zip_measurement_scope}",
            (
                "measured_namespace_zip_members: "
                f"inline={report.measured_namespace_zip_members_inline} "
                f"referenced_plus_store={report.measured_namespace_zip_members_with_store}"
            ),
            (
                "measured_namespace_zip_bytes: "
                f"inline={report.measured_namespace_zip_bytes_inline} "
                f"referenced_plus_store={report.measured_namespace_zip_bytes_with_store}"
            ),
            (
                "measured_namespace_zip_reduction: "
                f"bytes={report.measured_namespace_zip_reduction_bytes} "
                f"percent={report.measured_namespace_zip_reduction_percent:.3f}"
            ),
            "namespace_zip_note: standalone selected-namespace measurement; not whole-project archive size",
            (
                "estimated_export_deflate_reduction_bytes "
                "(compatibility payload-only estimate): "
                f"{report.estimated_export_deflate_reduction_bytes}"
            ),
            "provider_calls: 0",
            "writes: 0",
        )
    )


def _references_in(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    stack = [value]
    visited = 0
    while stack:
        current = stack.pop()
        visited += 1
        if visited > MAX_NODES:
            raise SourceIndependenceStorageReportError("node_limit_exceeded")
        if isinstance(current, Mapping):
            if current.get("schema_id") == source_independence_store.REFERENCE_SCHEMA_ID:
                found.append(dict(current))
                continue
            stack.extend(current.values())
        elif isinstance(current, (list, tuple)):
            stack.extend(current)
    return found


def _hydrate_from_cache(
    value: Any,
    contracts: Mapping[tuple[str, str], Mapping[str, Any]],
) -> Any:
    if isinstance(value, Mapping):
        if value.get("schema_id") == source_independence_store.REFERENCE_SCHEMA_ID:
            fingerprint = value.get("blob_fingerprint")
            key = (
                str(value.get("contract_digest") or ""),
                str(fingerprint.get("sha256") or "")
                if isinstance(fingerprint, Mapping)
                else "",
            )
            contract = contracts.get(key)
            if contract is None:
                raise SourceIndependenceStorageReportError(
                    "reference_not_resolved"
                )
            return dict(contract)
        return {
            key: _hydrate_from_cache(item, contracts)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_hydrate_from_cache(item, contracts) for item in value]
    return value


def _compact_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _deflate_size(raw: bytes) -> int:
    return len(zlib.compress(raw, level=9))


def _deterministic_namespace_zip_size(
    members: Iterable[tuple[str, bytes]],
) -> int:
    """Return exact bytes for a deterministic in-memory namespace-only ZIP."""

    ordered = sorted(members, key=lambda item: item[0])
    names = [name for name, _raw in ordered]
    if len(names) != len(set(names)):
        raise SourceIndependenceStorageReportError(
            "namespace_zip_member_name_duplicate"
        )
    output = BytesIO()
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=_NAMESPACE_ZIP_COMPRESSION_LEVEL,
    ) as archive:
        for name, raw in ordered:
            member = zipfile.ZipInfo(name, date_time=_NAMESPACE_ZIP_TIMESTAMP)
            member.compress_type = zipfile.ZIP_DEFLATED
            member.create_system = 3
            member.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(
                member,
                raw,
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=_NAMESPACE_ZIP_COMPRESSION_LEVEL,
            )
    return len(output.getvalue())


def _read_store_blobs(store_dir: Path) -> tuple[tuple[str, bytes], ...]:
    """Read every exact store leaf so export-size estimates include orphans."""

    try:
        children = sorted(store_dir.iterdir(), key=lambda path: path.name)
    except OSError as exc:
        raise SourceIndependenceStorageReportError("store_scan_failed") from exc
    if len(children) > MAX_STORE_ITEMS:
        raise SourceIndependenceStorageReportError("store_item_limit_exceeded")
    blobs: list[tuple[str, bytes]] = []
    total = 0
    for child in children:
        try:
            raw = fingerprints.read_regular_file_bytes(child)
        except fingerprints.FingerprintError as exc:
            raise SourceIndependenceStorageReportError(
                "store_leaf_unreadable"
            ) from exc
        total += len(raw)
        if total > MAX_STORE_BYTES:
            raise SourceIndependenceStorageReportError(
                "store_size_limit_exceeded"
            )
        blobs.append((child.name, raw))
    return tuple(blobs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure source-independence storage without writes or providers."
    )
    parser.add_argument("--namespace-dir", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = analyze_namespace(args.namespace_dir)
    except SourceIndependenceStorageReportError as exc:
        print(f"source_independence_storage: blocked={exc} provider_calls=0 writes=0")
        return 2
    print(
        json.dumps(report.to_dict(), indent=2, sort_keys=True)
        if args.json
        else format_report(report)
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through CLI smoke
    raise SystemExit(main())


__all__ = (
    "ARTIFACT_FILENAMES",
    "NAMESPACE_ZIP_MEASUREMENT_SCOPE",
    "SourceIndependenceStorageReport",
    "SourceIndependenceStorageReportError",
    "analyze_namespace",
    "format_report",
    "main",
)
