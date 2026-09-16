<script setup>
import { watchEffect } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import Toast from './components/Toast.vue'

const route = useRoute()

watchEffect(() => {
  const name = route.name
  document.body.classList.remove('surface-home', 'surface-read')
  if (name === 'home') {
    document.body.classList.add('surface-home')
  } else if (name === 'note-preview' || name === 'chat') {
    document.body.classList.add('surface-read')
  }
  // 笔记列表等其余页：沿用默认扁平 paper
})
</script>

<template>
  <RouterView />
  <Toast />
</template>
