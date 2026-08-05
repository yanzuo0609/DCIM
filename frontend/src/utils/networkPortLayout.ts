import type {
  CoreLineCard,
  LayoutSlotDef,
  NetworkLink,
  NetworkLinkType,
  NetworkNode,
  NetworkNodeKind,
  PortLayout,
  PortType,
  SlotConfig,
  SlotInterfaceGroup,
  SwitchSubtype,
  UplinkPosition,
} from '@/api/network'
import {
  CORE_CARD_PORT_TYPE,
  CORE_CARD_TYPE_LABELS,
  PORT_TYPE_LABELS,
  PORT_TYPE_SHORT,
  SWITCH_SUBTYPE_DEFAULTS,
  defaultSlots,
  newCoreLineCard,
} from '@/api/network'
import { layoutSwitchFrontPanel, normalizeGigabitUplinkCount, normalizeTenGigabitUplinkCount } from '@/utils/switchFrontPanel'
import {
  applyServerFormFactor,
  defaultServerSlotsDef,
  layoutServerRearPanel,
  newServerSlotDef,
  normalizeServerFormFactor,
} from '@/utils/serverRearPanel'
import { layoutServerFrontPanel } from '@/utils/serverFrontPanel'
import {
  buildSecuritySlotsDef,
  defaultSecurityZones,
  layoutSecurityFrontPanel,
  normalizeSecurityHeightU,
  type SecurityZoneInput,
} from '@/utils/securityFrontPanel'
import { defaultSlotOrientation } from '@/utils/serverPanelCommon'
import type { ServerSlotKind } from '@/api/network'

export { moveServerSlotInPanel, moveServerPortInPanel, resizeServerSlotInPanel } from '@/utils/serverRearPanel'
export {
  moveSecurityZoneInPanel,
  resizeSecurityZoneInPanel,
  resetSecurityZonePositions,
} from '@/utils/securityFrontPanel'

export const RACK_WIDTH_MM = 600
export const MIN_DEVICE_WIDTH_MM = 200
export const U_HEIGHT_MM = 44.45
export const FRAME_HEADER_PX = 22
export const EDITOR_MM_SCALE = 0.6
export const MAX_SLOT_COUNT = 16
export const MAX_HEIGHT_U = 16
export const MAX_RACK_WIDTH_MM = 1200
export const EAR_WIDTH_PX = 14
export const LAYOUT_PAD_X = 12
export const LAYOUT_PAD_Y = 8
export const SLOT_LABEL_H = 14
export const SLOT_GAP = 4
export const GROUP_GAP = 6
export const MIN_PORT_W = 10
export const MIN_PORT_H = 8
export const PORT_GAP = 3
const MIN_FIT_SCALE = 0.45
const GROUP_INNER_PAD = 8
const GROUP_LABEL_H = 10
export const SLOT_GRID_PX = 8
export const SLOT_ALIGN_THRESHOLD = 6

interface GroupGrid {
  cols: number
  rows: number
  portW: number
  portH: number
  gap: number
  w: number
  h: number
}

interface GroupLayoutPos {
  x: number
  y: number
  w: number
  h: number
  grid: GroupGrid
}

function sortedGroups(groups: SlotInterfaceGroup[]): SlotInterfaceGroup[] {
  return groups
    .map((g, i) => ({ g, i }))
    .sort((a, b) => (a.g.layout_order ?? a.i) - (b.g.layout_order ?? b.i))
    .map(({ g }) => g)
}

function normalizeGroupOrders(slot: LayoutSlotDef) {
  ensureSlotGroups(slot)
  slot.groups.forEach((g, i) => {
    g.layout_order = i
    g.layout_x = null
    g.layout_y = null
  })
}

const PORT_TYPE_WEIGHT: Record<PortType, number> = {
  '1g': 1,
  '10g': 1.15,
  '40_100g': 1.75,
  bmc: 1.1,
  other: 1,
}

export interface SlotBandLayout {
  slotIndex: number
  label: string
  x: number
  y: number
  w: number
  h: number
  contentY: number
  contentH: number
  contentW: number
}

export interface GroupVisualLayout {
  groupId: string
  slotIndex: number
  portType: PortType
  label: string
  x: number
  y: number
  w: number
  h: number
  cols: number
  rows: number
}

export function newInterfaceGroup(
  portType: PortType,
  count: number,
  opts?: { role?: SlotInterfaceGroup['role']; grid_cols?: number | null },
): SlotInterfaceGroup {
  return {
    id: crypto.randomUUID().slice(0, 8),
    port_type: portType,
    count: Math.max(1, count),
    role: opts?.role ?? null,
    grid_cols: opts?.grid_cols ?? null,
    layout_x: null,
    layout_y: null,
  }
}

export interface SwitchLayoutConfig {
  subtype: SwitchSubtype
  mainPortCount: number
  uplinkPortCount: number
  uplinkPosition: UplinkPosition
  lineCards?: CoreLineCard[]
}

function uplinkGridCols(portType: PortType, count: number): number {
  if (portType === '40_100g') return Math.min(2, count)
  return Math.min(4, count)
}

function mainGridCols(count: number): number {
  if (count >= 48) return 24
  if (count >= 24) return 12
  return Math.min(8, count)
}

function uplinkGroupLabel(portType: PortType, count: number): string {
  if (portType === '10g') return `${count} × 1G/10G SFP+`
  if (portType === '40_100g') return `${count} × 10G/40G QSFP+`
  return `${count} × ${PORT_TYPE_LABELS[portType]}`
}

function buildCoreSlotsDef(cards: CoreLineCard[]): LayoutSlotDef[] {
  const list = cards.length ? cards : [newCoreLineCard('ten_gigabit', 48)]
  return list.map((card, idx) => {
    if (card.card_type === 'blank') {
      return {
        groups: [],
        layout_x: idx === 0 ? 0 : null,
        layout_y: 0,
        zone_label: '空白板卡',
      }
    }
    const portType = CORE_CARD_PORT_TYPE[card.card_type]
    const count = Math.max(1, card.port_count)
    const group = newInterfaceGroup(portType, count, {
      role: 'card',
      grid_cols: mainGridCols(count),
    })
    group.id = card.id || group.id
    return {
      groups: [group],
      layout_x: idx === 0 ? 0 : null,
      layout_y: 0,
    }
  })
}

