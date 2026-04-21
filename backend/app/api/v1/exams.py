"""考试：管理员建考卷；学员开始作答 → 提交 → 查结果。"""
from fastapi import APIRouter, HTTPException
from sqlalchemy import desc

from app.core.deps import AdminUser, CurrentUser, DbSession
from app.models.exam import Exam, ExamAnswer, ExamAttempt, ExamStatus
from app.models.question import Question
from app.schemas.exam import (
    AnswerDetail,
    AttemptOut,
    AttemptResult,
    AttemptStartResponse,
    ExamCreate,
    ExamOut,
    SubmitAttemptRequest,
)
from app.schemas.question import QuestionOut
from app.services.exam_service import ExamError, start_attempt, submit_attempt

router = APIRouter()


def _normalize_legacy_exam_defaults(db: DbSession, exams: list[Exam]) -> None:
    """把历史遗留默认值 30/60 归一为 5/80。"""
    changed = False
    for e in exams:
        if e.duration_minutes == 30 and float(e.pass_score) == 60.0:
            e.duration_minutes = 5
            e.pass_score = 80.0
            changed = True
    if changed:
        db.commit()


@router.get("", response_model=list[ExamOut])
def list_exams(db: DbSession, user: CurrentUser, course_id: int | None = None):
    q = db.query(Exam)
    if course_id:
        q = q.filter(Exam.course_id == course_id)
    exams = q.order_by(desc(Exam.created_at)).limit(200).all()
    _normalize_legacy_exam_defaults(db, exams)
    return exams


@router.post("", response_model=ExamOut)
def create_exam(payload: ExamCreate, db: DbSession, admin: AdminUser):
    exam = Exam(**payload.model_dump())
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


@router.get("/{exam_id}", response_model=ExamOut)
def get_exam(exam_id: int, db: DbSession, user: CurrentUser):
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "考试不存在")
    _normalize_legacy_exam_defaults(db, [exam])
    return exam


@router.post("/{exam_id}/start", response_model=AttemptStartResponse)
def start_exam(exam_id: int, db: DbSession, user: CurrentUser):
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "考试不存在")
    try:
        attempt = start_attempt(db, exam=exam, user_id=user.id)
    except ExamError as e:
        raise HTTPException(400, str(e))

    questions = (
        db.query(Question)
        .filter(Question.id.in_(attempt.question_ids))
        .all()
    )
    # 保持抽题顺序
    q_by_id = {q.id: q for q in questions}
    ordered = [q_by_id[qid] for qid in attempt.question_ids if qid in q_by_id]
    return AttemptStartResponse(
        attempt=AttemptOut.model_validate(attempt),
        questions=[QuestionOut.model_validate(q) for q in ordered],
    )


@router.post("/attempts/{attempt_id}/submit", response_model=AttemptResult)
def submit(attempt_id: int, payload: SubmitAttemptRequest, db: DbSession, user: CurrentUser):
    attempt = db.get(ExamAttempt, attempt_id)
    if not attempt:
        raise HTTPException(404, "作答不存在")
    if attempt.user_id != user.id:
        raise HTTPException(403, "不能提交他人的作答")

    try:
        attempt = submit_attempt(
            db,
            attempt=attempt,
            answers=[a.model_dump() for a in payload.answers],
            proctor_events=payload.proctor_events,
        )
    except ExamError as e:
        raise HTTPException(400, str(e))

    exam = db.get(Exam, attempt.exam_id)
    answers = db.query(ExamAnswer).filter(ExamAnswer.attempt_id == attempt.id).all()
    q_map = {q.id: q for q in db.query(Question).filter(Question.id.in_([a.question_id for a in answers])).all()}

    details = []
    for a in answers:
        q = q_map.get(a.question_id)
        if not q:
            continue
        details.append(AnswerDetail(
            question_id=q.id,
            stem=q.stem,
            type=q.type.value,
            user_answer=a.answer,
            correct_answer=q.answer,
            is_correct=a.is_correct,
            score=a.score,
            ai_feedback=a.ai_feedback,
            explanation=q.explanation,
        ))
    return AttemptResult(
        attempt=AttemptOut.model_validate(attempt),
        passed=(attempt.score or 0) >= (exam.pass_score if exam else 60.0),
        details=details,
    )


@router.get("/attempts/me", response_model=list[AttemptOut])
def my_attempts(db: DbSession, user: CurrentUser):
    return (
        db.query(ExamAttempt)
        .filter(ExamAttempt.user_id == user.id)
        .order_by(desc(ExamAttempt.started_at))
        .limit(100)
        .all()
    )
