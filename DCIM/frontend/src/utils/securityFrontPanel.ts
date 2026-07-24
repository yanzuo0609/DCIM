import type {
  FramePort,
  LayoutSlotDef,
  PortLayout,
  PortType,
  SecurityZoneLayout,
  SlotInterfaceGroup,
} from '@/api/network'
import { PORT_TYPE_SHORT } from '@/api/network'

export const SEC_EAR = 14
export const SEC_PAD = 10
export const SEC_STATUS_W = 72
export const SEC_ZONE_GAP = 16
export const SEC_HEADER_H = 24
export const SEC_MM_SCALE = 0.6
export const SEC_RESIZE_HANDLE = 10
export const SEC_ZONE_MIN_W = 72
export const SEC_ZONE_MIN_H = 40

/** 2U 基准高度；1U 严格为 2U 的一半。前后同宽，仅高度变化便于区分 */
export const SEC_FRAME_HEIGHT_2U = 240
export const SEC_FRAME_HEIGHT_BY_U: Record<1 | 2, number> = {
  1: Math.round(SEC_FRAME_HEIGHT_2U / 2), // 120
  2: SEC_FRAME_HEIGHT_2U,
}

/** 1U/2U 共用机箱宽度（机架设备同宽不同高） */
export const SEC_FRAME_WIDTH = 640
export const SEC_FRAME_MIN_WIDTH_BY_U: Record<1 | 2, number> = {
  1: SEC_FRAME_WIDTH,
  2: SEC_FRAME_WIDTH,
}

export function normalizeSecurityHeightU(value: number | string | null | undefined): 1 | 2 {
  const n = typeof value === 'string' ? parseInt(value, 10) : Number(value)
  return Number.isFinite(n) && n >= 2 ? 2 : 1
}

export interface SecurityZoneView {
  id: string
  slotIndex: number
  label: string
  portType: PortType
  layoutMode: SecurityZoneLayout
  x: number
  y: number
  w: number
  h: number
}

export interface SecurityPanelView {
  title: string
  frameWidth: number
  frameHeight: number
  statusBlock: { x: number; y: number; w: number; h: number }
  zones: SecurityZoneView[]
}

export interface SecurityZoneInput {
  label: string
  port_type: PortType
  count: number
  zone_layout?: SecurityZoneLayout
}

function newGroup(portType: PortType, count: number): SlotInterfaceGroup {
  return {
    id: crypto.randomUUID().slice(0, 8),
    port_type: portType,
    count: Math.max(1, Math.min(128, count)),
    role: 'main',
    grid_cols: null,
    layout_x: null,
    layout_y: null,
  }
}

function portBox(type: PortType): { w: number; h: number } {
  if (type === '40_100g') return { w: 22, h: 15 }
  if (type === '10g') return { w: 14, h: 11 }
  if (type === 'bmc') return { w: 13, h: 11 }
  return { w: 12, h: 10 }
}

/** 满 8 口强制双行；单行模式在 <8 时保持单行；自动模式 >4 也换行 */
function resolveZoneLayout(mode: SecurityZoneLayout | null | undefined, count: number): 'single_row' | 'two_row' {
  if (count >= 8) return 'two_row'
  if (mode === 'two_row') return 'two_row'
  if (mode === 'single_row') return 'single_row'
  return count > 4 ? 'two_row' : 'single_row'
}

function snapSec(n: number): number {
  return Math.round(n)
}

export function defaultSecurityZones(): SecurityZoneInput[] {
  return [
    { label: 'WAN', port_type: '1g', count: 2, zone_layout: 'single_row' },
    { label: 'LAN', port_type: '1g', count: 8, zone_layout: 'two_row' },
    { label: 'HA', port_type: '10g', count: 2, zone_layout: 'single_row' },
    { label: 'MGMT', port_type: '1g', count: 1, zone_layout: 'single_row' },
  ]
}

export function newSecurityZoneSlot(
  label: string,
  portType: PortType,
  count: number,
  zoneLayout: SecurityZoneLayout = 'auto',
): LayoutSlotDef {
  return {
    zone_label: label,
    zone_layout: zoneLayout,
    groups: [newGroup(portType, count)],
    layout_x: null,
    layout_y: null,
    layout_w: null,
    layout_h: null,
  }
}

