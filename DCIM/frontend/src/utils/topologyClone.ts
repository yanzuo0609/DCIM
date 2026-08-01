import type { FramePort, NetworkNode, NetworkNodeKind, PortLayout } from '@/api/network'
import { NODE_KIND_LABELS } from '@/api/network'

/** 设备类型英文缩写，用于画布实例序号 */
export const NODE_KIND_ABBR: Record<NetworkNodeKind, string> = {
  switch: 'sw',
  server: 'srv',
  security: 'sec',
}

function clonePortLayout(layout: PortLayout | null | undefined): PortLayout | null {
  if (!layout) return null
  const copy = JSON.parse(JSON.stringify(layout)) as PortLayout
  if (copy.ports?.length) {
    copy.ports = copy.ports.map((p: FramePort) => ({
      ...p,
      peer_node_id: null,
      peer_port: null,
      peer_label: null,
      layout_locked: false,
    }))
  }
  return copy
}

function escapeRegExp(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

const ABBR_SUFFIX_RE = new RegExp(
  `[-_\\s]?(?:${Object.values(NODE_KIND_ABBR).join('|')})\\d+$`,
  'i',
)

/**
 * 取设备清单中的基础名称（去掉已有 -sw1 / -srv2 等序号后缀）。
 * 保证拖入画布后名称仍与清单一致，仅追加类型缩写序号。
 */
export function deviceNamePrefix(name: string, kind: NetworkNode['kind']): string {
  const trimmed = name.trim()
  if (!trimmed) return NODE_KIND_LABELS[kind]
  const withoutAbbr = trimmed.replace(ABBR_SUFFIX_RE, '').trim()
  if (withoutAbbr) return withoutAbbr
  return trimmed
}

export function kindAbbr(kind: NetworkNodeKind): string {
  return NODE_KIND_ABBR[kind]
}

/**
 * 命名规则：清单名-类型缩写序号，如「核心交换机-sw1」「Web服务器-srv2」
 * 序号按同清单名、同类型已有实例递增。
 */
export function nextDeviceName(nodes: NetworkNode[], template: NetworkNode): string {
  const base = deviceNamePrefix(template.name, template.kind)
  const abbr = kindAbbr(template.kind)
  const namedRe = new RegExp(`^${escapeRegExp(base)}[-_]${abbr}(\\d+)$`, 'i')

  let max = 0
  nodes.forEach((n) => {
    if (n.kind !== template.kind) return
    const m = n.name.match(namedRe)
    if (m) max = Math.max(max, Number(m[1]))
  })

  return `${base}-${abbr}${max + 1}`
}

/** 按模板克隆一台新设备并放到画布 */
export function cloneNodeOntoCanvas(
  template: NetworkNode,
  x: number,
  y: number,
  allNodes: NetworkNode[],
): NetworkNode {
  return {
    id: crypto.randomUUID(),
    topology_id: template.topology_id,
    kind: template.kind,
    name: nextDeviceName(allNodes, template),
    device_id: null,
    device_model_id: template.device_model_id ?? null,
    contract_device_name: template.contract_device_name ?? null,
    pos_x: x,
    pos_y: y,
    switch_port_count: template.switch_port_count,
    slots: template.slots ? (JSON.parse(JSON.stringify(template.slots)) as NetworkNode['slots']) : null,
    port_layout: clonePortLayout(template.port_layout),
    on_canvas: true,
    device: null,
  }
}
