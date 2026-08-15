import type {
  CoreCardType,
  CoreLineCard,
  FramePort,
  LayoutSlotDef,
  NetworkNode,
  NetworkNodeKind,
  PortLayout,
  PortType,
  ServerSlotKind,
  SlotInterfaceGroup,
  SwitchSubtype,
} from '@/api/network'
import { newCoreLineCard, SWITCH_SUBTYPE_DEFAULTS } from '@/api/network'
import type { NetworkDesignModel } from '@/api/networkModelDesign'
import {
  applySecurityLayoutConfig,
  applySwitchLayoutConfig,
  defaultPortLayout,
  generatePortsFromSlotsDef,
  newInterfaceGroup,
  syncPortsFromSlotsDef,
} from '@/utils/networkPortLayout'
import { applyServerFormFactor, defaultServerSlotsDef, newServerSlotDef } from '@/utils/serverRearPanel'
import type { SecurityZoneInput } from '@/utils/securityFrontPanel'
import { nextDeviceName } from '@/utils/topologyClone'
import { inferDeviceGroupFromDesignModel, inferFabricRoleFromDesignModel } from '@/utils/fabricRole'
import {
  annotatePortMediaAndInterface,
  isBmcSwitchFromDesignModel,
} from '@/utils/wiringDeviceType'
import {
  effectivePortCount,
  portTypeForSlot,
  readSwitchSlots,
  readSwitchSystemPorts,
  resolveSlotPort,
  slotsToLineCards,
  syncSwitchDerivedCounts,
  SWITCH_SYSTEM_PORT_NS,
  type SwitchSlotAttr,
  type SwitchSystemPortAttr,
} from '@/utils/switchModelAttrs'
import {
  isOnboardSlot,
  listServerPorts,
  normalizeFlexSpeed,
  normalizeServerFormFactor,
  readPcieSlots,
  readServerIfaceSlots,
  serverSlotNamePrefix,
  syncServerDerivedAttrs,
  type ServerFlexSpeed,
  type ServerIfaceSlotAttr,
  type ServerPcieSlotAttr,
} from '@/utils/serverModelAttrs'
import {
  normalizeSecurityFormFactor,
  readSecurityIfaceSlots,
  securitySlotsToZones,
  syncSecurityDerivedAttrs,
  type SecurityIfaceSlotAttr,
} from '@/utils/securityModelAttrs'

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
  /** 设备内稳定唯一 ID，供拓扑布线引用 */
  id?: string
  /** 人读编号，如 BMC1 / LOM1 / F10G1 */
  code?: string
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
  const prev = Array.isArray(slot.interfaces) ? slot.interfaces : []
  const n = Math.max(1, Math.min(32, Number(slot.port_count) || prev.length || 1))
  slot.port_count = n
  const defType = defaultPortTypeForSlot(t)
  const next: DesignSlotInterface[] = []
  for (let i = 0; i < n; i++) {
    const src = prev[i]
    const portType =
      t === 'nic_1g' || t === 'nic_10g' ? defType : String(src?.port_type || defType)
    next.push({
      index: i + 1,
      port_type: portType,
      local_label: String(src?.local_label || `${slotTypeLabel(t).replace('接口', '')}${i + 1}`),
      local_info: String(src?.local_info || ''),
      peer_label: String(src?.peer_label || ''),
      peer_info: String(src?.peer_info || ''),
      id: src?.id ? String(src.id) : undefined,
      code: src?.code ? String(src.code) : undefined,
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
  if (s === '25g') return '25g'
  if (s === '10g') return '10g'
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
      let cardTypeRaw = String(src.card_type || 'ten_gigabit')
      if (cardTypeRaw === '25g') cardTypeRaw = 'ten_gigabit'
      else if (cardTypeRaw === '40g' || cardTypeRaw === '400g') cardTypeRaw = '100g'
      let cardType = cardTypeRaw as CoreCardType
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
  if (type === 'nic_25g') return 'nic_10g' // ServerSlotKind 无 25g 槽位枚举；口类型由 ports 保留 25g
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
    syncSwitchDerivedCounts(attrs)
    const switchSlots = readSwitchSlots(attrs)
    if (Array.isArray(attrs.switch_slots) && switchSlots.length) {
      layout.switch_subtype = role
      layout.uplink_position = attrs.uplink_position === 'middle' ? 'middle' : 'right'
      layout.line_cards =
        role === 'core' || role === 'aggregation' ? slotsToLineCards(switchSlots) : null
      const isCoreAgg = role === 'core' || role === 'aggregation'
      const defs: LayoutSlotDef[] = []
      for (const s of switchSlots) {
        const count = effectivePortCount(s)
        if (s.card_type === 'blank' || count <= 0) {
          defs.push({
            groups: [],
            layout_x: null,
            layout_y: 0,
            zone_label: `Slot${s.index} 空白`,
          })
          continue
        }
        const pt = portTypeForSlot(s)
        const groupRole =
          s.purpose === 'UPLINK' ||
          s.purpose === 'DOWNLINK_UPLINK' ||
          s.card_type === '100g' ||
          s.card_type === '40g'
            ? 'uplink'
            : isCoreAgg
              ? 'card'
              : 'main'
        const group = newInterfaceGroup(pt, count, {
          role: groupRole,
          grid_cols: pt === '40_100g' ? Math.min(2, count) : Math.min(24, count),
        })
        group.id = `slot${s.index}`
        group.id_ns = `slot${s.index}`
        defs.push({
          groups: [group],
          layout_x: defs.length === 0 ? 0 : null,
          layout_y: 0,
          zone_label: `Slot${s.index} ${s.purpose}`,
        })
      }
      const ethMgmt = Math.max(
        0,
        asInt(isCoreAgg ? (attrs.eth_mgmt_ports ?? attrs.mgmt_ports) : attrs.mgmt_ports, 1),
      )
      if (ethMgmt > 0) {
        const g = newInterfaceGroup('1g', ethMgmt, { role: 'mgmt', grid_cols: ethMgmt })
        g.id = 'eth-mgmt'
        g.id_ns = 'eth-mgmt'
        defs.push({
          groups: [g],
          layout_x: null,
          layout_y: 0,
          zone_label: isCoreAgg ? 'ETH管理口' : 'MGMT',
        })
      }
      if (isCoreAgg) {
        const consolePorts = Math.max(0, asInt(attrs.console_ports, 0))
        if (consolePorts > 0) {
          const g = newInterfaceGroup('other', consolePorts, { role: 'mgmt', grid_cols: consolePorts })
          g.id = 'console'
          g.id_ns = 'console'
          defs.push({
            groups: [g],
            layout_x: null,
            layout_y: 0,
            zone_label: 'Console口',
          })
        }
        const usbPorts = Math.max(0, asInt(attrs.usb_ports, 0))
        if (usbPorts > 0) {
          const g = newInterfaceGroup('other', usbPorts, { role: 'mgmt', grid_cols: Math.min(4, usbPorts) })
          g.id = 'usb'
          g.id_ns = 'usb'
          defs.push({
            groups: [g],
            layout_x: null,
            layout_y: 0,
            zone_label: 'USB接口',
          })
        }
      }
      const stackPorts = Math.max(0, asInt(attrs.stack_cluster_ports, 0))
      if (stackPorts > 0) {
        const g = newInterfaceGroup('10g', stackPorts, { role: 'uplink', grid_cols: Math.min(4, stackPorts) })
        g.id = 'stack'
        g.id_ns = 'stack'
        defs.push({
          groups: [g],
          layout_x: null,
          layout_y: 0,
          zone_label: '堆叠/集群接口',
        })
      }
      layout.slots_def = defs
      layout.slot_count = defs.length
      layout.main_port_count = asInt(attrs.downlink_count, 0)
      // 上联口数：含 UPLINK 槽与 40/100G 板卡口
      const uplinkPorts = switchSlots.reduce((sum, s) => {
        if (s.card_type === 'blank') return sum
        if (s.purpose === 'UPLINK' || s.purpose === 'DOWNLINK_UPLINK' || s.card_type === '100g') {
          return sum + effectivePortCount(s)
        }
        return sum
      }, 0)
      layout.uplink_port_count = Math.max(asInt(attrs.uplink_count, 0), uplinkPorts)
      if (role === 'core' || role === 'aggregation') {
        layout.height_u = Math.max(
          1,
          asInt(attrs.chassis_height_u ?? model.height_u, switchSlots.length),
        )
      }
      syncPortsFromSlotsDef(layout, false)
      applySwitchSlotPortLabels(layout, switchSlots)
      applySwitchSystemPortIdentities(layout, readSwitchSystemPorts(attrs))
      layout.layout_locked = true
      return layout
    }
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
      const cards = Math.max(1, Math.min(16, asInt(attrs.optical_card_count, 1)))
      let ppc = asInt(attrs.optical_ports_per_card, 0)
      if (ppc <= 0) ppc = Math.max(1, Math.floor(downlink / cards))
      ppc = Math.max(1, Math.min(128, ppc))
      downlink = Math.max(1, Math.min(256, cards * ppc))
      const uplink = Math.max(0, asInt(attrs.uplink_count ?? attrs.wan_count, defaults.uplinkPortCount))
      applySwitchLayoutConfig(layout, {
        subtype: role,
        mainPortCount: downlink,
        uplinkPortCount: uplink,
        uplinkPosition: attrs.uplink_position === 'middle' ? 'middle' : 'right',
      })
      // 兼容旧属性：板卡口数由 optical_* 推导后写入 layout 主口
      layout.main_port_count = downlink
      layout.uplink_port_count = uplink
    }
    layout.layout_locked = true
    return layout
  }

  if (kind === 'security') {
    const heightSec = normalizeSecurityFormFactor(attrs.chassis_height_u ?? attrs.form_factor_u ?? heightU)
    const layout = defaultPortLayout('security', undefined, heightSec)
    syncSecurityDerivedAttrs(attrs)
    const ifaceSlots = readSecurityIfaceSlots(attrs)
    let zones: SecurityZoneInput[]
    if (Array.isArray(attrs.security_slots) && ifaceSlots.length) {
      zones = securitySlotsToZones(ifaceSlots)
    } else {
      const dataCount = asInt(attrs.data_port_count, 8)
      const dataType = mapSpeed(attrs.data_port_type)
      const ha = asInt(attrs.ha_ports, 0)
      const mgmt = asInt(attrs.mgmt_ports, 1)
      const control = asInt(attrs.control_ports, 1)
      zones = [{ label: 'DATA', port_type: dataType, count: dataCount, zone_layout: 'two_row' }]
      if (control > 0) {
        zones.push({ label: 'CONTROL', port_type: '1g', count: control, zone_layout: 'single_row' })
      }
      if (ha > 0) {
        zones.push({ label: 'HA', port_type: '10g', count: ha, zone_layout: 'single_row' })
      }
      if (mgmt > 0) {
        zones.push({ label: 'MGMT', port_type: '1g', count: mgmt, zone_layout: 'single_row' })
      }
    }
    applySecurityLayoutConfig(layout, { heightU: heightSec, zones, preservePeers: false })
    applySecurityIfacePortLabels(layout, ifaceSlots)
    layout.layout_locked = true
    return layout
  }

  const formFactor = normalizeServerFormFactor(attrs.form_factor_u ?? heightU)
  const layout = defaultPortLayout('server', undefined, formFactor)
  applyServerFormFactor(layout, formFactor)
  syncServerDerivedAttrs(attrs)
  const ifaceSlots = readServerIfaceSlots(attrs)
  if (ifaceSlots.length && (Array.isArray(attrs.server_slots) || Array.isArray(attrs.slots))) {
    const flexSpeed = normalizeFlexSpeed(attrs.flex_io_speed)
    const defs: LayoutSlotDef[] = []
    for (const s of ifaceSlots) {
      if (!isOnboardSlot(s)) continue
      defs.push(buildServerIfaceSlotDef(s, flexSpeed))
    }
    for (const pcie of readPcieSlots(attrs)) {
      defs.push(buildPcieSlotDef(pcie, flexSpeed))
    }
    layout.slots_def = defs
    layout.slot_count = defs.length
    generatePortsFromSlotsDef(layout, false)
    applyServerIfaceSlotPortLabels(layout, attrs)
  } else {
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
  }
  // 前后硬盘数量写入 layout 元数据，供简图展示
  layout.height_u = formFactor
  ;(layout as PortLayout & { disk_front_count?: number; disk_rear_count?: number }).disk_front_count =
    asInt(attrs.disk_front_count, 0)
  ;(layout as PortLayout & { disk_rear_count?: number }).disk_rear_count = Math.min(
    6,
    asInt(attrs.disk_rear_count, 0),
  )
  layout.layout_locked = true
  return layout
}

