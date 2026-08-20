import type { DesignSlotAttr } from '@/utils/designModelToNode'
import { resolveDesignSwitchRole } from '@/utils/designModelToNode'
import { readPcieSlots, readServerIfaceSlots, serverSlotNicPaletteLabel } from '@/utils/serverModelAttrs'
import { readSecurityIfaceSlots } from '@/utils/securityModelAttrs'
import {
  effectivePortCount,
  portTypeForSlot,
  readSwitchSlots,
  type SwitchSlotAttr,
} from '@/utils/switchModelAttrs'

export type PanelItemKind =
  | 'slot'
  | 'psu'
  | 'bmc'
  | 'usb'
  | 'hdmi'
  | 'disk_front'
  | 'disk_rear'
  | 'fan'
  | 'port_main'
  | 'port_uplink'
  | 'line_card'
export type PanelSide = 'front' | 'rear'

export interface PanelLayoutItem {
  id: string
  kind: PanelItemKind
  label: string
  side: PanelSide
  slot_index?: number
  row: number
  col: number
  w?: number
  h?: number
  /** 块内接口数量（交换机下联/上联/板卡） */
  port_count?: number
  /** 块内接口类型：1g / 10g / 40_100g 等 */
  port_type?: string
  /** 接口编号起点（万兆下联跨 Slot 连续） */
  port_start?: number
  /** 空板卡：无接口 */
  blank?: boolean
}

export interface PanelSideLayout {
  cols: number
  rows: number
  items: PanelLayoutItem[]
}

/** 网格细化倍率（单元格边长约为早期版本的 1/4） */
export const PANEL_GRID_SCALE = 4

/** 前后面板共用同一自定义网格尺寸 */
export interface PanelLayoutConfig {
  /** 列数（宽） */
  cols: number
  /** 行数（高） */
  rows: number
  /** 已按 PANEL_GRID_SCALE 细化；缺省时在 normalize 中迁移 */
  grid_scale?: number
  front: PanelSideLayout
  rear: PanelSideLayout
}

export interface PanelPaletteItem {
  id: string
  kind: PanelItemKind
  label: string
  side: PanelSide
  slot_index?: number
  port_count?: number
  port_type?: string
  /** 接口编号起点（与 switch_slots.port_start 对齐） */
  port_start?: number
  blank?: boolean
}

const SLOT_LABEL: Record<string, string> = {
  nic_1g: '千兆',
  nic_10g: '万兆',
  raid: 'RAID',
  disk_bay: '磁盘',
  blank: '空白',
}

const CARD_TYPE_SHORT: Record<string, string> = {
  gigabit: '1G',
  ten_gigabit: '10G',
  '25g': '25G',
  '40g': '40G',
  '100g': '100G',
  '400g': '400G',
  blank: '空白',
}

function switchSlotPurposeLabel(purpose: string): string {
  if (purpose === 'UPLINK') return '上联 / UPLINK'
  if (purpose === 'DOWNLINK_UPLINK') return '下联/上联 / DOWNLINK/UPLINK'
  if (purpose === 'BLANK') return '空白'
  return '业务接口 / DOWNLINK'
}

function paletteFromSwitchSlots(slots: SwitchSlotAttr[]): PanelPaletteItem[] {
  const palette: PanelPaletteItem[] = []
  for (const s of slots) {
    if (s.card_type === 'blank' || s.purpose === 'BLANK') {
      palette.push({
        id: `slot-card-${s.index}`,
        kind: 'line_card',
        label: `Slot${s.index}:空白`,
        side: 'front',
        slot_index: s.index,
        port_count: 0,
        port_start: 0,
        blank: true,
      })
      continue
    }
    const pc = effectivePortCount(s)
    const pt = portTypeForSlot(s)
    const short = CARD_TYPE_SHORT[s.card_type] || s.card_type
    const start = Math.max(0, Number(s.port_start) || 0)
    const end = start + Math.max(0, pc) - 1
    const range = pc > 0 ? `${start}-${end}` : '—'
    const purposeTag = switchSlotPurposeLabel(s.purpose)
    palette.push({
      id: `slot-card-${s.index}`,
      kind: s.purpose === 'UPLINK' ? 'port_uplink' : 'line_card',
      label: `Slot${s.index}:${purposeTag}${short}×${pc}(${range})`,
      side: 'front',
      slot_index: s.index,
      port_count: pc,
      port_type: pt,
      port_start: start,
      blank: false,
    })
  }
  return palette
}

/** 默认自定义面板网格：列×行 */
export const DEFAULT_PANEL_COLS = 38
export const DEFAULT_PANEL_ROWS = 16
export const MIN_PANEL_COLS = 4
export const MAX_PANEL_COLS = 64
export const MIN_PANEL_ROWS = 2
export const MAX_PANEL_ROWS = 48

