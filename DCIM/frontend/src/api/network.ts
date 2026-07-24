import api, { unwrap } from '@/api'
import type { ApiResponse } from '@/types/api'

export type NetworkNodeKind = 'switch' | 'server' | 'security'
export type NetworkLinkType = 'switch_server' | 'switch_switch' | 'switch_security'
export type SwitchSubtype = 'gigabit' | 'ten_gigabit' | 'core'
export type UplinkPosition = 'right' | 'middle'
export type InterfaceGroupRole = 'main' | 'uplink' | 'mgmt' | 'card'
export type CoreCardType = 'gigabit' | 'ten_gigabit' | '100g' | 'blank'
export type ServerFormFactor = 1 | 2 | 4
export type ServerSlotKind = 'nic_1g' | 'nic_10g' | 'raid' | 'hba' | 'blank'
export type ServerSlotOrientation = 'horizontal' | 'vertical'
export type ServerPanelSide = 'front' | 'rear'
/** 安全设备接口区排布 */
export type SecurityZoneLayout = 'single_row' | 'two_row' | 'auto'

export interface SlotConfig {
  enabled: boolean
  port_count: number
}

export interface NetworkDeviceBrief {
  device_id: string
  name: string | null
  hostname: string
  rack_code: string | null
  room_name: string | null
  u_position: number | null
  ip_summary: string | null
  bmc_ip: string | null
  vip: string | null
  device_type_name: string | null
}

export type PortType = '1g' | '10g' | '40_100g' | 'bmc' | 'other'

export interface SlotInterfaceGroup {
  id: string
  port_type: PortType
  count: number
  layout_order?: number | null
  role?: InterfaceGroupRole | null
  grid_cols?: number | null
  /** @deprecated 布局由引擎自动计算，仅保留兼容 */
  layout_x?: number | null
  layout_y?: number | null
}

export interface LayoutSlotDef {
  groups: SlotInterfaceGroup[]
  layout_x?: number | null
  layout_y?: number | null
  /** 扩展卡自定义宽度（后面板） */
  layout_w?: number | null
  /** 扩展卡自定义高度（后面板） */
  layout_h?: number | null
  /** 服务器后面板 Slot 类型 */
  server_slot_kind?: ServerSlotKind | null
  /** 板卡横/纵向放置 */
  orientation?: ServerSlotOrientation | null
  /** 安全设备前面板：接口区名称（WAN/LAN/MGMT…） */
  zone_label?: string | null
  /** 安全设备前面板：接口区排布 */
  zone_layout?: SecurityZoneLayout | null
  /** @deprecated migrated to groups */
  port_count?: number
  default_port_type?: PortType
  port_types?: PortType[]
}

export interface FramePort {
  id: string
  label: string
  x: number
  y: number
  w: number
  h: number
  port_type: PortType
  slot_index: number | null
  group_id: string | null
  peer_node_id: string | null
  peer_port: string | null
  peer_label: string | null
  /** 手动拖动后锁定，布局引擎不再覆盖坐标 */
  layout_locked?: boolean | null
}

export interface CoreLineCard {
  id: string
  card_type: CoreCardType
  port_count: number
}

export interface PortLayout {
  frame_width: number
  frame_height: number
  rack_width_mm?: number
  height_u?: number
  slot_count?: number
  slots_def?: LayoutSlotDef[]
  ports: FramePort[]
  switch_subtype?: SwitchSubtype | null
  uplink_position?: UplinkPosition | null
  main_port_count?: number | null
  uplink_port_count?: number | null
  line_cards?: CoreLineCard[] | null
  /** 服务器机箱规格：1U / 2U / 4U */
  server_form_factor?: ServerFormFactor | null
  /** 当前编辑/展示的面板侧 */
  server_panel_side?: ServerPanelSide | null
  /** 板载千兆口数量（后面板固定区） */
  server_onboard_1g_count?: number | null
  /** 安全设备前面板模式 */
  security_panel?: boolean | null
  /** 布局已锁定：仅允许配置接口对端，不可改面板结构 */
  layout_locked?: boolean | null
}

export interface NetworkNode {
  id: string
  topology_id: string
  kind: NetworkNodeKind
  name: string
  device_id: string | null
  pos_x: number
  pos_y: number
  switch_port_count: number
  slots: SlotConfig[] | null
  port_layout?: PortLayout | null
  device?: NetworkDeviceBrief | null
}

export interface NetworkLink {
  id: string
  topology_id: string
  link_type: NetworkLinkType
  source_node_id: string
  source_port: string
  target_node_id: string
  target_port: string
  label: string | null
}

