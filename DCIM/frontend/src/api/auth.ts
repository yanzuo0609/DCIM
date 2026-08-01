import api, { unwrap } from '@/api'
import type { ApiResponse } from '@/types/api'

export interface LoginPayload {
  username: string
  password: string
}

export interface TokenData {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface UserProfile {
  id: string
  username: string
  email: string
  full_name: string | null
  status: string
  roles: Array<{ id: string; code: string; name: string }>
  permissions: string[]
  created_at: string
}

export async function login(payload: LoginPayload): Promise<TokenData> {
  const response = await api.post<ApiResponse<TokenData>>('/auth/login', payload)
  return unwrap(response)
}

export async function fetchProfile(): Promise<UserProfile> {
  const response = await api.get<ApiResponse<UserProfile>>('/auth/profile')
  return unwrap(response)
}

export async function logout(): Promise<void> {
  await api.post('/auth/logout')
}
