from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, DbSession
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    SendRegisterCodeRequest,
    TokenResponse,
    UserOut,
)
from app.services.auth_email import send_register_code, verify_register_code

router = APIRouter()


@router.post("/register", response_model=UserOut)
def register(payload: RegisterRequest, db: DbSession):
    email = payload.email.lower().strip()
    if not verify_register_code(email, payload.verification_code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="邮箱已注册")

    is_first = db.query(User).count() == 0
    user = User(
        email=email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        department=payload.department,
        role=UserRole.ADMIN if is_first else UserRole.LEARNER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession):
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")
    token = create_access_token(user.id, extra_claims={"role": user.role.value})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@router.post("/send-register-code")
def send_code(payload: SendRegisterCodeRequest):
    try:
        send_register_code(payload.email.lower().strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="邮件发送失败，请稍后重试") from e
    return {"message": "验证码已发送"}