function namedGroup(
  portType: PortType,
  count: number,
  idNs: string,
  role: NonNullable<SlotInterfaceGroup['role']>,
) {
  const g = newInterfaceGroup(portType, count, { role, grid_cols: Math.min(4, count) })
  g.id = idNs
  g.id_ns = idNs
  return g
}

function buildServerIfaceSlotDef(slot: ServerIfaceSlotAttr, _flexSpeed: ServerFlexSpeed): LayoutSlotDef {
  const groups = []
  const bmc = Math.max(0, Number(slot.bmc_count) || 0)
  const ipmi = Math.max(0, Number(slot.ipmi_count) || 0)
  if (slot.ports_1g > 0) {
    groups.push(namedGroup('1g', slot.ports_1g, 'lom', 'card'))
  }
  if (bmc > 0) groups.push(namedGroup('bmc', bmc, 'bmc', 'mgmt'))
  if (ipmi > 0) groups.push(namedGroup('bmc', ipmi, 'ipmi', 'mgmt'))
  if (slot.hdmi_count > 0) groups.push(namedGroup('other', slot.hdmi_count, 'vga', 'mgmt'))
  if (slot.usb_count > 0) groups.push(namedGroup('other', slot.usb_count, 'usb', 'mgmt'))
  const kind: ServerSlotKind = slot.ports_1g > 0 ? 'nic_1g' : groups.length ? 'nic_1g' : 'blank'
  return {
    server_slot_kind: kind,
    orientation: 'horizontal',
    groups,
    layout_x: null,
    layout_y: null,
    layout_w: null,
    layout_h: null,
    zone_label: serverSlotNamePrefix(slot),
  }
}

