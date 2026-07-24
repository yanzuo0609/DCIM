import type {
  FramePort,
  LayoutSlotDef,
  PortLayout,
  PortType,
  ServerFormFactor,
  ServerSlotKind,
  ServerSlotOrientation,
} from '@/api/network'
import {
  SERVER_FORM_FACTOR_LABELS,
  SERVER_SLOT_KIND_LABELS,
  serverSlotDefaultPortType,
} from '@/api/network'
import {
  SERVER_CARD_H,
  SERVER_CARD_V,
  SERVER_HEADER_H,
  SERVER_PANEL_PAD,
  SERVER_SLOT_GAP,
  clampServerCardSize,
  defaultSlotOrientation,
  serverCardSize,
  serverChassisSize,
  serverPsuLayout,
  snapServerCoord,
  type ServerFixedIoVisual,
  type ServerVentVisual,
} from '@/utils/serverPanelCommon'

export const SERVER_LABEL_H = 12
export const SERVER_RESIZE_HANDLE = 10

export interface ServerSlotVisual {
  slotIndex: number
  kind: ServerSlotKind
  orientation: ServerSlotOrientation
  label: string
  shortLabel: string
  x: number
  y: number
  w: number
  h: number
  draggable: boolean
  resizable: boolean
}

export interface ServerPanelView {
  formFactor: ServerFormFactor
  title: string
  frameWidth: number
  frameHeight: number
  slots: ServerSlotVisual[]
  psus: ReturnType<typeof serverPsuLayout>
  fixedIo: ServerFixedIoVisual
  vent: ServerVentVisual
  expansionZone: { x: number; y: number; w: number; h: number }
  onboard1gZone: { x: number; y: number; w: number; h: number }
  grid: { rows: number; cols: number }
}

export function normalizeServerFormFactor(value: unknown): ServerFormFactor {
  if (value === 2 || value === 4 || value === '2' || value === '4') return Number(value) as ServerFormFactor
  return 1
}

function makeGroup(portType: PortType, count: number) {
  return {
    id: crypto.randomUUID().slice(0, 8),
    port_type: portType,
    count: Math.max(1, count),
    layout_x: null as number | null,
    layout_y: null as number | null,
  }
}

export function newServerSlotDef(
  kind: ServerSlotKind,
  portCount = 2,
  orientation?: ServerSlotOrientation,
): LayoutSlotDef {
  const ori = orientation ?? 'horizontal'
  const size = serverCardSize(ori)
  if (kind === 'raid' || kind === 'blank') {
    return {
      server_slot_kind: kind,
      orientation: ori,
      groups: [],
      layout_x: null,
      layout_y: null,
      layout_w: size.w,
      layout_h: size.h,
    }
  }
  const portType = serverSlotDefaultPortType(kind)
  const count = normalizeServerSlotPortCount(portCount)
  return {
    server_slot_kind: kind,
    orientation: ori,
    groups: [makeGroup(portType, count)],
    layout_x: null,
    layout_y: null,
    layout_w: size.w,
    layout_h: size.h,
  }
}

export function defaultServerSlotsDef(formFactor: ServerFormFactor = 1): LayoutSlotDef[] {
  if (formFactor === 1) {
    return [
      newServerSlotDef('nic_10g', 2, 'horizontal'),
      newServerSlotDef('nic_1g', 4, 'horizontal'),
    ]
  }
  if (formFactor === 2) {
    return [
      newServerSlotDef('nic_10g', 2, 'vertical'),
      newServerSlotDef('nic_10g', 2, 'vertical'),
      newServerSlotDef('nic_1g', 4, 'vertical'),
      newServerSlotDef('blank', 0, 'vertical'),
    ]
  }
  return [
    newServerSlotDef('nic_10g', 4, 'vertical'),
    newServerSlotDef('nic_10g', 4, 'vertical'),
    newServerSlotDef('nic_1g', 4, 'vertical'),
    newServerSlotDef('hba', 2, 'vertical'),
    newServerSlotDef('raid', 0, 'vertical'),
    newServerSlotDef('blank', 0, 'vertical'),
  ]
}

function inferServerSlotKind(slot: LayoutSlotDef): ServerSlotKind {
  if (slot.server_slot_kind) return slot.server_slot_kind
  const g = slot.groups?.[0]
  if (!g || g.count === 0) return 'blank'
  if (g.port_type === '1g') return 'nic_1g'
  if (g.port_type === '10g') return 'nic_10g'
  if (g.port_type === 'bmc') return 'nic_1g'
  return 'hba'
}

function shortKindLabel(kind: ServerSlotKind): string {
  if (kind === 'nic_1g') return '1G'
  if (kind === 'nic_10g') return '10G'
  if (kind === 'hba') return 'HBA'
  if (kind === 'raid') return 'RAID'
  return 'BLANK'
}

function panelMetrics(formFactor: ServerFormFactor, slotCount = 4) {
  // 宽高比以 2U = 5.43:1 为基准，同系列等宽、按 U 缩放高度
  const { frameWidth, frameHeight } = serverChassisSize(formFactor, 'rear')
  const psuW = formFactor === 1 ? 120 : 72
  const fixedIoW = 96
  const fixedIoH = formFactor === 1 ? 44 : 72
  const bottomPad = 8
  const bottom = frameHeight - bottomPad
  const fixedIo: ServerFixedIoVisual = {
    x: psuW + 12,
    y: bottom - fixedIoH,
    w: fixedIoW,
    h: fixedIoH,
  }
  const onboard1gZone = {
    x: fixedIo.x + fixedIo.w + 8,
    y: fixedIo.y,
    w: formFactor === 1 ? 88 : 100,
    h: fixedIoH,
  }

  // 1U：底部横向条带
  // 2U/4U：右侧区域，纵向卡横向并排；卡间距 + 最右卡距右边缘加大留白
  const cardH = SERVER_CARD_H.h
  const rightEdgeGap = formFactor === 1 ? 12 : 28
  const cardGap = formFactor === 1 ? SERVER_SLOT_GAP : 12
  const expansionZone =
    formFactor === 1
      ? (() => {
          const zoneH = Math.max(cardH + 10, 60)
          const zoneY = bottom - zoneH - 2
          const zoneX = Math.min(
            onboard1gZone.x + onboard1gZone.w + 10,
            frameWidth - SERVER_CARD_H.w - SERVER_PANEL_PAD,
          )
          return {
            x: zoneX,
            y: Math.max(SERVER_HEADER_H + 4, zoneY),
            w: Math.max(SERVER_CARD_H.w + 8, frameWidth - zoneX - SERVER_PANEL_PAD),
            h: zoneH,
          }
        })()
      : (() => {
          const n = Math.max(1, slotCount)
          const cardW = SERVER_CARD_V.w
          const cardVh = SERVER_CARD_V.h
          const zoneW = n * cardW + (n - 1) * cardGap + 8
          const zoneX = Math.max(
            psuW + 100,
            frameWidth - rightEdgeGap - zoneW,
          )
          const zoneY = SERVER_HEADER_H + 10
          const zoneH = Math.max(cardVh + 12, bottom - SERVER_HEADER_H - fixedIoH - 20)
          return {
            x: zoneX,
            y: zoneY,
            w: frameWidth - rightEdgeGap - zoneX,
            h: zoneH,
          }
        })()
  const vent: ServerVentVisual =
    formFactor === 1
      ? {
          x: psuW + 12,
          y: SERVER_HEADER_H + 4,
          w: Math.max(40, expansionZone.x - psuW - 20),
          h: Math.max(16, expansionZone.y - SERVER_HEADER_H - 6),
        }
      : formFactor === 2
        ? {
            x: psuW + 12,
            y: SERVER_HEADER_H + 8,
            w: Math.max(80, expansionZone.x - psuW - 24),
            h: Math.min(100, expansionZone.h * 0.45),
          }
        : {
            x: psuW + 12,
            y: SERVER_HEADER_H + 16,
            w: Math.max(80, expansionZone.x - psuW - 24),
            h: Math.min(160, expansionZone.h * 0.4),
          }
  return {
    frameWidth,
    frameHeight,
    fixedIo,
    onboard1gZone,
    expansionZone,
    vent,
    rightEdgeGap,
    cardGap,
  }
}

/** 按放置方向取尺寸；1U 仅允许横向 */
export function resolveSlotSize(
  slot: LayoutSlotDef,
  formFactor: ServerFormFactor,
): { w: number; h: number } {
  const orientation: ServerSlotOrientation =
    formFactor === 1 ? 'horizontal' : slot.orientation ?? defaultSlotOrientation(formFactor)
  const def = serverCardSize(orientation)
  let w = slot.layout_w ?? def.w
  let h = slot.layout_h ?? def.h

  // 方向与宽高比不一致时，回落到该方向的标准尺寸
  if (orientation === 'horizontal' && h > w) {
    w = def.w
    h = def.h
  } else if (orientation === 'vertical' && w > h) {
    w = def.w
    h = def.h
  }

  if (formFactor === 1) {
    const maxH = Math.max(36, Math.min(def.h + 8, 64))
    return clampServerCardSize(w, Math.min(h, maxH))
  }
  return clampServerCardSize(w, h)
}

function defaultSlotPosition(
  idx: number,
  slot: LayoutSlotDef,
  formFactor: ServerFormFactor,
  zone: { x: number; y: number; w: number; h: number },
  opts?: { total?: number; rightEdgeGap?: number; cardGap?: number; frameWidth?: number },
): { x: number; y: number; w: number; h: number } {
  const { w, h } = resolveSlotSize(slot, formFactor)
  const orientation: ServerSlotOrientation =
    formFactor === 1 ? 'horizontal' : slot.orientation ?? defaultSlotOrientation(formFactor)
  const cardGap = opts?.cardGap ?? (formFactor === 1 ? SERVER_SLOT_GAP : 12)

  // 1U 或横放：贴扩展区底部，自左向右排
  if (formFactor === 1 || orientation === 'horizontal') {
    const gap = formFactor === 1 ? SERVER_SLOT_GAP : cardGap
    const perRow = Math.max(1, Math.floor((zone.w + gap) / (w + gap)))
    const col = idx % perRow
    const row = Math.floor(idx / perRow)
    const x = zone.x + col * (w + gap)
    const y = zone.y + zone.h - h - 4 - row * (h + gap)
    return { x, y, w, h }
  }

  // 2U/4U 竖放：纵向卡横向并排；自左向右，最右侧卡距右边缘加大留白
  const total = Math.max(1, opts?.total ?? 1)
  const rightEdgeGap = opts?.rightEdgeGap ?? 28
  const frameWidth = opts?.frameWidth ?? zone.x + zone.w + rightEdgeGap
  const rightmostX = frameWidth - rightEdgeGap - w
  const x = rightmostX - (total - 1 - idx) * (w + cardGap)
  const y = zone.y + Math.max(4, Math.min(12, (zone.h - h) / 2))
  return { x, y, w, h }
}

/** 扩展卡接口数量：1–10；超过 5 必须为偶数 */
export const SERVER_SLOT_PORT_MAX = 10

export function normalizeServerSlotPortCount(count: number): number {
  let n = Math.max(1, Math.min(SERVER_SLOT_PORT_MAX, Math.round(count)))
  if (n > 5 && n % 2 === 1) n -= 1
  return Math.max(1, n)
}

/**
 * 在一维上均匀分布：边距 = 间距（space-evenly），并保证最小边距。
 * 返回每个元素的起始坐标与实际使用的尺寸。
 */
function evenSpread(
  origin: number,
  length: number,
  count: number,
  preferredSize: number,
  minGap = 6,
): { positions: number[]; size: number } {
  if (count <= 0) return { positions: [], size: preferredSize }
  if (count === 1) {
    const size = Math.max(6, Math.min(preferredSize, Math.max(6, length - minGap * 2)))
    return {
      positions: [origin + Math.max(0, (length - size) / 2)],
      size,
    }
  }
  const size = Math.max(6, Math.min(preferredSize, (length - minGap * (count + 1)) / count))
  const gap = Math.max(minGap, (length - size * count) / (count + 1))
  const positions: number[] = []
  for (let i = 0; i < count; i += 1) {
    positions.push(origin + gap + i * (size + gap))
  }
  return { positions, size }
}

function placePortsInSlot(
  ports: FramePort[],
  slotX: number,
  slotY: number,
  slotW: number,
  slotH: number,
  orientation: ServerSlotOrientation,
) {
  const unlocked = ports.filter((p) => !p.layout_locked)
  if (!unlocked.length) return

  // 边框留白：竖卡左侧挡板 / 横卡顶部挡板 + 四周内边距
  const sideBracket = orientation === 'vertical' ? 8 : 0
  const topBracket = orientation === 'horizontal' ? 6 : 0
  const edgePad = 6
  const labelH = SERVER_LABEL_H
  const areaX = slotX + sideBracket + edgePad
  const areaY = slotY + topBracket + labelH + edgePad
  const areaW = Math.max(16, slotW - sideBracket - edgePad * 2)
  const areaH = Math.max(12, slotH - topBracket - labelH - edgePad * 2)
  const count = unlocked.length
  const minGap = 6

  // ≤5：单列（纵向卡）或单行（横向卡）；>5：两列 / 两行
  let cols: number
  let rows: number
  if (count <= 1) {
    cols = 1
    rows = 1
  } else if (count <= 5) {
    if (orientation === 'vertical') {
      cols = 1
      rows = count
    } else {
      cols = count
      rows = 1
    }
  } else if (orientation === 'vertical') {
    cols = 2
    rows = Math.ceil(count / 2)
  } else {
    cols = Math.ceil(count / 2)
    rows = 2
  }

  const preferredW = orientation === 'vertical' ? 16 : 18
  const preferredH = orientation === 'vertical' ? 14 : 13
  const spreadX = evenSpread(areaX, areaW, cols, preferredW, minGap)
  const spreadY = evenSpread(areaY, areaH, rows, preferredH, minGap)
  const portW = spreadX.size
  const portH = spreadY.size
  const colX = spreadX.positions
  const rowY = spreadY.positions

  unlocked.forEach((port, i) => {
    const row = Math.floor(i / cols)
    const col = i % cols
    // 末行不足时，在该行内重新均匀分布并居中
    const itemsInRow = Math.min(cols, count - row * cols)
    let x = colX[col]
    if (itemsInRow < cols && itemsInRow > 0) {
      const rowSpread = evenSpread(areaX, areaW, itemsInRow, portW, minGap)
      x = rowSpread.positions[col] ?? x
    }

    port.x = x
    port.y = rowY[row]
    port.w = portW
    port.h = portH
    if (!port.label || /^\d+$/.test(port.label) || /^[A-Z]+\d+$/i.test(port.label)) {
      port.label = String(i + 1)
    }
  })
}

function placeOnboard1gPorts(
  layout: PortLayout,
  zone: { x: number; y: number; w: number; h: number },
) {
  const count = Math.max(0, Math.min(8, layout.server_onboard_1g_count ?? 4))
  layout.server_onboard_1g_count = count
  const existing = (layout.ports || []).filter((p) => p.slot_index === 0)
  const peerById = new Map(existing.map((p) => [p.id, p]))
  const onboardPorts: FramePort[] = []
  const ports: FramePort[] = (layout.ports || []).filter((p) => p.slot_index !== 0)
  const gap = 4
  const cols = Math.min(count, 4)
  const rows = Math.max(1, Math.ceil(count / cols))
  const portW = Math.min(14, (zone.w - 8 - gap * (cols - 1)) / Math.max(cols, 1))
  const portH = Math.min(11, (zone.h - 18 - gap * (rows - 1)) / rows)
  const blockW = cols * portW + (cols - 1) * gap
  const blockH = rows * portH + (rows - 1) * gap
  const startX = zone.x + Math.max(4, (zone.w - blockW) / 2)
  const startY = zone.y + zone.h - blockH - 6

  for (let i = 0; i < count; i += 1) {
    const id = `onboard-1g-${i + 1}`
    const prev = peerById.get(id)
    const col = i % cols
    const row = Math.floor(i / cols)
    const port: FramePort = prev
      ? { ...prev }
      : {
          id,
          label: String(i + 1),
          x: 0,
          y: 0,
          w: portW,
          h: portH,
          port_type: '1g',
          slot_index: 0,
          group_id: 'onboard',
          peer_node_id: null,
          peer_port: null,
          peer_label: null,
        }
    if (!port.layout_locked) {
      port.x = startX + col * (portW + gap)
      port.y = startY + row * (portH + gap)
      port.w = portW
      port.h = portH
    }
    onboardPorts.push(port)
  }
  layout.ports = [...onboardPorts, ...ports]
}

