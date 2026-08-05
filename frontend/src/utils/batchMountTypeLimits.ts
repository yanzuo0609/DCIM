/** 批量上架：按设备类型记忆「每柜最多」台数（localStorage） */

const STORAGE_KEY = 'dcim.batchMount.perRackByType.v1'

/** 系统预置类型 code → 默认每柜本批上限 */
export const DEFAULT_PER_RACK_BY_TYPE_CODE: Record<string, number> = {
  compute: 10,
  storage: 4,
  network: 2,
  security: 2,
}

export type DeviceTypeLike = {
  id: string
  code: string
  name: string
}

export function clampPerRackCount(n: number): number {
  const v = Math.floor(Number(n) || 1)
  return Math.max(1, Math.min(200, v))
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
