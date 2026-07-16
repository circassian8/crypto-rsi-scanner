"""Read-only source-independence storage measurement regressions."""

from __future__ import annotations

import json

import pytest

from crypto_rsi_scanner.event_alpha.operations import source_independence_storage
from crypto_rsi_scanner.event_alpha.radar import source_independence
from crypto_rsi_scanner.event_alpha.radar import source_independence_store


def _contract() -> dict:
    return source_independence.assess_source_independence(
        [
            {
                "source_id": "official",
                "source_url": "https://official.example/report",
                "source_provider": "official_exchange",
                "source_class": "official_exchange",
                "published_at": "2026-07-15T10:00:00Z",
                "title": "Official catalyst publication confirms the event",
                "body": " ".join(f"official-{index}" for index in range(40)),
            },
            {
                "source_id": "independent",
                "source_url": "https://independent.example/report",
                "source_provider": "public_rss",
                "source_class": "broad_news",
                "published_at": "2026-07-15T10:05:00Z",
                "title": "Independent reporting observes the same market event",
                "body": " ".join(f"independent-{index}" for index in range(40)),
            },
        ]
    )


def _write_rows(path, rows):
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def test_read_only_report_measures_exact_inline_and_store_reduction(tmp_path):
    namespace = tmp_path / "namespace"
    namespace.mkdir()
    contract = _contract()
    reference = source_independence_store.intern(namespace, contract)
    row = {
        "row_type": "measurement",
        "source_independence": reference,
        "decision_projection": {"source_independence": reference},
    }
    for filename in source_independence_storage.ARTIFACT_FILENAMES[:3]:
        _write_rows(namespace / filename, [row])

    before = {
        path.relative_to(namespace).as_posix(): path.read_bytes()
        for path in namespace.rglob("*")
        if path.is_file()
    }
    report = source_independence_storage.analyze_namespace(namespace)
    repeated = source_independence_storage.analyze_namespace(namespace)
    after = {
        path.relative_to(namespace).as_posix(): path.read_bytes()
        for path in namespace.rglob("*")
        if path.is_file()
    }

    assert report.reference_occurrences == 6
    assert report.unique_contracts == 1
    assert report.source_store_items == 1
    assert report.source_store_bytes == reference["blob_fingerprint"]["size_bytes"]
    assert report.inline_equivalent_artifact_bytes > (
        report.artifact_bytes_with_references
    )
    assert report.storage_reduction_bytes > 0
    assert report.storage_reduction_percent > 0
    assert report.estimated_export_deflate_bytes_with_store > 0
    assert (
        report.namespace_zip_measurement_scope
        == source_independence_storage.NAMESPACE_ZIP_MEASUREMENT_SCOPE
    )
    assert report.measured_namespace_zip_members_with_store == 4
    assert report.measured_namespace_zip_members_inline == 3
    assert report.measured_namespace_zip_bytes_with_store > (
        report.estimated_export_deflate_bytes_with_store
    )
    assert report.measured_namespace_zip_bytes_inline > (
        report.estimated_export_deflate_bytes_inline
    )
    assert report.measured_namespace_zip_reduction_bytes == (
        report.measured_namespace_zip_bytes_inline
        - report.measured_namespace_zip_bytes_with_store
    )
    assert report.measured_namespace_zip_reduction_percent > 0
    assert report.measured_namespace_zip_bytes_with_store == (
        repeated.measured_namespace_zip_bytes_with_store
    )
    assert report.measured_namespace_zip_bytes_inline == (
        repeated.measured_namespace_zip_bytes_inline
    )
    rendered = source_independence_storage.format_report(report)
    assert "standalone selected-namespace measurement" in rendered
    assert "not whole-project archive size" in rendered
    assert "compatibility payload-only estimate" in rendered
    assert report.measurement_status == "measured_read_only"
    assert report.provider_calls == report.writes == 0
    assert before == after


