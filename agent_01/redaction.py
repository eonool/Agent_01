"""Active PII scrubbing applied to tool responses, model outputs and logs.

Redacts:
- email addresses           -> [EMAIL]
- phone numbers             -> [PHONE]
- monetary amounts          -> [AMOUNT]
- real customer names/terms -> ACCOUNT_A / ACCOUNT_B (from git-ignored local config)
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from .config import load_config

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)\d{3,4}[\s.-]?\d{4}(?!\d)")
AMOUNT_RE = re.compile(r"(?:[$€£₩]\s?\d[\d,]*(?:\.\d+)?(?:\s?[kKmMbB])?|\d[\d,]*(?:\.\d+)?\s?(?:USD|KRW|EUR|원))")


@lru_cache(maxsize=1)
def _customer_term_map() -> tuple[tuple[re.Pattern, str], ...]:
    """Map real customer terms to their neutral alias (longest terms first)."""
    pairs = []
    for alias, acct in load_config().accounts.items():
        for term in [acct.gmail_label, acct.gmail_label.split(".")[-1], *acct.keywords]:
            if term and not term.upper().endswith(alias):
                pairs.append((term, alias))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return tuple((re.compile(re.escape(t), re.IGNORECASE), a) for t, a in pairs)


def redact_text(text: str) -> str:
    """Return `text` with PII and real customer names scrubbed."""
    if not text:
        return text
    for pattern, alias in _customer_term_map():
        text = pattern.sub(alias, text)
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = AMOUNT_RE.sub("[AMOUNT]", text)
    return PHONE_RE.sub("[PHONE]", text)


def redact(obj: Any) -> Any:
    """Recursively scrub strings inside dicts/lists (tool responses)."""
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj
