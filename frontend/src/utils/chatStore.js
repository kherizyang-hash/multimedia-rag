const STORAGE_KEY = 'rag_chats_v2'

export function loadChats() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) return parsed
    }
    // 迁移旧版全局对话
    const legacy = localStorage.getItem('rag_global_chats_v1')
    if (legacy) {
      const old = JSON.parse(legacy)
      if (Array.isArray(old)) {
        const migrated = old.map((c) => ({
          ...c,
          type: c.type || 'global',
        }))
        saveChats(migrated)
        return migrated
      }
    }
    return []
  } catch {
    return []
  }
}

export function saveChats(chats) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(chats))
}

export function createChat(partial = {}) {
  const now = new Date().toISOString()
  return {
    id: partial.id || (crypto.randomUUID?.() || `chat-${Date.now()}`),
    type: partial.type || 'global', // global | note
    noteId: partial.noteId || null,
    title: partial.title || '新对话',
    noteIds: partial.noteIds || [],
    messages: partial.messages || [],
    updatedAt: now,
    createdAt: now,
  }
}

/** 笔记内对话：按 noteId upsert */
export function upsertNoteChat({ noteId, title, messages }) {
  const chats = loadChats()
  const idx = chats.findIndex((c) => c.type === 'note' && c.noteId === noteId)
  const now = new Date().toISOString()
  let nextTitle = title || '讨论「未命名」'
  if (title && !title.startsWith('讨论「')) {
    nextTitle = `讨论「${title.replace(/^笔记[:：]\s*/, '')}」`
  }
  if (idx >= 0) {
    chats[idx] = {
      ...chats[idx],
      title: nextTitle || chats[idx].title,
      messages,
      updatedAt: now,
    }
  } else {
    chats.unshift(
      createChat({
        type: 'note',
        noteId,
        title: nextTitle,
        messages,
      }),
    )
  }
  saveChats(chats)
  return chats
}

export function getNoteChat(noteId) {
  return loadChats().find((c) => c.type === 'note' && c.noteId === noteId) || null
}
