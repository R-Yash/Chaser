import os
from dotenv import load_dotenv
from sqlmodel import SQLModel, create_engine, Session, text
load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"),pool_pre_ping=True, pool_recycle=300)

def init_db():
    SQLModel.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE thread ADD COLUMN IF NOT EXISTS contact_name VARCHAR"))
        conn.execute(text("ALTER TABLE thread ADD COLUMN IF NOT EXISTS snoozed_until TIMESTAMP"))
        conn.commit()

def get_session():
    return Session(engine)