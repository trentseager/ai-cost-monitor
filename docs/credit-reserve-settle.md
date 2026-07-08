# Prepaid Credit + Reserve/Settle

**Status: planned — not yet implemented**

Spec for the first of three automation gaps identified in
[[billing-pain-points]]. This is additive to, not a replacement for, the
existing [[daily-limits]] check — a request must still pass the daily limit
(if one is set) as well as this credit check.

## Why reserve/settle instead of the existing "check-then-log" pattern

The current daily-limit check (`today_cost_for_user` vs. `daily_limit_usd`)
looks at *already-logged* spend before forwarding. That's fine for an
internal daily cutoff, but it doesn't work for prepaid money: actual output
token count — and therefore actual cost — isn't known until the response
comes back. A user could fire several requests whose *combined* actual cost
blows past their balance before any single one is logged, because nothing
was held against the balance while those requests were in flight. Reserving
the worst-case cost up front, then settling to the real cost afterward,
closes that gap — this is the credit-card pre-auth model.

## Data model

New table `credit_balances`:
```
user_id TEXT PRIMARY KEY
balance_usd REAL NOT NULL DEFAULT 0
```

New table `reservations`:
```
id INTEGER PRIMARY KEY AUTOINCREMENT
user_id TEXT NOT NULL
provider TEXT NOT NULL
reserved_usd REAL NOT NULL
status TEXT NOT NULL DEFAULT 'pending'   -- pending | settled | released
created_at TEXT NOT NULL DEFAULT (datetime('now'))
```

A user with no `credit_balances` row is not credit-metered — only the
existing daily limit (if any) applies to them. This mirrors "no limit set =
unmetered" in [[daily-limits]].

## Request lifecycle

1. **Estimate worst-case cost before forwarding.**
   - `tokens_in`: count/estimate from the request body (prompt/messages).
   - `tokens_out_ceiling`: the request's `max_tokens` if provided; otherwise
     an operator-configured fallback default (open question below).
   - `reserved_usd = tokens_in * input_rate + tokens_out_ceiling * output_rate`,
     using the same `pricing.py` table already used for actual billing.
2. **Atomically reserve against balance.** A single conditional update —
   `UPDATE credit_balances SET balance_usd = balance_usd - ? WHERE user_id = ? AND balance_usd >= ?`
   — checked by row-count, not a separate read-then-write. This is
   intentionally *not* the same race-prone pattern flagged in
   [[daily-limits]]; because real money/credit exhaustion is the failure
   mode here (not just an internal soft cutoff), the atomic update is
   required, not optional, for this mechanism.
3. **Insufficient balance → block.** No reservation is created; request
   blocked before forwarding (status code: see open questions), logged the
   same way blocked daily-limit requests are (0 tokens, $0 cost,
   `blocked=True`).
4. **Reservation succeeds → forward the request**, same pass-through
   behavior as today.
5. **On response:**
   - Extract actual usage (existing `extract_usage` path) and compute actual
     cost via `pricing.estimate_cost`.
   - Settle: release the reservation, deduct only the *actual* cost from
     `balance_usd`, and refund `reserved_usd - actual_cost` back to the
     balance. Mark the `reservations` row `settled`.
   - Log the request row as today (actual tokens/cost), same `requests`
     table — no schema change needed there.
6. **On upstream failure (5xx/network error/malformed response):** no usage
   occurred — release the full reservation back to the balance, mark the
   `reservations` row `released`, no cost logged.

## Admin API additions

- `POST /admin/credits` — `{user_id, amount_usd}`, adds to (tops up)
  `balance_usd` (upsert, additive — not a set-to like `/admin/limits`,
  since top-ups should accumulate).
- `GET /admin/credits` — per-user current balance + any `pending`
  reservations, mirroring `user_summaries_today()`'s shape in
  [[daily-limits]].

## Open questions (not yet decided)

- **Block status code**: reuse `429` for consistency with the daily-limit
  block, or use `402 Payment Required` since this is specifically an
  out-of-credit condition rather than a rate/quota cutoff. Leaning `402` —
  more semantically correct and lets a caller's SDK/error handling
  distinguish "you're out of prepaid credit" from "you're rate limited" or
  "you hit your daily cap" — but not decided.
- **Fallback output-token ceiling** when a request omits `max_tokens`:
  a fixed operator-configurable default, or a per-model default from the
  provider's own documented max.
- **Stale/abandoned reservations**: what reaps a `pending` reservation that
  never settles because the proxy crashed mid-request (e.g. a sweep that
  releases anything `pending` older than N minutes). Needed for
  correctness, not needed to prove the mechanism out.
- **Input token counting accuracy**: exact tokenizer per provider/model vs.
  a cheaper character-based estimate. Only affects how conservative the
  reservation is, not the correctness of the settle step (settle always
  uses actual usage).

## Future work (after this spec is built and functional — do not start early)

1. **Stripe Meters API sync** — push settled per-user actual cost/usage
   events to Stripe so a founder's own end-customer billing reflects real
   AI cost automatically, instead of hand-rolled reconciliation. Addresses
   pain #1 in [[billing-pain-points]].
2. **Unified per-customer cost ledger across providers** — a reporting
   rollup once more than 2 providers exist, aggregating the existing
   per-provider `requests` rows into one blended per-customer view.
   Addresses pain #4 in [[billing-pain-points]].

Both are deliberately out of scope until reserve/settle itself is built,
tested, and proven correct under concurrent load — building billing-sync
or reporting on top of a not-yet-trustworthy balance mechanism would just
compound bugs.
