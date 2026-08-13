/**
 * 布线引擎入口 — 场景路由 + 具名算法
 * @see docs/18-rules_structured.md / V2 端口规则
 */

import type {
  CableType,
  FramePort,
  InterfaceClass,
  NetworkLink,
  NetworkLinkType,
  NetworkNode,
} from '@/api/network'
import type { NetworkWiringRule } from '@/api/networkModelDesign'
import { matchWiringEndpoints } from '@/utils/wiring/matchEndpoints'
import { inferLinkType } from '@/utils/networkPortLayout'
import {
  annotatePortMediaAndInterface,
  markReservedPeerDadForGroups,
} from '@/utils/wiringDeviceType'
import { annotateNodesPortPurposes } from '@/utils/designModelToNode'
import {
  CONNECTION_TO_LINK_ROLE,
  CONNECTION_TO_LINK_TYPE,
  normalizeWiringConfig,
  resolveWiringGroups,
  type ConnectionType,
  type MediaKind,
  type WiringPair,
  type WiringRuleConfig,
} from '@/utils/wiringTypes'
import type { AlgoCtx, PushLinkFn } from '@/utils/wiring/algorithms'
import { adaptDevices } from '@/utils/wiring/deviceAdapter'
import { pushIssue } from '@/utils/wiring/constraints'
import { resolveScenario } from '@/utils/wiring/scenarioRouter'
import { runAccessEndpointScenario } from '@/utils/wiring/scenarios/accessEndpoint'
import { runBmcScenario } from '@/utils/wiring/scenarios/bmc'
import { runCoreToAccessScenario } from '@/utils/wiring/scenarios/coreToAccess'
import { runD1Scenario, runD2Scenario } from '@/utils/wiring/scenarios/interconnect'
import {
  SCENARIO_LABELS,
  type ScenarioId,
  type WiringApplyReport,
  type WiringApplyResult,
} from '@/utils/wiring/types'

export type {
  WiringApplyIssue,
  WiringApplyReport,
  WiringApplyResult,
} from '@/utils/wiring/types'
export { resolveScenario } from '@/utils/wiring/scenarioRouter'
export { SCENARIO_LABELS, type ScenarioId } from '@/utils/wiring/types'

export interface ProposedPair {
  source_node_id: string
  source_port_id: string
  source_label: string
  target_node_id: string
  target_port_id: string
  target_label: string
}

export interface WiringPreviewResult {
  scenario: ScenarioId
  scenario_label: string
  pairs: ProposedPair[]
  issues: WiringApplyReport['issues']
  matched_sources: number
  matched_targets: number
  ok: boolean
}

function matchNodes(
  nodes: NetworkNode[],
  ids: string[] | undefined,
  role: string | null | undefined,
  groups: string[] | string | null | undefined,
): NetworkNode[] {
  return matchWiringEndpoints(nodes, { ids, role, groups })
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
    sp.status = 'OCCUPIED'
  }
  if (tp) {
    tp.peer_node_id = sourceId
    tp.peer_port = sourcePort
    tp.peer_label = source?.name || null
    tp.status = 'OCCUPIED'
  }
}

function formatLabel(template: string | null | undefined, conn: string, seq: number): string {
  const tpl = template || '{conn}-{seq:02d}'
  return tpl
    .replace(/\{conn\}/g, conn)
    .replace(/\{seq:(\d+)d\}/g, (_, w) => String(seq).padStart(Number(w), '0'))
    .replace(/\{seq\}/g, String(seq))
}

function resolveMedia(
  cfg: WiringRuleConfig,
  _source: NetworkNode,
  _target: NetworkNode,
): {
  cable_type: CableType
  interface_class: InterfaceClass
  media: MediaKind
  module: string | null
  length_m: number | null
} {
  const media = (cfg.media || 'AUTO') as MediaKind
  let cable_type: CableType = 'other'
  let interface_class: InterfaceClass = 'other'
  if (media === 'DAC') {
    cable_type = 'dac'
    interface_class = 'dac'
  } else if (media === 'AOC') {
    cable_type = 'aoc'
    interface_class = 'optical'
  } else if (media === 'FIBER_SM') {
    cable_type = 'fiber_sm'
    interface_class = 'optical'
  } else if (media === 'FIBER_MM' || media === 'AUTO') {
    cable_type = 'fiber_mm'
    interface_class = 'optical'
  } else if (media === 'COPPER') {
    cable_type = 'copper_cat6'
    interface_class = 'electric'
  }
  return {
    cable_type,
    interface_class,
    media,
    module: cfg.module || (cfg.speed ? `${cfg.speed}-LR4` : null),
    length_m: cfg.cable_length_mode === 'FIXED' ? Number(cfg.cable_length_m) || null : null,
  }
}

