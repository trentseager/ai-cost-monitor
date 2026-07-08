"""
Per-token pricing manifest (USD per 1,000,000 tokens).

These numbers WILL drift — verify against each provider's current pricing
page before relying on them for real billing decisions. Unknown models
return known=False so callers can flag "cost unverified" instead of
silently logging $0.
"""

PRICING = {
    "anthropic": {
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
        "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    },
    "openai": {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    },
}


def estimate_cost(provider: str, model: str, tokens_in: int, tokens_out: int) -> tuple[float, bool]:
    rates = PRICING.get(provider, {}).get(model)
    if rates is None:
        return 0.0, False
    cost = (tokens_in / 1_000_000) * rates["input"] + (tokens_out / 1_000_000) * rates["output"]
    return cost, True
