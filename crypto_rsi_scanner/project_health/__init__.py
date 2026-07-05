"""Permanent project-health and architecture tooling.

These static analyzers and report writers are the permanent home for
architecture and project-health checks. New code should import from this
package.
"""

from __future__ import annotations

__all__ = [
    "api_inventory",
    "architecture_contract",
    "architecture_report",
    "baseline",
    "class_ownership",
    "completion_map",
    "release_report",
    "size_gates",
    "terminology_check",
    "transitional_file_check",
]
