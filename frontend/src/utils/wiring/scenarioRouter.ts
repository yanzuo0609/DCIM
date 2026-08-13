/**
 * 场景分类决策树 — docs/18-rules_structured.md §1
 */

import {
  accessSpeedClass,
  isAccessSwitchType,
  isCoreOrAggType,
  isEndpointType,
  type WiringDeviceType,
} from '@/utils/wiringDeviceType'
import { nodeGroupList } from '@/utils/deviceGroups'
import type { RuleDeviceView, ScenarioId } from '@/utils/wiring/types'

function majorityType(devices: RuleDeviceView[]): WiringDeviceType {
  if (!devices.length) return 'OTHER'
  const counts = new Map<WiringDeviceType, number>()
  for (const d of devices) {
    counts.set(d.deviceType, (counts.get(d.deviceType) || 0) + 1)
  }
  let best: WiringDeviceType = devices[0].deviceType
  let n = 0
  for (const [t, c] of counts) {
    if (c > n) {
      best = t
      n = c
    }
  }
  return best
}

function sameGroup(sources: RuleDeviceView[], targets: RuleDeviceView[]): boolean {
  const sg = new Set(sources.flatMap((d) => nodeGroupList(d.node)).filter(Boolean))
  const tg = new Set(targets.flatMap((d) => nodeGroupList(d.node)).filter(Boolean))
  if (!sg.size || !tg.size) return false
  for (const g of sg) {
    if (g && tg.has(g)) return true
  }
  // 源目标是同一批设备（peer 模式）
  const sIds = new Set(sources.map((d) => d.node.id))
  return targets.every((t) => sIds.has(t.node.id)) && sources.length >= 2
}

export function resolveScenario(
  sources: RuleDeviceView[],
  targets: RuleDeviceView[],
  opts?: {
    peerLink?: boolean
    forceBmc?: boolean
    interconnectScope?: 'INTRA_GROUP' | 'INTER_GROUP'
  },
): ScenarioId {
  if (!sources.length || !targets.length) return 'UNSUPPORTED'

  const srcType = majorityType(sources)
  const tgtType = majorityType(targets)
  const srcN = sources.length
  const tgtN = targets.length

  if (opts?.forceBmc || srcType === 'BMC_SWITCH') return 'B1'

  if (opts?.peerLink) {
    const scope = opts.interconnectScope || 'INTRA_GROUP'
    if (scope === 'INTER_GROUP') return 'D2'
    if (sameGroup(sources, targets)) return 'D1'
    // 声明组内但匹配到不同组 → 走组间
    return 'D2'
  }

  // 核心/汇聚 → 接入
  if (isCoreOrAggType(srcType) && isAccessSwitchType(tgtType)) {
    const accessSpeed = accessSpeedClass(tgtType)
    if (accessSpeed === '1G') return 'C4'
    if (srcN === 1 && tgtN === 1) return 'C1'
    if (srcN >= 2 && tgtN === 1) return 'C2'
    if (srcN >= 1 && tgtN >= 2) return 'C3'
    return 'C1'
  }

  // 核心/汇聚 → 核心/汇聚（跨组）
  if (isCoreOrAggType(srcType) && isCoreOrAggType(tgtType)) {
    if (sameGroup(sources, targets)) return 'D1'
    return 'D2'
  }

  // 接入 → 服务器/安全
  if (isAccessSwitchType(srcType) && isEndpointType(tgtType)) {
    if (srcN === 1 && tgtN === 1) return 'A1'
    if (srcN >= 2 && tgtN === 1) return 'A2'
    if (srcN >= 1 && tgtN >= 2) return 'A3'
    return 'A1'
  }

  // 接入 ↔ 接入
  if (isAccessSwitchType(srcType) && isAccessSwitchType(tgtType)) {
    if (sameGroup(sources, targets) || (srcN >= 2 && targets.every((t) => sources.some((s) => s.node.id === t.node.id)))) {
      return 'D1'
    }
    return 'D2'
  }

  return 'UNSUPPORTED'
}

/** 供 UI 预览：根据配置匹配节点后解析场景 */
export function describeScenario(id: ScenarioId): string {
  return id
}