function buildPcieSlotDef(slot: ServerPcieSlotAttr, flexSpeed: ServerFlexSpeed): LayoutSlotDef {
  const n = Math.max(0, Number(slot.flex_ports) || 0)
  const groups = n > 0 ? [namedGroup(flexSpeed === '25ge' ? '25g' : '10g', n, `pcie${slot.index}`, 'card')] : []
  return {
    server_slot_kind: n > 0 ? 'nic_10g' : 'blank',
    orientation: 'vertical',
    groups,
    layout_x: null,
    layout_y: null,
    layout_w: null,
    layout_h: null,
    zone_label: `PCIE${slot.index}`,
  }
}

function applyServerIfaceSlotPortLabels(layout: PortLayout, attrs: Record<string, unknown>) {
  if (!layout.ports?.length) return
  const specs = listServerPorts(attrs)
  const byId = new Map(specs.map((s) => [s.id, s]))
  for (const p of layout.ports) {
    const spec = byId.get(p.id)
    if (!spec) {
      if (p.port_type === 'bmc') p.purpose = 'MGMT'
      else if (!p.purpose) p.purpose = 'SERVER'
      continue
    }
    p.code = spec.code
    p.label = spec.code
    p.media = spec.iface_type === 'optical' ? 'FIBER' : 'COPPER'
    if (spec.kind === 'bmc' || spec.kind === 'ipmi' || spec.kind === 'vga' || spec.kind === 'usb') {
      p.purpose = 'MGMT'
    } else {
      p.purpose = 'SERVER'
    }
  }
}

