from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken  # pyright: ignore[reportMissingImports]
from jose import JWTError, jwt  # pyright: ignore[reportMissingModuleSource]

from .config import get_settings


def _get_settings():
    return get_settings()


def _get_fernet() -> Fernet:
    settings = _get_settings()
    return Fernet(settings.field_encryption_key.encode())


class AuthError(ValueError):
    pass


def encrypt_secret(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _get_fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return None


def validate_origin(origin: str | None, allowed_origins: list[str]) -> str:
    if not origin:
        raise AuthError('Missing Origin header')
    normalized = origin.rstrip('/')
    if normalized not in {candidate.rstrip('/') for candidate in allowed_origins}:
        raise AuthError('Origin is not allowed for this site')
    return normalized


def create_session_jwt(*, session_id: str, site_id: str, origin: str, ttl_seconds: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        'sub': session_id,
        'site_id': site_id,
        'origin': origin,
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, _get_settings().jwt_secret, algorithm='HS256')


def verify_session_jwt(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, _get_settings().jwt_secret, algorithms=['HS256'])
    except JWTError as exc:
        raise AuthError('Invalid or expired session token') from exc
