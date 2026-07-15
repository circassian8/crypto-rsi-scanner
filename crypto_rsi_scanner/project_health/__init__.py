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
    "artifact_retention",
    "baseline",
    "class_ownership",
    "completion_map",
    "radar_north_star",
    "release_report",
    "source_cache",
    "size_gates",
    "terminology_check",
    "transitional_file_check",
]