export function slotShortLabel(slot: DesignSlotAttr): string {
  const t = SLOT_LABEL[String(slot.type)] || 'Slot'
  return `S${slot.index}:${t}`
}

function asCount(v: unknown, max: number): number {
  const n = Number(v)
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(max, Math.trunc(n)))
}

export function clampPanelCols(n: unknown): number {
  const v = Math.trunc(Number(n))
  if (!Number.isFinite(v)) return DEFAULT_PANEL_COLS
  return Math.max(MIN_PANEL_COLS, Math.min(MAX_PANEL_COLS, v))
}

export function clampPanelRows(n: unknown): number {
  const v = Math.trunc(Number(n))
  if (!Number.isFinite(v)) return DEFAULT_PANEL_ROWS
  return Math.max(MIN_PANEL_ROWS, Math.min(MAX_PANEL_ROWS, v))
}

function pushFanAndPsu(palette: PanelPaletteItem[], attrs: Record<string, unknown>, side: PanelSide = 'rear') {
  // 未配置时默认 2，避免后面板「设备配置及组件」空白
  const fans =
    attrs.fan_count == null || attrs.fan_count === ''
      ? 2
      : asCount(attrs.fan_count, 16)
  for (let i = 1; i <= fans; i++) {
    palette.push({
      id: `fan-${i}`,
      kind: 'fan',
      label: fans > 1 ? `风扇${i}` : '风扇',
      side,
    })
  }
  const psuCount =
    attrs.psu_count == null || attrs.psu_count === ''
      ? 2
      : asCount(attrs.psu_count, 8)
  for (let i = 1; i <= psuCount; i++) {
    palette.push({ id: `psu-${i}`, kind: 'psu', label: `电源${i}`, side })
  }
}

/** 交换机网格组件（与服务器同一套前后面板） */
export function buildSwitchPanelPalette(attrs: Record<string, unknown>): PanelPaletteItem[] {
  const palette: PanelPaletteItem[] = []
  const role = String(attrs.switch_role || 'gigabit')

  // 优先按 switch_slots 展开，保证万兆下联口与 Slot 配置连续编号一致
  if (Array.isArray(attrs.switch_slots) && attrs.switch_slots.length) {
    palette.push(...paletteFromSwitchSlots(readSwitchSlots(attrs)))
    pushFanAndPsu(palette, attrs, 'rear')
    return palette
  }

  if (role === 'core') {
    const raw = Array.isArray(attrs.line_cards) ? attrs.line_cards : []
    const cards = raw.filter((x): x is Record<string, unknown> => !!x && typeof x === 'object')
    const list = cards.length ? cards : [{ id: 'card1', card_type: 'ten_gigabit', port_count: 48 }]
    list.forEach((card, i) => {
      const ct = String(card.card_type || 'ten_gigabit')
      const short = CARD_TYPE_SHORT[ct] || ct
      const isBlank = ct === 'blank'
      const pc = isBlank ? 0 : asCount(card.port_count, 128) || 48
      const portType =
        ct === 'gigabit' ? '1g' : ct === '100g' ? '40_100g' : '10g'
      const label = isBlank ? `板卡${i + 1}:空白` : `板卡${i + 1}:${short}×${pc}`
      palette.push({
        id: `card-${String(card.id || i + 1)}`,
        kind: 'line_card',
        label,
        side: 'front',
        slot_index: i + 1,
        port_count: pc,
        port_type: portType,
        port_start: 0,
        blank: isBlank,
      })
    })
  } else if (role === 'gigabit' || role === 'ten_gigabit' || role === 'aggregation') {
    const cards = Math.max(1, Math.min(16, asCount(attrs.optical_card_count, 16) || 1))
    let ppc = asCount(attrs.optical_ports_per_card, 128)
    if (ppc <= 0) {
      const total = Math.max(1, asCount(attrs.downlink_count, 256) || 48)
      ppc = Math.max(1, Math.min(128, Math.floor(total / cards)))
    }
    const portType = role === 'gigabit' ? '1g' : '10g'
    const speedLabel = portType === '1g' ? '1G' : '10G'
    // 无 switch_slots 时的回退：万兆下联按板卡连续编号
    let downlinkCursor = 0
    for (let i = 1; i <= cards; i++) {
      const start = role === 'ten_gigabit' ? downlinkCursor : 0
      const end = start + ppc - 1
      const range = role === 'ten_gigabit' ? `(${start}-${end})` : ''
      palette.push({
        id: `card-optic-${i}`,
        kind: 'line_card',
        label: `板卡${i}:${speedLabel}×${ppc}${range}`,
        side: 'front',
        slot_index: i,
        port_count: ppc,
        port_type: portType,
        port_start: start,
        blank: false,
      })
      if (role === 'ten_gigabit') downlinkCursor += ppc
    }
    const up = asCount(attrs.uplink_count, 64)
    if (up > 0) {
      const upType = role === 'gigabit' ? '10g' : '40_100g'
      const upLabel = upType === '10g' ? '10G' : '40/100G'
      // 交换机所有业务接口均在前面板
      palette.push({
        id: 'port-uplink',
        kind: 'port_uplink',
        label: `上联${upLabel}×${up}`,
        side: 'front',
        port_count: up,
        port_type: upType,
        port_start: 0,
      })
    }
  }

  // 后面板仅风扇/电源（非业务接口）
  pushFanAndPsu(palette, attrs, 'rear')
  return palette
}

