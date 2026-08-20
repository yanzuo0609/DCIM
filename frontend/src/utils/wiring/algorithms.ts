/**
 * 具名端口选择算法 — docs/18-rules_structured.md §7
 */

import type { FramePort, NetworkNode } from '@/api/network'
import type { WiringRuleConfig } from '@/utils/wiringTypes'
import { freePorts, refreshFreeFlags } from '@/utils/wiring/deviceAdapter'
import {
  isBmcPort,
  mediaCompatible,
  portMatchesAccessSpeed,
  speedsCompatible,
  pushIssue,
} from '@/utils/wiring/constraints'
import {
  buildCandidatePorts,
  takeCandidatePort,
  takeNCandidatePorts,
} from '@/utils/wiring/portFilter'
import type { RuleDeviceView, RulePortView, WiringApplyReport } from '@/utils/wiring/types'

export type PushLinkFn = (
  source: NetworkNode,
  sourcePort: FramePort,
  target: NetworkNode,
  targetPort: FramePort,
  meta?: { path?: string | null; lagGroup?: string | null },
) => boolean

const deviceSequenceCollator = new Intl.Collator('zh-CN', { numeric: true, sensitivity: 'base' })

/** 按设备名称中的自然编号排序：H1,H2,H10 / W1,W2 / Q1,Q2 / SER1,SER2 */
export function sortDevicesBySequence(list: RuleDeviceView[]): RuleDeviceView[] {
  return [...list].sort((a, b) => deviceSequenceCollator.compare(a.node.name, b.node.name))
}

export interface AlgoCtx {
  occupied: Set<string>
  pushLink: PushLinkFn
  report: WiringApplyReport
  allowSpeedDowngrade: boolean
  /** 刷新 free 标记用 */
  allDevices: RuleDeviceView[]
  /** 规则配置（驱动 portFilter） */
  cfg: WiringRuleConfig
}

function acceptPair(
  ctx: AlgoCtx,
  sp: RulePortView,
  tp: RulePortView,
): boolean {
  const media = mediaCompatible(sp.port, tp.port)
  if (!media.ok) {
    pushIssue(
      ctx.report,
      'warning',
      'ERR_MEDIA_MISMATCH',
      `介质不匹配 ${sp.media}↔${tp.media}`,
    )
    return false
  }
  const speed = speedsCompatible(sp.port, tp.port, ctx.allowSpeedDowngrade)
  if (!speed.ok) return false
  if (speed.warning) {
    pushIssue(ctx.report, 'warning', 'SPEED_DOWNGRADE', speed.warning)
  }
  return true
}

function takeFirst(
  list: RulePortView[],
  pred?: (p: RulePortView) => boolean,
): RulePortView | null {
  for (const p of list) {
    if (!pred || pred(p)) return p
  }
  return null
}

/** SEQUENTIAL_SCAN：从最小口号选第一个匹配 */
export function sequentialScan(
  device: RuleDeviceView,
  pred: (p: RulePortView) => boolean,
): RulePortView | null {
  return takeFirst(freePorts(device, pred))
}

/** MIN_SLOT_MIN_PORT */
export function minSlotMinPort(
  device: RuleDeviceView,
  pred: (p: RulePortView) => boolean,
): RulePortView | null {
  return sequentialScan(device, pred)
}

/** 规则候选池 + 可选场景谓词 */
export function pickFilteredPort(
  ctx: AlgoCtx,
  device: RuleDeviceView,
  side: 'source' | 'target',
  extraPred?: (p: RulePortView) => boolean,
  preferPortNum?: number | null,
): RulePortView | null {
  return takeCandidatePort(device, side, ctx.cfg, { extraPred, preferPortNum })
}

export function listFilteredPorts(
  ctx: AlgoCtx,
  device: RuleDeviceView,
  side: 'source' | 'target',
  extraPred?: (p: RulePortView) => boolean,
): RulePortView[] {
  return buildCandidatePorts(device, side, ctx.cfg, { extraPred })
}

function rolePred(role: string | string[]): (p: RulePortView) => boolean {
  const set = new Set((Array.isArray(role) ? role : [role]).map((r) => r.toUpperCase()))
  return (p) => {
    const r = (p.role || '').toUpperCase()
    const pt = String(p.port.port_type || '').toLowerCase()
    const label = String(p.port.label || '')
    const isDedicatedUplinkLabel = /^U\d+/i.test(label)

    if (set.has('DOWNLINK')) {
      if (r === 'PEER' || r === 'DAD' || r === 'MGMT') return false
      if (r === 'UPLINK' && isDedicatedUplinkLabel) return false
      if (r === 'DOWNLINK' || r === 'SERVER' || !r) {
        return pt === '1g' || pt === '10g' || pt === '25g' || pt === '40_100g'
      }
      // 板卡 40/100G 误标 UPLINK：仍可作为核心下联
      if (pt === '40_100g' && !isDedicatedUplinkLabel) return true
      if ((pt === '1g' || pt === '10g' || pt === '25g') && !isDedicatedUplinkLabel) return true
      return false
    }
    if (set.has('UPLINK')) {
      return r === 'UPLINK' || pt === '40_100g' || isDedicatedUplinkLabel
    }
    if (set.has('SERVER')) {
      if (isBmcPort(p.port)) return false
      if (r === 'MGMT' || r === 'PEER' || r === 'DAD') return false
      return pt === '1g' || pt === '10g' || pt === '25g'
    }
    if (set.has('MGMT') || set.has('BMC')) return isBmcPort(p.port)
    if (set.has('PEER')) return r === 'PEER' || (!!p.port.reserved && r === 'PEER')
    if (set.has('DAD')) return r === 'DAD'
    return set.has(r)
  }
}

