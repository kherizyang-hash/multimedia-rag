/** 简易全局 toast（暖色主题） */
import { ref } from 'vue'

export const toastVisible = ref(false)
export const toastText = ref('')

let _timer = null

export function showToast(message, durationMs = 2400) {
  toastText.value = message || ''
  toastVisible.value = true
  if (_timer) clearTimeout(_timer)
  _timer = setTimeout(() => {
    toastVisible.value = false
    _timer = null
  }, durationMs)
}

export function hideToast() {
  toastVisible.value = false
  if (_timer) {
    clearTimeout(_timer)
    _timer = null
  }
}
