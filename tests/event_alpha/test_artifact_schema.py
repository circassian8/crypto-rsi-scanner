"""Focused pytest checks for Event Alpha schema v1."""

from __future__ import annotations

from crypto_rsi_scanner.event_alpha.artifacts import schema_v1
from crypto_rsi_scanner.event_alpha.doctor import schema_doctor


def test_schema_registry_contains_required_ids():
    assert "integrated_radar_candidate_v1" in schema_v1.SCHEMAS
    assert "namespace_status_v1" in schema_v1.SCHEMAS
    assert schema_doctor.check_registry_schema_dependency_errors() == ()