export function buildPanelPalette(attrs: Record<string, unknown>, slots: DesignSlotAttr[]): PanelPaletteItem[] {
  // 服务器：优先按 server_slots 展开千兆/万兆/IPMI/HDMI/USB
  if (Array.isArray(attrs.server_slots) || Array.isArray(attrs.slots) || attrs.form_factor_u != null) {
    const hasServerShape =
      Array.isArray(attrs.server_slots) ||
      (Array.isArray(attrs.slots) && attrs.cpu_sockets != null) ||
      (attrs.form_factor_u != null && attrs.switch_role == null && attrs.data_port_count == null)
    if (hasServerShape && attrs.switch_role == null) {
      return buildServerPanelPalette(attrs)
    }
  }

  const rawRole = String(attrs.switch_role || '').trim()
  const looksLikeSwitch =
    rawRole === 'gigabit' ||
    rawRole === 'ten_gigabit' ||
    rawRole === 'aggregation' ||
    rawRole === 'core' ||
    attrs.downlink_count != null ||
    attrs.optical_card_count != null ||
    attrs.optical_ports_per_card != null ||
    attrs.uplink_count != null ||
    Array.isArray(attrs.line_cards) ||
    Array.isArray(attrs.switch_slots)

  if (looksLikeSwitch) {
    const role = resolveDesignSwitchRole(attrs)
    const normalized: Record<string, unknown> = { ...attrs, switch_role: role }
    // 千兆/万兆：补齐板卡字段，避免组件栏空白
    if (role === 'gigabit' || role === 'ten_gigabit' || role === 'aggregation') {
      const cards = Math.max(1, Math.min(16, asCount(normalized.optical_card_count, 16) || 1))
      let ppc = asCount(normalized.optical_ports_per_card, 128)
      if (ppc <= 0) {
        const total = Math.max(1, asCount(normalized.downlink_count, 256) || 48)
        ppc = Math.max(1, Math.min(128, Math.floor(total / cards)))
      }
      normalized.optical_card_count = cards
      normalized.optical_ports_per_card = ppc
      normalized.downlink_count = Math.max(1, Math.min(256, cards * ppc))
      if (normalized.uplink_count == null) normalized.uplink_count = 4
    }
    if (normalized.fan_count == null) normalized.fan_count = 2
    if (normalized.psu_count == null) normalized.psu_count = 2
    return buildSwitchPanelPalette(normalized)
  }

  // 安全设备：按 security_slots 展开
  if (Array.isArray(attrs.security_slots)) {
    return buildSecurityPanelPalette(attrs)
  }

  // 安全/路由等：按规格口数生成可放置块
  const dataCount = asCount(attrs.data_port_count, 128)
  const wanCount = asCount(attrs.wan_count, 64)
  const lanCount = asCount(attrs.lan_count, 64)
  const serviceCount = asCount(attrs.service_port_count, 64)
  if (dataCount > 0 || wanCount > 0 || lanCount > 0 || serviceCount > 0) {
    const palette: PanelPaletteItem[] = []
    if (dataCount > 0) {
      palette.push({
        id: 'port-data',
        kind: 'port_main',
        label: `业务口×${dataCount}`,
        side: 'front',
        port_count: dataCount,
        port_type: String(attrs.data_port_type || '10g'),
      })
    }
    if (wanCount > 0) {
      palette.push({
        id: 'port-wan',
        kind: 'port_uplink',
        label: `WAN×${wanCount}`,
        side: 'front',
        port_count: wanCount,
        port_type: String(attrs.wan_type || '10g'),
      })
    }
    if (lanCount > 0) {
      palette.push({
        id: 'port-lan',
        kind: 'port_main',
        label: `LAN×${lanCount}`,
        side: 'front',
        port_count: lanCount,
        port_type: String(attrs.lan_type || '1g'),
      })
    }
    if (serviceCount > 0) {
      palette.push({
        id: 'port-svc',
        kind: 'port_main',
        label: `业务口×${serviceCount}`,
        side: 'front',
        port_count: serviceCount,
        port_type: String(attrs.service_port_type || '10g'),
      })
    }
    pushFanAndPsu(palette, attrs, 'rear')
    return palette
  }

  // 兼容旧服务器：仅有 design slots
  return buildServerPanelPaletteFromDesignSlots(attrs, slots)
}

