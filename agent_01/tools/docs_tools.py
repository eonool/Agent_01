"""Publishing tool: one new Google Docs tab per bi-weekly review.

demo mode : writes outputs/<tab_title>.md
live mode : adds a tab to the configured Google Doc and inserts the report
"""

from __future__ import annotations

import logging
import re

from ..config import load_config
from ..schemas import PublishResult

logger = logging.getLogger("agent_01.tools.docs")
_TAB_TITLE_RE = re.compile(r"^\d{4}-\d{2}-\d{2} Bi-weekly Review$")


def publish_biweekly_review_tab(tab_title: str, report_markdown: str) -> dict:
    """Publish the bi-weekly report as a new tab in the review Google Doc.

    Args:
        tab_title: Tab name in the exact form "YYYY-MM-DD Bi-weekly Review",
            where the date is the end of the review period.
        report_markdown: Full report text (summary + agenda + action items).
            Must not contain real customer names; use ACCOUNT_A / ACCOUNT_B.

    Returns:
        dict matching PublishResult with `status`, `destination`, `tab_title`,
        or `error_message` + `recovery_hint` on failure.
    """
    if not _TAB_TITLE_RE.match(tab_title):
        return _err(tab_title, f"Invalid tab_title '{tab_title}'.",
                    "Use the format 'YYYY-MM-DD Bi-weekly Review' with the period end date.")
    if not report_markdown.strip():
        return _err(tab_title, "report_markdown is empty.",
                    "Build the report from the account summaries and agenda, then call again.")

    cfg = load_config()
    try:
        if cfg.mode == "live":
            if not cfg.google_doc_id:
                return _err(tab_title, "No Google Doc configured.",
                            "Set google_doc_id in config.local.json or AGENT01_GOOGLE_DOC_ID.")
            dest = _publish_live(cfg.google_doc_id, tab_title, report_markdown)
        else:
            cfg.output_dir.mkdir(parents=True, exist_ok=True)
            path = cfg.output_dir / f"{tab_title.replace(' ', '_')}.md"
            path.write_text(report_markdown, encoding="utf-8")
            dest = str(path)
    except Exception as e:
        logger.exception("publish failed")
        return _err(tab_title, f"Publish failed: {type(e).__name__}: {e}",
                    "Retry once. If it still fails, return the report text to the user so nothing is lost.")
    logger.info("published tab '%s' to %s", tab_title, dest)
    return PublishResult(status="success", destination=dest, tab_title=tab_title).model_dump()


def _err(tab_title: str, msg: str, hint: str) -> dict:
    return PublishResult(status="error", tab_title=tab_title, error_message=msg, recovery_hint=hint).model_dump()


def _publish_live(doc_id: str, tab_title: str, text: str) -> str:
    from googleapiclient.discovery import build

    from .google_auth import get_credentials

    docs = build("docs", "v1", credentials=get_credentials(), cache_discovery=False)
    reply = docs.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"addDocumentTab": {"tabProperties": {"title": tab_title}}}]},
    ).execute()
    tab_id = reply["replies"][0]["addDocumentTab"]["tabProperties"]["tabId"]
    docs.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"insertText": {"location": {"index": 1, "tabId": tab_id}, "text": text}}]},
    ).execute()
    return f"https://docs.google.com/document/d/{doc_id}/edit?tab={tab_id}"
