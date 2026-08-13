/**
 * 网络设备（交换机）模型属性 — 对齐 docs/设备属性参数定义.xmind
 * 面板样式仍走现有 layout 引擎，本文件只定义属性与默认 Slot。
 */

import type { CoreCardType, CoreLineCard, PortType, SwitchSubtype, UplinkPosition } from '@/api/network'
import { newCoreLineCard } from '@/api/network'

/** Slot 用途 */
export type SwitchSlotPurpose = 'DOWNLINK' | 'UPLINK' | 'DOWNLINK_UPLINK' | 'BLANK'

/** 板卡类型（核心/汇聚可选；接入类按角色固定） */
export type SwitchSlotCardType = 'gigabit' | 'ten_gigabit' | '100g' | 'blank'

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
  if (role === 'gigabit') return 2
  if (role === 'ten_gigabit') return 3
  return 3 // core / aggregation
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
  if (role === 'gigabit') {
    // slot1 DOWNLINK 1G×48；slot2 UPLINK 10G×6；无默认 40/100G；每槽编号从 0 起
    const slots: SwitchSlotAttr[] = [
      {
        index: 1,
        purpose: 'DOWNLINK',
        card_type: 'gigabit',
        port_count: 48,
        port_start: 0,
      },
    ]
    if (n >= 2) {
      slots.push({
        index: 2,
        purpose: 'UPLINK',
        card_type: 'ten_gigabit',
        port_count: 6,
        port_start: 0,
      })
    }
    for (let i = slots.length; i < n; i++) {
      slots.push({
        index: i + 1,
        purpose: 'BLANK',
        card_type: 'blank',
        port_count: 0,
        port_start: 0,
      })
    }
    return renumberPortStarts(slots, role)
  }

  if (role === 'ten_gigabit') {
    // slot1/2 DOWNLINK 10G（连续编号 0-23 / 24-47）；slot3 UPLINK 40/100G 从 0 起
    const up = default100gPortCount('ten_gigabit')
    const slots: SwitchSlotAttr[] = [
      {
        index: 1,
        purpose: 'DOWNLINK',
        card_type: 'ten_gigabit',
        port_count: 24,
        port_start: 0,
      },
      {
        index: 2,
        purpose: 'DOWNLINK',
        card_type: 'ten_gigabit',
        port_count: 24,
        port_start: 0,
      },
      sync100gPortFields(
        {
          index: 3,
          purpose: 'UPLINK',
          card_type: '100g',
          port_count: up,
          mpo_count: up,
          lc_count: 0,
          port_start: 0,
        },
        up,
      ),
    ]
    return renumberPortStarts(
      slots
        .slice(0, Math.max(3, n))
        .concat(
          n > 3
            ? Array.from({ length: n - 3 }, (_, i) => ({
                index: 4 + i,
                purpose: 'BLANK' as const,
                card_type: 'blank' as const,
                port_count: 0,
                port_start: 0,
              }))
            : [],
        )
        .slice(0, n),
      role,
    )
  }

  // core / aggregation：默认 3 槽万兆板卡；每槽接口编号各自从 0 起
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
    if (next.card_type === '100g') {
      next = sync100gPortFields(next)
    } else {
      next.port_count = clamp(Number(next.port_count) || 0, 0, 128)
    }
    next.port_start = 0
    return next
  })
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
    if (!['gigabit', 'ten_gigabit', '100g', 'blank'].includes(card)) card = 'ten_gigabit'
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
    }
    list.push(entry)
  }
  return renumberPortStarts(list, role)
}

