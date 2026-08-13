/**
 * 拓扑节点设备组：同一拓扑中一台设备只能属于一个父设备组
 *（父组名 + 其「组::槽位」子组引用可同时存在，不算多组）。
 */

import type { NetworkNode } from '@/api/network'

export const PARENT_GROUP_SEP = '::'

export const MULTI_PARENT_GROUP_HINT = '同一拓扑中一台设备不能同时属于多个设备组'

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

/** 目录/父组名：去掉「组::槽位」后缀 */
export function parentGroupNameOf(name: string): string {
  const raw = String(name || '').trim()
  const i = raw.indexOf(PARENT_GROUP_SEP)
  return i > 0 ? raw.slice(0, i).trim() : raw
}

/** 组名列表中的唯一父组（子组引用归到其父组） */
export function uniqueParentGroupNames(groups: string[]): string[] {
  const parents: string[] = []
  for (const g of normalizeGroupNames(groups)) {
    const p = parentGroupNameOf(g)
    if (p && !parents.includes(p)) parents.push(p)
  }
  return parents
}

export function nodeParentGroups(node: NetworkNode | null | undefined): string[] {
  return uniqueParentGroupNames(nodeGroupList(node))
}

/** 只保留某一父组及其子组引用 */
export function groupsExclusiveToParent(groups: string[], parent: string | null | undefined): string[] {
  const p = (parent || '').trim()
  if (!p) return []
  const keep = normalizeGroupNames(groups).filter((g) => parentGroupNameOf(g) === p)
  if (!keep.includes(p)) keep.unshift(p)
  return keep
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

/** 加入组；若已属于其他父组则拒绝并返回 false */
export function addNodeToGroup(node: NetworkNode, group: string): boolean {
  const g = group.trim()
  if (!g) return true
  const parent = parentGroupNameOf(g)
  const other = nodeParentGroups(node).find((p) => p !== parent)
  if (other) return false
  const next = nodeGroupList(node)
  if (!next.includes(g)) next.push(g)
  setNodeGroups(node, next)
  return true
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

/** 加载旧数据时补齐 device_groups；若误标多个父组则只保留第一个 */
export function ensureNodeGroupsShape(node: NetworkNode): void {
  const list = nodeGroupList(node)
  const parents = uniqueParentGroupNames(list)
  if (parents.length > 1) {
    setNodeGroups(node, groupsExclusiveToParent(list, parents[0]))
    return
  }
  setNodeGroups(node, list)
}

export function nodeMatchesAnyGroup(node: NetworkNode, groups: string[]): boolean {
  if (!groups.length) return true
  const mine = new Set(nodeGroupList(node))
  return groups.some((g) => mine.has(g.trim()))
}
