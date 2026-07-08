# SaaS founder billing pain points (research, 2026-07-07)

Research pass done to find automatable gaps for the "indie SaaS builder
capping their own end customers' AI usage" buyer identified in
[[positioning-vs-litellm]]. None of these four pains are addressed by
LiteLLM/Portkey/Helicone/Langfuse — those tools serve internal engineering
teams metering org usage, not founders reselling AI inside a product to
paying customers.

## Findings

1. **Cash-flow timing mismatch.** Provider bills (OpenAI, etc.) land
   mid-month; the founder's own Stripe subscription/invoice cycle for that
   customer settles at month-end. The founder fronts the AI cost and eats
   the risk if the customer's payment later fails.
2. **No pre-authorization / real-time reservation.** Existing tools (and
   this project's current [[daily-limits]] check) only compare spend
   *after the fact* against a threshold. Best practice surfacing in the
   research is reserve-then-settle: hold the estimated cost against a
   customer's balance *before* the call runs (credit-card pre-auth model),
   so a runaway agent loop can't blow past what a customer can actually pay
   for before anyone notices.
3. **Deferred billing risk.** Usage happens now; the founder's invoice for
   that customer settles later. If the invoice/payment fails, the AI cost
   is already spent. The workaround that keeps coming up is prepaid credits
   (customer tops up before use), not postpaid invoicing.
4. **Multi-provider reconciliation.** Founders stitching together several
   providers (LLM + ASR + TTS, etc.) end up manually reconciling many line
   items per client per month with no unified per-customer cost view.

## How this feeds prioritization

- Pain #2 + #3 → **prepaid credit balance with reserve/settle**, spec'd in
  [[credit-reserve-settle]]. Chosen as the first build: most defensible,
  most different from what LiteLLM/Portkey/Helicone already do, and directly
  answers the two sharpest pains (cash-flow exposure, no real-time guard).
- Pain #1 → **Stripe Meters API sync**, deferred until the core reserve/
  settle mechanism is functional (see "Future work" in
  [[credit-reserve-settle]]).
- Pain #4 → **unified per-customer cost ledger across providers**, also
  deferred; this project's `requests` table already stores cost per provider
  per user, so this is mostly a reporting/rollup layer once more providers
  exist, not a new data model.

## Sources

- [Indie Hackers: how we discovered a $100M problem building an AI infra layer](https://www.indiehackers.com/post/how-we-discovered-a-100m-problem-while-building-an-ai-infrastructure-layer-9b1dabdf77)
- [Indie Hackers: use credit-based billing, here's why](https://www.indiehackers.com/post/building-an-ai-project-use-credit-based-billing-heres-why-f5bb4e89ad)
- [Stripe: Usage-Based Billing for AI Companies](https://stripe.com/resources/more/ai-companies-and-usage-based-billing)
- [Stripe: advanced usage-based billing docs](https://docs.stripe.com/billing/subscriptions/usage-based/advanced/about)
