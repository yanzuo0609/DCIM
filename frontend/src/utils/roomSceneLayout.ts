/** 3D 机房场景网格布局：排×列矩形 + 立柱/列头柜/电柜/空调柜/自定义模型 */

export type CellKind =
  | 'rack'
  | 'pillar'
  | 'pillar_round'
  | 'pdu'
  | 'power'
  | 'ac'
  | 'odf'
  | 'custom'
  | 'empty'

export type SceneMode = 'grid' | 'cells' | 'auto_middle'

/** 非机柜格附加属性（自定义模型名称/颜色等） */
export type CellProp = {
  label?: string
  color?: string
  customId?: string
}

export interface SceneLayout {
  mode: SceneMode
  rows: number
  cols: number
  cells: Record<string, CellKind[]>
  /** key: `${row}:${col}` */
  props?: Record<string, CellProp>
}

export interface RowCellPlan {
  kind: CellKind
  col: number
  rackIndex?: number
}

const FIXED: ReadonlySet<CellKind> = new Set([
  'pillar',
  'pillar_round',
  'pdu',
  'power',
  'ac',
  'odf',
  'custom',
])

const ALL_KINDS: ReadonlySet<string> = new Set([
  'rack',
  'pillar',
  'pillar_round',
  'pdu',
  'power',
  'ac',
  'odf',
  'custom',
  'empty',
])

export function isFixedKind(k: CellKind): boolean {
  return FIXED.has(k)
}

export function isPlaceableKind(k: string): k is CellKind {
  return (
    k === 'rack' ||
    k === 'pillar' ||
    k === 'pillar_round' ||
    k === 'pdu' ||
    k === 'power' ||
    k === 'ac' ||
    k === 'odf' ||
    k === 'custom'
  )
}

export function isPillarKind(k: CellKind): boolean {
  return k === 'pillar' || k === 'pillar_round'
}

export function cellKindLabel(kind: CellKind): string {
  switch (kind) {
    case 'pillar':
      return '方形立柱'
    case 'pillar_round':
      return '圆形立柱'
    case 'pdu':
      return '列头柜'
    case 'power':
      return '电柜'
    case 'ac':
      return '空调柜'
    case 'odf':
      return 'ODF架'
    case 'custom':
      return '自定义'
    case 'rack':
      return '机柜'
    default:
      return '空位'
  }
}

export function cellPropKey(row: number, col: number): string {
  return `${row}:${col}`
}

function normalizeKind(k: unknown): CellKind {
  if (typeof k === 'string' && ALL_KINDS.has(k)) return k as CellKind
  return 'empty'
}

function cloneProps(props?: Record<string, CellProp>): Record<string, CellProp> {
  if (!props) return {}
  const next: Record<string, CellProp> = {}
  for (const [k, v] of Object.entries(props)) {
    if (!v) continue
    next[k] = { ...v }
  }
  return next
}

function withProps(
  layout: SceneLayout,
  props: Record<string, CellProp> | undefined,
): SceneLayout {
  const cleaned: Record<string, CellProp> = {}
  for (const [k, v] of Object.entries(props || {})) {
    if (!v) continue
    if (!v.label && !v.color && !v.customId) continue
    cleaned[k] = { ...v }
  }
  return Object.keys(cleaned).length ? { ...layout, props: cleaned } : { ...layout, props: undefined }
}

/** 满格机柜矩形 */
export function buildFullRackGrid(rows: number, cols: number): SceneLayout {
  const r = Math.max(1, Math.min(50, Math.floor(rows) || 1))
  const c = Math.max(1, Math.min(50, Math.floor(cols) || 1))
  const cells: Record<string, CellKind[]> = {}
  for (let i = 1; i <= r; i++) {
    cells[String(i)] = Array.from({ length: c }, () => 'rack' as CellKind)
  }
  return { mode: 'grid', rows: r, cols: c, cells }
}

/**
 * 固定 pillar/pdu/power/ac/custom，其余空位内机柜左对齐连续排布。
 * 若被固定物分成多段，各段内各自左对齐。
 */
export function realignRow(kinds: CellKind[], rackCount?: number): CellKind[] {
  const span = kinds.length
  if (span === 0) return []
  const fixed = kinds.map((k) => (FIXED.has(k) ? k : null))
  const rackBudget =
    rackCount != null
      ? Math.max(0, rackCount)
      : kinds.filter((k) => k === 'rack').length

  const next: CellKind[] = Array.from({ length: span }, (_, i) =>
    fixed[i] ? (fixed[i] as CellKind) : 'empty',
  )

  let placed = 0
  let segStart = -1
  const flushSegment = (from: number, to: number) => {
    if (from < 0 || to <= from) return
    for (let i = from; i < to && placed < rackBudget; i++) {
      if (!fixed[i]) {
        next[i] = 'rack'
        placed += 1
      }
    }
  }

  for (let i = 0; i <= span; i++) {
    const isFixed = i < span && !!fixed[i]
    if (!isFixed && i < span) {
      if (segStart < 0) segStart = i
    } else {
      if (segStart >= 0) {
        flushSegment(segStart, i)
        segStart = -1
      }
    }
  }
  return next
}

