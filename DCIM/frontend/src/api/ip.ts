import api, { unwrap } from '@/api'
import type { ApiResponse } from '@/types/api'

export type IpBindType = 'none' | 'device' | 'rack' | 'rack_range'
export type IpStatus = 'free' | 'allocated' | 'disabled'

export interface IpAddress {
  id: string
  system_ip: string
  bmc_ip: string | null
  vip: string | null
  netmask: string | null
  gateway: string | null
  dns: string | null
  dns_secondary: string | null
  label: string | null
  description: string | null
  status: IpStatus | string
  bind_type: IpBindType | string
  device_id: string | null
  device_name: string | null
  rack_id: string | null
  rack_code: string | null
  room_id: string | null
  room_name: string | null
  scope_rack_ids: string[] | null
  u_position: number | null
  created_at: string
  updated_at: string
}

export interface IpAddressPayload {
  system_ip: string
  bmc_ip?: string | null
  vip?: string | null
  netmask?: string | null
  gateway?: string | null
  dns?: string | null
  dns_secondary?: string | null
  label?: string | null
  description?: string | null
  status?: IpStatus | null
}

export interface IpBatchCreatePayload {
  start_system_ip: string
  end_system_ip: string
  start_bmc_ip?: string | null
  netmask?: string | null
  gateway?: string | null
  dns?: string | null
  dns_secondary?: string | null
  label_prefix?: string | null
  description?: string | null
}

export interface IpBindPayload {
  bind_type: IpBindType
  device_id?: string | null
  rack_id?: string | null
  room_id?: string | null
  rack_ids?: string[]
}

export interface IpAllocatePayload {
  ip_ids: string[]
  room_id: string
  rack_ids?: string[]
  row_nos?: number[]
  column_nos?: number[]
}

export async function listIpAddresses(params: Record<string, unknown> = {}) {
  const response = await api.get('/ip-addresses', { params })
  return response.data.data
}

export async function createIpAddress(payload: IpAddressPayload): Promise<IpAddress> {
  const response = await api.post<ApiResponse<IpAddress>>('/ip-addresses', payload)
  return unwrap(response)
}

export async function updateIpAddress(id: string, payload: Partial<IpAddressPayload>): Promise<IpAddress> {
  const response = await api.put<ApiResponse<IpAddress>>(`/ip-addresses/${id}`, payload)
  return unwrap(response)
}

export async function deleteIpAddress(id: string): Promise<void> {
  await api.delete(`/ip-addresses/${id}`)
}

export async function batchCreateIpAddresses(payload: IpBatchCreatePayload) {
  const response = await api.post<ApiResponse<{ created: number; skipped: number; errors: string[] }>>(
    '/ip-addresses/batch-create',
    payload,
  )
  return unwrap(response)
}

export async function batchDeleteIpAddresses(ids: string[]) {
  const response = await api.post<ApiResponse<{ deleted: number; skipped: number; errors: string[] }>>(
    '/ip-addresses/batch-delete',
    { ids },
  )
  return unwrap(response)
}

export async function batchBindIpAddresses(ids: string[], bind: IpBindPayload) {
  const response = await api.post<ApiResponse<{ updated: number; skipped: number; errors: string[] }>>(
    '/ip-addresses/batch-bind',
    { ids, bind },
  )
  return unwrap(response)
}

export async function bindIpAddress(id: string, bind: IpBindPayload): Promise<IpAddress> {
  const response = await api.post<ApiResponse<IpAddress>>(`/ip-addresses/${id}/bind`, bind)
  return unwrap(response)
}

export async function allocateIpAddresses(payload: IpAllocatePayload) {
  const response = await api.post<
    ApiResponse<{
      allocated: number
      skipped: number
      errors: string[]
      assignments: Array<{
        ip_id: string
        system_ip: string
        device_id: string
        device_name: string | null
        rack_id: string
        rack_code: string
        u_position: number
      }>
    }>
  >('/ip-addresses/allocate', payload)
  return unwrap(response)
}

export async function batchSetIpStatus(ids: string[], status: IpStatus) {
  const response = await api.post<ApiResponse<{ updated: number; skipped: number; errors: string[] }>>(
    '/ip-addresses/batch-status',
    { ids, status },
  )
  return unwrap(response)
}