/** 安全设备：按 zone_label 写入 slotx-10G-(n) / slotx-1G-(n) */
function applySecurityIfacePortLabels(layout: PortLayout, _slots: SecurityIfaceSlotAttr[]) {
  if (!layout.ports?.length || !layout.slots_def?.length) return
  for (let zi = 0; zi < layout.slots_def.length; zi++) {
    const def = layout.slots_def[zi]
    const zoneLabel = String(def.zone_label || '')
    const m = /^Slot(\d+)\s+(10G|1G|CONTROL|HA|MGMT|USB)$/i.exec(zoneLabel)
    if (!m) continue
    const slotIdx = Number(m[1])
    const kind = m[2].toUpperCase()
    const list = layout.ports
      .filter((p) => p.slot_index === zi + 1)
      .slice()
      .sort((a, b) => a.id.localeCompare(b.id))
    list.forEach((p, i) => {
      const n = i + 1
      if (kind === '10G') p.label = `slot${slotIdx}-10G-${n}`
      else if (kind === '1G') p.label = `slot${slotIdx}-1G-${n}`
      else if (kind === 'CONTROL') p.label = `slot${slotIdx}-CTL-${n}`
      else if (kind === 'HA') p.label = `slot${slotIdx}-HA-${n}`
      else if (kind === 'MGMT') {
        p.label = `slot${slotIdx}-MGMT-${n}`
        p.purpose = 'MGMT'
      } else if (kind === 'USB') p.label = `slot${slotIdx}-USB-${n}`
    })
  }
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
  annotatePortPurposes(layout, kind)
  annotatePortMediaAndInterface(layout?.ports, (model.attributes || {}) as Record<string, unknown>)
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
    is_bmc_switch: kind === 'switch' ? isBmcSwitchFromDesignModel(model) : false,
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

/** 按 group.role / zone 为端口补全 purpose（已有 purpose 不覆盖） */
export function annotatePortPurposes(
  layout: PortLayout | null | undefined,
  kind?: NetworkNode['kind'] | null,
) {
  if (!layout?.ports?.length) return
  const isServer = kind === 'server'
  for (const p of layout.ports) {
    // 优先：slots_def 中 group.role（有明确 role 时纠正旧错误打标）
    let groupRole: string | null = null
    if (p.group_id && layout.slots_def?.length) {
      for (const slot of layout.slots_def) {
        const g = slot.groups?.find((x) => x.id === p.group_id)
        if (g?.role) {
          groupRole = g.role
          break
        }
      }
    }
    const pt = String(p.port_type || '').toLowerCase()
    // 服务器业务 NIC：强制 SERVER，覆盖历史误标 UPLINK（A3 空池根因）
    if (
      isServer &&
      (pt === '1g' || pt === '10g' || pt === '25g') &&
      groupRole !== 'mgmt' &&
      groupRole !== 'uplink'
    ) {
      const lab = String(p.label || '').toUpperCase()
      if (!lab.includes('IPMI') && !lab.includes('BMC') && pt !== 'bmc') {
        p.purpose = 'SERVER'
        continue
      }
    }
    if (groupRole === 'uplink') {
      p.purpose = 'UPLINK'
      continue
    }
    if (groupRole === 'mgmt') {
      p.purpose = 'MGMT'
      continue
    }
    if (groupRole === 'main' || groupRole === 'card') {
      // 40/100G 板卡口默认归上联用途（与端口池一致）；zone 明示下联时保留 DOWNLINK
      if (p.port_type === '40_100g') {
        const slotIdx =
          p.slot_index != null && p.slot_index > 0 ? p.slot_index - 1 : p.slot_index
        const slot =
          slotIdx != null && slotIdx >= 0 ? layout.slots_def?.[slotIdx] : null
        const hay = `${slot?.zone_label || ''}`.toUpperCase()
        if (hay.includes('DOWNLINK') && !hay.includes('UPLINK')) {
          p.purpose = isServer ? 'SERVER' : 'DOWNLINK'
        } else {
          p.purpose = 'UPLINK'
        }
      } else {
        p.purpose = isServer ? 'SERVER' : 'DOWNLINK'
      }
      continue
    }
    if (p.purpose) continue
    const slotIdx =
      p.slot_index != null && p.slot_index > 0 ? p.slot_index - 1 : p.slot_index
    const slot =
      slotIdx != null && slotIdx >= 0 ? layout.slots_def?.[slotIdx] : null
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
      p.purpose = isServer ? 'SERVER' : 'DOWNLINK'
    } else if (/^U\d+/i.test(String(p.label || '')) || p.port_type === '40_100g') {
      p.purpose = 'UPLINK'
    } else if (p.port_type === '1g' || p.port_type === '10g' || p.port_type === '25g') {
      p.purpose = isServer ? 'SERVER' : 'DOWNLINK'
    }
  }
}

