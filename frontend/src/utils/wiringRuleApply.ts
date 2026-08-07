import type {
  CableType,
  FramePort,
  InterfaceClass,
  NetworkLink,
  NetworkLinkType,
  NetworkNode,
  PortType,
} from '@/api/network'
import type { NetworkWiringRule } from '@/api/networkModelDesign'
import { resolveNodeFabricRole, resolvePortPurpose } from '@/utils/fabricRole'
import {
  CONNECTION_TO_LINK_ROLE,
  CONNECTION_TO_LINK_TYPE,
  normalizeWiringConfig,
  type ConnectionType,
  type MediaKind,
  type WiringRuleConfig,
} from '@/utils/wiringTypes'

export interface WiringApplyIssue {
  level: 'error' | 'warning' | 'info'
  code: string
  message: string
}

export interface WiringApplyReport {
  created: number
  matched_sources: number
  matched_targets: number
  issues: WiringApplyIssue[]
  ok: boolean
}

export interface WiringApplyResult {
  links: NetworkLink[]
  report: WiringApplyReport
}

const PORT_SPEED_RANK: Record<string, number> = {
  '1g': 1,
  '1G': 1,
  '10g': 10,
  '10G': 10,
  '25g': 25,
  '25G': 25,
  '40g': 40,
  '40G': 40,
  '40_100g': 100,
  '100g': 100,
  '100G': 100,
  '400g': 400,
  '400G': 400,
}

function speedRank(s: string | null | undefined): number {
  if (!s) return 0
  const key = String(s).trim()
  if (PORT_SPEED_RANK[key] != null) return PORT_SPEED_RANK[key]
  const n = Number(key.replace(/[^0-9.]/g, ''))
  return Number.isFinite(n) ? n : 0
}

function mapSpeedToPortType(speed: string | null | undefined): PortType | null {
  const r = speedRank(speed)
  if (r <= 0) return null
  if (r <= 1) return '1g'
  if (r <= 10) return '10g'
  return '40_100g'
}

function parsePortRange(range: string | null | undefined): Set<number> | null {
  if (!range || !String(range).trim()) return null
  const set = new Set<number>()
  for (const part of String(range).split(/[,;\s]+/)) {
    const m = part.match(/^(\d+)\s*-\s*(\d+)$/)
    if (m) {
      const a = Number(m[1])
      const b = Number(m[2])
      for (let i = Math.min(a, b); i <= Math.max(a, b); i++) set.add(i)
      continue
    }
    const n = Number(part)
    if (Number.isFinite(n)) set.add(n)
  }
  return set.size ? set : null
}

function portLabelNumber(label: string): number | null {
  const m = String(label).match(/(\d+)/)
  return m ? Number(m[1]) : null
}

function portsOf(node: NetworkNode): FramePort[] {
  return node.port_layout?.ports || []
}

function linkExists(links: NetworkLink[], a: string, ap: string, b: string, bp: string): boolean {
  return links.some(
    (l) =>
      (l.source_node_id === a &&
        l.source_port === ap &&
        l.target_node_id === b &&
        l.target_port === bp) ||
      (l.source_node_id === b &&
        l.source_port === bp &&
        l.target_node_id === a &&
        l.target_port === ap),
  )
}

function bindPeers(
  nodes: NetworkNode[],
  sourceId: string,
  sourcePort: string,
  targetId: string,
  targetPort: string,
) {
  const source = nodes.find((n) => n.id === sourceId)
  const target = nodes.find((n) => n.id === targetId)
  const sp = source?.port_layout?.ports?.find((p) => p.id === sourcePort)
  const tp = target?.port_layout?.ports?.find((p) => p.id === targetPort)
  if (sp) {
    sp.peer_node_id = targetId
    sp.peer_port = targetPort
    sp.peer_label = target?.name || null
  }
  if (tp) {
    tp.peer_node_id = sourceId
    tp.peer_port = sourcePort
    tp.peer_label = source?.name || null
  }
}