function clampSlotInFrame(
  layout: PortLayout,
  x: number,
  y: number,
  w: number,
  h: number,
) {
  const minX = SERVER_PANEL_PAD
  const minY = SERVER_HEADER_H
  const maxX = layout.frame_width - w - SERVER_PANEL_PAD
  const maxY = layout.frame_height - 8 - h
  return {
    x: snapServerCoord(Math.max(minX, Math.min(x, maxX))),
    y: snapServerCoord(Math.max(minY, Math.min(y, maxY))),
  }
}

export function layoutServerRearPanel(layout: PortLayout): ServerPanelView {
  const formFactor = normalizeServerFormFactor(layout.server_form_factor ?? layout.height_u ?? 1)
  layout.server_form_factor = formFactor
  layout.height_u = formFactor

  const usedSlots = layout.slots_def || []
  layout.slot_count = usedSlots.length

  const metrics = panelMetrics(formFactor, usedSlots.length)
  layout.frame_width = metrics.frameWidth
  layout.frame_height = metrics.frameHeight
  layout.rack_width_mm = Math.round(metrics.frameWidth / 0.6)

  const psus = serverPsuLayout(formFactor, metrics.frameWidth, metrics.frameHeight)
  const visuals: ServerSlotVisual[] = []

  usedSlots.forEach((slot, idx) => {
    const kind = inferServerSlotKind(slot)
    slot.server_slot_kind = kind
    // 1U：强制横向；2U/4U：保留用户选择的横/竖放
    if (formFactor === 1) {
      const wasVertical =
        slot.orientation === 'vertical' ||
        (slot.layout_h != null && slot.layout_w != null && slot.layout_h > slot.layout_w)
      slot.orientation = 'horizontal'
      if (wasVertical || slot.layout_w == null || slot.layout_h == null) {
        slot.layout_w = SERVER_CARD_H.w
        slot.layout_h = SERVER_CARD_H.h
      }
      if (wasVertical) {
        slot.layout_x = null
        slot.layout_y = null
      }
    } else if (!slot.orientation) {
      slot.orientation = defaultSlotOrientation(formFactor)
    }
    if (slot.layout_w == null || slot.layout_h == null) {
      const defSize = serverCardSize(slot.orientation ?? defaultSlotOrientation(formFactor))
      slot.layout_w = defSize.w
      slot.layout_h = defSize.h
    }
    const orientation = slot.orientation ?? defaultSlotOrientation(formFactor)
    if (slot.groups?.length && kind !== 'raid' && kind !== 'blank') {
      slot.groups.forEach((g) => {
        g.count = normalizeServerSlotPortCount(g.count)
      })
    }
    const size = resolveSlotSize(slot, formFactor)
    slot.layout_w = size.w
    slot.layout_h = size.h
    const def = defaultSlotPosition(idx, slot, formFactor, metrics.expansionZone, {
      total: usedSlots.length,
      rightEdgeGap: metrics.rightEdgeGap,
      cardGap: metrics.cardGap,
      frameWidth: metrics.frameWidth,
    })
    // 优先使用已拖动位置；1U 保持贴底（仅允许水平拖动）
    const rawX = slot.layout_x ?? def.x
    const rawY = formFactor === 1 ? def.y : (slot.layout_y ?? def.y)
    const pos = clampSlotInFrame(layout, rawX, rawY, size.w, size.h)
    slot.layout_x = pos.x
    slot.layout_y = pos.y

    visuals.push({
      slotIndex: idx + 1,
      kind,
      orientation,
      label: SERVER_SLOT_KIND_LABELS[kind],
      shortLabel: shortKindLabel(kind),
      x: pos.x,
      y: pos.y,
      w: size.w,
      h: size.h,
      draggable: true,
      resizable: true,
    })

    const slotPorts = (layout.ports || []).filter((p) => p.slot_index === idx + 1)
    if (kind !== 'raid' && kind !== 'blank') {
      placePortsInSlot(slotPorts, pos.x, pos.y, size.w, size.h, orientation)
    }
  })

  placeOnboard1gPorts(layout, metrics.onboard1gZone)

  return {
    formFactor,
    title: SERVER_FORM_FACTOR_LABELS[formFactor],
    frameWidth: metrics.frameWidth,
    frameHeight: metrics.frameHeight,
    slots: visuals,
    psus,
    fixedIo: metrics.fixedIo,
    vent: metrics.vent,
    expansionZone: metrics.expansionZone,
    onboard1gZone: metrics.onboard1gZone,
    grid: { rows: 1, cols: Math.max(1, usedSlots.length) },
  }
}

