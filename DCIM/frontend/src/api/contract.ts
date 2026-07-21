import api, { unwrap } from '@/api'
import type { ApiResponse, PaginatedResponse } from '@/types/api'

export interface DeviceContractItem {
  device_name: string
  device_model_name: string
  manufacturer_name?: string | null
  quantity?: number
  unit_price?: number | null
  line_amount?: number | null
}

export interface DeviceContract {
  id: string
  contract_no: string
  project_no: string | null
  device_items: DeviceContractItem[]
  device_names: string[]
  device_model_names: string[]
  manufacturer_names: string[]
  device_name: string
  device_model_name: string
  manufacturer_name: string | null
  device_model_id: string | null
  quantity: number
  linked_count: number
  unit_price: number | null
  contract_total: number | null
  items_amount: number | null
  price_unit: 'yuan' | 'wan' | string
  total_amount: number | null
  purchase_date: string | null
  description: string | null
  created_at: string
  updated_at: string
}

export interface DeviceContractSummary {
  manufacturer_name: string | null
  device_name?: string | null
  device_model_name: string
  purchase_quantity: number
  linked_count: number
  contract_count: number
  avg_unit_price: number | null
}

export interface DeviceContractPayload {
  contract_no: string
  project_no?: string | null
  device_items: DeviceContractItem[]
  contract_total?: number | null
  price_unit?: 'yuan' | 'wan'
  purchase_date?: string | null
  description?: string | null
}

export interface BindResult {
  bound: number
  skipped: number
  errors: string[]
}

export function formatItemLabel(item: DeviceContractItem): string {
  const parts = [item.device_name, item.device_model_name]
  if (item.manufacturer_name) parts.push(item.manufacturer_name)
  const qty = Number(item.quantity || 0)
  if (qty > 0) parts.push(`×${qty}`)
  if (item.unit_price !== null && item.unit_price !== undefined) {
    parts.push(`单价${Number(item.unit_price)}`)
  }
  return parts.filter(Boolean).join(' / ')
}

export function formatContractItems(contract: {
  device_items?: DeviceContractItem[] | null
  device_names?: string[] | null
  device_model_names?: string[] | null
  manufacturer_names?: string[] | null
  device_name?: string | null
  device_model_name?: string | null
  manufacturer_name?: string | null
  quantity?: number | null
  unit_price?: number | null
}): string {
  const items = normalizeContractItems(contract)
  if (!items.length) return '—'
  return items.map(formatItemLabel).join('；')
}

export function normalizeContractItems(contract: {
  device_items?: DeviceContractItem[] | null
  device_names?: string[] | null
  device_model_names?: string[] | null
  manufacturer_names?: string[] | null
  device_name?: string | null
  device_model_name?: string | null
  manufacturer_name?: string | null
  quantity?: number | null
  unit_price?: number | null
}): DeviceContractItem[] {
  if (contract.device_items?.length) {
    return contract.device_items.map((i) => ({
      device_name: i.device_name,
      device_model_name: i.device_model_name,
      manufacturer_name: i.manufacturer_name || null,
      quantity: Number(i.quantity || 0),
      unit_price: i.unit_price ?? null,
      line_amount: i.line_amount ?? null,
    }))
  }
  const names = contract.device_names?.length
    ? contract.device_names
    : contract.device_name
      ? [contract.device_name]
      : []
  const models = contract.device_model_names?.length
    ? contract.device_model_names
    : contract.device_model_name
      ? [contract.device_model_name]
      : []
  const mfgs = contract.manufacturer_names?.length
    ? contract.manufacturer_names
    : contract.manufacturer_name
      ? [contract.manufacturer_name]
      : []
  const count = Math.max(names.length, models.length, mfgs.length)
  const fallbackMfg = (contract.manufacturer_name || '').trim() || null
  const fallbackQty = Number(contract.quantity || 0)
  const fallbackPrice = contract.unit_price ?? null
  const items: DeviceContractItem[] = []
  for (let i = 0; i < count; i += 1) {
    const name = (names[i] || '').trim()
    const model = (models[i] || '').trim()
    const mfg = (mfgs[i] || '').trim() || fallbackMfg
    if (!name && !model) continue
    items.push({
      device_name: name || model,
      device_model_name: model || name,
      manufacturer_name: mfg,
      quantity: i === 0 ? fallbackQty : 0,
      unit_price: i === 0 ? fallbackPrice : null,
    })
  }
  return items
}

export function calcItemsAmount(items: DeviceContractItem[]): number | null {
  let total = 0
  let has = false
  for (const item of items) {
    const qty = Number(item.quantity || 0)
    const price = item.unit_price
    if (price === null || price === undefined || !qty) continue
    total += qty * Number(price)
    has = true
  }
  return has ? Math.round(total * 100) / 100 : null
}

export async function listDeviceContracts(params: Record<string, unknown> = {}) {
  const response = await api.get<PaginatedResponse<DeviceContract>>('/device-contracts', {
    params,
  })
  return response.data.data
}

export async function getDeviceContract(id: string) {
  const response = await api.get<ApiResponse<DeviceContract>>(`/device-contracts/${id}`)
  return unwrap(response)
}

export async function createDeviceContract(payload: DeviceContractPayload) {
  const response = await api.post<ApiResponse<DeviceContract>>('/device-contracts', payload)
  return unwrap(response)
}

export async function updateDeviceContract(id: string, payload: Partial<DeviceContractPayload>) {
  const response = await api.put<ApiResponse<DeviceContract>>(`/device-contracts/${id}`, payload)
  return unwrap(response)
}

export async function deleteDeviceContract(id: string) {
  await api.delete(`/device-contracts/${id}`)
}

export async function getContractSummary() {
  const response = await api.get<ApiResponse<DeviceContractSummary[]>>('/device-contracts/summary')
  return unwrap(response)
}

export async function bindContractDevices(id: string, deviceIds: string[]) {
  const response = await api.post<ApiResponse<BindResult>>(`/device-contracts/${id}/bind-devices`, {
    device_ids: deviceIds,
  })
  return unwrap(response)
}

export async function unbindContractDevices(id: string, deviceIds: string[]) {
  const response = await api.post<ApiResponse<BindResult>>(
    `/device-contracts/${id}/unbind-devices`,
    { device_ids: deviceIds },
  )
  return unwrap(response)
}