export function buildSwitchSlotsDef(config: SwitchLayoutConfig): LayoutSlotDef[] {
  if (config.subtype === 'core') {
    return buildCoreSlotsDef(config.lineCards ?? [])
  }

  const defaults = SWITCH_SUBTYPE_DEFAULTS[config.subtype]
  const mainCount = Math.max(1, config.mainPortCount)
  const uplinkCount = Math.max(0, config.uplinkPortCount)
  const mainType = defaults.mainType
  const uplinkType = defaults.uplinkType

  if (uplinkCount <= 0) {
    return [{
      groups: [newInterfaceGroup(mainType, mainCount, { role: 'main', grid_cols: mainGridCols(mainCount) })],
      layout_x: 0,
      layout_y: 0,
    }]
  }

  const uplink = newInterfaceGroup(uplinkType, uplinkCount, {
    role: 'uplink',
    grid_cols: uplinkGridCols(uplinkType, uplinkCount),
  })

  if (config.uplinkPosition === 'middle') {
    const half = Math.floor(mainCount / 2)
    const rest = mainCount - half
    const mainLeft = newInterfaceGroup(mainType, half, { role: 'main', grid_cols: mainGridCols(half) })
    const mainRight = newInterfaceGroup(mainType, rest, { role: 'main', grid_cols: mainGridCols(rest) })
    mainLeft.layout_order = 0
    uplink.layout_order = 1
    mainRight.layout_order = 2
    return [{ groups: [mainLeft, uplink, mainRight], layout_x: 0, layout_y: 0 }]
  }

  const main = newInterfaceGroup(mainType, mainCount, { role: 'main', grid_cols: mainGridCols(mainCount) })
  return [
    { groups: [main], layout_x: 0, layout_y: 0 },
    { groups: [uplink], layout_x: null, layout_y: 0 },
  ]
}

export function applySwitchLayoutConfig(layout: PortLayout, config: SwitchLayoutConfig) {
  layout.switch_subtype = config.subtype
  if (config.subtype === 'core') {
    const cards = (config.lineCards?.length ? config.lineCards : [newCoreLineCard()]).map((c) => ({
      id: c.id || crypto.randomUUID().slice(0, 8),
      card_type: c.card_type,
      port_count: c.card_type === 'blank' ? 0 : Math.max(1, c.port_count),
    }))
    layout.line_cards = cards
    layout.uplink_position = null
    layout.main_port_count = null
    layout.uplink_port_count = null
    layout.slots_def = buildCoreSlotsDef(cards)
  } else {
    const uplinkCount =
      config.subtype === 'gigabit'
        ? normalizeGigabitUplinkCount(config.uplinkPortCount)
        : config.subtype === 'ten_gigabit' || config.subtype === 'aggregation'
          ? normalizeTenGigabitUplinkCount(config.uplinkPortCount)
          : Math.max(0, Math.min(32, config.uplinkPortCount))
    layout.line_cards = null
    layout.uplink_position = config.uplinkPosition
    layout.main_port_count = config.mainPortCount
    layout.uplink_port_count = uplinkCount
    layout.slots_def = buildSwitchSlotsDef({
      ...config,
      uplinkPortCount: uplinkCount,
    })
  }
  layout.slot_count = layout.slots_def.length
  syncPortsFromSlotsDef(layout, true)
}

export function readSwitchLayoutConfig(layout: PortLayout): SwitchLayoutConfig {
  const subtype = layout.switch_subtype ?? 'gigabit'
  const defaults = SWITCH_SUBTYPE_DEFAULTS[subtype]
  return {
    subtype,
    mainPortCount: layout.main_port_count ?? defaults.mainPortCount,
    uplinkPortCount: layout.uplink_port_count ?? defaults.uplinkPortCount,
    uplinkPosition: layout.uplink_position ?? 'right',
    lineCards: layout.line_cards?.length
      ? layout.line_cards.map((c) => ({ ...c }))
      : subtype === 'core'
        ? [newCoreLineCard()]
        : [],
  }
}

function slotBandLabel(slot: LayoutSlotDef, idx: number): string {
  if (slot.zone_label) return slot.zone_label
  const groups = ensureSlotGroups(slot)
  if (!groups.length) return '空白板卡'
  if (groups.length === 1 && groups[0].role === 'card') {
    return `板卡 ${idx + 1}`
  }
  if (groups.length === 1 && groups[0].role === 'uplink') return '上联'
  if (groups.every((g) => g.role === 'main' || g.role == null)) {
    if (groups.some((g) => g.role === 'main')) {
      return groups[0]?.port_type === '1g' ? '电口' : '光口'
    }
  }
  if (groups.some((g) => g.role === 'uplink') && groups.some((g) => g.role === 'main')) return '接口区'
  return `Slot ${idx + 1}`
}

function groupDisplayLabel(group: SlotInterfaceGroup): string {
  if (group.role === 'uplink') return uplinkGroupLabel(group.port_type, group.count)
  if (group.role === 'card') {
    const cardType =
      group.port_type === '1g' ? 'gigabit' : group.port_type === '10g' ? 'ten_gigabit' : '100g'
    return `${CORE_CARD_TYPE_LABELS[cardType]} ×${group.count}`
  }
  if (group.role === 'main') {
    return group.port_type === '1g' ? `电口 ×${group.count}` : `光口 ×${group.count}`
  }
  return `${PORT_TYPE_SHORT[group.port_type]} ×${group.count}`
}

export function coreSlotDisplayLabel(slot: LayoutSlotDef, idx: number): string {
  if (slot.zone_label) return slot.zone_label
  if (!slot.groups?.length) return '空白板卡'
  return groupDisplayLabel(slot.groups[0]) || `Slot ${idx + 1}`
}

export function slotPortCount(slot: LayoutSlotDef): number {
  return slot.groups.reduce((sum, g) => sum + g.count, 0)
}

export function migrateSlotToGroups(slot: LayoutSlotDef): LayoutSlotDef {
  if (slot.groups?.length) {
    slot.groups.forEach((g) => {
      if (!g.id) g.id = crypto.randomUUID().slice(0, 8)
      if (g.layout_x == null) g.layout_x = null
      if (g.layout_y == null) g.layout_y = null
    })
    // 已有 groups 时清除旧字段，避免后端 LayoutSlotDef.port_count 校验失败
    delete slot.port_count
    delete slot.default_port_type
    delete slot.port_types
    return slot
  }

  const groups: SlotInterfaceGroup[] = []
  if (slot.port_types?.length) {
    let current: SlotInterfaceGroup | null = null
    slot.port_types.forEach((type) => {
      if (current && current.port_type === type) {
        current.count += 1
      } else {
        current = newInterfaceGroup(type, 1)
        groups.push(current)
      }
    })
  } else if (slot.port_count) {
    groups.push(newInterfaceGroup(slot.default_port_type || '1g', slot.port_count))
  }

  slot.groups = groups
  delete slot.port_count
  delete slot.default_port_type
  delete slot.port_types
  return slot
}

export function ensureSlotGroups(slot: LayoutSlotDef): SlotInterfaceGroup[] {
  migrateSlotToGroups(slot)
  if (slot.server_slot_kind === 'raid' || slot.server_slot_kind === 'blank') {
    slot.groups = []
    return slot.groups
  }
  // 核心交换机空白板卡：允许空 groups，不自动补默认接口
  if (slot.zone_label === '空白板卡') {
    slot.groups = []
    return slot.groups
  }
  if (!slot.groups.length) {
    slot.groups.push(newInterfaceGroup('1g', 1))
  }
  return slot.groups
}

export function deviceFramePixels(rackWidthMm = RACK_WIDTH_MM, heightU = 1) {
  const frame_width = rackWidthMm * EDITOR_MM_SCALE
  const contentHeight = U_HEIGHT_MM * heightU * EDITOR_MM_SCALE
  const frame_height = FRAME_HEADER_PX + contentHeight
  return {
    frame_width: Math.round(frame_width * 100) / 100,
    frame_height: Math.round(frame_height * 100) / 100,
    rack_width_mm: rackWidthMm,
    height_u: heightU,
  }
}

