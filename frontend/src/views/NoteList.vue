<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { deleteNote, listNotes, permanentizeNote } from '../api'
import BackLink from '../components/BackLink.vue'
import ConfirmModal from '../components/ConfirmModal.vue'
import NoteCard from '../components/NoteCard.vue'

const router = useRouter()

const loading = ref(true)
const error = ref('')
const busy = ref(false)
const notes = ref([])
const selected = ref(new Set())
const category = ref('')
const permanence = ref('all') // all | temp | permanent
const confirmState = ref({ open: false, mode: '', title: '', message: '', danger: false })
const progress = ref({ visible: false, pct: 0, text: '' })

const categories = computed(() => {
  const set = new Set()
  for (const n of notes.value) {
    if (n.category) set.add(n.category)
  }
  return [...set].sort()
})

const filtered = computed(() => {
  return notes.value.filter((n) => {
    if (category.value && n.category !== category.value) return false
    if (permanence.value === 'temp' && n.is_permanent) return false
    if (permanence.value === 'permanent' && !n.is_permanent) return false
    return true
  })
})

const selectedCount = computed(() => selected.value.size)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await listNotes()
    notes.value = data.items || []
    // 清理已不存在的选中项
    const ids = new Set(notes.value.map((n) => n.id))
    selected.value = new Set([...selected.value].filter((id) => ids.has(id)))
  } catch (err) {
    error.value = err?.response?.data?.detail || err?.message || '加载笔记失败'
  } finally {
    loading.value = false
  }
}

function onSelect({ note, checked }) {
  const next = new Set(selected.value)
  if (checked) next.add(note.id)
  else next.delete(note.id)
  selected.value = next
}

function openNote(note) {
  router.push({ name: 'note-preview', params: { id: note.id } })
}

function batchPermanentize() {
  const ids = [...selected.value]
  if (!ids.length) return
  const targets = notes.value.filter((n) => ids.includes(n.id) && !n.is_permanent)
  if (!targets.length) {
    error.value = '选中的笔记均已入库'
    return
  }
  confirmState.value = {
    open: true,
    mode: 'permanentize',
    title: '批量入库',
    message: `将 ${targets.length} 条临时笔记存入知识库？`,
    danger: false,
  }
}

function batchDelete() {
  const ids = [...selected.value]
  if (!ids.length) return
  confirmState.value = {
    open: true,
    mode: 'delete',
    title: '批量删除',
    message: `确定删除选中的 ${ids.length} 条笔记？此操作不可恢复。`,
    danger: true,
  }
}

function closeConfirm() {
  confirmState.value.open = false
}

function runProgress(label) {
  progress.value = { visible: true, pct: 8, text: label }
  const timer = setInterval(() => {
    if (progress.value.pct >= 90) return
    progress.value.pct += Math.random() * 8 + 2
  }, 350)
  return () => {
    clearInterval(timer)
    progress.value.pct = 100
    setTimeout(() => {
      progress.value.visible = false
      progress.value.pct = 0
    }, 400)
  }
}

async function onConfirm() {
  const mode = confirmState.value.mode
  closeConfirm()
  if (mode === 'permanentize') {
    const ids = [...selected.value]
    const targets = notes.value.filter((n) => ids.includes(n.id) && !n.is_permanent)
    busy.value = true
    error.value = ''
    const stop = runProgress('正在批量写入知识库…')
    try {
      for (const n of targets) {
        await permanentizeNote(n.id)
      }
      selected.value = new Set()
      await load()
    } catch (err) {
      error.value = err?.response?.data?.detail || err?.message || '入库失败'
    } finally {
      stop()
      busy.value = false
    }
  }
  if (mode === 'delete') {
    const ids = [...selected.value]
    busy.value = true
    error.value = ''
    try {
      for (const id of ids) {
        await deleteNote(id)
      }
      selected.value = new Set()
      await load()
    } catch (err) {
      error.value = err?.response?.data?.detail || err?.message || '删除失败'
    } finally {
      busy.value = false
    }
  }
}

onMounted(load)
</script>

<template>
  <main class="page">
    <div v-if="progress.visible" class="top-progress">
      <div class="top-progress__bar"><span :style="{ width: `${Math.min(progress.pct, 100)}%` }" /></div>
      <p>{{ progress.text }}</p>
    </div>
    <header class="page__header">
      <div>
        <BackLink fallback="/" />
        <h1 class="page__title">笔记列表</h1>
      </div>
      <div class="page__tools">
        <label class="page__filter">
          <span>分类</span>
          <select v-model="category">
            <option value="">全部</option>
            <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
        <label class="page__filter">
          <span>状态</span>
          <select v-model="permanence">
            <option value="all">全部</option>
            <option value="temp">临时</option>
            <option value="permanent">永久</option>
          </select>
        </label>
        <button
          type="button"
          class="btn btn--ghost"
          :disabled="busy || !selectedCount"
          @click="batchPermanentize"
        >
          入库
        </button>
        <button
          type="button"
          class="btn btn--danger"
          :disabled="busy || !selectedCount"
          @click="batchDelete"
        >
          删除
        </button>
      </div>
    </header>

    <p v-if="selectedCount" class="page__hint">已选 {{ selectedCount }} 条</p>
    <p v-if="error" class="page__error" role="alert">{{ error }}</p>
    <p v-if="loading" class="page__hint">加载中…</p>

    <section v-else-if="!filtered.length" class="page__empty">
      <p>还没有笔记。去首页上传一段视频吧。</p>
      <RouterLink class="btn" to="/">去上传</RouterLink>
    </section>

    <section v-else class="page__grid">
      <NoteCard
        v-for="note in filtered"
        :key="note.id"
        :note="note"
        :selected="selected.has(note.id)"
        @select="onSelect"
        @open="openNote"
      />
    </section>

    <Teleport to="body">
      <RouterLink class="fab" to="/chat" title="全局问答">AI</RouterLink>
    </Teleport>
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
.page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 40px 24px 96px;
  position: relative;
  animation: rise-in 0.55s ease both;
}

.top-progress {
  position: sticky;
  top: 0;
  z-index: 10;
  margin: -12px 0 16px;
  padding: 8px 0 6px;
  background: rgba(255, 248, 235, 0.92);
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
  background: linear-gradient(90deg, var(--color-amber), #e0a04a);
}

.top-progress p {
  margin: 6px 0 0;
  font-size: 0.85rem;
  color: var(--color-ink-muted);
}

.page__header {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 22px;
}

.page__title {
  margin: 8px 0 0;
  font-family: var(--font-display);
  font-size: clamp(1.8rem, 3vw, 2.3rem);
  font-weight: 800;
}

.page__tools {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 10px;
}

.page__filter {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.8rem;
  color: var(--color-ink-muted);
}

.page__filter select {
  min-width: 110px;
  border: 1px solid var(--color-edge);
  border-radius: 999px;
  background: var(--color-white);
  padding: 8px 12px;
  color: var(--color-ink);
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 999px;
  padding: 9px 16px;
  background: var(--color-ink);
  color: var(--color-paper);
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
}

.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn--ghost {
  background: transparent;
  color: var(--color-ink);
  border: 1.5px solid var(--color-edge);
}

.btn--danger {
  background: #8f2f2f;
}

.page__hint {
  color: var(--color-ink-muted);
  margin: 0 0 12px;
}

.page__error {
  color: #9b2c2c;
  margin: 0 0 12px;
  font-weight: 500;
}

.page__empty {
  border: 1px dashed var(--color-edge);
  border-radius: var(--radius-lg);
  padding: 48px 24px;
  text-align: center;
  background: rgba(255, 253, 247, 0.7);
}

.page__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.fab {
  position: fixed;
  right: 28px;
  bottom: 28px;
  width: 56px;
  height: 56px;
  border: none;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--color-ink);
  color: var(--color-paper);
  font-family: var(--font-display);
  font-weight: 700;
  text-decoration: none;
  box-shadow: 0 10px 28px rgba(42, 36, 24, 0.22);
  transition: transform 0.15s ease, background 0.15s ease;
  z-index: 40;
}

.fab:hover {
  background: var(--color-amber-deep);
  transform: translateY(-2px);
  color: var(--color-white);
}

@keyframes rise-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
</style>
