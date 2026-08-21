import api, { unwrap } from '@/api'
import type { ApiResponse, PaginatedResponse } from '@/types/api'

export interface Warehouse {
  id: string
  code: string
  name: string
  room_id: string
  room_name: string | null
  room_no: string | null
  building_no: string | null
  datacenter_id: string | null
  datacenter_name: string | null
  description: string | null
  asset_ledger_ready?: boolean
  asset_count?: number
  created_at: string
  updated_at: string
}

export interface WarehousePayload {
  room_id: string
  code?: string | null
  name: string
  description?: string | null
}

export type WarehouseAssetCategory = 'complete' | 'accessory' | 'material' | 'tool' | 'other'
export type WarehouseAssetStatus = 'new' | 'replace' | 'fault' | 'scrap'
export type WarehouseOutboundMode = 'undetermined' | 'fixed'
/** piece=个 unit=台 box=箱 set=套 other=其他 */
export type WarehouseAssetUnit = 'piece' | 'unit' | 'box' | 'set' | 'other'

export interface WarehouseAsset {
  id: string
  warehouse_id: string
  name: string
  quantity: number
  unit: WarehouseAssetUnit | string
  project: string | null
  application: string | null
  category: WarehouseAssetCategory | string
  status: WarehouseAssetStatus | string
  inbound_at: string | null
  outbound_mode: WarehouseOutboundMode | string
  outbound_at: string | null
  owner_name: string | null
  owner_contact: string | null
  remark: string | null
  created_at: string
  updated_at: string
}

export interface WarehouseAssetPayload {
  name: string
  quantity?: number
  unit?: WarehouseAssetUnit | string
  project?: string | null
  application?: string | null
  category?: WarehouseAssetCategory | string
  status?: WarehouseAssetStatus | string
  inbound_at?: string | null
  outbound_mode?: WarehouseOutboundMode | string
  outbound_at?: string | null
  owner_name?: string | null
  owner_contact?: string | null
  remark?: string | null
}

export async function listWarehouses(
  params: Record<string, unknown> = {},
): Promise<{ items: Warehouse[]; pagination: { page: number; page_size: number; total: number; pages: number } }> {
  const response = await api.get<PaginatedResponse<Warehouse>>('/warehouses', { params })
  return response.data.data
}

export async function getWarehouse(id: string): Promise<Warehouse> {
  const response = await api.get<ApiResponse<Warehouse>>(`/warehouses/${id}`)
  return unwrap(response)
}

export async function createWarehouse(payload: WarehousePayload): Promise<Warehouse> {
  const response = await api.post<ApiResponse<Warehouse>>('/warehouses', payload)
  return unwrap(response)
}

export async function updateWarehouse(
  id: string,
  payload: Partial<WarehousePayload>,
): Promise<Warehouse> {
  const response = await api.put<ApiResponse<Warehouse>>(`/warehouses/${id}`, payload)
  return unwrap(response)
}

export async function deleteWarehouse(id: string): Promise<void> {
  await api.delete(`/warehouses/${id}`)
}

export async function listWarehouseAssets(
  warehouseId: string,
  params: Record<string, unknown> = {},
): Promise<{ items: WarehouseAsset[]; pagination: { page: number; page_size: number; total: number; pages: number } }> {
  const response = await api.get<PaginatedResponse<WarehouseAsset>>(
    `/warehouses/${warehouseId}/assets`,
    { params },
  )
  return response.data.data
}

export async function createWarehouseAsset(
  warehouseId: string,
  payload: WarehouseAssetPayload,
): Promise<WarehouseAsset> {
  const response = await api.post<ApiResponse<WarehouseAsset>>(
    `/warehouses/${warehouseId}/assets`,
    payload,
  )
  return unwrap(response)
}

export async function updateWarehouseAsset(
  warehouseId: string,
  assetId: string,
  payload: Partial<WarehouseAssetPayload>,
): Promise<WarehouseAsset> {
  const response = await api.put<ApiResponse<WarehouseAsset>>(
    `/warehouses/${warehouseId}/assets/${assetId}`,
    payload,
  )
  return unwrap(response)
}

export async function deleteWarehouseAsset(warehouseId: string, assetId: string): Promise<void> {
  await api.delete(`/warehouses/${warehouseId}/assets/${assetId}`)
}