export function buildSecuritySlotsDef(zones: SecurityZoneInput[]): LayoutSlotDef[] {
  return zones.map((z) =>
    newSecurityZoneSlot(z.label, z.port_type, z.count, z.zone_layout ?? 'auto'),
  )
}

export function readSecurityZones(layout: PortLayout): SecurityZoneInput[] {
  const slots = layout.slots_def || []
  if (!slots.length) return defaultSecurityZones()
  return slots.map((slot, idx) => {
    const g = slot.groups?.[0]
    return {
      label: slot.zone_label?.trim() || `接口区 ${idx + 1}`,
      port_type: (g?.port_type || '1g') as PortType,
      count: Math.max(1, g?.count || 1),
      zone_layout: (slot.zone_layout || 'auto') as SecurityZoneLayout,
    }
  })
}

/** 一维均匀分布：边距 = 间距（space-evenly），端口始终落在 [origin, origin+length] 内 */
function evenSpread(
  origin: number,
  length: number,
  count: number,
  preferredSize: number,
  minGap = 5,
): { positions: number[]; size: number } {
  if (count <= 0) return { positions: [], size: preferredSize }
  const usable = Math.max(8, length)
  if (count === 1) {
    const size = Math.max(6, Math.min(preferredSize, Math.max(6, usable - minGap * 2)))
    return {
      positions: [origin + Math.max(0, (usable - size) / 2)],
      size,
    }
  }
  let size = preferredSize
  // (count+1) 段空隙等分：左边距 | 口 | 缝 | 口 | … | 右边距
  let gap = (usable - size * count) / (count + 1)
  if (gap < minGap) {
    size = Math.max(6, (usable - minGap * (count + 1)) / count)
    gap = (usable - size * count) / (count + 1)
  }
  if (gap < 0) {
    size = Math.max(6, usable / count)
    gap = 0
  }
  const positions: number[] = []
  for (let i = 0; i < count; i += 1) {
    const x = origin + gap + i * (size + gap)
    // 右缘不越界
    positions.push(Math.min(x, origin + usable - size))
  }
  return { positions, size: Math.max(6, size) }
}

/**
 * 在接口区内均匀排布端口：
 * - 单行：水平 space-evenly，垂直居中
 * - 双行：两行垂直均分 + 每行水平均匀
 * 保证所有端口矩形完全落在区域内。
 */
function placeZonePorts(
  ports: FramePort[],
  areaX: number,
  areaY: number,
  areaW: number,
  areaH: number,
  mode: 'single_row' | 'two_row',
  labelPrefix: string,
): void {
  if (!ports.length) return
  const type = ports[0].port_type || '1g'
  const preferred = portBox(type)
  const count = ports.length
  // 区内边距，避免贴边与标签区拥挤
  const insetX = Math.min(8, Math.max(3, Math.round(areaW * 0.06)))
  const insetY = Math.min(6, Math.max(2, Math.round(areaH * 0.08)))
  const ax = areaX + insetX
  const ay = areaY + insetY
  const aw = Math.max(10, areaW - insetX * 2)
  const ah = Math.max(10, areaH - insetY * 2)
  const areaRight = ax + aw
  const areaBottom = ay + ah

  const clampPort = (port: FramePort) => {
    port.w = Math.max(6, Math.min(port.w, aw))
    port.h = Math.max(6, Math.min(port.h, ah))
    port.x = Math.max(ax, Math.min(port.x, areaRight - port.w))
    port.y = Math.max(ay, Math.min(port.y, areaBottom - port.h))
  }

  if (mode === 'single_row' || count <= 1) {
    const spreadX = evenSpread(ax, aw, count, preferred.w, count <= 2 ? 10 : 6)
    const portH = Math.min(preferred.h, Math.max(6, ah - 2))
    const y = ay + Math.max(0, (ah - portH) / 2)
    ports.forEach((port, i) => {
      port.x = spreadX.positions[i] ?? ax
      port.y = y
      port.w = spreadX.size
      port.h = portH
      port.label = `${labelPrefix}${i + 1}`
      clampPort(port)
    })
    return
  }

  const rows = 2
  const spreadY = evenSpread(ay, ah, rows, preferred.h, 6)
  const portH = spreadY.size

  // 尽量上下两行数量均衡（如 8 口 → 4+4，7 口 → 4+3）
  const topCount = Math.ceil(count / 2)
  const rowCounts = [topCount, count - topCount]

  let start = 0
  for (let row = 0; row < rows; row += 1) {
    const rowPorts = ports.slice(start, start + rowCounts[row])
    start += rowCounts[row]
    if (!rowPorts.length) continue
    const spreadX = evenSpread(ax, aw, rowPorts.length, preferred.w, rowPorts.length >= 4 ? 6 : 8)
    rowPorts.forEach((port, col) => {
      const i = (row === 0 ? 0 : rowCounts[0]) + col
      port.x = spreadX.positions[col] ?? ax
      port.y = spreadY.positions[row] ?? ay
      port.w = spreadX.size
      port.h = portH
      port.label = `${labelPrefix}${i + 1}`
      clampPort(port)
    })
  }
}

