"""Scan status maintenance helpers."""

from __future__ import annotations

import json

from .connection import _now_iso, _parse_iso

_SCAN_STATUS_META_KEY = "scan_status"


class MaintenanceMixin:
    def scan_status(self) -> dict:
        raw = self.get_meta(_SCAN_STATUS_META_KEY)
        if not raw:
            return {}
        try:
            status = json.loads(raw)
        except Exception:  # noqa: BLE001
            return {}
        return status if isinstance(status, dict) else {}

    def _write_scan_status(self, status: dict) -> dict:
        self.set_meta(_SCAN_STATUS_META_KEY, json.dumps(status, default=str, sort_keys=True))
        return status

    def mark_scan_started(self, top_n: int | None = None, dry_run: bool = False) -> dict:
        prev = self.scan_status()
        now = _now_iso()
        return self._write_scan_status({
            "state": "running",
            "started_at": now,
            "finished_at": None,
            "top_n": top_n,
            "dry_run": bool(dry_run),
            "last_success_at": prev.get("last_success_at"),
            "last_failure_at": prev.get("last_failure_at"),
            "last_error": None,
        })

    def mark_scan_success(self, **fields) -> dict:
        prev = self.scan_status()
        now = _now_iso()
        status = {
            **{k: v for k, v in prev.items() if k.startswith("last_")},
            "state": "success",
            "started_at": prev.get("started_at"),
            "finished_at": now,
            "last_success_at": now,
            "last_failure_at": prev.get("last_failure_at"),
            "last_error": None,
        }
        status.update(fields)
        return self._write_scan_status(status)

    def mark_scan_failure(self, error: object, **fields) -> dict:
        prev = self.scan_status()
        now = _now_iso()
        status = {
            **{k: v for k, v in prev.items() if k.startswith("last_")},
            "state": "failure",
            "started_at": prev.get("started_at"),
            "finished_at": now,
            "last_success_at": prev.get("last_success_at"),
            "last_failure_at": now,
            "last_error": str(error)[:500],
        }
        status.update(fields)
        return self._write_scan_status(status)

    def last_successful_scan_at(self):
        status_dt = _parse_iso(self.scan_status().get("last_success_at"))
        return status_dt or self.last_scan_at()
