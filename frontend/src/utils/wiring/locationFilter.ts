import type { NetworkNode } from '@/api/network'
import type { WiringRuleConfig } from '@/utils/wiringTypes'
import { resolveWiringGroups } from '@/utils/wiringTypes'
import { resolveWiringDeviceType } from '@/utils/wiringDeviceType'

export type WiringEndpointSide = 'source' | 'target'

function text(value: unknown): string {
  return String(value ?? '').trim()
}

/** 接入交换机硬件分类的软匹配：按实际端口能力，避免误判导致整侧匹配为空 */
function accessSwitchSoftMatch(node: NetworkNode, deviceTypes: Set<string>): boolean {
  if (node.kind === 'server' || node.kind === 'security') return false
  const ports = node.port_layout?.ports || []
  if (!ports.length) return false
  const wants1g = deviceTypes.has('ACCESS_SWITCH_1G') || deviceTypes.has('BMC_SWITCH')
  const wants10g = deviceTypes.has('ACCESS_SWITCH_10G')
  if (wants1g) {
    return ports.some((p) => {
      const t = String(p.port_type || '').toLowerCase()
      return t === '1g' || t === 'bmc'
    })
  }
  if (wants10g) {
    return ports.some((p) =>
      ['10g', '25g', '40_100g'].includes(String(p.port_type || '').toLowerCase()),
    )
  }
  return false
}

function sideHasExplicitSelection(cfg: WiringRuleConfig, side: WiringEndpointSide): boolean {
  if (side === 'source') {
    return (
      (cfg.source_node_ids?.length || 0) > 0 ||
      resolveWiringGroups(cfg.source_groups, cfg.source_group).length > 0
    )
  }
  return (
    (cfg.target_node_ids?.length || 0) > 0 ||
    resolveWiringGroups(cfg.target_groups, cfg.target_group).length > 0
  )
}

/**
 * 将规则表中的机房/机柜/U 位条件应用到已经由角色、设备组或实例匹配出的设备。
 * 所有条件都来自实例化设备的 device 字段，避免使用画布坐标冒充物理位置。
 */
export function filterWiringNodesByLocation(
  nodes: NetworkNode[],
  cfg: WiringRuleConfig,
  side: WiringEndpointSide,
): NetworkNode[] {
  const rooms = new Set((side === 'source' ? cfg.source_room_ids : cfg.target_room_ids) || [])
  const deviceTypes = new Set((side === 'source' ? cfg.source_device_types : cfg.target_device_types) || [])
  if (side === 'source' && !deviceTypes.size) {
    if (cfg.rule_category === 'TEN_GIG_TO_ENDPOINT' || cfg.rule_category === 'TEN_GIG_TO_GIG') {
      deviceTypes.add('ACCESS_SWITCH_10G')
    } else if (cfg.rule_category === 'GIG_TO_ENDPOINT') {
      deviceTypes.add('ACCESS_SWITCH_1G')
    } else if (cfg.rule_category === 'BMC_TO_SERVER') {
      deviceTypes.add('BMC_SWITCH')
    }
  }
  // 用户已显式选择设备/设备组时，不再用硬件分类硬过滤（尊重手选）
  const skipDeviceTypeFilter = sideHasExplicitSelection(cfg, side)
  const rackStart = text(side === 'source' ? cfg.source_rack_start : cfg.target_rack_start)
  const rackEnd = text(side === 'source' ? cfg.source_rack_end : cfg.target_rack_end)
  const startU = side === 'source' ? cfg.source_start_u : cfg.target_start_u
  const interval = Math.max(1, Number(side === 'source' ? cfg.source_u_interval : cfg.target_u_interval) || 1)
  const perRack = side === 'source' ? cfg.source_devices_per_rack : cfg.target_devices_per_rack
  const collator = new Intl.Collator('zh-CN', { numeric: true, sensitivity: 'base' })

  const filtered = nodes.filter((node) => {
    if (deviceTypes.size && !skipDeviceTypeFilter) {
      const resolved = resolveWiringDeviceType(node)
      if (!deviceTypes.has(resolved) && !accessSwitchSoftMatch(node, deviceTypes)) return false
    }
    const device = node.device
    if (rooms.size) {
      const roomId = text(device?.room_id)
      const roomName = text(device?.room_name)
      if (!rooms.has(roomId) && !rooms.has(roomName)) return false
    }
    const rack = text(device?.rack_code)
    const rackSeq = Number(device?.rack_seq_no)
    const startAsSeq = Number(rackStart)
    const endAsSeq = Number(rackEnd)
    const startIsSeq = !!rackStart && Number.isFinite(startAsSeq) && String(startAsSeq) === rackStart
    const endIsSeq = !!rackEnd && Number.isFinite(endAsSeq) && String(endAsSeq) === rackEnd
    if (startIsSeq || endIsSeq) {
      if (!Number.isFinite(rackSeq)) return false
      if (startIsSeq && rackSeq < startAsSeq) return false
      if (endIsSeq && rackSeq > endAsSeq) return false
    } else {
      if (rackStart && (!rack || collator.compare(rack, rackStart) < 0)) return false
      if (rackEnd && (!rack || collator.compare(rack, rackEnd) > 0)) return false
    }
    if (startU != null) {
      const u = Number(device?.u_position)
      const first = Number(startU)
      if (!Number.isFinite(u) || u < first || (u - first) % interval !== 0) return false
    }
    return true
  })

  let result = [...filtered].sort((a, b) => {
      const rackCompare = collator.compare(text(a.device?.rack_code), text(b.device?.rack_code))
      if (rackCompare) return rackCompare
      const uCompare = Number(a.device?.u_position ?? Number.MAX_SAFE_INTEGER) - Number(b.device?.u_position ?? Number.MAX_SAFE_INTEGER)
      return uCompare || collator.compare(a.name, b.name)
    })
  if (perRack != null) {
    const limit = Math.max(1, Number(perRack) || 1)
    const rackCounts = new Map<string, number>()
    result = result.filter((node) => {
      const rackKey = text(node.device?.rack_id) || text(node.device?.rack_code) || '未上架'
      const count = rackCounts.get(rackKey) || 0
      if (count >= limit) return false
      rackCounts.set(rackKey, count + 1)
      return true
    })
  }
  if (side === 'source' && cfg.max_source_devices != null) {
    result = result.slice(0, Math.max(1, Number(cfg.max_source_devices) || 1))
  }
  return result
}
