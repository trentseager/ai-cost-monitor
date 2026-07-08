# AI API Cost/Token Monitor

Tracks AI API spend and token usage (Anthropic, OpenAI, ...) over time and shows it on a small local dashboard.

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Fill in `.env` with real credentials. Note: provider usage/cost endpoints generally need elevated
credentials (e.g. Anthropic's usage/cost reporting requires an **Admin API key**, not a regular API
key). Check each provider's current docs — `fetch_usage.py` has `TODO`s marking exactly where the
real endpoint calls go; they're stubbed as `NotImplementedError` until wired up.

## Run

```
uvicorn main:app --reload
```

Dashboard: http://localhost:8000
API: http://localhost:8000/api/usage

The server schedules `fetch_usage.py` to run every `FETCH_INTERVAL_MINUTES` (default 60). You can
also run it manually:

```
python fetch_usage.py
```

## Structure

- `main.py` — FastAPI app: serves the dashboard + `/api/usage`, schedules the fetcher
- `db.py` — SQLite schema + read/write helpers (`usage.db`, gitignored)
- `fetch_usage.py` — manifest-driven per-provider fetcher (`PROVIDERS` dict)
- `static/index.html` — dashboard (Chart.js via CDN)
