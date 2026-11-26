"""Agent_01: fetch -> summarize (parallel) -> build agenda -> human approval -> publish.

Design notes (mapped to the assessment rubric):
- Strategic model routing: extraction/summarization/publishing use the fast model;
  the agenda builder (prioritisation and reasoning) uses the reasoning model.
- Human-in-the-loop: publishing to the shared Google Doc requires explicit user
  confirmation (ADK tool confirmation), configurable for unattended runs.
- Context management: ADK events compaction summarises older turns.
- Long-term memory: structured action items (JSON/Firestore) plus semantic
  session memory via ADK MemoryService (Vertex AI Memory Bank) when configured.
"""

from __future__ import annotations

import logging

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.apps import App
from google.adk.apps.app import EventsCompactionConfig
from google.adk.tools import FunctionTool, preload_memory

from . import prompts
from .config import load_config
from .observability import (
    after_agent_log,
    after_model_redact,
    after_tool_log,
    before_agent_log,
    before_tool_guard,
    setup_tracing,
)
from .schemas import AccountSummary, BiweeklyAgenda
from .tools import (
    get_previous_action_items,
    get_review_period,
    publish_biweekly_review_tab,
    save_action_items,
    search_account_emails,
)

setup_tracing()
logger = logging.getLogger("agent_01.agent")
CFG = load_config()
FAST_MODEL = CFG.fast_model
REASONING_MODEL = CFG.reasoning_model

_cb = {
    "before_agent_callback": before_agent_log,
    "after_agent_callback": after_agent_log,
    "after_model_callback": after_model_redact,
}
_tool_cb = {"before_tool_callback": before_tool_guard, "after_tool_callback": after_tool_log}


async def save_session_to_memory_callback(callback_context) -> None:
    """Store the finished review session in the ADK memory service (if one is configured)."""
    after_agent_log(callback_context)
    try:
        await callback_context.add_session_to_memory()
        logger.info('{"event": "session_saved_to_memory"}')
    except Exception as e:  # noqa: BLE001 - no memory service configured is fine
        logger.info('{"event": "memory_service_unavailable", "reason": "%s"}', type(e).__name__)


gmail_fetcher_agent = LlmAgent(
    name="gmail_fetcher_agent",
    model=FAST_MODEL,
    description="Collects the review period, account emails and previous action items.",
    instruction=prompts.FETCHER_INSTRUCTION,
    tools=[get_review_period, search_account_emails, get_previous_action_items, preload_memory],
    output_key="raw_inputs",
    **_cb, **_tool_cb,
)


def _summarizer(alias: str) -> LlmAgent:
    return LlmAgent(
        name=f"summarizer_{alias.lower()}",
        model=FAST_MODEL,
        description=f"Summarizes two weeks of achievements for {alias}.",
        instruction=prompts.summarizer_instruction(alias),
        output_schema=AccountSummary,
        output_key=f"summary_{alias.lower()}",
        **_cb,
    )


parallel_summarizer = ParallelAgent(
    name="parallel_account_summarizer",
    description="Summarizes each account concurrently.",
    sub_agents=[_summarizer("ACCOUNT_A"), _summarizer("ACCOUNT_B")],
)

agenda_builder_agent = LlmAgent(
    name="agenda_builder_agent",
    model=REASONING_MODEL,
    description="Prioritises wins, risks and follow-ups into a manager 1:1 agenda.",
    instruction=prompts.AGENDA_INSTRUCTION,
    output_schema=BiweeklyAgenda,
    output_key="biweekly_agenda",
    **_cb,
)

publish_tool = FunctionTool(
    publish_biweekly_review_tab,
    require_confirmation=CFG.require_publish_confirmation,
)

publisher_agent = LlmAgent(
    name="publisher_agent",
    model=FAST_MODEL,
    description="Asks for approval, publishes the report as a new Google Docs tab and saves memory.",
    instruction=prompts.PUBLISHER_INSTRUCTION,
    tools=[publish_tool, save_action_items],
    before_agent_callback=before_agent_log,
    after_agent_callback=save_session_to_memory_callback,
    after_model_callback=after_model_redact,
    **_tool_cb,
)

root_agent = SequentialAgent(
    name="biweekly_review_orchestrator",
    description="Bi-weekly achievement summary and 1:1 agenda generator.",
    sub_agents=[gmail_fetcher_agent, parallel_summarizer, agenda_builder_agent, publisher_agent],
)

app = App(
    name="agent_01",
    root_agent=root_agent,
    events_compaction_config=EventsCompactionConfig(compaction_interval=4, overlap_size=1),
)
