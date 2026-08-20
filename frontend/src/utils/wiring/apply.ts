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
import { filterWiringNodesByLocation } from '@/utils/wiring/locationFilter'
import { alignAutomaticAccessRuleToHardware } from '@/utils/wiring/autoRuleConfig'
import {
  validateAutomaticUplinkDistribution,
  validateManualUplinkDistribution,
} from '@/utils/wiring/redundancy'
import { inferLinkType } from '@/utils/networkPortLayout'
import { normalizePortPurposeAlias } from '@/utils/fabricRole'
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
import { portSpeedLabel, pushIssue } from '@/utils/wiring/constraints'
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
  role: string | string[] | null | undefined,
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

function formatEndpointLabel(
  template: string | null | undefined,
  source: NetworkNode,
  sourcePort: FramePort,
  target: NetworkNode,
  targetPort: FramePort,
  seq: number,
): string {
  const value = template || '{source_device}-{source_port} / {target_device}-{target_port}'
  const replacements: Record<string, string> = {
    source_device: source.name,
    source_port: sourcePort.label || sourcePort.code || sourcePort.id,
    source_location: [source.device?.room_name, source.device?.rack_code].filter(Boolean).join('-') || '未定位',
    source_u: source.device?.u_position == null ? '未定U' : `${source.device.u_position}U`,
    target_device: target.name,
    target_port: targetPort.label || targetPort.code || targetPort.id,
    target_location: [target.device?.room_name, target.device?.rack_code].filter(Boolean).join('-') || '未定位',
    target_u: target.device?.u_position == null ? '未定U' : `${target.device.u_position}U`,
    seq: String(seq),
  }
  return Object.entries(replacements).reduce(
    (result, [key, replacement]) => result.replace(new RegExp(`\\{${key}\\}`, 'g'), replacement),
    value,
  )
}

function resolveMedia(
  cfg: WiringRuleConfig,
  source: NetworkNode,
  sourcePort: FramePort,
  target: NetworkNode,
  targetPort: FramePort,
): {
  cable_type: CableType
  interface_class: InterfaceClass
  media: MediaKind
  module: string | null
  length_m: number | null
} {
  const speedText = `${portSpeedLabel(sourcePort.port_type)} ${portSpeedLabel(targetPort.port_type)} ${cfg.speed || ''}`
  const speedGbps = Math.max(...(speedText.match(/\d+/g) || ['1']).map(Number))
  const portKinds = `${sourcePort.media_kind || ''} ${targetPort.media_kind || ''}`.toUpperCase()
  const bothCopper = sourcePort.media === 'COPPER' && targetPort.media === 'COPPER'
  const configured = (cfg.media || 'AUTO') as MediaKind

  let estimatedLength: number | null = null
  if (cfg.cable_length_mode === 'FIXED') {
    estimatedLength = Number(cfg.cable_length_m) || null
  } else {
    const sameRack =
      (!!source.device?.rack_id && source.device.rack_id === target.device?.rack_id) ||
      (!!source.device?.rack_code && source.device.rack_code === target.device?.rack_code)
    const sameRoom =
      (!!source.device?.room_id && source.device.room_id === target.device?.room_id) ||
      (!!source.device?.room_name && source.device.room_name === target.device?.room_name)
    const sourceU = Number(source.device?.u_position)
    const targetU = Number(target.device?.u_position)
    const vertical = Number.isFinite(sourceU) && Number.isFinite(targetU)
      ? Math.abs(sourceU - targetU) * 0.04445
      : 0
    const sourceRackNo = Number(String(source.device?.rack_code || '').match(/\d+/)?.[0])
    const targetRackNo = Number(String(target.device?.rack_code || '').match(/\d+/)?.[0])
    const rackHorizontal = Number.isFinite(sourceRackNo) && Number.isFinite(targetRackNo)
      ? Math.abs(sourceRackNo - targetRackNo) * 0.6
      : 0
    const canvasDistance = Math.hypot(source.pos_x - target.pos_x, source.pos_y - target.pos_y) / 100
    const routeBase = sameRack
      ? vertical
      : sameRoom
        ? Math.max(5, vertical + rackHorizontal, canvasDistance)
        : Math.max(20, vertical + rackHorizontal, canvasDistance)
    const withRoute = routeBase + Math.max(0, Number(cfg.route_extra_m) || 0)
    estimatedLength = withRoute * (1 + Math.max(0, Number(cfg.cable_slack_percent) || 0) / 100)
    const standards = [0.5, 1, 2, 3, 5, 7, 10, 15, 20, 30, 50, 100, 150, 200]
    estimatedLength = standards.find((length) => length >= estimatedLength!) || Math.ceil(estimatedLength / 50) * 50
  }

  let media: MediaKind = configured
  if (configured === 'AUTO' || configured === 'CUSTOM_SYNC') {
    if (bothCopper || /RJ45/.test(portKinds)) media = 'COPPER'
    else if (/\bDAC\b/.test(portKinds) && (estimatedLength || 0) <= 5) media = 'DAC'
    else if (/\bAOC\b/.test(portKinds) && (estimatedLength || 0) <= 30) media = 'AOC'
    else media = (estimatedLength || 0) > 100 ? 'FIBER_SM' : 'FIBER_MM'
  }
  let cable_type: CableType = 'other'
  let interface_class: InterfaceClass = 'other'
  const opticalLaneSuffix = speedGbps >= 400 ? '8' : speedGbps >= 40 ? '4' : ''
  if (media === 'DAC') {
    cable_type = 'dac'
    interface_class = 'dac'
  } else if (media === 'AOC') {
    cable_type = 'aoc'
    interface_class = 'optical'
  } else if (media === 'FIBER_SM' || media === 'MPO_MPO_OS2' || media === 'LC_LC_OS2') {
    cable_type = 'fiber_sm'
    interface_class = 'optical'
  } else if (
    media === 'FIBER_MM' ||
    media === 'MPO' ||
    media === 'BREAKOUT_1X4' ||
    media === 'MPO_MPO_OM34' ||
    media === 'LC_LC_OM34' ||
    media === 'MPO_LC_BREAKOUT'
  ) {
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
    module:
      cfg.module ||
      (media === 'COPPER' || media === 'DAC' || media === 'AOC'
        ? null
        : `${speedGbps}G-${['FIBER_SM', 'MPO_MPO_OS2', 'LC_LC_OS2'].includes(media) ? 'LR' : 'SR'}${opticalLaneSuffix}`),
    length_m: estimatedLength,
  }
}