/** 服务器：按 server_slots 生成千兆/万兆/IPMI/HDMI/USB 组件 */
function buildServerPanelPalette(attrs: Record<string, unknown>): PanelPaletteItem[] {
  const palette: PanelPaletteItem[] = []
  const frontDisks = asCount(attrs.disk_front_count, 48)
  for (let i = 1; i <= frontDisks; i++) {
    palette.push({
      id: `disk-f-${i}`,
      kind: 'disk_front',
      label: `前盘${i}`,
      side: 'front',
    })
  }

  const ifaceSlots = readServerIfaceSlots(attrs).filter((slot) => slot.kind === 'onboard' || slot.index === 1)
  for (const s of ifaceSlots) {
    const n10 = Math.max(0, Number(s.ports_10g) || 0)
    const n1 = Math.max(0, Number(s.ports_1g) || 0)
    const onboard = s.kind === 'onboard' || s.index === 1
    const prefix = onboard ? '板载' : `Slot${s.index}`

    if (onboard) {
      // 板载：10G / 1G 可并存，分组件；管理口仅板载
      if (n10 > 0) {
        palette.push({
          id: `slot-${s.index}-10g`,
          kind: 'slot',
          label: `${prefix}:10G×${n10}`,
          side: 'rear',
          slot_index: s.index,
          port_count: n10,
          port_type: '10g',
        })
      }
      if (n1 > 0) {
        palette.push({
          id: `slot-${s.index}-1g`,
          kind: 'slot',
          label: `${prefix}:1G×${n1}`,
          side: 'rear',
          slot_index: s.index,
          port_count: n1,
          port_type: '1g',
        })
      }
      for (let i = 1; i <= s.ipmi_count; i++) {
        palette.push({
          id: `slot-${s.index}-ipmi-${i}`,
          kind: 'bmc',
          label: s.ipmi_count > 1 ? `${prefix}:IPMI-${i}` : `${prefix}:IPMI`,
          side: 'rear',
          slot_index: s.index,
        })
      }
      for (let i = 1; i <= s.hdmi_count; i++) {
        palette.push({
          id: `slot-${s.index}-vga-${i}`,
          kind: 'hdmi',
          label: s.hdmi_count > 1 ? `${prefix}:VGA-${i}` : `${prefix}:VGA`,
          side: 'rear',
          slot_index: s.index,
        })
      }
      for (let i = 1; i <= s.usb_count; i++) {
        palette.push({
          id: `slot-${s.index}-usb-${i}`,
          kind: 'usb',
          label: s.usb_count > 1 ? `${prefix}:USB-${i}` : `${prefix}:USB`,
          side: 'rear',
          slot_index: s.index,
        })
      }
      if (n10 <= 0 && n1 <= 0 && s.ipmi_count <= 0 && s.hdmi_count <= 0 && s.usb_count <= 0) {
        palette.push({
          id: `slot-${s.index}-blank`,
          kind: 'slot',
          label: `${prefix}:空白`,
          side: 'rear',
          slot_index: s.index,
          blank: true,
        })
      }
      continue
    }

    // 扩展槽：仅单一类型网口
    const dataPorts = n10 > 0 ? n10 : n1
    const portType = n10 > 0 ? '10g' : n1 > 0 ? '1g' : undefined
    if (dataPorts > 0 && portType) {
      palette.push({
        id: `slot-${s.index}-nic`,
        kind: 'slot',
        label: serverSlotNicPaletteLabel(s),
        side: 'rear',
        slot_index: s.index,
        port_count: dataPorts,
        port_type: portType,
      })
    } else {
      palette.push({
        id: `slot-${s.index}-blank`,
        kind: 'slot',
        label: `${prefix}:空白`,
        side: 'rear',
        slot_index: s.index,
        blank: true,
      })
    }
  }

  for (const card of readPcieSlots(attrs)) {
    const isNic = card.card_type === 'nic_copper' || card.card_type === 'nic_optical'
    const speed = card.speed.replace('ge', 'GE')
    palette.push({
      id: `pcie-card-${card.index}`,
      kind: 'slot',
      label: card.card_type === 'raid'
        ? `PCIe${card.index}:RAID ${(card.raid_level || 'raid1').toUpperCase()}`
        : isNic
          ? `PCIe${card.index}:${speed}${card.card_type === 'nic_copper' ? '电口' : '光口'}×${card.port_count}`
          : `PCIe${card.index}:空挡板`,
      side: 'rear',
      slot_index: card.index + 1,
      port_count: isNic ? card.port_count : 0,
      port_type: isNic ? (card.speed === '1ge' ? '1g' : card.speed === '10ge' ? '10g' : card.speed === '25ge' ? '25g' : '40_100g') : undefined,
      blank: card.card_type === 'blank',
    })
  }
  pushFanAndPsu(palette, attrs, 'rear')
  const rearDisks = asCount(attrs.disk_rear_count, 6)
  for (let i = 1; i <= rearDisks; i++) {
    palette.push({
      id: `disk-r-${i}`,
      kind: 'disk_rear',
      label: `后盘${i}`,
      side: 'rear',
    })
  }
  return palette
}

function buildSecurityPanelPalette(attrs: Record<string, unknown>): PanelPaletteItem[] {
  const palette: PanelPaletteItem[] = []
  const slots = readSecurityIfaceSlots(attrs)
  for (const s of slots) {
    if (s.ports_10g > 0) {
      palette.push({
        id: `sec-${s.index}-10g`,
        kind: 'port_main',
        label: `S${s.index}:10G×${s.ports_10g}`,
        side: 'front',
        slot_index: s.index,
        port_count: s.ports_10g,
        port_type: '10g',
      })
    }
    if (s.ports_1g > 0) {
      palette.push({
        id: `sec-${s.index}-1g`,
        kind: 'port_main',
        label: `S${s.index}:1G×${s.ports_1g}`,
        side: 'front',
        slot_index: s.index,
        port_count: s.ports_1g,
        port_type: '1g',
      })
    }
    if (s.control_count > 0) {
      palette.push({
        id: `sec-${s.index}-ctl`,
        kind: 'port_uplink',
        label: `S${s.index}:Control×${s.control_count}`,
        side: 'front',
        slot_index: s.index,
        port_count: s.control_count,
        port_type: '1g',
      })
    }
    if (s.ha_count > 0) {
      palette.push({
        id: `sec-${s.index}-ha`,
        kind: 'port_uplink',
        label: `S${s.index}:HA×${s.ha_count}`,
        side: 'front',
        slot_index: s.index,
        port_count: s.ha_count,
        port_type: '10g',
      })
    }
    if (s.mgmt_count > 0) {
      palette.push({
        id: `sec-${s.index}-mgmt`,
        kind: 'bmc',
        label: `S${s.index}:MGMT×${s.mgmt_count}`,
        side: 'front',
        slot_index: s.index,
        port_count: s.mgmt_count,
      })
    }
    for (let i = 1; i <= s.usb_count; i++) {
      palette.push({
        id: `sec-${s.index}-usb-${i}`,
        kind: 'usb',
        label: s.usb_count > 1 ? `S${s.index}:USB${i}` : `S${s.index}:USB`,
        side: 'front',
        slot_index: s.index,
      })
    }
  }
  pushFanAndPsu(palette, attrs, 'rear')
  return palette
}

function buildServerPanelPaletteFromDesignSlots(
  attrs: Record<string, unknown>,
  slots: DesignSlotAttr[],
): PanelPaletteItem[] {
  const palette: PanelPaletteItem[] = []

  const frontDisks = asCount(attrs.disk_front_count, 48)
  for (let i = 1; i <= frontDisks; i++) {
    palette.push({
      id: `disk-f-${i}`,
      kind: 'disk_front',
      label: `前盘${i}`,
      side: 'front',
    })
  }
  const usb = asCount(attrs.usb_ports, 8)
  for (let i = 1; i <= usb; i++) {
    palette.push({
      id: `usb-${i}`,
      kind: 'usb',
      label: usb > 1 ? `USB${i}` : 'USB',
      side: 'front',
    })
  }

  for (const s of slots) {
    const list = Array.isArray(s.interfaces) ? s.interfaces : []
    let n10 = list.filter((x) => String(x.port_type) === '10g').length
    let n1 = list.filter((x) => String(x.port_type) === '1g').length
    if (!list.length) {
      if (s.type === 'nic_10g') n10 = Number(s.port_count) || 0
      else if (s.type === 'nic_1g') n1 = Number(s.port_count) || 0
    }
    // 同 Slot 仅一种
    if (n10 > 0) n1 = 0
    const dataPorts = n10 + n1
    const label =
      s.type === 'blank' || dataPorts <= 0
        ? `Slot${s.index}:空白`
        : serverSlotNicPaletteLabel({ index: s.index, ports_10g: n10, ports_1g: n1 })
    palette.push({
      id: `slot-${s.index}`,
      kind: 'slot',
      label,
      side: 'rear',
      slot_index: s.index,
      port_count: dataPorts,
      port_type: n10 > 0 ? '10g' : n1 > 0 ? '1g' : undefined,
      blank: s.type === 'blank' || dataPorts <= 0,
    })
  }
  pushFanAndPsu(palette, attrs, 'rear')
  const bmc = asCount(attrs.bmc_ports, 4)
  for (let i = 1; i <= bmc; i++) {
    palette.push({
      id: `bmc-${i}`,
      kind: 'bmc',
      label: bmc > 1 ? `BMC${i}` : 'BMC',
      side: 'rear',
    })
  }
  const rearDisks = asCount(attrs.disk_rear_count, 6)
  for (let i = 1; i <= rearDisks; i++) {
    palette.push({
      id: `disk-r-${i}`,
      kind: 'disk_rear',
      label: `后盘${i}`,
      side: 'rear',
    })
  }
  return palette
}

function emptySide(cols: number, rows: number): PanelSideLayout {
  return { cols, rows, items: [] }
}

function itemFits(it: PanelLayoutItem, cols: number, rows: number): boolean {
  const w = Math.max(1, it.w || 1)
  const h = Math.max(1, it.h || 1)
  return it.row >= 0 && it.col >= 0 && it.col + w <= cols && it.row + h <= rows
}

/** 归一化：前后面板强制同一 cols/rows；默认宽 38 × 高 16 */
export function normalizePanelLayoutConfig(raw: unknown): PanelLayoutConfig {
  const defaultLayout = (): PanelLayoutConfig => ({
    cols: DEFAULT_PANEL_COLS,
    rows: DEFAULT_PANEL_ROWS,
    grid_scale: PANEL_GRID_SCALE,
    front: emptySide(DEFAULT_PANEL_COLS, DEFAULT_PANEL_ROWS),
    rear: emptySide(DEFAULT_PANEL_COLS, DEFAULT_PANEL_ROWS),
  })

  /** 仅迁移未标记 grid_scale 的历史错误尺寸；已规范化的布局尊重用户设定 */
  const migrateBadSize = (cols: number, rows: number, gridScale: unknown) => {
    if (Number(gridScale) === PANEL_GRID_SCALE) return { cols, rows }
    if (
      (cols === 16 && rows === 4) ||
      (cols === MAX_PANEL_COLS && rows === MAX_PANEL_ROWS) ||
      (cols === 32 && rows === 16)
    ) {
      return { cols: DEFAULT_PANEL_COLS, rows: DEFAULT_PANEL_ROWS }
    }
    return { cols, rows }
  }

  if (raw && typeof raw === 'object') {
    const o = raw as Record<string, unknown>
    if (o.front && o.rear && typeof o.front === 'object' && typeof o.rear === 'object') {
      const front = o.front as PanelSideLayout
      const rear = o.rear as PanelSideLayout
      const frontItemsRaw = Array.isArray(front.items)
        ? front.items.map((it) => ({ ...it, side: 'front' as const }))
        : []
      const rearItemsRaw = Array.isArray(rear.items)
        ? rear.items.map((it) => ({ ...it, side: 'rear' as const }))
        : []

      // 交换机业务接口（板卡/下联/上联）统一归前面板
      const ifaceKinds = new Set(['line_card', 'port_main', 'port_uplink'])
      const frontItems: PanelLayoutItem[] = [...frontItemsRaw]
      const rearItems: PanelLayoutItem[] = []
      for (const it of rearItemsRaw) {
        if (ifaceKinds.has(it.kind)) {
          frontItems.push({ ...it, side: 'front' })
        } else {
          rearItems.push(it)
        }
      }

      let cols =
        o.cols != null
          ? Number(o.cols)
          : Math.max(Number(front.cols) || 0, Number(rear.cols) || 0, DEFAULT_PANEL_COLS)
      let rows =
        o.rows != null
          ? Number(o.rows)
          : Math.max(Number(front.rows) || 0, Number(rear.rows) || 0, DEFAULT_PANEL_ROWS)

      // 完全缺失尺寸时才回落默认；空面板也要保留用户改过的宽高
      if (!Number.isFinite(cols) || cols <= 0) cols = DEFAULT_PANEL_COLS
      if (!Number.isFinite(rows) || rows <= 0) rows = DEFAULT_PANEL_ROWS

      cols = clampPanelCols(cols)
      rows = clampPanelRows(rows)
      ;({ cols, rows } = migrateBadSize(cols, rows, o.grid_scale))

      // 无放置内容：保留尺寸，不要强行改回 38×16
      if (!frontItems.length && !rearItems.length) {
        return {
          cols,
          rows,
          grid_scale: PANEL_GRID_SCALE,
          front: emptySide(cols, rows),
          rear: emptySide(cols, rows),
        }
      }

      // 保证能包住已放置块
      const all = [...frontItems, ...rearItems]
      cols = Math.max(cols, ...all.map((i) => i.col + Math.max(1, i.w || 1)))
      rows = Math.max(rows, ...all.map((i) => i.row + Math.max(1, i.h || 1)))
      cols = clampPanelCols(cols)
      rows = clampPanelRows(rows)

      return {
        cols,
        rows,
        grid_scale: PANEL_GRID_SCALE,
        front: {
          cols,
          rows,
          items: frontItems.filter((it) => itemFits(it, cols, rows)),
        },
        rear: {
          cols,
          rows,
          items: rearItems.filter((it) => itemFits(it, cols, rows)),
        },
      }
    }
    if (Array.isArray(o.items) || o.cols != null) {
      const rearItems = Array.isArray(o.items)
        ? (o.items as PanelLayoutItem[]).map((it) => ({ ...it, side: 'rear' as const }))
        : []
      let cols = clampPanelCols(o.cols ?? DEFAULT_PANEL_COLS)
      let rows = clampPanelRows(o.rows ?? DEFAULT_PANEL_ROWS)
      ;({ cols, rows } = migrateBadSize(cols, rows, o.grid_scale))
      if (!rearItems.length) {
        return {
          cols,
          rows,
          grid_scale: PANEL_GRID_SCALE,
          front: emptySide(cols, rows),
          rear: emptySide(cols, rows),
        }
      }
      cols = Math.max(cols, ...rearItems.map((i) => i.col + Math.max(1, i.w || 1)))
      rows = Math.max(rows, ...rearItems.map((i) => i.row + Math.max(1, i.h || 1)))
      cols = clampPanelCols(cols)
      rows = clampPanelRows(rows)
      return {
        cols,
        rows,
        grid_scale: PANEL_GRID_SCALE,
        front: emptySide(cols, rows),
        rear: {
          cols,
          rows,
          items: rearItems.filter((it) => itemFits(it, cols, rows)),
        },
      }
    }
  }
  return defaultLayout()
}

