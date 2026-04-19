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
from us_market_watch import (  # noqa: E402
    DEFAULT_FULL_WATCHLIST,
    build_us_watch_table,
    fetch_major_indices,
    index_strip_updated_at,
)


def _render_major_indices_strip() -> None:
    rows = fetch_major_indices()
    c1, c2, c3 = st.columns(3)
    for col, r in zip((c1, c2, c3), rows):
        with col:
            nm = str(r.get("label", ""))
            px = r.get("last")
            chg = r.get("day_chg_pct")
            if px is None:
                st.metric(nm, "—")
            else:
                ccy = (r.get("ccy") or "").strip()
                suf = f" {ccy}" if ccy else ""
                st.metric(
                    nm,
                    f"{float(px):,.2f}{suf}",
                    f"{float(chg):+.2f}%" if chg is not None else None,
                )
    st.caption(
        f"Yahoo · vs prior daily close · {index_strip_updated_at()} · not real-time; exchange rules & vendor delay apply."
    )


@st.cache_data(ttl=600, show_spinner=False)
def _cached_us_watch(sort_by: str, top_n: int, custom: str) -> pd.DataFrame:
    extra = [s.strip().upper() for s in custom.replace(",", " ").split() if s.strip()]
    if extra:
        tickers: tuple[str, ...] = tuple(dict.fromkeys(list(DEFAULT_FULL_WATCHLIST) + extra))
    else:
        tickers = DEFAULT_FULL_WATCHLIST
    return build_us_watch_table(sort_by=sort_by, top_n=int(top_n), tickers=tickers)


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
    icon = {"info": "•", "warn": "!", "alert": "!!"}.get(f.severity, "•")
    st.markdown(f"**{icon} {f.title}** — {f.detail}")


