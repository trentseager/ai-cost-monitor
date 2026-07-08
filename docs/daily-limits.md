# Daily Spend Limits

**Status: built**

## Rules

- The operator sets a per-user daily USD cap via `POST /admin/limits` (`{user_id, daily_limit_usd}`), admin-key gated.
- A user with no limit set is unmetered — never blocked, still logged.
- Before forwarding any request, the proxy sums that user's non-blocked cost for the current calendar day (`date('now')` in the DB). If spend is at or over the limit, the request is blocked with `429` and never reaches the provider.
- A blocked request is still logged as a row (0 tokens, $0 cost, `blocked=True`) so the block itself is visible in the audit trail.
- The check-then-log sequence is not atomic — concurrent requests from the same user can both pass the check before either is logged. Known race, accepted for MVP; not to be "fixed" with a lock without being asked, since it changes concurrency behavior.
- `GET /admin/usage` returns today's per-user summary (spent vs. limit) for every user who has a limit configured.
