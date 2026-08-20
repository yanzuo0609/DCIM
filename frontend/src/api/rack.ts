import api, { unwrap } from '@/api'
import type { ApiResponse, PaginatedResponse } from '@/types/api'

export type RackVisualStyle = 'classic' | 'schematic' | 'realistic' | 'grid'

export interface Rack {
  id: string
  room_id: string
  rack_template_id: string | null
  code: string
  name: string
  /** 机房内顺序编号（1-based），便于划范围与定位 */
  seq_no?: number | null
  row_no: number
  column_no: number
  total_u: number
  width: number
  depth: number
  visual_style?: RackVisualStyle | string
  status: string
  description: string | null
  app_usage?: string | null
  app_color?: string | null
  occupied_u: number
  free_u: number
  utilization: number
  device_count: number
  total_power?: number
  created_at: string
  updated_at: string
}

export interface RackTemplateAppliedRoom {
  id: string
  name: string
  rack_count: number
  room_deleted?: boolean
}

export interface RackTemplate {
  id: string
  code: string
  name: string
  total_u: number
  width: number
  depth: number
  visual_style?: RackVisualStyle | string
  description?: string | null
  applied_rack_count?: number
  applied_rooms?: RackTemplateAppliedRoom[]
}

export interface RackPosition {
  id: string
  rack_id: string
  u_position: number
  occupied: boolean
  device_id: string | null
}

export interface RackLayoutDevice {
  device_id: string
  hostname: string
  height_u: number
  start_u: number
  power: number | null
  ip_summary: string | null
  bmc_ip?: string | null
  vip?: string | null
  model_name: string | null
}

export interface RackLayoutSlot {
  u_position: number
  occupied: boolean
  is_span_start: boolean
  span_height: number
  device: RackLayoutDevice | null
}

export interface RackLayoutData {
  rack: Rack
  positions: RackPosition[]
  slots: RackLayoutSlot[]
  devices: RackLayoutDevice[]
  total_power: number
}

export interface RackPayload {
  room_id: string
  code: string
  name: string
  rack_template_id?: string | null
  row_no?: number
  column_no?: number
  total_u?: number
  width?: number
  depth?: number
  status?: string
  description?: string | null
  app_usage?: string | null
  app_color?: string | null
}

export async function listRacks(params: Record<string, unknown> = {}) {
  const response = await api.get<PaginatedResponse<Rack>>('/racks', { params })
  return response.data.data
}

export async function getRackLayout(id: string): Promise<RackLayoutData> {
  const response = await api.get<ApiResponse<RackLayoutData>>(`/racks/${id}/layout`)
  return unwrap(response)
}

export interface RackTemplatePayload {
  code: string
  name: string
  total_u?: number
  width?: number
  depth?: number
  visual_style?: RackVisualStyle | string
  description?: string | null
}

export interface ApplyTemplateResult {
  updated: number
  created: number
  skipped: number
  errors: string[]
}

export interface UnapplyTemplateResult {
  deleted: number
  detached: number
  skipped: number
  errors: string[]
}

export interface RackBatchDeleteResult {
  deleted: number
  skipped: number
  errors: string[]
}

export async function listRackTemplates() {
  const response = await api.get<PaginatedResponse<RackTemplate>>('/rack-templates', {
    params: { page_size: 100 },
  })
  return response.data.data.items
}

export async function createRackTemplate(payload: RackTemplatePayload): Promise<RackTemplate> {
  const response = await api.post<ApiResponse<RackTemplate>>('/rack-templates', payload)
  return unwrap(response)
}

export async function updateRackTemplate(
  id: string,
  payload: Partial<RackTemplatePayload>,
): Promise<RackTemplate> {
  const response = await api.put<ApiResponse<RackTemplate>>(`/rack-templates/${id}`, payload)
  return unwrap(response)
}

export async function deleteRackTemplate(id: string): Promise<void> {
  await api.delete(`/rack-templates/${id}`)
}

export async function applyTemplateToRoom(
  templateId: string,
  roomId: string,
  fillEmptySlots = true,
  visualStyle?: RackVisualStyle | string | null,
): Promise<ApplyTemplateResult> {
  const response = await api.post<ApiResponse<ApplyTemplateResult>>(
    `/rack-templates/${templateId}/apply-to-room`,
    {
      room_id: roomId,
      fill_empty_slots: fillEmptySlots,
      visual_style: visualStyle || undefined,
    },
  )
  return unwrap(response)
}

export async function unapplyTemplateFromRoom(
  templateId: string,
  roomId: string,
  options: { deleteEmptyRacks?: boolean; detachTemplate?: boolean } = {},
): Promise<UnapplyTemplateResult> {
  const response = await api.post<ApiResponse<UnapplyTemplateResult>>(
    `/rack-templates/${templateId}/unapply-from-room`,
    {
      room_id: roomId,
      delete_empty_racks: options.deleteEmptyRacks ?? true,
      detach_template: options.detachTemplate ?? true,
    },
  )
  return unwrap(response)
}

export async function batchDeleteRacks(ids: string[]): Promise<RackBatchDeleteResult> {
  const response = await api.post<ApiResponse<RackBatchDeleteResult>>('/racks/batch-delete', {
    ids,
  })
  return unwrap(response)
}

export async function createRack(payload: RackPayload): Promise<Rack> {
  const response = await api.post<ApiResponse<Rack>>('/racks', payload)
  return unwrap(response)
}

export interface RackCodeConflict {
  id: string
  code: string
  name: string
  room_id: string
  room_name: string | null
  row_no: number
  column_no: number
}

export interface RackCodeCheck {
  code: string
  available: boolean
  suggestion: string
  conflict: RackCodeConflict | null
}

export async function checkRackCode(
  code: string,
  roomId?: string,
  preferredBase?: string,
): Promise<RackCodeCheck> {
  const response = await api.get<ApiResponse<RackCodeCheck>>('/racks/code-check', {
    params: {
      code,
      room_id: roomId || undefined,
      preferred_base: preferredBase || undefined,
    },
  })
  return unwrap(response)
}

export interface PlaceBatchPayload {
  room_id: string
  mode: 'all' | 'by_row' | 'by_column' | 'single'
  template_id?: string | null
  row_templates?: Record<string, string>
  column_templates?: Record<string, string>
  fill_empty_slots?: boolean
  update_existing?: boolean
  row_no?: number
  column_no?: number
  code?: string
  name?: string
}

export interface PlaceBatchResult {
  updated: number
  created: number
  skipped: number
  errors: string[]
}

export async function placeRacksBatch(payload: PlaceBatchPayload): Promise<PlaceBatchResult> {
  const response = await api.post<ApiResponse<PlaceBatchResult>>('/racks/place-batch', payload)
  return unwrap(response)
}

export async function updateRack(
  id: string,
  payload: Partial<RackPayload> & { app_usage?: string | null; app_color?: string | null },
): Promise<Rack> {
  const response = await api.put<ApiResponse<Rack>>(`/racks/${id}`, payload)
  return unwrap(response)
}

export async function deleteRack(id: string): Promise<void> {
  await api.delete(`/racks/${id}`)
}
