"""Plaid integration for holdings + transactions.

Implements:
- link token creation
- public token exchange -> access token
- transactions sync cursor
- investments holdings fetch

This file is safe to import even without Plaid env vars set; functions will raise with a
clear error in that case.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class PlaidConfig:
    client_id: str
    secret: str
    env: str  # sandbox|development|production


def _get_cfg() -> PlaidConfig:
    cid = (os.getenv("PLAID_CLIENT_ID") or "").strip()
    sec = (os.getenv("PLAID_SECRET") or "").strip()
    env = (os.getenv("PLAID_ENV") or "sandbox").strip().lower()
    if not cid or not sec:
        raise RuntimeError("Missing PLAID_CLIENT_ID / PLAID_SECRET environment variables.")
    if env not in ("sandbox", "development", "production"):
        raise RuntimeError("PLAID_ENV must be sandbox|development|production.")
    return PlaidConfig(client_id=cid, secret=sec, env=env)


def _client():
    # Import lazily so the app can start without Plaid installed/configured.
    from plaid import ApiClient, Configuration, Environment
    from plaid.api import plaid_api

    cfg = _get_cfg()
    host = {
        "sandbox": Environment.Sandbox,
        "development": Environment.Development,
        "production": Environment.Production,
    }[cfg.env]
    configuration = Configuration(
        host=host,
        api_key={
            "clientId": cfg.client_id,
            "secret": cfg.secret,
        },
    )
    api_client = ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)


def create_link_token(*, user_id: str, redirect_uri: str | None = None) -> str:
    """
    Create a Link token for the frontend Link flow.
    """
    client = _client()
    from plaid.model.country_code import CountryCode
    from plaid.model.link_token_create_request import LinkTokenCreateRequest
    from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
    from plaid.model.products import Products

    products = [Products("transactions"), Products("investments")]
    req = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=str(user_id)),
        client_name="Holdings Journal",
        products=products,
        country_codes=[CountryCode("US"), CountryCode("CA")],
        language="en",
        redirect_uri=redirect_uri,
    )
    resp = client.link_token_create(req)
    return str(resp["link_token"])


def exchange_public_token(public_token: str) -> dict[str, str]:
    """
    Exchange a Link public_token for a long-lived access token.
    Returns {access_token, item_id}.
    """
    client = _client()
    from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest

    resp = client.item_public_token_exchange(ItemPublicTokenExchangeRequest(public_token=public_token))
    return {"access_token": str(resp["access_token"]), "item_id": str(resp["item_id"])}


def investments_holdings(access_token: str) -> pd.DataFrame:
    client = _client()
    from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest

    resp = client.investments_holdings_get(InvestmentsHoldingsGetRequest(access_token=access_token))
    holdings = resp.get("holdings", []) or []
    securities = {s.get("security_id"): s for s in (resp.get("securities", []) or [])}

    rows: list[dict[str, Any]] = []
    for h in holdings:
        sid = h.get("security_id")
        sec = securities.get(sid, {}) if sid else {}
        rows.append(
            {
                "account_id": h.get("account_id"),
                "security_id": sid,
                "symbol": sec.get("ticker_symbol") or sec.get("iso_currency_code") or "",
                "name": sec.get("name") or "",
                "type": sec.get("type") or "",
                "quantity": h.get("quantity"),
                "institution_price": h.get("institution_price"),
                "institution_price_as_of": h.get("institution_price_as_of"),
                "institution_value": h.get("institution_value"),
                "iso_currency_code": h.get("iso_currency_code") or sec.get("iso_currency_code"),
            }
        )
    return pd.DataFrame(rows)


def transactions_sync(access_token: str, cursor: str | None) -> tuple[pd.DataFrame, str]:
    """
    Incremental sync. Returns (transactions_df, next_cursor).
    """
    client = _client()
    from plaid.model.transactions_sync_request import TransactionsSyncRequest

    added: list[dict[str, Any]] = []
    next_cursor = cursor
    has_more = True
    while has_more:
        resp = client.transactions_sync(
            TransactionsSyncRequest(access_token=access_token, cursor=next_cursor)
        )
        added.extend(resp.get("added", []) or [])
        has_more = bool(resp.get("has_more"))
        next_cursor = str(resp.get("next_cursor") or next_cursor or "")
        if not next_cursor:
            break
    return pd.DataFrame(added), next_cursor or (cursor or "")