export function defaultSlotsDef(kind: NetworkNodeKind, slotCount?: number): LayoutSlotDef[] {
  if (kind === 'switch') {
    return buildSwitchSlotsDef({
      subtype: 'gigabit',
      mainPortCount: 48,
      uplinkPortCount: 4,
      uplinkPosition: 'right',
    })
  }
  if (kind === 'server') {
    return defaultServerSlotsDef(1)
  }
  // security
  return buildSecuritySlotsDef(defaultSecurityZones())
}

export function defaultPortLayout(kind: NetworkNodeKind, rackWidthMm = RACK_WIDTH_MM, heightU = 1): PortLayout {
  const frame = deviceFramePixels(rackWidthMm, heightU)
  const slots_def = defaultSlotsDef(kind)
  const layout: PortLayout = {
    ...frame,
    slot_count: slots_def.length,
    slots_def,
    ports: [],
  }
  if (kind === 'switch') {
    layout.switch_subtype = 'gigabit'
    layout.uplink_position = 'right'
    layout.main_port_count = 48
    layout.uplink_port_count = 4
  }
  if (kind === 'server') {
    layout.server_form_factor = 1
    layout.height_u = 1
  }
  if (kind === 'security') {
    layout.security_panel = true
    layout.height_u = heightU
  }
  return layout
}

export function ensureSlotsDef(layout: PortLayout): LayoutSlotDef[] {
  if (layout.slots_def?.length) {
    layout.slot_count = layout.slots_def.length
    layout.slots_def.forEach(ensureSlotGroups)
    return layout.slots_def
  }
  layout.slots_def = defaultSlotsDef('server', layout.slot_count || 1)
  layout.slot_count = layout.slots_def.length
  return layout.slots_def
}

export function addSlotWithGroup(layout: PortLayout, portType: PortType, count: number) {
  const slots = ensureSlotsDef(layout)
  if (!layout.server_form_factor && slots.length >= MAX_SLOT_COUNT) return
  const displayScale = layoutDisplayScale(layout) || 1
  const gap = SLOT_GAP * displayScale
  const kind: ServerSlotKind =
    portType === '1g' ? 'nic_1g' : portType === '10g' ? 'nic_10g' : portType === 'other' ? 'hba' : 'nic_1g'
  const newSlot: LayoutSlotDef = layout.server_form_factor
    ? newServerSlotDef(kind, count)
    : { groups: [newInterfaceGroup(portType, count)], layout_x: 0, layout_y: 0 }
  if (!layout.server_form_factor && slots.length > 0) {
    const last = slots[slots.length - 1]
    const lastW = computeSlotRequiredContentWidth(last, displayScale) + 8 * displayScale
    newSlot.layout_x = (last.layout_x ?? 0) + lastW + gap
    newSlot.layout_y = last.layout_y ?? 0
  }
  slots.push(newSlot)
  layout.slot_count = slots.length
}

export function addServerSlot(layout: PortLayout, kind: ServerSlotKind, portCount: number) {
  const ff = normalizeServerFormFactor(layout.server_form_factor ?? 1)
  layout.server_form_factor = ff
  if (layout.height_u == null) layout.height_u = ff
  const slots = ensureSlotsDef(layout)
  const slot = newServerSlotDef(kind, portCount, defaultSlotOrientation(ff))
  slot.layout_x = null
  slot.layout_y = null
  slots.push(slot)
  layout.slot_count = slots.length
}

export function addGroupToSlot(layout: PortLayout, slotIndex: number, portType: PortType, count: number) {
  const slots = ensureSlotsDef(layout)
  const slot = slots[slotIndex]
  if (!slot) return
  slot.groups.push(newInterfaceGroup(portType, count))
}

export function removeSlot(layout: PortLayout, slotIndex: number) {
  const slots = ensureSlotsDef(layout)
  if (slots.length <= 1) return
  const removed = slotIndex + 1
  slots.splice(slotIndex, 1)
  layout.slot_count = slots.length
  // 删除对应端口，并将后续槽位序号前移，避免面板残留旧卡口
  layout.ports = (layout.ports || [])
    .filter((p) => p.slot_index !== removed)
    .map((p) => {
      if (p.slot_index != null && p.slot_index > removed) {
        const nextIdx = p.slot_index - 1
        return {
          ...p,
          slot_index: nextIdx,
          id: p.id.replace(new RegExp(`^slot${p.slot_index}`), `slot${nextIdx}`),
        }
      }
      return p
    })
}

export function removeGroupFromSlot(layout: PortLayout, slotIndex: number, groupId: string) {
  const slot = ensureSlotsDef(layout)[slotIndex]
  if (!slot) return
  slot.groups = slot.groups.filter((g) => g.id !== groupId)
  if (!slot.groups.length) {
    slot.groups.push(newInterfaceGroup('1g', 1))
  }
}

export function layoutDisplayScale(layout: PortLayout): number {
  const base = deviceFramePixels(layout.rack_width_mm ?? RACK_WIDTH_MM, layout.height_u ?? 1)
  return layout.frame_width / base.frame_width
}

function portSizeForType(portType: PortType, displayScale: number, fitScale = 1) {
  const scale = displayScale * fitScale
  const weight = PORT_TYPE_WEIGHT[portType] || 1
  const portW = Math.max(MIN_PORT_W * scale, 12 * scale * weight)
  const portH = Math.min(Math.max(MIN_PORT_H * scale, portW * 0.55), 24 * scale)
  return { portW, portH }
}

function computeGroupGrid(
  group: SlotInterfaceGroup,
  maxContentW: number,
  displayScale: number,
  fitScale = 1,
): GroupGrid {
  const gap = PORT_GAP * displayScale * fitScale
  const { portW, portH } = portSizeForType(group.port_type, displayScale, fitScale)
  let bestCols = 1
  const preferredCols = group.grid_cols && group.grid_cols > 0 ? Math.min(group.grid_cols, group.count) : null
  if (preferredCols) {
    bestCols = preferredCols
  } else {
    for (let cols = 1; cols <= group.count; cols += 1) {
      const rowW = cols * portW + (cols - 1) * gap
      if (rowW <= maxContentW) bestCols = cols
    }
  }
  const cols = bestCols
  const rows = Math.ceil(group.count / cols)
  const innerPad = GROUP_INNER_PAD * displayScale * fitScale
  const labelH = GROUP_LABEL_H * displayScale * fitScale
  const w = cols * portW + Math.max(0, cols - 1) * gap + innerPad
  const h = labelH + rows * portH + Math.max(0, rows - 1) * gap + innerPad * 0.5
  return { cols, rows, portW, portH, gap, w, h }
}