export interface NetworkTopology {
  id: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
}

export interface NetworkTopologyDetail extends NetworkTopology {
  nodes: NetworkNode[]
  links: NetworkLink[]
}

export interface CanvasNodeInput {
  id?: string | null
  kind: NetworkNodeKind
  name: string
  device_id?: string | null
  pos_x: number
  pos_y: number
  switch_port_count?: number
  slots?: SlotConfig[] | null
  port_layout?: PortLayout | null
}

export interface CanvasLinkInput {
  id?: string | null
  link_type: NetworkLinkType
  source_node_id: string
  source_port: string
  target_node_id: string
  target_port: string
  label?: string | null
}

export function defaultSlots(): SlotConfig[] {
  return Array.from({ length: 8 }, () => ({ enabled: false, port_count: 1 }))
}

export interface NodePortOption {
  id: string
  label: string
  port_type: PortType
  slot_index: number | null
}

export function formatNodeLocation(node: Pick<NetworkNode, 'name' | 'device' | 'pos_x' | 'pos_y'>): string {
  const parts: string[] = []
  const d = node.device
  if (d?.room_name) parts.push(d.room_name)
  if (d?.rack_code) parts.push(`机柜 ${d.rack_code}`)
  if (d?.u_position != null) parts.push(`${d.u_position}U`)
  if (!parts.length) {
    parts.push(`画布 (${Math.round(node.pos_x)}, ${Math.round(node.pos_y)})`)
  }
  return parts.join(' · ')
}

export function listNodePortOptions(
  node: Pick<NetworkNode, 'kind' | 'switch_port_count' | 'slots' | 'port_layout'>,
): NodePortOption[] {
  if (node.port_layout?.ports?.length) {
    return node.port_layout.ports.map((p) => ({
      id: p.id,
      label: `${p.label} · ${PORT_TYPE_LABELS[p.port_type || '1g']}${p.slot_index ? ` · Slot ${p.slot_index}` : ''}`,
      port_type: p.port_type || '1g',
      slot_index: p.slot_index,
    }))
  }
  return listNodePorts(node).map((id) => ({
    id,
    label: id,
    port_type: '1g' as PortType,
    slot_index: null,
  }))
}

export function listNodePorts(
  node: Pick<NetworkNode, 'kind' | 'switch_port_count' | 'slots' | 'port_layout'>,
): string[] {
  if (node.port_layout?.ports?.length) {
    return node.port_layout.ports.map((p) => p.id)
  }
  if (node.kind === 'switch') {
    const count = node.switch_port_count || 48
    return Array.from({ length: count }, (_, i) => `p${i + 1}`)
  }
  const slots = node.slots || defaultSlots()
  const ports: string[] = []
  slots.forEach((slot, idx) => {
    if (!slot.enabled) return
    for (let p = 1; p <= slot.port_count; p += 1) {
      ports.push(`slot${idx + 1}-p${p}`)
    }
  })
  return ports
}

export async function listNetworkTopologies(params: Record<string, unknown> = {}) {
  const response = await api.get('/network-topologies', { params })
  return response.data.data
}

export async function createNetworkTopology(payload: { name: string; description?: string | null }) {
  const response = await api.post<ApiResponse<NetworkTopology>>('/network-topologies', payload)
  return unwrap(response)
}

export async function getNetworkTopologyDetail(id: string): Promise<NetworkTopologyDetail> {
  const response = await api.get<ApiResponse<NetworkTopologyDetail>>(`/network-topologies/${id}`)
  return unwrap(response)
}

export async function updateNetworkTopology(
  id: string,
  payload: { name?: string; description?: string | null },
) {
  const response = await api.put<ApiResponse<NetworkTopology>>(`/network-topologies/${id}`, payload)
  return unwrap(response)
}

export async function saveNetworkCanvas(
  id: string,
  payload: { nodes: CanvasNodeInput[]; links: CanvasLinkInput[] },
): Promise<NetworkTopologyDetail> {
  const response = await api.put<ApiResponse<NetworkTopologyDetail>>(
    `/network-topologies/${id}/canvas`,
    payload,
  )
  return unwrap(response)
}

export async function deleteNetworkTopology(id: string) {
  await api.delete(`/network-topologies/${id}`)
}

export const PORT_TYPE_LABELS: Record<PortType, string> = {
  '1g': '千兆',
  '10g': '万兆',
  '40_100g': '40/100G',
  bmc: 'BMC',
  other: '其他',
}

