<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
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
}>()

const emit = defineEmits<{
  'update:modelValue': [value: PanelLayoutConfig]
  'edit-slot': [payload: { side: PanelSide; item: PanelLayoutItem }]
}>()

const selectedPaletteId = ref<string | null>(null)
const activeSide = ref<PanelSide>('front')
const anchor = ref<{ side: PanelSide; row: number; col: number } | null>(null)
const hoverCell = ref<{ side: PanelSide; row: number; col: number } | null>(null)
const suppressGridClickUntil = ref(0)
const sidesRef = ref<HTMLElement | null>(null)
const sidesWidth = ref(0)
const dragOrigin = ref<{ side: PanelSide; row: number; col: number } | null>(null)
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
  // side-block padding/border + grid border
  const chrome = 8 * 2 + 2 + 2 * 2
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

onMounted(() => {
  const el = sidesRef.value
  if (!el || typeof ResizeObserver === 'undefined') {
    sidesWidth.value = el?.clientWidth || window.innerWidth
    return
  }
  sidesObserver = new ResizeObserver((entries) => {
    const w = entries[0]?.contentRect?.width
    sidesWidth.value = typeof w === 'number' ? w : el.clientWidth
  })
  sidesObserver.observe(el)
  sidesWidth.value = el.clientWidth
})

onBeforeUnmount(() => {
  sidesObserver?.disconnect()
  sidesObserver = null
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
  emit('update:modelValue', normalizePanelLayoutConfig(next))
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
  if (!selectedPaletteId.value || !anchor.value || !hoverCell.value) return null
  if (anchor.value.side !== hoverCell.value.side) return null
  const pal = props.palette.find((p) => p.id === selectedPaletteId.value)
  if (!pal || pal.side !== anchor.value.side) return null
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
    blank: pal.blank,
  })
  emitFull({ ...cur, [side]: sideData })
  cancelAnchor()
  selectedPaletteId.value = null
}

function onCellClick(side: PanelSide, row: number, col: number) {
  if (!props.editable) return
  if (Date.now() < suppressGridClickUntil.value) return
  activeSide.value = side
  const occ = side === 'front' ? frontOcc.value : rearOcc.value
  const occupied = occ.get(`${row}:${col}`)

  // 未选组件：点已放置块可删除；Slot 可编辑
  if (!selectedPaletteId.value) {
    if (occupied) {
      if (occupied.kind === 'slot') {
        suppressGridClickUntil.value = Date.now() + 300
        emit('edit-slot', { side, item: occupied })
        return
      }
      const cur = normalizePanelLayoutConfig(props.modelValue)
      emitFull({
        ...cur,
        [side]: {
          cols: cur.cols,
          rows: cur.rows,
          items: cur[side].items.filter((i) => i.id !== occupied.id),
        },
      })
    }
    return
  }

  const pal = props.palette.find((p) => p.id === selectedPaletteId.value)
  if (!pal || pal.side !== side) return

  // 再次点击同组件已占区：移除
  if (occupied && occupied.id === pal.id) {
    const cur = normalizePanelLayoutConfig(props.modelValue)
    emitFull({
      ...cur,
      [side]: {
        cols: cur.cols,
        rows: cur.rows,
        items: cur[side].items.filter((i) => i.id !== pal.id),
      },
    })
    cancelAnchor()
  }
}

function onCellEnter(side: PanelSide, row: number, col: number) {
  if (!props.editable || !selectedPaletteId.value) return
  const pal = props.palette.find((p) => p.id === selectedPaletteId.value)
  if (!pal || pal.side !== side) return
  hoverCell.value = { side, row, col }
  if (dragOrigin.value && dragOrigin.value.side === side) {
    anchor.value = dragOrigin.value
  }
}

function onCellMouseDown(side: PanelSide, row: number, col: number, ev: MouseEvent) {
  if (!props.editable || !selectedPaletteId.value) return
  const pal = props.palette.find((p) => p.id === selectedPaletteId.value)
  if (!pal || pal.side !== side) return
  ev.preventDefault()
  dragOrigin.value = { side, row, col }
  anchor.value = { side, row, col }
  hoverCell.value = { side, row, col }
}

function onCellMouseUp(side: PanelSide, row: number, col: number) {
  if (!props.editable || !selectedPaletteId.value) {
    cancelAnchor()
    return
  }
  if (!dragOrigin.value || dragOrigin.value.side !== side) {
    cancelAnchor()
    return
  }
  const pal = props.palette.find((p) => p.id === selectedPaletteId.value)
  if (!pal || pal.side !== side) {
    cancelAnchor()
    return
  }
  const { row: r, col: c, w, h } = rectFrom(dragOrigin.value.row, dragOrigin.value.col, row, col)
  if (w < 1 || h < 1) {
    cancelAnchor()
    return
  }
  placeItem(side, r, c, w, h)
}

function selectPalette(id: string, side: PanelSide) {
  activeSide.value = side
  selectedPaletteId.value = selectedPaletteId.value === id ? null : id
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
const placing = computed(() => !!selectedPaletteId.value)

function findSlot(slotIndex?: number): DesignSlotAttr | undefined {
  if (slotIndex == null) return undefined
  return (props.slots || []).find((s) => s.index === slotIndex)
}

function itemTypeText(item: PanelLayoutItem): string {
  if (item.kind === 'slot') {
    const slot = findSlot(item.slot_index)
    if (!slot) return item.label
    if (slot.type === 'raid') return `Slot${slot.index} ${String(slot.raid_level || 'raid1').toUpperCase()}`
    return `Slot${slot.index} ${slotTypeLabel(String(slot.type))}`
  }
  return item.label
}

function isPortBlock(item: PanelLayoutItem) {
  return item.kind === 'slot' || item.kind === 'line_card' || item.kind === 'port_main' || item.kind === 'port_uplink'
}

function resolvedPortMeta(item: PanelLayoutItem): {
  blank: boolean
  count: number
  port_type: string
} {
  const pal = props.palette.find((p) => p.id === item.id)
  const blank = !!(item.blank ?? pal?.blank)
  const count = Math.max(0, Math.min(128, Number(item.port_count ?? pal?.port_count) || 0))
  const port_type = String(item.port_type || pal?.port_type || '1g')
  return { blank, count, port_type }
}

function itemInterfaces(item: PanelLayoutItem): DesignSlotInterface[] {
  if (item.kind === 'slot') {
    const slot = findSlot(item.slot_index)
    if (!slot) return []
    const list = Array.isArray(slot.interfaces) ? slot.interfaces : []
    const t = String(slot.type)
    if (t === 'nic_1g' || t === 'nic_10g') {
      const def = defaultPortTypeForSlot(t)
      return list.map((x) => ({ ...x, port_type: def }))
    }
    return list
  }
  if (item.kind !== 'line_card' && item.kind !== 'port_main' && item.kind !== 'port_uplink') return []
  const meta = resolvedPortMeta(item)
  if (meta.blank || meta.count <= 0) return []
  const out: DesignSlotInterface[] = []
  for (let i = 1; i <= meta.count; i++) {
    out.push({
      index: i,
      port_type: meta.port_type,
      local_label: `${i}`,
      local_info: '',
      peer_label: '',
      peer_info: '',
    })
  }
  return out
}

type SwitchPortsView = {
  ifaces: DesignSlotInterface[]
  gridStyle: Record<string, string>
  portStyle: Record<string, string>
}

/** 交换机：无标题字样；双排列向编号；接口均匀平铺满框选区 */
function switchPortsView(item: PanelLayoutItem): SwitchPortsView | null {
  const ifaces = itemInterfaces(item)
  const n = ifaces.length
  if (!n) return null

  const scale = cellW.value / BASE_CELL_W
  const pad = Math.max(1, Math.round(1 * scale))
  const itemPad = 2
  const boxW = Math.max(1, item.w || 1) * cellW.value - itemPad
  const boxH = Math.max(1, item.h || 1) * cellH.value - itemPad
  const availW = Math.max(8, boxW - pad * 2)
  const availH = Math.max(8, boxH - pad * 2)

  const rows = n <= 1 ? 1 : 2
  const cols = Math.max(1, Math.ceil(n / rows))
  // 按框选区宽高均分，口格铺满区域
  const cellSizeW = Math.max(4, Math.floor(availW / cols))
  const cellSizeH = Math.max(4, Math.floor(availH / rows))
  const fontPx = Math.max(5, Math.floor(Math.min(cellSizeW, cellSizeH) * 0.42))

  return {
    ifaces,
    gridStyle: {
      display: 'grid',
      gridTemplateColumns: `repeat(${cols}, 1fr)`,
      gridTemplateRows: `repeat(${rows}, 1fr)`,
      gridAutoFlow: 'column',
      gap: '0px',
      width: '100%',
      height: '100%',
      minHeight: '0',
      padding: `${pad}px`,
      boxSizing: 'border-box',
    },
    portStyle: {
      width: '100%',
      height: '100%',
      fontSize: `${fontPx}px`,
    },
  }
}

/** Slot 仍用简易均分；交换机块用 switchPortsView */
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
  return item.kind === 'line_card' || item.kind === 'port_main' || item.kind === 'port_uplink'
}

