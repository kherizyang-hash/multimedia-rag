"""百炼调用封装：优先走控制台「OpenAI 兼容」Base URL。"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Sequence

from openai import OpenAI

from app.config import settings

_DEFAULT_COMPATIBLE = (
    "https://dashscope.aliyuncs.com/compatible-mode/v1"
)


def compatible_base_url() -> str:
    """OpenAI 兼容端点（截图中那一行）。"""
    url = (settings.DASHSCOPE_COMPATIBLE_BASE_URL or "").strip().rstrip("/")
    if url:
        return url
    # 兼容旧配置：若只填了原生 /api/v1，自动换成 compatible-mode/v1
    native = (settings.DASHSCOPE_BASE_URL or "").strip().rstrip("/")
    if native.endswith("/api/v1"):
        return native[: -len("/api/v1")] + "/compatible-mode/v1"
    return _DEFAULT_COMPATIBLE


@lru_cache(maxsize=4)
def _client_for(base_url: str, api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=base_url)


def get_openai_client() -> OpenAI:
    if not settings.DASHSCOPE_API_KEY:
        raise RuntimeError(
            "DASHSCOPE_API_KEY 未配置，请在 .env 中填写（参见 .env.example）"
        )
    return _client_for(compatible_base_url(), settings.DASHSCOPE_API_KEY)


def configure_dashscope() -> None:
    """启动时打印/校验端点；实际请求走 OpenAI 兼容客户端。"""
    # 清缓存，便于改 .env 后热更新（重启时）
    _client_for.cache_clear()
    print(f"[CONFIG] dashscope_compatible_base={compatible_base_url()}")


def chat_completions(
    messages: Sequence[dict],
    *,
    max_tokens: int | None = None,
    temperature: float = 0.7,
    model: str | None = None,
) -> str:
    """Chat Completions；返回助手文本。失败抛 RuntimeError。"""
    used_model = model or settings.QWEN_MODEL
    print(f"[LLM] 请求 chat.completions model={used_model}")
    client = get_openai_client()
    try:
        resp = client.chat.completions.create(
            model=used_model,
            messages=list(messages),
            max_tokens=max_tokens if max_tokens is not None else settings.QWEN_MAX_TOKENS,
            temperature=temperature,
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"通义千问调用异常: {exc}") from exc

    try:
        content = resp.choices[0].message.content
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"通义千问返回解析失败: {exc}") from exc

    text = str(content or "").strip()
    if not text:
        raise RuntimeError("通义千问返回空内容")
    print(f"[LLM] chat.completions 成功，返回 {len(text)} 字")
    return text


def embed_texts_openai(texts: List[str], *, model: str = "text-embedding-v1") -> List[List[float]]:
    """OpenAI 兼容 Embedding；保持 1536 维 text-embedding-v1。"""
    if not texts:
        return []
    client = get_openai_client()
    try:
        resp = client.embeddings.create(model=model, input=texts)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"DashScope embedding 调用异常: {exc}") from exc

    items = sorted(resp.data, key=lambda x: x.index)
    if len(items) != len(texts):
        raise RuntimeError(
            f"DashScope embedding 返回条数不符: expect={len(texts)}, got={len(items)}"
        )
    vectors: List[List[float]] = []
    for item in items:
        emb = list(item.embedding or [])
        if len(emb) != settings.EMBEDDING_DIM:
            raise RuntimeError(
                f"嵌入维度不符: expect={settings.EMBEDDING_DIM}, got={len(emb)}"
            )
        vectors.append(emb)
    return vectors
