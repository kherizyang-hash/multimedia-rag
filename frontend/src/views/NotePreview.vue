<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { chatOnNote, deleteNote, getNote, permanentizeNote } from '../api'
import { formatDateTime } from '../utils/format'
import { getNoteChat, upsertNoteChat } from '../utils/chatStore'
import { renderMarkdown } from '../utils/markdown'
import BackLink from '../components/BackLink.vue'
import ChatWindow from '../components/ChatWindow.vue'
import ConfirmModal from '../components/ConfirmModal.vue'
import MindmapModal from '../components/MindmapModal.vue'
import TranscriptModal from '../components/TranscriptModal.vue'

const DEFAULT_LEFT_PCT = 55

const route = useRoute()
const router = useRouter()

const note = ref(null)
const loading = ref(true)
const error = ref('')
const actionBusy = ref(false)
const chatLoading = ref(false)
const messages = ref([])
const mindmapOpen = ref(false)
const transcriptOpen = ref(false)

/** 布局：默认只看笔记；chatOpen 展开右侧对话 */
const chatOpen = ref(false)
const noteCollapsed = ref(false)
const leftPct = ref(DEFAULT_LEFT_PCT)
const splitterHover = ref(false)

const confirmState = ref({
  open: false,
  mode: '', // permanentize | delete
  title: '',
  message: '',
  danger: false,
})

const progress = ref({
  visible: false,
  pct: 0,
  text: '',
})

const noteId = computed(() => String(route.params.id || ''))

const summaryHtml = computed(() => renderMarkdown(note.value?.summary || ''))

const layoutMode = computed(() => {
  if (noteCollapsed.value && chatOpen.value) return 'chat-only'
  if (!chatOpen.value) return 'note-only'
  return 'split'
})

const leftStyle = computed(() => {
  if (layoutMode.value === 'note-only') return { width: '100%' }
  if (layoutMode.value === 'chat-only') return { width: '0px', display: 'none' }
  return { width: `${leftPct.value}%` }
})

const rightStyle = computed(() => {
  if (layoutMode.value === 'note-only') return { width: '0px', display: 'none' }
  if (layoutMode.value === 'chat-only') return { width: '100%' }
  return { width: `${100 - leftPct.value}%` }
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    note.value = await getNote(noteId.value)
    const saved = getNoteChat(noteId.value)
    messages.value = saved?.messages ? [...saved.messages] : []
  } catch (err) {
    note.value = null
    error.value = err?.response?.data?.detail || err?.message || '加载笔记失败'
  } finally {
    loading.value = false
  }
}

function persistMessages() {
  if (!note.value) return
  const name = note.value.title || '未命名'
  upsertNoteChat({
    noteId: noteId.value,
    title: `讨论「${name}」`,
    messages: messages.value,
  })
}

function applyChatQuery() {
  if (route.query.chat === '1' || route.query.chat === 'true') {
    chatOpen.value = true
    noteCollapsed.value = false
    leftPct.value = DEFAULT_LEFT_PCT
  }
}

watch(noteId, () => {
  messages.value = []
  chatOpen.value = false
  noteCollapsed.value = false
  leftPct.value = DEFAULT_LEFT_PCT
  load().then(applyChatQuery)
})

onMounted(() => {
  load().then(applyChatQuery)
})

function openChat() {
  chatOpen.value = true
  noteCollapsed.value = false
  leftPct.value = DEFAULT_LEFT_PCT
}

function collapseChat() {
  chatOpen.value = false
  noteCollapsed.value = false
}

/** 展开笔记：宽度恢复默认，而非收起前的值 */
function expandNote() {
  noteCollapsed.value = false
  leftPct.value = DEFAULT_LEFT_PCT
}

function collapseNote() {
  noteCollapsed.value = true
}

function askPermanentize() {
  if (!note.value || note.value.is_permanent || actionBusy.value) return
  confirmState.value = {
    open: true,
    mode: 'permanentize',
    title: '存入知识库',
    message: '将此笔记切片并写入向量库，之后可参与全局问答。是否继续？',
    danger: false,
  }
}

function askDelete() {
  if (!note.value || actionBusy.value) return
  confirmState.value = {
    open: true,
    mode: 'delete',
    title: '删除笔记',
    message: '确定删除这篇笔记？此操作不可恢复，并会清理对应向量。',
    danger: true,
  }
}

function closeConfirm() {
  confirmState.value.open = false
}

async function onConfirm() {
  const mode = confirmState.value.mode
  closeConfirm()
  if (mode === 'permanentize') await doPermanentize()
  if (mode === 'delete') await doDelete()
}

