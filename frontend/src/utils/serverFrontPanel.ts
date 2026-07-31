import type { PortLayout, ServerFormFactor } from '@/api/network'
import { SERVER_FORM_FACTOR_LABELS } from '@/api/network'
import {
  SERVER_HEADER_H,
  serverChassisSize,
  type ServerDriveBayVisual,
  serverDriveGrid,
} from '@/utils/serverPanelCommon'

export interface ServerFrontPanelView {
  formFactor: ServerFormFactor
  title: string
  frameWidth: number
  frameHeight: number
  driveBays: ServerDriveBayVisual[]
  driveGrid: { rows: number; cols: number }
}

function ventPatternPath(x: number, y: number, w: number, h: number, hex = 5): string {
  const parts: string[] = []
  for (let row = 0; row < h / hex; row += 1) {
    for (let col = 0; col < w / hex; col += 1) {
      const cx = x + col * hex + (row % 2 ? hex / 2 : 0)
      const cy = y + row * hex * 0.86
      if (cx > x + w || cy > y + h) continue
      parts.push(`M ${cx} ${cy - 2} L ${cx + 2} ${cy} L ${cx} ${cy + 2} L ${cx - 2} ${cy} Z`)
    }
  }
  return parts.join(' ')
}

export function layoutServerFrontPanel(layout: PortLayout): ServerFrontPanelView {
  const formFactor = (layout.server_form_factor ?? layout.height_u ?? 1) as ServerFormFactor
  layout.server_form_factor = formFactor
  layout.height_u = formFactor

  const grid = serverDriveGrid(formFactor)
  const { frameWidth, frameHeight } = serverChassisSize(formFactor, 'rear')
  const ioW = formFactor === 1 ? 72 : 88
  const bayPad = 8
  const bayOriginX = ioW + bayPad
  const bayOriginY = SERVER_HEADER_H + bayPad
  const bayAreaW = frameWidth - ioW - bayPad * 2 - 36
  const bayAreaH = frameHeight - SERVER_HEADER_H - bayPad * 2
  const gap = 4
  const cellW = (bayAreaW - gap * (grid.cols - 1)) / grid.cols
  const cellH = (bayAreaH - gap * (grid.rows - 1)) / grid.rows

  const driveBays: ServerDriveBayVisual[] = []
  for (let r = 0; r < grid.rows; r += 1) {
    for (let c = 0; c < grid.cols; c += 1) {
      driveBays.push({
        row: r,
        col: c,
        x: bayOriginX + c * (cellW + gap),
        y: bayOriginY + r * (cellH + gap),
        w: cellW,
        h: cellH,
      })
    }
  }

  layout.frame_width = frameWidth
  layout.frame_height = frameHeight
  layout.rack_width_mm = 600

  return {
    formFactor,
    title: SERVER_FORM_FACTOR_LABELS[formFactor],
    frameWidth,
    frameHeight,
    driveBays,
    driveGrid: grid,
  }
}

export { ventPatternPath }
