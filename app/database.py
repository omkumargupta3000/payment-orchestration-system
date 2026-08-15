"""
Database setup for the payment orchestrator.

Using SQLite because this is a demo/student project - no separate DB server
needed, and it's easy for anyone to clone the repo and run it immediately.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# allow overriding via env var in case someone wants to point it somewhere else,
# but default to a local sqlite file
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./payments.db")

# check_same_thread is needed only for sqlite since FastAPI can use the
# same session across different threads
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
