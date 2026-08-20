import type { ModelCategory } from '@/api/networkModelDesign'
import type { SwitchSubtype } from '@/api/network'
import {
  defaultServerAttributes,
  syncServerDerivedAttrs,
  type ServerFormFactorU,
} from '@/utils/serverModelAttrs'
import {
  defaultSecurityAttributes,
  defaultSecurityIfaceSlotsForType,
  syncSecurityDerivedAttrs,
  type SecurityFormFactorU,
} from '@/utils/securityModelAttrs'
import {
  defaultNetworkSwitchAttributes,
  syncSwitchDerivedCounts,
} from '@/utils/switchModelAttrs'

export type NetworkModelPresetFamily = 'server' | 'switch' | 'security'

export interface NetworkModelPreset {
  id: string
  family: NetworkModelPresetFamily
  category: Exclude<ModelCategory, 'software'>
  subtype: string
  name: string
  vendorSku: string
  heightU: number
  summary: string
  tags: string[]
  switchRole?: SwitchSubtype
  attributes: Record<string, unknown>
}

function serverPreset(
  id: string,
  name: string,
  heightU: ServerFormFactorU,
  summary: string,
  attributes: Record<string, unknown>,
): NetworkModelPreset {
  return {
    id,
    family: 'server',
    category: 'server',
    subtype: id.includes('storage') ? 'storage' : id.includes('hpc') ? 'hpc' : 'compute',
    name,
    vendorSku: id.toUpperCase(),
    heightU,
    summary,
    tags: [`${heightU}U`, '双电源', 'BMC', '自动编号'],
    attributes,
  }
}

function switchPreset(
  id: string,
  name: string,
  role: SwitchSubtype,
  summary: string,
  attributes: Record<string, unknown>,
): NetworkModelPreset {
  return {
    id,
    family: 'switch',
    category: 'network',
    subtype: role,
    name,
    vendorSku: id.toUpperCase(),
    heightU: role === 'core' ? 10 : role === 'aggregation' ? 4 : 1,
    summary,
    tags: [role === 'gigabit' ? '千兆' : role === 'ten_gigabit' ? '万兆' : role === 'aggregation' ? '汇聚' : '核心', '端口池', '连续编号'],
    switchRole: role,
    attributes,
  }
}

function securityPreset(
  id: string,
  subtype: string,
  name: string,
  heightU: SecurityFormFactorU,
  summary: string,
  attributes: Record<string, unknown>,
): NetworkModelPreset {
  return {
    id,
    family: 'security',
    category: 'security',
    subtype,
    name,
    vendorSku: id.toUpperCase(),
    heightU,
    summary,
    tags: [`${heightU}U`, 'HA/MGMT', '业务口编号', '安全设备'],
    attributes,
  }
}

function serverAttrs(heightU: ServerFormFactorU, patch: Record<string, unknown>) {
  const attrs = { ...defaultServerAttributes(heightU), ...patch }
  syncServerDerivedAttrs(attrs)
  return attrs
}

function switchAttrs(role: SwitchSubtype, patch: Record<string, unknown>) {
  const attrs = { ...defaultNetworkSwitchAttributes(role), ...patch, switch_role: role }
  syncSwitchDerivedCounts(attrs)
  return attrs
}

function securityAttrs(
  heightU: SecurityFormFactorU,
  subtype: string,
  patch: Record<string, unknown>,
) {
  const attrs = {
    ...defaultSecurityAttributes(heightU, subtype),
    ...patch,
    security_device_type: subtype,
    security_slots: defaultSecurityIfaceSlotsForType(subtype),
    slot_count: defaultSecurityIfaceSlotsForType(subtype).length,
    fabric_role: 'FIREWALL',
  }
  syncSecurityDerivedAttrs(attrs)
  return attrs
}

