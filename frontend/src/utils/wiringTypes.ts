/** 拓扑布线规则结构化配置（与后端 wiring_rule_config 对齐；UI 按表格分区） */

export type FabricRole = 'CORE' | 'AGG' | 'ACCESS' | 'SERVER' | 'FIREWALL' | 'OTHER'
export type ConnectionType =
  | 'UPLINK'
  | 'DOWNLINK'
  | 'SERVER'
  | 'SECURITY'
  | 'PEER'
  | 'DAD'
  | 'MGMT'
export type SpeedMode = 'EXACT' | 'MIN'
export type PairingMode = 'PER_SOURCE_TARGET' | 'POOL'
export type PortPurpose = 'UPLINK' | 'DOWNLINK' | 'MGMT' | 'PEER' | 'DAD' | 'SERVER' | 'OTHER'
export type DiversityLevel = 'REQUIRED' | 'OPTIONAL' | 'OFF'
export type RedundancyMode = 'NONE' | 'A_B'
export type LagMode = 'STATIC' | 'LACP'
export type DistanceMode = 'AUTO' | 'FIXED'
export type CableLengthMode = 'AUTO' | 'FIXED'
export type MediaKind =
  | 'AUTO'
  | 'DAC'
  | 'AOC'
  | 'FIBER_MM'
  | 'FIBER_SM'
  | 'MPO'
  | 'COPPER'
  | 'BREAKOUT_1X4'

export interface WiringPair {
  source_node_id: string
  source_port_id: string
  target_node_id: string
  target_port_id: string
}

export interface WiringRuleConfig {
  source_role?: FabricRole | null
  target_role?: FabricRole | null
  source_group?: string | null
  target_group?: string | null
  source_node_ids?: string[]
  target_node_ids?: string[]
  connection_type?: ConnectionType
  required?: boolean

  link_count?: number
  min_link_count?: number | null
  max_link_count?: number | null
  speed?: string | null
  speed_mode?: SpeedMode
  pairing?: PairingMode
  max_links?: number | null
  link_type?: string | null
  cable_type?: string | null

  source_port_purpose?: PortPurpose | null
  target_port_purpose?: PortPurpose | null
  port_speed?: string | null
  port_type?: string | null
  source_port_types?: string[]
  target_port_types?: string[]
  source_port_ids?: string[]
  target_port_ids?: string[]
  source_port_range?: string | null
  target_port_range?: string | null
  peer_port_range?: string | null
  port_allocation?: 'AUTO'
  port_priority?: number

  redundancy_mode?: RedundancyMode
  device_diversity?: DiversityLevel
  path_diversity?: DiversityLevel
  rack_diversity?: DiversityLevel
  power_domain_diversity?: DiversityLevel
  card_diversity?: DiversityLevel
  port_diversity?: DiversityLevel

  peer_link?: boolean
  peer_link_count?: number
  peer_link_speed?: string | null
  peer_media?: MediaKind | null
  peer_port_purpose?: PortPurpose

  keepalive?: boolean
  keepalive_network?: string | null

  lag?: boolean
  lag_count?: number
  lag_mode?: LagMode

  media?: MediaKind
  fiber_type?: string | null
  connector?: string | null
  distance_mode?: DistanceMode
  max_distance_m?: number | null
  module?: string | null
  cable_length_mode?: CableLengthMode
  cable_length_m?: number | null

  label_template?: string | null
  cable_code_template?: string | null
  business_plane?: string | null

  validate_on_apply?: boolean
  pairs?: WiringPair[]
}

export const FABRIC_ROLE_OPTIONS: { value: FabricRole; label: string }[] = [
  { value: 'CORE', label: '核心 CORE' },
  { value: 'AGG', label: '汇聚 AGG' },
  { value: 'ACCESS', label: '接入 ACCESS' },
  { value: 'SERVER', label: '服务器 SERVER' },
  { value: 'FIREWALL', label: '安全设备 SECURITY' },
  { value: 'OTHER', label: '自定义角色' },
]

