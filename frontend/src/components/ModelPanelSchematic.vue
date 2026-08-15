<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type {
  PanelItemKind,
  PanelLayoutConfig,
  PanelLayoutItem,
  PanelPaletteItem,
  PanelSide,
} from '@/utils/modelPanelLayout'
import {
  MAX_PANEL_COLS,
  MAX_PANEL_ROWS,
  MIN_PANEL_COLS,
  MIN_PANEL_ROWS,
  normalizePanelLayoutConfig,
  withPanelSize,
} from '@/utils/modelPanelLayout'
import {
  defaultPortTypeForSlot,
  slotTypeLabel,
  type DesignSlotAttr,
  type DesignSlotInterface,
} from '@/utils/designModelToNode'
import {
  IFACE_BOARD_KIND_SHORT,
  SWITCH_IFACE_BOARD_OPTIONS,
  SWITCH_IFACE_BOARD_PORT_PRESETS,
  ifaceKindToPortType,
  portFaceFromType,
  portTypeToIfaceKind,
  type SwitchIfaceBoardKind,
} from '@/utils/switchModelAttrs'
import SwitchSquarePort from '@/components/SwitchSquarePort.vue'

const BASE_CELL_W = 16
const BASE_CELL_H = 8
const MIN_CELL_W = 4
const MIN_CELL_H = 2
const SIDES_STACK_BP = 1100

const props = defineProps<{
  modelValue: PanelLayoutConfig
  editable?: boolean
  palette: PanelPaletteItem[]
  slots?: DesignSlotAttr[]
  /** 不显示组件库：框选空白网格创建业务接口板，右键设置类型/口数 */
  freeBoard?: boolean
  maxBoards?: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: PanelLayoutConfig]
  'edit-slot': [payload: { side: PanelSide; item: PanelLayoutItem }]
  'board-change': [payload: { items: PanelLayoutItem[] }]
}>()

const selectedPaletteId = ref<string | null>(null)
/** 面板上已放置组件的选中态（用于删除） */
const selectedPlaced = ref<{ side: PanelSide; id: string } | null>(null)
const activeSide = ref<PanelSide>('front')
const anchor = ref<{ side: PanelSide; row: number; col: number } | null>(null)
const hoverCell = ref<{ side: PanelSide; row: number; col: number } | null>(null)
const suppressGridClickUntil = ref(0)
const sidesRef = ref<HTMLElement | null>(null)
const sidesWidth = ref(0)
const dragOrigin = ref<{ side: PanelSide; row: number; col: number } | null>(null)
const boardMenu = ref<{
  side: PanelSide
  id: string
  x: number
  y: number
  kind: SwitchIfaceBoardKind
  portCount: number
  portPreset: string
} | null>(null)
let sidesObserver: ResizeObserver | null = null

const layout = computed(() => normalizePanelLayoutConfig(props.modelValue))
const cols = computed(() => layout.value.cols)
const rows = computed(() => layout.value.rows)
const frontPalette = computed(() => props.palette.filter((p) => p.side === 'front'))
const rearPalette = computed(() => props.palette.filter((p) => p.side === 'rear'))

/** 按容器宽度缩放单元格，保证左右面板不重叠 */
const cellW = computed(() => {
  const total = sidesWidth.value
  if (total <= 0) return BASE_CELL_W
  const stacked = total < SIDES_STACK_BP
  // 中间线 1px + 两侧各 16px 间距
  const dividerChrome = stacked ? 0 : 1 + 32
  const panelW = stacked ? total : (total - dividerChrome) / 2
  // side-block padding/border + grid border + left ruler
  const chrome = 8 * 2 + 2 + 2 * 2 + 18
  const avail = Math.max(48, panelW - chrome)
  const fitted = Math.floor(avail / Math.max(1, cols.value))
  return Math.max(MIN_CELL_W, Math.min(BASE_CELL_W, fitted))
})
const cellH = computed(() => {
  const scale = cellW.value / BASE_CELL_W
  return Math.max(MIN_CELL_H, Math.round(BASE_CELL_H * scale))
})
const sidesStacked = computed(() => sidesWidth.value > 0 && sidesWidth.value < SIDES_STACK_BP)

function gridAreaStyle() {
  return {
    gridTemplateColumns: `repeat(${cols.value}, ${cellW.value}px)`,
    gridTemplateRows: `repeat(${rows.value}, ${cellH.value}px)`,
  }
}

function rulerLeftStyle() {
  return {
    gridTemplateRows: `repeat(${rows.value}, ${cellH.value}px)`,
  }
}

function rulerBottomStyle() {
  return {
    gridTemplateColumns: `repeat(${cols.value}, ${cellW.value}px)`,
  }
}

onMounted(() => {
  const el = sidesRef.value
  if (!el || typeof ResizeObserver === 'undefined') {
    sidesWidth.value = el?.clientWidth || window.innerWidth
  } else {
    sidesObserver = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect?.width
      sidesWidth.value = typeof w === 'number' ? w : el.clientWidth
    })
    sidesObserver.observe(el)
    sidesWidth.value = el.clientWidth
  }
  window.addEventListener('click', closeBoardMenu)
})

onBeforeUnmount(() => {
  sidesObserver?.disconnect()
  sidesObserver = null
  window.removeEventListener('mouseup', onWindowMouseUp)
  window.removeEventListener('click', closeBoardMenu)
})

const paletteExpanded = reactive<Record<PanelSide, boolean>>({ front: false, rear: false })
const paletteOverflow = reactive<Record<PanelSide, boolean>>({ front: false, rear: false })
const paletteRefs = reactive<Partial<Record<PanelSide, HTMLElement | null>>>({})

function setPaletteRef(side: PanelSide, el: unknown) {
  paletteRefs[side] = (el as HTMLElement) || null
  void nextTick(() => measurePaletteOverflow(side))
}

function measurePaletteOverflow(side: PanelSide) {
  const el = paletteRefs[side]
  if (!el) {
    paletteOverflow[side] = false
    return
  }
  if (paletteExpanded[side]) {
    const prevWrap = el.style.flexWrap
    const prevOverflow = el.style.overflow
    const prevMaxH = el.style.maxHeight
    el.style.flexWrap = 'nowrap'
    el.style.overflow = 'hidden'
    el.style.maxHeight = '24px'
    paletteOverflow[side] = el.scrollWidth > el.clientWidth + 1
    el.style.flexWrap = prevWrap
    el.style.overflow = prevOverflow
    el.style.maxHeight = prevMaxH
    return
  }
  paletteOverflow[side] = el.scrollWidth > el.clientWidth + 1
}

function togglePaletteExpand(side: PanelSide) {
  paletteExpanded[side] = !paletteExpanded[side]
  void nextTick(() => measurePaletteOverflow(side))
}

function showPaletteMore(side: PanelSide) {
  return paletteOverflow[side] || paletteExpanded[side]
}

watch([frontPalette, rearPalette, sidesWidth, cols], () => {
  void nextTick(() => {
    measurePaletteOverflow('front')
    measurePaletteOverflow('rear')
  })
})

function sideItems(side: PanelSide): PanelLayoutItem[] {
  return side === 'front' ? layout.value.front.items : layout.value.rear.items
}

