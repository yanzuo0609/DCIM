/**
 * 服务器设备模型属性 — 硬件配置信息 / 接口属性 / 稳定端口 ID。
 *
 * 板载：BMC / IPMI / VGA / USB / LOM 1G
 * 灵活 IO 光口定义在 PCIE 插槽上（挡板 / 2 光口 / 4 光口），ID 为 pcie{n}-p{i}。
 * 面板按 19 英寸机架长高比绘制（482.6mm × 44.45mm/U）。
 */

import type { DesignSlotAttr, DesignSlotInterface } from '@/utils/designModelToNode'

export type ServerFormFactorU = 1 | 2 | 4
export type ServerSlotKind = 'onboard' | 'expansion'
export type ServerMemoryType = 'ddr4' | 'ddr5' | 'other'
export type ServerDiskSize = '2.5' | '3.5'
export type ServerDiskProto = 'sas_sata' | 'sas' | 'sata' | 'nvme'
export type ServerSsdIface = 'sata' | 'nvme' | 'sas' | 'm.2' | 'u.2' | 'other'
export type ServerSsdType = 'sata' | 'nvme' | 'sas' | 'mixed' | 'other'
export type ServerPsuRedundancy = '1+1' | '1+n' | 'other'
export type ServerFlexSpeed = '10ge' | '25ge'
export type ServerPortKind = 'bmc' | 'ipmi' | 'vga' | 'usb' | 'lom' | 'flex'
export type ServerPortFace = 'copper' | 'optical' | 'other'

/** 接口板卡插槽 */
export interface ServerIfaceSlotAttr {
  index: number
  kind: ServerSlotKind
  /** BMC 1Gbps RJ45 管理口 */
  bmc_count: number
  /** 独立 IPMI 接口（通常走 BMC，可另计） */
  ipmi_count: number
  /** VGA（兼容字段名 hdmi_count） */
  hdmi_count: number
  usb_count: number
  /** 灵活 IO 光口（扩展槽）或历史 10G */
  ports_10g: number
  /** 板载 LOM 1G 电口 */
  ports_1g: number
  port_start: number
}

export type ServerSlotNicType = '10g' | '1g' | 'none'

export interface ServerPortAttr {
  kind: ServerPortKind
  index: number
  id: string
  code: string
  port_type: string
  iface_type: ServerPortFace
  speed: string
  module: string
  connector: string
  fiber_mode: 'sm' | 'mm' | 'na'
  face: 'front' | 'rear'
  /** 灵活 IO 所在 PCIE 槽位（1-based） */
  slot_index?: number
}

/** PCIE 插槽：灵活 IO 光口定义在槽上 */
export interface ServerPcieSlotAttr {
  index: number
  /** 本槽光口数，0=挡板 */
  flex_ports: number
}

export interface ServerDriveGrid {
  rows: number
  cols: number
  vertical: boolean
  empty: boolean
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n))
}

function asInt(v: unknown, fallback: number) {
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}

export function isOnboardSlot(slot: Pick<ServerIfaceSlotAttr, 'index' | 'kind'>): boolean {
  return slot.kind === 'onboard' || slot.index === 1
}

export function serverSlotNamePrefix(slot: Pick<ServerIfaceSlotAttr, 'index' | 'kind'>): string {
  return isOnboardSlot(slot) ? '板载' : `Slot${slot.index}`
}

export function enforceSlotNicRules(slot: ServerIfaceSlotAttr): ServerIfaceSlotAttr {
  const kind: ServerSlotKind = slot.kind === 'onboard' || slot.index === 1 ? 'onboard' : 'expansion'
  let n10 = clamp(Number(slot.ports_10g) || 0, 0, 16)
  let n1 = clamp(Number(slot.ports_1g) || 0, 0, 16)
  let bmc = clamp(Number(slot.bmc_count) || 0, 0, 4)
  let ipmi = clamp(Number(slot.ipmi_count) || 0, 0, 4)
  let vga = clamp(Number(slot.hdmi_count) || 0, 0, 4)
  let usb = clamp(Number(slot.usb_count) || 0, 0, 8)

  if (kind === 'expansion') {
    if (n10 > 0 && n1 > 0) n1 = 0
    bmc = 0
    ipmi = 0
    vga = 0
    usb = 0
  }

  return {
    ...slot,
    kind,
    bmc_count: bmc,
    ports_10g: n10,
    ports_1g: n1,
    ipmi_count: ipmi,
    hdmi_count: vga,
    usb_count: usb,
  }
}

/** @deprecated 兼容旧名 */
export function enforceSingleNicType(slot: ServerIfaceSlotAttr): ServerIfaceSlotAttr {
  return enforceSlotNicRules(slot)
}

