"""对话业务：笔记内讨论 / 全局知识库问答。"""

from __future__ import annotations

import time
from typing import List, Optional, Sequence
from uuid import UUID

from app.chat.llm import chat_completion
from app.config import settings
from app.models.chat import ChatResponse, ChatSource, Message
from app.models.chunk import SearchResult
from app.notes.exceptions import NoteNotFoundError
from app.notes.service import get_note, list_notes
from app.rag import search

_CONTEXT_PROMPT = """你是一个学习助手。请**只针对当前用户问题**作答。

### 回答原则
- 必须基于【用户问题】回答，不要被对话历史带偏；历史仅用于理解指代，不能改写当前题意。
- 参考资料只作为辅助。如果参考资料为空、不足，或与当前问题明显无关：
  1. 先明确说一句「个人知识库中没有找到相关内容」
  2. **不要停止回答**，接着用你自己的通用知识回答当前问题
- 不要因为上一轮聊过某篇笔记，就把无关问题硬往那篇笔记上靠。

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


def _chat_top_k() -> int:
    """对话检索条数：与 RAG_MAX_RESULTS 对齐，至少 1。"""
    return max(1, int(settings.RAG_MAX_RESULTS))


def _format_context(hits: Sequence[SearchResult]) -> str:
    if not hits:
        return "（无检索结果，与当前问题无关或知识库未覆盖）"
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
    """按 note_id 去重：同一笔记只保留 RRF 分数最高的一条，并带上命中片段数。"""
    if not hits:
        return []
    best: dict[UUID, SearchResult] = {}
    counts: dict[UUID, int] = {}
    order: List[UUID] = []
    for hit in hits:
        nid = hit.note_id
        counts[nid] = counts.get(nid, 0) + 1
        if nid not in best:
            best[nid] = hit
            order.append(nid)
            continue
        if float(hit.score or 0.0) > float(best[nid].score or 0.0):
            best[nid] = hit

    titles = _title_map(order)
    sources = [
        ChatSource(
            note_id=nid,
            title=titles.get(nid, str(nid)),
            start_sec=best[nid].start_sec,
            hit_count=counts[nid],
        )
        for nid in order
    ]
    print(
        f"[CHAT] sources 按笔记去重：{len(hits)} 个片段 → {len(sources)} 篇笔记"
    )
    return sources


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
    hist_n = len(history or [])
    print(
        f"[LLM] 正在生成回答… history={hist_n} sources={len(sources)} "
        f"context_chars={len(context)}"
    )
    t0 = time.perf_counter()
    answer = chat_completion(messages)
    elapsed = time.perf_counter() - t0
    out_sources = list(sources)
    # 模型声明知识库未命中时，前端不再展示误导性引用
    if "个人知识库中没有找到相关内容" in (answer or ""):
        if out_sources:
            print(
                f"[CHAT] 回答声明知识库未命中，清空 sources（原 {len(out_sources)} 条）"
            )
        out_sources = []
    print(
        f"[DONE] 回答生成完毕，耗时 {elapsed:.1f} 秒"
        f"（{len(answer)} 字，sources={len(out_sources)}）"
    )
    return ChatResponse(answer=answer, sources=out_sources)


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

    print(f"[CHAT] 收到问题（笔记内 {note_id}）：{query}")
    note = get_note(note_id)

    if not note.is_permanent:
        print("[CHAT] 临时笔记，使用摘要+正文，不走检索")
        context = _temp_note_context(note)
        sources = [
            ChatSource(
                note_id=note.id, title=note.title, start_sec=None, hit_count=1
            )
        ]
        return _run_chat(
            query=query, context=context, history=history, sources=sources
        )

    hits = search(query, note_ids=[note.id], top_k=_chat_top_k())
    print(f"[CHAT] 笔记内检索命中 {len(hits)} 条")
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
    - note_ids 为 None 或 []：检索全部已入库向量
    - note_ids 有值：仅检索其中仍为永久的笔记
    """
    query = (user_query or "").strip()
    if not query:
        raise ValueError("query 不能为空")

    print(f"[CHAT] 收到问题：{query}")
    permanent = list_notes(is_permanent=True)
    permanent_ids = {n.id for n in permanent}
    print(f"[CHAT] 永久笔记 {len(permanent_ids)} 篇")

    scoped = list(note_ids) if note_ids else []
    if not scoped:
        if not permanent_ids:
            print("[CHAT] 知识库为空，走通用知识回答")
            return _run_chat(
                query=query,
                context="（知识库中尚无永久笔记）",
                history=history,
                sources=[],
            )
        hits = search(
            query, note_ids=None, top_k=_chat_top_k()
        )
    else:
        filtered = [nid for nid in scoped if nid in permanent_ids]
        if not filtered:
            print("[CHAT] 指定范围内没有永久笔记，走通用知识回答")
            return _run_chat(
                query=query,
                context="（指定范围内没有已入库的永久笔记）",
                history=history,
                sources=[],
            )
        hits = search(
            query, note_ids=filtered, top_k=_chat_top_k()
        )

    print(f"[CHAT] 全局检索命中 {len(hits)} 条（截断后）")
    return _run_chat(
        query=query,
        context=_format_context(hits),
        history=history,
        sources=_sources_from_hits(hits),
    )
