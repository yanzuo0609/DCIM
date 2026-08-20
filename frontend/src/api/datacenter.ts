import api, { unwrap } from '@/api'
import type { ApiResponse, PaginatedResponse } from '@/types/api'

export interface DataCenter {
  id: string
  code: string
  name: string
  location: string | null
  description: string | null
  created_at: string
  updated_at: string
}

export interface DataCenterPayload {
  code?: string | null
  name: string
  location?: string | null
  description?: string | null
}

export interface ListParams {
  page?: number
  page_size?: number
  keyword?: string
}

export async function listDatacenters(params: ListParams = {}) {
  const response = await api.get<PaginatedResponse<DataCenter>>('/datacenters', { params })
  return response.data.data
}

export async function createDatacenter(payload: DataCenterPayload): Promise<DataCenter> {
  const response = await api.post<ApiResponse<DataCenter>>('/datacenters', payload)
  return unwrap(response)
}

export async function updateDatacenter(
  id: string,
  payload: Partial<DataCenterPayload>,
): Promise<DataCenter> {
  const response = await api.put<ApiResponse<DataCenter>>(`/datacenters/${id}`, payload)
  return unwrap(response)
}

export async function deleteDatacenter(id: string, options: { force?: boolean } = {}): Promise<void> {
  await api.delete(`/datacenters/${id}`, {
    params: options.force ? { force: true } : undefined,
  })
}
