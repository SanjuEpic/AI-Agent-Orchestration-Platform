import os
from sqlmodel import SQLModel, create_engine, Session

# SQLite file is saved locally in the backend directory or project root
DATABASE_FILE = "orchestrator.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

# SQLite check_same_thread=False is needed because FastAPI and LangGraph
# run across multiple asynchronous threads.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    echo=False
)

def init_db():
    """Create all database tables defined in SQLModel metadata."""
    SQLModel.metadata.create_all(engine)
    # Enable WAL mode for concurrency
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
    _run_schema_migrations()


def _run_schema_migrations():
    """Lightweight additive migrations for columns added after a DB already exists.

    create_all() only creates missing tables, never adds columns to existing ones,
    so new columns on existing tables must be ALTERed in here.
    """
    with engine.connect() as conn:
        # Schedule.chat_id — Telegram destination for scheduled (non-reply) runs
        cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(schedule);")]
        if "chat_id" not in cols:
            conn.exec_driver_sql("ALTER TABLE schedule ADD COLUMN chat_id VARCHAR;")
            print("[Migration] Added 'chat_id' column to schedule table.")

def get_session():
    """Dependency generator yielding active DB sessions."""
    with Session(engine) as session:
        yield session