export const PORT_TYPE_COLORS: Record<PortType, { fill: string; stroke: string }> = {
  '1g': { fill: '#d6eaff', stroke: '#2b7fd4' },
  '10g': { fill: '#ddf2d0', stroke: '#4e9b2e' },
  '40_100g': { fill: '#fce8c8', stroke: '#d48806' },
  bmc: { fill: '#e8e9eb', stroke: '#6b7280' },
  other: { fill: '#f3f4f6', stroke: '#9ca3af' },
}

export const PORT_TYPE_SHORT: Record<PortType, string> = {
  '1g': '1G',
  '10g': '10G',
  '40_100g': '40G',
  bmc: 'BMC',
  other: 'O',
}

export const NODE_KIND_LABELS: Record<NetworkNodeKind, string> = {
  switch: '交换机',
  server: '服务器',
  security: '安全设备',
}

export const SWITCH_SUBTYPE_LABELS: Record<SwitchSubtype, string> = {
  gigabit: '千兆交换机',
  ten_gigabit: '万兆交换机',
  core: '核心交换机',
}

export const UPLINK_POSITION_LABELS: Record<UplinkPosition, string> = {
  right: '右侧',
  middle: '中间',
}

export const SWITCH_SUBTYPE_DEFAULTS: Record<
  SwitchSubtype,
  { mainPortCount: number; uplinkPortCount: number; mainType: PortType; uplinkType: PortType }
> = {
  gigabit: { mainPortCount: 48, uplinkPortCount: 4, mainType: '1g', uplinkType: '10g' },
  ten_gigabit: { mainPortCount: 48, uplinkPortCount: 4, mainType: '10g', uplinkType: '40_100g' },
  core: { mainPortCount: 48, uplinkPortCount: 0, mainType: '10g', uplinkType: '40_100g' },
}

export const CORE_CARD_TYPE_LABELS: Record<CoreCardType, string> = {
  gigabit: '千兆板卡',
  ten_gigabit: '万兆板卡',
  '100g': '100G板卡',
  blank: '空白板卡',
}

export const CORE_CARD_PORT_TYPE: Record<Exclude<CoreCardType, 'blank'>, PortType> = {
  gigabit: '1g',
  ten_gigabit: '10g',
  '100g': '40_100g',
}

export function isBlankCoreCard(cardType: CoreCardType | null | undefined): boolean {
  return cardType === 'blank'
}

export const SERVER_FORM_FACTOR_LABELS: Record<ServerFormFactor, string> = {
  1: '1U 服务器',
  2: '2U 服务器',
  4: '4U 服务器',
}

/** 扩展卡数量不再按机箱规格限制；保留函数供兼容，返回较大上限 */
export function serverMaxSlotCount(_formFactor?: ServerFormFactor): number {
  return 256
}

/** @deprecated 保留兼容 */
export const SERVER_SLOT_GRID: Record<ServerFormFactor, { rows: number; cols: number }> = {
  1: { rows: 1, cols: 4 },
  2: { rows: 1, cols: 4 },
  4: { rows: 1, cols: 6 },
}

export const SERVER_SLOT_KIND_LABELS: Record<ServerSlotKind, string> = {
  nic_1g: '千兆网卡',
  nic_10g: '万兆网卡',
  raid: '独立 RAID 卡',
  hba: 'HBA 卡',
  blank: '空面板（占位）',
}

export const SERVER_ORIENTATION_LABELS: Record<ServerSlotOrientation, string> = {
  horizontal: '横向',
  vertical: '纵向',
}

export const SECURITY_ZONE_LAYOUT_LABELS: Record<SecurityZoneLayout, string> = {
  auto: '自动',
  single_row: '单行',
  two_row: '双行',
}

export function serverSlotDefaultPortType(kind: ServerSlotKind): PortType {
  if (kind === 'nic_1g') return '1g'
  if (kind === 'nic_10g') return '10g'
  if (kind === 'hba') return 'other'
  return 'other'
}

export function newCoreLineCard(
  cardType: CoreCardType = 'ten_gigabit',
  portCount = 48,
): CoreLineCard {
  return {
    id: crypto.randomUUID().slice(0, 8),
    card_type: cardType,
    port_count: cardType === 'blank' ? 0 : Math.max(1, portCount),
  }
}

export const LINK_TYPE_LABELS: Record<NetworkLinkType, string> = {
  switch_server: '交换机 ↔ 服务器',
  switch_switch: '交换机 ↔ 交换机',
  switch_security: '交换机 ↔ 安全设备',
}

export const NODE_KIND_COLORS: Record<NetworkNodeKind, string> = {
  switch: '#409eff',
  server: '#67c23a',
  security: '#e6a23c',
}
