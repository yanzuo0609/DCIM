/**
 * 布线规则：源/目标设备匹配
 * - 手选设备与设备组为并集（可混用）
 * - 仅当未选手选、未选组时，才按角色匹配
 * - 源侧与目标侧独立，不要求「源组必须对应目标组」
 */

import type { NetworkNode } from '@/api/network'
import { nodeMatchesAnyGroup } from '@/utils/deviceGroups'
import { resolveNodeFabricRole } from '@/utils/fabricRole'
import { resolveWiringGroups } from '@/utils/wiringTypes'

export function matchWiringEndpoints(
  nodes: NetworkNode[],
  opts: {
    ids?: string[] | null
    role?: string | null
    groups?: string[] | string | null
  },
): NetworkNode[] {
  const onCanvas = nodes.filter((n) => n.on_canvas !== false)
  const idList = (opts.ids || []).map((x) => String(x)).filter(Boolean)
  const idSet = idList.length ? new Set(idList) : null
  const groupList = resolveWiringGroups(opts.groups, null)
  const role = (opts.role || '').trim() || null

  const hasIds = !!idSet
  const hasGroups = groupList.length > 0
  const hasRole = !!role

  if (!hasIds && !hasGroups && !hasRole) return []

  return onCanvas.filter((n) => {
    // 手选 ∪ 设备组：任一侧命中即可；有组/手选时不再用角色强制过滤
    if (hasIds || hasGroups) {
      const byId = hasIds && idSet!.has(n.id)
      const byGroup = hasGroups && nodeMatchesAnyGroup(n, groupList)
      return !!(byId || byGroup)
    }
    return resolveNodeFabricRole(n) === role
  })
}
