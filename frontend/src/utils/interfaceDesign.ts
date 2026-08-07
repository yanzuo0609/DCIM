import {
  CABLE_TYPE_LABELS,
  INTERFACE_CLASS_LABELS,
  LINK_ROLE_LABELS,
  LINK_TYPE_LABELS,
  NODE_KIND_LABELS,
  PORT_TYPE_LABELS,
  SWITCH_ROLE_TIER,
  SWITCH_SUBTYPE_LABELS,
  type CableType,
  type FramePort,
  type InterfaceClass,
  type NetworkLink,
  type NetworkLinkRole,
  type NetworkLinkType,
  type NetworkNode,
  type PortType,
  type SwitchSubtype,
} from '@/api/network'

export interface InterfaceDesignRow {
  id: string
  link: NetworkLink
  linkType: NetworkLinkType
  linkRole: NetworkLinkRole
  linkRoleLabel: string
  linkTypeLabel: string
  /** 本端 */
  sourceKind: string
  sourceName: string
  sourceLocation: string
  sourceU: string
  sourcePortId: string
  sourcePortLabel: string
  /** 对端 */
  targetKind: string
  targetName: string
  targetLocation: string
  targetU: string
  targetPortId: string
  targetPortLabel: string
  interfaceClass: InterfaceClass
  interfaceClassLabel: string
  cableType: CableType
  cableTypeLabel: string
  sourceLabel: string
  targetLabel: string
  remark: string
  connectionType: string
  speed: string
  lagGroup: string
  redundancyPath: string
  media: string
  module: string
  cableLengthM: string
  wiringRuleId: string
}

function switchSubtype(node: NetworkNode | undefined): SwitchSubtype | null {
  const raw = node?.port_layout?.switch_subtype
  if (raw === 'gigabit' || raw === 'ten_gigabit' || raw === 'aggregation' || raw === 'core') return raw
  return null
}

export function nodeKindLabel(node: NetworkNode | undefined): string {
  if (!node) return '-'
  if (node.kind === 'switch') {
    const sub = switchSubtype(node)
    if (sub) return SWITCH_SUBTYPE_LABELS[sub]
  }
  return NODE_KIND_LABELS[node.kind]
}

export function nodeLocationOnly(node: NetworkNode | undefined): string {
  if (!node?.device) return '-'
  const parts: string[] = []
  if (node.device.room_name) parts.push(node.device.room_name)
  if (node.device.rack_code) parts.push(node.device.rack_code)
  return parts.length ? parts.join(' / ') : '-'
}

export function nodeUPosition(node: NetworkNode | undefined): string {
  if (node?.device?.u_position != null) return String(node.device.u_position)
  return '-'
}

export function findPort(node: NetworkNode | undefined, portId: string): FramePort | null {
  return node?.port_layout?.ports?.find((p) => p.id === portId) || null
}

export function portDisplayLabel(node: NetworkNode | undefined, portId: string): string {
  const p = findPort(node, portId)
  if (!p) return portId
  const type = PORT_TYPE_LABELS[p.port_type] || p.port_type
  if (p.label && p.label !== p.id) return `${p.label}（${p.id} · ${type}）`
  return `${p.id}（${type}）`
}

export function switchTier(node: NetworkNode | undefined): number {
  const sub = switchSubtype(node)
  if (!sub) return 0
  return SWITCH_ROLE_TIER[sub]
}

/** 根据两端设备推断连线场景角色 */
export function inferLinkRole(
  linkType: NetworkLinkType,
  source: NetworkNode | undefined,
  target: NetworkNode | undefined,
): NetworkLinkRole {
  if (linkType === 'switch_server') return 'server'
  if (linkType === 'switch_security') return 'security'
  const st = switchTier(source)
  const tt = switchTier(target)
  if (st && tt) {
    if (st < tt) return 'uplink'
    if (st > tt) return 'downlink'
  }
  return 'interconnect'
}

export function inferInterfaceClass(portType: PortType | undefined): InterfaceClass {
  if (!portType) return 'other'
  if (portType === '1g') return 'electric'
  if (portType === '10g' || portType === '40_100g') return 'optical'
  if (portType === 'bmc') return 'electric'
  return 'other'
}

