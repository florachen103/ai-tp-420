"""
RAG 答案缓存：用 Redis 缓存 `/courses/{id}/ask` 的结果，省 embedding + LLM 两次调用。

缓存 key 设计思路：
  - 与语义相关的全部输入都进 key：question / persona / style / top_k / material_ids / chapter / rewrite
  - 课程维度再挂一个 **course_version**：该课程任意课件发生上传/重解析/删除时 version bump，
    所有旧缓存自动失效。这比「全局 TTL + 手动清」可靠得多。

写入路径只在 backend 的 ask 接口里产生；失效路径挂在课件变更 / reparse / delete 处。
Redis 不可达时 **静默跳过**（退化为不缓存），不要把缓存层故障传给业务。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from loguru import logger
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings

# 缓存命中显著，但内容时效要可控：12h 是企业培训场景的合理上限
_CACHE_TTL_SECONDS = 12 * 3600
_VERSION_KEY_PREFIX = "rag:ver:"
_ANSWER_KEY_PREFIX = "rag:ans:"

_redis_client: Redis | None = None
_redis_unavailable_logged = False


def _client() -> Redis | None:
    global _redis_client, _redis_unavailable_logged
    if _redis_client is not None:
        return _redis_client
    try:
        _redis_client = Redis.from_url(settings.redis_url, socket_timeout=1.0, socket_connect_timeout=1.0)
        _redis_client.ping()
        return _redis_client
    except Exception as e:  # noqa: BLE001
        if not _redis_unavailable_logged:
            logger.warning("RAG answer cache disabled (Redis unreachable): {}", e)
            _redis_unavailable_logged = True
        _redis_client = None
        return None


def _entity_version(client: Redis, *, namespace: str, entity_id: int) -> int:
    raw = client.get(f"{_VERSION_KEY_PREFIX}{namespace}:{entity_id}")
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def bump_course_version(course_id: int) -> None:
    """课件发生变更（上传 / 重解析 / 删除）时调用，让该课程所有缓存答案立即失效。"""
    client = _client()
    if client is None:
        return
    try:
        client.incr(f"{_VERSION_KEY_PREFIX}course:{course_id}")
    except RedisError as e:
        logger.debug("bump_course_version failed for course={}: {}", course_id, e)


def bump_knowledge_space_version(space_id: int) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.incr(f"{_VERSION_KEY_PREFIX}space:{space_id}")
    except RedisError as e:
        logger.debug("bump_knowledge_space_version failed for space={}: {}", space_id, e)


def _make_key(*, namespace: str, entity_id: int, version: int, payload_for_hash: dict[str, Any]) -> str:
    raw = json.dumps(payload_for_hash, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]
    return f"{_ANSWER_KEY_PREFIX}{namespace}:{entity_id}:v{version}:{digest}"


def get_cached_answer(
    *,
    course_id: int,
    question: str,
    persona: str | None,
    response_style: str,
    top_k: int,
    material_ids: list[int] | None,
    chapter: str | None,
    rewrite: bool,
    rerank: bool = False,
) -> dict | None:
    client = _client()
    if client is None:
        return None
    try:
        version = _entity_version(client, namespace="course", entity_id=course_id)
        key = _make_key(
            namespace="course",
            entity_id=course_id,
            version=version,
            payload_for_hash={
                "q": (question or "").strip(),
                "p": (persona or "").strip(),
                "s": response_style,
                "k": top_k,
                "m": sorted(material_ids) if material_ids else [],
                "c": (chapter or "").strip(),
                "r": bool(rewrite),
                "rr": bool(rerank),
            },
        )
        raw = client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except (RedisError, json.JSONDecodeError) as e:
        logger.debug("get_cached_answer failed: {}", e)
        return None


def set_cached_answer(
    *,
    course_id: int,
    question: str,
    persona: str | None,
    response_style: str,
    top_k: int,
    material_ids: list[int] | None,
    chapter: str | None,
    rewrite: bool,
    rerank: bool = False,
    value: dict,
) -> None:
    client = _client()
    if client is None:
        return
    try:
        version = _entity_version(client, namespace="course", entity_id=course_id)
        key = _make_key(
            namespace="course",
            entity_id=course_id,
            version=version,
            payload_for_hash={
                "q": (question or "").strip(),
                "p": (persona or "").strip(),
                "s": response_style,
                "k": top_k,
                "m": sorted(material_ids) if material_ids else [],
                "c": (chapter or "").strip(),
                "r": bool(rewrite),
                "rr": bool(rerank),
            },
        )
        client.setex(key, _CACHE_TTL_SECONDS, json.dumps(value, ensure_ascii=False, default=str))
    except RedisError as e:
        logger.debug("set_cached_answer failed: {}", e)


def get_cached_knowledge_answer(
    *,
    space_id: int,
    question: str,
    response_style: str,
    top_k: int,
    rewrite: bool,
    rerank: bool = False,
) -> dict | None:
    client = _client()
    if client is None:
        return None
    try:
        version = _entity_version(client, namespace="space", entity_id=space_id)
        key = _make_key(
            namespace="space",
            entity_id=space_id,
            version=version,
            payload_for_hash={
                "q": (question or "").strip(),
                "s": response_style,
                "k": top_k,
                "r": bool(rewrite),
                "rr": bool(rerank),
            },
        )
        raw = client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except (RedisError, json.JSONDecodeError) as e:
        logger.debug("get_cached_knowledge_answer failed: {}", e)
        return None


def set_cached_knowledge_answer(
    *,
    space_id: int,
    question: str,
    response_style: str,
    top_k: int,
    rewrite: bool,
    rerank: bool = False,
    value: dict,
) -> None:
    client = _client()
    if client is None:
        return
    try:
        version = _entity_version(client, namespace="space", entity_id=space_id)
        key = _make_key(
            namespace="space",
            entity_id=space_id,
            version=version,
            payload_for_hash={
                "q": (question or "").strip(),
                "s": response_style,
                "k": top_k,
                "r": bool(rewrite),
                "rr": bool(rerank),
            },
        )
        client.setex(key, _CACHE_TTL_SECONDS, json.dumps(value, ensure_ascii=False, default=str))
    except RedisError as e:
        logger.debug("set_cached_knowledge_answer failed: {}", e)
