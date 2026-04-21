from pydantic import BaseModel, Field

from app.models.question import QuestionDifficulty, QuestionType


class QuestionOut(BaseModel):
    id: int
    course_id: int
    type: QuestionType
    difficulty: QuestionDifficulty
    stem: str
    options: list[dict] = Field(default_factory=list)
    knowledge_points: list[str] = Field(default_factory=list)
    # 学员作答时不返回 answer/explanation

    class Config:
        from_attributes = True


class QuestionFull(QuestionOut):
    """管理端看题库用，包含答案和解析。"""
    answer: list[str] = Field(default_factory=list)
    explanation: str | None = None
    source: str
    reviewed: bool


class QuestionReviewOut(QuestionOut):
    """学员按薄弱知识点复习：含答案与解析，仅供已登录学员自查。"""
    answer: list[str] = Field(default_factory=list)
    explanation: str | None = None


class GenerateQuestionsRequest(BaseModel):
    count: int = Field(default=10, ge=1, le=50)
    type_distribution: dict[str, int] | None = None
    difficulty_distribution: dict[str, int] | None = None


class QuestionUpdate(BaseModel):
    stem: str = Field(min_length=1, max_length=4000)
    options: list[dict] = Field(default_factory=list)
    answer: list[str] = Field(default_factory=list)
    explanation: str | None = None
    knowledge_points: list[str] = Field(default_factory=list)
