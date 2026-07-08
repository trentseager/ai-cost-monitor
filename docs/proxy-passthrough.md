# Proxy Pass-Through

**Status: built**

## Rules

- A dev's SDK points its `base_url` at this proxy instead of the provider directly. Route paths mirror each provider's real API path exactly (`/anthropic/v1/messages`, `/openai/v1/chat/completions`), so no other client code changes.
- Every request must carry an `X-User-Id` header. Missing it → `400`, request is not forwarded.
- The dev's own `Authorization` / `x-api-key` header is forwarded upstream unchanged. The proxy never holds or stores a provider API key itself.
- Hop-by-hop headers and the inbound `X-User-Id` are stripped before forwarding; everything else passes through as-is.
- The upstream response (status, body, content-type) is returned to the caller unchanged, regardless of whether usage parsing/logging succeeds.
- Requests with `"stream": true` are rejected with `400`. Streaming is not supported — usage only arrives in the final SSE chunk, and buffering it correctly while passing chunks through live is deferred on purpose.
- The proxy never stores or inspects prompt/response content — only the `usage` object.
