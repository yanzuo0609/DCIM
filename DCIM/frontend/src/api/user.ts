import api, { unwrap } from '@/api'
import type { ApiResponse } from '@/types/api'

export interface User {
  id: string
  username: string
  email: string
  full_name: string | null
  status: string
  roles: { id: string; code: string; name: string }[]
  created_at: string
  updated_at: string
}

export interface Role {
  id: string
  code: string
  name: string
  description: string | null
  permissions: Permission[]
  created_at: string
  updated_at: string
}

export interface Permission {
  id: string
  code: string
  name: string
  description: string | null
}

export interface UserPayload {
  username: string
  email: string
  password: string
  full_name?: string | null
  role_ids?: string[]
  status?: string
}

export interface UserUpdatePayload {
  email?: string
  password?: string
  full_name?: string | null
  role_ids?: string[]
  status?: string
}

export interface RolePayload {
  code: string
  name: string
  description?: string | null
  permission_ids?: string[]
}

export interface RoleUpdatePayload {
  name?: string
  description?: string | null
  permission_ids?: string[]
}

export async function listUsers(params: Record<string, unknown> = {}) {
  const response = await api.get('/users', { params })
  return response.data.data
}

export async function createUser(payload: UserPayload): Promise<User> {
  const response = await api.post<ApiResponse<User>>('/users', payload)
  return unwrap(response)
}

export async function updateUser(id: string, payload: UserUpdatePayload): Promise<User> {
  const response = await api.put<ApiResponse<User>>(`/users/${id}`, payload)
  return unwrap(response)
}

export async function deleteUser(id: string): Promise<void> {
  await api.delete(`/users/${id}`)
}

export async function listRoles(params: Record<string, unknown> = {}) {
  const response = await api.get('/roles', { params })
  return response.data.data
}

export async function listPermissions(): Promise<Permission[]> {
  const response = await api.get<ApiResponse<Permission[]>>('/permissions')
  return unwrap(response)
}

export async function createRole(payload: RolePayload): Promise<Role> {
  const response = await api.post<ApiResponse<Role>>('/roles', payload)
  return unwrap(response)
}

export async function updateRole(id: string, payload: RoleUpdatePayload): Promise<Role> {
  const response = await api.put<ApiResponse<Role>>(`/roles/${id}`, payload)
  return unwrap(response)
}

export async function deleteRole(id: string): Promise<void> {
  await api.delete(`/roles/${id}`)
}
