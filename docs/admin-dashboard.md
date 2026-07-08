# Admin Dashboard

**Status: built**

## Rules

- Served at `/`, backed by a single static file (`static/index.html`) — no build step, no routing.
- Gated by pasting the `PROXY_ADMIN_KEY` into a field client-side; the key is sent as `X-Admin-Key` on each fetch, not persisted across page loads.
- On load, fetches `/admin/users` (users overview table, see below), `/admin/daily-totals` (feeds a spend-over-time line chart and a tokens-in/out-over-time bar chart, via Chart.js), and `/admin/rate-limits` (see below).
- A wrong admin key surfaces as "Invalid admin key" instead of a blank/broken page.
- **Users overview** ([[user-overview]]): directory of every known user (not just those with a daily limit configured) — user id, editable label, spent today, daily limit/remaining (shown as "—" when unset), avg daily cost over 7d/30d (calendar-day bucketed, includes today's partial day, disclosed via a caption + header tooltips), requests today, blocked today (flagged once > 0). The label field is the one editable cell — saving it `POST`s to `/admin/users/label` and re-fetches just this table.
- **Rate-limit config/status section** ([[rate-limiting]]): a status table (user id, provider, limit type, limit value, window, used, remaining — remaining flagged the same way as the users overview table) plus a form to set a per-user-per-endpoint request/token limit. Submitting the form `POST`s to `/admin/rate-limits` and re-fetches just that table (no full page reload). No delete/clear affordance, since the admin API doesn't expose one.
- `GET /admin/usage` still exists as an API endpoint but is no longer called by the dashboard — superseded by `/admin/users`.
