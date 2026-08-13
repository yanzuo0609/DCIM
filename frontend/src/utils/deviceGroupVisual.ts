import type { NetworkNodeKind } from '@/api/network'
import type { FabricRole } from '@/utils/wiringTypes'

/** 设备组视觉类型：交换机组 / 服务器组 / 安全应用组 */
export type DeviceGroupKind = 'switch' | 'server' | 'security'

export const DEVICE_GROUP_KIND_LABELS: Record<DeviceGroupKind, string> = {
  switch: '交换机组',
  server: '服务器组',
  security: '安全应用组',
}

export function groupKindFromRole(role: FabricRole | null | undefined): DeviceGroupKind {
  if (role === 'SERVER') return 'server'
  if (role === 'FIREWALL') return 'security'
  return 'switch'
}

export function groupKindLabel(role: FabricRole | null | undefined): string {
  return DEVICE_GROUP_KIND_LABELS[groupKindFromRole(role)]
}

export function nodeKindForGroupRole(role: FabricRole | null | undefined): NetworkNodeKind {
  const kind = groupKindFromRole(role)
  if (kind === 'server') return 'server'
  if (kind === 'security') return 'security'
  return 'switch'
}

/** 网格排布：在原点附近展开 count 台设备 */
export function layoutGroupGrid(
  count: number,
  originX: number,
  originY: number,
  opts?: { cellW?: number; cellH?: number; cols?: number },
): Array<{ x: number; y: number }> {
  const n = Math.max(0, Math.floor(count))
  if (!n) return []
  const cellW = opts?.cellW ?? 110
  const cellH = opts?.cellH ?? 118
  const cols = Math.max(1, opts?.cols ?? Math.min(12, Math.ceil(Math.sqrt(n))))
  const out: Array<{ x: number; y: number }> = []
  for (let i = 0; i < n; i++) {
    const col = i % cols
    const row = Math.floor(i / cols)
    out.push({
      x: Math.max(0, originX + col * cellW),
      y: Math.max(0, originY + row * cellH),
    })
  }
  return out
}
