/**
 * 网络设备（交换机）模型属性 — 对齐 docs/设备属性参数定义.xmind
 * 面板样式仍走现有 layout 引擎，本文件只定义属性与默认 Slot。
 */

import type { CoreCardType, CoreLineCard, PortType, SwitchSubtype, UplinkPosition } from '@/api/network'
import { newCoreLineCard } from '@/api/network'

/** Slot 用途 */
export type SwitchSlotPurpose = 'DOWNLINK' | 'UPLINK' | 'DOWNLINK_UPLINK' | 'BLANK'

/** 板卡类型（核心/汇聚接口板 + 接入类 Slot） */
export type SwitchSlotCardType =
  | 'gigabit'
  | 'ten_gigabit'
  | '25g'
  | '40g'
  | '100g'
  | '400g'
  | 'blank'

/** 核心/汇聚业务接口板 */
export type SwitchIfaceBoardKind = '10ge' | '25ge' | '40ge' | '100ge' | '400ge'

export const SWITCH_IFACE_BOARD_OPTIONS: { value: SwitchIfaceBoardKind; label: string }[] = [
  { value: '10ge', label: '万兆以太网光接口板' },
  { value: '25ge', label: '25GE 以太网光接口板' },
  { value: '40ge', label: '40GE 光接口板' },
  { value: '100ge', label: '100GE 光接口板' },
  { value: '400ge', label: '400GE 光接口板' },
]

export const SWITCH_IFACE_BOARD_PORT_PRESETS = [18, 24, 36, 48] as const

export const ACCESS_DOWNLINK_COUNT_PRESETS = [48] as const
export const ACCESS_TENGIG_UPLINK_COUNT_PRESETS = [6, 8] as const

export type GigabitDownlinkMedia = 'optical' | 'copper'
export type TenGigUplinkKind = '40ge' | '100ge'

export const GIGABIT_DOWNLINK_MEDIA_OPTIONS: { value: GigabitDownlinkMedia; label: string }[] = [
  { value: 'optical', label: '千兆以太网光接口' },
  { value: 'copper', label: '千兆以太网电口' },
]

export const TENGIG_UPLINK_KIND_OPTIONS: { value: TenGigUplinkKind; label: string }[] = [
  { value: '40ge', label: '40G 光接口' },
  { value: '100ge', label: '100G 光接口' },
]

export const AIRFLOW_OPTIONS = [
  { value: 'front_to_rear', label: '标准前后风道' },
  { value: 'custom', label: '自定义' },
] as const

/** 面板演示：高度只由整机 U 决定；每 U 一行槽位，槽位/接口板高度固定 */
export const CHASSIS_DEMO = {
  slotH: 24,
  slotGap: 2,
  bayH: 14,
  topMin: 12,
  framePad: 5,
  maxW: 420,
  psuW: 18,
  psuH: 26,
}

/** 千兆/万兆 1U 面板演示：正面与背面同宽同高 */
export const ACCESS_DEMO = {
  height: 86,
  maxW: 640,
}

export function chassisDemoHeight(heightU: number, _expansionSlots?: number): number {
  const u = Math.max(1, Math.min(48, Math.trunc(heightU) || 1))
  const rowsH = u * CHASSIS_DEMO.slotH + Math.max(0, u - 1) * CHASSIS_DEMO.slotGap
  return CHASSIS_DEMO.framePad * 2 + CHASSIS_DEMO.topMin + rowsH + CHASSIS_DEMO.bayH + 8
}

/** 模块化扩展插槽上限 = 整机高度 U */
export function coreExpansionCap(attrs: Record<string, unknown> | number | null | undefined): number {
  const u = typeof attrs === 'number' ? attrs : Number(attrs?.chassis_height_u) || 10
  return clamp(Math.trunc(u) || 10, 1, 48)
}

export function clampCoreExpansionSlots(attrs: Record<string, unknown>): number {
  const cap = coreExpansionCap(attrs)
  const n = clamp(Number(attrs.modular_expansion_slots) || 6, 1, cap)
  attrs.modular_expansion_slots = n
  return n
}

export function defaultBlankPanelRows(heightU: number, expansionSlots: number): number[] {
  const u = clamp(heightU, 1, 48)
  const n = clamp(expansionSlots, 1, u)
  const want = u - n
  const rows: number[] = []
  for (let i = 0; i < want; i++) rows.push(u - want + 1 + i)
  return rows
}

export function computeBlankPanelRows(attrs: Record<string, unknown>): number[] {
  const u = coreExpansionCap(attrs)
  const n = clamp(Number(attrs.modular_expansion_slots) || 6, 1, u)
  const want = Math.max(0, u - n)
  const raw = Array.isArray(attrs.blank_panel_rows) ? attrs.blank_panel_rows : []
  const used = new Set<number>()
  const kept: number[] = []
  for (const v of raw) {
    const r = Math.trunc(Number(v) || 0)
    if (r < 1 || r > u || used.has(r)) continue
    used.add(r)
    kept.push(r)
  }
  kept.sort((a, b) => a - b)
  while (kept.length > want) kept.pop()
  for (let r = u; r >= 1 && kept.length < want; r--) {
    if (!used.has(r)) {
      used.add(r)
      kept.push(r)
    }
  }
  kept.sort((a, b) => a - b)
  return kept
}

export function normalizeBlankPanelRows(attrs: Record<string, unknown>): number[] {
  const kept = computeBlankPanelRows(attrs)
  attrs.blank_panel_rows = kept
  return kept
}

/** 空白面板与扩展槽对调：可从空白拖到槽位，或从槽位拖到空白 */
export function moveBlankPanelRow(
  attrs: Record<string, unknown>,
  fromRow: number,
  toRow: number,
): number[] {
  const u = coreExpansionCap(attrs)
  const blanks = new Set(normalizeBlankPanelRows(attrs))
  const from = clamp(Math.trunc(fromRow) || 0, 1, u)
  const to = clamp(Math.trunc(toRow) || 0, 1, u)
  const fromBlank = blanks.has(from)
  const toBlank = blanks.has(to)
  if (from === to || fromBlank === toBlank) {
    const next = [...blanks].sort((a, b) => a - b)
    attrs.blank_panel_rows = next
    return next
  }
  if (fromBlank) {
    blanks.delete(from)
    blanks.add(to)
  } else {
    blanks.delete(to)
    blanks.add(from)
  }
  const next = [...blanks].sort((a, b) => a - b)
  attrs.blank_panel_rows = next
  return next
}

/** 空白面板上/下移：跳过相邻空白，与最近的扩展槽对调 */
export function nudgeBlankPanelRow(
  attrs: Record<string, unknown>,
  fromRow: number,
  dir: -1 | 1,
): number[] {
  const u = coreExpansionCap(attrs)
  const blanks = new Set(normalizeBlankPanelRows(attrs))
  const from = clamp(Math.trunc(fromRow) || 0, 1, u)
  if (!blanks.has(from)) return [...blanks].sort((a, b) => a - b)
  let to = from + dir
  while (to >= 1 && to <= u && blanks.has(to)) to += dir
  if (to < 1 || to > u) return [...blanks].sort((a, b) => a - b)
  return moveBlankPanelRow(attrs, from, to)
}

export type ChassisDisplayRow = {
  row: number
  filler: boolean
  slot: SwitchSlotAttr | null
  slotNo: number | null
}

