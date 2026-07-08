from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from db import get_session
from models import Thread, User
from auth import get_current_user
from scheduler import sync_and_classify

router = APIRouter(prefix="/api")

@router.get("/threads")
def list_threads(source: str, user: User = Depends(get_current_user)):
    with get_session() as session:
        threads = session.exec(
            select(Thread).where(Thread.user_id == user.id, Thread.source == source)
        ).all()
        return threads
    
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