/** 写入统一尺寸到前后面板 */
export function withPanelSize(
  layout: PanelLayoutConfig,
  cols: number,
  rows: number,
): PanelLayoutConfig {
  const c = clampPanelCols(cols)
  const r = clampPanelRows(rows)
  const clip = (items: PanelLayoutItem[], side: PanelSide) =>
    items
      .filter((it) => itemFits(it, c, r))
      .map((it) => ({
        ...it,
        side,
        w: Math.max(1, it.w || 1),
        h: Math.max(1, it.h || 1),
      }))
  return {
    cols: c,
    rows: r,
    grid_scale: PANEL_GRID_SCALE,
    front: { cols: c, rows: r, items: clip(layout.front.items, 'front') },
    rear: { cols: c, rows: r, items: clip(layout.rear.items, 'rear') },
  }
}

/** 属性块默认占用（列×行）；Slot 更大以便展示接口 */
export function defaultItemSpan(kind?: PanelItemKind): { w: number; h: number } {
  if (kind === 'slot') return { w: 8, h: 10 }
  if (kind === 'line_card') return { w: 34, h: 4 }
  // 1U 双排方口：主口约 24 列×2 排高度；上联约 4 列
  if (kind === 'port_main') return { w: 26, h: 4 }
  if (kind === 'port_uplink') return { w: 6, h: 4 }
  if (kind === 'psu') return { w: 4, h: 4 }
  if (kind === 'fan') return { w: 2, h: 2 }
  return { w: 2, h: 4 }
}

