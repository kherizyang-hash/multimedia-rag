<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { formatSeconds } from '../utils/format'
import { renderMarkdown } from '../utils/markdown'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  placeholder: { type: String, default: '针对这篇笔记提问…' },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['send'])

const draft = ref('')
const listRef = ref(null)

const canSend = computed(
  () => !props.disabled && !props.loading && draft.value.trim().length > 0,
)

async function scrollBottom() {
  await nextTick()
  const el = listRef.value
  if (el) el.scrollTop = el.scrollHeight
}

watch(
  () => [props.messages.length, props.loading],
  () => {
    scrollBottom()
  },
  { flush: 'post' },
)

function submit() {
  if (!canSend.value) return
  const text = draft.value.trim()
  draft.value = ''
  emit('send', text)
}

function onKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}

function htmlFor(msg) {
  if (msg.role === 'user') return null
  return renderMarkdown(msg.content || '')
}
</script>

<template>
  <div class="chat">
    <div ref="listRef" class="chat__list">
      <p v-if="!messages.length && !loading" class="chat__empty">
        还没有对话。问一个关于内容的问题开始吧。
      </p>
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        class="bubble"
        :class="msg.role === 'user' ? 'bubble--user' : 'bubble--ai'"
      >
        <div v-if="msg.role === 'user'" class="bubble__body">{{ msg.content }}</div>
        <div v-else class="bubble__body bubble__md" v-html="htmlFor(msg)" />
        <ul v-if="msg.sources?.length" class="bubble__sources">
          <li v-for="(s, i) in msg.sources" :key="i">
            {{ s.title || s.note_id }}
            <template v-if="formatSeconds(s.start_sec)">
              · {{ formatSeconds(s.start_sec) }}
            </template>
            <template v-if="s.hit_count && s.hit_count > 1">
              · 命中 {{ s.hit_count }} 个片段
            </template>
          </li>
        </ul>
      </div>
      <div v-if="loading" class="chat__thinking" aria-live="polite">
        <span class="chat__dots" aria-hidden="true">
          <i /><i /><i />
        </span>
        <span>思考中</span>
      </div>
    </div>

    <form class="chat__composer" @submit.prevent="submit">
      <textarea
        v-model="draft"
        rows="2"
        :placeholder="placeholder"
        :disabled="disabled || loading"
        @keydown="onKeydown"
      />
      <button type="submit" class="chat__send" :disabled="!canSend">发送</button>
    </form>
  </div>
</template>

<style scoped>
.chat {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.chat__list {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding: 16px 16px 100px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chat__empty {
  margin: 0;
  color: var(--color-ink-muted);
  font-size: 0.95rem;
}

.chat__thinking {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  align-self: flex-start;
  padding: 10px 14px;
  border-radius: 14px;
  background: rgba(239, 230, 212, 0.45);
  border: 1px solid var(--color-edge);
  color: var(--color-ink-muted);
  font-size: 0.92rem;
}

.chat__dots {
  display: inline-flex;
  gap: 4px;
}

.chat__dots i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-amber-deep);
  opacity: 0.35;
  animation: chat-bounce 1.05s ease-in-out infinite;
}

.chat__dots i:nth-child(2) {
  animation-delay: 0.15s;
}

.chat__dots i:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes chat-bounce {
  0%,
  80%,
  100% {
    opacity: 0.3;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

.bubble {
  max-width: 92%;
  padding: 12px 14px;
  border-radius: 14px;
}

.bubble--user {
  align-self: flex-end;
  background: var(--color-ink);
  color: var(--color-paper);
}

.bubble--ai {
  align-self: flex-start;
  background: rgba(239, 230, 212, 0.45);
  border: 1px solid var(--color-edge);
}

.bubble__body {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.98rem;
}

.bubble__md {
  white-space: normal;
}

.bubble__md :deep(p) {
  margin: 0 0 0.65em;
}

.bubble__md :deep(p:last-child) {
  margin-bottom: 0;
}

.bubble__md :deep(ul),
.bubble__md :deep(ol) {
  margin: 0.4em 0 0.65em;
  padding-left: 1.25em;
}

.bubble__md :deep(li) {
  margin: 0.2em 0;
}

.bubble__md :deep(strong) {
  font-weight: 700;
}

.bubble__md :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.9em;
  background: rgba(42, 36, 24, 0.06);
  padding: 0.1em 0.35em;
  border-radius: 4px;
}

.bubble__sources {
  margin: 10px 0 0;
  padding-left: 18px;
  font-size: 0.82rem;
  opacity: 0.85;
}

.chat__composer {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 4;
  display: flex;
  gap: 10px;
  padding: 28px 12px 14px;
  border-top: none;
  background: transparent;
}

.chat__composer::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--color-paper) 0%, transparent) 0%,
    color-mix(in srgb, var(--color-paper) 35%, transparent) 32%,
    color-mix(in srgb, var(--color-paper) 58%, transparent) 100%
  );
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  -webkit-mask-image: linear-gradient(
    180deg,
    transparent 0%,
    rgba(0, 0, 0, 0.45) 22%,
    #000 48%,
    #000 100%
  );
  mask-image: linear-gradient(
    180deg,
    transparent 0%,
    rgba(0, 0, 0, 0.45) 22%,
    #000 48%,
    #000 100%
  );
}

.chat__composer textarea {
  flex: 1;
  resize: none;
  border: 1px solid var(--color-edge);
  border-radius: 12px;
  padding: 10px 12px;
  background: var(--color-white);
  color: var(--color-ink);
}

.chat__send {
  border: none;
  border-radius: 999px;
  padding: 0 18px;
  background: var(--color-amber-deep);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}

.chat__send:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

@media (prefers-reduced-motion: reduce) {
  .chat__dots i {
    animation: none;
    opacity: 0.7;
  }
}
</style>
