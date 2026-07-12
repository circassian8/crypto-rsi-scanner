"""Calibration/prior integration tests for the exact feedback firewall."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from types import SimpleNamespace


NOW = datetime(2026, 7, 12, 2, 0, tzinfo=timezone.utc)


def _feedback_row(
    *,
    core_id: str,
    feedback_id: str,
    label: str = "useful",
    **overrides,
) -> dict[str, object]:
    from crypto_rsi_scanner.event_alpha.outcomes import feedback_eligibility

    row: dict[str, object] = {
        "run_id": "run-priors",
        "profile": "fixture",
        "artifact_namespace": "feedback_priors_firewall",
        "core_opportunity_id": core_id,
        "feedback_id": feedback_id,
        "feedback_target_type": "core_opportunity_id",
        "feedback_target": core_id,
        "target": core_id,
        "label": label,
        "marked_at": "2026-07-12T01:00:00+00:00",
        "marked_by": "human-reviewer",
        "source": "manual_cli",
        "research_only": True,
        "notes": "reviewed research annotation",
    }
    row.update(overrides)
    row.update(feedback_eligibility.build_feedback_eligibility_fields(row))
    return row


def _core_row(
    *,
    core_id: str,
    playbook: str = "listing_volatility",
    provider: str = "binance_announcements",
    route: str = "HIGH_PRIORITY_WATCH",
    **overrides,
) -> dict[str, object]:
    row: dict[str, object] = {
        "schema_id": "core_opportunity_v1",
        "schema_version": "event_core_opportunity_store_v1",
        "row_type": "event_core_opportunity",
        "run_id": "run-priors",
        "profile": "fixture",
        "artifact_namespace": "feedback_priors_firewall",
        "core_opportunity_id": core_id,
        "feedback_target": core_id,
        "feedback_target_type": "core_opportunity_id",
        "generated_at": "2026-07-12T00:00:00+00:00",
        "research_only": True,
        "symbol": "CORE",
        "coin_id": "core-owned-id",
        "opportunity_type": "UNCONFIRMED_RESEARCH",
        "source_provider": provider,
        "source_provider_domain": "core.example",
        "source_domain": "core.example",
        "source_pack": "core-pack",
        "source_class": "official_exchange",
        "lane": "research",
        "playbook_type": playbook,
        "effective_playbook_type": playbook,
        "impact_path_type": "listing",
        "opportunity_level": "watchlist",
        "final_opportunity_level": "watchlist",
        "final_route_after_quality_gate": route,
        "thesis_origin": "catalyst_led",
        "directional_bias": "long",
        "catalyst_status": "confirmed",
        "confidence_band": "exploratory",
        "timing_state": "early",
        "tradability_status": "acceptable",
        "radar_route": "diagnostic",
        "actionability_score_cohort": "70_79",
        "anomaly_type": "none",
    }
    row.update(overrides)
    return row


def _reviewed_payload(
    *,
    count: int = 2,
    min_sample: int = 2,
    playbook: str = "listing_volatility",
    provider: str = "binance_announcements",
    route: str = "HIGH_PRIORITY_WATCH",
) -> dict[str, object]:
    from crypto_rsi_scanner.event_alpha.outcomes import calibration

    core_rows = [
        _core_row(
            core_id=f"core-{index}",
            playbook=playbook,
            provider=provider,
            route=route,
        )
        for index in range(count)
    ]
    feedback_rows = [
        _feedback_row(core_id=f"core-{index}", feedback_id=f"feedback-{index}")
        for index in range(count)
    ]
    payload = calibration.build_calibration_priors(
        [],
        feedback_rows=feedback_rows,
        core_rows=core_rows,
        generated_at=NOW,
        now=NOW,
        min_sample=min_sample,
    )
    return payload


def _write_payload(tmp_path, payload: dict[str, object]):
    path = tmp_path / "priors.json"
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def test_calibration_partitions_once_and_uses_only_core_owned_attribution(monkeypatch):
    from crypto_rsi_scanner.event_alpha.outcomes import calibration, feedback_eligibility

    eligible = _feedback_row(
        core_id="core-eligible",
        feedback_id="feedback-eligible",
        playbook_type="forged-feedback-playbook",
        source_provider="forged-feedback-provider",
        symbol="FORGED",
    )
    legacy_alias = {
        "symbol": "CORE",
        "coin_id": "core-owned-id",
        "key": "core-eligible",
        "label": "junk",
        "playbook_type": "forged-legacy-playbook",
    }
    core = _core_row(core_id="core-eligible", playbook="core-playbook")
    calls = 0
    real_partition = feedback_eligibility.partition_joined_calibration_feedback

    def counted_partition(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_partition(*args, **kwargs)

    monkeypatch.setattr(
        feedback_eligibility,
        "partition_joined_calibration_feedback",
        counted_partition,
    )
    payload = calibration.build_calibration_priors(
        [{"symbol": "irrelevant-alert"}],
        feedback_rows=[eligible, legacy_alias],
        core_rows=[core],
        generated_at=NOW,
        now=NOW,
        min_sample=2,
    )

    assert calls == 1
    assert payload["feedback_rows_supplied"] == 2
    assert payload["feedback_rows_eligible"] == 1
    assert payload["feedback_rows_excluded"] == 1
    assert payload["feedback_exclusion_reason_counts"]["legacy_feedback_contract"] == 1
    assert set(payload["playbook_priors"]) == {"core-playbook"}
    assert "forged-feedback-playbook" not in json.dumps(payload)
    assert "forged-legacy-playbook" not in json.dumps(payload)

    report = calibration.format_calibration_report(
        [],
        feedback_rows=[eligible, legacy_alias],
        core_rows=[core],
        now=NOW,
    )
    assert calls == 2
    assert "feedback_supplied=2" in report
    assert "feedback_eligible=1" in report
    assert "feedback_excluded=1" in report
    assert "legacy_feedback_contract=1" in report
    assert "feedback by playbook: core-playbook: useful=1" in report
    assert "forged-feedback-playbook" not in report
    assert "forged-legacy-playbook" not in report


def test_below_minimum_feedback_never_generates_or_loads_an_adjustment(tmp_path):
    from crypto_rsi_scanner.event_alpha.outcomes import calibration, priors

    payload = calibration.build_calibration_priors(
        [],
        feedback_rows=[
            _feedback_row(core_id="core-0", feedback_id="feedback-0"),
            _feedback_row(core_id="core-1", feedback_id="feedback-1"),
        ],
        core_rows=[_core_row(core_id="core-0"), _core_row(core_id="core-1")],
        generated_at=NOW,
        now=NOW,
        min_sample=3,
    )
    assert payload["eligible_for_auto_apply"] is False
    assert all(
        row["score_adjustment"] == 0
        for group_name in calibration.PRIOR_GROUP_NAMES
        for row in payload[group_name].values()
    )

    path = _write_payload(tmp_path, payload)
    cfg = priors.EventAlphaPriorsConfig(enabled=True, path=path)
    assert priors.load_priors(cfg) is not None

    alerts = _research_alerts()
    assert priors.apply_priors_to_alerts(alerts, cfg=cfg) == alerts


def test_reviewed_above_minimum_priors_remain_shadow_only(tmp_path):
    from crypto_rsi_scanner.event_alpha.artifacts import alerts as event_alerts
    from crypto_rsi_scanner.event_alpha.outcomes import calibration, priors

    alerts = _research_alerts()
    selected = next(alert for alert in alerts if alert.symbol == "TESTLATE")
    triggered = next(
        alert for alert in alerts if alert.tier == event_alerts.EventAlertTier.TRIGGERED_FADE
    )
    payload = _reviewed_payload(
        playbook=selected.effective_playbook_type,
        provider=selected.discovery_candidate.event.source,
        route=selected.tier.value,
    )
    payload["auto_apply"] = False
    path = _write_payload(tmp_path, payload)
    cfg = priors.EventAlphaPriorsConfig(enabled=True, path=path)

    assert payload["schema_version"] == calibration.CALIBRATION_PRIORS_SCHEMA_VERSION
    assert payload["eligible_for_auto_apply"] is True
    assert priors.load_priors(cfg) is not None
    assert priors.apply_priors_to_alerts([selected, triggered], cfg=cfg) == [selected, triggered]

    adjusted = priors.apply_priors_shadow([selected, triggered], cfg=cfg)
    adjusted_by_symbol = {row.symbol: row for row in adjusted}
    adjusted_selected = adjusted_by_symbol[selected.symbol]
    adjusted_triggered = adjusted_by_symbol[triggered.symbol]
    assert adjusted_selected.opportunity_score > selected.opportunity_score
    assert adjusted_selected.score_before_priors == selected.opportunity_score
    assert adjusted_selected.prior_file == str(path)
    assert adjusted_selected.prior_multipliers_applied == {
        "playbook": 1.03,
        "provider": 1.03,
        "tier": 1.03,
    }
    assert adjusted_triggered == triggered
    assert adjusted_triggered.score_before_priors is None


def test_prior_loader_rejects_untrusted_schema_telemetry_and_values(tmp_path):
    from crypto_rsi_scanner.event_alpha.outcomes import priors

    valid = _reviewed_payload()
    invalid_payloads: list[dict[str, object]] = []
    for path, value in (
        (("schema_version",), "event_alpha_calibration_priors_v1"),
        (("research_only",), False),
        (("feedback_firewall_applied",), False),
        (("auto_apply",), True),
        (("feedback_rows_supplied",), True),
        (("feedback_rows_excluded",), 1),
        (("playbook_priors", "listing_volatility", "median_primary_horizon_return"), float("nan")),
        (("playbook_priors", "listing_volatility", "median_primary_horizon_return"), 10**1000),
        (("playbook_priors", "listing_volatility", "multiplier"), 1.5),
    ):
        payload = copy.deepcopy(valid)
        target = payload
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        invalid_payloads.append(payload)

    below_minimum = _reviewed_payload(count=1, min_sample=2)
    below_minimum["eligible_for_auto_apply"] = True
    below_minimum["playbook_priors"]["listing_volatility"]["score_adjustment"] = 3
    invalid_payloads.append(below_minimum)

    for index, payload in enumerate(invalid_payloads):
        path = tmp_path / f"invalid-{index}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        cfg = priors.EventAlphaPriorsConfig(enabled=True, path=path)
        assert priors.load_priors(cfg) is None
        alerts = _research_alerts()[:1]
        assert priors.apply_priors_to_alerts(alerts, cfg=cfg) == alerts

    duplicate_path = tmp_path / "duplicate.json"
    duplicate_path.write_text(
        json.dumps(valid)[:-1] + ',"auto_apply":true}',
        encoding="utf-8",
    )
    assert priors.load_priors(
        priors.EventAlphaPriorsConfig(enabled=True, path=duplicate_path)
    ) is None
    valid_path = _write_payload(tmp_path, valid)
    assert priors.load_priors(
        priors.EventAlphaPriorsConfig(
            enabled=True,
            path=valid_path,
            min_multiplier=float("nan"),
        )
    ) is None
    assert priors.load_priors(
        priors.EventAlphaPriorsConfig(
            enabled=True,
            path=valid_path,
            min_multiplier=1.01,
            max_multiplier=1.30,
        )
    ) is None


def test_valid_but_unmatched_priors_leave_alert_and_metadata_unchanged(tmp_path):
    from crypto_rsi_scanner.event_alpha.outcomes import priors

    alerts = _research_alerts()
    selected = next(alert for alert in alerts if alert.symbol == "TESTLIST")
    payload = _reviewed_payload(
        playbook="never-matches-playbook",
        provider="never-matches-provider",
        route="never-matches-route",
    )
    path = _write_payload(tmp_path, payload)
    cfg = priors.EventAlphaPriorsConfig(enabled=True, path=path)

    assert priors.load_priors(cfg) is not None
    assert priors.apply_priors_to_alerts([selected], cfg=cfg) == [selected]
    assert selected.score_before_priors is None
    assert selected.prior_multipliers_applied == {}


def test_feedback_prior_artifact_schema_is_distinct_and_recommendation_only():
    from crypto_rsi_scanner.event_alpha.artifacts.schema import registry

    payload = _reviewed_payload()
    payload["auto_apply"] = False
    schema = registry.SCHEMAS["feedback_calibration_prior_v2"]
    assert registry.infer_schema_id_for_file("event_alpha_priors.json") == schema.schema_id
    assert registry.validate_row_against_schema(payload, schema) == []

    enabled = copy.deepcopy(payload)
    enabled["auto_apply"] = True
    errors = registry.validate_row_against_schema(enabled, schema)
    assert "unsafe_auto_apply:true" in errors
    assert "feedback_prior_auto_apply_not_false" in errors


def test_feedback_prior_schema_and_runtime_loader_share_exact_acceptance_contract(
    tmp_path,
):
    from crypto_rsi_scanner.event_alpha.artifacts.schema import registry
    from crypto_rsi_scanner.event_alpha.outcomes import priors

    valid = _reviewed_payload()
    valid_path = tmp_path / "event_alpha_priors.json"
    valid_path.write_text(json.dumps(valid, sort_keys=True), encoding="utf-8")
    assert priors.prior_payload_is_valid(valid) is True
    assert registry.validate_row_against_schema(
        valid,
        "feedback_calibration_prior_v2",
    ) == []
    assert priors.load_priors(
        priors.EventAlphaPriorsConfig(enabled=True, path=valid_path)
    ) is not None

    invalid_payloads: list[dict[str, object]] = []

    extra_payload_field = copy.deepcopy(valid)
    extra_payload_field["untrusted_extra"] = True
    invalid_payloads.append(extra_payload_field)

    unsafe_group_key = copy.deepcopy(valid)
    unsafe_group_key["playbook_priors"][" listing_volatility"] = (
        unsafe_group_key["playbook_priors"].pop("listing_volatility")
    )
    invalid_payloads.append(unsafe_group_key)

    extra_group_row_field = copy.deepcopy(valid)
    extra_group_row_field["playbook_priors"]["listing_volatility"]["multiplier"] = 1.03
    invalid_payloads.append(extra_group_row_field)

    nonfinite_median = copy.deepcopy(valid)
    nonfinite_median["playbook_priors"]["listing_volatility"][
        "median_primary_horizon_return"
    ] = float("inf")
    invalid_payloads.append(nonfinite_median)

    nondeterministic_adjustment = copy.deepcopy(valid)
    nondeterministic_adjustment["playbook_priors"]["listing_volatility"][
        "score_adjustment"
    ] = 99
    invalid_payloads.append(nondeterministic_adjustment)

    sample_accounting_mismatch = copy.deepcopy(valid)
    sample_accounting_mismatch["playbook_priors"]["listing_volatility"]["samples"] = 3
    invalid_payloads.append(sample_accounting_mismatch)

    eligibility_mismatch = copy.deepcopy(valid)
    eligibility_mismatch["eligible_for_auto_apply"] = False
    invalid_payloads.append(eligibility_mismatch)

    platform_edge_clock = copy.deepcopy(valid)
    platform_edge_clock["generated_at"] = "0001-01-01T00:00:00+23:59"
    invalid_payloads.append(platform_edge_clock)

    for payload in invalid_payloads:
        assert priors.prior_payload_is_valid(payload) is False
        errors = registry.validate_row_against_schema(
            payload,
            "feedback_calibration_prior_v2",
        )
        assert "feedback_prior_payload_invalid" in errors
        valid_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        assert priors.load_priors(
            priors.EventAlphaPriorsConfig(enabled=True, path=valid_path)
        ) is None


def _research_alerts():
    from crypto_rsi_scanner.event_alpha.artifacts import alerts as event_alerts

    def alert(
        symbol: str,
        *,
        tier: event_alerts.EventAlertTier,
        score: int,
        playbook: str,
        provider: str,
    ) -> event_alerts.EventAlertCandidate:
        discovery_candidate = SimpleNamespace(
            asset=SimpleNamespace(symbol=symbol, coin_id=symbol.lower()),
            event=SimpleNamespace(event_id=f"event-{symbol.lower()}", source=provider),
        )
        return event_alerts.EventAlertCandidate(
            discovery_candidate=discovery_candidate,
            tier=tier,
            opportunity_score=score,
            effective_playbook_type=playbook,
            playbook_type=playbook,
        )

    return [
        alert(
            "TESTLATE",
            tier=event_alerts.EventAlertTier.WATCHLIST,
            score=78,
            playbook="ai_ipo_proxy",
            provider="project_blog_rss",
        ),
        alert(
            "TESTLIST",
            tier=event_alerts.EventAlertTier.HIGH_PRIORITY_WATCH,
            score=58,
            playbook="listing_volatility",
            provider="binance_announcements",
        ),
        alert(
            "TRIGGER",
            tier=event_alerts.EventAlertTier.TRIGGERED_FADE,
            score=100,
            playbook="proxy_fade",
            provider="manual_json",
        ),
    ]
