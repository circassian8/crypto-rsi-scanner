"""Issue model for Event Alpha doctor checks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DoctorIssue:
    message: str
    severity: str
    check_id: str | None = None
    category: str | None = None

    def as_text(self) -> str:
        if self.check_id:
            return f"{self.check_id}: {self.message}"
        return self.message

    def to_dict(self) -> dict[str, str | None]:
        return {
            "message": self.message,
            "severity": self.severity,
            "check_id": self.check_id,
            "category": self.category,
        }