/** 垂直方向自上而下、水平方向居左排列接口组，整体块在 Slot 内水平居中 */
function flowGroupsCenteredBlock(
  groups: SlotInterfaceGroup[],
  contentW: number,
  displayScale: number,
  fitScale: number,
): Map<string, GroupLayoutPos> {
  const groupGap = GROUP_GAP * displayScale * fitScale
  const ordered = sortedGroups(groups)
  const positions = new Map<string, GroupLayoutPos>()
  const rows: Array<Array<{ id: string; pos: GroupLayoutPos }>> = []
  let row: Array<{ id: string; pos: GroupLayoutPos }> = []
  let rowW = 0

  ordered.forEach((group) => {
    const grid = computeGroupGrid(group, contentW, displayScale, fitScale)
    const item: GroupLayoutPos = { x: 0, y: 0, w: grid.w, h: grid.h, grid }
    if (row.length > 0 && rowW + groupGap + grid.w > contentW) {
      rows.push(row)
      row = []
      rowW = 0
    }
    if (row.length > 0) rowW += groupGap
    item.x = rowW
    row.push({ id: group.id, pos: item })
    rowW += grid.w
  })
  if (row.length) rows.push(row)

  let cursorY = 0
  rows.forEach((items) => {
    const rH = Math.max(...items.map((i) => i.pos.h))
    items.forEach(({ id, pos }) => {
      pos.y = cursorY
      positions.set(id, pos)
    })
    cursorY += rH + groupGap
  })

  let blockW = 0
  let blockH = Math.max(0, cursorY - groupGap)
  positions.forEach((pos) => {
    blockW = Math.max(blockW, pos.x + pos.w)
    blockH = Math.max(blockH, pos.y + pos.h)
  })
  const offsetX = Math.max(0, (contentW - blockW) / 2)
  positions.forEach((pos) => {
    pos.x += offsetX
  })

  return positions
}

function layoutSlotGroups(
  slot: LayoutSlotDef,
  contentW: number,
  contentH: number,
  displayScale: number,
): { positions: Map<string, GroupLayoutPos>; fitScale: number } {
  const groups = ensureSlotGroups(slot)
  for (let fitScale = 1; fitScale >= MIN_FIT_SCALE; fitScale -= 0.05) {
    const positions = flowGroupsCenteredBlock(groups, contentW, displayScale, fitScale)
    let maxX = 0
    let maxY = 0
    positions.forEach((pos) => {
      maxX = Math.max(maxX, pos.x + pos.w)
      maxY = Math.max(maxY, pos.y + pos.h)
    })
    if (maxX <= contentW + 0.5 && maxY <= contentH + 0.5) {
      return { positions, fitScale }
    }
  }
  const positions = flowGroupsCenteredBlock(groups, contentW, displayScale, MIN_FIT_SCALE)
  positions.forEach((pos) => {
    pos.x = Math.min(pos.x, Math.max(0, contentW - pos.w))
    pos.y = Math.min(pos.y, Math.max(0, contentH - pos.h))
  })
  return { positions, fitScale: MIN_FIT_SCALE }
}

function computeSlotRequiredContentWidth(slot: LayoutSlotDef, displayScale: number): number {
  const groups = ensureSlotGroups(slot)
  const unlimitedW = 10000
  const positions = flowGroupsCenteredBlock(groups, unlimitedW, displayScale, 1)
  let maxRight = 0
  positions.forEach((pos) => {
    maxRight = Math.max(maxRight, pos.x + pos.w)
  })
  return Math.max(maxRight + 8 * displayScale, 48 * displayScale)
}

function computeSlotBandHeight(
  slot: LayoutSlotDef,
  slotContentW: number,
  contentH: number,
  displayScale: number,
): number {
  const labelH = SLOT_LABEL_H * displayScale
  const { positions } = layoutSlotGroups(slot, slotContentW, contentH, displayScale)
  let maxBottom = 0
  positions.forEach((pos) => {
    maxBottom = Math.max(maxBottom, pos.y + pos.h)
  })
  return labelH + maxBottom + 8 * displayScale
}

interface SlotMetric {
  slotContentW: number
  bandH: number
  bandW: number
}

function computeSlotMetric(
  slot: LayoutSlotDef,
  availableH: number,
  displayScale: number,
): SlotMetric {
  const bandPad = 8 * displayScale
  const slotContentW = computeSlotRequiredContentWidth(slot, displayScale)
  const bandH = computeSlotBandHeight(slot, slotContentW, availableH, displayScale)
  return { slotContentW, bandH, bandW: slotContentW + bandPad }
}

function snapGrid(value: number, grid: number): number {
  return Math.round(value / grid) * grid
}

function snapSlotPosition(
  x: number,
  y: number,
  w: number,
  h: number,
  contentW: number,
  contentH: number,
  others: Array<{ x: number; y: number; w: number; h: number }>,
  displayScale: number,
): { x: number; y: number } {
  const grid = SLOT_GRID_PX * displayScale
  const threshold = SLOT_ALIGN_THRESHOLD * displayScale
  let sx = snapGrid(x, grid)
  let sy = snapGrid(y, grid)
  sx = Math.max(0, Math.min(sx, Math.max(0, contentW - w)))
  sy = Math.max(0, Math.min(sy, Math.max(0, contentH - h)))

  others.forEach((o) => {
    const xTargets = [o.x, o.x + o.w - w, o.x + (o.w - w) / 2]
    const yTargets = [o.y, o.y + o.h - h, o.y + (o.h - h) / 2]
    xTargets.forEach((tx) => {
      if (Math.abs(sx - tx) <= threshold) sx = tx
    })
    yTargets.forEach((ty) => {
      if (Math.abs(sy - ty) <= threshold) sy = ty
    })
  })

  sx = Math.max(0, Math.min(sx, Math.max(0, contentW - w)))
  sy = Math.max(0, Math.min(sy, Math.max(0, contentH - h)))
  return { x: sx, y: sy }
}

function assignDefaultSlotPositions(slots: LayoutSlotDef[], metrics: SlotMetric[], displayScale: number) {
  const gap = SLOT_GAP * displayScale
  let cursorX = 0
  slots.forEach((slot, idx) => {
    if (slot.layout_x != null && slot.layout_y != null) return
    slot.layout_x = cursorX
    slot.layout_y = 0
    cursorX += metrics[idx].bandW + gap
  })
}

function computeSlotsBoundingBox(
  slots_def: LayoutSlotDef[],
  _frameWidth: number,
  frameHeight: number,
  displayScale: number,
): { maxX: number; maxY: number } {
  const padX = LAYOUT_PAD_X * displayScale
  const padY = LAYOUT_PAD_Y * displayScale
  const header = FRAME_HEADER_PX
  const contentH = Math.max(frameHeight - header - padY * 2, 40 * displayScale)
  const metrics = slots_def.map((slot) => computeSlotMetric(slot, contentH, displayScale))
  assignDefaultSlotPositions(slots_def, metrics, displayScale)
  let maxX = 0
  let maxY = 0
  slots_def.forEach((slot, idx) => {
    const relX = slot.layout_x ?? 0
    const relY = slot.layout_y ?? 0
    maxX = Math.max(maxX, relX + metrics[idx].bandW)
    maxY = Math.max(maxY, relY + metrics[idx].bandH)
  })
  return { maxX: maxX + padX * 2, maxY: maxY + header + padY * 2 }
}

