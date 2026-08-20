/**
 * Node → 规则 Device 视图
 */

import type { FramePort, NetworkNode } from '@/api/network'
import {
  resolvePortGroupRole,
  resolvePortPurpose,
} from '@/utils/fabricRole'
import {
  annotatePortMediaAndInterface,
  derivePortMedia,
  normalizePortRole,
  resolveWiringDeviceType,
} from '@/utils/wiringDeviceType'
import { nodeGroupList } from '@/utils/deviceGroups'
import { isBmcPort, portSpeedLabel } from '@/utils/wiring/constraints'
import type { RuleDeviceView, RulePortView } from '@/utils/wiring/types'

function portLabelNumber(label: string): number | null {
  const s = String(label || '').trim()
  if (!s) return null
  const tail = s.match(/(?:^|[-:（(_])(\d+)\s*[)）]?\s*$/)
  if (tail) return Number(tail[1])
  const all = [...s.matchAll(/(\d+)/g)]
  if (!all.length) return null
  return Number(all[all.length - 1][1])
}

function toPortView(node: NetworkNode, port: FramePort, occupied: Set<string>): RulePortView {
  const groupRole = resolvePortGroupRole(node, port)
  let purpose = resolvePortPurpose(
    port.purpose,
    port.group_id,
    null,
    groupRole,
    node.kind,
  )
  const pt = String(port.port_type || '').toLowerCase()
  // 服务器/安全设备业务口：纠正误标 UPLINK/DOWNLINK，避免 A3 候选池被滤空
  if (
    (node.kind === 'server' || node.kind === 'security') &&
    (pt === '1g' || pt === '10g' || pt === '25g') &&
    !isBmcPort(port) &&
    groupRole !== 'mgmt'
  ) {
    const u = String(purpose || '').toUpperCase()
    if (!u || u === 'UPLINK' || u === 'DOWNLINK' || u === 'OTHER' || u === 'PEER' || u === 'DAD') {
      purpose = 'SERVER'
    }
  }
  const keyId = `${node.id}:${port.id}`
  const keyLabel = port.label ? `${node.id}:${port.label}` : ''
  // reserved 表示端口被预留给某种用途，并不等同于已经占用。
  // 历史交换机模型曾把整块 DOWNLINK 板卡都写成 reserved=true；如果在
  // 适配层直接排除，会把真实存在的 48 个业务口全部计算成 0。端口能否
  // 参与当前规则由 purpose / reserved_for 的候选池过滤负责。
  const free =
    !port.peer_node_id &&
    !occupied.has(keyId) &&
    !(keyLabel && occupied.has(keyLabel))
  return {
    port,
    slotId: port.slot_index,
    portNum: portLabelNumber(port.label),
    speed: (portSpeedLabel(port.port_type) as RulePortView['speed']) || 'OTHER',
    media:
      port.media === 'FIBER' || port.media === 'COPPER'
        ? port.media
        : derivePortMedia(port.port_type),
    role: normalizePortRole(purpose || port.purpose),
    free,
  }
}

export function adaptDevice(
  node: NetworkNode,
  occupied: Set<string>,
  groupSize = 1,
): RuleDeviceView {
  annotatePortMediaAndInterface(node.port_layout?.ports)
  const ports = (node.port_layout?.ports || []).map((p) => toPortView(node, p, occupied))
  // 同步 status：有 peer / occupied → OCCUPIED
  for (const pv of ports) {
    if (!pv.free && !pv.port.status) pv.port.status = 'OCCUPIED'
    else if (pv.free && (!pv.port.status || pv.port.status === 'OCCUPIED')) {
      pv.port.status = pv.port.reserved ? 'RESERVED' : 'AVAILABLE'
    }
  }
  return {
    node,
    deviceType: resolveWiringDeviceType(node),
    groupId: nodeGroupList(node)[0] || null,
    groupSize,
    ports,
  }
}

export function adaptDevices(nodes: NetworkNode[], occupied: Set<string>): RuleDeviceView[] {
  const byGroup = new Map<string, number>()
  for (const n of nodes) {
    const groups = nodeGroupList(n)
    if (!groups.length) {
      const solo = `_solo_${n.id}`
      byGroup.set(solo, (byGroup.get(solo) || 0) + 1)
      continue
    }
    for (const g of groups) {
      byGroup.set(g, (byGroup.get(g) || 0) + 1)
    }
  }
  return nodes.map((n) => {
    const groups = nodeGroupList(n)
    const g = groups[0] || `_solo_${n.id}`
    return adaptDevice(n, occupied, byGroup.get(g) || 1)
  })
}

export function freePorts(
  device: RuleDeviceView,
  pred: (p: RulePortView) => boolean,
): RulePortView[] {
  return device.ports
    .filter((p) => p.free && pred(p))
    .sort((a, b) => {
      const sa = a.slotId ?? 999
      const sb = b.slotId ?? 999
      if (sa !== sb) return sa - sb
      return (a.portNum ?? 0) - (b.portNum ?? 0)
    })
}

export function refreshFreeFlags(devices: RuleDeviceView[], occupied: Set<string>) {
  for (const d of devices) {
    for (const p of d.ports) {
      const key = `${d.node.id}:${p.port.id}`
      p.free = !p.port.peer_node_id && !occupied.has(key)
    }
  }
}
