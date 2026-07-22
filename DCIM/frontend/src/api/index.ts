import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type { ApiResponse } from '@/types/api'
import { useAuthStore } from '@/stores/auth'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

interface RetryableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
}

let refreshPromise: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  const auth = useAuthStore()
  if (!auth.refreshToken) {
    throw new Error('Missing refresh token')
  }
  const response = await axios.post<ApiResponse<{
    access_token: string
    refresh_token: string
  }>>('/api/v1/auth/refresh', { refresh_token: auth.refreshToken })
  const tokens = response.data.data
  if (!tokens?.access_token || !tokens.refresh_token) {
    throw new Error('Invalid refresh response')
  }
  auth.setTokens(tokens.access_token, tokens.refresh_token)
  return tokens.access_token
}

function redirectToLogin() {
  const auth = useAuthStore()
  auth.clearAuth()
  if (window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

api.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetryableConfig | undefined
    const status = error.response?.status
    const requestUrl = originalRequest?.url || ''

    if (
      status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !requestUrl.includes('/auth/login') &&
      !requestUrl.includes('/auth/refresh')
    ) {
      originalRequest._retry = true
      try {
        if (!refreshPromise) {
          refreshPromise = refreshAccessToken().finally(() => {
            refreshPromise = null
          })
        }
        const accessToken = await refreshPromise
        originalRequest.headers.Authorization = `Bearer ${accessToken}`
        return api(originalRequest)
      } catch {
        redirectToLogin()
      }
    }

    if (status === 401 && !requestUrl.includes('/auth/login')) {
      redirectToLogin()
    }

    return Promise.reject(error)
  },
)

export default api

export function unwrap<T>(response: { data: ApiResponse<T> }): T {
  return response.data.data as T
}
