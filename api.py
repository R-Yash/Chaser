from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from db import get_session
from models import Thread, User, Message, VoiceExample
from auth import get_current_user, build_login, exchange_code, make_token
from scheduler import sync_and_classify, decide_nudges, send_one_nudge, CLOSED_TYPES

VALID_TYPES = {"application_ack", "rejection", "interview_invite", "assessment", "recruiter_reply", "offer"}
MAX_VOICE_EXAMPLES = 15
MAX_VOICE_EXAMPLE_LEN = 8000

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
            msgs = session.exec(
                select(Message).where(Message.thread_id == t.id).order_by(Message.sent_at.desc())
            ).all()
            result.append({
                **t.model_dump(),
                "snippet": msgs[0].snippet if msgs else "",
                "message_count": len(msgs),
            })
        return result

class SendNudgeBody(BaseModel):
    text: str | None = None

@router.post("/threads/{thread_id}/send-nudge")
def send_nudge(thread_id: int, body: SendNudgeBody = SendNudgeBody(), user: User = Depends(get_current_user)):
    with get_session() as session:
        t = session.get(Thread, thread_id)
        if not t or t.user_id != user.id:
            raise HTTPException(status_code=404, detail="Thread not found")
    try:
        send_one_nudge(thread_id, body.text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Send failed: {e}")
    return {"status": "sent"}

class UpdateThreadBody(BaseModel):
    company: str
    role: str
    contact_name: str
    contact_email: str
    last_type: str
    created_at: datetime
    last_message_at: datetime

@router.patch("/threads/{thread_id}")
def update_thread(thread_id: int, body: UpdateThreadBody, user: User = Depends(get_current_user)):
    if body.last_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail="Invalid type")
    with get_session() as session:
        t = session.get(Thread, thread_id)
        if not t or t.user_id != user.id:
            raise HTTPException(status_code=404, detail="Thread not found")

        t.company = body.company or None
        t.role = body.role or None
        t.contact_name = body.contact_name or None
        t.contact_email = body.contact_email
        t.last_type = body.last_type
        t.created_at = body.created_at
        t.last_message_at = body.last_message_at

        if body.last_type in CLOSED_TYPES:
            t.status = "closed"
        elif t.status == "closed":
            t.status = "active"

        session.add(t)
        session.commit()
    return {"status": "ok"}

class VoiceExampleBody(BaseModel):
    content: str

@router.get("/voice-examples")
def list_voice_examples(user: User = Depends(get_current_user)):
    with get_session() as session:
        examples = session.exec(
            select(VoiceExample).where(VoiceExample.user_id == user.id).order_by(VoiceExample.created_at.desc())
        ).all()
    return [e.model_dump() for e in examples]

@router.post("/voice-examples")
def add_voice_example(body: VoiceExampleBody, user: User = Depends(get_current_user)):
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Content is empty")
    if len(content) > MAX_VOICE_EXAMPLE_LEN:
        raise HTTPException(status_code=400, detail=f"Content exceeds {MAX_VOICE_EXAMPLE_LEN} characters")

    with get_session() as session:
        count = len(session.exec(select(VoiceExample).where(VoiceExample.user_id == user.id)).all())
        if count >= MAX_VOICE_EXAMPLES:
            raise HTTPException(status_code=400, detail=f"Limit of {MAX_VOICE_EXAMPLES} examples reached, delete one first")

        example = VoiceExample(user_id=user.id, content=content)
        session.add(example)
        session.commit()
        session.refresh(example)
        return example.model_dump()

@router.delete("/voice-examples/{example_id}")
def delete_voice_example(example_id: int, user: User = Depends(get_current_user)):
    with get_session() as session:
        e = session.get(VoiceExample, example_id)
        if not e or e.user_id != user.id:
            raise HTTPException(status_code=404, detail="Not found")
        session.delete(e)
        session.commit()
    return {"status": "ok"}

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