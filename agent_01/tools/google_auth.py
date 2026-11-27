"""OAuth for live mode.

Credential sources, in priority order:
1. Google Secret Manager (when `oauth_client_secret_name` / `oauth_token_secret_name`
   are configured; provisioned by infra/terraform). Used for deployed runs.
2. Local git-ignored files `credentials.json` / `token.json`. Used on a laptop.
No secret is ever hardcoded in the repository.
"""

from __future__ import annotations

import json
import logging
import os

from ..config import REPO_ROOT, load_config

logger = logging.getLogger("agent_01.auth")
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/documents",
]
TOKEN_PATH = REPO_ROOT / "token.json"
CLIENT_SECRET_PATH = REPO_ROOT / "credentials.json"


def read_secret(project: str, secret_id: str) -> str:
    """Read the latest version of a Secret Manager secret as text."""
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project}/secrets/{secret_id}/versions/latest"
    return client.access_secret_version(name=name).payload.data.decode("utf-8")


def write_secret(project: str, secret_id: str, value: str) -> None:
    """Add a new version to a Secret Manager secret (used to persist refreshed tokens)."""
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{project}/secrets/{secret_id}"
    client.add_secret_version(parent=parent, payload={"data": value.encode("utf-8")})


def get_credentials():
    """Return user OAuth credentials from Secret Manager or local files."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    cfg = load_config()
    use_sm = bool(cfg.gcp_project and cfg.oauth_token_secret_name)

    creds = None
    if use_sm:
        info = json.loads(read_secret(cfg.gcp_project, cfg.oauth_token_secret_name))
        creds = Credentials.from_authorized_user_info(info, SCOPES)
        logger.info("loaded OAuth token from Secret Manager")
    elif TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        creds = _run_consent_flow(cfg)
    _persist(cfg, creds, use_sm)
    return creds


def _run_consent_flow(cfg):
    from google_auth_oauthlib.flow import InstalledAppFlow

    if cfg.gcp_project and cfg.oauth_client_secret_name:
        client_config = json.loads(read_secret(cfg.gcp_project, cfg.oauth_client_secret_name))
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    elif CLIENT_SECRET_PATH.exists():
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
    else:
        raise FileNotFoundError(
            "No OAuth client found. Configure oauth_client_secret_name (Secret Manager) "
            "or place credentials.json at the repo root."
        )
    # Fixed port so the redirect can be SSH-forwarded from a laptop to a remote VM:
    #   ssh -L 8765:localhost:8765 <vm>
    port = int(os.getenv("AGENT01_OAUTH_PORT", "8765"))
    return flow.run_local_server(port=port, open_browser=False)


def _persist(cfg, creds, use_sm: bool) -> None:
    if use_sm:
        write_secret(cfg.gcp_project, cfg.oauth_token_secret_name, creds.to_json())
    else:
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
