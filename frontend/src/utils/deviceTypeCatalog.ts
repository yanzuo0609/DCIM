import type { DeviceType } from '@/api/device'

/** 与设备管理一致的固定设备类型清单 */
export const DEVICE_TYPE_CODES = [
  'compute',
  'storage',
  'switch_core',
  'switch_agg',
  'switch_10g',
  'switch_1g',
  'switch_bmc_1g',
  'switch_ai',
  'security',
  'gpu',
  'other',
] as const

export type DeviceTypeCode = (typeof DEVICE_TYPE_CODES)[number]

export const DEVICE_TYPE_FALLBACK_NAMES: Record<DeviceTypeCode, string> = {
  compute: '计算服务器',
  storage: '存储服务器',
  switch_core: '核心交换机',
  switch_agg: '汇聚交换机',
  switch_10g: '万兆交换机',
  switch_1g: '千兆交换机',
  switch_bmc_1g: 'BMC千兆交换机',
  switch_ai: 'AI交换机',
  security: '安全设备',
  gpu: 'GPU',
  other: '其他',
}

export type ResourceClass = 'compute' | 'network' | 'storage' | 'ai' | 'security' | 'other'

export const RESOURCE_CLASS_LABELS: Record<ResourceClass, string> = {
  compute: '计算资源',
  network: '网络资源',
  storage: '存储资源',
  ai: '智算资源',
  security: '安全资源',
  other: '其他资源',
}

export function isDeviceTypeCode(code: string | null | undefined): code is DeviceTypeCode {
  return !!code && (DEVICE_TYPE_CODES as readonly string[]).includes(code)
}

export function resourceClassOf(code: string | null | undefined): ResourceClass {
  const c = (code || '').toLowerCase()
  if (c === 'compute') return 'compute'
  if (c === 'storage') return 'storage'
  if (c === 'security') return 'security'
  if (c === 'other') return 'other'
  if (c === 'gpu' || c === 'switch_ai') return 'ai'
  if (c.startsWith('switch_') || c === 'router' || c === 'network') return 'network'
  return 'other'
}

export function deviceTypeCanonicalName(code: string | null | undefined): string | null {
  if (!isDeviceTypeCode(code)) return null
  return DEVICE_TYPE_FALLBACK_NAMES[code]
}

export interface DeviceTypeOption {
  id: string
  code: DeviceTypeCode
  name: string
  missing: boolean
}

/** 按设备管理同一组固定清单生成下拉选项（展示名始终用标准名） */
export function buildDeviceTypeOptions(types: DeviceType[]): DeviceTypeOption[] {
  const byCode = new Map(types.map((t) => [t.code, t]))
  return DEVICE_TYPE_CODES.map((code) => {
    const hit = byCode.get(code)
    return {
      id: hit?.id || '',
      code,
      name: DEVICE_TYPE_FALLBACK_NAMES[code],
      missing: !hit,
    }
  })
}

export function resolveDeviceTypeCode(
  types: DeviceType[],
  typeId: string | null | undefined,
): string | null {
  if (!typeId) return null
  const byId = types.find((t) => t.id === typeId)
  if (byId?.code) return byId.code
  if (isDeviceTypeCode(typeId)) return typeId
  return null
}

export function displayDeviceTypeName(
  types: DeviceType[],
  typeIdOrCode: string | null | undefined,
  fallbackName?: string | null,
): string {
  const code = resolveDeviceTypeCode(types, typeIdOrCode)
  const canonical = deviceTypeCanonicalName(code)
  if (canonical) return canonical
  const name = (fallbackName || '').trim()
  const byName = Object.values(DEVICE_TYPE_FALLBACK_NAMES).find((n) => n === name)
  return byName || name || '—'
}
