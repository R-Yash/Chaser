from dotenv import load_dotenv
from datetime import datetime
import os
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from apscheduler.schedulers.background import BackgroundScheduler

from db import init_db
from api import router
from scheduler import run_for_all_users

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

app = FastAPI()
init_db()
app.include_router(router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = BackgroundScheduler()
scheduler.add_job(run_for_all_users, "interval", hours=1, next_run_time=datetime.now())
scheduler.start()

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/")
def home():
    return HTMLResponse("Chaser Backend is running.")