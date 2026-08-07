import type {
  CoreCardType,
  CoreLineCard,
  LayoutSlotDef,
  NetworkNode,
  NetworkNodeKind,
  PortLayout,
  PortType,
  ServerSlotKind,
  SwitchSubtype,
} from '@/api/network'
import { newCoreLineCard, SWITCH_SUBTYPE_DEFAULTS } from '@/api/network'
import type { NetworkDesignModel } from '@/api/networkModelDesign'
import {
  applySecurityLayoutConfig,
  applySwitchLayoutConfig,
  defaultPortLayout,
  generatePortsFromSlotsDef,
} from '@/utils/networkPortLayout'
import { applyServerFormFactor, defaultServerSlotsDef, newServerSlotDef } from '@/utils/serverRearPanel'
import type { SecurityZoneInput } from '@/utils/securityFrontPanel'
import { nextDeviceName } from '@/utils/topologyClone'
import { inferDeviceGroupFromDesignModel, inferFabricRoleFromDesignModel } from '@/utils/fabricRole'

export type DesignSlotType = 'nic_1g' | 'nic_10g' | 'raid' | 'disk_bay' | 'blank'

/** Slot 内单个接口：本端 / 对端设计信息 */
export interface DesignSlotInterface {
  index: number
  /** 接口类型：1g / 10g / other 等 */
  port_type: string
  /** 本端接口标签 */
  local_label: string
  /** 本端信息 */
  local_info: string
  /** 对端标签 */
  peer_label: string
  /** 对端信息 */
  peer_info: string
}

export interface DesignSlotAttr {
  index: number
  type: DesignSlotType | string
  port_count?: number
  raid_level?: string
  panel_row?: number
  panel_col?: number
  /** NIC/盘位等可编辑接口明细 */
  interfaces?: DesignSlotInterface[]
}

export function slotTypeLabel(type: string): string {
  return DESIGN_SLOT_TYPE_OPTIONS.find((o) => o.value === type)?.label || type
}

export function defaultPortTypeForSlot(type: string): string {
  if (type === 'nic_1g') return '1g'
  if (type === 'nic_10g') return '10g'
  if (type === 'disk_bay') return 'disk'
  return 'other'
}

export function syncSlotInterfaces(slot: DesignSlotAttr): DesignSlotInterface[] {
  const t = String(slot.type)
  if (t === 'raid' || t === 'blank') {
    slot.interfaces = []
    return []
  }
  const n = Math.max(1, Math.min(8, Number(slot.port_count) || 1))
  slot.port_count = n
  const prev = Array.isArray(slot.interfaces) ? slot.interfaces : []
  const defType = defaultPortTypeForSlot(t)
  const next: DesignSlotInterface[] = []
  for (let i = 0; i < n; i++) {
    const src = prev[i]
    // 千兆/万兆 Slot 强制接口速率与 Slot 类型一致，避免残留 10g/1g
    const portType =
      t === 'nic_1g' || t === 'nic_10g' ? defType : String(src?.port_type || defType)
    next.push({
      index: i + 1,
      port_type: portType,
      local_label: String(src?.local_label || `${slotTypeLabel(t).replace('接口', '')}${i + 1}`),
      local_info: String(src?.local_info || ''),
      peer_label: String(src?.peer_label || ''),
      peer_info: String(src?.peer_info || ''),
    })
  }
  slot.interfaces = next
  return next
}

export const DESIGN_SLOT_TYPE_OPTIONS: { value: DesignSlotType; label: string }[] = [
  { value: 'nic_1g', label: '千兆接口' },
  { value: 'nic_10g', label: '万兆接口' },
  { value: 'raid', label: 'RAID卡' },
  { value: 'disk_bay', label: '磁盘插槽' },
  { value: 'blank', label: '空白卡槽' },
]

export const DESIGN_RAID_LEVEL_OPTIONS = [
  { value: 'raid0', label: 'RAID 0' },
  { value: 'raid1', label: 'RAID 1' },
  { value: 'raid5', label: 'RAID 5' },
  { value: 'raid10', label: 'RAID 10' },
  { value: 'raid6', label: 'RAID 6' },
  { value: 'jbod', label: 'JBOD' },
]

/** 设计模型分类 → 拓扑节点 kind */
export function designCategoryToNodeKind(category: string): NetworkNodeKind {
  if (category === 'server' || category === 'software') return 'server'
  if (category === 'security') return 'security'
  return 'switch'
}

