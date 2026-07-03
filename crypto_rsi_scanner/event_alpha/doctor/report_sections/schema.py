"""Schema counter report section."""

from __future__ import annotations


def render_section(result: object) -> list[str]:
    return [
        (
            "schema: "
            f"schema_rows_validated={getattr(result, 'schema_rows_validated', 0)} "
            f"schema_validation_errors={getattr(result, 'schema_validation_errors', 0)}"
        )
    ]