export const CONNECTION_TYPE_OPTIONS: { value: ConnectionType; label: string }[] = [
  { value: 'UPLINK', label: '上联 UPLINK' },
  { value: 'DOWNLINK', label: '下联 DOWNLINK' },
  { value: 'SERVER', label: '服务器接入 SERVER' },
  { value: 'SECURITY', label: '安全接入 SECURITY' },
  { value: 'PEER', label: '互联线 PEER-LINK' },
  { value: 'DAD', label: '心跳线 DAD' },
]

export const PORT_PURPOSE_OPTIONS: { value: PortPurpose; label: string }[] = [
  { value: 'UPLINK', label: 'UPLINK' },
  { value: 'DOWNLINK', label: 'DOWNLINK' },
  { value: 'MGMT', label: 'MGMT' },
  { value: 'PEER', label: 'PEER-LINK' },
  { value: 'DAD', label: 'DAD' },
]

export const MEDIA_OPTIONS: { value: MediaKind; label: string }[] = [
  { value: 'AUTO', label: 'AUTO' },
  { value: 'DAC', label: 'DAC' },
  { value: 'AOC', label: 'AOC' },
  { value: 'FIBER_MM', label: '多模光纤' },
  { value: 'FIBER_SM', label: '单模光纤' },
  { value: 'MPO', label: 'MPO' },
  { value: 'COPPER', label: '网线' },
  { value: 'BREAKOUT_1X4', label: '1分4光纤跳线' },
]

export const SPEED_OPTIONS = ['1G', '10G', '25G', '40G', '100G', '400G']

export const CONNECTION_TO_LINK_ROLE: Record<ConnectionType, string> = {
  UPLINK: 'uplink',
  DOWNLINK: 'downlink',
  SERVER: 'server',
  SECURITY: 'security',
  PEER: 'interconnect',
  DAD: 'interconnect',
  MGMT: 'downlink',
}

export const CONNECTION_TO_LINK_TYPE: Record<ConnectionType, string> = {
  UPLINK: 'switch_switch',
  DOWNLINK: 'switch_switch',
  SERVER: 'switch_server',
  SECURITY: 'switch_security',
  PEER: 'switch_switch',
  DAD: 'switch_switch',
  MGMT: 'switch_switch',
}

function defaultPurpose(conn: ConnectionType, _side: 'source' | 'target'): PortPurpose {
  if (conn === 'UPLINK') return 'UPLINK'
  if (conn === 'DOWNLINK') return 'DOWNLINK'
  if (conn === 'SERVER') return 'DOWNLINK'
  if (conn === 'SECURITY') return 'DOWNLINK'
  if (conn === 'PEER') return 'PEER'
  if (conn === 'DAD') return 'DAD'
  if (conn === 'MGMT') return 'MGMT'
  return 'OTHER'
}

/** 连接类型切换时同步 Peer/DAD 相关开关与默认 Purpose */
export function applyConnectionTypeSideEffects(cfg: WiringRuleConfig): WiringRuleConfig {
  const conn = cfg.connection_type || 'UPLINK'
  if (conn === 'PEER') {
    cfg.peer_link = true
    cfg.keepalive = false
    cfg.source_port_purpose = 'PEER'
    cfg.target_port_purpose = 'PEER'
  } else if (conn === 'DAD') {
    cfg.peer_link = true
    cfg.keepalive = true
    cfg.source_port_purpose = 'DAD'
    cfg.target_port_purpose = 'DAD'
  } else {
    cfg.peer_link = false
    cfg.keepalive = false
    cfg.source_port_purpose = defaultPurpose(conn, 'source')
    cfg.target_port_purpose = defaultPurpose(conn, 'target')
  }
  return cfg
}