function zoneShortPrefix(label: string, portType: PortType): string {
  const cleaned = label.replace(/\s+/g, '').slice(0, 4)
  if (cleaned) return cleaned
  return PORT_TYPE_SHORT[portType] || 'P'
}

/** 按端口数量估算接口区最小宽度，保证 WAN 等少口区也有呼吸感 */
export function estimateZoneWidth(count: number, portType: PortType, mode: 'single_row' | 'two_row'): number {
  const { w } = portBox(portType)
  const cols = mode === 'two_row' ? Math.max(1, Math.ceil(count / 2)) : Math.max(1, count)
  const minGap = cols <= 2 ? 12 : 8
  const sidePad = 24
  // 少口区（如 WAN×2）额外加宽，便于均衡分布
  const comfort = cols <= 2 ? 28 : cols <= 4 ? 14 : 0
  return Math.max(80, cols * w + (cols + 1) * minGap + sidePad + comfort)
}

function contentMetrics(heightU: 1 | 2) {
  const frameHeight = SEC_FRAME_HEIGHT_BY_U[heightU]
  const contentY = SEC_HEADER_H + 6
  const contentH = Math.max(36, frameHeight - SEC_HEADER_H - 12)
  const zoneLabelH = heightU === 1 ? 13 : 16
  const portAreaPad = heightU === 1 ? 4 : 8
  return { frameHeight, contentY, contentH, zoneLabelH, portAreaPad }
}

function clampZoneRect(
  frameWidth: number,
  frameHeight: number,
  x: number,
  y: number,
  w: number,
  h: number,
): { x: number; y: number; w: number; h: number } {
  const maxW = Math.max(SEC_ZONE_MIN_W, frameWidth - SEC_PAD * 2)
  const minY = SEC_HEADER_H + 4
  const maxH = Math.max(SEC_ZONE_MIN_H, frameHeight - minY - SEC_PAD)
  const cw = Math.max(SEC_ZONE_MIN_W, Math.min(snapSec(w), maxW))
  const ch = Math.max(SEC_ZONE_MIN_H, Math.min(snapSec(h), maxH))
  const cx = Math.max(SEC_PAD, Math.min(snapSec(x), frameWidth - SEC_PAD - cw))
  const cy = Math.max(minY, Math.min(snapSec(y), frameHeight - SEC_PAD - ch))
  return { x: cx, y: cy, w: cw, h: ch }
}

/** 清除自定义位置/尺寸，恢复自左向右自动排列 */
export function resetSecurityZonePositions(layout: PortLayout) {
  ;(layout.slots_def || []).forEach((slot) => {
    slot.layout_x = null
    slot.layout_y = null
    slot.layout_w = null
    slot.layout_h = null
  })
  layout.frame_width = SEC_FRAME_WIDTH
  layoutSecurityFrontPanel(layout)
}

