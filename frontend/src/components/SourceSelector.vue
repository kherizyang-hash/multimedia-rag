<script setup>
import { onMounted, ref, watch } from 'vue'
import { listNotes } from '../api'

const props = defineProps({
  open: { type: Boolean, default: false },
  modelValue: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue', 'close'])

const loading = ref(false)
const error = ref('')
const notes = ref([])
const localSelected = ref(new Set(props.modelValue.map(String)))

watch(
  () => props.modelValue,
  (val) => {
    localSelected.value = new Set((val || []).map(String))
  },
)

watch(
  () => props.open,
  (open) => {
    if (open) load()
  },
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await listNotes({ is_permanent: true })
    notes.value = data.items || []
  } catch (err) {
    error.value = err?.response?.data?.detail || err?.message || '加载永久笔记失败'
  } finally {
    loading.value = false
  }
}

function toggle(id, checked) {
  const next = new Set(localSelected.value)
  if (checked) next.add(String(id))
  else next.delete(String(id))
  localSelected.value = next
}

function apply() {
  emit('update:modelValue', [...localSelected.value])
  emit('close')
}

function onBackdrop(event) {
  if (event.target === event.currentTarget) emit('close')
}

onMounted(() => {
  if (props.open) load()
})
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="drawer" @click="onBackdrop">
      <aside class="drawer__panel" role="dialog" aria-label="选择笔记">
        <header class="drawer__head">
          <h2>选择永久笔记</h2>
          <button type="button" @click="emit('close')">关闭</button>
        </header>
        <p class="drawer__hint">仅展示已入库笔记；不选则检索全部永久笔记。</p>
        <p v-if="loading" class="drawer__hint">加载中…</p>
        <p v-if="error" class="drawer__err">{{ error }}</p>
        <ul v-if="!loading" class="drawer__list">
          <li v-if="!notes.length" class="drawer__empty">暂无永久笔记，请先在列表中入库。</li>
          <li v-for="n in notes" :key="n.id">
            <label>
              <input
                type="checkbox"
                :checked="localSelected.has(String(n.id))"
                @change="toggle(n.id, $event.target.checked)"
              />
              <span>
                <strong>{{ n.title }}</strong>
                <small>{{ n.category }}</small>
              </span>
            </label>
          </li>
        </ul>
        <footer class="drawer__foot">
          <button type="button" class="btn" @click="apply">确认选择</button>
        </footer>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.drawer {
  position: fixed;
  inset: 0;
  z-index: 40;
  background: rgba(42, 36, 24, 0.28);
  display: flex;
  justify-content: flex-end;
}

.drawer__panel {
  width: min(380px, 100%);
  height: 100%;
  background: var(--color-white);
  border-left: 1px solid var(--color-edge);
  display: flex;
  flex-direction: column;
  box-shadow: -8px 0 30px rgba(42, 36, 24, 0.08);
}

.drawer__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 18px 8px;
}

.drawer__head h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.15rem;
}

.drawer__head button {
  border: none;
  background: transparent;
  color: var(--color-amber-deep);
  font-weight: 600;
  cursor: pointer;
}

.drawer__hint {
  margin: 0 18px 10px;
  color: var(--color-ink-muted);
  font-size: 0.9rem;
}

.drawer__err {
  margin: 0 18px 10px;
  color: #9b2c2c;
}

.drawer__list {
  list-style: none;
  margin: 0;
  padding: 0 10px;
  overflow: auto;
  flex: 1;
}

.drawer__list li {
  margin: 0 0 6px;
}

.drawer__list label {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 10px 8px;
  border-radius: 10px;
  cursor: pointer;
}

.drawer__list label:hover {
  background: rgba(243, 230, 200, 0.45);
}

.drawer__list strong {
  display: block;
}

.drawer__list small {
  color: var(--color-ink-muted);
}

.drawer__empty {
  padding: 20px 8px;
  color: var(--color-ink-muted);
}

.drawer__foot {
  padding: 14px 18px 20px;
  border-top: 1px solid var(--color-edge);
}

.btn {
  width: 100%;
  border: none;
  border-radius: 999px;
  padding: 12px;
  background: var(--color-ink);
  color: var(--color-paper);
  font-weight: 600;
  cursor: pointer;
}
</style>