/** 按对端接口速率联动：万兆→光口+多模光纤；千兆→电口+超六类铜缆 */
export function inferMediaFromTargetPort(portType: PortType | undefined): {
  interface_class: InterfaceClass
  cable_type: CableType
} {
  if (portType === '10g') {
    return { interface_class: 'optical', cable_type: 'fiber_mm' }
  }
  if (portType === '1g') {
    return { interface_class: 'electric', cable_type: 'copper_cat6' }
  }
  if (portType === '40_100g') {
    return { interface_class: 'optical', cable_type: 'fiber_sm' }
  }
  if (portType === 'bmc') {
    return { interface_class: 'electric', cable_type: 'copper_cat6' }
  }
  return { interface_class: 'other', cable_type: 'other' }
}

export function inferCableType(
  sourceType: PortType | undefined,
  targetType: PortType | undefined,
  linkRole: NetworkLinkRole,
): CableType {
  // 优先按对端接口联动
  if (targetType === '10g') return 'fiber_mm'
  if (targetType === '1g') return 'copper_cat6'
  const types = [sourceType, targetType].filter(Boolean) as PortType[]
  if (types.includes('40_100g')) return linkRole === 'interconnect' ? 'dac' : 'fiber_sm'
  if (types.includes('10g')) return 'fiber_mm'
  if (types.every((t) => t === '1g') || types.includes('1g')) return 'copper_cat6'
  return 'other'
}

/**
 * 按 Excel 习惯根据两端信息生成标签：
 * 设备名称-位置-U位-接口
 */
export function buildEndLabel(parts: {
  name: string
  location: string
  u: string
  port: string
}): string {
  const segs = [parts.name]
  if (parts.location && parts.location !== '-') segs.push(parts.location.replace(/\s*\/\s*/g, ''))
  if (parts.u && parts.u !== '-') segs.push(`${parts.u}U`)
  if (parts.port) segs.push(parts.port)
  return segs.join('-')
}

export function buildLinkLabels(
  source: NetworkNode | undefined,
  target: NetworkNode | undefined,
  sourcePortId: string,
  targetPortId: string,
): { source_label: string; target_label: string } {
  const sp = findPort(source, sourcePortId)
  const tp = findPort(target, targetPortId)
  return {
    source_label: buildEndLabel({
      name: managedDeviceDisplayName(source),
      location: nodeLocationOnly(source),
      u: nodeUPosition(source),
      port: sp?.label || sourcePortId,
    }),
    target_label: buildEndLabel({
      name: managedDeviceDisplayName(target),
      location: nodeLocationOnly(target),
      u: nodeUPosition(target),
      port: tp?.label || targetPortId,
    }),
  }
}

export function enrichLinkFields(
  linkType: NetworkLinkType,
  source: NetworkNode | undefined,
  target: NetworkNode | undefined,
  sourcePortId: string,
  targetPortId: string,
): {
  link_role: NetworkLinkRole
  interface_class: InterfaceClass
  cable_type: CableType
  source_label: string
  target_label: string
} {
  const sp = findPort(source, sourcePortId)
  const tp = findPort(target, targetPortId)
  const link_role = inferLinkRole(linkType, source, target)
  // 优先按对端接口速率联动接口类与线缆
  const fromTarget = inferMediaFromTargetPort(tp?.port_type)
  const interface_class =
    tp?.port_type != null
      ? fromTarget.interface_class
      : inferInterfaceClass(sp?.port_type || tp?.port_type)
  const cable_type =
    tp?.port_type != null
      ? fromTarget.cable_type
      : inferCableType(sp?.port_type, tp?.port_type, link_role)
  const labels = buildLinkLabels(source, target, sourcePortId, targetPortId)
  return { link_role, interface_class, cable_type, ...labels }
}

