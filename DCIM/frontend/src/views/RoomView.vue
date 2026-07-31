<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listDatacenters, type DataCenter } from '@/api/datacenter'
import {
  applyTemplateToRoom,
  getRackLayout,
  listRackTemplates,
  listRacks,
  unapplyTemplateFromRoom,
  updateRack,
  type Rack,
  type RackLayoutSlot,
  type RackTemplate,
} from '@/api/rack'
import { createRoomQuick, deleteRoom, getRoom, listRooms, updateRoom } from '@/api/room'
import type { Room, RoomImportance } from '@/api/room'
import { useAuthStore } from '@/stores/auth'
import RackCabinet from '@/components/RackCabinet.vue'
import {
  exportRoomRackLayoutsExcel,
  exportRoomRackLayoutsPdf,
  type ExportRackBundle,
} from '@/utils/rackLayoutExport'
import {
  loadUsagePresets,
  saveUsagePresets,
  type RackUsagePreset,
} from '@/utils/rackUsagePresets'

const ATTR_PRESETS: Array<{ value: string; label: string }> = [
  { value: 'internet', label: '互联网机房' },
  { value: 'private_network', label: '专网机房' },
]

const IMPORTANCE_OPTIONS: Array<{ value: RoomImportance; label: string }> = [
  { value: 'critical', label: '关键' },
  { value: 'high', label: '高' },
  { value: 'medium', label: '中' },
  { value: 'low', label: '低' },
]

const IMPORTANCE_LABEL: Record<string, string> = Object.fromEntries(
  IMPORTANCE_OPTIONS.map((o) => [o.value, o.label]),
)

const CREATE_STEPS = [
  { title: '基础信息' },
  { title: '机房轮廓' },
  { title: '机柜编排' },
  { title: '编号设置' },
]

function attributeLabel(value: string) {
  return ATTR_PRESETS.find((p) => p.value === value)?.label || value
}

function roomAttributes(row: Room): string[] {
  if (Array.isArray(row.attributes) && row.attributes.length) return row.attributes
  return []
}

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const tableData = ref<Room[]>([])
const datacenters = ref<DataCenter[]>([])
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const keyword = ref('')
const dialogVisible = ref(false)
const createStep = ref(0)
const customAttrInput = ref('')
const editingId = ref<string | null>(null)
const layoutVisible = ref(false)
const layoutLoading = ref(false)
const layoutRoom = ref<Room | null>(null)
const layoutRacks = ref<Rack[]>([])
const layoutDisplayMode = ref<'simple' | 'full'>('simple')
const layoutDetails = ref<Record<string, { slots: RackLayoutSlot[]; totalPower: number }>>({})
const fullLayoutLoading = ref(false)

const rackZoomVisible = ref(false)
const rackZoomLoading = ref(false)
const rackZoomRack = ref<Rack | null>(null)
const rackZoomSlots = ref<RackLayoutSlot[]>([])
const rackZoomPower = ref(0)
const pendingFocusRackId = ref<string | null>(null)

const templates = ref<RackTemplate[]>([])
const applyVisible = ref(false)
const applyLoading = ref(false)
const applyForm = reactive({
  template_id: '',
  fill_empty_slots: true,
})
const unapplyVisible = ref(false)
const unapplyLoading = ref(false)
const unapplyForm = reactive({
  template_id: '',
  delete_empty_racks: true,
  detach_template: true,
})

interface LayoutSlot {
  row: number
  col: number
  code: string
  rack: Rack | null
  kind: 'rack' | 'pillar'
}

function roomGridLayout(room: Room): number[] {
  if (room.row_layout?.length) return room.row_layout.map((n) => Math.max(1, Number(n) || 1))
  const rows = Math.max(1, room.rack_rows || 1)
  const cols = Math.max(1, room.rack_columns || 1)
  return Array.from({ length: rows }, () => cols)
}

function roomCellKind(room: Room, rowIdx: number, colIdx: number): 'rack' | 'pillar' {
  const cells = room.pillar_layout?.cells?.[String(rowIdx + 1)]
  const kind = cells?.[colIdx]
  if (kind === 'pillar' || kind === 'pillar_round') return 'pillar'
  if (kind != null && kind !== 'rack' && kind !== 'empty') return 'pillar'
  const code = String(room.slot_codes?.[rowIdx]?.[colIdx] || '').trim()
  if (room.code_mode === 'custom' && !code) return 'pillar'
  return 'rack'
}

/** 按机房设定生成展示编号：连续、跳过立柱；绝不合成 R行列表占位码 */
function resolveRoomDisplayCodes(room: Room): string[][] {
  const layout = roomGridLayout(room)
  const stored = room.slot_codes || []
  const kinds = layout.map((cols, ri) =>
    Array.from({ length: cols }, (_, ci) => roomCellKind(room, ri, ci)),
  )

  const aligned = layout.map((cols, ri) => {
    const row = stored[ri] || []
    return Array.from({ length: cols }, (_, ci) =>
      kinds[ri][ci] === 'pillar' ? '' : String(row[ci] ?? '').trim(),
    )
  })

  const hasCompleteCodes = aligned.every((row, ri) =>
    row.every((c, ci) => kinds[ri][ci] === 'pillar' || Boolean(c)),
  )
  if (hasCompleteCodes) return aligned

  // 缺号时按排前缀连续补齐（仅机柜格），保持与机房设置一致
  let prefixes: string[]
  try {
    prefixes = expandRowPrefixes(room.code_prefix || 'A', layout.length)
  } catch {
    prefixes = layout.map((_, i) => indexToLetter(i + 1))
  }
  return layout.map((cols, ri) => {
    const prefix = prefixes[ri] || indexToLetter(ri + 1)
    const rackCount = kinds[ri].filter((k) => k === 'rack').length
    const width = Math.max(2, String(Math.max(rackCount, 1)).length)
    let seq = 0
    return Array.from({ length: cols }, (_, ci) => {
      if (kinds[ri][ci] === 'pillar') return ''
      const existing = aligned[ri][ci]
      if (existing) {
        const m = existing.match(/(\d+)$/)
        if (m) seq = Math.max(seq, Number.parseInt(m[1], 10))
        return existing
      }
      seq += 1
      return `${prefix}${String(seq).padStart(width, '0')}`
    })
  })
}

const layoutRows = computed(() => {
  const room = layoutRoom.value
  if (!room) return [] as Array<{ row: number; label: string; slots: LayoutSlot[]; rackCount: number }>
  const layout = roomGridLayout(room)
  const displayCodes = resolveRoomDisplayCodes(room)
  const byPos = new Map(layoutRacks.value.map((r) => [`${r.row_no}-${r.column_no}`, r]))
  const byCode = new Map(
    layoutRacks.value
      .filter((r) => (r.code || '').trim())
      .map((r) => [(r.code || '').trim().toLowerCase(), r]),
  )
  const claimed = new Set<string>()

  return layout.map((cols, idx) => {
    const row = idx + 1
    const slots: LayoutSlot[] = Array.from({ length: cols }, (_, colIdx) => {
      const col = colIdx + 1
      const kind = roomCellKind(room, idx, colIdx)
      const code = kind === 'pillar' ? '' : displayCodes[idx]?.[colIdx] || ''
      let rack: Rack | null = null
      if (kind === 'rack') {
        const posRack = byPos.get(`${row}-${col}`) || null
        const codeRack = code ? byCode.get(code.toLowerCase()) || null : null
        // 优先按机房编号落位，保证布局图与编号设置一致
        if (codeRack && !claimed.has(codeRack.id)) {
          rack = codeRack
        } else if (posRack && !claimed.has(posRack.id)) {
          // 位置上有柜但编号不同：仍显示该柜，编号以机房设定为准
          rack = posRack
        }
        if (rack) claimed.add(rack.id)
      }
      return { row, col, code, kind, rack }
    })
    const rackCount = slots.filter((s) => s.kind === 'rack').length
    const firstRackCode = slots.find((s) => s.kind === 'rack' && s.code)?.code
    const label = firstRackCode?.replace(/\d+$/, '') || `第${row}排`
    return { row, label, slots, rackCount }
  })
})

const layoutStats = computed(() => {
  const rackSlots = layoutRows.value.flatMap((r) => r.slots.filter((s) => s.kind === 'rack'))
  const total = rackSlots.length
  const occupied = rackSlots.filter((s) => s.rack).length
  const pillars = layoutRows.value.reduce(
    (sum, r) => sum + r.slots.filter((s) => s.kind === 'pillar').length,
    0,
  )
  return { total, occupied, free: total - occupied, pillars }
})

const form = reactive({
  datacenter_id: '',
  building_no: '',
  room_no: '',
  attributes: [] as string[],
  importance: 'medium' as RoomImportance,
  outline_rows: 8,
  outline_cols: 10,
  layout_mode: 'auto' as 'auto' | 'manual',
  rack_rows: 4,
  rack_columns: 6,
  row_layout: [6, 6, 6, 6] as number[],
  code_mode: 'auto' as 'auto' | 'custom',
  code_prefix: 'A',
  slot_codes: [] as string[][],
  /** 与 slot_codes 同形：rack=机柜位，pillar=立柱（不占编号） */
  slot_kinds: [] as Array<Array<'rack' | 'pillar'>>,
  description: '',
})

const activeLayout = computed(() =>
  form.layout_mode === 'auto'
    ? Array.from({ length: form.rack_rows }, () => form.rack_columns)
    : form.row_layout,
)

const rackCapacity = computed(() => activeLayout.value.reduce((sum, n) => sum + n, 0))

const layoutSummary = computed(() => {
  const layout = activeLayout.value
  const outline = `轮廓 ${form.outline_cols}×${form.outline_rows}`
  if (form.code_mode !== 'custom') {
    if (form.layout_mode === 'auto') {
      return `${outline} · 编排 ${form.rack_rows} 排 × ${form.rack_columns} 列（共 ${rackCapacity.value} 柜）`
    }
    return `${outline} · ${layout.length} 排（${layout.join('+')}）· 机柜 ${rackCapacity.value} 台`
  }
  const pillarCount = form.slot_kinds.flat().filter((k) => k === 'pillar').length
  const rackSlots = form.slot_kinds.length
    ? form.slot_kinds.flat().filter((k) => k === 'rack').length
    : rackCapacity.value - pillarCount
  const perRow = form.slot_kinds.length
    ? form.slot_kinds
        .map((row, i) => `第${i + 1}排${row.filter((k) => k === 'rack').length}柜`)
        .join('，')
    : ''
  return `${outline} · 机柜 ${rackSlots} 台${
    pillarCount ? ` · 立柱 ${pillarCount}` : ''
  }${perRow ? `（${perRow}）` : ''}`
})

const rowPrefixResult = computed(() => {
  try {
    return { ok: true as const, prefixes: expandRowPrefixes(form.code_prefix, activeLayout.value.length) }
  } catch (error) {
    return { ok: false as const, message: error instanceof Error ? error.message : '前缀无效', prefixes: [] as string[] }
  }
})

const codePreview = computed(() => {
  if (form.code_mode === 'auto' && !rowPrefixResult.value.ok) {
    return rowPrefixResult.value.message
  }
  const codes = form.slot_codes.flat().filter(Boolean)
  const pillars = form.slot_kinds.flat().filter((k) => k === 'pillar').length
  const suffix = pillars ? `；立柱 ${pillars} 处` : ''
  if (!codes.length) return pillars ? `（仅立柱${suffix}）` : '—'
  if (codes.length <= 8) return `${codes.join('、')}${suffix}`
  return `${codes.slice(0, 8).join('、')} …（共 ${codes.length} 个）${suffix}`
})

const rowPrefixHint = computed(() => {
  if (!rowPrefixResult.value.ok) return rowPrefixResult.value.message
  const prefixes = rowPrefixResult.value.prefixes
  const map = prefixes.map((p, i) => `第${i + 1}排=${p}`).join('，')
  const sample = prefixes[0] ? `${prefixes[0]}01、${prefixes[0]}02` : ''
  return `排前缀：${map}；同排示例：${sample}`
})

const canCreate = auth.hasPermission('datacenter:create')
const canUpdate = auth.hasPermission('datacenter:update')
const canDelete = auth.hasPermission('datacenter:delete')
const canApplyRack = auth.hasPermission('rack:update')

