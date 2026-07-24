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
  SERVER_CARD_MIN,
  SERVER_CARD_MAX,
  SERVER_HEADER_H,
  SERVER_PANEL_PAD,
  SERVER_SLOT_GAP,
  clampServerCardSize,
  computeServerRearGeometry,
  defaultSlotOrientation,
  rearDefaultSlotCount,
  serverCardSize,
  snapServerCoord,
  type ServerFixedIoVisual,
  type ServerRearIoRegions,
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
  psus: ReturnType<typeof computeServerRearGeometry>['psus']
  fixedIo: ServerFixedIoVisual
  ioRegions: ServerRearIoRegions
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
  // 尺寸留空，由 layoutServerRearPanel 按网格单元赋与默认卡一致的宽高
  if (kind === 'raid' || kind === 'blank') {
    return {
      server_slot_kind: kind,
      orientation: ori,
      groups: [],
      layout_x: null,
      layout_y: null,
      layout_w: null,
      layout_h: null,
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
    layout_w: null,
    layout_h: null,
  }
}

/** 默认 Slot：1U 两张扩展卡；2U/4U 对齐参考网格数量 */
export function defaultServerSlotsDef(formFactor: ServerFormFactor = 1): LayoutSlotDef[] {
  if (formFactor === 1) {
    return [
      newServerSlotDef('nic_10g', 2, 'horizontal'),
      newServerSlotDef('nic_1g', 4, 'horizontal'),
    ]
  }
  if (formFactor === 2) {
    return [
      newServerSlotDef('nic_10g', 2, 'horizontal'),
      newServerSlotDef('nic_10g', 2, 'horizontal'),
      newServerSlotDef('nic_1g', 4, 'horizontal'),
      newServerSlotDef('blank', 0, 'horizontal'),
      newServerSlotDef('blank', 0, 'horizontal'),
      newServerSlotDef('blank', 0, 'horizontal'),
      newServerSlotDef('blank', 0, 'horizontal'),
      newServerSlotDef('blank', 0, 'horizontal'),
    ]
  }
  const kinds: ServerSlotKind[] = [
    'nic_10g', 'nic_10g', 'nic_1g', 'hba', 'raid',
    'blank', 'blank', 'blank', 'blank', 'blank',
    'blank', 'blank', 'blank',
  ]
  const n = rearDefaultSlotCount(formFactor)
  return kinds.slice(0, n).map((k) =>
    newServerSlotDef(k, k === 'hba' ? 2 : k.startsWith('nic') ? 2 : 0, 'horizontal'),
  )
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

export function resolveSlotSize(
  slot: LayoutSlotDef,
  formFactor: ServerFormFactor,
  gridCell?: { w: number; h: number },
): { w: number; h: number } {
  const orientation: ServerSlotOrientation =
    formFactor === 1
      ? 'horizontal'
      : (slot.orientation ?? defaultSlotOrientation(formFactor))
  const def = serverCardSize(orientation)

  let w = slot.layout_w
  let h = slot.layout_h

  if (w == null || h == null) {
    if (orientation === 'horizontal' && gridCell) {
      w = gridCell.w
      h = gridCell.h
    } else if (orientation === 'vertical' && gridCell) {
      // 竖卡：窄而高，默认贴近列宽的约 1/3、高度约两格
      w = Math.max(SERVER_CARD_MIN.w, Math.min(def.w, Math.round(gridCell.w * 0.32)))
      h = Math.max(def.h, Math.round(gridCell.h * 2.2))
    } else {
      w = def.w
      h = def.h
    }
  }

  // 方向与宽高比不一致时交换，保证「纵向」真正变成竖卡
  if (orientation === 'horizontal' && h > w) {
    ;[w, h] = [h, w]
  } else if (orientation === 'vertical' && w > h) {
    ;[w, h] = [h, w]
  }

  return clampServerCardSize(w, h)
}

export const SERVER_SLOT_PORT_MAX = 10

export function normalizeServerSlotPortCount(count: number): number {
  let n = Math.max(1, Math.min(SERVER_SLOT_PORT_MAX, Math.round(count)))
  if (n > 5 && n % 2 === 1) n -= 1
  return Math.max(1, n)
}

/** 扩展卡接口目标尺寸（按类型区分，优先放大以便识别） */
function preferredServerPortBox(type: FramePort['port_type'] | null | undefined): {
  w: number
  h: number
  aspect: number
} {
  if (type === '40_100g') return { w: 30, h: 18, aspect: 30 / 18 }
  if (type === '10g') return { w: 24, h: 16, aspect: 24 / 16 }
  if (type === 'bmc') return { w: 22, h: 14, aspect: 22 / 14 }
  return { w: 26, h: 16, aspect: 26 / 16 }
}

function placePortsInSlot(
  ports: FramePort[],
  slotX: number,
  slotY: number,
  slotW: number,
  slotH: number,
) {
  const unlocked = ports.filter((p) => !p.layout_locked)
  if (!unlocked.length) return

  // 顶部留给卡类型短标签；编号画在接口内部，不再额外预留下方文字带
  const titleBand = Math.min(12, Math.max(9, slotH * 0.22))
  const edgePadX = 4
  const edgePadBot = 2
  const areaX = slotX + edgePadX
  const areaY = slotY + titleBand
  const areaW = Math.max(20, slotW - edgePadX * 2)
  const areaH = Math.max(14, slotH - titleBand - edgePadBot)
  const count = unlocked.length

  let cols: number
  let rows: number
  const verticalSlot = slotH >= slotW * 1.15
  if (count <= 1) {
    cols = 1
    rows = 1
  } else if (verticalSlot) {
    if (count <= 5) {
      cols = 1
      rows = count
    } else {
      cols = 2
      rows = Math.ceil(count / 2)
    }
  } else if (count <= 4) {
    cols = count
    rows = 1
  } else if (count <= 6) {
    cols = Math.ceil(count / 2)
    rows = 2
  } else {
    cols = Math.ceil(count / 2)
    rows = 2
  }

  const typeVotes = new Map<string, number>()
  unlocked.forEach((p) => {
    const t = p.port_type || '1g'
    typeVotes.set(t, (typeVotes.get(t) || 0) + 1)
  })
  const dominantType = [...typeVotes.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || '1g'
  const pref = preferredServerPortBox(dominantType as FramePort['port_type'])

  const gapX = cols <= 2 ? 5 : cols <= 4 ? 3.5 : 2.5
  const gapY = rows <= 1 ? 0 : 3

  let portW = Math.min(pref.w, (areaW - gapX * (cols + 1)) / cols)
  let portH = Math.min(pref.h, (areaH - gapY * (rows + 1)) / rows)
  // 保持插座比例，避免被压扁成难辨认的小条
  if (portW / Math.max(portH, 0.1) > pref.aspect) {
    portW = portH * pref.aspect
  } else {
    portH = portW / pref.aspect
  }
  portW = Math.max(11, portW)
  portH = Math.max(8, portH)
  // 若保比例后仍超区，再等比缩小
  const maxW = (areaW - gapX * (cols + 1)) / cols
  const maxH = (areaH - gapY * (rows + 1)) / rows
  const fit = Math.min(1, maxW / portW, maxH / portH)
  portW = Math.max(10, portW * fit)
  portH = Math.max(8, portH * fit)

  const blockW = cols * portW + Math.max(0, cols - 1) * gapX
  const blockH = rows * portH + Math.max(0, rows - 1) * gapY
  const startX = areaX + Math.max(0, (areaW - blockW) / 2)
  const startY = areaY + Math.max(0, (areaH - blockH) / 2)

  unlocked.forEach((port, i) => {
    const row = Math.floor(i / cols)
    const col = i % cols
    const itemsInRow = Math.min(cols, count - row * cols)
    let x = startX + col * (portW + gapX)
    if (itemsInRow < cols && itemsInRow > 0) {
      const rowBlockW = itemsInRow * portW + (itemsInRow - 1) * gapX
      const rowStartX = areaX + Math.max(0, (areaW - rowBlockW) / 2)
      x = rowStartX + col * (portW + gapX)
    }
    port.x = Math.round(x * 10) / 10
    port.y = Math.round((startY + row * (portH + gapY)) * 10) / 10
    port.w = Math.round(portW * 10) / 10
    port.h = Math.round(portH * 10) / 10
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
  const gap = 5
  const cols = Math.min(count, 4)
  const rows = Math.max(1, Math.ceil(count / cols))
  const pref = preferredServerPortBox('1g')
  let portW = Math.min(pref.w, (zone.w - 10 - gap * (cols - 1)) / Math.max(cols, 1))
  let portH = Math.min(pref.h, (zone.h - 10 - gap * (rows - 1)) / rows)
  if (portW / Math.max(portH, 0.1) > pref.aspect) portW = portH * pref.aspect
  else portH = portW / pref.aspect
  portW = Math.max(12, portW)
  portH = Math.max(9, portH)
  const blockW = cols * portW + (cols - 1) * gap
  const blockH = rows * portH + (rows - 1) * gap
  const startX = zone.x + Math.max(4, (zone.w - blockW) / 2)
  const startY = zone.y + Math.max(4, (zone.h - blockH) / 2)

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

/** 竖卡从扩展区右侧向左依次占位，避免重叠 */
function packVerticalSlotX(
  zone: { x: number; y: number; w: number; h: number },
  cardW: number,
  occupied: Array<{ x: number; w: number }>,
): number {
  const gap = Math.max(SERVER_SLOT_GAP, 12)
  let x = zone.x + zone.w - cardW
  const rightFirst = [...occupied].sort((a, b) => b.x - a.x)
  for (const block of rightFirst) {
    const overlaps = !(x + cardW + gap <= block.x || x >= block.x + block.w + gap)
    if (overlaps) {
      x = block.x - gap - cardW
    }
  }
  return snapServerCoord(Math.max(zone.x, x))
}

export function layoutServerRearPanel(layout: PortLayout): ServerPanelView {
  const formFactor = normalizeServerFormFactor(layout.server_form_factor ?? layout.height_u ?? 1)
  layout.server_form_factor = formFactor
  layout.height_u = formFactor

  let usedSlots = layout.slots_def || []
  // 不再自动补空白挡板：删除扩展卡后必须与列表/图形一一对应
  layout.slot_count = usedSlots.length
  usedSlots = layout.slots_def || []

  const geo = computeServerRearGeometry(formFactor)
  layout.frame_width = geo.frameWidth
  layout.frame_height = geo.frameHeight
  // 示意图素尺寸 ≠ mm 换算；机架宽度保持标准 600mm，避免超过后端校验上限
  layout.rack_width_mm = 600

  type Prepared = {
    idx: number
    slot: LayoutSlotDef
    kind: ServerSlotKind
    orientation: ServerSlotOrientation
    size: { w: number; h: number }
    needsAutoPlace: boolean
  }

  const prepared: Prepared[] = usedSlots.map((slot, idx) => {
    const kind = inferServerSlotKind(slot)
    slot.server_slot_kind = kind
    const orientation: ServerSlotOrientation =
      formFactor === 1 ? 'horizontal' : (slot.orientation ?? defaultSlotOrientation(formFactor))
    slot.orientation = orientation

    // 超出预设网格时仍用同类单元尺寸，保证新建卡与默认卡一致
    const grid = geo.slotRects[idx] ?? geo.slotRects[0]
    const gridCell = grid ? { w: grid.w, h: grid.h } : undefined
    let size = resolveSlotSize(slot, formFactor, gridCell)
    // 横卡限制在网格单元内，保证列/行间隙可见（尤其 2U）
    if (orientation === 'horizontal' && gridCell) {
      size = clampServerCardSize(
        Math.min(size.w, gridCell.w),
        Math.min(size.h, gridCell.h),
      )
    }
    // 竖卡默认拉满扩展区高度，形成右侧立柱排列
    if (orientation === 'vertical' && (slot.layout_h == null || slot.layout_w == null)) {
      const tallH = Math.max(
        size.h,
        Math.min(SERVER_CARD_MAX.h, Math.round(geo.expansionZone.h - 2)),
      )
      size = clampServerCardSize(size.w, tallH)
    }
    slot.layout_w = size.w
    slot.layout_h = size.h

    if (slot.groups?.length && kind !== 'raid' && kind !== 'blank') {
      slot.groups.forEach((g) => {
        g.count = normalizeServerSlotPortCount(g.count)
      })
    }

    return {
      idx,
      slot,
      kind,
      orientation,
      size,
      needsAutoPlace: slot.layout_x == null || slot.layout_y == null,
    }
  })

  // 已手动定位的竖卡先占位，其余按索引从右向左依次插入
  const verticalOccupied: Array<{ x: number; w: number }> = []
  prepared.forEach((item) => {
    if (item.orientation !== 'vertical') return
    if (!item.needsAutoPlace && item.slot.layout_x != null) {
      verticalOccupied.push({ x: item.slot.layout_x, w: item.size.w })
    }
  })

  const visuals: ServerSlotVisual[] = []

  prepared.forEach((item) => {
    const { idx, slot, kind, orientation, size } = item
    const grid = geo.slotRects[idx]
    const refGrid = grid ?? geo.slotRects[Math.min(idx, geo.slotRects.length - 1)]

    let rawX: number
    let rawY: number
    if (orientation === 'vertical') {
      if (item.needsAutoPlace) {
        rawX = packVerticalSlotX(geo.expansionZone, size.w, verticalOccupied)
        rawY = snapServerCoord(geo.expansionZone.y)
        verticalOccupied.push({ x: rawX, w: size.w })
      } else {
        rawX = slot.layout_x as number
        rawY = slot.layout_y as number
      }
    } else if (item.needsAutoPlace) {
      if (grid) {
        rawX = grid.x
        rawY = grid.y
      } else if (refGrid) {
        // 超出预设网格：沿用单元尺寸，向下错开半格避免完全重叠
        const overflow = idx - (geo.slotRects.length - 1)
        rawX = refGrid.x
        rawY = snapServerCoord(refGrid.y + overflow * Math.max(8, Math.round(size.h * 0.35)))
      } else {
        rawX = SERVER_PANEL_PAD
        rawY = SERVER_HEADER_H
      }
    } else {
      rawX = slot.layout_x as number
      rawY = slot.layout_y as number
    }

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
      placePortsInSlot(slotPorts, pos.x, pos.y, size.w, size.h)
    }
  })

  if (layout.server_onboard_1g_count == null) layout.server_onboard_1g_count = 4
  placeOnboard1gPorts(layout, geo.onboard1gZone)

  // 仅保留当前扩展卡对应的端口，防止删除后面板残留旧卡口
  const validSlotIndexes = new Set(
    usedSlots.map((_, idx) => idx + 1).concat([0]),
  )
  layout.ports = (layout.ports || []).filter(
    (p) => p.slot_index == null || validSlotIndexes.has(p.slot_index),
  )

  return {
    formFactor,
    title: SERVER_FORM_FACTOR_LABELS[formFactor],
    frameWidth: geo.frameWidth,
    frameHeight: geo.frameHeight,
    slots: visuals,
    psus: geo.psus,
    fixedIo: geo.fixedIo,
    ioRegions: geo.ioRegions,
    vent: geo.vent,
    expansionZone: geo.expansionZone,
    onboard1gZone: geo.onboard1gZone,
    grid: { rows: Math.max(...geo.slotRects.map((r) => r.rowFromBottom + 1), 1), cols: 3 },
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
  const geo = computeServerRearGeometry(formFactor)
  const grid = geo.slotRects[slotIndex]
  const { w, h } = resolveSlotSize(slot, formFactor, grid ? { w: grid.w, h: grid.h } : undefined)
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
  const formFactor = normalizeServerFormFactor(layout.server_form_factor ?? 1)
  const size = clampServerCardSize(snapServerCoord(nextW), snapServerCoord(nextH))
  slot.layout_w = size.w
  slot.layout_h = size.h
  // 1U 强制横向；其余按宽高比推断放置方向
  slot.orientation =
    formFactor === 1 ? 'horizontal' : size.w >= size.h ? 'horizontal' : 'vertical'
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
  const geo = computeServerRearGeometry(formFactor)

  if (port.slot_index === 0) {
    const zone = geo.onboard1gZone
    port.x = snapServerCoord(Math.max(zone.x, Math.min(absX, zone.x + zone.w - port.w)), 2)
    port.y = snapServerCoord(Math.max(zone.y, Math.min(absY, zone.y + zone.h - port.h)), 2)
    port.layout_locked = true
    return
  }

  const slotIdx = port.slot_index - 1
  const slot = layout.slots_def?.[slotIdx]
  if (!slot) return
  const grid = geo.slotRects[slotIdx]
  const size = resolveSlotSize(slot, formFactor, grid ? { w: grid.w, h: grid.h } : undefined)
  const slotX = slot.layout_x ?? SERVER_PANEL_PAD
  const slotY = slot.layout_y ?? SERVER_HEADER_H
  const pad = 2
  port.x = snapServerCoord(Math.max(slotX + pad, Math.min(absX, slotX + size.w - port.w - pad)), 2)
  port.y = snapServerCoord(Math.max(slotY + 4, Math.min(absY, slotY + size.h - port.h - pad)), 2)
  port.layout_locked = true
}

export function applyServerFormFactor(layout: PortLayout, formFactor: ServerFormFactor) {
  const next = normalizeServerFormFactor(formFactor)
  layout.server_form_factor = next
  layout.height_u = next
  layout.slots_def = defaultServerSlotsDef(next)
  layout.slot_count = layout.slots_def.length
  if (layout.server_onboard_1g_count == null) layout.server_onboard_1g_count = 4
  layout.slots_def.forEach((slot) => {
    slot.orientation = 'horizontal'
    slot.layout_w = null
    slot.layout_h = null
    slot.layout_x = null
    slot.layout_y = null
  })
}

export { SERVER_CARD_H, SERVER_CARD_V }
