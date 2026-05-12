"""Pydantic response and request models for the Holdings API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str = "holdings"


class PortfolioSummary(BaseModel):
    as_of: str | None = None
    total_cad: float
    positions: int
    unrealized: float
    usd_cad: float
    top_position: str | None = None


class HoldingRow(BaseModel):
    data: dict[str, Any]


class AllocationResponse(BaseModel):
    security_type: list[dict[str, Any]]
    currency: list[dict[str, Any]]
    accounts: list[dict[str, Any]]
    symbols: list[dict[str, Any]]


class ReturnsHistoryResponse(BaseModel):
    rows: list[dict[str, Any]]
    account_history: list[dict[str, Any]]
    symbol_history: list[dict[str, Any]]
    summary: dict[str, float]


class UniverseResponse(BaseModel):
    key: str
    label: str
    symbols: list[str]


class ActivityPayload(BaseModel):
    when: str
    kind: str
    symbol: str | None = None
    qty: float | None = None
    price: float | None = None
    ccy: str | None = "CAD"
    text: str = ""


class JournalPayload(BaseModel):
    when: str
    title: str
    category: str = "Thesis"
    body: str = ""
    symbol: str | None = None


class GoalsPayload(BaseModel):
    target_portfolio_value_cad: float | None = None
    target_annual_return_pct: float | None = None
    months_to_goal: int | None = None
    max_single_position_pct: float | None = 25.0
    max_equity_non_index_pct: float | None = 15.0
    notes: str = ""
    account_targets_cad: dict[str, float] = Field(default_factory=dict)