function asInt(v: unknown, fallback: number): number {
  const n = Number(v)
  return Number.isFinite(n) ? Math.trunc(n) : fallback
}

function mapSpeed(v: unknown): PortType {
  const s = String(v || '1g')
  if (s === '10g' || s === '25g') return '10g'
  if (s === '40_100g' || s === '100g') return '40_100g'
  return '1g'
}

/** 网络模型交换机样式 → PortLayout switch_subtype */
export function resolveDesignSwitchRole(attrs: Record<string, unknown>): SwitchSubtype {
  const role = String(attrs.switch_role || '').trim()
  if (role === 'gigabit' || role === 'ten_gigabit' || role === 'aggregation' || role === 'core') {
    return role
  }
  const dt = mapSpeed(attrs.downlink_type ?? attrs.lan_type ?? attrs.service_port_type)
  if (dt === '10g' || dt === '40_100g') return 'ten_gigabit'
  return 'gigabit'
}

export function normalizeDesignLineCards(raw: unknown): CoreLineCard[] {
  const list: CoreLineCard[] = []
  if (Array.isArray(raw)) {
    for (const item of raw) {
      if (!item || typeof item !== 'object') continue
      const src = item as Record<string, unknown>
      let cardType = String(src.card_type || 'ten_gigabit') as CoreCardType
      if (!['gigabit', 'ten_gigabit', '100g', 'blank'].includes(cardType)) {
        cardType = 'ten_gigabit'
      }
      const portCount =
        cardType === 'blank' ? 0 : Math.max(1, Math.min(128, asInt(src.port_count, 48)))
      list.push({
        id: String(src.id || crypto.randomUUID().slice(0, 8)),
        card_type: cardType,
        port_count: portCount,
      })
    }
  }
  return list.length ? list.slice(0, 16) : [newCoreLineCard('ten_gigabit', 48)]
}

/** 核心交换机：板卡数量 = 设备高度(U) */
export function syncCoreLineCardsByHeight(
  attrs: Record<string, unknown>,
  heightU: number,
): CoreLineCard[] {
  const n = Math.max(1, Math.min(16, Math.trunc(heightU) || 1))
  const prev = normalizeDesignLineCards(attrs.line_cards)
  const next: CoreLineCard[] = []
  for (let i = 0; i < n; i++) {
    next.push(prev[i] ? { ...prev[i] } : newCoreLineCard('ten_gigabit', 48))
  }
  attrs.line_cards = next
  attrs.chassis_height_u = n
  return next
}

function mapSlotKind(type: string): ServerSlotKind {
  if (type === 'nic_1g' || type === 'nic_10g' || type === 'raid') return type
  if (type === 'disk_bay' || type === 'blank') return 'blank'
  if (type === 'nic_25g') return 'nic_10g'
  if (type === 'hba') return 'raid'
  return 'blank'
}

/** 按 slot_count 规范化 slots 数组（前端本地） */
export function normalizeDesignSlots(attrs: Record<string, unknown>): DesignSlotAttr[] {
  const raw = Array.isArray(attrs.slots) ? (attrs.slots as Record<string, unknown>[]) : []
  let count = attrs.slot_count != null ? asInt(attrs.slot_count, raw.length || 2) : raw.length || 2
  count = Math.max(0, Math.min(16, count))
  attrs.slot_count = count
  const slots: DesignSlotAttr[] = []
  for (let i = 0; i < count; i++) {
    const src = raw[i] || {}
    let type = String(src.type || 'nic_10g')
    if (!['nic_1g', 'nic_10g', 'raid', 'disk_bay', 'blank'].includes(type)) {
      type = type === 'nic_25g' ? 'nic_10g' : type === 'hba' ? 'raid' : type === 'empty' ? 'blank' : 'nic_10g'
    }
    const entry: DesignSlotAttr = { index: i + 1, type }
    if (type === 'nic_1g' || type === 'nic_10g') {
      entry.port_count = Math.max(1, Math.min(8, asInt(src.port_count, 2)))
    } else if (type === 'raid') {
      entry.raid_level = String(src.raid_level || 'raid1')
      entry.port_count = 0
    } else if (type === 'blank') {
      entry.port_count = 0
    } else {
      entry.port_count = Math.max(1, Math.min(8, asInt(src.port_count, 1)))
    }
    if (src.panel_row != null) entry.panel_row = asInt(src.panel_row, 0)
    if (src.panel_col != null) entry.panel_col = asInt(src.panel_col, 0)
    if (Array.isArray(src.interfaces)) {
      entry.interfaces = src.interfaces as DesignSlotInterface[]
    }
    syncSlotInterfaces(entry)
    slots.push(entry)
  }
  attrs.slots = slots
  return slots
}

