"""Gmail retrieval tools.

demo mode : reads synthetic emails from agent_01/data/synthetic_emails.json
live mode : queries the Gmail API with local OAuth credentials (never committed)
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

from pydantic import ValidationError

from ..config import load_config
from ..schemas import EmailRecord, EmailSearchRequest, EmailSearchResult

logger = logging.getLogger("agent_01.tools.gmail")
SYNTHETIC_PATH = Path(__file__).resolve().parent.parent / "data" / "synthetic_emails.json"


def get_review_period(reference_date: str = "") -> dict:
    """Return the two-week review window ending on the reference date.

    Args:
        reference_date: ISO date (YYYY-MM-DD) that ends the window. Empty
            string means today.

    Returns:
        dict with `start_date`, `end_date` (ISO strings) and `period_label`,
        or `status="error"` with a `recovery_hint`.
    """
    try:
        end = date.fromisoformat(reference_date) if reference_date else date.today()
    except ValueError:
        return {
            "status": "error",
            "error_message": f"Invalid reference_date '{reference_date}'.",
            "recovery_hint": "Pass an ISO date like 2026-11-26, or an empty string for today.",
        }
    start = end - timedelta(days=load_config().lookback_days - 1)
    return {
        "status": "success",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "period_label": f"{start.isoformat()} to {end.isoformat()}",
    }


def search_account_emails(
    account_alias: str, start_date: str, end_date: str, max_results: int = 50
) -> dict:
    """Fetch emails for one customer account within a date range.

    Use this once per account alias. Results contain only subject, sender,
    date and a short snippet; full bodies are never returned.

    Args:
        account_alias: Neutral account alias, either "ACCOUNT_A" or "ACCOUNT_B".
            Never pass a real customer name.
        start_date: Inclusive start date, ISO format YYYY-MM-DD.
        end_date: Inclusive end date, ISO format YYYY-MM-DD.
        max_results: Maximum emails to return (1-200). Default 50.

    Returns:
        dict matching EmailSearchResult: `status`, `account_alias`, `emails`,
        and on failure `error_message` plus a `recovery_hint` describing how
        to retry.
    """
    try:
        req = EmailSearchRequest(
            account_alias=account_alias,
            start_date=start_date,
            end_date=end_date,
            max_results=max_results,
        )
    except ValidationError as e:
        return EmailSearchResult(
            status="error",
            account_alias=account_alias,
            error_message=f"Invalid arguments: {e.errors()[0]['msg']}",
            recovery_hint=(
                "Use account_alias ACCOUNT_A or ACCOUNT_B and ISO dates with "
                "start_date <= end_date. Call get_review_period to obtain valid dates."
            ),
        ).model_dump(mode="json")

    cfg = load_config()
    try:
        if cfg.mode == "live":
            emails = _search_gmail_live(req, cfg.accounts[req.account_alias])
        else:
            emails = _search_synthetic(req)
    except Exception as e:
        logger.exception("gmail search failed")
        return EmailSearchResult(
            status="error",
            account_alias=req.account_alias,
            error_message=f"Email backend failure: {type(e).__name__}: {e}",
            recovery_hint=(
                "Retry once. If it fails again, continue with the other account and "
                "note in the summary that this account's data is unavailable."
            ),
        ).model_dump(mode="json")

    logger.info("fetched %d emails for %s", len(emails), req.account_alias)
    return EmailSearchResult(
        status="success", account_alias=req.account_alias, emails=emails
    ).model_dump(mode="json")


def _search_synthetic(req: EmailSearchRequest) -> list[EmailRecord]:
    data = json.loads(SYNTHETIC_PATH.read_text(encoding="utf-8"))
    out = []
    for item in data:
        rec = EmailRecord(**{k: item[k] for k in EmailRecord.model_fields})
        if item["account_alias"] == req.account_alias and req.start_date <= rec.date <= req.end_date:
            out.append(rec)
    return out[: req.max_results]


def _search_gmail_live(req: EmailSearchRequest, account) -> list[EmailRecord]:
    """Query Gmail by label + keywords. Requires local OAuth (token.json)."""
    from googleapiclient.discovery import build  # local-only dependency

    from .google_auth import get_credentials

    service = build("gmail", "v1", credentials=get_credentials(), cache_discovery=False)
    before = req.end_date + timedelta(days=1)
    query = f'label:"{account.gmail_label}" after:{req.start_date:%Y/%m/%d} before:{before:%Y/%m/%d}'
    if account.keywords:
        query += " {" + " ".join(f'"{k}"' for k in account.keywords) + "}"
    resp = service.users().messages().list(userId="me", q=query, maxResults=req.max_results).execute()
    out = []
    for m in resp.get("messages", []):
        msg = service.users().messages().get(
            userId="me", id=m["id"], format="metadata", metadataHeaders=["From", "Subject"]
        ).execute()
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        out.append(
            EmailRecord(
                message_id=m["id"],
                date=date.fromtimestamp(int(msg["internalDate"]) / 1000),
                sender=headers.get("From", ""),
                subject=headers.get("Subject", ""),
                snippet=msg.get("snippet", "")[:2000],
            )
        )
    return out
