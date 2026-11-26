"""Structural tests: the agent graph is wired as designed."""

from agent_01 import agent as agent_mod
from agent_01.agent import app, root_agent


def test_pipeline_order():
    assert [a.name for a in root_agent.sub_agents] == [
        "gmail_fetcher_agent",
        "parallel_account_summarizer",
        "agenda_builder_agent",
        "publisher_agent",
    ]


def test_parallel_summarizers_have_schemas():
    par = root_agent.sub_agents[1]
    assert {a.name for a in par.sub_agents} == {"summarizer_account_a", "summarizer_account_b"}
    assert all(a.output_schema is not None for a in par.sub_agents)


def test_model_routing_uses_reasoning_model_for_agenda():
    assert agent_mod.agenda_builder_agent.model == agent_mod.REASONING_MODEL
    assert agent_mod.gmail_fetcher_agent.model == agent_mod.FAST_MODEL
    assert agent_mod.REASONING_MODEL != agent_mod.FAST_MODEL


def test_publish_requires_human_confirmation_by_default():
    assert agent_mod.publish_tool._require_confirmation is True


def test_app_has_events_compaction():
    assert app.events_compaction_config is not None