function runProgress(label) {
  progress.value = { visible: true, pct: 8, text: label }
  const timer = setInterval(() => {
    if (progress.value.pct >= 90) return
    progress.value.pct += Math.random() * 8 + 2
  }, 400)
  return () => {
    clearInterval(timer)
    progress.value.pct = 100
    progress.value.text = '完成'
    setTimeout(() => {
      progress.value.visible = false
      progress.value.pct = 0
    }, 450)
  }
}

async function doPermanentize() {
  actionBusy.value = true
  error.value = ''
  const stop = runProgress('正在切片并写入知识库…')
  try {
    note.value = await permanentizeNote(note.value.id)
  } catch (err) {
    error.value = err?.response?.data?.detail || err?.message || '入库失败'
  } finally {
    stop()
    actionBusy.value = false
  }
}

async function doDelete() {
  actionBusy.value = true
  try {
    await deleteNote(note.value.id)
    router.push({ name: 'notes' })
  } catch (err) {
    error.value = err?.response?.data?.detail || err?.message || '删除失败'
    actionBusy.value = false
  }
}

async function onSend(text) {
  messages.value.push({ role: 'user', content: text })
  persistMessages()
  chatLoading.value = true
  error.value = ''
  try {
    const history = messages.value
      .slice(0, -1)
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ role: m.role, content: m.content }))
    const res = await chatOnNote({
      note_id: noteId.value,
      query: text,
      history,
    })
    messages.value.push({
      role: 'assistant',
      content: res.answer,
      sources: res.sources || [],
    })
    persistMessages()
  } catch (err) {
    messages.value.push({
      role: 'assistant',
      content: `回答失败：${err?.response?.data?.detail || err?.message || '未知错误'}`,
    })
    persistMessages()
  } finally {
    chatLoading.value = false
  }
}

/** 拖动分割线 */
const dragging = ref(false)

function onSplitterDown(event) {
  if (layoutMode.value !== 'split') return
  // 点箭头不进入拖动
  if (event.target?.closest?.('.splitter__btn')) return
  dragging.value = true
  event.preventDefault()
}

function onMove(event) {
  if (!dragging.value) return
  const root = document.querySelector('.preview')
  if (!root) return
  const rect = root.getBoundingClientRect()
  const x = event.clientX - rect.left
  const pct = (x / rect.width) * 100

  if (pct < 18) {
    collapseNote()
    dragging.value = false
    return
  }
  if (pct > 82) {
    collapseChat()
    dragging.value = false
    return
  }
  leftPct.value = Math.min(78, Math.max(22, pct))
}

function onUp() {
  dragging.value = false
}

onMounted(() => {
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
})

onUnmounted(() => {
  window.removeEventListener('pointermove', onMove)
  window.removeEventListener('pointerup', onUp)
})
</script>

