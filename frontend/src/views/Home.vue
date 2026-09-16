<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { pollTask, processBilibiliLink, uploadVideo } from '../api'
import { showToast } from '../components/toast'
import UploadArea from '../components/UploadArea.vue'
import { formatElapsed } from '../utils/format'

const router = useRouter()

const JOB_STORAGE_KEY = 'pipeline_active_job'

const phase = ref('idle') // idle | uploading | processing | done | error
const uploadPct = ref(0)
const statusText = ref('')
const errorText = ref('')
const linkUrl = ref('')
const linkBusy = ref(false)

const ALLOWED = ['.mp4', '.mov', '.avi']
const busy = () =>
  phase.value === 'uploading' || phase.value === 'processing' || linkBusy.value

let elapsedTimer = null
let startedAt = 0
let pollAbort = false
const elapsedLabel = ref('')
const lastStep = ref('')

function clearElapsedTimer() {
  if (elapsedTimer) {
    clearInterval(elapsedTimer)
    elapsedTimer = null
  }
}

function refreshStatus() {
  const step = lastStep.value || '处理中…'
  statusText.value = `${step}（已处理 ${elapsedLabel.value || '0秒'}）`
}

function startElapsedTimer(initialStep = '处理中…', fromMs = null) {
  clearElapsedTimer()
  startedAt = fromMs != null ? Number(fromMs) : Date.now()
  lastStep.value = initialStep
  const tick = () => {
    const sec = Math.floor((Date.now() - startedAt) / 1000)
    elapsedLabel.value = formatElapsed(sec)
    refreshStatus()
  }
  elapsedLabel.value = formatElapsed(0)
  tick()
  elapsedTimer = setInterval(tick, 1000)
}

function stopElapsedTimer() {
  clearElapsedTimer()
  const totalSec = startedAt ? Math.floor((Date.now() - startedAt) / 1000) : 0
  return totalSec
}

function saveActiveJob(jobId) {
  try {
    sessionStorage.setItem(
      JOB_STORAGE_KEY,
      JSON.stringify({ jobId, startedAt }),
    )
  } catch {
    /* ignore quota / private mode */
  }
}

function loadActiveJob() {
  try {
    const raw = sessionStorage.getItem(JOB_STORAGE_KEY)
    if (!raw) return null
    const data = JSON.parse(raw)
    if (!data?.jobId) return null
    return data
  } catch {
    return null
  }
}

function clearActiveJob() {
  try {
    sessionStorage.removeItem(JOB_STORAGE_KEY)
  } catch {
    /* ignore */
  }
}

function applyTaskProgress(task) {
  if (pollAbort) return
  const pct = Math.min(100, Math.max(0, Number(task.progress) || 0))
  uploadPct.value = pct || uploadPct.value
  lastStep.value = task.current_step || lastStep.value || '处理中…'
  refreshStatus()
}

async function waitJob(jobId) {
  phase.value = 'processing'
  const task = await pollTask(jobId, {
    intervalMs: 3000,
    onProgress: applyTaskProgress,
    shouldAbort: () => pollAbort,
  })
  if (pollAbort || !task) {
    return null
  }
  if (task.status === 'failed') {
    throw new Error(task.error_message || '处理失败')
  }
  const noteId = task.note_id
  if (!noteId) {
    throw new Error('任务完成但未返回 note_id')
  }
  return noteId
}

async function finishSuccess(noteId, totalSec) {
  clearActiveJob()
  phase.value = 'done'
  uploadPct.value = 100
  const elapsed = formatElapsed(totalSec)
  statusText.value = `解析成功！总耗时 ${elapsed}`
  showToast(`解析成功！总耗时 ${elapsed}`)
  await new Promise((r) => setTimeout(r, 900))
  if (pollAbort) return
  await router.push({ name: 'note-preview', params: { id: noteId } })
}

