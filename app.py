"""
Interactive holdings dashboard: overview, NYSE+TSX trading days, flags, goals.

Run from this folder:
  pip install -r requirements.txt
  streamlit run app.py
"""

from __future__ import annotations

import html
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
    inject_lekha_css,
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
from activity_store import ActivityItem, append_activity, load_activity, today_iso as today_iso_activity  # noqa: E402
from journal_store import JournalEntry, append_entry, load_journal, today_iso as today_iso_journal  # noqa: E402
from market_universe import get_universes  # noqa: E402
from broker_store import BrokerConnection, get_connection, mark_sync, upsert_connection  # noqa: E402
from plaid_integration import create_link_token, exchange_public_token, investments_holdings, transactions_sync  # noqa: E402
from us_market_watch import (  # noqa: E402
    DEFAULT_FULL_WATCHLIST,
    build_us_watch_table,
    fetch_major_indices,
    index_strip_updated_at,
)
from auth import (  # noqa: E402
    auth_configured,
    is_signed_in,
    render_authorization_page,
    should_gate,
    sign_out,
)


@st.cache_data(ttl=30, show_spinner=False)
def _cached_major_indices():
    """Short TTL so Pulse refreshes without hammering Yahoo; fragment drives reruns."""
    return fetch_major_indices()


def _render_session_calendar_grid(ctx: dict) -> None:
    """HTML grid avoids Streamlit metric ellipsis on ISO dates."""
    today = html.escape(str(ctx["today_et"]))
    joint = "Yes" if ctx["joint_session_today"] else "No"
    prev = html.escape(str(ctx["previous_joint_session"] or "—"))
    nxt = html.escape(str(ctx["next_joint_session"] or "—"))
    st.markdown(
        f"""
<div class="vb-cal-grid">
  <div class="vb-cal-cell"><div class="vb-cal-l">US / Eastern date</div><div class="vb-cal-v">{today}</div></div>
  <div class="vb-cal-cell"><div class="vb-cal-l">NYSE + TSX open today</div><div class="vb-cal-v">{joint}</div></div>
  <div class="vb-cal-cell"><div class="vb-cal-l">Previous joint session</div><div class="vb-cal-v">{prev}</div></div>
  <div class="vb-cal-cell"><div class="vb-cal-l">Next joint session</div><div class="vb-cal-v">{nxt}</div></div>
</div>
        """,
        unsafe_allow_html=True,
    )


def _render_major_indices_strip() -> None:
    # Index levels are public benchmarks — never hide behind the portfolio privacy mask.
    rows = _cached_major_indices()
    parts: list[str] = []
    for r in rows:
        nm = html.escape(str(r.get("label", "")))
        px = r.get("last")
        prev = r.get("prev_close")
        chg = r.get("day_chg_pct")
        ccy = html.escape((str(r.get("ccy") or "").strip() or "USD"))
        if px is None:
            parts.append(
                f'<div class="vb-idx-cell"><div class="vb-idx-name">{nm}</div>'
                f'<div class="vb-idx-row"><span class="vb-idx-last">—</span></div>'
                f'<div class="vb-idx-prev">Prev close unavailable (data)</div></div>'
            )
            continue
        chg_s = f"{float(chg):+.2f}%" if chg is not None else "—"
        cg = float(chg) if chg is not None else 0.0
        cls = "pos" if cg > 0 else ("neg" if cg < 0 else "flat")
        prev_s = f"{float(prev):,.2f}" if prev is not None else "—"
        last_s = f"{float(px):,.2f}"
        parts.append(
            f'<div class="vb-idx-cell"><div class="vb-idx-name">{nm}</div>'
            f'<div class="vb-idx-row"><span class="vb-idx-last">{last_s} {ccy}</span>'
            f'<span class="vb-idx-chg {cls}">{chg_s}</span></div>'
            f'<div class="vb-idx-prev">Prev close {prev_s} {ccy} · vs prior session close</div></div>'
        )
    st.markdown('<div class="vb-idx-grid">' + "".join(parts) + "</div>", unsafe_allow_html=True)
    st.caption(f"Pulse · Yahoo · {index_strip_updated_at()} · vendor delay applies")


def _clear_index_strip_cache() -> None:
    _cached_major_indices.clear()


