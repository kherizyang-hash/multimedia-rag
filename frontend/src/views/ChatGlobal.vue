<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { chatGlobal } from '../api'
import BackLink from '../components/BackLink.vue'
import ChatWindow from '../components/ChatWindow.vue'
import SourceSelector from '../components/SourceSelector.vue'
import { createChat, loadChats, saveChats } from '../utils/chatStore'

const router = useRouter()

const chats = ref([])
const activeId = ref('')
const sidebarCollapsed = ref(false)
const selectorOpen = ref(false)
const chatLoading = ref(false)
const error = ref('')

const activeChat = computed(() => chats.value.find((c) => c.id === activeId.value) || null)

const sortedChats = computed(() =>
  [...chats.value].sort(
    (a, b) => new Date(b.updatedAt || 0).getTime() - new Date(a.updatedAt || 0).getTime(),
  ),
)

function displayTitle(c) {
  if (c.type === 'note') {
    const raw = String(c.title || '')
    if (raw.startsWith('讨论「') && raw.endsWith('」')) return raw
    const name = raw.replace(/^笔记[:：]\s*/, '') || '未命名'
    return `讨论「${name}」`
  }
  return c.title || '新对话'
}

function persist() {
  saveChats(chats.value)
}

function ensureActive() {
  const globals = chats.value.filter((c) => c.type !== 'note')
  if (!globals.length) {
    const chat = createChat({ type: 'global' })
    chats.value = [chat, ...chats.value.filter((c) => c.type === 'note')]
    activeId.value = chat.id
    persist()
    return
  }
  if (!activeId.value || !chats.value.some((c) => c.id === activeId.value && c.type !== 'note')) {
    activeId.value = globals[0].id
  }
}

function reload() {
  chats.value = loadChats()
  ensureActive()
}

function newChat() {
  const chat = createChat({ type: 'global' })
  chats.value = [chat, ...chats.value]
  activeId.value = chat.id
  sidebarCollapsed.value = false
  persist()
}

function selectChat(c) {
  if (c.type === 'note' && c.noteId) {
    router.push({
      name: 'note-preview',
      params: { id: c.noteId },
      query: { chat: '1' },
    })
    return
  }
  activeId.value = c.id
}

function removeChat(id) {
  chats.value = chats.value.filter((c) => c.id !== id)
  ensureActive()
  persist()
}

function updateActive(mutator) {
  chats.value = chats.value.map((c) => {
    if (c.id !== activeId.value) return c
    const next = mutator({ ...c, messages: [...(c.messages || [])] })
    next.updatedAt = new Date().toISOString()
    return next
  })
  persist()
}

function onNoteIdsUpdate(ids) {
  updateActive((c) => {
    c.noteIds = ids
    return c
  })
}

async function onSend(text) {
  if (!activeChat.value || activeChat.value.type === 'note') return
  updateActive((c) => {
    c.messages.push({ role: 'user', content: text })
    if (c.title === '新对话') {
      c.title = text.slice(0, 24) || '新对话'
    }
    return c
  })

  chatLoading.value = true
  error.value = ''
  try {
    const current = chats.value.find((c) => c.id === activeId.value)
    const history = (current?.messages || [])
      .slice(0, -1)
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ role: m.role, content: m.content }))

    const payload = {
      query: text,
      history,
      note_ids: current?.noteIds?.length ? current.noteIds : null,
    }

    const res = await chatGlobal(payload)
    updateActive((c) => {
      c.messages.push({
        role: 'assistant',
        content: res.answer,
        sources: res.sources || [],
      })
      return c
    })
  } catch (err) {
    updateActive((c) => {
      c.messages.push({
        role: 'assistant',
        content: `回答失败：${err?.response?.data?.detail || err?.message || '未知错误'}`,
      })
      return c
    })
  } finally {
    chatLoading.value = false
  }
}

onMounted(reload)

watch(activeId, () => {
  error.value = ''
})
</script>

<template>
  <main class="chat-page" :class="{ 'chat-page--collapse': sidebarCollapsed }">
    <aside v-show="!sidebarCollapsed" class="sidebar">
      <div class="sidebar__head">
        <BackLink fallback="/" />
        <button
          type="button"
          class="sidebar__icon"
          title="收起历史对话"
          @click="sidebarCollapsed = true"
        >
          «
        </button>
      </div>

      <button type="button" class="sidebar__new" @click="newChat">
        <span class="sidebar__plus">+</span>
        开启新对话
      </button>

      <p class="sidebar__label">历史对话</p>
      <ul class="sidebar__list">
        <li
          v-for="c in sortedChats"
          :key="c.id"
          :class="{ active: c.id === activeId && c.type !== 'note' }"
        >
          <button type="button" class="sidebar__item" :title="displayTitle(c)" @click="selectChat(c)">
            {{ displayTitle(c) }}
          </button>
          <button
            type="button"
            class="sidebar__del"
            title="删除对话"
            @click="removeChat(c.id)"
          >
            ×
          </button>
        </li>
      </ul>
    </aside>

    <!-- 收起后：左上角展开 + 新对话 -->
    <div v-if="sidebarCollapsed" class="rail">
      <button type="button" class="rail__btn" title="展开历史对话" @click="sidebarCollapsed = false">
        ☰
      </button>
      <button type="button" class="rail__btn" title="开启新对话" @click="newChat">+</button>
    </div>

    <section class="main">
      <div class="main__shell">
        <header class="main__head">
          <h1>全局问答</h1>
          <button type="button" class="btn btn--ghost" @click="selectorOpen = true">
            选择笔记
          </button>
        </header>

        <p v-if="activeChat?.noteIds?.length" class="main__picked">
          已限定 {{ activeChat.noteIds.length }} 篇笔记
        </p>
        <p v-if="error" class="main__err">{{ error }}</p>

        <div class="main__chat">
          <ChatWindow
            v-if="activeChat && activeChat.type !== 'note'"
            :messages="activeChat.messages"
            :loading="chatLoading"
            placeholder="向知识库提问…"
            @send="onSend"
          />
        </div>
      </div>
    </section>

    <SourceSelector
      :open="selectorOpen"
      :model-value="activeChat?.noteIds || []"
      @update:model-value="onNoteIdsUpdate"
      @close="selectorOpen = false"
    />
  </main>
