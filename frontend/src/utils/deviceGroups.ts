/**
 * 拓扑节点设备组：支持一台设备归属多个组
 */

import type { NetworkNode } from '@/api/network'

/** 归一化组名列表（去空、去重、保序） */
export function normalizeGroupNames(raw: unknown): string[] {
  const list: string[] = []
  const push = (v: unknown) => {
    const s = String(v ?? '').trim()
    if (s && !list.includes(s)) list.push(s)
  }
  if (Array.isArray(raw)) {
    for (const item of raw) push(item)
  } else if (typeof raw === 'string' && raw.trim()) {
    // 兼容历史：逗号/分号分隔，或单组名
    for (const part of raw.split(/[,;|/]/)) push(part)
  }
  return list
}

/** 读取节点所属全部组（device_groups 优先，回退 device_group） */
export function nodeGroupList(node: NetworkNode | null | undefined): string[] {
  if (!node) return []
  const fromArr = normalizeGroupNames(node.device_groups)
  if (fromArr.length) return fromArr
  return normalizeGroupNames(node.device_group)
}

export function nodeInGroup(node: NetworkNode, group: string): boolean {
  const g = group.trim()
  if (!g) return false
  return nodeGroupList(node).includes(g)
}

/** 列出组内成员 */
export function listGroupMembers<T extends NetworkNode>(
  nodes: T[],
  group: string,
  opts?: { canvasOnly?: boolean },
): T[] {
  const g = group.trim()
  if (!g) return []
  return nodes.filter((n) => {
    if (opts?.canvasOnly && n.on_canvas === false) return false
    return nodeInGroup(n, g)
  })
}

export function countGroupMembers(
  nodes: NetworkNode[],
  group: string,
  opts?: { canvasOnly?: boolean },
): number {
  return listGroupMembers(nodes, group, opts).length
}

/** 写回多组，并同步遗留字段 device_group（首个组，便于旧逻辑/短展示） */
export function setNodeGroups(node: NetworkNode, groups: string[]): void {
  const next = normalizeGroupNames(groups)
  node.device_groups = next.length ? next : null
  node.device_group = next[0] || null
}

export function addNodeToGroup(node: NetworkNode, group: string): void {
  const g = group.trim()
  if (!g) return
  const next = nodeGroupList(node)
  if (!next.includes(g)) next.push(g)
  setNodeGroups(node, next)
}

export function removeNodeFromGroup(node: NetworkNode, group: string): void {
  const g = group.trim()
  if (!g) return
  setNodeGroups(
    node,
    nodeGroupList(node).filter((x) => x !== g),
  )
}

export function renameNodeGroup(node: NetworkNode, from: string, to: string): void {
  const a = from.trim()
  const b = to.trim()
  if (!a || !b || a === b) return
  const sep = '::'
  const list = nodeGroupList(node).map((g) => {
    if (g === a) return b
    if (g.startsWith(a + sep)) return b + g.slice(a.length)
    return g
  })
  setNodeGroups(node, list)
}

/** 加载旧数据时补齐 device_groups */
export function ensureNodeGroupsShape(node: NetworkNode): void {
  setNodeGroups(node, nodeGroupList(node))
}

export function nodeMatchesAnyGroup(node: NetworkNode, groups: string[]): boolean {
  if (!groups.length) return true
  const mine = new Set(nodeGroupList(node))
  return groups.some((g) => mine.has(g.trim()))
}
