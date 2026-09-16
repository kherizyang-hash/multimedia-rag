import axios from 'axios'

const http = axios.create({
  baseURL: '',
  timeout: 600000,
})

/**
 * 上传视频：立刻返回 job_id，需轮询任务状态。
 * @param {File} file
 * @param {{ title?: string, category?: string, onUploadProgress?: Function }} [options]
 */
export async function uploadVideo(file, options = {}) {
  const form = new FormData()
  form.append('file', file)
  const title = (options.title || file.name.replace(/\.[^.]+$/, '') || '未命名视频笔记').trim()
  form.append('title', title)
  form.append('category', options.category || '学习')

  const { data } = await http.post('/api/pipeline/video', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: options.onUploadProgress,
  })
  return data
}

/**
 * 解析 B 站公开视频链接：立刻返回 job_id。
 * @param {string} url
 * @param {string} [title]
 */
export async function processBilibiliLink(url, title = '') {
  const { data } = await http.post('/api/pipeline/bilibili', {
    url,
    title: title || undefined,
  })
  return data
}

/**
 * 查询异步处理任务状态。
 * @param {string} jobId
 */
export async function getTask(jobId) {
  const { data } = await http.get(`/api/tasks/${jobId}`)
  return data
}

/**
 * 轮询直到 done/failed；离开页面时可 shouldAbort 提前结束。
 * @param {string} jobId
 * @param {{ intervalMs?: number, onProgress?: Function, shouldAbort?: () => boolean }} [options]
 * @returns {Promise<object|null>} 中止时返回 null
 */
export async function pollTask(jobId, options = {}) {
  const intervalMs = options.intervalMs ?? 3000
  const onProgress = options.onProgress
  const shouldAbort = options.shouldAbort

  // eslint-disable-next-line no-constant-condition
  while (true) {
    if (typeof shouldAbort === 'function' && shouldAbort()) {
      return null
    }
    const task = await getTask(jobId)
    if (typeof onProgress === 'function') {
      onProgress(task)
    }
    if (task.status === 'done' || task.status === 'failed') {
      return task
    }
    await new Promise((r) => setTimeout(r, intervalMs))
  }
}

export async function listNotes(params = {}) {
  const { data } = await http.get('/api/notes', { params })
  return data
}

export async function getNote(noteId) {
  const { data } = await http.get(`/api/notes/${noteId}`)
  return data
}

export async function permanentizeNote(noteId) {
  const { data } = await http.post(`/api/notes/${noteId}/permanentize`)
  return data
}

export async function deleteNote(noteId) {
  const { data } = await http.delete(`/api/notes/${noteId}`)
  return data
}

export async function chatOnNote(payload) {
  const { data } = await http.post('/api/chat/note', payload)
  return data
}

export async function chatGlobal(payload) {
  const { data } = await http.post('/api/chat/global', payload)
  return data
}

export { http }
