/**
 * 布线原则说明与默认策略 — 对齐 docs/rules.md
 * 场景路由仍由 wiring/scenarioRouter 决定；本模块描述「人可读原则」与表单默认。
 */

import type { ConnectionType, WiringRuleConfig } from '@/utils/wiringTypes'
import { migrateConnectionType } from '@/utils/wiringTypes'

export type InterconnectScope = 'INTRA_GROUP' | 'INTER_GROUP'

export interface WiringPrincipleHint {
  id: string
  title: string
  bullets: string[]
}

/** 按连接类型给出原则摘要（UI 展示） */
export function principleHintsForConnection(conn: string | null | undefined): WiringPrincipleHint {
  const c = migrateConnectionType(conn)
  if (c === 'ACCESS_ENDPOINT') {
    return {
      id: 'A',
      title: '接入 → 服务器/安全设备',
      bullets: [
        '源口固定 DOWNLINK：自动时每台交换机从最小空闲口号递增选口',
        '目标为服务器时按 Slot 分散：交换机数 ≤ Slot 数则每台进不同 Slot；不足则同 Slot 轮询口号',
        '万兆接入仅对接服务器 10G/25G 业务口；无匹配口提示「缺少匹配的接口」',
        '组→组时：每台服务器分别双上联到组内每台交换机',
      ],
    }
  }
  if (c === 'BMC_ENDPOINT') {
    return {
      id: 'B',
      title: 'BMC → 服务器/安全设备',
      bullets: [
        '千兆 BMC 交换机从 0 口起顺序连接各服务器 IPMI/BMC 口',
        '目标仅使用 MGMT/IPMI 口，不占用业务网卡',
      ],
    }
  }
  if (c === 'CORE_TO_ACCESS') {
    return {
      id: 'C',
      title: '核心/汇聚 → 接入交换机',
      bullets: [
        '源口 DOWNLINK（板卡最小 Slot、最小口号）；目标口 UPLINK',
        '单台↔单台 / 组↔单台 / 组↔组均保证每台设备至少一条上联',
        '目标为千兆接入时允许速率降级（万兆板卡 → 千兆 UPLINK）',
      ],
    }
  }
  return {
    id: 'D',
    title: '交换机互联（Peer / DAD）',
    bullets: [
      '组内：UPLINK 末 N 口做 peer-link，DOWNLINK 末 N 口做 DAD（默认 N=2）',
      '组间：默认手动指定端口对；自动时取各板卡末 2 口交叉互联',
      '需保证除组内堆叠外，源组与目标组每台设备均有连线',
    ],
  }
}

/** 根据场景规模补充原则（检测到的 A1/A2…） */
export function principleBulletsForScenario(scenario: string | null | undefined): string[] {
  switch (scenario) {
    case 'A1':
      return ['当前：单台接入 → 单台服务器（A1），按链路数循环取最小空闲口']
    case 'A2':
      return ['当前：接入组 → 单台服务器（A2），目标 Slot 分散，每源交换机 1 线']
    case 'A3':
      return [
        '当前：接入组 → 服务器组（A3）',
        '每台服务器上联分别接到源组内每台交换机；容量按交换机下联空闲口总数判断，不要求源/目标台数一致',
      ]
    case 'B1':
      return ['当前：BMC 管理布线（B1）']
    case 'C1':
      return ['当前：单台核心/汇聚 → 单台接入（C1）']
    case 'C2':
      return ['当前：核心/汇聚组 → 单台接入（C2），目标 UPLINK 顺序分配']
    case 'C3':
    case 'C4':
      return [
        '当前：核心/汇聚组 → 接入组（C3/C4）',
        '每台接入须分别上联到源组内每一台核心/汇聚（完全二分，禁止双上联落到同一台）',
        '每对可多条（link_count），但单台接入占用上联数须小于其可用 UPLINK 数（口数刚好等于源台数时除外）',
      ]
    case 'D1':
      return ['当前：组内互联（D1）— Peer 用 UPLINK 尾口，DAD 用 DOWNLINK 尾口']
    case 'D2':
      return ['当前：组间互联（D2）— 板卡尾口交叉；建议手动核对端口对']
    default:
      return []
  }
}

/** 连接类型切换时套用 rules.md 默认策略 */
export function applyPrincipleDefaults(cfg: WiringRuleConfig): WiringRuleConfig {
  const conn = migrateConnectionType(cfg.connection_type) as ConnectionType
  if (conn === 'ACCESS_ENDPOINT') {
    cfg.source_port_policy = cfg.source_port_policy || 'MIN_ASC'
    cfg.target_port_policy = 'SLOT_SPREAD'
    cfg.speed_mode = 'EXACT'
    cfg.allocation_mode = cfg.allocation_mode || 'AUTO'
  } else if (conn === 'BMC_ENDPOINT') {
    cfg.source_port_policy = 'MIN_ASC'
    cfg.target_port_policy = 'MIN_ASC'
    cfg.speed = '1G'
    cfg.port_speed = '1G'
    cfg.speed_mode = 'EXACT'
  } else if (conn === 'CORE_TO_ACCESS') {
    cfg.source_port_policy = 'MIN_ASC'
    cfg.target_port_policy = 'MIN_ASC'
    cfg.speed_mode = 'MIN'
  } else if (conn === 'SWITCH_INTERCONNECT') {
    cfg.interconnect_scope = cfg.interconnect_scope || 'INTRA_GROUP'
    cfg.enable_peer_link = cfg.enable_peer_link ?? true
    cfg.enable_dad = cfg.enable_dad ?? true
    cfg.peer_tail_count = cfg.peer_tail_count ?? 2
    cfg.dad_tail_count = cfg.dad_tail_count ?? 2
    if (cfg.interconnect_scope === 'INTER_GROUP') {
      cfg.allocation_mode = cfg.allocation_mode === 'AUTO' ? 'AUTO' : 'MANUAL'
    } else {
      cfg.allocation_mode = 'AUTO'
    }
  }
  return cfg
}
