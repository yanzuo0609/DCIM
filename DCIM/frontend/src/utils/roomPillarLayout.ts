/** 3D 机房：两端对齐机柜 + 可编辑立柱 */

export type PillarMode = 'auto_middle' | 'cells'

export type RowCellKind = 'rack' | 'pillar' | 'empty'

export interface PillarLayout {
  mode: PillarMode
  /** 显式单元格：排号 -> 满宽 kinds */
  cells?: Record<string, RowCellKind[]>
}

export interface RowCellPlan {
  kind: RowCellKind
  col: number
  rackIndex?: number
}

/** 自动：两端机柜，中间立柱补齐 */
export function buildAutoMiddleCells(maxCols: number, rackCount: number): RowCellKind[] {
  const span = Math.max(1, maxCols)
  const n = Math.max(0, Math.min(rackCount, span))
  const cells: RowCellKind[] = Array.from({ length: span }, () => 'empty')
  if (n === 0) {
    for (let i = 0; i < span; i++) cells[i] = 'pillar'
    return cells
  }
  const gap = Math.max(0, span - n)
  const leftN = Math.ceil(n / 2)
  for (let i = 0; i < leftN; i++) cells[i] = 'rack'
  for (let i = 0; i < gap; i++) cells[leftN + i] = 'pillar'
  for (let i = 0; i < n - leftN; i++) cells[leftN + gap + i] = 'rack'
  return cells
}

/**
 * 保留立柱位置，机柜两端对齐：
 * 左半机柜贴最左空位，右半机柜贴最右空位。
 */
export function alignRacksToEnds(kinds: RowCellKind[], rackCount: number): RowCellKind[] {
  const span = Math.max(1, kinds.length)
  const pillarIdx = new Set<number>()
  for (let i = 0; i < span; i++) {
    if (kinds[i] === 'pillar') pillarIdx.add(i)
  }
  const free = Array.from({ length: span }, (_, i) => i).filter((i) => !pillarIdx.has(i))
  const n = Math.max(0, Math.min(rackCount, free.length))
  const leftN = Math.ceil(n / 2)
  const rightN = n - leftN
  const rackSet = new Set<number>([
    ...free.slice(0, leftN),
    ...(rightN > 0 ? free.slice(free.length - rightN) : []),
  ])
  return Array.from({ length: span }, (_, i) => {
    if (pillarIdx.has(i)) return 'pillar'
    if (rackSet.has(i)) return 'rack'
    return 'empty'
  })
}

/**
 * 左侧连续机柜整体右移一格，填入 holeIdx（原立柱位）。
 * 例：[R,R,R,P,…] 删 P → [∅,R,R,R,…]
 */
function shiftLeftRacksIntoHole(kinds: RowCellKind[], holeIdx: number): RowCellKind[] {
  const next = [...kinds]
  let start = holeIdx - 1
  while (start >= 0 && next[start] === 'rack') start -= 1
  start += 1
  if (start > holeIdx - 1) return next
  for (let i = holeIdx; i > start; i--) {
    next[i] = next[i - 1]
  }
  next[start] = 'empty'
  return next
}

/**
 * 右侧连续机柜整体左移一格，填入 holeIdx。
 * 例：[…,P,R,R,R] 删 P → […,R,R,R,∅]
 */
function shiftRightRacksIntoHole(kinds: RowCellKind[], holeIdx: number): RowCellKind[] {
  const next = [...kinds]
  let end = holeIdx + 1
  while (end < next.length && next[end] === 'rack') end += 1
  end -= 1
  if (end < holeIdx + 1) return next
  for (let i = holeIdx; i < end; i++) {
    next[i] = next[i + 1]
  }
  next[end] = 'empty'
  return next
}

export function resolveRowKinds(
  maxCols: number,
  rackCount: number,
  layout: PillarLayout | null | undefined,
  rowNo: number,
): RowCellKind[] {
  const span = Math.max(1, maxCols)
  const key = String(rowNo)
  const stored = layout?.cells?.[key]
  if (layout?.mode === 'cells' && Array.isArray(stored) && stored.length) {
    const cells = stored.slice(0, span).map((k) =>
      k === 'pillar' || k === 'empty' || k === 'rack' ? k : 'empty',
    )
    while (cells.length < span) cells.push('empty')
    // cells 模式保留显式机柜/立柱位置（删除立柱后的滑动占位不能被重排冲掉）
    const rackSlots = cells.filter((k) => k === 'rack').length
    if (rackSlots === 0 && rackCount > 0) {
      return alignRacksToEnds(cells, rackCount)
    }
    return cells
  }
  return buildAutoMiddleCells(span, rackCount)
}

