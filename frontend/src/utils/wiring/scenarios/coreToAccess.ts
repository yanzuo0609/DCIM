/**
 * 场景 C1–C4 — 核心/汇聚 → 接入
 * C3：组→组完全二分；每台接入 ↔ 源组每台核心至少 1 条，禁止同核心双上联
 */

import type { AlgoCtx } from '@/utils/wiring/algorithms'
import {
  downlinkPred,
  linkPair,
  listFilteredPorts,
  pickFilteredPort,
  uplinkPred,
} from '@/utils/wiring/algorithms'
import { pushIssue } from '@/utils/wiring/constraints'
import type { RuleDeviceView, ScenarioId } from '@/utils/wiring/types'

function sortByName(list: RuleDeviceView[]): RuleDeviceView[] {
  const collator = new Intl.Collator('zh-CN', { numeric: true, sensitivity: 'base' })
  return [...list].sort((a, b) => collator.compare(a.node.name, b.node.name))
}

function runC1(ctx: AlgoCtx, sources: RuleDeviceView[], targets: RuleDeviceView[], rounds: number) {
  const src = sources[0]
  const tgt = targets[0]
  let made = 0
  for (let r = 0; r < rounds; r++) {
    const sp = pickFilteredPort(ctx, src, 'source', downlinkPred(null))
    const tp = pickFilteredPort(ctx, tgt, 'target', uplinkPred(null), sp?.portNum)
    if (!sp || !tp) {
      if (!made) {
        pushIssue(
          ctx.report,
          'error',
          'ERR_NO_FREE_PORT',
          !sp
            ? `${src.node.name} 无可用 DOWNLINK/板卡口（请确认板卡口未全部标成专用 UPLINK）`
            : `${tgt.node.name} 无空闲 UPLINK`,
          !sp ? src.node.id : tgt.node.id,
        )
      }
      break
    }
    if (linkPair(ctx, src, sp, tgt, tp, { path: r % 2 === 0 ? 'A' : 'B' })) made += 1
    else break
  }
  return made
}

/** C2: link_count 为目标总上联数，链路在源核心/汇聚之间轮询分散。 */
function runC2(ctx: AlgoCtx, sources: RuleDeviceView[], targets: RuleDeviceView[], rounds: number) {
  const tgt = targets[0]
  const srcs = sortByName(sources)
  let total = 0
  const usedSources = new Set<string>()
  for (let r = 0; r < Math.max(1, rounds); r++) {
    let linked = false
    for (let offset = 0; offset < srcs.length; offset++) {
      const i = (r + offset) % srcs.length
      const src = srcs[i]
      if (usedSources.has(src.node.id)) continue
      const sp = pickFilteredPort(ctx, src, 'source', downlinkPred(null))
      const tp = pickFilteredPort(ctx, tgt, 'target', uplinkPred(null))
      if (!sp || !tp) continue
      if (
        linkPair(ctx, src, sp, tgt, tp, {
          path: i % 2 === 0 ? 'A' : 'B',
          lagGroup: ctx.cfg.lag === false ? null : `LAG-${tgt.node.name}-up`,
        })
      ) {
        usedSources.add(src.node.id)
        total += 1
        linked = true
        break
      }
    }
    if (!linked) break
  }
  if (total < Math.max(1, rounds)) {
    pushIssue(ctx.report, total ? 'warning' : 'error', 'ERR_INSUFFICIENT_PORTS', `${tgt.node.name} 计划 ${Math.max(1, rounds)} 条上联，实际生成 ${total} 条`, tgt.node.id)
  }
  if (ctx.cfg.device_diversity === 'REQUIRED' && srcs.length > 1 && usedSources.size < Math.min(srcs.length, Math.max(1, rounds))) {
    pushIssue(ctx.report, 'error', 'ERR_INSUFFICIENT_PORTS', `${tgt.node.name} 上联未能分散到足够的源设备，存在单点风险`, tgt.node.id)
  }
  return total
}

/**
 * C3: 核心/汇聚组 → 接入组。
 * link_count 是每台目标交换机的总上联数；先跨源设备分散，再复用源设备追加链路。
 */