function resolveMatchedNodes(cfg: WiringRuleConfig, nodes: NetworkNode[], conn: ConnectionType) {
  const scope = cfg.interconnect_scope || 'INTRA_GROUP'
  if ((cfg.peer_link || conn === 'SWITCH_INTERCONNECT') && scope === 'INTRA_GROUP') {
    const role = cfg.source_role || cfg.target_role || 'ACCESS'
    const peers = matchNodes(
      nodes,
      cfg.source_node_ids?.length ? cfg.source_node_ids : undefined,
      role,
      resolveWiringGroups(cfg.source_groups, cfg.source_group),
    )
    return { sourceNodes: peers, targetNodes: peers }
  }
  // 组间互联或其它连接：源/目标分别按设备参数匹配
  return {
    sourceNodes: matchNodes(
      nodes,
      cfg.source_node_ids,
      cfg.source_role,
      resolveWiringGroups(cfg.source_groups, cfg.source_group),
    ),
    targetNodes: matchNodes(
      nodes,
      cfg.target_node_ids,
      cfg.target_role,
      resolveWiringGroups(cfg.target_groups, cfg.target_group),
    ),
  }
}

function applyManualPairs(
  pairs: WiringPair[],
  nodes: NetworkNode[],
  pushLink: PushLinkFn,
  report: WiringApplyReport,
) {
  for (const pair of pairs) {
    const s = nodes.find((n) => n.id === pair.source_node_id)
    const t = nodes.find((n) => n.id === pair.target_node_id)
    const sp = s?.port_layout?.ports?.find((p) => p.id === pair.source_port_id)
    const tp = t?.port_layout?.ports?.find((p) => p.id === pair.target_port_id)
    if (!s || !t || !sp || !tp) {
      pushIssue(
        report,
        'error',
        'ERR_NO_FREE_PORT',
        `手动配对端口不存在: ${pair.source_node_id}/${pair.source_port_id}`,
      )
      continue
    }
    pushLink(s, sp, t, tp, {})
  }
}

function runScenarioEngine(
  scenario: ScenarioId,
  ctx: AlgoCtx,
  sourceViews: ReturnType<typeof adaptDevices>,
  targetViews: ReturnType<typeof adaptDevices>,
  perPair: number,
) {
  if (scenario === 'A1' || scenario === 'A2' || scenario === 'A3') {
    runAccessEndpointScenario(scenario, ctx, sourceViews, targetViews, perPair)
  } else if (scenario === 'B1') {
    runBmcScenario(ctx, sourceViews, targetViews)
  } else if (scenario === 'C1' || scenario === 'C2' || scenario === 'C3' || scenario === 'C4') {
    runCoreToAccessScenario(scenario, ctx, sourceViews, targetViews, perPair)
  } else if (scenario === 'D1') {
    const devices =
      sourceViews.length >= 2
        ? sourceViews
        : [
            ...sourceViews,
            ...targetViews.filter((t) => !sourceViews.some((s) => s.node.id === t.node.id)),
          ]
    runD1Scenario(ctx, devices.length >= 2 ? devices : sourceViews)
  } else if (scenario === 'D2') {
    runD2Scenario(ctx, sourceViews, targetViews)
  }
}

/**
 * 预览场景（不执行连线）— 供规则 UI 展示
 */
export function previewWiringScenario(
  rule: NetworkWiringRule,
  nodes: NetworkNode[],
): { scenario: ScenarioId; label: string; sources: number; targets: number } {
  const cfg = normalizeWiringConfig((rule.config || {}) as Record<string, unknown>)
  for (const n of nodes) annotatePortMediaAndInterface(n.port_layout?.ports)

  const conn = (cfg.connection_type || 'CORE_TO_ACCESS') as ConnectionType
  const { sourceNodes, targetNodes } = resolveMatchedNodes(cfg, nodes, conn)

  const occupied = new Set<string>()
  const srcViews = adaptDevices(sourceNodes, occupied)
  const tgtViews = adaptDevices(targetNodes, occupied)
  const scenario = resolveScenario(srcViews, tgtViews, {
    peerLink: !!cfg.peer_link,
    forceBmc:
      cfg.connection_type === 'BMC_ENDPOINT' || srcViews.some((d) => d.deviceType === 'BMC_SWITCH'),
    interconnectScope: cfg.interconnect_scope || 'INTRA_GROUP',
  })
  return {
    scenario,
    label: SCENARIO_LABELS[scenario],
    sources: sourceNodes.length,
    targets: targetNodes.length,
  }
}

