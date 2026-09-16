<script setup>
import { computed } from 'vue'
import { formatDateTime } from '../utils/format'

const props = defineProps({
  note: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  selectable: { type: Boolean, default: true },
})

const emit = defineEmits(['select', 'open'])

const preview = computed(() => {
  const text = (props.note.summary || '').replace(/\s+/g, ' ').trim()
  return text || '（暂无摘要）'
})

function onCardClick(event) {
  if (event.target.closest('input, label, button')) return
  emit('open', props.note)
}

function onCheck(event) {
  emit('select', { note: props.note, checked: event.target.checked })
}
</script>

<template>
  <article
    class="card"
    :class="{ 'card--selected': selected }"
    role="button"
    tabindex="0"
    @click="onCardClick"
    @keydown.enter.prevent="emit('open', note)"
  >
    <div class="card__top">
      <label v-if="selectable" class="card__check" @click.stop>
        <input type="checkbox" :checked="selected" @change="onCheck" />
        <span class="sr-only">选择笔记</span>
      </label>
      <h2 class="card__title">{{ note.title }}</h2>
      <span
        class="card__badge"
        :class="note.is_permanent ? 'card__badge--perm' : 'card__badge--temp'"
      >
        {{ note.is_permanent ? '永久' : '临时' }}
      </span>
    </div>
    <div class="card__meta">
      <span>{{ formatDateTime(note.updated_at || note.created_at) }}</span>
      <span class="card__cat">{{ note.category || '学习' }}</span>
    </div>
    <p class="card__preview">{{ preview }}</p>
  </article>
</template>

<style scoped>
.card {
  border: 1.5px solid var(--color-edge);
  border-radius: var(--radius-md);
  background: rgba(255, 253, 247, 0.92);
  padding: 18px 18px 16px;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.15s ease;
  box-shadow: 0 6px 20px rgba(42, 36, 24, 0.04);
}

.card:hover,
.card:focus-visible {
  border-color: var(--color-amber);
  box-shadow: var(--shadow-soft);
  transform: translateY(-1px);
  outline: none;
}

.card--selected {
  border-color: var(--color-amber);
  background: #fff9ef;
}

.card__top {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.card__check {
  margin-top: 4px;
  flex: 0 0 auto;
}

.card__check input {
  width: 16px;
  height: 16px;
  accent-color: var(--color-amber-deep);
}

.card__title {
  margin: 0;
  flex: 1;
  min-width: 0;
  font-family: var(--font-display);
  font-size: 1.15rem;
  font-weight: 700;
  line-height: 1.35;
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: normal;
}

.card__badge {
  flex: 0 0 auto;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 999px;
}

.card__badge--temp {
  background: rgba(92, 83, 70, 0.1);
  color: var(--color-ink-muted);
}

.card__badge--perm {
  background: rgba(196, 122, 26, 0.16);
  color: var(--color-amber-deep);
}

.card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  margin: 10px 0 8px;
  font-size: 0.88rem;
  color: var(--color-ink-muted);
}

.card__cat {
  padding: 1px 8px;
  border-radius: 999px;
  border: 1px solid var(--color-edge);
}

.card__preview {
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  color: var(--color-ink-muted);
  font-size: 0.95rem;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}
</style>
