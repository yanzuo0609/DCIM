/**
 * 服务器设备模型属性 — 对齐 docs/设备属性参数定义.xmind
 * 面板样式仍走现有 layout 引擎，本文件定义基础/配置/接口 Slot。
 *
 * Slot1 固定为板载：可同时配置 IPMI / VGA / USB / 10G / 1G
 * Slot2+ 为扩展卡：仅网口（10G 或 1G 二选一），无管理口设置
 */

import type { DesignSlotAttr, DesignSlotInterface } from '@/utils/designModelToNode'

export type ServerFormFactorU = 1 | 2 | 4

export type ServerSlotKind = 'onboard' | 'expansion'

/** 接口板卡插槽 */
export interface ServerIfaceSlotAttr {
  index: number
  /** onboard=板载（固定 Slot1）；expansion=扩展卡 */
  kind: ServerSlotKind
  ipmi_count: number
  /** VGA（兼容字段名 hdmi_count） */
  hdmi_count: number
  usb_count: number
  /** 10G 光口；扩展槽与 ports_1g 互斥，板载可同时有 */
  ports_10g: number
  /** 1G 电口；扩展槽与 ports_10g 互斥，板载可同时有 */
  ports_1g: number
  /** 本槽接口自动编号起点 */
  port_start: number
}

export type ServerSlotNicType = '10g' | '1g' | 'none'

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n))
}

export function isOnboardSlot(slot: Pick<ServerIfaceSlotAttr, 'index' | 'kind'>): boolean {
  return slot.kind === 'onboard' || slot.index === 1
}

/** 编号前缀：板载 / SlotN */
export function serverSlotNamePrefix(slot: Pick<ServerIfaceSlotAttr, 'index' | 'kind'>): string {
  return isOnboardSlot(slot) ? '板载' : `Slot${slot.index}`
}

/** 扩展槽：同一 Slot 只保留一种网口；板载允许 10G+1G 共存 */
export function enforceSlotNicRules(slot: ServerIfaceSlotAttr): ServerIfaceSlotAttr {
  const kind: ServerSlotKind = slot.kind === 'onboard' || slot.index === 1 ? 'onboard' : 'expansion'
  let n10 = clamp(Number(slot.ports_10g) || 0, 0, 16)
  let n1 = clamp(Number(slot.ports_1g) || 0, 0, 16)
  let ipmi = clamp(Number(slot.ipmi_count) || 0, 0, 4)
  let vga = clamp(Number(slot.hdmi_count) || 0, 0, 4)
  let usb = clamp(Number(slot.usb_count) || 0, 0, 8)

  if (kind === 'expansion') {
    if (n10 > 0 && n1 > 0) n1 = 0
    ipmi = 0
    vga = 0
    usb = 0
  }

  return {
    ...slot,
    kind,
    ports_10g: n10,
    ports_1g: n1,
    ipmi_count: ipmi,
    hdmi_count: vga,
    usb_count: usb,
  }
}

/** @deprecated 兼容旧名：仅对扩展槽生效的互斥 */
export function enforceSingleNicType(slot: ServerIfaceSlotAttr): ServerIfaceSlotAttr {
  return enforceSlotNicRules(slot)
}

export function serverSlotNicType(slot: Pick<ServerIfaceSlotAttr, 'ports_10g' | 'ports_1g' | 'kind' | 'index'>): ServerSlotNicType {
  const n10 = clamp(Number(slot.ports_10g) || 0, 0, 16)
  const n1 = clamp(Number(slot.ports_1g) || 0, 0, 16)
  if (isOnboardSlot(slot)) {
    // 板载可双类型，选择器仅用于扩展槽；此处返回主导类型供展示
    if (n10 > 0 && n1 <= 0) return '10g'
    if (n1 > 0 && n10 <= 0) return '1g'
    if (n10 > 0) return '10g'
    if (n1 > 0) return '1g'
    return 'none'
  }
  if (n10 > 0) return '10g'
  if (n1 > 0) return '1g'
  return 'none'
}

export function applyServerSlotNicType(
  slot: ServerIfaceSlotAttr,
  type: ServerSlotNicType,
  count?: number,
): ServerIfaceSlotAttr {
  const n = clamp(count ?? (type === 'none' ? 0 : Math.max(slot.ports_10g, slot.ports_1g, 2)), 0, 16)
  if (isOnboardSlot(slot)) {
    // 板载不用此切换；若调用则只改对应侧
    if (type === '10g') return enforceSlotNicRules({ ...slot, ports_10g: Math.max(1, n || 2) })
    if (type === '1g') return enforceSlotNicRules({ ...slot, ports_1g: Math.max(1, n || 2) })
    return enforceSlotNicRules({ ...slot, ports_10g: 0, ports_1g: 0 })
  }
  if (type === '10g') return enforceSlotNicRules({ ...slot, ports_10g: Math.max(1, n || 2), ports_1g: 0 })
  if (type === '1g') return enforceSlotNicRules({ ...slot, ports_10g: 0, ports_1g: Math.max(1, n || 2) })
  return enforceSlotNicRules({ ...slot, ports_10g: 0, ports_1g: 0 })
}

export function normalizeServerFormFactor(u: unknown): ServerFormFactorU {
  const n = Number(u)
  if (n >= 4) return 4
  if (n >= 2) return 2
  return 1
}

/** 前面板磁盘插槽上限：1U≤4 / 2U≤24 / 4U≤48 */
export function diskFrontMaxForU(u: unknown): number {
  const ff = normalizeServerFormFactor(u)
  if (ff === 4) return 48
  if (ff === 2) return 24
  return 4
}

/** 后面板磁盘插槽上限：一律 ≤6 */
export function diskRearMaxForU(_u?: unknown): number {
  return 6
}

export const SERVER_HEIGHT_OPTIONS: { value: ServerFormFactorU; label: string }[] = [
  { value: 1, label: '1U' },
  { value: 2, label: '2U' },
  { value: 4, label: '4U' },
]

export function defaultOnboardSlot(): ServerIfaceSlotAttr {
  return {
    index: 1,
    kind: 'onboard',
    ipmi_count: 1,
    hdmi_count: 1,
    usb_count: 2,
    ports_10g: 2,
    ports_1g: 2,
    port_start: 1,
  }
}

export function defaultExpansionSlot(index: number): ServerIfaceSlotAttr {
  const use10g = index % 2 === 0
  return {
    index,
    kind: 'expansion',
    ipmi_count: 0,
    hdmi_count: 0,
    usb_count: 0,
    ports_10g: use10g ? 2 : 0,
    ports_1g: use10g ? 0 : 2,
    port_start: 1,
  }
}

export function defaultServerIfaceSlots(slotCount = 3): ServerIfaceSlotAttr[] {
  const n = clamp(slotCount, 1, 16)
  const slots: ServerIfaceSlotAttr[] = [defaultOnboardSlot()]
  for (let i = 2; i <= n; i++) slots.push(defaultExpansionSlot(i))
  return renumberServerSlotPorts(slots)
}

export function effectiveServerSlotPortCount(slot: ServerIfaceSlotAttr): number {
  return (
    clamp(Number(slot.ports_10g) || 0, 0, 16) +
    clamp(Number(slot.ports_1g) || 0, 0, 16) +
    clamp(Number(slot.ipmi_count) || 0, 0, 4) +
    clamp(Number(slot.hdmi_count) || 0, 0, 4) +
    clamp(Number(slot.usb_count) || 0, 0, 8)
  )
}

/** 面板组件栏标签 */
export function serverSlotNicPaletteLabel(
  slot: Pick<ServerIfaceSlotAttr, 'index' | 'ports_10g' | 'ports_1g'> & { kind?: ServerSlotKind },
): string {
  const prefix = serverSlotNamePrefix({
    index: slot.index,
    kind: slot.kind || (slot.index === 1 ? 'onboard' : 'expansion'),
  })
  const n10 = clamp(Number(slot.ports_10g) || 0, 0, 16)
  const n1 = clamp(Number(slot.ports_1g) || 0, 0, 16)
  if (slot.index === 1 || slot.kind === 'onboard') {
    const parts: string[] = []
    if (n10 > 0) parts.push(`10G×${n10}`)
    if (n1 > 0) parts.push(`1G×${n1}`)
    if (!parts.length) return `${prefix}:空白`
    return `${prefix}:${parts.join('+')}`
  }
  if (n10 > 0) return `${prefix}:10G×${n10}`
  if (n1 > 0) return `${prefix}:1G×${n1}`
  return `${prefix}:空白`
}

export function serverSlotLabelFromInterfaces(
  index: number,
  interfaces: { port_type?: string }[] | undefined,
  kind?: ServerSlotKind,
): string {
  const list = Array.isArray(interfaces) ? interfaces : []
  const n10 = list.filter((x) => String(x.port_type) === '10g').length
  const n1 = list.filter((x) => String(x.port_type) === '1g').length
  return serverSlotNicPaletteLabel({
    index,
    kind: kind || (index === 1 ? 'onboard' : 'expansion'),
    ports_10g: n10,
    ports_1g: n1,
  })
}

/** 接口显示编号：板载:10G-1 / Slot2:1G-1 / 板载:IPMI-1 */
export function serverPortLocalLabel(
  slot: Pick<ServerIfaceSlotAttr, 'index' | 'kind'>,
  portTag: string,
  portNum: number,
): string {
  return `${serverSlotNamePrefix(slot)}:${portTag}-${portNum}`
}

export function renumberServerSlotPorts(slots: ServerIfaceSlotAttr[]): ServerIfaceSlotAttr[] {
  return slots.map((s, i) => {
    const index = i + 1
    const kind: ServerSlotKind = index === 1 ? 'onboard' : 'expansion'
    return enforceSlotNicRules({
      ...s,
      index,
      kind,
      ipmi_count: clamp(Number(s.ipmi_count) || 0, 0, 4),
      hdmi_count: clamp(Number(s.hdmi_count) || 0, 0, 4),
      usb_count: clamp(Number(s.usb_count) || 0, 0, 8),
      ports_10g: clamp(Number(s.ports_10g) || 0, 0, 16),
      ports_1g: clamp(Number(s.ports_1g) || 0, 0, 16),
      port_start: 1,
    })
  })
}

export function normalizeServerIfaceSlots(raw: unknown, slotCount?: number): ServerIfaceSlotAttr[] {
  const want = clamp(slotCount ?? (Array.isArray(raw) ? raw.length : 3) ?? 3, 1, 16)
  if (!Array.isArray(raw) || !raw.length) return defaultServerIfaceSlots(want)
  const list: ServerIfaceSlotAttr[] = []
  for (let i = 0; i < want; i++) {
    const src = (raw[i] && typeof raw[i] === 'object' ? raw[i] : {}) as Record<string, unknown>
    const index = i + 1
    const kind: ServerSlotKind = index === 1 ? 'onboard' : 'expansion'
    const legacyType = String(src.type || '')
    let ports10 = Number(src.ports_10g)
    let ports1 = Number(src.ports_1g)
    if (!Number.isFinite(ports10) && !Number.isFinite(ports1) && legacyType) {
      const pc = clamp(Number(src.port_count) || 2, 0, 16)
      if (legacyType === 'nic_10g') {
        ports10 = pc
        ports1 = 0
      } else if (legacyType === 'nic_1g') {
        ports10 = 0
        ports1 = pc
      } else if (legacyType === 'blank' || legacyType === 'raid') {
        ports10 = 0
        ports1 = 0
      } else {
        ports10 = kind === 'onboard' ? 2 : 2
        ports1 = kind === 'onboard' ? 2 : 0
      }
    }
    // 板载缺省补管理口
    let ipmi = Number(src.ipmi_count)
    let vga = Number(src.hdmi_count ?? src.vga_count)
    let usb = Number(src.usb_count)
    if (kind === 'onboard') {
      if (!Number.isFinite(ipmi)) ipmi = 1
      if (!Number.isFinite(vga)) vga = 1
      if (!Number.isFinite(usb)) usb = 2
      if (!Number.isFinite(ports10)) ports10 = 2
      if (!Number.isFinite(ports1)) ports1 = 2
    } else {
      ipmi = 0
      vga = 0
      usb = 0
      if (!Number.isFinite(ports10)) ports10 = 2
      if (!Number.isFinite(ports1)) ports1 = 0
    }
    list.push({
      index,
      kind,
      ipmi_count: ipmi || 0,
      hdmi_count: vga || 0,
      usb_count: usb || 0,
      ports_10g: ports10 || 0,
      ports_1g: ports1 || 0,
      port_start: 1,
    })
  }
  return renumberServerSlotPorts(list)
}

