import type { NetworkDesignModel } from '@/api/networkModelDesign'
import type { NetworkNode, SwitchSubtype } from '@/api/network'
import type { FabricRole } from '@/utils/wiringTypes'

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

/** 端口 purpose：显式 > group_id/role 启发式 > 连接场景默认 */
export function resolvePortPurpose(
  purpose: string | null | undefined,
  groupId: string | null | undefined,
  zoneLabel: string | null | undefined,
): string | null {
  if (purpose) return String(purpose).toUpperCase()
  const hay = `${groupId || ''} ${zoneLabel || ''}`.toUpperCase()
  if (hay.includes('PEER') || hay.includes('PEER-LINK')) return 'PEER'
  if (hay.includes('DAD') || hay.includes('KEEPALIVE') || hay.includes('心跳')) return 'DAD'
  if (hay.includes('UPLINK') || hay.includes('上联')) return 'UPLINK'
  if (hay.includes('DOWNLINK') || hay.includes('下联')) return 'DOWNLINK'
  if (hay.includes('MGMT') || hay.includes('管理')) return 'MGMT'
  if (hay.includes('SERVER') || hay.includes('业务') || hay.includes('DOWN')) return 'SERVER'
  return null
}
