/**
 * 规则端口候选池 — docs/18 V2 §3/§5
 * purpose/pool → speed → media → range/ids/types → AVAILABLE → sort(policy)
 */

import type { FramePort } from '@/api/network'
import {
  resolveEffectivePortPool,
  type PortSelectPolicy,
  type WiringRuleConfig,
} from '@/utils/wiringTypes'
import { derivePortMedia } from '@/utils/wiringDeviceType'
import {
  mediaOf,
  portSpeedLabel,
  speedRank,
} from '@/utils/wiring/constraints'
import { freePorts } from '@/utils/wiring/deviceAdapter'
import type { RuleDeviceView, RulePortView } from '@/utils/wiring/types'

export type PortFilterSide = 'source' | 'target'

function parsePortRange(range: string | null | undefined): { min: number; max: number } | null {
  if (!range) return null
  const s = String(range).trim()
  if (!s) return null
  const m = s.match(/^(\d+)\s*[-~–]\s*(\d+)$/)
  if (m) {
    const a = Number(m[1])
    const b = Number(m[2])
    return { min: Math.min(a, b), max: Math.max(a, b) }
  }
  const n = Number(s)
  if (Number.isFinite(n)) return { min: n, max: n }
  return null
}

function portInRange(p: RulePortView, range: { min: number; max: number } | null): boolean {
  if (!range) return true
  const n = p.portNum
  if (n == null) return false
  return n >= range.min && n <= range.max
}

function matchesPurpose(p: RulePortView, purpose: string | null | undefined): boolean {
  if (!purpose) return true
  const want = String(purpose).toUpperCase()
  const role = String(p.role || p.port.purpose || '').toUpperCase()
  const pt = String(p.port.port_type || '').toLowerCase()
  const label = String(p.port.label || '')
  const isDedicatedUplinkLabel = /^U\d+/i.test(label)

  if (want === 'DOWNLINK') {
    if (role === 'PEER' || role === 'DAD' || role === 'MGMT') return false
    // 专用上联区（U1/U2…）不作下联
    if (role === 'UPLINK' && isDedicatedUplinkLabel) return false
    if (role === 'DOWNLINK' || role === 'SERVER' || !role) return true
    // 1G/10G/25G 业务板卡口
    if (pt === '1g' || pt === '10g' || pt === '25g') return role !== 'UPLINK' || !isDedicatedUplinkLabel
    // 核心/汇聚板卡 40/100G：模型常误标 UPLINK，但 C 场景作 DOWNLINK 下联接入
    if (pt === '40_100g') return !isDedicatedUplinkLabel
    return false
  }
  if (want === 'SERVER') {
    // 业务 NIC：容忍误标 UPLINK（服务器口常见历史脏数据）
    if (label.toUpperCase().includes('IPMI') || label.toUpperCase().includes('BMC')) return false
    if (pt !== '1g' && pt !== '10g' && pt !== '25g') return false
    if (role === 'MGMT' || role === 'PEER' || role === 'DAD') return false
    return true
  }
  if (want === 'UPLINK') {
    return role === 'UPLINK' || pt === '40_100g' || isDedicatedUplinkLabel
  }
  if (want === 'MGMT') {
    const lab = label.toUpperCase()
    if (
      pt === 'bmc' ||
      role === 'MGMT' ||
      lab.includes('IPMI') ||
      lab.includes('BMC')
    ) {
      return true
    }
    return (role === 'DOWNLINK' || !role) && pt === '1g'
  }
  if (want === 'PEER' || want === 'DAD') {
    return role === want || (!!p.port.reserved && role === want)
  }
  return role === want
}

function matchesPool(p: RulePortView, pool: string | null | undefined): boolean {
  if (!pool || pool === 'AUTO') return true
  const role = String(p.role || '').toUpperCase()
  const pt = String(p.port.port_type || '').toLowerCase()
  const label = String(p.port.label || '')
  if (pool === 'UPLINK') {
    return pt === '40_100g' || role === 'UPLINK' || /^U\d+/i.test(label)
  }
  if (pool === 'OPTICAL') {
    // 板卡光/业务口：排除专用上联小区 U1… 与 PEER/DAD
    if (role === 'PEER' || role === 'DAD') return false
    if (role === 'UPLINK' && /^U\d+/i.test(label)) return false
    return pt === '1g' || pt === '10g' || pt === '25g' || pt === '40_100g'
  }
  return true
}

function matchesSpeed(
  p: RulePortView,
  speed: string | null | undefined,
  mode: string | null | undefined,
): boolean {
  if (!speed) return true
  const want = speedRank(speed)
  if (!want) return true
  const got = speedRank(portSpeedLabel(p.port.port_type) || p.speed)
  if (!got) return false
  const m = String(mode || 'EXACT').toUpperCase()
  if (m === 'MIN') return got >= want
  return got === want
}