/** 批量为拓扑节点补全端口 purpose（加载旧拓扑时用） */
export function annotateNodesPortPurposes(nodes: NetworkNode[]) {
  for (const n of nodes) {
    annotatePortPurposes(n.port_layout, n.kind)
    annotatePortMediaAndInterface(n.port_layout?.ports)
  }
}

/**
 * 用最新设备模型重建节点 port_layout（保留已有对端连线）。
 * 确保拓扑接口数量/类型与模型设计一致。
 */
export function refreshNodePortLayoutFromDesignModel(
  node: NetworkNode,
  model: NetworkDesignModel,
): boolean {
  if (!node.design_model_id || node.design_model_id !== model.id) return false
  const next = buildPortLayoutFromDesignModel(model)
  if (!next) return false
  annotatePortPurposes(next, node.kind)
  annotatePortMediaAndInterface(next.ports, model.attributes as Record<string, unknown>)
  if (node.kind === 'switch') {
    node.is_bmc_switch = isBmcSwitchFromDesignModel(model)
  }

  const oldPorts = node.port_layout?.ports || []
  const peerByLabel = new Map<string, FramePort>()
  for (const p of oldPorts) {
    if (!p.peer_node_id) continue
    const key = `${p.port_type}|${String(p.label || '').trim()}`
    if (key !== '|') peerByLabel.set(key, p)
  }
  for (const p of next.ports || []) {
    const key = `${p.port_type}|${String(p.label || '').trim()}`
    const old = peerByLabel.get(key)
    if (!old) continue
    p.peer_node_id = old.peer_node_id
    p.peer_port = old.peer_port
    p.peer_label = old.peer_label
    p.peer_device_id = old.peer_device_id ?? null
    p.peer_device_name = old.peer_device_name ?? null
  }

  node.port_layout = next
  if (!node.network_role) {
    node.network_role = inferFabricRoleFromDesignModel(model)
  }
  if (!node.device_group) {
    node.device_group = inferDeviceGroupFromDesignModel(model)
  }
  return true
}

