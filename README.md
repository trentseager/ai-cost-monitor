# AI API Cost/Token Monitor

A drop-in reverse proxy for Anthropic and OpenAI API calls. A dev points their
existing SDK at this proxy instead of the provider directly (their own API
key still flows through, unchanged); the proxy reads token usage straight out
of each response, prices it, attributes it to a per-request user ID, and
blocks a user's requests once they hit a daily spend limit you (the operator)
configure.

No AI-generated content is used anywhere in this tool — it's a pure relay
that reads the `usage` object every provider already returns.

## How it works

1. Dev's app sets its SDK `base_url` to this proxy instead of the provider's API.
2. Every request must carry an `X-User-Id` header identifying the end user.
3. Before forwarding, the proxy checks that user's spend so far today against
   a daily limit (if one is set for them). Over limit → `429`, request never
   reaches the provider.
4. Otherwise the request (including the dev's own `Authorization`/`x-api-key`
   header) is forwarded upstream as-is.
5. The response comes back through unchanged to the dev's app; the proxy
   separately parses the `usage` field, prices it (see `pricing.py`), and
   logs it against that user.

The proxy **never holds a provider API key** — it only ever forwards the
caller's own key through. It never stores or inspects prompt/response
content.

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Generate a long random string for `PROXY_ADMIN_KEY` in `.env` — this
authenticates you (the operator) to `/admin/*` endpoints. It's unrelated to
Anthropic/OpenAI credentials.

## Run

```
uvicorn main:app --reload
```

Dashboard: http://localhost:8000 (paste your `PROXY_ADMIN_KEY` in to load it)

## Wiring a dev's app to the proxy

**Anthropic SDK:**
```python
client = anthropic.Anthropic(
    api_key="THEIR_OWN_ANTHROPIC_KEY",
    base_url="http://localhost:8000/anthropic",
)
# then call client.messages.create(...) as usual, but pass extra_headers={"X-User-Id": "user-123"}
```

**OpenAI SDK:**
```python
client = openai.OpenAI(
    api_key="THEIR_OWN_OPENAI_KEY",
    base_url="http://localhost:8000/openai/v1",
)
# client.chat.completions.create(..., extra_headers={"X-User-Id": "user-123"})
```

Raw curl example (Anthropic):
```
curl http://localhost:8000/anthropic/v1/messages \
  -H "x-api-key: $ANTHROPIC_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -H "X-User-Id: user-123" \
  -d '{"model":"claude-3-5-sonnet-20241022","max_tokens":100,"messages":[{"role":"user","content":"hi"}]}'
```

## Admin API

Set a user's daily limit:
```
curl -X POST http://localhost:8000/admin/limits \
  -H "X-Admin-Key: $PROXY_ADMIN_KEY" -H "content-type: application/json" \
  -d '{"user_id":"user-123","daily_limit_usd":5.00}'
```

View today's per-user spend: `GET /admin/usage` (same header).
View daily aggregate totals (for charts): `GET /admin/daily-totals`.

A user with no limit set is unmetered (never blocked, still logged).

## Known limitations (MVP)

- **No streaming support.** Requests with `"stream": true` are rejected with
  `400` — usage only arrives in the final SSE chunk, and buffering it
  correctly while still passing chunks through live is real complexity,
  deferred on purpose.
- **Pricing table (`pricing.py`) is a manually maintained snapshot.** Verify
  against current Anthropic/OpenAI pricing pages before relying on it —
  unknown models are logged with `pricing_known=False` and `$0` cost rather
  than a guessed number.
- **TLS is your responsibility in production.** Real provider API keys
  transit through this proxy in request headers — never run it over plain
  HTTP outside local development.
- **Race condition on the block check** under concurrent requests from the
  same user isn't locked — acceptable for an MVP, worth a proper atomic
  check if you're metering high-concurrency traffic.

## Structure

- `main.py` — FastAPI app: the two proxy routes + `/admin/*` endpoints
- `providers.py` — manifest: upstream URL + usage-extraction per provider
- `pricing.py` — per-token pricing table + cost calculation
- `db.py` — SQLite: `requests` log + per-user `limits`
- `static/index.html` — admin-key-gated dashboard