export function computeDeviceContentWidth(
  slots_def: LayoutSlotDef[],
  displayScale: number,
  frameHeight?: number,
): number {
  if (!slots_def.length) return MIN_DEVICE_WIDTH_MM * EDITOR_MM_SCALE
  const estH = frameHeight ?? 120 * displayScale
  const bbox = computeSlotsBoundingBox(slots_def, 10000, estH, displayScale)
  const minPx = MIN_DEVICE_WIDTH_MM * EDITOR_MM_SCALE
  const maxPx = MAX_RACK_WIDTH_MM * EDITOR_MM_SCALE
  return Math.min(maxPx, Math.max(minPx, bbox.maxX + 8 * displayScale))
}

export function computeRequiredFrameWidthPx(slots_def: LayoutSlotDef[], displayScale: number): number {
  return computeDeviceContentWidth(slots_def, displayScale)
}

export function computeRequiredContentHeight(
  frameWidth: number,
  slots_def: LayoutSlotDef[],
  displayScale: number,
): number {
  const bbox = computeSlotsBoundingBox(slots_def, frameWidth, 10000, displayScale)
  return bbox.maxY + LAYOUT_PAD_Y * displayScale
}

export function moveSlotInFrame(
  layout: PortLayout,
  slotIndex: number,
  relX: number,
  relY: number,
) {
  const slots = ensureSlotsDef(layout)
  const slot = slots[slotIndex]
  if (!slot) return
  const displayScale = layoutDisplayScale(layout) || 1
  const padX = LAYOUT_PAD_X * displayScale
  const padY = LAYOUT_PAD_Y * displayScale
  const header = FRAME_HEADER_PX
  const contentW = layout.frame_width - padX * 2
  const contentH = Math.max(layout.frame_height - header - padY * 2, 20)
  const metric = computeSlotMetric(slot, contentH, displayScale)

  const others: Array<{ x: number; y: number; w: number; h: number }> = []
  slots.forEach((s, idx) => {
    if (idx === slotIndex) return
    const m = computeSlotMetric(s, contentH, displayScale)
    others.push({ x: s.layout_x ?? 0, y: s.layout_y ?? 0, w: m.bandW, h: m.bandH })
  })

  const snapped = snapSlotPosition(relX, relY, metric.bandW, metric.bandH, contentW, contentH, others, displayScale)
  slot.layout_x = snapped.x
  slot.layout_y = snapped.y
  ensureFrameFitsSlots(layout)
  autoArrangePortsBySlots(layout)
}

function ensureFrameFitsSlots(layout: PortLayout) {
  const displayScale = layoutDisplayScale(layout) || 1
  const zoom = (frameDisplayScalePercent(layout) || 100) / 100
  const slots = ensureSlotsDef(layout)
  const bbox = computeSlotsBoundingBox(slots, layout.frame_width, layout.frame_height, displayScale)
  const minW = Math.ceil(bbox.maxX)
  if (layout.frame_width < minW) {
    layout.frame_width = minW
    layout.rack_width_mm = Math.max(MIN_DEVICE_WIDTH_MM, Math.round(minW / EDITOR_MM_SCALE / zoom))
  }
  const minH = Math.ceil(bbox.maxY)
  if (layout.frame_height < minH) {
    layout.frame_height = minH
    const contentH = minH - FRAME_HEADER_PX
    layout.height_u = Math.max(
      layout.height_u ?? 1,
      Math.ceil(contentH / (U_HEIGHT_MM * EDITOR_MM_SCALE * zoom)),
    )
  }
}

export function computeSlotPlans(
  _frameWidth: number,
  frameHeight: number,
  slots_def: LayoutSlotDef[],
  displayScale = 1,
): {
  bands: SlotBandLayout[]
  groupLayouts: GroupVisualLayout[]
  portPositions: Map<string, { x: number; y: number; w: number; h: number }>
} {
  const padX = LAYOUT_PAD_X * displayScale
  const padY = LAYOUT_PAD_Y * displayScale
  const header = FRAME_HEADER_PX
  const contentOriginX = padX
  const contentOriginY = header + padY
  const contentAreaH = Math.max(frameHeight - header - padY * 2, 20)

  const metrics = slots_def.map((slot) => computeSlotMetric(slot, contentAreaH, displayScale))
  assignDefaultSlotPositions(slots_def, metrics, displayScale)

  const bands: SlotBandLayout[] = []
  const groupLayouts: GroupVisualLayout[] = []
  const portPositions = new Map<string, { x: number; y: number; w: number; h: number }>()

  slots_def.forEach((slot, idx) => {
    const groups = ensureSlotGroups(slot)
    const labelH = SLOT_LABEL_H * displayScale
    const { slotContentW, bandH, bandW } = metrics[idx]
    const relX = slot.layout_x ?? 0
    const relY = slot.layout_y ?? 0
    const bandX = contentOriginX + relX
    const bandY = contentOriginY + relY
    const contentY = bandY + labelH
    const contentH = Math.max(bandH - labelH - 4 * displayScale, 20 * displayScale)

    bands.push({
      slotIndex: idx + 1,
      label: slotBandLabel(slot, idx),
      x: bandX,
      y: bandY,
      w: bandW,
      h: bandH,
      contentY,
      contentH,
      contentW: slotContentW,
    })

    const { positions: groupPos } = layoutSlotGroups(slot, slotContentW, contentH, displayScale)
    const innerPadX = bandX + 4 * displayScale

    groups.forEach((group) => {
      const pos = groupPos.get(group.id)
      if (!pos) return
      const grid = pos.grid
      const gx = innerPadX + pos.x
      const gy = contentY + pos.y

      groupLayouts.push({
        groupId: group.id,
        slotIndex: idx + 1,
        portType: group.port_type,
        label: groupDisplayLabel(group),
        x: gx,
        y: gy - GROUP_LABEL_H * displayScale * 0.5,
        w: grid.w,
        h: grid.h,
        cols: grid.cols,
        rows: grid.rows,
      })

      const innerPad = GROUP_INNER_PAD * displayScale * 0.5
      const labelOffset = GROUP_LABEL_H * displayScale
      const innerX = gx + innerPad
      const innerY = gy + labelOffset
      const portsAreaW = grid.w - innerPad * 2

      for (let p = 0; p < group.count; p += 1) {
        const row = Math.floor(p / grid.cols)
        const col = p % grid.cols
        const portsInRow = Math.min(grid.cols, group.count - row * grid.cols)
        const rowWidth = portsInRow * grid.portW + (portsInRow - 1) * grid.gap
        const rowStartX = innerX + (portsAreaW - rowWidth) / 2
        const portId = `slot${idx + 1}-g${group.id}-p${p + 1}`
        portPositions.set(portId, {
          x: rowStartX + col * (grid.portW + grid.gap),
          y: innerY + row * (grid.portH + grid.gap),
          w: grid.portW,
          h: grid.portH,
        })
      }
    })
  })

  return { bands, groupLayouts, portPositions }
}