/** 从路由读取数据中心筛选（兼容 string / string[]） */
function readRouteDatacenterId(): string {
  const raw = route.query.datacenter_id
  if (typeof raw === 'string' && raw) return raw
  if (Array.isArray(raw) && typeof raw[0] === 'string' && raw[0]) return raw[0]
  return ''
}

/** 下拉框本地值；仅在用户操作时回写路由，避免选项未加载时被清空 */
const filterDcId = ref('')
const hasDcFilter = computed(() => Boolean(filterDcId.value))
const filteredDatacenter = computed(
  () => datacenters.value.find((d) => d.id === filterDcId.value) || null,
)

const pageStats = computed(() => {
  const rooms = tableData.value
  const rackCount = rooms.reduce((sum, r) => sum + (r.rack_count || 0), 0)
  const usedCount = rooms.reduce((sum, r) => sum + (r.used_count || 0), 0)
  const freeCount = rooms.reduce((sum, r) => sum + (r.free_count || 0), 0)
  const totalPower = rooms.reduce((sum, r) => sum + (Number(r.total_power) || 0), 0)
  const capacity = rooms.reduce((sum, r) => sum + roomCapacity(r), 0)
  const dcIds = new Set(rooms.map((r) => r.datacenter_id).filter(Boolean))
  const util = capacity > 0 ? Math.round((rackCount / capacity) * 100) : 0
  const mountUtil = rackCount > 0 ? Math.round((usedCount / rackCount) * 100) : 0
  return {
    roomCount: rooms.length,
    rackCount,
    usedCount,
    freeCount,
    totalPower,
    capacity,
    util,
    mountUtil,
    dcCount: hasDcFilter.value ? 1 : dcIds.size,
  }
})

const metaSavingIds = ref<Set<string>>(new Set())

function importanceLabel(value?: string | null) {
  return IMPORTANCE_LABEL[value || ''] || value || '—'
}

function formatPower(watts?: number | null) {
  const w = Number(watts) || 0
  if (w >= 1000) return `${(w / 1000).toFixed(1)} kW`
  return `${Math.round(w)} W`
}

function roomGridLabel(row: Room) {
  const outline =
    row.outline_cols && row.outline_rows
      ? `轮廓 ${row.outline_cols}×${row.outline_rows}`
      : ''
  const layoutLabel = row.row_layout?.length
    ? `${row.row_layout.length}排 · ${row.row_layout.join('/')}`
    : `${row.rack_rows || 0}×${row.rack_columns || 0}`
  return outline ? `${outline} · ${layoutLabel}` : layoutLabel
}

function roomCapacity(row: Room) {
  const layout =
    row.row_layout?.length > 0
      ? row.row_layout
      : Array.from({ length: row.rack_rows || 0 }, () => row.rack_columns || 0)
  const grid = layout.reduce((a, b) => a + b, 0)
  let pillars = 0
  const cells = row.pillar_layout?.cells
  if (cells) {
    for (const [rowKey, kinds] of Object.entries(cells)) {
      const rowIdx = Number(rowKey) - 1
      if (!Array.isArray(kinds) || rowIdx < 0 || rowIdx >= layout.length) continue
      pillars += kinds
        .slice(0, layout[rowIdx])
        .filter((k) => k === 'pillar' || k === 'pillar_round').length
    }
  }
  const rackSlots = Math.max(0, grid - pillars)
  if (row.rack_capacity && row.rack_capacity <= rackSlots) return row.rack_capacity
  return rackSlots || row.rack_capacity || 0
}

async function updateRoomMeta(row: Room, patch: { importance?: RoomImportance }) {
  if (!canUpdate) return
  const prevImportance = row.importance
  if (patch.importance !== undefined) row.importance = patch.importance
  metaSavingIds.value = new Set(metaSavingIds.value).add(row.id)
  try {
    const updated = await updateRoom(row.id, patch)
    row.importance = updated.importance
  } catch (error: unknown) {
    row.importance = prevImportance
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '更新失败')
  } finally {
    const next = new Set(metaSavingIds.value)
    next.delete(row.id)
    metaSavingIds.value = next
  }
}

function onImportanceChange(row: Room, value: string) {
  void updateRoomMeta(row, { importance: value as RoomImportance })
}

function hasPresetAttr(code: string) {
  return form.attributes.includes(code)
}

function togglePresetAttr(code: string) {
  const idx = form.attributes.indexOf(code)
  if (idx >= 0) form.attributes.splice(idx, 1)
  else form.attributes.push(code)
}

function addCustomAttribute() {
  const value = customAttrInput.value.trim()
  if (!value) return
  if (ATTR_PRESETS.some((p) => p.value === value || p.label === value)) {
    ElMessage.warning('请直接勾选预设属性')
    return
  }
  if (form.attributes.includes(value)) {
    ElMessage.warning('属性已存在')
    return
  }
  if (value.length > 40) {
    ElMessage.warning('自定义属性不超过 40 字')
    return
  }
  form.attributes.push(value)
  customAttrInput.value = ''
}

function removeAttribute(value: string) {
  const idx = form.attributes.indexOf(value)
  if (idx >= 0) form.attributes.splice(idx, 1)
}

function customAttributes() {
  return form.attributes.filter((a) => !ATTR_PRESETS.some((p) => p.value === a))
}

function validateOutlineFits(layout: number[]): string | null {
  if (form.outline_rows < 1 || form.outline_cols < 1) return '请设置有效的机房轮廓网格'
  if (layout.length > form.outline_rows) {
    return `机柜排数 ${layout.length} 超出轮廓宽向 ${form.outline_rows} 格`
  }
  const widest = Math.max(...layout, 0)
  if (widest > form.outline_cols) {
    return `机柜列数 ${widest} 超出轮廓长向 ${form.outline_cols} 格`
  }
  return null
}

function datacenterLabel(dc: DataCenter) {
  return dc.location ? `${dc.name}（${dc.location}）` : dc.name
}

function letterToIndex(label: string): number {
  const text = label.trim().toUpperCase()
  if (!text || !/^[A-Z]+$/.test(text)) {
    throw new Error(`无效字母标签：${label}`)
  }
  let value = 0
  for (const ch of text) {
    value = value * 26 + (ch.charCodeAt(0) - 64)
  }
  return value
}

function indexToLetter(index: number): string {
  if (index < 1) throw new Error('字母序号无效')
  let n = index
  let result = ''
  while (n > 0) {
    const rem = (n - 1) % 26
    result = String.fromCharCode(65 + rem) + result
    n = Math.floor((n - 1) / 26)
  }
  return result
}

function expandRowPrefixes(expression: string, rowCount: number): string[] {
  if (rowCount < 1) throw new Error('排数无效')
  let raw = (expression || 'A').trim().toUpperCase().replace(/\s+/g, '')
  if (!raw) raw = 'A'

  if (raw.includes('-')) {
    const [startRaw, endRaw] = raw.split('-', 2)
    if (!startRaw || !endRaw) throw new Error('范围格式应为 A-D 或 A-BZ')
    const start = letterToIndex(startRaw)
    const end = letterToIndex(endRaw)
    if (end < start) throw new Error('范围终点必须大于等于起点')
    const labels: string[] = []
    for (let i = start; i <= end; i += 1) labels.push(indexToLetter(i))
    if (labels.length < rowCount) {
      throw new Error(`范围 ${raw} 仅有 ${labels.length} 个字母，但机房有 ${rowCount} 排`)
    }
    return labels.slice(0, rowCount)
  }

  const start = letterToIndex(raw)
  return Array.from({ length: rowCount }, (_, i) => indexToLetter(start + i))
}

function buildSlotKinds(layout: number[], keepExisting = true): Array<Array<'rack' | 'pillar'>> {
  return layout.map((cols, rowIdx) => {
    const existing = keepExisting ? form.slot_kinds[rowIdx] || [] : []
    return Array.from({ length: cols }, (_, colIdx) =>
      existing[colIdx] === 'pillar' ? 'pillar' : 'rack',
    )
  })
}

function buildSlotCodes(layout: number[], prefixExpr = form.code_prefix, keepExisting = true): string[][] {
  const kinds = buildSlotKinds(layout, keepExisting)

  if (form.code_mode === 'custom' && keepExisting) {
    // 保留手改编号，但立柱强制空码；随后统一跳号重排可由 renumberSkippingPillars 触发
    return layout.map((cols, rowIdx) => {
      const existing = form.slot_codes[rowIdx] || []
      return Array.from({ length: cols }, (_, colIdx) => {
        if (kinds[rowIdx]?.[colIdx] === 'pillar') return ''
        return existing[colIdx] || ''
      })
    })
  }

  const prefixes = expandRowPrefixes(prefixExpr, layout.length)
  return layout.map((cols, rowIdx) => {
    const prefix = prefixes[rowIdx]
    const rackCount = kinds[rowIdx]?.filter((k) => k === 'rack').length || cols
    const width = Math.max(2, String(rackCount).length)
    let seq = 0
    return Array.from({ length: cols }, (_, colIdx) => {
      if (kinds[rowIdx]?.[colIdx] === 'pillar') return ''
      seq += 1
      return `${prefix}${String(seq).padStart(width, '0')}`
    })
  })
}

/** 按当前逐位格子同步排布局网格（含立柱格）；机柜数 = 非立柱编号格数量 */
function syncRowLayoutFromSlots() {
  if (!form.slot_kinds.length) return
  form.layout_mode = 'manual'
  form.row_layout = form.slot_kinds.map((row) => Math.max(1, row.length))
  form.rack_rows = form.row_layout.length
  form.rack_columns = Math.max(...form.row_layout, 1)
}

/** 跳过立柱后按排连续编号；编号数量即该排机柜数量 */
function renumberSkippingPillars() {
  const rowCount = Math.max(form.slot_kinds.length, form.slot_codes.length, 1)
  try {
    const prefixes = expandRowPrefixes(form.code_prefix || 'A', rowCount)
    form.slot_codes = form.slot_kinds.map((kinds, rowIdx) => {
      const prefix = prefixes[rowIdx] || indexToLetter(rowIdx + 1)
      const rackCount = kinds.filter((k) => k === 'rack').length
      const width = Math.max(2, String(Math.max(rackCount, 1)).length)
      let seq = 0
      return kinds.map((k) => {
        if (k === 'pillar') return ''
        seq += 1
        return `${prefix}${String(seq).padStart(width, '0')}`
      })
    })
  } catch {
    form.slot_codes = form.slot_kinds.map((kinds, rowIdx) =>
      kinds.map((k, colIdx) =>
        k === 'pillar' ? '' : form.slot_codes[rowIdx]?.[colIdx] || '',
      ),
    )
  }
  syncRowLayoutFromSlots()
}

function toggleSlotPillar(rowIdx: number, colIdx: number) {
  if (!form.slot_kinds[rowIdx]) return
  const next = form.slot_kinds.map((row) => [...row])
  const becomingPillar = next[rowIdx][colIdx] !== 'pillar'
  next[rowIdx][colIdx] = becomingPillar ? 'pillar' : 'rack'
  // 设立柱时在排尾补一个机柜格，保持该排机柜位数不变（空白框占位不挤占机柜）
  if (becomingPillar) {
    if (next[rowIdx].length >= form.outline_cols) {
      ElMessage.warning(
        `该排已达轮廓长向上限 ${form.outline_cols} 格，无法再设立柱占位，请先删格或扩大轮廓`,
      )
      return
    }
    next[rowIdx] = [...next[rowIdx], 'rack']
  }
  form.slot_kinds = next
  form.slot_codes = form.slot_kinds.map((kinds, ri) => {
    const existing = form.slot_codes[ri] || []
    return kinds.map((k, ci) => (k === 'pillar' ? '' : existing[ci] || ''))
  })
  renumberSkippingPillars()
}

