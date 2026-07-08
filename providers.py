"""
Per-provider proxy manifest: where to forward, and how to pull token usage
back out of that provider's response shape. Route paths mirror each
provider's real API path exactly, so a dev only has to change their SDK's
base_url to point at this proxy — no other client code changes.
"""


def _anthropic_usage(body: dict):
    usage = body.get("usage")
    model = body.get("model")
    if not usage or not model:
        return None
    return model, usage.get("input_tokens", 0), usage.get("output_tokens", 0)


def _openai_usage(body: dict):
    usage = body.get("usage")
    model = body.get("model")
    if not usage or not model:
        return None
    return model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


PROVIDERS = {
    "anthropic": {
        "upstream_url": "https://api.anthropic.com/v1/messages",
        "extract_usage": _anthropic_usage,
    },
    "openai": {
        "upstream_url": "https://api.openai.com/v1/chat/completions",
        "extract_usage": _openai_usage,
    },
}
