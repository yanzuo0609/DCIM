import type {
  CoreLineCard,
  FramePort,
  PortLayout,
  PortType,
  SwitchSubtype,
  UplinkPosition,
} from '@/api/network'
import {
  CORE_CARD_TYPE_LABELS,
  SWITCH_SUBTYPE_LABELS,
  newCoreLineCard,
} from '@/api/network'

export const PANEL_EAR = 14
export const PANEL_PAD = 8
export const PANEL_MGMT_W = 88
export const ACCESS_PANEL_H = 78
export const CORE_HEADER_H = 28
export const CORE_CARD_H = 72
export const CORE_CARD_GAP = 6

export interface PanelZone {
  id: string
  kind: 'mgmt' | 'main' | 'uplink' | 'card'
  label: string
  x: number
  y: number
  w: number
  h: number
  cardIndex?: number
  /** 空白板卡（无接口） */
  blank?: boolean
}

export interface SwitchPanelView {
  subtype: SwitchSubtype
  title: string
  modelHint: string
  frameWidth: number
  frameHeight: number
  zones: PanelZone[]
  uplinkPosition: UplinkPosition | null
}

function portBox(type: PortType): { w: number; h: number } {
  // 1U 交换机简图：方口（与面板示意图一致）
  if (type === '40_100g') return { w: 14, h: 14 }
  if (type === '10g') return { w: 12, h: 12 }
  return { w: 11, h: 11 }
}

function measureTwoRowBlockWidth(ports: FramePort[]): number {
  if (!ports.length) return 0
  const type = ports[0].port_type || '1g'
  const { w } = portBox(type)
  const cols = Math.max(1, Math.ceil(ports.length / 2))
  return cols * w
}

/**
 * 业务接口板双排口标签：与交换机前面板相同，列向填充（先上后下再下一列）。
 * 从 start（默认 0）起编：上排偶数 0,2,4… / 下排奇数 1,3,5…
 */
export function ifaceBoardTwoRowLabels(count: number, start = 0): string[] {
  const n = Math.max(0, Math.min(128, Math.trunc(count) || 0))
  const s = Math.max(0, Math.trunc(start) || 0)
  return Array.from({ length: n }, (_, i) => String(s + i))
}

/**
 * 1U 交换机双排：列向编号（上奇下偶）
 * 例：上 1 3 5 … / 下 2 4 6 …
 */
function placeTwoRowBlock(
  ports: FramePort[],
  originX: number,
  originY: number,
  areaH: number,
  targetWidth?: number,
): { width: number; height: number } {
  if (!ports.length) return { width: 0, height: 0 }
  const type = ports[0].port_type || '1g'
  const { w: size } = portBox(type)
  const cols = Math.max(1, Math.ceil(ports.length / 2))
  const rows = ports.length <= 1 ? 1 : 2
  const blockH = rows * size
  const naturalW = cols * size
  const spanW = Math.max(targetWidth ?? naturalW, size)
  const startY = originY + Math.max(0, (areaH - blockH) / 2)

  const colX: number[] = []
  if (cols === 1) {
    colX.push(originX)
  } else if (spanW <= naturalW + 0.5) {
    for (let c = 0; c < cols; c += 1) colX.push(originX + c * size)
  } else {
    // 拉伸到目标宽时仍保持列均匀，口本身保持方形紧贴感
    const travel = Math.max(0, spanW - size)
    for (let c = 0; c < cols; c += 1) {
      colX.push(originX + (travel * c) / (cols - 1))
    }
  }

  ports.forEach((port, i) => {
    const col = Math.floor(i / 2)
    const row = i % 2
    port.x = colX[Math.min(col, colX.length - 1)]
    port.y = startY + row * size
    port.w = size
    port.h = size
    port.label = String(i + 1)
  })

  return { width: spanW, height: blockH }
}

function placeUplinkBlock(
  ports: FramePort[],
  originX: number,
  originY: number,
  areaH: number,
  _subtype: SwitchSubtype,
): { width: number; height: number; label: string } {
  if (!ports.length) return { width: 0, height: 0, label: '' }
  const type = ports[0].port_type || '10g'
  const { w: size } = portBox(type)
  const count = ports.length
  const label =
    type === '40_100g' ? `${count} × 10G/40G QSFP+` : `${count} × 1G/10G SFP+`

  // 上联也按双排列向奇偶（与主口同一套 1U 样式）；口数=1 时单口
  const rows = count <= 1 ? 1 : 2
  const cols = Math.max(1, Math.ceil(count / rows))
  const width = cols * size
  const height = rows * size
  const startY = originY + Math.max(0, (areaH - height) / 2)
  ports.forEach((port, i) => {
    const col = Math.floor(i / rows)
    const row = i % rows
    port.x = originX + col * size
    port.y = startY + row * size
    port.w = size
    port.h = size
    port.label = String(i + 1)
  })
  return { width, height, label }
}