export function moveServerSlotInPanel(
  layout: PortLayout,
  slotIndex: number,
  absX: number,
  absY: number,
) {
  const slot = layout.slots_def?.[slotIndex]
  if (!slot) return
  const formFactor = normalizeServerFormFactor(layout.server_form_factor ?? 1)
  const { w, h } = resolveSlotSize(slot, formFactor)
  const pos = clampSlotInFrame(layout, absX, absY, w, h)
  slot.layout_x = pos.x
  slot.layout_y = pos.y
  layoutServerRearPanel(layout)
}

export function resizeServerSlotInPanel(
  layout: PortLayout,
  slotIndex: number,
  nextW: number,
  nextH: number,
) {
  const slot = layout.slots_def?.[slotIndex]
  if (!slot) return
  const size = clampServerCardSize(snapServerCoord(nextW), snapServerCoord(nextH))
  slot.layout_w = size.w
  slot.layout_h = size.h
  // 尺寸变化后根据宽高比推断方向
  slot.orientation = size.w >= size.h ? 'horizontal' : 'vertical'
  const x = slot.layout_x ?? SERVER_PANEL_PAD
  const y = slot.layout_y ?? SERVER_HEADER_H
  const pos = clampSlotInFrame(layout, x, y, size.w, size.h)
  slot.layout_x = pos.x
  slot.layout_y = pos.y
  ;(layout.ports || [])
    .filter((p) => p.slot_index === slotIndex + 1)
    .forEach((p) => {
      p.layout_locked = false
    })
  layoutServerRearPanel(layout)
}

export function moveServerPortInPanel(layout: PortLayout, portId: string, absX: number, absY: number) {
  const port = layout.ports.find((p) => p.id === portId)
  if (!port || port.slot_index == null) return
  const formFactor = normalizeServerFormFactor(layout.server_form_factor ?? 1)
  const metrics = panelMetrics(formFactor, layout.slots_def?.length ?? 4)

  if (port.slot_index === 0) {
    const zone = metrics.onboard1gZone
    port.x = snapServerCoord(Math.max(zone.x, Math.min(absX, zone.x + zone.w - port.w)), 2)
    port.y = snapServerCoord(Math.max(zone.y, Math.min(absY, zone.y + zone.h - port.h)), 2)
    port.layout_locked = true
    return
  }

  const slotIdx = port.slot_index - 1
  const slot = layout.slots_def?.[slotIdx]
  if (!slot) return
  const size = resolveSlotSize(slot, formFactor)
  const slotX = slot.layout_x ?? SERVER_PANEL_PAD
  const slotY = slot.layout_y ?? SERVER_HEADER_H
  const pad = 2
  port.x = snapServerCoord(Math.max(slotX + pad, Math.min(absX, slotX + size.w - port.w - pad)), 2)
  port.y = snapServerCoord(Math.max(slotY + SERVER_LABEL_H, Math.min(absY, slotY + size.h - port.h - pad)), 2)
  port.layout_locked = true
}

export function applyServerFormFactor(layout: PortLayout, formFactor: ServerFormFactor) {
  const next = normalizeServerFormFactor(formFactor)
  layout.server_form_factor = next
  layout.height_u = next
  if (!layout.slots_def?.length) {
    layout.slots_def = defaultServerSlotsDef(next)
  }
  layout.slot_count = layout.slots_def.length
  if (layout.server_onboard_1g_count == null) layout.server_onboard_1g_count = 4
  layout.slots_def.forEach((slot) => {
    if (next === 1) {
      slot.orientation = 'horizontal'
      slot.layout_w = SERVER_CARD_H.w
      slot.layout_h = SERVER_CARD_H.h
      slot.layout_x = null
      slot.layout_y = null
    } else {
      slot.orientation = 'vertical'
      slot.layout_w = SERVER_CARD_V.w
      slot.layout_h = SERVER_CARD_V.h
      slot.layout_x = null
      slot.layout_y = null
    }
  })
}

export { SERVER_CARD_H, SERVER_CARD_V }