function matchNodes(
  nodes: NetworkNode[],
  ids: string[] | undefined,
  role: string | null | undefined,
  group: string | null | undefined,
): NetworkNode[] {
  const onCanvas = nodes.filter((n) => n.on_canvas !== false)
  if (ids?.length) {
    const set = new Set(ids)
    return onCanvas.filter((n) => set.has(n.id))
  }
  return onCanvas.filter((n) => {
    if (role && resolveNodeFabricRole(n) !== role) return false
    if (group && (n.device_group || '').trim() !== group.trim()) return false
    return !!(role || group)
  })
}

function slotZoneLabel(node: NetworkNode, port: FramePort): string | null {
  if (port.slot_index == null) return null
  const slot = node.port_layout?.slots_def?.[port.slot_index]
  return slot?.zone_label || null
}

function filterPorts(
  node: NetworkNode,
  cfg: WiringRuleConfig,
  side: 'source' | 'target',
  occupied: Set<string>,
): FramePort[] {
  const purpose =
    side === 'source' ? cfg.source_port_purpose : cfg.target_port_purpose
  const types =
    side === 'source' ? cfg.source_port_types || [] : cfg.target_port_types || []
  const ids = side === 'source' ? cfg.source_port_ids || [] : cfg.target_port_ids || []
  const range = parsePortRange(
    side === 'source' ? cfg.source_port_range : cfg.target_port_range,
  )
  const wantSpeed = cfg.port_speed || cfg.speed
  const speedMode = cfg.speed_mode || 'EXACT'
  const mappedType = mapSpeedToPortType(wantSpeed)

  let list = [...portsOf(node)]
  if (ids.length) {
    const set = new Set(ids)
    list = list.filter((p) => set.has(p.id))
  }
  list = list.filter((p) => {
    if (p.reserved) return false
    if (p.peer_node_id) return false
    if (occupied.has(`${node.id}:${p.id}`)) return false
    const resolved = resolvePortPurpose(p.purpose, p.group_id, slotZoneLabel(node, p))
    // PEER / DAD 口不参与普通业务规则
    if (purpose !== 'PEER' && purpose !== 'DAD' && (resolved === 'PEER' || resolved === 'DAD')) {
      return false
    }
    if (purpose && resolved && resolved !== purpose) return false
    if (purpose && !resolved) {
      // 无 purpose 时：仅当未指定严格 purpose 过滤，或端口类型匹配时放行
      // 严格模式下要求 purpose；此处允许无标记口参与（兼容旧面板）
    }
    if (types.length && !types.includes(p.port_type)) return false
    if (range) {
      const num = portLabelNumber(p.label)
      if (num == null || !range.has(num)) return false
    }
    if (wantSpeed) {
      const pr = speedRank(p.port_type)
      const wr = speedRank(wantSpeed)
      if (speedMode === 'EXACT') {
        if (mappedType && p.port_type !== mappedType && pr !== wr) return false
      } else if (pr < wr) {
        return false
      }
    }
    return true
  })
  // 优先级：有匹配 purpose 的靠前
  list.sort((a, b) => {
    const ap = resolvePortPurpose(a.purpose, a.group_id, slotZoneLabel(node, a)) === purpose ? 0 : 1
    const bp = resolvePortPurpose(b.purpose, b.group_id, slotZoneLabel(node, b)) === purpose ? 0 : 1
    if (ap !== bp) return ap - bp
    return (portLabelNumber(a.label) || 0) - (portLabelNumber(b.label) || 0)
  })
  return list
}

function estimateDistanceM(a: NetworkNode, b: NetworkNode): number {
  const ra = a.device?.rack_code || null
  const rb = b.device?.rack_code || null
  if (ra && rb && ra === rb) return 1.5
  if (ra && rb) return 15
  // 画布距离粗估（像素→米）
  const dx = (a.pos_x || 0) - (b.pos_x || 0)
  const dy = (a.pos_y || 0) - (b.pos_y || 0)
  const px = Math.sqrt(dx * dx + dy * dy)
  return Math.max(1, px / 40)
}