export function buildChassisDisplayRows(
  heightU: number,
  slots: SwitchSlotAttr[],
  blankRows: number[],
): ChassisDisplayRow[] {
  const u = clamp(heightU, 1, 48)
  const blanks = new Set(
    (Array.isArray(blankRows) ? blankRows : []).filter((r) => r >= 1 && r <= u),
  )
  const list = Array.isArray(slots) ? slots : []
  let si = 0
  const rows: ChassisDisplayRow[] = []
  for (let r = 1; r <= u; r++) {
    if (blanks.has(r)) {
      rows.push({ row: r, filler: true, slot: null, slotNo: null })
    } else {
      const slot = list[si] || null
      si += 1
      rows.push({
        row: r,
        filler: false,
        slot,
        slotNo: slot?.index ?? si,
      })
    }
  }
  return rows
}

export function isCoreOrAggRole(role: string | null | undefined): boolean {
  return role === 'core' || role === 'aggregation'
}

export function ifaceBoardToSlotCard(kind: SwitchIfaceBoardKind): SwitchSlotCardType {
  if (kind === '25ge') return '25g'
  if (kind === '40ge') return '40g'
  if (kind === '100ge') return '100g'
  if (kind === '400ge') return '400g'
  return 'ten_gigabit'
}

export function slotCardToIfaceBoard(card: SwitchSlotCardType): SwitchIfaceBoardKind {
  if (card === '25g') return '25ge'
  if (card === '40g') return '40ge'
  if (card === '100g') return '100ge'
  if (card === '400g') return '400ge'
  return '10ge'
}

export interface SwitchSlotAttr {
  index: number
  purpose: SwitchSlotPurpose
  card_type: SwitchSlotCardType
  /** 1G/10G 口数；100G 时用 mpo/lc */
  port_count: number
  mpo_count?: number
  lc_count?: number
  /** 自动编号起始口号（全局连续） */
  port_start: number
  /** 单口覆盖（未写的口用板卡默认规格） */
  ports?: SwitchBoardPortAttr[]
}

export const NETWORK_DEVICE_TYPE_OPTIONS = [
  { value: 'network', label: '网络设备' },
  { value: 'server', label: '服务器设备' },
  { value: 'security', label: '安全设备' },
] as const

/** 交换机样式（接口属性三类：核心/汇聚、万兆、千兆） */
export const SWITCH_STYLE_OPTIONS: { value: SwitchSubtype; label: string }[] = [
  { value: 'core', label: '核心/汇聚交换机' },
  { value: 'ten_gigabit', label: '万兆交换机' },
  { value: 'gigabit', label: '千兆交换机' },
]

export const SWITCH_SLOT_CARD_OPTIONS: { value: SwitchSlotCardType; label: string }[] = [
  { value: 'gigabit', label: '千兆板卡（1G 电口）' },
  { value: 'ten_gigabit', label: '万兆板卡（10G 光口）' },
  { value: '100g', label: '40/100G 板卡' },
  { value: 'blank', label: '空白板卡' },
]

export const SWITCH_SLOT_PURPOSE_OPTIONS: { value: SwitchSlotPurpose; label: string }[] = [
  { value: 'DOWNLINK', label: 'DOWNLINK' },
  { value: 'UPLINK', label: 'UPLINK' },
  { value: 'DOWNLINK_UPLINK', label: 'DOWNLINK/UPLINK' },
  { value: 'BLANK', label: '空白' },
]

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n))
}

export function defaultCardSlotCount(role: SwitchSubtype): number {
  if (role === 'gigabit' || role === 'ten_gigabit') return 2
  return 6
}

/** 40/100G 板卡默认口数：千兆=0，万兆=6，核心/汇聚=36 */
export function default100gPortCount(role: SwitchSubtype): number {
  if (role === 'gigabit') return 0
  if (role === 'ten_gigabit') return 6
  return 36 // core / aggregation
}

/** 统一 40/100G 口数到 port_count，并同步 mpo（默认全走 MPO，lc 保留用户值） */
export function sync100gPortFields(slot: SwitchSlotAttr, total?: number): SwitchSlotAttr {
  const next = { ...slot }
  let count =
    total != null
      ? Number(total)
      : Number(next.port_count) ||
        clamp(Number(next.mpo_count) || 0, 0, 36) + clamp(Number(next.lc_count) || 0, 0, 36)
  count = clamp(Number.isFinite(count) ? count : 0, 0, 36)
  next.port_count = count
  const lc = clamp(Number(next.lc_count) || 0, 0, count)
  next.lc_count = lc
  next.mpo_count = clamp(count - lc, 0, 36)
  return next
}

/** 按角色生成默认 Slot 列表（含自动编号起点；所有交换机每槽从 0 起编） */
export function defaultSwitchSlots(role: SwitchSubtype, slotCount?: number): SwitchSlotAttr[] {
  const n = clamp(slotCount ?? defaultCardSlotCount(role), 1, 16)
  if (role === 'gigabit' || role === 'ten_gigabit') {
    const downCount = 48
    const upCount = role === 'gigabit' ? 8 : 6
    const slots: SwitchSlotAttr[] = [
      {
        index: 1,
        purpose: 'DOWNLINK',
        card_type: role === 'gigabit' ? 'gigabit' : 'ten_gigabit',
        port_count: downCount,
        port_start: 0,
      },
      {
        index: 2,
        purpose: 'UPLINK',
        card_type: role === 'gigabit' ? 'ten_gigabit' : '40g',
        port_count: upCount,
        port_start: 0,
        mpo_count: role === 'ten_gigabit' ? upCount : 0,
        lc_count: 0,
      },
    ]
    for (let i = slots.length; i < n; i++) {
      slots.push({
        index: i + 1,
        purpose: 'BLANK',
        card_type: 'blank',
        port_count: 0,
        port_start: 0,
      })
    }
    return renumberPortStarts(slots.slice(0, Math.max(2, n)), role)
  }

  // core / aggregation：模块化扩展插槽，前 N 槽为业务接口板
  const slots: SwitchSlotAttr[] = []
  for (let i = 0; i < n; i++) {
    slots.push({
      index: i + 1,
      purpose: 'DOWNLINK',
      card_type: 'ten_gigabit',
      port_count: 48,
      port_start: 0,
    })
  }
  return renumberPortStarts(slots, role)
}

/**
 * 按口数重算自动编号起点。
 * - 万兆：DOWNLINK（含 DOWNLINK_UPLINK）槽位全局连续编号（从 0 起）；其余槽各自从 0 起
 * - 千兆 / 核心 / 汇聚：每个 slot 内各自从 0 起编
 */
export function renumberPortStarts(
  slots: SwitchSlotAttr[],
  role?: SwitchSubtype,
): SwitchSlotAttr[] {
  if (role === 'ten_gigabit') {
    let downlinkCursor = 0
    return slots.map((s, i) => {
      let next = { ...s, index: i + 1 }
      if (next.card_type === 'blank' || next.purpose === 'BLANK') {
        next.port_count = 0
        next.mpo_count = 0
        next.lc_count = 0
        next.port_start = 0
        return next
      }
      if (next.card_type === '100g') {
        next = sync100gPortFields(next)
      } else {
        next.port_count = clamp(Number(next.port_count) || 0, 0, 128)
      }
      const count = Math.max(0, Number(next.port_count) || 0)
      if (next.purpose === 'DOWNLINK' || next.purpose === 'DOWNLINK_UPLINK') {
        next.port_start = downlinkCursor
        downlinkCursor += count
      } else {
        next.port_start = 0
      }
      return next
    })
  }

  return slots.map((s, i) => {
    let next = { ...s, index: i + 1 }
    if (next.card_type === 'blank' || next.purpose === 'BLANK') {
      next.port_count = 0
      next.mpo_count = 0
      next.lc_count = 0
      next.port_start = 0
      return next
    }
    if (next.card_type === '100g' && !isCoreOrAggRole(role)) {
      next = sync100gPortFields(next)
    } else {
      next.port_count = clamp(Number(next.port_count) || 0, 0, 128)
    }
    next.port_start = 0
    return next
  })
}

