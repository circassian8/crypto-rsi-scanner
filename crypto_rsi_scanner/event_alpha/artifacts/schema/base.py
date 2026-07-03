"""Base schema objects and registry exports."""

from __future__ import annotations

from .legacy import (
    EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION,
    ROW_TYPE_TO_SCHEMA_ID,
    SCHEMAS,
    ArtifactSchema,
    get_schema,
    infer_schema_id_for_file,
    schema_for_row,
)

__all__ = (
    "EVENT_ALPHA_ARTIFACT_SCHEMA_VERSION",
    "ROW_TYPE_TO_SCHEMA_ID",
    "SCHEMAS",
    "ArtifactSchema",
    "get_schema",
    "infer_schema_id_for_file",
    "schema_for_row",
)
