import type { NetworkLink, NetworkNode } from '@/api/network'
import { nodeGroupList } from '@/utils/deviceGroups'
import { resolveNodeFabricRole } from '@/utils/fabricRole'

export interface TopologyAutoLayoutOptions {
  originX?: number
  originY?: number
  nodeGap?: number
  groupGap?: number
  layerGap?: number
  maxColumns?: number
}

const ROLE_LAYER: Record<string, number> = {
  CORE: 0,
  AGG: 1,
  ACCESS: 2,
  FIREWALL: 3,
  SERVER: 4,
  OTHER: 5,
}

function primaryGroup(node: NetworkNode): string {
  return nodeGroupList(node)[0] || '未分组'
}

function connectedWeight(node: NetworkNode, links: NetworkLink[]): number {
  let total = 0
  for (const link of links) {
    if (link.source_node_id === node.id || link.target_node_id === node.id) total += 1
  }
  return total
}

/**
 * 按 CORE → AGG → ACCESS → SECURITY → SERVER 分层，并保持设备组连续。
 * 同层优先把连接度高的设备放在中间，减少交叉线；返回位置但不直接修改节点。
 */
export function layoutTopologyByRole(
  nodes: NetworkNode[],
  links: NetworkLink[],
  options: TopologyAutoLayoutOptions = {},
): Map<string, { x: number; y: number }> {
  const originX = options.originX ?? 72
  const originY = options.originY ?? 72
  const nodeGap = options.nodeGap ?? 126
  const groupGap = options.groupGap ?? 72
  const layerGap = options.layerGap ?? 168
  const maxColumns = Math.max(4, options.maxColumns ?? 14)
  const visible = nodes.filter((node) => node.on_canvas !== false)
  const layers = new Map<number, NetworkNode[]>()

  for (const node of visible) {
    const role = resolveNodeFabricRole(node)
    const layer = ROLE_LAYER[role] ?? ROLE_LAYER.OTHER
    const bucket = layers.get(layer) || []
    bucket.push(node)
    layers.set(layer, bucket)
  }

  const result = new Map<string, { x: number; y: number }>()
  for (const [layer, layerNodes] of [...layers.entries()].sort((a, b) => a[0] - b[0])) {
    const groups = new Map<string, NetworkNode[]>()
    for (const node of layerNodes) {
      const group = primaryGroup(node)
      const bucket = groups.get(group) || []
      bucket.push(node)
      groups.set(group, bucket)
    }

    const orderedGroups = [...groups.entries()].sort(([a], [b]) => {
      if (a === '未分组') return 1
      if (b === '未分组') return -1
      return a.localeCompare(b, 'zh-CN')
    })
    const rows: Array<Array<{ node: NetworkNode; group: string; firstInGroup: boolean }>> = [[]]
    let colCount = 0
    for (const [group, members] of orderedGroups) {
      members.sort((a, b) => {
        const weight = connectedWeight(b, links) - connectedWeight(a, links)
        return weight || a.name.localeCompare(b.name, 'zh-CN')
      })
      if (colCount && colCount + members.length > maxColumns) {
        rows.push([])
        colCount = 0
      }
      members.forEach((node, index) => {
        rows[rows.length - 1].push({ node, group, firstInGroup: index === 0 && colCount > 0 })
        colCount += 1
      })
    }

    rows.forEach((row, rowIndex) => {
      const extraGaps = row.filter((item) => item.firstInGroup).length
      const width = Math.max(0, row.length - 1) * nodeGap + extraGaps * groupGap
      let x = Math.max(originX, originX + (maxColumns * nodeGap - width) / 2)
      row.forEach((item, index) => {
        if (index > 0) x += nodeGap
        if (item.firstInGroup) x += groupGap
        result.set(item.node.id, {
          x: Math.round(x),
          y: Math.round(originY + layer * layerGap + rowIndex * 112),
        })
      })
    })
  }
  return result
}