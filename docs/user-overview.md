# Users Overview (Dashboard)

**Status: built** (`db.py`, `main.py`, `static/index.html`)

Spec for a directory/reporting view on top of the existing
[[admin-dashboard]], aimed at both team and solo-indie usage: today the
dashboard's user table only lists users who have a daily `$` limit
configured (`FROM limits` in `user_summaries_today()`), so anyone without
one set is invisible. This section gives the admin one place to see every
known user regardless of which metering features (if any) apply to them,
plus enough of a usage trend to judge whether their own configured caps
([[daily-limits]], [[rate-limiting]], [[credit-reserve-settle]]) are set
sensibly relative to actual behavior.

## Rules (spec)

- A "known" user is the union of: every distinct `user_id` in `requests`,
  plus every `user_id` present in `limits`, `credit_balances`, or
  `rate_limit_configs` — so a user configured ahead of their first request
  still shows up.
- New endpoint `GET /admin/users`, admin-key gated, returns one row per
  known user with:
  - `user_id`
  - `label` — optional display name, see below
  - `spent_today` — same figure as today's `today_cost_for_user`
  - `daily_limit_usd` — `null` if unset (not every user has one)
  - `avg_daily_cost_7d` — total cost over the last 7 calendar days
    (today + previous 6) ÷ 7
  - `avg_daily_cost_30d` — same, ÷ 30, over the last 30 calendar days
  - `requests_today`, `blocked_today` — counts from `requests` for the
    current calendar day
- Calendar-day bucketing (`date(ts)`), consistent with the existing
  daily-limit/daily-totals convention — not an exact rolling N×24h window.
- Averages divide by the full window size (7 or 30) regardless of how many
  of those days actually had traffic — an idle day counts as $0 toward the
  average. The point is comparing against a daily budget, so idle days
  should pull the average down, not be excluded.
- Today's bucket is always partial as of whenever the admin loads the page
  — included in the average as-is, not excluded or specially computed. The
  dashboard discloses this (see below) rather than adjusting the math.
- **Display label**: purely cosmetic, free-text, no effect on any
  billing/limiting logic. New table `user_labels(user_id PRIMARY KEY,
  label TEXT)`, independent of `limits`/`credit_balances`/
  `rate_limit_configs` — a user can have a label with none of those
  configured, or vice versa. Set via `POST /admin/users/label`
  (`{user_id, label}`), upsert semantics like every other admin-set
  endpoint. No delete endpoint — set the label to an empty string to clear
  it.
- Read-only reporting for everything except the label — no new
  limiting/blocking behavior, no changes to `_proxy_request()`.

## Dashboard

- Replaces the existing `#userTable` (currently User ID | Spent today |
  Daily limit | Remaining, populated only from `limits`) with the fuller
  Users Overview table: User ID | Label | Spent today | Daily limit |
  Remaining | Avg (7d) | Avg (30d) | Requests today | Blocked today. Rows
  with no daily limit configured show "—" for limit/remaining instead of
  `$0`, so "unmetered" isn't visually confused with "$0 remaining."
- Caption below the table: "Averages include today's partial day (as of
  load time) — today alone will typically look lower than a full day."
- `title` tooltips on the "Avg (7d)"/"Avg (30d)" column headers repeating
  that note for anyone hovering just that column.
- Small inline edit affordance per row to set/update a user's label —
  `POST` then re-fetch just this table, same write-then-refresh pattern
  the rate-limit section already uses.
- `blocked_today` gets the existing `.over`-style visual flag once > 0, so
  an admin scanning the table can immediately spot who's actively being
  blocked.

## Assumptions made in this doc (flag if wrong)

- This table *replaces* the existing daily-limit table rather than sitting
  alongside it — keeping both would duplicate spent-today/daily-limit/
  remaining columns across two tables for no reason.
- Cost (not token count) is what's averaged/shown for 7d/30d — tokens
  in/out are already covered by the existing tokens-over-time chart, and
  cost is the figure the daily and rate limits are actually denominated in
  (rate limits' `tokens` mode is per-window, not comparable to a daily
  average the same way).
- Real provider-side rate-limit headroom (parsing Anthropic's/OpenAI's own
  rate-limit response headers) is explicitly out of scope here — a
  separate, larger feature if wanted later. This section only reports
  usage against limits the admin has configured in this tool.

## Decisions made during implementation

- `user_overview()` is one query built as a CTE: a `known_users` union of
  distinct `user_id` across `requests`/`limits`/`credit_balances`/
  `rate_limit_configs`, left-joined against per-user aggregates (today's
  stats, 7d window, 30d window) and against `limits`/`user_labels` — so a
  user with zero requests (config-only) still gets a full row of
  zeros/nulls rather than being dropped by an inner join.
- `GET /admin/usage` and `user_summaries_today()` were **not removed** —
  nothing calls for deleting existing API surface, and `/admin/credits`
  (also currently unused by the dashboard) is kept around the same way.
  Only the dashboard's fetch target changed, from `/admin/usage` to
  `/admin/users`.
- The label `<input>`'s value is set via the DOM `.value` property
  (`document.createElement` + assignment), not interpolated into an HTML
  attribute string — an admin-entered label containing a `"` would
  otherwise break out of the attribute and, since labels get re-rendered
  on every table refresh, create a stored-injection path. Every other
  field in this table is still plain template-string interpolation,
  consistent with the rest of the file — only the label needed this
  because it's the one genuinely free-text, admin-controlled value.

## Verified behavior (manual test pass, mocked upstream)

- A user with no `limits` row (only ever made a proxied request) appears
  in `GET /admin/users` with `daily_limit_usd: null`.
- 7d/30d averages hand-verified against backdated `requests` rows (a $1
  today + $2 three days ago + $5 ten days ago row set): 7d avg correctly
  excludes the 10-day-old row, 30d avg correctly includes all three,
  both divide by the full window size.
- Setting a label, then setting it again with a new value, updates the
  same row in place (`user_labels` upsert) rather than duplicating.
- A user blocked by the daily limit shows `blocked_today` incremented with
  `spent_today` unaffected (blocked requests log `$0`/`blocked=True`, same
  as documented in [[daily-limits]]).
- Bad admin key → `401` on both `GET /admin/users` and
  `POST /admin/users/label`.
