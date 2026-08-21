/** 拓扑布线规则结构化配置（与后端 wiring_rule_config 对齐；UI 按表格分区） */

export type FabricRole = 'CORE' | 'AGG' | 'ACCESS' | 'SERVER' | 'FIREWALL' | 'OTHER'
/** 布线连接类型（业务语义）；旧值在 normalize 时迁移 */
export type ConnectionType =
  | 'ACCESS_ENDPOINT'
  | 'BMC_ENDPOINT'
  | 'CORE_TO_ACCESS'
  | 'SWITCH_INTERCONNECT'
  // legacy
  | 'UPLINK'
  | 'DOWNLINK'
  | 'SERVER'
  | 'SECURITY'
  | 'PEER'
  | 'DAD'
  | 'MGMT'
export type SpeedMode = 'EXACT' | 'MIN'
export type PairingMode = 'PER_SOURCE_TARGET' | 'POOL'
export type PortPurpose =
  | 'UPLINK'
  | 'DOWNLINK'
  | 'MGMT'
  | 'PEER'
  | 'DAD'
  | 'SERVER'
  | 'SERVICE'
  | 'DATA'
  | 'INSIDE'
  | 'OUTSIDE'
  | 'TRUST'
  | 'UNTRUST'
  | 'DMZ'
  | 'HA'
  | 'SYNC'
  | 'OTHER'
/** 端口池：关联模型板卡光口 / 40/100G 上联口 */
export type PortPool = 'AUTO' | 'OPTICAL' | 'UPLINK'
export type DiversityLevel = 'REQUIRED' | 'OPTIONAL' | 'OFF'
export type RedundancyMode = 'NONE' | 'A_B'
export type LagMode = 'STATIC' | 'LACP'
export type DistanceMode = 'AUTO' | 'FIXED'
export type CableLengthMode = 'AUTO' | 'FIXED'
export type RuleCategory =
  | 'CORE_AGG_TO_10G'
  | 'TEN_GIG_TO_GIG'
  | 'TEN_GIG_TO_ENDPOINT'
  | 'GIG_TO_ENDPOINT'
  | 'BMC_TO_SERVER'
  | 'SWITCH_STACK_PEER_DAD'
  | 'CORE_AGG_INTERCONNECT'
  | 'CUSTOM'
export type EndpointConnectStrategy =
  | 'ROUND_ROBIN_ASC'
  | 'DEVICE_ASC'
  | 'DEVICE_DESC'
  | 'SLOT_ROUND_ROBIN'
  | 'SAME_SLOT_ASC'
  | 'SAME_NUMBER'
  | 'CROSS'
  | 'FULL_MESH'
  | 'FIXED_PORT'
  | 'MANUAL'
/** 端口分配模式：AUTO 场景配对；MANUAL 手动定义规则后由系统自动配对（可选 pairs 覆盖）；HYBRID 先预览可改口 */
export type AllocationMode = 'AUTO' | 'MANUAL' | 'HYBRID'
/** 候选口排序/选取策略 */
export type PortSelectPolicy = 'MIN_ASC' | 'MAX_DESC' | 'SAME_NUMBER' | 'SLOT_SPREAD'
/** 端口介质类型（内置键或自定义 value；兼容旧 FIBER|COPPER） */
export type PortMediaFilter = string
export type MediaKind =
  | 'AUTO'
  | 'MPO_MPO_OS2'
  | 'MPO_MPO_OM34'
  | 'LC_LC_OM34'
  | 'LC_LC_OS2'
  | 'MPO_LC_BREAKOUT'
  | 'CUSTOM_SYNC'
  | 'DAC'
  | 'AOC'
  | 'FIBER_MM'
  | 'FIBER_SM'
  | 'MPO'
  | 'COPPER'
  | 'BREAKOUT_1X4'

/** 面向真实综合布线场景的规则模板；CUSTOM 保留完全手工定义能力。 */
export type WiringScenarioTemplate =
  | 'CORE_TO_TEN_GIG'
  | 'TEN_GIG_TO_GIG'
  | 'TEN_GIG_TO_SERVER'
  | 'GIG_TO_SERVER'
  | 'SWITCH_TO_SECURITY'
  | 'BMC_TO_SERVER'
  | 'BMC_TO_SECURITY'
  | 'SWITCH_PEER'
  | 'CORE_INTERCONNECT'
  | 'CUSTOM'

export interface WiringPair {
  source_node_id: string
  source_port_id: string
  target_node_id: string
  target_port_id: string
}