function occupancy(side: PanelSide) {
  const map = new Map<string, PanelLayoutItem>()
  for (const item of sideItems(side) || []) {
    const w = Math.max(1, item.w || 1)
    const h = Math.max(1, item.h || 1)
    for (let r = 0; r < h; r++) {
      for (let c = 0; c < w; c++) {
        map.set(`${item.row + r}:${item.col + c}`, item)
      }
    }
  }
  return map
}

const frontOcc = computed(() => occupancy('front'))
const rearOcc = computed(() => occupancy('rear'))

function kindClass(kind: PanelItemKind) {
  return `kind-${kind}`
}

function emitFull(next: PanelLayoutConfig) {
  const normalized = normalizePanelLayoutConfig(next)
  emit('update:modelValue', normalized)
  if (props.freeBoard) {
    emit('board-change', {
      items: [...normalized.front.items, ...normalized.rear.items],
    })
  }
}

function setSize(nextCols: number, nextRows: number) {
  if (!props.editable) return
  const cur = normalizePanelLayoutConfig(props.modelValue)
  emitFull(withPanelSize(cur, nextCols, nextRows))
  anchor.value = null
  hoverCell.value = null
}

function onColsChange(v: number | undefined) {
  setSize(v ?? cols.value, rows.value)
}

function onRowsChange(v: number | undefined) {
  setSize(cols.value, v ?? rows.value)
}

function rectFrom(r1: number, c1: number, r2: number, c2: number) {
  const row = Math.min(r1, r2)
  const col = Math.min(c1, c2)
  const w = Math.abs(c2 - c1) + 1
  const h = Math.abs(r2 - r1) + 1
  return { row, col, w, h }
}

const previewRect = computed(() => {
  if (!anchor.value || !hoverCell.value) return null
  if (anchor.value.side !== hoverCell.value.side) return null
  if (!props.freeBoard) {
    if (!selectedPaletteId.value) return null
    const pal = props.palette.find((p) => p.id === selectedPaletteId.value)
    if (!pal || pal.side !== anchor.value.side) return null
  }
  const rect = rectFrom(anchor.value.row, anchor.value.col, hoverCell.value.row, hoverCell.value.col)
  return { side: anchor.value.side, ...rect }
})

function cellInPreview(side: PanelSide, row: number, col: number) {
  const p = previewRect.value
  if (!p || p.side !== side) return false
  return row >= p.row && row < p.row + p.h && col >= p.col && col < p.col + p.w
}

function rangeConflicts(side: PanelSide, row: number, col: number, w: number, h: number, ignoreId?: string): boolean {
  const occ = occupancy(side)
  for (let r = row; r < row + h; r++) {
    for (let c = col; c < col + w; c++) {
      const hit = occ.get(`${r}:${c}`)
      if (hit && hit.id !== ignoreId) return true
    }
  }
  return false
}

function placeItem(side: PanelSide, row: number, col: number, w: number, h: number) {
  const pal = props.palette.find((p) => p.id === selectedPaletteId.value)
  if (!pal || pal.side !== side) return
  if (col + w > cols.value || row + h > rows.value) {
    ElMessage.warning('超出自定义面板网格范围')
    cancelAnchor()
    return
  }
  if (rangeConflicts(side, row, col, w, h, pal.id)) {
    ElMessage.warning('目标区域与其它属性重叠，请重新框选')
    cancelAnchor()
    return
  }
  const cur = normalizePanelLayoutConfig(props.modelValue)
  const sideData = {
    cols: cur.cols,
    rows: cur.rows,
    items: cur[side].items.filter((i) => i.id !== pal.id),
  }
  sideData.items.push({
    id: pal.id,
    kind: pal.kind,
    label: pal.label,
    side,
    slot_index: pal.slot_index,
    row,
    col,
    w,
    h,
    port_count: pal.port_count,
    port_type: pal.port_type,
    port_start: pal.port_start,
    blank: pal.blank,
  })
  emitFull({ ...cur, [side]: sideData })
  cancelAnchor()
  selectedPaletteId.value = null
  selectedPlaced.value = { side, id: pal.id }
}

function boardItems(cfg?: PanelLayoutConfig): PanelLayoutItem[] {
  const cur = cfg || normalizePanelLayoutConfig(props.modelValue)
  return [...cur.front.items, ...cur.rear.items].filter((i) => i.kind === 'line_card' && !i.blank)
}

function nextBoardSlotIndex(): number | null {
  const cap = Math.max(1, props.maxBoards || 48)
  const used = new Set(boardItems().map((i) => Number(i.slot_index) || 0))
  for (let i = 1; i <= cap; i++) {
    if (!used.has(i)) return i
  }
  return null
}

function boardLabel(slot: number, kind: SwitchIfaceBoardKind, count: number) {
  return `Slot${slot} ${IFACE_BOARD_KIND_SHORT[kind]}×${count}`
}

function placeFreeBoard(side: PanelSide, row: number, col: number, w: number, h: number) {
  if (col + w > cols.value || row + h > rows.value) {
    ElMessage.warning('超出自定义面板网格范围')
    cancelAnchor()
    return
  }
  if (rangeConflicts(side, row, col, w, h)) {
    ElMessage.warning('目标区域与其它属性重叠，请重新框选')
    cancelAnchor()
    return
  }
  const slot = nextBoardSlotIndex()
  if (slot == null) {
    ElMessage.warning('模块化扩展插槽已满，无法再添加接口板')
    cancelAnchor()
    return
  }
  const kind: SwitchIfaceBoardKind = '10ge'
  const portCount = 48
  const id = `slot-card-${slot}`
  const cur = normalizePanelLayoutConfig(props.modelValue)
  const sideData = {
    cols: cur.cols,
    rows: cur.rows,
    items: cur[side].items.filter((i) => i.id !== id),
  }
  sideData.items.push({
    id,
    kind: 'line_card',
    label: boardLabel(slot, kind, portCount),
    side,
    slot_index: slot,
    row,
    col,
    w,
    h,
    port_count: portCount,
    port_type: ifaceKindToPortType(kind),
  })
  emitFull({ ...cur, [side]: sideData })
  cancelAnchor()
  selectedPlaced.value = { side, id }
}

function patchBoardItem(
  side: PanelSide,
  id: string,
  patch: { kind?: SwitchIfaceBoardKind; port_count?: number },
) {
  const cur = normalizePanelLayoutConfig(props.modelValue)
  const items = cur[side].items.map((item) => {
    if (item.id !== id) return item
    const kind = patch.kind || portTypeToIfaceKind(item.port_type)
    const portCount = patch.port_count ?? item.port_count ?? 48
    const slot = item.slot_index || 1
    return {
      ...item,
      kind: 'line_card' as const,
      port_type: ifaceKindToPortType(kind),
      port_count: portCount,
      blank: false,
      label: boardLabel(slot, kind, portCount),
    }
  })
  emitFull({ ...cur, [side]: { cols: cur.cols, rows: cur.rows, items } })
}

