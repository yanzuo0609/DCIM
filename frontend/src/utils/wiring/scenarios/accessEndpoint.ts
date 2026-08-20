/**
 * 场景 A1/A2/A3 — 接入 → 服务器/安全设备
 *
 * A2/A3 容量原则（按端口，不按设备数对齐）：
 * - link_count 表示每台目标设备的总链路数，链路在源交换机之间轮询分散
 * - 是否够接：看交换机下联空闲口总数 ≥ 服务器数 × 每台上联数
 * - 只要交换机还有空闲口就可继续接入；单台服务器口不够时跳过/部分接入并告警
 */

import { accessSpeedClass } from '@/utils/wiringDeviceType'
import {
  type AlgoCtx,
  downlinkPred,
  linkPair,
  listFilteredPorts,
  pickFilteredPort,
  pickTargetPortsForSwitchGroup,
  serverNicPred,
} from '@/utils/wiring/algorithms'
import { pushIssue } from '@/utils/wiring/constraints'
import type { RuleDeviceView, ScenarioId } from '@/utils/wiring/types'

function srcAccessSpeed(sources: RuleDeviceView[]): '10G' | '1G' {
  const t = sources[0]?.deviceType
  return accessSpeedClass(t || 'ACCESS_SWITCH_10G') || '10G'
}

function sortByName(list: RuleDeviceView[]): RuleDeviceView[] {
  const collator = new Intl.Collator('zh-CN', { numeric: true, sensitivity: 'base' })
  return [...list].sort((a, b) => collator.compare(a.node.name, b.node.name))
}

function countSwitchDownlinks(
  ctx: AlgoCtx,
  sources: RuleDeviceView[],
  speed: '10G' | '1G',
): number {
  return sources.reduce(
    (n, s) => n + listFilteredPorts(ctx, s, 'source', downlinkPred(speed)).length,
    0,
  )
}

/** A1: 单台 → 单台 */
function runA1(ctx: AlgoCtx, sources: RuleDeviceView[], targets: RuleDeviceView[], rounds: number) {
  const src = sources[0]
  const tgt = targets[0]
  const speed = srcAccessSpeed(sources)
  let made = 0
  for (let r = 0; r < rounds; r++) {
    const sp = pickFilteredPort(ctx, src, 'source', downlinkPred(speed))
    const tp = pickFilteredPort(
      ctx,
      tgt,
      'target',
      serverNicPred(speed),
      ctx.cfg.source_port_policy === 'SAME_NUMBER' || ctx.cfg.target_port_policy === 'SAME_NUMBER'
        ? sp?.portNum
        : null,
    )
    if (!sp || !tp) {
      if (!made) {
        if (!sp) {
          pushIssue(ctx.report, 'error', 'ERR_NO_FREE_PORT', `${src.node.name} 无匹配空闲下联口`, src.node.id)
        } else if (!tp) {
          pushIssue(
            ctx.report,
            'error',
            'ERR_NO_MATCHING_INTERFACE',
            `${tgt.node.name} 无匹配 ${speed} 业务口`,
            tgt.node.id,
          )
        }
      }
      break
    }
    if (linkPair(ctx, src, sp, tgt, tp, { path: r % 2 === 0 ? 'A' : 'B' })) made += 1
    else break
  }
  return made
}

/**
 * 将一台服务器分别上联到源组内每台交换机（每台交换机 rounds 条）。
 * 不预先要求服务器 NIC 数 == 交换机台数；逐台交换机取口，口不够则告警并尽量接入。
 */
