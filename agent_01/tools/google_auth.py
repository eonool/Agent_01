"""Local OAuth helper for live mode. credentials.json / token.json are git-ignored."""

from __future__ import annotations

from pathlib import Path

from ..config import REPO_ROOT

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/documents",
]
TOKEN_PATH = REPO_ROOT / "token.json"
CLIENT_SECRET_PATH = REPO_ROOT / "credentials.json"


def get_credentials():
    """Return user OAuth credentials, running the local consent flow if needed."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not Path(CLIENT_SECRET_PATH).exists():
            raise FileNotFoundError(
                "credentials.json not found. Create an OAuth Desktop client and save it at repo root."
            )
        creds = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES).run_local_server(port=0)
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds
