"""通义千问：生成总结笔记 + 思维导图。"""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

import dashscope
from dashscope import Generation

from app.config import settings


def build_prompt(cleaned_text: str) -> str:
    """构造发给通义千问的 Prompt（标题 + 笔记 + 导图）。"""
    return f"""你是一个耐心的学习助手。下面是一段视频的语音转写稿。请完成三项任务。

### 关于转写稿（必读）
转写可能有同音错字或不顺处。请结合上下文在脑中纠正后，**只输出最终正确版本**。
硬性禁止（标题、笔记与导图均适用）：
- 禁止出现：原转写、误听、听写错误、同音误、疑似、应为、实际指、语音误差 等字样
- 禁止用括号/脚注对比「错词→正词」（例如「拆铝（实为差旅）」「非常准（飞常准）」）
- 禁止讨论或解释你如何纠错；读者应感觉文稿本来就是对的
- 也不要编造转写中完全未涉及的情节

### 任务0：标题
用简体中文写一个短标题（8～20 字为宜），概括本期核心主题；不要用「视频」「转写」「笔记」等空洞词，不要加书名号。

### 任务1：总结笔记
用简体中文写一篇好读的学习笔记（像听完课后自己整理给同学看的那种），要求：
- 开头用 1～2 句话点明「这期大概在讲什么」
- 结构要「该分则分、不该分则合」：叙述与过渡用自然段；真正并列的要点（组件、步骤、对比项、能力清单等）用少量「-」列表，一眼能扫到
- 不要写成 1. / 1.1 / 1.2 的厚大纲或说明书体；也不要整篇纯自然段、把并列信息全揉进长句里
- 全文列表块控制在大约 2～4 处，每处条目宜短；段落与列表穿插即可
- 语气自然、简洁，保留关键信息与专有名词（一律用纠正后的正确写法）
- 篇幅随转写稿长短自然伸缩，不凑字数、不刻意灌水

### 任务2：思维导图
用 **Mermaid flowchart LR** 输出从左到右的树状结构（一级标题 → 二级 → 要点），要求：
- 第一行必须是 `flowchart LR`
- 根节点 id 用 `root`，形如 `root["主题"]`
- 子节点用短 id（如 a / a1 / b），用 `-->` 连接；节点文案放在方括号 `["文案"]` 内
- 最多三层（主题 / 分支 / 要点），文案短而清楚；不要引号嵌套、不要 Markdown 列表符、不要代码围栏
- 专有名词与任务1完全一致
示例形态（内容请换成本期主题）：
flowchart LR
  root["主题"]
  root --> a["分支甲"]
  a --> a1["要点1"]
  a --> a2["要点2"]
  root --> b["分支乙"]
  b --> b1["要点3"]

### 输出格式要求
请严格按下列分隔符输出（不要省略标记）：

【标题】
（你的短标题）

【总结笔记】
（你的总结内容）

【思维导图】
（你的 Mermaid flowchart LR 全文，从 flowchart LR 一行开始）

### 转写稿：
{cleaned_text}
"""


def parse_response(content: str) -> Dict[str, Optional[str]]:
    """
    从模型回复中提取标题、总结笔记与思维导图。
    解析失败时对应字段为 None。
    """
    if not content or not content.strip():
        print("[Qwen] parse_response: empty content")
        return {"title": None, "summary": None, "mindmap": None}

    text = content.strip()

    title: Optional[str] = None
    summary: Optional[str] = None
    mindmap: Optional[str] = None

    m_title = re.search(
        r"【标题】\s*(.*?)(?=【总结笔记】|【思维导图】|$)",
        text,
        flags=re.DOTALL,
    )
    m_summary = re.search(
        r"【总结笔记】\s*(.*?)(?=【思维导图】|$)",
        text,
        flags=re.DOTALL,
    )
    m_mindmap = re.search(
        r"【思维导图】\s*(.*)\Z",
        text,
        flags=re.DOTALL,
    )
    if m_title:
        title = m_title.group(1).strip().splitlines()[0].strip("「」『』\"' ") or None
        if title and len(title) > 40:
            title = title[:40].rstrip()
    if m_summary:
        summary = m_summary.group(1).strip() or None
    if m_mindmap:
        mindmap = m_mindmap.group(1).strip() or None

    if summary is None:
        m = re.search(
            r"(?:总结笔记|Summary)\s*[:：]?\s*(.*?)(?=(?:思维导图|Mind\s*map)|$)",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if m:
            summary = m.group(1).strip() or None
    if mindmap is None:
        m = re.search(
            r"(?:思维导图|Mind\s*map)\s*[:：]?\s*(.*)\Z",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if m:
            mindmap = m.group(1).strip() or None

    if summary is None and mindmap is None and title is None:
        print("[Qwen] parse_response: failed to split fields")
        summary = text

    return {"title": title, "summary": summary, "mindmap": mindmap}


def call_qwen(prompt: str) -> Dict[str, Optional[str]]:
    """
    调用通义千问；失败时返回 title/summary/mindmap 为 None，不抛异常中断流水线。
    """
    empty = {"title": None, "summary": None, "mindmap": None}
    if not settings.DASHSCOPE_API_KEY:
        print("[Qwen] DASHSCOPE_API_KEY 未配置")
        return empty

    dashscope.api_key = settings.DASHSCOPE_API_KEY

    try:
        response = Generation.call(
            model=settings.QWEN_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=settings.QWEN_MAX_TOKENS,
            temperature=0.7,
            result_format="message",
        )

        status = getattr(response, "status_code", None)
        if status == 200:
            content = response.output.choices[0].message.content
            return parse_response(str(content))

        message = getattr(response, "message", response)
        print(f"[Qwen] API error: status={status}, message={message}")
        return empty
    except Exception as exc:  # noqa: BLE001 — 流水线容错
        print(f"[Qwen] Exception: {exc}")
        return empty


def generate_summary_and_mindmap(
    text: str,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """高层接口：清洗稿 → (title, summary, mindmap_markdown)。"""
    if not text or not text.strip():
        return None, None, None
    result = call_qwen(build_prompt(text.strip()))
    return result.get("title"), result.get("summary"), result.get("mindmap")
