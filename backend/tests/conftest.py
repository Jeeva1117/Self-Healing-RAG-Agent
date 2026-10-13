"""Pytest test configuration, fixtures, and database dependency overrides."""

import os
import shutil
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Set test environment
os.environ["APP_ENV"] = "test"
os.environ["LOG_LEVEL"] = "ERROR"
os.environ["EMBEDDING_PROVIDER"] = "mock"
os.environ["STORAGE_LOCAL_PATH"] = "data/test_storage"

import app.api.routes.documents as doc_routes_module  # noqa: E402
import app.api.routes.knowledge_bases as kb_routes_module  # noqa: E402
import app.infrastructure.database.session as db_session_module  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.infrastructure.database.base import Base  # noqa: E402
from app.infrastructure.database.models import (  # noqa: F401, E402
    AuditLog,
    Document,
    DocumentChunk,
    DocumentVersion,
    KnowledgeBase,
    User,
    UserRole,
    UserSession,
)
from app.main import app  # noqa: E402

# Test SQLite Engine for hermetic asynchronous integration testing
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Patch session factory for background tasks
db_session_module.AsyncSessionLocal = TestSessionLocal
kb_routes_module.AsyncSessionLocal = TestSessionLocal
doc_routes_module.AsyncSessionLocal = TestSessionLocal


@pytest.fixture(autouse=True)
async def setup_test_database():
    """Initializes tables before each test and cleans up after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    # Clean test storage directory if present
    if os.path.exists("data/test_storage"):
        shutil.rmtree("data/test_storage", ignore_errors=True)


async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides test database session."""
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[db_session_module.get_db_session] = override_get_db_session


@pytest.fixture
async def client():
    """Provides an async HTTP client for integration testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def user_a(db_session: AsyncSession) -> User:
    """Creates primary test user (User A)."""
    user = User(
        email="alice@test.local",
        name="Alice",
        password_hash="mockhash",
        role=UserRole.USER.value,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def user_b(db_session: AsyncSession) -> User:
    """Creates secondary test user (User B) for authorization tests."""
    user = User(
        email="bob@test.local",
        name="Bob",
        password_hash="mockhash",
        role=UserRole.USER.value,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers_user_a(user_a: User) -> dict[str, str]:
    token = create_access_token(user_id=user_a.id, role=user_a.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user_b(user_b: User) -> dict[str, str]:
    token = create_access_token(user_id=user_b.id, role=user_b.role)
    return {"Authorization": f"Bearer {token}"}

