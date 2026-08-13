/**
 * 安全设备模型属性 — 对齐 docs/设备属性参数定义.xmind
 * 面板样式仍走现有 securityFrontPanel，本文件定义基础/接口 Slot。
 */

import type { SecurityZoneInput } from '@/utils/securityFrontPanel'

/** 安全设备接口板卡插槽 */
export interface SecurityIfaceSlotAttr {
  index: number
  control_count: number
  ha_count: number
  mgmt_count: number
  usb_count: number
  /** 10G 光口数量 */
  ports_10g: number
  /** 1G 电口数量 */
  ports_1g: number
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n))
}

/** 安全设备高度：现有面板引擎支持 1U/2U */
export type SecurityFormFactorU = 1 | 2

export const SECURITY_HEIGHT_OPTIONS: { value: SecurityFormFactorU; label: string }[] = [
  { value: 1, label: '1U' },
  { value: 2, label: '2U' },
]

export function normalizeSecurityFormFactor(u: unknown): SecurityFormFactorU {
  const n = Number(u)
  return Number.isFinite(n) && n >= 2 ? 2 : 1
}

export function defaultSecurityIfaceSlots(slotCount = 4): SecurityIfaceSlotAttr[] {
  const n = clamp(slotCount, 1, 16)
  const slots: SecurityIfaceSlotAttr[] = []
  for (let i = 0; i < n; i++) {
    slots.push({
      index: i + 1,
      control_count: i === 0 ? 1 : 0,
      ha_count: i === 0 ? 2 : 0,
      mgmt_count: i === 0 ? 1 : 0,
      usb_count: i === 0 ? 2 : 0,
      ports_10g: 4,
      ports_1g: 2,
    })
  }
  return normalizeSecurityIfaceSlots(slots, n)
}

export function normalizeSecurityIfaceSlots(
  raw: unknown,
  slotCount?: number,
): SecurityIfaceSlotAttr[] {
  const want = clamp(slotCount ?? (Array.isArray(raw) ? raw.length : 4) ?? 4, 1, 16)
  if (!Array.isArray(raw) || !raw.length) return defaultSecurityIfaceSlots(want)
  const list: SecurityIfaceSlotAttr[] = []
  for (let i = 0; i < want; i++) {
    const src = (raw[i] && typeof raw[i] === 'object' ? raw[i] : {}) as Record<string, unknown>
    list.push({
      index: i + 1,
      control_count: clamp(Number(src.control_count) || 0, 0, 8),
      ha_count: clamp(Number(src.ha_count) || 0, 0, 8),
      mgmt_count: clamp(Number(src.mgmt_count) || 0, 0, 8),
      usb_count: clamp(Number(src.usb_count) || 0, 0, 8),
      ports_10g: clamp(Number(src.ports_10g) || 0, 0, 48),
      ports_1g: clamp(Number(src.ports_1g) || 0, 0, 48),
    })
  }
  return list
}

export function readSecurityIfaceSlots(
  attrs: Record<string, unknown> | null | undefined,
): SecurityIfaceSlotAttr[] {
  if (!attrs) return defaultSecurityIfaceSlots(4)
  const count = Number(attrs.slot_count) || Number(attrs.card_slot_count) || 4
  if (Array.isArray(attrs.security_slots) && attrs.security_slots.length) {
    return normalizeSecurityIfaceSlots(attrs.security_slots, count)
  }
  // 兼容旧扁平口数：合成 1 槽
  const data10 = String(attrs.data_port_type || '') === '1g' ? 0 : Number(attrs.data_port_count) || 0
  const data1 = String(attrs.data_port_type || '') === '1g' ? Number(attrs.data_port_count) || 0 : 0
  if (data10 || data1 || attrs.control_ports || attrs.ha_ports || attrs.mgmt_ports) {
    return normalizeSecurityIfaceSlots(
      [
        {
          index: 1,
          control_count: Number(attrs.control_ports) || 0,
          ha_count: Number(attrs.ha_ports) || 0,
          mgmt_count: Number(attrs.mgmt_ports) || 0,
          usb_count: Number(attrs.usb_ports) || 0,
          ports_10g: data10 || 4,
          ports_1g: data1 || 2,
        },
      ],
      count,
    )
  }
  return defaultSecurityIfaceSlots(count)
}

