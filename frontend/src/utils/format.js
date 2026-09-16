/** 格式化笔记时间 */
export function formatDateTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function formatSeconds(sec) {
  if (sec == null || Number.isNaN(Number(sec))) return null
  const n = Number(sec)
  if (n < 0) return null
  const m = Math.floor(n / 60)
  const s = Math.floor(n % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

/** 已用/总耗时文案，如「1分23秒」「45秒」 */
export function formatElapsed(seconds) {
  const n = Math.max(0, Math.floor(Number(seconds) || 0))
  const m = Math.floor(n / 60)
  const s = n % 60
  if (m <= 0) return `${s}秒`
  return `${m}分${String(s).padStart(2, '0')}秒`
}

export function newId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`
}
