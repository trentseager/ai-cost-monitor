# Roadmap

Checklist of the site broken into chunks, so we can track what's built vs.
planned and stay on one piece at a time. Each item links to its rules/spec
doc, which is the source of truth for behavior — this file just tracks
status. Update the checkbox here whenever a doc's own `Status:` line changes.

## Core proxy

- [x] [Proxy pass-through](proxy-passthrough.md) — built
- [x] [Cost & token tracking](cost-tracking.md) — built

## Metering & limits

- [x] [Daily spend limits](daily-limits.md) — built
- [x] [Prepaid credit + reserve/settle](credit-reserve-settle.md) — built
- [x] [Per-endpoint rate limiting](rate-limiting.md) — built

## Billing / monetization (post-credit follow-ons)

Were deferred until reserve/settle was proven correct under concurrent
load — that gate cleared 2026-07-08 (found and fixed a real "database is
locked" issue under load in the process; see "Verified under concurrent
load" in [credit-reserve-settle.md](credit-reserve-settle.md)). Both items
below are now unblocked, not yet started.

- [ ] Stripe Meters API sync — not yet spec'd as its own doc
- [ ] Unified per-customer cost ledger across providers — not yet spec'd as its own doc

## Onboarding / integration friction

Reduce the setup work a founder needs to do before a new customer is
actually protected. Other candidates discussed but not yet prioritized: an
SDK wrapper package (auto-inject `X-User-Id` instead of manual header
work at every call site), an integration quickstart doc.

- [ ] [Default daily limit for new users](default-daily-limit.md) — planned

## Dashboard

- [x] [Admin dashboard](admin-dashboard.md) — built (per-user table + charts)
- [x] Rate-limit config/status section — built, see [admin-dashboard.md](admin-dashboard.md)
- [x] Credit balance / reservation view — built, see [admin-dashboard.md](admin-dashboard.md)
- [x] [Users overview (directory + 7d/30d avg spend)](user-overview.md) — built, replaced the per-user table

## Research & positioning (reference, not features — no checkbox)

- [Market validation ($500/mo gap check)](market-validation.md)
- [Positioning against LiteLLM](positioning-vs-litellm.md)
- [SaaS founder billing pain points](billing-pain-points.md)

## Working agreement

- One chunk at a time — finish and verify a checked item before starting the next, rather than spreading across several.
- No skills/agents to enforce this yet — revisit once bugs/process friction actually show up, or once the file count in `docs/` gets hard to track by hand.
