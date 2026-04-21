"""
学习行为记录：用于生成数据看板（学习时长、完成率、薄弱知识点等）。
"""
import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.pg_enum import pg_enum


class LearningAction(str, enum.Enum):
    VIEW_COURSE = "view_course"
    READ_CHUNK = "read_chunk"
    ASK_QUESTION = "ask_question"      # 与 AI 对话
    COMPLETE_CHAPTER = "complete_chapter"
    START_EXAM = "start_exam"
    SUBMIT_EXAM = "submit_exam"
    PRACTICE = "practice"              # 练习模式
    REVIEW_KP_PERFECT = "review_kp_perfect"  # 薄弱知识点自测本轮全对（用于掌握度）


class LearningRecord(Base):
    __tablename__ = "learning_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True, index=True)
    action: Mapped[LearningAction] = mapped_column(pg_enum(LearningAction, "learningaction"), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    # 例如 {"chunk_id": 12, "question": "...", "duration_sec": 45}
    duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
