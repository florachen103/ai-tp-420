"""
课件解析：下载 → 解析 → 切块向量化入库。
供 Celery 任务与后台线程共用；上传后默认用后台线程触发，避免仅依赖 Celery worker 时任务一直 pending。
"""
from __future__ import annotations

import os
import tempfile

from loguru import logger
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.course import Course, CourseMaterial, CourseStatus
from app.services.knowledge_service import create_draft_from_material
from app.services.parser import parse_file
from app.services.rag import index_document
from app.services.storage import get_storage


def _empty_text_hint(doc_meta: dict) -> str:
    """根据解析器诊断信息，给出针对性的失败建议。"""
    # PDF 专用反馈
    if "text_pages" in doc_meta or "ocr_fallback_used" in doc_meta:
        if not doc_meta.get("ocr_deps_available", True):
            return (
                "该 PDF 没有文字层（常见于 Mac 截图导出 PDF、扫描件），必须 OCR 才能抽文本；"
                "但后端未安装 OCR 依赖。请执行：\n"
                "  docker compose build --no-cache backend worker && docker compose up -d backend worker"
            )
        if doc_meta.get("ocr_fallback_used") and doc_meta.get("ocr_pages_got_text", 0) == 0:
            return (
                "已对 PDF 执行 OCR，但未识别到有效文字（可能是图片过小/分辨率过低/语言不匹配）。"
                "建议：①把截图导出为更大分辨率后再合并为 PDF；"
                "②或直接把原始课件（可复制文本的 PDF/Word/PPT）上传。"
            )
        if doc_meta.get("text_pages", 0) == 0:
            return (
                "PDF 中未提取到可用文本。请先对文件做 OCR 或改用可复制文本的课件后重新上传。"
            )
    return "未提取到可用文本，无法生成知识切片。请改用包含可复制文本的课件后重新上传。"


def _save_parse_progress(db: Session, material_id: int, pct: int, stage: str) -> None:
    m = db.get(CourseMaterial, material_id)
    if not m:
        return
    meta = dict(m.meta or {})
    meta["parse_progress"] = min(100, max(0, int(pct)))
    meta["parse_stage"] = stage
    m.meta = meta
    db.commit()


def parse_material_job(material_id: int) -> None:
    """同步执行完整解析流程（在独立线程中调用，勿阻塞 HTTP 主线程外的逻辑自行管理 Session）。"""
    db = SessionLocal()
    tmp_path: str | None = None
    try:
        material: CourseMaterial | None = db.get(CourseMaterial, material_id)
        if not material:
            logger.warning(f"material {material_id} not found")
            return

        material.parse_status = "parsing"
        db.commit()
        _save_parse_progress(db, material_id, 4, "已接手解析任务")

        storage = get_storage()
        suffix = os.path.splitext(material.filename)[1]
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        storage.download_to(material.storage_key, tmp_path)
        _save_parse_progress(db, material_id, 16, "文件已下载")

        doc = parse_file(tmp_path, material.filename)
        _save_parse_progress(db, material_id, 28, "正文提取完成")

        # 把解析器诊断信息提前写进 meta，便于前端/日志排查
        if doc.meta:
            material.meta = {**(material.meta or {}), "parse_doc_meta": doc.meta}
            db.commit()

        mid = material.id

        def _hook(pct: int, stage: str) -> None:
            _save_parse_progress(db, mid, pct, stage)

        chunks_count = index_document(
            db,
            course_id=material.course_id,
            material=material,
            doc=doc,
            progress_hook=_hook,
        )

        # 解析成功但未得到任何有效切片时，视为失败——根据上游诊断信息给出具体建议
        if chunks_count <= 0:
            raise ValueError(_empty_text_hint(doc.meta or {}))

        material.parse_status = "parsed"
        material.parse_error = None
        material.meta = {
            **(material.meta or {}),
            "chunks": chunks_count,
            "sections": len(doc.sections),
            "parse_progress": 100,
            "parse_stage": "解析完成",
        }

        course: Course | None = db.get(Course, material.course_id)
        if course:
            kd, kr = create_draft_from_material(
                db,
                course=course,
                material=material,
                doc=doc,
                actor_id=course.created_by,
            )
            material.meta = {
                **(material.meta or {}),
                "knowledge_document_id": kd.id,
                "knowledge_revision_id": kr.id,
            }
        if course and course.status == CourseStatus.DRAFT and chunks_count > 0:
            course.status = CourseStatus.READY

        db.commit()
        logger.info(f"material {material_id} parsed: {chunks_count} chunks")
    except Exception as e:
        logger.exception(f"parse material {material_id} failed: {e}")
        material = db.get(CourseMaterial, material_id)
        if material:
            material.parse_status = "failed"
            material.parse_error = str(e)[:1000]
            meta = dict(material.meta or {})
            meta["parse_progress"] = 0
            meta["parse_stage"] = "解析失败"
            material.meta = meta
            db.commit()
    finally:
        db.close()
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def schedule_parse_material(material_id: int) -> None:
    """启动后台线程解析（不阻塞 HTTP 响应）。"""
    import threading

    t = threading.Thread(
        target=parse_material_job,
        args=(material_id,),
        daemon=True,
        name=f"parse-material-{material_id}",
    )
    t.start()