export function serverSlotNicType(
  slot: Pick<ServerIfaceSlotAttr, 'ports_10g' | 'ports_1g' | 'kind' | 'index'>,
): ServerSlotNicType {
  const n10 = clamp(Number(slot.ports_10g) || 0, 0, 16)
  const n1 = clamp(Number(slot.ports_1g) || 0, 0, 16)
  if (isOnboardSlot(slot)) {
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

export function diskFrontMaxForU(u: unknown): number {
  const ff = normalizeServerFormFactor(u)
  if (ff === 4) return 48
  if (ff === 2) return 24
  return 4
}

export function diskRearMaxForU(_u?: unknown): number {
  return 6
}

export const SERVER_HEIGHT_OPTIONS: { value: ServerFormFactorU; label: string }[] = [
  { value: 1, label: '1U' },
  { value: 2, label: '2U' },
  { value: 4, label: '4U' },
]

export const SERVER_MEMORY_TYPE_OPTIONS: { value: ServerMemoryType; label: string }[] = [
  { value: 'ddr4', label: 'DDR4' },
  { value: 'ddr5', label: 'DDR5' },
  { value: 'other', label: '其他' },
]

export const SERVER_DISK_SIZE_OPTIONS: { value: ServerDiskSize; label: string }[] = [
  { value: '2.5', label: '2.5 寸' },
  { value: '3.5', label: '3.5 寸' },
]

export const SERVER_DISK_PROTO_OPTIONS: { value: ServerDiskProto; label: string }[] = [
  { value: 'sas_sata', label: 'SAS/SATA' },
  { value: 'sas', label: 'SAS' },
  { value: 'sata', label: 'SATA' },
  { value: 'nvme', label: 'NVMe' },
]

export const SERVER_SSD_IFACE_OPTIONS: { value: ServerSsdIface; label: string }[] = [
  { value: 'sata', label: 'SATA' },
  { value: 'nvme', label: 'NVMe' },
  { value: 'm.2', label: 'M.2' },
  { value: 'u.2', label: 'U.2' },
  { value: 'sas', label: 'SAS' },
  { value: 'other', label: '其他' },
]

export const SERVER_SSD_TYPE_OPTIONS: { value: ServerSsdType; label: string }[] = [
  { value: 'sata', label: 'SATA SSD' },
  { value: 'nvme', label: 'NVMe SSD' },
  { value: 'sas', label: 'SAS SSD' },
  { value: 'mixed', label: '混合' },
  { value: 'other', label: '其他' },
]

export const SERVER_PSU_REDUNDANCY_OPTIONS: { value: ServerPsuRedundancy; label: string }[] = [
  { value: '1+1', label: '1+1 冗余' },
  { value: '1+n', label: '1+N 冗余' },
  { value: 'other', label: '其他' },
]

export const SERVER_FLEX_SPEED_OPTIONS: { value: ServerFlexSpeed; label: string }[] = [
  { value: '10ge', label: '10GE 光口' },
  { value: '25ge', label: '25GE 光口' },
]

export const SERVER_OS_OPTIONS: { value: string; label: string }[] = [
  { value: 'windows_server', label: 'Windows Server' },
  { value: 'rhel', label: 'RHEL' },
  { value: 'ubuntu', label: 'Ubuntu' },
  { value: 'centos', label: 'CentOS' },
  { value: 'esxi', label: 'VMware ESXi' },
  { value: 'other', label: '其他' },
]

export const SERVER_PORT_KIND_OPTIONS: { value: ServerPortKind; label: string }[] = [
  { value: 'bmc', label: 'BMC 管理口' },
  { value: 'ipmi', label: 'IPMI 接口' },
  { value: 'vga', label: 'VGA' },
  { value: 'usb', label: 'USB' },
  { value: 'lom', label: '板载 LOM' },
  { value: 'flex', label: '灵活 IO' },
]

export const SERVER_PORT_NS: Record<ServerPortKind, string> = {
  bmc: 'bmc',
  ipmi: 'ipmi',
  vga: 'vga',
  usb: 'usb',
  lom: 'lom',
  flex: 'flex',
}

/** 19 英寸机架实际尺寸：宽 482.6mm，1U=44.45mm，用于面板长高比 */
export const SERVER_RACK_WIDTH_MM = 482.6
export const SERVER_U_HEIGHT_MM = 44.45
export const SERVER_DEMO_WIDTH = 720

export const SERVER_DEMO = {
  width: SERVER_DEMO_WIDTH,
  aspect(u: ServerFormFactorU) {
    return `${SERVER_RACK_WIDTH_MM} / ${u * SERVER_U_HEIGHT_MM}`
  },
  heightFor(u: ServerFormFactorU, width = SERVER_DEMO_WIDTH) {
    return Math.max(44, Math.round((width * u * SERVER_U_HEIGHT_MM) / SERVER_RACK_WIDTH_MM))
  },
}

export const PCIE_FLEX_PORT_OPTIONS: { value: number; label: string }[] = [
  { value: 0, label: '挡板' },
  { value: 2, label: '2 光口' },
  { value: 4, label: '4 光口' },
]

export function pciePortId(slotIndex: number, portIndex: number) {
  return `pcie${Math.max(1, slotIndex)}-p${Math.max(0, portIndex)}`
}

export function pciePortCode(slotIndex: number, portIndex: number) {
  return `S${Math.max(1, slotIndex)}-${portIndex + 1}`
}

export function distributeFlexToPcie(max: number, flexCount: number, perCard = 2): ServerPcieSlotAttr[] {
  const n = clamp(max, 0, 16)
  let remain = clamp(flexCount, 0, 64)
  const slots: ServerPcieSlotAttr[] = []
  for (let i = 1; i <= n; i++) {
    const take = remain <= 0 ? 0 : Math.min(4, remain, perCard)
    slots.push({ index: i, flex_ports: take })
    remain -= take
  }
  if (remain > 0 && slots.length) {
    const last = slots[slots.length - 1]
    last.flex_ports = clamp(last.flex_ports + remain, 0, 4)
  }
  return slots
}

export function normalizePcieSlots(raw: unknown, max: number, flexFallback: number): ServerPcieSlotAttr[] {
  const n = clamp(max, 0, 16)
  if (!Array.isArray(raw) || !raw.length) return distributeFlexToPcie(n, flexFallback)
  const list: ServerPcieSlotAttr[] = []
  for (let i = 0; i < n; i++) {
    const src = raw[i] && typeof raw[i] === 'object' ? (raw[i] as Record<string, unknown>) : {}
    list.push({
      index: i + 1,
      flex_ports: clamp(asInt(src.flex_ports, 0), 0, 4),
    })
  }
  return list
}

export function readPcieSlots(attrs: Record<string, unknown> | null | undefined): ServerPcieSlotAttr[] {
  if (!attrs) return distributeFlexToPcie(2, 2)
  const max = clamp(asInt(attrs.pcie_slot_max, 2), 0, 16)
  return normalizePcieSlots(attrs.pcie_slots, max, asInt(attrs.flex_io_count, 2))
}

export function pcieFlexTotal(slots: ServerPcieSlotAttr[]) {
  return slots.reduce((sum, s) => sum + clamp(s.flex_ports, 0, 4), 0)
}

export function serverPortId(kind: ServerPortKind, portIndex: number) {
  return `${SERVER_PORT_NS[kind]}-p${Math.max(0, portIndex)}`
}

export function serverPortCode(kind: ServerPortKind, portIndex: number, flexSpeed: ServerFlexSpeed = '10ge') {
  const prefix =
    kind === 'bmc'
      ? 'BMC'
      : kind === 'ipmi'
        ? 'IPMI'
        : kind === 'vga'
          ? 'VGA'
          : kind === 'usb'
            ? 'USB'
            : kind === 'lom'
              ? 'LOM'
              : flexSpeed === '25ge'
                ? 'F25G'
                : 'F10G'
  return `${prefix}${portIndex + 1}`
}

export function serverPortKindLabel(kind: ServerPortKind) {
  return SERVER_PORT_KIND_OPTIONS.find((o) => o.value === kind)?.label || kind
}

function portSpecForKind(
  kind: ServerPortKind,
  flexSpeed: ServerFlexSpeed,
): Pick<ServerPortAttr, 'port_type' | 'iface_type' | 'speed' | 'module' | 'connector' | 'fiber_mode'> {
  if (kind === 'bmc' || kind === 'ipmi' || kind === 'lom') {
    return {
      port_type: kind === 'lom' ? '1g' : 'bmc',
      iface_type: 'copper',
      speed: '1GE',
      module: 'RJ45',
      connector: 'RJ45',
      fiber_mode: 'na',
    }
  }
  if (kind === 'flex') {
    const ge25 = flexSpeed === '25ge'
    return {
      port_type: ge25 ? '25g' : '10g',
      iface_type: 'optical',
      speed: ge25 ? '25GE' : '10GE',
      module: ge25 ? 'SFP28' : 'SFP+',
      connector: 'LC',
      fiber_mode: 'mm',
    }
  }
  if (kind === 'usb') {
    return {
      port_type: 'other',
      iface_type: 'other',
      speed: 'USB',
      module: 'USB',
      connector: 'USB',
      fiber_mode: 'na',
    }
  }
  return {
    port_type: 'other',
    iface_type: 'other',
    speed: 'VGA',
    module: 'VGA',
    connector: 'VGA',
    fiber_mode: 'na',
  }
}

export function listServerPorts(attrs: Record<string, unknown> | null | undefined): ServerPortAttr[] {
  const a = attrs || {}
  const flexSpeed = normalizeFlexSpeed(a.flex_io_speed)
  const counts: { kind: ServerPortKind; n: number; face: 'front' | 'rear' }[] = [
    { kind: 'bmc', n: clamp(asInt(a.bmc_ports, 1), 0, 4), face: 'rear' },
    { kind: 'ipmi', n: clamp(asInt(a.ipmi_iface_count, 0), 0, 4), face: 'rear' },
    { kind: 'vga', n: clamp(asInt(a.vga_count ?? a.hdmi_ports, 1), 0, 4), face: 'rear' },
    { kind: 'usb', n: clamp(asInt(a.usb_count ?? a.usb_ports, 2), 0, 8), face: 'rear' },
    { kind: 'lom', n: clamp(asInt(a.lom_1g_count, 2), 0, 8), face: 'rear' },
  ]
  const list: ServerPortAttr[] = []
  for (const c of counts) {
    for (let i = 0; i < c.n; i++) {
      list.push({
        kind: c.kind,
        index: i,
        id: serverPortId(c.kind, i),
        code: serverPortCode(c.kind, i, flexSpeed),
        face: c.face,
        ...portSpecForKind(c.kind, flexSpeed),
      })
    }
  }
  const pcieSlots = readPcieSlots(a)
  let flexSeq = 0
  for (const slot of pcieSlots) {
    for (let i = 0; i < slot.flex_ports; i++) {
      list.push({
        kind: 'flex',
        index: flexSeq,
        slot_index: slot.index,
        id: pciePortId(slot.index, i),
        code: pciePortCode(slot.index, i),
        face: 'rear',
        ...portSpecForKind('flex', flexSpeed),
      })
      flexSeq += 1
    }
  }
  return list
}

export function groupServerPorts(ports: ServerPortAttr[]) {
  const order: ServerPortKind[] = ['bmc', 'ipmi', 'vga', 'usb', 'lom']
  const groups = order
    .map((kind) => ({
      kind,
      label: serverPortKindLabel(kind),
      ports: ports.filter((p) => p.kind === kind),
    }))
    .filter((g) => g.ports.length)
  const flex = ports.filter((p) => p.kind === 'flex')
  const slotIds = [...new Set(flex.map((p) => p.slot_index || 0))].filter((n) => n > 0).sort((a, b) => a - b)
  for (const si of slotIds) {
    groups.push({
      kind: 'flex',
      label: `PCIE${si}`,
      ports: flex.filter((p) => p.slot_index === si),
    })
  }
  return groups
}

export function normalizeMemoryType(v: unknown): ServerMemoryType {
  const s = String(v || '').toLowerCase()
  if (s === 'ddr5') return 'ddr5'
  if (s === 'other') return 'other'
  return 'ddr4'
}

export function normalizeDiskSize(v: unknown, fallback: ServerDiskSize = '3.5'): ServerDiskSize {
  const s = String(v || '')
  if (s === '2.5' || s === '2.5inch' || s === 'sff') return '2.5'
  if (s === '3.5' || s === '3.5inch' || s === 'lff') return '3.5'
  return fallback
}

export function normalizeDiskProto(v: unknown): ServerDiskProto {
  const s = String(v || '').toLowerCase()
  if (s === 'sas' || s === 'sata' || s === 'nvme') return s
  return 'sas_sata'
}

export function normalizeSsdIface(v: unknown): ServerSsdIface {
  const s = String(v || '').toLowerCase()
  if (s === 'nvme' || s === 'sas' || s === 'm.2' || s === 'u.2' || s === 'other') return s as ServerSsdIface
  return 'sata'
}

export function normalizeSsdType(v: unknown): ServerSsdType {
  const s = String(v || '').toLowerCase()
  if (s === 'nvme' || s === 'sas' || s === 'mixed' || s === 'other') return s as ServerSsdType
  return 'sata'
}

export function normalizePsuRedundancy(v: unknown): ServerPsuRedundancy {
  const s = String(v || '')
  if (s === '1+n' || s === '1+N') return '1+n'
  if (s === 'other') return 'other'
  return '1+1'
}

export function normalizeFlexSpeed(v: unknown): ServerFlexSpeed {
  const s = String(v || '').toLowerCase()
  if (s === '25ge' || s === '25g' || s === '25') return '25ge'
  return '10ge'
}

export function normalizeOsSupport(v: unknown): string[] {
  if (Array.isArray(v)) return v.map((x) => String(x).trim()).filter(Boolean)
  if (typeof v === 'string' && v.trim()) {
    return v
      .split(/[,，\n]/)
      .map((s) => s.trim())
      .filter(Boolean)
  }
  return ['windows_server', 'rhel']
}

/** 前面板盘位网格：按 U 高与 2.5/3.5 寸尽量贴近常见机箱 */
export function frontDriveGrid(u: unknown, count: number, size: ServerDiskSize): ServerDriveGrid {
  const ff = normalizeServerFormFactor(u)
  const n = Math.max(0, Math.trunc(count) || 0)
  if (n <= 0) return { rows: 1, cols: 1, vertical: false, empty: true }
  if (ff === 1) {
    if (size === '2.5') return { rows: 1, cols: Math.min(10, n), vertical: n >= 8, empty: false }
    return { rows: 1, cols: Math.min(4, n), vertical: false, empty: false }
  }
  if (ff === 2) {
    if (size === '2.5') {
      if (n <= 12) return { rows: 1, cols: n, vertical: true, empty: false }
      const cols = Math.min(12, Math.ceil(n / 2))
      return { rows: 2, cols, vertical: true, empty: false }
    }
    const cols = n <= 4 ? n : 4
    return { rows: Math.min(3, Math.ceil(n / cols)), cols, vertical: false, empty: false }
  }
  if (size === '2.5') {
    const cols = n <= 24 ? 6 : 8
    return { rows: Math.min(8, Math.ceil(n / cols)), cols, vertical: false, empty: false }
  }
  const cols = n <= 12 ? 4 : 6
  return { rows: Math.min(8, Math.ceil(n / cols)), cols, vertical: false, empty: false }
}

export function rearDriveGrid(count: number, size: ServerDiskSize): ServerDriveGrid {
  const n = Math.max(0, Math.trunc(count) || 0)
  if (n <= 0) return { rows: 1, cols: 1, vertical: false, empty: true }
  if (n === 1) return { rows: 1, cols: 1, vertical: size === '2.5', empty: false }
  if (n === 2) return { rows: 2, cols: 1, vertical: false, empty: false }
  if (n <= 4) return { rows: 2, cols: 2, vertical: false, empty: false }
  return { rows: 2, cols: 3, vertical: false, empty: false }
}

export function defaultOnboardSlot(): ServerIfaceSlotAttr {
  return {
    index: 1,
    kind: 'onboard',
    bmc_count: 1,
    ipmi_count: 0,
    hdmi_count: 1,
    usb_count: 2,
    ports_10g: 0,
    ports_1g: 2,
    port_start: 1,
  }
}

export function defaultExpansionSlot(index: number): ServerIfaceSlotAttr {
  return {
    index,
    kind: 'expansion',
    bmc_count: 0,
    ipmi_count: 0,
    hdmi_count: 0,
    usb_count: 0,
    ports_10g: index === 2 ? 2 : 0,
    ports_1g: 0,
    port_start: 1,
  }
}

export function defaultServerIfaceSlots(slotCount = 2): ServerIfaceSlotAttr[] {
  const n = clamp(slotCount, 1, 16)
  const slots: ServerIfaceSlotAttr[] = [defaultOnboardSlot()]
  for (let i = 2; i <= n; i++) slots.push(defaultExpansionSlot(i))
  return renumberServerSlotPorts(slots)
}

export function effectiveServerSlotPortCount(slot: ServerIfaceSlotAttr): number {
  return (
    clamp(Number(slot.ports_10g) || 0, 0, 16) +
    clamp(Number(slot.ports_1g) || 0, 0, 16) +
    clamp(Number(slot.bmc_count) || 0, 0, 4) +
    clamp(Number(slot.ipmi_count) || 0, 0, 4) +
    clamp(Number(slot.hdmi_count) || 0, 0, 4) +
    clamp(Number(slot.usb_count) || 0, 0, 8)
  )
}

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
  const n10 = list.filter((x) => String(x.port_type) === '10g' || String(x.port_type) === '25g').length
  const n1 = list.filter((x) => String(x.port_type) === '1g').length
  return serverSlotNicPaletteLabel({
    index,
    kind: kind || (index === 1 ? 'onboard' : 'expansion'),
    ports_10g: n10,
    ports_1g: n1,
  })
}

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
      bmc_count: clamp(Number(s.bmc_count) || 0, 0, 4),
      ipmi_count: clamp(Number(s.ipmi_count) || 0, 0, 4),
      hdmi_count: clamp(Number(s.hdmi_count) || 0, 0, 4),
      usb_count: clamp(Number(s.usb_count) || 0, 0, 8),
      ports_10g: clamp(Number(s.ports_10g) || 0, 0, 16),
      ports_1g: clamp(Number(s.ports_1g) || 0, 0, 16),
      port_start: 1,
    })
  })
}