export function ensureRowWidth(kinds: CellKind[], cols: number): CellKind[] {
  const c = Math.max(1, cols)
  const next = kinds.slice(0, c).map(normalizeKind)
  while (next.length < c) next.push('rack')
  return next
}

export function getRow(layout: SceneLayout, row: number): CellKind[] {
  const key = String(row)
  const raw = layout.cells[key] || []
  return ensureRowWidth(raw, layout.cols)
}

export function setRow(layout: SceneLayout, row: number, kinds: CellKind[]): SceneLayout {
  return {
    ...layout,
    cells: {
      ...layout.cells,
      [String(row)]: ensureRowWidth(kinds, layout.cols),
    },
  }
}

export function getCellProp(layout: SceneLayout, row: number, col: number): CellProp | undefined {
  return layout.props?.[cellPropKey(row, col)]
}

/** 应用排×列：裁剪或扩展；新格默认机柜（不重排已有格位） */
export function applyGridSize(
  layout: SceneLayout | null | undefined,
  rows: number,
  cols: number,
): SceneLayout {
  const r = Math.max(1, Math.min(50, Math.floor(rows) || 1))
  const c = Math.max(1, Math.min(50, Math.floor(cols) || 1))
  const prev = layout?.cells || {}
  const cells: Record<string, CellKind[]> = {}
  for (let i = 1; i <= r; i++) {
    const old = (prev[String(i)] || []).map(normalizeKind)
    cells[String(i)] = ensureRowWidth(
      old.length ? old : Array.from({ length: c }, () => 'rack' as CellKind),
      c,
    )
  }
  const props = cloneProps(layout?.props)
  for (const key of Object.keys(props)) {
    const [rs, cs] = key.split(':')
    const row = Number(rs)
    const col = Number(cs)
    if (row < 1 || row > r || col < 1 || col > c) delete props[key]
  }
  return withProps({ mode: 'grid', rows: r, cols: c, cells }, props)
}

/** 扩到至少包含 (row,col) */
export function expandToFit(layout: SceneLayout, row: number, col: number): SceneLayout {
  const rows = Math.max(layout.rows, row)
  const cols = Math.max(layout.cols, col)
  if (rows === layout.rows && cols === layout.cols) return layout
  return applyGridSize(layout, rows, cols)
}

export function toggleRackPillar(layout: SceneLayout, row: number, col: number): SceneLayout {
  if (row < 1 || row > layout.rows || col < 1 || col > layout.cols) return layout
  const kinds = [...getRow(layout, row)]
  const idx = col - 1
  const cur = kinds[idx]
  if (cur === 'rack') kinds[idx] = 'pillar'
  else if (cur === 'pillar') kinds[idx] = 'rack'
  else return layout
  return setRow(layout, row, kinds)
}

/** 在指定格放置模型（原地替换，不自动左/右对齐） */
export function placeAt(
  layout: SceneLayout,
  kind: CellKind,
  row: number,
  col: number,
  prop?: CellProp | null,
): SceneLayout {
  let next = expandToFit(layout, row, col)
  const kinds = [...getRow(next, row)]
  const idx = col - 1
  if (idx < 0 || idx >= kinds.length) return next
  kinds[idx] = kind
  next = setRow(next, row, kinds)
  const props = cloneProps(next.props)
  const key = cellPropKey(row, col)
  if (kind === 'custom' && prop) {
    props[key] = {
      label: (prop.label || '自定义').trim() || '自定义',
      color: prop.color || '#5a7a9a',
      customId: prop.customId,
    }
  } else if (kind === 'power' || kind === 'ac' || kind === 'odf') {
    props[key] = {
      label: prop?.label || cellKindLabel(kind),
      color: prop?.color,
    }
  } else {
    delete props[key]
  }
  return withProps(next, props)
}

/** 清除格位为 empty（删除后原位留空，不挤位对齐） */
export function clearAt(layout: SceneLayout, row: number, col: number): SceneLayout {
  if (row < 1 || row > layout.rows || col < 1 || col > layout.cols) return layout
  const kinds = [...getRow(layout, row)]
  const idx = col - 1
  if (kinds[idx] === 'empty') return layout
  kinds[idx] = 'empty'
  let next = setRow(layout, row, kinds)
  const props = cloneProps(next.props)
  delete props[cellPropKey(row, col)]
  return withProps(next, props)
}

