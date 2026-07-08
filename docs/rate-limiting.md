# Per-Endpoint Rate Limiting

**Status: built** (`db.py`, `main.py`)

## Rules (spec)

- Rate limits are keyed on **user + endpoint**, not just user. A given user's `/anthropic/v1/messages` usage and `/openai/v1/chat/completions` usage are tracked and limited independently.
- The operator can configure, per user per endpoint, **either**:
  - a **request-count** limit per time window (e.g. max N requests/minute), or
  - a **token-count** limit per time window (e.g. max N tokens/minute).
- A user/endpoint pair with no rate limit configured is unmetered for rate purposes (daily cost limit, if set, still applies separately).
- Hitting the limit is a **hard block**: `429`, request never reaches the provider — same block-before-forward behavior as the existing daily cost limit, and logged the same way (0 tokens, $0 cost, `blocked=True`).
- This is layered on top of, not a replacement for, the daily cost limit — a request must pass both checks to be forwarded.

## Decisions made during implementation

- **Fixed window**, not sliding. A bucket per `(user_id, provider, window_start)`, `window_start` floored to the nearest `window_seconds` boundary — same shape as the existing daily limit's `date('now')` bucketing, just computed in Python since SQLite's `datetime()` can't floor to an arbitrary N-second bucket. Accepts a boundary burst (two windows' worth of traffic possible right at an edge) in exchange for real simplicity; consistent with this codebase's other MVP-pragmatic tradeoffs (e.g. the daily-limit race, credit's chars/4 token estimate).
- **`/admin/rate-limits`** — yes, its own endpoints, mirroring `/admin/limits` and `/admin/credits` exactly: `POST` upserts a `(user_id, provider)` config, `GET` returns every config joined with its current window's usage.
- **No persisted reservation ledger** (unlike credit's `reservations` table). A hold is a plain dict threaded through `_proxy_request()` in memory and settled/released before the function returns. Safe because a fixed window self-heals every rollover — a crash mid-request just leaves that one window's `used_value` bounded-off, not indefinitely wrong the way an un-swept credit reservation would be.
- **Token-mode settles like credit does**: reserve `estimate_input_tokens(body) + (max_tokens or fallback)`, then refund `reserved − actual` once real usage comes back, so `used_value` reflects real consumption, not the worst-case ceiling.
- **Request-mode never settles** — the reserved amount (always 1) equals the actual amount, so there's nothing to refund once a response comes back. It's only released if a *later* check (credit) blocks the request before it reaches the provider — a request that never happened shouldn't count against the endpoint's rate budget.
- **Ordering**: daily limit → rate limit → credit → forward. Coarsest/cheapest check first, so a later failure never leaves an earlier one's reservation dangling (verified: a credit failure correctly releases an already-consumed rate-limit hold).

## Verified behavior (manual test pass, mocked upstream)

- Requests-mode: 2-per-window limit allows exactly 2, blocks the 3rd with `429`.
- Tokens-mode: a 200-token budget settles to actual usage after each request (not the reserved ceiling), and correctly blocks once real consumption leaves no room for the next reservation.
- Layering: a rate-limit block leaves the user's credit balance completely untouched (confirmed identical before/after the blocked request).
- A credit-check failure after a successful rate-limit reservation correctly releases that hold back to `used_value = 0`.
- A user/endpoint pair with no rate-limit config configured passes through unaffected.
