# akari-x402-mcp

An [MCP](https://modelcontextprotocol.io) server that exposes a live **x402-paid crypto-intel API**
as tools any MCP host (Claude Desktop, Cursor, Cline, custom agents) can call. Every tool is
metered in USDC on Base — no API keys, no subscriptions, no signup.

**Earn from it:** this repo is also the starter kit for the **Akari Builder Program** — 40 % of
every sale your copy refers goes back to your wallet, read straight off the paid resource URL.

**No install at all:** the same catalogue is served as a **remote MCP endpoint** —
`POST https://akari-x402.puzzling-marten.workers.dev/mcp` (JSON-RPC 2.0). `tools/list` returns every
paid route with its price in `_meta.x402`; `akari_board` is free. Point any MCP client at that URL.

**The flagship tool is the decision, not the data:** `akari_alpha_brief` ($1.00) returns the market
regime, the ranked LONG/SHORT edges that cleared the full gate set (funding-carry × momentum
confluence, $5M/$2M liquidity floors, TA + sentiment vetoes) with size/stop/target hints and
invalidations, the avoid list, stand-down reasons and provenance. Free redacted preview:
<https://akari-x402.puzzling-marten.workers.dev/board>.

```bash
# 1. install
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# 2a. dry run — tools return the live HTTP 402 challenge (price, payTo, network, schema)
python server.py

# 2b. paying — point it at a Base wallet holding USDC (no ETH needed: the facilitator pays gas)
AKARI_PRIVATE_KEY=0x… AKARI_REF=0xYourPayoutWallet python server.py
```

## Tools

| tool | price | what you get |
|---|---|---|
| `akari_feed` | $0.02 | one signal digest: HL funding+momentum (confluence gate), Reddit bias, meme radar, armed Polymarket rows |
| `akari_ta` | $0.02 | TradingView TA per timeframe (1h/4h/1d/1w), RSI, ATR %, composite bias |
| `akari_hl_market` | $0.02 | ~180 Hyperliquid perps: funding APR, side-to-collect, OI, volume, change |
| `akari_trade_plan` | $0.25 | executable order ticket: live-book limit, size, 3x cap, ATR stop, 1.5R target, gate trace |
| `akari_wallet_intel` | $0.02 | Base ETH+USDC balances for any address (payer vetting) |
| `akari_wallet_batch` | $0.50 | 50 addresses in one paid call (50 % off per address) |
| `akari_desk_state` | $0.05 | live desk mirror: equity, positions, armed fixtures, stake ladder |
| `akari_affiliate` | free | your referred gross and 40 % share owed |

## MCP host config (Claude Desktop / Cursor / Cline)

```json
{
  "mcpServers": {
    "akari-x402": {
      "command": "python",
      "args": ["/absolute/path/to/server.py"],
      "env": { "AKARI_PRIVATE_KEY": "0x…", "AKARI_REF": "0xYourPayoutWallet" }
    }
  }
}
```

Omit `AKARI_PRIVATE_KEY` to explore the tools without spending anything — each call returns the
402 challenge instead of data.

## How payment works

1. The tool calls the endpoint with no credentials and receives `402 Payment Required` plus a
   base64 `payment-required` header describing price, asset, payTo and network (`eip155:8453`).
2. The bundled `x402` client signs an **EIP-3009 transferWithAuthorization** for exactly that amount
   — the payer needs USDC, not ETH.
3. The facilitator (Coinbase CDP) verifies and broadcasts, then the tool's request is retried with
   `X-PAYMENT` and the JSON comes back. Settlement is on-chain and auditable by anyone.

### If you poll on a schedule, buy the pass instead

`GET /x402/pass` — **$5.00 buys 30 days of every paid route**, up to 5,000 calls (fair use). You get a
bearer token back; send it as `Authorization: Bearer akari_pass_…` on the same URLs and the payment
step disappears:

```bash
# buy once with any x402 client (pays $5 USDC on Base, returns the token in the JSON body)
tok=$(x402-pay https://akari-x402.puzzling-marten.workers.dev/x402/pass | jq -r .pass_token)
curl -H "Authorization: Bearer $tok" https://akari-x402.puzzling-marten.workers.dev/x402/feed
curl -H "Authorization: Bearer $tok" https://akari-x402.puzzling-marten.workers.dev/x402/pass/status
```

At $0.02 per call, polling one route hourly costs $14.40/month — the pass covers all of them for $5.
`GET /x402/pass/status` is free and tells you calls used and the expiry without spending a call.

## Builder Program (how to actually earn)

1. Copy this server (or any client) into your product.
2. Set `AKARI_REF=0xYourPayoutWallet` — every paid call you serve carries `?ref=` on the resource URL.
3. Check earnings any time, no account needed:
   `GET https://akari-x402.puzzling-marten.workers.dev/x402/affiliate?address=0xYourPayoutWallet`
   Public board (unseeded, honest): `/x402/affiliate/leaderboard`.
4. Payouts: 40 % of referred gross, USDC on Base, monthly once accrued ≥ $1.00.
   Full terms, live prices and the exclusion rules: https://edvyno.github.io/akari-proof/builder.html

## Notes

- Free endpoints you can inspect without paying: `/market.json`, `/llms.txt`, `/x402/feed/preview`,
  `/.well-known/x402`, `/openapi.json`.
- The desk publishes its real numbers, including losses — the data is live, not backfilled.
- This server is a thin client: it holds no keys beyond the payer wallet you choose to give it.

## License

MIT — see [LICENSE](LICENSE). Fork it, keep the builder ref, keep the 40 %.