export interface WiringRuleConfig {
  /** 规则表头分类，用于规则库检索和场景归类。 */
  rule_category?: RuleCategory
  /** 新版规则设计器选择的业务场景。 */
  scenario_template?: WiringScenarioTemplate
  source_role?: FabricRole | null
  target_role?: FabricRole | null
  source_roles?: FabricRole[]
  target_roles?: FabricRole[]
  /** 自动场景的实例硬件分类过滤，由模型属性推导。 */
  source_device_types?: string[]
  target_device_types?: string[]
  /** 源设备组（可多选） */
  source_groups?: string[]
  /** 目标设备组（可多选） */
  target_groups?: string[]
  /** @deprecated 兼容旧配置，normalize 时并入 source_groups */
  source_group?: string | null
  /** @deprecated 兼容旧配置，normalize 时并入 target_groups */
  target_group?: string | null
  source_node_ids?: string[]
  target_node_ids?: string[]
  /** 单台源交换机允许被本规则占用的最大 DOWNLINK 口数；UPLINK/Peer/DAD/MGMT 不计入。 */
  source_port_limit_per_device?: number | null
  /** 自动规则最多使用的本端交换机数量；空值表示使用全部匹配交换机。 */
  max_source_devices?: number | null
  source_connection_strategy?: EndpointConnectStrategy
  target_connection_strategy?: EndpointConnectStrategy
  /** 可选物理位置范围；与设备/组/角色条件取交集。 */
  source_room_ids?: string[]
  target_room_ids?: string[]
  source_rack_start?: string | null
  source_rack_end?: string | null
  target_rack_start?: string | null
  target_rack_end?: string | null
  source_devices_per_rack?: number | null
  target_devices_per_rack?: number | null
  source_start_u?: number | null
  target_start_u?: number | null
  source_u_interval?: number | null
  target_u_interval?: number | null
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
  /** 源端口池：AUTO 按 purpose 推导；OPTICAL=板卡光口；UPLINK=40/100G 上联 */
  source_port_pool?: PortPool | null
  target_port_pool?: PortPool | null
  port_speed?: string | null
  port_type?: string | null
  source_port_types?: string[]
  target_port_types?: string[]
  source_port_ids?: string[]
  target_port_ids?: string[]
  /** 物理槽位白名单；为空时使用全部槽位 */
  source_slot_ids?: number[]
  target_slot_ids?: number[]
  /** 物理槽位范围，如 1-4；与 slot_ids 同时设置时取交集 */
  source_slot_range?: string | null
  target_slot_range?: string | null
  source_port_range?: string | null
  target_port_range?: string | null
  peer_port_range?: string | null
  /** @deprecated 用 allocation_mode */
  port_allocation?: 'AUTO'
  /** AUTO | MANUAL | HYBRID */
  allocation_mode?: AllocationMode
  source_port_policy?: PortSelectPolicy
  target_port_policy?: PortSelectPolicy
  /** 端口能力介质过滤（非线缆类型） */
  port_media?: PortMediaFilter | null
  port_priority?: number
  /** true=规则条件无匹配时直接报错；false=允许兼容旧规则的软回退 */
  strict_port_match?: boolean

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
  /** 组内 INTRA / 组间 INTER — docs/rules.md 第四节 */
  interconnect_scope?: 'INTRA_GROUP' | 'INTER_GROUP'
  /** 启用 peer-link（UPLINK 尾口） */
  enable_peer_link?: boolean
  /** 启用 DAD（DOWNLINK 尾口） */
  enable_dad?: boolean
  /** peer 使用 UPLINK 末口数量，默认 2 */
  peer_tail_count?: number
  /** DAD 使用 DOWNLINK 末口数量，默认 2 */
  dad_tail_count?: number

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
  /** 自动估长时预留的机柜内走线长度。 */
  route_extra_m?: number | null
  /** 自动估长后的余量百分比。 */
  cable_slack_percent?: number | null

  label_template?: string | null
  /** 端子表两端标签，支持 source/target device/location/u/port 与 seq 占位符。 */
  source_label_template?: string | null
  target_label_template?: string | null
  sync_media_color?: boolean
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
  { value: 'ACCESS_ENDPOINT', label: '接入到服务器/安全设备' },
  { value: 'BMC_ENDPOINT', label: 'BMC到服务器/安全设备' },
  { value: 'CORE_TO_ACCESS', label: '核心/汇聚到接入交换机' },
  { value: 'SWITCH_INTERCONNECT', label: '交换机到交换机互联' },
]