export const NETWORK_MODEL_PRESETS: NetworkModelPreset[] = [
  serverPreset(
    'srv-1u-compute',
    '通用 1U 计算服务器',
    1,
    '双路计算节点，板载管理口、双千兆 LOM 与双 25GE 灵活 IO，适合通用业务和虚拟化计算。',
    serverAttrs(1, {
      cpu_sockets: 2,
      cpu_cores_per_socket: 24,
      memory_type: 'ddr5',
      memory_module_gb: 32,
      memory_modules: 8,
      disk_front_count: 4,
      disk_front_proto: 'nvme',
      flex_io_speed: '25ge',
      pcie_slots: [{ index: 1, flex_ports: 2 }, { index: 2, flex_ports: 2 }],
      sim_icon: 'Server.png',
    }),
  ),
  serverPreset(
    'srv-2u-virtualization',
    '高密 2U 虚拟化服务器',
    2,
    '双路大内存、12 盘位、双板卡四口 25GE，面向虚拟化集群与数据库计算节点。',
    serverAttrs(2, {
      cpu_sockets: 2,
      cpu_cores_per_socket: 32,
      memory_type: 'ddr5',
      memory_module_gb: 32,
      memory_modules: 16,
      disk_front_count: 12,
      disk_front_proto: 'sas_sata',
      pcie_slots: [
        { index: 1, flex_ports: 2 }, { index: 2, flex_ports: 2 },
        { index: 3, flex_ports: 0 }, { index: 4, flex_ports: 0 },
        { index: 5, flex_ports: 0 }, { index: 6, flex_ports: 0 },
      ],
      flex_io_speed: '25ge',
      sim_icon: 'Server.png',
    }),
  ),
  serverPreset(
    'srv-2u-storage',
    '高密 2U 存储服务器',
    2,
    '24 盘位存储节点，双 25GE 数据口和冗余管理接口，适合分布式存储与备份。',
    serverAttrs(2, {
      cpu_sockets: 2,
      cpu_cores_per_socket: 20,
      memory_type: 'ddr5',
      memory_module_gb: 32,
      memory_modules: 8,
      disk_front_count: 24,
      disk_front_size: '2.5',
      disk_front_proto: 'sas_sata',
      pcie_slots: [
        { index: 1, flex_ports: 2 }, { index: 2, flex_ports: 2 },
        { index: 3, flex_ports: 0 }, { index: 4, flex_ports: 0 },
        { index: 5, flex_ports: 0 }, { index: 6, flex_ports: 0 },
      ],
      flex_io_speed: '25ge',
      sim_icon: 'Server.png',
    }),
  ),
  serverPreset(
    'srv-4u-hpc',
    '4U GPU/HPC 服务器',
    4,
    '四路高性能计算与 GPU 扩展机箱，四口 25GE，适合 AI、HPC 和高吞吐分析。',
    serverAttrs(4, {
      cpu_sockets: 4,
      cpu_cores_per_socket: 48,
      memory_type: 'ddr5',
      memory_module_gb: 64,
      memory_modules: 16,
      disk_front_count: 24,
      pcie_slots: Array.from({ length: 8 }, (_, index) => ({ index: index + 1, flex_ports: index < 2 ? 2 : 0 })),
      flex_io_speed: '25ge',
      psu_count: 4,
      psu_watt: 1600,
      sim_icon: 'Server.png',
    }),
  ),

  switchPreset(
    'sw-access-1g-48',
    '48 口千兆接入交换机',
    'gigabit',
    '48×1GE 下联 + 8×10GE 上联，业务口 1–48、上联口独立编号，适合终端和 BMC 接入。',
    switchAttrs('gigabit', { switching_capacity_gbps: 256, stackable: true, sim_icon: 'Switch.png' }),
  ),
  switchPreset(
    'sw-access-10g-48',
    '48 口万兆接入交换机',
    'ten_gigabit',
    '48×10GE 下联 + 6×40/100GE 上联，适合服务器双归接入和叶交换架构。',
    switchAttrs('ten_gigabit', { switching_capacity_gbps: 2400, stackable: true, sim_icon: 'Switch.png' }),
  ),
  switchPreset(
    'sw-aggregation-100g',
    '模块化汇聚交换机',
    'aggregation',
    '多板卡 10/25/100GE 汇聚设备，区分 DOWNLINK/UPLINK 端口池，支持双机互联。',
    switchAttrs('aggregation', { chassis_height_u: 4, modular_expansion_slots: 4, switching_capacity_gbps: 6400, sim_icon: 'Switch.png' }),
  ),
  switchPreset(
    'sw-core-100g',
    '高容量核心交换机',
    'core',
    '10U 核心机箱，模块化 40/100GE 线卡与冗余系统口，适合核心—汇聚双平面。',
    switchAttrs('core', { chassis_height_u: 10, modular_expansion_slots: 8, switching_capacity_gbps: 25600, sim_icon: 'Switch.png' }),
  ),

  securityPreset('sec-firewall-ng', 'firewall', '2U 下一代防火墙', 2, '双机 HA，管理/控制口与 16×10GE 业务口分区编号。', securityAttrs(2, 'firewall', { cpu_cores: 24, memory_gb: 128, throughput_gbps: 80, sim_icon: 'Firewall.png' })),
  securityPreset('sec-ips-inline', 'ips', '1U 入侵防御 IPS', 1, '旁路/串联部署，8×10GE 检测口、管理口与 HA 口独立编号。', securityAttrs(1, 'ips', { cpu_cores: 16, memory_gb: 64, throughput_gbps: 40, deployment_mode: 'inline', sim_icon: 'Firewall.png' })),
  securityPreset('sec-ids-tap', 'ids', '1U 入侵检测 IDS', 1, '旁路镜像流量检测，8×10GE 采集口与独立管理接口。', securityAttrs(1, 'ids', { cpu_cores: 16, memory_gb: 64, throughput_gbps: 40, deployment_mode: 'tap', ha_ports: 0, sim_icon: 'Firewall.png' })),
  securityPreset('sec-vpn-gateway', 'vpn', '1U VPN 安全网关', 1, '双链路 VPN 接入，4×10GE + 4×1GE 业务接口与 HA/MGMT 口。', securityAttrs(1, 'vpn', { cpu_cores: 16, memory_gb: 64, throughput_gbps: 20, sim_icon: 'Firewall.png' })),
  securityPreset('sec-optical-gate', 'optical_gate', '2U 双网光闸', 2, '内外网物理隔离，接口按 INNER/OUTER 语义分区，适合单向或受控交换。', securityAttrs(2, 'optical_gate', { cpu_cores: 12, memory_gb: 32, throughput_gbps: 10, isolation_mode: 'dual_network', sim_icon: 'Firewall.png' })),
  securityPreset('sec-host-audit', 'host_audit', '1U 主机审计设备', 1, '业务采集、管理和存储接口分区，面向主机行为审计。', securityAttrs(1, 'host_audit', { cpu_cores: 16, memory_gb: 64, disk_count: 4, disk_gb: 1920, throughput_gbps: 10, sim_icon: 'Firewall.png' })),
  securityPreset('sec-db-audit', 'database_audit', '2U 数据库审计设备', 2, '高性能镜像采集与审计存储，8×10GE 采集口和冗余管理口。', securityAttrs(2, 'database_audit', { cpu_cores: 24, memory_gb: 128, disk_count: 8, disk_gb: 3840, throughput_gbps: 40, sim_icon: 'Firewall.png' })),
  securityPreset('sec-net-audit', 'net_audit', '1U 网络审计设备', 1, '多链路流量采集、审计与回溯，管理口与采集口独立。', securityAttrs(1, 'net_audit', { cpu_cores: 16, memory_gb: 64, disk_count: 4, disk_gb: 1920, throughput_gbps: 20, sim_icon: 'Firewall.png' })),
]

export const NETWORK_MODEL_PRESET_GROUPS = [
  { family: 'server' as const, label: '服务器', presets: NETWORK_MODEL_PRESETS.filter((p) => p.family === 'server') },
  { family: 'switch' as const, label: '交换机', presets: NETWORK_MODEL_PRESETS.filter((p) => p.family === 'switch') },
  { family: 'security' as const, label: '安全设备', presets: NETWORK_MODEL_PRESETS.filter((p) => p.family === 'security') },
]

export function findNetworkModelPreset(id: string | null | undefined) {
  return NETWORK_MODEL_PRESETS.find((preset) => preset.id === id) || null
}

export function buildNetworkModelPresetAttributes(preset: NetworkModelPreset): Record<string, unknown> {
  return structuredClone(preset.attributes)
}