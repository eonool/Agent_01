"""Agent_01 root agent: fetch -> summarize (parallel) -> build agenda -> publish."""

from __future__ import annotations

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

from . import prompts
from .config import load_config
from .observability import (
    after_agent_log,
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
MODEL = load_config().model
_cb = {"before_agent_callback": before_agent_log, "after_agent_callback": after_agent_log}
_tool_cb = {"before_tool_callback": before_tool_guard, "after_tool_callback": after_tool_log}

gmail_fetcher_agent = LlmAgent(
    name="gmail_fetcher_agent",
    model=MODEL,
    description="Collects the review period, account emails and previous action items.",
    instruction=prompts.FETCHER_INSTRUCTION,
    tools=[get_review_period, search_account_emails, get_previous_action_items],
    output_key="raw_inputs",
    **_cb, **_tool_cb,
)


def _summarizer(alias: str) -> LlmAgent:
    return LlmAgent(
        name=f"summarizer_{alias.lower()}",
        model=MODEL,
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
    model=MODEL,
    description="Builds the manager 1:1 agenda from account summaries.",
    instruction=prompts.AGENDA_INSTRUCTION,
    output_schema=BiweeklyAgenda,
    output_key="biweekly_agenda",
    **_cb,
)

publisher_agent = LlmAgent(
    name="publisher_agent",
    model=MODEL,
    description="Publishes the report as a new Google Docs tab and saves memory.",
    instruction=prompts.PUBLISHER_INSTRUCTION,
    tools=[publish_biweekly_review_tab, save_action_items],
    **_cb, **_tool_cb,
)

root_agent = SequentialAgent(
    name="biweekly_review_orchestrator",
    description="Bi-weekly achievement summary and 1:1 agenda generator.",
    sub_agents=[gmail_fetcher_agent, parallel_summarizer, agenda_builder_agent, publisher_agent],
)
