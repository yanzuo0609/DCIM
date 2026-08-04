/** 机房机柜编号：排前缀展开与按预设补齐 slot_codes */

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

export function expandRowPrefixes(expression: string, rowCount: number): string[] {
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
      throw new Error(`范围 ${raw} 仅有 ${labels.length} 个字母，但需要 ${rowCount} 排`)
    }
    return labels.slice(0, rowCount)
  }

  const start = letterToIndex(raw)
  return Array.from({ length: rowCount }, (_, i) => indexToLetter(start + i))
}

export function parseSlotCode(code: string): { prefix: string; num: number } | null {
  const m = String(code || '')
    .trim()
    .match(/^(.*?)(\d+)$/)
  if (!m) return null
  return { prefix: m[1] || 'A', num: Number.parseInt(m[2], 10) }
}

function padSeq(n: number, cols: number): string {
  const width = Math.max(2, String(Math.max(cols, n)).length)
  return String(n).padStart(width, '0')
}

/**
 * 按机房预设前缀为场景网格生成/补齐编号。
 * - 已有编号尽量保留
 * - 新增排/列按排前缀与编号方向补齐
 * - 仅机柜格占号
 */
export function buildPresetSlotCodes(options: {
  rows: number
  cols: number
  kindsByRow: string[][]
  existing?: string[][]
  codePrefix?: string | null
  /** true：从右向左编号；false：从左向右 */
  fromRight?: boolean
}): string[][] {
  const { rows, cols, kindsByRow, existing = [], codePrefix, fromRight = false } = options
  let prefixes: string[]
  try {
    prefixes = expandRowPrefixes(codePrefix || inferPrefixSeed(existing) || 'A', rows)
  } catch {
    prefixes = Array.from({ length: rows }, (_, i) => indexToLetter(1 + i))
  }

  return Array.from({ length: rows }, (_, ri) => {
    const kinds = kindsByRow[ri] || Array.from({ length: cols }, () => 'rack')
    const prefixFromExisting = inferRowPrefix(existing[ri], prefixes[ri])
    const prefix = prefixFromExisting || prefixes[ri] || 'A'
    const row = Array.from({ length: cols }, (_, ci) => (existing[ri]?.[ci] || '').trim())

    const rackColsAsc: number[] = []
    for (let ci = 0; ci < cols; ci++) {
      if (kinds[ci] === 'rack') rackColsAsc.push(ci)
      else row[ci] = ''
    }

    const used = new Set<number>()
    for (const ci of rackColsAsc) {
      const parsed = parseSlotCode(row[ci])
      if (parsed && parsed.prefix === prefix) used.add(parsed.num)
    }

    const order = fromRight ? [...rackColsAsc].reverse() : rackColsAsc
    let n = 1
    for (const ci of order) {
      if (row[ci]) continue
      while (used.has(n)) n += 1
      row[ci] = `${prefix}${padSeq(n, cols)}`
      used.add(n)
      n += 1
    }
    return row
  })
}

function inferPrefixSeed(existing: string[][]): string {
  for (const row of existing) {
    for (const code of row || []) {
      const parsed = parseSlotCode(code)
      if (parsed?.prefix) return parsed.prefix
    }
  }
  return 'A'
}

function inferRowPrefix(row: string[] | undefined, fallback: string): string {
  for (const code of row || []) {
    const parsed = parseSlotCode(code)
    if (parsed?.prefix) return parsed.prefix
  }
  return fallback
}

/** 规范化为 rows×cols：机柜格保留编号，非机柜格置空（可保存） */
export function normalizeSlotCodesMatrix(
  rows: number,
  cols: number,
  codes: string[][] | undefined,
  kindsByRow: string[][],
): string[][] {
  const src = codes || []
  return Array.from({ length: rows }, (_, ri) => {
    const kinds = kindsByRow[ri] || []
    return Array.from({ length: cols }, (_, ci) => {
      if (kinds[ci] && kinds[ci] !== 'rack') return ''
      return (src[ri]?.[ci] || '').trim()
    })
  })
}

/**
 * 强制按排重编号（删除/替换后补齐断号，或手动「更新机柜编号」）。
 * - 仅机柜格占号；立柱/列头柜/空位置空
 * - 左编号：该排从左端起；右编号：从右端起（从右向左）
 * - 每排独立，序号从 start 连续递增
 */
export function renumberRackSlots(options: {
  rows: number
  cols: number
  kindsByRow: string[][]
  existing?: string[][]
  codePrefix?: string | null
  fromRight?: boolean
  start?: number
  /** 1-based 排号；省略则更新全部排 */
  targetRows?: number[]
}): string[][] {
  const {
    rows,
    cols,
    kindsByRow,
    existing = [],
    codePrefix,
    fromRight = false,
    start = 1,
    targetRows,
  } = options

  const base = normalizeSlotCodesMatrix(rows, cols, existing, kindsByRow)
  let prefixes: string[]
  try {
    prefixes = expandRowPrefixes(codePrefix || inferPrefixSeed(base) || 'A', rows)
  } catch {
    prefixes = Array.from({ length: rows }, (_, i) => indexToLetter(1 + i))
  }

  const targets = targetRows?.length
    ? new Set(targetRows.filter((r) => r >= 1 && r <= rows))
    : null

  const seqStart = Math.max(1, Math.floor(Number(start) || 1))

  return Array.from({ length: rows }, (_, ri) => {
    const rowNo = ri + 1
    if (targets && !targets.has(rowNo)) {
      return [...(base[ri] || Array.from({ length: cols }, () => ''))]
    }

    const kinds = kindsByRow[ri] || Array.from({ length: cols }, () => 'rack')
    const next = Array.from({ length: cols }, () => '')
    const rackColsAsc: number[] = []
    for (let ci = 0; ci < cols; ci++) {
      if (kinds[ci] === 'rack') rackColsAsc.push(ci)
    }

    const prefix =
      inferRowPrefix(
        base[ri]?.filter((_, ci) => kinds[ci] === 'rack'),
        prefixes[ri] || 'A',
      ) ||
      prefixes[ri] ||
      'A'

    const order = fromRight ? [...rackColsAsc].reverse() : rackColsAsc
    const width = Math.max(2, String(seqStart + Math.max(order.length, 1) - 1).length)
    let n = seqStart
    for (const ci of order) {
      next[ci] = `${prefix}${String(n).padStart(width, '0')}`
      n += 1
    }
    return next
  })
}