async function resumeActiveJob() {
  const saved = loadActiveJob()
  if (!saved?.jobId) return

  errorText.value = ''
  pollAbort = false
  linkBusy.value = true
  phase.value = 'processing'
  uploadPct.value = Math.max(uploadPct.value, 5)
  startElapsedTimer('恢复任务进度…', saved.startedAt || Date.now())

  try {
    const noteId = await waitJob(saved.jobId)
    if (!noteId || pollAbort) return
    const totalSec = stopElapsedTimer()
    await finishSuccess(noteId, totalSec)
  } catch (err) {
    stopElapsedTimer()
    clearActiveJob()
    phase.value = 'error'
    errorText.value = err?.message || '处理失败，请稍后重试'
    statusText.value = ''
    uploadPct.value = 0
  } finally {
    linkBusy.value = false
  }
}

onMounted(() => {
  resumeActiveJob()
})

onUnmounted(() => {
  pollAbort = true
  clearElapsedTimer()
})

function validateFile(file) {
  const name = (file?.name || '').toLowerCase()
  return ALLOWED.some((ext) => name.endsWith(ext))
}

function mapLinkError(err) {
  const detail = err?.response?.data?.detail
  const msg = typeof detail === 'string' ? detail : err?.message || ''
  if (/无效|未找到 BV|请提供/i.test(msg)) {
    return msg || '链接无效，请检查是否为 B 站视频地址'
  }
  if (/仅支持解析公开视频|登录|credential|SESSDATA/i.test(msg)) {
    return '目前仅支持解析公开视频哦~'
  }
  if (!err?.response || err?.code === 'ERR_NETWORK' || /Network Error|timeout/i.test(msg)) {
    return '网络错误，请稍后重试'
  }
  return msg || '解析失败，请稍后重试'
}

async function handleFile(file) {
  if (!file) return
  if (!validateFile(file)) {
    errorText.value = `仅支持 ${ALLOWED.join(' / ')} 视频文件`
    phase.value = 'error'
    return
  }

  errorText.value = ''
  pollAbort = false
  clearActiveJob()
  phase.value = 'uploading'
  uploadPct.value = 0
  statusText.value = '正在上传视频…'
  startElapsedTimer('正在上传视频…')

  try {
    const data = await uploadVideo(file, {
      onUploadProgress(event) {
        if (!event.total) return
        const pct = Math.round((event.loaded / event.total) * 100)
        uploadPct.value = Math.min(pct, 99)
        lastStep.value = `正在上传视频… ${pct}%`
        refreshStatus()
      },
    })

    const jobId = data?.job_id
    if (!jobId) {
      throw new Error('后端未返回 job_id')
    }
    saveActiveJob(jobId)
    lastStep.value = '任务已提交，等待处理…'
    refreshStatus()
    const noteId = await waitJob(jobId)
    if (!noteId || pollAbort) return
    const totalSec = stopElapsedTimer()
    await finishSuccess(noteId, totalSec)
  } catch (err) {
    stopElapsedTimer()
    clearActiveJob()
    phase.value = 'error'
    const detail = err?.response?.data?.detail
    errorText.value =
      typeof detail === 'string'
        ? detail
        : err?.message || '上传或处理失败，请稍后重试'
    statusText.value = ''
  }
}

async function handleLinkParse() {
  const url = linkUrl.value.trim()
  if (!url) {
    errorText.value = '请粘贴 B 站视频链接'
    phase.value = 'error'
    return
  }
  if (busy()) return

  errorText.value = ''
  pollAbort = false
  clearActiveJob()
  linkBusy.value = true
  phase.value = 'processing'
  uploadPct.value = 5
  startElapsedTimer('提交解析任务…')

  try {
    const data = await processBilibiliLink(url)
    const jobId = data?.job_id
    if (!jobId) {
      throw new Error('后端未返回 job_id')
    }
    saveActiveJob(jobId)
    lastStep.value = '任务已提交，等待处理…'
    refreshStatus()
    const noteId = await waitJob(jobId)
    if (!noteId || pollAbort) return
    const totalSec = stopElapsedTimer()
    await finishSuccess(noteId, totalSec)
  } catch (err) {
    stopElapsedTimer()
    clearActiveJob()
    phase.value = 'error'
    errorText.value = mapLinkError(err)
    statusText.value = ''
    uploadPct.value = 0
  } finally {
    linkBusy.value = false
  }
}

