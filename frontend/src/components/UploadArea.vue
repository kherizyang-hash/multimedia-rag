<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  disabled: { type: Boolean, default: false },
  phase: { type: String, default: 'idle' },
  uploadPct: { type: Number, default: 0 },
  statusText: { type: String, default: '' },
  errorText: { type: String, default: '' },
})

const emit = defineEmits(['file'])

const dragging = ref(false)
const inputRef = ref(null)

const showProgress = computed(
  () => props.phase === 'uploading' || props.phase === 'processing' || props.phase === 'done',
)

function openPicker() {
  if (props.disabled) return
  inputRef.value?.click()
}

function onInputChange(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (file) emit('file', file)
}

function onDragEnter(event) {
  event.preventDefault()
  if (props.disabled) return
  dragging.value = true
}

function onDragOver(event) {
  event.preventDefault()
}

function onDragLeave(event) {
  if (event.currentTarget.contains(event.relatedTarget)) return
  dragging.value = false
}

function onDrop(event) {
  event.preventDefault()
  dragging.value = false
  if (props.disabled) return
  const file = event.dataTransfer?.files?.[0]
  if (file) emit('file', file)
}

function onKeydown(event) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    openPicker()
  }
}
</script>

<template>
  <section
    class="upload"
    :class="{
      'upload--dragging': dragging,
      'upload--busy': disabled,
    }"
    role="button"
    tabindex="0"
    :aria-disabled="disabled"
    @click="openPicker"
    @keydown="onKeydown"
    @dragenter="onDragEnter"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <input
      ref="inputRef"
      class="upload__input"
      type="file"
      accept=".mp4,.mov,.avi,video/mp4,video/quicktime,video/x-msvideo"
      :disabled="disabled"
      @change="onInputChange"
      @click.stop
    />

    <div class="upload__glow" aria-hidden="true" />

    <div class="upload__body">
      <p class="upload__eyebrow">视频文件</p>
      <h2 class="upload__heading">点击选择，或拖拽到此处</h2>
      <p class="upload__meta">支持 .mp4 / .mov / .avi</p>

      <div v-if="showProgress" class="upload__progress" @click.stop>
        <div class="upload__bar" role="progressbar" :aria-valuenow="uploadPct" aria-valuemin="0" aria-valuemax="100">
          <span class="upload__bar-fill" :style="{ width: `${uploadPct}%` }" />
        </div>
        <p class="upload__status">{{ statusText }}</p>
      </div>

      <p v-if="errorText" class="upload__error" role="alert" @click.stop>{{ errorText }}</p>
    </div>
  </section>
</template>

<style scoped>
.upload {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  border: 1.5px solid var(--color-edge);
  border-radius: var(--radius-lg);
  background:
    linear-gradient(145deg, rgba(255, 253, 247, 0.95), rgba(243, 230, 200, 0.55));
  box-shadow: var(--shadow-soft);
  padding: 40px 28px;
  cursor: pointer;
  outline: none;
  transition: border-color 0.25s ease, transform 0.25s ease, box-shadow 0.25s ease;
}

.upload:hover,
.upload:focus-visible {
  border-color: var(--color-amber);
  box-shadow: 0 16px 44px rgba(42, 36, 24, 0.1);
}

.upload:focus-visible {
  outline: 2px solid var(--color-amber);
  outline-offset: 3px;
}

.upload--dragging {
  border-color: var(--color-amber);
  transform: translateY(-2px);
}

.upload--dragging .upload__glow {
  opacity: 1;
  animation: breathe 1.6s ease-in-out infinite;
}

.upload--busy {
  cursor: wait;
}

.upload__input {
  display: none;
}

.upload__glow {
  position: absolute;
  inset: -20%;
  background: radial-gradient(circle at 50% 40%, rgba(196, 122, 26, 0.18), transparent 55%);
  opacity: 0;
  pointer-events: none;
  z-index: 0;
  transition: opacity 0.3s ease;
}

.upload__body {
  position: relative;
  z-index: 1;
  text-align: center;
}

.upload__eyebrow {
  margin: 0 0 8px;
  font-size: 0.8rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--color-amber-deep);
  font-weight: 600;
}

.upload__heading {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.55rem;
  font-weight: 700;
}

.upload__meta {
  margin: 10px 0 0;
  color: var(--color-ink-muted);
}

.upload__progress {
  margin: 28px auto 0;
  max-width: 420px;
  text-align: left;
}

.upload__bar {
  height: 8px;
  border-radius: 999px;
  background: rgba(42, 36, 24, 0.08);
  overflow: hidden;
}

.upload__bar-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--color-amber), #e0a04a);
  transition: width 0.25s ease;
}

.upload__status {
  margin: 10px 0 0;
  font-size: 0.95rem;
  color: var(--color-ink-muted);
}

.upload__error {
  margin: 18px 0 0;
  color: #9b2c2c;
  font-weight: 500;
}

@keyframes breathe {
  0%,
  100% {
    opacity: 0.55;
  }
  50% {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .upload--dragging .upload__glow {
    animation: none;
  }
}
</style>
