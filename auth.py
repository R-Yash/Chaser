import os
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.oauth2 import id_token as google_id_token
from google.auth.transport.requests import Request as GoogleRequest
from sqlmodel import select

from db import get_session
from models import User

CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
REDIRECT_URI = os.environ["REDIRECT_URI"]

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

    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=REDIRECT_URI, state=state, autogenerate_code_verifier=autogenerate_code_verifier)

def get_login_url(request) -> str:
    flow = _flow(autogenerate_code_verifier=True)
    url, state = flow.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")
    
    request.session['state'] = state
    request.session['code_verifier'] = flow.code_verifier
    
    return url

def handle_callback(request, request_url: str) -> str:
    state = request.session.get('state')
    code_verifier = request.session.get('code_verifier')

    flow = _flow(state=state, autogenerate_code_verifier=False)
    flow.code_verifier = code_verifier
    
    flow.fetch_token(authorization_response=request_url)
    creds = flow.credentials

    claims = google_id_token.verify_oauth2_token(creds.id_token, GoogleRequest(), CLIENT_ID,clock_skew_in_seconds=10)
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

    return email

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