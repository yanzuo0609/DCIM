/** 设备类型细分：千兆/万兆交换机等不得共用同一类型 */

export type DeviceTypeLike = {
  id: string
  code: string
  name: string
}

/** 系统预置类型 code → 默认本批每柜上限 */
export const DEFAULT_PER_RACK_BY_TYPE_CODE: Record<string, number> = {
  compute: 10,
  storage: 4,
  switch_1g: 2,
  switch_10g: 2,
  switch_bmc_1g: 2,
  switch_ai: 2,
  switch_agg: 2,
  switch_core: 1,
  gpu: 4,
  router: 2,
  network: 2,
  security: 2,
}

const STORAGE_KEY = 'dcim.batchMount.perRackByType.v1'

export function clampPerRackCount(n: number): number {
  const v = Math.floor(Number(n) || 1)
  return Math.max(1, Math.min(200, v))
}

/** 从名称/型号文本推断设备类型 code（千兆与万兆互斥） */
export function inferDeviceTypeCodeFromText(
  ...parts: Array<string | null | undefined>
): string | null {
  const text = parts.filter(Boolean).join(' ').trim()
  if (!text) return null
  const lower = text.toLowerCase()
  const compact = lower.replace(/[\s_\-/]+/g, '')

  if (/gpu/.test(lower) || /GPU/.test(text)) return 'gpu'
  if (/bmc/.test(lower) && (/千兆|1g|gigabit|交换|switch/.test(lower) || /千兆/.test(text))) {
    return 'switch_bmc_1g'
  }
  if (/\bai\b|人工智能|智能网/.test(lower) && /交换|switch/.test(lower)) return 'switch_ai'
  if (/存储|storage|san|nas|disk/.test(lower)) return 'storage'
  if (/服务器|server|compute|host|刀片/.test(lower) && !/交换|switch/.test(lower)) {
    return 'compute'
  }
  if (/核心/.test(text) && /交换|switch/.test(lower)) return 'switch_core'
  if (/汇聚/.test(text) && /交换|switch/.test(lower)) return 'switch_agg'
  if (/路由|router/.test(lower)) return 'router'

  // 万兆优先于千兆，避免「万兆」被千兆规则误伤
  if (
    /万兆|10g|10ge|10gb|tengig|ten_gigabit|ten-gigabit/.test(compact)
    || /万兆/.test(text)
  ) {
    return 'switch_10g'
  }
  if (
    /千兆|1ge\b|1g(?!\d)|gigabit|ge交换机/.test(lower)
    || /千兆/.test(text)
  ) {
    return 'switch_1g'
  }
  if (/交换|switch/.test(lower)) return 'network'
  return null
}

/** 在类型列表中按推断 code / 名称命中 */
export function resolveDeviceTypeByInfer(
  types: DeviceTypeLike[],
  ...parts: Array<string | null | undefined>
): DeviceTypeLike | null {
  if (!types.length) return null
  const code = inferDeviceTypeCodeFromText(...parts)
  if (!code) return null
  const byCode = types.find((t) => t.code === code)
  if (byCode) return byCode
  // 名称兜底（库中可能尚未跑迁移但已手工建类型）
  const nameHints: Record<string, RegExp> = {
    switch_10g: /万兆/,
    switch_1g: /千兆/,
    switch_core: /核心/,
    switch_agg: /汇聚/,
    router: /路由/,
    security: /安全|防火墙/,
    storage: /存储/,
    compute: /计算|服务器/,
  }
  const re = nameHints[code]
  if (re) {
    const byName = types.find((t) => re.test(t.name))
    if (byName) return byName
  }
  return null
}

/** 未保存过时，按类型 code/名称推断合理默认值 */
export function defaultPerRackForType(
  code: string | null | undefined,
  name?: string | null,
): number {
  const c = (code || '').trim().toLowerCase()
  if (c && DEFAULT_PER_RACK_BY_TYPE_CODE[c] != null) {
    return DEFAULT_PER_RACK_BY_TYPE_CODE[c]
  }
  const inferred = inferDeviceTypeCodeFromText(code, name)
  if (inferred && DEFAULT_PER_RACK_BY_TYPE_CODE[inferred] != null) {
    return DEFAULT_PER_RACK_BY_TYPE_CODE[inferred]
  }
  const text = `${code || ''} ${name || ''}`.toLowerCase()
  if (/network|switch|router|交换机|网络|路由/.test(text)) return 2
  if (/storage|san|nas|存储/.test(text)) return 4
  if (/security|firewall|waf|安全|防火墙/.test(text)) return 2
  if (/compute|server|host|计算|服务器/.test(text)) return 10
  return 1
}

export function loadPerRackLimits(): Record<string, number> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as Record<string, unknown>
    if (!parsed || typeof parsed !== 'object') return {}
    const out: Record<string, number> = {}
    for (const [key, val] of Object.entries(parsed)) {
      if (!key) continue
      out[key] = clampPerRackCount(Number(val))
    }
    return out
  } catch {
    return {}
  }
}

export function savePerRackLimits(map: Record<string, number>) {
  const cleaned: Record<string, number> = {}
  for (const [key, val] of Object.entries(map)) {
    if (!key) continue
    cleaned[key] = clampPerRackCount(val)
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(cleaned))
}

export function typeLimitStorageKey(type: DeviceTypeLike): string {
  return (type.code || type.id).trim() || type.id
}

export function getPerRackLimitForType(type: DeviceTypeLike | null | undefined): number {
  if (!type) return 1
  const map = loadPerRackLimits()
  const byCode = map[type.code]
  if (byCode != null) return clampPerRackCount(byCode)
  const byId = map[type.id]
  if (byId != null) return clampPerRackCount(byId)
  return defaultPerRackForType(type.code, type.name)
}

export function setPerRackLimitForType(type: DeviceTypeLike, count: number) {
  const map = loadPerRackLimits()
  map[typeLimitStorageKey(type)] = clampPerRackCount(count)
  savePerRackLimits(map)
}
