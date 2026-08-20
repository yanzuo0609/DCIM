import type { NetworkNode } from '@/api/network'
import type { WiringRuleConfig } from '@/utils/wiringTypes'
import { resolveWiringDeviceType } from '@/utils/wiringDeviceType'

export type WiringEndpointSide = 'source' | 'target'

function text(value: unknown): string {
  return String(value ?? '').trim()
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
  const rackStart = text(side === 'source' ? cfg.source_rack_start : cfg.target_rack_start)
  const rackEnd = text(side === 'source' ? cfg.source_rack_end : cfg.target_rack_end)
  const startU = side === 'source' ? cfg.source_start_u : cfg.target_start_u
  const interval = Math.max(1, Number(side === 'source' ? cfg.source_u_interval : cfg.target_u_interval) || 1)
  const perRack = side === 'source' ? cfg.source_devices_per_rack : cfg.target_devices_per_rack
  const collator = new Intl.Collator('zh-CN', { numeric: true, sensitivity: 'base' })

  const filtered = nodes.filter((node) => {
    if (deviceTypes.size && !deviceTypes.has(resolveWiringDeviceType(node))) return false
    const device = node.device
    if (rooms.size) {
      const roomId = text(device?.room_id)
      const roomName = text(device?.room_name)
      if (!rooms.has(roomId) && !rooms.has(roomName)) return false
    }
    const rack = text(device?.rack_code)
    if (rackStart && (!rack || collator.compare(rack, rackStart) < 0)) return false
    if (rackEnd && (!rack || collator.compare(rack, rackEnd) > 0)) return false
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
