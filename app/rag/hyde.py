"""HyDE 查询改写：语义关键词扩展（不做假设性回答，避免编造事实）。"""

from __future__ import annotations

from app.config import settings
from app.llm_dashscope import chat_completions

_HYDE_PROMPT = """请把用户问题改写成一段「检索友好的语义描述」，要求：

- 只做关键词扩展和语义补充，不要编造具体事实
- 不要生成假设性答案，不要输出具体数字、名称、结论
- 输出应该像「搜索关键词的语义延伸」，而不是「一个回答」
- 保持简洁，50-100字即可
- 使用简体中文；不要解释你在做什么，直接输出改写结果

示例：
用户问「今天天气怎么样？」→「天气 气温 城市 预报 实况 气象条件」
用户问「推荐一部电影」→「电影 推荐 类型 剧情 评价 观影」
用户问「LoRA怎么降低显存？」→「LoRA 低秩适配 显存优化 微调 参数训练」

用户问题：{query}
"""


def generate_hypothetical_answer(query: str) -> str:
    """
    调用千问做检索友好的语义扩展（关键词延伸，非假设答案）。
    失败则返回原始 query。函数名保留以兼容现有调用方。
    """
    original = (query or "").strip()
    if not original:
        return original
    if not settings.DASHSCOPE_API_KEY:
        print("[HyDE] DASHSCOPE_API_KEY 未配置，回退原 query")
        return original

    try:
        content = chat_completions(
            [{"role": "user", "content": _HYDE_PROMPT.format(query=original)}],
            max_tokens=200,
            temperature=0.3,
        )
        if not content:
            print("[HyDE] 空回复，回退原 query")
            return original
        preview = content.replace("\n", " ").strip()
        print(f"[HyDE] 改写为：{preview[:50]}...")
        return content
    except Exception as exc:  # noqa: BLE001
        print(f"[HyDE] 失败，回退原 query: {exc}")
        return original
