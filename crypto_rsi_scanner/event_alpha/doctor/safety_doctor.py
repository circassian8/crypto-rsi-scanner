"""Safety phase for schema-backed Event Alpha artifact doctor checks."""

from __future__ import annotations

from dataclasses import dataclass

from . import check_registry
from .schema_doctor import SchemaDoctorResult


@dataclass(frozen=True)
class SafetyDoctorResult:
    invalid_safety_fields: int = 0
    secret_redaction_errors: int = 0
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def validate_schema_safety(
    schema_result: SchemaDoctorResult,
    *,
    strict: bool = False,
    schema_only: bool = False,
) -> SafetyDoctorResult:
    """Promote schema safety/secret errors into doctor phase messages."""
    safety_errors = [
        error
        for error in schema_result.errors
        if str(error.get("error") or "").startswith(
            ("unsafe_side_effect", "invalid_safety", "unsafe_auto_apply")
        )
    ]
    secret_errors = [
        error
        for error in schema_result.errors
        if str(error.get("error") or "").startswith("secret_field_unredacted:")
    ]
    messages: list[str] = []
    if safety_errors:
        messages.append(
            check_registry.format_check_message(
                "safety.invalid_safety_fields",
                f"schema_safety_validation_errors={len(safety_errors)}",
            )
        )
    if secret_errors:
        messages.append(
            check_registry.format_check_message(
                "secrets.provider_key_leakage",
                f"schema_secret_redaction_errors={len(secret_errors)}",
            )
        )
    block = bool(messages and (strict or schema_only))
    return SafetyDoctorResult(
        invalid_safety_fields=len(safety_errors),
        secret_redaction_errors=len(secret_errors),
        blockers=tuple(messages if block else ()),
        warnings=tuple(() if block else messages),
    )