/**
 * 按模型属性自动生成面板布局（始终由属性驱动，不沿用手工编辑结果）。
 */
export function buildPortLayoutFromDesignModel(model: NetworkDesignModel): PortLayout | null {
  if (model.category === 'software') return null

  const kind = designCategoryToNodeKind(model.category)
  const attrs = { ...(model.attributes || {}) }
  const heightU = Math.max(1, asInt(attrs.form_factor_u ?? model.height_u, model.height_u || 1))

  if (kind === 'switch') {
    const layout = defaultPortLayout('switch', undefined, 1)
    const role = resolveDesignSwitchRole(attrs)
    if (role === 'core') {
      const heightU = Math.max(1, asInt(attrs.chassis_height_u ?? model.height_u, model.height_u || 1))
      const cards = syncCoreLineCardsByHeight(attrs, heightU)
      applySwitchLayoutConfig(layout, {
        subtype: 'core',
        mainPortCount: 48,
        uplinkPortCount: 0,
        uplinkPosition: 'right',
        lineCards: cards,
      })
      layout.height_u = heightU
    } else {
      const defaults = SWITCH_SUBTYPE_DEFAULTS[role]
      let downlink = Math.max(
        1,
        asInt(attrs.downlink_count ?? attrs.lan_count ?? attrs.service_port_count, defaults.mainPortCount),
      )
      if (role === 'gigabit' || role === 'ten_gigabit' || role === 'aggregation') {
        const cards = Math.max(1, Math.min(16, asInt(attrs.optical_card_count, 1)))
        let ppc = asInt(attrs.optical_ports_per_card, 0)
        if (ppc <= 0) ppc = Math.max(1, Math.floor(downlink / cards))
        ppc = Math.max(1, Math.min(128, ppc))
        downlink = Math.max(1, Math.min(256, cards * ppc))
      }
      const uplink = Math.max(
        0,
        asInt(attrs.uplink_count ?? attrs.wan_count, defaults.uplinkPortCount),
      )
      applySwitchLayoutConfig(layout, {
        subtype: role,
        mainPortCount: downlink,
        uplinkPortCount: uplink,
        uplinkPosition: attrs.uplink_position === 'middle' ? 'middle' : 'right',
      })
    }
    layout.layout_locked = true
    return layout
  }

  if (kind === 'security') {
    const layout = defaultPortLayout('security', undefined, heightU)
    const dataCount = asInt(attrs.data_port_count, 8)
    const dataType = mapSpeed(attrs.data_port_type)
    const ha = asInt(attrs.ha_ports, 0)
    const mgmt = asInt(attrs.mgmt_ports, 1)
    const control = asInt(attrs.control_ports, 1)
    const zones: SecurityZoneInput[] = [
      { label: 'DATA', port_type: dataType, count: dataCount, zone_layout: 'two_row' },
    ]
    if (control > 0) {
      zones.push({ label: 'CONTROL', port_type: '1g', count: control, zone_layout: 'single_row' })
    }
    if (ha > 0) {
      zones.push({ label: 'HA', port_type: '10g', count: ha, zone_layout: 'single_row' })
    }
    if (mgmt > 0) {
      zones.push({ label: 'MGMT', port_type: '1g', count: mgmt, zone_layout: 'single_row' })
    }
    applySecurityLayoutConfig(layout, { heightU, zones, preservePeers: false })
    layout.layout_locked = true
    return layout
  }

  const formFactor = (heightU === 2 || heightU === 4 ? heightU : 1) as 1 | 2 | 4
  const layout = defaultPortLayout('server', undefined, formFactor)
  applyServerFormFactor(layout, formFactor)
  const slots = normalizeDesignSlots(attrs)
  if (slots.length) {
    const defs: LayoutSlotDef[] = slots.map((slot) => {
      const kindSlot = mapSlotKind(String(slot.type))
      if (slot.type === 'blank') {
        return {
          ...newServerSlotDef('blank', 0, 'horizontal'),
          zone_label: '空白',
        }
      }
      if (slot.type === 'disk_bay') {
        const bay = Math.max(1, asInt(slot.port_count, 1))
        return {
          ...newServerSlotDef('blank', 0, 'horizontal'),
          zone_label: `磁盘×${bay}`,
        }
      }
      if (slot.type === 'raid') {
        return {
          ...newServerSlotDef('raid', 0, 'horizontal'),
          zone_label: String(slot.raid_level || 'raid1').toUpperCase(),
        }
      }
      const portCount = asInt(slot.port_count, kindSlot.startsWith('nic') ? 2 : 0)
      return newServerSlotDef(kindSlot, portCount, 'horizontal')
    })
    layout.slots_def = defs
    layout.slot_count = defs.length
    generatePortsFromSlotsDef(layout, false)
  } else {
    layout.slots_def = defaultServerSlotsDef(formFactor)
    layout.slot_count = layout.slots_def.length
    generatePortsFromSlotsDef(layout, false)
  }
  // 前后硬盘数量写入 layout 元数据，供简图展示
  layout.height_u = formFactor
  ;(layout as PortLayout & { disk_front_count?: number; disk_rear_count?: number }).disk_front_count =
    asInt(attrs.disk_front_count, 0)
  ;(layout as PortLayout & { disk_rear_count?: number }).disk_rear_count = Math.min(
    4,
    asInt(attrs.disk_rear_count, 0),
  )
  layout.layout_locked = true
  return layout
}