function matchesPortMedia(p: RulePortView, filter: string | null | undefined): boolean {
  if (!filter || filter === 'AUTO') return true
  const want = String(filter).trim()
  const upper = want.toUpperCase()

  // 旧值兼容
  if (upper === 'FIBER' || upper === 'COPPER') {
    return mediaOf(p.port) === upper
  }

  const physical =
    upper === 'LC_LC' || upper === 'MPO8' || upper === 'MPO4' || upper.startsWith('CUSTOM_')
      ? upper.startsWith('CUSTOM_')
        ? null
        : 'FIBER'
      : null

  // 内置光纤接头类：要求光口
  if (upper === 'LC_LC' || upper === 'MPO8' || upper === 'MPO4') {
    if (mediaOf(p.port) !== 'FIBER') return false
    const kind = String(p.port.media_kind || '').toUpperCase()
    const lab = `${p.port.label || ''} ${p.port.interface_type || ''}`.toUpperCase()
    if (upper === 'LC_LC') {
      // LC 常见于 10G/25G SFP；无细标时放行所有光口
      if (kind.includes('QSFP') && !lab.includes('LC')) return true
      return true
    }
    if (upper === 'MPO8' || upper === 'MPO4') {
      // MPO 常见于 40/100G QSFP；无细标时放行 40_100g / QSFP
      if (p.port.port_type === '40_100g' || kind.includes('QSFP') || lab.includes('MPO')) return true
      // 软匹配：光口也允许（模型尚未打 MPO 标时不卡死）
      return mediaOf(p.port) === 'FIBER'
    }
  }

  // 自定义：端口 media_kind / interface / label 含名称关键字则命中；否则仅按粗分
  if (physical === null && upper.startsWith('CUSTOM_')) {
    const hay = `${p.port.media_kind || ''} ${p.port.interface_type || ''} ${p.port.label || ''}`.toUpperCase()
    if (hay.includes(upper.replace(/^CUSTOM_/, ''))) return true
    // 无细标：不硬拒，避免无标注口全部被滤空
    return true
  }

  // 按中文标签软匹配（用户可能存了 label）
  const hay2 = `${p.port.media_kind || ''} ${p.port.interface_type || ''} ${p.port.label || ''}`.toUpperCase()
  if (want.includes('MPO') || upper.includes('MPO')) {
    return mediaOf(p.port) === 'FIBER'
  }
  if (want.includes('LC') || upper.includes('LC')) {
    return mediaOf(p.port) === 'FIBER'
  }
  if (want.includes('电') || upper.includes('RJ45') || upper.includes('COPPER')) {
    return mediaOf(p.port) === 'COPPER'
  }
  if (want.includes('光') || upper.includes('FIBER')) {
    return mediaOf(p.port) === 'FIBER'
  }
  return true
}

function matchesTypes(p: RulePortView, types: string[] | undefined): boolean {
  if (!types?.length) return true
  const pt = String(p.port.port_type || '').toLowerCase()
  const speed = portSpeedLabel(p.port.port_type).toUpperCase()
  return types.some((t) => {
    const x = String(t).trim().toLowerCase()
    if (!x) return false
    if (x === pt) return true
    if (x.replace(/[^0-9a-z]/g, '') === speed.toLowerCase()) return true
    return false
  })
}

function matchesIds(p: RulePortView, ids: string[] | undefined): boolean {
  if (!ids?.length) return true
  return ids.includes(p.port.id)
}

function isAvailable(p: RulePortView): boolean {
  if (!p.free) return false
  const st = String(p.port.status || '').toUpperCase()
  if (st === 'DISABLED' || st === 'FAULT' || st === 'NOT_SUPPORTED' || st === 'OCCUPIED') {
    return false
  }
  // RESERVED：仅当未占用且场景需要 PEER/DAD 时由 purpose 放行；默认跳过
  if (p.port.reserved && st !== 'AVAILABLE') {
    const role = String(p.role || '').toUpperCase()
    if (role !== 'PEER' && role !== 'DAD') return false
  }
  return true
}

function sortByPolicy(list: RulePortView[], policy: PortSelectPolicy | null | undefined): RulePortView[] {
  const p = policy || 'MIN_ASC'
  const sorted = [...list]
  if (p === 'MAX_DESC') {
    sorted.sort((a, b) => {
      const sa = a.slotId ?? 999
      const sb = b.slotId ?? 999
      if (sa !== sb) return sa - sb
      return (b.portNum ?? 0) - (a.portNum ?? 0)
    })
    return sorted
  }
  if (p === 'SLOT_SPREAD') {
    // 按 slot 交错：slot1.p0, slot2.p0, … 再 slot1.p1 …
    const bySlot = new Map<number, RulePortView[]>()
    for (const item of sorted) {
      const sid = item.slotId ?? 0
      if (!bySlot.has(sid)) bySlot.set(sid, [])
      bySlot.get(sid)!.push(item)
    }
    for (const arr of bySlot.values()) {
      arr.sort((a, b) => (a.portNum ?? 0) - (b.portNum ?? 0))
    }
    const slotIds = [...bySlot.keys()].sort((a, b) => a - b)
    const out: RulePortView[] = []
    let guard = 0
    const maxLen = Math.max(0, ...[...bySlot.values()].map((a) => a.length))
    while (out.length < sorted.length && guard < maxLen + 2) {
      for (const sid of slotIds) {
        const arr = bySlot.get(sid) || []
        if (arr[guard]) out.push(arr[guard])
      }
      guard += 1
    }
    return out
  }
  // MIN_ASC / SAME_NUMBER（同号在配对层处理，池内仍升序）
  sorted.sort((a, b) => {
    const sa = a.slotId ?? 999
    const sb = b.slotId ?? 999
    if (sa !== sb) return sa - sb
    return (a.portNum ?? 0) - (b.portNum ?? 0)
  })
  return sorted
}

