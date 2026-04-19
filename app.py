"""
Interactive holdings dashboard: overview, NYSE+TSX trading days, flags, goals.

Run from this folder:
  pip install -r requirements.txt
  streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")

from ai_flags import Flag, heuristic_flags, openai_flags  # noqa: E402
from contributions import monthly_contribution  # noqa: E402
from goals_store import PortfolioGoals, load_goals, save_goals  # noqa: E402
from history_store import load_snapshots, snapshots_to_dataframe, upsert_snapshot  # noqa: E402
from market_calendar import now_et, session_context_for_today, trading_schedule_day  # noqa: E402
from portfolio_loader import approx_total_market_value_cad, load_holdings_csv, parse_as_of_date  # noqa: E402


def _mv_cad_row(row: pd.Series, usd_cad: float) -> float:
    mv = row.get("Market Value")
    if mv is None or pd.isna(mv):
        return 0.0
    ccy = str(row.get("mv_ccy", "CAD")).upper()
    v = float(mv)
    return v * usd_cad if ccy == "USD" else v


def account_market_value_cad(df: pd.DataFrame, usd_cad: float) -> pd.DataFrame:
    keys = [k for k in ["Account Name", "Account Type", "Account Number"] if k in df.columns]
    if not keys:
        keys = ["Account Name"]
    t = df.copy()
    t["_mv_cad"] = t.apply(lambda r: _mv_cad_row(r, usd_cad), axis=1)
    g = t.groupby(keys, dropna=False)["_mv_cad"].sum().reset_index(name="market_value_cad")
    g["label"] = g.apply(
        lambda r: " · ".join(str(r[k]) for k in keys if pd.notna(r[k]) and str(r[k]).strip()),
        axis=1,
    )
    return g


def security_bucket(row: pd.Series) -> str:
    stype = str(row.get("Security Type", "") or "").upper().replace(" ", "_")
    if "EXCHANGE_TRADED" in stype or stype.endswith("_ETF") or stype == "ETF":
        return "ETF"
    if stype == "EQUITY":
        return "Stock"
    return "Other"


def stocks_vs_etf_cad(df: pd.DataFrame, usd_cad: float) -> pd.DataFrame:
    t = df.copy()
    t["_mv_cad"] = t.apply(lambda r: _mv_cad_row(r, usd_cad), axis=1)
    t["asset_class"] = t.apply(security_bucket, axis=1)
    g = t.groupby("asset_class", dropna=False)["_mv_cad"].sum().reset_index(name="market_value_cad")
    return g


def symbol_weight_cad(df: pd.DataFrame, usd_cad: float) -> pd.DataFrame:
    t = df.copy()
    t["_mv_cad"] = t.apply(lambda r: _mv_cad_row(r, usd_cad), axis=1)
    g = t.groupby("Symbol", dropna=False)["_mv_cad"].sum().reset_index(name="market_value_cad")
    total = float(g["market_value_cad"].sum()) or 1.0
    g["weight_pct"] = g["market_value_cad"] / total * 100.0
    return g.sort_values("market_value_cad", ascending=False)


def render_flag(f: Flag) -> None:
    icon = {"info": "ℹ️", "warn": "⚠️", "alert": "🚨"}.get(f.severity, "•")
    st.markdown(f"**{icon} {f.title}**  \n{f.detail}")
    if f.symbols:
        st.caption(", ".join(f.symbols))


def main() -> None:
    st.set_page_config(page_title="Holdings dashboard", layout="wide")
    default_csv = _ROOT / "data" / "holdings-report-2026-04-18.csv"

    st.title("Holdings dashboard")
    st.caption("Tracks NYSE + TSX trading days, surfaces risk flags, and stores goals next to this app.")

    ctx = session_context_for_today()
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Date (US/Eastern)", ctx["today_et"])
    with col_b:
        st.metric(
            "Both NYSE & TSX open today",
            "Yes" if ctx["joint_session_today"] else "No",
        )
    with col_c:
        st.caption(
            f"Previous joint session: {ctx['previous_joint_session'] or '—'}  \n"
            f"Next joint session: {ctx['next_joint_session'] or '—'}"
        )

    with st.sidebar:
        st.header("Data")
        uploaded = st.file_uploader("Upload holdings CSV", type=["csv"])
        path_str = st.text_input(
            "Or path to CSV on disk",
            value=str(default_csv) if default_csv.exists() else "",
        )
        st.header("FX (for CAD totals)")
        usd_cad = st.number_input("USD → CAD", min_value=0.5, max_value=2.5, value=1.38, step=0.01)

    path = Path(path_str) if path_str.strip() else default_csv
    if uploaded is not None:
        tmp = _ROOT / "_uploaded_holdings.csv"
        tmp.write_bytes(uploaded.getvalue())
        path = tmp

    if not path.exists():
        st.error("CSV path not found. Upload a file or set a valid path.")
        st.stop()

    try:
        df, as_of = load_holdings_csv(path)
    except Exception as e:
        st.exception(e)
        st.stop()

    if as_of:
        st.success(as_of)
    as_of_ts = parse_as_of_date(as_of)
    if as_of_ts is not None:
        st.caption(f"Parsed as-of date: {as_of_ts.date()}")

    total_cad = approx_total_market_value_cad(df, usd_cad)
    goals_path = _ROOT / "portfolio_goals.json"
    snapshots_path = _ROOT / "portfolio_snapshots.json"
    if "goals_cache" not in st.session_state:
        st.session_state["goals_cache"] = load_goals(goals_path)
    goals: PortfolioGoals = st.session_state["goals_cache"]

    acct = account_market_value_cad(df, usd_cad)
    sym = symbol_weight_cad(df, usd_cad)
    by_account_cad = {str(r["label"]): float(r["market_value_cad"]) for _, r in acct.iterrows()}
    by_symbol_cad = {str(r["Symbol"]): float(r["market_value_cad"]) for _, r in sym.iterrows()}

    if as_of_ts is not None:
        upsert_snapshot(
            as_of_ts.date(),
            total_cad,
            usd_cad,
            "broker_as_of",
            by_account_cad=by_account_cad,
            by_symbol_cad=by_symbol_cad,
            path=snapshots_path,
        )

    with st.sidebar:
        st.header("Portfolio history")
        if st.button("Record snapshot for today (Eastern)", help="Stores today’s totals using the USD→CAD rate above."):
            upsert_snapshot(
                now_et().date(),
                total_cad,
                usd_cad,
                "manual_today",
                by_account_cad=by_account_cad,
                by_symbol_cad=by_symbol_cad,
                path=snapshots_path,
            )
            st.success("Snapshot saved.")

    tab_over, tab_hist, tab_mkt, tab_ai, tab_goals = st.tabs(
        ["Overview", "History", "Market days", "AI & flags", "Goals"]
    )

    with tab_over:
        m1, m2, m3 = st.columns(3)
        m1.metric("Positions", str(len(df)))
        m2.metric("Approx total MV (CAD)", f"${total_cad:,.0f}")
        ur = df["Market Unrealized Returns"].sum(skipna=True)
        m3.metric("Sum unrealized (mixed ccy)", f"{ur:,.2f}")

        bucket = stocks_vs_etf_cad(df, usd_cad)
        c1, c2 = st.columns(2)
        with c1:
            fig_a = px.pie(acct, names="label", values="market_value_cad", hole=0.35, title="By account (CAD approx)")
            st.plotly_chart(fig_a, use_container_width=True)
        with c2:
            fig_b = px.pie(
                bucket,
                names="asset_class",
                values="market_value_cad",
                hole=0.35,
                title="Stock vs ETF vs other (CAD approx)",
            )
            st.plotly_chart(fig_b, use_container_width=True)
        fig_s = px.bar(sym.head(12), x="Symbol", y="weight_pct", title="Weight % by symbol (CAD approx)")
        st.plotly_chart(fig_s, use_container_width=True)

        st.subheader("Holdings")
        show = df[
            [
                c
                for c in [
                    "Account Name",
                    "Symbol",
                    "Name",
                    "Security Type",
                    "Quantity",
                    "mv_ccy",
                    "Market Value",
                    "Market Unrealized Returns",
                ]
                if c in df.columns
            ]
        ]
        st.dataframe(show, use_container_width=True, hide_index=True)

    with tab_hist:
        st.subheader("Portfolio value over time")
        st.caption(
            "Values come from **saved snapshots** in `portfolio_snapshots.json`. Loading a CSV with an "
            "“As of …” footer stores that date automatically. Use **Record snapshot for today** in the "
            "sidebar when you do not have a dated export."
        )

        rows = load_snapshots(snapshots_path)
        hist = snapshots_to_dataframe(rows)
        if hist.empty or "total_market_value_cad" not in hist.columns:
            st.info("No history yet. Load a holdings CSV with an “As of …” footer, or record a manual snapshot.")
        else:
            hx = hist.copy()
            hx["date"] = pd.to_datetime(hx["date"], errors="coerce")
            hx = hx.dropna(subset=["date"]).sort_values("date")
            fig_l = px.line(
                hx,
                x="date",
                y="total_market_value_cad",
                markers=True,
                title="Total market value (CAD, snapshot basis)",
                hover_data=["source", "usd_cad"],
            )
            st.plotly_chart(fig_l, use_container_width=True)
            show_h = hx.assign(date=lambda d: d["date"].dt.date.astype(str))[
                ["date", "total_market_value_cad", "usd_cad", "source", "recorded_at"]
            ]
            st.dataframe(show_h, use_container_width=True, hide_index=True)

    with tab_mkt:
        st.write(
            "Use joint **NYSE + TSX** sessions as a simple “real market day” gate when your "
            "portfolio spans both Canada-listed and US-listed names."
        )
        pick = st.date_input("Inspect a calendar date", value=pd.Timestamp.now().date())
        sched = trading_schedule_day(pick)
        st.json(sched)

    with tab_ai:
        st.write(
            "**Rules-based flags** always run (concentration, single-stock sleeve, deep drawdowns). "
            "If `OPENAI_API_KEY` is set in `.env`, optional model commentary is merged in."
        )
        hf = heuristic_flags(df, goals)
        of, oerr = openai_flags(df, goals)
        merged: list[Flag] = list(hf)
        if of:
            merged.extend(of)
        if oerr:
            st.warning(oerr)

        if not merged:
            st.info("No flags right now.")
        else:
            for f in merged:
                render_flag(f)
                st.divider()

    with tab_goals:
        st.write("Goals are saved to `portfolio_goals.json` in this same folder.")
        with st.form("goals_form"):
            tgt_pv = st.number_input(
                "Target total portfolio value (CAD, optional)",
                min_value=0.0,
                value=float(goals.target_portfolio_value_cad or 0.0),
                step=1000.0,
            )
            months_goal = st.number_input(
                "Months to reach that target (for contribution math)",
                min_value=0,
                value=int(goals.months_to_goal or 0),
                step=1,
            )
            tgt_ret = st.number_input(
                "Expected annual return % (used for contribution math; optional)",
                min_value=0.0,
                max_value=50.0,
                value=float(goals.target_annual_return_pct or 0.0),
                step=0.5,
            )
            max_pos = st.number_input("Max single position % per account", value=float(goals.max_single_position_pct or 25.0), step=1.0)
            max_eq = st.number_input("Max non-index equity % per account", value=float(goals.max_equity_non_index_pct or 15.0), step=1.0)
            notes = st.text_area("Notes", value=goals.notes, height=80)
            submitted = st.form_submit_button("Save goals")

        if submitted:
            goals.target_portfolio_value_cad = tgt_pv if tgt_pv > 0 else None
            goals.target_annual_return_pct = float(tgt_ret)
            goals.months_to_goal = int(months_goal) if months_goal > 0 else None
            goals.max_single_position_pct = max_pos
            goals.max_equity_non_index_pct = max_eq
            goals.notes = notes
            if goals.account_targets_cad is None:
                goals.account_targets_cad = {}
            save_goals(goals, goals_path)
            st.session_state["goals_cache"] = goals
            st.success("Saved.")

        st.subheader("Progress vs portfolio target")
        if goals.target_portfolio_value_cad:
            pct = min(100.0, max(0.0, total_cad / goals.target_portfolio_value_cad * 100.0))
            st.progress(min(1.0, pct / 100.0))
            st.caption(f"{pct:.1f}% of ${goals.target_portfolio_value_cad:,.0f} CAD (approx)")
        else:
            st.caption("Set a target total above to see a progress bar.")

        st.subheader("Monthly contribution (estimate)")
        st.caption(
            "Assumes end-of-month contributions, the same **expected annual return** on both your "
            "current balance and new deposits, and the **months to goal** horizon. Not tax or fee advice."
        )
        if goals.target_portfolio_value_cad and goals.months_to_goal:
            pay, warn = monthly_contribution(
                current_value=total_cad,
                target_value=float(goals.target_portfolio_value_cad),
                months=int(goals.months_to_goal),
                annual_return_pct=goals.target_annual_return_pct,
            )
            st.metric("Approx. monthly contribution (CAD)", f"${pay:,.2f}")
            if warn:
                st.warning(warn)
        else:
            st.info("Set a **target portfolio value (CAD)** and **months to goal**, then save goals.")

        st.subheader("Per-account targets (CAD, optional)")
        at = dict(goals.account_targets_cad or {})
        new_at: dict[str, float] = {}
        for _, row in acct.iterrows():
            label = str(row["label"])
            cur = float(row["market_value_cad"])
            prev = float(at.get(label, 0.0) or 0.0)
            tgt = st.number_input(f"Target for {label}", min_value=0.0, value=prev, step=500.0, key=f"acct_tgt_{label}")
            if tgt > 0:
                new_at[label] = tgt
                st.caption(f"Current (approx CAD): ${cur:,.0f} → {min(100.0, cur / tgt * 100.0):.1f}% of target")

        if st.button("Save per-account targets"):
            goals.account_targets_cad = new_at
            save_goals(goals, goals_path)
            st.session_state["goals_cache"] = goals
            st.success("Account targets saved.")


if __name__ == "__main__":
    main()
