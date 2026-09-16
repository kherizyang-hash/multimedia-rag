<script setup>
const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '确认' },
  message: { type: String, default: '' },
  confirmText: { type: String, default: '确定' },
  cancelText: { type: String, default: '取消' },
  danger: { type: Boolean, default: false },
})

const emit = defineEmits(['confirm', 'cancel'])

function onBackdrop(event) {
  if (event.target === event.currentTarget) emit('cancel')
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="confirm" role="dialog" aria-modal="true" @click="onBackdrop">
      <div class="confirm__panel">
        <h2>{{ title }}</h2>
        <p>{{ message }}</p>
        <div class="confirm__actions">
          <button type="button" class="btn btn--ghost" @click="emit('cancel')">
            {{ cancelText }}
          </button>
          <button
            type="button"
            class="btn"
            :class="{ 'btn--danger': danger }"
            @click="emit('confirm')"
          >
            {{ confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.confirm {
  position: fixed;
  inset: 0;
  z-index: 60;
  background: rgba(42, 36, 24, 0.35);
  display: grid;
  place-items: center;
  padding: 24px;
}

.confirm__panel {
  width: min(420px, 100%);
  background: var(--color-white);
  border: 1px solid var(--color-edge);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-soft);
  padding: 24px 22px 20px;
}

h2 {
  margin: 0 0 10px;
  font-family: var(--font-display);
  font-size: 1.2rem;
}

p {
  margin: 0 0 22px;
  color: var(--color-ink-muted);
  line-height: 1.55;
}

.confirm__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn {
  border: none;
  border-radius: 999px;
  padding: 9px 16px;
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

.btn--danger {
  background: #8f2f2f;
}
</style>
