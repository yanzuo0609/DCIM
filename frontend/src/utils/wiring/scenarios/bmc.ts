/**
 * 场景 B1 — BMC 管理交换机 → 服务器 IPMI
 */

import type { AlgoCtx } from '@/utils/wiring/algorithms'
import { bmcPred, downlinkPred, linkPair, pickFilteredPort } from '@/utils/wiring/algorithms'
import { pushIssue } from '@/utils/wiring/constraints'
import type { RuleDeviceView } from '@/utils/wiring/types'

function sortByName(list: RuleDeviceView[]): RuleDeviceView[] {
  return [...list].sort((a, b) => a.node.name.localeCompare(b.node.name, 'zh-CN'))
}

export function runBmcScenario(
  ctx: AlgoCtx,
  sources: RuleDeviceView[],
  targets: RuleDeviceView[],
): number {
  const srcs = sortByName(sources)
  const tgts = sortByName(targets)
  let total = 0
  let srcTurn = 0

  for (const tgt of tgts) {
    const tp = pickFilteredPort(ctx, tgt, 'target', bmcPred())
    if (!tp) {
      pushIssue(
        ctx.report,
        'error',
        'ERR_NO_BMC_INTERFACE',
        `${tgt.node.name} 没有可用的 IPMI/BMC 接口`,
        tgt.node.id,
      )
      continue
    }

    let linked = false
    for (let k = 0; k < srcs.length; k++) {
      const si = (srcTurn + k) % srcs.length
      const sp = pickFilteredPort(ctx, srcs[si], 'source', downlinkPred('1G'))
      if (!sp) continue
      if (linkPair(ctx, srcs[si], sp, tgt, tp, { path: null })) {
        total += 1
        linked = true
        srcTurn = (si + 1) % srcs.length
        break
      }
    }
    if (!linked) {
      pushIssue(ctx.report, 'error', 'ERR_NO_FREE_PORT', 'BMC 交换机无可用下联口')
      break
    }
  }
  return total
}