/** 千兆上联合法数量：0–4 任意；6/8（>4 须偶数） */
const GIGABIT_UPLINK_ALLOWED = [0, 1, 2, 3, 4, 6, 8] as const

/**
 * 千兆上联：0–8；大于 4 时必须为偶数。
 * @param previous 变更前的值，用于加号/减号时跳到相邻合法数（避免 4→5→4 卡死）
 */
export function normalizeGigabitUplinkCount(count: number, previous?: number): number {
  const raw = Math.max(0, Math.min(8, Math.round(Number(count))))
  if ((GIGABIT_UPLINK_ALLOWED as readonly number[]).includes(raw)) return raw
  const prev = previous ?? raw
  if (raw > prev) {
    // 加号：升到下一个合法值（4→5→6）
    return GIGABIT_UPLINK_ALLOWED.find((a) => a >= raw) ?? 8
  }
  // 减号：降到上一个合法值（6→5→4）
  for (let i = GIGABIT_UPLINK_ALLOWED.length - 1; i >= 0; i -= 1) {
    if (GIGABIT_UPLINK_ALLOWED[i] <= raw) return GIGABIT_UPLINK_ALLOWED[i]
  }
  return 0
}

/** 万兆 40/100G 上联：0–8，必须为偶数（两排向后扩展） */
export function normalizeTenGigabitUplinkCount(count: number, previous?: number): number {
  let n = Math.max(0, Math.min(8, Math.round(Number(count))))
  if (n === 0) return 0
  if (n % 2 === 0) return n
  const prev = previous ?? n
  // 奇数时按增减方向取偶，避免卡在非法值
  if (n > prev) return Math.min(8, n + 1)
  return Math.max(0, n - 1)
}

function groupRoleMap(layout: PortLayout): Map<string, string> {
  const map = new Map<string, string>()
  ;(layout.slots_def || []).forEach((slot) => {
    ;(slot.groups || []).forEach((g) => {
      if (g.role) map.set(g.id, g.role)
    })
  })
  return map
}

function collectRolePorts(layout: PortLayout, role: string): FramePort[] {
  const roles = groupRoleMap(layout)
  return layout.ports.filter((p) => p.group_id && roles.get(p.group_id) === role)
}

function collectCardPorts(layout: PortLayout, cardIndex: number): FramePort[] {
  const slot = layout.slots_def?.[cardIndex]
  if (!slot) return []
  const ids = new Set((slot.groups || []).map((g) => g.id))
  return layout.ports.filter((p) => p.group_id && ids.has(p.group_id))
}

function modelHint(subtype: SwitchSubtype): string {
  if (subtype === 'gigabit') return 'Gigabit Switch'
  if (subtype === 'ten_gigabit') return '10 Gigabit Switch'
  if (subtype === 'aggregation') return 'Aggregation Switch'
  return 'Core Chassis'
}

export function layoutSwitchFrontPanel(layout: PortLayout): SwitchPanelView {
  const subtype = layout.switch_subtype ?? 'gigabit'
  if (subtype === 'core') {
    return layoutCoreChassis(layout, layout.line_cards ?? [])
  }
  return layoutAccessPanel(layout, subtype, layout.uplink_position ?? 'right')
}

