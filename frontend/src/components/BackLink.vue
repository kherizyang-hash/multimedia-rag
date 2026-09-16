<script setup>
import { useRouter } from 'vue-router'

const props = defineProps({
  /** 无历史时的回退路径 */
  fallback: { type: String, default: '/' },
})

const router = useRouter()

function goBack() {
  // 有可回退历史则返回上一页，否则落到 fallback
  if (typeof window !== 'undefined' && window.history.length > 1) {
    router.back()
    return
  }
  router.push(props.fallback)
}
</script>

<template>
  <button type="button" class="back" @click="goBack">
    <span aria-hidden="true">‹</span> 返回
  </button>
</template>

<style scoped>
.back {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  border: none;
  background: transparent;
  padding: 0;
  margin: 0;
  color: var(--color-amber-deep);
  font: inherit;
  font-weight: 600;
  font-size: 0.95rem;
  cursor: pointer;
}

.back span {
  font-size: 1.15em;
  line-height: 1;
}

.back:hover {
  color: var(--color-amber);
}
</style>
