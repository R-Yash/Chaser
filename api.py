from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from db import get_session
from models import Thread, User, Message
from auth import get_current_user, build_login, exchange_code, make_token
from scheduler import sync_and_classify, decide_nudges

router = APIRouter(prefix="/api")

class ExchangeBody(BaseModel):
    code: str
    state: str
    code_verifier: str

@router.get("/auth/login-url")
def login_url():
    return build_login()

@router.post("/auth/exchange")
def auth_exchange(body: ExchangeBody):
    user_id = exchange_code(body.code, body.state, body.code_verifier)
    return {"token": make_token(user_id)}

@router.get("/threads")
def list_threads(category: str, user: User = Depends(get_current_user)):
    with get_session() as session:
        query = select(Thread).where(Thread.user_id == user.id)
        if category == "rejected":
            query = query.where(Thread.last_type == "rejection")
        else:
            query = query.where(Thread.source == category, Thread.last_type != "rejection")
        query = query.order_by(Thread.last_message_at.desc())
        threads = session.exec(query).all()

        result = []
        for t in threads:
            latest = session.exec(
                select(Message).where(Message.thread_id == t.id).order_by(Message.sent_at.desc())
            ).first()
            result.append({**t.model_dump(), "snippet": latest.snippet if latest else ""})
        return result

@router.post("/threads/{thread_id}/send-nudge")
def send_nudge(thread_id: int, user: User = Depends(get_current_user)):
    with get_session() as session:
        t = session.get(Thread, thread_id)
        if not t or t.user_id != user.id:
            raise HTTPException(status_code=404, detail="Thread not found")
    try:
        send_nudge(thread_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Send failed: {e}")
    return {"status": "sent"}

@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"email": user.email}

@router.post("/sync")
def sync_inbox(user: User = Depends(get_current_user)):
    try:
        sync_and_classify(user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")
    return {"status": "ok"}

@router.post("/debug/decide-nudges")
def debug_decide_nudges(user: User = Depends(get_current_user)):
    decide_nudges(user)
    return {"status": "ran"}
