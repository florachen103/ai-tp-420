"""
可选：LLM rerank。

MMR + 混合召回已经能让 Top-K 在大多数情况下表现不错。但当：
  - 候选池较大（Top-K × 2 个以上）
  - 学员用的是相对复杂的长问题
  - 领域术语密集，向量模型不够专业
LLM rerank 对「最终 K 条」的相关度通常能再提升 5~10%（尤其能把"跑题但词面相似"踢出去）。

实现策略：
  1) 先用 retriever 取 top_k * 2 的候选（靠 pool_multiplier 隐式控制）
  2) 把候选切片 + 原问题发给一个小 LLM，给每段打 0~10 相关度分
  3) 用 rerank_score * 0.7 + 原 score * 0.3 线性融合，按新分排序
  4) 取前 top_k
失败时直接返回原列表（rerank 永远是「加分项」，不能因为服务不稳就让检索挂掉）。

调用会额外花一次 LLM 请求 + ~150 tokens，所以默认关闭，由 AskRequest.rerank 控制。
"""
from __future__ import annotations

import json

from loguru import logger

from app.services.ai.provider import get_ai_provider, safe_json_loads
from app.services.rag.retriever import RetrievedChunk


_RERANK_SYSTEM = """你是一个检索重排器。给你「问题」和一组「候选片段」，
请对每个片段给出 0~10 的相关度分（10 = 能直接回答问题；0 = 完全跑题）。
规则：
1. 只根据片段内容与问题的匹配度打分，不要被措辞华丽/篇幅长的干扰。
2. 必须对每个候选给分，缺一不可。
3. 输出严格 JSON：{"scores":[{"idx":0,"score":8},{"idx":1,"score":3},...]}，
   idx 对应输入里 [C0][C1]... 的编号。禁止任何额外文字。"""


def rerank_chunks(question: str, chunks: list[RetrievedChunk], *, top_k: int) -> list[RetrievedChunk]:
    """对候选切片做 LLM rerank；失败时返回原列表的前 top_k。"""
    if not chunks:
        return []
    if len(chunks) <= 1:
        return chunks[:top_k]

    # 构造简化的片段列表（太长会让 LLM 反应慢 / 跑偏；每段截 240 字）
    lines = []
    for i, c in enumerate(chunks):
        snippet = (c.content or "").strip()[:240].replace("\n", " ")
        lines.append(f"[C{i}] {snippet}")
    user = f"【问题】{question}\n\n【候选片段】\n" + "\n".join(lines) + "\n\n请输出 JSON。"

    ai = get_ai_provider()
    try:
        raw = ai.chat(
            messages=[
                {"role": "system", "content": _RERANK_SYSTEM},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
            max_tokens=300,
            response_format="json_object",
        )
    except Exception as e:  # noqa: BLE001
        logger.debug("rerank skipped (provider error): {}", e)
        return chunks[:top_k]

    try:
        data = safe_json_loads(raw)
        if not isinstance(data, dict):
            raise ValueError("not a dict")
        items = data.get("scores") or []
        if not isinstance(items, list):
            raise ValueError("scores is not list")
    except (ValueError, TypeError, json.JSONDecodeError) as e:
        logger.debug("rerank parse failed: {}", e)
        return chunks[:top_k]

    rerank_scores: dict[int, float] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item["idx"])
            score = float(item["score"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= idx < len(chunks):
            rerank_scores[idx] = max(0.0, min(10.0, score))

    # 对未返回分数的候选，给一个中性默认值 5，避免被一棍子打死
    fused: list[tuple[int, float]] = []
    for i, c in enumerate(chunks):
        r = rerank_scores.get(i, 5.0) / 10.0  # 归一到 0..1
        fused_score = 0.7 * r + 0.3 * c.score
        fused.append((i, fused_score))

    fused.sort(key=lambda x: x[1], reverse=True)
    out: list[RetrievedChunk] = []
    for i, new_score in fused[:top_k]:
        c = chunks[i]
        out.append(RetrievedChunk(
            id=c.id,
            content=c.content,
            chapter=c.chapter,
            score=round(new_score, 4),
            meta=c.meta,
        ))
    return out