const LEGACY_CONNECTION_MAP: Record<string, ConnectionType> = {
  UPLINK: 'CORE_TO_ACCESS',
  DOWNLINK: 'CORE_TO_ACCESS',
  SERVER: 'ACCESS_ENDPOINT',
  SECURITY: 'ACCESS_ENDPOINT',
  PEER: 'SWITCH_INTERCONNECT',
  DAD: 'SWITCH_INTERCONNECT',
  MGMT: 'BMC_ENDPOINT',
}

/** 将旧连接类型迁移为现行四类 */
export function migrateConnectionType(raw: string | null | undefined): ConnectionType {
  const v = String(raw || '').trim() || 'CORE_TO_ACCESS'
  if (
    v === 'ACCESS_ENDPOINT' ||
    v === 'BMC_ENDPOINT' ||
    v === 'CORE_TO_ACCESS' ||
    v === 'SWITCH_INTERCONNECT'
  ) {
    return v
  }
  return LEGACY_CONNECTION_MAP[v] || 'CORE_TO_ACCESS'
}

export function connectionTypeLabel(raw: string | null | undefined): string {
  const v = migrateConnectionType(raw)
  return CONNECTION_TYPE_OPTIONS.find((o) => o.value === v)?.label || v
}

/** 交换机互联（含旧 PEER/DAD） */
export function isSwitchInterconnect(conn: string | null | undefined): boolean {
  const v = migrateConnectionType(conn)
  return v === 'SWITCH_INTERCONNECT' || conn === 'PEER' || conn === 'DAD'
}

export const PORT_PURPOSE_OPTIONS: { value: PortPurpose; label: string }[] = [
  { value: 'UPLINK', label: 'UPLINK' },
  { value: 'DOWNLINK', label: 'DOWNLINK' },
  { value: 'MGMT', label: 'MGMT' },
  { value: 'PEER', label: 'PEER-LINK' },
  { value: 'DAD', label: 'DAD' },
  { value: 'SERVER', label: 'SERVER' },
  { value: 'SERVICE', label: '业务 SERVICE' },
  { value: 'DATA', label: '数据 DATA' },
  { value: 'INSIDE', label: '安全域 INSIDE' },
  { value: 'OUTSIDE', label: '安全域 OUTSIDE' },
  { value: 'TRUST', label: '安全域 TRUST' },
  { value: 'UNTRUST', label: '安全域 UNTRUST' },
  { value: 'DMZ', label: '安全域 DMZ' },
  { value: 'HA', label: '高可用 HA' },
  { value: 'SYNC', label: '同步 SYNC' },
  { value: 'OTHER', label: '其他 OTHER' },
]

export const PORT_POOL_OPTIONS: { value: PortPool; label: string }[] = [
  { value: 'AUTO', label: '自动（按 Purpose）' },
  { value: 'OPTICAL', label: '板卡光口' },
  { value: 'UPLINK', label: '40/100G 上联' },
]

export const ALLOCATION_MODE_OPTIONS: { value: AllocationMode; label: string }[] = [
  { value: 'AUTO', label: '自动分配' },
  { value: 'HYBRID', label: '自动后可改' },
  { value: 'MANUAL', label: '手动定义规则' },
]

export const INTERCONNECT_SCOPE_OPTIONS: {
  value: 'INTRA_GROUP' | 'INTER_GROUP'
  label: string
}[] = [
  { value: 'INTRA_GROUP', label: '组内互联（Peer + DAD）' },
  { value: 'INTER_GROUP', label: '组间互联（交叉上联）' },
]

export const PORT_POLICY_OPTIONS: { value: PortSelectPolicy; label: string }[] = [
  { value: 'MIN_ASC', label: '口号升序' },
  { value: 'MAX_DESC', label: '口号降序' },
  { value: 'SAME_NUMBER', label: '同号优先' },
  { value: 'SLOT_SPREAD', label: 'Slot 分散' },
]

/** @deprecated 使用 portMediaCatalog.listPortMediaTypes */
export const PORT_MEDIA_FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: 'AUTO', label: '不限' },
  { value: 'LC_LC', label: 'LC-LC光纤接口' },
  { value: 'MPO8', label: 'MPO8芯光纤' },
  { value: 'MPO4', label: 'MPO4芯光纤' },
  { value: 'FIBER', label: '光纤口（旧）' },
  { value: 'COPPER', label: '电口（旧）' },
]