/** 删除编号单元格，缩短该排网格并保持连续编号 */
function deleteSlotCell(rowIdx: number, colIdx: number) {
  const row = form.slot_kinds[rowIdx]
  if (!row) return
  if (row.length <= 1) {
    ElMessage.warning('每排至少保留一格')
    return
  }
  const rackLeft = row.filter((k, i) => i !== colIdx && k === 'rack').length
  if (rackLeft < 1) {
    ElMessage.warning('每排至少保留一个机柜编号位（立柱除外）')
    return
  }
  form.slot_kinds = form.slot_kinds.map((r, ri) =>
    ri === rowIdx ? r.filter((_, ci) => ci !== colIdx) : [...r],
  )
  form.slot_codes = form.slot_codes.map((r, ri) =>
    ri === rowIdx ? r.filter((_, ci) => ci !== colIdx) : [...r],
  )
  renumberSkippingPillars()
}

/** 在指定排末尾增加一个机柜编号格 */
function addSlotCell(rowIdx: number) {
  if (!form.slot_kinds[rowIdx]) return
  if (form.slot_kinds[rowIdx].length >= form.outline_cols) {
    ElMessage.warning(`每排最多 ${form.outline_cols} 格（轮廓长向上限）`)
    return
  }
  form.slot_kinds = form.slot_kinds.map((r, ri) => (ri === rowIdx ? [...r, 'rack'] : [...r]))
  form.slot_codes = form.slot_codes.map((r, ri) => (ri === rowIdx ? [...r, ''] : [...r]))
  if (!form.slot_codes[rowIdx]) {
    form.slot_codes[rowIdx] = Array.from({ length: form.slot_kinds[rowIdx].length }, () => '')
  }
  renumberSkippingPillars()
}

function ensureSlotMatricesAligned() {
  if (!form.slot_kinds.length) {
    form.slot_kinds = buildSlotKinds(activeLayout.value, false)
  }
  // 以当前格子矩阵为准对齐编号（支持每排不等长），不回扩已删格
  form.slot_codes = form.slot_kinds.map((kinds, ri) => {
    const existing = form.slot_codes[ri] || []
    return kinds.map((k, ci) => (k === 'pillar' ? '' : String(existing[ci] ?? '')))
  })
}

function rowRackCount(rowIdx: number) {
  return (form.slot_kinds[rowIdx] || []).filter((k) => k === 'rack').length
}

function syncSlotKindsFromPillarLayout(
  layout: number[],
  pillarLayout: Room['pillar_layout'] | null | undefined,
) {
  const cells = pillarLayout?.cells
  form.slot_kinds = layout.map((cols, rowIdx) => {
    const key = String(rowIdx + 1)
    const rowCells = cells?.[key]
    return Array.from({ length: cols }, (_, colIdx) => {
      const kind = rowCells?.[colIdx]
      return kind === 'pillar' || kind === 'pillar_round' ? 'pillar' : 'rack'
    })
  })
}

function buildPillarLayoutPayload() {
  const layout = activeLayout.value
  const cells: Record<string, Array<'rack' | 'pillar' | 'empty'>> = {}
  let hasPillar = false
  layout.forEach((cols, rowIdx) => {
    const row: Array<'rack' | 'pillar' | 'empty'> = []
    for (let colIdx = 0; colIdx < cols; colIdx += 1) {
      const kind = form.slot_kinds[rowIdx]?.[colIdx] === 'pillar' ? 'pillar' : 'rack'
      if (kind === 'pillar') hasPillar = true
      row.push(kind)
    }
    cells[String(rowIdx + 1)] = row
  })
  if (!hasPillar) {
    return { mode: 'cells' as const, cells: {} as Record<string, Array<'rack' | 'pillar' | 'empty'>> }
  }
  return {
    mode: 'cells' as const,
    rows: layout.length,
    cols: Math.max(...layout, 1),
    cells,
  }
}

function syncAutoLayout() {
  form.row_layout = Array.from({ length: form.rack_rows }, () => form.rack_columns)
}

function regenerateCodes(keepCustom = false) {
  try {
    form.slot_kinds = buildSlotKinds(activeLayout.value, keepCustom || form.code_mode === 'custom')
    form.slot_codes = buildSlotCodes(activeLayout.value, form.code_prefix, keepCustom)
  } catch {
    if (form.code_mode === 'auto') {
      form.slot_codes = []
      form.slot_kinds = buildSlotKinds(activeLayout.value, false)
    }
  }
}

watch(
  () => [form.rack_rows, form.rack_columns, form.layout_mode] as const,
  () => {
    if (form.layout_mode === 'auto') {
      syncAutoLayout()
    }
    regenerateCodes(form.code_mode === 'custom')
  },
)

watch(
  () => form.row_layout.join(','),
  () => {
    if (form.layout_mode === 'manual') {
      regenerateCodes(form.code_mode === 'custom')
    }
  },
)

watch(
  () => form.code_prefix,
  () => {
    if (form.code_mode === 'auto') {
      regenerateCodes(false)
    }
  },
)

watch(
  () => form.code_mode,
  (mode) => {
    if (mode === 'auto') {
      // 自动编号不维护立柱占位，整网按排布局连续编号
      form.slot_kinds = buildSlotKinds(activeLayout.value, false)
      regenerateCodes(false)
    } else {
      regenerateCodes(true)
    }
  },
)

function addManualRow() {
  if (form.row_layout.length >= form.outline_rows) {
    ElMessage.warning(`最多 ${form.outline_rows} 排（轮廓宽向上限）`)
    return
  }
  form.row_layout.push(Math.min(6, form.outline_cols))
}

function removeManualRow(index: number) {
  if (form.row_layout.length <= 1) {
    ElMessage.warning('至少保留一排')
    return
  }
  form.row_layout.splice(index, 1)
  form.slot_codes.splice(index, 1)
  form.slot_kinds.splice(index, 1)
}

async function loadDatacenters() {
  const data = await listDatacenters({ page_size: 100 })
  datacenters.value = data.items
}

async function syncFilterFromRoute() {
  filterDcId.value = readRouteDatacenterId()
}

async function loadData() {
  loading.value = true
  try {
    const dcId = filterDcId.value || readRouteDatacenterId()
    if (dcId && filterDcId.value !== dcId) {
      filterDcId.value = dcId
    }
    const data = await listRooms({
      page: pagination.page,
      page_size: pagination.page_size,
      keyword: keyword.value || undefined,
      datacenter_id: dcId || undefined,
    })
    // 服务端按数据中心过滤；前端再兜底一次，确保不串数据中心
    const items = dcId
      ? data.items.filter((r) => r.datacenter_id === dcId)
      : data.items
    tableData.value = items
    pagination.total = data.pagination.total
  } finally {
    loading.value = false
  }
}

async function applyDatacenterFilter(id: string | null | undefined) {
  const nextId = id || ''
  filterDcId.value = nextId
  pagination.page = 1
  const nextQuery = { ...route.query }
  if (nextId) nextQuery.datacenter_id = nextId
  else delete nextQuery.datacenter_id
  delete nextQuery.open_layout
  delete nextQuery.rack_id
  await router.replace({ name: 'rooms-manage', query: nextQuery })
  await loadData()
}

function onFilterDcChange(value: string | null | undefined) {
  // 选项未加载完时 el-select 可能误发空值，忽略以免冲掉路由筛选
  if (!value && !datacenters.value.length) return
  void applyDatacenterFilter(value)
}

function clearDatacenterFilter() {
  void applyDatacenterFilter('')
}

const editingRackCount = ref(0)

function openCreate() {
  editingId.value = null
  editingRackCount.value = 0
  createStep.value = 0
  customAttrInput.value = ''
  form.datacenter_id = filterDcId.value || datacenters.value[0]?.id || ''
  form.building_no = ''
  form.room_no = ''
  form.attributes = []
  form.importance = 'medium'
  form.outline_rows = 8
  form.outline_cols = 10
  form.layout_mode = 'auto'
  form.rack_rows = 4
  form.rack_columns = 6
  form.code_mode = 'auto'
  form.code_prefix = 'A'
  syncAutoLayout()
  form.slot_kinds = buildSlotKinds(activeLayout.value, false)
  regenerateCodes(false)
  form.description = ''
  dialogVisible.value = true
}

function openEdit(row: Room) {
  editingId.value = row.id
  editingRackCount.value = row.rack_count || 0
  createStep.value = 0
  customAttrInput.value = ''
  form.datacenter_id = row.datacenter_id || ''
  form.building_no = row.building_no || ''
  form.room_no = row.room_no || row.name
  form.attributes = [...roomAttributes(row)]
  form.importance = (row.importance as RoomImportance) || 'medium'
  form.outline_rows = row.outline_rows || row.rack_rows || 8
  form.outline_cols = row.outline_cols || row.rack_columns || 10
  form.layout_mode = row.layout_mode === 'manual' ? 'manual' : 'auto'
  form.rack_rows = row.rack_rows
  form.rack_columns = row.rack_columns
  form.row_layout = [...(row.row_layout?.length ? row.row_layout : [row.rack_columns])]
  form.code_mode = row.code_mode === 'custom' ? 'custom' : 'auto'
  form.code_prefix = row.code_prefix || 'A'
  if (form.code_mode === 'custom') {
    form.slot_codes = row.slot_codes?.length
      ? row.slot_codes.map((r) => [...r])
      : buildSlotCodes(form.row_layout, form.code_prefix, false)
    syncSlotKindsFromPillarLayout(form.row_layout, row.pillar_layout)
    form.slot_codes = form.slot_kinds.map((kinds, ri) => {
      const rowCodes = form.slot_codes[ri] || []
      return kinds.map((kind, ci) => (kind === 'pillar' ? '' : rowCodes[ci] || ''))
    })
  } else {
    form.slot_kinds = buildSlotKinds(form.row_layout, false)
    form.slot_codes = buildSlotCodes(form.row_layout, form.code_prefix, false)
  }
  form.description = row.description || ''
  dialogVisible.value = true
}

function validateStep(step: number): boolean {
  if (step === 0) {
    if (!editingId.value && !form.datacenter_id) {
      ElMessage.warning('请选择所属数据中心')
      return false
    }
    if (!form.building_no || !form.room_no) {
      ElMessage.warning('请填写机房楼号和机房门牌号')
      return false
    }
    return true
  }
  if (step === 1) {
    if (form.outline_rows < 1 || form.outline_cols < 1) {
      ElMessage.warning('请设置有效的机房轮廓（长×宽网格）')
      return false
    }
    return true
  }
  if (step === 2) {
    if (form.layout_mode === 'manual') {
      if (!form.row_layout.length || form.row_layout.some((n) => n < 1)) {
        ElMessage.warning('请为每一排设置有效的机柜数量')
        return false
      }
    } else if (form.rack_rows < 1 || form.rack_columns < 1) {
      ElMessage.warning('请填写有效的机柜排数与每排机柜数')
      return false
    }
    const err = validateOutlineFits(activeLayout.value)
    if (err) {
      ElMessage.warning(err)
      return false
    }
    return true
  }
  if (step === 3) {
    if (!String(form.code_prefix || '').trim()) {
      ElMessage.warning('请先填写编号前缀')
      return false
    }
    if (form.code_mode === 'auto' && !rowPrefixResult.value.ok) {
      ElMessage.warning(rowPrefixResult.value.message)
      return false
    }
    return true
  }
  return true
}

function nextCreateStep() {
  if (!validateStep(createStep.value)) return
  if (createStep.value < CREATE_STEPS.length - 1) createStep.value += 1
}

function prevCreateStep() {
  if (createStep.value > 0) createStep.value -= 1
}

