"""Long-term memory across review cycles.

Two layers:
1. Structured action-item store (this module). Backends:
   - "json"      : local file, default for demo/tests
   - "firestore" : persistent Firestore collection (provisioned by Terraform)
2. Semantic session memory via ADK MemoryService (Vertex AI Memory Bank),
   enabled with `adk web --memory_service_uri=agentengine://<engine_id>`;
   see agent.py (`preload_memory` + `save_session_to_memory_callback`).

Tools are async; writes run in a background thread so the agent loop is not blocked.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date
from typing import Protocol

from ..config import load_config

logger = logging.getLogger("agent_01.tools.memory")
_background_tasks: set[asyncio.Task] = set()


class ActionItemStore(Protocol):
    def last(self) -> dict | None: ...
    def append(self, record: dict) -> None: ...


class JsonFileStore:
    """Local JSON history, keeps the last 12 cycles."""

    def __init__(self, path):
        self.path = path

    def _read(self) -> list[dict]:
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []

    def last(self) -> dict | None:
        history = self._read()
        return history[-1] if history else None

    def append(self, record: dict) -> None:
        history = self._read() + [record]
        self.path.write_text(json.dumps(history[-12:], indent=2), encoding="utf-8")


class FirestoreStore:
    """Persistent store in Firestore collection `agent01_reviews`."""

    def __init__(self, project: str | None, collection: str = "agent01_reviews"):
        from google.cloud import firestore  # optional dependency

        self.col = firestore.Client(project=project).collection(collection)

    def last(self) -> dict | None:
        docs = list(self.col.order_by("saved_on", direction="DESCENDING").limit(1).stream())
        return docs[0].to_dict() if docs else None

    def append(self, record: dict) -> None:
        self.col.document(record["period_label"].replace(" ", "_")).set(record)


def get_store() -> ActionItemStore:
    cfg = load_config()
    if cfg.memory_backend == "firestore":
        return FirestoreStore(cfg.gcp_project)
    return JsonFileStore(cfg.memory_path)


async def get_previous_action_items() -> dict:
    """Return action items saved at the end of the previous bi-weekly review.

    Use these to add a "Follow-ups from last review" agenda item.

    Returns:
        dict with `status`, `period_label` of the last review (or null) and
        `action_items` (list of strings, empty on the first run). On failure,
        `error_message` and `recovery_hint`.
    """
    try:
        last = await asyncio.to_thread(lambda: get_store().last())
    except Exception as e:
        logger.exception("memory read failed")
        return {"status": "error", "action_items": [],
                "error_message": f"Memory read failed: {type(e).__name__}",
                "recovery_hint": "Proceed without follow-ups and mention that memory was unavailable."}
    last = last or {}
    return {"status": "success", "period_label": last.get("period_label"),
            "action_items": last.get("action_items", [])}


async def save_action_items(period_label: str, action_items: list[str]) -> dict:
    """Persist this cycle's action items so the next review can follow up.

    The write is scheduled as a background task and the tool returns at once.

    Args:
        period_label: The review window, e.g. "2026-11-13 to 2026-11-26".
        action_items: Short, owner-oriented action items agreed for next cycle.

    Returns:
        dict with `status` ("scheduled") and `saved_count`, or an error with
        `recovery_hint`.
    """
    if not period_label:
        return {"status": "error", "error_message": "period_label is required.",
                "recovery_hint": "Pass the period_label returned by get_review_period."}
    record = {"period_label": period_label, "saved_on": date.today().isoformat(),
              "action_items": action_items}

    async def _write():
        try:
            await asyncio.to_thread(lambda: get_store().append(record))
            logger.info("saved %d action items for %s", len(action_items), period_label)
        except Exception:
            logger.exception("background memory write failed")

    task = asyncio.create_task(_write())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return {"status": "scheduled", "saved_count": len(action_items)}


async def wait_for_background_writes() -> None:
    """Await pending writes (used by tests and graceful shutdown)."""
    if _background_tasks:
        await asyncio.gather(*list(_background_tasks))
