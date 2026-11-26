"""Long-term memory across review cycles (local JSON file, git-ignored)."""

from __future__ import annotations

import json
from datetime import date

from ..config import load_config


def get_previous_action_items() -> dict:
    """Return action items saved at the end of the previous bi-weekly review.

    Use these to add a "Follow-ups from last review" agenda item.

    Returns:
        dict with `status`, `period_label` of the last review (or null) and
        `action_items` (list of strings, empty on the first run).
    """
    path = load_config().memory_path
    if not path.exists():
        return {"status": "success", "period_label": None, "action_items": []}
    try:
        history = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "error", "action_items": [],
                "error_message": "Memory file is corrupted.",
                "recovery_hint": "Proceed without follow-ups and tell the user to check the memory file."}
    last = history[-1] if history else {}
    return {"status": "success", "period_label": last.get("period_label"),
            "action_items": last.get("action_items", [])}


def save_action_items(period_label: str, action_items: list[str]) -> dict:
    """Persist this cycle's action items so the next review can follow up.

    Args:
        period_label: The review window, e.g. "2026-11-13 to 2026-11-26".
        action_items: Short, owner-oriented action items agreed for next cycle.

    Returns:
        dict with `status` and `saved_count`.
    """
    if not period_label:
        return {"status": "error", "error_message": "period_label is required.",
                "recovery_hint": "Pass the period_label returned by get_review_period."}
    path = load_config().memory_path
    history = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    history.append({"period_label": period_label, "saved_on": date.today().isoformat(),
                    "action_items": action_items})
    path.write_text(json.dumps(history[-12:], indent=2), encoding="utf-8")
    return {"status": "success", "saved_count": len(action_items)}