@st.cache_data(ttl=600, show_spinner=False)
def _cached_us_watch(sort_by: str, top_n: int, custom: str, universe_key: str) -> pd.DataFrame:
    extra = [s.strip().upper() for s in custom.replace(",", " ").split() if s.strip()]
    uni = {u.key: u for u in get_universes(refresh=False)}
    if universe_key == "curated" or universe_key not in uni or not uni[universe_key].symbols:
        base = list(DEFAULT_FULL_WATCHLIST)
    else:
        base = list(uni[universe_key].symbols)
    tickers: tuple[str, ...] = tuple(dict.fromkeys(base + extra))
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


def _is_public_view() -> bool:
    qp = st.query_params
    v = str(qp.get("public", "") or "").strip().lower()
    return v in ("1", "true", "yes", "y", "on")


def _nav_choice() -> str:
    items = ["Home", "Connect", "Portfolio", "Returns", "Markets", "Activity", "Journal", "Signal", "Goals", "Account"]
    default = "Portfolio" if not _is_public_view() else "Home"
    # segmented_control exists in newer Streamlit; fall back to radio for older.
    seg = getattr(st, "segmented_control", None)
    if callable(seg):
        return seg("Navigate", items, default=default, label_visibility="collapsed")  # type: ignore[misc]
    return st.radio("Navigate", items, index=items.index(default), horizontal=True, label_visibility="collapsed")


