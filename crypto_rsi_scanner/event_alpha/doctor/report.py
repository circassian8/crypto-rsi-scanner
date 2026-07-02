"""Report helpers for Event Alpha artifact doctor."""

from __future__ import annotations

from typing import Any

from . import check_registry


def schema_counter_line(result: Any) -> str:
    """Render schema counters with stable field names for tests and operators."""
    return (
        "schema validation: "
        f"schema_rows_validated={getattr(result, 'schema_rows_validated', 0)} "
        f"schema_validation_errors={getattr(result, 'schema_validation_errors', 0)} "
        f"missing_required_fields={getattr(result, 'missing_required_fields', 0)} "
        f"invalid_enum_fields={getattr(result, 'invalid_enum_fields', 0)} "
        f"invalid_path_fields={getattr(result, 'invalid_path_fields', 0)} "
        f"invalid_safety_fields={getattr(result, 'invalid_safety_fields', 0)} "
        f"deprecated_field_usage={getattr(result, 'deprecated_field_usage', 0)}"
    )


def phase_line(result: Any) -> str:
    return (
        "phases: "
        f"schema_only={str(bool(getattr(result, 'schema_only', False))).lower()} "
        f"legacy_checks_skipped={str(bool(getattr(result, 'legacy_checks_skipped', False))).lower()}"
    )


def check_registry_lines() -> list[str]:
    return check_registry.registry_report_lines()