export function toInterfaceDesignRow(
  link: NetworkLink,
  nodes: NetworkNode[],
): InterfaceDesignRow {
  const source = nodes.find((n) => n.id === link.source_node_id)
  const target = nodes.find((n) => n.id === link.target_node_id)
  const sp = findPort(source, link.source_port)
  const tp = findPort(target, link.target_port)
  const linkRole = (link.link_role as NetworkLinkRole) || inferLinkRole(link.link_type, source, target)
  const interfaceClass =
    (link.interface_class as InterfaceClass) ||
    inferInterfaceClass(sp?.port_type || tp?.port_type)
  const cableType =
    (link.cable_type as CableType) ||
    inferCableType(sp?.port_type, tp?.port_type, linkRole)
  const labels =
    link.source_label && link.target_label
      ? { source_label: link.source_label, target_label: link.target_label }
      : buildLinkLabels(source, target, link.source_port, link.target_port)

  return {
    id: link.id,
    link,
    linkType: link.link_type,
    linkRole,
    linkRoleLabel: LINK_ROLE_LABELS[linkRole] || linkRole,
    linkTypeLabel: LINK_TYPE_LABELS[link.link_type] || link.link_type,
    sourceKind: nodeKindLabel(source),
    sourceName: managedDeviceDisplayName(source),
    sourceLocation: nodeLocationOnly(source),
    sourceU: nodeUPosition(source),
    sourcePortId: link.source_port,
    sourcePortLabel: portDisplayLabel(source, link.source_port),
    targetKind: nodeKindLabel(target),
    targetName: managedDeviceDisplayName(target),
    targetLocation: nodeLocationOnly(target),
    targetU: nodeUPosition(target),
    targetPortId: link.target_port,
    targetPortLabel: portDisplayLabel(target, link.target_port),
    interfaceClass,
    interfaceClassLabel: INTERFACE_CLASS_LABELS[interfaceClass] || interfaceClass,
    cableType,
    cableTypeLabel: CABLE_TYPE_LABELS[cableType] || cableType,
    sourceLabel: labels.source_label,
    targetLabel: labels.target_label,
    remark: link.label || '',
    connectionType: link.connection_type || '',
    speed: link.speed || '',
    lagGroup: link.lag_group || '',
    redundancyPath: link.redundancy_path || '',
    media: link.media || '',
    module: link.module || '',
    cableLengthM: link.cable_length_m != null ? String(link.cable_length_m) : '',
    wiringRuleId: link.wiring_rule_id || '',
  }
}

export function preferPortsForLink(
  source: NetworkNode,
  target: NetworkNode,
  linkType: NetworkLinkType,
  freeSource: { id: string }[],
  freeTarget: { id: string }[],
): { sourcePortId: string; targetPortId: string } {
  const role = inferLinkRole(linkType, source, target)
  const sourcePorts = source.port_layout?.ports || []
  const targetPorts = target.port_layout?.ports || []

  const pick = (
    free: { id: string }[],
    all: FramePort[],
    preferRole: string | null,
    preferType: PortType | null,
  ) => {
    const freeSet = new Set(free.map((p) => p.id))
    const candidates = all.filter((p) => freeSet.has(p.id))
    if (preferRole) {
      const byRole = candidates.filter((p) => {
        const slot = source.port_layout?.slots_def?.[p.slot_index ?? -1]
        // role stored on groups; match port via group_id
        const group = slot?.groups?.find((g) => g.id === p.group_id)
        return group?.role === preferRole
      })
      if (byRole.length) return byRole[0].id
    }
    if (preferType) {
      const byType = candidates.filter((p) => p.port_type === preferType)
      if (byType.length) return byType[0].id
    }
    return free[0]?.id || ''
  }

  if (role === 'uplink') {
    return {
      sourcePortId: pick(freeSource, sourcePorts, 'uplink', '10g'),
      targetPortId: pick(freeTarget, targetPorts, 'main', null),
    }
  }
  if (role === 'server') {
    const sw = source.kind === 'switch' ? source : target
    const srv = source.kind === 'server' ? source : target
    const swFree = source.kind === 'switch' ? freeSource : freeTarget
    const srvFree = source.kind === 'server' ? freeSource : freeTarget
    const swPorts = sw.port_layout?.ports || []
    const srvPorts = srv.port_layout?.ports || []
    const mainType =
      switchSubtype(sw) === 'gigabit' ? ('1g' as PortType) : ('10g' as PortType)
    const swPort = pick(swFree, swPorts, 'main', mainType)
    const srvPort = pick(srvFree, srvPorts, null, mainType)
    if (source.kind === 'switch') {
      return { sourcePortId: swPort, targetPortId: srvPort }
    }
    return { sourcePortId: srvPort, targetPortId: swPort }
  }
  return {
    sourcePortId: freeSource[0]?.id || '',
    targetPortId: freeTarget[0]?.id || '',
  }
}