def main() -> None:
    st.set_page_config(page_title="Holdings", layout="wide", initial_sidebar_state="expanded")
    default_csv = _ROOT / "data" / "holdings-report-2026-04-18.csv"

    st.title("Holdings")

    ctx = session_context_for_today()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("US/Eastern", ctx["today_et"])
    c2.metric("NYSE+TSX today", "Yes" if ctx["joint_session_today"] else "No")
    c3.metric("Prev session", ctx["previous_joint_session"] or "—")
    c4.metric("Next session", ctx["next_joint_session"] or "—")

    with st.sidebar:
        st.markdown("### File")
        uploaded = st.file_uploader("CSV", type=["csv"], label_visibility="collapsed")
        path_str = st.text_input(
            "Path",
            value=str(default_csv) if default_csv.exists() else "",
            placeholder="path/to/holdings.csv",
            label_visibility="collapsed",
        )
        st.markdown("### FX")
        usd_cad = st.slider("USD→CAD", 0.5, 2.5, 1.38, 0.01)

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

    as_of_ts = parse_as_of_date(as_of)
    if as_of:
        with st.expander("File as-of", expanded=False):
            st.write(as_of)

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
        st.markdown("### Snapshot")
        if st.button("Save today (ET)"):
            upsert_snapshot(
                now_et().date(),
                total_cad,
                usd_cad,
                "manual_today",
                by_account_cad=by_account_cad,
                by_symbol_cad=by_symbol_cad,
                path=snapshots_path,
            )
            st.sidebar.success("OK")

    tab_over, tab_us, tab_hist, tab_mkt, tab_ai, tab_goals = st.tabs(
        ["Portfolio", "Watchlist", "History", "Calendar", "Flags", "Goals"]
    )

    with tab_over:
        m1, m2, m3 = st.columns(3)
        m1.metric("Positions", str(len(df)))
        m2.metric("Approx total MV (CAD)", f"${total_cad:,.0f}")
        ur = df["Market Unrealized Returns"].sum(skipna=True)
        m3.metric("Unrealized Σ", f"{ur:,.0f}")

        bucket = stocks_vs_etf_cad(df, usd_cad)
        c1, c2 = st.columns(2)
        with c1:
            fig_a = px.pie(acct, names="label", values="market_value_cad", hole=0.4, title="Accounts")
            fig_a.update_layout(margin=dict(t=30, b=0, l=0, r=0), showlegend=True, legend_font_size=11)
            st.plotly_chart(fig_a, use_container_width=True)
        with c2:
            fig_b = px.pie(bucket, names="asset_class", values="market_value_cad", hole=0.4, title="Stock / ETF / other")
            fig_b.update_layout(margin=dict(t=30, b=0, l=0, r=0), showlegend=True, legend_font_size=11)
            st.plotly_chart(fig_b, use_container_width=True)
        fig_s = px.bar(sym.head(12), x="Symbol", y="weight_pct", title="Weights %")
        fig_s.update_layout(xaxis_title=None, yaxis_title="%", margin=dict(t=40, b=0, l=0, r=0))
        st.plotly_chart(fig_s, use_container_width=True)

        st.markdown("**Lines**")
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
        st.dataframe(show, use_container_width=True, hide_index=True, height=320)

    with tab_us:
        st.markdown("**S&P 500 · Nasdaq · Nifty 50**")
        try:
            import inspect

            _frag = getattr(st, "fragment", None)
            if _frag is not None and "run_every" in inspect.signature(_frag).parameters:
                _frag(run_every=45)(_render_major_indices_strip)()
            else:
                _render_major_indices_strip()
        except Exception:
            _render_major_indices_strip()

        st.divider()
        st.markdown(
            "**US + TSX basket** — ranked by recent % change. Not every TSX listing; curated liquid names, ETFs, and common CDRs."
        )
        with st.expander("Data notes", expanded=False):
            st.markdown(
                "**P/E** and **dividend yield** come from Yahoo `info` when present (often delayed). "
                "**Implied upside** = analyst mean target vs last price, not a forecast. "
                "Index strip uses 5m bars when Yahoo serves them; still subject to vendor delay vs a live terminal."
            )
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            sort_by = st.selectbox("Sort", ["1M %", "3M %"], index=0)
        with c2:
            top_n = st.slider("Rows", 10, 40, 22)
        with c3:
            custom = st.text_input("Extra tickers (spaces/commas)", placeholder="e.g. GME, MSTR")

        if st.button("Refresh prices", type="primary"):
            _cached_us_watch.clear()

        with st.spinner("Loading…"):
            try:
                watch = _cached_us_watch(sort_by, top_n, custom or "")
            except Exception as e:
                watch = pd.DataFrame()
                st.error(str(e))
        if watch is None or watch.empty:
            st.info("No rows (network or rate limit). Try Refresh again.")
        else:
            st.dataframe(watch, use_container_width=True, hide_index=True)
            bar_x = sort_by if sort_by in watch.columns else "1M %"
            color_col = "1M %" if "1M %" in watch.columns else bar_x
            fig_m = px.bar(
                watch.head(15).iloc[::-1],
                x=bar_x,
                y="Symbol",
                orientation="h",
                title=f"Top 15 ({bar_x})",
                color=color_col if color_col in watch.columns else bar_x,
                color_continuous_scale="Tealgrn",
            )
            fig_m.update_layout(yaxis=dict(categoryorder="total ascending"), margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig_m, use_container_width=True)

    with tab_hist:
        with st.expander("How history is built"):
            st.write("Snapshots in `portfolio_snapshots.json`. CSV “As of” dates save automatically; sidebar **Save today** adds today.")

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
                title="Total MV (CAD)",
                hover_data=["source", "usd_cad"],
            )
            fig_l.update_layout(margin=dict(t=40, b=0, l=0, r=0))
            st.plotly_chart(fig_l, use_container_width=True)
            show_h = hx.assign(date=lambda d: d["date"].dt.date.astype(str))[
                ["date", "total_market_value_cad", "usd_cad", "source", "recorded_at"]
            ]
            st.dataframe(show_h, use_container_width=True, hide_index=True)

    with tab_mkt:
        pick = st.date_input("Date", value=pd.Timestamp.now().date())
        sched = trading_schedule_day(pick)
        ny = sched["nyse"]["is_session"]
        tsx = sched["tsx"]["is_session"]
        st.markdown(f"**NYSE** {'session' if ny else 'closed'} · **TSX** {'session' if tsx else 'closed'}")
        with st.expander("Schedule JSON"):
            st.json(sched)

    with tab_ai:
        st.caption("Rules + optional OpenAI if `OPENAI_API_KEY` is set.")
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
        st.caption("Persisted in `portfolio_goals.json`.")

        st.subheader("Target & contribution")
        g1, g2, g3 = st.columns(3)
        with g1:
            tgt_pv = st.number_input(
                "Target (CAD)",
                min_value=0.0,
                value=float(goals.target_portfolio_value_cad or 0.0),
                step=1000.0,
            )
        with g2:
            _default_months = (
                int(goals.months_to_goal)
                if goals.months_to_goal and goals.months_to_goal > 0
                else 120
            )
            months_goal = st.number_input(
                "Months",
                min_value=1,
                max_value=600,
                value=_default_months,
                step=1,
            )
        with g3:
            _ret = goals.target_annual_return_pct
            if _ret is None:
                _ret = 5.0
            tgt_ret = st.number_input(
                "Model return %/yr",
                min_value=0.0,
                max_value=50.0,
                value=float(_ret),
                step=0.5,
            )

        st.subheader("Monthly deposit (model)")
        if tgt_pv > 0:
            gap = tgt_pv - total_cad
            st.caption(f"Now **${total_cad:,.0f}** · gap **${gap:,.0f}** · **{months_goal}** mo")
            pay, warn = monthly_contribution(
                current_value=total_cad,
                target_value=float(tgt_pv),
                months=int(months_goal),
                annual_return_pct=float(tgt_ret),
            )
            st.metric("Monthly (CAD)", f"${pay:,.0f}")
            if warn:
                st.warning(warn)
        else:
            st.caption("Enter a target (CAD).")

        st.subheader("Progress")
        if tgt_pv > 0:
            pct = min(100.0, max(0.0, total_cad / tgt_pv * 100.0))
            st.progress(min(1.0, pct / 100.0))
            st.caption(f"{pct:.1f}% of ${tgt_pv:,.0f}")
        else:
            st.caption("Set a target.")

        with st.form("goals_form"):
            max_pos = st.number_input("Max position %", value=float(goals.max_single_position_pct or 25.0), step=1.0)
            max_eq = st.number_input("Max non-index equity %", value=float(goals.max_equity_non_index_pct or 15.0), step=1.0)
            notes = st.text_area("Notes", value=goals.notes, height=72)
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

        st.subheader("Per-account targets")
        at = dict(goals.account_targets_cad or {})
        new_at: dict[str, float] = {}
        for _, row in acct.iterrows():
            label = str(row["label"])
            cur = float(row["market_value_cad"])
            prev = float(at.get(label, 0.0) or 0.0)
            tgt = st.number_input(label, min_value=0.0, value=prev, step=500.0, key=f"acct_tgt_{label}")
            if tgt > 0:
                new_at[label] = tgt
                st.caption(f"${cur:,.0f} → {min(100.0, cur / tgt * 100.0):.0f}%")

        if st.button("Save account targets"):
            goals.account_targets_cad = new_at
            save_goals(goals, goals_path)
            st.session_state["goals_cache"] = goals
            st.success("Account targets saved.")


if __name__ == "__main__":
    main()
