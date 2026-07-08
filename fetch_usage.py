"""
Manifest-driven usage/cost fetcher.

Each entry in PROVIDERS describes how to pull usage data for one provider.
Run manually (`python fetch_usage.py`) or on a schedule (see main.py's
startup scheduler). Exact endpoint shapes are NOT finalized here — pull the
current usage/cost API docs for each provider before wiring up `fetch_fn`,
since these endpoints and their auth requirements change.
"""

import os
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

from db import init_db, upsert_usage

load_dotenv()


def fetch_anthropic() -> list[dict]:
    """
    Requires an Admin API key (ANTHROPIC_ADMIN_KEY), not a regular API key.
    TODO: confirm current endpoint + response shape against Anthropic's
    usage/cost reporting docs, then map the response into:
        [{"model": ..., "tokens_in": ..., "tokens_out": ..., "cost_usd": ..., "date": "YYYY-MM-DD"}]
    """
    key = os.environ.get("ANTHROPIC_ADMIN_KEY")
    if not key:
        print("skip anthropic: ANTHROPIC_ADMIN_KEY not set")
        return []
    raise NotImplementedError("wire up the real Anthropic usage/cost endpoint here")


def fetch_openai() -> list[dict]:
    """
    Requires elevated OpenAI credentials for usage endpoints.
    TODO: confirm current endpoint + response shape, map into the same
    record shape as fetch_anthropic().
    """
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("skip openai: OPENAI_API_KEY not set")
        return []
    raise NotImplementedError("wire up the real OpenAI usage endpoint here")


PROVIDERS = {
    "anthropic": fetch_anthropic,
    "openai": fetch_openai,
}


def run():
    init_db()
    fetched_at = datetime.now(timezone.utc).isoformat()
    for provider, fetch_fn in PROVIDERS.items():
        try:
            records = fetch_fn()
        except NotImplementedError as e:
            print(f"{provider}: not implemented yet ({e})")
            continue
        except Exception as e:
            print(f"{provider}: fetch failed: {e}")
            continue
        for r in records:
            upsert_usage(
                provider=provider,
                date=r["date"],
                model=r["model"],
                tokens_in=r.get("tokens_in", 0),
                tokens_out=r.get("tokens_out", 0),
                cost_usd=r.get("cost_usd", 0.0),
                fetched_at=fetched_at,
            )
        print(f"{provider}: upserted {len(records)} rows")


if __name__ == "__main__":
    run()