/**
 * 预览拟建端口对（不改 occupied / 不写 peer）
 */
export function previewWiringPairs(
  rule: NetworkWiringRule,
  nodes: NetworkNode[],
  existingLinks: NetworkLink[],
): WiringPreviewResult {
  const report: WiringApplyReport = {
    created: 0,
    matched_sources: 0,
    matched_targets: 0,
    scenario: null,
    scenario_label: null,
    issues: [],
    ok: true,
  }
  const cfg = normalizeWiringConfig((rule.config || {}) as Record<string, unknown>)
  for (const n of nodes) annotatePortMediaAndInterface(n.port_layout?.ports)
  annotateNodesPortPurposes(nodes)
  markReservedPeerDadForGroups(nodes)

  const occupied = new Set<string>()
  for (const l of existingLinks) {
    occupied.add(`${l.source_node_id}:${l.source_port}`)
    occupied.add(`${l.target_node_id}:${l.target_port}`)
  }

  const pairs: ProposedPair[] = []
  const pushLink: PushLinkFn = (source, sourcePort, target, targetPort) => {
    const sk = `${source.id}:${sourcePort.id}`
    const tk = `${target.id}:${targetPort.id}`
    if (occupied.has(sk) || occupied.has(tk)) return false
    if (sourcePort.label && occupied.has(`${source.id}:${sourcePort.label}`)) return false
    if (targetPort.label && occupied.has(`${target.id}:${targetPort.label}`)) return false
    if (linkExists(existingLinks, source.id, sourcePort.id, target.id, targetPort.id)) return false
    if (
      pairs.some(
        (p) =>
          (p.source_node_id === source.id &&
            p.source_port_id === sourcePort.id &&
            p.target_node_id === target.id &&
            p.target_port_id === targetPort.id) ||
          (p.source_node_id === target.id &&
            p.source_port_id === targetPort.id &&
            p.target_node_id === source.id &&
            p.target_port_id === sourcePort.id),
      )
    ) {
      return false
    }
    occupied.add(sk)
    occupied.add(tk)
    pairs.push({
      source_node_id: source.id,
      source_port_id: sourcePort.id,
      source_label: `${source.name}:${sourcePort.label}`,
      target_node_id: target.id,
      target_port_id: targetPort.id,
      target_label: `${target.name}:${targetPort.label}`,
    })
    return true
  }

  // 已有手动 pairs：直接展示
  if (cfg.pairs?.length) {
    for (const pair of cfg.pairs) {
      const s = nodes.find((n) => n.id === pair.source_node_id)
      const t = nodes.find((n) => n.id === pair.target_node_id)
      const sp = s?.port_layout?.ports?.find((p) => p.id === pair.source_port_id)
      const tp = t?.port_layout?.ports?.find((p) => p.id === pair.target_port_id)
      if (!s || !t || !sp || !tp) {
        pushIssue(report, 'error', 'ERR_NO_FREE_PORT', '预览：手动端口对无效')
        continue
      }
      pushLink(s, sp, t, tp, {})
    }
    return {
      scenario: 'UNSUPPORTED',
      scenario_label: '手动端口对',
      pairs,
      issues: report.issues,
      matched_sources: 0,
      matched_targets: 0,
      ok: !report.issues.some((i) => i.level === 'error'),
    }
  }

  const conn = (cfg.connection_type || 'CORE_TO_ACCESS') as ConnectionType
  const { sourceNodes, targetNodes } = resolveMatchedNodes(cfg, nodes, conn)
  report.matched_sources = sourceNodes.length
  report.matched_targets = targetNodes.length

  if (!sourceNodes.length || !targetNodes.length) {
    pushIssue(report, 'error', 'ERR_UNSUPPORTED_TOPOLOGY', '预览：未匹配到源/目标设备')
    return {
      scenario: 'UNSUPPORTED',
      scenario_label: SCENARIO_LABELS.UNSUPPORTED,
      pairs: [],
      issues: report.issues,
      matched_sources: sourceNodes.length,
      matched_targets: targetNodes.length,
      ok: false,
    }
  }

  const perPair = Math.max(1, Number(cfg.link_count) || 1)
  const sourceViews = adaptDevices(sourceNodes, occupied)
  const targetViews = adaptDevices(targetNodes, occupied)
  const allDevices = [...sourceViews]
  for (const t of targetViews) {
    if (!allDevices.some((d) => d.node.id === t.node.id)) allDevices.push(t)
  }

  const scenario = resolveScenario(sourceViews, targetViews, {
    peerLink: !!cfg.peer_link || conn === 'SWITCH_INTERCONNECT',
    forceBmc:
      conn === 'BMC_ENDPOINT' || sourceViews.some((d) => d.deviceType === 'BMC_SWITCH'),
    interconnectScope: cfg.interconnect_scope || 'INTRA_GROUP',
  })
  report.scenario = scenario
  report.scenario_label = SCENARIO_LABELS[scenario]

  if (scenario === 'UNSUPPORTED') {
    pushIssue(report, 'error', 'ERR_UNSUPPORTED_TOPOLOGY', '预览：不支持的拓扑组合')
    return {
      scenario,
      scenario_label: SCENARIO_LABELS[scenario],
      pairs: [],
      issues: report.issues,
      matched_sources: sourceNodes.length,
      matched_targets: targetNodes.length,
      ok: false,
    }
  }

  const allowSpeedDowngrade =
    scenario === 'C1' ||
    scenario === 'C2' ||
    scenario === 'C3' ||
    scenario === 'C4' ||
    cfg.speed_mode === 'MIN'
  const ctx: AlgoCtx = {
    occupied,
    pushLink,
    report,
    allowSpeedDowngrade,
    allDevices,
    cfg,
  }
  runScenarioEngine(scenario, ctx, sourceViews, targetViews, perPair)

  return {
    scenario,
    scenario_label: SCENARIO_LABELS[scenario],
    pairs,
    issues: report.issues,
    matched_sources: sourceNodes.length,
    matched_targets: targetNodes.length,
    ok: !report.issues.some((i) => i.level === 'error'),
  }
}

