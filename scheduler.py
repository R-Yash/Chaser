# scheduler.py
from datetime import datetime
from sqlmodel import select

from db import get_session
from models import User, Thread, Message
from gmail import fetch_new_messages
from llm import analyze_email

NUDGE_THRESHOLDS = {0: 5, 1: 9, 2: 16}
CLOSED_TYPES = {"rejection", "offer"}

def sync_and_classify(user: User) -> None:
    for m in fetch_new_messages(user):
        with get_session() as session:
            already_seen = session.exec(select(Message).where(Message.gmail_message_id == m["gmail_id"])).first()
            
            if already_seen:
                continue

            analysis = analyze_email(m["subject"], m["body"], m["from_addr"])
            if analysis["type"] == "not_job_related":
                continue

            thread = session.exec(
                select(Thread).where(
                    Thread.user_id == user.id,
                    Thread.gmail_thread_id == m["thread_id"],
                )
            ).first()

            if thread is None:
                thread = Thread(
                    user_id=user.id,
                    gmail_thread_id=m["thread_id"],
                    company=analysis["company"],
                    role=analysis["role"],
                    contact_email=m["from_addr"],
                    last_type=analysis["type"],
                )

            thread.last_type = analysis["type"]
            thread.company = thread.company or analysis["company"]
            thread.role = thread.role or analysis["role"]

            if analysis["type"] in CLOSED_TYPES:
                thread.status = "closed"
                thread.last_message_at = datetime.utcnow()
            elif not analysis["is_no_reply"]:
                thread.status = "active"
                thread.sequence_step = 0
                thread.last_message_at = datetime.utcnow()
 
            session.add(thread)
            session.commit()
            session.refresh(thread)

            session.add(Message(
                thread_id=thread.id,
                gmail_message_id=m["gmail_id"],
                direction="in",
                snippet=m["snippet"],
            ))
            session.commit()


def decide_nudges(user: User) -> None:
    max_step = max(NUDGE_THRESHOLDS)
    with get_session() as session:
        threads = session.exec(
            select(Thread).where(Thread.user_id == user.id, Thread.status == "active")
        ).all()

        for t in threads:
            if t.sequence_step > max_step:
                t.status = "stale"  
                session.add(t)
                continue
            days_quiet = (datetime.utcnow() - t.last_message_at).days
            if days_quiet >= NUDGE_THRESHOLDS[t.sequence_step]:
                t.status = "needs_nudge"
                session.add(t)
        session.commit()


def run_for_all_users() -> None:
    with get_session() as session:
        users = session.exec(select(User)).all()
    
    for user in users:
        sync_and_classify(user)
        decide_nudges(user)