export function defaultWiringConfig(): WiringRuleConfig {
  return {
    source_role: 'CORE',
    target_role: 'AGG',
    source_group: null,
    target_group: null,
    source_node_ids: [],
    target_node_ids: [],
    connection_type: 'UPLINK',
    required: true,
    link_count: 2,
    min_link_count: 2,
    max_link_count: 4,
    speed: '100G',
    speed_mode: 'EXACT',
    pairing: 'PER_SOURCE_TARGET',
    source_port_purpose: 'UPLINK',
    target_port_purpose: 'UPLINK',
    port_speed: '100G',
    source_port_types: [],
    target_port_types: [],
    source_port_ids: [],
    target_port_ids: [],
    source_port_range: null,
    target_port_range: null,
    peer_port_range: null,
    port_allocation: 'AUTO',
    port_priority: 100,
    redundancy_mode: 'A_B',
    device_diversity: 'OFF',
    path_diversity: 'OPTIONAL',
    rack_diversity: 'OPTIONAL',
    power_domain_diversity: 'OFF',
    card_diversity: 'OPTIONAL',
    port_diversity: 'REQUIRED',
    peer_link: false,
    peer_link_count: 2,
    peer_link_speed: '100G',
    peer_media: 'DAC',
    peer_port_purpose: 'PEER',
    keepalive: false,
    keepalive_network: 'OOB',
    lag: true,
    lag_count: 1,
    lag_mode: 'LACP',
    media: 'AUTO',
    fiber_type: 'OS2',
    connector: 'LC',
    distance_mode: 'AUTO',
    max_distance_m: 3,
    module: null,
    cable_length_mode: 'AUTO',
    cable_length_m: null,
    label_template: '{conn}-{seq:02d}',
    cable_code_template: null,
    validate_on_apply: true,
    pairs: [],
  }
}

export function normalizeWiringConfig(raw: Record<string, unknown> | null | undefined): WiringRuleConfig {
  const base = defaultWiringConfig()
  const data = { ...base, ...(raw || {}) } as WiringRuleConfig
  let conn = (data.connection_type || 'UPLINK') as ConnectionType
  // 兼容旧 MGMT
  if ((conn as string) === 'MGMT') conn = 'DOWNLINK'
  data.connection_type = conn

  if (data.max_link_count == null && data.max_links != null) {
    data.max_link_count = Number(data.max_links)
  }
  data.link_count = Math.max(1, Number(data.link_count) || 2)
  if (data.min_link_count == null) data.min_link_count = data.link_count
  if (data.max_link_count == null) data.max_link_count = Math.max(data.link_count, 4)
  data.min_link_count = Math.min(Number(data.min_link_count), data.link_count)
  data.max_link_count = Math.max(Number(data.max_link_count), data.link_count)

  if (!data.source_port_purpose) data.source_port_purpose = defaultPurpose(conn, 'source')
  if (!data.target_port_purpose) data.target_port_purpose = defaultPurpose(conn, 'target')
  if (!data.port_speed && data.speed) data.port_speed = data.speed

  if (data.peer_link || conn === 'PEER' || conn === 'DAD') {
    data.peer_link = true
    if (conn === 'DAD') {
      data.keepalive = true
      data.source_port_purpose = 'DAD'
      data.target_port_purpose = 'DAD'
    } else {
      if (conn !== 'PEER') data.connection_type = 'PEER'
      data.source_port_purpose = data.source_port_purpose || 'PEER'
      data.target_port_purpose = data.target_port_purpose || 'PEER'
    }
    data.link_count = Math.max(1, Number(data.peer_link_count) || 2)
    if (data.peer_port_range) {
      data.source_port_range = data.source_port_range || data.peer_port_range
      data.target_port_range = data.target_port_range || data.peer_port_range
    }
    if (data.peer_link_speed) {
      data.speed = data.peer_link_speed
      data.port_speed = data.peer_link_speed
    }
    if (data.peer_media) data.media = data.peer_media
  }

  data.source_node_ids = Array.isArray(data.source_node_ids) ? data.source_node_ids : []
  data.target_node_ids = Array.isArray(data.target_node_ids) ? data.target_node_ids : []
  data.source_port_types = Array.isArray(data.source_port_types) ? data.source_port_types : []
  data.target_port_types = Array.isArray(data.target_port_types) ? data.target_port_types : []
  return data
}
