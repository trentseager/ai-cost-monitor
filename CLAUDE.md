# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A drop-in reverse proxy for Anthropic and OpenAI API calls. A dev points their SDK's `base_url` at this proxy instead of the provider directly (their own API key still flows through unchanged). The proxy reads the `usage` object out of each response, prices it, attributes it to a per-request `X-User-Id`, and blocks that user's future requests once they hit a configured daily spend limit, exhaust a prepaid credit balance, or exceed a per-endpoint rate limit.

The proxy never holds a provider API key itself — it only forwards the caller's own key through — and it never stores or inspects prompt/response content, only the `usage` object.

## Setup & running

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Set `PROXY_ADMIN_KEY` in `.env` to a long random string — this authenticates the operator to `/admin/*` endpoints. It is unrelated to any Anthropic/OpenAI credentials (there are none stored here on purpose).

Run the server:
```
uvicorn main:app --reload
```

Dashboard at http://localhost:8000 (paste `PROXY_ADMIN_KEY` in to load it).

There is no test suite, linter, or build step configured in this repo currently.

## Architecture

Each file is a distinct layer:

- `main.py` — FastAPI app. Two proxy routes (`/anthropic/v1/messages`, `/openai/v1/chat/completions`) that both funnel through `_proxy_request()`, plus `/admin/*` endpoints.
- `providers.py` — per-provider manifest (`PROVIDERS` dict): upstream URL to forward to, and an `extract_usage(body) -> (model, tokens_in, tokens_out) | None` function that pulls usage out of that provider's response shape. Route paths intentionally mirror each provider's real API path exactly, so a dev changes only their SDK's `base_url` — no other client code changes.
- `pricing.py` — manually maintained per-token pricing table (`PRICING`, USD per 1M tokens) and `estimate_cost()`. Unknown models return `known=False` rather than a guessed cost, so `main.py` can log `pricing_known=False` / `$0` instead of silently mis-billing.
- `db.py` — raw SQLite (`usage.db`, no ORM) via a `get_conn()` context manager that commits on success. Six tables: `requests` (per-call log), `limits` (per-user daily USD cap), `credit_balances` (per-user prepaid balance) + `reservations` (in-flight holds against a balance), and `rate_limit_configs` (per-`(user_id, provider)` limit config) + `rate_limit_windows` (per-`(user_id, provider, window_start)` fixed-window usage counter). Query helpers (`today_cost_for_user`, `user_summaries_today`, `daily_totals`, `credit_summaries`, `rate_limit_summaries`) return plain dicts/rows for the admin API to serialize directly.
- `static/index.html` — single-page admin dashboard gated by pasting the admin key client-side; talks to `/admin/*`.

### Request flow (`_proxy_request` in `main.py`)

1. Require `X-User-Id` header (400 if missing).
2. Parse body as JSON; reject `"stream": true` (400 — streaming isn't supported, see below).
3. If the user has a daily limit set (`db.get_limit`), check today's spend (`db.today_cost_for_user`); if at/over limit, log a zero-cost `blocked=True` row and return 429 **before** contacting the provider.
4. If a rate-limit config exists for `(user_id, provider)` (`db.get_rate_limit_config`), reserve against the current fixed window (`db.reserve_rate_limit`) — `1` for requests-mode, or an estimated worst-case token count for tokens-mode (same estimate credit uses). Exceeding the limit → 429, logged the same way, **before** contacting the provider.
5. If the user is credit-metered (`db.has_credit_metering`), size a worst-case reservation from the request (`cfg["estimate_input_tokens"]` × input rate + `max_tokens`-or-fallback × output rate) and atomically reserve it (`db.reserve_credit`). Unknown pricing or insufficient balance → 402, logged the same way as a daily-limit block, **before** contacting the provider — and if this fails, any rate-limit hold from step 4 is released (`db.release_rate_limit`), since the request never actually reached the provider. Steps 3–5 layer on top of each other; none replaces another. See `docs/credit-reserve-settle.md` and `docs/rate-limiting.md`.
6. Strip hop-by-hop headers and the inbound `X-User-Id` (`STRIPPED_HEADERS`), forward everything else — including the dev's own `Authorization`/`x-api-key` — verbatim to `cfg["upstream_url"]`.
7. On response, attempt to parse JSON and run `cfg["extract_usage"]`; if usage is present, price it via `pricing.estimate_cost` and log the row via `db.log_request`. If a credit reservation was made, settle it to the actual cost (`db.settle_reservation`). If a tokens-mode rate-limit hold was made, settle it to actual token usage the same way. If no usage came back (upstream error/malformed response), release any credit reservation and any tokens-mode rate-limit hold in full — a requests-mode hold stays consumed either way, since a response was received.
8. Return the upstream response body/status/content-type untouched to the caller, regardless of whether usage parsing succeeded.

Adding a new provider means adding one entry to `PROVIDERS` (upstream URL + usage extractor) in `providers.py`, a pricing sub-table in `pricing.py`, and a new route in `main.py` that calls `_proxy_request("newprovider", request)`.

## Known limitations (intentional, not bugs to silently "fix")

- **No streaming support.** `"stream": true` requests are rejected with 400 — usage only arrives in the final SSE chunk of a stream, and buffering it correctly while still passing chunks through live is real complexity, deferred on purpose.
- **Pricing table is a manual snapshot.** Treat `PRICING` in `pricing.py` as stale-by-default; don't assume it reflects current provider pricing.
- **No TLS handling.** This proxy relays real provider API keys in headers; running it over plain HTTP outside local development is a caller responsibility, not something to add here without being asked.
- **The daily-limit check has a known race** under concurrent requests from the same user (check-then-log isn't atomic). This is accepted for the MVP — don't "fix" it with a lock unless asked, since it changes concurrency behavior. The credit reserve/settle mechanism does **not** share this race — `db.reserve_credit` uses a single conditional `UPDATE ... WHERE balance_usd >= ?` checked by row-count, which is atomic under SQLite's single-writer model. `db.reserve_rate_limit` uses the same atomic-update pattern.
- **Rate limiting uses fixed windows, not sliding.** A boundary burst (up to ~2x the limit right at a window edge) is possible by design — accepted for simplicity, matching the daily limit's own `date('now')` day-bucketing. Don't "fix" this with sliding-window logic unless asked.