function onLinkKeydown(event) {
  if (event.key === 'Enter') {
    event.preventDefault()
    handleLinkParse()
  }
}
</script>

<template>
  <main class="home">
    <div class="home__inner">
      <p class="home__brand">嗨~上传视频，帮你快速吸收新鲜知识</p>
      <h1 class="home__title">学习笔记助手</h1>
      <p class="home__lead">把视频变成可读、可搜、可问答的笔记</p>

      <UploadArea
        :disabled="busy()"
        :phase="phase"
        :upload-pct="uploadPct"
        :status-text="statusText"
        :error-text="errorText"
        @file="handleFile"
      />

      <div class="home__link-row">
        <div class="home__link-bar">
          <input
            v-model="linkUrl"
            class="home__link-input"
            type="url"
            placeholder="粘贴 B 站视频链接，解析公开视频"
            :disabled="busy()"
            @keydown="onLinkKeydown"
          />
          <button
            type="button"
            class="home__link-btn"
            :disabled="busy() || !linkUrl.trim()"
            @click="handleLinkParse"
          >
            解析
          </button>
        </div>
      </div>

      <nav class="home__actions" aria-label="快捷入口">
        <RouterLink class="home__btn" to="/notes">查看所有笔记</RouterLink>
        <RouterLink class="home__btn home__btn--ghost" to="/chat">全局问答</RouterLink>
      </nav>
    </div>
  </main>
</template>

<style scoped>
.home {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  padding: 56px 24px 72px;
}

.home__inner {
  width: 100%;
  max-width: var(--max-width);
  animation: rise-in 0.7s ease both;
}

.home__brand {
  margin: 0 0 18px;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 0.95rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-amber-deep);
}

.home__title {
  margin: 0;
  max-width: 18ch;
  font-family: var(--font-display);
  font-weight: 800;
  font-size: clamp(2rem, 4vw, 2.85rem);
  line-height: 1.15;
  letter-spacing: -0.02em;
  color: var(--color-ink);
  overflow-wrap: anywhere;
  word-break: break-word;
}

.home__lead {
  margin: 16px 0 36px;
  max-width: 42ch;
  color: var(--color-ink-muted);
  font-size: 1.05rem;
}

.home__link-row {
  margin-top: 16px;
}

.home__link-bar {
  display: flex;
  gap: 10px;
  align-items: stretch;
}

.home__link-input {
  flex: 1;
  min-width: 0;
  border: 1px dashed var(--color-edge);
  border-radius: 999px;
  background: rgba(255, 253, 247, 0.7);
  color: var(--color-ink);
  padding: 12px 18px;
  text-align: left;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.home__link-input::placeholder {
  color: var(--color-ink-muted);
}

.home__link-input:hover:not(:disabled),
.home__link-input:focus {
  outline: none;
  border-color: var(--color-amber);
  background: var(--color-white);
}

.home__link-input:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.home__link-btn {
  flex-shrink: 0;
  min-width: 88px;
  padding: 0 20px;
  border: none;
  border-radius: 999px;
  background: var(--color-ink);
  color: var(--color-paper);
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, transform 0.15s ease;
}

.home__link-btn:hover:not(:disabled) {
  background: var(--color-amber-deep);
  color: var(--color-white);
  transform: translateY(-1px);
}

.home__link-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.home__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 40px;
}

.home__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 140px;
  padding: 12px 20px;
  border-radius: 999px;
  background: var(--color-ink);
  color: var(--color-paper);
  text-decoration: none;
  font-weight: 600;
  transition: transform 0.15s ease, background 0.15s ease;
}

.home__btn:hover {
  background: var(--color-amber-deep);
  color: var(--color-white);
  transform: translateY(-1px);
}

.home__btn--ghost {
  background: transparent;
  color: var(--color-ink);
  border: 1.5px solid var(--color-edge);
}

.home__btn--ghost:hover {
  border-color: var(--color-amber);
  background: rgba(196, 122, 26, 0.08);
  color: var(--color-amber-deep);
}

@keyframes rise-in {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .home__inner {
    animation: none;
  }
}
</style>