def test_export_estimate_counts_unreferenced_immutable_store_leaves(tmp_path):
    namespace = tmp_path / "namespace"
    namespace.mkdir()
    reference = source_independence_store.intern(namespace, _contract())
    _write_rows(
        namespace / source_independence_storage.ARTIFACT_FILENAMES[0],
        [{"source_independence": reference}],
    )
    referenced_only = source_independence_storage.analyze_namespace(namespace)
    orphan = source_independence.assess_source_independence(
        [
            {
                "source_id": "orphan-official",
                "source_url": "https://orphan-official.example/report",
                "source_provider": "official_exchange",
                "source_class": "official_exchange",
                "published_at": "2026-07-15T11:00:00Z",
                "title": "Separate official evidence contract",
                "body": " ".join(f"orphan-official-{index}" for index in range(40)),
            },
            {
                "source_id": "orphan-independent",
                "source_url": "https://orphan-independent.example/report",
                "source_provider": "public_rss",
                "source_class": "broad_news",
                "published_at": "2026-07-15T11:05:00Z",
                "title": "Separate independent evidence contract",
                "body": " ".join(f"orphan-independent-{index}" for index in range(40)),
            },
        ]
    )
    source_independence_store.intern(namespace, orphan)

    with_orphan = source_independence_storage.analyze_namespace(namespace)

    assert with_orphan.unreferenced_store_items == 1
    assert with_orphan.source_store_items == 2
    assert with_orphan.total_bytes_with_store > referenced_only.total_bytes_with_store
    assert (
        with_orphan.estimated_export_deflate_bytes_with_store
        > referenced_only.estimated_export_deflate_bytes_with_store
    )
    assert with_orphan.measured_namespace_zip_members_with_store == (
        referenced_only.measured_namespace_zip_members_with_store + 1
    )
    assert with_orphan.measured_namespace_zip_members_inline == (
        referenced_only.measured_namespace_zip_members_inline
    )
    assert with_orphan.measured_namespace_zip_bytes_with_store > (
        referenced_only.measured_namespace_zip_bytes_with_store
    )
    assert with_orphan.measured_namespace_zip_bytes_inline == (
        referenced_only.measured_namespace_zip_bytes_inline
    )
    assert with_orphan.measured_namespace_zip_reduction_bytes < (
        referenced_only.measured_namespace_zip_reduction_bytes
    )


def test_report_fails_closed_when_a_referenced_blob_is_missing(tmp_path):
    namespace = tmp_path / "namespace"
    namespace.mkdir()
    reference = source_independence_store.intern(namespace, _contract())
    _write_rows(
        namespace / source_independence_storage.ARTIFACT_FILENAMES[0],
        [{"source_independence": reference}],
    )
    (
        namespace
        / source_independence_store.STORE_DIRECTORY
        / reference["artifact_name"]
    ).unlink()

    with pytest.raises(
        source_independence_storage.SourceIndependenceStorageReportError,
        match="blob_unreadable",
    ):
        source_independence_storage.analyze_namespace(namespace)


def test_legacy_inline_rows_are_measured_without_rewriting_history(tmp_path):
    namespace = tmp_path / "namespace"
    namespace.mkdir()
    artifact = namespace / source_independence_storage.ARTIFACT_FILENAMES[0]
    _write_rows(artifact, [{"source_independence": _contract()}])
    before = artifact.read_bytes()

    report = source_independence_storage.analyze_namespace(namespace)

    assert report.reference_occurrences == 0
    assert report.source_store_items == 0
    assert report.storage_reduction_bytes == 0
    assert report.measured_namespace_zip_members_with_store == 1
    assert report.measured_namespace_zip_members_inline == 1
    assert report.measured_namespace_zip_bytes_with_store == (
        report.measured_namespace_zip_bytes_inline
    )
    assert report.measured_namespace_zip_reduction_bytes == 0
    assert artifact.read_bytes() == before
