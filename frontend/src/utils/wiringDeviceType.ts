/**
 * 规则文档 Device.type 与模型/拓扑字段对齐
 * @see docs/18-rules_structured.md §0.1
 */

import type {
  FramePort,
  NetworkNode,
  PortDuplex,
  PortInterfaceType,
  PortMedia,
  PortMediaKind,
  PortRuntimeStatus,
  PortType,
  SwitchSubtype,
} from '@/api/network'
import type { NetworkDesignModel } from '@/api/networkModelDesign'
import { resolveNodeFabricRole } from '@/utils/fabricRole'
import { nodeGroupList } from '@/utils/deviceGroups'

export type WiringDeviceType =
  | 'CORE_SWITCH'
  | 'AGG_SWITCH'
  | 'ACCESS_SWITCH_10G'
  | 'ACCESS_SWITCH_1G'
  | 'BMC_SWITCH'
  | 'SERVER'
  | 'SECURITY_DEVICE'
  | 'OTHER'

export function derivePortMedia(portType: PortType | string | null | undefined): PortMedia {
  const t = String(portType || '').toLowerCase()
  if (t === '1g' || t === 'bmc' || t === 'other') return 'COPPER'
  return 'FIBER'
}

export function derivePortMediaKind(
  portType: PortType | string | null | undefined,
  media?: PortMedia | null,
): PortMediaKind {
  const t = String(portType || '').toLowerCase()
  if (t === '1g' || t === 'bmc') return 'RJ45'
  if (t === '10g') return 'SFP+'
  if (t === '25g') return 'SFP28'
  if (t === '40_100g') return 'QSFP28'
  if (media === 'COPPER') return 'RJ45'
  if (media === 'FIBER') return 'FIBER'
  return 'OTHER'
}

export function derivePortInterfaceType(
  portType: PortType | string | null | undefined,
): PortInterfaceType {
  const t = String(portType || '').toLowerCase()
  if (t === 'bmc') return 'GE_RJ45'
  if (t === '1g') return '1G_COPPER'
  if (t === '10g') return '10G_FIBER'
  if (t === '25g') return '25G_FIBER'
  if (t === '40_100g') return '100G_FIBER'
  return 'OTHER'
}

export function derivePortRuntimeStatus(port: FramePort): PortRuntimeStatus {
  if (port.status) return port.status
  if (port.peer_node_id) return 'OCCUPIED'
  if (port.reserved) return 'RESERVED'
  return 'AVAILABLE'
}

/**
 * 为端口补全 media / media_kind / duplex / status / interface_type。
 * 已有显式值不覆盖；可选 modelAttrs 提供 downlink_media / uplink_media。
 */
export function annotatePortCapabilities(
  ports: FramePort[] | null | undefined,
  modelAttrs?: Record<string, unknown> | null,
) {
  if (!ports?.length) return
  const downMedia = normalizeModelMedia(modelAttrs?.downlink_media ?? modelAttrs?.nic_media)
  const upMedia = normalizeModelMedia(modelAttrs?.uplink_media)
  for (const p of ports) {
    if (!p.media) {
      const purpose = String(p.purpose || '').toUpperCase()
      if (purpose === 'UPLINK' && upMedia) p.media = upMedia
      else if ((purpose === 'DOWNLINK' || purpose === 'SERVER') && downMedia) p.media = downMedia
      else p.media = derivePortMedia(p.port_type)
    }
    if (!p.media_kind) {
      const purpose = String(p.purpose || '').toUpperCase()
      const kindOverride =
        purpose === 'UPLINK'
          ? normalizeModelMediaKind(modelAttrs?.uplink_media)
          : purpose === 'DOWNLINK' || purpose === 'SERVER'
            ? normalizeModelMediaKind(modelAttrs?.downlink_media ?? modelAttrs?.nic_media)
            : null
      p.media_kind = kindOverride || derivePortMediaKind(p.port_type, p.media)
    }
    if (!p.duplex) p.duplex = 'FULL' as PortDuplex
    if (!p.status) p.status = derivePortRuntimeStatus(p)
    if (!p.interface_type) p.interface_type = derivePortInterfaceType(p.port_type)
    if (p.reserved && !p.reserved_for && (p.purpose === 'PEER' || p.purpose === 'DAD')) {
      p.reserved_for = p.purpose
    }
  }
}

function normalizeModelMedia(raw: unknown): PortMedia | null {
  const s = String(raw || '')
    .trim()
    .toUpperCase()
  if (s === 'FIBER' || s === 'COPPER') return s
  if (s === 'RJ45' || s === 'COPPER_CAT6') return 'COPPER'
  if (
    s === 'SFP' ||
    s === 'SFP+' ||
    s === 'SFP28' ||
    s === 'QSFP+' ||
    s === 'QSFP28' ||
    s === 'DAC' ||
    s === 'AOC' ||
    s === 'FIBER_MM' ||
    s === 'FIBER_SM'
  ) {
    return 'FIBER'
  }
  return null
}

function normalizeModelMediaKind(raw: unknown): PortMediaKind | null {
  const s = String(raw || '').trim().toUpperCase()
  const allowed: PortMediaKind[] = [
    'RJ45',
    'SFP',
    'SFP+',
    'SFP28',
    'QSFP+',
    'QSFP28',
    'DAC',
    'AOC',
    'FIBER',
    'OTHER',
  ]
  return (allowed as string[]).includes(s) ? (s as PortMediaKind) : null
}

/** @deprecated 使用 annotatePortCapabilities */
export function annotatePortMediaAndInterface(
  ports: FramePort[] | null | undefined,
  modelAttrs?: Record<string, unknown> | null,
) {
  annotatePortCapabilities(ports, modelAttrs)
}

