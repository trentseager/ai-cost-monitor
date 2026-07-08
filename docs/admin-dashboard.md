# Admin Dashboard

**Status: built (rate-limiting section planned)**

## Rules

- Served at `/`, backed by a single static file (`static/index.html`) — no build step, no routing.
- Gated by pasting the `PROXY_ADMIN_KEY` into a field client-side; the key is sent as `X-Admin-Key` on each fetch, not persisted across page loads.
- On load, fetches `/admin/usage` (per-user table: spent today, daily limit, remaining — remaining is flagged visually once ≤ 0) and `/admin/daily-totals` (feeds a spend-over-time line chart and a tokens-in/out-over-time bar chart, via Chart.js).
- A wrong admin key surfaces as "Invalid admin key" instead of a blank/broken page.
- Planned: a rate-limit config/status section once [[rate-limiting]] ships (view + set per-user-per-endpoint request/token limits, see current window usage).