def _hero(title: str, subtitle: str, *, kicker: str = "Your portfolio, in the open") -> None:
    st.markdown(
        f"""
<div class="lk-hero">
  <div class="lk-hero-kicker">{html.escape(kicker)}</div>
  <div class="lk-hero-title">{html.escape(title)}</div>
  <div class="lk-hero-sub">{html.escape(subtitle)}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def _pillrow(pills: list[tuple[str, str]]) -> None:
    parts = []
    for k, v in pills:
        parts.append(f'<div class="lk-pill"><span class="lk-muted">{html.escape(k)}</span> <strong>{html.escape(v)}</strong></div>')
    st.markdown('<div class="lk-pillrow">' + "".join(parts) + "</div>", unsafe_allow_html=True)


def _kpi_grid(items: list[tuple[str, str, str | None]]) -> None:
    parts = []
    for label, value, sub in items:
        sub_html = f'<div class="lk-kpi-s">{html.escape(sub)}</div>' if sub else ""
        parts.append(
            f'<div class="lk-kpi"><div class="lk-kpi-l">{html.escape(label)}</div>'
            f'<div class="lk-kpi-v lk-mono">{html.escape(value)}</div>{sub_html}</div>'
        )
    st.markdown('<div class="lk-kpi-grid">' + "".join(parts) + "</div>", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(
        page_title="Vaultboard",
        layout="wide",
        initial_sidebar_state="expanded",
        page_icon="◈",
    )
    public = _is_public_view()
    default_csv = _ROOT / "data" / "holdings-report-2026-04-18.csv"

    if REVEAL_KEY not in st.session_state:
        st.session_state[REVEAL_KEY] = False if public else True
    inject_lekha_css()
    if not public:
        inject_vault_css()

    if should_gate(public_view=public):
        render_authorization_page()
        st.stop()

    if public:
        _hero(
            "Vaultboard",
            "One place for allocation, market context, and the story behind your positions.",
            kicker="Portfolio intelligence",
        )
        st.caption("Indicative data · Not real-time · For your records, not investment advice")
    else:
        st.markdown("## Vaultboard")
        h1, h2 = st.columns([4, 1])
        with h1:
            st.caption("Allocation · markets · activity · notes — a clear view of your book")
        with h2:
            st.toggle("Show balances", key=REVEAL_KEY, help="Off = dollar amounts hidden across the app")
    reveal = (False if public else reveal_balances())

    ctx = session_context_for_today()
    if not public:
        _render_session_calendar_grid(ctx)

    uploaded = None
    path_str = str(default_csv) if default_csv.exists() else ""
    usd_cad = 1.38
    if not public:
        with st.sidebar:
            if auth_configured() and is_signed_in():
                st.markdown("### Account")
                if st.button("Sign out", use_container_width=True):
                    sign_out()
                    st.rerun()
                st.caption("You are signed in.")
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
        if not public:
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

    if not public:
        with st.sidebar:
            st.markdown("### Snapshots")
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

            st.markdown("### Share")
            st.caption("Public view hides balances by default.")
            st.code("?public=1", language="text")

    view = _nav_choice()

    if view == "Home":
        _pillrow(
            [
                ("As of", str(as_of_ts.date() if as_of_ts is not None else "—")),
                ("NYSE + TSX open today", "Yes" if ctx["joint_session_today"] else "No"),
                ("USD→CAD", f"{usd_cad:.2f}"),
            ]
        )
        _kpi_grid(
            [
                ("Portfolio value (CAD)", mask_cad(total_cad, reveal=reveal), "Indicative · broker export"),
                ("Positions", str(len(df)), "Lines in the holdings file"),
                (
                    "Unrealized Σ",
                    mask_plain(
                        float(df["Market Unrealized Returns"].sum(skipna=True) if "Market Unrealized Returns" in df.columns else 0.0),
                        reveal=reveal,
                        decimals=2,
                    ),
                    "Across all lines",
                ),
            ]
        )
        st.divider()
        st.subheader("Markets")
        _render_major_indices_strip()
        st.subheader("What this is")
        st.markdown(
            "- **Portfolio**: your positions and weights.\n"
            "- **Returns**: your snapshot curve (stamped from CSV as-of or manual stamps).\n"
            "- **Activity**: a lightweight log of buys/sells/notes.\n"
            "- **Journal**: thesis and exit notes.\n\n"
            "Not investment advice."
        )

    elif view == "Connect":
        st.subheader("Connect broker")
        st.caption("Connect via Plaid to sync holdings + transactions. Tokens are stored locally in `broker_connections.json`.")
        if public:
            st.info("Connect is disabled in public view.")
            st.stop()

        user_id = st.text_input("User id", value="default", help="Used to key the connection locally.")
        conn = get_connection("plaid", user_id) if user_id.strip() else None

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Create Link token"):
                try:
                    tok = create_link_token(user_id=user_id.strip())
                    st.session_state["plaid_link_token"] = tok
                    st.success("Link token created.")
                except Exception as e:
                    st.error(str(e))
        with c2:
            if conn and conn.access_token and st.button("Sync now", type="primary"):
                try:
                    tx_df, next_cursor = transactions_sync(conn.access_token, conn.transactions_cursor)
                    conn.transactions_cursor = next_cursor
                    mark_sync(conn, holdings=False)
                    upsert_connection(conn)

                    # Import transactions into Activity log (best-effort)
                    if tx_df is not None and not tx_df.empty:
                        for _, r in tx_df.head(250).iterrows():
                            # Map to activity note
                            when = str(r.get("date") or "")[:10] or today_iso_activity()
                            name = str(r.get("name") or r.get("merchant_name") or "Transaction")
                            amt = r.get("amount")
                            txt = f"{name} · {amt}" if amt is not None else name
                            append_activity(ActivityItem(when=when, kind="note", text=txt))

                    # Holdings snapshot
                    h = investments_holdings(conn.access_token)
                    if h is not None and not h.empty and "institution_value" in h.columns:
                        # Treat as USD if currency not specified; user can still use FX slider elsewhere.
                        total = float(pd.to_numeric(h["institution_value"], errors="coerce").fillna(0.0).sum())
                        upsert_snapshot(
                            now_et().date(),
                            total_market_value_cad=total,  # stored as "total"; in Connect view we don't FX-convert
                            usd_cad=1.0,
                            source="plaid_sync",
                            path=snapshots_path,
                        )
                        mark_sync(conn, holdings=True)
                        upsert_connection(conn)
                    st.success("Synced.")
                except Exception as e:
                    st.error(str(e))

        st.divider()
        st.markdown("### Paste public_token (dev shortcut)")
        st.caption("If you already ran Plaid Link elsewhere, paste the public_token here to exchange it.")
        public_token = st.text_input("public_token", value="", type="password")
        if st.button("Exchange token") and public_token.strip():
            try:
                ex = exchange_public_token(public_token.strip())
                conn = conn or BrokerConnection(provider="plaid", user_id=user_id.strip())
                conn.access_token = ex["access_token"]
                conn.item_id = ex["item_id"]
                upsert_connection(conn)
                st.success("Connected.")
            except Exception as e:
                st.error(str(e))

        if conn and conn.access_token:
            st.markdown("### Connection status")
            st.json(
                {
                    "provider": conn.provider,
                    "user_id": conn.user_id,
                    "item_id": conn.item_id,
                    "last_sync_at": conn.last_sync_at,
                    "holdings_last_sync_at": conn.holdings_last_sync_at,
                }
            )
        else:
            st.info("Not connected yet. Set Plaid env vars and complete Link, or exchange a public_token.")

    elif view == "Portfolio":
        st.subheader("Portfolio")
        lens = "All"
        if (not public) and "Account Name" in df.columns:
            lens = st.selectbox("Account lens", ["All"] + sorted({str(x).strip() for x in df["Account Name"].dropna().unique()}))
        if lens != "All" and "Account Name" in df.columns:
            df_v = df[df["Account Name"].astype(str).str.strip() == lens].copy()
        else:
            df_v = df
        if df_v.empty:
            df_v = df
        chamber_total = approx_total_market_value_cad(df_v, usd_cad)
        sym_v = symbol_weight_cad(df_v, usd_cad)
        acct_v = account_market_value_cad(df_v, usd_cad)
        _kpi_grid(
            [
                ("Portfolio (CAD)", mask_cad(chamber_total, reveal=reveal), "Approx · USD rows converted"),
                ("Accounts", str(len(acct_v)), "Vaults in this view"),
                ("Top position", (str(sym_v.iloc[0]["Symbol"]) if not sym_v.empty else "—"), "By market value"),
            ]
        )

        c1, c2 = st.columns([1, 1])
        with c1:
            st.plotly_chart(pie_accounts_vault(acct_v, reveal=reveal), use_container_width=True)
        with c2:
            roll = rollup_symbols_by_return(df_v, usd_cad)
            stx = roll[roll["Security_Type"].map(_is_equity_type)].copy()
            st.plotly_chart(pie_holdings_colored_by_return(stx, "Equities", reveal=reveal), use_container_width=True)

        st.subheader("Holdings")
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
        st.dataframe(show, use_container_width=True, hide_index=True, height=380)

    elif view == "Returns":
        st.subheader("Returns")
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

    elif view == "Markets":
        st.subheader("Markets")
        _render_major_indices_strip()
        st.divider()
        st.markdown("**Universe** — ranked by recent % change (Yahoo).")
        universes = get_universes(refresh=False)
        uni_labels = [u.label for u in universes]
        uni_by_label = {u.label: u for u in universes}
        u1, u2, u3, u4 = st.columns([1.4, 1, 1, 1.4])
        with u1:
            labels_by_key = {u.key: u.label for u in universes}
            default_label = labels_by_key.get("both") or labels_by_key.get("sp500") or uni_labels[0]
            uni_label = st.selectbox("Universe", uni_labels, index=uni_labels.index(default_label))
            universe_key = uni_by_label[uni_label].key
        with u2:
            sort_by = st.selectbox("Sort", ["1M %", "3M %"], index=0)
        with u3:
            top_n = st.slider("Rows", 10, 60, 30)
        with u4:
            custom = st.text_input("Extra tickers (spaces/commas)", placeholder="e.g. GME, MSTR")

        if universe_key != "curated":
            st.caption("Large universes can rate-limit Yahoo. If results are empty, try Refresh, fewer rows, or Curated.")

        if st.button("Refresh prices", type="primary"):
            _cached_us_watch.clear()
            _clear_index_strip_cache()
            try:
                get_universes(refresh=True)
            except Exception:
                pass

        with st.spinner("Loading…"):
            try:
                watch = _cached_us_watch(sort_by, top_n, custom or "", universe_key)
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
        st.divider()
        pick = st.date_input("Exchange calendar date", value=pd.Timestamp.now().date())
        sched = trading_schedule_day(pick)
        ny = sched["nyse"]["is_session"]
        tsx = sched["tsx"]["is_session"]
        st.markdown(f"**NYSE** {'session' if ny else 'closed'} · **TSX** {'session' if tsx else 'closed'}")
        with st.expander("Schedule JSON"):
            st.json(sched)

    elif view == "Activity":
        st.subheader("Activity")
        if public:
            st.info("Activity editing is disabled in public view.")
        else:
            with st.form("activity_form"):
                when = st.date_input("Date", value=pd.to_datetime(today_iso_activity()).date())
                kind = st.selectbox(
                    "Type",
                    ["buy", "sell", "note", "dividend", "deposit", "withdrawal", "rebalance", "other"],
                    index=2,
                )
                c1, c2, c3 = st.columns(3)
                with c1:
                    symbol = st.text_input("Symbol (optional)", placeholder="e.g. RELIANCE, AAPL")
                with c2:
                    qty = st.number_input("Qty (optional)", value=0.0, step=1.0)
                with c3:
                    price = st.number_input("Price (optional)", value=0.0, step=0.01)
                text = st.text_area("Note", placeholder="What happened and why?", height=80)
                submitted = st.form_submit_button("Add")
            if submitted:
                append_activity(
                    ActivityItem(
                        when=when.isoformat(),
                        kind=str(kind),
                        symbol=(symbol.strip().upper() or None),
                        qty=(float(qty) if qty and qty != 0 else None),
                        price=(float(price) if price and price != 0 else None),
                        ccy="CAD",
                        text=str(text or "").strip(),
                    )
                )
                st.success("Added.")

        rows = load_activity()
        if not rows:
            st.caption("No activity yet.")
        else:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    elif view == "Journal":
        st.subheader("Journal")
        if public:
            st.info("Journal editing is disabled in public view.")
        else:
            with st.form("journal_form"):
                when = st.date_input("Date", value=pd.to_datetime(today_iso_journal()).date())
                category = st.selectbox("Category", ["Thesis", "Thesis update", "Exit note", "Macro", "Learning", "Other"])
                title = st.text_input("Title", placeholder="e.g. Why I doubled despite the miss")
                symbol = st.text_input("Symbol (optional)", placeholder="e.g. TCS")
                body = st.text_area("Entry", placeholder="Write your reasoning. What would change your mind?", height=160)
                submitted = st.form_submit_button("Publish")
            if submitted:
                if not title.strip():
                    st.error("Title is required.")
                else:
                    append_entry(
                        JournalEntry(
                            when=when.isoformat(),
                            title=title.strip(),
                            category=category,
                            symbol=(symbol.strip().upper() or None),
                            body=body.strip(),
                        )
                    )
                    st.success("Published.")

        rows = load_journal()
        if not rows:
            st.caption("No entries yet.")
        else:
            for r in rows[:30]:
                t = str(r.get("title") or "Untitled")
                when = str(r.get("when") or "")
                cat = str(r.get("category") or "")
                sym = str(r.get("symbol") or "")
                st.markdown(f"**{html.escape(t)}**")
                meta = " · ".join([x for x in [when, cat, sym] if x and x != "None"])
                if meta:
                    st.caption(meta)
                body = str(r.get("body") or "").strip()
                if body:
                    st.markdown(body)
                st.divider()

    elif view == "Signal":
        st.subheader("Signal")
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

    elif view == "Goals":
        st.subheader("Goals")
        st.caption("Persisted in `portfolio_goals.json`.")

        if public:
            st.info("Goals editing is disabled in public view.")
            st.stop()

        g1, g2, g3 = st.columns(3)
        with g1:
            tgt_pv = st.number_input(
                "Target (CAD)",
                min_value=0.0,
                value=float(goals.target_portfolio_value_cad or 0.0),
                step=1000.0,
            )
        with g2:
            _default_months = int(goals.months_to_goal) if goals.months_to_goal and goals.months_to_goal > 0 else 120
            months_goal = st.number_input("Months", min_value=1, max_value=600, value=_default_months, step=1)
        with g3:
            _ret = goals.target_annual_return_pct if goals.target_annual_return_pct is not None else 5.0
            tgt_ret = st.number_input("Model return %/yr", min_value=0.0, max_value=50.0, value=float(_ret), step=0.5)

        st.divider()
        st.subheader("Monthly deposit (model)")
        if tgt_pv > 0:
            gap = tgt_pv - total_cad
            st.caption(f"Now **{mask_cad(total_cad, reveal=reveal)}** · gap **{mask_cad(gap, reveal=reveal)}** · **{months_goal}** mo")
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

    elif view == "Account":
        st.subheader("Account & authorization")
        if public:
            st.info("Public view does not use sign-in. Add `?public=1` to share a read-only style page.")
        elif not auth_configured():
            st.success("No password gate is configured. Anyone with the app URL can use it.")
            st.markdown(
                "To require sign-in, set **`VAULTBOARD_USERNAME`** and **`VAULTBOARD_PASSWORD`** "
                "in the environment, or add an `[auth]` block to **`.streamlit/secrets.toml`** "
                "(see `.env.example`)."
            )
        else:
            st.markdown("You are **signed in**. Session lasts until you sign out or close the browser.")
            if st.button("Sign out", type="primary"):
                sign_out()
                st.rerun()

    if public:
        st.caption("Not investment advice. Prices are indicative and may be delayed.")


if __name__ == "__main__":
    main()
