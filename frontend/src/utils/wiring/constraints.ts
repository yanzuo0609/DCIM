/**
 * 统一错误与约束 — docs/18-rules_structured.md §6 / §8
 */

import type { FramePort } from '@/api/network'
import { derivePortMedia } from '@/utils/wiringDeviceType'
import type { WiringApplyIssue, WiringApplyReport } from '@/utils/wiring/types'
import { ERROR_CODE_META } from '@/utils/wiring/types'

export function pushIssue(
  report: WiringApplyReport,
  level: WiringApplyIssue['level'],
  code: string,
  message: string,
  deviceId?: string,
) {
  const meta = ERROR_CODE_META[code]
  const prefix = meta ? `[${meta.code}] ` : ''
  report.issues.push({
    level,
    code: meta?.code || code,
    message: `${prefix}${message}`,
    device_id: deviceId,
  })
}

export function speedRank(s: string | null | undefined): number {
  if (!s) return 0
  const key = String(s).trim().toUpperCase().replace('_', '')
  const map: Record<string, number> = {
    '1G': 1,
    '10G': 10,
    '25G': 25,
    '40G': 40,
    '40_100G': 100,
    '100G': 100,
    '400G': 400,
    BMC: 1,
  }
  if (map[key] != null) return map[key]
  const n = Number(key.replace(/[^0-9.]/g, ''))
  return Number.isFinite(n) ? n : 0
}

export function portSpeedLabel(portType: string | null | undefined): string {
  const t = String(portType || '').toLowerCase()
  if (t === '1g' || t === 'bmc') return '1G'
  if (t === '10g') return '10G'
  if (t === '25g') return '25G'
  if (t === '40_100g') return '100G'
  return 'OTHER'
}

export function mediaOf(port: FramePort): 'FIBER' | 'COPPER' {
  if (port.media === 'FIBER' || port.media === 'COPPER') return port.media
  return derivePortMedia(port.port_type)
}

/** A 场景：严格同速；C4 等允许降速时源≥目标即可 */
export function speedsCompatible(
  src: FramePort,
  tgt: FramePort,
  allowDowngrade: boolean,
): { ok: boolean; warning?: string } {
  const sr = speedRank(portSpeedLabel(src.port_type))
  const tr = speedRank(portSpeedLabel(tgt.port_type))
  if (sr === tr) return { ok: true }
  if (allowDowngrade && sr > 0 && tr > 0 && (sr >= tr || tr >= sr)) {
    return {
      ok: true,
      warning: `速率降级 ${portSpeedLabel(src.port_type)}↔${portSpeedLabel(tgt.port_type)}`,
    }
  }
  return { ok: false }
}

export function mediaCompatible(
  src: FramePort,
  tgt: FramePort,
): { ok: boolean; code?: string } {
  const a = mediaOf(src)
  const b = mediaOf(tgt)
  if (a === b) return { ok: true }
  return { ok: false, code: 'ERR_MEDIA_MISMATCH' }
}

/** 匹配业务网口速率类：10G 交换机对 10G/25G slot；1G 只对 1G */
export function portMatchesAccessSpeed(
  port: FramePort,
  accessSpeed: '10G' | '1G',
): boolean {
  const label = portSpeedLabel(port.port_type)
  if (accessSpeed === '10G') return label === '10G' || label === '25G'
  return label === '1G'
}

export function isBmcPort(port: FramePort): boolean {
  const pt = String(port.port_type || '').toLowerCase()
  if (pt === 'bmc') return true
  const purpose = String(port.purpose || '').toUpperCase()
  const lab = String(port.label || '').toUpperCase()
  if (purpose === 'MGMT' || purpose === 'BMC') {
    return lab.includes('IPMI') || lab.includes('BMC') || pt === 'bmc'
  }
  return lab.includes('IPMI') || lab.includes('BMC')
}
