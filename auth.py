import os
import hmac
import hashlib
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.oauth2 import id_token as google_id_token
from google.auth.transport.requests import Request as GoogleRequest
from sqlmodel import select
from fastapi import HTTPException, Header

from db import get_session
from models import User

CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
REDIRECT_URI = os.environ["REDIRECT_URI"]
SESSION_SECRET = os.environ["SESSION_SECRET"].encode()

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.modify",
]

def _flow(state=None, autogenerate_code_verifier=False):
    client_config = {
        "web": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        state=state,
        autogenerate_code_verifier=autogenerate_code_verifier,
    )

def make_token(user_id: int) -> str:
    """Create a signed bearer token: '<user_id>.<hmac signature>'"""
    sig = hmac.new(SESSION_SECRET, str(user_id).encode(), hashlib.sha256).hexdigest()
    return f"{user_id}.{sig}"

# auth.py — temporary debug version of get_current_user
def get_current_user(authorization: str | None = Header(default=None)) -> User:
    print("raw authorization header:", repr(authorization))

    if not authorization or not authorization.startswith("Bearer "):
        print("failed at: missing/malformed Bearer prefix")
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.removeprefix("Bearer ")
    user_id_str, _, sig = token.partition(".")
    print("parsed user_id_str:", repr(user_id_str), "| sig:", repr(sig))

    if not user_id_str.isdigit():
        print("failed at: user_id_str is not digits")
        raise HTTPException(status_code=401, detail="Not authenticated")

    expected_sig = hmac.new(SESSION_SECRET, user_id_str.encode(), hashlib.sha256).hexdigest()
    print("expected_sig:", expected_sig)
    print("sigs match:", hmac.compare_digest(sig, expected_sig))

    if not hmac.compare_digest(sig, expected_sig):
        print("failed at: signature mismatch")
        raise HTTPException(status_code=401, detail="Not authenticated")

    with get_session() as session:
        user = session.get(User, int(user_id_str))
    if not user:
        print("failed at: no user row for id", user_id_str)
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

def build_login() -> dict:
    """Returns the Google auth URL plus the state/verifier the frontend must hold onto
    (in short-lived cookies) until the callback comes back."""
    flow = _flow(autogenerate_code_verifier=True)
    url, state = flow.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="true"
    )
    return {"url": url, "state": state, "code_verifier": flow.code_verifier}

def exchange_code(code: str, state: str, code_verifier: str) -> int:
    """Exchanges the OAuth code for tokens, upserts the User row, returns user.id."""
    flow = _flow(state=state, autogenerate_code_verifier=False)
    flow.code_verifier = code_verifier
    flow.fetch_token(code=code)
    creds = flow.credentials

    claims = google_id_token.verify_oauth2_token(
        creds.id_token, GoogleRequest(), CLIENT_ID, clock_skew_in_seconds=10
    )
    email = claims["email"]

    with get_session() as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if user is None:
            user = User(
                email=email,
                access_token=creds.token,
                refresh_token=creds.refresh_token,
                token_expiry=creds.expiry,
            )
        else:
            user.access_token = creds.token
            user.refresh_token = creds.refresh_token
            user.token_expiry = creds.expiry
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id

def get_credentials(user: User) -> Credentials:
    creds = Credentials(
        token=user.access_token,
        refresh_token=user.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=SCOPES,
    )
    if creds.expired:
        creds.refresh(GoogleRequest())
        with get_session() as session:
            db_user = session.get(User, user.id)
            db_user.access_token = creds.token
            db_user.token_expiry = creds.expiry
            session.add(db_user)
            session.commit()
    return creds