async function handleSubmit() {
  for (let step = 0; step < CREATE_STEPS.length; step += 1) {
    if (!validateStep(step)) {
      if (!editingId.value) createStep.value = step
      return
    }
  }

  const isCustom = form.code_mode === 'custom'
  if (isCustom) {
    ensureSlotMatricesAligned()
    syncRowLayoutFromSlots()
    for (let i = 0; i < form.slot_kinds.length; i += 1) {
      if (rowRackCount(i) < 1) {
        ElMessage.warning(`第 ${i + 1} 排至少保留一个机柜编号位`)
        return
      }
    }
    const missing = form.slot_kinds.some((kinds, ri) =>
      kinds.some((kind, ci) => kind === 'rack' && !String(form.slot_codes[ri]?.[ci] || '').trim()),
    )
    if (missing) {
      ElMessage.warning('请填写全部机柜编号（立柱空白框可留空）')
      return
    }
    const flat = form.slot_kinds.flatMap((kinds, ri) =>
      kinds
        .map((kind, ci) => (kind === 'pillar' ? '' : form.slot_codes[ri]?.[ci] || ''))
        .filter((c) => c !== ''),
    )
    const lower = flat.map((c) => c.trim().toLowerCase())
    if (new Set(lower).size !== lower.length) {
      ElMessage.warning('机柜编号不能重复')
      return
    }
  }

  const layout = activeLayout.value
  const outlineErr = validateOutlineFits(
    isCustom ? form.slot_kinds.map((row) => Math.max(1, row.length)) : layout,
  )
  if (outlineErr) {
    ElMessage.warning(outlineErr)
    if (!editingId.value) createStep.value = 2
    return
  }

  const layoutPayload = isCustom
    ? {
        layout_mode: 'manual' as const,
        row_layout: form.slot_kinds.map((row) => Math.max(1, row.length)),
        rack_rows: form.slot_kinds.length,
        rack_columns: Math.max(...form.slot_kinds.map((r) => r.length), 1),
      }
    : form.layout_mode === 'auto'
      ? {
          layout_mode: 'auto' as const,
          rack_rows: form.rack_rows,
          rack_columns: form.rack_columns,
          row_layout: layout,
        }
      : {
          layout_mode: 'manual' as const,
          row_layout: [...form.row_layout],
          rack_rows: form.row_layout.length,
          rack_columns: Math.max(...form.row_layout, 1),
        }

  const codePayload = isCustom
    ? {
        code_mode: 'custom' as const,
        code_prefix: form.code_prefix || 'A',
        slot_codes: form.slot_kinds.map((kinds, ri) => {
          const rowCodes = form.slot_codes[ri] || []
          return kinds.map((kind, ci) => {
            if (kind === 'pillar') return ''
            return String(rowCodes[ci] ?? '').trim()
          })
        }),
      }
    : {
        code_mode: 'auto' as const,
        code_prefix: form.code_prefix || 'A',
        slot_codes: buildSlotCodes(layout, form.code_prefix, false),
      }

  const pillarPayload = {
    pillar_layout: isCustom
      ? buildPillarLayoutPayload()
      : ({ mode: 'cells' as const, cells: {} }),
  }

  const metaPayload = {
    attributes: [...form.attributes],
    importance: form.importance,
    outline_rows: form.outline_rows,
    outline_cols: form.outline_cols,
  }

  try {
    if (editingId.value) {
      const updated = await updateRoom(editingId.value, {
        room_no: form.room_no,
        description: form.description || null,
        ...metaPayload,
        ...layoutPayload,
        ...codePayload,
        ...pillarPayload,
      })
      ElMessage.success('更新成功')
      if (layoutRoom.value?.id === updated.id) {
        layoutRoom.value = updated
        await reloadLayoutRacks()
      }
    } else {
      const created = await createRoomQuick({
        datacenter_id: form.datacenter_id,
        building_no: form.building_no,
        room_no: form.room_no,
        description: form.description || null,
        ...metaPayload,
        ...layoutPayload,
        ...codePayload,
        ...pillarPayload,
      })
      ElMessage.success('创建成功')
      dialogVisible.value = false
      await loadData()
      await openLayout(created)
      return
    }
    dialogVisible.value = false
    await loadData()
  } catch (error: unknown) {
    const err = error as {
      response?: { data?: { message?: string; details?: { errors?: Array<{ msg?: string }> } } }
      message?: string
    }
    const details = err.response?.data?.details?.errors
    const detailMsg = details?.map((e) => e.msg).filter(Boolean).join('；')
    const message = detailMsg || err.response?.data?.message || err.message || '操作失败'
    ElMessage.error(message)
  }
}

function roomTitle(row: Room) {
  return [row.datacenter_name || row.location, row.building_no, row.room_no || row.name]
    .filter(Boolean)
    .join('-')
}

function utilizationClass(rack: Rack | null) {
  if (!rack) return 'empty'
  if (rack.app_color) return 'custom'
  if (rack.utilization >= 80) return 'high'
  if (rack.utilization >= 40) return 'mid'
  if (rack.utilization > 0) return 'low'
  return 'idle'
}

function rackCellStyle(rack: Rack | null): Record<string, string> {
  if (rack?.app_color) {
    return { background: rack.app_color, borderColor: '#8a8a8a' }
  }
  return {}
}

/** 简单布局：框选 / 用途着色 / 导出 */
const selectedSlotKeys = ref<Set<string>>(new Set())
const selecting = ref(false)
const selectionDirty = ref(false)
const usagePresets = ref<RackUsagePreset[]>(loadUsagePresets())
const activePresetId = ref(usagePresets.value[0]?.id || '')
const usageApplyLoading = ref(false)
const exportLoading = ref(false)
const presetDialogVisible = ref(false)
const presetDraft = ref<RackUsagePreset[]>([])

const activePreset = computed(
  () => usagePresets.value.find((p) => p.id === activePresetId.value) || usagePresets.value[0] || null,
)

const selectedBuiltRacks = computed(() => {
  const keys = selectedSlotKeys.value
  const racks: Rack[] = []
  for (const row of layoutRows.value) {
    for (const slot of row.slots) {
      if (!slot.rack) continue
      if (keys.has(`${slot.row}-${slot.col}`)) racks.push(slot.rack)
    }
  }
  return racks
})

function slotKey(row: number, col: number) {
  return `${row}-${col}`
}

function isSlotSelected(row: number, col: number) {
  return selectedSlotKeys.value.has(slotKey(row, col))
}

function clearSelection() {
  selectedSlotKeys.value = new Set()
}

function toggleSlotSelection(row: number, col: number, additive = true) {
  const key = slotKey(row, col)
  const next = new Set(additive ? selectedSlotKeys.value : [])
  if (next.has(key) && additive) next.delete(key)
  else next.add(key)
  selectedSlotKeys.value = next
}

function addSlotToSelection(row: number, col: number) {
  const key = slotKey(row, col)
  if (selectedSlotKeys.value.has(key)) return
  const next = new Set(selectedSlotKeys.value)
  next.add(key)
  selectedSlotKeys.value = next
}

function onSlotPointerDown(slot: { row: number; col: number; rack: Rack | null }, event: MouseEvent) {
  if (layoutDisplayMode.value !== 'simple') return
  if (event.button !== 0) return
  event.preventDefault()
  selecting.value = true
  selectionDirty.value = false
  if (event.ctrlKey || event.metaKey) {
    toggleSlotSelection(slot.row, slot.col, true)
  } else {
    selectedSlotKeys.value = new Set([slotKey(slot.row, slot.col)])
  }
  const onUp = () => {
    selecting.value = false
    window.removeEventListener('mouseup', onUp)
  }
  window.addEventListener('mouseup', onUp)
}

function onSlotPointerEnter(slot: { row: number; col: number }) {
  if (!selecting.value) return
  selectionDirty.value = true
  addSlotToSelection(slot.row, slot.col)
}

function onSlotClick(slot: { row: number; col: number; rack: Rack | null }) {
  // 拖选后不触发单击逻辑；空闲位仅用于选择
  if (selectionDirty.value) {
    selectionDirty.value = false
    return
  }
  if (!slot.rack) return
  // 已选中且仅选一个时，单击打开放大；多选时保持选择
  if (selectedSlotKeys.value.size === 1 && isSlotSelected(slot.row, slot.col)) {
    void openRackZoom(slot.rack)
  }
}

function onSlotDblClick(slot: { row: number; col: number; rack: Rack | null }) {
  if (slot.rack) void openRackZoom(slot.rack)
}

async function applyUsageToSelection() {
  const preset = activePreset.value
  if (!preset) {
    ElMessage.warning('请先选择或创建用途色标')
    return
  }
  const racks = selectedBuiltRacks.value
  if (!racks.length) {
    ElMessage.warning('请先框选已建机柜（空闲位无法着色）')
    return
  }
  if (!canApplyRack) {
    ElMessage.warning('没有机柜更新权限')
    return
  }
  usageApplyLoading.value = true
  try {
    await Promise.all(
      racks.map((rack) =>
        updateRack(rack.id, {
          app_usage: preset.label,
          app_color: preset.color,
        }),
      ),
    )
    for (const rack of racks) {
      rack.app_usage = preset.label
      rack.app_color = preset.color
    }
    ElMessage.success(`已为 ${racks.length} 台机柜设置用途「${preset.label}」`)
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '设置用途失败')
  } finally {
    usageApplyLoading.value = false
  }
}

async function clearUsageOnSelection() {
  const racks = selectedBuiltRacks.value
  if (!racks.length) {
    ElMessage.warning('请先选择已建机柜')
    return
  }
  if (!canApplyRack) return
  usageApplyLoading.value = true
  try {
    await Promise.all(
      racks.map((rack) =>
        updateRack(rack.id, {
          app_usage: null,
          app_color: null,
        }),
      ),
    )
    for (const rack of racks) {
      rack.app_usage = null
      rack.app_color = null
    }
    ElMessage.success('已清除所选机柜用途色标')
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '清除失败')
  } finally {
    usageApplyLoading.value = false
  }
}

function openPresetDialog() {
  presetDraft.value = usagePresets.value.map((p) => ({ ...p }))
  presetDialogVisible.value = true
}

function addPresetDraft() {
  presetDraft.value.push({
    id: `custom-${Date.now()}`,
    label: '自定义用途',
    color: '#FFE566',
  })
}

function removePresetDraft(index: number) {
  if (presetDraft.value.length <= 1) {
    ElMessage.warning('至少保留一个用途色标')
    return
  }
  presetDraft.value.splice(index, 1)
}

function savePresetDialog() {
  const cleaned = presetDraft.value
    .map((p, idx) => ({
      id: p.id || `custom-${idx}`,
      label: (p.label || '').trim() || `用途${idx + 1}`,
      color: p.color || '#FFE566',
    }))
  usagePresets.value = cleaned
  saveUsagePresets(cleaned)
  if (!cleaned.some((p) => p.id === activePresetId.value)) {
    activePresetId.value = cleaned[0]?.id || ''
  }
  presetDialogVisible.value = false
  ElMessage.success('用途色标已保存')
}

async function collectExportBundles(): Promise<ExportRackBundle[]> {
  // 导出机房全部已建机柜（所有排/列），按布局位置排列
  const source = layoutRows.value.flatMap(
    (r) => r.slots.map((s) => s.rack).filter(Boolean) as Rack[],
  )
  if (!source.length) return []
  const unique = new Map(source.map((r) => [r.id, r]))
  const bundles: ExportRackBundle[] = []
  for (const rack of unique.values()) {
    const cached = layoutDetails.value[rack.id]
    if (cached) {
      bundles.push({
        rack,
        layout: {
          rack,
          positions: [],
          slots: cached.slots,
          devices: [],
          total_power: cached.totalPower,
        },
      })
      continue
    }
    const layout = await getRackLayout(rack.id)
    bundles.push({ rack, layout })
  }
  return bundles
}

async function handleExportLayouts(format: 'excel' | 'pdf') {
  if (!layoutRoom.value) return
  exportLoading.value = true
  try {
    const bundles = await collectExportBundles()
    if (!bundles.length) {
      ElMessage.warning('当前机房没有已建机柜可导出')
      return
    }
    const title = roomTitle(layoutRoom.value)
    if (format === 'excel') {
      await exportRoomRackLayoutsExcel(title, bundles)
      ElMessage.success(`已导出全部 ${bundles.length} 台机柜布局（Excel）`)
    } else {
      exportRoomRackLayoutsPdf(title, bundles)
      ElMessage.success('已打开打印预览，可另存为 PDF')
    }
  } catch (error: unknown) {
    const err = error as { message?: string }
    ElMessage.error(err.message || '导出失败')
  } finally {
    exportLoading.value = false
  }
}

const appliedTemplates = computed(() =>
  templates.value.filter((t) => (t.applied_rack_count || 0) > 0 || (t.applied_rooms?.length || 0) > 0),
)

const roomAppliedTemplates = computed(() => {
  const roomId = layoutRoom.value?.id
  if (!roomId) return [] as RackTemplate[]
  return appliedTemplates.value.filter((t) =>
    (t.applied_rooms || []).some((r) => r.id === roomId),
  )
})