function layoutAccessPanel(
  layout: PortLayout,
  subtype: SwitchSubtype,
  uplinkPosition: UplinkPosition,
): SwitchPanelView {
  const contentY = PANEL_PAD
  const contentH = ACCESS_PANEL_H - PANEL_PAD * 2
  const zones: PanelZone[] = []

  zones.push({
    id: 'mgmt',
    kind: 'mgmt',
    label: 'MGMT',
    x: PANEL_PAD,
    y: contentY,
    w: PANEL_MGMT_W,
    h: contentH,
  })

  let cursorX = PANEL_PAD + PANEL_MGMT_W + 10
  const mainPorts = collectRolePorts(layout, 'main')
  const uplinkPorts = collectRolePorts(layout, 'uplink')
  const zoneGap = 14

  if (uplinkPosition === 'middle' && uplinkPorts.length && mainPorts.length) {
    const half = Math.ceil(mainPorts.length / 2)
    const leftPorts = mainPorts.slice(0, half)
    const rightPorts = mainPorts.slice(half)

    const left = placeTwoRowBlock(leftPorts, cursorX, contentY, contentH)
    zones.push({
      id: 'main-left',
      kind: 'main',
      label: subtype === 'gigabit' ? 'Copper' : 'SFP+',
      x: cursorX,
      y: contentY,
      w: left.width,
      h: contentH,
    })
    cursorX += left.width + zoneGap

    const up = placeUplinkBlock(uplinkPorts, cursorX, contentY, contentH, subtype)
    zones.push({
      id: 'uplink',
      kind: 'uplink',
      label: up.label,
      x: cursorX,
      y: contentY,
      w: Math.max(up.width, 56),
      h: contentH,
    })
    cursorX += Math.max(up.width, 56) + zoneGap

    const right = placeTwoRowBlock(rightPorts, cursorX, contentY, contentH)
    rightPorts.forEach((p, i) => {
      p.label = String(half + i + 1)
    })
    zones.push({
      id: 'main-right',
      kind: 'main',
      label: subtype === 'gigabit' ? 'Copper' : 'SFP+',
      x: cursorX,
      y: contentY,
      w: right.width,
      h: contentH,
    })
    cursorX += right.width
  } else {
    const main = placeTwoRowBlock(mainPorts, cursorX, contentY, contentH)
    zones.push({
      id: 'main',
      kind: 'main',
      label: subtype === 'gigabit' ? 'Copper' : 'SFP+',
      x: cursorX,
      y: contentY,
      w: main.width,
      h: contentH,
    })
    cursorX += main.width + zoneGap

    if (uplinkPorts.length) {
      const up = placeUplinkBlock(uplinkPorts, cursorX, contentY, contentH, subtype)
      zones.push({
        id: 'uplink',
        kind: 'uplink',
        label: up.label,
        x: cursorX,
        y: contentY,
        w: Math.max(up.width, 56),
        h: contentH,
      })
      cursorX += Math.max(up.width, 56)
    }
  }

  const frameWidth = Math.max(420, Math.ceil(cursorX + PANEL_PAD))
  const frameHeight = ACCESS_PANEL_H
  layout.frame_width = frameWidth
  layout.frame_height = frameHeight
  layout.height_u = 1
  layout.rack_width_mm = Math.round(frameWidth / 0.6)

  return {
    subtype,
    title: SWITCH_SUBTYPE_LABELS[subtype],
    modelHint: modelHint(subtype),
    frameWidth,
    frameHeight,
    zones,
    uplinkPosition,
  }
}

function layoutCoreChassis(layout: PortLayout, cards: CoreLineCard[]): SwitchPanelView {
  const list = cards.length ? cards : [newCoreLineCard()]
  const zones: PanelZone[] = []
  const labelW = 72
  const portsOriginX = PANEL_PAD + labelW + 8
  const portsRightPad = 12

  // 以所有板卡中最宽的自然布局为共享接口区宽度，保证左右两端对齐
  const naturalWidths = list.map((_, idx) => measureTwoRowBlockWidth(collectCardPorts(layout, idx)))
  const sharedPortWidth = Math.max(240, ...naturalWidths)
  const frameWidth = Math.max(480, Math.ceil(portsOriginX + sharedPortWidth + portsRightPad + PANEL_PAD))
  const cardZoneW = frameWidth - PANEL_PAD * 2

  list.forEach((card, idx) => {
    const y = CORE_HEADER_H + PANEL_PAD + idx * (CORE_CARD_H + CORE_CARD_GAP)
    const isBlank = card.card_type === 'blank'
    const cardPorts = isBlank ? [] : collectCardPorts(layout, idx)
    if (!isBlank) {
      placeTwoRowBlock(cardPorts, portsOriginX, y + 4, CORE_CARD_H - 8, sharedPortWidth)
      cardPorts.forEach((p, i) => {
        p.label = String(i + 1)
      })
    }
    zones.push({
      id: `card-${idx}`,
      kind: 'card',
      label: `Slot ${idx + 1} · ${CORE_CARD_TYPE_LABELS[card.card_type]}`,
      x: PANEL_PAD,
      y,
      w: cardZoneW,
      h: CORE_CARD_H,
      cardIndex: idx,
      blank: isBlank,
    })
  })

  const frameHeight = Math.ceil(
    CORE_HEADER_H + PANEL_PAD * 2 + list.length * CORE_CARD_H + Math.max(0, list.length - 1) * CORE_CARD_GAP,
  )

  layout.frame_width = frameWidth
  layout.frame_height = frameHeight
  layout.height_u = Math.max(1, list.length)
  layout.rack_width_mm = Math.round(frameWidth / 0.6)

  return {
    subtype: 'core',
    title: SWITCH_SUBTYPE_LABELS.core,
    modelHint: modelHint('core'),
    frameWidth,
    frameHeight,
    zones,
    uplinkPosition: null,
  }
}

export function getSwitchPanelView(layout: PortLayout): SwitchPanelView {
  if (!layout.switch_subtype) {
    return {
      subtype: 'gigabit',
      title: SWITCH_SUBTYPE_LABELS.gigabit,
      modelHint: modelHint('gigabit'),
      frameWidth: layout.frame_width,
      frameHeight: layout.frame_height,
      zones: [],
      uplinkPosition: layout.uplink_position ?? 'right',
    }
  }
  return layoutSwitchFrontPanel(layout)
}
