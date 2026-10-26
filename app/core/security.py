import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
import bcrypt
import jwt
from app.core.config import settings

# Global semaphore to limit concurrent bcrypt hashing operations
_bcrypt_semaphore = asyncio.Semaphore(settings.BCRYPT_MAX_CONCURRENCY)


def validate_password_length(password: str) -> str:
    """Validates that UTF-8 encoded password does not exceed 72 bytes (bcrypt limit)."""
    if len(password.encode("utf-8")) > 72:
        raise ValueError("La contraseña no puede superar los 72 bytes")
    return password


def _hash_password_sync(password: str, rounds: int) -> str:
    pw_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=rounds)
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


async def get_password_hash(password: str) -> str:
    """Computes bcrypt hash off the event loop using asyncio.to_thread and limited by a semaphore."""
    validate_password_length(password)
    async with _bcrypt_semaphore:
        return await asyncio.to_thread(_hash_password_sync, password, settings.BCRYPT_ROUNDS)


def _verify_password_sync(plain_password: str, hashed_password: str) -> bool:
    try:
        pw_bytes = plain_password.encode("utf-8")
        h_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pw_bytes, h_bytes)
    except Exception:
        return False


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain password against hash off the event loop under semaphore protection."""
    validate_password_length(plain_password)
    async with _bcrypt_semaphore:
        return await asyncio.to_thread(_verify_password_sync, plain_password, hashed_password)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """
    Creates a signed JWT with sub, iat (float without truncation), exp, and roles.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    iat_float = now.timestamp()
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(seconds=settings.JWT_EXPIRATION_SECONDS)

    to_encode.update({
        "iat": iat_float,
        "exp": expire,
    })
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decodes and validates a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except Exception:
        return None
