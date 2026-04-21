"""
FastAPI 依赖注入：当前用户、权限校验。
"""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    token: str | None = Depends(oauth2_scheme),
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub", "0"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效")

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def role_dependency(*roles: UserRole):
    """返回一个 FastAPI 依赖：只允许指定角色（admin 永远可通行）。"""
    allowed = set(roles)

    def _inner(user: CurrentUser) -> User:
        if user.role == UserRole.ADMIN:
            return user
        if user.role not in allowed:
            role_names = " / ".join(r.value for r in roles) or "指定角色"
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要以下角色之一：{role_names}",
            )
        return user

    return _inner


def require_editorial(user: CurrentUser) -> User:
    return role_dependency(
        UserRole.EDITOR,
        UserRole.REVIEWER,
        UserRole.PUBLISHER,
        UserRole.MANAGER,
    )(user)


EditorialUser = Annotated[User, Depends(require_editorial)]
EditorUser = Annotated[User, Depends(role_dependency(UserRole.EDITOR))]
ReviewerUser = Annotated[User, Depends(role_dependency(UserRole.REVIEWER))]
PublisherUser = Annotated[User, Depends(role_dependency(UserRole.PUBLISHER))]
