"""
AI Provider 抽象层。
所有 LLM 调用必须经过 AIProvider 接口，这样切换厂商时业务代码零改动。

当前支持：
  - deepseek: 用 OpenAI 兼容接口（推荐默认）
  - openai:   原生 OpenAI
  - qwen:     阿里通义（Dashscope OpenAI 兼容模式 + text-embedding-v2/v3）
  - custom:   任意 OpenAI 兼容的自托管端点（vLLM/Ollama/FastChat 部署的 Qwen 等）
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import AsyncIterator, Sequence

import httpx
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings


class AIProvider(ABC):
    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_format: str | None = None,  # "json_object" 或 None
    ) -> str: ...

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class OpenAICompatibleProvider(AIProvider):
    """DeepSeek / OpenAI / 自托管 vLLM 共用的实现。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        chat_model: str,
        embedding_model: str,
        embedding_via_dashscope: bool = False,
    ):
        if not api_key:
            raise RuntimeError(
                f"AI Provider 未配置 API Key（base_url={base_url}）。请在项目根目录 .env 中设置相应的 API_KEY。"
            )
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.embedding_via_dashscope = embedding_via_dashscope

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
    def chat(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_format: str | None = None,
    ) -> str:
        kwargs: dict = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}
        resp = self.client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if self.embedding_via_dashscope:
            return _dashscope_embed(list(texts), model=self.embedding_model)
        resp = self.client.embeddings.create(model=self.embedding_model, input=list(texts))
        return [d.embedding for d in resp.data]


def _dashscope_embed(texts: list[str], *, model: str) -> list[list[float]]:
    """
    阿里云 Dashscope 的 embedding 接口与 OpenAI 不完全兼容，走原生 HTTP。
    单次最多 25 条文本。
    """
    key = (settings.DASHSCOPE_API_KEY or "").strip()
    if not key:
        raise RuntimeError(
            "未配置 DASHSCOPE_API_KEY。课件向量化（embedding）依赖阿里云百炼："
            "请打开 https://dashscope.console.aliyun.com/apiKey 创建 API-KEY，"
            "写入项目根目录 .env 中的 DASHSCOPE_API_KEY=sk-...，然后执行 docker compose restart backend。"
        )
    url = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    out: list[list[float]] = []
    for i in range(0, len(texts), 25):
        batch = texts[i : i + 25]
        body = {"model": model, "input": {"texts": batch}}
        r = httpx.post(url, headers=headers, json=body, timeout=60.0)
        if r.status_code in (401, 403):
            raise RuntimeError(
                "阿里云 DashScope 鉴权失败（401/403）：DASHSCOPE_API_KEY 无效、过期或未开通文本向量模型权限。"
                "请到 https://dashscope.console.aliyun.com/apiKey 核对密钥是否为「API-KEY」格式（通常以 sk- 开头），"
                "确认账户已开通百炼 / 灵积服务，修改 .env 后执行 docker compose restart backend。"
                f" 接口返回片段：{r.text[:300]!r}"
            )
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"DashScope embedding 请求失败 HTTP {r.status_code}：{r.text[:400]!r}"
            ) from e
        data = r.json()
        out.extend(item["embedding"] for item in data["output"]["embeddings"])
    return out


def get_ai_provider() -> AIProvider:
    """工厂：根据配置返回相应 Provider。"""
    p = settings.AI_PROVIDER
    if p == "deepseek":
        # DeepSeek 本身不提供 embedding，用 Dashscope 补齐
        return OpenAICompatibleProvider(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            chat_model=settings.AI_MODEL_CHAT,
            embedding_model=settings.AI_MODEL_EMBEDDING,
            embedding_via_dashscope=True,
        )
    if p == "openai":
        return OpenAICompatibleProvider(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            chat_model=settings.AI_MODEL_CHAT or "gpt-4o-mini",
            embedding_model=settings.AI_MODEL_EMBEDDING or "text-embedding-3-small",
        )
    if p == "qwen":
        return OpenAICompatibleProvider(
            api_key=settings.DASHSCOPE_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            chat_model=settings.AI_MODEL_CHAT or "qwen-plus",
            embedding_model=settings.AI_MODEL_EMBEDDING or "text-embedding-v2",
            embedding_via_dashscope=True,
        )
    if p == "custom":
        return OpenAICompatibleProvider(
            api_key=settings.OPENAI_API_KEY or "sk-noop",
            base_url=settings.OPENAI_BASE_URL,
            chat_model=settings.AI_MODEL_CHAT,
            embedding_model=settings.AI_MODEL_EMBEDDING,
        )
    raise ValueError(f"unsupported AI_PROVIDER: {p}")


def safe_json_loads(text: str) -> dict | list:
    """LLM 可能返回带 ```json 包裹的代码块或多余字符，这里尽量容错。"""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{") if "{" in text else text.find("[")
    end = max(text.rfind("}"), text.rfind("]"))
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)
