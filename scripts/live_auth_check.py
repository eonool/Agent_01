"""One-time OAuth login + connectivity check for live mode.

Usage (on the machine that runs the agent):
    python scripts/live_auth_check.py
Prints the consent URL; after approval it verifies Gmail label access and
Google Doc access, without printing any email content.
"""

from googleapiclient.discovery import build

from agent_01.config import load_config
from agent_01.tools.google_auth import get_credentials


def main() -> None:
    cfg = load_config()
    creds = get_credentials()
    gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)
    labels = {lab["name"] for lab in gmail.users().labels().list(userId="me").execute()["labels"]}
    for alias, acct in cfg.accounts.items():
        print(f"{alias}: label found = {acct.gmail_label in labels}")
    if cfg.google_doc_id:
        docs = build("docs", "v1", credentials=creds, cache_discovery=False)
        doc = docs.documents().get(documentId=cfg.google_doc_id, includeTabsContent=True).execute()
        print(f"Google Doc reachable, tabs = {len(doc.get('tabs', []))}")
    else:
        print("google_doc_id not set")


if __name__ == "__main__":
    main()