export interface SwitchIfaceBoardPlacement {
  slot_index: number
  kind: SwitchIfaceBoardKind
  port_count: number
  port_custom?: boolean
  ports?: SwitchBoardPortAttr[]
}

export type SwitchPortIfaceType = 'optical' | 'copper'
export type SwitchPortFiberMode = 'sm' | 'mm' | 'na'

export interface SwitchBoardPortAttr {
  index: number
  /** 设备内稳定唯一 ID，供布线引用 */
  id: string
  /** 人读编号，全机唯一 */
  code: string
  iface_type: SwitchPortIfaceType
  speed: string
  module: string
  connector: string
  fiber_mode: SwitchPortFiberMode
}

export type SwitchSystemPortKind = 'eth_mgmt' | 'console' | 'usb' | 'stack'

export interface SwitchSystemPortAttr extends SwitchBoardPortAttr {
  kind: SwitchSystemPortKind
}

export const SWITCH_SYSTEM_PORT_KIND_OPTIONS: { value: SwitchSystemPortKind; label: string }[] = [
  { value: 'eth_mgmt', label: 'ETH管理口' },
  { value: 'console', label: 'Console口' },
  { value: 'usb', label: 'USB接口' },
  { value: 'stack', label: '堆叠/集群接口' },
]

export function boardPortId(slotIndex: number, portIndex: number) {
  return `slot${Math.max(1, slotIndex)}-p${Math.max(0, portIndex)}`
}

export function boardPortCode(slotIndex: number, portNum: number) {
  return `S${Math.max(1, slotIndex)}-${Math.max(0, portNum)}`
}

export const SWITCH_SYSTEM_PORT_NS: Record<SwitchSystemPortKind, string> = {
  eth_mgmt: 'eth-mgmt',
  console: 'console',
  usb: 'usb',
  stack: 'stack',
}

export function systemPortId(kind: SwitchSystemPortKind, portIndex: number) {
  return `${SWITCH_SYSTEM_PORT_NS[kind]}-p${Math.max(0, portIndex)}`
}

export function systemPortCode(kind: SwitchSystemPortKind, portIndex: number) {
  const prefix =
    kind === 'eth_mgmt' ? 'MGT' : kind === 'console' ? 'CON' : kind === 'usb' ? 'USB' : 'STACK'
  return `${prefix}${portIndex + 1}`
}

export function systemPortKindLabel(kind: SwitchSystemPortKind) {
  return SWITCH_SYSTEM_PORT_KIND_OPTIONS.find((o) => o.value === kind)?.label || kind
}

export function groupSwitchSystemPorts(ports: SwitchSystemPortAttr[]) {
  const order: SwitchSystemPortKind[] = ['console', 'eth_mgmt', 'usb', 'stack']
  return order
    .map((kind) => ({
      kind,
      label: systemPortKindLabel(kind),
      ports: ports.filter((p) => p.kind === kind),
    }))
    .filter((g) => g.ports.length)
}

export const SWITCH_PORT_IFACE_TYPE_OPTIONS = [
  { value: 'optical', label: '光口' },
  { value: 'copper', label: '电口' },
] as const

export const SWITCH_PORT_SPEED_OPTIONS = [
  { value: '1GE', label: '1GE' },
  { value: '10GE', label: '10GE' },
  { value: '25GE', label: '25GE' },
  { value: '40GE', label: '40GE' },
  { value: '100GE', label: '100GE' },
  { value: '400GE', label: '400GE' },
  { value: 'USB', label: 'USB' },
] as const

export const SWITCH_PORT_MODULE_OPTIONS = [
  { value: 'SFP', label: 'SFP' },
  { value: 'SFP+', label: 'SFP+' },
  { value: 'SFP28', label: 'SFP28' },
  { value: 'QSFP+', label: 'QSFP+' },
  { value: 'QSFP28', label: 'QSFP28' },
  { value: 'QSFP-DD', label: 'QSFP-DD' },
  { value: 'RJ45', label: 'RJ45' },
  { value: 'USB', label: 'USB' },
] as const

export const SWITCH_PORT_CONNECTOR_OPTIONS = [
  { value: 'LC', label: 'LC' },
  { value: 'SC', label: 'SC' },
  { value: 'MPO', label: 'MPO' },
  { value: 'MPO12', label: 'MPO12' },
  { value: 'RJ45', label: 'RJ45' },
  { value: 'USB', label: 'USB' },
] as const

export const SWITCH_PORT_FIBER_MODE_OPTIONS = [
  { value: 'sm', label: '单模' },
  { value: 'mm', label: '多模' },
  { value: 'na', label: '不适用' },
] as const

export function defaultPortSpecForKind(
  kind: SwitchIfaceBoardKind,
): Omit<SwitchBoardPortAttr, 'index' | 'id' | 'code'> {
  if (kind === '25ge') {
    return { iface_type: 'optical', speed: '25GE', module: 'SFP28', connector: 'LC', fiber_mode: 'mm' }
  }
  if (kind === '40ge') {
    return { iface_type: 'optical', speed: '40GE', module: 'QSFP+', connector: 'MPO', fiber_mode: 'mm' }
  }
  if (kind === '100ge') {
    return { iface_type: 'optical', speed: '100GE', module: 'QSFP28', connector: 'MPO', fiber_mode: 'mm' }
  }
  if (kind === '400ge') {
    return { iface_type: 'optical', speed: '400GE', module: 'QSFP-DD', connector: 'MPO', fiber_mode: 'mm' }
  }
  return { iface_type: 'optical', speed: '10GE', module: 'SFP+', connector: 'LC', fiber_mode: 'mm' }
}

export function suggestPortSpecBySpeed(speed: string): Partial<SwitchBoardPortAttr> {
  if (speed === '1GE') {
    return { module: 'SFP', connector: 'LC', fiber_mode: 'mm', iface_type: 'optical' }
  }
  if (speed === '25GE') {
    return { module: 'SFP28', connector: 'LC', fiber_mode: 'mm', iface_type: 'optical' }
  }
  if (speed === '40GE') {
    return { module: 'QSFP+', connector: 'MPO', fiber_mode: 'mm', iface_type: 'optical' }
  }
  if (speed === '100GE') {
    return { module: 'QSFP28', connector: 'MPO', fiber_mode: 'mm', iface_type: 'optical' }
  }
  if (speed === '400GE') {
    return { module: 'QSFP-DD', connector: 'MPO', fiber_mode: 'mm', iface_type: 'optical' }
  }
  return { module: 'SFP+', connector: 'LC', fiber_mode: 'mm', iface_type: 'optical' }
}

function asPortIfaceType(v: unknown, fallback: SwitchPortIfaceType): SwitchPortIfaceType {
  return v === 'copper' || v === 'optical' ? v : fallback
}

function asPortFiberMode(v: unknown, fallback: SwitchPortFiberMode): SwitchPortFiberMode {
  return v === 'sm' || v === 'mm' || v === 'na' ? v : fallback
}

