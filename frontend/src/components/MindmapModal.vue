<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import mermaid from 'mermaid'
import { toMermaidFlowTree } from '../utils/markdown'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '思维导图' },
  content: { type: String, default: '' },
})

const emit = defineEmits(['close'])

const mode = ref('graph') // graph | code
const renderError = ref('')
const svgHtml = ref('')
const copied = ref(false)
const downloading = ref(false)
const graphHost = ref(null)

mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  securityLevel: 'loose',
  flowchart: {
    htmlLabels: true,
    curve: 'basis',
    padding: 12,
    nodeSpacing: 36,
    rankSpacing: 48,
    useMaxWidth: true,
  },
  themeVariables: {
    fontFamily: 'Source Sans 3, Segoe UI, sans-serif',
    fontSize: '14px',
    lineColor: '#9a5c10',
    primaryBorderColor: '#c47a1a',
  },
})

const codeText = computed(() => toMermaidFlowTree(props.content))

async function renderGraph() {
  renderError.value = ''
  svgHtml.value = ''
  const code = codeText.value
  if (!code) {
    renderError.value = '暂无思维导图内容。'
    return
  }
  try {
    const id = `mm-${Date.now()}-${Math.floor(Math.random() * 1e6)}`
    const { svg } = await mermaid.render(id, code)
    svgHtml.value = svg
    await nextTick()
  } catch (err) {
    console.warn('[mindmap] mermaid render failed', err)
    renderError.value = '导图渲染失败，可切换到「代码」查看原文。'
  }
}

watch(
  () => [props.open, props.content, mode.value],
  async ([open]) => {
    if (!open) return
    if (mode.value === 'graph') await renderGraph()
  },
  { immediate: true },
)

watch(
  () => props.open,
  (open) => {
    if (open) {
      mode.value = 'graph'
      copied.value = false
    }
  },
)

async function copyCode() {
  try {
    await navigator.clipboard.writeText(codeText.value)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 1600)
  } catch {
    copied.value = false
  }
}

async function downloadPng() {
  const svg = graphHost.value?.querySelector?.('svg')
  if (!svg || downloading.value) return
  downloading.value = true
  try {
    const rect = svg.getBoundingClientRect()
    const w = Math.max(svg.width?.baseVal?.value || rect.width || 800, 1)
    const h = Math.max(svg.height?.baseVal?.value || rect.height || 600, 1)
    const clone = svg.cloneNode(true)
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
    if (!clone.getAttribute('width')) clone.setAttribute('width', String(w))
    if (!clone.getAttribute('height')) clone.setAttribute('height', String(h))

    const serializer = new XMLSerializer()
    const svgStr = serializer.serializeToString(clone)
    const blob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(blob)

    await new Promise((resolve, reject) => {
      const img = new Image()
      img.onload = () => {
        const scale = 2
        const canvas = document.createElement('canvas')
        canvas.width = Math.ceil(w * scale)
        canvas.height = Math.ceil(h * scale)
        const ctx = canvas.getContext('2d')
        ctx.fillStyle = '#fffdf7'
        ctx.fillRect(0, 0, canvas.width, canvas.height)
        ctx.setTransform(scale, 0, 0, scale, 0, 0)
        ctx.drawImage(img, 0, 0)
        canvas.toBlob((png) => {
          URL.revokeObjectURL(url)
          if (!png) {
            reject(new Error('png blob failed'))
            return
          }
          const a = document.createElement('a')
          a.href = URL.createObjectURL(png)
          a.download = '思维导图.png'
          a.click()
          setTimeout(() => URL.revokeObjectURL(a.href), 2000)
          resolve()
        }, 'image/png')
      }
      img.onerror = () => {
        URL.revokeObjectURL(url)
        reject(new Error('svg load failed'))
      }
      img.src = url
    })
  } catch (err) {
    console.warn('[mindmap] download png failed', err)
  } finally {
    downloading.value = false
  }
}

function onToolbarAction() {
  if (mode.value === 'code') copyCode()
  else downloadPng()
}