export function readServerIfaceSlots(attrs: Record<string, unknown> | null | undefined): ServerIfaceSlotAttr[] {
  if (!attrs) return defaultServerIfaceSlots(3)
  const count = Number(attrs.slot_count) || Number(attrs.card_slot_count) || 3
  if (Array.isArray(attrs.server_slots) && attrs.server_slots.length) {
    return normalizeServerIfaceSlots(attrs.server_slots, count)
  }
  return normalizeServerIfaceSlots(attrs.slots, count)
}

/** 转为面板 DesignSlotAttr；板载可含 10G+1G，扩展仅一种 */
export function serverIfaceSlotsToDesignSlots(slots: ServerIfaceSlotAttr[]): DesignSlotAttr[] {
  return slots.map((raw) => {
    const s = enforceSlotNicRules(raw)
    const n10 = clamp(s.ports_10g, 0, 16)
    const n1 = clamp(s.ports_1g, 0, 16)
    if (n10 <= 0 && n1 <= 0 && !s.ipmi_count && !s.hdmi_count && !s.usb_count) {
      return { index: s.index, type: 'blank', port_count: 0, interfaces: [] }
    }
    const interfaces: DesignSlotInterface[] = []
    let idx = 1
    for (let i = 0; i < n10; i++) {
      interfaces.push({
        index: idx++,
        port_type: '10g',
        local_label: serverPortLocalLabel(s, '10G', i + 1),
        local_info: '',
        peer_label: '',
        peer_info: '',
      })
    }
    for (let i = 0; i < n1; i++) {
      interfaces.push({
        index: idx++,
        port_type: '1g',
        local_label: serverPortLocalLabel(s, '1G', i + 1),
        local_info: '',
        peer_label: '',
        peer_info: '',
      })
    }
    const type = n10 > 0 ? 'nic_10g' : n1 > 0 ? 'nic_1g' : 'blank'
    return {
      index: s.index,
      type,
      port_count: interfaces.length,
      interfaces,
    }
  })
}

export function syncServerDerivedAttrs(attrs: Record<string, unknown>): void {
  const u = normalizeServerFormFactor(attrs.form_factor_u)
  attrs.form_factor_u = u
  const frontMax = diskFrontMaxForU(u)
  const rearMax = diskRearMaxForU(u)
  attrs.disk_front_count = clamp(Number(attrs.disk_front_count) || 0, 0, frontMax)
  attrs.disk_rear_count = clamp(Number(attrs.disk_rear_count) || 0, 0, rearMax)
  attrs.disk_rear_max = rearMax
  attrs.disk_front_max = frontMax

  const count = clamp(Number(attrs.slot_count) || 3, 1, 16)
  attrs.slot_count = count
  const slots = normalizeServerIfaceSlots(attrs.server_slots ?? attrs.slots, count)
  attrs.server_slots = slots
  attrs.slots = serverIfaceSlotsToDesignSlots(slots)

  const moduleGb = clamp(Number(attrs.memory_module_gb) || 16, 1, 1024)
  attrs.memory_module_gb = moduleGb
  let total = Number(attrs.memory_gb)
  if (!Number.isFinite(total) || total <= 0) {
    const modules = clamp(Number(attrs.memory_modules) || 8, 1, 64)
    total = moduleGb * modules
  }
  attrs.memory_gb = clamp(total, 1, 1_048_576)

  if (attrs.fan_count == null) attrs.fan_count = u === 1 ? 4 : u === 2 ? 6 : 8
  if (attrs.psu_count == null) attrs.psu_count = 2
  attrs.fan_count = clamp(Number(attrs.fan_count) || 0, 0, 16)
  attrs.psu_count = clamp(Number(attrs.psu_count) || 0, 0, 8)

  const onboard = slots.find((s) => isOnboardSlot(s)) || slots[0]
  attrs.bmc_ports = clamp(Number(onboard?.ipmi_count) || 0, 0, 4)
  attrs.usb_ports = clamp(Number(onboard?.usb_count) || 0, 0, 8)
  attrs.hdmi_ports = clamp(Number(onboard?.hdmi_count) || 0, 0, 4)
}