<template>
  <main class="preview" :class="{ 'preview--dragging': dragging }">
    <div v-if="progress.visible" class="top-progress" aria-live="polite">
      <div class="top-progress__bar">
        <span :style="{ width: `${Math.min(progress.pct, 100)}%` }" />
      </div>
      <p>{{ progress.text }}</p>
    </div>

    <p v-if="loading" class="preview__banner">加载中…</p>
    <p v-else-if="error && !note" class="preview__banner preview__banner--err">{{ error }}</p>

    <template v-else-if="note">
      <section class="preview__left" :style="leftStyle">
        <div class="preview__left-scroll">
          <div class="preview__toolbar">
            <div class="preview__toolbar-inner">
              <BackLink fallback="/notes" />
              <div class="preview__actions">
                <button
                  type="button"
                  class="btn btn--ghost"
                  :disabled="actionBusy || note.is_permanent"
                  @click="askPermanentize"
                >
                  {{ note.is_permanent ? '已入库' : '存入知识库' }}
                </button>
                <button type="button" class="btn btn--ghost" @click="mindmapOpen = true">
                  思维导图
                </button>
                <button
                  type="button"
                  class="btn btn--danger"
                  :disabled="actionBusy"
                  @click="askDelete"
                >
                  删除
                </button>
              </div>
            </div>
          </div>

          <div class="preview__reading">
            <h1 class="preview__title">{{ note.title }}</h1>
            <div class="preview__meta">
              <span>{{ formatDateTime(note.updated_at || note.created_at) }}</span>
              <span class="tag">{{ note.category }}</span>
              <span class="tag" :class="note.is_permanent ? 'tag--perm' : 'tag--temp'">
                {{ note.is_permanent ? '永久' : '临时' }}
              </span>
              <a
                v-if="note.source_url"
                class="meta-link"
                :href="note.source_url"
                target="_blank"
                rel="noopener"
              >来源链接</a>
              <button
                v-if="note.cleaned_text"
                type="button"
                class="meta-link meta-link--btn"
                @click="transcriptOpen = true"
              >
                查看原文稿
              </button>
            </div>
            <p v-if="error" class="preview__inline-err">{{ error }}</p>
            <article class="preview__body" v-html="summaryHtml" />
          </div>
        </div>
      </section>

      <div
        v-if="layoutMode === 'split'"
        class="splitter"
        :class="{ 'splitter--hot': splitterHover || dragging }"
        title="拖动调节宽度"
        @pointerdown="onSplitterDown"
        @pointerenter="splitterHover = true"
        @pointerleave="splitterHover = false"
      >
        <div class="splitter__rail" />
        <div class="splitter__controls" @pointerdown.stop>
          <button
            type="button"
            class="splitter__btn"
            title="收起笔记"
            @click="collapseNote"
          >
            ‹
          </button>
          <button
            type="button"
            class="splitter__btn"
            title="收起对话"
            @click="collapseChat"
          >
            ›
          </button>
        </div>
      </div>

      <aside v-if="chatOpen" class="preview__right" :style="rightStyle">
        <!-- chat-only：左侧贴边展开笔记 -->
        <button
          v-if="noteCollapsed"
          type="button"
          class="edge-expand"
          title="展开笔记"
          @click="expandNote"
        >
          ›
        </button>

        <header class="preview__chat-head">
          <h2>笔记内讨论</h2>
          <p>基于本篇内容提问</p>
        </header>
        <div class="preview__chat-body">
          <ChatWindow
            :messages="messages"
            :loading="chatLoading"
            placeholder="针对这篇笔记提问…"
            @send="onSend"
          />
        </div>
      </aside>

      <Teleport to="body">
        <button
          v-if="!chatOpen"
          type="button"
          class="fab"
          title="打开讨论"
          @click="openChat"
        >
          AI
        </button>
      </Teleport>
    </template>

    <MindmapModal
      :open="mindmapOpen"
      :content="note?.mindmap || ''"
      @close="mindmapOpen = false"
    />
    <TranscriptModal
      :open="transcriptOpen"
      :content="note?.cleaned_text || ''"
      @close="transcriptOpen = false"
    />
    <ConfirmModal
      :open="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :danger="confirmState.danger"
      @confirm="onConfirm"
      @cancel="closeConfirm"
    />
  </main>
</template>

<style scoped>
.preview {
  position: relative;
  display: flex;
  width: 100%;
  max-width: 1100px;
  height: 100vh;
  margin: 0 auto;
  overflow: hidden;
  background: transparent;
}

.preview--dragging {
  cursor: col-resize;
  user-select: none;
}

.top-progress {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 25;
  padding: 8px 16px 6px;
  background: color-mix(in srgb, var(--color-paper) 78%, transparent);
  backdrop-filter: blur(8px);
}

.top-progress__bar {
  height: 6px;
  border-radius: 999px;
  background: rgba(42, 36, 24, 0.08);
  overflow: hidden;
}

.top-progress__bar span {
  display: block;
  height: 100%;
  background: var(--color-amber);
  transition: width 0.25s ease;
}

.top-progress p {
  margin: 6px 0 0;
  font-size: 0.85rem;
  color: var(--color-ink-muted);
}

.preview__banner {
  margin: 40px 24px;
  color: var(--color-ink-muted);
}

.preview__banner--err {
  color: #9b2c2c;
}

.preview__left {
  flex: 0 0 auto;
  min-width: 0;
  height: 100%;
  background: transparent;
}

.preview__left-scroll {
  height: 100%;
  overflow: auto;
  padding: 0 0 64px;
}

.preview__toolbar {
  position: sticky;
  top: 0;
  z-index: 12;
  padding: 16px 24px 28px;
  background: transparent;
}

.preview__toolbar::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background: linear-gradient(
    0deg,
    color-mix(in srgb, var(--color-paper) 0%, transparent) 0%,
    color-mix(in srgb, var(--color-paper) 35%, transparent) 32%,
    color-mix(in srgb, var(--color-paper) 58%, transparent) 100%
  );
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  -webkit-mask-image: linear-gradient(
    0deg,
    transparent 0%,
    rgba(0, 0, 0, 0.45) 22%,
    #000 48%,
    #000 100%
  );
  mask-image: linear-gradient(
    0deg,
    transparent 0%,
    rgba(0, 0, 0, 0.45) 22%,
    #000 48%,
    #000 100%
  );
}

