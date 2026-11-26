# Agent_01 — Bi-weekly Review Agent

An ADK multi-agent system that turns two weeks of customer email into a
grounded achievement summary and a focused manager 1:1 agenda, published as a
new tab in a Google Doc every two weeks.

## Problem
Preparing a bi-weekly 1:1 means manually scanning dozens of customer emails
across multiple accounts. It is slow, and wins, risks and follow-ups get missed.

## Solution
Agent_01 fetches the last 14 days of labeled email per account, summarizes each
account in parallel with strict schemas, builds a 30-minute agenda that
includes follow-ups from the previous cycle, and publishes it as a dated tab.

Track: **Enterprise Agents**.

## Architecture
```mermaid
flowchart LR
  U[User / bi-weekly schedule] --> R[biweekly_review_orchestrator<br/>SequentialAgent]
  R --> F[gmail_fetcher_agent]
  F -->|get_review_period<br/>search_account_emails<br/>get_previous_action_items| S
  S[parallel_account_summarizer<br/>ParallelAgent] --> SA[summarizer_account_a]
  S --> SB[summarizer_account_b]
  SA & SB --> A[agenda_builder_agent<br/>output_schema=BiweeklyAgenda]
  A --> P[publisher_agent]
  P -->|publish_biweekly_review_tab<br/>save_action_items| D[(Google Doc tab / memory)]
```

| Rubric area | Where in code |
|---|---|
| Tool & Interface Design | `agent_01/tools/*` — specific names, full docstrings, Pydantic schemas (`schemas.py`), `recovery_hint` on every error |
| Context & Memory | `prompts.py` constitution; session state via `output_key`; cross-cycle memory in `memory_tools.py` |
| Orchestration & Logic | `agent.py` — Sequential + Parallel agents, structured outputs |
| Observability & Tracing | `observability.py` — JSON logs, tool latency, privacy guardrail callback, Cloud Trace exporter |
| Infrastructure & CI/CD | `pyproject.toml`, `tests/`, `tests/eval/`, GitHub Actions, `Dockerfile`, `scripts/deploy.sh` |

## Privacy by design
- Customers are only ever called `ACCOUNT_A` / `ACCOUNT_B`. The real label
  mapping lives in git-ignored `config.local.json`.
- The public demo uses synthetic emails (`agent_01/data/synthetic_emails.json`).
- A `before_tool_callback` blocks tool calls that contain real customer names.
- CI runs a denylist scan driven by a GitHub secret.

## Quick start (demo mode)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp agent_01/.env.example agent_01/.env   # set GOOGLE_CLOUD_PROJECT
gcloud auth application-default login
pytest -q
adk web .          # open the UI, select agent_01
# or: adk run agent_01
adk eval agent_01 tests/eval/demo.evalset.json
```
Demo output is written to `outputs/<date>_Bi-weekly_Review.md`.

## Live mode (local only)
1. `pip install -e ".[live]"`
2. Create an OAuth Desktop client, save as `credentials.json` (git-ignored).
3. Create `config.local.json` from `config.example.json` with your real Gmail
   labels, `"mode": "live"` and your Google Doc ID.
4. `adk run agent_01` — first run opens the OAuth consent screen.

## Scheduling
Run every other Monday, e.g. cron:
`0 9 * * 1 [ $(( $(date +\%V) \% 2 )) -eq 0 ] && cd ~/Agent_01 && adk run agent_01 <<< "Prepare my bi-weekly review"`

## Deploy
`GOOGLE_CLOUD_PROJECT=<project> scripts/deploy.sh` (Cloud Run, demo mode).