/** Purpose → 默认端口池 */
export function poolFromPurpose(purpose: PortPurpose | null | undefined): PortPool {
  if (purpose === 'UPLINK' || purpose === 'PEER' || purpose === 'DAD') return 'UPLINK'
  if (purpose === 'DOWNLINK' || purpose === 'SERVER') return 'OPTICAL'
  return 'AUTO'
}

/** 解析有效端口池（显式非 AUTO 优先，否则按 purpose） */
export function resolveEffectivePortPool(
  pool: PortPool | null | undefined,
  purpose: PortPurpose | null | undefined,
): PortPool | null {
  if (pool && pool !== 'AUTO') return pool
  const derived = poolFromPurpose(purpose)
  return derived === 'AUTO' ? null : derived
}

export const MEDIA_OPTIONS: { value: MediaKind; label: string }[] = [
  { value: 'MPO_MPO_OS2', label: 'MPO-MPO(OS2)' },
  { value: 'MPO_MPO_OM34', label: 'MPO-MPO(OM3/OM4)' },
  { value: 'LC_LC_OM34', label: 'LC-LC(OM3/OM4)' },
  { value: 'LC_LC_OS2', label: 'LC-LC(OS2)' },
  { value: 'MPO_LC_BREAKOUT', label: 'MPO-LC 分支跳线' },
  { value: 'COPPER', label: '网线' },
  { value: 'CUSTOM_SYNC', label: '自定义类型（和本端介质同步）' },
]

export const SPEED_OPTIONS = ['1G', '10G', '25G', '40G', '100G', '400G']

export const CONNECTION_TO_LINK_ROLE: Record<string, string> = {
  ACCESS_ENDPOINT: 'server',
  BMC_ENDPOINT: 'mgmt',
  CORE_TO_ACCESS: 'uplink',
  SWITCH_INTERCONNECT: 'interconnect',
  // legacy
  UPLINK: 'uplink',
  DOWNLINK: 'downlink',
  SERVER: 'server',
  SECURITY: 'security',
  PEER: 'interconnect',
  DAD: 'interconnect',
  MGMT: 'mgmt',
}

export const CONNECTION_TO_LINK_TYPE: Record<string, string> = {
  ACCESS_ENDPOINT: 'switch_server',
  BMC_ENDPOINT: 'switch_server',
  CORE_TO_ACCESS: 'switch_switch',
  SWITCH_INTERCONNECT: 'switch_switch',
  // legacy
  UPLINK: 'switch_switch',
  DOWNLINK: 'switch_switch',
  SERVER: 'switch_server',
  SECURITY: 'switch_security',
  PEER: 'switch_switch',
  DAD: 'switch_switch',
  MGMT: 'switch_switch',
}

function defaultPurpose(conn: ConnectionType, side: 'source' | 'target'): PortPurpose {
  const c = migrateConnectionType(conn)
  // 核心/汇聚板卡口(DOWNLINK) → 接入 UPLINK
  if (c === 'CORE_TO_ACCESS') return side === 'source' ? 'DOWNLINK' : 'UPLINK'
  if (c === 'ACCESS_ENDPOINT') return side === 'source' ? 'DOWNLINK' : 'SERVER'
  if (c === 'BMC_ENDPOINT') return 'MGMT'
  if (c === 'SWITCH_INTERCONNECT') return 'PEER'
  return 'OTHER'
}

function defaultSpeedForConnection(conn: ConnectionType): string {
  const c = migrateConnectionType(conn)
  if (c === 'CORE_TO_ACCESS' || c === 'SWITCH_INTERCONNECT') return '100G'
  if (c === 'BMC_ENDPOINT') return '1G'
  return '10G'
}

function defaultRolesForConnection(conn: ConnectionType): {
  source_role: FabricRole
  target_role: FabricRole
} {
  const c = migrateConnectionType(conn)
  if (c === 'ACCESS_ENDPOINT' || c === 'BMC_ENDPOINT') {
    return { source_role: 'ACCESS', target_role: 'SERVER' }
  }
  if (c === 'SWITCH_INTERCONNECT') {
    return { source_role: 'ACCESS', target_role: 'ACCESS' }
  }
  // CORE_TO_ACCESS
  return { source_role: 'CORE', target_role: 'ACCESS' }
}

