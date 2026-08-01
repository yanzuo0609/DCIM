import type { Device } from '@/api/device'
import type { NetworkDeviceBrief, NetworkNode, NetworkNodeKind } from '@/api/network'

/** 将设备管理台账转为拓扑节点简报（含合同设备名称/型号） */
export function deviceToNetworkBrief(d: Device): NetworkDeviceBrief {
  return {
    device_id: d.id,
    name: d.name || d.hostname,
    hostname: d.hostname,
    rack_id: d.rack_id,
    room_id: d.room_id,
    rack_code: d.rack_code,
    room_name: d.room_name,
    u_position: d.u_position,
    ip_summary: d.ip_summary,
    bmc_ip: d.bmc_ip ?? null,
    vip: d.vip ?? null,
    device_type_name: d.device_type_name,
    device_type_code: d.device_type_code ?? null,
    device_model_name: d.device_model_name,
    height_u: d.height_u,
  }
}

/** 拓扑 kind 与设备管理类型建议对应 */
export function preferredDeviceTypeCode(kind: NetworkNodeKind): string | null {
  if (kind === 'switch') return 'network'
  if (kind === 'server') return 'compute'
  if (kind === 'security') return 'security'
  return null
}

export function formatDeviceOptionLabel(d: Device): string {
  const name = d.name || d.hostname
  const parts = [name]
  if (d.device_model_name) parts.push(d.device_model_name)
  if (d.device_type_name) parts.push(d.device_type_name)
  if (d.hostname && d.hostname !== name) parts.push(d.hostname)
  if (d.serial_number) parts.push(d.serial_number)
  return parts.join(' · ')
}

/** 按连线端类型过滤设备管理清单 */
export function filterDevicesByEndType(
  devices: Device[],
  filter: 'network' | 'compute' | 'storage' | 'security' | 'any',
): Device[] {
  if (filter === 'any') return devices
  return devices.filter((d) => {
    const code = (d.device_type_code || '').toLowerCase()
    if (code === filter) return true
    const name = d.device_type_name || ''
    if (filter === 'network' && (name === '网络' || /交换机|路由|network/i.test(name))) return true
    if (filter === 'compute' && (name === '计算' || /服务器|compute/i.test(name))) return true
    if (filter === 'storage' && (name === '存储' || /storage/i.test(name))) return true
    if (filter === 'security' && (name === '安全' || /防火|security/i.test(name))) return true
    return false
  })
}

/** 拓扑设备用于匹配台账的名称（优先合同设备名称） */
export function topologyDeviceMatchKey(node: NetworkNode | null | undefined): string {
  if (!node) return ''
  return (node.contract_device_name || node.name || '').trim()
}

/** 台账是否与拓扑设备名称相关（等值 / 包含 / 面板应用名） */
export function deviceMatchesTopologyName(device: Device, topologyName: string): boolean {
  const key = topologyName.trim().toLowerCase()
  if (!key) return true
  const name = (device.name || '').trim().toLowerCase()
  const host = (device.hostname || '').trim().toLowerCase()
  const panel = (device.panel_apply_device_name || '').trim().toLowerCase()
  if (panel === key) return true
  if (name === key || host === key) return true
  if (name.includes(key) || host.includes(key)) return true
  return false
}

/** 按拓扑设备名称过滤设备管理清单 */
export function filterDevicesByTopologyName(
  devices: Device[],
  topologyName: string | null | undefined,
): Device[] {
  const key = (topologyName || '').trim()
  if (!key) return devices
  return devices.filter((d) => deviceMatchesTopologyName(d, key))
}

/** 是否匹配任一合同设备名称（等值/包含/面板应用名） */
export function deviceMatchesAnyTopologyName(device: Device, names: string[]): boolean {
  const keys = names.map((n) => n.trim()).filter(Boolean)
  if (!keys.length) return false
  return keys.some((k) => deviceMatchesTopologyName(device, k))
}

/**
 * 厂商型号采购汇总中名称含指定关键字的设备名称列表
 * （如「服务器」→ 计算服务器2、机架服务器 等）
 */
export function contractDeviceNamesContaining(
  summaries: Array<{ device_name?: string | null }>,
  keyword: string,
): string[] {
  const key = keyword.trim()
  if (!key) return []
  const seen = new Set<string>()
  const result: string[] = []
  for (const row of summaries) {
    const name = (row.device_name || '').trim()
    if (!name || !name.includes(key) || seen.has(name)) continue
    seen.add(name)
    result.push(name)
  }
  return result
}

/** 过滤出台账中与采购汇总「名称含关键字」条目对应的设备 */
export function filterDevicesByContractNameKeyword(
  devices: Device[],
  summaries: Array<{ device_name?: string | null }>,
  keyword: string,
): Device[] {
  const names = contractDeviceNamesContaining(summaries, keyword)
  if (names.length) {
    return devices.filter((d) => deviceMatchesAnyTopologyName(d, names))
  }
  // 汇总暂无匹配项时，回退：台账名称/面板应用名含关键字
  const key = keyword.trim()
  if (!key) return []
  return devices.filter((d) => {
    const n = (d.name || '').trim()
    const h = (d.hostname || '').trim()
    const p = (d.panel_apply_device_name || '').trim()
    return n.includes(key) || h.includes(key) || p.includes(key)
  })
}

/** 为台账设备查找可绑定的拓扑定义节点（用于取设备定义面板接口） */
export function findTopologyNodeForDevice(
  nodes: NetworkNode[],
  device: Device,
  expectedKind?: NetworkNodeKind | null,
): NetworkNode | null {
  const already = nodes.find((n) => n.device_id === device.id)
  if (already) return already

  const kindNodes = expectedKind ? nodes.filter((n) => n.kind === expectedKind) : nodes
  const keys = [
    (device.panel_apply_device_name || '').trim(),
    (device.name || '').trim(),
    (device.hostname || '').trim(),
  ].filter(Boolean)

  const score = (n: NetworkNode): number => {
    const topoKey = topologyDeviceMatchKey(n)
    if (!topoKey && !n.name) return 0
    for (const k of keys) {
      if (topoKey === k || n.name === k) return 3
      if (deviceMatchesTopologyName(device, topoKey || n.name)) return 2
    }
    // 已应用面板且型号一致时弱匹配
    if (device.device_model_id && n.device_model_id === device.device_model_id) return 1
    return 0
  }

  // 优先未绑定且名称匹配的定义节点
  const unbound = kindNodes
    .filter((n) => !n.device_id)
    .map((n) => ({ n, s: score(n) }))
    .filter((x) => x.s > 0)
    .sort((a, b) => b.s - a.s)
  if (unbound[0]) return unbound[0].n

  // 名称强匹配的已有节点（允许编辑场景）
  const named = kindNodes
    .map((n) => ({ n, s: score(n) }))
    .filter((x) => x.s >= 2)
    .sort((a, b) => b.s - a.s)
  return named[0]?.n || null
}

/** 绑定台账后同步简报；保留拓扑/合同设备名称，避免覆盖成单台台账名 */
export function applyDeviceBinding(node: NetworkNode, device: Device | null) {
  if (!device) {
    node.device_id = null
    node.device = null
    return
  }
  node.device_id = device.id
  node.device = deviceToNetworkBrief(device)
  // 已有合同设备名称时保持拓扑显示名（如「计算服务器2」），便于一对多选台账
  if (!node.contract_device_name) {
    const displayName = (device.name || device.hostname || '').trim()
    if (displayName) node.name = displayName
  }
}