export function defaultSystemPortSpec(kind: SwitchSystemPortKind): Omit<SwitchBoardPortAttr, 'index' | 'id' | 'code'> {
  if (kind === 'stack') {
    return { iface_type: 'optical', speed: '10GE', module: 'SFP+', connector: 'LC', fiber_mode: 'mm' }
  }
  if (kind === 'usb') {
    return { iface_type: 'copper', speed: 'USB', module: 'USB', connector: 'USB', fiber_mode: 'na' }
  }
  return { iface_type: 'copper', speed: '1GE', module: 'RJ45', connector: 'RJ45', fiber_mode: 'na' }
}

export function normalizeBoardPorts(
  kind: SwitchIfaceBoardKind,
  count: number,
  raw: unknown,
  slotIndex = 1,
  portStart = 0,
  fallback?: Omit<SwitchBoardPortAttr, 'index' | 'id' | 'code'>,
): SwitchBoardPortAttr[] {
  const n = clamp(count, 0, 128)
  const def = fallback || defaultPortSpecForKind(kind)
  const byIndex = new Map<number, Record<string, unknown>>()
  if (Array.isArray(raw)) {
    for (const item of raw) {
      if (!item || typeof item !== 'object') continue
      const src = item as Record<string, unknown>
      const idx = Math.trunc(Number(src.index))
      if (idx < 0 || idx >= n) continue
      byIndex.set(idx, src)
    }
  }
  const out: SwitchBoardPortAttr[] = []
  for (let i = 0; i < n; i++) {
    const src = byIndex.get(i)
    const num = portStart + i
    const id = boardPortId(slotIndex, i)
    const code = boardPortCode(slotIndex, num)
    if (!src) {
      out.push({
        index: i,
        id,
        code,
        ...def,
      })
      continue
    }
    const ifaceType = asPortIfaceType(src.iface_type, def.iface_type)
    const copper = ifaceType === 'copper'
    out.push({
      index: i,
      id,
      code,
      iface_type: ifaceType,
      speed: String(src.speed || def.speed),
      module: String(src.module || (copper ? 'RJ45' : def.module)),
      connector: String(src.connector || (copper ? 'RJ45' : def.connector)),
      fiber_mode: copper ? 'na' : asPortFiberMode(src.fiber_mode, def.fiber_mode),
    })
  }
  return out
}

export function resolveSlotPort(slot: SwitchSlotAttr, portIndex: number): SwitchBoardPortAttr {
  const kind = slotCardToIfaceBoard(slot.card_type)
  const n = effectivePortCount(slot)
  const list = normalizeBoardPorts(kind, n, slot.ports, slot.index, Math.max(0, Number(slot.port_start) || 0))
  const spec =
    list[portIndex] || {
      index: portIndex,
      id: boardPortId(slot.index, portIndex),
      code: boardPortCode(slot.index, (Number(slot.port_start) || 0) + portIndex),
      ...defaultPortSpecForKind(kind),
    }
  if (slot.purpose === 'UPLINK') {
    return { ...spec, id: spec.id || boardPortId(slot.index, portIndex), code: `U${portIndex + 1}` }
  }
  return spec
}

export function ifaceBoardKindLabel(kind: SwitchIfaceBoardKind): string {
  return SWITCH_IFACE_BOARD_OPTIONS.find((o) => o.value === kind)?.label || IFACE_BOARD_KIND_SHORT[kind]
}

export function switchPortFieldLabel(
  key: 'iface_type' | 'speed' | 'module' | 'connector' | 'fiber_mode',
  value: string,
): string {
  const tables = {
    iface_type: SWITCH_PORT_IFACE_TYPE_OPTIONS,
    speed: SWITCH_PORT_SPEED_OPTIONS,
    module: SWITCH_PORT_MODULE_OPTIONS,
    connector: SWITCH_PORT_CONNECTOR_OPTIONS,
    fiber_mode: SWITCH_PORT_FIBER_MODE_OPTIONS,
  } as const
  const hit = tables[key].find((o) => o.value === value)
  return hit?.label || value
}

export const IFACE_BOARD_KIND_SHORT: Record<SwitchIfaceBoardKind, string> = {
  '10ge': '10GE',
  '25ge': '25GE',
  '40ge': '40GE',
  '100ge': '100GE',
  '400ge': '400GE',
}

export function isIfaceBoardKind(v: string): v is SwitchIfaceBoardKind {
  return SWITCH_IFACE_BOARD_OPTIONS.some((o) => o.value === v)
}

export function ifaceKindToPortType(kind: SwitchIfaceBoardKind): string {
  if (kind === '25ge') return '25g'
  if (kind === '40ge') return '40g'
  if (kind === '100ge') return '100g'
  if (kind === '400ge') return '400g'
  return '10g'
}

export function portTypeToIfaceKind(raw: string | null | undefined): SwitchIfaceBoardKind {
  const t = String(raw || '').toLowerCase()
  if (t === '25g' || t === '25ge') return '25ge'
  if (t === '40g' || t === '40ge') return '40ge'
  if (t === '100g' || t === '40_100g' || t === '100ge') return '100ge'
  if (t === '400g' || t === '400ge') return '400ge'
  return '10ge'
}

export function normalizeIfaceBoards(raw: unknown, slotCount: number): SwitchIfaceBoardPlacement[] {
  const n = clamp(slotCount, 1, 48)
  if (!Array.isArray(raw)) return []
  const used = new Set<number>()
  const out: SwitchIfaceBoardPlacement[] = []
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const src = item as Record<string, unknown>
    const slot = Math.trunc(Number(src.slot_index) || 0)
    if (slot < 1 || slot > n || used.has(slot)) continue
    let kind = String(src.kind || '')
    if (!isIfaceBoardKind(kind)) {
      kind = slotCardToIfaceBoard(String(src.card_type || 'ten_gigabit') as SwitchSlotCardType)
    }
    if (!isIfaceBoardKind(kind)) kind = '10ge'
    used.add(slot)
    const portCount = clamp(Number(src.port_count) || 48, 1, 128)
    out.push({
      slot_index: slot,
      kind,
      port_count: portCount,
      port_custom: !!src.port_custom,
      ports: normalizeBoardPorts(kind, portCount, src.ports, slot, 0),
    })
  }
  return out.sort((a, b) => a.slot_index - b.slot_index)
}

export function slotsToIfaceBoards(slots: SwitchSlotAttr[]): SwitchIfaceBoardPlacement[] {
  return slots
    .filter((s) => s.card_type !== 'blank' && s.purpose !== 'BLANK')
    .map((s) => ({
      slot_index: s.index,
      kind: slotCardToIfaceBoard(s.card_type),
      port_count: Math.max(1, effectivePortCount(s)),
      ports: s.ports,
    }))
}

export function applyIfaceBoardsToSlots(
  n: number,
  boards: SwitchIfaceBoardPlacement[],
): SwitchSlotAttr[] {
  const want = clamp(n, 1, 48)
  const bySlot = new Map(boards.map((b) => [b.slot_index, b]))
  const slots: SwitchSlotAttr[] = []
  for (let i = 1; i <= want; i++) {
    const b = bySlot.get(i)
    if (b) {
      slots.push({
        index: i,
        purpose: 'DOWNLINK',
        card_type: ifaceBoardToSlotCard(b.kind),
        port_count: clamp(b.port_count || 48, 1, 128),
        port_start: 0,
        ports: normalizeBoardPorts(b.kind, clamp(b.port_count || 48, 1, 128), b.ports, i, 0),
      })
    } else {
      slots.push({
        index: i,
        purpose: 'BLANK',
        card_type: 'blank',
        port_count: 0,
        port_start: 0,
      })
    }
  }
  return renumberPortStarts(slots, 'core').map((s) => {
    if (s.card_type === 'blank' || s.purpose === 'BLANK') return s
    return {
      ...s,
      ports: normalizeBoardPorts(
        slotCardToIfaceBoard(s.card_type),
        effectivePortCount(s),
        s.ports,
        s.index,
        Math.max(0, Number(s.port_start) || 0),
      ),
    }
  })
}