function onSlotAreaClick(side: PanelSide, item: PanelLayoutItem) {
  if (!props.editable || placing.value) return
  suppressGridClickUntil.value = Date.now() + 600
  emit('edit-slot', { side, item })
}

function onPortClick(side: PanelSide, item: PanelLayoutItem, _iface: DesignSlotInterface) {
  onSlotAreaClick(side, item)
}

function displayPortType(item: PanelLayoutItem, iface: DesignSlotInterface): string {
  if (item.kind === 'slot') {
    const slot = findSlot(item.slot_index)
    const t = String(slot?.type || '')
    if (t === 'nic_1g' || t === 'nic_10g') return defaultPortTypeForSlot(t)
  }
  if (usesSwitchPortLayout(item)) return resolvedPortMeta(item).port_type
  if (item.port_type) return String(item.port_type)
  return iface.port_type
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
      <span class="dim">前后面板共用画布</span>
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
    </div>

    <p v-if="editable" class="tb-hint">
      ① 点选「设备配置及组件」中的组件 ② 在面板上拖拽框选范围放置；交换机口自动双排紧凑均分。
      <el-button v-if="anchor" link type="warning" size="small" @click="cancelAnchor">取消框选</el-button>
    </p>

    <div ref="sidesRef" class="sides" :class="{ stacked: sidesStacked }">
      <section
        v-for="side in (['front', 'rear'] as const)"
        :key="side"
        class="side-wrap"
        :class="{ active: activeSide === side }"
      >
        <div v-if="editable" class="palette-box">
          <div class="palette-box-head">设备配置及组件</div>
          <div class="palette-row" :class="{ expanded: paletteExpanded[side] }">
            <div class="palette" :ref="(el) => setPaletteRef(side, el)">
              <button
                v-for="p in side === 'front' ? frontPalette : rearPalette"
                :key="p.id"
                type="button"
                class="palette-item"
                :class="[kindClass(p.kind), { active: selectedPaletteId === p.id && activeSide === side }]"
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
                {
                  placing,
                  'is-slot': isPortBlock(item),
                  interactive: editable && !placing && item.kind === 'slot',
                  blank: !!item.blank,
                },
              ]"
              :style="{
                gridRow: `${item.row + 1} / span ${Math.max(1, item.h || 1)}`,
                gridColumn: `${item.col + 1} / span ${Math.max(1, item.w || 1)}`,
              }"
              :title="itemTypeText(item)"
              @click.stop="item.kind === 'slot' && onSlotAreaClick(side, item)"
            >
              <template v-if="isPortBlock(item)">
                <div v-if="!usesSwitchPortLayout(item)" class="slot-title">{{ itemTypeText(item) }}</div>
                <template v-if="usesSwitchPortLayout(item)">
                  <template v-for="sw in [switchPortsView(item)]" :key="`${item.id}-sw`">
                    <div v-if="sw" class="switch-ports" :style="sw.gridStyle">
                      <button
                        v-for="(iface, idx) in sw.ifaces"
                        :key="iface.index"
                        type="button"
                        class="sw-port"
                        :class="`port-${iface.port_type}`"
                        disabled
                        :title="`${itemTypeText(item)} · 口${idx + 1}`"
                        :style="sw.portStyle"
                      >
                        <span class="sw-port-lab">{{ idx + 1 }}</span>
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
        </div>
      </section>
      <div class="sides-divider" aria-hidden="true" />
    </div>

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
.cell.item.is-slot.kind-line_card {
  padding: 0;
  gap: 0;
}
.sw-port {
  position: relative;
  margin: 0;
  padding: 0;
  border: 1px solid #303133;
  border-radius: 0;
  background: #fff;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: default;
  overflow: hidden;
  line-height: 1;
  flex: 0 0 auto;
}
.sw-port.port-1g {
  background: #fff;
  border-color: #303133;
}
.sw-port.port-10g,
.sw-port.port-25g {
  background: #f5f7fa;
  border-color: #303133;
}
.sw-port.port-10g .sw-port-lab,
.sw-port.port-25g .sw-port-lab {
  color: #303133;
}
.sw-port.port-40_100g,
.sw-port.port-100g {
  background: #fafafa;
  border-color: #303133;
}
.sw-port.port-40_100g .sw-port-lab,
.sw-port.port-100g .sw-port-lab {
  color: #303133;
}
.sw-port-lab {
  font-size: inherit;
  font-weight: 600;
  color: #303133;
  transform: none;
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
.tb-hint {
  margin: 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
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
</style>
