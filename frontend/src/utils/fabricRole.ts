import type { NetworkDesignModel } from '@/api/networkModelDesign'
import type {
  FramePort,
  InterfaceGroupRole,
  NetworkNode,
  PortLayout,
  SwitchSubtype,
} from '@/api/network'
import type { FabricRole, PortPool, PortPurpose } from '@/utils/wiringTypes'

const SUBTYPE_TO_ROLE: Record<SwitchSubtype, FabricRole> = {
  core: 'CORE',
  aggregation: 'AGG',
  gigabit: 'ACCESS',
  ten_gigabit: 'ACCESS',
}

/** 从节点已存字段 / 面板 subtype / kind 解析网络角色 */
export function resolveNodeFabricRole(node: NetworkNode): FabricRole {
  const explicit = (node.network_role || '').trim().toUpperCase()
  if (
    explicit === 'CORE' ||
    explicit === 'AGG' ||
    explicit === 'ACCESS' ||
    explicit === 'SERVER' ||
    explicit === 'FIREWALL' ||
    explicit === 'OTHER'
  ) {
    return explicit
  }
  if (node.kind === 'server') return 'SERVER'
  if (node.kind === 'security') return 'FIREWALL'
  const sub = node.port_layout?.switch_subtype as SwitchSubtype | undefined
  if (sub && SUBTYPE_TO_ROLE[sub]) return SUBTYPE_TO_ROLE[sub]
  return 'OTHER'
}

export function inferFabricRoleFromDesignModel(model: NetworkDesignModel): FabricRole {
  const attrs = (model.attributes || {}) as Record<string, unknown>
  const raw = String(attrs.fabric_role || attrs.network_role || '').trim().toUpperCase()
  if (
    raw === 'CORE' ||
    raw === 'AGG' ||
    raw === 'ACCESS' ||
    raw === 'SERVER' ||
    raw === 'FIREWALL'
  ) {
    return raw
  }
  if (model.category === 'server') return 'SERVER'
  if (model.category === 'security') return 'FIREWALL'
  const switchRole = String(attrs.switch_role || '').trim()
  if (switchRole === 'core') return 'CORE'
  if (switchRole === 'aggregation') return 'AGG'
  if (switchRole === 'gigabit' || switchRole === 'ten_gigabit') return 'ACCESS'
  const layout = model.port_layout as { switch_subtype?: string } | null
  const sub = layout?.switch_subtype as SwitchSubtype | undefined
  if (sub && SUBTYPE_TO_ROLE[sub]) return SUBTYPE_TO_ROLE[sub]
  return 'OTHER'
}

export function inferDeviceGroupFromDesignModel(model: NetworkDesignModel): string | null {
  const attrs = (model.attributes || {}) as Record<string, unknown>
  const g = String(attrs.device_group || attrs.group || '').trim()
  return g || null
}

/** 从 slots_def 解析端口所属接口组 role（main/card/uplink/mgmt） */
export function resolvePortGroupRole(
  layoutOrNode: PortLayout | NetworkNode | null | undefined,
  port: FramePort | null | undefined,
): InterfaceGroupRole | null {
  if (!port) return null
  const layout: PortLayout | null | undefined =
    layoutOrNode && 'port_layout' in layoutOrNode
      ? layoutOrNode.port_layout
      : (layoutOrNode as PortLayout | null | undefined)
  if (!layout?.slots_def?.length || !port.group_id) return null
  for (const slot of layout.slots_def) {
    const group = slot.groups?.find((g) => g.id === port.group_id)
    if (group?.role) return group.role
  }
  return null
}

/** group.role → 默认 Port Purpose */
export function purposeFromGroupRole(
  role: InterfaceGroupRole | null | undefined,
  kind?: NetworkNode['kind'] | null,
): PortPurpose | null {
  if (!role) return null
  if (role === 'uplink') return 'UPLINK'
  if (role === 'mgmt') return 'MGMT'
  if (role === 'main' || role === 'card') {
    return kind === 'server' ? 'SERVER' : 'DOWNLINK'
  }
  return null
}

/**
 * 将模型、导入文件和人工输入中的中英文用途名称归一到规则引擎 Purpose。
 * 接入交换机的“业务接口/下联/DOWNLINK”是同一接口板；“上联/UPLINK”同理。
 */