function closeBoardMenu(ev?: Event) {
  if (!boardMenu.value) return
  const t = ev?.target
  if (t instanceof Node) {
    const menu = document.querySelector('.board-ctx')
    if (menu?.contains(t)) return
    const popper = (t as HTMLElement).closest?.('.el-select-dropdown, .el-popper')
    if (popper) return
  }
  boardMenu.value = null
}

function onBoardContext(side: PanelSide, item: PanelLayoutItem, ev: MouseEvent) {
  if (!props.editable || !props.freeBoard) return
  ev.preventDefault()
  ev.stopPropagation()
  selectPlacedItem(side, item)
  const kind = portTypeToIfaceKind(item.port_type)
  const portCount = Math.max(1, Number(item.port_count) || 48)
  const preset = SWITCH_IFACE_BOARD_PORT_PRESETS.includes(
    portCount as (typeof SWITCH_IFACE_BOARD_PORT_PRESETS)[number],
  )
    ? String(portCount)
    : 'other'
  boardMenu.value = {
    side,
    id: item.id,
    x: ev.clientX,
    y: ev.clientY,
    kind,
    portCount,
    portPreset: preset,
  }
}

function onBoardMenuKind(kind: SwitchIfaceBoardKind) {
  const menu = boardMenu.value
  if (!menu) return
  menu.kind = kind
  patchBoardItem(menu.side, menu.id, { kind, port_count: menu.portCount })
}

function onBoardMenuPreset(v: string) {
  const menu = boardMenu.value
  if (!menu) return
  menu.portPreset = v
  if (v === 'other') {
    const cur = SWITCH_IFACE_BOARD_PORT_PRESETS.includes(
      menu.portCount as (typeof SWITCH_IFACE_BOARD_PORT_PRESETS)[number],
    )
      ? 36
      : menu.portCount
    menu.portCount = cur
    patchBoardItem(menu.side, menu.id, { kind: menu.kind, port_count: cur })
    return
  }
  const n = Math.max(1, Number(v) || 48)
  menu.portCount = n
  patchBoardItem(menu.side, menu.id, { kind: menu.kind, port_count: n })
}

function onBoardMenuCustomCount(v: number | undefined) {
  const menu = boardMenu.value
  if (!menu) return
  const n = Math.max(1, Math.min(128, v ?? 36))
  menu.portCount = n
  patchBoardItem(menu.side, menu.id, { kind: menu.kind, port_count: n })
}

function removeBoardFromMenu() {
  const menu = boardMenu.value
  if (!menu) return
  removeItemOnSide(menu.side, menu.id)
  closeBoardMenu()
}

function isPlacedSelected(side: PanelSide, id: string) {
  return selectedPlaced.value?.side === side && selectedPlaced.value.id === id
}

function selectPlacedItem(side: PanelSide, item: PanelLayoutItem) {
  activeSide.value = side
  selectedPaletteId.value = null
  cancelAnchor()
  selectedPlaced.value = { side, id: item.id }
}

function removeItemOnSide(side: PanelSide, id: string) {
  const cur = normalizePanelLayoutConfig(props.modelValue)
  emitFull({
    ...cur,
    [side]: {
      cols: cur.cols,
      rows: cur.rows,
      items: cur[side].items.filter((i) => i.id !== id),
    },
  })
  if (selectedPlaced.value?.side === side && selectedPlaced.value.id === id) {
    selectedPlaced.value = null
  }
}

function removeSelectedOnSide(side: PanelSide) {
  if (!props.editable) return
  if (!selectedPlaced.value || selectedPlaced.value.side !== side) {
    ElMessage.warning(`请先点选${side === 'front' ? '前面板' : '后面板'}上的组件`)
    return
  }
  removeItemOnSide(side, selectedPlaced.value.id)
  ElMessage.success('已删除选中组件')
}

