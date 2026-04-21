"""
题库：AI 生成的题目 + 人工题目都入这张表，用 source 区分。
"""
import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.pg_enum import pg_enum


class QuestionType(str, enum.Enum):
    SINGLE = "single"          # 单选
    MULTIPLE = "multiple"      # 多选
    JUDGE = "judge"            # 判断
    FILL = "fill"              # 填空
    SHORT = "short"            # 简答（主观题，需 AI 判分）


class QuestionDifficulty(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("chunks.id"), nullable=True)
    # 记录题目来源于哪个知识切片，便于溯源
    type: Mapped[QuestionType] = mapped_column(pg_enum(QuestionType, "questiontype"), index=True)
    difficulty: Mapped[QuestionDifficulty] = mapped_column(
        pg_enum(QuestionDifficulty, "questiondifficulty"),
        default=QuestionDifficulty.MEDIUM,
        index=True,
    )
    stem: Mapped[str] = mapped_column(Text)  # 题干
    options: Mapped[list[dict]] = mapped_column(JSON, default=list)
    # 选择题: [{"key": "A", "text": "..."}, ...]；判断题/简答留空
    answer: Mapped[list[str]] = mapped_column(JSON, default=list)
    # 单选/判断: ["A"] / ["true"]；多选: ["A", "C"]；填空/简答: ["参考答案"]
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    knowledge_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(30), default="ai")  # ai | human
    reviewed: Mapped[bool] = mapped_column(default=False)  # 是否人工审核通过
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