export function kindsToPlans(kinds: RowCellKind[]): RowCellPlan[] {
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

export function planRowCells(
  maxCols: number,
  rackCount: number,
  layout: PillarLayout | null | undefined,
  rowNo: number,
): RowCellPlan[] {
  return kindsToPlans(resolveRowKinds(maxCols, rackCount, layout, rowNo))
}

/**
 * 删除立柱：
 * - 若紧邻左侧机柜 → 同侧（左）机柜整体右移，占满立柱位
 * - 若紧邻右侧机柜 → 同侧（右）机柜整体左移，占满立柱位
 * - 两侧都紧邻 → 左侧机柜右移占位（合并）
 * - 不靠机柜 → 仅变空位，不重排
 */
export function deletePillarAt(
  kinds: RowCellKind[],
  col: number,
  _rackCount?: number,
): RowCellKind[] {
  const idx = col - 1
  if (idx < 0 || idx >= kinds.length) return [...kinds]
  if (kinds[idx] !== 'pillar') return [...kinds]

  const leftIsRack = idx > 0 && kinds[idx - 1] === 'rack'
  const rightIsRack = idx < kinds.length - 1 && kinds[idx + 1] === 'rack'

  const cleared = [...kinds]
  cleared[idx] = 'empty'

  if (leftIsRack && !rightIsRack) {
    return shiftLeftRacksIntoHole(cleared, idx)
  }
  if (rightIsRack && !leftIsRack) {
    return shiftRightRacksIntoHole(cleared, idx)
  }
  if (leftIsRack && rightIsRack) {
    return shiftLeftRacksIntoHole(cleared, idx)
  }
  return cleared
}

/** 在指定列增加立柱（可挤占），再两端对齐 */
export function addPillarAt(
  kinds: RowCellKind[],
  col: number,
  rackCount: number,
): RowCellKind[] {
  const next = [...kinds]
  const idx = col - 1
  if (idx < 0 || idx >= next.length) return next
  next[idx] = 'pillar'
  // 立柱占用后，可用机柜槽不足时自然挤占
  return alignRacksToEnds(next, rackCount)
}

/**
 * 拖拽立柱换列：与目标格交换类型（机柜/空位），不整排重排，保证跟手。
 */
export function movePillar(
  kinds: RowCellKind[],
  fromCol: number,
  toCol: number,
  _rackCount?: number,
): RowCellKind[] {
  const next = [...kinds]
  const from = fromCol - 1
  const to = toCol - 1
  if (from < 0 || to < 0 || from >= next.length || to >= next.length) return next
  if (next[from] !== 'pillar') return next
  if (from === to) return next
  const target = next[to]
  next[to] = 'pillar'
  next[from] = target === 'pillar' ? 'empty' : target
  return next
}

/** 立柱 → 机柜位（同格替换） */
export function replacePillarWithRack(kinds: RowCellKind[], col: number): RowCellKind[] {
  const next = [...kinds]
  const idx = col - 1
  if (idx < 0 || idx >= next.length || next[idx] !== 'pillar') return next
  next[idx] = 'rack'
  return next
}

/** 机柜位 → 立柱（同格替换） */
export function replaceRackWithPillar(kinds: RowCellKind[], col: number): RowCellKind[] {
  const next = [...kinds]
  const idx = col - 1
  if (idx < 0 || idx >= next.length || next[idx] !== 'rack') return next
  next[idx] = 'pillar'
  return next
}

export function toCellsLayout(
  cellsByRow: Record<string, RowCellKind[]>,
): PillarLayout {
  return { mode: 'cells', cells: cellsByRow }
}

export function countRacksInRow(
  data: { racks: Array<{ row_no: number }>; row_layout?: number[] },
  row: number,
  fallbackCols: number,
): number {
  const fromLayout = data.row_layout?.[row - 1]
  const fromRacks = data.racks.filter((r) => r.row_no === row).length
  return Math.max(fromLayout ?? 0, fromRacks, 0) || fallbackCols
}