/** 接线说明：按交换机类型提示 */
export function wiringHint(subtype: SwitchSubtype | null | undefined): string {
  switch (subtype) {
    case 'gigabit':
      return '千兆：业务口 Cat6 下联服务器；上联口 10G 光/DAC 至汇聚或核心'
    case 'ten_gigabit':
      return '万兆：业务口 10G 下联；上联口 40/100G 至汇聚或核心'
    case 'aggregation':
      return '汇聚：下联接入交换机（10G）；上联核心（40/100G）；同层可互联'
    case 'core':
      return '核心：线卡互联汇聚/核心；按板卡速率选择光纤或 DAC'
    default:
      return '请先定义交换机角色（千兆/万兆/汇聚/核心）'
  }
}

export function portTypeLabel(t: PortType | undefined): string {
  if (!t) return '-'
  return PORT_TYPE_LABELS[t] || t
}

/** 设备管理类型编码（与 seed DEFAULT_DEVICE_TYPES 对齐） */
export type DeviceMgmtTypeCode = 'network' | 'compute' | 'storage' | 'security'

/** 连线端过滤：按设备管理类型，any=全部已关联类型 */
export type LinkEndTypeFilter = DeviceMgmtTypeCode | 'any'

export function linkEndTypeFilters(
  linkType: NetworkLinkType,
  linkRole?: NetworkLinkRole | null,
): { source: LinkEndTypeFilter; target: LinkEndTypeFilter; preferSourceNetwork?: boolean } {
  // 交换机→服务器：本端交换机(网络)，对端服务器(计算)
  if (linkType === 'switch_server' || linkRole === 'server') {
    return { source: 'network', target: 'compute' }
  }
  // 交换机→安全：本端交换机，对端安全设备
  if (linkType === 'switch_security' || linkRole === 'security') {
    return { source: 'network', target: 'security' }
  }
  // 交换机→交换机（上联/互联/下联）：两端均为交换机
  return { source: 'network', target: 'network' }
}

/** @deprecated 兼容旧名 */
export type LinkEndKindFilter = LinkEndTypeFilter
export function linkEndKindFilters(
  linkType: NetworkLinkType,
  linkRole?: NetworkLinkRole | null,
) {
  return linkEndTypeFilters(linkType, linkRole)
}

export function resolveDeviceTypeCode(node: NetworkNode): string | null {
  const code = node.device?.device_type_code?.trim().toLowerCase()
  if (code) return code
  const name = node.device?.device_type_name?.trim()
  if (name) {
    if (name === '网络' || /network|交换机|路由/i.test(name)) return 'network'
    if (name === '计算' || /compute|服务器/i.test(name)) return 'compute'
    if (name === '存储' || /storage|存储/i.test(name)) return 'storage'
    if (name === '安全' || /security|防火|安全/i.test(name)) return 'security'
  }
  // 按拓扑 kind 兜底，保证筛选/回退可用
  if (node.kind === 'switch') return 'network'
  if (node.kind === 'server') return 'compute'
  if (node.kind === 'security') return 'security'
  return null
}

export function filterToTopologyKind(filter: LinkEndTypeFilter): NetworkNode['kind'] | null {
  if (filter === 'network') return 'switch'
  if (filter === 'compute') return 'server'
  if (filter === 'security') return 'security'
  return null
}

export function nodeMatchesTypeFilter(node: NetworkNode, filter: LinkEndTypeFilter): boolean {
  if (filter === 'any') return true
  return resolveDeviceTypeCode(node) === filter
}

