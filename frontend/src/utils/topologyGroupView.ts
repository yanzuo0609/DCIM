/**
 * 画布「按设备组简化」视图：把同组设备收成组节点，组间连线合并。
 */

import type { NetworkLink, NetworkNode } from '@/api/network'
import { nodeGroupList } from '@/utils/deviceGroups'
import type { FabricRole } from '@/utils/wiringTypes'

export interface CanvasGroupGlyph {
  /** 组名 */
  id: string
  name: string
  pos_x: number
  pos_y: number
  count: number
  role: FabricRole | null
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

/** 节点主组：多组时取第一个；无组返回 null */
export function primaryGroupName(node: NetworkNode): string | null {
  const g = nodeGroupList(node)[0]
  return g || null
}

export function buildGroupGlyphs(
  nodes: NetworkNode[],
  links: NetworkLink[],
  roleByGroup?: Map<string, FabricRole | null>,
): CanvasGroupGlyph[] {
  const onCanvas = nodes.filter((n) => n.on_canvas !== false)
  const byGroup = new Map<string, NetworkNode[]>()
  for (const n of onCanvas) {
    const g = primaryGroupName(n)
    if (!g) continue
    const list = byGroup.get(g) || []
    list.push(n)
    byGroup.set(g, list)
  }

  const memberSetByGroup = new Map<string, Set<string>>()
  for (const [g, list] of byGroup) {
    memberSetByGroup.set(g, new Set(list.map((n) => n.id)))
  }

  const glyphs: CanvasGroupGlyph[] = []
  for (const [name, members] of byGroup) {
    const ids = members.map((m) => m.id)
    const idSet = memberSetByGroup.get(name)!
    let sx = 0
    let sy = 0
    for (const m of members) {
      sx += m.pos_x
      sy += m.pos_y
    }
    const intraLinkCount = links.filter(
      (l) => idSet.has(l.source_node_id) && idSet.has(l.target_node_id),
    ).length
    glyphs.push({
      id: name,
      name,
      pos_x: Math.round(sx / members.length),
      pos_y: Math.round(sy / members.length),
      count: members.length,
      role: roleByGroup?.get(name) ?? (members[0]?.network_role as FabricRole) ?? null,
      memberIds: ids,
      intraLinkCount,
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