.preview__toolbar-inner {
  position: relative;
  z-index: 1;
  width: 100%;
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.preview__reading {
  width: 100%;
  margin: 0;
  padding: 8px 24px 0;
  box-sizing: border-box;
}

.preview__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.btn {
  border: none;
  border-radius: 999px;
  padding: 8px 14px;
  font-weight: 600;
  cursor: pointer;
}

.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn--ghost {
  background: transparent;
  border: 1.5px solid var(--color-edge);
  color: var(--color-ink);
}

.btn--danger {
  background: #8f2f2f;
  color: #fff;
}

.preview__title {
  margin: 0 0 12px;
  font-family: var(--font-display);
  font-size: clamp(1.55rem, 2.4vw, 2rem);
  line-height: 1.35;
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: normal;
  max-width: 100%;
}

.preview__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 14px;
  margin-bottom: 20px;
  color: var(--color-ink-muted);
  font-size: 0.9rem;
}

.meta-link {
  color: var(--color-amber-deep);
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
}

.meta-link--btn {
  border: none;
  background: none;
  padding: 0;
  cursor: pointer;
  font: inherit;
  color: var(--color-amber-deep);
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
}

.meta-link--btn:hover,
.meta-link:hover {
  color: var(--color-amber);
}

.tag {
  border: 1px solid var(--color-edge);
  border-radius: 999px;
  padding: 1px 8px;
}

.tag--perm {
  background: rgba(196, 122, 26, 0.14);
  border-color: transparent;
  color: var(--color-amber-deep);
}

.tag--temp {
  background: rgba(92, 83, 70, 0.08);
}

.preview__inline-err {
  color: #9b2c2c;
  margin: 0 0 12px;
}

.preview__body {
  word-break: break-word;
  font-size: 1.05rem;
  line-height: 1.7;
  color: var(--color-ink);
}

.preview__body :deep(p) {
  margin: 0 0 1em;
}

.preview__body :deep(p:last-child) {
  margin-bottom: 0;
}

.preview__body :deep(ul),
.preview__body :deep(ol) {
  margin: 0.35em 0 1em;
  padding-left: 1.35em;
}

.preview__body :deep(li) {
  margin: 0.25em 0;
}

.preview__body :deep(strong) {
  font-weight: 700;
}

.splitter {
  flex: 0 0 14px;
  position: relative;
  z-index: 8;
  cursor: col-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
}

.splitter__rail {
  width: 2px;
  height: 100%;
  background: var(--color-edge);
  transition: background 0.15s ease, width 0.15s ease;
}

.splitter--hot .splitter__rail,
.splitter:hover .splitter__rail {
  width: 3px;
  background: var(--color-amber);
}

.splitter__controls {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  gap: 2px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
}

.splitter--hot .splitter__controls,
.splitter:hover .splitter__controls {
  opacity: 1;
  pointer-events: auto;
}

.splitter__btn {
  width: 22px;
  height: 36px;
  border: 1px solid var(--color-edge);
  border-radius: 8px;
  background: var(--color-white);
  color: var(--color-ink);
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(42, 36, 24, 0.1);
}

.splitter__btn:hover {
  border-color: var(--color-amber);
  color: var(--color-amber-deep);
}

.preview__right {
  position: relative;
  flex: 0 0 auto;
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: transparent;
  overflow: hidden;
}

.preview__chat-head {
  flex: 0 0 auto;
  padding: 18px 18px 10px;
}

.preview__chat-head h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.15rem;
}

.preview__chat-head p {
  margin: 4px 0 0;
  color: var(--color-ink-muted);
  font-size: 0.88rem;
}

.preview__chat-body {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  width: 100%;
  margin: 0;
}

.preview__chat-body :deep(.chat) {
  flex: 1;
  min-height: 0;
}

.edge-expand {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  z-index: 6;
  width: 18px;
  height: 52px;
  border: 1px solid var(--color-edge);
  border-left: none;
  background: var(--color-white);
  color: var(--color-ink);
  font-size: 1rem;
  cursor: pointer;
  border-radius: 0 8px 8px 0;
  box-shadow: 2px 0 10px rgba(42, 36, 24, 0.08);
}

.edge-expand:hover {
  color: var(--color-amber-deep);
  border-color: var(--color-amber);
}

.fab {
  position: fixed;
  right: 28px;
  bottom: 28px;
  width: 56px;
  height: 56px;
  border: none;
  border-radius: 50%;
  background: var(--color-ink);
  color: var(--color-paper);
  font-family: var(--font-display);
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 10px 28px rgba(42, 36, 24, 0.22);
  transition: transform 0.15s ease, background 0.15s ease;
  z-index: 40;
}

.fab:hover {
  background: var(--color-amber-deep);
  transform: translateY(-2px);
  color: var(--color-white);
}

@media (max-width: 720px) {
  .preview {
    max-width: 100%;
  }

  .preview__toolbar,
  .preview__reading {
    padding-left: 16px;
    padding-right: 16px;
  }
}
</style>
