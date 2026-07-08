# Positioning against LiteLLM

See [[market-validation]] for the pricing/competitive research this is based
on. This doc is the "how to narrow it" answer, not more research.

## Do not compete on

LiteLLM already wins these outright — don't spend build time trying to match:

- Provider breadth (100+ providers vs. our 2)
- Guardrails, caching, fallback routing, load balancing
- Streaming support
- Enterprise SSO/RBAC/audit logs
- A hosted cloud tier already exists for them too (contact-sales, not
  self-serve, but it exists — "we're the hosted version" is not virgin
  ground)

Trying to out-feature a 3-year-old, YC-backed, funded incumbent on its own
turf is not a winnable fight for a solo/small project.

## Compete on: buyer, not features

LiteLLM (and Portkey/Helicone/Langfuse) sell to **platform/infra teams
metering internal org LLM usage** — hence the org/team/RBAC/SSO/config-file
shape of the product. That buyer already has an ops team and picks LiteLLM
for free, or pays $2K+/mo for the enterprise version.

The open buyer is different: **an indie dev or small SaaS team that needs to
cap what their own *end customers* spend on AI inside a product they're
shipping** — not managing internal headcount, just "user Alice on my SaaS
gets $2/day of AI before she's cut off." That's a simpler mental model (one
proxy URL, one header, one number) than an internal enterprise gateway, and
it's not the buyer LiteLLM's enterprise sales motion or org/team data model
is built around.

## Concrete positioning moves

1. **Message around setup time, explicitly**: "cap a user's AI spend in 5
   minutes — no Postgres, no Redis, no YAML, no Docker" vs. LiteLLM's
   self-host requirements. This is a real, honest difference as long as the
   product stays true self-serve (sign up, get a URL, no sales call) —
   LiteLLM Cloud is not self-serve today.
2. **Name the buyer in the copy**: "for indie SaaS builders billing/limiting
   your own customers' AI usage" — not "AI gateway" or "LLM observability
   platform," which reads as competing with LiteLLM/Portkey/Helicone
   head-on and invites the feature-for-feature comparison you'd lose.
3. **Pricing shape, not just price**: pure usage-based (cents per proxied
   request, or a % markup) rather than a flat monthly subscription, so it's
   trivially adoptable at near-zero volume — undercutting the psychological
   floor of even LiteLLM's $250/mo enterprise add-on or a $29–49/mo
   Langfuse/Portkey tier.
4. **Stay narrow on purpose**: don't add providers/guardrails/caching just
   because LiteLLM has them — every feature added in that direction moves
   the comparison onto ground LiteLLM already owns. The pitch only stays
   defensible while it's obviously simpler, not while it's catching up.
5. **Be honest in the copy that LiteLLM exists.** Technical buyers evaluating
   this space already know it (~20k+ GitHub stars, the default answer in
   "how do I track LLM API costs" discussions). A landing page claiming "no
   alternative exists" will read as either uninformed or dishonest to the
   exact audience being targeted; "simpler and hosted, if you don't want to
   run LiteLLM yourself" is the credible version of the same claim.
