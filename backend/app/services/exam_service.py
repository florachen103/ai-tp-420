"""
考试业务：按规则抽题 → 创建 Attempt → 判分 → 落库。
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
import re

from sqlalchemy.orm import Session

from app.models.exam import Exam, ExamAnswer, ExamAttempt, ExamStatus
from app.models.question import Question, QuestionType
from app.models.record import LearningAction, LearningRecord
from app.services.question_service import grade_objective, grade_short


class ExamError(Exception):
    pass


_MULTI_SPACE_RE = re.compile(r"\s+")


def _normalize_stem(stem: str) -> str:
    return _MULTI_SPACE_RE.sub("", (stem or "").strip().lower())


def draw_questions(db: Session, exam: Exam) -> list[Question]:
    """按 exam.rules 抽题。rules 示例：
        {"single": {"count": 10, "score": 2},
         "judge":  {"count": 5,  "score": 1},
         "short":  {"count": 2,  "score": 10}}
    """
    drawn: list[Question] = []
    seen_stem_keys: set[str] = set()
    for type_key, cfg in (exam.rules or {}).items():
        try:
            qtype = QuestionType(type_key)
        except ValueError:
            continue
        pool = (
            db.query(Question)
            .filter(Question.course_id == exam.course_id, Question.type == qtype)
            .all()
        )
        count = int(cfg.get("count", 0))
        if count <= 0 or not pool:
            continue
        random.shuffle(pool)
        picked = 0
        for q in pool:
            stem_key = _normalize_stem(q.stem)
            if not stem_key or stem_key in seen_stem_keys:
                continue
            drawn.append(q)
            seen_stem_keys.add(stem_key)
            picked += 1
            if picked >= count:
                break
    return drawn


def start_attempt(db: Session, *, exam: Exam, user_id: int) -> ExamAttempt:
    questions = draw_questions(db, exam)
    if not questions:
        raise ExamError("题库尚未就绪，无法发起考试")

    max_score = 0.0
    for type_key, cfg in (exam.rules or {}).items():
        count = int(cfg.get("count", 0))
        score_each = float(cfg.get("score", 0))
        max_score += count * score_each

    if exam.shuffle_questions:
        random.shuffle(questions)

    attempt = ExamAttempt(
        exam_id=exam.id,
        user_id=user_id,
        question_ids=[q.id for q in questions],
        status=ExamStatus.IN_PROGRESS,
        max_score=max_score or 100.0,
    )
    db.add(attempt)
    db.add(LearningRecord(
        user_id=user_id,
        course_id=exam.course_id,
        action=LearningAction.START_EXAM,
        payload={
            "exam_id": exam.id,
            "exam_title": exam.title,
            "attempt_max_score": max_score,
        },
    ))
    db.commit()
    db.refresh(attempt)
    return attempt


def submit_attempt(
    db: Session,
    *,
    attempt: ExamAttempt,
    answers: list[dict],
    proctor_events: list[dict] | None = None,
) -> ExamAttempt:
    """
    answers 格式：[{"question_id": 1, "answer": ["B"], "time_spent_sec": 30}, ...]
    """
    if attempt.status != ExamStatus.IN_PROGRESS:
        raise ExamError("该作答已提交或已过期")

    exam: Exam = db.get(Exam, attempt.exam_id)  # type: ignore[assignment]
    score_map: dict[QuestionType, float] = {}
    for type_key, cfg in (exam.rules or {}).items():
        try:
            score_map[QuestionType(type_key)] = float(cfg.get("score", 0))
        except ValueError:
            continue

    total_score = 0.0
    answer_by_qid = {int(a["question_id"]): a for a in answers}

    for qid in attempt.question_ids:
        q: Question | None = db.get(Question, qid)
        if not q:
            continue
        a = answer_by_qid.get(qid, {})
        user_ans = a.get("answer", []) or []
        time_spent = int(a.get("time_spent_sec", 0))
        score_each = score_map.get(q.type, 0.0)

        if q.type in (QuestionType.SINGLE, QuestionType.MULTIPLE, QuestionType.JUDGE, QuestionType.FILL):
            is_correct, ratio = grade_objective(q, [str(x) for x in user_ans])
            earned = score_each * ratio
            db.add(ExamAnswer(
                attempt_id=attempt.id,
                question_id=qid,
                answer=[str(x) for x in user_ans],
                is_correct=is_correct,
                score=earned,
                time_spent_sec=time_spent,
            ))
            total_score += earned
        elif q.type == QuestionType.SHORT:
            user_text = user_ans[0] if user_ans else ""
            ratio, feedback = grade_short(q, str(user_text))
            earned = score_each * ratio
            db.add(ExamAnswer(
                attempt_id=attempt.id,
                question_id=qid,
                answer=[str(user_text)],
                is_correct=None,
                score=earned,
                ai_feedback=feedback,
                time_spent_sec=time_spent,
            ))
            total_score += earned

    now = datetime.now(timezone.utc)
    attempt.status = ExamStatus.GRADED
    attempt.score = round(total_score, 2)
    attempt.submitted_at = now
    attempt.graded_at = now
    if proctor_events:
        attempt.proctor_events = proctor_events

    elapsed_sec = max(0, int((now - attempt.started_at).total_seconds())) if attempt.started_at else 0
    db.add(LearningRecord(
        user_id=attempt.user_id,
        course_id=exam.course_id,
        action=LearningAction.SUBMIT_EXAM,
        payload={
            "exam_id": exam.id,
            "exam_title": exam.title,
            "attempt_id": attempt.id,
            "score": attempt.score,
            "max_score": attempt.max_score,
            "passed": (attempt.score or 0) >= exam.pass_score,
        },
        duration_sec=elapsed_sec,
    ))
    db.commit()
    db.refresh(attempt)
    return attempt
