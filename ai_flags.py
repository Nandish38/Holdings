"""Portfolio risk flags: deterministic checks plus optional OpenAI commentary."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import pandas as pd

from goals_store import PortfolioGoals


@dataclass
class Flag:
    severity: str  # "info" | "warn" | "alert"
    title: str
    detail: str
    symbols: list[str]


def _is_broad_indexish(row: pd.Series) -> bool:
    st = str(row.get("Security Type", "")).upper()
    name = str(row.get("Name", "")).upper()
    sym = str(row.get("Symbol", "")).upper()
    if "EXCHANGE_TRADED" in st or "ETF" in st:
        return any(k in name for k in ("INDEX", "S&P", "NASDAQ", "500", "100")) or sym in (
            "VFV",
            "QQQ",
            "QQC",
            "VOO",
            "IVV",
            "SPY",
        )
    return False


def heuristic_flags(df: pd.DataFrame, goals: PortfolioGoals) -> list[Flag]:
    flags: list[Flag] = []
    if df.empty:
        return flags

    keys = [k for k in ["Account Name", "Account Number"] if k in df.columns]
    group_cols = keys if keys else ["Account Name"]
    for acc_key, part in df.groupby(group_cols, dropna=False):
        label = " / ".join(str(x) for x in (acc_key if isinstance(acc_key, tuple) else (acc_key,)))
        total_mv = part["Market Value"].sum()
        if total_mv <= 0 or pd.isna(total_mv):
            continue
        for sym, sym_part in part.groupby("Symbol"):
            w = float(sym_part["Market Value"].sum() / total_mv * 100.0)
            max_pct = goals.max_single_position_pct
            if max_pct is not None and w > max_pct:
                flags.append(
                    Flag(
                        severity="warn",
                        title=f"Concentration in {sym}",
                        detail=f"{sym} is ~{w:.1f}% of {label} market value (goal: max {max_pct:.0f}% per name).",
                        symbols=[str(sym)],
                    )
                )

    max_eq = goals.max_equity_non_index_pct
    for acc_key, part in df.groupby(group_cols, dropna=False):
        label = " / ".join(str(x) for x in (acc_key if isinstance(acc_key, tuple) else (acc_key,)))
        eq = part[~part.apply(_is_broad_indexish, axis=1)].copy()
        eq = eq[eq["Security Type"].astype(str).str.upper().eq("EQUITY")]
        if eq.empty:
            continue
        total_mv = part["Market Value"].sum()
        eq_mv = eq["Market Value"].sum()
        if total_mv <= 0:
            continue
        w = float(eq_mv / total_mv * 100.0)
        if max_eq is not None and w > max_eq:
            syms = sorted(eq["Symbol"].astype(str).unique().tolist())
            flags.append(
                Flag(
                    severity="info",
                    title=f"Single-stock equity sleeve ({label})",
                    detail=f"Non-index equities are ~{w:.1f}% of account MV (guideline: {max_eq:.0f}%).",
                    symbols=syms,
                )
            )

    for _, row in df.iterrows():
        mv = row.get("Market Value")
        ur = row.get("Market Unrealized Returns")
        if mv is None or ur is None or pd.isna(mv) or pd.isna(ur) or float(mv) <= 0:
            continue
        pnl_pct = float(ur) / float(mv) * 100.0
        if str(row.get("Security Type", "")).upper() == "EQUITY" and pnl_pct < -15:
            flags.append(
                Flag(
                    severity="alert",
                    title=f"Deep drawdown: {row.get('Symbol')}",
                    detail=f"Unrealized P&L is about {pnl_pct:.1f}% of current market value.",
                    symbols=[str(row.get("Symbol"))],
                )
            )

    seen: set[tuple[str, tuple[str, ...]]] = set()
    out: list[Flag] = []
    for f in flags:
        k = (f.title, tuple(sorted(f.symbols)))
        if k in seen:
            continue
        seen.add(k)
        out.append(f)
    return out


def openai_flags(df: pd.DataFrame, goals: PortfolioGoals) -> tuple[list[Flag] | None, str | None]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None, None

    try:
        from openai import OpenAI
    except ImportError:
        return None, "openai package not installed (pip install openai)"

    summary = df[
        [
            c
            for c in [
                "Account Name",
                "Symbol",
                "Name",
                "Security Type",
                "Quantity",
                "Market Value",
                "Market Value Currency",
                "Market Unrealized Returns",
            ]
            if c in df.columns
        ]
    ].head(80)

    goals_blob = goals.to_dict()
    client = OpenAI(api_key=api_key)
    prompt = (
        "You are a portfolio risk assistant. Given holdings and user goals JSON, "
        "return ONLY valid JSON: {\"flags\":[{\"severity\":\"info|warn|alert\","
        "\"title\":string,\"detail\":string,\"symbols\":[string]}]} "
        "Focus on concentration, tax-advantaged account fit (FHSA/TFSA), overlap, "
        "currency mismatch, and obvious single-stock risk. Be concise.\n\n"
        f"HOLDINGS_CSV_PREVIEW:\n{summary.to_csv(index=False)}\n\nGOALS:\n{json.dumps(goals_blob)}"
    )
    resp = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": "Return only JSON. No markdown."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    text = (resp.choices[0].message.content or "").strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None, "Model did not return valid JSON."

    out: list[Flag] = []
    for item in payload.get("flags", []):
        if not isinstance(item, dict):
            continue
        sev = str(item.get("severity", "info")).lower()
        if sev not in ("info", "warn", "alert"):
            sev = "info"
        syms = item.get("symbols") or []
        if isinstance(syms, str):
            syms = [syms]
        syms = [str(s) for s in syms if s]
        out.append(
            Flag(
                severity=sev,
                title=str(item.get("title", "Note")),
                detail=str(item.get("detail", "")),
                symbols=syms,
            )
        )
    return out, None
