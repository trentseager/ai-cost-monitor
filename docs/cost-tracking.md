# Cost & Token Tracking

**Status: built**

## Rules

- After a successful upstream response, the proxy parses the response body as JSON and extracts `(model, tokens_in, tokens_out)` via the matching provider's usage extractor.
- If usage is present, cost is computed from a manually maintained per-token pricing table (USD per 1M tokens), keyed by provider + exact model string.
- An unrecognized model returns `pricing_known=False` and `$0` cost rather than a guessed number — never silently mis-bill.
- Every request is logged as one row (user, provider, model, tokens in/out, cost, blocked flag, pricing_known flag), regardless of whether it was blocked or pricing was known.
- The pricing table is a snapshot and will drift — it is not fetched live from provider pricing pages.
