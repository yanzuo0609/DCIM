import type { NetworkNode, NetworkNodeKind } from '@/api/network'
import type { FabricRole } from '@/utils/wiringTypes'

/** 设备组视觉类型 */
export type DeviceGroupKind = 'core' | 'aggregation' | 'access' | 'server' | 'security' | 'mixed'

export const DEVICE_GROUP_KIND_LABELS: Record<DeviceGroupKind, string> = {
  core: '核心交换机组',
  aggregation: '汇聚交换机组',
  access: '接入交换机组',
  server: '服务器组',
  security: '安全设备组',
  mixed: '混合组',
}

export function groupKindFromRole(role: FabricRole | null | undefined): DeviceGroupKind {
  if (role === 'CORE') return 'core'
  if (role === 'AGG') return 'aggregation'
  if (role === 'ACCESS') return 'access'
  if (role === 'SERVER') return 'server'
  if (role === 'FIREWALL') return 'security'
  return 'mixed'
}

export function groupKindLabel(role: FabricRole | null | undefined): string {
  return DEVICE_GROUP_KIND_LABELS[groupKindFromRole(role)]
}

export function groupKindFromNode(
  node: Pick<NetworkNode, 'kind' | 'network_role'> & {
    port_layout?: { switch_subtype?: string | null } | null
  },
): DeviceGroupKind {
  const role = node.network_role as FabricRole | null | undefined
  if (role && role !== 'OTHER') return groupKindFromRole(role)
  if (node.kind === 'server') return 'server'
  if (node.kind === 'security') return 'security'
  const subtype = node.port_layout?.switch_subtype
  if (subtype === 'core') return 'core'
  if (subtype === 'aggregation') return 'aggregation'
  return 'access'
}

export function resolveDeviceGroupKind(opts: {
  role?: FabricRole | null
  slotRoles?: Array<FabricRole | null | undefined>
  members?: Array<
    Pick<NetworkNode, 'kind' | 'network_role'> & {
      port_layout?: { switch_subtype?: string | null } | null
    }
  >
}): DeviceGroupKind {
  if (opts.members?.length) {
    const kinds = new Set(opts.members.map(groupKindFromNode))
    if (kinds.size > 1) return 'mixed'
    if (kinds.size === 1) return [...kinds][0]
  }
  const slotKinds = new Set<DeviceGroupKind>()
  for (const role of opts.slotRoles || []) {
    if (role) slotKinds.add(groupKindFromRole(role))
  }
  if (opts.role) slotKinds.add(groupKindFromRole(opts.role))
  if (slotKinds.size > 1) return 'mixed'
  if (slotKinds.size === 1) return [...slotKinds][0]
  return groupKindFromRole(opts.role)
}

export function nodeKindForGroupRole(role: FabricRole | null | undefined): NetworkNodeKind {
  const kind = groupKindFromRole(role)
  if (kind === 'server') return 'server'
  if (kind === 'security') return 'security'
  return 'switch'
}

/** 网格排布：在原点附近展开 count 台设备 */
export function layoutGroupGrid(
  count: number,
  originX: number,
  originY: number,
  opts?: { cellW?: number; cellH?: number; cols?: number },
): Array<{ x: number; y: number }> {
  const n = Math.max(0, Math.floor(count))
  if (!n) return []
  const cellW = opts?.cellW ?? 110
  const cellH = opts?.cellH ?? 118
  const cols = Math.max(1, opts?.cols ?? Math.min(12, Math.ceil(Math.sqrt(n))))
  const out: Array<{ x: number; y: number }> = []
  for (let i = 0; i < n; i++) {
    const col = i % cols
    const row = Math.floor(i / cols)
    out.push({
      x: Math.max(0, originX + col * cellW),
      y: Math.max(0, originY + row * cellH),
    })
  }
  return out
}
