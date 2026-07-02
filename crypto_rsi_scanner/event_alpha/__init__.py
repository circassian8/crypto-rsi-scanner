"""Event Alpha compatibility package.

The implementation still lives mostly in top-level ``event_*`` modules. This
package provides stable future import locations while incremental migrations
move code behind the wrappers.
"""

from __future__ import annotations

__all__ = [
    "artifacts",
    "cli",
    "doctor",
    "namespace",
    "notifications",
    "outcomes",
    "providers",
    "radar",
]