function onBackdrop(event) {
  if (event.target === event.currentTarget) emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="modal" role="dialog" aria-modal="true" @click="onBackdrop">
      <div class="modal__panel">
        <header class="modal__header">
          <h2>{{ title }}</h2>
          <button type="button" class="modal__close" @click="emit('close')">关闭</button>
        </header>

        <div class="modal__toolbar">
          <div class="seg" role="tablist">
            <button
              type="button"
              role="tab"
              :aria-selected="mode === 'graph'"
              :class="{ active: mode === 'graph' }"
              @click="mode = 'graph'"
            >
              图表
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="mode === 'code'"
              :class="{ active: mode === 'code' }"
              @click="mode = 'code'"
            >
              代码
            </button>
          </div>
          <button
            type="button"
            class="tool-action"
            :title="mode === 'code' ? '复制代码' : '下载 PNG'"
            :disabled="mode === 'graph' && downloading"
            @click="onToolbarAction"
          >
            <template v-if="mode === 'code'">
              {{ copied ? '已复制' : '复制' }}
            </template>
            <template v-else>
              <span class="tool-action__icon" aria-hidden="true">⬇</span>
              {{ downloading ? '导出中…' : '下载' }}
            </template>
          </button>
        </div>

        <div class="modal__body">
          <div v-if="mode === 'code'" class="code">
            <p v-if="!content" class="modal__empty">暂无思维导图内容。</p>
            <pre v-else class="modal__pre">{{ codeText }}</pre>
          </div>
          <div v-else class="graph">
            <p v-if="renderError" class="modal__empty">{{ renderError }}</p>
            <div v-else ref="graphHost" class="graph__svg" v-html="svgHtml" />
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: rgba(42, 36, 24, 0.35);
  display: grid;
  place-items: center;
  padding: 24px;
}

.modal__panel {
  width: min(980px, 100%);
  max-height: min(88vh, 860px);
  display: flex;
  flex-direction: column;
  background: var(--color-white);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-edge);
  box-shadow: var(--shadow-soft);
  overflow: hidden;
}

.modal__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 14px 18px 8px;
}

.modal__header h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.2rem;
}

.modal__close {
  border: 1px solid var(--color-edge);
  background: transparent;
  border-radius: 999px;
  padding: 6px 12px;
  cursor: pointer;
  font-weight: 600;
}

.modal__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 18px 12px;
}

.seg {
  display: inline-flex;
  padding: 3px;
  border-radius: 10px;
  background: rgba(42, 36, 24, 0.08);
  gap: 2px;
}

.seg button {
  border: none;
  background: transparent;
  padding: 6px 14px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  color: var(--color-ink-muted);
  transition: background 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
}

.seg button.active {
  background: var(--color-white);
  color: var(--color-ink);
  box-shadow: 0 1px 4px rgba(42, 36, 24, 0.12);
}

.tool-action {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  background: transparent;
  color: var(--color-ink-muted);
  font-weight: 600;
  cursor: pointer;
  padding: 6px 8px;
}

.tool-action:hover:not(:disabled) {
  color: var(--color-amber-deep);
}

.tool-action:disabled {
  opacity: 0.55;
  cursor: wait;
}

.tool-action__icon {
  font-size: 0.95rem;
  line-height: 1;
}

.modal__body {
  padding: 8px 20px 22px;
  overflow: auto;
  flex: 1;
  min-height: 0;
}

.modal__empty {
  color: var(--color-ink-muted);
}

.modal__pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.9rem;
  line-height: 1.55;
  background: rgba(42, 36, 24, 0.04);
  border-radius: 12px;
  padding: 14px 16px;
}

.graph {
  display: flex;
  justify-content: flex-start;
  min-height: 220px;
  overflow: auto;
}

.graph__svg {
  width: 100%;
  min-width: max-content;
}

.graph__svg :deep(svg) {
  max-width: none;
  height: auto;
}

.graph__svg :deep(.nodeLabel) {
  font-family: var(--font-body);
}
</style>
