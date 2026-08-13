/**
 * 场景 D1/D2 — 交换机互联（对齐 docs/rules.md 第四节）
 * D1 组内：UPLINK 末 N 口 → peer-link；DOWNLINK 末 N 口 → DAD
 * D2 组间：各板卡末 2 口交叉互联；优先覆盖每台设备
 */

import type { AlgoCtx } from '@/utils/wiring/algorithms'
import {
  downlinkPred,
  linkPair,
  tailFreePorts,
  uplinkPred,
} from '@/utils/wiring/algorithms'
import { pushIssue } from '@/utils/wiring/constraints'
import { markReservedPeerDadPorts } from '@/utils/wiringDeviceType'
import { freePorts, refreshFreeFlags } from '@/utils/wiring/deviceAdapter'
import type { RuleDeviceView, RulePortView } from '@/utils/wiring/types'

function sortByName(list: RuleDeviceView[]): RuleDeviceView[] {
  return [...list].sort((a, b) => a.node.name.localeCompare(b.node.name, 'zh-CN'))
}

function pairDevices(devices: RuleDeviceView[]): [RuleDeviceView, RuleDeviceView][] {
  const pairs: [RuleDeviceView, RuleDeviceView][] = []
  const used = new Set<string>()
  const byGroup = new Map<string, RuleDeviceView[]>()
  for (const d of devices) {
    const g = d.groupId || '_default'
    if (!byGroup.has(g)) byGroup.set(g, [])
    byGroup.get(g)!.push(d)
  }
  for (const list of byGroup.values()) {
    const sorted = sortByName(list)
    for (let i = 0; i + 1 < sorted.length; i += 2) {
      const a = sorted[i]
      const b = sorted[i + 1]
      if (used.has(a.node.id) || used.has(b.node.id)) continue
      pairs.push([a, b])
      used.add(a.node.id)
      used.add(b.node.id)
    }
  }
  if (!pairs.length && devices.length >= 2) {
    const sorted = sortByName(devices)
    for (let i = 0; i + 1 < sorted.length; i += 2) {
      pairs.push([sorted[i], sorted[i + 1]])
    }
  }
  return pairs
}

function unlockReserved(p: RulePortView) {
  p.port.reserved = false
  p.free = true
}

function linkTailPair(
  ctx: AlgoCtx,
  a: RuleDeviceView,
  b: RuleDeviceView,
  pa: RulePortView,
  pb: RulePortView,
  role: 'PEER' | 'DAD',
): boolean {
  const ra = pa.port.reserved
  const rb = pb.port.reserved
  unlockReserved(pa)
  unlockReserved(pb)
  const ok = linkPair(ctx, a, pa, b, pb, {
    lagGroup: `${role}-${a.node.name}/${b.node.name}`,
    path: role === 'PEER' ? 'A' : 'B',
  })
  if (!ok) {
    pa.port.reserved = ra
    pb.port.reserved = rb
    return false
  }
  pa.port.purpose = role
  pb.port.purpose = role
  pa.port.reserved = true
  pb.port.reserved = true
  pa.port.reserved_for = role
  pb.port.reserved_for = role
  return true
}