export function autoAdjustDeviceFrame(layout: PortLayout) {
  if (layout.switch_subtype) {
    layoutSwitchFrontPanel(layout)
    return
  }
  if (layout.server_form_factor != null) {
    if (layout.server_panel_side === 'front') {
      layoutServerFrontPanel(layout)
    } else {
      layoutServerRearPanel(layout)
    }
    return
  }
  // 安全设备：禁止用通用 U 拟合覆盖用户选择的 1U/2U 高度
  if (layout.security_panel || (layout.slots_def || []).some((s) => s.zone_label)) {
    layout.security_panel = true
    layoutSecurityFrontPanel(layout)
    return
  }
  const slots_def = ensureSlotsDef(layout)
  const zoom = (frameDisplayScalePercent(layout) || 100) / 100

  let rackW = Math.round(computeDeviceContentWidth(slots_def, 1) / EDITOR_MM_SCALE)
  rackW = Math.max(MIN_DEVICE_WIDTH_MM, Math.min(MAX_RACK_WIDTH_MM, rackW))

  let frameWidthPx = rackW * EDITOR_MM_SCALE * zoom
  let heightU = 1
  let fitted = false

  for (let attempt = 0; attempt < 24 && !fitted; attempt += 1) {
    frameWidthPx = rackW * EDITOR_MM_SCALE * zoom
    for (heightU = 1; heightU <= MAX_HEIGHT_U; heightU += 1) {
      const contentH = U_HEIGHT_MM * heightU * EDITOR_MM_SCALE * zoom
      const frameHeightPx = FRAME_HEADER_PX + contentH
      const required = computeRequiredContentHeight(frameWidthPx, slots_def, zoom)
      const available = frameHeightPx - FRAME_HEADER_PX
      if (required <= available) {
        fitted = true
        layout.rack_width_mm = rackW
        layout.height_u = heightU
        layout.frame_width = Math.round(frameWidthPx * 100) / 100
        layout.frame_height = Math.round(frameHeightPx * 100) / 100
        break
      }
    }
    if (fitted) break
    if (rackW >= MAX_RACK_WIDTH_MM) {
      heightU = MAX_HEIGHT_U
      const contentH = U_HEIGHT_MM * heightU * EDITOR_MM_SCALE * zoom
      layout.rack_width_mm = rackW
      layout.height_u = heightU
      layout.frame_width = Math.round(rackW * EDITOR_MM_SCALE * zoom * 100) / 100
      layout.frame_height = Math.round((FRAME_HEADER_PX + contentH) * 100) / 100
      break
    }
    rackW = Math.min(MAX_RACK_WIDTH_MM, rackW + 50)
  }

  autoArrangePortsBySlots(layout)
}

export function reorderGroupInSlot(
  layout: PortLayout,
  slotIndex: number,
  groupId: string,
  dragCenterY: number,
) {
  const slot = ensureSlotsDef(layout)[slotIndex]
  if (!slot) return
  const currentLayouts = computeSlotPlans(
    layout.frame_width,
    layout.frame_height,
    ensureSlotsDef(layout),
    layoutDisplayScale(layout),
  ).groupLayouts.filter((g) => g.slotIndex === slotIndex + 1)

  let insertAt = 0
  currentLayouts.forEach((gl) => {
    if (gl.groupId === groupId) return
    const centerY = gl.y + gl.h / 2
    if (dragCenterY > centerY) insertAt += 1
  })

  const groups = sortedGroups(ensureSlotGroups(slot))
  const fromIdx = groups.findIndex((g) => g.id === groupId)
  if (fromIdx < 0) return
  const reordered = [...groups]
  const [item] = reordered.splice(fromIdx, 1)
  insertAt = Math.max(0, Math.min(insertAt, reordered.length))
  reordered.splice(insertAt, 0, item)
  slot.groups = reordered
  reordered.forEach((g, i) => {
    g.layout_order = i
    g.layout_x = null
    g.layout_y = null
  })
  autoArrangePortsBySlots(layout)
}

/** @deprecated use reorderGroupInSlot */
export function moveGroupInSlot(
  layout: PortLayout,
  slotIndex: number,
  groupId: string,
  _layoutX: number,
  layoutY: number,
) {
  reorderGroupInSlot(layout, slotIndex, groupId, layoutY)
}

export function normalizePortLayout(layout: PortLayout): PortLayout {
  ensureSlotsDef(layout)
  layout.ports.forEach((port) => {
    if (!port.port_type) port.port_type = '1g'
    if (port.group_id == null) {
      const m = /^slot\d+-g([^-]+)-/.exec(port.id)
      if (m) port.group_id = m[1]
    }
    if (port.slot_index == null && port.id.startsWith('slot')) {
      const m = /^slot(\d+)-/.exec(port.id)
      if (m) port.slot_index = parseInt(m[1], 10)
    }
    // 后端 FramePort 约束：w∈[8,120] h∈[8,60]
    if (port.w != null) port.w = Math.max(8, Math.min(120, port.w))
    if (port.h != null) port.h = Math.max(8, Math.min(60, port.h))
  })

  // 后端 rack_width_mm ≤ 1200；示意图素尺寸不可直接换算为 mm
  if (layout.rack_width_mm != null && layout.rack_width_mm > MAX_RACK_WIDTH_MM) {
    layout.rack_width_mm = MAX_RACK_WIDTH_MM
  }
  if (layout.rack_width_mm != null && layout.rack_width_mm < MIN_DEVICE_WIDTH_MM) {
    layout.rack_width_mm = MIN_DEVICE_WIDTH_MM
  }

  if (layout.rack_width_mm != null && layout.height_u != null) {
    return layout
  }

  const rackWidthMm = layout.rack_width_mm ?? RACK_WIDTH_MM
  const heightU = layout.height_u ?? 1
  const target = deviceFramePixels(rackWidthMm, heightU)
  const oldW = layout.frame_width || target.frame_width
  const oldH = layout.frame_height || target.frame_height
  const scaleX = target.frame_width / oldW
  const oldContentH = Math.max(oldH - FRAME_HEADER_PX, 1)
  const targetContentH = target.frame_height - FRAME_HEADER_PX
  const scaleY = targetContentH / oldContentH

  layout.ports.forEach((port) => {
    port.x *= scaleX
    port.y = FRAME_HEADER_PX + Math.max(0, port.y - FRAME_HEADER_PX) * scaleY
    port.w *= scaleX
    port.h *= scaleY
  })

  layout.frame_width = target.frame_width
  layout.frame_height = target.frame_height
  layout.rack_width_mm = rackWidthMm
  layout.height_u = heightU
  return layout
}

export function applyProportionalScale(layout: PortLayout, scale: number) {
  if (scale <= 0 || scale === 1) return
  const oldW = layout.frame_width
  const oldH = layout.frame_height
  const oldContentH = Math.max(oldH - FRAME_HEADER_PX, 1)
  layout.ports.forEach((port) => {
    port.x *= scale
    port.y = FRAME_HEADER_PX + Math.max(0, port.y - FRAME_HEADER_PX) * scale
    port.w *= scale
    port.h *= scale
  })
  layout.frame_width = oldW * scale
  layout.frame_height = FRAME_HEADER_PX + oldContentH * scale
  ensureSlotsDef(layout).forEach((slot) => {
    if (slot.layout_x != null) slot.layout_x *= scale
    if (slot.layout_y != null) slot.layout_y *= scale
    slot.groups.forEach((g) => {
      if (g.layout_x != null) g.layout_x *= scale
      if (g.layout_y != null) g.layout_y *= scale
    })
  })
}

