import axios from 'axios'
import { getBspLoginUrl, getLoginStatus } from '@/api/bspAuth'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000,
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
