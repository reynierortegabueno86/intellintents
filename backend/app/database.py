from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "sqlite+aiosqlite:///./intellintents.db"

engine = create_async_engine(DATABASE_URL, echo=False)


# Enable SQLite foreign key enforcement (OFF by default)
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Overridable session factory for background tasks.
# Tests can replace this to point at the in-memory DB.
_session_factory = None


def get_session_factory() -> async_sessionmaker:
    """Return the active session factory (overridable for tests)."""
    return _session_factory or async_session


def set_session_factory(factory: async_sessionmaker) -> None:
    """Override the session factory (used by tests)."""
    global _session_factory
    _session_factory = factory


class Base(DeclarativeBase):
    pass


async def get_db():
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()
