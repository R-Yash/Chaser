from dotenv import load_dotenv
import os
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse

from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from db import init_db, get_session
from auth import get_login_url, handle_callback
from api import router
from models import User
from scheduler import sync_and_classify, run_for_all_users

FRONTEND_URL = "http://localhost:3000"

app = FastAPI()
init_db()
app.include_router(router)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET"),
    same_site="none" if FRONTEND_URL.startswith("https") else "lax",
    https_only=FRONTEND_URL.startswith("https"),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = BackgroundScheduler()
scheduler.add_job(run_for_all_users, "interval", hours=1)
scheduler.start()               
                
@app.get("/")
def home():
    return HTMLResponse('<a href="/login">Connect your Gmail</a>')

@app.get("/login")
def login(request: Request):
    return RedirectResponse(get_login_url(request))

@app.get("/auth/callback")
def auth_callback(request: Request, code:str):
    user_id = handle_callback(request, str(request.url))
    request.session["user_id"] = user_id

    # with get_session() as session:
    #     user = session.get(User, user_id)
    #     try:
    #         sync_and_classify(user)
    #     except Exception as e:
    #         print(f"initial sync failed for user {user_id}: {e}")

    return RedirectResponse(url=f"{FRONTEND_URL}/dashboard")
