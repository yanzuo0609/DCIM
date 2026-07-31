import type { ServerFormFactor, ServerSlotKind, ServerSlotOrientation } from '@/api/network'

export const SERVER_HEADER_H = 18
export const SERVER_PANEL_PAD = 8
/** 扩展卡列/行间距（图形显示） */
export const SERVER_SLOT_GAP = 14
/** 2U 扩展卡列间距、行间距（保证卡间可见缝隙） */
export const SERVER_SLOT_COL_GAP_2U = 20
export const SERVER_SLOT_ROW_GAP_2U = 16

/**
 * 2U 后面板以参考图 865×238（约 3.634:1）为基准。
 * 同系列 1U / 4U 等宽，高度按 U 数比例缩放。
 */
export const SERVER_CHASSIS_ASPECT_2U = 865 / 238
export const SERVER_REAR_HEIGHT_2U = 238
export const SERVER_FRONT_HEIGHT_2U = SERVER_REAR_HEIGHT_2U

export function serverChassisSize(
  formFactor: ServerFormFactor,
  _panel: 'front' | 'rear' = 'rear',
): { frameWidth: number; frameHeight: number } {
  const frameWidth = Math.round(SERVER_REAR_HEIGHT_2U * SERVER_CHASSIS_ASPECT_2U)
  const frameHeight = Math.round((SERVER_REAR_HEIGHT_2U * formFactor) / 2)
  return { frameWidth, frameHeight }
}

/** 横置 Slot 默认尺寸（由布局网格覆盖） */
export const SERVER_CARD_H = { w: 260, h: 48 }
export const SERVER_CARD_V = { w: 56, h: 140 }

export const SERVER_CARD_MIN = { w: 40, h: 28 }
export const SERVER_CARD_MAX = { w: 420, h: 200 }

export function serverCardSize(orientation: ServerSlotOrientation = 'horizontal') {
  return orientation === 'vertical' ? { ...SERVER_CARD_V } : { ...SERVER_CARD_H }
}

export function clampServerCardSize(w: number, h: number) {
  return {
    w: Math.max(SERVER_CARD_MIN.w, Math.min(SERVER_CARD_MAX.w, w)),
    h: Math.max(SERVER_CARD_MIN.h, Math.min(SERVER_CARD_MAX.h, h)),
  }
}

/** 背板参考图为横置 Slot，全规格默认横向 */
export function defaultSlotOrientation(_formFactor: ServerFormFactor): ServerSlotOrientation {
  return 'horizontal'
}

export function serverExpansionMaxSlots(_formFactor?: ServerFormFactor): number {
  return 256
}

/** 扩展卡配色：浅色机箱上的横置 Slot */
export const SERVER_CARD_PALETTE: Record<
  ServerSlotKind,
  { face: string; faceDark: string; bracket: string; accent: string; label: string }
