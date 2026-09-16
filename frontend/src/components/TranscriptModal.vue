<script setup>
/**
 * 展示笔记清洗后原文稿（cleaned_text）
 * 样式对齐 MindmapModal 的遮罩与面板。
 */
defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '视频原文稿' },
  content: { type: String, default: '' },
})

const emit = defineEmits(['close'])

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
        <div class="modal__body">
          <p v-if="!content" class="modal__empty">暂无原文稿。</p>
          <pre v-else class="modal__pre">{{ content }}</pre>
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
  width: min(760px, 100%);
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
  padding: 14px 18px;
  border-bottom: 1px solid var(--color-edge);
}

.modal__header h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.15rem;
}

.modal__close {
  border: 1px solid var(--color-edge);
  background: transparent;
  border-radius: 999px;
  padding: 6px 12px;
  cursor: pointer;
  font-weight: 600;
}

.modal__body {
  padding: 16px 20px 22px;
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
  overflow-wrap: anywhere;
  word-break: break-word;
  font-family: var(--font-body);
  font-size: 0.98rem;
  line-height: 1.7;
  color: var(--color-ink);
}
</style>
