"""Strict Pydantic schemas for tool inputs/outputs and agent outputs."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

AccountAlias = Literal["ACCOUNT_A", "ACCOUNT_B"]


class EmailSearchRequest(BaseModel):
    """Validated arguments for search_account_emails."""

    account_alias: AccountAlias
    start_date: date
    end_date: date
    max_results: int = Field(default=50, ge=1, le=200)

    @field_validator("end_date")
    @classmethod
    def _end_after_start(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be on or after start_date")
        return v


class EmailRecord(BaseModel):
    """A single email reduced to the fields the summarizer needs."""

    message_id: str
    date: date
    sender: str
    subject: str
    snippet: str = Field(max_length=2000)


class EmailSearchResult(BaseModel):
    status: Literal["success", "error"]
    account_alias: str
    emails: list[EmailRecord] = Field(default_factory=list)
    error_message: str | None = None
    recovery_hint: str | None = None


class Achievement(BaseModel):
    title: str
    impact: str
    evidence_message_ids: list[str] = Field(default_factory=list)


class AccountSummary(BaseModel):
    """Structured output of each account summarizer agent."""

    account_alias: AccountAlias
    achievements: list[Achievement] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    asks_for_manager: list[str] = Field(default_factory=list)
    next_two_weeks: list[str] = Field(default_factory=list)


class AgendaItem(BaseModel):
    topic: str
    account_alias: str | None = None
    talking_points: list[str] = Field(default_factory=list)
    minutes: int = Field(default=5, ge=1, le=30)


class BiweeklyAgenda(BaseModel):
    """Structured output of the agenda builder agent."""

    period_label: str
    executive_summary: str
    agenda: list[AgendaItem]
    action_items: list[str] = Field(default_factory=list)


class PublishResult(BaseModel):
    status: Literal["success", "error"]
    destination: str | None = None
    tab_title: str | None = None
    error_message: str | None = None
    recovery_hint: str | None = None
