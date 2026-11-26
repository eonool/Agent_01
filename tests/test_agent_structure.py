"""Structural tests: the agent graph is wired as designed."""

from agent_01.agent import root_agent


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