/** 设备管理显示名（合同设备名称优先） */
export function managedDeviceDisplayName(node: NetworkNode | undefined): string {
  if (!node) return '-'
  return (node.device?.name || node.name || node.device?.hostname || '-').trim() || '-'
}

export function managedDeviceModelName(node: NetworkNode | undefined): string {
  return node?.device?.device_model_name?.trim() || '-'
}

/**
 * 连线端候选设备：
 * 1) 优先：已关联台账且类型匹配
 * 2) 若无：按拓扑 kind 回退（避免下拉 No Data），未绑定台账的项仍可选但会提示
 */
export function filterBoundNodesForEnd(
  nodes: NetworkNode[],
  filter: LinkEndTypeFilter,
  opts?: {
    includeId?: string | null
    requireBound?: boolean
    preferNetworkFirst?: boolean
    allowKindFallback?: boolean
  },
): NetworkNode[] {
  const allowKindFallback = opts?.allowKindFallback !== false
  const requireBound = opts?.requireBound === true

  const boundMatched = nodes.filter((n) => {
    if (opts?.includeId && n.id === opts.includeId) return true
    if (!n.device_id) return false
    return nodeMatchesTypeFilter(n, filter)
  })

  let list = boundMatched
  if (!list.length && !requireBound && allowKindFallback) {
    const kind = filterToTopologyKind(filter)
    list = nodes.filter((n) => {
      if (opts?.includeId && n.id === opts.includeId) return true
      if (filter === 'any' || !kind) return true
      return n.kind === kind
    })
  }

  if (!opts?.preferNetworkFirst) return list
  return [...list].sort((a, b) => {
    const ab = a.device_id ? 0 : 1
    const bb = b.device_id ? 0 : 1
    if (ab !== bb) return ab - bb
    const an = resolveDeviceTypeCode(a) === 'network' ? 0 : 1
    const bn = resolveDeviceTypeCode(b) === 'network' ? 0 : 1
    return an - bn
  })
}

export function pickDefaultSourceNode(
  candidates: NetworkNode[],
  preferNetwork: boolean,
): NetworkNode | undefined {
  if (!candidates.length) return undefined
  if (preferNetwork) {
    const net = candidates.find((n) => resolveDeviceTypeCode(n) === 'network')
    if (net) return net
  }
  return candidates[0]
}

export function boundDeviceOptionLabel(n: NetworkNode): string {
  const mgmtName = managedDeviceDisplayName(n)
  const model = n.device?.device_model_name
  const typeName = n.device?.device_type_name
  const host = n.device?.hostname
  const loc = nodeLocationOnly(n)
  const u = nodeUPosition(n)
  const parts = [`名称:${mgmtName}`]
  if (!n.device_id) parts.push('未关联台账')
  if (model) parts.push(`型号:${model}`)
  if (typeName) parts.push(`类型:${typeName}`)
  if (host && host !== mgmtName) parts.push(`主机:${host}`)
  if (loc !== '-') parts.push(loc)
  if (u !== '-') parts.push(`${u}U`)
  if (n.name && n.name !== mgmtName) parts.push(`拓扑:${n.name}`)
  return parts.join(' · ')
}

export function linkEndFilterHint(filter: LinkEndTypeFilter): string {
  if (filter === 'compute') {
    return '设备管理中暂无服务器类设备，请先在设备管理中创建'
  }
  if (filter === 'network') {
    return '设备管理中暂无交换机类设备，请先在设备管理中创建'
  }
  if (filter === 'storage') {
    return '设备管理中暂无存储类设备'
  }
  if (filter === 'security') {
    return '设备管理中暂无安全类设备，请先在设备管理中创建'
  }
  return '设备管理中暂无可用设备'
}

export function linkEndTypeLabel(filter: LinkEndTypeFilter): string {
  if (filter === 'compute') return '服务器'
  if (filter === 'network') return '交换机'
  if (filter === 'security') return '安全设备'
  if (filter === 'storage') return '存储设备'
  return '设备'
}

/** @deprecated */
export function nodeMatchesKindFilter(node: NetworkNode, filter: LinkEndTypeFilter): boolean {
  return nodeMatchesTypeFilter(node, filter)
}
