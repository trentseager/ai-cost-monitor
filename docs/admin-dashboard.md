# Admin Dashboard

**Status: built**

## Rules

- Served at `/`, backed by a single static file (`static/index.html`) — no build step, no routing.
- Gated by pasting the `PROXY_ADMIN_KEY` into a field client-side; the key is sent as `X-Admin-Key` on each fetch, not persisted across page loads.
- On load, fetches `/admin/usage` (per-user table: spent today, daily limit, remaining — remaining is flagged visually once ≤ 0), `/admin/daily-totals` (feeds a spend-over-time line chart and a tokens-in/out-over-time bar chart, via Chart.js), and `/admin/rate-limits` (see below).
- A wrong admin key surfaces as "Invalid admin key" instead of a blank/broken page.
- **Rate-limit config/status section** ([[rate-limiting]]): a status table (user id, provider, limit type, limit value, window, used, remaining — remaining flagged the same way as the spend table) plus a form to set a per-user-per-endpoint request/token limit. Submitting the form `POST`s to `/admin/rate-limits` and re-fetches just that table (no full page reload). This is the dashboard's first write path — the rest of the page is read-only. No delete/clear affordance, since the admin API doesn't expose one.
