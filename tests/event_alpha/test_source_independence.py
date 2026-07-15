"""Closed source-independence contract regressions."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from crypto_rsi_scanner.event_alpha.radar import source_independence


def _redigest(value):
    payload = dict(value)
    payload.pop("contract_digest", None)
    value["contract_digest"] = hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
    return value


def _long_text(prefix="token"):
    return " ".join(f"{prefix}{index}" for index in range(30))


def _source(source_id, origin, body=None, **overrides):
    row = {
        "source_id": source_id,
        "source_url": f"https://{origin}/story/{source_id}",
        "title": "Market catalyst evidence report",
        "body": _long_text(source_id) if body is None else body,
        "published_at": "2026-07-15T10:00:00Z",
        "provider": "public_rss",
        "source_class": "broad_news",
    }
    row.update(overrides)
    return row


def test_normalization_exact_match_and_origin_canonicalization_are_deterministic():
    first = _source(
        "first",
        "www.Example.COM.",
        title="ＦＯＯ—Bar!",
        body="ONE, two; three four five six seven eight nine ten eleven twelve.",
    )
    second = _source(
        "second",
        "example.com",
        title="foo bar",
        body="one two three four five six seven eight nine ten eleven twelve",
        published_at="2026-07-15T10:01:00Z",
    )

    value = source_independence.assess_source_independence([second, first])

    assert source_independence.validate_contract(value) == []
    assert value["raw_document_count"] == 2
    assert value["distinct_origins"] == ["example.com"]
    assert value["content_cluster_count"] == 1
    assert value["independent_evidence_count"] == 1
    assert value["independent_corroboration_count"] == 0
    assert value["documents"][0]["normalized_title"] == "foo bar"
    assert value["documents"][1]["match_kind"] == "exact"


def test_nfkc_expansion_preserves_a_self_validating_contract():
    value = source_independence.assess_source_independence(
        [
            _source(
                "ligature",
                "example.com",
                title="o\ufb03cial market catalyst evidence report",
            )
        ]
    )

    assert value["documents"][0]["normalized_title"].startswith("official")
    assert value["documents"][0]["title_input_length"] < len(
        value["documents"][0]["normalized_title"]
    )
    assert source_independence.validate_contract(value) == []


def test_closed_container_rejects_status_errors_and_alias_drift():
    contract = source_independence.assess_source_independence(
        [_source("one", "one.example"), _source("two", "two.example")]
    )
    wrapped = {
        "source_independence": contract,
        "source_independence_status": "assessed",
        "source_independence_errors": [],
        "independent_source_count": contract["independent_evidence_count"],
        "independent_corroboration_count": contract[
            "independent_corroboration_count"
        ],
        "source_content_cluster_count": contract["content_cluster_count"],
    }

    assert source_independence.validate_source_independence_container(wrapped) == []
    assert source_independence.validated_source_independence_container(wrapped) == contract
    for invalid in (
        {**wrapped, "source_independence_status": "rejected"},
        {
            **wrapped,
            "source_independence_errors": [
                "source_independence_source_context_incomplete"
            ],
        },
        {**wrapped, "independent_source_count": 999},
    ):
        assert source_independence.validate_source_independence_container(invalid)
        assert source_independence.validated_source_independence_container(invalid) == {}


def test_near_duplicate_uses_three_word_jaccard_at_conservative_threshold():
    tokens = [f"word{index}" for index in range(30)]
    changed = list(tokens)
    changed[8] = "replacement"
    value = source_independence.assess_source_independence(
        [
            _source("a", "one.example", " ".join(tokens)),
            _source(
                "b",
                "two.example",
                " ".join(changed),
                published_at="2026-07-15T10:01:00Z",
            ),
        ]
    )

    assert value["algorithm"]["shingle_size_words"] == 3
    assert value["algorithm"]["near_duplicate_threshold"] == 0.8
    assert value["content_cluster_count"] == 1
    assert value["clusters"][0]["members"][1]["match_kind"] == "near_duplicate"
    assert value["clusters"][0]["members"][1]["similarity"] >= 0.8
    assert value["distinct_origin_count"] == 2
    assert value["independent_evidence_count"] == 1


def test_clustering_does_not_use_transitive_near_duplicate_chaining():
    original = [f"word{index}" for index in range(30)]
    bridge = list(original)
    bridge[8] = "bridgechange"
    tail = list(bridge)
    tail[20] = "tailchange"
    value = source_independence.assess_source_independence(
        [
            _source("a", "a.example", " ".join(original)),
            _source(
                "b",
                "b.example",
                " ".join(bridge),
                published_at="2026-07-15T10:01:00Z",
            ),
            _source(
                "c",
                "c.example",
                " ".join(tail),
                published_at="2026-07-15T10:02:00Z",
            ),
        ]
    )

    assert value["content_cluster_count"] == 2
    assert [cluster["member_count"] for cluster in value["clusters"]] == [2, 1]
    assert value["independent_evidence_count"] == 2


def test_independent_corroboration_requires_new_content_and_new_origin():
    baseline = _long_text("baseline")
    same_origin_new_content = _long_text("sameorigin")
    new_origin_new_content = _long_text("independent")
    value = source_independence.assess_source_independence(
        [
            _source("a", "one.example", baseline),
            _source(
                "b",
                "two.example",
                baseline,
                published_at="2026-07-15T10:01:00Z",
            ),
            _source(
                "c",
                "one.example",
                same_origin_new_content,
                published_at="2026-07-15T10:02:00Z",
            ),
            _source(
                "d",
                "three.example",
                new_origin_new_content,
                published_at="2026-07-15T10:03:00Z",
            ),
        ]
    )

    assert value["distinct_origin_count"] == 3
    assert value["content_cluster_count"] == 3
    assert value["independent_evidence_count"] == 2
    assert value["independent_corroboration_count"] == 1
    assert value["has_independent_corroboration"] is True
    assert len(value["corroborating_representative_ids"]) == 1


def test_short_nonidentical_and_missing_text_are_unassessable():
    value = source_independence.assess_source_independence(
        [
            _source("a", "a.example", title="tiny headline", body=""),
            _source("b", "b.example", title="different tiny headline", body=""),
            _source("c", "c.example", title="", body=""),
        ]
    )

    assert value["independent_evidence_count"] == 0
    assert value["has_independent_corroboration"] is False
    assert len(value["unassessable_document_ids"]) == 3
    assert {row["content_similarity_status"] for row in value["documents"]} == {
        "missing",
        "too_short",
    }


def test_exact_short_copies_collapse_but_never_add_corroboration():
    value = source_independence.assess_source_independence(
        [
            _source("a", "a.example", title="same short title", body=""),
            _source("b", "b.example", title="SAME short title!", body=""),
        ]
    )

    assert value["content_cluster_count"] == 1
    assert value["clusters"][0]["member_count"] == 2
    assert value["clusters"][0]["corroboration_eligible"] is False
    assert value["independent_evidence_count"] == 0


def test_public_time_then_source_id_selects_representative_and_is_permutation_stable():
    text = _long_text("same")
    known = _source(
        "z-known",
        "known.example",
        text,
        published_at="2026-07-15T11:00:00Z",
    )
    missing = _source(
        "a-missing",
        "missing.example",
        text,
        published_at=None,
        fetched_at=None,
    )
    forward = source_independence.assess_source_independence([missing, known])
    reverse = source_independence.assess_source_independence([known, missing])

    assert forward == reverse
    representative_id = forward["clusters"][0]["representative_id"]
    representative = next(
        row for row in forward["documents"] if row["document_id"] == representative_id
    )
    assert representative["source_id"] == "z-known"
    assert representative["public_time_status"] == "published"
    assert forward["documents"][1]["public_time_status"] == "missing"


@pytest.mark.parametrize(
    ("url", "expected_status"),
    [
        ("https://user:secret@example.com/story", "userinfo_rejected"),
        ("https://example.com:99999/story", "port_rejected"),
        ("https://example.com:notaport/story", "port_rejected"),
        ("ftp://example.com/story", "scheme_rejected"),
        ("https://[broken/story", "malformed"),
    ],
)
def test_unsafe_or_malformed_urls_are_rejected_without_origin(url, expected_status):
    value = source_independence.assess_source_independence(
        [_source("unsafe", "placeholder.example", source_url=url)]
    )
    document = value["documents"][0]

    assert document["source_url"] is None
    assert document["canonical_origin"] is None
    assert document["source_url_status"] == expected_status
    assert document["assessment_status"] == "rejected"
    assert value["independent_evidence_count"] == 0


def test_valid_port_is_checked_but_does_not_fragment_canonical_hostname():
    value = source_independence.assess_source_independence(
        [
            _source(
                "port",
                "placeholder.example",
                source_url="https://WWW.Example.COM.:443/story?token=removed#fragment",
            )
        ]
    )
    document = value["documents"][0]

    assert document["canonical_origin"] == "example.com"
    assert document["source_url"] == "https://example.com:443/story"
    assert "token" not in document["source_url"]


def test_document_text_shingle_and_input_count_bounds_fail_closed():
    overflow = source_independence.assess_source_independence(
        [_source("overflow", "example.com", body="x" * (source_independence.MAX_BODY_CHARS + 1))]
    )
    many_shingles = source_independence.assess_source_independence(
        [
            _source(
                "shingles",
                "example.com",
                body=" ".join(
                    f"w{index}"
                    for index in range(source_independence.MAX_SHINGLES_PER_DOCUMENT + 3)
                ),
            )
        ]
    )

    assert overflow["documents"][0]["assessment_status"] == "rejected"
    assert "body_overflow" in overflow["documents"][0]["reason_codes"]
    assert many_shingles["documents"][0]["assessment_status"] == "rejected"
    assert "shingle_limit_exceeded" in many_shingles["documents"][0]["reason_codes"]
    with pytest.raises(ValueError, match="document_limit"):
        source_independence.assess_source_independence(
            [
                _source(f"source-{index}", f"source-{index}.example")
                for index in range(source_independence.MAX_DOCUMENTS + 1)
            ]
        )


def test_official_metadata_is_preserved_without_inventing_authority():
    value = source_independence.assess_source_independence(
        [
            _source(
                "official",
                "exchange.example",
                provider="official_exchange",
                source_class="official_exchange",
            )
        ]
    )
    document = value["documents"][0]

    assert document["source_provider"] == "official_exchange"
    assert document["source_class"] == "official_exchange"
    assert document["authority_status"] == "not_assessed"
    assert value["authority_assessed"] is False
    assert value["research_only"] is True


def test_validator_recomputes_semantics_and_rejects_redigested_tampering():
    value = source_independence.assess_source_independence(
        [
            _source("a", "a.example"),
            _source(
                "b",
                "b.example",
                _long_text("other"),
                published_at="2026-07-15T10:01:00Z",
            ),
        ]
    )
    tampered_count = _redigest(
        {**deepcopy(value), "independent_corroboration_count": 99}
    )
    tampered_origin = deepcopy(value)
    tampered_origin["documents"][0]["canonical_origin"] = "attacker.example"
    _redigest(tampered_origin)

    assert "source_independence_contract_semantics_mismatch" in (
        source_independence.validate_contract(tampered_count)
    )
    assert "source_independence_contract_semantics_mismatch" in (
        source_independence.validate_contract(tampered_origin)
    )


def test_valid_contract_union_deduplicates_overlap_and_recomputes_independence():
    first = source_independence.assess_source_independence(
        [_source("a", "a.example", _long_text("baseline"))]
    )
    overlap = source_independence.assess_source_independence(
        [
            _source("a", "a.example", _long_text("baseline")),
            _source("b", "b.example", _long_text("independent")),
        ]
    )

    combined = source_independence.combine_contracts([first, overlap])

    assert source_independence.validate_contract(combined) == []
    assert combined["raw_document_count"] == 2
    assert combined["independent_evidence_count"] == 2
    assert combined["independent_corroboration_count"] == 1


def test_contract_union_rejects_invalid_or_unbounded_inputs():
    contract = source_independence.assess_source_independence(
        [_source("a", "a.example")]
    )
    tampered = deepcopy(contract)
    tampered["independent_evidence_count"] = 99

    with pytest.raises(ValueError, match="contract_invalid"):
        source_independence.combine_contracts([contract, tampered])


def test_validator_rejects_permuted_rows_even_with_recomputed_digest():
    value = source_independence.assess_source_independence(
        [
            _source("a", "a.example"),
            _source(
                "b",
                "b.example",
                _long_text("other"),
                published_at="2026-07-15T10:01:00Z",
            ),
        ]
    )
    permuted = deepcopy(value)
    permuted["documents"].reverse()
    _redigest(permuted)

    assert "source_independence_contract_semantics_mismatch" in (
        source_independence.validate_contract(permuted)
    )


def test_validator_rejects_digest_algorithm_and_bool_schema_tampering():
    value = source_independence.assess_source_independence([_source("a", "a.example")])
    digest_tampered = {**deepcopy(value), "has_independent_corroboration": True}
    algorithm_tampered = deepcopy(value)
    algorithm_tampered["algorithm"]["near_duplicate_threshold"] = 0.5
    _redigest(algorithm_tampered)
    bool_schema = _redigest({**deepcopy(value), "schema_version": True})

    assert "source_independence_contract_digest_invalid" in (
        source_independence.validate_contract(digest_tampered)
    )
    assert "source_independence_algorithm_invalid" in (
        source_independence.validate_contract(algorithm_tampered)
    )
    assert "source_independence_schema_version_invalid" in (
        source_independence.validate_contract(bool_schema)
    )
