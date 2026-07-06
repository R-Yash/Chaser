from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    access_token: str
    refresh_token: str
    token_expiry: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)