function defaultUniformIfaceBoards(attrs: Record<string, unknown>, n: number): SwitchIfaceBoardPlacement[] {
  const rawCount = attrs.service_board_count
  const filled = clamp(rawCount == null ? 4 : Number(rawCount), 0, n)
  const kindRaw = String(attrs.iface_board_type || '10ge')
  const kind = isIfaceBoardKind(kindRaw) ? kindRaw : '10ge'
  const ports = clamp(Number(attrs.iface_board_port_count) || 48, 1, 128)
  const boards: SwitchIfaceBoardPlacement[] = []
  for (let i = 0; i < filled; i++) {
    boards.push({ slot_index: i + 1, kind, port_count: ports })
  }
  return boards
}

export function readCoreIfaceBoards(attrs: Record<string, unknown>): SwitchIfaceBoardPlacement[] {
  const n = clampCoreExpansionSlots(attrs)
  if (Array.isArray(attrs.iface_boards)) {
    return normalizeIfaceBoards(attrs.iface_boards, n)
  }
  const raw = Array.isArray(attrs.switch_slots) ? (attrs.switch_slots as SwitchSlotAttr[]) : []
  if (raw.length) {
    const fromSlots = normalizeIfaceBoards(slotsToIfaceBoards(raw), n)
    const hasBlank = raw.some((s) => s && (s.card_type === 'blank' || s.purpose === 'BLANK'))
    const kinds = new Set(fromSlots.map((b) => b.kind))
    if (fromSlots.length && (hasBlank || kinds.size > 1)) return fromSlots
  }
  return defaultUniformIfaceBoards(attrs, n)
}

export function emptyCoreSlotIndexes(attrs: Record<string, unknown>): number[] {
  const n = clampCoreExpansionSlots(attrs)
  const used = new Set(readCoreIfaceBoards(attrs).map((b) => b.slot_index))
  const empty: number[] = []
  for (let i = 1; i <= n; i++) {
    if (!used.has(i)) empty.push(i)
  }
  return empty
}

export function persistCoreIfaceBoards(
  attrs: Record<string, unknown>,
  boards: SwitchIfaceBoardPlacement[],
): SwitchSlotAttr[] {
  const n = clampCoreExpansionSlots(attrs)
  const next = normalizeIfaceBoards(boards, n)
  attrs.iface_boards = next
  attrs.service_board_count = next.length
  if (next[0]) {
    attrs.iface_board_type = next[0].kind
    attrs.iface_board_port_count = next[0].port_count
  }
  const slots = applyIfaceBoardsToSlots(n, next)
  attrs.switch_slots = slots
  attrs.card_slot_count = slots.length
  return slots
}

export function adjustCoreIfaceBoardCount(attrs: Record<string, unknown>, want: number): SwitchSlotAttr[] {
  const n = clampCoreExpansionSlots(attrs)
  const boards = readCoreIfaceBoards(attrs)
  const target = clamp(want, 0, n)
  const last = boards[boards.length - 1]
  const kind = last?.kind || (isIfaceBoardKind(String(attrs.iface_board_type || '')) ? (attrs.iface_board_type as SwitchIfaceBoardKind) : '10ge')
  const ports = last?.port_count || Number(attrs.iface_board_port_count) || 48
  boards.sort((a, b) => a.slot_index - b.slot_index)
  while (boards.length > target) boards.pop()
  const used = new Set(boards.map((b) => b.slot_index))
  while (boards.length < target) {
    let slot = 1
    while (used.has(slot) && slot <= n) slot += 1
    if (slot > n) break
    used.add(slot)
    boards.push({ slot_index: slot, kind, port_count: clamp(ports, 1, 128) })
  }
  return persistCoreIfaceBoards(attrs, boards)
}

export function addCoreIfaceBoard(
  attrs: Record<string, unknown>,
  patch?: Partial<SwitchIfaceBoardPlacement>,
): boolean {
  const empty = emptyCoreSlotIndexes(attrs)
  if (!empty.length) return false
  const boards = readCoreIfaceBoards(attrs)
  const last = boards[boards.length - 1]
  const slot =
    patch?.slot_index && empty.includes(patch.slot_index) ? patch.slot_index : empty[0]
  boards.push({
    slot_index: slot,
    kind: patch?.kind || last?.kind || '10ge',
    port_count: clamp(patch?.port_count || last?.port_count || 48, 1, 128),
    port_custom: patch?.port_custom,
  })
  persistCoreIfaceBoards(attrs, boards)
  return true
}

export function updateCoreIfaceBoard(
  attrs: Record<string, unknown>,
  slotIndex: number,
  patch: Partial<SwitchIfaceBoardPlacement>,
): void {
  const n = clampCoreExpansionSlots(attrs)
  const boards = readCoreIfaceBoards(attrs)
  const idx = boards.findIndex((b) => b.slot_index === slotIndex)
  if (idx < 0) return
  const next = { ...boards[idx], ...patch }
  if (patch.slot_index != null && patch.slot_index !== slotIndex) {
    const dest = clamp(patch.slot_index, 1, n)
    const occupant = boards.findIndex((b) => b.slot_index === dest)
    if (occupant >= 0) boards[occupant] = { ...boards[occupant], slot_index: slotIndex }
    next.slot_index = dest
  }
  if (patch.kind && patch.kind !== boards[idx].kind) {
    next.ports = normalizeBoardPorts(next.kind, next.port_count, [], next.slot_index, 0)
  } else {
    next.ports = normalizeBoardPorts(next.kind, next.port_count, next.ports, next.slot_index, 0)
  }
  boards[idx] = next
  persistCoreIfaceBoards(attrs, boards)
}

export function patchCoreBoardPort(
  attrs: Record<string, unknown>,
  slotIndex: number,
  portIndex: number,
  patch: Partial<SwitchBoardPortAttr>,
): SwitchBoardPortAttr | null {
  const boards = readCoreIfaceBoards(attrs)
  const board = boards.find((b) => b.slot_index === slotIndex)
  if (!board) return null
  const ports = normalizeBoardPorts(board.kind, board.port_count, board.ports, board.slot_index, 0)
  const idx = clamp(Math.trunc(portIndex) || 0, 0, Math.max(0, ports.length - 1))
  const cur = ports[idx]
  if (!cur) return null
  const next: SwitchBoardPortAttr = {
    ...cur,
    ...patch,
    index: idx,
    id: cur.id || boardPortId(board.slot_index, idx),
    code: cur.code || boardPortCode(board.slot_index, idx),
  }
  if (next.iface_type === 'copper') {
    next.module = patch.module || 'RJ45'
    next.connector = patch.connector || 'RJ45'
    next.fiber_mode = 'na'
    if (!patch.speed) next.speed = '1GE'
  }
  ports[idx] = next
  board.ports = ports
  persistCoreIfaceBoards(attrs, boards)
  return next
}

export function readSwitchSystemPorts(attrs: Record<string, unknown> | null | undefined): SwitchSystemPortAttr[] {
  if (!attrs) return []
  return syncSwitchSystemPorts(attrs, false)
}

