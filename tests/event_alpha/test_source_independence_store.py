"""Content-addressed source-independence store regressions."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from crypto_rsi_scanner.event_alpha.artifacts.fingerprints import canonical_json_bytes
from crypto_rsi_scanner.event_alpha.dashboard import loader as dashboard_loader
from crypto_rsi_scanner.event_alpha.dashboard.secure_reader import (
    open_anchored_namespace,
)
from crypto_rsi_scanner.event_alpha.doctor.checks import operations as doctor_operations
from crypto_rsi_scanner.event_alpha.radar import source_independence
from crypto_rsi_scanner.event_alpha.radar import source_independence_store as store


def _source(source_id: str, origin: str) -> dict[str, str]:
    return {
        "source_id": source_id,
        "source_url": f"https://{origin}/story/{source_id}",
        "title": f"Market catalyst evidence report {source_id}",
        "body": " ".join(f"{source_id}-token-{index}" for index in range(30)),
        "published_at": "2026-07-15T10:00:00Z",
        "provider": "public_rss",
        "source_class": "broad_news",
    }


def _contract(suffix: str = "one") -> dict[str, object]:
    return source_independence.assess_source_independence(
        [
            _source(f"{suffix}-a", f"{suffix}-a.example"),
            _source(f"{suffix}-b", f"{suffix}-b.example"),
        ]
    )


def _namespace(tmp_path: Path) -> Path:
    namespace = tmp_path / "radar_namespace"
    namespace.mkdir()
    return namespace


def test_intern_is_idempotent_and_resolves_exact_canonical_blob(tmp_path):
    namespace = _namespace(tmp_path)
    contract = _contract()
    raw = canonical_json_bytes(contract)

    first = store.intern(namespace, contract)
    second = store.intern(namespace, deepcopy(contract))

    blob_sha = hashlib.sha256(raw).hexdigest()
    expected_name = f"{contract['contract_digest']}.{blob_sha}.json"
    artifact = namespace / store.STORE_DIRECTORY / expected_name
    assert first == second
    assert store.validate_reference(first) == ()
    assert first["artifact_name"] == expected_name
    assert first["artifact_relative_path"] == (
        f"{store.STORE_DIRECTORY}/{expected_name}"
    )
    assert first["blob_fingerprint"]["sha256"] == blob_sha
    assert first["validation_status"] == "validated"
    for field in (
        "raw_document_count",
        "content_cluster_count",
        "independent_evidence_count",
        "independent_corroboration_count",
        "distinct_origin_count",
    ):
        assert first[field] == contract[field]
    assert first["syndicated_copy_count"] == sum(
        document["match_kind"] in {"exact", "near_duplicate"}
        for document in contract["documents"]
    )
    assert artifact.read_bytes() == raw
    assert [path.name for path in artifact.parent.iterdir()] == [expected_name]
    assert store.resolve(namespace, first) == contract
    assert store.resolve_bytes(first, raw) == contract


def test_dashboard_resolves_repeated_references_through_anchored_reader(tmp_path):
    namespace = _namespace(tmp_path)
    contract = _contract()
    reference = store.intern(namespace, contract)
    value = {
        "source_independence": reference,
        "decision_projection": {"source_independence": reference},
    }

    with open_anchored_namespace(namespace) as reader:
        hydrated = dashboard_loader._hydrate_source_independence_references(  # noqa: SLF001
            value,
            reader=reader,
            cache={},
        )

    assert hydrated["source_independence"] == contract
    assert hydrated["decision_projection"]["source_independence"] == contract


def test_dashboard_cache_does_not_hide_later_reference_summary_tamper(tmp_path):
    namespace = _namespace(tmp_path)
    reference = store.intern(namespace, _contract())
    tampered = deepcopy(reference)
    tampered["distinct_origin_count"] -= 1

    with open_anchored_namespace(namespace) as reader:
        with pytest.raises(store.SourceIndependenceStoreError, match="summary_mismatch"):
            dashboard_loader._hydrate_source_independence_references(  # noqa: SLF001
                [reference, tampered],
                reader=reader,
                cache={},
            )


@pytest.mark.parametrize("mutation", ["missing", "tampered"])
def test_dashboard_reference_resolution_fails_closed_for_bad_blob(tmp_path, mutation):
    namespace = _namespace(tmp_path)
    reference = store.intern(namespace, _contract())
    artifact = namespace / store.STORE_DIRECTORY / reference["artifact_name"]
    if mutation == "missing":
        artifact.unlink()
    else:
        artifact.write_bytes(b"{}")

    with open_anchored_namespace(namespace) as reader:
        with pytest.raises(store.SourceIndependenceStoreError):
            dashboard_loader._hydrate_source_independence_references(  # noqa: SLF001
                {"source_independence": reference},
                reader=reader,
                cache={},
            )


@pytest.mark.parametrize(
    "mutation, expected_error",
    [
        (
            lambda value: value.update(schema_version=True),
            "source_independence_reference_schema_version_invalid",
        ),
        (
            lambda value: value.update(store_directory="../outside"),
            "source_independence_reference_store_directory_invalid",
        ),
        (
            lambda value: value.update(artifact_name="../contract.json"),
            "source_independence_reference_artifact_name_invalid",
        ),
        (
            lambda value: value.update(artifact_relative_path="../contract.json"),
            "source_independence_reference_artifact_relative_path_invalid",
        ),
        (
            lambda value: value.update(validation_status="unchecked"),
            "source_independence_reference_validation_status_invalid",
        ),
        (
            lambda value: value["blob_fingerprint"].update(size_bytes=0),
            "source_independence_reference_blob_size_invalid",
        ),
        (
            lambda value: value["blob_fingerprint"].update(item_count=2),
            "source_independence_reference_blob_item_count_invalid",
        ),
        (
            lambda value: value.update(unexpected=True),
            "source_independence_reference_keys_invalid",
        ),
    ],
)
def test_reference_validation_is_closed_and_path_free(
    tmp_path,
    mutation,
    expected_error,
):
    reference = store.intern(_namespace(tmp_path), _contract())
    invalid = deepcopy(reference)

    mutation(invalid)

    assert expected_error in store.validate_reference(invalid)


def test_resolve_fails_closed_for_missing_tampered_and_symlink_blobs(tmp_path):
    namespace = _namespace(tmp_path)
    reference = store.intern(namespace, _contract())
    artifact = namespace / store.STORE_DIRECTORY / reference["artifact_name"]

    artifact.unlink()
    with pytest.raises(store.SourceIndependenceStoreError, match="blob_unreadable"):
        store.resolve(namespace, reference)

    artifact.write_bytes(b"{}")
    with pytest.raises(
        store.SourceIndependenceStoreError,
        match="blob_fingerprint_mismatch",
    ):
        store.resolve(namespace, reference)

    artifact.unlink()
    outside = tmp_path / "outside.json"
    outside.write_bytes(canonical_json_bytes(_contract()))
    artifact.symlink_to(outside)
    with pytest.raises(store.SourceIndependenceStoreError, match="blob_unreadable"):
        store.resolve(namespace, reference)


def test_resolve_rejects_reference_summary_tamper(tmp_path):
    namespace = _namespace(tmp_path)
    reference = store.intern(namespace, _contract())
    tampered = deepcopy(reference)
    tampered["distinct_origin_count"] -= 1

    assert store.validate_reference(tampered) == ()
    with pytest.raises(store.SourceIndependenceStoreError, match="summary_mismatch"):
        store.resolve(namespace, tampered)


def test_copy_summary_counts_match_kinds_without_misclassifying_rejected_inputs(
    tmp_path,
):
    namespace = _namespace(tmp_path)
    rejected = source_independence.assess_source_independence(
        [
            {
                **_source("unsafe", "placeholder.example"),
                "source_url": "https://user:secret@example.com/story",
            },
            _source("eligible", "eligible.example"),
        ]
    )

    assert rejected["raw_document_count"] == 2
    assert rejected["content_cluster_count"] == 1
    assert {row["assessment_status"] for row in rejected["documents"]} == {
        "eligible",
        "rejected",
    }
    reference = store.intern(namespace, rejected)
    assert reference["syndicated_copy_count"] == 0
    assert store.resolve(namespace, reference) == rejected


def test_copy_summary_counts_exact_unassessable_copies_and_revalidates_blob(
    tmp_path,
):
    namespace = _namespace(tmp_path)
    unassessable = source_independence.assess_source_independence(
        [
            {
                **_source("short-a", "a.example"),
                "title": "same short title",
                "body": "",
            },
            {
                **_source("short-b", "b.example"),
                "title": "SAME short title!",
                "body": "",
            },
        ]
    )

    assert set(unassessable["unassessable_document_ids"]) == {
        row["document_id"] for row in unassessable["documents"]
    }
    assert sorted(row["match_kind"] for row in unassessable["documents"]) == [
        "exact",
        "representative",
    ]
    reference = store.intern(namespace, unassessable)
    assert reference["syndicated_copy_count"] == 1

    tampered = deepcopy(reference)
    tampered["syndicated_copy_count"] = 0
    assert store.validate_reference(tampered) == ()
    with pytest.raises(store.SourceIndependenceStoreError, match="summary_mismatch"):
        store.resolve(namespace, tampered)


def test_intern_rejects_a_symlinked_store_directory(tmp_path):
    namespace = _namespace(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (namespace / store.STORE_DIRECTORY).symlink_to(outside, target_is_directory=True)

    with pytest.raises(store.SourceIndependenceStoreError, match="write_failed"):
        store.intern(namespace, _contract())
    assert list(outside.iterdir()) == []


def test_externalize_and_hydrate_are_recursive_and_preserve_legacy_inline(tmp_path):
    namespace = _namespace(tmp_path)
    contract = _contract()
    legacy = {"legacy": contract}
    nested = {
        "candidate": {"source_independence": contract},
        "history": [contract, ("untouched", contract)],
    }

    assert store.hydrate(namespace, legacy) == legacy
    assert not (namespace / store.STORE_DIRECTORY).exists()

    externalized = store.externalize(namespace, nested)
    assert externalized["candidate"]["source_independence"]["schema_id"] == (
        store.REFERENCE_SCHEMA_ID
    )
    assert externalized["history"][0] == externalized["history"][1][1]
    assert store.externalize(namespace, externalized) == externalized
    assert store.hydrate(namespace, externalized) == nested


def test_hydrate_memoizes_exact_references_but_revalidates_distinct_metadata(
    tmp_path,
    monkeypatch,
):
    namespace = _namespace(tmp_path)
    reference = store.intern(namespace, _contract())
    calls = 0
    original = store.resolve

    def counted(namespace_dir, value):
        nonlocal calls
        calls += 1
        return original(namespace_dir, value)

    monkeypatch.setattr(store, "resolve", counted)
    hydrated = store.hydrate(namespace, [deepcopy(reference) for _ in range(100)])

    assert len(hydrated) == 100
    assert calls == 1

    tampered = deepcopy(reference)
    tampered["distinct_origin_count"] -= 1
    with pytest.raises(store.SourceIndependenceStoreError, match="summary_mismatch"):
        store.hydrate(namespace, [reference, tampered])
    assert calls == 3


def test_doctor_requires_canonical_store_path_and_checks_each_reference_summary(
    tmp_path,
    monkeypatch,
):
    namespace = _namespace(tmp_path)
    reference = store.intern(namespace, _contract())
    tampered = deepcopy(reference)
    tampered["distinct_origin_count"] -= 1
    (namespace / "event_integrated_radar_candidates.jsonl").write_text(
        json.dumps({"references": [reference, tampered]}) + "\n",
        encoding="utf-8",
    )
    state = {
        "artifacts": {
            "source_independence_contract_store": {
                "status": "current",
                "path": "alternate_store",
            }
        }
    }
    monkeypatch.setattr(
        doctor_operations.event_alpha_operator_state,
        "load_operator_state",
        lambda _path: SimpleNamespace(valid=True, state=state),
    )
    blockers: list[str] = []

    doctor_operations._check_source_independence_store(  # noqa: SLF001
        SimpleNamespace(namespace_dir=namespace),
        blockers,
    )

    assert any("source_independence_store_operator_path_mismatch" in item for item in blockers)
    assert any("source_independence_store_reference_summary_mismatch" in item for item in blockers)


def test_claimed_contract_and_reference_schemas_fail_closed(tmp_path):
    namespace = _namespace(tmp_path)
    malformed_contract = deepcopy(_contract())
    malformed_contract["research_only"] = False
    malformed_reference = {
        "schema_id": store.REFERENCE_SCHEMA_ID,
        "schema_version": store.REFERENCE_SCHEMA_VERSION,
    }

    with pytest.raises(store.SourceIndependenceStoreError, match="contract_invalid"):
        store.externalize(namespace, {"value": malformed_contract})
    with pytest.raises(store.SourceIndependenceStoreError, match="reference_invalid"):
        store.hydrate(namespace, {"value": malformed_reference})


def test_recursive_helpers_enforce_depth_and_node_budgets(tmp_path):
    namespace = _namespace(tmp_path)

    with pytest.raises(store.SourceIndependenceStoreError, match="depth_exceeded"):
        store.externalize(namespace, {"one": {"two": "value"}}, max_depth=1)
    with pytest.raises(store.SourceIndependenceStoreError, match="node_limit"):
        store.hydrate(namespace, {"one": "value"}, max_nodes=1)


def test_measurement_stats_are_bounded_and_measure_content_deduplication():
    contract = _contract()
    value = {"one": contract, "two": [deepcopy(contract)]}

    measured = store.measurement_stats(value)

    assert measured.inline_contract_occurrences == 2
    assert measured.reference_occurrences == 0
    assert measured.unique_contract_count == 1
    assert measured.inline_contract_bytes == 2 * measured.unique_inline_blob_bytes
    assert measured.duplicate_inline_blob_bytes == measured.unique_inline_blob_bytes
    assert measured.projected_reference_bytes > 0
    assert measured.projected_inline_savings_bytes > 0
    assert measured.to_dict()["nodes_visited"] == measured.nodes_visited
    with pytest.raises(store.SourceIndependenceStoreError, match="node_limit"):
        store.measurement_stats(value, max_nodes=1)


def test_measurement_unique_contract_bound_is_fail_closed():
    value = [_contract("one"), _contract("two")]

    with pytest.raises(store.SourceIndependenceStoreError, match="unique_contract_limit"):
        store.measurement_stats(value, max_unique_contracts=1)


def test_contract_blob_size_limit_is_enforced_before_store_write(tmp_path, monkeypatch):
    namespace = _namespace(tmp_path)
    contract = _contract()
    monkeypatch.setattr(
        store,
        "MAX_CONTRACT_BLOB_BYTES",
        len(canonical_json_bytes(contract)) - 1,
    )

    with pytest.raises(store.SourceIndependenceStoreError, match="size_limit"):
        store.intern(namespace, contract)
    assert not (namespace / store.STORE_DIRECTORY).exists()