export interface BuildCandidateOptions {
  /** 额外谓词（场景拓扑约束，如同速类） */
  extraPred?: (p: RulePortView) => boolean
  /** SAME_NUMBER 配对时的对端口号 */
  preferPortNum?: number | null
}

/**
 * 按规则配置构建候选口（仅 AVAILABLE / free）
 */
export function buildCandidatePorts(
  device: RuleDeviceView,
  side: PortFilterSide,
  cfg: WiringRuleConfig,
  opts?: BuildCandidateOptions,
): RulePortView[] {
  const purpose =
    side === 'source' ? cfg.source_port_purpose : cfg.target_port_purpose
  const pool = resolveEffectivePortPool(
    side === 'source' ? cfg.source_port_pool : cfg.target_port_pool,
    purpose,
  )
  const range = parsePortRange(
    side === 'source' ? cfg.source_port_range : cfg.target_port_range,
  )
  const types = side === 'source' ? cfg.source_port_types : cfg.target_port_types
  const ids = side === 'source' ? cfg.source_port_ids : cfg.target_port_ids
  const policy =
    (side === 'source' ? cfg.source_port_policy : cfg.target_port_policy) || 'MIN_ASC'
  const speed = cfg.port_speed || cfg.speed
  const speedMode = cfg.speed_mode
  const portMedia = cfg.port_media

  let list = freePorts(device, () => true).filter((p) => {
    if (!isAvailable(p)) return false
    if (!matchesPurpose(p, purpose)) return false
    if (!matchesPool(p, pool)) return false
    if (!matchesPortMedia(p, portMedia)) return false
    if (!portInRange(p, range)) return false
    if (!matchesTypes(p, types)) return false
    if (!matchesIds(p, ids)) return false
    if (opts?.extraPred && !opts.extraPred(p)) return false
    return true
  })

  // 目的口 PURPOSE/池过严导致空池时：对 SERVER 场景软回退（保留速率/介质/范围）
  if (!list.length && purpose === 'SERVER') {
    list = freePorts(device, () => true).filter((p) => {
      if (!isAvailable(p)) return false
      if (!matchesPurpose(p, 'SERVER')) return false
      if (!matchesPortMedia(p, portMedia)) return false
      if (!portInRange(p, range)) return false
      if (!matchesTypes(p, types)) return false
      if (!matchesIds(p, ids)) return false
      if (opts?.extraPred && !opts.extraPred(p)) return false
      return true
    })
  }

  const withSpeed = list.filter((p) => matchesSpeed(p, speed, speedMode))
  if (withSpeed.length) {
    list = withSpeed
  } else if (speed && String(speedMode || 'EXACT').toUpperCase() === 'EXACT') {
    // EXACT：无匹配速率则尝试 MIN 软回退，避免规则残留 100G 把 10G 口滤空
    const soft = list.filter((p) => matchesSpeed(p, speed, 'MIN'))
    list = soft.length ? soft : []
  }
  // MIN 且无 ≥speed 口时软回退到未限速候选，避免 C 场景源板卡口被 100G 默认值清空
  else if (speed && String(speedMode || '').toUpperCase() === 'MIN' && !withSpeed.length) {
    // keep list as-is (unspeed-filtered)
  }

  list = sortByPolicy(list, policy)

  if (policy === 'SAME_NUMBER' && opts?.preferPortNum != null) {
    const prefer = opts.preferPortNum
    list = [
      ...list.filter((p) => p.portNum === prefer),
      ...list.filter((p) => p.portNum !== prefer),
    ]
  }

  return list
}

/** 取候选池第一个口 */
export function takeCandidatePort(
  device: RuleDeviceView,
  side: PortFilterSide,
  cfg: WiringRuleConfig,
  opts?: BuildCandidateOptions,
): RulePortView | null {
  return buildCandidatePorts(device, side, cfg, opts)[0] || null
}

/** 按 SLOT_SPREAD / 池顺序取 N 口 */
export function takeNCandidatePorts(
  device: RuleDeviceView,
  side: PortFilterSide,
  cfg: WiringRuleConfig,
  n: number,
  opts?: BuildCandidateOptions,
): RulePortView[] | null {
  const list = buildCandidatePorts(device, side, cfg, opts)
  if (list.length < n) return null
  return list.slice(0, n)
}

export function portMediaOf(port: FramePort): 'FIBER' | 'COPPER' {
  return mediaOf(port) || derivePortMedia(port.port_type)
}