export function frameDisplayScalePercent(layout: PortLayout): number {
  const rackWidthMm = layout.rack_width_mm ?? RACK_WIDTH_MM
  const heightU = layout.height_u ?? 1
  const base = deviceFramePixels(rackWidthMm, heightU)
  return Math.round((layout.frame_width / base.frame_width) * 100)
}

export function setFrameDisplayScale(layout: PortLayout, percent: number) {
  const rackWidthMm = layout.rack_width_mm ?? RACK_WIDTH_MM
  const heightU = layout.height_u ?? 1
  const base = deviceFramePixels(rackWidthMm, heightU)
  const targetScale = percent / 100
  const currentScale = layout.frame_width / base.frame_width
  if (currentScale <= 0) return
  applyProportionalScale(layout, targetScale / currentScale)
  autoArrangePortsBySlots(layout)
}

export function applyHeightU(layout: PortLayout, heightU: number) {
  const zoom = (frameDisplayScalePercent(layout) || 100) / 100
  const prevWidth = layout.frame_width
  layout.height_u = Math.max(1, Math.min(MAX_HEIGHT_U, heightU))
  const contentH = U_HEIGHT_MM * layout.height_u * EDITOR_MM_SCALE * zoom
  layout.frame_height = Math.round((FRAME_HEADER_PX + contentH) * 100) / 100
  layout.frame_width = prevWidth
  autoArrangePortsBySlots(layout)
}

export function portLabel(type: PortType, _slotIndex: number, portIndex: number, role?: SlotInterfaceGroup['role']) {
  if (role === 'uplink') return `U${portIndex}`
  if (role === 'main' || role === 'card') return String(portIndex)
  return `${PORT_TYPE_SHORT[type]}${portIndex}`
}

export function syncPortsFromSlotsDef(layout: PortLayout, preservePeers = true) {
  const slots_def = ensureSlotsDef(layout)
  const peerMap = new Map<
    string,
    Pick<
      PortLayout['ports'][0],
      | 'peer_node_id'
      | 'peer_port'
      | 'peer_label'
      | 'peer_device_id'
      | 'peer_device_name'
      | 'label'
    >
  >()
  if (preservePeers) {
    layout.ports.forEach((p) => {
      peerMap.set(p.id, {
        peer_node_id: p.peer_node_id,
        peer_port: p.peer_port,
        peer_label: p.peer_label,
        peer_device_id: p.peer_device_id ?? null,
        peer_device_name: p.peer_device_name ?? null,
        label: p.label,
      })
      if (p.group_id) {
        const legacyMatch = /^slot(\d+)-p(\d+)$/.exec(p.id)
        if (legacyMatch) {
          peerMap.set(`slot${legacyMatch[1]}-legacy-p${legacyMatch[2]}`, {
            peer_node_id: p.peer_node_id,
            peer_port: p.peer_port,
            peer_label: p.peer_label,
            peer_device_id: p.peer_device_id ?? null,
            peer_device_name: p.peer_device_name ?? null,
            label: p.label,
          })
        }
      }
    })
  }

  const ports: PortLayout['ports'] = []
  slots_def.forEach((slot, slotIdx) => {
    if (slot.server_slot_kind === 'raid' || slot.server_slot_kind === 'blank') return
    let mainSeq = 0
    slot.groups.forEach((group) => {
      for (let p = 1; p <= group.count; p += 1) {
        if (group.role === 'main') mainSeq += 1
        const displayIndex = group.role === 'main' ? mainSeq : p
        const id = `slot${slotIdx + 1}-g${group.id}-p${p}`
        const legacyId = `slot${slotIdx + 1}-p${mainSeq || p}`
        const peer = peerMap.get(id) ?? peerMap.get(legacyId)
        ports.push({
          id,
          label: peer?.label || portLabel(group.port_type, slotIdx + 1, displayIndex, group.role),
          x: 0,
          y: 0,
          w: 0,
          h: 0,
          port_type: group.port_type,
          slot_index: slotIdx + 1,
          group_id: group.id,
          peer_node_id: peer?.peer_node_id ?? null,
          peer_port: peer?.peer_port ?? null,
          peer_label: peer?.peer_label ?? null,
          peer_device_id: peer?.peer_device_id ?? null,
          peer_device_name: peer?.peer_device_name ?? null,
        })
      }
    })
  })
  const onboardExisting = (layout.ports || []).filter((p) => p.slot_index === 0)
  layout.ports = [...onboardExisting, ...ports]
  slots_def.forEach((slot) => {
    if (slot.server_slot_kind !== 'raid' && slot.server_slot_kind !== 'blank') {
      normalizeGroupOrders(slot)
    }
  })
  autoAdjustDeviceFrame(layout)
}

/** @deprecated use syncPortsFromSlotsDef */
export function generatePortsFromSlotsDef(layout: PortLayout, preservePeers = true) {
  syncPortsFromSlotsDef(layout, preservePeers)
}

export function applySecurityLayoutConfig(
  layout: PortLayout,
  opts: { heightU?: number; zones?: SecurityZoneInput[]; preservePeers?: boolean } = {},
) {
  layout.security_panel = true
  const heightU = normalizeSecurityHeightU(opts.heightU ?? layout.height_u ?? 1)
  layout.height_u = heightU
  if (opts.zones?.length) {
    layout.slots_def = buildSecuritySlotsDef(opts.zones)
  } else if (!layout.slots_def?.length) {
    layout.slots_def = buildSecuritySlotsDef(defaultSecurityZones())
  }
  layout.slot_count = layout.slots_def.length
  // 先标记 security_panel，避免 syncPorts → autoAdjust 把高度压回 1U
  syncPortsFromSlotsDef(layout, opts.preservePeers !== false)
  // 再次锁定高度并生成面板（防止中间步骤改写）
  layout.height_u = heightU
  layout.security_panel = true
  layoutSecurityFrontPanel(layout)
}

export function autoArrangePortsBySlots(layout: PortLayout) {
  if (layout.switch_subtype) {
    layoutSwitchFrontPanel(layout)
    return
  }
  if (layout.server_form_factor != null || (layout.slots_def || []).some((s) => s.server_slot_kind)) {
    if (layout.server_form_factor == null) layout.server_form_factor = 1
    if (layout.server_panel_side === 'front') {
      layoutServerFrontPanel(layout)
    } else {
      layoutServerRearPanel(layout)
    }
    return
  }
  if (layout.security_panel || (layout.slots_def || []).some((s) => s.zone_label)) {
    layout.security_panel = true
    layoutSecurityFrontPanel(layout)
    return
  }
  const slots_def = ensureSlotsDef(layout)
  const displayScale = layoutDisplayScale(layout)
  const { portPositions } = computeSlotPlans(
    layout.frame_width,
    layout.frame_height,
    slots_def,
    displayScale,
  )

  layout.ports.forEach((port) => {
    const pos = portPositions.get(port.id)
    if (!pos) return
    port.x = pos.x
    port.y = pos.y
    port.w = pos.w
    port.h = pos.h
    if (!port.label || /^[A-Za-z]+\d+$/.test(port.label)) {
      const portNum = parseInt(/-p(\d+)$/.exec(port.id)?.[1] || '1', 10)
      port.label = portLabel(port.port_type || '1g', port.slot_index ?? 1, portNum)
    }
  })
}

