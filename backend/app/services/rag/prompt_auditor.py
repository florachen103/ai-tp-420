"""
差评驱动的 Prompt 自检报告。

动机：
  我们已经把学员的"没解决"+评语回收到 answer_feedbacks 表，但靠管理员
  一条一条看差评很被动。不如直接让 LLM 批量看一遍：
    - 发现差评里的共性模式（例：都和价格相关，都无引用，都问售后流程…）
    - 倒推 Prompt / 检索策略要怎么改
    - 给出 2~4 条可操作的改进建议（而不是"回答得再仔细点"这种废话）

安全边界：
  - 只把学员问题 + 学员评语 + 是否有引用 / 是否缓存命中 这些"诊断信号"发给 LLM，
    不发 AI 的原始答案（那会让 LLM 评价 LLM 自己的输出，容易绕圈子），
    也不发学员身份 / 课程敏感内容。
  - 采样上限 30 条，避免 token 爆炸。
  - 失败时返回 {"error": ..., "patterns": [], "recommendations": []}，不抛。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.feedback import AnswerFeedback
from app.services.ai.provider import get_ai_provider, safe_json_loads

_MAX_CASES = 30
_MIN_CASES = 3  # 少于 3 条差评不做报告，样本太小结论没意义

_AUDIT_SYSTEM = """你是一个企业培训 RAG 问答系统的"答案质量审计员"。
我会给你一批学员对 AI 答案打了差评的记录，每条包含：
  - 学员的问题（question）
  - 学员的评语（comment，可能为空）
  - 系统是否检索到引用（has_citation）
  - 是否命中答案缓存（cache_hit）

你的任务：
  1. 找出差评案例中反复出现的模式（patterns），每条 1~2 句话，聚焦"问题类型 / 缺陷性质"；
  2. 给出 2~4 条可操作的改进建议（recommendations），每条必须说明：
     - 改什么（Prompt 某处 / 检索策略 / 切块粒度 / 补充课件…）
     - 为什么这么改（对应哪些差评模式）
  3. 挑 2~3 个最有代表性的案例（examples），用 index 指回输入列表。

输出严格 JSON（禁止多余文字）：
{
  "patterns": [{"title":"...","count":N,"note":"..."}],
  "recommendations": [{"area":"prompt|retrieval|chunking|corpus","action":"...","reason":"..."}],
  "examples": [{"idx":0,"why":"..."}]
}

严禁：编造没出现的共性；给"多加上下文""再优化一下"这类空话；给超过 4 条建议。"""


@dataclass
class AuditResult:
    sample_size: int
    patterns: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]
    examples: list[dict[str, Any]]
    cases: list[dict[str, Any]]  # 原始样本，前端要显示出来让管理员核对
    error: str | None = None


def generate_prompt_audit(
    db: Session,
    *,
    days: int = 30,
    course_id: int | None = None,
    max_cases: int = _MAX_CASES,
) -> AuditResult:
    """抽取最近差评，让 LLM 产出 Prompt 调整建议。"""
    days = max(1, min(days, 180))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    q = (
        db.query(AnswerFeedback)
        .filter(AnswerFeedback.created_at >= since)
        .filter(AnswerFeedback.rating == -1)
    )
    if course_id is not None:
        q = q.filter(AnswerFeedback.course_id == course_id)
    rows = q.order_by(desc(AnswerFeedback.created_at)).limit(max_cases).all()

    cases: list[dict[str, Any]] = []
    for f in rows:
        snap = f.snapshot or {}
        cases.append({
            "idx": len(cases),
            "question": (snap.get("question") or "").strip()[:400],
            "comment": (f.comment or "").strip()[:300],
            "has_citation": bool((snap.get("citations_used") or [])),
            "cache_hit": bool(snap.get("cache_hit")),
            "course_id": f.course_id,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        })

    if len(cases) < _MIN_CASES:
        return AuditResult(
            sample_size=len(cases),
            patterns=[],
            recommendations=[],
            examples=[],
            cases=cases,
            error=f"差评样本太少（{len(cases)} 条，低于 {_MIN_CASES} 条阈值），暂不生成报告。继续积累数据吧。",
        )

    # 拼 LLM 输入：紧凑点，别浪费 token
    compact = "\n".join(
        f"[{c['idx']}] Q: {c['question']}"
        f" | 评语: {c['comment'] or '(无)'}"
        f" | 有引用: {'是' if c['has_citation'] else '否'}"
        f" | 缓存命中: {'是' if c['cache_hit'] else '否'}"
        for c in cases
    )
    user_prompt = f"共 {len(cases)} 条差评案例：\n{compact}\n\n请输出 JSON 报告。"

    ai = get_ai_provider()
    try:
        raw = ai.chat(
            messages=[
                {"role": "system", "content": _AUDIT_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1200,
            response_format="json_object",
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Prompt 自检报告 LLM 调用失败：{}", e)
        return AuditResult(
            sample_size=len(cases),
            patterns=[],
            recommendations=[],
            examples=[],
            cases=cases,
            error=f"LLM 调用失败：{e}",
        )

    try:
        data = safe_json_loads(raw)
        if not isinstance(data, dict):
            raise ValueError("not a dict")
    except Exception as e:  # noqa: BLE001
        logger.warning("Prompt 自检报告 JSON 解析失败：{} / raw={!r}", e, raw[:300])
        return AuditResult(
            sample_size=len(cases),
            patterns=[],
            recommendations=[],
            examples=[],
            cases=cases,
            error=f"LLM 输出不是合法 JSON：{e}",
        )

    def _safe_list(v: Any) -> list[dict[str, Any]]:
        return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []

    return AuditResult(
        sample_size=len(cases),
        patterns=_safe_list(data.get("patterns")),
        recommendations=_safe_list(data.get("recommendations")),
        examples=_safe_list(data.get("examples")),
        cases=cases,
    )