/** 转为安全面板 zones（保留现有 zone 布局引擎） */
export function securitySlotsToZones(slots: SecurityIfaceSlotAttr[]): SecurityZoneInput[] {
  const zones: SecurityZoneInput[] = []
  for (const s of slots) {
    if (s.ports_10g > 0) {
      zones.push({
        label: `Slot${s.index} 10G`,
        port_type: '10g',
        count: s.ports_10g,
        zone_layout: s.ports_10g >= 8 ? 'two_row' : 'auto',
      })
    }
    if (s.ports_1g > 0) {
      zones.push({
        label: `Slot${s.index} 1G`,
        port_type: '1g',
        count: s.ports_1g,
        zone_layout: s.ports_1g >= 8 ? 'two_row' : 'auto',
      })
    }
    if (s.control_count > 0) {
      zones.push({
        label: `Slot${s.index} CONTROL`,
        port_type: '1g',
        count: s.control_count,
        zone_layout: 'single_row',
      })
    }
    if (s.ha_count > 0) {
      zones.push({
        label: `Slot${s.index} HA`,
        port_type: '10g',
        count: s.ha_count,
        zone_layout: 'single_row',
      })
    }
    if (s.mgmt_count > 0) {
      zones.push({
        label: `Slot${s.index} MGMT`,
        port_type: 'bmc',
        count: s.mgmt_count,
        zone_layout: 'single_row',
      })
    }
    if (s.usb_count > 0) {
      zones.push({
        label: `Slot${s.index} USB`,
        port_type: 'other',
        count: s.usb_count,
        zone_layout: 'single_row',
      })
    }
  }
  return zones.length
    ? zones
    : [{ label: 'DATA', port_type: '10g', count: 8, zone_layout: 'two_row' }]
}

export function syncSecurityDerivedAttrs(attrs: Record<string, unknown>): void {
  const u = normalizeSecurityFormFactor(attrs.chassis_height_u ?? attrs.form_factor_u)
  attrs.chassis_height_u = u
  attrs.form_factor_u = u
  const count = clamp(Number(attrs.slot_count) || 4, 1, 16)
  attrs.slot_count = count
  const slots = normalizeSecurityIfaceSlots(attrs.security_slots, count)
  attrs.security_slots = slots

  // 兼容旧扁平字段（汇总）
  attrs.data_port_type = '10g'
  attrs.data_port_count = slots.reduce((a, s) => a + s.ports_10g, 0)
  attrs.control_ports = slots.reduce((a, s) => a + s.control_count, 0)
  attrs.ha_ports = slots.reduce((a, s) => a + s.ha_count, 0)
  attrs.mgmt_ports = slots.reduce((a, s) => a + s.mgmt_count, 0)
  attrs.usb_ports = slots.reduce((a, s) => a + s.usb_count, 0)

  if (attrs.fan_count == null) attrs.fan_count = 2
  if (attrs.psu_count == null) attrs.psu_count = 2
  attrs.fan_count = clamp(Number(attrs.fan_count) || 0, 0, 16)
  attrs.psu_count = clamp(Number(attrs.psu_count) || 0, 0, 8)

  if (!attrs.panel_layout || typeof attrs.panel_layout !== 'object') {
    attrs.panel_layout = {
      cols: 38,
      rows: 16,
      grid_scale: 4,
      front: { cols: 38, rows: 16, items: [] },
      rear: { cols: 38, rows: 16, items: [] },
    }
  }
  if (!Array.isArray(attrs.custom_attributes)) attrs.custom_attributes = []
}

export function defaultSecurityAttributes(
  formFactor: SecurityFormFactorU = 1,
): Record<string, unknown> {
  const slots = defaultSecurityIfaceSlots(4)
  const attrs: Record<string, unknown> = {
    chassis_height_u: formFactor,
    form_factor_u: formFactor,
    slot_count: 4,
    security_slots: slots,
    fan_count: 2,
    psu_count: 2,
    cpu_cores: 8,
    memory_gb: 32,
    disk_gb: 480,
    disk_count: 2,
    throughput_gbps: null,
    panel_layout: {
      cols: 38,
      rows: 16,
      grid_scale: 4,
      front: { cols: 38, rows: 16, items: [] },
      rear: { cols: 38, rows: 16, items: [] },
    },
    custom_attributes: [],
  }
  syncSecurityDerivedAttrs(attrs)
  return attrs
}

export function securitySlot10gRangeLabel(slot: SecurityIfaceSlotAttr): string {
  if (slot.ports_10g <= 0) return '—'
  return `slot${slot.index}-10G-(1-${slot.ports_10g})`
}

export function securitySlot1gRangeLabel(slot: SecurityIfaceSlotAttr): string {
  if (slot.ports_1g <= 0) return '—'
  return `slot${slot.index}-1G-(1-${slot.ports_1g})`
}
