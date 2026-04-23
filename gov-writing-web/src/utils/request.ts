import axios from 'axios'
import { getBspLoginUrl, getLoginStatus } from '@/api/bspAuth'

function readJsonSession(key: string): Record<string, unknown> | null {
  try {
    const raw = sessionStorage.getItem(key)
    if (!raw) return null
    const v = JSON.parse(raw) as unknown
    return v && typeof v === 'object' ? (v as Record<string, unknown>) : null
  } catch {
    return null
  }
}

/** 三个必填 Legacy Header 必须同时存在才注入，否则走 Cookie / 后端 Mock。 */
function buildLegacyAuthHeaders(): Record<string, string> | null {
  if (import.meta.env.VITE_USE_LEGACY_AUTH_HEADER !== 'true') return null

  const u = readJsonSession('user')
  const pick = (keys: string[]) => {
    if (!u) return ''
    for (const k of keys) {
      const v = u[k]
      if (v !== undefined && v !== null && String(v).trim() !== '') return String(v).trim()
    }
    return ''
  }

  let userId = pick(['ID', 'id', 'userId', 'user_id'])
  let account = pick(['ACCOUNT', 'account', 'userAccount', 'loginName'])
  let name = pick(['NAME', 'name', 'userName', 'realName'])
  const orgName = pick(['ORG_NAME', 'orgName', 'deptName'])
  const orgCode = pick(['ORG_CODE', 'orgCode', 'deptCode'])

  if (!userId || !account || !name) {
    userId = (import.meta.env.VITE_LEGACY_USER_ID as string | undefined)?.trim() || ''
    account = (import.meta.env.VITE_LEGACY_ACCOUNT as string | undefined)?.trim() || ''
    name = (import.meta.env.VITE_LEGACY_NAME as string | undefined)?.trim() || ''
  }

  if (!userId || !account || !name) return null

  const headers: Record<string, string> = {
    'X-Legacy-User-Id': userId,
    'X-Legacy-Account': account,
    'X-Legacy-Name': name,
  }
  if (orgName) headers['X-Legacy-Org-Name'] = orgName
  if (orgCode) headers['X-Legacy-Org-Code'] = orgCode
  return headers
}

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/agentloop',
  timeout: 30000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    const legacy = buildLegacyAuthHeaders()
    if (legacy) {
      Object.assign(config.headers, legacy)
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  (response) => {
    const { data } = response
    if (data.code === 0) {
      return data
    }
    return Promise.reject(new Error(data.message || '请求失败'))
  },
  async (error) => {
    const status = error.response?.status
    if (status === 401 || status === 403) {
      try {
        const resp = await getLoginStatus()
        const code = String(resp.data?.code ?? '')
        if (code !== '1') {
          window.open(getBspLoginUrl(), '_self')
        }
      } catch {
        window.open(getBspLoginUrl(), '_self')
      }
    }
    const message = error.response?.data?.message || error.message || '网络错误'
    return Promise.reject(new Error(message))
  },
)

export default request
