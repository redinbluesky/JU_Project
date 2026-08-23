from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

DB_PATH = "runtime/db/ju-project.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """foreign_keys 활성화, journal_mode=WAL (동시 읽기 개선)"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, expire_on_commit=False)