/** 将设计模型实例化为拓扑画布节点 */
export function stampDesignModelOntoCanvas(
  model: NetworkDesignModel,
  topologyId: string,
  x: number,
  y: number,
  allNodes: NetworkNode[],
): NetworkNode {
  const kind = designCategoryToNodeKind(model.category)
  const layout = buildPortLayoutFromDesignModel(model)
  annotatePortPurposes(layout)
  const template: NetworkNode = {
    id: crypto.randomUUID(),
    topology_id: topologyId,
    kind,
    name: model.name,
    device_id: null,
    device_model_id: model.device_model_id,
    design_model_id: model.id,
    contract_device_name: model.contract_device_name,
    network_role: inferFabricRoleFromDesignModel(model),
    device_group: inferDeviceGroupFromDesignModel(model),
    switch_port_count: 0,
    slots: null,
    pos_x: 0,
    pos_y: 0,
    on_canvas: false,
    port_layout: layout,
  }
  const name = nextDeviceName(allNodes, template)
  return {
    ...template,
    id: crypto.randomUUID(),
    name,
    pos_x: x,
    pos_y: y,
    on_canvas: true,
  }
}

/** 按 slot zone / group 为端口补全 purpose（已有 purpose 不覆盖） */
export function annotatePortPurposes(layout: PortLayout | null | undefined) {
  if (!layout?.ports?.length) return
  for (const p of layout.ports) {
    if (p.purpose) continue
    const slot = p.slot_index != null ? layout.slots_def?.[p.slot_index] : null
    const hay = `${p.group_id || ''} ${slot?.zone_label || ''} ${slot?.server_slot_kind || ''}`.toUpperCase()
    if (hay.includes('PEER')) p.purpose = 'PEER'
    else if (hay.includes('UPLINK') || hay.includes('上联')) p.purpose = 'UPLINK'
    else if (hay.includes('MGMT') || hay.includes('管理')) p.purpose = 'MGMT'
    else if (
      hay.includes('SERVER') ||
      hay.includes('NIC') ||
      hay.includes('业务') ||
      hay.includes('DOWN')
    ) {
      p.purpose = 'SERVER'
    } else if (layout.switch_subtype === 'core' || layout.switch_subtype === 'aggregation') {
      // 核心/汇聚：高速率口倾向 UPLINK，其余 DOWNLINK
      p.purpose = p.port_type === '40_100g' ? 'UPLINK' : 'DOWNLINK'
    } else if (layout.switch_subtype === 'gigabit' || layout.switch_subtype === 'ten_gigabit') {
      p.purpose = p.port_type === '40_100g' || (layout.uplink_port_count && p.slot_index != null)
        ? 'UPLINK'
        : 'SERVER'
    }
  }
}
