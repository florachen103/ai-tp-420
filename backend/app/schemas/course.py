from datetime import datetime

from typing import Literal

from pydantic import BaseModel, Field

from app.models.course import CourseStatus, MaterialType


class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)


class CourseUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    status: CourseStatus | None = None


class MaterialOut(BaseModel):
    id: int
    filename: str
    material_type: MaterialType
    parse_status: str
    parse_error: str | None = None
    size_bytes: int
    meta: dict = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


class CourseOut(BaseModel):
    id: int
    title: str
    description: str | None = None
    cover_url: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    knowledge_space_id: int | None = None
    status: CourseStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CourseDetail(CourseOut):
    materials: list[MaterialOut] = Field(default_factory=list)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    persona: str | None = None  # 顾客画像描述，可为空
    top_k: int = Field(default=5, ge=1, le=20)
    # micro：短场景小口粮（默认）；standard：条理适中；deep：可较长展开
    response_style: Literal["micro", "standard", "deep"] = "micro"
    # 检索范围限定：只在指定课件里找；为空 = 全课程
    material_ids: list[int] | None = None
    # 检索范围限定：只在某一章节内找；None = 不限
    chapter: str | None = None
    # 是否启用查询改写（把口语问题扩成多条检索变体）。默认开启；调试可以关。
    rewrite: bool = True
    # 是否启用 LLM 重排：会额外花一次 LLM 调用。默认关闭，管理端/高要求场景再打开。
    rerank: bool = False


class AskResponse(BaseModel):
    answer: str
    # 后端生成的 uuid，用于学员之后对这次答案点赞 / 点踩。命中缓存时会复用同一个 id。
    answer_id: str
    sources: list[dict]  # [{"index":1,"chunk_id":..,"chapter":..,"score":..,"snippet":..,"citations":N}]
    # 本次实际用于检索的查询变体（原问题 + 改写；含 rewrite 关闭时只有原问题），便于前端调试展示
    queries_used: list[str] = Field(default_factory=list)


class AnswerFeedbackIn(BaseModel):
    """学员对某次 AI 答案的满意度反馈。"""
    answer_id: str = Field(min_length=1, max_length=40)
    rating: Literal[-1, 1]  # -1 差评，1 好评
    comment: str | None = Field(default=None, max_length=1000)
