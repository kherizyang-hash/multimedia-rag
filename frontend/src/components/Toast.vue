<script setup>
import { toastText, toastVisible } from './toast'

defineProps({
  // 预留；状态由 toast.js 驱动
})
</script>

<template>
  <Teleport to="body">
    <Transition name="toast">
      <div
        v-if="toastVisible"
        class="toast"
        role="status"
        aria-live="polite"
      >
        {{ toastText }}
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.toast {
  position: fixed;
  left: 50%;
  bottom: 36px;
  z-index: 80;
  transform: translateX(-50%);
  max-width: min(90vw, 420px);
  padding: 12px 20px;
  border-radius: 999px;
  background: var(--color-ink);
  color: var(--color-paper);
  font-weight: 600;
  font-size: 0.95rem;
  box-shadow: 0 12px 32px rgba(42, 36, 24, 0.18);
  text-align: center;
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(10px);
}
</style>