function resolveMedia(
  cfg: WiringRuleConfig,
  source: NetworkNode,
  target: NetworkNode,
): { media: string; cable_type: CableType; interface_class: InterfaceClass; length_m: number | null; module: string | null } {
  const dist = estimateDistanceM(source, target)
  let media: MediaKind | string = cfg.media || 'AUTO'
  if (media === 'AUTO') {
    const maxShort = cfg.max_distance_m ?? 3
    if (dist <= maxShort) media = 'DAC'
    else if (dist <= 10) media = 'AOC'
    else media = 'FIBER_SM'
  }
  const length =
    cfg.cable_length_mode === 'FIXED' && cfg.cable_length_m != null
      ? cfg.cable_length_m
      : Math.round(dist * 10) / 10

  if (media === 'MPO') {
    return {
      media: 'MPO',
      cable_type: 'fiber_sm',
      interface_class: 'optical',
      length_m: length,
      module: cfg.module || 'MPO',
    }
  }
  if (media === 'BREAKOUT_1X4') {
    return {
      media: 'BREAKOUT_1X4',
      cable_type: 'fiber_sm',
      interface_class: 'optical',
      length_m: length,
      module: cfg.module || '1x4-Breakout',
    }
  }
  if (media === 'DAC') {
    return {
      media: 'DAC',
      cable_type: 'dac',
      interface_class: 'dac',
      length_m: length,
      module: cfg.module ?? null,
    }
  }
  if (media === 'AOC') {
    return {
      media: 'AOC',
      cable_type: 'aoc',
      interface_class: 'optical',
      length_m: length,
      module: cfg.module ?? null,
    }
  }
  if (media === 'FIBER_MM') {
    return {
      media: 'FIBER_MM',
      cable_type: 'fiber_mm',
      interface_class: 'optical',
      length_m: length,
      module: cfg.module || (cfg.speed ? `${cfg.speed}-SR` : null),
    }
  }
  if (media === 'COPPER') {
    return {
      media: 'COPPER',
      cable_type: (cfg.cable_type as CableType) || 'copper_cat6',
      interface_class: 'electric',
      length_m: length,
      module: null,
    }
  }
  return {
    media: 'FIBER_SM',
    cable_type: 'fiber_sm',
    interface_class: 'optical',
    length_m: length,
    module: cfg.module || (cfg.speed ? `${cfg.speed}-LR4` : null),
  }
}

function formatLabel(template: string | null | undefined, conn: string, seq: number): string {
  const tpl = template || '{conn}-{seq:02d}'
  return tpl
    .replace(/\{conn\}/g, conn)
    .replace(/\{seq:(\d+)d\}/g, (_, w) => String(seq).padStart(Number(w), '0'))
    .replace(/\{seq\}/g, String(seq))
}

function pickPort(
  ports: FramePort[],
  usedSlots: Set<number>,
  requireCardDiversity: boolean,
  requirePortDiversity: boolean,
): FramePort | null {
  for (const p of ports) {
    if (requireCardDiversity && p.slot_index != null && usedSlots.has(p.slot_index) && usedSlots.size > 0) {
      continue
    }
    if (requirePortDiversity && usedSlots.has(-(portLabelNumber(p.label) || 0) - 1)) {
      // already used this label number marker — skip if we track by id separately
    }
    return p
  }
  return ports[0] || null
}

function pairPeerNodes(nodes: NetworkNode[]): [NetworkNode, NetworkNode][] {
  const pairs: [NetworkNode, NetworkNode][] = []
  const used = new Set<string>()
  const byGroup = new Map<string, NetworkNode[]>()
  for (const n of nodes) {
    const g = (n.device_group || '').trim() || '_default'
    if (!byGroup.has(g)) byGroup.set(g, [])
    byGroup.get(g)!.push(n)
  }
  for (const list of byGroup.values()) {
    const sorted = [...list].sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
    for (let i = 0; i + 1 < sorted.length; i += 2) {
      const a = sorted[i]
      const b = sorted[i + 1]
      if (used.has(a.id) || used.has(b.id)) continue
      pairs.push([a, b])
      used.add(a.id)
      used.add(b.id)
    }
  }
  // 命名 A/B 启发式
  if (!pairs.length && nodes.length >= 2) {
    const sorted = [...nodes].sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
    for (let i = 0; i + 1 < sorted.length; i += 2) {
      pairs.push([sorted[i], sorted[i + 1]])
    }
  }
  return pairs
}

