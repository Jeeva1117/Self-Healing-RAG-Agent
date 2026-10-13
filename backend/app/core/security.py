"""Security module for password hashing, token management, and cryptographic abstractions.

Uses Argon2id for secure modern password hashing and PyJWT for signed access tokens.
Refresh tokens use cryptographically secure high-entropy random bytes hashed with SHA-256
prior to database persistence.
"""

import hashlib
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings
from app.core.errors import UnauthorizedError, ValidationError

# Initialize Argon2id password hasher with secure production parameters
_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MB
    parallelism=1,
    hash_len=32,
)

# Password validation policy regex: requires at least one letter and at least one digit
_LETTER_PATTERN = re.compile(r"[A-Za-z]")
_DIGIT_PATTERN = re.compile(r"\d")


def hash_password(password: str) -> str:
    """Hashes a plaintext password using Argon2id."""
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Safely verifies a plaintext password against an Argon2id hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception:
        return False


def validate_password_strength(password: str) -> None:
    """Validates that a password satisfies the production complexity policy."""
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        raise ValidationError(
            f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long",
            code="WEAK_PASSWORD",
        )
    if len(password) > settings.PASSWORD_MAX_LENGTH:
        raise ValidationError(
            f"Password must not exceed {settings.PASSWORD_MAX_LENGTH} characters",
            code="PASSWORD_TOO_LONG",
        )
    if not _LETTER_PATTERN.search(password):
        raise ValidationError(
            "Password must contain at least one letter",
            code="WEAK_PASSWORD",
        )
    if not _DIGIT_PATTERN.search(password):
        raise ValidationError(
            "Password must contain at least one number",
            code="WEAK_PASSWORD",
        )


def hash_token(token: str) -> str:
    """Computes a SHA-256 hash of a refresh token for secure database storage and indexing."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_secure_token(nbytes: int = 48) -> str:
    """Generates a cryptographically strong URL-safe random string."""
    return secrets.token_urlsafe(nbytes)


def create_access_token(
    user_id: str | uuid.UUID,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Creates a short-lived signed JWT access token with minimal claims."""
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_access_token(token: str) -> dict[str, Any]:
    """Validates signature and claims of an access token."""
    if not token:
        raise UnauthorizedError("Missing authentication token", code="TOKEN_MISSING")

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "exp", "type"]},
        )
        if payload.get("type") != "access":
            raise UnauthorizedError("Invalid token type", code="INVALID_TOKEN_TYPE")
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Access token has expired", code="TOKEN_EXPIRED") from None
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid or corrupted authentication token", code="INVALID_TOKEN") from None