export function syncSwitchSystemPorts(
  attrs: Record<string, unknown>,
  write = true,
): SwitchSystemPortAttr[] {
  const role = String(attrs.switch_role || 'gigabit') as SwitchSubtype
  const core = isCoreOrAggRole(role)
  const specs: { kind: SwitchSystemPortKind; count: number }[] = core
    ? [
        { kind: 'console', count: clamp(Number(attrs.console_ports) || 0, 0, 8) },
        { kind: 'eth_mgmt', count: clamp(Number(attrs.eth_mgmt_ports ?? attrs.mgmt_ports) || 0, 0, 8) },
        { kind: 'usb', count: clamp(Number(attrs.usb_ports) || 0, 0, 8) },
        { kind: 'stack', count: clamp(Number(attrs.stack_cluster_ports) || 0, 0, 16) },
      ]
    : [
        { kind: 'eth_mgmt', count: clamp(Number(attrs.mgmt_ports) || 0, 0, 8) },
        { kind: 'stack', count: clamp(Number(attrs.stack_cluster_ports) || 0, 0, 16) },
      ]
  const prev = new Map<string, SwitchSystemPortAttr>()
  if (Array.isArray(attrs.system_ports)) {
    for (const item of attrs.system_ports) {
      if (!item || typeof item !== 'object') continue
      const src = item as Record<string, unknown>
      const kind = String(src.kind || '') as SwitchSystemPortKind
      if (!['eth_mgmt', 'console', 'usb', 'stack'].includes(kind)) continue
      const index = Math.max(0, Math.trunc(Number(src.index) || 0))
      const parsed: SwitchSystemPortAttr = {
        kind,
        index,
        id: systemPortId(kind, index),
        code: systemPortCode(kind, index),
        iface_type: asPortIfaceType(src.iface_type, defaultSystemPortSpec(kind).iface_type),
        speed: String(src.speed || defaultSystemPortSpec(kind).speed),
        module: String(src.module || defaultSystemPortSpec(kind).module),
        connector: String(src.connector || defaultSystemPortSpec(kind).connector),
        fiber_mode: asPortFiberMode(src.fiber_mode, defaultSystemPortSpec(kind).fiber_mode),
      }
      prev.set(`${kind}:${index}`, parsed)
    }
  }
  const next: SwitchSystemPortAttr[] = []
  for (const spec of specs) {
    const def = defaultSystemPortSpec(spec.kind)
    for (let i = 0; i < spec.count; i++) {
      const old = prev.get(`${spec.kind}:${i}`)
      next.push({
        kind: spec.kind,
        index: i,
        id: systemPortId(spec.kind, i),
        code: systemPortCode(spec.kind, i),
        iface_type: old?.iface_type || def.iface_type,
        speed: old?.speed || def.speed,
        module: old?.module || def.module,
        connector: old?.connector || def.connector,
        fiber_mode: old?.fiber_mode || def.fiber_mode,
      })
    }
  }
  if (write) attrs.system_ports = next
  return next
}

export function patchSwitchSystemPort(
  attrs: Record<string, unknown>,
  portId: string,
  patch: Partial<SwitchBoardPortAttr>,
): SwitchSystemPortAttr | null {
  const ports = syncSwitchSystemPorts(attrs)
  const idx = ports.findIndex((p) => p.id === portId)
  if (idx < 0) return null
  const cur = ports[idx]
  const next: SwitchSystemPortAttr = {
    ...cur,
    ...patch,
    kind: cur.kind,
    index: cur.index,
    id: cur.id,
    code: cur.code,
  }
  if (next.iface_type === 'copper' && cur.kind !== 'usb') {
    next.module = patch.module || 'RJ45'
    next.connector = patch.connector || 'RJ45'
    next.fiber_mode = 'na'
  }
  ports[idx] = next
  attrs.system_ports = ports
  return next
}

export function removeCoreIfaceBoard(attrs: Record<string, unknown>, slotIndex: number): void {
  persistCoreIfaceBoards(
    attrs,
    readCoreIfaceBoards(attrs).filter((b) => b.slot_index !== slotIndex),
  )
}

export function rebuildCoreExpansionSlots(attrs: Record<string, unknown>): SwitchSlotAttr[] {
  return persistCoreIfaceBoards(attrs, readCoreIfaceBoards(attrs))
}

export function normalizeSwitchSlots(
  raw: unknown,
  role: SwitchSubtype,
  slotCount?: number,
): SwitchSlotAttr[] {
  const want = clamp(slotCount ?? defaultCardSlotCount(role), 1, 16)
  if (!Array.isArray(raw) || !raw.length) return defaultSwitchSlots(role, want)
  const list: SwitchSlotAttr[] = []
  for (let i = 0; i < want; i++) {
    const src = (raw[i] && typeof raw[i] === 'object' ? raw[i] : {}) as Record<string, unknown>
    let card = String(src.card_type || 'ten_gigabit') as SwitchSlotCardType
    if (!['gigabit', 'ten_gigabit', '25g', '40g', '100g', '400g', 'blank'].includes(card)) {
      card = 'ten_gigabit'
    }
    let purpose = String(src.purpose || 'DOWNLINK') as SwitchSlotPurpose
    if (!['DOWNLINK', 'UPLINK', 'DOWNLINK_UPLINK', 'BLANK'].includes(purpose)) purpose = 'DOWNLINK'
    if (card === 'blank') purpose = 'BLANK'
    let portCount = Number(src.port_count) || 0
    let mpoCount = Number(src.mpo_count) || 0
    let lcCount = Number(src.lc_count) || 0
    // 历史数据选了 40/100G 但未填口数时，按角色补默认
    if (card === '100g' && portCount <= 0 && mpoCount + lcCount <= 0) {
      portCount = default100gPortCount(role)
      mpoCount = portCount
      lcCount = 0
    }
    const entry: SwitchSlotAttr = {
      index: i + 1,
      purpose,
      card_type: card,
      port_count: portCount,
      mpo_count: mpoCount,
      lc_count: lcCount,
      port_start: Number(src.port_start) || 0,
      ports: Array.isArray(src.ports) ? (src.ports as SwitchBoardPortAttr[]) : undefined,
    }
    list.push(entry)
  }
  return renumberPortStarts(list, role).map((s) => {
    if (s.card_type === 'blank' || s.purpose === 'BLANK') {
      return { ...s, ports: undefined }
    }
    return {
      ...s,
      ports: normalizeBoardPorts(
        slotCardToIfaceBoard(s.card_type),
        effectivePortCount(s),
        s.ports,
        s.index,
        Math.max(0, Number(s.port_start) || 0),
      ),
    }
  })
}

