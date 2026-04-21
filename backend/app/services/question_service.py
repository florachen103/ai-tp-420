"""
题目生成 + 客观题判分 + AI 主观题判分。
"""
from __future__ import annotations

import random
from dataclasses import dataclass
import re

from sqlalchemy.orm import Session

from app.models.course import Chunk
from app.models.question import Question, QuestionDifficulty, QuestionType
from app.services.ai.prompts import (
    GRADE_SHORT_SYSTEM,
    GRADE_SHORT_USER_TEMPLATE,
    QUESTION_GEN_SYSTEM,
    QUESTION_GEN_USER_TEMPLATE,
)
from app.services.ai.provider import get_ai_provider, safe_json_loads


_MULTI_SPACE_RE = re.compile(r"\s+")


def _normalize_stem(stem: str) -> str:
    """题干归一化：去空白差异、统一大小写，便于去重。"""
    s = (stem or "").strip().lower()
    s = _MULTI_SPACE_RE.sub("", s)
    return s


@dataclass
class GenerateSpec:
    course_id: int
    count: int = 10
    type_distribution: dict[str, int] | None = None
    # 如 {"single": 6, "judge": 3, "short": 1}
    difficulty_distribution: dict[str, int] | None = None
    # 如 {"easy": 3, "medium": 5, "hard": 2}


def generate_questions_for_course(db: Session, spec: GenerateSpec) -> list[Question]:
    """
    从该课程的 chunks 中采样内容，调 LLM 批量生成题目。
    为保证知识点覆盖面，将 chunks 分组分批生成。
    """
    chunks: list[Chunk] = (
        db.query(Chunk)
        .filter(Chunk.course_id == spec.course_id)
        .order_by(Chunk.order_idx)
        .all()
    )
    if not chunks:
        raise ValueError(
            "该课程还没有可用的知识切片。请先上传课件并等待状态变为「解析完成」（parsed）；"
            "若长期停留在排队中/解析中，可点「重新解析」或检查 .env 中的 DASHSCOPE_API_KEY / DEEPSEEK_API_KEY 是否有效。"
        )

    td = spec.type_distribution or {"single": max(1, spec.count * 6 // 10),
                                    "judge": max(1, spec.count * 2 // 10),
                                    "short": max(1, spec.count * 2 // 10)}
    dd = spec.difficulty_distribution or {"easy": spec.count // 3,
                                          "medium": spec.count // 2,
                                          "hard": max(1, spec.count // 6)}

    # 采样覆盖多个章节：把 chunks 合并成大段，控制在 prompt 上下文内
    sample_chunks = chunks if len(chunks) <= 20 else random.sample(chunks, 20)
    sample_chunks = sorted(sample_chunks, key=lambda c: c.order_idx)
    content = "\n\n".join(
        f"【{c.chapter or '章节'}】\n{c.content}" for c in sample_chunks
    )[:8000]  # 限制长度，避免超 token

    ai = get_ai_provider()
    raw = ai.chat(
        messages=[
            {"role": "system", "content": QUESTION_GEN_SYSTEM},
            {"role": "user", "content": QUESTION_GEN_USER_TEMPLATE.format(
                count=spec.count,
                type_distribution=td,
                difficulty_distribution=dd,
                content=content,
            )},
        ],
        temperature=0.4,
        max_tokens=3000,
        response_format="json_object",
    )
    data = safe_json_loads(raw)
    items = data.get("questions", []) if isinstance(data, dict) else []

    existing_q = db.query(Question.stem).filter(Question.course_id == spec.course_id).all()
    existing_stem_keys = {_normalize_stem(stem) for (stem,) in existing_q if stem}

    questions: list[Question] = []
    seen_in_batch: set[str] = set()
    for item in items:
        try:
            stem = str(item["stem"]).strip()
            stem_key = _normalize_stem(stem)
            if not stem_key:
                continue
            if stem_key in existing_stem_keys or stem_key in seen_in_batch:
                continue

            q = Question(
                course_id=spec.course_id,
                chunk_id=sample_chunks[0].id if sample_chunks else None,
                type=QuestionType(item.get("type", "single")),
                difficulty=QuestionDifficulty(item.get("difficulty", "medium")),
                stem=stem,
                options=item.get("options", []) or [],
                answer=[str(a) for a in (item.get("answer", []) or [])],
                explanation=item.get("explanation"),
                knowledge_points=item.get("knowledge_points", []) or [],
                source="ai",
                reviewed=False,
            )
            questions.append(q)
            seen_in_batch.add(stem_key)
        except (KeyError, ValueError):
            continue

    if not questions:
        raise ValueError("本轮生成的题目与现有题库重复度过高，未新增有效题目。请调整课件内容后重试。")

    db.add_all(questions)
    db.commit()
    for q in questions:
        db.refresh(q)
    return questions


def grade_objective(question: Question, user_answer: list[str]) -> tuple[bool, float]:
    """客观题判分：精确匹配答案集合。返回 (是否正确, 得分比例 0-1)。"""
    correct = set(a.upper() for a in question.answer)
    given = set(a.upper() for a in user_answer)
    if question.type == QuestionType.MULTIPLE:
        # 多选：全对才给分，漏选给一半，多选错选不给分（可按需调整）
        if given == correct:
            return True, 1.0
        if given and given.issubset(correct):
            return False, 0.5
        return False, 0.0
    # 单选 / 判断 / 填空
    is_ok = given == correct
    return is_ok, 1.0 if is_ok else 0.0


def grade_short(question: Question, user_answer: str) -> tuple[float, str]:
    """主观题判分：LLM 给 0-100，返回 (得分比例 0-1, 评语)。"""
    reference = "\n".join(question.answer) if question.answer else "（无参考答案）"
    ai = get_ai_provider()
    raw = ai.chat(
        messages=[
            {"role": "system", "content": GRADE_SHORT_SYSTEM},
            {"role": "user", "content": GRADE_SHORT_USER_TEMPLATE.format(
                stem=question.stem,
                reference=reference,
                answer=user_answer or "（未作答）",
            )},
        ],
        temperature=0.1,
        max_tokens=300,
        response_format="json_object",
    )
    try:
        data = safe_json_loads(raw)
        score = float(data.get("score", 0))
        feedback = str(data.get("feedback", ""))
    except Exception:
        score, feedback = 0.0, "自动判分失败，请人工复核。"
    score = max(0.0, min(100.0, score))
    return score / 100.0, feedback
