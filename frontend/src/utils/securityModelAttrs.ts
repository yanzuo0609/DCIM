/**
 * 安全设备模型属性 — 对齐 docs/设备属性参数定义.xmind
 * 面板样式仍走现有 securityFrontPanel，本文件定义基础/接口 Slot。
 */

import type { SecurityZoneInput } from '@/utils/securityFrontPanel'

export type SecurityDeviceType =
  | 'firewall'
  | 'ips'
  | 'ids'
  | 'vpn'
  | 'optical_gate'
  | 'host_audit'
  | 'database_audit'
  | 'net_audit'
  | 'ddos'
  | 'crypto'

export interface SecurityDeviceProfile {
  label: string
  shortLabel: string
  accent: string
  deploymentMode: string
  hardwareTitle: string
  processorLabel: string
  storageLabel: string
  throughputLabel: string
  panelMode: 'gateway' | 'inline' | 'sensor' | 'isolation' | 'collector' | 'cleaner' | 'crypto'
  defaultHeight: SecurityFormFactorU
  fanCount: number
  psuCount: number
  throughputGbps: number
  cpuCores: number
  memoryGb: number
  diskCount: number
  diskGb: number
  retentionDays: number
  metricLabel: string
  metricKey: string
  metricDefault: number
}

export const SECURITY_DEVICE_PROFILES: Record<SecurityDeviceType, SecurityDeviceProfile> = {
  firewall: { label: '下一代防火墙', shortLabel: 'NGFW', accent: '#e25555', deploymentMode: 'route/transparent', hardwareTitle: '安全网关硬件配置', processorLabel: '会话处理核', storageLabel: '策略日志盘', throughputLabel: '防火墙吞吐', panelMode: 'gateway', defaultHeight: 2, fanCount: 4, psuCount: 2, throughputGbps: 40, cpuCores: 24, memoryGb: 128, diskCount: 2, diskGb: 960, retentionDays: 30, metricLabel: '并发会话（万）', metricKey: 'concurrent_sessions_10k', metricDefault: 400 },
  ips: { label: '入侵防御系统', shortLabel: 'IPS', accent: '#ed8b35', deploymentMode: 'inline/bypass', hardwareTitle: '串联检测硬件配置', processorLabel: '检测处理核', storageLabel: '事件取证盘', throughputLabel: '防御吞吐', panelMode: 'inline', defaultHeight: 1, fanCount: 3, psuCount: 2, throughputGbps: 40, cpuCores: 28, memoryGb: 128, diskCount: 2, diskGb: 1920, retentionDays: 60, metricLabel: '规则特征库（万）', metricKey: 'signature_capacity_10k', metricDefault: 20 },
  ids: { label: '入侵检测系统', shortLabel: 'IDS', accent: '#f1b94b', deploymentMode: 'tap/mirror', hardwareTitle: '旁路采集分析配置', processorLabel: '分析处理核', storageLabel: '全流量取证盘', throughputLabel: '采集分析带宽', panelMode: 'sensor', defaultHeight: 2, fanCount: 4, psuCount: 2, throughputGbps: 40, cpuCores: 32, memoryGb: 192, diskCount: 8, diskGb: 3840, retentionDays: 90, metricLabel: '采集流量（Gbps）', metricKey: 'capture_gbps', metricDefault: 40 },
  vpn: { label: 'VPN 安全网关', shortLabel: 'VPN', accent: '#5b8def', deploymentMode: 'gateway', hardwareTitle: '隧道与密码加速配置', processorLabel: '隧道加速核', storageLabel: '系统审计盘', throughputLabel: '加密吞吐', panelMode: 'gateway', defaultHeight: 1, fanCount: 3, psuCount: 2, throughputGbps: 20, cpuCores: 20, memoryGb: 64, diskCount: 2, diskGb: 960, retentionDays: 30, metricLabel: '并发隧道数', metricKey: 'vpn_tunnels', metricDefault: 20000 },
  optical_gate: { label: '双网安全光闸', shortLabel: 'GAP', accent: '#7b73e8', deploymentMode: 'dual-network/isolation', hardwareTitle: '双主机隔离交换配置', processorLabel: '交换处理核', storageLabel: '摆渡交换盘', throughputLabel: '交换吞吐', panelMode: 'isolation', defaultHeight: 2, fanCount: 4, psuCount: 2, throughputGbps: 10, cpuCores: 24, memoryGb: 128, diskCount: 4, diskGb: 1920, retentionDays: 90, metricLabel: '交换任务数', metricKey: 'exchange_tasks', metricDefault: 1000 },
  host_audit: { label: '主机审计系统', shortLabel: 'H-AUDIT', accent: '#37a87b', deploymentMode: 'agent/collector', hardwareTitle: '终端日志汇聚配置', processorLabel: '日志处理核', storageLabel: '主机审计存储', throughputLabel: '接入吞吐', panelMode: 'collector', defaultHeight: 2, fanCount: 4, psuCount: 2, throughputGbps: 10, cpuCores: 24, memoryGb: 128, diskCount: 8, diskGb: 3840, retentionDays: 180, metricLabel: '审计主机数', metricKey: 'audit_hosts', metricDefault: 2000 },
  database_audit: { label: '数据库审计系统', shortLabel: 'DB-AUDIT', accent: '#258ea6', deploymentMode: 'mirror/agent', hardwareTitle: '数据库流量审计配置', processorLabel: 'SQL 分析核', storageLabel: '数据库审计存储', throughputLabel: 'SQL 审计吞吐', panelMode: 'collector', defaultHeight: 2, fanCount: 5, psuCount: 2, throughputGbps: 20, cpuCores: 32, memoryGb: 256, diskCount: 12, diskGb: 3840, retentionDays: 180, metricLabel: '数据库实例数', metricKey: 'database_instances', metricDefault: 500 },
  net_audit: { label: '网络审计系统', shortLabel: 'N-AUDIT', accent: '#3d9f73', deploymentMode: 'tap/mirror', hardwareTitle: '全流量审计存储配置', processorLabel: '协议分析核', storageLabel: '网络审计存储', throughputLabel: '审计吞吐', panelMode: 'sensor', defaultHeight: 2, fanCount: 5, psuCount: 2, throughputGbps: 20, cpuCores: 28, memoryGb: 192, diskCount: 12, diskGb: 3840, retentionDays: 180, metricLabel: '日志处理（EPS）', metricKey: 'log_eps', metricDefault: 50000 },
  ddos: { label: 'DDoS 防护设备', shortLabel: 'ANTI-DDoS', accent: '#d45d79', deploymentMode: 'inline/diversion', hardwareTitle: '大流量清洗硬件配置', processorLabel: '流量清洗核', storageLabel: '攻击取证盘', throughputLabel: '清洗吞吐', panelMode: 'cleaner', defaultHeight: 2, fanCount: 6, psuCount: 2, throughputGbps: 400, cpuCores: 48, memoryGb: 256, diskCount: 4, diskGb: 1920, retentionDays: 60, metricLabel: '清洗能力（Gbps）', metricKey: 'cleaning_gbps', metricDefault: 400 },
  crypto: { label: '密码安全设备', shortLabel: 'CRYPTO', accent: '#8a6fb3', deploymentMode: 'service', hardwareTitle: '密码运算加速配置', processorLabel: '密码运算核', storageLabel: '密钥审计盘', throughputLabel: '服务吞吐', panelMode: 'crypto', defaultHeight: 1, fanCount: 3, psuCount: 2, throughputGbps: 10, cpuCores: 20, memoryGb: 64, diskCount: 2, diskGb: 960, retentionDays: 90, metricLabel: '密码运算（TPS）', metricKey: 'crypto_tps', metricDefault: 5000 },
}