/**
 * 将接口区在内容区两端对齐分布：
 * - 各区保持估算宽度（不压扁 WAN 等少口区）
 * - 余量均分到区缝，首贴左、末贴右
 * - 总宽不够时返回所需右缘，由调用方加宽机箱
 */
function justifyZonesInFrame(
  items: Array<{ w: number; h: number }>,
  contentLeft: number,
  contentRight: number,
  contentY: number,
  contentH: number,
): { rects: Array<{ x: number; y: number; w: number; h: number }>; neededRight: number } {
  const n = items.length
  const areaW = Math.max(SEC_ZONE_MIN_W, contentRight - contentLeft)
  if (n <= 0) return { rects: [], neededRight: contentLeft }
  if (n === 1) {
    return {
      rects: [{
        x: contentLeft,
        y: contentY,
        w: areaW,
        h: Math.min(items[0].h, contentH),
      }],
      neededRight: contentLeft + areaW,
    }
  }

  const minGap = SEC_ZONE_GAP
  const widths = items.map((it) => Math.max(SEC_ZONE_MIN_W, Math.round(it.w)))
  const heights = items.map((it) => Math.min(it.h, contentH))
  const sumW = widths.reduce((s, w) => s + w, 0)
  const need = sumW + minGap * (n - 1)

  if (need > areaW) {
    // 不够：保持自然宽度左起排列，机箱随后加宽
    const rects: Array<{ x: number; y: number; w: number; h: number }> = []
    let x = contentLeft
    items.forEach((_, i) => {
      rects.push({ x: snapSec(x), y: contentY, w: widths[i], h: heights[i] })
      x += widths[i] + minGap
    })
    return { rects, neededRight: x - minGap }
  }

  // 余量均分到区间缝隙，两端贴齐（space-between）
  const gap = (areaW - sumW) / (n - 1)
  const rects: Array<{ x: number; y: number; w: number; h: number }> = []
  let x = contentLeft
  items.forEach((_, i) => {
    rects.push({ x: snapSec(x), y: contentY, w: widths[i], h: heights[i] })
    x += widths[i] + gap
  })
  // 修正末区右缘精确贴齐
  const last = rects[n - 1]
  last.x = snapSec(contentRight - last.w)
  return { rects, neededRight: contentRight }
}

