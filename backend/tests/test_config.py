"""Configuration and environment variable tests."""

from app.core.config import Settings


def test_settings_defaults():
    s = Settings(
        APP_NAME="test-service",
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/testdb",
        CORS_ORIGINS=["http://localhost:3000"],
    )
    assert s.APP_NAME == "test-service"
    assert "postgresql+asyncpg" in s.DATABASE_URL
    assert "http://localhost:3000" in s.CORS_ORIGINS


def test_cors_origins_string_parsing():
    s = Settings(
        CORS_ORIGINS="http://localhost:3000, http://localhost:5173",
    )
    assert isinstance(s.CORS_ORIGINS, list)
    assert "http://localhost:3000" in s.CORS_ORIGINS
    assert "http://localhost:5173" in s.CORS_ORIGINS
