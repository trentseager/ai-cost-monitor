# Default Daily Limit for New Users

**Status: planned — not yet implemented**

Onboarding-friction fix, not a new metering mechanism: today a brand-new
`user_id` is completely unmetered until the operator manually adds a
`limits` row via `/admin/limits` (see [[daily-limits]]). A founder
onboarding customers has to remember to do this for every single new
customer before they're covered by any spend protection — easy to forget,
and nothing in the system currently prompts for it. This closes that gap
with an operator-configured global default, auto-applied the first time an
unconfigured user's request comes through.

## Rules (spec)

- New env var `DEFAULT_DAILY_LIMIT_USD` (optional; unset = today's
  existing behavior, unchanged). Mirrors the existing
  `CREDIT_FALLBACK_MAX_TOKENS` env var pattern (`providers.py`,
  [[credit-reserve-settle]]) — global, operator-tunable via `.env`, not a
  runtime/dashboard-editable setting for this first pass. Parsed once at
  import time in `main.py` (where it's consumed), `None` if unset — unlike
  the token fallback, this must not silently default to some hardcoded
  number, since a default of e.g. `$0` would mean "block every new user
  immediately," which is the opposite of the intent.
- On a request from a `user_id` with no existing `limits` row: if
  `DEFAULT_DAILY_LIMIT_USD` is set, materialize a real row for that user
  via the existing `set_limit(user_id, DEFAULT_DAILY_LIMIT_USD)` before
  the existing daily-limit check runs, then proceed with that check
  unchanged (now sees a real limit instead of `None`). If the env var is
  unset, behavior is exactly as today.
- **Materialized, not virtual.** Once auto-provisioned, that user has a
  real `limits` row indistinguishable from a manually-configured one —
  visible in the Users Overview dashboard table immediately, editable or
  removable by the operator via `/admin/limits` at any time afterward. No
  "is this a default or an explicit override" flag anywhere — deliberately
  avoids adding that extra state.
- **Forward-only, no backfill.** Applies the first time an *already-known*
  unmetered user's next request comes in after this ships. Existing users
  with no `limits` row are not retroactively assigned a default via a
  migration — they get one naturally on their next request, same path a
  brand-new user goes through.
- **No new race.** Two concurrent "first" requests from the same brand-new
  `user_id` could both see `get_limit(user_id) is None` and both call
  `set_limit(...)` — harmless, since it's an idempotent upsert to the same
  constant value, not a balance decrement. Unlike credit's reserve
  mechanism, there's no contention to protect against here, so no atomic
  conditional update is needed for the auto-provisioning write itself.
- Scope: **daily limit only** for this pass. Credit metering and rate
  limits stay opt-in-only — no default credit balance (a default grant has
  real financial implications the operator should set deliberately per
  customer) and no default rate limit (a reasonable follow-on later, same
  pattern, deliberately not bundled into this first pass).
- Does not change the daily-limit check's known race (see `CLAUDE.md`) —
  the auto-provisioning write and the spend check remain two separate
  operations, same as for any manually-configured user today.
