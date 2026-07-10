"""Read-only Event Alpha burn-in contract checks."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from crypto_rsi_scanner.event_alpha.operations import common, daily_burn_in
from crypto_rsi_scanner.project_health import radar_north_star


def test_burn_in_contract_check_is_read_only(tmp_path):
    generated_at = datetime(2026, 7, 5, tzinfo=timezone.utc)
    json_path, md_path, _ = radar_north_star.write_burn_in_contract(
        out_dir=tmp_path,
        generated_at=generated_at,
    )
    before = {json_path: json_path.read_bytes(), md_path: md_path.read_bytes()}

    status = radar_north_star.check_burn_in_contract(out_dir=tmp_path)

    assert status["valid"] is True
    assert status["errors"] == []
    assert {path: path.read_bytes() for path in before} == before


def test_burn_in_contract_check_rejects_empty_contract(tmp_path):
    (tmp_path / radar_north_star.BURN_IN_CONTRACT_JSON).write_text("{}\n", encoding="utf-8")
    (tmp_path / radar_north_star.BURN_IN_CONTRACT_MD).write_text("# Empty contract\n", encoding="utf-8")

    status = radar_north_star.check_burn_in_contract(out_dir=tmp_path)

    assert status["valid"] is False
    assert "burn_in_contract_schema_invalid" in status["errors"]
    assert "burn_in_contract_auto_apply_not_false" in status["errors"]


def test_burn_in_contract_check_rejects_out_of_sync_markdown(tmp_path):
    _, md_path, _ = radar_north_star.write_burn_in_contract(out_dir=tmp_path)
    md_path.write_text("# Stale contract rendering\n", encoding="utf-8")

    status = radar_north_star.check_burn_in_contract(out_dir=tmp_path)

    assert status["valid"] is False
    assert "burn_in_contract_markdown_out_of_sync" in status["errors"]


def test_daily_burn_in_smoke_checks_contract_without_rewriting_it(tmp_path, monkeypatch):
    real_repo = common.repo_root_from_module()
    fake_repo = tmp_path / "repo"
    research_dir = fake_repo / "research"
    json_path, md_path, _ = radar_north_star.write_burn_in_contract(
        out_dir=research_dir,
        generated_at=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )
    before = {json_path: json_path.read_bytes(), md_path: md_path.read_bytes()}
    artifact_base = tmp_path / "artifacts"
    monkeypatch.delenv("RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR", raising=False)
    monkeypatch.delenv("RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE", raising=False)
    pythonpath = os.environ.get("PYTHONPATH", "")
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join(part for part in (str(real_repo), pythonpath) if part),
    )
    monkeypatch.setattr(daily_burn_in.common, "repo_root_from_module", lambda: fake_repo)

    payload = daily_burn_in.run_daily_burn_in(
        profile="fixture",
        artifact_namespace="hermetic_contract_smoke",
        base_dir=artifact_base,
        python=sys.executable,
        smoke=True,
        report_timeout_seconds=10,
    )

    assert payload["status"] == "passed"
    contract_step = next(row for row in payload["steps"] if row["name"] == "burn_in_contract")
    assert contract_step["status"] == "passed"
    assert "--check-burn-in-contract" in contract_step["command"]
    assert "--burn-in-contract-only" not in contract_step["command"]
    assert {path: path.read_bytes() for path in before} == before
    assert (artifact_base / "hermetic_contract_smoke" / daily_burn_in.RUN_JSON).exists()
