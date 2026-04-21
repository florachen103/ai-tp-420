from datetime import datetime

from pydantic import BaseModel, Field

from app.models.record import LearningAction


class ReviewKpPerfectRequest(BaseModel):
    """薄弱知识点复习：本轮自测全部答对时上报，用于掌握度统计。"""
    knowledge_point: str = Field(..., min_length=1, max_length=400)
    question_count: int = Field(..., ge=1, le=100)


class RecordOut(BaseModel):
    id: int
    user_id: int
    course_id: int | None
    action: LearningAction
    payload: dict = Field(default_factory=dict)
    duration_sec: int
    created_at: datetime

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    total_learning_minutes: int
    courses_viewed: int
    exams_taken: int
    exams_passed: int
    average_score: float | None
    recent_records: list[RecordOut]
    weak_knowledge_points: list[dict] = Field(default_factory=list)
    # [{"point": "产品A定价", "wrong_rate": 0.7, "attempts": 10}, ...]
