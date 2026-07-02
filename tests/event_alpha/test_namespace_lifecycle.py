"""Focused pytest checks for namespace lifecycle inventory."""

from __future__ import annotations

from pathlib import Path

from crypto_rsi_scanner.event_alpha.namespace import lifecycle


def test_known_stale_namespace_classifies_without_marker(tmp_path: Path):
    (tmp_path / "notify_llm_deep").mkdir()
    registry = lifecycle.build_namespace_registry(tmp_path)
    rows = {row["namespace"]: row for row in registry["namespaces"]}
    assert rows["notify_llm_deep"]["status"] == "stale_deprecated"
    assert rows["notify_llm_deep"]["safe_for_send_readiness"] is False
