"""Tests for active PII scrubbing."""

from dataclasses import replace

from agent_01 import config as cfg_mod
from agent_01 import redaction


def _with_accounts(monkeypatch):
    base = cfg_mod.load_config()
    accounts = {
        "ACCOUNT_A": cfg_mod.AccountConfig("ACCOUNT_A", "0.Contoso", ["Contoso Games"]),
        "ACCOUNT_B": cfg_mod.AccountConfig("ACCOUNT_B", "1.Fabrikam", []),
    }
    monkeypatch.setattr(redaction, "load_config", lambda: replace(base, accounts=accounts))
    redaction._customer_term_map.cache_clear()


def test_scrubs_email_phone_amount():
    out = redaction.redact_text("Mail kim@corp.example or call +82 10-1234-5678 about $1,200k")
    assert out == "Mail [EMAIL] or call [PHONE] about [AMOUNT]"


def test_keeps_dates_and_percentages():
    assert redaction.redact_text("2026-11-14: 40% done") == "2026-11-14: 40% done"


def test_replaces_customer_names_with_alias(monkeypatch):
    _with_accounts(monkeypatch)
    out = redaction.redact_text("Contoso Games and fabrikam signed; label 0.Contoso")
    assert out == "ACCOUNT_A and ACCOUNT_B signed; label ACCOUNT_A"
    redaction._customer_term_map.cache_clear()


def test_redacts_nested_tool_response():
    resp = {"emails": [{"sender": "a@b.example", "snippet": "ok"}], "status": "success"}
    assert redaction.redact(resp)["emails"][0]["sender"] == "[EMAIL]"
