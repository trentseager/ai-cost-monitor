import os
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from db import all_usage, init_db
from fetch_usage import run as fetch_usage_run

load_dotenv()

app = FastAPI(title="AI API Cost/Token Monitor")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

scheduler = BackgroundScheduler()


@app.on_event("startup")
def startup():
    init_db()
    interval = int(os.environ.get("FETCH_INTERVAL_MINUTES", "60"))
    scheduler.add_job(fetch_usage_run, "interval", minutes=interval, id="fetch_usage")
    scheduler.start()


@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown(wait=False)


@app.get("/")
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/usage")
def usage():
    return all_usage()
