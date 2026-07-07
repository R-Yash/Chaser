from dotenv import load_dotenv
import os
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from starlette.middleware.sessions import SessionMiddleware

from db import init_db
from auth import get_login_url, handle_callback

app = FastAPI()
init_db()
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET"))
                
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