export function slotBandRects(layout: PortLayout): SlotBandLayout[] {
  const slots_def = ensureSlotsDef(layout)
  const displayScale = layoutDisplayScale(layout)
  return computeSlotPlans(layout.frame_width, layout.frame_height, slots_def, displayScale).bands
}

export function groupVisualLayouts(layout: PortLayout): GroupVisualLayout[] {
  const slots_def = ensureSlotsDef(layout)
  const displayScale = layoutDisplayScale(layout)
  return computeSlotPlans(layout.frame_width, layout.frame_height, slots_def, displayScale).groupLayouts
}

export function ensurePortLayout(node: NetworkNode): PortLayout {
  if (node.port_layout) {
    const layout = normalizePortLayout({
      ...node.port_layout,
      ports: (node.port_layout.ports || []).map((p) => ({
        ...p,
        port_type: p.port_type || ('1g' as PortType),
        slot_index: p.slot_index ?? null,
        group_id: p.group_id ?? null,
      })),
    })
    // 写回节点，避免浅拷贝导致后续编辑丢失
    node.port_layout = layout
    if (node.kind === 'security') {
      applySecurityLayoutConfig(layout, {
        heightU: layout.height_u,
        preservePeers: true,
      })
      return layout
    }
    if (!layout.ports.length && layout.slots_def?.length) {
      syncPortsFromSlotsDef(layout, false)
    } else if (layout.ports.length) {
      autoArrangePortsBySlots(layout)
    }
    return layout
  }
  return migrateLegacyToPortLayout(node)
}

export function migrateLegacyToPortLayout(node: NetworkNode): PortLayout {
  const heightU = 1
  const layout = defaultPortLayout(node.kind, RACK_WIDTH_MM, heightU)

  if (node.kind === 'switch') {
    const count = node.switch_port_count || 48
    layout.slots_def = [{ groups: [newInterfaceGroup('1g', count)] }]
    layout.slot_count = 1
  } else {
    const legacy = node.slots || defaultSlots()
    layout.slots_def = legacy
      .map((s, i) => ({ slot: s, index: i }))
      .filter(({ slot }) => slot.enabled)
      .map(({ slot, index }) => {
        const defaultType = (index === legacy.filter((x) => x.enabled).length - 1 ? 'bmc' : '10g') as PortType
        return { groups: [newInterfaceGroup(defaultType, slot.port_count)] }
      })
    if (!layout.slots_def.length) {
      layout.slots_def = defaultSlotsDef(node.kind)
    }
    layout.slot_count = layout.slots_def.length
  }

  syncPortsFromSlotsDef(layout, false)
  return layout
}

export function syncLegacyFromPortLayout(node: NetworkNode) {
  const layout = node.port_layout
  if (!layout) return

  if (layout.slots_def?.length) {
    const slots: SlotConfig[] = defaultSlots()
    layout.slots_def.forEach((def, idx) => {
      if (idx >= 8) return
      migrateSlotToGroups(def)
      const count = slotPortCount(def)
      if (count <= 0) {
        slots[idx] = { enabled: false, port_count: 1 }
      } else {
        slots[idx] = { enabled: true, port_count: Math.max(1, Math.min(128, count)) }
      }
    })
    node.slots = slots
    if (node.kind === 'switch') {
      node.switch_port_count = Math.max(
        1,
        Math.min(
          128,
          layout.slots_def.reduce((sum, s) => sum + slotPortCount(migrateSlotToGroups(s)), 0),
        ),
      )
    }
    return
  }

  if (!layout.ports?.length) return
  if (node.kind === 'switch') {
    node.switch_port_count = Math.max(layout.ports.length, 1)
    node.slots = null
    return
  }
  const slots: SlotConfig[] = defaultSlots()
  layout.ports.forEach((p) => {
    const match = /^slot(\d+)-/.exec(p.id)
    if (!match) return
    const idx = parseInt(match[1], 10) - 1
    if (idx < 0 || idx >= 8) return
    slots[idx].enabled = true
    slots[idx].port_count = layout.ports.filter((x) => x.slot_index === idx + 1).length
  })
  node.slots = slots
}

export function inferLinkType(source: NetworkNode, target: NetworkNode): NetworkLinkType {
  const kinds = new Set([source.kind, target.kind])
  if (kinds.has('switch') && kinds.has('server')) return 'switch_server'
  if (kinds.has('switch') && kinds.has('security')) return 'switch_security'
  return 'switch_switch'
}

export function syncLinksFromPortLayout(nodes: NetworkNode[], links: NetworkLink[]) {
  const nodeMap = new Map(nodes.map((n) => [n.id, n]))
  const deviceNodeMap = new Map<string, NetworkNode>()
  for (const n of nodes) {
    if (n.device_id) deviceNodeMap.set(n.device_id, n)
  }

  for (const node of nodes) {
    const layout = node.port_layout
    if (!layout) continue
    for (const port of layout.ports) {
      let peerNodeId = port.peer_node_id
      let peerPort = port.peer_port
      if ((!peerNodeId || !peerPort) && port.peer_device_id && port.peer_port) {
        const bound = deviceNodeMap.get(port.peer_device_id)
        if (bound) {
          peerNodeId = bound.id
          peerPort = port.peer_port
          // 回填 node 对端，便于拓扑连线与后续编辑
          port.peer_node_id = bound.id
        } else {
          continue
        }
      }
      if (!peerNodeId || !peerPort) continue
      const peer = nodeMap.get(peerNodeId)
      if (!peer) continue
      const existing = links.find(
        (l) =>
          (l.source_node_id === node.id
            && l.source_port === port.id
            && l.target_node_id === peerNodeId
            && l.target_port === peerPort)
          || (l.target_node_id === node.id
            && l.target_port === port.id
            && l.source_node_id === peerNodeId
            && l.source_port === peerPort),
      )
      if (existing) {
        existing.label = port.peer_label
      } else {
        links.push({
          id: crypto.randomUUID(),
          topology_id: node.topology_id,
          link_type: inferLinkType(node, peer),
          source_node_id: node.id,
          source_port: port.id,
          target_node_id: peerNodeId,
          target_port: peerPort,
          label: port.peer_label,
        })
      }
    }
  }
}

export function formatFrameSizeLabel(layout: PortLayout): string {
  const widthMm = layout.rack_width_mm ?? Math.round(layout.frame_width / EDITOR_MM_SCALE)
  const heightU = layout.height_u ?? 1
  return `${widthMm}mm × ${heightU}U`
}

export function formatDeviceFrameLabel(layout: PortLayout): string {
  return `设备框架 ${formatFrameSizeLabel(layout)}`
}

export { PORT_TYPE_WEIGHT }