function wireServerToSwitchGroup(
  ctx: AlgoCtx,
  sources: RuleDeviceView[],
  tgt: RuleDeviceView,
  plannedLinks: number,
  speed: '10G' | '1G',
): number {
  const srcs = sortByName(sources)
  let total = 0
  const linkedSourceIds = new Set<string>()
  const desired = Math.max(1, plannedLinks)
  const spreadPorts = pickTargetPortsForSwitchGroup(ctx, tgt, desired, speed)

  for (let linkIndex = 0; linkIndex < desired; linkIndex++) {
    // 每条冗余链路选择不同的上联设备，并优先选择剩余口最多的设备，
    // 使连续多台服务器在所有上联交换机之间自动均衡。
    const selected = srcs
      .map((src, sourceIndex) => ({
        src,
        sourceIndex,
        freeCount: listFilteredPorts(ctx, src, 'source', downlinkPred(speed)).length,
        port: pickFilteredPort(ctx, src, 'source', downlinkPred(speed)),
      }))
      .filter((item) => !linkedSourceIds.has(item.src.node.id) && item.port && item.freeCount > 0)
      .sort((a, b) => b.freeCount - a.freeCount || a.sourceIndex - b.sourceIndex)[0] || null
    if (!selected) break
    const tp = spreadPorts?.[linkIndex] || pickFilteredPort(ctx, tgt, 'target', serverNicPred(speed))
    if (!tp) {
      pushIssue(
        ctx.report,
        'warning',
        'ERR_NO_MATCHING_INTERFACE',
        `${tgt.node.name} 匹配 ${speed} 口不足，计划 ${desired} 条、已生成 ${total} 条`,
        tgt.node.id,
      )
      break
    }
    if (
      linkPair(ctx, selected.src, selected.port!, tgt, tp, {
        path: selected.sourceIndex % 2 === 0 ? 'A' : 'B',
        lagGroup: ctx.cfg.lag === false ? null : `LAG-${tgt.node.name}`,
      })
    ) {
      linkedSourceIds.add(selected.src.node.id)
      total += 1
    }
  }

  if (!total) {
    const nicFree = listFilteredPorts(ctx, tgt, 'target', serverNicPred(speed)).length
    const swFree = countSwitchDownlinks(ctx, srcs, speed)
    pushIssue(
      ctx.report,
      swFree <= 0 ? 'error' : 'warning',
      swFree <= 0 ? 'ERR_NO_FREE_PORT' : 'ERR_NO_MATCHING_INTERFACE',
      swFree <= 0
        ? `交换机下联口不足，无法接入 ${tgt.node.name}`
        : `${tgt.node.name} 无可用 ${speed} 业务口（交换机仍有 ${swFree} 个下联空闲口；服务器剩余匹配口 ${nicFree}）`,
      tgt.node.id,
    )
  } else if (ctx.cfg.device_diversity === 'REQUIRED' && srcs.length > 1 && linkedSourceIds.size < Math.min(srcs.length, desired)) {
    pushIssue(
      ctx.report,
      'warning',
      'ERR_INSUFFICIENT_PORTS',
      `${tgt.node.name} 计划跨 ${Math.min(srcs.length, desired)} 台交换机，实际仅使用 ${linkedSourceIds.size} 台，冗余域未完全满足`,
      tgt.node.id,
    )
  }
  return total
}

/** A2: 交换机组 → 单台服务器 */
function runA2(ctx: AlgoCtx, sources: RuleDeviceView[], targets: RuleDeviceView[], rounds: number) {
  const tgt = targets[0]
  const speed = srcAccessSpeed(sources)
  const srcs = sortByName(sources)
  const perServer = Math.max(1, rounds)
  const swFree = countSwitchDownlinks(ctx, srcs, speed)
  if (swFree < perServer) {
    pushIssue(
      ctx.report,
      'warning',
      'ERR_INSUFFICIENT_PORTS',
      `交换机下联空闲口 ${swFree} < 本服务器计划上联 ${perServer} 条，将按剩余端口尽力接入`,
    )
  }
  return wireServerToSwitchGroup(ctx, srcs, tgt, Math.max(1, rounds), speed)
}

/**
 * A3: 组 → 组
 * 容量按「交换机下联口总数」判断；每台服务器分别上联到组内每台交换机。
 */
function runA3(ctx: AlgoCtx, sources: RuleDeviceView[], targets: RuleDeviceView[], rounds: number) {
  const srcs = sortByName(sources)
  const tgts = sortByName(targets)
  const speed = srcAccessSpeed(sources)
  const r = Math.max(1, rounds)
  const perServer = r
  const swFree = countSwitchDownlinks(ctx, srcs, speed)
  const needed = tgts.length * perServer

  if (swFree <= 0) {
    pushIssue(
      ctx.report,
      'error',
      'ERR_NO_FREE_PORT',
      `源交换机组无可用下联口，无法接入 ${tgts.length} 台目标设备`,
    )
    return 0
  }

  if (swFree < needed) {
    const maxServers = Math.floor(swFree / Math.max(1, perServer))
    pushIssue(
      ctx.report,
      'warning',
      'ERR_INSUFFICIENT_PORTS',
      `交换机下联空闲口 ${swFree}，按每台上联 ${perServer} 条最多约 ${maxServers} 台；目标 ${tgts.length} 台，将按剩余端口继续接入（不要求源/目标设备数一致）`,
    )
  }

  let total = 0
  let wiredTargets = 0
  for (const tgt of tgts) {
    // 交换机口已耗尽则停止，不再因后续服务器报「不足以接入 N 台交换机」
    if (countSwitchDownlinks(ctx, srcs, speed) <= 0) {
      pushIssue(
        ctx.report,
        'warning',
        'ERR_INSUFFICIENT_PORTS',
        `交换机下联口已用尽，已接入 ${wiredTargets}/${tgts.length} 台目标设备`,
      )
      break
    }
    const made = wireServerToSwitchGroup(ctx, srcs, tgt, r, speed)
    if (made > 0) {
      total += made
      wiredTargets += 1
    }
  }

  if (!total) {
    pushIssue(ctx.report, 'error', 'ERR_NO_FREE_PORT', '组到组交叉连接未生成任何链路')
  }
  return total
}

export function runAccessEndpointScenario(
  scenario: ScenarioId,
  ctx: AlgoCtx,
  sources: RuleDeviceView[],
  targets: RuleDeviceView[],
  linksPerSource: number,
): number {
  const rounds = Math.max(1, linksPerSource)
  if (scenario === 'A1') return runA1(ctx, sources, targets, rounds)
  if (scenario === 'A2') return runA2(ctx, sources, targets, rounds)
  if (scenario === 'A3') return runA3(ctx, sources, targets, rounds)
  return 0
}