export function downlinkPred(accessSpeed?: '10G' | '1G' | null) {
  const base = rolePred('DOWNLINK')
  return (p: RulePortView) => {
    if (!base(p)) return false
    if (accessSpeed && !portMatchesAccessSpeed(p.port, accessSpeed)) return false
    return true
  }
}

export function uplinkPred(accessSpeed?: '10G' | '1G' | null) {
  const base = rolePred('UPLINK')
  return (p: RulePortView) => {
    if (!base(p)) return false
    if (accessSpeed === '1G') {
      const s = String(p.speed)
      return s === '10G' || s === '1G' || s === '25G'
    }
    return true
  }
}

export function serverNicPred(accessSpeed: '10G' | '1G') {
  const base = rolePred('SERVER')
  return (p: RulePortView) => base(p) && portMatchesAccessSpeed(p.port, accessSpeed)
}

export function bmcPred() {
  return rolePred('MGMT')
}

/** 按 slot 分组的空闲业务口（规则过滤后） */
export function freeSlotsBySpeed(
  ctx: AlgoCtx,
  device: RuleDeviceView,
  accessSpeed: '10G' | '1G',
): Map<number, RulePortView[]> {
  const map = new Map<number, RulePortView[]>()
  for (const p of listFilteredPorts(ctx, device, 'target', serverNicPred(accessSpeed))) {
    const sid = p.slotId ?? 0
    if (!map.has(sid)) map.set(sid, [])
    map.get(sid)!.push(p)
  }
  return map
}

/**
 * ONE_PORT_PER_SLOT：N 台交换机 → 不同 slot 各取 1 口
 * ROUND_ROBIN_ACROSS_SLOTS：slot 不足时轮询
 */
export function pickTargetPortsForSwitchGroup(
  ctx: AlgoCtx,
  target: RuleDeviceView,
  switchCount: number,
  accessSpeed: '10G' | '1G',
): RulePortView[] | null {
  const cfg: WiringRuleConfig = {
    ...ctx.cfg,
    target_port_policy: ctx.cfg.target_port_policy || 'SLOT_SPREAD',
  }
  const fromFilter = takeNCandidatePorts(target, 'target', cfg, switchCount, {
    extraPred: serverNicPred(accessSpeed),
  })
  if (fromFilter) return fromFilter

  const bySlot = freeSlotsBySpeed(ctx, target, accessSpeed)
  const slotIds = [...bySlot.keys()].sort((a, b) => a - b)
  if (!slotIds.length) return null

  const result: RulePortView[] = []
  const cursors = new Map<number, number>()
  for (const id of slotIds) cursors.set(id, 0)

  if (slotIds.length >= switchCount) {
    for (let i = 0; i < switchCount; i++) {
      const sid = slotIds[i]
      const list = bySlot.get(sid) || []
      const idx = cursors.get(sid) || 0
      if (idx >= list.length) return null
      result.push(list[idx])
      cursors.set(sid, idx + 1)
    }
    return result
  }

  let guard = 0
  while (result.length < switchCount && guard < switchCount * 64) {
    guard += 1
    let progressed = false
    for (const sid of slotIds) {
      if (result.length >= switchCount) break
      const list = bySlot.get(sid) || []
      const idx = cursors.get(sid) || 0
      if (idx < list.length) {
        result.push(list[idx])
        cursors.set(sid, idx + 1)
        progressed = true
      }
    }
    if (!progressed) break
  }
  return result.length >= switchCount ? result : null
}

export function linkPair(
  ctx: AlgoCtx,
  src: RuleDeviceView,
  sp: RulePortView,
  tgt: RuleDeviceView,
  tp: RulePortView,
  meta?: { path?: string | null; lagGroup?: string | null },
): boolean {
  if (!sp.free || !tp.free) return false
  if (!acceptPair(ctx, sp, tp)) return false
  const ok = ctx.pushLink(src.node, sp.port, tgt.node, tp.port, meta)
  if (ok) {
    refreshFreeFlags(ctx.allDevices, ctx.occupied)
  }
  return ok
}

/** 尾部 N 个空闲口（按口号） */
export function tailFreePorts(
  device: RuleDeviceView,
  pred: (p: RulePortView) => boolean,
  n: number,
): RulePortView[] {
  const list = freePorts(device, pred)
  if (list.length <= n) return list
  return list.slice(-n)
}
