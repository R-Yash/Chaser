import os
from sqlmodel import select
from google import genai

from db import get_session
from models import Thread, Message
from dotenv import load_dotenv
load_dotenv()

client = genai.Client()
MODEL = "gemini-3.1-pro-preview" 

def _extract_text(interaction) -> str:
    for step in interaction.steps:
        if step.type == "model_output":
            for block in step.content:
                if block.type == "text":
                    return block.text

def load_thread_context(thread_id: int) -> str:
    with get_session() as session:
        thread = session.get(Thread, thread_id)
        messages = session.exec(
            select(Message).where(Message.thread_id == thread_id).order_by(Message.sent_at)
        ).all()

    history = "\n".join(f"[{m.direction}] {m.snippet}" for m in messages)
    return (
        f"Company: {thread.company or 'unknown'}\n"
        f"Role: {thread.role or 'unknown'}\n"
        f"Contact: {thread.contact_email}\n"
        f"Last email type: {thread.last_type}\n"
        f"Message history:\n{history}"
    )

def get_voice_examples() -> str:
    path = os.path.join(os.path.dirname(__file__), "voice_examples.txt")
    if not os.path.exists(path):
        return ""
    with open(path) as f:
        return f.read()


def draft_followup(thread_id: int) -> str:
    context = load_thread_context(thread_id)

    interaction = client.interactions.create(
        model=MODEL,
        input=(
            "You're drafting a short follow-up email for a job search thread.\n\n"
            f"{context}\n\n"
            "If a company news hook or the posting's current status would meaningfully "
            "change the tone, search for it. Otherwise just write the follow-up directly, "
            "searching isn't required. Keep it under 120 words, no subject line."
        ),
        tools=[{"type": "google_search"}],
    )

    return critique_and_revise(_extract_text(interaction))

def critique_and_revise(draft: str) -> str:
    examples = get_voice_examples()
    if not examples:
        return draft 

    interaction = client.interactions.create(
        model=MODEL,
        input=(
            "Here are examples of how this person actually writes emails:\n\n"
            f"{examples}\n\n"
            f"Here's a drafted follow-up:\n\n{draft}\n\n"
            "Rewrite it so it sounds like them, not an AI assistant. Specifically cut: "
            "em dashes, 'I hope this finds you well', overly parallel sentence structure, "
            "or a listicle-style opener. Keep the length and intent the same. "
            "Return only the rewritten email, nothing else."
        ),
    )
    return _extract_text(interaction)