"""题库管理：列表、AI 生成、人工编辑、审核。"""
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc
import re

from app.core.deps import AdminUser, CurrentUser, DbSession
from app.models.course import Course
from app.models.exam import Exam, ExamAttempt
from app.models.question import Question, QuestionType
from app.schemas.question import GenerateQuestionsRequest, QuestionFull, QuestionOut, QuestionReviewOut, QuestionUpdate
from app.services.question_service import GenerateSpec, generate_questions_for_course

router = APIRouter()
_MULTI_SPACE_RE = re.compile(r"\s+")


def _normalize_stem(stem: str) -> str:
    return _MULTI_SPACE_RE.sub("", (stem or "").strip().lower())


@router.get("/review-by-knowledge", response_model=list[QuestionReviewOut])
def review_questions_by_knowledge(
    db: DbSession,
    user: CurrentUser,
    knowledge_point: str = Query(..., min_length=1, max_length=400, description="薄弱知识点文案，与统计口径一致"),
):
    """学员复习：返回当前用户参考过的课程中、包含该知识点的题目（含答案与解析）。"""
    rows = (
        db.query(Exam.course_id)
        .join(ExamAttempt, ExamAttempt.exam_id == Exam.id)
        .filter(ExamAttempt.user_id == user.id)
        .distinct()
        .all()
    )
    course_ids = [r[0] for r in rows if r[0] is not None]
    if not course_ids:
        return []
    all_q = db.query(Question).filter(Question.course_id.in_(course_ids)).all()
    matched = [q for q in all_q if knowledge_point in (q.knowledge_points or [])]
    deduped: list[Question] = []
    seen: set[str] = set()
    for q in matched:
        key = _normalize_stem(q.stem)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(q)
        if len(deduped) >= 30:
            break
    return [QuestionReviewOut.model_validate(q) for q in deduped]


@router.get("", response_model=list[QuestionFull])
def list_questions(
    db: DbSession,
    admin: AdminUser,
    course_id: int | None = None,
    type: QuestionType | None = None,
):
    q = db.query(Question)
    if course_id:
        q = q.filter(Question.course_id == course_id)
    if type:
        q = q.filter(Question.type == type)
    return q.order_by(desc(Question.created_at)).limit(200).all()


@router.post("/course/{course_id}/generate", response_model=list[QuestionFull])
def generate_questions(
    course_id: int,
    payload: GenerateQuestionsRequest,
    db: DbSession,
    admin: AdminUser,
):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    try:
        questions = generate_questions_for_course(
            db,
            GenerateSpec(
                course_id=course_id,
                count=payload.count,
                type_distribution=payload.type_distribution,
                difficulty_distribution=payload.difficulty_distribution,
            ),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return questions


@router.patch("/{question_id}/review", response_model=QuestionFull)
def review_question(question_id: int, db: DbSession, admin: AdminUser):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "题目不存在")
    q.reviewed = True
    db.commit()
    db.refresh(q)
    return q


@router.patch("/{question_id}", response_model=QuestionFull)
def update_question(question_id: int, payload: QuestionUpdate, db: DbSession, admin: AdminUser):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "题目不存在")
    q.stem = payload.stem.strip()
    q.options = payload.options
    q.answer = [str(a).strip() for a in payload.answer if str(a).strip()]
    q.explanation = payload.explanation.strip() if isinstance(payload.explanation, str) and payload.explanation.strip() else None
    q.knowledge_points = [str(k).strip() for k in payload.knowledge_points if str(k).strip()]
    # 编辑后需重新审核
    q.reviewed = False
    db.commit()
    db.refresh(q)
    return q


@router.delete("/{question_id}")
def delete_question(question_id: int, db: DbSession, admin: AdminUser):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "题目不存在")
    db.delete(q)
    db.commit()
    return {"message": "已删除"}