</template>

<style scoped>
.chat-page {
  display: flex;
  height: 100vh;
  width: 100%;
  overflow: hidden;
  background: transparent;
}

.chat-page--collapse .main {
  padding-left: 56px;
}

.sidebar {
  flex: 0 0 260px;
  width: 260px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100vh;
  padding: 14px 12px 18px;
  background: color-mix(in srgb, var(--color-white) 55%, transparent);
  border-right: 1px solid rgba(228, 220, 200, 0.55);
}

.sidebar__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}

.sidebar__icon {
  border: none;
  background: transparent;
  color: var(--color-ink-muted);
  font-size: 1.05rem;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
}

.sidebar__icon:hover {
  background: rgba(42, 36, 24, 0.06);
  color: var(--color-ink);
}

.sidebar__new {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  border: 1px solid var(--color-edge);
  border-radius: 12px;
  background: var(--color-white);
  color: var(--color-ink);
  font-weight: 600;
  padding: 10px 12px;
  cursor: pointer;
  margin-bottom: 16px;
}

.sidebar__new:hover {
  border-color: var(--color-amber);
  color: var(--color-amber-deep);
}

.sidebar__plus {
  display: inline-grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1.5px solid currentColor;
  font-size: 0.95rem;
  line-height: 1;
}

.sidebar__label {
  margin: 0 6px 8px;
  font-size: 0.78rem;
  letter-spacing: 0.04em;
  color: var(--color-ink-muted);
}

.sidebar__list {
  list-style: none;
  margin: 0;
  padding: 0 0 12px;
  overflow: auto;
  flex: 1;
  min-height: 0;
}

.sidebar__list li {
  display: flex;
  align-items: center;
  gap: 2px;
  border-radius: 10px;
  margin-bottom: 2px;
}

.sidebar__list li.active {
  background: rgba(196, 122, 26, 0.12);
}

.sidebar__list li:hover {
  background: rgba(42, 36, 24, 0.04);
}

.sidebar__item {
  flex: 1;
  min-width: 0;
  border: none;
  background: transparent;
  text-align: left;
  padding: 10px 8px;
  cursor: pointer;
  color: var(--color-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.92rem;
}

.sidebar__del {
  border: none;
  background: transparent;
  color: var(--color-ink-muted);
  cursor: pointer;
  font-size: 1.05rem;
  padding: 4px 8px;
  opacity: 0;
}

.sidebar__list li:hover .sidebar__del,
.sidebar__list li.active .sidebar__del {
  opacity: 1;
}

.rail {
  position: fixed;
  top: 14px;
  left: 14px;
  z-index: 20;
  display: flex;
  gap: 8px;
}

.rail__btn {
  width: 36px;
  height: 36px;
  border: 1px solid var(--color-edge);
  border-radius: 10px;
  background: rgba(255, 253, 247, 0.92);
  color: var(--color-ink);
  font-size: 1.1rem;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(42, 36, 24, 0.08);
}

.rail__btn:hover {
  border-color: var(--color-amber);
  color: var(--color-amber-deep);
}

.main {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  height: 100vh;
  display: flex;
  justify-content: center;
  overflow: hidden;
}

.main__shell {
  width: min(760px, 100%);
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 0 16px;
}

.main__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 22px 4px 10px;
  flex: 0 0 auto;
}

.main__head h1 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.55rem;
}

.btn {
  border: none;
  border-radius: 999px;
  padding: 10px 14px;
  background: var(--color-ink);
  color: var(--color-paper);
  font-weight: 600;
  cursor: pointer;
}

.btn--ghost {
  background: transparent;
  border: 1.5px solid var(--color-edge);
  color: var(--color-ink);
}

.main__picked {
  margin: 0 4px 8px;
  color: var(--color-amber-deep);
  font-size: 0.92rem;
}

.main__err {
  margin: 0 4px 8px;
  color: #9b2c2c;
}

.main__chat {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main__chat :deep(.chat) {
  flex: 1;
  min-height: 0;
}
</style>
