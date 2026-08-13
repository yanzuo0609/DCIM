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
  return [...list].sort((a, b) => a.node.name.localeCompare(b.node.name, 'zh-CN'))
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

/** C2: 源组每台 1 线 → 目标 UPLINK 顺序分配 */
function runC2(ctx: AlgoCtx, sources: RuleDeviceView[], targets: RuleDeviceView[], rounds: number) {
  const tgt = targets[0]
  const srcs = sortByName(sources)
  let total = 0
  for (let r = 0; r < rounds; r++) {
    let roundMade = 0
    for (let i = 0; i < srcs.length; i++) {
      const src = srcs[i]
      const sp = pickFilteredPort(ctx, src, 'source', downlinkPred(null))
      const tp = pickFilteredPort(ctx, tgt, 'target', uplinkPred(null))
      if (!sp || !tp) {
        if (!total && !sp) {
          pushIssue(ctx.report, 'error', 'ERR_NO_FREE_PORT', `${src.node.name} 无可用下联/板卡口`, src.node.id)
        } else if (!total && !tp) {
          pushIssue(ctx.report, 'error', 'ERR_INSUFFICIENT_PORTS', `${tgt.node.name} UPLINK 不足`, tgt.node.id)
        }
        continue
      }
      if (
        linkPair(ctx, src, sp, tgt, tp, {
          path: i % 2 === 0 ? 'A' : 'B',
          lagGroup: `LAG-${tgt.node.name}-up`,
        })
      ) {
        roundMade += 1
        total += 1
      }
    }
    if (!roundMade) break
  }
  return total
}

/**
 * C3: 核心/汇聚组 → 接入组（完全二分）
 * - 每台接入必须与源组内【每一台】核心/汇聚都有连线（禁止两条上联落到同一台核心）
 * - 每对设备可连 link_count 条（≥1）
 * - 单台接入占用的上联口总数 ≤ 其可用 UPLINK 数，且须能覆盖「源台数 × 每对条数」；
 *   若 UPLINK 不足则压缩每对条数，但至少保证与每台源各 1 条（否则报不足）
 */
function runC3(ctx: AlgoCtx, sources: RuleDeviceView[], targets: RuleDeviceView[], rounds: number) {
  const srcs = sortByName(sources)
  const tgts = sortByName(targets)
  if (!srcs.length || !tgts.length) return 0

  const linksPerPairWanted = Math.max(1, rounds)
  let total = 0
  /** targetId -> set of sourceIds already linked */
  const coverage = new Map<string, Set<string>>()

  for (const tgt of tgts) {
    const uplinkFree = listFilteredPorts(ctx, tgt, 'target', uplinkPred(null)).length
    if (uplinkFree < srcs.length) {
      pushIssue(
        ctx.report,
        'error',
        'ERR_INSUFFICIENT_PORTS',
        `${tgt.node.name} 可用 UPLINK 仅 ${uplinkFree}，少于源组 ${srcs.length} 台，无法做到「每台核心各至少 1 条上联」`,
        tgt.node.id,
      )
      continue
    }

    // 每对条数：尽量满足 link_count；占用上联数须 < 可用 UPLINK（口数刚好=源台数时允许用满以保全覆盖）
    const maxUsable = uplinkFree > srcs.length ? uplinkFree - 1 : uplinkFree
    const perPair = Math.max(
      1,
      Math.min(linksPerPairWanted, Math.floor(maxUsable / srcs.length)),
    )
    if (perPair * srcs.length > uplinkFree) {
      pushIssue(
        ctx.report,
        'error',
        'ERR_INSUFFICIENT_PORTS',
        `${tgt.node.name} UPLINK=${uplinkFree} 不足以连接 ${srcs.length} 台源（每台至少 1 条）`,
        tgt.node.id,
      )
      continue
    }

    const linkedSrcs = coverage.get(tgt.node.id) || new Set<string>()
    coverage.set(tgt.node.id, linkedSrcs)

    for (let si = 0; si < srcs.length; si++) {
      const src = srcs[si]
      let madePair = 0
      for (let r = 0; r < perPair; r++) {
        const sp = pickFilteredPort(ctx, src, 'source', downlinkPred(null))
        const tp = pickFilteredPort(ctx, tgt, 'target', uplinkPred(null))
        if (!sp) {
          pushIssue(
            ctx.report,
            'warning',
            'ERR_NO_FREE_PORT',
            `${src.node.name} DOWNLINK/板卡口不足，无法与 ${tgt.node.name} 建齐 ${perPair} 条`,
            src.node.id,
          )
          break
        }
        if (!tp) {
          pushIssue(
            ctx.report,
            'warning',
            'ERR_INSUFFICIENT_PORTS',
            `${tgt.node.name} UPLINK 在连接过程中耗尽`,
            tgt.node.id,
          )
          break
        }
        if (
          linkPair(ctx, src, sp, tgt, tp, {
            path: si % 2 === 0 ? 'A' : 'B',
            lagGroup: `LAG-${tgt.node.name}-${src.node.name}`,
          })
        ) {
          total += 1
          madePair += 1
          linkedSrcs.add(src.node.id)
        }
      }
      if (!madePair) {
        pushIssue(
          ctx.report,
          'error',
          'ERR_NO_FREE_PORT',
          `${tgt.node.name} 未能连接到源 ${src.node.name}（要求与源组每台设备都有连线）`,
          tgt.node.id,
        )
      }
    }
  }

  // 校验：每台接入是否覆盖全部源
  const incomplete: string[] = []
  for (const tgt of tgts) {
    const set = coverage.get(tgt.node.id)
    if (!set || set.size < srcs.length) {
      const miss = srcs.filter((s) => !set?.has(s.node.id)).map((s) => s.node.name)
      incomplete.push(`${tgt.node.name}↔缺[${miss.join(',')}]`)
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
  } else if (incomplete.length) {
    pushIssue(
      ctx.report,
      'error',
      'ERR_INSUFFICIENT_PORTS',
      `未做到「每台接入↔每台核心」全覆盖：${incomplete.join('；')}`,
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
