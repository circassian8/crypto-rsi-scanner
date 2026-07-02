"""Schema-backed validation layer for Event Alpha artifact doctor."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ..artifacts import schema_v1


SCHEMA_VALIDATED_FILENAMES = tuple(schema_v1.FILENAME_TO_SCHEMA_ID)


@dataclass(frozen=True)
class SchemaDoctorResult:
    schema_rows_validated: int = 0
    schema_validation_errors: int = 0
    missing_required_fields: int = 0
    invalid_enum_fields: int = 0
    invalid_path_fields: int = 0
    invalid_safety_fields: int = 0
    deprecated_field_usage: int = 0
    validated_files: tuple[str, ...] = ()
    errors: tuple[dict[str, Any], ...] = field(default_factory=tuple)


def validate_namespace_artifacts(namespace_dir: str | Path | None) -> SchemaDoctorResult:
    if namespace_dir is None:
        return SchemaDoctorResult()
    base = Path(namespace_dir)
    if not base.exists():
        return SchemaDoctorResult()
    files = [base / name for name in SCHEMA_VALIDATED_FILENAMES if (base / name).exists()]
    return validate_artifact_files(files)


def validate_artifact_files(paths: Iterable[str | Path]) -> SchemaDoctorResult:
    rows_validated = 0
    errors: list[dict[str, Any]] = []
    files: list[str] = []
    deprecated = 0
    for raw_path in paths:
        path = Path(raw_path)
        result = schema_v1.validate_artifact_file(path)
        rows_validated += int(result.get("rows_validated") or 0)
        deprecated += int(result.get("deprecated_field_usage") or 0)
        if int(result.get("rows_validated") or 0):
            files.append(str(path))
        for error in result.get("errors") or ():
            if isinstance(error, dict):
                errors.append(dict(error, path=str(path)))
    missing = sum(1 for error in errors if str(error.get("error") or "").startswith("missing_required_field:"))
    invalid_enum = sum(1 for error in errors if str(error.get("error") or "").startswith("invalid_enum:"))
    invalid_path = sum(1 for error in errors if str(error.get("error") or "").startswith("absolute_non_debug_path:"))
    invalid_safety = sum(
        1
        for error in errors
        if str(error.get("error") or "").startswith(("unsafe_side_effect", "invalid_safety", "unsafe_auto_apply"))
    )
    return SchemaDoctorResult(
        schema_rows_validated=rows_validated,
        schema_validation_errors=len(errors),
        missing_required_fields=missing,
        invalid_enum_fields=invalid_enum,
        invalid_path_fields=invalid_path,
        invalid_safety_fields=invalid_safety,
        deprecated_field_usage=deprecated,
        validated_files=tuple(files),
        errors=tuple(errors),
    )


def check_registry_schema_dependency_errors() -> tuple[str, ...]:
    from . import check_registry

    return check_registry.schema_dependency_errors()