const unapplyTemplateOptions = computed(() => roomAppliedTemplates.value)

const unapplyTemplate = computed(
  () => templates.value.find((t) => t.id === unapplyForm.template_id) || null,
)

async function refreshTemplates() {
  templates.value = await listRackTemplates()
}

async function reloadLayoutRacks() {
  if (!layoutRoom.value) return
  const data = await listRacks({ room_id: layoutRoom.value.id, page_size: 500 })
  layoutRacks.value = data.items
}

async function loadFullLayoutDetails() {
  const racksWithInstance = layoutRacks.value
  if (!racksWithInstance.length) {
    layoutDetails.value = {}
    return
  }
  fullLayoutLoading.value = true
  try {
    const results = await Promise.all(
      racksWithInstance.map(async (rack) => {
        const data = await getRackLayout(rack.id)
        return [
          rack.id,
          { slots: data.slots || [], totalPower: data.total_power || 0 },
        ] as const
      }),
    )
    layoutDetails.value = Object.fromEntries(results)
  } catch (error: unknown) {
    layoutDetails.value = {}
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '加载机柜详情失败')
  } finally {
    fullLayoutLoading.value = false
  }
}

async function onLayoutModeChange(mode: 'simple' | 'full') {
  if (mode === 'full') {
    await loadFullLayoutDetails()
  }
}

function openApplyTemplate() {
  if (!layoutRoom.value) return
  applyForm.template_id = templates.value[0]?.id || ''
  applyForm.fill_empty_slots = true
  applyVisible.value = true
}

async function submitApplyTemplate() {
  if (!layoutRoom.value || !applyForm.template_id) {
    ElMessage.warning('请选择机柜样式模板')
    return
  }
  const tpl = templates.value.find((t) => t.id === applyForm.template_id)
  await ElMessageBox.confirm(
    `将模板「${tpl?.name}」应用到机房「${roomTitle(layoutRoom.value)}」？\n` +
      (applyForm.fill_empty_slots
        ? '将更新已有机柜，并按机房布局在有效机柜位建柜（自动跳过立柱空白占位）。'
        : '仅更新该机房已有机柜规格。'),
    '应用模板',
    { type: 'warning' },
  )
  applyLoading.value = true
  try {
    const result = await applyTemplateToRoom(
      applyForm.template_id,
      layoutRoom.value.id,
      applyForm.fill_empty_slots,
    )
    ElMessage.success(
      `完成：更新 ${result.updated}，新建 ${result.created}` +
        (result.skipped ? `，跳过 ${result.skipped}` : ''),
    )
    if (result.errors?.length) {
      ElMessage.warning(result.errors.slice(0, 3).join('；'))
    }
    applyVisible.value = false
    await Promise.all([refreshTemplates(), reloadLayoutRacks()])
    if (layoutDisplayMode.value === 'full') {
      await loadFullLayoutDetails()
    }
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '应用失败')
  } finally {
    applyLoading.value = false
  }
}

function openUnapplyTemplate() {
  if (!layoutRoom.value) return
  const preferred = roomAppliedTemplates.value[0]
  if (!preferred) {
    ElMessage.info('当前机房没有已应用的机柜模板')
    return
  }
  unapplyForm.template_id = preferred.id
  unapplyForm.delete_empty_racks = true
  unapplyForm.detach_template = true
  unapplyVisible.value = true
}

async function submitUnapplyTemplate() {
  if (!layoutRoom.value || !unapplyForm.template_id) {
    ElMessage.warning('请选择要取消的模板')
    return
  }
  if (!unapplyForm.delete_empty_racks && !unapplyForm.detach_template) {
    ElMessage.warning('请至少勾选一项操作')
    return
  }
  const tpl = unapplyTemplate.value
  await ElMessageBox.confirm(
    `取消模板「${tpl?.name}」在机房「${roomTitle(layoutRoom.value)}」的应用？\n` +
      (unapplyForm.delete_empty_racks ? '• 删除绑定该模板且无设备的机柜\n' : '') +
      (unapplyForm.detach_template ? '• 其余机柜解除模板关联（保留实例）' : ''),
    '取消模板应用',
    { type: 'warning' },
  )
  unapplyLoading.value = true
  try {
    const result = await unapplyTemplateFromRoom(unapplyForm.template_id, layoutRoom.value.id, {
      deleteEmptyRacks: unapplyForm.delete_empty_racks,
      detachTemplate: unapplyForm.detach_template,
    })
    ElMessage.success(
      `完成：删除 ${result.deleted}，解除关联 ${result.detached}` +
        (result.skipped ? `，跳过 ${result.skipped}` : ''),
    )
    if (result.errors?.length) {
      ElMessage.warning(result.errors.slice(0, 3).join('；'))
    }
    unapplyVisible.value = false
    await Promise.all([refreshTemplates(), reloadLayoutRacks()])
    if (layoutDisplayMode.value === 'full') {
      await loadFullLayoutDetails()
    }
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '取消应用失败')
  } finally {
    unapplyLoading.value = false
  }
}

async function openLayout(row: Room, focusRackId?: string | null) {
  layoutVisible.value = true
  layoutDisplayMode.value = 'simple'
  clearSelection()
  layoutDetails.value = {}
  pendingFocusRackId.value = focusRackId || null
  layoutLoading.value = true
  try {
    // 拉取最新机房排柜/编号/立柱，保证布局图与编辑设置一致
    try {
      layoutRoom.value = await getRoom(row.id)
    } catch {
      layoutRoom.value = row
    }
    await reloadLayoutRacks()
    if (focusRackId) {
      const rack = layoutRacks.value.find((r) => r.id === focusRackId)
      if (rack) {
        await nextTick()
        await openRackZoom(rack)
      }
    }
  } catch (error: unknown) {
    layoutRacks.value = []
    const err = error as {
      response?: { data?: { message?: string; detail?: string } }
      message?: string
    }
    ElMessage.error(err.response?.data?.message || err.response?.data?.detail || err.message || '加载机柜数据失败')
  } finally {
    layoutLoading.value = false
  }
}

async function openRackZoom(rack: Rack) {
  rackZoomRack.value = rack
  rackZoomVisible.value = true
  rackZoomLoading.value = true
  rackZoomSlots.value = []
  rackZoomPower.value = 0
  try {
    const data = await getRackLayout(rack.id)
    rackZoomRack.value = data.rack
    rackZoomSlots.value = data.slots || []
    rackZoomPower.value = data.total_power || 0
  } catch (error: unknown) {
    rackZoomVisible.value = false
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '加载机柜正面布局失败')
  } finally {
    rackZoomLoading.value = false
  }
}

async function consumeLayoutQuery() {
  const openLayoutId = typeof route.query.open_layout === 'string' ? route.query.open_layout : ''
  const rackId = typeof route.query.rack_id === 'string' ? route.query.rack_id : ''
  if (!openLayoutId) return

  let room = tableData.value.find((r) => r.id === openLayoutId) || null
  if (!room) {
    try {
      const data = await listRooms({
        page: 1,
        page_size: 200,
        datacenter_id: filterDcId.value || undefined,
      })
      room = data.items.find((r) => r.id === openLayoutId) || null
    } catch {
      room = null
    }
  }
  if (!room) {
    ElMessage.warning('未找到对应机房')
  } else {
    await openLayout(room, rackId || null)
  }

  const nextQuery = { ...route.query }
  delete nextQuery.open_layout
  delete nextQuery.rack_id
  await router.replace({ name: 'rooms-manage', query: nextQuery })
}

function open3DSimulate(row: Room) {
  void router.push({ name: 'rooms-simulate', query: { room_id: row.id } })
}

async function handleDelete(row: Room) {
  const label = [row.location || row.datacenter_name, row.building_no, row.room_no || row.name]
    .filter(Boolean)
    .join('-')
  await ElMessageBox.confirm(`确定删除机房「${label}」吗？`, '确认删除', { type: 'warning' })
  await deleteRoom(row.id)
  ElMessage.success('删除成功')
  await loadData()
}

onMounted(async () => {
  await syncFilterFromRoute()
  await loadDatacenters()
  await Promise.all([loadData(), refreshTemplates()])
  await consumeLayoutQuery()
})

watch(
  () => route.query.datacenter_id,
  async () => {
    const next = readRouteDatacenterId()
    if (next === filterDcId.value) return
    filterDcId.value = next
    pagination.page = 1
    await loadData()
  },
)
</script>