export function normalizeSecurityDeviceType(value: unknown): SecurityDeviceType {
  const key = String(value || 'firewall') as SecurityDeviceType
  return SECURITY_DEVICE_PROFILES[key] ? key : 'firewall'
}

export function securityDeviceProfile(value: unknown): SecurityDeviceProfile {
  return SECURITY_DEVICE_PROFILES[normalizeSecurityDeviceType(value)]
}
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

/** 单台安全设备允许配置的最大接口板卡插槽数。 */
export const MAX_SECURITY_IFACE_SLOTS = 8

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
  const n = clamp(slotCount, 1, MAX_SECURITY_IFACE_SLOTS)
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
  const want = clamp(slotCount ?? (Array.isArray(raw) ? raw.length : 4) ?? 4, 0, MAX_SECURITY_IFACE_SLOTS)
  if (want === 0) return []
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
  if (Array.isArray(attrs.security_slots)) {
    if (!attrs.security_slots.length && Number(attrs.slot_count) === 0) return []
    if (attrs.security_slots.length) return normalizeSecurityIfaceSlots(attrs.security_slots, count)
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

export function defaultSecurityIfaceSlotsForType(value: unknown): SecurityIfaceSlotAttr[] {
  const type = normalizeSecurityDeviceType(value)
  const management = { control_count: 1, ha_count: type === 'ids' ? 0 : 2, mgmt_count: 1, usb_count: 2 }
  if (type === 'optical_gate') {
    return normalizeSecurityIfaceSlots([
      { index: 1, ...management, ports_10g: 2, ports_1g: 4 },
      { index: 2, control_count: 0, ha_count: 0, mgmt_count: 1, usb_count: 0, ports_10g: 2, ports_1g: 4 },
    ], 2)
  }
  const ports10 = type === 'firewall' || type === 'ips' || type === 'ids' || type === 'ddos' ? 8 : type === 'database_audit' || type === 'net_audit' ? 8 : 4
  const ports1 = type === 'vpn' ? 4 : 2
  return normalizeSecurityIfaceSlots([{ index: 1, ...management, ports_10g: ports10, ports_1g: ports1 }], 1)
}

export function securityPortId(slotIndex: number, kind: string, portIndex: number): string {
  return `sec-s${slotIndex}-${kind.toLowerCase()}-p${portIndex}`
}
/** 转为安全面板 zones（保留现有 zone 布局引擎） */
export function securitySlotsToZones(slots: SecurityIfaceSlotAttr[]): SecurityZoneInput[] {
  const zones: SecurityZoneInput[] = []
  for (const s of slots) {
    const push = (kind: string, portType: '1g' | '10g' | 'bmc' | 'other', count: number) => {
      if (count <= 0) return
      zones.push({
        label: `Slot${s.index} ${kind.toUpperCase()}`,
        port_type: portType,
        count,
        zone_layout: count >= 8 ? 'two_row' : 'single_row',
        id_ns: `sec-s${s.index}-${kind.toLowerCase()}`,
      })
    }
    push('10g', '10g', s.ports_10g)
    push('1g', '1g', s.ports_1g)
    push('control', '1g', s.control_count)
    push('ha', '10g', s.ha_count)
    push('mgmt', 'bmc', s.mgmt_count)
    push('usb', 'other', s.usb_count)
  }
  return zones

}

export function syncSecurityDerivedAttrs(attrs: Record<string, unknown>): void {
  const deviceType = normalizeSecurityDeviceType(attrs.security_device_type)
  const profile = securityDeviceProfile(deviceType)
  const needsProfileApply =
    String(attrs.security_profile_type_applied || '') !== deviceType ||
    Number(attrs.security_profile_version || 0) < 3

  attrs.security_device_type = deviceType
  attrs.panel_variant = deviceType
  if (needsProfileApply) {
    attrs.deployment_mode = profile.deploymentMode
    attrs.cpu_cores = profile.cpuCores
    attrs.memory_gb = profile.memoryGb
    attrs.disk_count = profile.diskCount
    attrs.disk_gb = profile.diskGb
    attrs.throughput_gbps = profile.throughputGbps
    attrs.retention_days = profile.retentionDays
    attrs[profile.metricKey] = profile.metricDefault
    attrs.fan_count = profile.fanCount
    attrs.psu_count = profile.psuCount
    attrs.security_slots = defaultSecurityIfaceSlotsForType(deviceType)
    attrs.slot_count = defaultSecurityIfaceSlotsForType(deviceType).length
    attrs.security_profile_type_applied = deviceType
    attrs.security_profile_version = 3
  }

  attrs.deployment_mode = String(attrs.deployment_mode || profile.deploymentMode)
  attrs.cpu_cores = clamp(Number(attrs.cpu_cores) || profile.cpuCores, 1, 128)
  attrs.memory_gb = clamp(Number(attrs.memory_gb) || profile.memoryGb, 1, 2048)
  attrs.disk_count = clamp(Number(attrs.disk_count) || profile.diskCount, 0, 24)
  attrs.disk_gb = clamp(Number(attrs.disk_gb) || profile.diskGb, 0, 100000)
  attrs.throughput_gbps = Math.max(0, Number(attrs.throughput_gbps) || profile.throughputGbps)
  attrs.retention_days = clamp(Number(attrs.retention_days) || profile.retentionDays, 1, 3650)
  if (attrs[profile.metricKey] == null) attrs[profile.metricKey] = profile.metricDefault

  const u = normalizeSecurityFormFactor(attrs.chassis_height_u ?? attrs.form_factor_u ?? profile.defaultHeight)
  attrs.chassis_height_u = u
  attrs.form_factor_u = u
  const rawCount = Number(attrs.slot_count)
  const count = Number.isFinite(rawCount) && rawCount >= 0
    ? clamp(rawCount, 0, MAX_SECURITY_IFACE_SLOTS)
    : defaultSecurityIfaceSlotsForType(deviceType).length
  attrs.slot_count = count
  const slots = normalizeSecurityIfaceSlots(attrs.security_slots, count)
  attrs.security_slots = slots

  attrs.data_port_type = '10g'
  attrs.data_port_count = slots.reduce((a, s) => a + s.ports_10g, 0)
  attrs.control_ports = slots.reduce((a, s) => a + s.control_count, 0)
  attrs.ha_ports = slots.reduce((a, s) => a + s.ha_count, 0)
  attrs.mgmt_ports = slots.reduce((a, s) => a + s.mgmt_count, 0)
  attrs.usb_ports = slots.reduce((a, s) => a + s.usb_count, 0)

  attrs.fan_count = clamp(Number(attrs.fan_count) || profile.fanCount, 0, 16)
  attrs.psu_count = clamp(Number(attrs.psu_count) || profile.psuCount, 0, 8)

  if (!attrs.panel_layout || typeof attrs.panel_layout !== 'object') {
    attrs.panel_layout = {
      cols: 38, rows: 16, grid_scale: 4,
      front: { cols: 38, rows: 16, items: [] },
      rear: { cols: 38, rows: 16, items: [] },
    }
  }
  if (!Array.isArray(attrs.custom_attributes)) attrs.custom_attributes = []
}

export function defaultSecurityAttributes(
  formFactor: SecurityFormFactorU | undefined = undefined,
  value: unknown = 'firewall',
): Record<string, unknown> {
  const deviceType = normalizeSecurityDeviceType(value)
  const profile = securityDeviceProfile(deviceType)
  const u = formFactor ?? profile.defaultHeight
  const attrs: Record<string, unknown> = {
    security_device_type: deviceType,
    chassis_height_u: u,
    form_factor_u: u,
    panel_layout: {
      cols: 38, rows: 16, grid_scale: 4,
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
