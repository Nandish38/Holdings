"""NYSE + TSX session awareness for portfolio review on real trading days."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import pandas_market_calendars as mcal


def trading_schedule_day(session_date: date) -> dict:
    """NYSE and TSX open/close on a calendar date in local exchange time."""
    nyse = mcal.get_calendar("XNYS")
    tsx = mcal.get_calendar("XTSE")
    day = pd.Timestamp(session_date)

    def _session(cal: mcal.MarketCalendar, name: str) -> dict:
        sched = cal.schedule(start_date=day, end_date=day)
        if sched.empty:
            return {"exchange": name, "is_session": False, "open": None, "close": None}
        row = sched.iloc[0]
        return {
            "exchange": name,
            "is_session": True,
            "open": row["market_open"].to_pydatetime(),
            "close": row["market_close"].to_pydatetime(),
        }

    return {
        "date": session_date.isoformat(),
        "nyse": _session(nyse, "NYSE"),
        "tsx": _session(tsx, "TSX"),
    }


def is_joint_equity_session(session_date: date) -> bool:
    info = trading_schedule_day(session_date)
    return bool(info["nyse"]["is_session"] and info["tsx"]["is_session"])


def next_trading_day(from_date: date, *, max_step: int = 14) -> date | None:
    d = from_date
    for _ in range(max_step):
        d = d + timedelta(days=1)
        if is_joint_equity_session(d):
            return d
    return None


def previous_trading_day(from_date: date, *, max_step: int = 14) -> date | None:
    d = from_date
    for _ in range(max_step):
        d = d - timedelta(days=1)
        if is_joint_equity_session(d):
            return d
    return None


def now_et() -> datetime:
    return datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York"))


def session_context_for_today() -> dict:
    """Human-oriented snapshot for the dashboard header."""
    today = now_et().date()
    sched = trading_schedule_day(today)
    joint = sched["nyse"]["is_session"] and sched["tsx"]["is_session"]
    prev_ = previous_trading_day(today)
    nxt = next_trading_day(today)
    return {
        "today_et": today.isoformat(),
        "joint_session_today": joint,
        "nyse": sched["nyse"],
        "tsx": sched["tsx"],
        "previous_joint_session": prev_.isoformat() if prev_ else None,
        "next_joint_session": nxt.isoformat() if nxt else None,
    }
