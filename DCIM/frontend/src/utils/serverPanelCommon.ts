import type { ServerFormFactor, ServerSlotKind, ServerSlotOrientation } from '@/api/network'

export const SERVER_HEADER_H = 26
export const SERVER_PANEL_PAD = 10
export const SERVER_SLOT_GAP = 6

/**
 * 机箱设计宽高比：以 2U 为基准 5.43:1（约等于 19″ 机架宽 / 2U 高）。
 * 同系列 1U / 4U 保持相同宽度，高度按 U 数比例缩放。
 */
export const SERVER_CHASSIS_ASPECT_2U = 5.43

/** 后面板 2U 基准高度（需容纳纵向扩展卡 210） */
export const SERVER_REAR_HEIGHT_2U = 320
/** 前面板 2U 基准高度 */
export const SERVER_FRONT_HEIGHT_2U = 148

export function serverChassisSize(
  formFactor: ServerFormFactor,
  panel: 'front' | 'rear' = 'rear',
): { frameWidth: number; frameHeight: number } {
  // 宽度一律按后面板 2U × 5.43 计算，保证前/后面板等宽
  const frameWidth = Math.round(SERVER_REAR_HEIGHT_2U * SERVER_CHASSIS_ASPECT_2U)
  const height2U = panel === 'rear' ? SERVER_REAR_HEIGHT_2U : SERVER_FRONT_HEIGHT_2U
  const frameHeight = Math.round((height2U * formFactor) / 2)
  return { frameWidth, frameHeight }
}

/** 标准板卡单元尺寸（默认宽 50、高 210；横向时对调） */
export const SERVER_CARD_V = { w: 50, h: 210 }
export const SERVER_CARD_H = { w: 210, h: 50 }

export const SERVER_CARD_MIN = { w: 28, h: 28 }
export const SERVER_CARD_MAX = { w: 320, h: 320 }

export function serverCardSize(orientation: ServerSlotOrientation = 'horizontal') {
  return orientation === 'vertical' ? { ...SERVER_CARD_V } : { ...SERVER_CARD_H }
}

export function clampServerCardSize(w: number, h: number) {
  return {
    w: Math.max(SERVER_CARD_MIN.w, Math.min(SERVER_CARD_MAX.w, w)),
    h: Math.max(SERVER_CARD_MIN.h, Math.min(SERVER_CARD_MAX.h, h)),
  }
}

export function defaultSlotOrientation(formFactor: ServerFormFactor): ServerSlotOrientation {
  return formFactor === 1 ? 'horizontal' : 'vertical'
}

export function serverExpansionMaxSlots(_formFactor?: ServerFormFactor): number {
  return 256
}

/** 扩展卡金属挡板色调 */
export const SERVER_CARD_PALETTE: Record<
  ServerSlotKind,
  { face: string; faceDark: string; bracket: string; accent: string; label: string }
> = {
  nic_1g: {
    face: '#3d4654',
    faceDark: '#2a3140',
    bracket: '#8b939e',
    accent: '#409eff',
    label: '#c6d4e8',
  },
  nic_10g: {
    face: '#354038',
    faceDark: '#243028',
    bracket: '#7a8a7e',
    accent: '#67c23a',
    label: '#c8e0c0',
  },
  hba: {
    face: '#4a4034',
    faceDark: '#342c22',
    bracket: '#9a8a72',
    accent: '#e6a23c',
    label: '#e8d8b8',
  },
  raid: {
    face: '#3a3e48',
    faceDark: '#282c34',
    bracket: '#8a9098',
    accent: '#909399',
    label: '#c0c4cc',
  },
  blank: {
    face: '#2e333c',
    faceDark: '#22262e',
    bracket: '#6e7580',
    accent: '#606266',
    label: '#909399',
  },
}

export interface ServerPsuVisual {
  id: string
  label: string
  x: number
  y: number
  w: number
  h: number
}

export interface ServerFixedIoVisual {
  x: number
  y: number
  w: number
  h: number
}

export interface ServerVentVisual {
  x: number
  y: number
  w: number
  h: number
}

export interface ServerDriveBayVisual {
  row: number
  col: number
  x: number
  y: number
  w: number
  h: number
}

export function serverDriveGrid(formFactor: ServerFormFactor): { rows: number; cols: number } {
  if (formFactor === 1) return { rows: 1, cols: 4 }
  if (formFactor === 2) return { rows: 3, cols: 4 }
  return { rows: 5, cols: 4 }
}

export function serverPsuLayout(formFactor: ServerFormFactor, _frameW: number, frameH: number): ServerPsuVisual[] {
  const bottom = frameH - 8
  if (formFactor === 1) {
    const pw = 52
    const ph = 22
    const y = bottom - ph
    return [
      { id: 'psu1', label: 'PSU1', x: 10, y, w: pw, h: ph },
      { id: 'psu2', label: 'PSU2', x: 10 + pw + 6, y, w: pw, h: ph },
    ]
  }
  const pw = 56
  const ph = formFactor === 2 ? 52 : 44
  const x = 10
  const count = formFactor === 2 ? 2 : 3
  const gap = 4
  const totalH = count * ph + (count - 1) * gap
  const y = bottom - totalH
  return Array.from({ length: count }, (_, i) => ({
    id: `psu${i + 1}`,
    label: `PSU${i + 1}`,
    x,
    y: y + i * (ph + gap),
    w: pw,
    h: ph,
  }))
}

export function snapServerCoord(value: number, grid = 2): number {
  return Math.round(value / grid) * grid
}
