"""
Per-provider proxy manifest: where to forward, and how to pull token usage
back out of that provider's response shape. Route paths mirror each
provider's real API path exactly, so a dev only has to change their SDK's
base_url to point at this proxy — no other client code changes.
"""

import os

# Used to size a credit reservation when a request omits an output-token
# ceiling (e.g. OpenAI chat completions without `max_tokens`). Anthropic's
# Messages API requires `max_tokens` on every request, so this only ever
# applies to OpenAI in practice today.
FALLBACK_MAX_OUTPUT_TOKENS = int(os.environ.get("CREDIT_FALLBACK_MAX_TOKENS", "4096"))


def _text_len(content) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(b.get("text", "")) for b in content if isinstance(b, dict) and b.get("type") == "text")
    return 0


def _estimate_input_tokens(body: dict) -> int:
    """Cheap chars/4 estimate of input tokens for sizing a credit
    reservation before the request is forwarded. Only affects how
    conservative the reservation is — actual billing always uses the real
    usage reported by the provider's response."""
    chars = _text_len(body.get("system"))
    for msg in body.get("messages", []):
        chars += _text_len(msg.get("content"))
    return max(1, chars // 4)


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
        "estimate_input_tokens": _estimate_input_tokens,
    },
    "openai": {
        "upstream_url": "https://api.openai.com/v1/chat/completions",
        "extract_usage": _openai_usage,
        "estimate_input_tokens": _estimate_input_tokens,
    },
}
