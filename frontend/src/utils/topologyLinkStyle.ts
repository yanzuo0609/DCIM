/** 拓扑连线路径形状与线型 */

export type TopologyLineShape = 'straight' | 'orthogonal' | 'curve'
export type TopologyLineStroke = 'solid' | 'dashed' | 'dotted'
export type TopologyLineStyle =
  | 'straight'
  | 'orthogonal'
  | 'curve'
  | 'straight-dashed'
  | 'orthogonal-dashed'
  | 'curve-dashed'
  | 'dotted'

export const LINE_STYLE_OPTIONS: Array<{ value: TopologyLineStyle; label: string }> = [
  { value: 'orthogonal', label: '直角' },
  { value: 'straight', label: '直线' },
  { value: 'curve', label: '曲线' },
  { value: 'straight-dashed', label: '虚线' },
  { value: 'orthogonal-dashed', label: '直角虚线' },
  { value: 'curve-dashed', label: '曲线虚线' },
  { value: 'dotted', label: '点线' },
]

const STYLE_SET = new Set(LINE_STYLE_OPTIONS.map((o) => o.value))

export function normalizeLineStyle(raw: string | null | undefined): TopologyLineStyle {
  const v = String(raw || '').trim() as TopologyLineStyle
  return STYLE_SET.has(v) ? v : 'orthogonal'
}

export function lineShapeOf(style: TopologyLineStyle): TopologyLineShape {
  if (style === 'orthogonal' || style === 'orthogonal-dashed') return 'orthogonal'
  if (style === 'curve' || style === 'curve-dashed') return 'curve'
  return 'straight'
}

export function lineStrokeOf(style: TopologyLineStyle): TopologyLineStroke {
  if (style === 'dotted') return 'dotted'
  if (style.endsWith('-dashed') || style === 'straight-dashed') return 'dashed'
  return 'solid'
}

export function strokeDasharrayOf(style: TopologyLineStyle): string | undefined {
  const stroke = lineStrokeOf(style)
  if (stroke === 'dashed') return '9 5'
  if (stroke === 'dotted') return '2 4'
  return undefined
}

function curveControl(x1: number, y1: number, x2: number, y2: number) {
  const dx = x2 - x1
  const dy = y2 - y1
  const len = Math.hypot(dx, dy) || 1
  const offset = Math.min(56, Math.max(18, len * 0.2))
  return {
    cx: (x1 + x2) / 2 - (dy / len) * offset,
    cy: (y1 + y2) / 2 + (dx / len) * offset,
  }
}

export function topologyLinkPath(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  style: TopologyLineStyle | string | null | undefined,
): string {
  const shape = lineShapeOf(normalizeLineStyle(style))
  if (shape === 'straight') {
    return `M ${x1} ${y1} L ${x2} ${y2}`
  }
  if (shape === 'curve') {
    const { cx, cy } = curveControl(x1, y1, x2, y2)
    return `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`
  }
  const dx = Math.abs(x2 - x1)
  const dy = Math.abs(y2 - y1)
  if (dx >= dy) {
    const mx = (x1 + x2) / 2
    return `M ${x1} ${y1} L ${mx} ${y1} L ${mx} ${y2} L ${x2} ${y2}`
  }
  const my = (y1 + y2) / 2
  return `M ${x1} ${y1} L ${x1} ${my} L ${x2} ${my} L ${x2} ${y2}`
}

export function topologyLinkLabelPos(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  style: TopologyLineStyle | string | null | undefined,
): { x: number; y: number } {
  const shape = lineShapeOf(normalizeLineStyle(style))
  if (shape === 'curve') {
    const { cx, cy } = curveControl(x1, y1, x2, y2)
    return {
      x: 0.25 * x1 + 0.5 * cx + 0.25 * x2,
      y: 0.25 * y1 + 0.5 * cy + 0.25 * y2 - 8,
    }
  }
  return { x: (x1 + x2) / 2, y: (y1 + y2) / 2 - 8 }
}