/** 连接类型切换时同步 Peer、Purpose、端口池、默认角色与速率 */
export function applyConnectionTypeSideEffects(cfg: WiringRuleConfig): WiringRuleConfig {
  const conn = migrateConnectionType(cfg.connection_type)
  cfg.connection_type = conn
  const roles = defaultRolesForConnection(conn)
  cfg.source_role = roles.source_role
  cfg.target_role = roles.target_role

  if (conn === 'SWITCH_INTERCONNECT') {
    cfg.peer_link = true
    cfg.keepalive = false
    cfg.source_port_purpose = 'PEER'
    cfg.target_port_purpose = 'PEER'
    cfg.source_port_pool = 'UPLINK'
    cfg.target_port_pool = 'UPLINK'
    cfg.speed_mode = 'EXACT'
    cfg.interconnect_scope = cfg.interconnect_scope || 'INTRA_GROUP'
    cfg.enable_peer_link = cfg.enable_peer_link ?? true
    cfg.enable_dad = cfg.enable_dad ?? true
    cfg.peer_tail_count = Math.max(1, Number(cfg.peer_tail_count) || 2)
    cfg.dad_tail_count = Math.max(1, Number(cfg.dad_tail_count) || 2)
    if (cfg.interconnect_scope === 'INTER_GROUP' && !cfg.allocation_mode) {
      cfg.allocation_mode = 'MANUAL'
    } else if (!cfg.allocation_mode) {
      cfg.allocation_mode = 'AUTO'
    }
  } else {
    cfg.peer_link = false
    cfg.keepalive = false
    cfg.source_port_purpose = defaultPurpose(conn, 'source')
    cfg.target_port_purpose = defaultPurpose(conn, 'target')
    cfg.source_port_pool = poolFromPurpose(cfg.source_port_purpose)
    cfg.target_port_pool = poolFromPurpose(cfg.target_port_purpose)
    cfg.speed_mode = conn === 'CORE_TO_ACCESS' ? 'MIN' : 'EXACT'
    if (conn === 'ACCESS_ENDPOINT') {
      cfg.target_port_policy = 'SLOT_SPREAD'
      cfg.source_port_policy = 'MIN_ASC'
    }
  }
  const speed = defaultSpeedForConnection(conn)
  cfg.speed = speed
  cfg.port_speed = speed
  return cfg
}

/** 将 source_group(s) / target_group(s) 统一为去重字符串数组 */
export function coerceWiringGroups(raw: unknown): string[] {
  const out: string[] = []
  const push = (v: unknown) => {
    const s = String(v ?? '').trim()
    if (s && !out.includes(s)) out.push(s)
  }
  if (Array.isArray(raw)) {
    for (const item of raw) push(item)
  } else if (raw != null && raw !== '') {
    push(raw)
  }
  return out
}

/** 合并复数与旧版单数字段 */
export function resolveWiringGroups(
  groups: unknown,
  legacySingular: unknown,
): string[] {
  const fromList = coerceWiringGroups(groups)
  if (fromList.length) return fromList
  return coerceWiringGroups(legacySingular)
}

export function defaultWiringConfig(): WiringRuleConfig {
  return {
    rule_category: 'CORE_AGG_TO_10G',
    scenario_template: 'CORE_TO_TEN_GIG',
    source_role: 'CORE',
    target_role: 'ACCESS',
    source_roles: ['CORE', 'AGG'],
    target_roles: ['ACCESS'],
    source_device_types: ['CORE_SWITCH', 'AGG_SWITCH'],
    target_device_types: ['ACCESS_SWITCH_10G'],
    source_groups: [],
    target_groups: [],
    source_group: null,
    target_group: null,
    source_node_ids: [],
    target_node_ids: [],
    source_port_limit_per_device: null,
    max_source_devices: null,
    source_connection_strategy: 'ROUND_ROBIN_ASC',
    target_connection_strategy: 'SLOT_ROUND_ROBIN',
    source_room_ids: [],
    target_room_ids: [],
    source_rack_start: null,
    source_rack_end: null,
    target_rack_start: null,
    target_rack_end: null,
    source_devices_per_rack: null,
    target_devices_per_rack: null,
    source_start_u: null,
    target_start_u: null,
    source_u_interval: 1,
    target_u_interval: 1,
    connection_type: 'CORE_TO_ACCESS',
    required: true,
    link_count: 2,
    min_link_count: 2,
    max_link_count: 4,
    speed: '100G',
    speed_mode: 'MIN',
    pairing: 'PER_SOURCE_TARGET',
    source_port_purpose: 'DOWNLINK',
    target_port_purpose: 'UPLINK',
    source_port_pool: 'OPTICAL',
    target_port_pool: 'UPLINK',
    port_speed: '100G',
    source_port_types: [],
    target_port_types: [],
    source_port_ids: [],
    target_port_ids: [],
    source_slot_ids: [],
    target_slot_ids: [],
    source_slot_range: null,
    target_slot_range: null,
    source_port_range: null,
    target_port_range: null,
    peer_port_range: null,
    port_allocation: 'AUTO',
    allocation_mode: 'AUTO',
    source_port_policy: 'MIN_ASC',
    target_port_policy: 'MIN_ASC',
    port_media: 'AUTO',
    port_priority: 100,
    strict_port_match: true,
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
    interconnect_scope: 'INTRA_GROUP',
    enable_peer_link: true,
    enable_dad: true,
    peer_tail_count: 2,
    dad_tail_count: 2,
    keepalive: false,
    keepalive_network: 'OOB',
    lag: true,
    lag_count: 1,
    lag_mode: 'LACP',
    media: 'MPO_MPO_OS2',
    fiber_type: 'OS2',
    connector: 'LC',
    distance_mode: 'AUTO',
    max_distance_m: 3,
    module: null,
    cable_length_mode: 'AUTO',
    cable_length_m: null,
    route_extra_m: 1.5,
    cable_slack_percent: 10,
    label_template: '{conn}-{seq:02d}',
    source_label_template: 'F:{source_device}-{source_port}\nT:{target_device}-{target_location}-{target_u}-{target_port}',
    target_label_template: 'F:{target_device}-{target_port}\nT:{source_device}-{source_location}-{source_u}-{source_port}',
    sync_media_color: true,
    cable_code_template: null,
    validate_on_apply: true,
    pairs: [],
  }
}

