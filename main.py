import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from db import daily_totals, get_limit, init_db, log_request, set_limit, today_cost_for_user, user_summaries_today
from pricing import estimate_cost
from providers import PROVIDERS

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

    forward_headers = {k: v for k, v in request.headers.items() if k.lower() not in STRIPPED_HEADERS}

    async with httpx.AsyncClient(timeout=120) as client:
        try:
            upstream = await client.post(cfg["upstream_url"], content=body_bytes, headers=forward_headers)
        except httpx.HTTPError as e:
            raise HTTPException(502, f"upstream request failed: {e}")

    try:
        resp_json = upstream.json()
    except ValueError:
        resp_json = None

    if resp_json is not None:
        extracted = cfg["extract_usage"](resp_json)
        if extracted:
            model, tokens_in, tokens_out = extracted
            cost, known = estimate_cost(provider, model, tokens_in, tokens_out)
            log_request(user_id, provider, model, tokens_in, tokens_out, cost, blocked=False, pricing_known=known)

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
