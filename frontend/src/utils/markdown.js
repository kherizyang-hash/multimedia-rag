import { marked } from 'marked'

marked.setOptions({
  gfm: true,
  breaks: true,
})

/** 将 Markdown 转为安全可用的 HTML（仅渲染，不做 XSS 清洗到极致；内容来自本站 AI）。 */
export function renderMarkdown(text) {
  if (!text) return ''
  return marked.parse(String(text))
}

function escapeLabel(label) {
  return String(label || '')
    .replace(/[\[\](){}|"\\]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 48)
}

function parseTreeItems(raw) {
  const text = String(raw || '').trim()
  if (!text) return null

  const fenced = text.match(/```(?:mermaid)?\s*([\s\S]*?)```/i)
  const body = (fenced ? fenced[1] : text).trim()

  // mindmap 语法 → 树
  if (/^mindmap\b/i.test(body)) {
    const lines = body.split('\n').slice(1)
    const items = []
    for (const rawLine of lines) {
      const line = rawLine.replace(/\t/g, '  ')
      if (!line.trim()) continue
      const m = line.match(/^( *)(.*)$/)
      if (!m) continue
      const spaces = m[1].length
      let label = m[2].trim()
      const root = label.match(/^root\(\((.*)\)\)$/)
      if (root) label = root[1]
      label = label.replace(/^\(+|\)+$/g, '').trim()
      if (!label) continue
      // mindmap: 2 spaces per level; root line often 2 spaces
      const level = Math.max(0, Math.floor(spaces / 2) - 1)
      items.push({ level, label: escapeLabel(label) })
    }
    return items.length ? items : null
  }

  // flowchart 已有 → 不当树解析，返回 null 让调用方原样用
  if (/^(flowchart|graph)\b/i.test(body)) {
    return { rawFlow: body }
  }

  // Markdown 列表
  const lines = body.split('\n')
  const items = []
  for (const rawLine of lines) {
    const line = rawLine.replace(/\t/g, '  ')
    const m = line.match(/^(\s*)([-*+]|\d+\.)\s+(.*)$/)
    if (!m) continue
    const indent = m[1].length
    const level = Math.floor(indent / 2)
    const label = escapeLabel(m[3])
    if (!label) continue
    items.push({ level, label })
  }
  return items.length ? items : null
}

/**
 * 转为从左到右的 Mermaid flowchart（一级→二级→要点），带鲜明配色。
 * 「代码」面板也展示此语法，便于复制。
 */
export function toMermaidFlowTree(raw) {
  const parsed = parseTreeItems(raw)
  if (!parsed) {
    const safe = escapeLabel(String(raw || '').slice(0, 40)) || '导图'
    return buildFlow([{ level: 0, label: safe }])
  }
  if (parsed.rawFlow) return parsed.rawFlow
  return buildFlow(parsed)
}

function buildFlow(items) {
  // 规范化：若首项为根且其余更深，保持；否则整体 +0
  let rootLabel = items[0]?.label || '导图'
  let start = 0
  if (items.length > 1 && items[0].level === 0 && items.slice(1).every((it) => it.level > 0)) {
    start = 1
  } else if (items[0] && items.every((it) => it.level >= items[0].level)) {
    rootLabel = items[0].label
    start = 1
  }

  const lines = [
    'flowchart LR',
    `  root["${rootLabel}"]:::lv0`,
  ]

  const stack = [{ level: -1, id: 'root' }]
  let seq = 0

  for (let i = start; i < items.length; i += 1) {
    const { level, label } = items[i]
    const depth = Math.min(3, Math.max(0, level))
    while (stack.length && stack[stack.length - 1].level >= depth) {
      stack.pop()
    }
    const parent = stack[stack.length - 1]?.id || 'root'
    const id = `n${seq}`
    seq += 1
    const cls = `lv${Math.min(depth + 1, 3)}`
    lines.push(`  ${id}["${label}"]:::${cls}`)
    lines.push(`  ${parent} --> ${id}`)
    stack.push({ level: depth, id })
  }

  lines.push(
    '  classDef lv0 fill:#1f6f5b,stroke:#155a4a,color:#fff,stroke-width:1px',
    '  classDef lv1 fill:#c47a1a,stroke:#9a5c10,color:#fff,stroke-width:1px',
    '  classDef lv2 fill:#2f6fed,stroke:#1f54c4,color:#fff,stroke-width:1px',
    '  classDef lv3 fill:#e8f0fe,stroke:#2f6fed,color:#1a2b4a,stroke-width:1px',
  )

  return lines.join('\n')
}

/** @deprecated 兼容旧调用名 */
export function toMermaidMindmap(raw) {
  return toMermaidFlowTree(raw)
}
