import base64
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from dotenv import load_dotenv
load_dotenv()

from googleapiclient.discovery import build

from auth import get_credentials
from db import get_session
from models import User
from sqlmodel import select

def _service(user: User):
    creds = get_credentials(user)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)

def header(headers: list, name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""

def extract_body(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    
    for part in payload.get("parts", []):
        text = extract_body(part)
        if text:
            return text
    return ""

def parse_message(raw: dict) -> dict:
    headers = raw["payload"]["headers"]
    label_ids = raw.get("labelIds", [])
    return {
        "gmail_id": raw["id"],
        "thread_id": raw["threadId"],
        "direction": "out" if "SENT" in label_ids else "in",
        "from_addr": header(headers, "From"),
        "to_addr": header(headers, "To"),
        "subject": header(headers, "Subject"),
        "message_id_header": header(headers, "Message-ID"),
        "date": header(headers, "Date"),
        "snippet": raw.get("snippet", ""),
        "body": extract_body(raw["payload"]),
    }

def fetch_new_messages(user: User) -> list[dict]:
    service = _service(user)
    since = user.last_synced_at or (datetime.utcnow() - timedelta(days=7))
    
    query = f"after:{int(since.timestamp())} (in:inbox OR in:sent)"

    results = service.users().messages().list(userId="me", q=query).execute()
    ids = [m["id"] for m in results.get("messages", [])]
    
    messages = [
        parse_message(service.users().messages().get(userId="me", id=i, format="full").execute())
        for i in ids
    ]

    with get_session() as session:
        db_user = session.get(User, user.id)
        db_user.last_synced_at = datetime.utcnow()
        session.add(db_user)
        session.commit()

    return messages

def send_email(user: User, to_addr: str, subject: str, body_text: str,
                thread_id: str = None, in_reply_to: str = None) -> dict:
    serv = _service(user)

    mime = MIMEText(body_text)
    mime["to"] = to_addr
    mime["subject"] = subject
    if in_reply_to:
        mime["In-Reply-To"] = in_reply_to
        mime["References"] = in_reply_to

    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    body = {"raw": raw}
    if thread_id:
        body["threadId"] = thread_id

    return serv.users().messages().send(userId="me", body=body).execute()