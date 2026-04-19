"""
Interactive holdings dashboard: overview, NYSE+TSX trading days, flags, goals.

Run from this folder:
  pip install -r requirements.txt
  streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.colors import sample_colorscale
from dotenv import load_dotenv

from ui_theme import (  # noqa: E402
    REVEAL_KEY,
    holdings_table_for_display,
    inject_vault_css,
    mask_cad,
    mask_plain,
    mask_signed_cad,
    reveal_balances,
    watchlist_table_for_display,
)

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
    rev = reveal_balances()
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
                suf = f" {ccy}" if ccy and rev else ""
                val = mask_plain(float(px), reveal=rev, decimals=2) + (suf if rev else "")
                st.metric(nm, val, f"{float(chg):+.2f}%" if chg is not None else None)
    st.caption(
        f"Pulse · Yahoo · {index_strip_updated_at()} · vendor delay applies"
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


def symbol_weight_cad(df: pd.DataFrame, usd_cad: float) -> pd.DataFrame:
    t = df.copy()
    t["_mv_cad"] = t.apply(lambda r: _mv_cad_row(r, usd_cad), axis=1)
    g = t.groupby("Symbol", dropna=False)["_mv_cad"].sum().reset_index(name="market_value_cad")
    total = float(g["market_value_cad"].sum()) or 1.0
    g["weight_pct"] = g["market_value_cad"] / total * 100.0
    return g.sort_values("market_value_cad", ascending=False)


def _is_equity_type(st: object) -> bool:
    return str(st).upper().strip() == "EQUITY"


def _is_etf_type(st: object) -> bool:
    u = str(st).upper().replace(" ", "_")
    return "EXCHANGE_TRADED" in u or u.endswith("_ETF") or u == "ETF"


def rollup_symbols_by_return(df: pd.DataFrame, usd_cad: float) -> pd.DataFrame:
    """One row per symbol: CAD MV, unrealized P&L % vs MV, label = full name + (ticker)."""
    t = df.copy()
    t["_mv_cad"] = t.apply(lambda r: _mv_cad_row(r, usd_cad), axis=1)
    t["_ur"] = pd.to_numeric(t.get("Market Unrealized Returns"), errors="coerce").fillna(0.0)
    g = t.groupby("Symbol", as_index=False, dropna=False).agg(
        market_value_cad=("_mv_cad", "sum"),
        unrealized=("_ur", "sum"),
        Name=("Name", "first"),
        Security_Type=("Security Type", "first"),
    )
    mv = g["market_value_cad"].astype(float)
    ur = g["unrealized"].astype(float)
    g["ret_pct"] = (ur / mv.replace(0, np.nan) * 100.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    nm = g["Name"].astype(str).str.strip()
    g["pie_label"] = nm.where(nm.str.len() > 0, g["Symbol"].astype(str)) + " (" + g["Symbol"].astype(str) + ")"
    return g


def _u_from_returns(ret: pd.Series) -> np.ndarray:
    """Map return % to [0,1] for RdYlGn: negatives→red side, positives→green; span respects min/max."""
    a = ret.replace([np.inf, -np.inf], np.nan).fillna(0.0).astype(float).to_numpy()
    if len(a) == 0:
        return np.array([])
    lo, hi = float(np.min(a)), float(np.max(a))
    if not np.isfinite(lo) or not np.isfinite(hi):
        return np.full(len(a), 0.5)
    if hi <= lo:
        return np.full(len(a), 0.5)
    if lo >= 0:
        return np.clip(0.5 + 0.5 * (a - lo) / (hi - lo + 1e-9), 0.0, 1.0)
    if hi <= 0:
        return np.clip(0.5 * (a - lo) / (0.0 - lo + 1e-9), 0.0, 1.0)
    u = np.zeros_like(a, dtype=float)
    neg = a <= 0.0
    u[neg] = 0.5 * (a[neg] - lo) / (0.0 - lo + 1e-9)
    u[~neg] = 0.5 + 0.5 * (a[~neg]) / (hi + 1e-9)
    return np.clip(u, 0.0, 1.0)


def pie_holdings_colored_by_return(sub: pd.DataFrame, title: str, *, reveal: bool) -> go.Figure:
    fig = go.Figure()
    if sub is None or sub.empty:
        fig.update_layout(title=dict(text=title), annotations=[dict(text="No rows", showarrow=False, x=0.5, y=0.5)])
        return fig
    sub = sub.loc[sub["market_value_cad"].astype(float) > 0].copy()
    if sub.empty:
        fig.update_layout(title=dict(text=title), annotations=[dict(text="No rows", showarrow=False, x=0.5, y=0.5)])
        return fig
    sub = sub.sort_values("market_value_cad", ascending=False)
    r = sub["ret_pct"]
    u = _u_from_returns(r)
    colors = [sample_colorscale("RdYlGn", float(ui))[0] for ui in u]
    if reveal:
        tinfo = "label+percent"
        ht = "<b>%{label}</b><br>MV (CAD): %{value:,.2f}<br>Return vs MV: %{customdata:.2f}%<extra></extra>"
    else:
        tinfo = "percent"
        ht = "<b>%{label}</b><br>Weight: %{percent}<br>Return vs MV: %{customdata:.2f}%<extra></extra>"
    fig.add_trace(
        go.Pie(
            labels=sub["pie_label"],
            values=sub["market_value_cad"],
            marker=dict(colors=colors, line=dict(color="#1a1a1a", width=0.6)),
            hole=0.38,
            textinfo=tinfo,
            textposition="outside",
            insidetextorientation="horizontal",
            hovertemplate=ht,
            customdata=r.astype(float),
            sort=False,
        )
    )
    fig.update_layout(
        title=dict(text=title, font=dict(size=14)),
        margin=dict(t=48, b=80, l=20, r=20),
        showlegend=True,
        legend=dict(font=dict(size=9), traceorder="normal"),
        height=560,
    )
    return fig


def pie_accounts_vault(acct: pd.DataFrame, *, reveal: bool) -> go.Figure:
    if acct is None or acct.empty:
        return go.Figure()
    fig = px.pie(acct, names="label", values="market_value_cad", hole=0.42, title="Chamber · by vault")
    if not reveal:
        fig.update_traces(
            textinfo="percent",
            hovertemplate="<b>%{label}</b><br>Share: %{percent}<extra></extra>",
        )
    else:
        fig.update_traces(
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>CAD: %{value:,.0f}<br>%{percent}<extra></extra>",
        )
    fig.update_layout(margin=dict(t=36, b=0, l=0, r=0), showlegend=True, legend_font_size=10)
    return fig


def render_flag(f: Flag) -> None:
    icon = {"info": "•", "warn": "!", "alert": "!!"}.get(f.severity, "•")
    st.markdown(f"**{icon} {f.title}** — {f.detail}")


def main() -> None:
    st.set_page_config(page_title="Vaultboard", layout="wide", initial_sidebar_state="expanded", page_icon="◈")
    default_csv = _ROOT / "data" / "holdings-report-2026-04-18.csv"

    if REVEAL_KEY not in st.session_state:
        st.session_state[REVEAL_KEY] = False
    inject_vault_css()

    top_l, _, top_r = st.columns([5, 2, 2])
    with top_l:
        st.markdown("## ◈ Vaultboard")
        st.caption("composition · risk · pulse — not advice")
    with top_r:
        st.toggle("Show balances", key=REVEAL_KEY, help="Off = dollar amounts hidden in Chamber & Pulse")
    reveal = reveal_balances()

    ctx = session_context_for_today()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("US/Eastern", ctx["today_et"])
    c2.metric("NYSE+TSX today", "Yes" if ctx["joint_session_today"] else "No")
    c3.metric("Prev session", ctx["previous_joint_session"] or "—")
    c4.metric("Next session", ctx["next_joint_session"] or "—")

    with st.sidebar:
        st.markdown("### Ingest")
        uploaded = st.file_uploader("CSV", type=["csv"], label_visibility="collapsed")
        path_str = st.text_input(
            "Path",
            value=str(default_csv) if default_csv.exists() else "",
            placeholder="path/to/holdings.csv",
            label_visibility="collapsed",
        )
        st.markdown("### FX blend")
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
        st.markdown("### Stamp")
        if st.button("Stamp today (ET)"):
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

    with st.expander("Room map", expanded=False):
        st.markdown(
            "**Chamber** = your lines & halos · **Pulse** = indices & watchlist · **Memory** = stamped curve · "
            "**Orbit** = exchange calendar · **Signal** = risk flags · **Horizon** = targets & flow."
        )

    tab_over, tab_us, tab_hist, tab_mkt, tab_ai, tab_goals = st.tabs(
        ["Chamber", "Pulse", "Memory", "Orbit", "Signal", "Horizon"]
    )

    with tab_over:
        lens = st.radio(
            "Chamber lens",
            ["All", "FHSA", "TFSA"],
            horizontal=True,
            label_visibility="collapsed",
            key="vault_lens",
        )
        if lens != "All" and "Account Name" in df.columns:
            df_v = df[df["Account Name"].astype(str).str.upper() == lens.upper()].copy()
        else:
            df_v = df
        if df_v.empty:
            df_v = df
        chamber_total = approx_total_market_value_cad(df_v, usd_cad)
        acct_v = account_market_value_cad(df_v, usd_cad)
        sym_v = symbol_weight_cad(df_v, usd_cad)
        roll = rollup_symbols_by_return(df_v, usd_cad)
        stx = roll[roll["Security_Type"].map(_is_equity_type)].copy()
        etf = roll[roll["Security_Type"].map(_is_etf_type)].copy()

        m1, m2, m3 = st.columns(3)
        m1.metric("Lines", str(len(df_v)))
        m2.metric("Book (CAD)", mask_cad(chamber_total, reveal=reveal))
        ur_v = df_v["Market Unrealized Returns"].sum(skipna=True) if "Market Unrealized Returns" in df_v.columns else 0.0
        m3.metric("Unrealized Σ", mask_plain(float(ur_v), reveal=reveal, decimals=2))

        st.caption(
            "Colour = return vs line MV inside each halo · **Lens** narrows Chamber only (snapshots & goals still full book)."
        )
        ra, rb = st.columns(2)
        with ra:
            st.plotly_chart(pie_accounts_vault(acct_v, reveal=reveal), use_container_width=True)
        with rb:
            st.plotly_chart(
                pie_holdings_colored_by_return(stx, "Equities — every name", reveal=reveal),
                use_container_width=True,
            )
        st.plotly_chart(
            pie_holdings_colored_by_return(etf, "Funds — every name", reveal=reveal),
            use_container_width=True,
        )
        fig_s = px.bar(sym_v.head(12), x="Symbol", y="weight_pct", title="Weight in Chamber %")
        fig_s.update_layout(xaxis_title=None, yaxis_title="%", margin=dict(t=40, b=0, l=0, r=0))
        st.plotly_chart(fig_s, use_container_width=True)

        st.markdown("**Ledger**")
        show_cols = [
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
            if c in df_v.columns
        ]
        show = holdings_table_for_display(df_v[show_cols], reveal=reveal)
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
            st.dataframe(
                watchlist_table_for_display(watch, reveal=reveal),
                use_container_width=True,
                hide_index=True,
            )
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
        with st.expander("How Memory is built"):
            st.write("Snapshots in `portfolio_snapshots.json`. CSV “As of” dates stamp automatically; sidebar **Stamp today** adds today.")

        rows = load_snapshots(snapshots_path)
        hist = snapshots_to_dataframe(rows)
        if hist.empty or "total_market_value_cad" not in hist.columns:
            st.info("No history yet. Load a holdings CSV with an “As of …” footer, or stamp a day.")
        else:
            hx = hist.copy()
            hx["date"] = pd.to_datetime(hx["date"], errors="coerce")
            hx = hx.dropna(subset=["date"]).sort_values("date")
            if reveal:
                ycol = "total_market_value_cad"
                ttl = "Total MV (CAD)"
            else:
                base = float(hx["total_market_value_cad"].iloc[0]) or 1.0
                hx["_idx"] = hx["total_market_value_cad"].astype(float) / base * 100.0
                ycol = "_idx"
                ttl = "Indexed path (first day = 100)"
            fig_l = px.line(
                hx,
                x="date",
                y=ycol,
                markers=True,
                title=ttl,
                hover_data=["source", "usd_cad"] if reveal else ["source"],
            )
            fig_l.update_layout(margin=dict(t=40, b=0, l=0, r=0))
            if not reveal:
                fig_l.update_traces(hovertemplate="<b>%{x}</b><br>Index: %{y:.2f}<extra></extra>")
            st.plotly_chart(fig_l, use_container_width=True)
            show_h = hx.assign(date=lambda d: d["date"].dt.date.astype(str))[
                ["date", "total_market_value_cad", "usd_cad", "source", "recorded_at"]
            ]
            if not reveal:
                show_h["total_market_value_cad"] = "·······"
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
            st.caption(
                f"Now **{mask_cad(total_cad, reveal=reveal)}** · gap **{mask_cad(gap, reveal=reveal)}** · **{months_goal}** mo"
            )
            pay, warn = monthly_contribution(
                current_value=total_cad,
                target_value=float(tgt_pv),
                months=int(months_goal),
                annual_return_pct=float(tgt_ret),
            )
            st.metric("Monthly (CAD)", mask_cad(pay, reveal=reveal, decimals=0))
            if warn:
                st.warning(warn)
        else:
            st.caption("Enter a target (CAD).")

        st.subheader("Progress")
        if tgt_pv > 0:
            pct = min(100.0, max(0.0, total_cad / tgt_pv * 100.0))
            st.progress(min(1.0, pct / 100.0))
            st.caption(f"{pct:.1f}% of {mask_cad(tgt_pv, reveal=reveal)}")
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
                st.caption(f"{mask_cad(cur, reveal=reveal)} → {min(100.0, cur / tgt * 100.0):.0f}%")

        if st.button("Save account targets"):
            goals.account_targets_cad = new_at
            save_goals(goals, goals_path)
            st.session_state["goals_cache"] = goals
            st.success("Account targets saved.")


if __name__ == "__main__":
    main()
