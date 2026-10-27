#!/usr/bin/env python3
"""Akari x402 MCP server — paid crypto-intel tools any MCP host can call.

Wraps the Akari x402 catalog (https://akari-x402.puzzling-marten.workers.dev) as MCP tools.
Every tool costs $0.02–$0.50 per call and is paid in USDC on Base through the x402 protocol.

Two modes:
  * dry-run (default): calls return the live HTTP 402 challenge (price, payTo, network, schema)
    so you can wire the tools up before funding a wallet.
  * paying: export AKARI_PRIVATE_KEY=0x… (a Base wallet holding USDC) and calls settle
    automatically — the x402 client signs an EIP-3009 authorization and the facilitator
    broadcasts it, so the payer needs USDC but no ETH for gas.

Builder Program: append AKARI_REF=0xYourWallet and every paid call you serve through this
server credits 40% of the sale back to you. No signup — attribution is read off the paid
resource URL. Check earnings (free): GET /x402/affiliate?address=0x…

Run (stdio transport, works with Claude Desktop, Cursor, Cline, any MCP client):
  AKARI_PRIVATE_KEY=0x… AKARI_REF=0x… python server.py
"""
from __future__ import annotations

import json
import os
import sys
import traceback

BASE = os.environ.get("AKARI_BASE", "https://akari-x402.puzzling-marten.workers.dev").rstrip("/")
REF = os.environ.get("AKARI_REF", "").strip()
PAID = bool(os.environ.get("AKARI_PRIVATE_KEY"))

