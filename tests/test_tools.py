"""Unit tests for Agent_01 tools (demo mode, synthetic data only)."""

from dataclasses import replace

import pytest

from agent_01 import config as cfg_mod
from agent_01.tools import docs_tools, gmail_tools, memory_tools


@pytest.fixture
def demo_cfg(tmp_path, monkeypatch):
    base = cfg_mod.load_config()
    cfg = replace(base, mode="demo", output_dir=tmp_path / "out", memory_path=tmp_path / "mem.json")
    for mod in (gmail_tools, docs_tools, memory_tools):
        monkeypatch.setattr(mod, "load_config", lambda: cfg)
    return cfg


def test_review_period_is_14_days(demo_cfg):
    r = gmail_tools.get_review_period("2026-11-26")
    assert r == {"status": "success", "start_date": "2026-11-13", "end_date": "2026-11-26",
                 "period_label": "2026-11-13 to 2026-11-26"}


def test_review_period_bad_date_gives_recovery_hint(demo_cfg):
    r = gmail_tools.get_review_period("26/11/2026")
    assert r["status"] == "error" and "ISO" in r["recovery_hint"]


def test_search_filters_account_and_window(demo_cfg):
    r = gmail_tools.search_account_emails("ACCOUNT_B", "2026-11-13", "2026-11-26")
    assert r["status"] == "success"
    assert [e["message_id"] for e in r["emails"]] == ["b-001", "b-002", "b-003"]


def test_search_rejects_unknown_alias(demo_cfg):
    r = gmail_tools.search_account_emails("RealCustomer", "2026-11-13", "2026-11-26")
    assert r["status"] == "error" and "ACCOUNT_A" in r["recovery_hint"]


def test_search_rejects_reversed_dates(demo_cfg):
    r = gmail_tools.search_account_emails("ACCOUNT_A", "2026-11-26", "2026-11-13")
    assert r["status"] == "error"


def test_publish_writes_markdown(demo_cfg):
    r = docs_tools.publish_biweekly_review_tab("2026-11-26 Bi-weekly Review", "# Report")
    assert r["status"] == "success"
    assert (demo_cfg.output_dir / "2026-11-26_Bi-weekly_Review.md").read_text() == "# Report"


def test_publish_rejects_bad_title(demo_cfg):
    r = docs_tools.publish_biweekly_review_tab("Nov review", "# Report")
    assert r["status"] == "error" and "YYYY-MM-DD" in r["recovery_hint"]


def test_memory_roundtrip(demo_cfg):
    assert memory_tools.get_previous_action_items()["action_items"] == []
    memory_tools.save_action_items("2026-11-13 to 2026-11-26", ["Send residency doc"])
    r = memory_tools.get_previous_action_items()
    assert r["period_label"] == "2026-11-13 to 2026-11-26"
    assert r["action_items"] == ["Send residency doc"]
