import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db, set_session_factory
from app.main import sub_app

# In-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create all tables before each test and drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Override session factory so background tasks use the test DB
    set_session_factory(TestSessionLocal)
    yield
    set_session_factory(None)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    """Provide a clean database session for direct DB tests."""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    """Async HTTP test client with DB override."""
    from httpx import AsyncClient, ASGITransport

    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session

    sub_app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=sub_app)
    async with AsyncClient(transport=transport, base_url="http://test/api") as ac:
        yield ac

    sub_app.dependency_overrides.clear()
