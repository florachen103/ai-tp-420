"""学习记录 + 数据看板。"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
import re

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc

from app.core.deps import CurrentUser, DbSession
from app.models.exam import Exam, ExamAnswer, ExamAttempt, ExamStatus
from app.models.question import Question
from app.models.record import LearningAction, LearningRecord
from app.schemas.record import DashboardStats, RecordOut, ReviewKpPerfectRequest

router = APIRouter()

# 近 90 天内同一知识点「自测全对」达到该次数后，不再计入薄弱知识点
REVIEW_KP_MASTER_ROUNDS = 3
_MULTI_SPACE_RE = re.compile(r"\s+")


def _normalize_kp(kp: str) -> str:
    return _MULTI_SPACE_RE.sub(" ", (kp or "").strip()).lower()


def _learning_record_dedupe_key(r: LearningRecord) -> str:
    """与前端一致：相同场景的多条记录只展示一条（保留最新的）。"""
    p = dict(r.payload or {})
    if r.action == LearningAction.START_EXAM:
        return f"start_exam:{p.get('exam_id')}:{p.get('attempt_max_score')}"
    if r.action == LearningAction.SUBMIT_EXAM:
        return f"submit_exam:{p.get('attempt_id', r.id)}"
    if r.action == LearningAction.ASK_QUESTION:
        q = str(p.get("question") or "")[:160]
        return f"ask_question:{q}"
    if r.action == LearningAction.VIEW_COURSE:
        return f"view_course:{r.course_id}:{p.get('title')}"
    if r.action == LearningAction.READ_CHUNK:
        return f"read_chunk:{r.course_id}:{p.get('chunk_id')}"
    if r.action == LearningAction.COMPLETE_CHAPTER:
        return f"complete_chapter:{r.course_id}:{p.get('chapter') or p.get('title')}"
    if r.action == LearningAction.PRACTICE:
        return f"practice:{r.course_id}:{p.get('topic') or p.get('title')}"
    if r.action == LearningAction.REVIEW_KP_PERFECT:
        kp = str(p.get("knowledge_point") or "").strip()[:200]
        # 同一知识点只保留最新一条在「最近活动」展示，避免刷屏；掌握次数在统计里单独累计
        return f"review_kp_perfect:{kp}"
    act_s = r.action.value if hasattr(r.action, "value") else str(r.action)
    return f"{act_s}:{r.course_id}:{json.dumps(p, sort_keys=True, ensure_ascii=False)}"


def _dedupe_learning_records(records: list[LearningRecord]) -> list[LearningRecord]:
    seen: set[str] = set()
    out: list[LearningRecord] = []
    for row in records:
        k = _learning_record_dedupe_key(row)
        if k in seen:
            continue
        seen.add(k)
        out.append(row)
    return out


def _learning_records_base_query(db: DbSession, user_id: int, *, meaningful: bool):
    """meaningful=True 时排除「仅浏览课程」类高频低信息记录。"""
    q = db.query(LearningRecord).filter(LearningRecord.user_id == user_id)
    if meaningful:
        q = q.filter(LearningRecord.action != LearningAction.VIEW_COURSE)
    return q.order_by(desc(LearningRecord.created_at))


@router.post("/me/review-kp-perfect")
def log_review_kp_perfect_round(
    db: DbSession,
    user: CurrentUser,
    body: ReviewKpPerfectRequest,
):
    """薄弱知识点复习页：本轮自测全部答对时上报，用于「全对满 3 次则移出薄弱列表」。"""
    kp = body.knowledge_point.strip()
    if not kp:
        raise HTTPException(400, "knowledge_point 不能为空")
    db.add(
        LearningRecord(
            user_id=user.id,
            course_id=None,
            action=LearningAction.REVIEW_KP_PERFECT,
            payload={
                "knowledge_point": kp,
                "question_count": body.question_count,
            },
            duration_sec=0,
        )
    )
    db.commit()
    return {"ok": True, "message": "已记录本轮全对"}


@router.get("/me/review-kp-status")
def review_kp_status(
    db: DbSession,
    user: CurrentUser,
    knowledge_point: str = Query(..., min_length=1, max_length=400),
):
    """返回某薄弱知识点累计全对次数（近 90 天）与剩余次数。"""
    since = datetime.now(timezone.utc) - timedelta(days=90)
    target = _normalize_kp(knowledge_point)
    rows = (
        db.query(LearningRecord)
        .filter(
            LearningRecord.user_id == user.id,
            LearningRecord.action == LearningAction.REVIEW_KP_PERFECT,
            LearningRecord.created_at >= since,
        )
        .all()
    )
    rounds = 0
    for r in rows:
        raw = (r.payload or {}).get("knowledge_point")
        if isinstance(raw, str) and _normalize_kp(raw) == target:
            rounds += 1
    return {
        "knowledge_point": knowledge_point.strip(),
        "rounds": rounds,
        "master_rounds": REVIEW_KP_MASTER_ROUNDS,
        "remaining": max(0, REVIEW_KP_MASTER_ROUNDS - rounds),
        "mastered": rounds >= REVIEW_KP_MASTER_ROUNDS,
    }


@router.get("/me", response_model=list[RecordOut])
def my_records(
    db: DbSession,
    user: CurrentUser,
    limit: int = 50,
    meaningful: bool = Query(
        True,
        description="为 true 时隐藏「仅浏览课程」类高频记录",
    ),
):
    fetch = min(max(limit * 6, limit), 300)
    rows = _learning_records_base_query(db, user.id, meaningful=meaningful).limit(fetch).all()
    deduped = _dedupe_learning_records(rows)
    return [RecordOut.model_validate(r) for r in deduped[: min(limit, 200)]]


@router.get("/dashboard/me", response_model=DashboardStats)
def my_dashboard(db: DbSession, user: CurrentUser):
    """个人学习看板。"""
    since = datetime.now(timezone.utc) - timedelta(days=90)

    records = (
        db.query(LearningRecord)
        .filter(LearningRecord.user_id == user.id, LearningRecord.created_at >= since)
        .all()
    )
    non_exam_sec = 0
    submit_exam_record_sec = 0
    for r in records:
        sec = int(r.duration_sec or 0)
        if sec <= 0:
            sec = int((r.payload or {}).get("duration_sec") or 0)
        if r.action == LearningAction.SUBMIT_EXAM:
            submit_exam_record_sec += max(0, sec)
        else:
            non_exam_sec += max(0, sec)

    # 兼容历史数据：早期 submit_exam 未写 duration_sec，回算考试用时
    attempts_90d = (
        db.query(ExamAttempt)
        .filter(
            ExamAttempt.user_id == user.id,
            ExamAttempt.started_at >= since,
        )
        .all()
    )
    exam_elapsed_sec = 0
    for a in attempts_90d:
        end_at = a.submitted_at or a.graded_at
        if not end_at or not a.started_at:
            continue
        exam_elapsed_sec += max(0, int((end_at - a.started_at).total_seconds()))

    total_sec = non_exam_sec + max(submit_exam_record_sec, exam_elapsed_sec)
    courses_viewed = len({r.course_id for r in records if r.course_id and r.action == LearningAction.VIEW_COURSE})

    attempts = (
        db.query(ExamAttempt)
        .filter(ExamAttempt.user_id == user.id, ExamAttempt.status == ExamStatus.GRADED)
        .all()
    )
    exams_taken = len(attempts)
    passed = 0
    scores: list[float] = []
    for a in attempts:
        exam = db.get(Exam, a.exam_id)
        if a.score is not None:
            scores.append(a.score)
            if exam and a.score >= exam.pass_score:
                passed += 1
    avg = sum(scores) / len(scores) if scores else None

    # 薄弱知识点：统计错题关联的 knowledge_points
    wrong_answers = (
        db.query(ExamAnswer, Question)
        .join(Question, Question.id == ExamAnswer.question_id)
        .join(ExamAttempt, ExamAttempt.id == ExamAnswer.attempt_id)
        .filter(
            ExamAttempt.user_id == user.id,
            ExamAnswer.is_correct == False,  # noqa: E712
        )
        .all()
    )
    kp_counter: Counter[str] = Counter()
    kp_total: Counter[str] = Counter()
    kp_display: dict[str, str] = {}
    all_answers = (
        db.query(ExamAnswer, Question)
        .join(Question, Question.id == ExamAnswer.question_id)
        .join(ExamAttempt, ExamAttempt.id == ExamAnswer.attempt_id)
        .filter(ExamAttempt.user_id == user.id)
        .all()
    )
    for _, q in all_answers:
        for kp in (q.knowledge_points or []):
            n = _normalize_kp(kp)
            if not n:
                continue
            kp_total[n] += 1
            kp_display.setdefault(n, kp)
    for _, q in wrong_answers:
        for kp in (q.knowledge_points or []):
            n = _normalize_kp(kp)
            if not n:
                continue
            kp_counter[n] += 1
            kp_display.setdefault(n, kp)

    perfect_by_kp: Counter[str] = Counter()
    for r in records:
        if r.action != LearningAction.REVIEW_KP_PERFECT:
            continue
        raw = (r.payload or {}).get("knowledge_point")
        if isinstance(raw, str) and raw.strip():
            perfect_by_kp[_normalize_kp(raw)] += 1

    weak = []
    for kp_norm, wrong_n in kp_counter.most_common(30):
        if perfect_by_kp.get(kp_norm, 0) >= REVIEW_KP_MASTER_ROUNDS:
            continue
        total_n = kp_total.get(kp_norm, 0) or 1
        weak.append({
            "point": kp_display.get(kp_norm, kp_norm),
            "wrong_rate": round(wrong_n / total_n, 2),
            "attempts": total_n,
            "mastery_rounds": perfect_by_kp.get(kp_norm, 0),
            "mastery_target": REVIEW_KP_MASTER_ROUNDS,
        })
        if len(weak) >= 10:
            break

    recent_rows = _learning_records_base_query(db, user.id, meaningful=True).limit(48).all()
    recent = _dedupe_learning_records(recent_rows)[:8]
    return DashboardStats(
        total_learning_minutes=total_sec // 60,
        courses_viewed=courses_viewed,
        exams_taken=exams_taken,
        exams_passed=passed,
        average_score=round(avg, 2) if avg is not None else None,
        recent_records=[RecordOut.model_validate(r) for r in recent],
        weak_knowledge_points=weak,
    )