/** 网络设备完整默认 attributes */
export function defaultNetworkSwitchAttributes(role: SwitchSubtype = 'gigabit'): Record<string, unknown> {
  const core = isCoreOrAggRole(role)
  const slots = defaultSwitchSlots(role)
  const downlinkPorts = slots
    .filter((s) => s.purpose === 'DOWNLINK' || s.purpose === 'DOWNLINK_UPLINK')
    .reduce((a, s) => a + effectivePortCount(s), 0)
  const uplinkPorts = slots
    .filter((s) => s.purpose === 'UPLINK')
    .reduce((a, s) => a + effectivePortCount(s), 0)
  const attrs: Record<string, unknown> = {
    switch_role: role === 'aggregation' ? 'aggregation' : role,
    is_bmc_switch: false,
    card_slot_count: slots.length,
    switch_slots: slots,
    optical_card_count: 1,
    optical_ports_per_card: 48,
    downlink_count: downlinkPorts || 48,
    uplink_count: core ? 0 : role === 'gigabit' ? 8 : 6,
    uplink_type: role === 'gigabit' ? '10g' : role === 'ten_gigabit' ? '40g' : '40_100g',
    downlink_type: role === 'gigabit' ? '1g' : '10g',
    downlink_media: role === 'gigabit' ? 'copper' : 'optical',
    uplink_media: 'AUTO',
    uplink_position: 'right' as UplinkPosition,
    mgmt_ports: 1,
    console_ports: 1,
    eth_mgmt_ports: 1,
    usb_ports: 1,
    stack_cluster_ports: core ? 2 : 0,
    fabric_slot_count: core ? 2 : 0,
    airflow_type: 'front_to_rear',
    airflow_custom: '',
    chassis_dim_a: 442,
    chassis_dim_b: core ? 660 : 420,
    chassis_dim_c: core ? 175 : 44,
    max_power_watt: core ? 3000 : 150,
    modular_expansion_slots: core ? 6 : slots.length,
    service_board_count: core ? 4 : 0,
    iface_board_type: '10ge' as SwitchIfaceBoardKind,
    iface_board_port_count: 48,
    iface_board_port_custom: false,
    panel_style_image: null,
    panel_style_mode: 'generated',
    fan_count: core ? 4 : 2,
    psu_count: core ? 4 : 2,
    line_cards: slotsToLineCards(slots),
    chassis_height_u: core ? 10 : 1,
    panel_layout: {
      cols: 38,
      rows: 16,
      grid_scale: 4,
      front: { cols: 38, rows: 16, items: [] },
      rear: { cols: 38, rows: 16, items: [] },
    },
    custom_attributes: [],
  }
  if (core) {
    const rebuilt = rebuildCoreExpansionSlots(attrs)
    attrs.switch_slots = rebuilt
    attrs.card_slot_count = rebuilt.length
    attrs.line_cards = slotsToLineCards(rebuilt)
    normalizeBlankPanelRows(attrs)
  } else {
    syncAccessSwitchSlots(attrs)
  }
  syncSwitchSystemPorts(attrs)
  return attrs
}

export function effectivePortCount(slot: SwitchSlotAttr): number {
  if (slot.card_type === 'blank' || slot.purpose === 'BLANK') return 0
  const total = Number(slot.port_count)
  if (Number.isFinite(total) && total >= 0) return clamp(total, 0, 128)
  if (slot.card_type === '100g') {
    return clamp(Number(slot.mpo_count) || 0, 0, 36) + clamp(Number(slot.lc_count) || 0, 0, 36)
  }
  return 0
}

function toCoreCardType(card: SwitchSlotCardType): CoreCardType {
  if (card === 'blank') return 'blank'
  if (card === 'gigabit') return 'gigabit'
  if (card === '40g' || card === '100g' || card === '400g') return '100g'
  return 'ten_gigabit'
}

export function slotsToLineCards(slots: SwitchSlotAttr[]): CoreLineCard[] {
  return slots.map((s) => {
    const ct = toCoreCardType(s.card_type)
    return {
      ...newCoreLineCard(ct, effectivePortCount(s) || (ct === 'blank' ? 0 : 48)),
      id: `slot${s.index}`,
    }
  })
}

export function portTypeForSlot(slot: SwitchSlotAttr): PortType {
  if (slot.card_type === 'gigabit') return '1g'
  if (slot.card_type === 'ten_gigabit') return '10g'
  if (slot.card_type === '25g') return '25g'
  if (slot.card_type === '40g' || slot.card_type === '100g' || slot.card_type === '400g') return '40_100g'
  return 'other'
}

/** 切换交换机样式时重置接口 Slot */
export function applySwitchStyleDefaults(
  attrs: Record<string, unknown>,
  role: SwitchSubtype,
): Record<string, unknown> {
  const next = { ...attrs, ...defaultNetworkSwitchAttributes(role) }
  // 保留面板手动画过的 layout 可选：按需求「模板样式暂不变」，重置为默认空面板
  return next
}

/** 从 attributes 读取并规范化 switch_slots */
export function readSwitchSlots(attrs: Record<string, unknown> | null | undefined): SwitchSlotAttr[] {
  if (!attrs) return defaultSwitchSlots('gigabit')
  const role = String(attrs.switch_role || 'gigabit') as SwitchSubtype
  const count = Number(attrs.card_slot_count) || defaultCardSlotCount(role)
  return normalizeSwitchSlots(attrs.switch_slots, role, count)
}

function ensureSwitchHardwareDefaults(attrs: Record<string, unknown>, core: boolean): void {
  if (attrs.airflow_type == null) attrs.airflow_type = 'front_to_rear'
  if (attrs.airflow_custom == null) attrs.airflow_custom = ''
  if (attrs.chassis_dim_a == null) attrs.chassis_dim_a = 442
  if (attrs.chassis_dim_b == null) attrs.chassis_dim_b = core ? 660 : 420
  if (attrs.chassis_dim_c == null) attrs.chassis_dim_c = core ? 175 : 44
  if (attrs.max_power_watt == null) attrs.max_power_watt = core ? 3000 : 150
  if (attrs.fabric_slot_count == null) attrs.fabric_slot_count = core ? 2 : 0
  if (attrs.console_ports == null) attrs.console_ports = 1
  if (attrs.eth_mgmt_ports == null) attrs.eth_mgmt_ports = Number(attrs.mgmt_ports) || 1
  if (attrs.usb_ports == null) attrs.usb_ports = 1
  if (attrs.stack_cluster_ports == null) attrs.stack_cluster_ports = core ? 2 : 0
  if (attrs.fan_count == null) attrs.fan_count = core ? 4 : 2
  if (attrs.psu_count == null) attrs.psu_count = core ? 4 : 2
  if (attrs.panel_style_mode == null) {
    attrs.panel_style_mode = attrs.panel_style_image ? 'custom' : 'generated'
  }
}

export function readGigabitDownlinkMedia(
  attrs: Record<string, unknown> | null | undefined,
): GigabitDownlinkMedia {
  const raw = String(attrs?.downlink_media || '').toLowerCase()
  if (raw === 'optical' || raw === 'fiber') return 'optical'
  return 'copper'
}

export function readTenGigUplinkKind(attrs: Record<string, unknown> | null | undefined): TenGigUplinkKind {
  const raw = String(attrs?.uplink_type || '').toLowerCase()
  if (raw === '100g' || raw === '100ge') return '100ge'
  return '40ge'
}

export function defaultAccessDownlinkSpec(
  role: SwitchSubtype,
  media: GigabitDownlinkMedia,
): Omit<SwitchBoardPortAttr, 'index' | 'id' | 'code'> {
  if (role === 'gigabit' && media === 'copper') {
    return { iface_type: 'copper', speed: '1GE', module: 'RJ45', connector: 'RJ45', fiber_mode: 'na' }
  }
  if (role === 'gigabit') {
    return { iface_type: 'optical', speed: '1GE', module: 'SFP', connector: 'LC', fiber_mode: 'mm' }
  }
  return defaultPortSpecForKind('10ge')
}

export function defaultAccessUplinkSpec(
  role: SwitchSubtype,
  kind: TenGigUplinkKind,
): Omit<SwitchBoardPortAttr, 'index' | 'id' | 'code'> {
  if (role === 'gigabit') return defaultPortSpecForKind('10ge')
  if (kind === '100ge') return defaultPortSpecForKind('100ge')
  return defaultPortSpecForKind('40ge')
}

