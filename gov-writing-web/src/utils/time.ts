export function fmtTime(v?: string | null) {
  if (!v) return '--'
  // 兼容后端返回的 ISO 8601（含 T / Z / 毫秒）以及普通字符串
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

