"""Atomic rewrite regressions for externalized source-independence evidence."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from crypto_rsi_scanner.event_alpha.outcomes import artifact_io
from crypto_rsi_scanner.event_alpha.radar import source_independence
from crypto_rsi_scanner.event_alpha.radar import source_independence_store as store


def _source(source_id: str, origin: str) -> dict[str, str]:
    return {
        "source_id": source_id,
        "source_url": f"https://{origin}/story/{source_id}",
        "title": f"Independent catalyst report {source_id}",
        "body": " ".join(f"{source_id}-token-{index}" for index in range(30)),
        "published_at": "2026-07-15T10:00:00Z",
        "provider": "public_rss",
        "source_class": "broad_news",
    }


def _contract() -> dict[str, object]:
    return source_independence.assess_source_independence(
        [
            _source("alpha", "alpha.example"),
            _source("beta", "beta.example"),
        ]
    )


def _namespace(tmp_path: Path) -> Path:
    namespace = tmp_path / "atomic_namespace"
    namespace.mkdir()
    return namespace


def _write_raw(path: Path, row: dict[str, object]) -> bytes:
    payload = (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.write_bytes(payload)
    return payload


def _forced_store_failure(*_args, **_kwargs):
    raise store.SourceIndependenceStoreError("forced_store_failure")


def test_outcome_rewrite_preserves_a_legacy_inline_contract(tmp_path):
    namespace = _namespace(tmp_path)
    path = namespace / "event_outcomes.jsonl"
    contract = _contract()
    _write_raw(path, {"row_type": "outcome", "source_independence": contract})

    artifact_io.write_jsonl(
        path,
        [
            {
                "row_type": "outcome",
                "source_independence": contract,
                "outcome_status": "pending",
            }
        ],
    )

    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["source_independence"]["schema_id"] == source_independence.SCHEMA_ID
    assert row["source_independence"]["contract_digest"] == contract["contract_digest"]
    assert not (namespace / store.STORE_DIRECTORY).exists()


def test_unsafe_contract_store_cannot_truncate_existing_outcomes(tmp_path):
    namespace = _namespace(tmp_path)
    path = namespace / "event_outcomes.jsonl"
    before = _write_raw(path, {"row_type": "outcome", "sentinel": "keep"})
    outside = tmp_path / "outside"
    outside.mkdir()
    (namespace / store.STORE_DIRECTORY).symlink_to(outside, target_is_directory=True)

    with pytest.raises(store.SourceIndependenceStoreError, match="store_write_failed"):
        artifact_io.write_jsonl(
            path,
            [{"row_type": "outcome", "source_independence": _contract()}],
        )

    assert path.read_bytes() == before
    assert list(outside.iterdir()) == []


def test_core_normalization_store_failure_leaves_target_byte_exact(
    tmp_path,
    monkeypatch,
):
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store  # noqa: F401
    from crypto_rsi_scanner.event_alpha.radar.core import store as core_store

    namespace = _namespace(tmp_path)
    path = namespace / "event_core_opportunities.jsonl"
    row = {
        "row_type": "event_core_opportunity",
        "run_id": "run-atomic",
        "core_opportunity_id": "core-atomic",
        "final_opportunity_level": "local_only",
    }
    before = _write_raw(path, row)
    monkeypatch.setattr(
        core_store,
        "normalize_core_opportunity_rows",
        lambda rows, *, now=None: [{**dict(next(iter(rows))), "normalized": True}],
    )
    monkeypatch.setattr(store, "externalize", _forced_store_failure)

    result = core_store.normalize_core_opportunity_store(path)

    assert result.success is False
    assert "forced_store_failure" in str(result.block_reason)
    assert path.read_bytes() == before


def test_acquisition_reconciliation_store_failure_leaves_target_byte_exact(
    tmp_path,
    monkeypatch,
):
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition  # noqa: F401
    from crypto_rsi_scanner.event_alpha.radar.evidence import serialization

    namespace = _namespace(tmp_path)
    path = namespace / "event_evidence_acquisition.jsonl"
    before = _write_raw(
        path,
        {
            "row_type": "event_evidence_acquisition",
            "run_id": "run-atomic",
            "core_opportunity_id": "core-old",
        },
    )
    monkeypatch.setattr(
        serialization.event_core_opportunities,
        "resolve_canonical_core_opportunity_id",
        lambda *_args, **_kwargs: SimpleNamespace(
            canonical_core_opportunity_id="core-new",
            resolution_status="resolved",
            diagnostic_support_for_core_opportunity_id=None,
            warnings=(),
        ),
    )
    monkeypatch.setattr(store, "externalize", _forced_store_failure)

    changed = serialization.reconcile_acquisition_core_ids(
        path,
        [{"core_opportunity_id": "core-new"}],
        run_id="run-atomic",
    )

    assert changed == 0
    assert path.read_bytes() == before


def test_alert_outcome_store_failure_leaves_target_byte_exact(
    tmp_path,
    monkeypatch,
):
    from crypto_rsi_scanner.event_alpha.artifacts.alert_store import outcomes

    namespace = _namespace(tmp_path)
    path = namespace / "event_alert_outcomes.jsonl"
    before = _write_raw(path, {"row_type": "event_alert_snapshot", "sentinel": "keep"})
    prices = namespace / "prices.json"
    prices.write_text('{"prices":[]}', encoding="utf-8")
    monkeypatch.setattr(store, "externalize", _forced_store_failure)

    with pytest.raises(store.SourceIndependenceStoreError, match="forced_store_failure"):
        outcomes.fill_alert_outcomes(
            [{"row_type": "event_alert_snapshot", "asset_symbol": "TEST"}],
            prices,
            path,
        )

    assert path.read_bytes() == before


def test_integrated_sidecar_store_failure_leaves_target_byte_exact(
    tmp_path,
    monkeypatch,
):
    from crypto_rsi_scanner.event_alpha.radar.integrated.pipeline_parts import sidecars

    namespace = _namespace(tmp_path)
    path = namespace / "event_integrated_radar_candidates.jsonl"
    before = _write_raw(path, {"row_type": "event_integrated_radar_candidate", "sentinel": "keep"})
    monkeypatch.setattr(store, "externalize", _forced_store_failure)

    with pytest.raises(store.SourceIndependenceStoreError, match="forced_store_failure"):
        sidecars._write_jsonl(  # noqa: SLF001
            path,
            [{"row_type": "event_integrated_radar_candidate", "candidate_id": "new"}],
        )

    assert path.read_bytes() == before


def test_evidence_append_prepares_all_rows_before_reading_target(
    tmp_path,
    monkeypatch,
):
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition  # noqa: F401
    from crypto_rsi_scanner.event_alpha.radar.evidence import serialization

    namespace = _namespace(tmp_path)
    path = namespace / "event_evidence_acquisition.jsonl"
    before = _write_raw(path, {"row_type": "existing"})
    prepared: list[str] = []
    original_externalize = store.externalize
    original_read = serialization.market_no_send_io.read_regular_bytes

    def tracked_externalize(*args, **kwargs):
        prepared.append("row")
        return original_externalize(*args, **kwargs)

    def checked_read(*args, **kwargs):
        assert prepared == ["row"]
        return original_read(*args, **kwargs)

    monkeypatch.setattr(store, "externalize", tracked_externalize)
    monkeypatch.setattr(serialization.market_no_send_io, "read_regular_bytes", checked_read)
    result = serialization.EvidenceAcquisitionResult(
        acquisition_id="acq-atomic",
        opportunity_id="opp-atomic",
        core_opportunity_id=None,
        hypothesis_id=None,
        incident_id=None,
        source_pack="broad_news_context_pack",
        status="no_results",
    )

    assert serialization.write_acquisition_results(path, [result]) == 1
    assert path.read_bytes().startswith(before)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_evidence_append_rejects_a_nonterminated_prefix_without_altering_it(tmp_path):
    import crypto_rsi_scanner.event_alpha.radar.evidence_acquisition  # noqa: F401
    from crypto_rsi_scanner.event_alpha.radar.evidence import serialization

    namespace = _namespace(tmp_path)
    path = namespace / "event_evidence_acquisition.jsonl"
    before = b'{"row_type":"existing"}'
    path.write_bytes(before)
    result = serialization.EvidenceAcquisitionResult(
        acquisition_id="acq-atomic",
        opportunity_id="opp-atomic",
        core_opportunity_id=None,
        hypothesis_id=None,
        incident_id=None,
        source_pack="broad_news_context_pack",
        status="no_results",
    )

    with pytest.raises(ValueError, match="trailing newline"):
        serialization.write_acquisition_results(path, [result])

    assert path.read_bytes() == before


def test_core_append_is_atomic_and_retains_the_exact_existing_prefix(
    tmp_path,
    monkeypatch,
):
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store  # noqa: F401
    from crypto_rsi_scanner.event_alpha.radar.core import store as core_store

    namespace = _namespace(tmp_path)
    path = namespace / "event_core_opportunities.jsonl"
    existing_row = {"row_type": "existing", "spacing": "is retained"}
    before = (json.dumps(existing_row, indent=2) + "\n").encode("utf-8")
    path.write_bytes(before)
    opportunity = SimpleNamespace(core_opportunity_id="core-atomic")
    monkeypatch.setattr(
        core_store.event_core_opportunities,
        "aggregate_core_opportunities",
        lambda _rows: (opportunity,),
    )
    monkeypatch.setattr(
        core_store,
        "_row_from_core_opportunity",
        lambda *_args, **_kwargs: {
            "row_type": "event_core_opportunity",
            "core_opportunity_id": "core-atomic",
        },
    )

    result = core_store.write_core_opportunities(
        [{}],
        cfg=core_store.EventCoreOpportunityStoreConfig(path=path),
    )

    assert result.success is True
    assert result.rows_written == 1
    assert path.read_bytes().startswith(before)

    unterminated = namespace / "unterminated_core.jsonl"
    unterminated_before = b'{"row_type":"existing"}'
    unterminated.write_bytes(unterminated_before)
    failed = core_store.write_core_opportunities(
        [{}],
        cfg=core_store.EventCoreOpportunityStoreConfig(path=unterminated),
    )
    assert failed.success is False
    assert "trailing newline" in str(failed.block_reason)
    assert unterminated.read_bytes() == unterminated_before