TOOLS = [
    {
        "name": "akari_feed",
        "description": "Consolidated trading-signal digest (akari.feed.v1): Hyperliquid funding+momentum "
                       "signals under a strict confluence gate, Reddit sentiment bias, meme radar, armed "
                       "Polymarket in-play rows. One call replaces five. $0.02.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "akari_ta",
        "description": "TradingView technical analysis: per-timeframe buy/sell/neutral (1h, 4h, 1d, 1w), "
                       "RSI, ATR%, composite bias and trend alignment for up to 20 crypto symbols. $0.02.",
        "inputSchema": {"type": "object", "properties": {
            "symbols": {"type": "string", "description": "Comma-separated tickers, e.g. BTC,ETH,SOL (default: top 12 majors)"}},
            "additionalProperties": False},
    },
    {
        "name": "akari_hl_market",
        "description": "Hyperliquid perp market snapshot: ~180 coins with mark/oracle, premium bps, funding "
                       "(8h + annualised APR) and which side collects, OI, 24h volume/change, max leverage. $0.02.",
        "inputSchema": {"type": "object", "properties": {
            "coins": {"type": "string", "description": "Comma subset, e.g. BTC,ETH (default: all)"},
            "sort": {"type": "string", "enum": ["volume", "funding", "oi", "change", "name"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 300}},
            "additionalProperties": False},
    },
    {
        "name": "akari_trade_plan",
        "description": "Executable Hyperliquid order tickets: coin, side, IOC limit from the live book, size for "
                       "your equity/risk budget, 3x leverage cap, ATR stop, 1.5R target, full gate trace "
                       "(funding, momentum, TradingView veto, sentiment veto) and invalidations. $0.25.",
        "inputSchema": {"type": "object", "properties": {
            "coin": {"type": "string", "description": "e.g. HYPE; omit to scan and rank all perps"},
            "equity": {"type": "number", "description": "account equity in USD (default 1000)"},
            "risk_pct": {"type": "number", "description": "risk per trade in percent (default 1)"},
            "max_plans": {"type": "integer", "minimum": 1, "maximum": 10}},
            "additionalProperties": False},
    },
    {
        "name": "akari_wallet_intel",
        "description": "Base wallet balances (ETH + USDC via raw RPC) for any EVM address. Use before paying an "
                       "agent or verifying a funding source. $0.02.",
        "inputSchema": {"type": "object", "properties": {
            "address": {"type": "string", "description": "0x… EVM address (omit for the host's own watched set)"}},
            "required": ["address"], "additionalProperties": False},
    },
    {
        "name": "akari_wallet_batch",
        "description": "Batch wallet vetting: up to 50 addresses, deduped and validated, one paid call. "
                       "Built for payer vetting at scale. $0.50.",
        "inputSchema": {"type": "object", "properties": {
            "addresses": {"type": "array", "items": {"type": "string"},
                          "description": "List of 0x… addresses (max 50)"}},
            "required": ["addresses"], "additionalProperties": False},
    },
    {
        "name": "akari_desk_state",
        "description": "Live desk mirror: Hyperliquid equity + open positions, Polymarket cash, combined desk "
                       "value, armed fixtures with slugs, in-play stake ladder, sentiment inputs. $0.05.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "akari_affiliate",
        "description": "FREE. Builder-program status: pass your wallet to see referred gross and the 40% share "
                       "owed, or omit it for the program terms.",
        "inputSchema": {"type": "object", "properties": {
            "address": {"type": "string", "description": "0x… payout wallet"}},
            "additionalProperties": False},
    },
]


def _session():
    """Requests session that pays 402 challenges automatically (only when a key is set)."""
    if not PAID:
        import requests
        return requests.Session()
    from eth_account import Account
    from x402 import x402ClientSync
    from x402.mechanisms.evm.signers import EthAccountSigner
    from x402.mechanisms.evm.exact import register_exact_evm_client
    from x402.http.clients.requests import x402_requests

    account = Account.from_key(os.environ["AKARI_PRIVATE_KEY"])
    client = x402ClientSync()
    register_exact_evm_client(client, EthAccountSigner(account))
    sess = x402_requests(client)
    sess.headers.update({"User-Agent": "akari-x402-mcp/1.0"})
    return sess


_SESSION = None


def fetch(path: str, params: dict | None = None, body: dict | None = None):
    global _SESSION
    if _SESSION is None:
        _SESSION = _session()
    url = BASE + path
    if REF:
        params = dict(params or {})
        params["ref"] = REF
    if body is not None:
        r = _SESSION.post(url, json=body, params=params, timeout=90)
    else:
        r = _SESSION.get(url, params=params, timeout=90)
    try:
        payload = r.json()
    except Exception:
        payload = {"raw": r.text[:800]}
    # 402 in dry-run mode: hand the challenge back as a structured result, not an error
    if r.status_code == 402:
        hdr = r.headers.get("payment-required") or r.headers.get("x-payment-required") or ""
        return {"paid": False, "http_status": 402,
                "instruction": "This tool costs money. Set AKARI_PRIVATE_KEY to a funded Base wallet to pay "
                               "automatically, or pay the challenge with any x402 client and re-call.",
                "challenge_header_present": bool(hdr), "challenge": payload}
    if r.status_code >= 400:
        return {"paid": PAID, "http_status": r.status_code, "error": payload}
    return {"paid": PAID, "http_status": r.status_code, "data": payload}


def call_tool(name: str, args: dict):
    if name == "akari_feed":
        return fetch("/x402/feed")
    if name == "akari_ta":
        return fetch("/x402/ta", {"symbols": args.get("symbols", "")})
    if name == "akari_hl_market":
        p = {k: args[k] for k in ("coins", "sort", "limit") if args.get(k) not in (None, "")}
        return fetch("/x402/hl-market", p)
    if name == "akari_trade_plan":
        p = {k: args[k] for k in ("coin", "equity", "risk_pct", "max_plans") if args.get(k) is not None}
        return fetch("/x402/trade-plan", p)
    if name == "akari_wallet_intel":
        return fetch("/x402/wallet-intel", {"address": args.get("address", "")})
    if name == "akari_wallet_batch":
        return fetch("/x402/wallet-intel/batch", {"addresses": ",".join(args.get("addresses") or [])})
    if name == "akari_desk_state":
        return fetch("/x402/desk-state")
    if name == "akari_affiliate":
        return fetch("/x402/affiliate", {"address": args.get("address", "")})
    raise KeyError(name)


def reply(id_, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": id_}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        method = req.get("method")
        rid = req.get("id")
        try:
            if method == "initialize":
                reply(rid, {"protocolVersion": req.get("params", {}).get("protocolVersion", "2024-11-05"),
                            "capabilities": {"tools": {}},
                            "serverInfo": {"name": "akari-x402", "version": "1.0.0"}})
            elif method in ("notifications/initialized", "notifications/cancelled"):
                continue
            elif method == "ping":
                reply(rid, {})
            elif method == "tools/list":
                reply(rid, {"tools": TOOLS})
            elif method == "tools/call":
                params = req.get("params") or {}
                out = call_tool(params.get("name"), params.get("arguments") or {})
                reply(rid, {"content": [{"type": "text", "text": json.dumps(out)[:100000]}],
                            "isError": out.get("http_status", 200) >= 400})
            else:
                reply(rid, error={"code": -32601, "message": f"method not found: {method}"})
        except Exception as exc:  # keep the pipe alive; MCP hosts surface isError
            reply(rid, error={"code": -32000, "message": str(exc),
                              "data": traceback.format_exc()[-800:]})


if __name__ == "__main__":
    main()