export function applyWiringRule(
  rule: NetworkWiringRule,
  nodes: NetworkNode[],
  existingLinks: NetworkLink[],
): WiringApplyResult {
  const report: WiringApplyReport = {
    created: 0,
    matched_sources: 0,
    matched_targets: 0,
    scenario: null,
    scenario_label: null,
    issues: [],
    ok: true,
  }

  if (!rule.enabled) {
    report.ok = false
    pushIssue(report, 'warning', 'disabled', '规则未启用')
    return { links: [], report }
  }

  for (const n of nodes) annotatePortMediaAndInterface(n.port_layout?.ports)
  annotateNodesPortPurposes(nodes)
  markReservedPeerDadForGroups(nodes)

  const cfg = normalizeWiringConfig((rule.config || {}) as Record<string, unknown>)
  const created: NetworkLink[] = []
  const occupied = new Set<string>()
  for (const l of existingLinks) {
    occupied.add(`${l.source_node_id}:${l.source_port}`)
    occupied.add(`${l.target_node_id}:${l.target_port}`)
  }

  const conn = (cfg.connection_type || 'CORE_TO_ACCESS') as ConnectionType
  const defaultLinkType = (CONNECTION_TO_LINK_TYPE[conn] || 'switch_switch') as NetworkLinkType
  const linkRole = CONNECTION_TO_LINK_ROLE[conn] || 'uplink'
  const perPair = Math.max(1, Number(cfg.link_count) || 1)
  const maxPerPair = Math.max(perPair, Number(cfg.max_link_count) || perPair)
  let maxTotal = Math.max(1, maxPerPair)
  let seq = 1

  const pushLink: PushLinkFn = (source, sourcePort, target, targetPort, meta) => {
    if (created.length >= maxTotal) return false
    if (linkExists(existingLinks, source.id, sourcePort.id, target.id, targetPort.id)) return false
    if (linkExists(created, source.id, sourcePort.id, target.id, targetPort.id)) return false
    const mediaInfo = resolveMedia(cfg, source, target)
    bindPeers(nodes, source.id, sourcePort.id, target.id, targetPort.id)
    occupied.add(`${source.id}:${sourcePort.id}`)
    occupied.add(`${target.id}:${targetPort.id}`)
    if (sourcePort.label) occupied.add(`${source.id}:${sourcePort.label}`)
    if (targetPort.label) occupied.add(`${target.id}:${targetPort.label}`)
    const label = formatLabel(cfg.label_template, conn, seq)
    // 按端点设备 kind 推断，避免规则里残留 switch_switch 导致保存校验失败
    const linkType = inferLinkType(source, target) || cfg.link_type || defaultLinkType
    created.push({
      id: crypto.randomUUID(),
      topology_id: rule.topology_id,
      source_node_id: source.id,
      target_node_id: target.id,
      source_port: sourcePort.id,
      target_port: targetPort.id,
      link_type: linkType as NetworkLinkType,
      cable_type: mediaInfo.cable_type,
      interface_class: mediaInfo.interface_class,
      link_role: linkRole,
      label,
      source_label: `${source.name}:${sourcePort.label}`,
      target_label: `${target.name}:${targetPort.label}`,
      connection_type: conn,
      speed: cfg.speed || null,
      lag_group: meta?.lagGroup ?? null,
      redundancy_path: meta?.path ?? null,
      media: mediaInfo.media,
      module: mediaInfo.module,
      cable_length_m: mediaInfo.length_m,
      wiring_rule_id: rule.id,
    })
    seq += 1
    return true
  }

  const allocation = String(cfg.allocation_mode || 'AUTO').toUpperCase()
  const useManualPairs =
    (rule.mode === 'manual' || allocation === 'MANUAL' || allocation === 'HYBRID') &&
    !!cfg.pairs?.length

  if (useManualPairs) {
    applyManualPairs(cfg.pairs!, nodes, pushLink, report)
    report.created = created.length
    report.ok = !report.issues.some((i) => i.level === 'error')
    return { links: created, report }
  }

  if (allocation === 'MANUAL' && !cfg.pairs?.length) {
    pushIssue(report, 'error', 'ERR_NO_FREE_PORT', '手动分配模式请先指定端口对')
    report.ok = false
    return { links: created, report }
  }

  const { sourceNodes, targetNodes } = resolveMatchedNodes(cfg, nodes, conn)
  report.matched_sources = sourceNodes.length
  report.matched_targets = targetNodes.length

  if (!sourceNodes.length || !targetNodes.length) {
    pushIssue(
      report,
      'error',
      'ERR_UNSUPPORTED_TOPOLOGY',
      `未匹配到源/目标设备（源 ${sourceNodes.length}，目标 ${targetNodes.length}）。源/目标可分别用设备组、手选设备或角色；组与手选为并集，两侧独立无需互相对应。`,
    )
    report.ok = false
    return { links: created, report }
  }

  maxTotal = Math.max(
    maxPerPair,
    Math.max(1, sourceNodes.length) * Math.max(1, targetNodes.length) * maxPerPair,
  )

  const sourceViews = adaptDevices(sourceNodes, occupied)
  const targetViews = adaptDevices(targetNodes, occupied)
  const allDevices = [...sourceViews]
  for (const t of targetViews) {
    if (!allDevices.some((d) => d.node.id === t.node.id)) allDevices.push(t)
  }

  const scenario = resolveScenario(sourceViews, targetViews, {
    peerLink: !!cfg.peer_link || conn === 'SWITCH_INTERCONNECT',
    forceBmc:
      conn === 'BMC_ENDPOINT' || sourceViews.some((d) => d.deviceType === 'BMC_SWITCH'),
    interconnectScope: cfg.interconnect_scope || 'INTRA_GROUP',
  })
  report.scenario = scenario
  report.scenario_label = SCENARIO_LABELS[scenario]

  if (scenario === 'UNSUPPORTED') {
    pushIssue(
      report,
      'error',
      'ERR_UNSUPPORTED_TOPOLOGY',
      `当前源/目标类型组合不在支持范围（源 ${sourceViews[0]?.deviceType} ×${sourceViews.length}，目标 ${targetViews[0]?.deviceType} ×${targetViews.length}）`,
    )
    report.ok = false
    return { links: created, report }
  }

  const allowSpeedDowngrade =
    scenario === 'C1' ||
    scenario === 'C2' ||
    scenario === 'C3' ||
    scenario === 'C4' ||
    cfg.speed_mode === 'MIN'
  const ctx: AlgoCtx = {
    occupied,
    pushLink,
    report,
    allowSpeedDowngrade,
    allDevices,
    cfg,
  }

  runScenarioEngine(scenario, ctx, sourceViews, targetViews, perPair)

  report.created = created.length
  if (!created.length && cfg.required) {
    if (!report.issues.some((i) => i.level === 'error')) {
      pushIssue(
        report,
        'error',
        'ERR_NO_FREE_PORT',
        `场景 ${scenario} 未生成任何连线：请检查端口 Purpose/速率/空闲口`,
      )
    }
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

/** 供 UI：从节点取空闲口选项 */
export function listFreePortOptions(
  node: NetworkNode,
  occupied: Set<string> = new Set(),
): Array<{ id: string; label: string; port: FramePort }> {
  annotatePortMediaAndInterface(node.port_layout?.ports)
  return (node.port_layout?.ports || [])
    .filter((p) => !p.peer_node_id && !p.reserved && !occupied.has(`${node.id}:${p.id}`))
    .map((p) => ({
      id: p.id,
      label: `${p.label} (${p.port_type}${p.purpose ? '/' + p.purpose : ''})`,
      port: p,
    }))
}
