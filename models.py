from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    access_token: str
    refresh_token: str
    token_expiry: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_synced_at: Optional[datetime] = None

class Thread(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    gmail_thread_id: str = Field(index=True)
    company: Optional[str] = None
    role: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: str
    source: str = "job"
    last_type: str 
    status: str = "active" 
    sequence_step: int = 0
    last_message_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    draft_nudge: str | None = None

class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    thread_id: int = Field(foreign_key="thread.id", index=True)
    gmail_message_id: str = Field(unique=True, index=True)
    direction: str  
    snippet: str
    sent_at: datetime = Field(default_factory=datetime.utcnow)

class UpdateThreadBody(BaseModel):
    company: str
    role: str
    contact_name: str
    contact_email: str
    last_type: str
    created_at: datetime
    last_message_at: datetime

class VoiceExample(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)