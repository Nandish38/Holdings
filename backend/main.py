"""FastAPI app exposing the Holdings backend API."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import services
from backend.schemas import (
    ActivityPayload,
    AllocationResponse,
    GoalsPayload,
    HealthResponse,
    HoldingRow,
    JournalPayload,
    PortfolioSummary,
    ReturnsHistoryResponse,
    UniverseResponse,
)


app = FastAPI(title="Holdings API", version="0.1.0")

cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
cors_origins.extend(
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
    if origin.strip()
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/api/portfolio/summary", response_model=PortfolioSummary)
def portfolio_summary(usd_cad: float = 1.38) -> dict:
    return services.portfolio_summary(usd_cad=usd_cad)


@app.get("/api/portfolio/holdings", response_model=list[HoldingRow])
def portfolio_holdings(usd_cad: float = 1.38) -> list[dict]:
    return [{"data": row} for row in services.holdings_rows(usd_cad=usd_cad)]


@app.get("/api/portfolio/allocation", response_model=AllocationResponse)
def portfolio_allocation(usd_cad: float = 1.38) -> dict:
    return services.allocation_payload(usd_cad=usd_cad)


@app.get("/api/returns/history", response_model=ReturnsHistoryResponse)
def returns_history() -> dict:
    return services.returns_payload()


@app.get("/api/markets/universes", response_model=list[UniverseResponse])
def market_universes(refresh: bool = False) -> list[dict]:
    return services.universes_payload(refresh=refresh)


@app.get("/api/activity")
def get_activity() -> list[dict]:
    return services.activity_rows()


@app.post("/api/activity")
def post_activity(payload: ActivityPayload) -> list[dict]:
    return services.add_activity(payload.model_dump())


@app.get("/api/journal")
def get_journal() -> list[dict]:
    return services.journal_rows()


@app.post("/api/journal")
def post_journal(payload: JournalPayload) -> list[dict]:
    return services.add_journal(payload.model_dump())


@app.get("/api/goals", response_model=GoalsPayload)
def get_goals() -> dict:
    return services.goals_payload()


@app.put("/api/goals", response_model=GoalsPayload)
def put_goals(payload: GoalsPayload) -> dict:
    return services.update_goals(payload.model_dump())


@app.get("/api/alerts")
def alerts(usd_cad: float = 1.38) -> list[dict]:
    return services.alerts_payload(usd_cad=usd_cad)
