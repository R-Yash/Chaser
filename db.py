# db.py
import os
from sqlmodel import SQLModel, create_engine, Session

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    return Session(engine)