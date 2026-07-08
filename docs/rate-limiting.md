# Per-Endpoint Rate Limiting

**Status: planned — not yet implemented**

## Rules (spec)

- Rate limits are keyed on **user + endpoint**, not just user. A given user's `/anthropic/v1/messages` usage and `/openai/v1/chat/completions` usage are tracked and limited independently.
- The operator can configure, per user per endpoint, **either**:
  - a **request-count** limit per time window (e.g. max N requests/minute), or
  - a **token-count** limit per time window (e.g. max N tokens/minute).
- A user/endpoint pair with no rate limit configured is unmetered for rate purposes (daily cost limit, if set, still applies separately).
- Hitting the limit is a **hard block**: `429`, request never reaches the provider — same block-before-forward behavior as the existing daily cost limit, and logged the same way (0 tokens, $0 cost, `blocked=True`).
- This is layered on top of, not a replacement for, the daily cost limit — a request must pass both checks to be forwarded.

## Open questions (not yet decided)

- Window semantics: fixed window vs. sliding window.
- Whether admin config/status for rate limits gets its own endpoints (`/admin/rate-limits`) mirroring `/admin/limits`, and its own dashboard section.