export function normalizeWiringConfig(raw: Record<string, unknown> | null | undefined): WiringRuleConfig {
  const base = defaultWiringConfig()
  const data = { ...base, ...(raw || {}) } as WiringRuleConfig
  // 历史规则没有场景模板标记，按自定义展示，避免误认为已套用新版核心上联模板。
  if (!raw?.scenario_template) data.scenario_template = 'CUSTOM'
  const conn = migrateConnectionType(data.connection_type as string)
  data.connection_type = conn
  const categoryMap: Record<string, RuleCategory> = {
    UPLINK: 'CORE_AGG_TO_10G',
    ACCESS: 'TEN_GIG_TO_ENDPOINT',
    SECURITY: 'TEN_GIG_TO_ENDPOINT',
    INTERCONNECT: 'SWITCH_STACK_PEER_DAD',
    BMC: 'BMC_TO_SERVER',
    CUSTOM: 'CUSTOM',
  }
  const rawCategory = String(raw?.rule_category || '')
  if (categoryMap[rawCategory]) data.rule_category = categoryMap[rawCategory]
  else if (!rawCategory) {
    const legacySpeed = String(raw?.port_speed || raw?.speed || data.port_speed || data.speed || '')
      .trim()
      .toUpperCase()
    data.rule_category = conn === 'BMC_ENDPOINT'
      ? 'BMC_TO_SERVER'
      : conn === 'SWITCH_INTERCONNECT'
        ? 'SWITCH_STACK_PEER_DAD'
        : conn === 'ACCESS_ENDPOINT'
          // 旧后端曾删除 rule_category/source_device_types；此时必须按已保存
          // 速率恢复千兆/万兆硬件分类，不能把全部 ACCESS 规则默认成万兆。
          ? legacySpeed === '1G'
            ? 'GIG_TO_ENDPOINT'
            : 'TEN_GIG_TO_ENDPOINT'
          : 'CORE_AGG_TO_10G'
  }

  if (data.max_link_count == null && data.max_links != null) {
    data.max_link_count = Number(data.max_links)
  }
  data.link_count = Math.max(1, Number(data.link_count) || 2)
  data.route_extra_m = Math.max(0, Number(data.route_extra_m) || 0)
  data.cable_slack_percent = Math.min(100, Math.max(0, Number(data.cable_slack_percent) || 0))
  if (data.min_link_count == null) data.min_link_count = data.link_count
  if (data.max_link_count == null) data.max_link_count = Math.max(data.link_count, 4)
  data.min_link_count = Math.min(Number(data.min_link_count), data.link_count)
  data.max_link_count = Math.max(Number(data.max_link_count), data.link_count)

  if (!data.source_port_purpose) data.source_port_purpose = defaultPurpose(conn, 'source')
  if (!data.target_port_purpose) data.target_port_purpose = defaultPurpose(conn, 'target')
  if (!data.port_speed && data.speed) data.port_speed = data.speed
  if (!data.source_port_pool) data.source_port_pool = poolFromPurpose(data.source_port_purpose)
  if (!data.target_port_pool) data.target_port_pool = poolFromPurpose(data.target_port_purpose)

  if (data.peer_link || isSwitchInterconnect(conn)) {
    data.peer_link = true
    data.connection_type = 'SWITCH_INTERCONNECT'
    data.source_port_purpose = data.source_port_purpose || 'PEER'
    data.target_port_purpose = data.target_port_purpose || 'PEER'
    data.source_port_pool = 'UPLINK'
    data.target_port_pool = 'UPLINK'
    data.link_count = Math.max(1, Number(data.peer_link_count) || 2)
    data.interconnect_scope = data.interconnect_scope || 'INTRA_GROUP'
    data.enable_peer_link = data.enable_peer_link ?? true
    data.enable_dad = data.enable_dad ?? true
    data.peer_tail_count = Math.max(1, Number(data.peer_tail_count) || 2)
    data.dad_tail_count = Math.max(1, Number(data.dad_tail_count) || 2)
    if (data.peer_port_range) {
      data.source_port_range = data.source_port_range || data.peer_port_range
      data.target_port_range = data.target_port_range || data.peer_port_range
    }
    if (data.peer_link_speed) {
      data.speed = data.peer_link_speed
      data.port_speed = data.peer_link_speed
    }
    if (raw?.peer_media && data.peer_media) data.media = data.peer_media
  }

  data.source_node_ids = Array.isArray(data.source_node_ids) ? data.source_node_ids : []
  data.target_node_ids = Array.isArray(data.target_node_ids) ? data.target_node_ids : []
  data.source_roles = Array.isArray(raw?.source_roles) ? data.source_roles : []
  data.target_roles = Array.isArray(raw?.target_roles) ? data.target_roles : []
  data.source_device_types = Array.isArray(raw?.source_device_types) ? (data.source_device_types || []).map(String) : []
  data.target_device_types = Array.isArray(raw?.target_device_types) ? (data.target_device_types || []).map(String) : []
  // 自动分类是设备硬件范围的权威来源。即使规则中残留了其它 ACCESS
  // 子类型，也必须按所选分类覆盖，避免千兆规则落到万兆交换机（反之亦然）。
  if (String(data.allocation_mode || 'AUTO').toUpperCase() === 'AUTO') {
    if (data.rule_category === 'TEN_GIG_TO_ENDPOINT') {
      data.source_device_types = ['ACCESS_SWITCH_10G']
      data.target_device_types = ['SERVER', 'SECURITY_DEVICE']
    } else if (data.rule_category === 'TEN_GIG_TO_GIG') {
      data.source_device_types = ['ACCESS_SWITCH_10G']
      data.target_device_types = ['ACCESS_SWITCH_1G']
    } else if (data.rule_category === 'GIG_TO_ENDPOINT') {
      data.source_device_types = ['ACCESS_SWITCH_1G']
      data.target_device_types = ['SERVER', 'SECURITY_DEVICE']
    } else if (data.rule_category === 'BMC_TO_SERVER') {
      data.source_device_types = ['BMC_SWITCH']
      data.target_device_types = ['SERVER']
    } else if (data.rule_category === 'CORE_AGG_TO_10G') {
      data.source_device_types = ['CORE_SWITCH', 'AGG_SWITCH']
      data.target_device_types = ['ACCESS_SWITCH_10G']
    } else if (data.rule_category === 'CORE_AGG_INTERCONNECT') {
      data.source_device_types = ['CORE_SWITCH', 'AGG_SWITCH']
      data.target_device_types = ['CORE_SWITCH', 'AGG_SWITCH']
    }
  }
  data.source_room_ids = Array.isArray(data.source_room_ids) ? data.source_room_ids.map(String).filter(Boolean) : []
  data.target_room_ids = Array.isArray(data.target_room_ids) ? data.target_room_ids.map(String).filter(Boolean) : []
  data.source_port_limit_per_device = data.source_port_limit_per_device == null
    ? null
    : Math.max(1, Number(data.source_port_limit_per_device) || 1)
  data.max_source_devices = data.max_source_devices == null
    ? null
    : Math.max(1, Number(data.max_source_devices) || 1)
  data.source_devices_per_rack = data.source_devices_per_rack == null ? null : Math.max(1, Number(data.source_devices_per_rack) || 1)
  data.target_devices_per_rack = data.target_devices_per_rack == null ? null : Math.max(1, Number(data.target_devices_per_rack) || 1)
  data.source_u_interval = Math.max(1, Number(data.source_u_interval) || 1)
  data.target_u_interval = Math.max(1, Number(data.target_u_interval) || 1)
  const mediaMigration: Partial<Record<MediaKind, MediaKind>> = {
    AUTO: 'CUSTOM_SYNC',
    FIBER_SM: 'LC_LC_OS2',
    FIBER_MM: 'LC_LC_OM34',
    MPO: 'MPO_MPO_OM34',
    BREAKOUT_1X4: 'MPO_LC_BREAKOUT',
    DAC: 'CUSTOM_SYNC',
    AOC: 'CUSTOM_SYNC',
  }
  data.media = mediaMigration[data.media || 'CUSTOM_SYNC'] || data.media || 'CUSTOM_SYNC'
  data.source_port_types = Array.isArray(data.source_port_types) ? data.source_port_types : []
  data.target_port_types = Array.isArray(data.target_port_types) ? data.target_port_types : []
  data.source_port_ids = Array.isArray(data.source_port_ids) ? data.source_port_ids : []
  data.target_port_ids = Array.isArray(data.target_port_ids) ? data.target_port_ids : []
  data.source_slot_ids = Array.isArray(data.source_slot_ids)
    ? data.source_slot_ids.map(Number).filter((v) => Number.isInteger(v) && v >= 0)
    : []
  data.target_slot_ids = Array.isArray(data.target_slot_ids)
    ? data.target_slot_ids.map(Number).filter((v) => Number.isInteger(v) && v >= 0)
    : []
  data.source_slot_range = data.source_slot_range ? String(data.source_slot_range).trim() : null
  data.target_slot_range = data.target_slot_range ? String(data.target_slot_range).trim() : null
  data.strict_port_match = data.strict_port_match !== false

  // allocation_mode：兼容旧 port_allocation
  const modeRaw = String(data.allocation_mode || data.port_allocation || 'AUTO').toUpperCase()
  data.allocation_mode =
    modeRaw === 'MANUAL' || modeRaw === 'HYBRID' ? (modeRaw as AllocationMode) : 'AUTO'
  data.port_allocation = 'AUTO'
  if (!data.source_port_policy) data.source_port_policy = 'MIN_ASC'
  if (!data.target_port_policy) data.target_port_policy = 'MIN_ASC'
  if (!data.port_media) data.port_media = 'AUTO'
  if (!data.speed_mode) {
    data.speed_mode =
      conn === 'CORE_TO_ACCESS' || conn === 'ACCESS_ENDPOINT' ? 'MIN' : 'EXACT'
  }

  data.source_groups = resolveWiringGroups(data.source_groups, data.source_group)
  data.target_groups = resolveWiringGroups(data.target_groups, data.target_group)
  data.source_group = data.source_groups[0] ?? null
  data.target_group = data.target_groups[0] ?? null

  // 接入→服务器：纠正连接类型与 purpose/pool/speed 不一致（残留 CORE 的 UPLINK/100G 会导致空池）
  if (conn === 'ACCESS_ENDPOINT') {
    const badTarget =
      !data.target_port_purpose ||
      data.target_port_purpose === 'UPLINK' ||
      data.target_port_purpose === 'PEER' ||
      data.target_port_purpose === 'DAD'
    if (badTarget) data.target_port_purpose = 'SERVER'
    const badSource =
      !data.source_port_purpose ||
      data.source_port_purpose === 'UPLINK' ||
      data.source_port_purpose === 'PEER' ||
      data.source_port_purpose === 'SERVER'
    if (badSource) data.source_port_purpose = 'DOWNLINK'
    if (!data.source_port_pool || data.source_port_pool === 'UPLINK') {
      data.source_port_pool = poolFromPurpose(data.source_port_purpose)
    }
    if (!data.target_port_pool || data.target_port_pool === 'UPLINK') {
      data.target_port_pool = poolFromPurpose(data.target_port_purpose)
    }
    const sp = String(data.port_speed || data.speed || '')
      .trim()
      .toUpperCase()
      .replace('_', '')
    if (!sp || sp === '40G' || sp === '100G' || sp === '400G' || sp === '40100G') {
      data.speed = '10G'
      data.port_speed = '10G'
    }
    // MIN：允许 25G NIC；避免 EXACT+错误速率把两端滤空
    data.speed_mode = 'MIN'
  }

  return data
}
