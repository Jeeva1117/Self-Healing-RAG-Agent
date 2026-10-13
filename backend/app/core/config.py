"""Core configuration module using Pydantic Settings.

Manages application environment variables, connection strings,
security keys, and integration settings with strict type validation.
"""

from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application Information
    APP_ENV: Literal["development", "staging", "production", "test"] = Field(
        default="development",
        validation_alias="APP_ENV",
        description="Application runtime environment mode",
    )
    ENVIRONMENT: str | None = Field(
        default=None,
        description="Optional alias for APP_ENV",
    )
    DEMO_LOGIN_ENABLED: bool = Field(
        default=False,
        validation_alias="DEMO_LOGIN_ENABLED",
        description="Enable development-only quick demo user login (MUST be False in production)",
    )

    @property
    def effective_environment(self) -> str:
        """Resolves active environment giving precedence to ENVIRONMENT then APP_ENV."""
        if self.ENVIRONMENT:
            return self.ENVIRONMENT.lower()
        return self.APP_ENV.lower()

    @property
    def is_demo_login_allowed(self) -> bool:
        """Returns True strictly when explicitly enabled AND running in development or test environment."""
        return self.DEMO_LOGIN_ENABLED and self.effective_environment in ("development", "test")

    APP_NAME: str = "self-healing-rag-agent"
    APP_VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # Database Configuration (PostgreSQL + asyncpg)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/self_healing_rag",
        description="Async PostgreSQL connection string",
    )
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: float = 30.0

    # Redis Configuration
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for caching, sessions, and state",
    )
    REDIS_ENABLED: bool = True
    REDIS_SOCKET_TIMEOUT: float = 5.0
    REDIS_MAX_CONNECTIONS: int = 20

    # Security & Authentication (Phase 3)
    JWT_SECRET: str = Field(
        default="phase1-production-foundation-insecure-secret-key-change-me",
        validation_alias="JWT_SECRET",
        description="Cryptographic secret key for signing JWT tokens",
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    COOKIE_NAME_REFRESH: str = "refresh_token"
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_MAX_LENGTH: int = 128

    # CORS Configuration
    CORS_ORIGINS: list[str] | str = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]

    @model_validator(mode="after")
    def validate_security_invariants(self) -> "Settings":
        env = self.effective_environment
        insecure_secrets = {
            "phase1-production-foundation-insecure-secret-key-change-me",
            "secret",
            "changeme",
            "default",
            "password",
        }
        if env == "production":
            if not self.JWT_SECRET or self.JWT_SECRET.lower() in insecure_secrets or len(self.JWT_SECRET) < 32:
                raise ValueError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: JWT_SECRET must be configured with a "
                    "cryptographically secure string (minimum 32 characters) in production environment mode."
                )
            if not self.COOKIE_SECURE:
                # Enforce secure cookies automatically in production
                self.COOKIE_SECURE = True
        elif env == "staging" and not self.COOKIE_SECURE:
            self.COOKIE_SECURE = True
        return self

    # Document Ingestion & Storage Configuration (Phase 4)
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_DOCUMENT_TYPES: list[str] = ["pdf", "docx", "txt", "md", "csv", "html", "htm", "json", "xlsx"]
    CHUNK_SIZE: int = 500  # Token count per chunk
    CHUNK_OVERLAP: int = 50  # Overlap token count
    STORAGE_PROVIDER: Literal["local", "s3", "minio"] = "local"
    STORAGE_LOCAL_PATH: str = "data/storage"
    INGESTION_MAX_RETRIES: int = 3

    # Embedding Provider Configuration (Phase 4)
    EMBEDDING_PROVIDER: str = "fastembed"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_BATCH_SIZE: int = 32

    # Retrieval & Reranking Configuration (Phase 5)
    RETRIEVAL_DEFAULT_MODE: str = "hybrid"  # "vector", "lexical", "hybrid"
    RETRIEVAL_CANDIDATE_LIMIT: int = 20
    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_SIMILARITY_THRESHOLD: float = 0.0
    RETRIEVAL_RRF_K: int = 60  # Reciprocal Rank Fusion constant
    RETRIEVAL_ENABLE_RERANKING: bool = True
    RERANKER_PROVIDER: str = "flashrank"  # "flashrank" or "mock"
    RERANKER_MODEL: str = "ms-marco-TinyBERT-L-2-v2"  # Fast ONNX cross-encoder
    RERANKER_MAX_CANDIDATES: int = 20

    # Generation & LLM Providers (Phase 6 & Groq Integration)
    LLM_PROVIDER: str = "groq"  # "groq", "openai", or "synthesis"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    LLM_BASE_URL: str = ""
    LLM_TEMPERATURE: float = 0.0  # Deterministic generation for grounded RAG
    LLM_TIMEOUT_SECONDS: float = 30.0
    LLM_MAX_CONTEXT_TOKENS: int = 4000
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    OBJECT_STORAGE_ENDPOINT: str = ""
    OBJECT_STORAGE_BUCKET: str = "self-healing-rag"
    OBJECT_STORAGE_ACCESS_KEY: str = ""
    OBJECT_STORAGE_SECRET_KEY: str = ""

    # Self-Healing Recovery Engine Configuration (Phase 8)
    RECOVERY_MAX_ATTEMPTS: int = 2
    RECOVERY_TIMEOUT_SECONDS: float = 45.0
    RECOVERY_PROVIDER_MAX_RETRIES: int = 2
    RECOVERY_EXPANSION_CANDIDATE_LIMIT: int = 35
    RECOVERY_BACKOFF_FACTOR: float = 0.5
    RECOVERY_MAX_GENERATION_ATTEMPTS: int = 2


# Global singleton instance
settings = Settings()
