from __future__ import annotations

import random
import smtplib
from email.message import EmailMessage

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings

_CODE_KEY_PREFIX = "auth:register_code:"
_COOLDOWN_KEY_PREFIX = "auth:register_cooldown:"


def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, socket_timeout=1.0, socket_connect_timeout=1.0)


def _code_key(email: str) -> str:
    return f"{_CODE_KEY_PREFIX}{email}"


def _cooldown_key(email: str) -> str:
    return f"{_COOLDOWN_KEY_PREFIX}{email}"


def _smtp_ready() -> bool:
    return bool(
        settings.SMTP_ENABLED
        and settings.SMTP_HOST
        and settings.SMTP_PORT
        and settings.SMTP_FROM_EMAIL
    )


def is_register_verification_required() -> bool:
    """Whether registration must verify an emailed code in the current env."""
    return _smtp_ready()


def send_register_code(email: str) -> None:
    if not _smtp_ready():
        raise ValueError("邮件服务未配置")
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("邮箱不能为空")

    code = f"{random.randint(0, 999999):06d}"
    ttl_seconds = max(60, settings.AUTH_REGISTER_CODE_TTL_MINUTES * 60)
    cooldown = max(1, settings.AUTH_REGISTER_CODE_RESEND_SECONDS)

    try:
        r = _redis()
        if r.exists(_cooldown_key(email)):
            raise ValueError(f"发送过于频繁，请 {cooldown} 秒后重试")
        r.setex(_code_key(email), ttl_seconds, code)
        r.setex(_cooldown_key(email), cooldown, "1")
    except RedisError as e:
        raise RuntimeError("验证码服务暂不可用") from e

    msg = EmailMessage()
    msg["Subject"] = "注册验证码"
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = email
    msg.set_content(
        f"您好，\n\n您的注册验证码是：{code}\n"
        f"{settings.AUTH_REGISTER_CODE_TTL_MINUTES} 分钟内有效。\n\n"
        "如果这不是您的操作，请忽略本邮件。\n",
        charset="utf-8",
    )

    if settings.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
        return

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(msg)


def verify_register_code(email: str, code: str) -> bool:
    email = (email or "").strip().lower()
    code = (code or "").strip()
    if not email or not code:
        return False
    try:
        r = _redis()
        raw = r.get(_code_key(email))
        if raw is None:
            return False
        expected = raw.decode("utf-8")
        if expected != code:
            return False
        r.delete(_code_key(email))
        return True
    except RedisError:
        return False