/** 按规则生成连线，返回新增 links + 校验报告 */
export function applyWiringRule(
  rule: NetworkWiringRule,
  nodes: NetworkNode[],
  existingLinks: NetworkLink[],
): WiringApplyResult {
  const report: WiringApplyReport = {
    created: 0,
    matched_sources: 0,
    matched_targets: 0,
    issues: [],
    ok: true,
  }
  if (!rule.enabled) {
    report.ok = false
    report.issues.push({ level: 'warning', code: 'disabled', message: '规则未启用' })
    return { links: [], report }
  }

  const cfg = normalizeWiringConfig((rule.config || {}) as Record<string, unknown>)
  const created: NetworkLink[] = []
  const occupied = new Set<string>()
  for (const l of existingLinks) {
    occupied.add(`${l.source_node_id}:${l.source_port}`)
    occupied.add(`${l.target_node_id}:${l.target_port}`)
  }

  const conn = (cfg.connection_type || 'UPLINK') as ConnectionType
  const linkType = (cfg.link_type || CONNECTION_TO_LINK_TYPE[conn] || 'switch_switch') as NetworkLinkType
  const linkRole = CONNECTION_TO_LINK_ROLE[conn] || 'uplink'
  const maxTotal = Math.max(1, Number(cfg.max_link_count) || 256)
  const perPair = Math.max(1, Number(cfg.link_count) || 1)
  const minPerPair = Math.max(0, Number(cfg.min_link_count ?? perPair))

  const pushLink = (
    source: NetworkNode,
    sourcePort: FramePort,
    target: NetworkNode,
    targetPort: FramePort,
    meta: {
      seq: number
      path: string | null
      lagGroup: string | null
    },
  ) => {
    if (created.length >= maxTotal) return false
    if (linkExists(existingLinks, source.id, sourcePort.id, target.id, targetPort.id)) return false
    if (linkExists(created, source.id, sourcePort.id, target.id, targetPort.id)) return false
    const mediaInfo = resolveMedia(cfg, source, target)
    bindPeers(nodes, source.id, sourcePort.id, target.id, targetPort.id)
    occupied.add(`${source.id}:${sourcePort.id}`)
    occupied.add(`${target.id}:${targetPort.id}`)
    const label = formatLabel(cfg.label_template, conn, meta.seq)
    created.push({
      id: crypto.randomUUID(),
      topology_id: rule.topology_id,
      source_node_id: source.id,
      target_node_id: target.id,
      source_port: sourcePort.id,
      target_port: targetPort.id,
      link_type: linkType,
      cable_type: mediaInfo.cable_type,
      interface_class: mediaInfo.interface_class,
      link_role: linkRole,
      label,
      source_label: `${source.name}:${sourcePort.label}`,
      target_label: `${target.name}:${targetPort.label}`,
      connection_type: conn,
      speed: cfg.speed || null,
      lag_group: meta.lagGroup,
      redundancy_path: meta.path,
      media: mediaInfo.media,
      module: mediaInfo.module,
      cable_length_m: mediaInfo.length_m,
      wiring_rule_id: rule.id,
    })
    return true
  }

  // manual pairs
  if (rule.mode === 'manual' && cfg.pairs?.length) {
    let seq = 1
    for (const pair of cfg.pairs) {
      const s = nodes.find((n) => n.id === pair.source_node_id)
      const t = nodes.find((n) => n.id === pair.target_node_id)
      const sp = s && portsOf(s).find((p) => p.id === pair.source_port_id)
      const tp = t && portsOf(t).find((p) => p.id === pair.target_port_id)
      if (!s || !t || !sp || !tp) {
        report.issues.push({
          level: 'error',
          code: 'pair_missing',
          message: `手动配对端口不存在: ${pair.source_node_id}/${pair.source_port_id}`,
        })
        continue
      }
      if (pushLink(s, sp, t, tp, { seq, path: null, lagGroup: null })) seq += 1
    }
    report.created = created.length
    report.ok = !report.issues.some((i) => i.level === 'error')
    return { links: created, report }
  }

  // Peer-Link 模式
  if (cfg.peer_link) {
    const role = cfg.source_role || cfg.target_role || 'ACCESS'
    const peers = matchNodes(nodes, cfg.source_node_ids?.length ? cfg.source_node_ids : undefined, role, cfg.source_group)
    report.matched_sources = peers.length
    report.matched_targets = peers.length
    const pairs = pairPeerNodes(peers)
    if (!pairs.length) {
      report.issues.push({
        level: 'error',
        code: 'no_peer_pairs',
        message: '未找到可配对的 Peer 设备（需至少 2 台同角色/同组）',
      })
      report.ok = false
      return { links: created, report }
    }
    let seq = 1
    for (const [a, b] of pairs) {
      const lagGroup = cfg.lag ? `LAG-PEER-${a.name}/${b.name}` : null
      let made = 0
      const usedSlotsA = new Set<number>()
      const usedSlotsB = new Set<number>()
      for (let i = 0; i < perPair; i++) {
        const portsA = filterPorts(a, cfg, 'source', occupied)
        const portsB = filterPorts(b, cfg, 'target', occupied)
        const pa = pickPort(portsA, usedSlotsA, cfg.card_diversity === 'REQUIRED', cfg.port_diversity === 'REQUIRED')
        const pb = pickPort(portsB, usedSlotsB, cfg.card_diversity === 'REQUIRED', cfg.port_diversity === 'REQUIRED')
        if (!pa || !pb) break
        const path =
          cfg.redundancy_mode === 'A_B' ? (i % 2 === 0 ? 'A' : 'B') : null
        if (
          pushLink(a, pa, b, pb, {
            seq,
            path,
            lagGroup,
          })
        ) {
          if (pa.slot_index != null) usedSlotsA.add(pa.slot_index)
          if (pb.slot_index != null) usedSlotsB.add(pb.slot_index)
          made += 1
          seq += 1
        }
      }
      if (made < minPerPair) {
        report.issues.push({
          level: cfg.required ? 'error' : 'warning',
          code: 'peer_short',
          message: `${a.name}↔${b.name} 仅生成 ${made} 条 Peer-Link，少于 min=${minPerPair}`,
        })
      }
    }
    report.created = created.length
    report.ok = !report.issues.some((i) => i.level === 'error')
    return { links: created, report }
  }

  let sources = matchNodes(nodes, cfg.source_node_ids, cfg.source_role, cfg.source_group)
  let targets = matchNodes(nodes, cfg.target_node_ids, cfg.target_role, cfg.target_group)
  report.matched_sources = sources.length
  report.matched_targets = targets.length

  if (!sources.length || !targets.length) {
    report.issues.push({
      level: 'error',
      code: 'no_devices',
      message: `未匹配到源/目标设备（源 ${sources.length}，目标 ${targets.length}）。请检查角色/设备组或显式选择设备。`,
    })
    report.ok = false
    return { links: created, report }
  }

  const requireDeviceDiv = cfg.device_diversity === 'REQUIRED'
  const pairing = cfg.pairing || 'PER_SOURCE_TARGET'
  let seq = 1

  if (pairing === 'POOL') {
    // 全局端口池顺序配对（兼容旧行为）
    type PortRef = { node: NetworkNode; port: FramePort }
    const sourcePorts: PortRef[] = []
    const targetPorts: PortRef[] = []
    for (const n of sources) {
      for (const p of filterPorts(n, cfg, 'source', occupied)) sourcePorts.push({ node: n, port: p })
    }
    for (const n of targets) {
      for (const p of filterPorts(n, cfg, 'target', occupied)) targetPorts.push({ node: n, port: p })
    }
    const count = Math.min(sourcePorts.length, targetPorts.length, maxTotal, perPair * Math.max(sources.length, targets.length))
    for (let i = 0; i < count; i++) {
      const path = cfg.redundancy_mode === 'A_B' ? (i % 2 === 0 ? 'A' : 'B') : null
      const lagGroup = cfg.lag ? `LAG-${conn}-${Math.floor(i / Math.max(1, cfg.lag_count || 1))}` : null
      pushLink(sourcePorts[i].node, sourcePorts[i].port, targetPorts[i].node, targetPorts[i].port, {
        seq,
        path,
        lagGroup,
      })
      seq += 1
    }
  } else if (requireDeviceDiv && sources.length >= 1 && targets.length >= 2) {
    // 设备多样性：每个 source 的多条链路落到不同 target（典型：Server → ACCESS-A/B）
    for (const src of sources) {
      let made = 0
      const usedTargets = new Set<string>()
      const usedSlots = new Set<number>()
      const targetOrder = [...targets]
      for (let i = 0; i < perPair; i++) {
        const candidateTargets = targetOrder.filter((t) => !usedTargets.has(t.id) || !requireDeviceDiv)
        let linked = false
        for (const tgt of candidateTargets) {
          if (cfg.rack_diversity === 'REQUIRED') {
            const ra = src.device?.rack_code
            const rb = tgt.device?.rack_code
            if (ra && rb && ra === rb && usedTargets.size > 0) continue
          }
          const sp = pickPort(
            filterPorts(src, cfg, 'source', occupied),
            usedSlots,
            cfg.card_diversity === 'REQUIRED',
            cfg.port_diversity === 'REQUIRED',
          )
          const tp = filterPorts(tgt, cfg, 'target', occupied)[0]
          if (!sp || !tp) continue
          const path = cfg.redundancy_mode === 'A_B' ? (i % 2 === 0 ? 'A' : 'B') : null
          const lagGroup = cfg.lag ? `LAG-${src.name}` : null
          if (pushLink(src, sp, tgt, tp, { seq, path, lagGroup })) {
            usedTargets.add(tgt.id)
            if (sp.slot_index != null) usedSlots.add(sp.slot_index)
            made += 1
            seq += 1
            linked = true
            break
          }
        }
        if (!linked) break
      }
      if (made < minPerPair) {
        report.issues.push({
          level: cfg.required ? 'error' : 'warning',
          code: 'link_short',
          message: `${src.name} 仅生成 ${made} 条链路，少于 min=${minPerPair}（设备多样性）`,
        })
      }
    }
  } else {
    // 默认：每个 source×target 生成 link_count 条
    for (const src of sources) {
      for (const tgt of targets) {
        if (src.id === tgt.id) continue
        let made = 0
        const usedSlotsS = new Set<number>()
        const usedSlotsT = new Set<number>()
        const lagGroup = cfg.lag ? `LAG-${src.name}-${tgt.name}` : null
        for (let i = 0; i < perPair; i++) {
          const sp = pickPort(
            filterPorts(src, cfg, 'source', occupied),
            usedSlotsS,
            cfg.card_diversity === 'REQUIRED',
            cfg.port_diversity === 'REQUIRED',
          )
          const tp = pickPort(
            filterPorts(tgt, cfg, 'target', occupied),
            usedSlotsT,
            cfg.card_diversity === 'REQUIRED',
            cfg.port_diversity === 'REQUIRED',
          )
          if (!sp || !tp) break
          const path = cfg.redundancy_mode === 'A_B' ? (i % 2 === 0 ? 'A' : 'B') : null
          if (pushLink(src, sp, tgt, tp, { seq, path, lagGroup })) {
            if (sp.slot_index != null) usedSlotsS.add(sp.slot_index)
            if (tp.slot_index != null) usedSlotsT.add(tp.slot_index)
            made += 1
            seq += 1
          }
        }
        if (made < minPerPair) {
          report.issues.push({
            level: cfg.required ? 'error' : 'warning',
            code: 'link_short',
            message: `${src.name}→${tgt.name} 仅生成 ${made} 条，少于 min=${minPerPair}`,
          })
        }
      }
    }
  }

  if (cfg.power_domain_diversity === 'REQUIRED') {
    report.issues.push({
      level: 'info',
      code: 'power_domain_skipped',
      message: '电源域多样性已配置为 REQUIRED，但当前无电源域数据，已跳过校验',
    })
  }

  report.created = created.length
  if (!created.length && cfg.required) {
    report.issues.push({
      level: 'error',
      code: 'none_created',
      message: '未生成任何连线：请检查端口 Purpose/速率/范围是否匹配空闲口',
    })
  }
  report.ok = !report.issues.some((i) => i.level === 'error')
  return { links: created, report }
}

/** @deprecated 兼容旧调用：仅返回 links */
export function applyWiringRuleLinks(
  rule: NetworkWiringRule,
  nodes: NetworkNode[],
  existingLinks: NetworkLink[],
): NetworkLink[] {
  return applyWiringRule(rule, nodes, existingLinks).links
}
