"""
认证与安全：密码哈希、JWT 签发与校验。

说明：passlib 与 bcrypt 4.1+ 存在兼容性问题（注册时可能 500）。
这里直接使用 bcrypt 官方库，避免 passlib 维护停滞带来的崩溃。
"""
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(raw: str) -> str:
    raw_b = raw.encode("utf-8")
    if len(raw_b) > 72:
        raw_b = raw_b[:72]
    return bcrypt.hashpw(raw_b, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str | int, extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.APP_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.APP_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as e:
        raise ValueError("invalid token") from e
