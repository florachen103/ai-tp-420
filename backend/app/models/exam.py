"""
考试体系：
  Exam          ：考卷模板（管理员配置：从哪些课程/题型/难度抽多少题，及格分，时长）
  ExamAttempt   ：学员的一次作答（快照：当时抽到的题 ID 列表 + 状态 + 总分）
  ExamAnswer    ：学员对每道题的作答结果（原始答案 + 是否正确 + AI 评语）
"""
import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.pg_enum import pg_enum


class ExamStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    GRADED = "graded"
    EXPIRED = "expired"


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    pass_score: Mapped[float] = mapped_column(Float, default=60.0)
    # rules: 抽题规则，例如
    # { "single": {"count": 10, "score": 2}, "judge": {"count": 5, "score": 1},
    #   "short":  {"count": 2,  "score": 10} }
    rules: Mapped[dict] = mapped_column(JSON, default=dict)
    shuffle_questions: Mapped[bool] = mapped_column(default=True)
    shuffle_options: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    attempts: Mapped[list["ExamAttempt"]] = relationship(back_populates="exam")


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # 抽到的题目快照，避免后续题库变动导致成绩不一致
    question_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    status: Mapped[ExamStatus] = mapped_column(
        pg_enum(ExamStatus, "examstatus"), default=ExamStatus.IN_PROGRESS, index=True
    )
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float] = mapped_column(Float, default=100.0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 作弊监测：记录切屏次数、作答耗时异常等
    proctor_events: Mapped[list[dict]] = mapped_column(JSON, default=list)

    exam: Mapped["Exam"] = relationship(back_populates="attempts")
    answers: Mapped[list["ExamAnswer"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class ExamAnswer(Base):
    __tablename__ = "exam_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("exam_attempts.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    answer: Mapped[list[str]] = mapped_column(JSON, default=list)
    # 学员作答：单选 ["B"]；多选 ["A","C"]；简答 ["自由文本"]
    is_correct: Mapped[bool | None] = mapped_column(nullable=True)  # 简答题判分前为 None
    score: Mapped[float] = mapped_column(Float, default=0.0)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)  # AI 对主观题的评语
    time_spent_sec: Mapped[int] = mapped_column(Integer, default=0)

    attempt: Mapped["ExamAttempt"] = relationship(back_populates="answers")
