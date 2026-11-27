"""Backend using locally installed, organisation-approved Workspace CLIs (corp_cli mode).

Used when third-party OAuth clients are blocked for corporate accounts. The CLIs
authenticate with the user's own corporate credentials, so no OAuth client or
token is stored by this project. CLI locations are machine-specific and are
configured only via environment variables (AGENT01_GMAIL_CLI, AGENT01_GDOCS_CLI)
in the git-ignored agent_01/.env file.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone

from ..schemas import EmailRecord, EmailSearchRequest


def _cli(env_var: str) -> str:
    path = os.getenv(env_var)
    if not path:
        raise RuntimeError(f"{env_var} is not set. Add the CLI path to agent_01/.env (git-ignored).")
    return path
_TIMEOUT_S = 180


def gmail_label_query(label: str) -> str:
    """Convert a Gmail label name to search syntax (lowercase, spaces -> '-')."""
    return "label:" + re.sub(r"\s", "-", label.strip().lower())


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=_TIMEOUT_S, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"{os.path.basename(cmd[0])} exited {proc.returncode}: {proc.stderr.strip()[:300]}")
    return proc.stdout


def search_emails(req: EmailSearchRequest, account) -> list[EmailRecord]:
    """Fetch messages for one account label within the request window."""
    before = req.end_date + timedelta(days=1)
    query = (
        f"{gmail_label_query(account.gmail_label)} "
        f"after:{req.start_date:%Y/%m/%d} before:{before:%Y/%m/%d}"
    )
    raw = json.loads(_run([_cli("AGENT01_GMAIL_CLI"), "readonly", "read", query, "--max", str(req.max_results), "--json"]))
    messages = raw if isinstance(raw, list) else raw.get("messages", [])
    out = []
    for m in messages:
        headers = {h.get("name", "").lower(): h.get("value", "") for h in m.get("payload", {}).get("headers", [])}
        sent = datetime.fromtimestamp(int(m["internalDate"]) / 1000, tz=timezone.utc).date()
        out.append(
            EmailRecord(
                message_id=m["id"],
                date=sent,
                sender=headers.get("from", ""),
                subject=headers.get("subject", ""),
                snippet=m.get("snippet", "")[:2000],
            )
        )
    return out


def publish_tab(doc_id: str, tab_title: str, markdown: str) -> str:
    """Create a new tab and import the Markdown report into it with native formatting."""
    created = json.loads(_run([_cli("AGENT01_GDOCS_CLI"), "--json", "mutate", "create-tab", doc_id, "--title", tab_title]))
    tab_id = _find_tab_id(created) or _lookup_tab_id(doc_id, tab_title)
    if not tab_id:
        raise RuntimeError("Tab was created but its ID could not be determined.")
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(markdown)
        path = f.name
    try:
        _run([_cli("AGENT01_GDOCS_CLI"), "mutate", "import-md", path, "--update", doc_id, "--tab", tab_id])
    finally:
        os.unlink(path)
    return f"https://docs.google.com/document/d/{doc_id}/edit?tab={tab_id}"


def _find_tab_id(obj) -> str | None:
    if isinstance(obj, dict):
        for key in ("tabId", "tab_id", "TabID", "id"):
            if isinstance(obj.get(key), str) and obj[key].startswith("t."):
                return obj[key]
        for v in obj.values():
            if (found := _find_tab_id(v)) is not None:
                return found
    if isinstance(obj, list):
        for v in obj:
            if (found := _find_tab_id(v)) is not None:
                return found
    return None


def _lookup_tab_id(doc_id: str, title: str) -> str | None:
    tabs = json.loads(_run([_cli("AGENT01_GDOCS_CLI"), "--json", "readonly", "list-tabs", doc_id]))
    for t in tabs if isinstance(tabs, list) else tabs.get("tabs", []):
        if t.get("title") == title or t.get("Title") == title:
            return _find_tab_id(t)
    return None

