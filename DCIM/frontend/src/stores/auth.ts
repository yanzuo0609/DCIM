import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchProfile, login as loginApi, logout as logoutApi, type UserProfile } from '@/api/auth'

const TOKEN_KEY = 'rackdcim_access_token'
const REFRESH_KEY = 'rackdcim_refresh_token'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const refreshToken = ref<string | null>(localStorage.getItem(REFRESH_KEY))
  const profile = ref<UserProfile | null>(null)
  const loading = ref(false)

  function setTokens(access: string, refresh: string) {
    accessToken.value = access
    refreshToken.value = refresh
    localStorage.setItem(TOKEN_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  }

  function clearAuth() {
    accessToken.value = null
    refreshToken.value = null
    profile.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
  }

  async function login(username: string, password: string) {
    loading.value = true
    try {
      const tokens = await loginApi({ username, password })
      setTokens(tokens.access_token, tokens.refresh_token)
      profile.value = await fetchProfile()
      return profile.value
    } finally {
      loading.value = false
    }
  }

  async function loadProfile() {
    if (!accessToken.value) return null
    profile.value = await fetchProfile()
    return profile.value
  }

  async function logout() {
    try {
      if (accessToken.value) {
        await logoutApi()
      }
    } finally {
      clearAuth()
    }
  }

  function hasPermission(permission: string): boolean {
    const permissions = profile.value?.permissions ?? []
    return permissions.includes('admin:*') || permissions.includes(permission)
  }

  return {
    accessToken,
    refreshToken,
    profile,
    loading,
    login,
    loadProfile,
    logout,
    clearAuth,
    setTokens,
    hasPermission,
  }
})