/** 安全设备前面板：状态区 + 可自由摆放/缩放的接口区 */
export function layoutSecurityFrontPanel(layout: PortLayout): SecurityPanelView {
  layout.security_panel = true
  const heightU = normalizeSecurityHeightU(layout.height_u)
  layout.height_u = heightU

  if (!layout.slots_def?.length) {
    layout.slots_def = buildSecuritySlotsDef(defaultSecurityZones())
    layout.slot_count = layout.slots_def.length
  }

  const { frameHeight, contentY, contentH, zoneLabelH, portAreaPad } = contentMetrics(heightU)
  const statusBlock = {
    x: SEC_PAD,
    y: contentY,
    w: SEC_STATUS_W,
    h: contentH,
  }

  const contentLeft = SEC_PAD + SEC_STATUS_W + SEC_ZONE_GAP
  type Draft = {
    slot: LayoutSlotDef
    idx: number
    label: string
    portType: PortType
    layoutMode: 'single_row' | 'two_row'
    groupId: string
    x: number
    y: number
    w: number
    h: number
    hasPos: boolean
  }

  const draft: Draft[] = []
  ;(layout.slots_def || []).forEach((slot, idx) => {
    const group = slot.groups?.[0]
    if (!group) return
    const label = slot.zone_label?.trim() || `接口区 ${idx + 1}`
    const portType = (group.port_type || '1g') as PortType
    const layoutMode = resolveZoneLayout(slot.zone_layout, group.count)
    const portCount = Math.max(1, group.count)
    const estimatedW = estimateZoneWidth(portCount, portType, layoutMode)
    const hasPos = slot.layout_x != null && slot.layout_y != null
    const w = slot.layout_w != null ? slot.layout_w : estimatedW
    const h = slot.layout_h != null ? slot.layout_h : contentH
    draft.push({
      slot,
      idx,
      label,
      portType,
      layoutMode,
      groupId: group.id,
      x: hasPos ? (slot.layout_x as number) : 0,
      y: hasPos ? (slot.layout_y as number) : contentY,
      w,
      h,
      hasPos,
    })
  })

  const allUnset = draft.length > 0 && draft.every((z) => !z.hasPos)
  // 全部未定位（新建 / 自动排列）：接口区保持估算宽，两端对齐；不够则加宽机箱
  if (allUnset) {
    layout.frame_width = SEC_FRAME_WIDTH
    const contentRight = SEC_FRAME_WIDTH - SEC_PAD
    const { rects, neededRight } = justifyZonesInFrame(
      draft.map((z) => ({ w: z.w, h: z.h })),
      contentLeft,
      contentRight,
      contentY,
      contentH,
    )
    if (neededRight > contentRight) {
      layout.frame_width = Math.ceil(neededRight + SEC_PAD)
      const again = justifyZonesInFrame(
        draft.map((z) => ({ w: z.w, h: z.h })),
        contentLeft,
        layout.frame_width - SEC_PAD,
        contentY,
        contentH,
      )
      draft.forEach((z, i) => {
        const rect = again.rects[i]
        if (!rect) return
        z.x = rect.x
        z.y = rect.y
        z.w = rect.w
        z.h = rect.h
      })
    } else {
      draft.forEach((z, i) => {
        const rect = rects[i]
        if (!rect) return
        z.x = rect.x
        z.y = rect.y
        z.w = rect.w
        z.h = rect.h
      })
    }
  } else {
    // 混合/已拖动：未定位区接在已放置区右侧；机箱随最右缘扩展
    let cursorX = contentLeft
    let placedRight = contentLeft
    draft.forEach((z) => {
      if (!z.hasPos) return
      placedRight = Math.max(placedRight, z.x + z.w + SEC_ZONE_GAP)
    })
    draft.forEach((z) => {
      if (z.hasPos) return
      z.x = Math.max(cursorX, placedRight)
      z.y = contentY
      cursorX = z.x + z.w + SEC_ZONE_GAP
      placedRight = cursorX
    })
  }

  let frameWidth = layout.frame_width || SEC_FRAME_WIDTH
  if (!allUnset) {
    frameWidth = SEC_FRAME_WIDTH
    draft.forEach((z) => {
      frameWidth = Math.max(frameWidth, Math.ceil(z.x + z.w + SEC_PAD))
    })
  } else {
    frameWidth = layout.frame_width || SEC_FRAME_WIDTH
  }

  const zones: SecurityZoneView[] = []
  draft.forEach((z) => {
    const rect = clampZoneRect(frameWidth, frameHeight, z.x, z.y, z.w, z.h)
    z.slot.layout_x = rect.x
    z.slot.layout_y = rect.y
    z.slot.layout_w = rect.w
    z.slot.layout_h = rect.h

    const slotPorts = (layout.ports || []).filter((p) => p.slot_index === z.idx + 1)
    slotPorts.forEach((p) => {
      p.layout_locked = false
    })

    const portAreaX = rect.x + portAreaPad
    const portAreaY = rect.y + zoneLabelH
    const portAreaW = Math.max(24, rect.w - portAreaPad * 2)
    const portAreaH = Math.max(18, rect.h - zoneLabelH - portAreaPad)

    placeZonePorts(
      slotPorts,
      portAreaX,
      portAreaY,
      portAreaW,
      portAreaH,
      z.layoutMode,
      zoneShortPrefix(z.label, z.portType),
    )

    zones.push({
      id: z.groupId,
      slotIndex: z.idx + 1,
      // 短标签避免挤占 WAN 等窄区；详情见接口上的 WAN1/WAN2
      label: `${z.label} ×${z.slot.groups?.[0]?.count ?? slotPorts.length}`,
      portType: z.portType,
      layoutMode: (z.slot.zone_layout || 'auto') as SecurityZoneLayout,
      x: rect.x,
      y: rect.y,
      w: rect.w,
      h: rect.h,
    })
  })

  layout.frame_width = frameWidth
  layout.frame_height = frameHeight
  layout.rack_width_mm = Math.round(frameWidth / SEC_MM_SCALE)
  layout.height_u = heightU
  layout.security_panel = true

  return {
    title: `${heightU}U 前面板`,
    frameWidth,
    frameHeight,
    statusBlock,
    zones,
  }
}

