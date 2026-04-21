from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.exam import ExamAttempt, ExamStatus
from app.schemas.question import QuestionOut


class ExamCreate(BaseModel):
    course_id: int
    title: str
    description: str | None = None
    duration_minutes: int = Field(default=5, ge=1, le=300)
    pass_score: float = Field(default=80.0, ge=0, le=100)
    rules: dict = Field(
        default_factory=lambda: {
            "single": {"count": 10, "score": 5},
            "judge": {"count": 5, "score": 2},
            "short": {"count": 2, "score": 20},
        }
    )
    shuffle_questions: bool = True
    shuffle_options: bool = True


class ExamOut(BaseModel):
    id: int
    course_id: int
    title: str
    description: str | None = None
    duration_minutes: int
    pass_score: float
    rules: dict
    created_at: datetime

    class Config:
        from_attributes = True


class AttemptOut(BaseModel):
    id: int
    exam_id: int
    user_id: int
    status: ExamStatus
    score: float | None = None
    max_score: float
    started_at: datetime
    submitted_at: datetime | None = None
    graded_at: datetime | None = None
    """本次抽题数量（进行中时用于展示「共 N 题」等）。"""
    question_count: int = 0

    @model_validator(mode="before")
    @classmethod
    def _from_attempt_orm(cls, data: Any) -> Any:
        if isinstance(data, ExamAttempt):
            return {
                "id": data.id,
                "exam_id": data.exam_id,
                "user_id": data.user_id,
                "status": data.status,
                "score": data.score,
                "max_score": data.max_score,
                "started_at": data.started_at,
                "submitted_at": data.submitted_at,
                "graded_at": data.graded_at,
                "question_count": len(data.question_ids or []),
            }
        return data

    class Config:
        from_attributes = True


class AttemptStartResponse(BaseModel):
    attempt: AttemptOut
    questions: list[QuestionOut]


class SubmitAnswerItem(BaseModel):
    question_id: int
    answer: list[str]
    time_spent_sec: int = 0


class SubmitAttemptRequest(BaseModel):
    answers: list[SubmitAnswerItem]
    proctor_events: list[dict] = Field(default_factory=list)


class AnswerDetail(BaseModel):
    question_id: int
    stem: str
    type: str
    user_answer: list[str]
    correct_answer: list[str]
    is_correct: bool | None
    score: float
    ai_feedback: str | None = None
    explanation: str | None = None


class AttemptResult(BaseModel):
    attempt: AttemptOut
    passed: bool
    details: list[AnswerDetail]
