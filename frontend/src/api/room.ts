import api, { unwrap } from '@/api'
import type { ApiResponse, PaginatedResponse } from '@/types/api'

export interface Room {
  id: string
  floor_id: string
  name: string
  datacenter_id: string | null
  datacenter_name: string | null
  location: string | null
  building_no: string | null
  room_no: string | null
  layout_mode: 'auto' | 'manual' | string
  rack_rows: number
  rack_columns: number
  row_layout: number[]
  rack_capacity: number
  code_mode: 'auto' | 'custom' | string
  code_prefix: string | null
  slot_codes: string[][]
  description: string | null
  created_at: string
  updated_at: string
}

export interface RoomQuickPayload {
  datacenter_id: string
  building_no: string
  room_no: string
  description?: string | null
  layout_mode?: 'auto' | 'manual'
  rack_rows?: number
  rack_columns?: number
  row_layout?: number[]
  code_mode?: 'auto' | 'custom'
  code_prefix?: string | null
  slot_codes?: string[][]
}

export interface Floor {
  id: string
  building_id: string
  name: string
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
    description?: string | null
    layout_mode?: 'auto' | 'manual'
    rack_rows?: number
    rack_columns?: number
    row_layout?: number[]
    code_mode?: 'auto' | 'custom'
    code_prefix?: string | null
    slot_codes?: string[][]
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