export function moveSecurityZoneInPanel(
  layout: PortLayout,
  slotIndex: number,
  absX: number,
  absY: number,
) {
  const slot = layout.slots_def?.[slotIndex]
  if (!slot) return
  const w = slot.layout_w ?? SEC_ZONE_MIN_W
  const h = slot.layout_h ?? SEC_ZONE_MIN_H
  const fw = layout.frame_width || SEC_FRAME_WIDTH
  const fh = layout.frame_height || SEC_FRAME_HEIGHT_BY_U[normalizeSecurityHeightU(layout.height_u)]
  // 拖到右缘时允许扩展机箱
  const nextRight = absX + w + SEC_PAD
  if (nextRight > fw) {
    layout.frame_width = Math.ceil(nextRight)
  }
  const rect = clampZoneRect(layout.frame_width || fw, fh, absX, absY, w, h)
  slot.layout_x = rect.x
  slot.layout_y = rect.y
  slot.layout_w = rect.w
  slot.layout_h = rect.h
  layoutSecurityFrontPanel(layout)
}

export function resizeSecurityZoneInPanel(
  layout: PortLayout,
  slotIndex: number,
  nextW: number,
  nextH: number,
) {
  const slot = layout.slots_def?.[slotIndex]
  if (!slot) return
  const x = slot.layout_x ?? SEC_PAD + SEC_STATUS_W + 12
  const y = slot.layout_y ?? SEC_HEADER_H + 6
  const fw = layout.frame_width || SEC_FRAME_WIDTH
  const fh = layout.frame_height || SEC_FRAME_HEIGHT_BY_U[normalizeSecurityHeightU(layout.height_u)]
  const wantW = Math.max(SEC_ZONE_MIN_W, snapSec(nextW))
  const wantH = Math.max(SEC_ZONE_MIN_H, snapSec(nextH))
  if (x + wantW + SEC_PAD > fw) {
    layout.frame_width = Math.ceil(x + wantW + SEC_PAD)
  }
  const rect = clampZoneRect(layout.frame_width || fw, fh, x, y, wantW, wantH)
  slot.layout_x = rect.x
  slot.layout_y = rect.y
  slot.layout_w = rect.w
  slot.layout_h = rect.h
  ;(layout.ports || [])
    .filter((p) => p.slot_index === slotIndex + 1)
    .forEach((p) => {
      p.layout_locked = false
    })
  layoutSecurityFrontPanel(layout)
}

export function patchSecurityZoneSlot(
  slot: LayoutSlotDef,
  slotIndex: number,
  patch: Partial<{
    label: string
    port_type: PortType
    count: number
    zone_layout: SecurityZoneLayout
    layout_w: number
    layout_h: number
  }>,
) {
  if (patch.label != null) slot.zone_label = patch.label.trim() || `接口区 ${slotIndex + 1}`
  if (patch.zone_layout != null) slot.zone_layout = patch.zone_layout
  if (patch.layout_w != null) slot.layout_w = Math.max(SEC_ZONE_MIN_W, snapSec(patch.layout_w))
  if (patch.layout_h != null) slot.layout_h = Math.max(SEC_ZONE_MIN_H, snapSec(patch.layout_h))
  if (!slot.groups?.length) {
    slot.groups = [newGroup(patch.port_type || '1g', patch.count || 1)]
    return
  }
  const g = slot.groups[0]
  if (patch.port_type != null) g.port_type = patch.port_type
  if (patch.count != null) g.count = Math.max(1, Math.min(128, patch.count))
  // 满 8 口自动改为双行，保证 WAN 等区换行显示
  const count = g.count
  if (count >= 8 && (slot.zone_layout === 'single_row' || slot.zone_layout == null || slot.zone_layout === 'auto')) {
    slot.zone_layout = 'two_row'
  }
  slot.groups = [g]
}