export function normalizePortPurposeAlias(
  value: string | null | undefined,
  kind?: NetworkNode['kind'] | null,
): string | null {
  const raw = String(value || '').trim()
  if (!raw) return null
  const upper = raw.toUpperCase()
  const compact = upper.replace(/[\s_\-/]+/g, '')
  if (upper.includes('PEER') || upper.includes('堆叠')) return 'PEER'
  if (upper.includes('DAD') || upper.includes('KEEPALIVE') || upper.includes('心跳')) return 'DAD'
  if (
    upper.includes('UPLINK') ||
    compact.includes('上联') ||
    compact.includes('上连接口')
  ) return 'UPLINK'
  if (
    upper.includes('DOWNLINK') ||
    compact.includes('下联') ||
    compact.includes('业务接口') ||
    compact === '业务'
  ) {
    return kind === 'server' || kind === 'security' ? 'SERVER' : 'DOWNLINK'
  }
  if (upper.includes('MGMT') || upper.includes('BMC') || compact.includes('管理')) return 'MGMT'
  if (upper.includes('SERVER') || compact.includes('服务器')) return 'SERVER'
  return upper
}

/** 端口 purpose：显式 > group.role > group_id/zone 启发式 */
export function resolvePortPurpose(
  purpose: string | null | undefined,
  groupId: string | null | undefined,
  zoneLabel: string | null | undefined,
  groupRole?: InterfaceGroupRole | null,
  kind?: NetworkNode['kind'] | null,
): string | null {
  if (purpose) return normalizePortPurposeAlias(purpose, kind)
  const fromRole = purposeFromGroupRole(groupRole, kind)
  if (fromRole) return fromRole
  const hay = `${groupId || ''} ${zoneLabel || ''}`.toUpperCase()
  if (hay.includes('PEER') || hay.includes('PEER-LINK')) return 'PEER'
  if (hay.includes('DAD') || hay.includes('KEEPALIVE') || hay.includes('心跳')) return 'DAD'
  if (hay.includes('UPLINK') || hay.includes('上联') || hay.includes('上连接口')) return 'UPLINK'
  if (hay.includes('DOWNLINK') || hay.includes('下联') || hay.includes('业务接口')) {
    return kind === 'server' || kind === 'security' ? 'SERVER' : 'DOWNLINK'
  }
  if (hay.includes('MGMT') || hay.includes('管理')) return 'MGMT'
  if (hay.includes('SERVER') || hay.includes('业务') || hay.includes('DOWN')) return 'SERVER'
  return null
}

/** 启发式判断端口是否属于板卡光口 / 上联口（无 group.role 时的回退） */
export function inferPortPoolMembership(
  port: FramePort,
  groupRole: InterfaceGroupRole | null,
): PortPool | null {
  if (groupRole === 'uplink') return 'UPLINK'
  if (groupRole === 'mgmt') return null
  // 40/100G 与 U* 标签优先归上联池（即使 group.role=card，如核心线卡）
  const label = String(port.label || '')
  if (port.port_type === '40_100g' || /^U\d+/i.test(label)) return 'UPLINK'
  if (groupRole === 'main' || groupRole === 'card') return 'OPTICAL'
  if (port.port_type === '1g' || port.port_type === '10g') return 'OPTICAL'
  return null
}

/** 端口是否属于指定端口池（40/100G 板卡可双用：上联池 + 光口池） */
export function portBelongsToPool(
  port: FramePort,
  groupRole: InterfaceGroupRole | null,
  pool: PortPool | null,
): boolean {
  if (!pool || pool === 'AUTO') return true
  const membership = inferPortPoolMembership(port, groupRole)
  if (membership === pool) return true
  // 核心/汇聚 40/100G 线卡：下联规则仍可使用
  if (
    pool === 'OPTICAL' &&
    port.port_type === '40_100g' &&
    (groupRole === 'card' || groupRole === 'main' || groupRole === 'uplink' || !groupRole)
  ) {
    return true
  }
  return false
}

export function countModelPortPool(
  node: NetworkNode,
  pool: 'OPTICAL' | 'UPLINK',
): { total: number; free: number } {
  const ports = node.port_layout?.ports || []
  let total = 0
  let free = 0
  for (const p of ports) {
    if (p.reserved) continue
    const role = resolvePortGroupRole(node, p)
    if (!portBelongsToPool(p, role, pool)) continue
    total += 1
    if (!p.peer_node_id) free += 1
  }
  // layout 计数兜底（端口尚未展开时）
  if (!total && node.port_layout) {
    if (pool === 'OPTICAL') {
      total = Number(node.port_layout.main_port_count) || 0
    } else {
      total = Number(node.port_layout.uplink_port_count) || 0
    }
    free = total
  }
  return { total, free }
}
