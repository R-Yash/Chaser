import os
from dotenv import load_dotenv
from sqlmodel import SQLModel, create_engine, Session
load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"), connect_args={"check_same_thread": False} )

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    return Session(engine)