function readSlotBmcIpmi(src: Record<string, unknown>, kind: ServerSlotKind) {
  const rawIpmi = Number(src.ipmi_count)
  const rawBmc = Number(src.bmc_count)
  if (kind !== 'onboard') return { bmc: 0, ipmi: 0 }
  if (Number.isFinite(rawBmc)) {
    return {
      bmc: clamp(rawBmc || 0, 0, 4),
      ipmi: clamp(Number.isFinite(rawIpmi) ? rawIpmi : 0, 0, 4),
    }
  }
  // 旧模型 ipmi_count 即 BMC RJ45
  return {
    bmc: clamp(Number.isFinite(rawIpmi) ? rawIpmi : 1, 0, 4),
    ipmi: 0,
  }
}

export function normalizeServerIfaceSlots(raw: unknown, slotCount?: number): ServerIfaceSlotAttr[] {
  const want = clamp(slotCount ?? (Array.isArray(raw) ? raw.length : 2) ?? 2, 1, 16)
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
        ports10 = kind === 'onboard' ? 0 : 2
        ports1 = kind === 'onboard' ? 2 : 0
      }
    }
    const { bmc, ipmi } = readSlotBmcIpmi(src, kind)
    let vga = Number(src.hdmi_count ?? src.vga_count)
    let usb = Number(src.usb_count)
    if (kind === 'onboard') {
      if (!Number.isFinite(vga)) vga = 1
      if (!Number.isFinite(usb)) usb = 2
      if (!Number.isFinite(ports10)) ports10 = 0
      if (!Number.isFinite(ports1)) ports1 = 2
    } else {
      vga = 0
      usb = 0
      if (!Number.isFinite(ports10)) ports10 = index === 2 ? 2 : 0
      if (!Number.isFinite(ports1)) ports1 = 0
    }
    list.push({
      index,
      kind,
      bmc_count: kind === 'onboard' ? bmc : 0,
      ipmi_count: kind === 'onboard' ? ipmi : 0,
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
  if (!attrs) return defaultServerIfaceSlots(2)
  const count = Number(attrs.slot_count) || Number(attrs.card_slot_count) || 2
  if (Array.isArray(attrs.server_slots) && attrs.server_slots.length) {
    return normalizeServerIfaceSlots(attrs.server_slots, count)
  }
  return normalizeServerIfaceSlots(attrs.slots, count)
}

function pushIface(
  list: DesignSlotInterface[],
  port: ServerPortAttr,
): void {
  list.push({
    index: list.length + 1,
    port_type: port.port_type,
    local_label: port.code,
    local_info: `${port.id}`,
    peer_label: '',
    peer_info: '',
    id: port.id,
    code: port.code,
  })
}

/** 转为面板 DesignSlotAttr；灵活 IO 按 PCIE 槽拆分 */
export function serverIfaceSlotsToDesignSlots(
  slots: ServerIfaceSlotAttr[],
  attrs?: Record<string, unknown> | null,
): DesignSlotAttr[] {
  const ports = attrs ? listServerPorts(attrs) : null
  const onboard = slots.find((s) => isOnboardSlot(s)) || slots[0]
  const out: DesignSlotAttr[] = []
  if (onboard && ports) {
    const interfaces: DesignSlotInterface[] = []
    for (const p of ports.filter((x) => x.kind !== 'flex')) pushIface(interfaces, p)
    out.push({
      index: 1,
      type: interfaces.some((i) => i.port_type === '1g') ? 'nic_1g' : 'blank',
      port_count: interfaces.length,
      interfaces,
    })
    for (const slot of readPcieSlots(attrs)) {
      const interfacesPcie: DesignSlotInterface[] = []
      for (const p of ports.filter((x) => x.kind === 'flex' && x.slot_index === slot.index)) {
        pushIface(interfacesPcie, p)
      }
      out.push({
        index: out.length + 1,
        type: interfacesPcie.length ? 'nic_10g' : 'blank',
        port_count: interfacesPcie.length,
        interfaces: interfacesPcie,
      })
    }
    return out
  }
  return slots.map((raw) => {
    const s = enforceSlotNicRules(raw)
    const n10 = clamp(s.ports_10g, 0, 16)
    const n1 = clamp(s.ports_1g, 0, 16)
    const bmc = clamp(s.bmc_count, 0, 4)
    const ipmi = clamp(s.ipmi_count, 0, 4)
    if (n10 <= 0 && n1 <= 0 && !bmc && !ipmi && !s.hdmi_count && !s.usb_count) {
      return { index: s.index, type: 'blank', port_count: 0, interfaces: [] }
    }
    const interfaces: DesignSlotInterface[] = []
    const add = (kind: ServerPortKind, count: number, portType: string) => {
      for (let i = 0; i < count; i++) {
        const id = serverPortId(kind, i)
        const code = serverPortCode(kind, i)
        interfaces.push({
          index: interfaces.length + 1,
          port_type: portType,
          local_label: code,
          local_info: id,
          peer_label: '',
          peer_info: '',
          id,
          code,
        })
      }
    }
    if (isOnboardSlot(s)) {
      add('bmc', bmc, 'bmc')
      add('ipmi', ipmi, 'bmc')
      add('lom', n1, '1g')
      add('vga', s.hdmi_count, 'other')
      add('usb', s.usb_count, 'other')
    } else {
      add('flex', n10, '10g')
    }
    const type = n10 > 0 ? 'nic_10g' : n1 > 0 || isOnboardSlot(s) ? 'nic_1g' : 'blank'
    return {
      index: s.index,
      type,
      port_count: interfaces.length,
      interfaces,
    }
  })
}

function applyCountsToSlots(
  attrs: Record<string, unknown>,
  slots: ServerIfaceSlotAttr[],
): ServerIfaceSlotAttr[] {
  const bmc = clamp(asInt(attrs.bmc_ports, 1), 0, 4)
  const ipmi = clamp(asInt(attrs.ipmi_iface_count, 0), 0, 4)
  const vga = clamp(asInt(attrs.vga_count ?? attrs.hdmi_ports, 1), 0, 4)
  const usb = clamp(asInt(attrs.usb_count ?? attrs.usb_ports, 2), 0, 8)
  const lom = clamp(asInt(attrs.lom_1g_count, 2), 0, 8)
  const flex = clamp(asInt(attrs.flex_io_count, 2), 0, 16)
  const want = Math.max(flex > 0 ? 2 : 1, 1)
  let next = slots.slice()
  if (!next.length) next = defaultServerIfaceSlots(want)
  while (next.length < want) next.push(defaultExpansionSlot(next.length + 1))
  if (next.length > Math.max(want, 2)) next = next.slice(0, Math.max(want, 2))
  next = next.map((s, i) => {
    const index = i + 1
    if (index === 1) {
      return enforceSlotNicRules({
        ...s,
        index,
        kind: 'onboard',
        bmc_count: bmc,
        ipmi_count: ipmi,
        hdmi_count: vga,
        usb_count: usb,
        ports_1g: lom,
        ports_10g: 0,
      })
    }
    return enforceSlotNicRules({
      ...s,
      index,
      kind: 'expansion',
      bmc_count: 0,
      ipmi_count: 0,
      hdmi_count: 0,
      usb_count: 0,
      ports_10g: index === 2 ? flex : 0,
      ports_1g: 0,
    })
  })
  return renumberServerSlotPorts(next)
}

export function syncServerDerivedAttrs(attrs: Record<string, unknown>): void {
  const u = normalizeServerFormFactor(attrs.form_factor_u)
  attrs.form_factor_u = u
  const frontMax = diskFrontMaxForU(u)
  const rearMax = diskRearMaxForU(u)
  attrs.disk_front_count = clamp(asInt(attrs.disk_front_count, u === 1 ? 4 : u === 2 ? 12 : 24), 0, frontMax)
  attrs.disk_rear_count = clamp(asInt(attrs.disk_rear_count, 0), 0, rearMax)
  attrs.disk_rear_max = rearMax
  attrs.disk_front_max = frontMax
  attrs.disk_front_size = normalizeDiskSize(attrs.disk_front_size, u === 1 ? '3.5' : '3.5')
  attrs.disk_rear_size = normalizeDiskSize(attrs.disk_rear_size, '2.5')
  attrs.disk_front_proto = normalizeDiskProto(attrs.disk_front_proto)
  attrs.disk_rear_proto = normalizeDiskProto(attrs.disk_rear_proto)

  attrs.memory_type = normalizeMemoryType(attrs.memory_type)
  const moduleGb = clamp(asInt(attrs.memory_module_gb, 16), 1, 1024)
  attrs.memory_module_gb = moduleGb
  const modules = clamp(asInt(attrs.memory_modules, 8), 1, 64)
  attrs.memory_modules = modules
  let total = Number(attrs.memory_gb)
  if (!Number.isFinite(total) || total <= 0) total = moduleGb * modules
  attrs.memory_gb = clamp(total, 1, 1_048_576)

  attrs.cpu_sockets = clamp(asInt(attrs.cpu_sockets, 2), 1, 8)
  attrs.cpu_cores_per_socket = clamp(asInt(attrs.cpu_cores_per_socket, 16), 1, 128)
  attrs.pcie_slot_max = clamp(asInt(attrs.pcie_slot_max, u === 1 ? 2 : u === 2 ? 6 : 8), 0, 16)

  attrs.ssd_internal_count = clamp(asInt(attrs.ssd_internal_count, 0), 0, 16)
  attrs.ssd_internal_iface = normalizeSsdIface(attrs.ssd_internal_iface)
  attrs.ssd_max_count = clamp(asInt(attrs.ssd_max_count, Math.max(2, asInt(attrs.ssd_internal_count, 0))), 0, 64)
  attrs.ssd_max_type = normalizeSsdType(attrs.ssd_max_type)

  attrs.psu_watt = clamp(asInt(attrs.psu_watt, 800), 100, 5000)
  attrs.psu_redundancy = normalizePsuRedundancy(attrs.psu_redundancy)
  if (attrs.psu_count == null) {
    attrs.psu_count = attrs.psu_redundancy === '1+n' ? clamp(asInt(attrs.psu_redundant_n, 1) + 1, 2, 8) : 2
  }
  attrs.psu_count = clamp(asInt(attrs.psu_count, 2), 0, 8)
  attrs.psu_redundant = attrs.psu_redundancy !== 'other' && asInt(attrs.psu_count, 2) >= 2
  attrs.psu_redundant_n = clamp(asInt(attrs.psu_redundant_n, Math.max(1, asInt(attrs.psu_count, 2) - 1)), 1, 7)
  if (attrs.fan_count == null) attrs.fan_count = u === 1 ? 4 : u === 2 ? 6 : 8
  attrs.fan_count = clamp(asInt(attrs.fan_count, 0), 0, 16)

  attrs.os_support = normalizeOsSupport(attrs.os_support)
  attrs.os_support_custom = String(attrs.os_support_custom || '')

  const legacySlots = normalizeServerIfaceSlots(attrs.server_slots ?? attrs.slots, Number(attrs.slot_count) || 2)
  const migrated = attrs.lom_1g_count != null || attrs.flex_io_count != null || attrs.vga_count != null
  if (!migrated) {
    const onboard = legacySlots.find((s) => isOnboardSlot(s)) || legacySlots[0]
    const flexSlot = legacySlots.find((s) => !isOnboardSlot(s))
    attrs.bmc_ports = clamp(Number(onboard?.bmc_count || onboard?.ipmi_count) || 1, 0, 4)
    attrs.ipmi_iface_count = clamp(Number(onboard?.bmc_count != null ? onboard.ipmi_count : 0) || 0, 0, 4)
    attrs.vga_count = clamp(Number(onboard?.hdmi_count) || 1, 0, 4)
    attrs.usb_count = clamp(Number(onboard?.usb_count) || 2, 0, 8)
    attrs.lom_1g_count = clamp(Number(onboard?.ports_1g) || 2, 0, 8)
    attrs.flex_io_count = clamp(Number(flexSlot?.ports_10g || onboard?.ports_10g) || 2, 0, 16)
    attrs.flex_io_speed = normalizeFlexSpeed(attrs.flex_io_speed)
  }

  attrs.bmc_ports = clamp(asInt(attrs.bmc_ports, 1), 0, 4)
  attrs.ipmi_iface_count = clamp(asInt(attrs.ipmi_iface_count, 0), 0, 4)
  attrs.vga_count = clamp(asInt(attrs.vga_count ?? attrs.hdmi_ports, 1), 0, 4)
  attrs.usb_count = clamp(asInt(attrs.usb_count ?? attrs.usb_ports, 2), 0, 8)
  attrs.usb_ports = attrs.usb_count
  attrs.hdmi_ports = attrs.vga_count
  attrs.lom_1g_count = clamp(asInt(attrs.lom_1g_count, 2), 0, 8)
  attrs.flex_io_speed = normalizeFlexSpeed(attrs.flex_io_speed)
  const pcieSlots = normalizePcieSlots(attrs.pcie_slots, Number(attrs.pcie_slot_max) || 2, asInt(attrs.flex_io_count, 2))
  attrs.pcie_slots = pcieSlots
  attrs.flex_io_count = pcieFlexTotal(pcieSlots)

  const slots = applyCountsToSlots(attrs, legacySlots)
  attrs.slot_count = slots.length
  attrs.server_slots = slots
  attrs.slots = serverIfaceSlotsToDesignSlots(slots, attrs)
  attrs.server_ports = listServerPorts(attrs)

  if (attrs.panel_style_mode !== 'custom' && attrs.panel_style_mode !== 'generated') {
    attrs.panel_style_mode = attrs.panel_style_image ? 'custom' : 'generated'
  }
}

export function defaultServerAttributes(formFactor: ServerFormFactorU = 1): Record<string, unknown> {
  const frontMax = diskFrontMaxForU(formFactor)
  const slots = defaultServerIfaceSlots(2)
  const moduleGb = 16
  const modules = 8
  const attrs: Record<string, unknown> = {
    form_factor_u: formFactor,
    cpu_sockets: 2,
    cpu_cores_per_socket: 16,
    memory_type: 'ddr4',
    memory_module_gb: moduleGb,
    memory_modules: modules,
    memory_gb: moduleGb * modules,
    pcie_slot_max: formFactor === 1 ? 2 : formFactor === 2 ? 6 : 8,
    pcie_slots: distributeFlexToPcie(formFactor === 1 ? 2 : formFactor === 2 ? 6 : 8, 2),
    slot_count: 2,
    server_slots: slots,
    disk_front_count: formFactor === 1 ? 4 : formFactor === 2 ? 12 : 24,
    disk_rear_count: formFactor === 1 ? 0 : 2,
    disk_front_size: '3.5',
    disk_rear_size: '2.5',
    disk_front_proto: 'sas_sata',
    disk_rear_proto: 'sas_sata',
    disk_front_max: frontMax,
    disk_rear_max: 6,
    ssd_internal_count: 0,
    ssd_internal_iface: 'sata',
    ssd_max_count: 2,
    ssd_max_type: 'sata',
    fan_count: formFactor === 1 ? 4 : formFactor === 2 ? 6 : 8,
    psu_count: 2,
    psu_watt: 800,
    psu_redundancy: '1+1',
    psu_redundant: true,
    psu_redundant_n: 1,
    bmc_ports: 1,
    ipmi_iface_count: 0,
    vga_count: 1,
    usb_count: 2,
    usb_ports: 2,
    hdmi_ports: 1,
    lom_1g_count: 2,
    flex_io_count: 2,
    flex_io_speed: '10ge',
    os_support: ['windows_server', 'rhel'],
    os_support_custom: '',
    downlink_media: 'AUTO',
    nic_media: 'AUTO',
    panel_style_image: null,
    panel_style_image_rear: null,
    panel_style_mode: 'generated',
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
  if (s.bmc_count > 0) parts.push(`BMC1–BMC${s.bmc_count}（bmc-p0–bmc-p${s.bmc_count - 1}）`)
  if (s.ipmi_count > 0) parts.push(`IPMI1–IPMI${s.ipmi_count}`)
  if (s.ports_10g > 0) {
    parts.push(s.ports_10g === 1 ? `${prefix}:F10G1` : `${prefix}:F10G-(1-${s.ports_10g})`)
  }
  if (s.ports_1g > 0) {
    parts.push(s.ports_1g === 1 ? `LOM1` : `LOM1–LOM${s.ports_1g}（lom-p0–lom-p${s.ports_1g - 1}）`)
  }
  if (isOnboardSlot(s)) {
    if (s.hdmi_count > 0) parts.push(`VGA1–VGA${s.hdmi_count}`)
    if (s.usb_count > 0) parts.push(`USB1–USB${s.usb_count}`)
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
  if (next.pcie_slot_max == null) next.pcie_slot_max = formFactor === 1 ? 2 : formFactor === 2 ? 6 : 8
  if (next.fan_count == null) next.fan_count = formFactor === 1 ? 4 : formFactor === 2 ? 6 : 8
  if (formFactor === 1 && Number(next.disk_front_count) > 4) next.disk_front_count = 4
  if (formFactor >= 2 && Number(next.disk_front_count) < 8) {
    next.disk_front_count = formFactor === 2 ? 12 : 24
  }
  syncServerDerivedAttrs(next)
  return next
}
