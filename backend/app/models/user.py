"""
用户与组织：MVP 先做单租户 + 部门/角色，SaaS 扩展时再拆 tenant。
"""
import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.pg_enum import pg_enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"        # 平台管理员：上传课件、管理题库、看全公司数据
    MANAGER = "manager"    # 部门经理：看部门数据、指派课程
    EDITOR = "editor"      # 知识编辑：整理草稿、维护知识页正文
    REVIEWER = "reviewer"  # 审核人：负责事实核验、驳回修改
    PUBLISHER = "publisher"  # 发布人：控制最终发布与回滚
    LEARNER = "learner"    # 普通学员


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "userrole"), default=UserRole.LEARNER)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