<template>
  <div class="page">
    <section class="hero">
      <div class="hero-copy">
        <h2>机房管理</h2>
        <p v-if="hasDcFilter">
          当前数据中心：
          <strong>{{ filteredDatacenter ? filteredDatacenter.name : '已指定' }}</strong>
          <template v-if="filteredDatacenter?.location">（{{ filteredDatacenter.location }}）</template>
          。仅显示该数据中心下属机房，其他数据中心机房不会出现在本列表。
        </p>
        <p v-else>
          主菜单进入：显示全部机房。可通过「数据中心」筛选，单独查看某一数据中心下的机房与详细信息。
        </p>
      </div>
      <div class="hero-actions">
        <el-button @click="$router.push('/datacenters')">数据中心</el-button>
        <el-button v-if="hasDcFilter" @click="clearDatacenterFilter">显示全部机房</el-button>
        <el-button @click="$router.push('/rooms/simulate')">3D 仿真</el-button>
        <el-button v-if="canCreate" type="primary" @click="openCreate">新建机房</el-button>
      </div>
    </section>

    <section class="overview-panel">
      <div class="overview-metrics">
        <article class="metric">
          <span class="metric-label">机房</span>
          <strong class="metric-value">{{ pageStats.roomCount }}</strong>
          <span class="metric-hint">{{ hasDcFilter ? '本数据中心' : `${pageStats.dcCount} 个中心` }}</span>
        </article>
        <article class="metric">
          <span class="metric-label">已建机柜</span>
          <strong class="metric-value">{{ pageStats.rackCount }}</strong>
          <span class="metric-hint">容量 {{ pageStats.capacity }} · 占用 {{ pageStats.util }}%</span>
        </article>
        <article class="metric">
          <span class="metric-label">已上架</span>
          <strong class="metric-value accent">{{ pageStats.usedCount }}</strong>
          <span class="metric-hint">上架率 {{ pageStats.mountUtil }}%</span>
        </article>
        <article class="metric">
          <span class="metric-label">空余机柜位</span>
          <strong class="metric-value">{{ pageStats.freeCount }}</strong>
          <span class="metric-hint">容量 − 已建</span>
        </article>
        <article class="metric">
          <span class="metric-label">总功耗</span>
          <strong class="metric-value">{{ formatPower(pageStats.totalPower) }}</strong>
          <span class="metric-hint">设备额定功率合计</span>
        </article>
      </div>
      <div class="overview-legend">
        <div class="legend-inline">
          <span class="legend-title">属性</span>
          <span
            v-for="item in ATTR_PRESETS"
            :key="item.value"
            class="tag-pill sm"
            :class="`attr-${item.value}`"
          >{{ item.label }}</span>
          <span class="tag-pill sm attr-custom">自定义</span>
        </div>
        <div class="legend-inline">
          <span class="legend-title">重要性</span>
          <span
            v-for="item in IMPORTANCE_OPTIONS"
            :key="item.value"
            class="tag-pill sm"
            :class="`importance-${item.value}`"
          >{{ item.label }}</span>
        </div>
        <p class="legend-note">
          统计来自当前列表机房的机柜上架数据；重要性可在列表直接修改，机房属性请在编辑中调整。
        </p>
      </div>
    </section>

    <el-card shadow="never" class="list-card">
      <template #header>
        <div class="card-header">
          <span>{{ hasDcFilter ? '所选数据中心机房' : '全部机房列表' }}</span>
          <div class="actions">
            <el-select
              :model-value="filterDcId || undefined"
              clearable
              filterable
              placeholder="全部数据中心"
              style="width: 240px"
              :disabled="!datacenters.length"
              @change="onFilterDcChange"
            >
              <el-option
                v-for="dc in datacenters"
                :key="dc.id"
                :label="datacenterLabel(dc)"
                :value="dc.id"
              />
            </el-select>
            <el-input
              v-model="keyword"
              placeholder="搜索门牌号"
              clearable
              style="width: 200px"
              @keyup.enter="loadData"
              @clear="loadData"
            />
            <el-button @click="loadData">搜索</el-button>
            <el-button @click="$router.push('/rooms/simulate')">3D 仿真</el-button>
            <el-button v-if="canCreate" type="primary" @click="openCreate">新建</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" stripe class="room-table">
        <el-table-column label="数据中心" min-width="150">
          <template #default="{ row }">
            {{ row.datacenter_name || row.location || '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="building_no" label="机房楼号" min-width="100" />
        <el-table-column label="门牌号" min-width="100">
          <template #default="{ row }">{{ row.room_no || row.name }}</template>
        </el-table-column>
        <el-table-column label="机房属性" min-width="180">
          <template #default="{ row }">
            <div class="attr-tags">
              <span
                v-for="attr in roomAttributes(row)"
                :key="attr"
                class="tag-pill sm"
                :class="ATTR_PRESETS.some((p) => p.value === attr) ? `attr-${attr}` : 'attr-custom'"
              >{{ attributeLabel(attr) }}</span>
              <span v-if="!roomAttributes(row).length" class="muted-text">—</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="重要性" width="112" align="center">
          <template #default="{ row }">
            <el-select
              v-if="canUpdate"
              :model-value="row.importance || 'medium'"
              size="small"
              class="meta-select"
              :class="`importance-${row.importance || 'medium'}`"
              :loading="metaSavingIds.has(row.id)"
              @change="(v: string | number) => onImportanceChange(row, String(v))"
            >
              <el-option
                v-for="item in IMPORTANCE_OPTIONS"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <span v-else class="tag-pill" :class="`importance-${row.importance || 'medium'}`">
              {{ importanceLabel(row.importance) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="机柜数量" width="96" align="center">
          <template #default="{ row }">
            <span class="count-pill">{{ row.rack_count ?? 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="使用" width="80" align="center">
          <template #default="{ row }">{{ row.used_count ?? 0 }}</template>
        </el-table-column>
        <el-table-column label="空余" width="80" align="center">
          <template #default="{ row }">{{ row.free_count ?? 0 }}</template>
        </el-table-column>
        <el-table-column label="总功耗" width="100" align="center">
          <template #default="{ row }">{{ formatPower(row.total_power) }}</template>
        </el-table-column>
        <el-table-column label="容量" width="80" align="center">
          <template #default="{ row }">
            <span class="count-pill muted">{{ roomCapacity(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="网格" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="grid-pill">{{ roomGridLabel(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="120" show-overflow-tooltip />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openLayout(row)">布局图</el-button>
            <el-button type="primary" link @click="open3DSimulate(row)">3D</el-button>
            <el-button v-if="canUpdate" type="primary" link @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canDelete" type="danger" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          layout="total, prev, pager, next"
          :total="pagination.total"
          @change="loadData"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="layoutVisible"
      :title="layoutRoom ? `机房布局图 - ${roomTitle(layoutRoom)}` : '机房布局图'"
      fullscreen
      destroy-on-close
      class="layout-dialog"
    >
      <div v-loading="layoutLoading || fullLayoutLoading" class="floorplan">
        <div class="floorplan-toolbar">
          <div class="floorplan-summary">
            <span>机柜位 {{ layoutStats.total }}</span>
            <span>已建 {{ layoutStats.occupied }}</span>
            <span>未建 {{ layoutStats.free }}</span>
            <span v-if="layoutStats.pillars">立柱 {{ layoutStats.pillars }}</span>
          </div>
          <div class="floorplan-actions">
            <el-radio-group v-model="layoutDisplayMode" @change="onLayoutModeChange">
              <el-radio-button value="simple">简单布局</el-radio-button>
              <el-radio-button value="full">完整机柜</el-radio-button>
            </el-radio-group>
            <el-dropdown trigger="click" :disabled="exportLoading" @command="handleExportLayouts">
              <el-button type="success" plain :loading="exportLoading">
                导出布局图
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="excel">导出全部机柜 Excel</el-dropdown-item>
                  <el-dropdown-item command="pdf">导出全部机柜 PDF</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button
              v-if="layoutRoom"
              type="primary"
              plain
              @click="open3DSimulate(layoutRoom)"
            >
              3D 仿真
            </el-button>
            <el-button v-if="canApplyRack" type="primary" plain @click="openApplyTemplate">
              应用机柜模板
            </el-button>
            <el-button
              v-if="canApplyRack"
              :disabled="!roomAppliedTemplates.length"
              @click="openUnapplyTemplate"
            >
              取消模板
            </el-button>
          </div>
        </div>

        <div v-if="layoutDisplayMode === 'simple'" class="usage-toolbar">
          <div class="usage-toolbar-main">
            <span class="usage-label">用途色标</span>
            <el-select v-model="activePresetId" size="small" style="width: 150px">
              <el-option
                v-for="p in usagePresets"
                :key="p.id"
                :label="p.label"
                :value="p.id"
              >
                <span class="preset-option">
                  <i class="preset-swatch" :style="{ background: p.color }" />
                  {{ p.label }}
                </span>
              </el-option>
            </el-select>
            <el-button
              v-if="canApplyRack"
              size="small"
              type="primary"
              :loading="usageApplyLoading"
              @click="applyUsageToSelection"
            >
              应用到选中
            </el-button>
            <el-button
              v-if="canApplyRack"
              size="small"
              :loading="usageApplyLoading"
              @click="clearUsageOnSelection"
            >
              清除用途
            </el-button>
            <el-button size="small" @click="openPresetDialog">自定义色标</el-button>
            <el-button size="small" @click="clearSelection">清空选择</el-button>
            <span class="usage-count">已选 {{ selectedSlotKeys.size }} 位 / 已建 {{ selectedBuiltRacks.length }}</span>
          </div>
          <div class="usage-presets-row">
            <span
              v-for="p in usagePresets"
              :key="`lg-${p.id}`"
              class="tag-pill sm"
              :style="{ background: p.color, borderColor: '#bbb', color: '#333' }"
            >{{ p.label }}</span>
          </div>
        </div>

        <div v-if="layoutDisplayMode === 'simple'" class="floorplan-legend">
          <span><i class="dot empty" />未建柜（机房已编号）</span>
          <span><i class="dot idle" />已建空载</span>
          <span><i class="dot low" />利用率&lt;40%</span>
          <span><i class="dot mid" />40%–80%</span>
          <span><i class="dot high" />≥80%</span>
          <span><i class="dot pillar" />立柱（空白占位）</span>
          <span class="legend-tip">布局严格按机房排数/每排格数（含立柱）与连续编号展示，不额外增加占位</span>
        </div>

        <div
          v-if="layoutRows.length && layoutDisplayMode === 'simple'"
          class="floorplan-map"
          @dragstart.prevent
        >
          <div v-for="row in layoutRows" :key="row.row" class="floorplan-row">
            <div class="floorplan-row-label">
              第 {{ row.row }} 排
              <span class="floorplan-row-meta">机柜 {{ row.rackCount }} / 格 {{ row.slots.length }}</span>
            </div>
            <div class="floorplan-slots">
              <template v-for="slot in row.slots" :key="`${slot.row}-${slot.col}`">
                <div v-if="slot.kind === 'pillar'" class="pillar-placeholder" title="立柱占位">
                  <div class="pillar-blank" />
                </div>
                <button
                  v-else
                  type="button"
                  class="rack-cell"
                  :class="[
                    utilizationClass(slot.rack),
                    {
                      clickable: true,
                      selected: isSlotSelected(slot.row, slot.col),
                    },
                  ]"
                  :style="rackCellStyle(slot.rack)"
                  @mousedown="onSlotPointerDown(slot, $event)"
                  @mouseenter="onSlotPointerEnter(slot)"
                  @click="onSlotClick(slot)"
                  @dblclick="onSlotDblClick(slot)"
                >
                  <div class="rack-code">{{ slot.code || slot.rack?.code || '—' }}</div>
                  <div class="rack-meta">
                    <template v-if="slot.rack">
                      <div v-if="slot.rack.app_usage" class="rack-usage">{{ slot.rack.app_usage }}</div>
                      {{ slot.rack.device_count ?? 0 }}台 · 空闲{{ slot.rack.free_u }}U · {{ slot.rack.utilization }}%
                    </template>
                    <template v-else>未建柜</template>
                  </div>
                </button>
              </template>
            </div>
          </div>
        </div>

        <div v-else-if="layoutRows.length && layoutDisplayMode === 'full'" class="floorplan-map floorplan-map-full">
          <div v-for="row in layoutRows" :key="row.row" class="floorplan-row floorplan-row-full">
            <div class="floorplan-row-label">
              第 {{ row.row }} 排
              <span class="floorplan-row-meta">机柜 {{ row.rackCount }} / 格 {{ row.slots.length }}</span>
            </div>
            <div class="floorplan-slots floorplan-slots-full">
              <template v-for="slot in row.slots" :key="`${slot.row}-${slot.col}-full`">
                <div v-if="slot.kind === 'pillar'" class="rack-cell-full pillar-placeholder-full" title="立柱占位">
                  <div class="pillar-blank" />
                </div>
                <div
                  v-else
                  class="rack-cell-full"
                  :class="{ empty: !slot.rack }"
                >
                  <template v-if="slot.rack">
                    <RackCabinet
                      v-if="layoutDetails[slot.rack.id]"
                      :code="slot.code || slot.rack.code"
                      :total-u="slot.rack.total_u"
                      :slots="layoutDetails[slot.rack.id].slots"
                      :total-power="layoutDetails[slot.rack.id].totalPower"
                      :visual-style="(slot.rack.visual_style as any) || 'classic'"
                      compact
                    />
                    <div v-else class="rack-cell-loading">加载中…</div>
                  </template>
                  <div v-else class="rack-cell-empty">
                    <div class="rack-code">{{ slot.code || '—' }}</div>
                    <div class="rack-meta">未建柜</div>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无布局数据" />
      </div>
      <template #footer>
        <el-button type="primary" @click="layoutVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="rackZoomVisible"
      :title="`机柜正面布局 - ${rackZoomRack?.code || ''}`"
      width="520px"
      top="6vh"
      destroy-on-close
      append-to-body
      class="rack-zoom-dialog"
    >
      <div v-loading="rackZoomLoading" class="rack-zoom-panel">
        <div v-if="rackZoomRack" class="rack-zoom-meta">
          <span>{{ rackZoomRack.name }}</span>
          <span>位置 R{{ rackZoomRack.row_no }}-C{{ rackZoomRack.column_no }}</span>
          <span>已用 {{ rackZoomRack.occupied_u }}/{{ rackZoomRack.total_u }}U</span>
          <span>空闲 {{ rackZoomRack.free_u }}U</span>
          <span>利用率 {{ rackZoomRack.utilization }}%</span>
          <span>设备 {{ rackZoomRack.device_count }} 台</span>
          <span>功率 {{ Math.round(rackZoomPower) }} W</span>
        </div>
        <div class="rack-zoom-cabinet">
          <RackCabinet
            v-if="rackZoomRack && !rackZoomLoading"
            :code="rackZoomRack.code"
            :total-u="rackZoomRack.total_u"
            :slots="rackZoomSlots"
            :total-power="rackZoomPower"
            :visual-style="(rackZoomRack.visual_style as any) || 'classic'"
          />
        </div>
      </div>
      <template #footer>
        <el-button type="primary" @click="rackZoomVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="applyVisible" title="应用机柜模板" width="520px">
      <el-form label-width="110px">
        <el-form-item label="目标机房">
          <el-input :model-value="layoutRoom ? roomTitle(layoutRoom) : ''" disabled />
        </el-form-item>
        <el-form-item label="样式模板" required>
          <el-select v-model="applyForm.template_id" style="width: 100%">
            <el-option
              v-for="t in templates"
              :key="t.id"
              :label="`${t.name}（${t.total_u}U）`"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="空闲位">
          <el-checkbox v-model="applyForm.fill_empty_slots">为空闲机柜位创建机柜并套用模板</el-checkbox>
          <div class="field-hint">开启后：按机房排柜布局补齐有效机柜位（跳过立柱空白占位）</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="applyVisible = false">取消</el-button>
        <el-button type="primary" :loading="applyLoading" @click="submitApplyTemplate">开始应用</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="unapplyVisible" title="取消机柜模板应用" width="520px">
      <el-form label-width="110px">
        <el-form-item label="目标机房">
          <el-input :model-value="layoutRoom ? roomTitle(layoutRoom) : ''" disabled />
        </el-form-item>
        <el-form-item label="样式模板" required>
          <el-select v-model="unapplyForm.template_id" style="width: 100%">
            <el-option
              v-for="t in unapplyTemplateOptions"
              :key="t.id"
              :label="t.name"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="处理方式">
          <el-checkbox v-model="unapplyForm.delete_empty_racks">
            删除绑定该模板且无设备的机柜
          </el-checkbox>
          <el-checkbox v-model="unapplyForm.detach_template">
            对其余机柜解除模板关联（保留机柜实例与规格）
          </el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="unapplyVisible = false">关闭</el-button>
        <el-button type="warning" :loading="unapplyLoading" @click="submitUnapplyTemplate">
          确认取消应用
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="presetDialogVisible" title="自定义机柜用途色标" width="560px" append-to-body>
      <p class="field-hint" style="margin-bottom: 12px">
        色标用于简单布局着色，提示设备部署的应用类型；可自由增删改名称与颜色。
      </p>
      <div v-for="(item, index) in presetDraft" :key="item.id" class="preset-edit-row">
        <el-color-picker v-model="item.color" size="small" />
        <el-input v-model="item.label" placeholder="用途名称" />
        <el-button type="danger" link @click="removePresetDraft(index)">删除</el-button>
      </div>
      <el-button type="primary" plain @click="addPresetDraft">新增用途</el-button>
      <template #footer>
        <el-button @click="presetDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="savePresetDialog">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑机房' : '新建机房'"
      width="920px"
      class="room-form-dialog"
      destroy-on-close
    >
      <el-steps
        v-if="!editingId"
        :active="createStep"
        finish-status="success"
        align-center
        class="create-steps"
      >
        <el-step v-for="item in CREATE_STEPS" :key="item.title" :title="item.title" />
      </el-steps>

      <el-form label-width="118px" class="room-form">
        <!-- Step 1 / Edit section: 基础信息 -->
        <section v-show="editingId || createStep === 0" class="form-section">
          <h4 v-if="editingId" class="section-title">基础信息</h4>
          <el-form-item label="数据中心" required>
            <el-select
              v-model="form.datacenter_id"
              placeholder="选择所属数据中心"
              style="width: 100%"
              :disabled="!!editingId || hasDcFilter"
              filterable
            >
              <el-option
                v-for="dc in hasDcFilter
                  ? datacenters.filter((d) => d.id === filterDcId)
                  : datacenters"
                :key="dc.id"
                :label="datacenterLabel(dc)"
                :value="dc.id"
              />
            </el-select>
            <div v-if="hasDcFilter" class="field-hint">
              当前从「{{ filteredDatacenter?.name || '所选数据中心' }}」进入，新建机房将归属该数据中心
            </div>
          </el-form-item>
          <el-form-item label="机房楼号" required>
            <el-input v-model="form.building_no" placeholder="例如：A栋" :disabled="!!editingId" />
          </el-form-item>
          <el-form-item label="机房门牌号" required>
            <el-input v-model="form.room_no" placeholder="例如：101" />
          </el-form-item>
          <el-form-item label="机房属性">
            <div class="attr-editor">
              <div class="attr-presets">
                <el-check-tag
                  v-for="item in ATTR_PRESETS"
                  :key="item.value"
                  :checked="hasPresetAttr(item.value)"
                  @change="() => togglePresetAttr(item.value)"
                >
                  {{ item.label }}
                </el-check-tag>
              </div>
              <div class="attr-custom-row">
                <el-input
                  v-model="customAttrInput"
                  placeholder="自定义属性，回车添加"
                  maxlength="40"
                  @keyup.enter="addCustomAttribute"
                />
                <el-button @click="addCustomAttribute">添加</el-button>
              </div>
              <div v-if="customAttributes().length" class="attr-tags">
                <el-tag
                  v-for="attr in customAttributes()"
                  :key="attr"
                  closable
                  type="info"
                  @close="removeAttribute(attr)"
                >
                  {{ attr }}
                </el-tag>
              </div>
            </div>
          </el-form-item>
          <el-form-item label="重要性" required>
            <el-select v-model="form.importance" style="width: 100%">
              <el-option
                v-for="item in IMPORTANCE_OPTIONS"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model="form.description" type="textarea" :rows="2" />
          </el-form-item>
        </section>

        <!-- Step 2: 机房轮廓 -->
        <section v-show="editingId || createStep === 1" class="form-section">
          <h4 v-if="editingId" class="section-title">机房轮廓</h4>
          <el-form-item label="长（列网格）" required>
            <el-input-number v-model="form.outline_cols" :min="1" :max="50" style="width: 100%" />
          </el-form-item>
          <el-form-item label="宽（排网格）" required>
            <el-input-number v-model="form.outline_rows" :min="1" :max="50" style="width: 100%" />
          </el-form-item>
          <el-form-item label="轮廓预览">
            <div class="outline-preview-wrap">
              <div class="outline-meta">长 {{ form.outline_cols }} × 宽 {{ form.outline_rows }} 网格</div>
              <div class="outline-preview-frame">
                <div
                  class="outline-grid"
                  :style="{
                    gridTemplateColumns: `repeat(${Math.max(form.outline_cols, 1)}, 1fr)`,
                    gridTemplateRows: `repeat(${Math.max(form.outline_rows, 1)}, 1fr)`,
                  }"
                >
                  <div
                    v-for="idx in Math.max(form.outline_rows, 1) * Math.max(form.outline_cols, 1)"
                    :key="idx"
                    class="outline-cell"
                  />
                </div>
              </div>
            </div>
          </el-form-item>
        </section>

        <!-- Step 3: 机柜编排 -->
        <section v-show="editingId || createStep === 2" class="form-section">
          <h4 v-if="editingId" class="section-title">机柜编排</h4>
          <el-form-item label="编排方式" required>
            <el-radio-group v-model="form.layout_mode">
              <el-radio value="auto">按排×列</el-radio>
              <el-radio value="manual">逐排指定</el-radio>
            </el-radio-group>
          </el-form-item>

          <template v-if="form.layout_mode === 'auto'">
            <el-form-item label="机柜排数 a" required>
              <el-input-number
                v-model="form.rack_rows"
                :min="1"
                :max="form.outline_rows"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="每排机柜 b" required>
              <el-input-number
                v-model="form.rack_columns"
                :min="1"
                :max="form.outline_cols"
                style="width: 100%"
              />
            </el-form-item>
          </template>

          <template v-else>
            <el-form-item label="排布局" required>
              <div class="manual-layout">
                <div class="field-hint" style="margin-bottom: 8px">
                  每排机柜数 ≤ 轮廓长向 {{ form.outline_cols }}；排数 ≤ 轮廓宽向 {{ form.outline_rows }}。
                </div>
                <div v-for="(_, index) in form.row_layout" :key="index" class="manual-row">
                  <span class="row-label">第 {{ index + 1 }} 排</span>
                  <el-input-number
                    v-model="form.row_layout[index]"
                    :min="1"
                    :max="form.outline_cols"
                  />
                  <span class="row-unit">柜</span>
                  <el-button type="danger" link @click="removeManualRow(index)">删除</el-button>
                </div>
                <el-button
                  type="primary"
                  plain
                  :disabled="form.row_layout.length >= form.outline_rows"
                  @click="addManualRow"
                >
                  增加一排
                </el-button>
              </div>
            </el-form-item>
          </template>

          <el-form-item label="容量摘要">
            <el-input :model-value="layoutSummary" disabled />
          </el-form-item>
        </section>

        <!-- Step 4: 编号 -->
        <section v-show="editingId || createStep === 3" class="form-section">
          <h4 v-if="editingId" class="section-title">编号设置</h4>
          <el-form-item label="编号前缀" required>
            <el-input
              v-model="form.code_prefix"
              placeholder="单个字母如 A，或范围如 A-D / A-BZ"
              maxlength="20"
            />
            <div class="field-hint">
              两种编号方式均需先定义前缀。单个字母按排递增；范围需覆盖机柜排数。
            </div>
            <div v-if="form.code_mode === 'auto'" class="field-hint">{{ rowPrefixHint }}</div>
          </el-form-item>

          <el-form-item label="编号方式" required>
            <el-radio-group v-model="form.code_mode">
              <el-radio value="auto">自动编号</el-radio>
              <el-radio value="custom">手动编号</el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item v-if="form.code_mode === 'custom'" label="逐位编号" required>
            <div class="slot-codes">
              <div class="slot-codes-toolbar">
                <el-button size="small" type="primary" plain @click="renumberSkippingPillars">
                  重排连续编号
                </el-button>
                <span class="field-hint" style="margin: 0">
                  可增删机柜格；点「立柱」以空白框占位（自动在排尾补一机柜格）
                </span>
              </div>
              <div v-for="(kinds, rowIdx) in form.slot_kinds" :key="rowIdx" class="slot-row">
                <div class="slot-row-title">
                  第 {{ rowIdx + 1 }} 排
                  <span class="slot-row-meta">
                    网格 {{ kinds.length }} · 机柜 {{ rowRackCount(rowIdx) }}
                    <template v-if="kinds.length !== rowRackCount(rowIdx)">
                      · 立柱 {{ kinds.length - rowRackCount(rowIdx) }}
                    </template>
                  </span>
                  <el-button
                    size="small"
                    link
                    type="primary"
                    :disabled="kinds.length >= form.outline_cols"
                    @click="addSlotCell(rowIdx)"
                  >
                    添加格
                  </el-button>
                </div>
                <div class="slot-inputs">
                  <div
                    v-for="(kind, colIdx) in kinds"
                    :key="`${rowIdx}-${colIdx}`"
                    class="slot-cell"
                    :class="{ pillar: kind === 'pillar' }"
                  >
                    <div
                      v-if="kind === 'pillar'"
                      class="slot-blank"
                      title="立柱空白占位，点击可改回机柜"
                      @click="toggleSlotPillar(rowIdx, colIdx)"
                    />
                    <el-input
                      v-else
                      v-model="form.slot_codes[rowIdx][colIdx]"
                      :placeholder="`列${colIdx + 1}`"
                      size="small"
                      style="width: 88px"
                    />
                    <div class="slot-cell-actions">
                      <el-button
                        size="small"
                        link
                        :type="kind === 'pillar' ? 'warning' : 'primary'"
                        @click="toggleSlotPillar(rowIdx, colIdx)"
                      >
                        {{ kind === 'pillar' ? '改回机柜' : '立柱' }}
                      </el-button>
                      <el-button
                        size="small"
                        link
                        type="danger"
                        @click="deleteSlotCell(rowIdx, colIdx)"
                      >
                        删除
                      </el-button>
                    </div>
                  </div>
                  <div
                    v-for="pad in Math.max(0, form.outline_cols - kinds.length)"
                    :key="`pad-${rowIdx}-${pad}`"
                    class="slot-cell aisle"
                    title="轮廓内未编排（走廊）"
                  >
                    <div class="slot-aisle">走廊</div>
                  </div>
                </div>
              </div>
            </div>
          </el-form-item>

          <el-form-item label="编号预览">
            <el-input :model-value="codePreview" disabled />
          </el-form-item>
        </section>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <template v-if="!editingId">
          <el-button v-if="createStep > 0" @click="prevCreateStep">上一步</el-button>
          <el-button
            v-if="createStep < CREATE_STEPS.length - 1"
            type="primary"
            @click="nextCreateStep"
          >
            下一步
          </el-button>
          <el-button v-else type="primary" @click="handleSubmit">创建</el-button>
        </template>
        <el-button v-else type="primary" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hero {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 22px 24px;
  border-radius: 12px;
  border: 1px solid #d7e3ef;
  background:
    linear-gradient(135deg, rgba(232, 243, 255, 0.95), rgba(245, 250, 255, 0.9)),
    radial-gradient(ellipse at 90% 10%, rgba(58, 160, 255, 0.18), transparent 55%);
}

.hero-copy h2 {
  margin: 0 0 6px;
  font-size: 22px;
  color: #1f3348;
}

.hero-copy p {
  margin: 0;
  max-width: 560px;
  font-size: 13px;
  line-height: 1.55;
  color: #6b7c8f;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.overview-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid #d7e3ef;
  background:
    linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
}

.overview-metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}

.metric {
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid #e4ebf3;
  background: #fff;
  min-width: 0;
}

.metric-label {
  display: block;
  font-size: 11px;
  color: #8aa0b5;
  letter-spacing: 0.02em;
}

.metric-value {
  display: block;
  margin-top: 4px;
  font-size: 22px;
  line-height: 1.15;
  color: #1f3348;
  font-variant-numeric: tabular-nums;
}

.metric-value.accent {
  color: #1d6b4f;
}

.metric-hint {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: #909399;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.overview-legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
  padding-top: 2px;
  border-top: 1px dashed #e4ebf3;
}

.legend-inline {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 6px;
}

.legend-title {
  font-size: 11px;
  color: #6b7c8f;
  margin-right: 2px;
}

.legend-note {
  margin: 0;
  margin-left: auto;
  font-size: 11px;
  color: #909399;
}

.tag-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  padding: 1px 7px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.4;
  border: 1px solid transparent;
}

.tag-pill.sm {
  min-width: 28px;
  padding: 0 6px;
  font-size: 10px;
  line-height: 1.6;
}

.meta-select {
  width: 108px;
}

.meta-select :deep(.el-select__wrapper) {
  min-height: 26px;
  font-size: 12px;
  font-weight: 600;
}

.meta-select.purpose-production :deep(.el-select__wrapper) {
  background: #e8f7ef;
  box-shadow: 0 0 0 1px #b7e0c8 inset;
}
.meta-select.purpose-test :deep(.el-select__wrapper) {
  background: #eaf2fc;
  box-shadow: 0 0 0 1px #bdd3ef inset;
}
.meta-select.purpose-backup :deep(.el-select__wrapper) {
  background: #fbf3df;
  box-shadow: 0 0 0 1px #ebd9a8 inset;
}
.meta-select.purpose-network :deep(.el-select__wrapper) {
  background: #e6f6f8;
  box-shadow: 0 0 0 1px #b5dde4 inset;
}
.meta-select.purpose-storage :deep(.el-select__wrapper) {
  background: #f1edfa;
  box-shadow: 0 0 0 1px #d2c8eb inset;
}
.meta-select.purpose-other :deep(.el-select__wrapper) {
  background: #eef2f6;
  box-shadow: 0 0 0 1px #d5dde6 inset;
}
.meta-select.importance-critical :deep(.el-select__wrapper) {
  background: #c0392b;
  box-shadow: 0 0 0 1px #a93226 inset;
  color: #fff;
}
.meta-select.importance-critical :deep(.el-select__selected-item),
.meta-select.importance-critical :deep(.el-select__caret) {
  color: #fff;
}
.meta-select.importance-high :deep(.el-select__wrapper) {
  background: #ffedd5;
  box-shadow: 0 0 0 1px #fdba74 inset;
}
.meta-select.importance-medium :deep(.el-select__wrapper) {
  background: #fef9c3;
  box-shadow: 0 0 0 1px #fde047 inset;
}
.meta-select.importance-low :deep(.el-select__wrapper) {
  background: #f1f5f9;
  box-shadow: 0 0 0 1px #cbd5e1 inset;
}

.purpose-production {
  color: #1d6b4f;
  background: #e8f7ef;
  border-color: #b7e0c8;
}
.purpose-test {
  color: #2f5f9a;
  background: #eaf2fc;
  border-color: #bdd3ef;
}
.purpose-backup {
  color: #7a5a16;
  background: #fbf3df;
  border-color: #ebd9a8;
}
.purpose-network {
  color: #0f6b7a;
  background: #e6f6f8;
  border-color: #b5dde4;
}
.purpose-storage {
  color: #5b4a9a;
  background: #f1edfa;
  border-color: #d2c8eb;
}
.purpose-other {
  color: #5c6b7a;
  background: #eef2f6;
  border-color: #d5dde6;
}

.importance-critical {
  color: #fff;
  background: #c0392b;
  border-color: #a93226;
}
.importance-high {
  color: #9a3412;
  background: #ffedd5;
  border-color: #fdba74;
}
.importance-medium {
  color: #854d0e;
  background: #fef9c3;
  border-color: #fde047;
}
.importance-low {
  color: #475569;
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.count-pill.muted {
  background: #f2f5f8;
  color: #7a8b9c;
}

.list-card {
  border-radius: 10px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.grid-pill,
.count-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f0f5fa;
  color: #3a5570;
  font-size: 12px;
  font-weight: 600;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

@media (max-width: 1100px) {
  .overview-metrics {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .overview-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .legend-note {
    margin-left: 0;
    width: 100%;
  }
}

.field-hint {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}

.manual-layout {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.manual-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.row-label {
  width: 64px;
  color: #606266;
}

.row-unit {
  color: #909399;
  font-size: 13px;
}

.slot-codes {
  width: 100%;
  max-height: 320px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 8px 0;
}

.slot-codes-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.slot-row-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
}

.slot-row-meta {
  color: #909399;
  font-size: 12px;
  font-weight: 400;
}

.slot-inputs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.slot-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 4px;
  border-radius: 6px;
  border: 1px solid transparent;
}

.slot-cell.pillar {
  background: transparent;
  border-color: transparent;
}

.slot-blank {
  width: 88px;
  height: 24px;
  box-sizing: border-box;
  border: 1.5px dashed #c0c4cc;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
}

.slot-blank:hover {
  border-color: #909399;
  background: #fafafa;
}

.slot-cell-actions {
  display: flex;
  gap: 2px;
}

.floorplan-legend .dot.pillar {
  background: #fff;
  border: 1.5px dashed #c0c4cc;
}

.pillar-placeholder,
.pillar-placeholder-full {
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  user-select: none;
  background: #fafafa;
  border: 1.5px dashed #c0c4cc;
  box-shadow: none;
  box-sizing: border-box;
}

.pillar-placeholder {
  flex: 0 0 108px;
  width: 108px;
  min-height: 80px;
  border-radius: 6px;
  padding: 8px;
}

.pillar-placeholder-full {
  min-width: 120px;
  min-height: 160px;
  border-radius: 8px;
}

.pillar-blank {
  width: 70%;
  height: 70%;
  min-height: 36px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  background: #fff;
}

.floorplan {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: calc(100vh - 160px);
}

:deep(.layout-dialog .el-dialog__body) {
  padding-top: 12px;
}

.floorplan-summary {
  display: flex;
  gap: 20px;
  color: #606266;
  font-size: 14px;
}

.floorplan-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.floorplan-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.usage-toolbar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid #e4ebf3;
  border-radius: 8px;
  background: #f7fbff;
}

.usage-toolbar-main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.usage-label {
  font-size: 12px;
  color: #3a5570;
  font-weight: 600;
}

.usage-count {
  font-size: 12px;
  color: #909399;
}

.usage-presets-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.preset-option {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.preset-swatch {
  width: 12px;
  height: 12px;
  border-radius: 2px;
  border: 1px solid #999;
  display: inline-block;
}

.preset-edit-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.rack-usage {
  font-size: 11px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 2px;
}

.floorplan-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: center;
  font-size: 12px;
  color: #909399;
}

.floorplan-legend .legend-tip {
  margin-left: auto;
  color: #a8abb2;
}

.floorplan-legend .dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  margin-right: 6px;
  vertical-align: middle;
}

.floorplan-legend .dot.empty,
.rack-cell.empty {
  background: #f5f7fa;
  border-color: #dcdfe6;
}

.floorplan-legend .dot.idle,
.rack-cell.idle {
  background: #ecf5ff;
  border-color: #b3d8ff;
}

.floorplan-legend .dot.low,
.rack-cell.low {
  background: #f0f9eb;
  border-color: #c2e7b0;
}

.floorplan-legend .dot.mid,
.rack-cell.mid {
  background: #fdf6ec;
  border-color: #f5dab1;
}

.floorplan-legend .dot.high,
.rack-cell.high {
  background: #fef0f0;
  border-color: #fbc4c4;
}

.floorplan-map {
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex: 1;
  overflow: auto;
  user-select: none;
}

.floorplan-row {
  display: flex;
  align-items: stretch;
  gap: 12px;
}

.floorplan-row-label {
  flex: 0 0 96px;
  font-weight: 600;
  color: #303133;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 2px;
  line-height: 1.3;
}

.floorplan-row-meta {
  font-size: 11px;
  font-weight: 400;
  color: #909399;
}

.floorplan-slots {
  display: flex;
  flex-wrap: nowrap;
  gap: 10px;
  flex: 1;
  min-width: 0;
  overflow-x: auto;
  padding-bottom: 4px;
}

.rack-cell {
  flex: 0 0 108px;
  width: 108px;
  min-height: 80px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-sizing: border-box;
  background: #fff;
  text-align: left;
  font: inherit;
  cursor: default;
}

.rack-cell.clickable {
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}

.rack-cell.clickable:hover {
  border-color: #409eff;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.18);
  transform: translateY(-1px);
}

.rack-cell.selected {
  outline: 2px solid #409eff;
  outline-offset: 1px;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.25);
  z-index: 1;
}

.rack-zoom-panel {
  min-height: 280px;
}

.rack-zoom-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #606266;
}

.rack-zoom-cabinet {
  display: flex;
  justify-content: center;
  max-height: 70vh;
  overflow: auto;
  padding-bottom: 8px;
}

.rack-code {
  font-weight: 600;
  font-size: 13px;
  color: #303133;
  word-break: break-all;
}

.rack-meta {
  font-size: 12px;
  color: #909399;
}

.floorplan-map-full {
  gap: 24px;
}

.floorplan-row-full {
  align-items: flex-start;
}

.floorplan-slots-full {
  align-items: flex-start;
  padding-bottom: 12px;
}

.rack-cell-full {
  flex: 0 0 300px;
  width: 300px;
  min-height: 120px;
}

.rack-cell-full.empty {
  display: flex;
  align-items: center;
  justify-content: center;
}

.rack-cell-empty {
  width: 100%;
  min-height: 100px;
  border: 1px dashed #dcdfe6;
  border-radius: 6px;
  padding: 12px;
  background: #fafafa;
  box-sizing: border-box;
}

.rack-cell-loading {
  padding: 24px;
  text-align: center;
  color: #909399;
  font-size: 13px;
}

.create-steps {
  margin-bottom: 18px;
}

.form-section + .form-section {
  margin-top: 8px;
}

.section-title {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: #334155;
}

.attr-editor {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.attr-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.attr-custom-row {
  display: flex;
  gap: 8px;
}

.attr-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.muted-text {
  color: #94a3b8;
  font-size: 13px;
}

.attr-internet {
  color: #0f766e;
  background: #ccfbf1;
  border-color: #99f6e4;
}

.attr-private_network {
  color: #1d4ed8;
  background: #dbeafe;
  border-color: #93c5fd;
}

.attr-custom {
  color: #475569;
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.outline-preview-wrap {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.outline-meta {
  font-size: 12px;
  color: #64748b;
}

.outline-preview-frame {
  width: 220px;
  height: 160px;
  flex-shrink: 0;
  padding: 6px;
  border: 2px solid #334155;
  border-radius: 4px;
  background: #f8fafc;
  box-sizing: border-box;
  overflow: hidden;
}

.outline-grid {
  width: 100%;
  height: 100%;
  display: grid;
  gap: 2px;
}

.outline-cell {
  min-width: 0;
  min-height: 0;
  border: 1px solid #cbd5e1;
  background: #fff;
  border-radius: 1px;
}

.slot-cell.aisle .slot-aisle {
  width: 88px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #94a3b8;
  background: repeating-linear-gradient(
    -45deg,
    #f8fafc,
    #f8fafc 4px,
    #e2e8f0 4px,
    #e2e8f0 8px
  );
  border: 1px dashed #cbd5e1;
  border-radius: 4px;
}
</style>