> = {
  nic_1g: {
    face: '#f7fbff',
    faceDark: '#eef5fc',
    bracket: '#c5ccd6',
    accent: '#409eff',
    label: '#c45656',
  },
  nic_10g: {
    face: '#f5faf3',
    faceDark: '#ebf5e8',
    bracket: '#c5d0c4',
    accent: '#67c23a',
    label: '#c45656',
  },
  hba: {
    face: '#fdf8f0',
    faceDark: '#f7eedf',
    bracket: '#d4cbb8',
    accent: '#e6a23c',
    label: '#c45656',
  },
  raid: {
    face: '#fafafa',
    faceDark: '#f0f2f5',
    bracket: '#c8ced6',
    accent: '#909399',
    label: '#c45656',
  },
  blank: {
    face: '#ffffff',
    faceDark: '#f5f7fa',
    bracket: '#b8bfc9',
    accent: '#606266',
    label: '#c45656',
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

export interface ServerRearRegion {
  x: number
  y: number
  w: number
  h: number
}

/** 参考图底部固定区：OCP / VGA / Mgmt / USB */
export interface ServerRearIoRegions {
  ocp: ServerRearRegion
  vga: ServerRearRegion
  mgmt: ServerRearRegion
  usb: ServerRearRegion
}

/**
 * 各规格 Slot 列配置（自左向右；每列自下而上为 Slot 序号递增）。
 * 1U：左右各 1，共 2 个扩展卡
 * 2U：对齐参考图 3 + 3 + 2 = 8
 */
export function rearSlotColumnCounts(formFactor: ServerFormFactor): number[] {
  if (formFactor === 1) return [1, 1]
  if (formFactor === 2) return [3, 3, 2]
  return [5, 5, 3]
}

export function rearDefaultSlotCount(formFactor: ServerFormFactor): number {
  return rearSlotColumnCounts(formFactor).reduce((a, b) => a + b, 0)
}

export function serverDriveGrid(formFactor: ServerFormFactor): { rows: number; cols: number } {
  if (formFactor === 1) return { rows: 1, cols: 4 }
  if (formFactor === 2) return { rows: 3, cols: 4 }
  return { rows: 5, cols: 4 }
}

/**
 * 2U 参考布局几何；1U/4U 同比缩放高度并微调底部带比例。
 */
export function computeServerRearGeometry(formFactor: ServerFormFactor) {
  const { frameWidth, frameHeight } = serverChassisSize(formFactor, 'rear')
  const pad = SERVER_PANEL_PAD
  const header = SERVER_HEADER_H
  const gap = SERVER_SLOT_GAP

  // 底部固定带：略收一点，把高度让给扩展卡区，接口更好排布
  const bottomRatio = formFactor === 1 ? 0.36 : formFactor === 2 ? 0.33 : 0.3
  const bottomH = Math.round((frameHeight - header - pad) * bottomRatio)
  const bottomY = frameHeight - pad - bottomH
  const slotTop = header + 4
  const slotAreaH = Math.max(36, bottomY - gap - slotTop)

  const contentW = frameWidth - pad * 2
  const cols = rearSlotColumnCounts(formFactor)
  const colCount = cols.length
  const colGap =
    formFactor === 1 ? 12 : formFactor === 2 ? SERVER_SLOT_COL_GAP_2U : 16
  const colW = (contentW - colGap * (colCount - 1)) / colCount

  const maxSlotsInCol = Math.max(...cols)
  const slotGapY =
    formFactor === 1 ? 8 : formFactor === 2 ? 12 : 10
  const slotH = Math.max(
    26,
    (slotAreaH - slotGapY * (maxSlotsInCol - 1)) / maxSlotsInCol,
  )
  // 2U：卡宽略小于列宽，左右再留出缝隙，避免贴边挤在一起
  const slotInsetX = formFactor === 2 ? 4 : 0
  const slotW = Math.max(24, colW - slotInsetX * 2)

  const slotRects: Array<{ slotIndex: number; x: number; y: number; w: number; h: number; col: number; rowFromBottom: number }> = []
  let slotIndex = 1
  cols.forEach((count, colIdx) => {
    const x = pad + colIdx * (colW + colGap) + slotInsetX
    for (let row = 0; row < count; row += 1) {
      // 自下而上：Slot1 在列底
      const y = slotTop + slotAreaH - slotH - row * (slotH + slotGapY)
      slotRects.push({
        slotIndex,
        x: Math.round(x),
        y: Math.round(y),
        w: Math.round(slotW),
        h: Math.round(slotH),
        col: colIdx,
        rowFromBottom: row,
      })
      slotIndex += 1
    }
  })

  // 左列底部：OCP；中列：VGA/Mgmt/USB；右列：双 PSU
  const leftColX = pad
  const leftColW = colW
  const midColX = pad + colW + colGap
  const midColW = colCount >= 2 ? colW : contentW * 0.4
  const rightColX = pad + (colCount - 1) * (colW + colGap)
  const rightColW = colW

  const ocp: ServerRearRegion = {
    x: Math.round(leftColX),
    y: Math.round(bottomY),
    w: Math.round(leftColW),
    h: Math.round(bottomH),
  }

  const midInnerPad = 8
  const midY = bottomY + 8
  const midH = bottomH - 16
  const vgaW = Math.min(36, midColW * 0.22)
  const mgmtW = Math.min(28, midColW * 0.18)
  const usbW = Math.min(22, midColW * 0.14)
  let cursor = midColX + midInnerPad
  const vga: ServerRearRegion = {
    x: Math.round(cursor),
    y: Math.round(midY + midH * 0.15),
    w: Math.round(vgaW),
    h: Math.round(midH * 0.7),
  }
  cursor += vgaW + 10
  const mgmt: ServerRearRegion = {
    x: Math.round(cursor),
    y: Math.round(midY + midH * 0.25),
    w: Math.round(mgmtW),
    h: Math.round(midH * 0.5),
  }
  cursor += mgmtW + 10
  const usb: ServerRearRegion = {
    x: Math.round(cursor),
    y: Math.round(midY + midH * 0.15),
    w: Math.round(usbW),
    h: Math.round(midH * 0.7),
  }

  const fixedIo: ServerFixedIoVisual = {
    x: Math.round(midColX),
    y: Math.round(bottomY),
    w: Math.round(midColW),
    h: Math.round(bottomH),
  }

  // OCP 口区域 ≈ 板载千兆区
  const onboard1gZone = {
    x: ocp.x + 10,
    y: ocp.y + 16,
    w: Math.max(48, ocp.w - 20),
    h: Math.max(28, ocp.h - 28),
  }

  const psuGap = 6
  const psuCount = formFactor === 4 ? 3 : 2
  const psuW = (rightColW - psuGap * (psuCount - 1)) / psuCount
  const psus: ServerPsuVisual[] = Array.from({ length: psuCount }, (_, i) => ({
    id: `psu${i + 1}`,
    label: `PSU${i + 1}`,
    x: Math.round(rightColX + i * (psuW + psuGap)),
    y: Math.round(bottomY),
    w: Math.round(psuW),
    h: Math.round(bottomH),
  }))

  const expansionZone = {
    x: pad,
    y: slotTop,
    w: contentW,
    h: slotAreaH,
  }

  const vent: ServerVentVisual = {
    x: 0,
    y: 0,
    w: 0,
    h: 0,
  }

  return {
    frameWidth,
    frameHeight,
    slotRects,
    fixedIo,
    ioRegions: { ocp, vga, mgmt, usb } as ServerRearIoRegions,
    onboard1gZone,
    expansionZone,
    vent,
    psus,
    slotW: Math.round(slotW),
    slotH: Math.round(slotH),
    bottomY,
    bottomH,
  }
}

/** @deprecated 使用 computeServerRearGeometry().psus */
export function serverPsuLayout(formFactor: ServerFormFactor, _frameW: number, _frameH: number): ServerPsuVisual[] {
  return computeServerRearGeometry(formFactor).psus
}

export function snapServerCoord(value: number, grid = 2): number {
  return Math.round(value / grid) * grid
}