function runC3(ctx: AlgoCtx, sources: RuleDeviceView[], targets: RuleDeviceView[], rounds: number) {
  const srcs = sortByName(sources)
  const tgts = sortByName(targets)
  if (!srcs.length || !tgts.length) return 0
  const planned = Math.max(1, rounds)
  let total = 0

  for (const tgt of tgts) {
    const uplinkFree = listFilteredPorts(ctx, tgt, 'target', uplinkPred(null)).length
    if (uplinkFree < planned) {
      pushIssue(
        ctx.report,
        uplinkFree ? 'warning' : 'error',
        'ERR_INSUFFICIENT_PORTS',
        `${tgt.node.name} 可用 UPLINK ${uplinkFree} 个，少于计划链路 ${planned} 条`,
        tgt.node.id,
      )
    }
    if (ctx.cfg.device_diversity === 'REQUIRED' && srcs.length > planned) {
      pushIssue(
        ctx.report,
        'error',
        'ERR_INSUFFICIENT_PORTS',
        `${tgt.node.name} 计划 ${planned} 条上联，无法覆盖 ${srcs.length} 台源设备；请增加链路数或缩小源范围`,
        tgt.node.id,
      )
    }
    const linkedSrcs = new Set<string>()
    let madeForTarget = 0
    for (let r = 0; r < planned; r++) {
      let linked = false
      const candidates = srcs
        .map((src, si) => ({
          src,
          si,
          freeCount: listFilteredPorts(ctx, src, 'source', downlinkPred(null)).length,
        }))
        .filter((item) => !linkedSrcs.has(item.src.node.id) && item.freeCount > 0)
        .sort((a, b) => b.freeCount - a.freeCount || a.si - b.si)
      for (const { src, si } of candidates) {
        const sp = pickFilteredPort(ctx, src, 'source', downlinkPred(null))
        const tp = pickFilteredPort(ctx, tgt, 'target', uplinkPred(null))
        if (!sp || !tp) continue
        if (
          linkPair(ctx, src, sp, tgt, tp, {
            path: si % 2 === 0 ? 'A' : 'B',
            lagGroup: ctx.cfg.lag === false ? null : `LAG-${tgt.node.name}-up`,
          })
        ) {
          total += 1
          madeForTarget += 1
          linkedSrcs.add(src.node.id)
          linked = true
          break
        }
      }
      if (!linked) break
    }
    if (madeForTarget < planned) {
      pushIssue(ctx.report, madeForTarget ? 'warning' : 'error', 'ERR_INSUFFICIENT_PORTS', `${tgt.node.name} 计划 ${planned} 条上联，实际生成 ${madeForTarget} 条`, tgt.node.id)
    }
    if (ctx.cfg.device_diversity === 'REQUIRED' && srcs.length > 1 && linkedSrcs.size < Math.min(srcs.length, planned)) {
      pushIssue(ctx.report, 'error', 'ERR_INSUFFICIENT_PORTS', `${tgt.node.name} 上联仅分散到 ${linkedSrcs.size} 台源设备，未满足冗余域要求`, tgt.node.id)
    }
  }

  if (!total) {
    const srcFree = srcs.reduce(
      (n, d) => n + listFilteredPorts(ctx, d, 'source', downlinkPred(null)).length,
      0,
    )
    const tgtFree = tgts.reduce(
      (n, d) => n + listFilteredPorts(ctx, d, 'target', uplinkPred(null)).length,
      0,
    )
    pushIssue(
      ctx.report,
      'error',
      'ERR_NO_FREE_PORT',
      `核心/汇聚组到接入组未生成链路（源侧板卡/DOWNLINK ${srcFree}，目标 UPLINK ${tgtFree}）`,
    )
  }
  return total
}

export function runCoreToAccessScenario(
  scenario: ScenarioId,
  ctx: AlgoCtx,
  sources: RuleDeviceView[],
  targets: RuleDeviceView[],
  linksPerSource: number,
): number {
  const rounds = Math.max(1, linksPerSource)
  if (scenario === 'C1') return runC1(ctx, sources, targets, rounds)
  if (scenario === 'C2') return runC2(ctx, sources, targets, rounds)
  if (scenario === 'C3' || scenario === 'C4') {
    if (sources.length === 1 && targets.length === 1) return runC1(ctx, sources, targets, rounds)
    if (sources.length >= 2 && targets.length === 1) return runC2(ctx, sources, targets, rounds)
    return runC3(ctx, sources, targets, rounds)
  }
  return 0
}