/** 规则文档 PortRole ↔ 现有 purpose 归一 */
export function normalizePortRole(purpose: string | null | undefined): string | null {
  if (!purpose) return null
  const u = String(purpose).toUpperCase()
  if (u === 'SERVER_NIC' || u === 'SERVER') return 'SERVER'
  if (u === 'BMC' || u === 'MGMT') return 'MGMT'
  if (u === 'PEER_LINK' || u === 'PEER') return 'PEER'
  return u
}

export function isAccessSwitchType(t: WiringDeviceType): boolean {
  return t === 'ACCESS_SWITCH_10G' || t === 'ACCESS_SWITCH_1G' || t === 'BMC_SWITCH'
}

export function isCoreOrAggType(t: WiringDeviceType): boolean {
  return t === 'CORE_SWITCH' || t === 'AGG_SWITCH'
}

export function isEndpointType(t: WiringDeviceType): boolean {
  return t === 'SERVER' || t === 'SECURITY_DEVICE'
}

export function accessSpeedClass(t: WiringDeviceType): '10G' | '1G' | null {
  if (t === 'ACCESS_SWITCH_10G') return '10G'
  if (t === 'ACCESS_SWITCH_1G' || t === 'BMC_SWITCH') return '1G'
  return null
}

function switchSubtypeOf(node: NetworkNode): SwitchSubtype | null {
  const sub = node.port_layout?.switch_subtype
  if (sub === 'core' || sub === 'aggregation' || sub === 'ten_gigabit' || sub === 'gigabit') {
    return sub
  }
  return null
}

export function resolveWiringDeviceType(node: NetworkNode): WiringDeviceType {
  if (node.kind === 'server') return 'SERVER'
  if (node.kind === 'security') return 'SECURITY_DEVICE'

  if (node.is_bmc_switch) return 'BMC_SWITCH'

  const role = resolveNodeFabricRole(node)
  const sub = switchSubtypeOf(node)

  if (role === 'CORE' || sub === 'core') return 'CORE_SWITCH'
  if (role === 'AGG' || sub === 'aggregation') return 'AGG_SWITCH'
  if (sub === 'ten_gigabit') return 'ACCESS_SWITCH_10G'
  if (sub === 'gigabit') return node.is_bmc_switch ? 'BMC_SWITCH' : 'ACCESS_SWITCH_1G'
  if (role === 'ACCESS') {
    // 无 subtype 时按下行口类型猜测
    const ports = node.port_layout?.ports || []
    const has10 = ports.some((p) => p.port_type === '10g' && (p.purpose === 'DOWNLINK' || !p.purpose))
    return has10 ? 'ACCESS_SWITCH_10G' : 'ACCESS_SWITCH_1G'
  }
  if (role === 'FIREWALL') return 'SECURITY_DEVICE'
  if (role === 'SERVER') return 'SERVER'
  return 'OTHER'
}

export function isBmcSwitchFromDesignModel(model: NetworkDesignModel): boolean {
  const attrs = (model.attributes || {}) as Record<string, unknown>
  return !!attrs.is_bmc_switch
}

/**
 * 标记组内互联保留口：UPLINK/DOWNLINK 池尾部各 2 口 → PEER + DAD + reserved
 * @see docs/18-rules_structured.md §5.1 D1
 */
export function markReservedPeerDadPorts(node: NetworkNode): void {
  const ports = node.port_layout?.ports
  if (!ports?.length) return

  const markTail = (pool: FramePort[], roles: Array<'PEER' | 'DAD'>) => {
    if (pool.length < roles.length) return
    const sorted = [...pool].sort((a, b) => {
      const na = Number(String(a.label).replace(/\D/g, '')) || 0
      const nb = Number(String(b.label).replace(/\D/g, '')) || 0
      return na - nb
    })
    const tail = sorted.slice(-roles.length)
    tail.forEach((p, i) => {
      p.purpose = roles[i]
      p.reserved = true
    })
  }

  const uplink = ports.filter(
    (p) =>
      !p.peer_node_id &&
      (p.purpose === 'UPLINK' || /^U\d+/i.test(String(p.label || '')) || p.port_type === '40_100g'),
  )
  const downlink = ports.filter(
    (p) =>
      !p.peer_node_id &&
      !p.reserved &&
      (p.purpose === 'DOWNLINK' ||
        ((p.port_type === '1g' || p.port_type === '10g') && p.purpose !== 'UPLINK' && p.purpose !== 'MGMT')),
  )

  // 仅当尚未标记 PEER/DAD 时写入，避免重复打标破坏已有连线口
  const already = ports.filter((p) => p.purpose === 'PEER' || p.purpose === 'DAD')
  if (already.length >= 2) return

  markTail(
    uplink.filter((p) => p.purpose !== 'PEER' && p.purpose !== 'DAD'),
    ['PEER', 'DAD'],
  )
  markTail(
    downlink.filter((p) => p.purpose !== 'PEER' && p.purpose !== 'DAD' && !p.reserved),
    ['PEER', 'DAD'],
  )
}

/** 批量为同组交换机标记 D1 保留口（组内 ≥2 台时） */
export function markReservedPeerDadForGroups(nodes: NetworkNode[]): void {
  const byGroup = new Map<string, NetworkNode[]>()
  for (const n of nodes) {
    if (n.on_canvas === false) continue
    if (n.kind !== 'switch') continue
    for (const g of nodeGroupList(n)) {
      if (!byGroup.has(g)) byGroup.set(g, [])
      byGroup.get(g)!.push(n)
    }
  }
  for (const list of byGroup.values()) {
    if (list.length < 2) continue
    for (const n of list) markReservedPeerDadPorts(n)
  }
}
