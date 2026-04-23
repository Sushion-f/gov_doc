from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings


engine_kwargs = {"future": True}
if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=30000;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_workspace_schema() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    columns = {
        "path": "ALTER TABLE v4_workspace_node ADD COLUMN path VARCHAR(1000)",
        "kind": "ALTER TABLE v4_workspace_node ADD COLUMN kind VARCHAR(32)",
        "size": "ALTER TABLE v4_workspace_node ADD COLUMN size INTEGER",
        "etag": "ALTER TABLE v4_workspace_node ADD COLUMN etag VARCHAR(64)",
        "title_override": "ALTER TABLE v4_workspace_node ADD COLUMN title_override VARCHAR(255)",
    }
    indexes = [
        "CREATE INDEX IF NOT EXISTS ix_v4_workspace_node_path ON v4_workspace_node (path)",
    ]
    with engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        }
        if "v4_workspace_node" not in tables:
            return
        existing = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(v4_workspace_node)")).fetchall()
        }
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(text(ddl))
        for ddl in indexes:
            conn.execute(text(ddl))


def ensure_conversation_schema() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    columns = {
        "title_locked": "ALTER TABLE v4_conversation ADD COLUMN title_locked BOOLEAN DEFAULT 0",
        "title_version": "ALTER TABLE v4_conversation ADD COLUMN title_version INTEGER DEFAULT 0",
        "title_last_summarized_at": "ALTER TABLE v4_conversation ADD COLUMN title_last_summarized_at DATETIME",
    }
    message_columns = {
        "content_blocks_json": "ALTER TABLE v4_conversation_message ADD COLUMN content_blocks_json TEXT",
        "schema_version": "ALTER TABLE v4_conversation_message ADD COLUMN schema_version INTEGER DEFAULT 2",
    }
    with engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        }
        if "v4_conversation" in tables:
            existing = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(v4_conversation)")).fetchall()
            }
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(ddl))
        if "v4_conversation_message" in tables:
            existing_msg = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(v4_conversation_message)")).fetchall()
            }
            for name, ddl in message_columns.items():
                if name not in existing_msg:
                    conn.execute(text(ddl))