export function removeFixedAt(layout: SceneLayout, row: number, col: number): SceneLayout {
  if (row < 1 || row > layout.rows || col < 1 || col > layout.cols) return layout
  const kinds = [...getRow(layout, row)]
  const idx = col - 1
  if (!FIXED.has(kinds[idx])) return layout
  return clearAt(layout, row, col)
}

/** 拖动固定物：移动固定物，原位变空（不自动对齐） */
export function moveFixed(
  layout: SceneLayout,
  fromRow: number,
  fromCol: number,
  toRow: number,
  toCol: number,
): SceneLayout {
  if (fromRow === toRow && fromCol === toCol) return layout
  let next = expandToFit(layout, Math.max(fromRow, toRow), Math.max(fromCol, toCol))
  const fromKinds = [...getRow(next, fromRow)]
  const fi = fromCol - 1
  if (fi < 0 || fi >= fromKinds.length || !FIXED.has(fromKinds[fi])) return layout
  const moving = fromKinds[fi]
  fromKinds[fi] = 'empty'
  next = setRow(next, fromRow, fromKinds)

  const toKinds = [...getRow(next, toRow)]
  const ti = toCol - 1
  if (ti < 0 || ti >= toKinds.length) return next
  toKinds[ti] = moving
  next = setRow(next, toRow, toKinds)

  const props = cloneProps(next.props)
  const fromKey = cellPropKey(fromRow, fromCol)
  const toKey = cellPropKey(toRow, toCol)
  const movingProp = props[fromKey]
  delete props[fromKey]
  if (movingProp) props[toKey] = movingProp
  else delete props[toKey]
  return withProps(next, props)
}

export function kindsToPlans(kinds: CellKind[]): RowCellPlan[] {
  let rackIndex = 0
  return kinds.map((kind, i) => {
    const col = i + 1
    if (kind === 'rack') {
      const plan: RowCellPlan = { kind, col, rackIndex }
      rackIndex += 1
      return plan
    }
    return { kind, col }
  })
}

export function planSceneRow(layout: SceneLayout, row: number): RowCellPlan[] {
  return kindsToPlans(getRow(layout, row))
}

function parseProps(raw: unknown): Record<string, CellProp> | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  const out: Record<string, CellProp> = {}
  for (const [key, val] of Object.entries(raw as Record<string, unknown>)) {
    if (!val || typeof val !== 'object') continue
    const obj = val as Record<string, unknown>
    const label = typeof obj.label === 'string' ? obj.label : undefined
    const color = typeof obj.color === 'string' ? obj.color : undefined
    const customId = typeof obj.customId === 'string' ? obj.customId : undefined
    if (!label && !color && !customId) continue
    out[key] = { label, color, customId }
  }
  return Object.keys(out).length ? out : undefined
}

/** 从后端 pillar_layout / 机房尺寸解析场景 */
export function parseSceneLayout(
  raw: Record<string, unknown> | null | undefined,
  fallbackRows: number,
  fallbackCols: number,
): SceneLayout {
  const rows0 = Math.max(1, fallbackRows || 1)
  const cols0 = Math.max(1, fallbackCols || 1)
  if (!raw || typeof raw !== 'object') {
    return buildFullRackGrid(rows0, cols0)
  }
  const mode = (raw.mode as string) || 'grid'
  const rows = Math.max(1, Number(raw.rows) || rows0)
  const cols = Math.max(1, Number(raw.cols) || cols0)
  const cellsIn = (raw.cells as Record<string, unknown>) || {}
  const props = parseProps(raw.props)
  if (mode === 'grid' || mode === 'cells') {
    const cells: Record<string, CellKind[]> = {}
    for (let i = 1; i <= rows; i++) {
      const key = String(i)
      const arr = Array.isArray(cellsIn[key]) ? (cellsIn[key] as unknown[]) : []
      if (arr.length) {
        cells[key] = ensureRowWidth(arr.map(normalizeKind), cols)
      } else {
        cells[key] = Array.from({ length: cols }, () => 'rack' as CellKind)
      }
    }
    return withProps({ mode: 'grid', rows, cols, cells }, props)
  }
  // auto_middle 等：生成满格后中间立柱（简化为满柜，由用户编辑）
  return buildFullRackGrid(rows0, cols0)
}

export function toPersistLayout(layout: SceneLayout): SceneLayout {
  const cells: Record<string, CellKind[]> = {}
  for (let i = 1; i <= layout.rows; i++) {
    cells[String(i)] = [...getRow(layout, i)]
  }
  return withProps({ mode: 'grid', rows: layout.rows, cols: layout.cols, cells }, layout.props)
}

export function countRackSlots(layout: SceneLayout): number {
  let n = 0
  for (let i = 1; i <= layout.rows; i++) {
    n += getRow(layout, i).filter((k) => k === 'rack').length
  }
  return n
}
