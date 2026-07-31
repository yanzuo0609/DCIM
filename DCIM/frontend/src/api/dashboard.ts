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

export interface UtilizationItem {
  rack_id: string
  rack_code: string
  rack_name: string
  room_id: string
  total_u: number
  occupied_u: number
  utilization: number
}

export interface DashboardUtilization {
  items: UtilizationItem[]
}

export interface NamedMetric {
  name: string
  value: number
  code?: string | null
}

export interface DualMetric {
  name: string
  normal: number
  abnormal: number
  code?: string | null
}

export interface TrendPoint {
  label: string
  value: number
}

export interface DeviceRuntimeStats {
  total: number
  running: number
  fault: number
  offline: number
  repair: number
  running_ratio: number
}

export interface NetworkScreenStats {
  project_count: number
  topology_count: number
  node_count: number
  link_count: number
}

export interface ContractScreenStats {
  contract_count: number
  purchase_quantity: number
  linked_count: number
  summary_rows: number
}

export interface AlertRecord {
  code: string
  device_name: string
  event_time: string
  value?: string | null
}

export interface RoomMonitorOption {
  id: string
  name: string
  datacenter_name?: string | null
  location?: string | null
  rack_count: number
}

export interface RoomMonitorRack {
  id: string
  code: string
  name: string
  row_no: number
  column_no: number
  total_u: number
  occupied_u: number
  utilization: number
  device_count: number
  status: string
}

export interface RoomMonitorLayout {
  room_id: string
  room_name: string
  datacenter_name?: string | null
  location?: string | null
  rack_rows: number
  rack_columns: number
  row_layout: number[]
  slot_codes: string[][]
  code_prefix?: string | null
  code_mode?: string | null
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
  racks: RoomMonitorRack[]
}

export interface DashboardAnalytics {
  summary: DashboardSummary
  utilization: DashboardUtilization
  device_by_type: NamedMetric[]
  device_by_status: NamedMetric[]
  rack_util_buckets: NamedMetric[]
  power_by_room: NamedMetric[]
  power_by_rack: NamedMetric[]
  devices_by_datacenter: NamedMetric[]
  device_trend: TrendPoint[]
  type_online_status: DualMetric[]
  runtime: DeviceRuntimeStats
  alert_racks: UtilizationItem[]
  alert_records: AlertRecord[]
  mount_ratio: number
  network: NetworkScreenStats
  contract: ContractScreenStats
  generated_at?: string | null
}

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  const response = await api.get<ApiResponse<DashboardSummary>>('/dashboard/summary')
  return unwrap(response)
}

export async function fetchDashboardUtilization(): Promise<DashboardUtilization> {
  const response = await api.get<ApiResponse<DashboardUtilization>>('/dashboard/utilization')
  return unwrap(response)
}

function emptyAnalytics(summary: DashboardSummary, util: DashboardUtilization): DashboardAnalytics {
  const running = summary.mounted_device_count
  const total = summary.device_count || 1
  return {
    summary,
    utilization: util,
    device_by_type: [],
    device_by_status: [],
    rack_util_buckets: [],
    power_by_room: [],
    power_by_rack: [],
    devices_by_datacenter: [],
    device_trend: [],
    type_online_status: [],
    runtime: {
      total: summary.device_count,
      running,
      fault: 0,
      offline: 0,
      repair: Math.max(0, summary.device_count - running),
      running_ratio: Math.round((running / total) * 1000) / 10,
    },
    alert_racks: (util.items || []).filter((r) => r.utilization >= 85).slice(0, 15),
    alert_records: (util.items || [])
      .filter((r) => r.utilization >= 85)
      .slice(0, 8)
      .map((r) => ({
        code: r.rack_code,
        device_name: r.rack_name || r.rack_code,
        event_time: `${r.utilization}%`,
        value: `${r.occupied_u}/${r.total_u}U`,
      })),
    mount_ratio: summary.device_count
      ? Math.round((summary.mounted_device_count / summary.device_count) * 10000) / 100
      : 0,
    network: { project_count: 0, topology_count: 0, node_count: 0, link_count: 0 },
    contract: { contract_count: 0, purchase_quantity: 0, linked_count: 0, summary_rows: 0 },
  }
}

/** 优先 analytics；失败时回退 summary + utilization，避免大屏空白 */
export async function fetchDashboardAnalytics(): Promise<DashboardAnalytics> {
  try {
    const response = await api.get<ApiResponse<DashboardAnalytics>>('/dashboard/analytics')
    return unwrap(response)
  } catch {
    const [summary, utilization] = await Promise.all([
      fetchDashboardSummary(),
      fetchDashboardUtilization(),
    ])
    return emptyAnalytics(summary, utilization)
  }
}

export async function fetchDashboardRooms(): Promise<RoomMonitorOption[]> {
  const response = await api.get<ApiResponse<RoomMonitorOption[]>>('/dashboard/rooms')
  return unwrap(response)
}

export async function fetchDashboardRoomLayout(roomId: string): Promise<RoomMonitorLayout> {
  const response = await api.get<ApiResponse<RoomMonitorLayout>>(`/dashboard/rooms/${roomId}/layout`)
  return unwrap(response)
}
