import api, { unwrap } from '@/api'
import type { ApiResponse, PaginatedResponse } from '@/types/api'

/** @deprecated 兼容旧字段；展示以 attributes 为准 */
export type RoomPurpose = 'production' | 'test' | 'backup' | 'network' | 'storage' | 'other'
export type RoomImportance = 'critical' | 'high' | 'medium' | 'low'

/** 预设属性码 */
export type RoomAttributePreset = 'internet' | 'private_network'

export interface Room {
  id: string
  floor_id: string
  name: string
  /** 机房唯一业务编号 */
  code?: string
  datacenter_id: string | null
  datacenter_name: string | null
  location: string | null
  building_no: string | null
  room_no: string | null
  layout_mode: 'auto' | 'manual' | string
  rack_rows: number
  rack_columns: number
  row_layout: number[]
  outline_rows: number
  outline_cols: number
  rack_capacity: number
  code_mode: 'auto' | 'custom' | string
  code_prefix: string | null
  slot_codes: string[][]
  pillar_layout?: {
    mode?: 'auto_middle' | 'cells' | 'grid'
    rows?: number
    cols?: number
    cells?: Record<
      string,
      Array<'rack' | 'pillar' | 'pillar_round' | 'pdu' | 'power' | 'ac' | 'odf' | 'custom' | 'empty'>
    >
    props?: Record<string, { label?: string; color?: string; customId?: string }>
  } | null
  purpose: RoomPurpose | string | null
  importance: RoomImportance | string | null
  attributes?: string[]
  rack_count: number
  used_count: number
  free_count: number
  /** 机房内已上架设备总数 */
  device_count: number
  /** 容量：Σ(机柜应用模板的 U 位数)；等同于机柜数×对应模板 U 位 */
  total_u: number
  total_power: number
  description: string | null
  created_at: string
  updated_at: string
}

export interface RoomQuickPayload {
  datacenter_id: string
  building_no: string
  room_no: string
  /** 机房唯一编号；空则后端按数据中心编码自动生成 */
  code?: string | null
  description?: string | null
  purpose?: RoomPurpose | null
  importance?: RoomImportance | null
  attributes?: string[]
  outline_rows?: number
  outline_cols?: number
  layout_mode?: 'auto' | 'manual'
  rack_rows?: number
  rack_columns?: number
  row_layout?: number[]
  code_mode?: 'auto' | 'custom'
  code_prefix?: string | null
  slot_codes?: string[][]
  pillar_layout?: {
    mode?: 'auto_middle' | 'cells' | 'grid'
    rows?: number
    cols?: number
    cells?: Record<
      string,
      Array<'rack' | 'pillar' | 'pillar_round' | 'pdu' | 'power' | 'ac' | 'odf' | 'custom' | 'empty'>
    >
    props?: Record<string, { label?: string; color?: string; customId?: string }>
  } | null
}

export interface Floor {
  id: string
  building_id: string
  name: string
}

export async function getRoom(id: string): Promise<Room> {
  const response = await api.get<ApiResponse<Room>>(`/rooms/${id}`)
  return unwrap(response)
}

export async function listRooms(params: Record<string, unknown> = {}) {
  const response = await api.get<PaginatedResponse<Room>>('/rooms', { params })
  return response.data.data
}

export async function createRoomQuick(payload: RoomQuickPayload): Promise<Room> {
  const response = await api.post<ApiResponse<Room>>('/rooms/quick', payload)
  return unwrap(response)
}

export async function updateRoom(
  id: string,
  payload: {
    room_no?: string
    code?: string | null
    description?: string | null
    purpose?: RoomPurpose | null
    importance?: RoomImportance | null
    attributes?: string[]
    outline_rows?: number
    outline_cols?: number
    layout_mode?: 'auto' | 'manual'
    rack_rows?: number
    rack_columns?: number
    row_layout?: number[]
    code_mode?: 'auto' | 'custom'
    code_prefix?: string | null
    slot_codes?: string[][]
    pillar_layout?: {
      mode?: 'auto_middle' | 'cells' | 'grid'
      rows?: number
      cols?: number
      cells?: Record<
        string,
        Array<'rack' | 'pillar' | 'pillar_round' | 'pdu' | 'power' | 'ac' | 'odf' | 'custom' | 'empty'>
      >
      props?: Record<string, { label?: string; color?: string; customId?: string }>
    } | null
  },
): Promise<Room> {
  const response = await api.put<ApiResponse<Room>>(`/rooms/${id}`, payload)
  return unwrap(response)
}

export async function deleteRoom(id: string): Promise<void> {
  await api.delete(`/rooms/${id}`)
}

export async function listFloors(params: Record<string, unknown> = {}) {
  const response = await api.get<PaginatedResponse<Floor>>('/floors', { params })
  return response.data.data
}
