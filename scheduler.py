# scheduler.py
from datetime import datetime
from sqlmodel import select

from db import get_session
from models import User, Thread, Message
from gmail import fetch_new_messages, send_email
from llm import analyze_email
from agent import draft_followup

NUDGE_THRESHOLDS = {0: 5, 1: 9, 2: 16}
CLOSED_TYPES = {"rejection", "offer"}

def sync_and_classify(user: User) -> None:
    for m in fetch_new_messages(user):
        try:
            with get_session() as session:
                already_seen = session.exec(select(Message).where(Message.gmail_message_id == m["gmail_id"])).first()

                if already_seen:
                    continue

                thread = session.exec(
                    select(Thread).where(
                        Thread.user_id == user.id,
                        Thread.gmail_thread_id == m["thread_id"],
                    )
                ).first()

                if m["direction"] == "out" and thread is not None:
                    thread.last_message_at = datetime.utcnow()
                    session.add(thread)
                    _log_message(session, thread, m)
                    continue

                analysis = analyze_email(
                    m["subject"], m["body"], m["from_addr"],
                    to_addr=m.get("to_addr"), direction=m["direction"],
                )

                is_trackable = (
                    analysis["type"] == "cold_outreach" if m["direction"] == "out"
                    else analysis["type"] != "not_job_related"
                )
                if not is_trackable:
                    continue

                if thread is None:
                    thread = Thread(
                        user_id=user.id,
                        gmail_thread_id=m["thread_id"],
                        company=analysis["company"],
                        role=analysis["role"],
                        contact_email=m["to_addr"] if m["direction"] == "out" else m["from_addr"],
                        last_type=analysis["type"],
                        source="outreach" if analysis["type"] == "cold_outreach" else "job"
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
                _log_message(session, thread, m)
        except Exception as e:
            print(f"sync failed for user {user.id}, message {m.get('gmail_id')}: {e}")
            continue

def _log_message(session, thread: Thread, m: dict) -> None:
    session.commit()
    session.refresh(thread)
    session.add(Message(
        thread_id=thread.id,
        gmail_message_id=m["gmail_id"],
        direction=m["direction"],
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
                try:
                    t.draft_nudge = draft_followup(t.id)
                    t.status = "needs_nudge"
                    session.add(t)
                except Exception as e:
                    print(f"draft failed for thread {t.id}: {e}")
        session.commit()

def send_nudge(thread_id: int) -> None:
    with get_session() as session:
        t = session.get(Thread, thread_id)
        if not t or t.status != "needs_nudge" or not t.draft_nudge:
            raise ValueError("Thread not ready to nudge")
        user = session.get(User, t.user_id)

    sent = send_email(
        user,
        to_addr=t.contact_email,
        subject=f"Re: {t.role or t.company or 'following up'}",
        body_text=t.draft_nudge,
        thread_id=t.gmail_thread_id,
    )

    with get_session() as session:
        db_thread = session.get(Thread, thread_id)
        db_thread.sequence_step += 1
        db_thread.status = "active"
        db_thread.last_message_at = datetime.utcnow()
        db_thread.draft_nudge = None
        session.add(db_thread)
        session.add(Message(
            thread_id=thread_id,
            gmail_message_id=sent["id"],
            direction="out",
            snippet=t.draft_nudge[:200],
        ))
        session.commit()

def run_for_all_users() -> None:
    with get_session() as session:
        users = session.exec(select(User)).all()
    for user in users:
        try:
            sync_and_classify(user)
        except Exception as e:
            print(f"sync_and_classify crashed for user {user.id}: {e}")

        try:
            decide_nudges(user)
        except Exception as e:
            print(f"decide_nudges crashed for user {user.id}: {e}")