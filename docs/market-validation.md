# Market Validation — "$500/mo gap" check (2026-07-07)

Reference notes from the validation pass run before building the rate-limiting
feature. Keep this updated if pricing/competitors shift — it's a snapshot, not
a living source of truth.

## Framework

- **Problem**: does enterprise software solving this exist, and does it cost
  enough per month to be out of reach for an individual dev / small team?
- **Solution (status quo)**: is the alternative a free-but-inadequate DIY hack
  (spreadsheet-tier)?
- **Opportunity**: is there room for a low-cost, per-usage-priced tool sitting
  between the two?

## 1. Enterprise pricing survey

The specific capability this project targets — **hard per-user/per-team
budget enforcement with request blocking**, not just observability/logging —
is consistently gated behind a custom-quote Enterprise tier:

| Tool | Self-serve tiers | Enterprise (has budget enforcement/RBAC) |
|---|---|---|
| Portkey | Free → $49/mo | $2,000–$10,000+/mo |
| Helicone | Free → $79/mo → $799/mo (Team) | Custom, contact sales |
| Langfuse | Free → $29/mo → $199/mo | $2,499/mo (+$300/mo SSO/RBAC add-on) |
| LangSmith | Free → $39/mo | ~$2,000–5,000/mo (typical reported range) |
| Kong AI Gateway | — | $30K–250K+/year ($2.5K–20K+/mo) |
| LiteLLM (BerriAI) | Free (self-hosted, full features) | ~$2,500/mo (SSO/audit/RBAC/support) |

**Average enterprise entry point for this capability: ~$2,000–5,000/mo.**
The "over $500/mo" leg of the framework holds.

## 2. The "free alternative" reality check — important caveat

The free alternative is **not** just an inadequate spreadsheet. It's real:

**[LiteLLM](https://github.com/BerriAI/litellm)** (BerriAI, YC W23) is a free,
MIT-licensed, actively maintained OSS proxy that already does almost exactly
what this repo does, and more:

- OpenAI-compatible pass-through to 100+ providers (this repo: 2)
- Virtual API keys with per-key/per-user/per-team **budgets** (daily/monthly)
- **RPM/TPM rate limits** per key — i.e., the per-endpoint rate limiting
  feature planned in [[rate-limiting]] already exists here, for free
- Cost tracking, admin UI, load balancing, fallback routing, guardrails,
  streaming support
- Only SSO, audit logs, JWT auth, and org-wide RBAC are paywalled (~$250/mo+
  enterprise add-on)
- **Also has a hosted/managed cloud offering** (LiteLLM Cloud) for teams that
  don't want to run their own Postgres/Redis — pricing not self-serve,
  contact-sales for anything beyond the OSS self-host

Company facts (as of this check): founded 2023, San Francisco, YC-backed,
~$2.1M raised (FoundersX, Gravity Fund, Pioneer Fund, YC), ~13 employees.
This is a funded, multi-year-head-start incumbent — not an abandoned side
project.

**The real gap is operational, not feature-based.** LiteLLM's free tier
requires self-hosting: Docker, Postgres (+Redis at scale), YAML config,
ongoing patching. That's a genuine barrier for a solo dev or a 2–10 person
team with no ops capacity — but it's a *convenience/hosting* gap, and
LiteLLM Cloud is already positioned to close it (just not self-serve/cheap).

## 3. Revised opportunity statement

Not: *"no affordable option exists between free-and-useless and $2K/mo
enterprise."*

Instead: *"the free option that already does this makes you run
infrastructure and think in org/team/RBAC concepts; there's room for a
narrower, zero-config, truly self-serve, per-usage-priced tool aimed at
people LiteLLM's design doesn't optimize for."*

See [[positioning-vs-litellm]] for how to narrow this before building.

## 4. Honest build-vs-compete assessment

- **Can this "knock out" LiteLLM as a general LLM gateway?** No. LiteLLM has
  a 3-year head start, YC/VC backing, a team, 100+ provider support,
  guardrails, caching, fallback routing, and a hosted cloud tier already
  aimed at the exact "don't want ops burden" buyer this project would target.
  Competing head-on on feature breadth is not realistic for a solo/small
  project in any reasonable timeframe.
- **Where a wedge might exist**: extreme simplicity and a different buyer.
  LiteLLM (and Portkey/Helicone/Langfuse) are sold to platform/infra teams
  managing *internal* org LLM usage (hence org/team/RBAC/SSO concepts). A
  narrower, credible JTBD is **indie SaaS builders who need to cap spend on
  their own *end customers'* AI usage** inside a product they're shipping —
  a simpler mental model (one URL, one header, one limit) than an internal
  enterprise gateway, and a buyer LiteLLM's enterprise motion isn't chasing.
- **Time-to-build**: the current MVP (pass-through + cost tracking + daily
  limit) is already essentially done in ~500 lines. Rate limiting adds days,
  not weeks. A sellable product (auth, multi-tenant, hosted infra, billing,
  landing page) is a few weeks of focused solo work — the build is not the
  hard part.
- **Time-to-revenue**: the hard part is distribution, not code. This space
  already has multiple well-marketed free tiers (LiteLLM, Portkey, Helicone)
  competing for the exact same low-volume/solo-dev attention. Realistic
  outlook is a niche micro-SaaS / side-income tool if the positioning above
  is executed and marketed specifically to the indie-SaaS-builder segment —
  not a venture-scale outcome, and not a LiteLLM replacement.
