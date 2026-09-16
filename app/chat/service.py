"""对话业务：笔记内讨论 / 全局知识库问答。"""

from __future__ import annotations

from typing import List, Optional, Sequence
from uuid import UUID

from app.chat.llm import chat_completion
from app.models.chat import ChatResponse, ChatSource, Message
from app.models.chunk import SearchResult
from app.notes.exceptions import NoteNotFoundError
from app.notes.service import get_note, list_notes
from app.rag import search

_CONTEXT_PROMPT = """你是一个学习助手。基于以下参考资料回答用户问题。
如果参考资料不足以回答，请说明。

### 关于参考资料（必读）
资料可能来自语音转写，会有同音错字或不顺处。请结合上下文在脑中纠正后，**只使用正确表述作答**。
硬性禁止：
- 禁止出现：原转写、误听、听写错误、同音误、口误、疑似、应为、实际指、语音误差 等字样
- 禁止用括号/脚注对比「错词→正词」（例如「拆铝（实为差旅）」）
- 禁止讨论或解释资料里有没有错字、你如何纠错；读者应感觉资料本来就是对的
- 直接用纠正后的专有名词（如「差旅助手」），不要提及纠正过程

【参考资料】
{context}

【用户问题】
{query}
"""


def _format_context(hits: Sequence[SearchResult]) -> str:
    if not hits:
        return "（无检索结果）"
    parts: List[str] = []
    for i, hit in enumerate(hits, start=1):
        ts = ""
        if hit.start_sec is not None:
            if hit.end_sec is not None:
                ts = f"（时间 {hit.start_sec:.1f}s-{hit.end_sec:.1f}s）"
            else:
                ts = f"（时间 {hit.start_sec:.1f}s）"
        parts.append(f"[{i}]{ts}\n{hit.chunk_text}")
    return "\n\n".join(parts)


def _temp_note_context(note) -> str:
    """临时笔记：优先 summary + cleaned_text，避免把最脏的 raw 全文直接塞进对话。"""
    parts: List[str] = []
    if note.summary and note.summary.strip():
        parts.append(f"【笔记摘要】\n{note.summary.strip()}")
    body = (note.cleaned_text or note.full_text or "").strip()
    if body:
        parts.append(f"【笔记正文】\n{body}")
    return "\n\n".join(parts) if parts else "（笔记正文为空）"


def _title_map(note_ids: Sequence[UUID]) -> dict[UUID, str]:
    titles: dict[UUID, str] = {}
    for nid in note_ids:
        if nid in titles:
            continue
        try:
            titles[nid] = get_note(nid).title
        except NoteNotFoundError:
            titles[nid] = str(nid)
    return titles


def _sources_from_hits(hits: Sequence[SearchResult]) -> List[ChatSource]:
    titles = _title_map([h.note_id for h in hits])
    return [
        ChatSource(
            note_id=h.note_id,
            title=titles.get(h.note_id, str(h.note_id)),
            start_sec=h.start_sec,
        )
        for h in hits
    ]


def _run_chat(
    *,
    query: str,
    context: str,
    history: Optional[List[Message]],
    sources: List[ChatSource],
) -> ChatResponse:
    prompt = _CONTEXT_PROMPT.format(context=context, query=query.strip())
    messages: List[Message] = list(history or [])
    messages.append(Message(role="user", content=prompt))
    answer = chat_completion(messages)
    return ChatResponse(answer=answer, sources=sources)


def chat_on_note(
    note_id: UUID,
    user_query: str,
    history: Optional[List[Message]] = None,
) -> ChatResponse:
    """
    笔记内讨论：
    - 临时笔记：summary + cleaned_text 入 prompt，不检索
    - 永久笔记：仅检索该笔记向量
    """
    query = (user_query or "").strip()
    if not query:
        raise ValueError("query 不能为空")

    note = get_note(note_id)

    if not note.is_permanent:
        context = _temp_note_context(note)
        sources = [
            ChatSource(note_id=note.id, title=note.title, start_sec=None)
        ]
        return _run_chat(
            query=query, context=context, history=history, sources=sources
        )

    hits = search(query, note_ids=[note.id], top_k=5)
    context = _format_context(hits)
    sources = _sources_from_hits(hits)
    return _run_chat(
        query=query, context=context, history=history, sources=sources
    )


def chat_global(
    user_query: str,
    note_ids: Optional[List[UUID]] = None,
    history: Optional[List[Message]] = None,
) -> ChatResponse:
    """
    全局知识库问答：只覆盖永久笔记。
    - note_ids 为空：检索全部已入库向量
    - note_ids 有值：仅检索其中仍为永久的笔记
    """
    query = (user_query or "").strip()
    if not query:
        raise ValueError("query 不能为空")

    permanent = list_notes(is_permanent=True)
    permanent_ids = {n.id for n in permanent}

    if note_ids is not None:
        filtered = [nid for nid in note_ids if nid in permanent_ids]
        if not filtered:
            return _run_chat(
                query=query,
                context="（指定范围内没有已入库的永久笔记）",
                history=history,
                sources=[],
            )
        hits = search(query, note_ids=filtered, top_k=5)
    else:
        if not permanent_ids:
            return _run_chat(
                query=query,
                context="（知识库中尚无永久笔记）",
                history=history,
                sources=[],
            )
        hits = search(query, note_ids=None, top_k=5)

    return _run_chat(
        query=query,
        context=_format_context(hits),
        history=history,
        sources=_sources_from_hits(hits),
    )