/** 按 design_model_id 批量同步拓扑节点接口布局 */
export function syncTopologyNodesFromDesignModels(
  nodes: NetworkNode[],
  models: NetworkDesignModel[],
): number {
  const byId = new Map(models.map((m) => [m.id, m]))
  let updated = 0
  for (const node of nodes) {
    if (!node.design_model_id) continue
    const model = byId.get(node.design_model_id)
    if (!model) continue
    if (refreshNodePortLayoutFromDesignModel(node, model)) updated += 1
  }
  if (!updated) annotateNodesPortPurposes(nodes)
  else annotateNodesPortPurposes(nodes)
  return updated
}

/** 按 switch_slots.port_start 写入端口标签（slotx 连续编号） */
function moduleToMediaKind(module: string): FramePort['media_kind'] {
  const m = String(module || '')
  if (m === 'RJ45' || m === 'SFP' || m === 'SFP+' || m === 'SFP28' || m === 'QSFP+' || m === 'QSFP28') return m
  if (m === 'USB') return 'OTHER'
  return 'FIBER'
}

function applySwitchSlotPortLabels(layout: PortLayout, switchSlots: SwitchSlotAttr[]) {
  if (!layout.ports?.length) return
  for (const s of switchSlots) {
    const prefix = `slot${s.index}-p`
    const ports = layout.ports
      .filter((p) => p.id.startsWith(prefix))
      .slice()
      .sort((a, b) => {
        const na = Number(/-p(\d+)$/.exec(a.id)?.[1] ?? 0)
        const nb = Number(/-p(\d+)$/.exec(b.id)?.[1] ?? 0)
        return na - nb
      })
    ports.forEach((p, i) => {
      const spec = resolveSlotPort(s, i)
      p.id = spec.id
      p.code = spec.code
      p.label = spec.code
      p.slot_index = s.index
      p.media = spec.iface_type === 'copper' ? 'COPPER' : 'FIBER'
      p.media_kind = moduleToMediaKind(spec.module)
      if (s.purpose === 'BLANK') p.purpose = 'OTHER'
      else if (
        s.purpose === 'UPLINK' ||
        s.purpose === 'DOWNLINK_UPLINK' ||
        s.card_type === '100g'
      ) {
        p.purpose = 'UPLINK'
      } else {
        p.purpose = 'DOWNLINK'
      }
    })
  }
}

function applySwitchSystemPortIdentities(layout: PortLayout, systemPorts: SwitchSystemPortAttr[]) {
  if (!layout.ports?.length || !systemPorts.length) return
  const byNs = new Map<string, typeof layout.ports>()
  for (const p of layout.ports) {
    if (p.id.startsWith('slot')) continue
    const ns = p.id.replace(/-p\d+$/, '')
    const list = byNs.get(ns) || []
    list.push(p)
    byNs.set(ns, list)
  }
  const kindNs: Record<string, string> = { ...SWITCH_SYSTEM_PORT_NS }
  for (const spec of systemPorts) {
    const ns = kindNs[spec.kind]
    const list = (byNs.get(ns) || []).slice().sort((a, b) => {
      const na = Number(/-p(\d+)$/.exec(a.id)?.[1] ?? 0)
      const nb = Number(/-p(\d+)$/.exec(b.id)?.[1] ?? 0)
      return na - nb
    })
    const p = list[spec.index]
    if (!p) continue
    p.id = spec.id
    p.code = spec.code
    p.label = spec.code
    p.media = spec.iface_type === 'copper' ? 'COPPER' : 'FIBER'
    p.media_kind = moduleToMediaKind(spec.module)
    p.purpose = spec.kind === 'stack' ? 'PEER' : spec.kind === 'usb' ? 'OTHER' : 'MGMT'
    p.port_group = spec.kind.toUpperCase()
  }
}

