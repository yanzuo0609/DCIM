import api, { unwrap } from '@/api'
import type { ApiResponse } from '@/types/api'

export interface DashboardSummary {
  datacenter_count: number
  room_count: number
  rack_count: number
  device_count: number
  mounted_device_count: number
  total_u: number
  occupied_u: number
  free_u: number
  utilization: number
  total_power: number
}

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  const response = await api.get<ApiResponse<DashboardSummary>>('/dashboard/summary')
  return unwrap(response)
}
