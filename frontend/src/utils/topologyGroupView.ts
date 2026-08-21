/**
 * 画布「按设备组简化」视图：把同组设备收成组节点，组间连线合并。
 */

import type { NetworkLink, NetworkNode } from '@/api/network'
import { nodeParentGroups } from '@/utils/deviceGroups'
import { resolveDeviceGroupKind, type DeviceGroupKind } from '@/utils/deviceGroupVisual'
import type { FabricRole } from '@/utils/wiringTypes'

export interface CanvasGroupGlyph {
  /** 组名 */
  id: string
  name: string
  pos_x: number
  pos_y: number
  count: number
  role: FabricRole | null
  kind: DeviceGroupKind
  memberIds: string[]
  /** 组内连线数 */
  intraLinkCount: number
}

export interface CanvasGroupEdge {
  id: string
  sourceGroup: string
  targetGroup: string
  count: number
  linkType: string | null
  label: string
}

/** 节点主组：父组名；无组返回 null */
export function primaryGroupName(node: NetworkNode): string | null {
  return nodeParentGroups(node)[0] || null
}

/** 画布组图标使用的组名：父组，不含「组::子组」引用；同一设备只显示一个组 */
export function canvasGroupNamesOf(node: NetworkNode): string[] {
  return nodeParentGroups(node).slice(0, 1)
}

export function buildGroupGlyphs(
  nodes: NetworkNode[],
  links: NetworkLink[],
  roleByGroup?: Map<string, FabricRole | null>,
  positions?: Record<string, { x: number; y: number }>,
): CanvasGroupGlyph[] {
  const onCanvas = nodes.filter((n) => n.on_canvas !== false)
  const byGroup = new Map<string, NetworkNode[]>()
  const nodePrimaryGroup = new Map<string, string>()
  for (const n of onCanvas) {
    for (const g of canvasGroupNamesOf(n)) {
      const list = byGroup.get(g) || []
      list.push(n)
      byGroup.set(g, list)
      if (!nodePrimaryGroup.has(n.id)) nodePrimaryGroup.set(n.id, g)
    }
  }

  // 一次扫描连线统计组内边数，避免 O(groups × links)
  const intraByGroup = new Map<string, number>()
  for (const l of links) {
    const a = nodePrimaryGroup.get(l.source_node_id)
    const b = nodePrimaryGroup.get(l.target_node_id)
    if (!a || a !== b) continue
    intraByGroup.set(a, (intraByGroup.get(a) || 0) + 1)
  }

  const glyphs: CanvasGroupGlyph[] = []
  for (const [name, members] of byGroup) {
    const ids = members.map((m) => m.id)
    let sx = 0
    let sy = 0
    for (const m of members) {
      sx += m.pos_x
      sy += m.pos_y
    }
    const stored = positions?.[name]
    const role = roleByGroup?.get(name) ?? (members[0]?.network_role as FabricRole) ?? null
    glyphs.push({
      id: name,
      name,
      pos_x: stored ? stored.x : Math.round(sx / members.length),
      pos_y: stored ? stored.y : Math.round(sy / members.length),
      count: members.length,
      role,
      kind: resolveDeviceGroupKind({ role, members }),
      memberIds: ids,
      intraLinkCount: intraByGroup.get(name) || 0,
    })
  }
  return glyphs.sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
}

/** 组间连线（含组↔未分组设备，未分组用 node:id 作为端点键） */
export function buildGroupEdges(
  nodes: NetworkNode[],
  links: NetworkLink[],
): CanvasGroupEdge[] {
  const onCanvas = nodes.filter((n) => n.on_canvas !== false)
  const groupOf = new Map<string, string>()
  for (const n of onCanvas) {
    const g = primaryGroupName(n)
    groupOf.set(n.id, g || `node:${n.id}`)
  }

  const bag = new Map<string, CanvasGroupEdge>()
  for (const l of links) {
    const a = groupOf.get(l.source_node_id)
    const b = groupOf.get(l.target_node_id)
    if (!a || !b) continue
    if (a === b) continue // 组内线不在组间边展示
    const [s, t] = a < b ? [a, b] : [b, a]
    const key = `${s}|${t}`
    const prev = bag.get(key)
    if (prev) {
      prev.count += 1
      continue
    }
    bag.set(key, {
      id: key,
      sourceGroup: s,
      targetGroup: t,
      count: 1,
      linkType: l.link_type || null,
      label: l.label || '',
    })
  }
  return [...bag.values()]
}

export function ungroupedCanvasNodes(nodes: NetworkNode[]): NetworkNode[] {
  return nodes.filter((n) => n.on_canvas !== false && !primaryGroupName(n))
}
