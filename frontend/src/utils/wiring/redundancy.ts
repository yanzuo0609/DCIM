import type { NetworkNode } from '@/api/network'
import type { WiringPair, WiringRuleConfig } from '@/utils/wiringTypes'

/** 只有“设备上联/接入”需要跨设备冗余；BMC、Peer-link、DAD 不套用本约束。 */
export function requiresDistinctUplinkDevices(cfg: WiringRuleConfig): boolean {
  return cfg.connection_type === 'ACCESS_ENDPOINT' || cfg.connection_type === 'CORE_TO_ACCESS'
}

export function validateAutomaticUplinkDistribution(
  cfg: WiringRuleConfig,
  sourceCount: number,
): string[] {
  if (!requiresDistinctUplinkDevices(cfg)) return []
  const count = Math.max(1, Number(cfg.link_count) || 1)
  if (count <= 1) return []
  const issues: string[] = []
  if (count % 2 !== 0) issues.push(`冗余上联接口数必须为偶数，当前设置为 ${count}`)
  if (sourceCount < count) {
    issues.push(`每台设备计划 ${count} 条上联，但仅匹配到 ${sourceCount} 台上联设备；同一设备的不同接口不得重复连接同一台上联设备`)
  }
  return issues
}

export function validateManualUplinkDistribution(
  cfg: WiringRuleConfig,
  pairs: WiringPair[],
  nodes: NetworkNode[] = [],
): string[] {
  if (!requiresDistinctUplinkDevices(cfg) || !pairs.length) return []
  const byTarget = new Map<string, WiringPair[]>()
  for (const pair of pairs) {
    if (!byTarget.has(pair.target_node_id)) byTarget.set(pair.target_node_id, [])
    byTarget.get(pair.target_node_id)!.push(pair)
  }
  const issues: string[] = []
  const expected = Math.max(1, Number(cfg.link_count) || 1)
  for (const [targetId, targetPairs] of byTarget) {
    const targetName = nodes.find((node) => node.id === targetId)?.name || targetId
    if (expected > 1 && targetPairs.length !== expected) {
      issues.push(`${targetName} 计划 ${expected} 条冗余上联，手动规则实际定义 ${targetPairs.length} 条`)
    }
    if (targetPairs.length > 1 && targetPairs.length % 2 !== 0) {
      issues.push(`${targetName} 的上联接口数为 ${targetPairs.length}，冗余接口数必须为偶数`)
    }
    const sourceIds = targetPairs.map((pair) => pair.source_node_id)
    const duplicate = sourceIds.find((id, index) => sourceIds.indexOf(id) !== index)
    if (duplicate) {
      const sourceName = nodes.find((node) => node.id === duplicate)?.name || duplicate
      issues.push(`${targetName} 有多个接口同时上联到 ${sourceName}；每条冗余链路必须连接不同的上联设备`)
    }
  }
  return issues
}