async function clearSideComponents(side: PanelSide) {
  if (!props.editable) return
  const cur = normalizePanelLayoutConfig(props.modelValue)
  const count = cur[side].items.length
  if (!count) {
    ElMessage.info(`${side === 'front' ? '前面板' : '后面板'}暂无组件`)
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定清空${side === 'front' ? '前面板' : '后面板'}上的全部 ${count} 个组件？`,
      '清空组件',
      { type: 'warning', confirmButtonText: '清空', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  emitFull({
    ...cur,
    [side]: { cols: cur.cols, rows: cur.rows, items: [] },
  })
  if (selectedPlaced.value?.side === side) selectedPlaced.value = null
  ElMessage.success('已清空组件')
}

function onCellClick(side: PanelSide, row: number, col: number) {
  if (!props.editable) return
  if (Date.now() < suppressGridClickUntil.value) return
  activeSide.value = side
  const occ = side === 'front' ? frontOcc.value : rearOcc.value
  const occupied = occ.get(`${row}:${col}`)

  if (props.freeBoard || !selectedPaletteId.value) {
    if (occupied) selectPlacedItem(side, occupied)
    else selectedPlaced.value = null
    return
  }

  const pal = props.palette.find((p) => p.id === selectedPaletteId.value)
  if (!pal || pal.side !== side) return

  if (occupied && occupied.id === pal.id) {
    removeItemOnSide(side, pal.id)
    cancelAnchor()
  }
}

function onCellEnter(side: PanelSide, row: number, col: number) {
  if (!props.editable) return
  if (!props.freeBoard && !selectedPaletteId.value) return
  if (!props.freeBoard) {
    const pal = props.palette.find((p) => p.id === selectedPaletteId.value)
    if (!pal || pal.side !== side) return
  }
  hoverCell.value = { side, row, col }
  if (dragOrigin.value && dragOrigin.value.side === side) {
    anchor.value = dragOrigin.value
  }
}

function finishBoxSelect(side: PanelSide, row: number, col: number) {
  if (!dragOrigin.value || dragOrigin.value.side !== side) {
    cancelAnchor()
    return
  }
  const { row: r, col: c, w, h } = rectFrom(dragOrigin.value.row, dragOrigin.value.col, row, col)
  if (w < 1 || h < 1) {
    cancelAnchor()
    return
  }
  if (props.freeBoard) {
    placeFreeBoard(side, r, c, w, h)
    return
  }
  const pal = props.palette.find((p) => p.id === selectedPaletteId.value)
  if (!pal || pal.side !== side) {
    cancelAnchor()
    return
  }
  placeItem(side, r, c, w, h)
}

function onWindowMouseUp() {
  if (!dragOrigin.value) return
  const end = hoverCell.value
  if (!end || end.side !== dragOrigin.value.side) {
    cancelAnchor()
    return
  }
  finishBoxSelect(end.side, end.row, end.col)
}

function onCellMouseDown(side: PanelSide, row: number, col: number, ev: MouseEvent) {
  if (!props.editable || ev.button !== 0) return
  if (!props.freeBoard) {
    if (!selectedPaletteId.value) return
    const pal = props.palette.find((p) => p.id === selectedPaletteId.value)
    if (!pal || pal.side !== side) return
  } else {
    const occ = side === 'front' ? frontOcc.value : rearOcc.value
    if (occ.get(`${row}:${col}`)) return
  }
  ev.preventDefault()
  closeBoardMenu()
  dragOrigin.value = { side, row, col }
  anchor.value = { side, row, col }
  hoverCell.value = { side, row, col }
  window.addEventListener('mouseup', onWindowMouseUp, { once: true })
}

function onCellMouseUp(side: PanelSide, row: number, col: number) {
  if (!props.editable) {
    cancelAnchor()
    return
  }
  if (!dragOrigin.value) return
  window.removeEventListener('mouseup', onWindowMouseUp)
  finishBoxSelect(side, row, col)
}

function selectPalette(id: string, side: PanelSide) {
  activeSide.value = side
  selectedPaletteId.value = selectedPaletteId.value === id ? null : id
  selectedPlaced.value = null
  cancelAnchor()
}

function cancelAnchor() {
  anchor.value = null
  hoverCell.value = null
  dragOrigin.value = null
}

function allCells() {
  const list: { row: number; col: number }[] = []
  for (let r = 0; r < rows.value; r++) {
    for (let c = 0; c < cols.value; c++) list.push({ row: r, col: c })
  }
  return list
}

const cells = computed(() => allCells())
const placing = computed(() => (props.freeBoard ? !!dragOrigin.value : !!selectedPaletteId.value))

function findSlot(slotIndex?: number): DesignSlotAttr | undefined {
  if (slotIndex == null) return undefined
  return (props.slots || []).find((s) => s.index === slotIndex)
}

function itemTypeText(item: PanelLayoutItem): string {
  // 与「设备配置及组件」按钮文案保持一致：优先调色板 label，其次布局项 label
  const pal = props.palette.find((p) => p.id === item.id)
  if (pal?.label) return pal.label
  if (item.label) return item.label
  if (item.kind === 'slot') {
    const slot = findSlot(item.slot_index)
    if (!slot) return item.id
    if (slot.type === 'raid') return `Slot${slot.index} ${String(slot.raid_level || 'raid1').toUpperCase()}`
    const list = Array.isArray(slot.interfaces) ? slot.interfaces : []
    const n10 = list.filter((x) => String(x.port_type) === '10g').length
    const n1 = list.filter((x) => String(x.port_type) === '1g').length
    if (n10 > 0) return `Slot${slot.index}:10G×${n10}`
    if (n1 > 0) return `Slot${slot.index}:1G×${n1}`
    if (slot.type === 'blank') return `Slot${slot.index}:空白`
    return `Slot${slot.index} ${slotTypeLabel(String(slot.type))}`
  }
  return item.id
}

function palettePortTypeClass(p: PanelPaletteItem): string {
  const t = String(p.port_type || '')
  if (t === '10g' || t === '25g') return 'ptype-10g'
  if (t === '1g') return 'ptype-1g'
  if (t === '40_100g' || t === '100g') return 'ptype-100g'
  if (p.kind === 'slot' && (p.port_count || 0) > 0 && !p.port_type) return 'ptype-mixed'
  return ''
}

function isPortBlock(item: PanelLayoutItem) {
  return item.kind === 'slot' || item.kind === 'line_card' || item.kind === 'port_main' || item.kind === 'port_uplink'
}

function resolvedPortMeta(item: PanelLayoutItem): {
  blank: boolean
  count: number
  port_type: string
  port_start: number
} {
  const pal = props.palette.find((p) => p.id === item.id)
  const blank = !!(item.blank ?? pal?.blank)
  const count = Math.max(0, Math.min(128, Number(item.port_count ?? pal?.port_count) || 0))
  const port_type = String(item.port_type || pal?.port_type || '1g')
  const port_start = Math.max(0, Math.trunc(Number(item.port_start ?? pal?.port_start) || 0))
  return { blank, count, port_type, port_start }
}

function itemInterfaces(item: PanelLayoutItem): DesignSlotInterface[] {
  if (item.kind === 'slot') {
    const slot = findSlot(item.slot_index)
    if (!slot) return []
    let list = Array.isArray(slot.interfaces) ? slot.interfaces : []
    // 板载 10G/1G 分组件：按 port_type 过滤，避免同一 Slot 口重复显示
    const wantType = String(item.port_type || props.palette.find((p) => p.id === item.id)?.port_type || '')
    if (wantType && list.length) {
      list = list.filter((x) => String(x.port_type) === wantType)
    }
    if (!list.length) {
      const meta = resolvedPortMeta(item)
      if (meta.blank || meta.count <= 0) return []
      const out: DesignSlotInterface[] = []
      const tag = meta.port_type === '10g' ? '10G' : meta.port_type === '1g' ? '1G' : '口'
      const prefix = item.slot_index === 1 ? '板载' : `Slot${item.slot_index}`
      for (let i = 0; i < meta.count; i++) {
        out.push({
          index: i + 1,
          port_type: meta.port_type,
          local_label: `${prefix}:${tag}-${i + 1}`,
          local_info: '',
          peer_label: '',
          peer_info: '',
        })
      }
      return out
    }
    const t = String(slot.type)
    const def =
      t === 'nic_1g' || t === 'nic_10g' ? defaultPortTypeForSlot(t) : undefined
    return list.map((x) => ({
      ...x,
      port_type: String(x.port_type || def || '1g'),
    }))
  }
  if (item.kind !== 'line_card' && item.kind !== 'port_main' && item.kind !== 'port_uplink') return []
  const meta = resolvedPortMeta(item)
  if (meta.blank || meta.count <= 0) return []
  const out: DesignSlotInterface[] = []
  for (let i = 0; i < meta.count; i++) {
    const num = meta.port_start + i
    out.push({
      index: i + 1,
      port_type: meta.port_type,
      local_label: `${num}`,
      local_info: '',
      peer_label: '',
      peer_info: '',
    })
  }
  return out
}

type EvenPortsView = {
  ifaces: DesignSlotInterface[]
  gridStyle: Record<string, string>
  portStyle: Record<string, string>
}

/** 按框选区宽高比决定行列，接口均匀铺开 */
function evenPortGrid(n: number, boxW: number, boxH: number): { cols: number; rows: number } {
  if (n <= 1) return { cols: 1, rows: 1 }
  const vertical = boxH >= boxW * 1.15
  if (vertical) {
    if (n <= 5) return { cols: 1, rows: n }
    return { cols: 2, rows: Math.ceil(n / 2) }
  }
  if (n <= 4) return { cols: n, rows: 1 }
  if (n <= 6) return { cols: Math.ceil(n / 2), rows: 2 }
  const preferCols = Math.max(2, Math.ceil(n / 2))
  const byAspect = Math.max(2, Math.round(Math.sqrt((n * boxW) / Math.max(1, boxH))))
  const cols = Math.min(n, Math.max(preferCols, Math.min(byAspect, Math.ceil(n / 2) + 2)))
  return { cols, rows: Math.ceil(n / cols) }
}

/** 交换机板卡 / 服务器 Slot：接口均匀分布；服务器为正方框 */
function evenPortsView(item: PanelLayoutItem): EvenPortsView | null {
  const ifaces = itemInterfaces(item)
  const n = ifaces.length
  if (!n) return null

  const scale = cellW.value / BASE_CELL_W
  const pad = Math.max(2, Math.round(2 * scale))
  const itemPad = 2
  const boxW = Math.max(1, item.w || 1) * cellW.value - itemPad
  const boxH = Math.max(1, item.h || 1) * cellH.value - itemPad
  const availW = Math.max(8, boxW - pad * 2)
  const availH = Math.max(8, boxH - pad * 2)

  const isSwitchCard =
    item.kind === 'line_card' || item.kind === 'port_main' || item.kind === 'port_uplink'
  const isServerSlot = item.kind === 'slot'

  if (isServerSlot) {
    const { cols, rows } = evenPortGrid(n, availW, availH)
    const minGap = Math.max(2, Math.round(2 * scale))
    // 正方口：取行列可容纳的最大边长，边距与间距均匀（space-evenly）
    let side = Math.floor(
      Math.min((availW - minGap * (cols + 1)) / cols, (availH - minGap * (rows + 1)) / rows),
    )
    side = Math.max(6, side)
    const fontPx = Math.max(5, Math.floor(side * 0.36))
    return {
      ifaces,
      gridStyle: {
        display: 'grid',
        gridTemplateColumns: `repeat(${cols}, ${side}px)`,
        gridTemplateRows: `repeat(${rows}, ${side}px)`,
        gridAutoFlow: 'row',
        gap: '0px',
        width: '100%',
        height: '100%',
        minHeight: '0',
        padding: `${pad}px`,
        boxSizing: 'border-box',
        justifyContent: 'space-evenly',
        alignContent: 'space-evenly',
        justifyItems: 'center',
        alignItems: 'center',
      },
      portStyle: {
        width: `${side}px`,
        height: `${side}px`,
        minWidth: `${side}px`,
        minHeight: `${side}px`,
        maxWidth: `${side}px`,
        maxHeight: `${side}px`,
        aspectRatio: '1 / 1',
        flex: 'none',
        fontSize: `${fontPx}px`,
      },
    }
  }

  const { cols, rows } = isSwitchCard
    ? { rows: n <= 1 ? 1 : 2, cols: Math.max(1, Math.ceil(n / (n <= 1 ? 1 : 2))) }
    : evenPortGrid(n, availW, availH)
  const gap = 0
  const cellSizeW = Math.max(4, Math.floor((availW - gap * (cols - 1)) / cols))
  const cellSizeH = Math.max(4, Math.floor((availH - gap * (rows - 1)) / rows))
  const fontPx = Math.max(5, Math.floor(Math.min(cellSizeW, cellSizeH) * 0.42))

  return {
    ifaces,
    gridStyle: {
      display: 'grid',
      gridTemplateColumns: `repeat(${cols}, 1fr)`,
      gridTemplateRows: `repeat(${rows}, 1fr)`,
      gridAutoFlow: isSwitchCard ? 'column' : 'row',
      gap: `${gap}px`,
      width: '100%',
      height: '100%',
      minHeight: '0',
      padding: `${pad}px`,
      boxSizing: 'border-box',
      alignContent: 'stretch',
      justifyContent: 'stretch',
    },
    portStyle: {
      width: '100%',
      height: '100%',
      fontSize: `${fontPx}px`,
    },
  }
}

/** @deprecated 兼容旧调用名 */
function switchPortsView(item: PanelLayoutItem): EvenPortsView | null {
  return evenPortsView(item)
}

/** Slot 简易轴（非均匀网格回退） */
function portLayoutAxis(item: PanelLayoutItem): 'horizontal' | 'vertical' {
  const w = Math.max(1, item.w || 1)
  const h = Math.max(1, item.h || 1)
  return w >= h ? 'horizontal' : 'vertical'
}

function portSizePx(item: PanelLayoutItem): number {
  const n = Math.max(1, itemInterfaces(item).length)
  const boxW = Math.max(1, item.w || 1) * cellW.value
  const boxH = Math.max(1, item.h || 1) * cellH.value
  const titleH = Math.max(8, Math.round(11 * (cellW.value / BASE_CELL_W)))
  const pad = Math.max(2, Math.round(6 * (cellW.value / BASE_CELL_W)))
  const gap = Math.max(1, Math.round(2 * (cellW.value / BASE_CELL_W)))
  const minPort = Math.max(3, Math.round(6 * (cellW.value / BASE_CELL_W)))
  const availW = Math.max(minPort, boxW - pad)
  const availH = Math.max(minPort, boxH - titleH - pad)
  const axis = portLayoutAxis(item)
  if (axis === 'horizontal') {
    const byW = (availW - gap * (n - 1)) / n
    return Math.max(minPort, Math.floor(Math.min(byW, availH)))
  }
  const byH = (availH - gap * (n - 1)) / n
  return Math.max(minPort, Math.floor(Math.min(byH, availW)))
}

function portTrackStyle(item: PanelLayoutItem) {
  const size = portSizePx(item)
  return { '--port-size': `${size}px` } as Record<string, string>
}

function usesSwitchPortLayout(item: PanelLayoutItem) {
  if (item.kind === 'line_card' || item.kind === 'port_main' || item.kind === 'port_uplink') return true
  // 服务器/通用 Slot：有接口时同样均匀铺满框选区
  if (item.kind === 'slot' && !item.blank && itemInterfaces(item).length > 0) return true
  return false
}

function onSlotAreaClick(side: PanelSide, item: PanelLayoutItem) {
  if (!props.editable || placing.value) return
  const already = isPlacedSelected(side, item.id)
  selectPlacedItem(side, item)
  // Slot：再次点击已选中的打开编辑
  if (item.kind === 'slot' && already) {
    suppressGridClickUntil.value = Date.now() + 600
    emit('edit-slot', { side, item })
  }
}

function onPlacedItemClick(side: PanelSide, item: PanelLayoutItem) {
  if (!props.editable || placing.value) return
  onSlotAreaClick(side, item)
}

function onPlacedItemContext(side: PanelSide, item: PanelLayoutItem, ev: MouseEvent) {
  if (props.freeBoard && (item.kind === 'line_card' || item.kind === 'port_main' || item.kind === 'slot')) {
    onBoardContext(side, item, ev)
    return
  }
}

function onPortClick(side: PanelSide, item: PanelLayoutItem, _iface: DesignSlotInterface) {
  onSlotAreaClick(side, item)
}

function displayPortType(item: PanelLayoutItem, iface: DesignSlotInterface): string {
  if (iface.port_type) return String(iface.port_type)
  if (item.kind === 'slot') {
    const slot = findSlot(item.slot_index)
    const t = String(slot?.type || '')
    if (t === 'nic_1g' || t === 'nic_10g') return defaultPortTypeForSlot(t)
  }
  if (usesSwitchPortLayout(item)) return resolvedPortMeta(item).port_type
  if (item.port_type) return String(item.port_type)
  return '1g'
}

function portDisplayLabel(iface: DesignSlotInterface): string {
  const raw = String(iface.local_label || iface.index)
  // 板载:10G-1 / Slot2:1G-1 → 10G-1
  const colon = raw.lastIndexOf(':')
  if (colon >= 0 && colon < raw.length - 1) return raw.slice(colon + 1)
  return raw.replace(/^slot\d+-/i, '')
}

function portTypeShort(t: string) {
  if (t === '1g') return '1G'
  if (t === '10g') return '10G'
  if (t === '40_100g' || t === '100g') return '100G'
  if (t === 'disk') return '盘'
  return t || '口'
}
</script>

<template>
  <div class="panel-schematic">
    <div class="size-bar">
      <strong>面板网格</strong>
      <span class="dim">{{
        freeBoard ? '拖拽框选空白网格创建业务接口板；右键板卡设置类型和口数' : '前后面板共用画布'
      }}</span>
      <label class="size-field">
        宽
        <el-input-number
          :model-value="cols"
          :min="MIN_PANEL_COLS"
          :max="MAX_PANEL_COLS"
          :step="1"
          size="small"
          controls-position="right"
          :disabled="!editable"
          @update:model-value="onColsChange"
        />
      </label>
      <label class="size-field">
        高
        <el-input-number
          :model-value="rows"
          :min="MIN_PANEL_ROWS"
          :max="MAX_PANEL_ROWS"
          :step="1"
          size="small"
          controls-position="right"
          :disabled="!editable"
          @update:model-value="onRowsChange"
        />
      </label>
      <span class="size-badge">宽 {{ cols }} × 高 {{ rows }}</span>
      <el-button v-if="editable && anchor" link type="warning" size="small" @click="cancelAnchor">
        取消框选
      </el-button>
    </div>

    <div ref="sidesRef" class="sides" :class="{ stacked: sidesStacked }">
      <section
        v-for="side in (['front', 'rear'] as const)"
        :key="side"
        class="side-wrap"
        :class="{ active: activeSide === side }"
      >
        <div v-if="editable && !freeBoard" class="palette-box">
          <div class="palette-box-head">设备配置及组件</div>
          <div class="palette-row" :class="{ expanded: paletteExpanded[side] }">
            <div class="palette" :ref="(el) => setPaletteRef(side, el)">
              <button
                v-for="p in side === 'front' ? frontPalette : rearPalette"
                :key="p.id"
                type="button"
                class="palette-item"
                :class="[
                  kindClass(p.kind),
                  palettePortTypeClass(p),
                  { active: selectedPaletteId === p.id && activeSide === side },
                ]"
                :title="p.label"
                @click="selectPalette(p.id, side)"
              >
                {{ p.label }}
              </button>
            <span v-if="!(side === 'front' ? frontPalette : rearPalette).length" class="dim">
              {{
                side === 'front'
                  ? '无板卡/下联/上联组件'
                  : '无风扇/电源组件'
              }}
            </span>
            </div>
            <button
              v-if="showPaletteMore(side)"
              type="button"
              class="palette-more"
              @click="togglePaletteExpand(side)"
            >
              {{ paletteExpanded[side] ? '收起' : 'more' }}
            </button>
          </div>
        </div>

        <div class="side-block" :class="{ active: activeSide === side }">
          <div class="side-head">
            <strong>{{ side === 'front' ? '前面板' : '后面板' }}</strong>
            <span class="dim">{{ cols }}×{{ rows }}</span>
            <div v-if="editable" class="side-actions">
              <el-button
                link
                type="danger"
                size="small"
                :disabled="!(selectedPlaced && selectedPlaced.side === side)"
                @click="removeSelectedOnSide(side)"
              >
                删除
              </el-button>
              <el-button link type="danger" size="small" @click="clearSideComponents(side)">
                清空组件
              </el-button>
            </div>
          </div>
          <div class="grid-frame">
            <div class="ruler ruler-left" :style="rulerLeftStyle()" aria-hidden="true">
              <span v-for="r in rows" :key="`rl-${side}-${r}`" class="ruler-tick">{{ r - 1 }}</span>
            </div>
            <div class="grid area" :style="gridAreaStyle()">
            <button
              v-for="cell in cells"
              :key="`c-${side}-${cell.row}-${cell.col}`"
              type="button"
              class="cell hit"
              :class="{
                editable,
                occupied: (side === 'front' ? frontOcc : rearOcc).has(`${cell.row}:${cell.col}`),
                preview: cellInPreview(side, cell.row, cell.col),
                anchor:
                  anchor?.side === side && anchor.row === cell.row && anchor.col === cell.col,
              }"
              :style="{
                gridRow: cell.row + 1,
                gridColumn: cell.col + 1,
              }"
              :disabled="!editable"
              @click="onCellClick(side, cell.row, cell.col)"
              @mouseenter="onCellEnter(side, cell.row, cell.col)"
              @mousedown="onCellMouseDown(side, cell.row, cell.col, $event)"
              @mouseup="onCellMouseUp(side, cell.row, cell.col)"
            />

            <div
              v-for="item in sideItems(side)"
              :key="item.id"
              class="cell item"
              :class="[
                kindClass(item.kind),
                palettePortTypeClass({
                  id: item.id,
                  kind: item.kind,
                  label: item.label,
                  side,
                  port_count: item.port_count,
                  port_type: item.port_type ?? props.palette.find((p) => p.id === item.id)?.port_type,
                }),
                {
                  placing,
                  'is-slot': isPortBlock(item),
                  interactive: editable && !placing,
                  blank: !!item.blank,
                  selected: isPlacedSelected(side, item.id),
                },
              ]"
              :style="{
                gridRow: `${item.row + 1} / span ${Math.max(1, item.h || 1)}`,
                gridColumn: `${item.col + 1} / span ${Math.max(1, item.w || 1)}`,
              }"
              :title="itemTypeText(item)"
              @click.stop="onPlacedItemClick(side, item)"
              @contextmenu.prevent="onPlacedItemContext(side, item, $event)"
            >
              <template v-if="isPortBlock(item)">
                <div v-if="!usesSwitchPortLayout(item)" class="slot-title">{{ itemTypeText(item) }}</div>
                <template v-if="usesSwitchPortLayout(item)">
                  <template v-for="sw in [switchPortsView(item)]" :key="`${item.id}-sw`">
                    <div v-if="sw" class="switch-ports" :style="sw.gridStyle">
                      <button
                        v-for="iface in sw.ifaces"
                        :key="iface.index"
                        type="button"
                        class="sw-port"
                        :class="`port-${iface.port_type}`"
                        disabled
                        :title="`${itemTypeText(item)} · ${iface.local_label || '口' + iface.index}`"
                        :style="sw.portStyle"
                      >
                        <SwitchSquarePort
                          :kind="portFaceFromType(displayPortType(item, iface))"
                          :label="portDisplayLabel(iface)"
                        />
                      </button>
                    </div>
                    <div v-else class="slot-ports empty">
                      {{ item.blank || resolvedPortMeta(item).blank ? '空白板卡' : '无接口' }}
                    </div>
                  </template>
                </template>
                <div
                  v-else-if="itemInterfaces(item).length"
                  class="slot-ports"
                  :class="portLayoutAxis(item)"
                  :style="portTrackStyle(item)"
                >
                  <button
                    v-for="iface in itemInterfaces(item)"
                    :key="iface.index"
                    type="button"
                    class="slot-port"
                    :class="`port-${displayPortType(item, iface)}`"
                    :disabled="!editable || placing || item.kind !== 'slot'"
                    :title="`${iface.local_label || '口' + iface.index}`"
                    @click.stop="item.kind === 'slot' && onPortClick(side, item, iface)"
                  >
                    <span class="port-type">{{ portTypeShort(displayPortType(item, iface)) }}</span>
                    <span v-if="item.kind === 'slot'" class="port-lab">{{
                      iface.local_label || `口${iface.index}`
                    }}</span>
                  </button>
                </div>
                <div v-else class="slot-ports empty">
                  {{
                    item.blank || item.kind === 'line_card'
                      ? '空白板卡'
                      : item.kind === 'slot'
                        ? findSlot(item.slot_index)?.type === 'raid'
                          ? 'RAID'
                          : findSlot(item.slot_index)?.type === 'blank'
                            ? '空白'
                            : '点击编辑接口'
                        : '无接口'
                  }}
                </div>
              </template>
              <template v-else>
                <span class="cell-lab">{{ item.label }}</span>
              </template>
            </div>

            <div
              v-if="previewRect && previewRect.side === side"
              class="preview-block"
              :style="{
                gridRow: `${previewRect.row + 1} / span ${previewRect.h}`,
                gridColumn: `${previewRect.col + 1} / span ${previewRect.w}`,
              }"
            />
            </div>
            <div class="ruler-corner" aria-hidden="true" />
            <div class="ruler ruler-bottom" :style="rulerBottomStyle()" aria-hidden="true">
              <span v-for="c in cols" :key="`rb-${side}-${c}`" class="ruler-tick">{{ c - 1 }}</span>
            </div>
          </div>
        </div>
      </section>
      <div class="sides-divider" aria-hidden="true" />
    </div>

    <Teleport to="body">
      <div
        v-if="boardMenu"
        class="board-ctx"
        :style="{ left: `${boardMenu.x}px`, top: `${boardMenu.y}px` }"
        @click.stop
        @contextmenu.prevent
      >
        <div class="board-ctx-title">业务接口板</div>
        <label class="board-ctx-row">
          <span>接口类型</span>
          <el-select
            :model-value="boardMenu.kind"
            size="small"
            teleported
            @change="(v: string) => onBoardMenuKind(v as SwitchIfaceBoardKind)"
          >
            <el-option
              v-for="opt in SWITCH_IFACE_BOARD_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </label>
        <label class="board-ctx-row">
          <span>接口个数</span>
          <el-select
            :model-value="boardMenu.portPreset"
            size="small"
            teleported
            @change="onBoardMenuPreset"
          >
            <el-option
              v-for="n in SWITCH_IFACE_BOARD_PORT_PRESETS"
              :key="n"
              :label="String(n)"
              :value="String(n)"
            />
            <el-option label="其他" value="other" />
          </el-select>
        </label>
        <label v-if="boardMenu.portPreset === 'other'" class="board-ctx-row">
          <span>自定义</span>
          <el-input-number
            :model-value="boardMenu.portCount"
            :min="1"
            :max="128"
            :controls="false"
            size="small"
            @change="onBoardMenuCustomCount"
          />
        </label>
        <el-button type="danger" link size="small" @click="removeBoardFromMenu">删除接口板</el-button>
      </div>
    </Teleport>

  </div>
</template>

<style scoped>
.panel-schematic {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  width: 100%;
}
.size-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 14px;
  padding: 8px 10px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #fff;
  font-size: 13px;
}
.cell.item.blank {
  opacity: 0.72;
  background: repeating-linear-gradient(
    -45deg,
    #fafafa,
    #fafafa 4px,
    #f0f2f5 4px,
    #f0f2f5 8px
  );
}
.switch-ports {
  position: relative;
  flex: 1 1 auto;
  align-self: stretch;
  min-height: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  box-sizing: border-box;
}
.cell.item.is-slot.kind-port_main,
.cell.item.is-slot.kind-port_uplink,
.cell.item.is-slot.kind-line_card,
.cell.item.is-slot.kind-slot {
  padding: 0;
  gap: 0;
}
.sw-port {
  position: relative;
  margin: 0;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-sizing: border-box;
  display: block;
  cursor: default;
  overflow: hidden;
  line-height: 1;
  flex: 0 0 auto;
  aspect-ratio: 1 / 1;
}
.size-field {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #606266;
  font-size: 12px;
}
.size-badge {
  margin-left: auto;
  font-size: 12px;
  color: #409eff;
  font-variant-numeric: tabular-nums;
}
.sides {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 1px minmax(0, 1fr);
  column-gap: 16px;
  align-items: stretch;
  width: 100%;
  min-width: 0;
}
.side-wrap {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
}
.side-wrap:first-of-type {
  grid-column: 1;
  grid-row: 1;
}
.side-wrap:last-of-type {
  grid-column: 3;
  grid-row: 1;
}
.sides-divider {
  grid-column: 2;
  grid-row: 1;
  width: 1px;
  background: #c0c4cc;
  align-self: stretch;
  min-height: 120px;
}
.side-wrap.active .side-block {
  border-color: #b3d8ff;
}
.side-block {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 8px;
  background: #fafafa;
  min-width: 0;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}
.side-block.active {
  border-color: #b3d8ff;
}
.side-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 13px;
}
.side-actions {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.dim {
  color: #909399;
  font-size: 12px;
}
.palette-box {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: #fff;
  padding: 6px 8px;
  box-sizing: border-box;
  width: 100%;
  max-width: 100%;
  min-width: 0;
}
.palette-box-head {
  font-size: 12px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 6px;
  line-height: 1.2;
}
.palette-row {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  min-width: 0;
}
.palette {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.palette-row:not(.expanded) .palette {
  flex-wrap: nowrap;
  overflow: hidden;
  max-height: 24px;
}
.palette-item {
  flex: 0 0 auto;
  border: 1px solid #dcdfe6;
  border-radius: 3px;
  padding: 2px 6px;
  font-size: 11px;
  background: #fff;
  cursor: pointer;
  line-height: 1.4;
  white-space: nowrap;
}
.palette-item.active {
  outline: 2px solid var(--el-color-primary);
}
.palette-item.ptype-1g {
  border-color: #67c23a;
  background: #f0f9eb;
}
.palette-item.ptype-10g {
  border-color: #409eff;
  background: #ecf5ff;
}
.palette-item.ptype-100g {
  border-color: #909399;
  background: #f4f4f5;
}
.palette-item.ptype-mixed {
  border-color: #409eff;
  background: linear-gradient(90deg, #ecf5ff 0 50%, #f0f9eb 50% 100%);
}
.palette-more {
  flex: 0 0 auto;
  border: 1px solid #c0c4cc;
  border-radius: 3px;
  padding: 2px 8px;
  font-size: 11px;
  line-height: 1.4;
  background: #f5f7fa;
  color: #409eff;
  cursor: pointer;
  white-space: nowrap;
}
.palette-more:hover {
  border-color: #409eff;
  background: #ecf5ff;
}
.grid.area {
  position: relative;
  display: grid;
  gap: 0;
  width: max-content;
  max-width: 100%;
  padding: 0;
  border: 2px solid #909399;
  border-radius: 0;
  background: #fff;
  box-sizing: border-box;
  user-select: none;
}
.grid-frame {
  display: grid;
  grid-template-columns: 18px max-content;
  grid-template-rows: max-content 16px;
  grid-template-areas:
    'left main'
    'corner bottom';
  width: max-content;
  max-width: 100%;
  overflow: auto;
  align-items: stretch;
}
.grid-frame .grid.area {
  grid-area: main;
}
.ruler {
  display: grid;
  gap: 0;
  font-size: 9px;
  line-height: 1;
  color: #909399;
  font-variant-numeric: tabular-nums;
  user-select: none;
}
.ruler-left {
  grid-area: left;
  width: 18px;
  border-right: 1px solid #dcdfe6;
  background: #fafafa;
}
.ruler-bottom {
  grid-area: bottom;
  height: 16px;
  border-top: 1px solid #dcdfe6;
  background: #fafafa;
}
.ruler-corner {
  grid-area: corner;
  width: 18px;
  height: 16px;
  border-top: 1px solid #dcdfe6;
  border-right: 1px solid #dcdfe6;
  background: #f5f7fa;
  box-sizing: border-box;
}
.ruler-tick {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  box-sizing: border-box;
  box-shadow: inset 0 0 0 1px rgba(192, 196, 204, 0.25);
}
.cell {
  border: none;
  border-radius: 0;
  background: rgba(255, 255, 255, 0.7);
  min-width: 0;
  min-height: 0;
  padding: 0;
  font-size: 9px;
  line-height: 1.1;
  color: #303133;
  overflow: hidden;
  z-index: 1;
  /* 内部分割线约 80% 透明度 */
  box-shadow: inset 0 0 0 1px rgba(192, 196, 204, 0.2);
}
.cell.hit {
  width: 100%;
  height: 100%;
  background: rgba(255, 255, 255, 0.7);
  z-index: 1;
}
.cell.hit.occupied {
  background: transparent;
  box-shadow: none;
}
.cell.item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 2;
  pointer-events: none;
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.12);
  box-sizing: border-box;
  overflow: hidden;
}
.cell.item.placing {
  opacity: 0.92;
}
.cell.editable {
  cursor: pointer;
}
.cell.editable:hover {
  box-shadow: inset 0 0 0 1px var(--el-color-primary);
  z-index: 4;
}
.cell.preview {
  background: rgba(64, 158, 255, 0.15) !important;
  box-shadow: inset 0 0 0 1px #409eff;
}
.cell.anchor {
  outline: 2px solid #409eff;
  outline-offset: -2px;
  z-index: 4;
}
.preview-block {
  z-index: 3;
  pointer-events: none;
  border: 2px dashed #409eff;
  background: rgba(64, 158, 255, 0.18);
  border-radius: 0;
  box-sizing: border-box;
}
.kind-slot {
  background: #e8f3ff;
  border-color: #79bbff;
}
.cell.item.ptype-1g,
.kind-slot.ptype-1g {
  background: #f0f9eb;
  border-color: #67c23a;
}
.cell.item.ptype-10g,
.kind-slot.ptype-10g {
  background: #ecf5ff;
  border-color: #409eff;
}
.cell.item.ptype-100g,
.kind-slot.ptype-100g {
  background: #f4f4f5;
  border-color: #909399;
}
.cell.item.ptype-mixed,
.kind-slot.ptype-mixed {
  background: linear-gradient(90deg, #ecf5ff 0 50%, #f0f9eb 50% 100%);
  border-color: #409eff;
}
.kind-psu {
  background: #fef0f0;
  border-color: #f89898;
}
.kind-bmc {
  background: #f0f9eb;
  border-color: #95d475;
}
.kind-usb {
  background: #fdf6ec;
  border-color: #eebe77;
}
.kind-hdmi {
  background: #f3e8ff;
  border-color: #c084fc;
}
.kind-disk_front {
  background: #eceff5;
  border-color: #8d99ae;
}
.kind-disk_rear {
  background: #e9e5f0;
  border-color: #a78bba;
}
.kind-fan {
  background: #e6f4ff;
  border-color: #69b1ff;
}
.kind-port_main {
  background: #e8f3ff;
  border-color: #409eff;
}
.kind-port_uplink {
  background: #f0f9eb;
  border-color: #67c23a;
}
.kind-line_card {
  background: #fdf6ec;
  border-color: #e6a23c;
}
.cell-lab {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
  padding: 0 2px;
}
.cell.item.is-slot {
  align-items: stretch;
  justify-content: flex-start;
  padding: 2px;
  gap: 2px;
}
.cell.item.is-slot.interactive {
  pointer-events: auto;
  cursor: pointer;
  z-index: 5;
}
.cell.item.selected {
  outline: 2px solid #409eff;
  outline-offset: -1px;
  z-index: 6;
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.35);
}
.slot-title {
  flex: 0 0 auto;
  font-size: 8px;
  font-weight: 600;
  line-height: 1.15;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding: 0 1px;
  color: #303133;
}
.slot-ports {
  flex: 1 1 auto;
  min-height: 0;
  width: 100%;
  display: flex;
  gap: 2px;
  padding: 2px;
  box-sizing: border-box;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.slot-ports.horizontal {
  flex-direction: row;
  flex-wrap: nowrap;
}
.slot-ports.vertical {
  flex-direction: column;
}
.slot-ports.empty {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 8px;
  color: #909399;
}
.slot-port {
  --size: var(--port-size, 16px);
  flex: 0 0 var(--size);
  width: var(--size);
  height: var(--size);
  min-width: var(--size);
  min-height: var(--size);
  max-width: var(--size);
  max-height: var(--size);
  aspect-ratio: 1 / 1;
  margin: 0;
  padding: 1px;
  border: 1px solid #79bbff;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.95);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  overflow: hidden;
  box-sizing: border-box;
  line-height: 1.05;
}
.slot-port.port-1g {
  border-color: #67c23a;
}
.slot-port.port-1g .port-type {
  color: #67c23a;
}
.slot-port.port-10g {
  border-color: #409eff;
}
.slot-port.port-10g .port-type {
  color: #409eff;
}
.slot-port:disabled {
  cursor: default;
  opacity: 0.85;
}
.slot-port:not(:disabled):hover {
  border-color: #409eff;
  background: #ecf5ff;
}
.port-type {
  font-size: 8px;
  font-weight: 700;
  color: #409eff;
}
.port-lab {
  font-size: 7px;
  color: #606266;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sides.stacked {
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: auto 1px auto;
  column-gap: 0;
  row-gap: 16px;
}
.sides.stacked .side-wrap:first-of-type {
  grid-column: 1;
  grid-row: 1;
}
.sides.stacked .sides-divider {
  grid-column: 1;
  grid-row: 2;
  width: 100%;
  height: 1px;
  min-height: 1px;
}
.sides.stacked .side-wrap:last-of-type {
  grid-column: 1;
  grid-row: 3;
}
@media (max-width: 1100px) {
  .size-badge {
    margin-left: 0;
  }
}
.board-ctx {
  position: fixed;
  z-index: 4000;
  min-width: 240px;
  padding: 10px 12px;
  background: #fff;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.board-ctx-title {
  font-size: 13px;
  font-weight: 600;
}
.board-ctx-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  color: var(--el-text-color-regular);
}
.board-ctx-row :deep(.el-select),
.board-ctx-row :deep(.el-input-number) {
  width: 150px;
}
</style>