function flattenSlotPorts(slots: SwitchSlotAttr[], uplink: boolean): unknown[] {
  const out: Record<string, unknown>[] = []
  for (const s of slots) {
    const isUp = s.purpose === 'UPLINK'
    if (uplink !== isUp) continue
    if (s.card_type === 'blank' || s.purpose === 'BLANK') continue
    const ports = Array.isArray(s.ports) ? s.ports : []
    for (const p of ports) {
      if (!p || typeof p !== 'object') continue
      out.push({ ...(p as Record<string, unknown>), index: out.length })
    }
  }
  return out
}

function clampAccessUplinkCount(role: SwitchSubtype, count: number) {
  let n = clamp(Math.round(Number(count) || 0), 0, 8)
  if (role === 'ten_gigabit' && n > 0 && n % 2 !== 0) n -= 1
  if (role === 'gigabit' && n > 4 && n % 2 !== 0) n -= 1
  return n
}

export function syncAccessSwitchSlots(attrs: Record<string, unknown>): SwitchSlotAttr[] {
  const role = String(attrs.switch_role || 'gigabit') as SwitchSubtype
  const media = readGigabitDownlinkMedia(attrs)
  const ulKind = readTenGigUplinkKind(attrs)
  const downCount = clamp(Number(attrs.downlink_count) || 48, 1, 128)
  const upCount = clampAccessUplinkCount(role, Number(attrs.uplink_count) ?? (role === 'gigabit' ? 8 : 6))
  const prev = Array.isArray(attrs.switch_slots) ? (attrs.switch_slots as SwitchSlotAttr[]) : []
  const downRaw = flattenSlotPorts(prev, false)
  const upRaw = flattenSlotPorts(prev, true)
  const downSpec = defaultAccessDownlinkSpec(role, media)
  const upSpec = defaultAccessUplinkSpec(role, ulKind)
  const downKind: SwitchIfaceBoardKind = '10ge'
  const upBoardKind: SwitchIfaceBoardKind = role === 'gigabit' ? '10ge' : ulKind === '100ge' ? '100ge' : '40ge'
  const downSlot: SwitchSlotAttr = {
    index: 1,
    purpose: 'DOWNLINK',
    card_type: role === 'gigabit' ? 'gigabit' : 'ten_gigabit',
    port_count: downCount,
    port_start: 0,
    ports: normalizeBoardPorts(downKind, downCount, downRaw, 1, 0, downSpec),
  }
  const upSlot: SwitchSlotAttr = {
    index: 2,
    purpose: 'UPLINK',
    card_type: role === 'gigabit' ? 'ten_gigabit' : ulKind === '100ge' ? '100g' : '40g',
    port_count: upCount,
    port_start: 0,
    mpo_count: role === 'ten_gigabit' ? upCount : 0,
    lc_count: 0,
    ports: normalizeBoardPorts(upBoardKind, upCount, upRaw, 2, 0, upSpec).map((p, i) => ({
      ...p,
      id: boardPortId(2, i),
      code: `U${i + 1}`,
    })),
  }
  const slots = [downSlot, upSlot]
  attrs.switch_slots = slots
  attrs.card_slot_count = 2
  attrs.downlink_count = downCount
  attrs.uplink_count = upCount
  attrs.optical_card_count = 1
  attrs.optical_ports_per_card = downCount
  attrs.downlink_type = role === 'gigabit' ? '1g' : '10g'
  attrs.uplink_type = role === 'gigabit' ? '10g' : ulKind === '100ge' ? '100g' : '40g'
  attrs.downlink_media = role === 'gigabit' ? media : 'optical'
  attrs.uplink_position = role === 'gigabit' ? 'right' : attrs.uplink_position === 'middle' ? 'middle' : 'right'
  attrs.line_cards = slotsToLineCards(slots)
  if (attrs.chassis_height_u == null) attrs.chassis_height_u = 1
  return slots
}

export function patchAccessBoardPort(
  attrs: Record<string, unknown>,
  slotIndex: number,
  portIndex: number,
  patch: Partial<SwitchBoardPortAttr>,
): SwitchBoardPortAttr | null {
  const slots = syncAccessSwitchSlots(attrs)
  const slot = slots.find((s) => s.index === slotIndex)
  if (!slot) return null
  const kind = slotCardToIfaceBoard(slot.card_type)
  const spec =
    slot.purpose === 'UPLINK'
      ? defaultAccessUplinkSpec(String(attrs.switch_role || 'gigabit') as SwitchSubtype, readTenGigUplinkKind(attrs))
      : defaultAccessDownlinkSpec(
          String(attrs.switch_role || 'gigabit') as SwitchSubtype,
          readGigabitDownlinkMedia(attrs),
        )
  const ports = normalizeBoardPorts(
    kind,
    effectivePortCount(slot),
    slot.ports,
    slot.index,
    Math.max(0, Number(slot.port_start) || 0),
    spec,
  )
  const idx = clamp(Math.trunc(portIndex) || 0, 0, Math.max(0, ports.length - 1))
  const cur = ports[idx]
  if (!cur) return null
  const next: SwitchBoardPortAttr = {
    ...cur,
    ...patch,
    index: idx,
    id: cur.id || boardPortId(slot.index, idx),
    code: slot.purpose === 'UPLINK' ? `U${idx + 1}` : cur.code || boardPortCode(slot.index, idx),
  }
  if (next.iface_type === 'copper') {
    next.module = patch.module || 'RJ45'
    next.connector = patch.connector || 'RJ45'
    next.fiber_mode = 'na'
    if (!patch.speed) next.speed = '1GE'
  }
  ports[idx] = next
  slot.ports = ports
  attrs.switch_slots = slots.map((s) => (s.index === slot.index ? { ...slot, ports } : s))
  return next
}

export function syncSwitchDerivedCounts(attrs: Record<string, unknown>): void {
  const role = String(attrs.switch_role || 'gigabit') as SwitchSubtype
  const core = isCoreOrAggRole(role)
  ensureSwitchHardwareDefaults(attrs, core)
  if (core) {
    if (attrs.modular_expansion_slots == null) {
      attrs.modular_expansion_slots = Array.isArray(attrs.switch_slots)
        ? (attrs.switch_slots as unknown[]).length || 6
        : 6
    }
    if (attrs.service_board_count == null) {
      const raw = Array.isArray(attrs.switch_slots) ? (attrs.switch_slots as SwitchSlotAttr[]) : []
      const filled = raw.filter((s) => s && s.card_type !== 'blank' && s.purpose !== 'BLANK').length
      attrs.service_board_count = filled || 4
    }
    if (attrs.iface_board_type == null) attrs.iface_board_type = '10ge'
    if (attrs.iface_board_port_count == null) attrs.iface_board_port_count = 48
    if (attrs.chassis_height_u == null) attrs.chassis_height_u = 10
    clampCoreExpansionSlots(attrs)
    normalizeBlankPanelRows(attrs)
    const slots = rebuildCoreExpansionSlots(attrs)
    attrs.service_board_count = clamp(
      Number(attrs.service_board_count) || 0,
      0,
      Number(attrs.modular_expansion_slots) || 6,
    )
    attrs.switch_slots = slots
    attrs.card_slot_count = slots.length
    attrs.line_cards = slotsToLineCards(slots)
    attrs.downlink_count = slots.reduce((a, s) => a + effectivePortCount(s), 0)
    attrs.uplink_count = 0
    attrs.optical_card_count = slots.filter((s) => s.card_type !== 'blank').length || 1
    attrs.optical_ports_per_card = Number(attrs.iface_board_port_count) || 48
    syncSwitchSystemPorts(attrs)
    return
  }
  syncAccessSwitchSlots(attrs)
  syncSwitchSystemPorts(attrs)
}
