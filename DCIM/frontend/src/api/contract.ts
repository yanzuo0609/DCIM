import api, { unwrap } from '@/api'
import type { ApiResponse, PaginatedResponse } from '@/types/api'

export type QuantityUnit = '台' | '个' | '件' | '套'
export type ContractItemKind = 'hardware' | 'software'

export const QUANTITY_UNIT_OPTIONS: QuantityUnit[] = ['台', '个', '件', '套']

export const ITEM_KIND_OPTIONS: Array<{ value: ContractItemKind; label: string }> = [
  { value: 'hardware', label: '硬件' },
  { value: 'software', label: '软件' },
]

export function normalizeQuantityUnit(value: string | null | undefined): QuantityUnit {
  const text = (value || '台').trim()
  return QUANTITY_UNIT_OPTIONS.includes(text as QuantityUnit) ? (text as QuantityUnit) : '台'
}

export function normalizeItemKind(value: string | null | undefined): ContractItemKind {
  const text = (value || 'hardware').trim().toLowerCase()
  if (['software', '软', '软件', '许可', 'license'].includes(text)) return 'software'
  return 'hardware'
}

export function itemKindLabel(value: string | null | undefined) {
  return normalizeItemKind(value) === 'software' ? '软件' : '硬件'
}

export interface DeviceContractItem {
  device_name: string
  device_model_name: string
  manufacturer_name?: string | null
  item_kind?: ContractItemKind | string
  quantity?: number
  quantity_unit?: QuantityUnit
  unit_price?: number | null
  price_unit?: 'yuan' | 'wan'
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
  item_kind?: ContractItemKind | string
  purchase_quantity: number
  purchase_amount?: number | null
  linked_count: number
  contract_count: number
  avg_unit_price: number | null
  remaining_quantity?: number
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

export interface ContractModelSyncResult {
  created: number
  skipped: number
  deleted: number
  kept_in_use: number
  messages: string[]
}

export function formatItemLabel(item: DeviceContractItem): string {
  const parts = [item.device_name, item.device_model_name]
  if (item.manufacturer_name) parts.push(item.manufacturer_name)
  const qty = Number(item.quantity || 0)
  if (qty > 0) parts.push(`×${qty}${normalizeQuantityUnit(item.quantity_unit)}`)
  if (item.unit_price !== null && item.unit_price !== undefined) {
    const unit = item.price_unit === 'wan' ? '万元' : '元'
    parts.push(`单价${Number(item.unit_price)}${unit}`)
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
      item_kind: normalizeItemKind(i.item_kind),
      quantity: Number(i.quantity || 0),
      quantity_unit: normalizeQuantityUnit(i.quantity_unit),
      unit_price:
        i.unit_price === null || i.unit_price === undefined ? null : Number(i.unit_price),
      price_unit: i.price_unit === 'wan' ? 'wan' : 'yuan',
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
      item_kind: 'hardware',
      quantity: i === 0 ? fallbackQty : 0,
      quantity_unit: '台',
      unit_price: i === 0 ? fallbackPrice : null,
      price_unit: 'yuan' as const,
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
    const line = qty * Number(price)
    const yuan = item.price_unit === 'wan' ? line * 10000 : line
    total += yuan
    has = true
  }
  return has ? Math.round(total * 100) / 100 : null
}

export interface ContractItemsImportResult {
  items: DeviceContractItem[]
  imported: number
  skipped: number
  errors: string[]
}

async function downloadBlob(path: string, filename: string) {
  const response = await api.get(path, { responseType: 'blob' })
  const url = window.URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  window.URL.revokeObjectURL(url)
}

export async function downloadContractItemsTemplate() {
  await downloadBlob('/device-contracts/items/import/template', 'contract_items_template.xlsx')
}

export async function importContractItems(file: File): Promise<ContractItemsImportResult> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post<ApiResponse<ContractItemsImportResult>>(
    '/device-contracts/items/import',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  )
  return unwrap(response)
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

/** 全量：按合同同步型号，并清理已无合同引用的同步型号 */
export async function syncContractModels() {
  const response = await api.post<ApiResponse<ContractModelSyncResult>>(
    '/device-contracts/sync-models',
  )
  return unwrap(response)
}

/** 将指定合同明细同步为设备型号 */
export async function syncContractModelsById(id: string) {
  const response = await api.post<ApiResponse<ContractModelSyncResult>>(
    `/device-contracts/${id}/sync-models`,
  )
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