/** 网络设备完整默认 attributes */
export function defaultNetworkSwitchAttributes(role: SwitchSubtype = 'gigabit'): Record<string, unknown> {
  const slots = defaultSwitchSlots(role)
  const downlinkPorts = slots
    .filter((s) => s.purpose === 'DOWNLINK' || s.purpose === 'DOWNLINK_UPLINK')
    .reduce((a, s) => a + effectivePortCount(s), 0)
  const uplinkPorts = slots
    .filter((s) => s.purpose === 'UPLINK')
    .reduce((a, s) => a + effectivePortCount(s), 0)
  return {
    switch_role: role === 'aggregation' ? 'aggregation' : role,
    /** 千兆交换机可标记为 BMC 管理交换机（18-rules BMC_SWITCH） */
    is_bmc_switch: false,
    card_slot_count: slots.length,
    switch_slots: slots,
    optical_card_count: slots.filter((s) => s.purpose !== 'UPLINK' && s.card_type !== 'blank').length || 1,
    optical_ports_per_card:
      role === 'ten_gigabit' ? 24 : role === 'gigabit' ? 48 : 48,
    downlink_count: downlinkPorts || 48,
    uplink_count: clamp(uplinkPorts || (role === 'gigabit' ? 6 : 6), 0, 8),
    uplink_type: role === 'gigabit' ? '10g' : '40_100g',
    downlink_type: role === 'gigabit' ? '1g' : role === 'ten_gigabit' ? '10g' : '10g',
    /** 可选：默认介质粗分/细类，stamp 到端口（AUTO=按口类型推导） */
    downlink_media: 'AUTO',
    uplink_media: 'AUTO',
    uplink_position: 'right' as UplinkPosition,
    mgmt_ports: 1,
    fan_count: 2,
    psu_count: 2,
    // 兼容旧核心线卡
    line_cards: slotsToLineCards(slots),
    chassis_height_u: role === 'core' || role === 'aggregation' ? Math.max(3, slots.length) : 1,
    panel_layout: {
      cols: 38,
      rows: 16,
      grid_scale: 4,
      front: { cols: 38, rows: 16, items: [] },
      rear: { cols: 38, rows: 16, items: [] },
    },
    custom_attributes: [],
  }
}

export function effectivePortCount(slot: SwitchSlotAttr): number {
  if (slot.card_type === 'blank' || slot.purpose === 'BLANK') return 0
  if (slot.card_type === '100g') {
    const total = Number(slot.port_count)
    if (Number.isFinite(total) && total >= 0) return clamp(total, 0, 36)
    return clamp(Number(slot.mpo_count) || 0, 0, 36) + clamp(Number(slot.lc_count) || 0, 0, 36)
  }
  return clamp(Number(slot.port_count) || 0, 0, 128)
}

export function slotsToLineCards(slots: SwitchSlotAttr[]): CoreLineCard[] {
  return slots.map((s) => {
    const ct = (s.card_type === 'blank' ? 'blank' : s.card_type) as CoreCardType
    return {
      ...newCoreLineCard(ct, effectivePortCount(s) || (ct === 'blank' ? 0 : 48)),
      id: `slot${s.index}`,
    }
  })
}

export function portTypeForSlot(slot: SwitchSlotAttr): PortType {
  if (slot.card_type === 'gigabit') return '1g'
  if (slot.card_type === 'ten_gigabit') return '10g'
  if (slot.card_type === '100g') return '40_100g'
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

export function syncSwitchDerivedCounts(attrs: Record<string, unknown>): void {
  const role = String(attrs.switch_role || 'gigabit') as SwitchSubtype
  const slots = readSwitchSlots(attrs)
  attrs.switch_slots = slots
  attrs.card_slot_count = slots.length
  attrs.line_cards = slotsToLineCards(slots)
  let down = 0
  let up = 0
  for (const s of slots) {
    const c = effectivePortCount(s)
    if (s.card_type === 'blank' || s.purpose === 'BLANK') continue
    if (s.purpose === 'UPLINK' || s.purpose === 'DOWNLINK_UPLINK' || s.card_type === '100g') {
      up += c
    }
    if (s.purpose !== 'UPLINK') {
      down += c
    }
  }
  attrs.downlink_count = down
  // 接入交换机上联口物理上限 8；核心/汇聚 40/100G 线卡可更大
  attrs.uplink_count =
    role === 'core' || role === 'aggregation' ? clamp(up, 0, 256) : clamp(up, 0, 8)
  attrs.optical_card_count = slots.filter((s) => s.purpose !== 'UPLINK' && s.card_type !== 'blank').length || 1
  const downSlots = slots.filter((s) => s.purpose !== 'UPLINK' && s.card_type !== 'blank')
  attrs.optical_ports_per_card = downSlots.length
    ? Math.max(1, Math.round(down / downSlots.length))
    : 48
  if (role === 'core' || role === 'aggregation') {
    attrs.chassis_height_u = Math.max(Number(attrs.chassis_height_u) || slots.length, slots.length)
  }
}
