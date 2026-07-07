from dotenv import load_dotenv
import os
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from scheduler import run_for_all_users

from db import init_db
from auth import get_login_url, handle_callback

app = FastAPI()
init_db()
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET"))

scheduler = BackgroundScheduler()
scheduler.add_job(run_for_all_users, "interval", hours=12)
scheduler.start()               
                
@app.get("/")
def home():
    return HTMLResponse('<a href="/login">Connect your Gmail</a>')

@app.get("/login")
def login(request: Request):
    return RedirectResponse(get_login_url(request))

@app.get("/auth/callback")
def auth_callback(request: Request):
    email = handle_callback(request, str(request.url))
    return HTMLResponse(f"Connected as {email}. You can close this tab.")