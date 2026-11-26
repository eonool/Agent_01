"""Runtime configuration for Agent_01.

Customer names never appear in this repository. Accounts are referred to by
neutral aliases (ACCOUNT_A, ACCOUNT_B). The mapping from alias to the real
Gmail label lives only in a local, git-ignored file (`config.local.json`).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_CONFIG_PATH = Path(os.getenv("AGENT01_CONFIG", REPO_ROOT / "config.local.json"))
EXAMPLE_CONFIG_PATH = REPO_ROOT / "config.example.json"


@dataclass(frozen=True)
class AccountConfig:
    """One customer account, identified only by a neutral alias."""

    alias: str
    gmail_label: str
    keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AppConfig:
    """Top-level settings. `mode` is 'demo' (synthetic data) or 'live'."""

    mode: str
    model: str
    accounts: dict[str, AccountConfig]
    google_doc_id: str | None
    output_dir: Path
    memory_path: Path
    lookback_days: int = 14


def load_config() -> AppConfig:
    """Load config.local.json if present, otherwise the public example config."""
    path = LOCAL_CONFIG_PATH if LOCAL_CONFIG_PATH.exists() else EXAMPLE_CONFIG_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    accounts = {
        a["alias"]: AccountConfig(a["alias"], a["gmail_label"], a.get("keywords", []))
        for a in raw["accounts"]
    }
    return AppConfig(
        mode=os.getenv("AGENT01_MODE", raw.get("mode", "demo")),
        model=os.getenv("AGENT01_MODEL", raw.get("model", "gemini-2.5-flash")),
        accounts=accounts,
        google_doc_id=os.getenv("AGENT01_GOOGLE_DOC_ID", raw.get("google_doc_id")),
        output_dir=REPO_ROOT / raw.get("output_dir", "outputs"),
        memory_path=REPO_ROOT / raw.get("memory_path", ".agent01_memory.json"),
        lookback_days=int(raw.get("lookback_days", 14)),
    )
