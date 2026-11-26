"""Observability and guardrail callbacks (structured JSON logs + OpenTelemetry spans)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from .config import load_config
from .redaction import redact, redact_text

logger = logging.getLogger("agent_01.trace")
_START_KEY = "_tool_started_at"


def _log(event: str, **fields: Any) -> None:
    logger.info(json.dumps({"event": event, **fields}, default=str))


def _forbidden_terms() -> list[str]:
    """Real labels from the local config; these must never leave the machine in outputs."""
    terms = []
    for acct in load_config().accounts.values():
        terms.append(acct.gmail_label.split(".")[-1])
        terms.extend(acct.keywords)
    return [t.lower() for t in terms if t and not t.upper().startswith("ACCOUNT_")]


def before_agent_log(callback_context) -> None:
    _log("agent_start", agent=callback_context.agent_name,
         invocation_id=callback_context.invocation_id)


def after_agent_log(callback_context) -> None:
    _log("agent_end", agent=callback_context.agent_name,
         invocation_id=callback_context.invocation_id)


def before_tool_guard(tool, args: dict, tool_context) -> dict | None:
    """Log the call and block arguments that leak real customer names."""
    tool_context.state[_START_KEY] = time.monotonic()
    _log("tool_start", tool=tool.name, args=list(args.keys()))
    blob = json.dumps(args).lower()
    leaked = [t for t in _forbidden_terms() if t in blob]
    if leaked:
        _log("guardrail_block", tool=tool.name)
        return {
            "status": "error",
            "error_message": "Arguments contain a real customer name.",
            "recovery_hint": "Replace customer names with ACCOUNT_A / ACCOUNT_B and call again.",
        }
    return None


def after_tool_log(tool, args: dict, tool_context, tool_response):
    """Log outcome + latency, then actively scrub PII from the response before the LLM sees it."""
    started = tool_context.state.get(_START_KEY)
    latency_ms = round((time.monotonic() - started) * 1000, 1) if started else None
    status = tool_response.get("status") if isinstance(tool_response, dict) else "n/a"
    _log("tool_end", tool=tool.name, status=status, latency_ms=latency_ms)
    if isinstance(tool_response, dict):
        scrubbed = redact(tool_response)
        if scrubbed != tool_response:
            _log("pii_redacted", source="tool_response", tool=tool.name)
            return scrubbed
    return None


def after_model_redact(callback_context, llm_response):
    """Scrub PII from model text output before it is stored in state or shown to the user."""
    content = getattr(llm_response, "content", None)
    if not content or not content.parts:
        return None
    changed = False
    for part in content.parts:
        if getattr(part, "text", None):
            clean = redact_text(part.text)
            if clean != part.text:
                part.text = clean
                changed = True
    if changed:
        _log("pii_redacted", source="model_output", agent=callback_context.agent_name)
        return llm_response
    return None


class RedactingFilter(logging.Filter):
    """Logging filter that scrubs PII from every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage())
        record.args = ()
        return True


def setup_tracing() -> None:
    """Configure JSON logging; export OpenTelemetry spans to Cloud Trace when available."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for handler in logging.getLogger().handlers:
        handler.addFilter(RedactingFilter())
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(CloudTraceSpanExporter()))
        trace.set_tracer_provider(provider)
        _log("tracing_enabled", exporter="cloud_trace")
    except Exception as e:  # noqa: BLE001 - tracing is optional
        _log("tracing_disabled", reason=type(e).__name__)
