"""
学员对 AI 答案的满意度反馈（答案回路）。
  - rating = 1  表示好评（此答案有帮助）
  - rating = -1 表示差评（此答案不靠谱/没解决问题）

设计选择：
  - 独立建表而非塞进 LearningRecord.payload，便于管理员面板按 rating 过滤、聚合。
  - answer_id 是后端 ask 接口生成的 uuid4，客户端在消息里记住，提交反馈时带上。
  - 保存 question / answer 片段和 source chunks 快照：后端做 Prompt 优化时，
    即使该课件后续被更新，也能复现"当时为什么给了个差答案"。
"""
import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class FeedbackRating(int, enum.Enum):
    BAD = -1
    GOOD = 1


class AnswerFeedback(Base):
    __tablename__ = "answer_feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # ask 接口生成的 uuid，用于「一次答案」的唯一定位。同一条 answer 若被多次点赞/差评，取最新一次。
    answer_id: Mapped[str] = mapped_column(String(40), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True, index=True)
    rating: Mapped[int] = mapped_column(SmallInteger, index=True)  # 1 / -1
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 快照：{"question":"...", "answer":"...", "sources":[{index,chunk_id,chapter,snippet},...], "response_style":"..."}
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