/** 在固定网格内按默认跨度铺排（超出则停止） */
function placeSequential(
  side: PanelSide,
  palette: PanelPaletteItem[],
  cols: number,
  rows: number,
): PanelLayoutItem[] {
  const items: PanelLayoutItem[] = []
  let col = 0
  let row = 0
  let rowH = 1
  const safeCols = Math.max(1, cols)

  for (const p of palette) {
    let { w, h } = defaultItemSpan(p.kind)
    w = Math.min(w, safeCols)
    // 上联与主口之间留空，贴近 1U 交换机分区
    if (p.kind === 'port_uplink' && col > 0) {
      col = Math.min(safeCols - w, col + 2)
    }
    if (col + w > safeCols) {
      col = 0
      row += rowH
      rowH = 1
    }
    if (row + h > rows) break
    items.push({
      id: p.id,
      kind: p.kind,
      label: p.label,
      side,
      slot_index: p.slot_index,
      row,
      col,
      w,
      h,
      port_count: p.port_count,
      port_type: p.port_type,
      port_start: p.port_start,
      blank: p.blank,
    })
    col += w
    rowH = Math.max(rowH, h)
  }
  return items
}

function syncSideItems(
  side: PanelSide,
  existing: PanelLayoutItem[],
  palette: PanelPaletteItem[],
  cols: number,
  rows: number,
): PanelLayoutItem[] {
  const sidePal = palette.filter((p) => p.side === side)
  const byId = new Map(sidePal.map((p) => [p.id, p]))
  const used = new Set<string>()
  const out: PanelLayoutItem[] = []

  for (const it of existing) {
    if (!itemFits(it, cols, rows)) continue
    let p = byId.get(it.id)
    // 旧 HDMI id → VGA
    if (!p && it.id.includes('-hdmi-')) {
      p = byId.get(it.id.replace('-hdmi-', '-vga-'))
    }
    // 兼容旧 id（card-optic-N / port-uplink / card-* / slot-N-10g|1g|nic）
    if (!p && it.slot_index != null) {
      if (it.kind === 'slot') {
        p = sidePal.find(
          (x) =>
            x.kind === 'slot' &&
            x.slot_index === it.slot_index &&
            !used.has(x.id) &&
            (!it.port_type || !x.port_type || x.port_type === it.port_type),
        )
      }
      if (!p) {
        p = sidePal.find(
          (x) =>
            x.slot_index === it.slot_index &&
            !used.has(x.id) &&
            x.kind === it.kind,
        )
      }
      if (!p) {
        p = sidePal.find((x) => x.slot_index === it.slot_index && !used.has(x.id))
      }
    }
    if (!p && it.id === 'port-uplink') {
      p = sidePal.find((x) => x.kind === 'port_uplink' && !used.has(x.id))
    }
    if (!p || used.has(p.id)) {
      if (!p && it.kind === 'line_card' && !it.blank) {
        out.push({ ...it, side })
      }
      continue
    }
    used.add(p.id)
    out.push({
      ...it,
      id: p.id,
      label: p.label,
      kind: p.kind,
      slot_index: p.slot_index,
      side,
      w: Math.max(1, it.w || 1),
      h: Math.max(1, it.h || 1),
      port_count: p.port_count ?? it.port_count,
      port_type: p.port_type ?? it.port_type,
      port_start: p.port_start ?? it.port_start,
      blank: p.blank ?? it.blank,
    })
  }
  return out
}

/**
 * 同步接口属性到面板布局。
 * 尺寸由用户自定义，前后一致；不因属性数量自动改网格。
 * forceRelayout=true 时在当前尺寸内自动铺排。
 */
export function ensurePanelLayout(
  attrs: Record<string, unknown>,
  slots: DesignSlotAttr[],
  forceRelayout = false,
): PanelLayoutConfig {
  const palette = buildPanelPalette(attrs, slots)
  const frontPal = palette.filter((p) => p.side === 'front')
  const rearPal = palette.filter((p) => p.side === 'rear')
  const prev = normalizePanelLayoutConfig(attrs.panel_layout)
  const cols = prev.cols
  const rows = prev.rows

  const frontItems = forceRelayout
    ? placeSequential('front', frontPal, cols, rows)
    : syncSideItems('front', prev.front.items, palette, cols, rows)
  const rearItems = forceRelayout
    ? placeSequential('rear', rearPal, cols, rows)
    : syncSideItems('rear', prev.rear.items, palette, cols, rows)

  const layout: PanelLayoutConfig = {
    cols,
    rows,
    grid_scale: PANEL_GRID_SCALE,
    front: { cols, rows, items: frontItems },
    rear: { cols, rows, items: rearItems },
  }
  attrs.panel_layout = layout
  return layout
}

export type CustomAttr = { name: string; value: string }

export function getCustomAttributes(attrs: Record<string, unknown> | null | undefined): CustomAttr[] {
  const raw = attrs?.custom_attributes
  if (!Array.isArray(raw)) return []
  return raw
    .filter((x): x is Record<string, unknown> => !!x && typeof x === 'object')
    .map((x) => ({ name: String(x.name ?? ''), value: String(x.value ?? '') }))
}
