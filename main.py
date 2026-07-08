import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from db import (
    add_credit, credit_summaries, daily_totals, get_limit, has_credit_metering, init_db,
    log_request, release_reservation, reserve_credit, set_limit, settle_reservation,
    today_cost_for_user, user_summaries_today,
)
from pricing import estimate_cost
from providers import PROVIDERS, FALLBACK_MAX_OUTPUT_TOKENS

load_dotenv()

app = FastAPI(title="AI API Cost/Token Monitor Proxy")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Headers we must not blindly forward: hop-by-hop headers plus our own
# out-of-band control header (the user id tag, stripped before upstream).
STRIPPED_HEADERS = {
    "host", "content-length", "connection", "keep-alive", "transfer-encoding",
    "upgrade", "te", "trailer", "proxy-authenticate", "proxy-authorization",
    "x-user-id",
}


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


async def _proxy_request(provider: str, request: Request) -> Response:
    cfg = PROVIDERS[provider]

    user_id = request.headers.get("x-user-id")
    if not user_id:
        raise HTTPException(400, "X-User-Id header is required")

    body_bytes = await request.body()
    try:
        body_json = json.loads(body_bytes) if body_bytes else {}
    except json.JSONDecodeError:
        raise HTTPException(400, "request body must be JSON")

    if body_json.get("stream"):
        raise HTTPException(400, "streaming is not supported by this proxy yet")

    limit = get_limit(user_id)
    if limit is not None:
        spent = today_cost_for_user(user_id)
        if spent >= limit:
            log_request(user_id, provider, body_json.get("model", "unknown"), 0, 0, 0.0, blocked=True, pricing_known=True)
            raise HTTPException(429, f"daily limit reached (${spent:.4f} spent of ${limit:.4f})")

    # Prepaid credit: reserve the worst-case cost before forwarding, settle
    # to the actual cost once the response comes back. See
    # docs/credit-reserve-settle.md. Layered on top of the daily limit above,
    # not a replacement for it.
    reservation_id = None
    request_model = body_json.get("model", "unknown")
    if has_credit_metering(user_id):
        tokens_in_estimate = cfg["estimate_input_tokens"](body_json)
        tokens_out_ceiling = body_json.get("max_tokens") or FALLBACK_MAX_OUTPUT_TOKENS
        reserved_cost, pricing_known = estimate_cost(provider, request_model, tokens_in_estimate, tokens_out_ceiling)
        if not pricing_known:
            log_request(user_id, provider, request_model, 0, 0, 0.0, blocked=True, pricing_known=False)
            raise HTTPException(402, f"cannot reserve credit: no known pricing for model '{request_model}'")

        reservation_id = reserve_credit(user_id, provider, reserved_cost)
        if reservation_id is None:
            log_request(user_id, provider, request_model, 0, 0, 0.0, blocked=True, pricing_known=True)
            raise HTTPException(402, f"insufficient credit: need ${reserved_cost:.4f} reserved")

    forward_headers = {k: v for k, v in request.headers.items() if k.lower() not in STRIPPED_HEADERS}

    async with httpx.AsyncClient(timeout=120) as client:
        try:
            upstream = await client.post(cfg["upstream_url"], content=body_bytes, headers=forward_headers)
        except httpx.HTTPError as e:
            if reservation_id is not None:
                release_reservation(reservation_id)
            raise HTTPException(502, f"upstream request failed: {e}")

    try:
        resp_json = upstream.json()
    except ValueError:
        resp_json = None

    extracted = cfg["extract_usage"](resp_json) if resp_json is not None else None
    if extracted:
        model, tokens_in, tokens_out = extracted
        cost, known = estimate_cost(provider, model, tokens_in, tokens_out)
        log_request(user_id, provider, model, tokens_in, tokens_out, cost, blocked=False, pricing_known=known)
        if reservation_id is not None:
            settle_reservation(reservation_id, cost)
    elif reservation_id is not None:
        # No usage came back (upstream error/malformed response) — no
        # billable work happened, so refund the reservation in full.
        release_reservation(reservation_id)

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={"content-type": upstream.headers.get("content-type", "application/json")},
    )


@app.post("/anthropic/v1/messages")
async def anthropic_proxy(request: Request):
    return await _proxy_request("anthropic", request)


@app.post("/openai/v1/chat/completions")
async def openai_proxy(request: Request):
    return await _proxy_request("openai", request)


def require_admin(x_admin_key: str = Header(...)):
    expected = os.environ.get("PROXY_ADMIN_KEY")
    if not expected or x_admin_key != expected:
        raise HTTPException(401, "invalid admin key")


class LimitIn(BaseModel):
    user_id: str
    daily_limit_usd: float


@app.post("/admin/limits")
def admin_set_limit(payload: LimitIn, _: None = Depends(require_admin)):
    set_limit(payload.user_id, payload.daily_limit_usd)
    return {"ok": True}


@app.get("/admin/usage")
def admin_usage(_: None = Depends(require_admin)):
    return user_summaries_today()


@app.get("/admin/daily-totals")
def admin_daily_totals(_: None = Depends(require_admin)):
    return daily_totals()


class CreditIn(BaseModel):
    user_id: str
    amount_usd: float


@app.post("/admin/credits")
def admin_add_credit(payload: CreditIn, _: None = Depends(require_admin)):
    add_credit(payload.user_id, payload.amount_usd)
    return {"ok": True}


@app.get("/admin/credits")
def admin_credits(_: None = Depends(require_admin)):
    return credit_summaries()