/** D1: 同组 — UPLINK 尾口 peer，DOWNLINK 尾口 DAD */
export function runD1Scenario(ctx: AlgoCtx, devices: RuleDeviceView[]): number {
  for (const d of devices) markReservedPeerDadPorts(d.node)
  for (const d of devices) {
    for (const p of d.ports) {
      const raw = d.node.port_layout?.ports?.find((x) => x.id === p.port.id)
      if (!raw) continue
      p.role = raw.purpose || p.role
      p.port.reserved = raw.reserved
      p.free = !raw.peer_node_id && !ctx.occupied.has(`${d.node.id}:${raw.id}`)
      if (raw.reserved && (raw.purpose === 'PEER' || raw.purpose === 'DAD')) {
        p.free = !raw.peer_node_id && !ctx.occupied.has(`${d.node.id}:${raw.id}`)
      }
    }
  }

  const pairs = pairDevices(devices)
  if (!pairs.length) {
    pushIssue(ctx.report, 'error', 'ERR_UNSUPPORTED_TOPOLOGY', '未找到可配对的同组交换机（需至少 2 台）')
    return 0
  }

  const enablePeer = ctx.cfg.enable_peer_link !== false
  const enableDad = ctx.cfg.enable_dad !== false
  const peerN = Math.max(1, Number(ctx.cfg.peer_tail_count) || 2)
  const dadN = Math.max(1, Number(ctx.cfg.dad_tail_count) || 2)

  let total = 0
  for (const [a, b] of pairs) {
    if (enablePeer) {
      const ta = tailFreePorts(a, uplinkPred(null), peerN)
      const tb = tailFreePorts(b, uplinkPred(null), peerN)
      const n = Math.min(peerN, ta.length, tb.length)
      if (!n) {
        pushIssue(
          ctx.report,
          'error',
          'ERR_NO_FREE_PORT',
          `${a.node.name}/${b.node.name} UPLINK 尾口不足，无法建立 peer-link`,
        )
      }
      for (let i = 0; i < n; i++) {
        if (linkTailPair(ctx, a, b, ta[i], tb[i], 'PEER')) total += 1
      }
    }
    if (enableDad) {
      refreshFreeFlags(ctx.allDevices, ctx.occupied)
      const ta = tailFreePorts(a, downlinkPred(null), dadN)
      const tb = tailFreePorts(b, downlinkPred(null), dadN)
      const n = Math.min(dadN, ta.length, tb.length)
      if (!n) {
        pushIssue(
          ctx.report,
          'warning',
          'ERR_NO_FREE_PORT',
          `${a.node.name}/${b.node.name} DOWNLINK 尾口不足，DAD 未建立`,
        )
      }
      for (let i = 0; i < n; i++) {
        if (linkTailPair(ctx, a, b, ta[i], tb[i], 'DAD')) total += 1
      }
    }
  }
  if (!total) {
    pushIssue(ctx.report, 'error', 'ERR_NO_FREE_PORT', '组内互联未生成任何 peer/DAD 链路')
  }
  return total
}

/** 每板卡（slot）取末尾空闲口 */
function tailPortsPerSlot(
  device: RuleDeviceView,
  pred: (p: RulePortView) => boolean,
  perSlot: number,
): RulePortView[] {
  const bySlot = new Map<number, RulePortView[]>()
  for (const p of freePorts(device, pred)) {
    const sid = p.slotId ?? 0
    if (!bySlot.has(sid)) bySlot.set(sid, [])
    bySlot.get(sid)!.push(p)
  }
  const out: RulePortView[] = []
  for (const sid of [...bySlot.keys()].sort((a, b) => a - b)) {
    const list = bySlot.get(sid) || []
    out.push(...list.slice(-perSlot))
  }
  return out
}

/** D2: 跨组交叉 — 每板卡末 2 口；保证源/目标覆盖 */
export function runD2Scenario(
  ctx: AlgoCtx,
  sources: RuleDeviceView[],
  targets: RuleDeviceView[],
): number {
  const srcs = sortByName(sources)
  const tgts = sortByName(targets)
  let total = 0
  const perSlot = Math.max(1, Number(ctx.cfg.peer_tail_count) || 2)

  // 全连接覆盖：每源至少连一台目标，每目标至少连一台源
  const pairs: Array<[RuleDeviceView, RuleDeviceView]> = []
  const n = Math.max(srcs.length, tgts.length)
  for (let i = 0; i < n; i++) {
    pairs.push([srcs[i % srcs.length], tgts[i % tgts.length]])
  }
  // 额外：反向补齐，避免单向漏连
  for (let i = 0; i < tgts.length; i++) {
    const s = srcs[i % srcs.length]
    const t = tgts[i]
    if (!pairs.some(([a, b]) => a.node.id === s.node.id && b.node.id === t.node.id)) {
      pairs.push([s, t])
    }
  }

  for (const [src, tgt] of pairs) {
    if (src.node.id === tgt.node.id) continue
    const spList = tailPortsPerSlot(
      src,
      (p) => downlinkPred(null)(p) || uplinkPred(null)(p),
      perSlot,
    )
    const tpList = tailPortsPerSlot(
      tgt,
      (p) => downlinkPred(null)(p) || uplinkPred(null)(p),
      perSlot,
    )
    const sp = spList[0] || tailFreePorts(src, (p) => downlinkPred(null)(p) || uplinkPred(null)(p), 1)[0]
    const tp = tpList[0] || tailFreePorts(tgt, (p) => downlinkPred(null)(p) || uplinkPred(null)(p), 1)[0]
    if (!sp || !tp) {
      pushIssue(
        ctx.report,
        'warning',
        'ERR_NO_FREE_PORT',
        `${src.node.name}↔${tgt.node.name} 板卡尾口不足`,
      )
      continue
    }
    if (linkPair(ctx, src, sp, tgt, tp)) total += 1
  }

  if (!total) pushIssue(ctx.report, 'error', 'ERR_NO_FREE_PORT', '组间交叉互联未生成链路')
  return total
}