/** 完整默认 attributes（按高度） */
export function defaultServerAttributes(formFactor: ServerFormFactorU = 1): Record<string, unknown> {
  const frontMax = diskFrontMaxForU(formFactor)
  const slots = defaultServerIfaceSlots(3)
  const moduleGb = 16
  const modules = 8
  const attrs: Record<string, unknown> = {
    form_factor_u: formFactor,
    cpu_sockets: 2,
    cpu_cores_per_socket: 16,
    memory_module_gb: moduleGb,
    memory_modules: modules,
    memory_gb: moduleGb * modules,
    slot_count: 3,
    server_slots: slots,
    slots: serverIfaceSlotsToDesignSlots(slots),
    disk_front_count: Math.min(4, frontMax),
    disk_rear_count: 0,
    disk_front_max: frontMax,
    disk_rear_max: 6,
    fan_count: formFactor === 1 ? 4 : formFactor === 2 ? 6 : 8,
    psu_count: 2,
    bmc_ports: 1,
    usb_ports: 2,
    hdmi_ports: 1,
    /** 可选：业务口默认介质（AUTO=按口类型推导） */
    downlink_media: 'AUTO',
    nic_media: 'AUTO',
    panel_layout: {
      cols: 38,
      rows: 16,
      grid_scale: 4,
      front: { cols: 38, rows: 16, items: [] },
      rear: { cols: 38, rows: 16, items: [] },
    },
    custom_attributes: [],
  }
  syncServerDerivedAttrs(attrs)
  return attrs
}

export function serverSlotPortRangeLabel(slot: ServerIfaceSlotAttr): string {
  const s = enforceSlotNicRules(slot)
  const prefix = serverSlotNamePrefix(s)
  const parts: string[] = []
  if (s.ports_10g > 0) {
    parts.push(s.ports_10g === 1 ? `${prefix}:10G-1` : `${prefix}:10G-(1-${s.ports_10g})`)
  }
  if (s.ports_1g > 0) {
    parts.push(s.ports_1g === 1 ? `${prefix}:1G-1` : `${prefix}:1G-(1-${s.ports_1g})`)
  }
  if (isOnboardSlot(s)) {
    if (s.ipmi_count > 0) parts.push(`${prefix}:IPMI-(1-${s.ipmi_count})`)
    if (s.hdmi_count > 0) parts.push(`${prefix}:VGA-(1-${s.hdmi_count})`)
    if (s.usb_count > 0) parts.push(`${prefix}:USB-(1-${s.usb_count})`)
  }
  return parts.length ? parts.join(' · ') : '—'
}

export function applyServerHeightDefaults(
  attrs: Record<string, unknown>,
  formFactor: ServerFormFactorU,
): Record<string, unknown> {
  const next = { ...attrs }
  next.form_factor_u = formFactor
  const frontMax = diskFrontMaxForU(formFactor)
  next.disk_front_max = frontMax
  next.disk_rear_max = 6
  if (Number(next.disk_front_count) > frontMax) next.disk_front_count = frontMax
  if (Number(next.disk_rear_count) > 6) next.disk_rear_count = 6
  syncServerDerivedAttrs(next)
  return next
}
