/**
 * 布线引擎类型 — 对齐 docs/18-rules_structured.md
 */

import type { FramePort, NetworkLink, NetworkNode } from '@/api/network'
import type { WiringDeviceType } from '@/utils/wiringDeviceType'

export type ScenarioId =
  | 'A1'
  | 'A2'
  | 'A3'
  | 'B1'
  | 'C1'
  | 'C2'
  | 'C3'
  | 'C4'
  | 'D1'
  | 'D2'
  | 'UNSUPPORTED'

export const SCENARIO_LABELS: Record<ScenarioId, string> = {
  A1: '单台接入 → 单台服务器/安全设备',
  A2: '接入组 → 单台服务器/安全设备',
  A3: '接入组 → 服务器/安全设备组',
  B1: 'BMC 管理交换机 → 服务器 IPMI',
  C1: '单台核心/汇聚 → 单台接入',
  C2: '核心/汇聚组 → 单台接入',
  C3: '核心/汇聚组 → 接入组',
  C4: '核心/汇聚 → 千兆接入（可降速）',
  D1: '同组交换机互联（PEER/DAD）',
  D2: '组间交换机交叉互联',
  UNSUPPORTED: '不支持的拓扑组合',
}

/** 文档 §6 错误码 */
export type WiringErrorCode =
  | 'ERR_NO_FREE_PORT'
  | 'ERR_PORT_TYPE_MISMATCH'
  | 'ERR_NO_MATCHING_INTERFACE'
  | 'ERR_INSUFFICIENT_PORTS'
  | 'ERR_NO_BMC_INTERFACE'
  | 'ERR_UNSUPPORTED_TOPOLOGY'
  | 'ERR_MEDIA_MISMATCH'
  | 'ERR_SPEED_MISMATCH'
  | 'E001'
  | 'E002'
  | 'E003'
  | 'E004'
  | 'E005'
  | 'E006'
  | 'E007'
  | 'E008'

export const ERROR_CODE_META: Record<
  string,
  { code: string; message: string }
> = {
  ERR_NO_FREE_PORT: { code: 'E001', message: '无可用端口' },
  ERR_PORT_TYPE_MISMATCH: { code: 'E002', message: '端口类型不匹配' },
  ERR_NO_MATCHING_INTERFACE: { code: 'E003', message: '缺少匹配的接口' },
  ERR_INSUFFICIENT_PORTS: { code: 'E004', message: '端口数量不足' },
  ERR_NO_BMC_INTERFACE: { code: 'E005', message: '服务器无BMC/IPMI接口' },
  ERR_UNSUPPORTED_TOPOLOGY: { code: 'E006', message: '不支持的拓扑结构' },
  ERR_MEDIA_MISMATCH: { code: 'E007', message: '介质类型不匹配' },
  ERR_SPEED_MISMATCH: { code: 'E008', message: '速率不匹配' },
}

export interface WiringApplyIssue {
  level: 'error' | 'warning' | 'info'
  code: string
  message: string
  device_id?: string
}

export interface WiringApplyReport {
  created: number
  matched_sources: number
  matched_targets: number
  scenario?: ScenarioId | null
  scenario_label?: string | null
  issues: WiringApplyIssue[]
  ok: boolean
}

export interface WiringApplyResult {
  links: NetworkLink[]
  report: WiringApplyReport
}

export interface RulePortView {
  port: FramePort
  slotId: number | null
  portNum: number | null
  speed: '1G' | '10G' | '25G' | '40G' | '100G' | 'OTHER'
  media: 'FIBER' | 'COPPER'
  role: string | null
  free: boolean
}

export interface RuleDeviceView {
  node: NetworkNode
  deviceType: WiringDeviceType
  groupId: string | null
  groupSize: number
  ports: RulePortView[]
}

export interface ScenarioContext {
  sources: RuleDeviceView[]
  targets: RuleDeviceView[]
  scenario: ScenarioId
  allowSpeedDowngrade: boolean
  linksPerSource: number
  minLinksPerTarget: number
  maxTotal: number
}