function resolveMatchedNodes(cfg: WiringRuleConfig, nodes: NetworkNode[], conn: ConnectionType) {
  const scope = cfg.interconnect_scope || 'INTRA_GROUP'
  if ((cfg.peer_link || conn === 'SWITCH_INTERCONNECT') && scope === 'INTRA_GROUP') {
    const role = cfg.source_roles?.length
      ? cfg.source_roles
      : cfg.target_roles?.length
        ? cfg.target_roles
        : cfg.source_role || cfg.target_role || 'ACCESS'
    const matchedPeers = matchNodes(
      nodes,
      cfg.source_node_ids?.length ? cfg.source_node_ids : undefined,
      role,
      resolveWiringGroups(cfg.source_groups, cfg.source_group),
    )
    const peers = filterWiringNodesByLocation(
      filterWiringNodesByLocation(matchedPeers, cfg, 'source'),
      cfg,
      'target',
    )
    return { sourceNodes: peers, targetNodes: peers }
  }
  // 组间互联或其它连接：源/目标分别按设备参数匹配
  const sourceGroups = resolveWiringGroups(cfg.source_groups, cfg.source_group)
  let sourceNodes = filterWiringNodesByLocation(matchNodes(
    nodes,
    cfg.source_node_ids,
    cfg.source_roles?.length ? cfg.source_roles : cfg.source_role,
    sourceGroups,
  ), cfg, 'source')
  // BMC 场景仅在“只按角色”时自动收敛到管理交换机；显式设备/设备组仍尊重用户选择。
  if (
    conn === 'BMC_ENDPOINT' &&
    !cfg.source_node_ids?.length &&
    !sourceGroups.length
  ) {
    sourceNodes = sourceNodes.filter((node) => node.is_bmc_switch)
  }
  return {
    sourceNodes,
    targetNodes: filterWiringNodesByLocation(matchNodes(
      nodes,
      cfg.target_node_ids,
      cfg.target_roles?.length ? cfg.target_roles : cfg.target_role,
      resolveWiringGroups(cfg.target_groups, cfg.target_group),
    ), cfg, 'target'),
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
  if (cfgConnection(ctx.cfg) === 'CORE_TO_ACCESS') {
    const forcedScenario: ScenarioId = sourceViews.length === 1 && targetViews.length === 1
      ? 'C1'
      : sourceViews.length >= 2 && targetViews.length === 1
        ? 'C2'
        : 'C3'
    runCoreToAccessScenario(forcedScenario, ctx, sourceViews, targetViews, perPair)
    return
  }
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

function cfgConnection(cfg: WiringRuleConfig): ConnectionType {
  return (cfg.connection_type || 'CORE_TO_ACCESS') as ConnectionType
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
  alignAutomaticAccessRuleToHardware(cfg, sourceNodes)

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
    const distributionIssues = validateManualUplinkDistribution(cfg, cfg.pairs, nodes)
    if (distributionIssues.length) {
      pushIssue(report, 'error', 'ERR_INSUFFICIENT_PORTS', distributionIssues[0])
      return {
        scenario: 'UNSUPPORTED',
        scenario_label: '手动端口对',
        pairs: [],
        issues: report.issues,
        matched_sources: 0,
        matched_targets: 0,
        ok: false,
      }
    }
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
  alignAutomaticAccessRuleToHardware(cfg, sourceNodes)
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

  const distributionIssues = validateAutomaticUplinkDistribution(cfg, sourceNodes.length)
  if (distributionIssues.length) {
    pushIssue(report, 'error', 'ERR_INSUFFICIENT_PORTS', distributionIssues[0])
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

  if (
    cfg.device_diversity === 'REQUIRED' &&
    perPair > 1 &&
    sourceViews.length < 2
  ) {
    pushIssue(
      report,
      'error',
      'ERR_INSUFFICIENT_PORTS',
      `规则要求设备级冗余且每个目标计划 ${perPair} 条链路，但源范围仅匹配到 ${sourceViews.length} 台设备；请增加源设备或将设备分散改为可选。`,
    )
  }
  if (cfg.card_diversity === 'REQUIRED' && perPair > 1) {
    for (const target of targetViews) {
      const slots = new Set(
        target.ports.filter((port) => port.free && port.slotId != null).map((port) => port.slotId),
      )
      if (slots.size < 2) {
        pushIssue(
          report,
          'error',
          'ERR_INSUFFICIENT_PORTS',
          `${target.node.name} 要求跨 Slot/接口卡冗余，但可用接口仅覆盖 ${slots.size} 个槽位。`,
          target.node.id,
        )
      }
    }
  }
  if (report.issues.some((issue) => issue.level === 'error')) {
    report.ok = false
    return {
      scenario: 'UNSUPPORTED',
      scenario_label: '冗余条件未满足',
      pairs: [],
      issues: report.issues,
      matched_sources: sourceNodes.length,
      matched_targets: targetNodes.length,
      ok: false,
    }
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

  const allowSpeedDowngrade = cfg.speed_mode === 'MIN'
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
  const sourceRuleUsage = new Map<string, number>()
  for (const link of existingLinks) {
    if (link.wiring_rule_id !== rule.id) continue
    const source = nodes.find((node) => node.id === link.source_node_id)
    const sourcePort = source?.port_layout?.ports?.find(
      (port) => port.id === link.source_port || port.label === link.source_port,
    )
    // 单机接口上限仅统计交换机 DOWNLINK 业务口；UPLINK、Peer、DAD、MGMT
    // 即使由同一条规则创建，也不消耗此配额。
    if (!sourcePort || normalizePortPurposeAlias(sourcePort.purpose, source?.kind) !== 'DOWNLINK') continue
    sourceRuleUsage.set(link.source_node_id, (sourceRuleUsage.get(link.source_node_id) || 0) + 1)
  }

  const pushLink: PushLinkFn = (source, sourcePort, target, targetPort, meta) => {
    if (created.length >= maxTotal) return false
    const perDeviceLimit = cfg.source_port_limit_per_device
    const consumesDownlinkQuota =
      source.kind === 'switch' && normalizePortPurposeAlias(sourcePort.purpose, source.kind) === 'DOWNLINK'
    if (
      consumesDownlinkQuota &&
      perDeviceLimit != null &&
      (sourceRuleUsage.get(source.id) || 0) >= perDeviceLimit
    ) return false
    if (linkExists(existingLinks, source.id, sourcePort.id, target.id, targetPort.id)) return false
    if (linkExists(created, source.id, sourcePort.id, target.id, targetPort.id)) return false
    const mediaInfo = resolveMedia(cfg, source, sourcePort, target, targetPort)
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
      topology_id: rule.topology_id || '',
      source_node_id: source.id,
      target_node_id: target.id,
      source_port: sourcePort.id,
      target_port: targetPort.id,
      link_type: linkType as NetworkLinkType,
      cable_type: mediaInfo.cable_type,
      interface_class: mediaInfo.interface_class,
      link_role: linkRole,
      label,
      source_label: formatEndpointLabel(cfg.source_label_template, source, sourcePort, target, targetPort, seq),
      target_label: formatEndpointLabel(cfg.target_label_template, source, sourcePort, target, targetPort, seq),
      connection_type: conn,
      speed:
        portSpeedLabel(sourcePort.port_type) === portSpeedLabel(targetPort.port_type)
          ? portSpeedLabel(sourcePort.port_type)
          : portSpeedLabel(sourcePort.port_type) + '/' + portSpeedLabel(targetPort.port_type),
      lag_group: meta?.lagGroup ?? null,
      redundancy_path: meta?.path ?? null,
      media: mediaInfo.media,
      module: mediaInfo.module,
      cable_length_m: mediaInfo.length_m,
      wiring_rule_id: rule.id,
    })
    if (consumesDownlinkQuota) {
      sourceRuleUsage.set(source.id, (sourceRuleUsage.get(source.id) || 0) + 1)
    }
    seq += 1
    return true
  }

  const allocation = String(cfg.allocation_mode || 'AUTO').toUpperCase()
  const useManualPairs =
    (rule.mode === 'manual' || allocation === 'MANUAL' || allocation === 'HYBRID') &&
    !!cfg.pairs?.length

  if (useManualPairs) {
    const distributionIssues = validateManualUplinkDistribution(cfg, cfg.pairs || [], nodes)
    if (distributionIssues.length) {
      pushIssue(report, 'error', 'ERR_INSUFFICIENT_PORTS', distributionIssues[0])
      report.ok = false
      return { links: created, report }
    }
    maxTotal = Math.max(maxTotal, cfg.pairs?.length || 0)
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
  alignAutomaticAccessRuleToHardware(cfg, sourceNodes)
  maxTotal = Math.max(
    maxTotal,
    maxPerPair * Math.max(1, sourceNodes.length) * Math.max(1, targetNodes.length),
  )
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

  if (cfg.device_diversity === 'REQUIRED' && perPair > 1 && sourceViews.length < 2) {
    pushIssue(
      report,
      'error',
      'ERR_INSUFFICIENT_PORTS',
      `规则要求设备级冗余且每个目标计划 ${perPair} 条链路，但源范围仅匹配到 ${sourceViews.length} 台设备；请增加源设备或将设备分散改为可选。`,
    )
  }
  if (cfg.card_diversity === 'REQUIRED' && perPair > 1) {
    for (const target of targetViews) {
      const slots = new Set(
        target.ports.filter((port) => port.free && port.slotId != null).map((port) => port.slotId),
      )
      if (slots.size < 2) {
        pushIssue(
          report,
          'error',
          'ERR_INSUFFICIENT_PORTS',
          `${target.node.name} 要求跨 Slot/接口卡冗余，但可用接口仅覆盖 ${slots.size} 个槽位。`,
          target.node.id,
        )
      }
    }
  }
  if (report.issues.some((issue) => issue.level === 'error')) {
    report.ok = false
    return { links: created, report }
  }

  const distributionIssues = validateAutomaticUplinkDistribution(cfg, sourceNodes.length)
  if (distributionIssues.length) {
    pushIssue(report, 'error', 'ERR_INSUFFICIENT_PORTS', distributionIssues[0])
    report.ok = false
    return { links: created, report }
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

  const allowSpeedDowngrade = cfg.speed_mode === 'MIN'
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
