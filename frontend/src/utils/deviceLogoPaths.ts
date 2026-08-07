/**
 * 设备简图 / Logo 图库路径
 * 静态资源目录：frontend/public/logos/
 * 浏览器访问前缀：/logos/
 */

export const LOGO_BASE = '/logos'

export type DeviceLogoKey =
  | 'switch-gigabit'
  | 'switch-ten-gigabit'
  | 'switch-aggregation'
  | 'switch-core'
  | 'server-1u'
  | 'server-2u'
  | 'server-4u'
  | 'security-1u'
  | 'security-2u'
  | 'router'
  | 'load-balancer'
  | 'optical-gate'
  | 'software'
  | 'placeholder'

const DEVICE_FILE: Record<DeviceLogoKey, string> = {
  'switch-gigabit': 'devices/switch-gigabit.svg',
  'switch-ten-gigabit': 'devices/switch-ten-gigabit.svg',
  'switch-aggregation': 'devices/switch-aggregation.svg',
  'switch-core': 'devices/switch-core.svg',
  'server-1u': 'devices/server-1u.svg',
  'server-2u': 'devices/server-2u.svg',
  'server-4u': 'devices/server-4u.svg',
  'security-1u': 'devices/security-1u.svg',
  'security-2u': 'devices/security-2u.svg',
  router: 'devices/router.svg',
  'load-balancer': 'devices/load-balancer.svg',
  'optical-gate': 'devices/optical-gate.svg',
  software: 'devices/software.svg',
  placeholder: 'common/placeholder.svg',
}

/** 设备简图 URL（public/logos） */
export function deviceLogoUrl(key: DeviceLogoKey): string {
  return `${LOGO_BASE}/${DEVICE_FILE[key] || DEVICE_FILE.placeholder}`
}

/** 厂商 Logo URL */
export function brandLogoUrl(fileName: string): string {
  const name = String(fileName || '').replace(/^\/+/, '')
  return `${LOGO_BASE}/brands/${name}`
}

/** 通用图 URL */
export function commonLogoUrl(fileName: string): string {
  const name = String(fileName || '').replace(/^\/+/, '')
  return `${LOGO_BASE}/common/${name}`
}
