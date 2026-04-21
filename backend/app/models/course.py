"""
课件体系：
  Course (课程) ─┬─ CourseMaterial (原始课件文件: Word/PDF/PPT/Excel/音视频)
                 └─ Chunk (从课件中解析+切分出来的知识切片，带向量，供 RAG 检索)

Chunk 向量用 pgvector 存储，查询时用 <=> 操作符做余弦相似度。
"""
import enum
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.config import settings
from app.core.database import Base
from app.core.pg_enum import pg_enum


class CourseStatus(str, enum.Enum):
    DRAFT = "draft"            # 草稿
    PROCESSING = "processing"  # 正在解析
    READY = "ready"            # 已就绪，学员可学
    ARCHIVED = "archived"


class MaterialType(str, enum.Enum):
    WORD = "word"
    PDF = "pdf"
    PPT = "ppt"
    EXCEL = "excel"
    VIDEO = "video"
    AUDIO = "audio"
    MARKDOWN = "markdown"
    OTHER = "other"


class ChunkSourceType(str, enum.Enum):
    COURSE_MATERIAL = "course_material"
    KNOWLEDGE_REVISION = "knowledge_revision"


class ChunkVisibility(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    knowledge_space_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_spaces.id"), nullable=True, index=True
    )
    status: Mapped[CourseStatus] = mapped_column(
        pg_enum(CourseStatus, "coursestatus"), default=CourseStatus.DRAFT, index=True
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    materials: Mapped[list["CourseMaterial"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )


class CourseMaterial(Base):
    """一个课程可以包含多份原始课件文件。"""
    __tablename__ = "course_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    filename: Mapped[str] = mapped_column(String(500))
    material_type: Mapped[MaterialType] = mapped_column(pg_enum(MaterialType, "materialtype"))
    storage_key: Mapped[str] = mapped_column(String(1000))  # 对象存储中的 key
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    parse_status: Mapped[str] = mapped_column(String(30), default="pending")
    # pending | parsing | parsed | failed
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)  # 作者、页数、时长等
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    course: Mapped["Course"] = relationship(back_populates="materials")


class Chunk(Base):
    """
    RAG 的核心单元：从课件中切分出的一段文本 + 其向量。
    检索时按 embedding 找最相近的 Chunk，再把原文喂给 LLM。
    """
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True, index=True)
    material_id: Mapped[int | None] = mapped_column(
        ForeignKey("course_materials.id"), nullable=True, index=True
    )
    knowledge_space_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_spaces.id"), nullable=True, index=True
    )
    knowledge_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_documents.id"), nullable=True, index=True
    )
    knowledge_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_revisions.id"), nullable=True, index=True
    )
    source_type: Mapped[ChunkSourceType] = mapped_column(
        pg_enum(ChunkSourceType, "chunksourcetype"),
        default=ChunkSourceType.COURSE_MATERIAL,
        index=True,
    )
    visibility: Mapped[ChunkVisibility] = mapped_column(
        pg_enum(ChunkVisibility, "chunkvisibility"),
        default=ChunkVisibility.PUBLISHED,
        index=True,
    )
    chapter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 课件中的段落顺序，用于拼接上下文
    order_idx: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.EMBEDDING_DIM), nullable=True
    )
    meta: Mapped[dict] = mapped_column(JSON, default=dict)  # 页码、来源文件名等
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    course: Mapped["Course"] = relationship(back_populates="chunks")

    __table_args__ = (
        # HNSW 索引用于快速向量检索；pgvector 0.5+ 支持
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
