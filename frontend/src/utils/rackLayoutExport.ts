import ExcelJS from 'exceljs'
import type { Rack, RackLayoutData } from '@/api/rack'

export interface ExportRackBundle {
  rack: Rack
  layout: RackLayoutData
}

/** 单机柜 4 列：U | 设备 | IP地址 | 功率；机柜之间空 1 列 */
const RACK_COLS = 4
const GAP_COLS = 1
const RACK_STRIDE = RACK_COLS + GAP_COLS

function hexToArgb(hex: string | null | undefined): string | null {
  if (!hex) return null
  const cleaned = hex.replace('#', '').trim()
  if (/^[0-9a-fA-F]{6}$/.test(cleaned)) return `FF${cleaned.toUpperCase()}`
  if (/^[0-9a-fA-F]{8}$/.test(cleaned)) return cleaned.toUpperCase()
  return null
}

function thinBorder(): Partial<ExcelJS.Borders> {
  const edge: Partial<ExcelJS.Border> = { style: 'thin', color: { argb: 'FF000000' } }
  return { top: edge, left: edge, bottom: edge, right: edge }
}

function applyBorder(cell: ExcelJS.Cell) {
  cell.border = thinBorder()
  cell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: true }
}

interface DeviceSpan {
  name: string
  ip: string
  power: string
  topU: number
  bottomU: number
  height: number
  color: string | null
}

function deviceIp(device: {
  ip_summary?: string | null
  bmc_ip?: string | null
  vip?: string | null
}): string {
  const ip = (device.ip_summary || device.bmc_ip || device.vip || '').trim()
  return ip || '-'
}

function collectDevices(layout: RackLayoutData, rackColor: string | null): DeviceSpan[] {
  const devices: DeviceSpan[] = []
  for (const slot of layout.slots) {
    if (!slot.is_span_start || !slot.device) continue
    const height = Math.max(1, slot.span_height || slot.device.height_u || 1)
    const topU = slot.u_position
    const bottomU = Math.max(1, topU - height + 1)
    devices.push({
      name: slot.device.hostname || slot.device.model_name || '设备',
      ip: deviceIp(slot.device),
      power:
        slot.device.power == null || Number.isNaN(Number(slot.device.power))
          ? ''
          : String(Math.round(Number(slot.device.power))),
      topU,
      bottomU,
      height,
      color: rackColor,
    })
  }
  return devices
}

function rackTableHeight(totalU: number): number {
  return 1 + totalU + 1
}

/**
 * 图片样式：
 * 表头：编码（合并 U+设备）| IP地址 | 功率
 * 行：U | 设备名 | IP（无则 -）| 功率
 * 底：总功率（合并前三列）| 合计
 */
function writeRackTable(
  sheet: ExcelJS.Worksheet,
  bundle: ExportRackBundle,
  startRow: number,
  startCol: number,
): { rowsUsed: number; colsUsed: number } {
  const { rack, layout } = bundle
  const totalU = Math.max(1, rack.total_u || layout.slots.length || 42)
  const fillArgb = hexToArgb(rack.app_color)
  const cols = {
    u: startCol,
    name: startCol + 1,
    ip: startCol + 2,
    power: startCol + 3,
  }

  sheet.getColumn(cols.u).width = 5
  sheet.getColumn(cols.name).width = 28
  sheet.getColumn(cols.ip).width = 14
  sheet.getColumn(cols.power).width = 8

  // —— 表头 ——
  const header = sheet.getRow(startRow)
  header.height = 20
  for (const c of [cols.u, cols.name, cols.ip, cols.power]) {
    const cell = header.getCell(c)
    applyBorder(cell)
    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF000000' } }
    cell.font = { bold: true, color: { argb: 'FFFFFFFF' }, size: 11 }
  }
  header.getCell(cols.u).value = rack.code
  header.getCell(cols.ip).value = 'IP地址'
  header.getCell(cols.power).value = '功率'
  try {
    sheet.mergeCells(startRow, cols.u, startRow, cols.name)
  } catch {
    /* ignore */
  }

  const uToRow = (u: number) => startRow + 1 + (totalU - u)

  // 先铺满边框：空位 IP 用 -
  for (let u = totalU; u >= 1; u -= 1) {
    const excelRow = uToRow(u)
    const row = sheet.getRow(excelRow)
    row.height = 15
    const cellU = row.getCell(cols.u)
    const cellName = row.getCell(cols.name)
    const cellIp = row.getCell(cols.ip)
    const cellPower = row.getCell(cols.power)
    ;[cellU, cellName, cellIp, cellPower].forEach(applyBorder)
    cellU.value = u
    cellIp.value = '-'
  }

  const devices = collectDevices(layout, fillArgb)
  for (const device of devices) {
    const topRow = uToRow(device.topU)
    const bottomRow = uToRow(device.bottomU)

    const paint = (r: number) => {
      const nameCell = sheet.getRow(r).getCell(cols.name)
      const ipCell = sheet.getRow(r).getCell(cols.ip)
      const powerCell = sheet.getRow(r).getCell(cols.power)
      applyBorder(nameCell)
      applyBorder(ipCell)
      applyBorder(powerCell)
      nameCell.value = device.name
      ipCell.value = device.ip
      powerCell.value = device.power
      nameCell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: true }
      ipCell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: true }
      powerCell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: true }
      if (device.color) {
        const fill = {
          type: 'pattern' as const,
          pattern: 'solid' as const,
          fgColor: { argb: device.color },
        }
        nameCell.fill = fill
      }
    }

    paint(topRow)
    if (device.height >= 2 && bottomRow > topRow) {
      try {
        sheet.mergeCells(topRow, cols.name, bottomRow, cols.name)
      } catch {
        /* ignore */
      }
      try {
        sheet.mergeCells(topRow, cols.ip, bottomRow, cols.ip)
      } catch {
        /* ignore */
      }
      try {
        sheet.mergeCells(topRow, cols.power, bottomRow, cols.power)
      } catch {
        /* ignore */
      }
      paint(topRow)
    }
  }

  // —— 总功率 ——
  const footerRowIdx = startRow + 1 + totalU
  const footer = sheet.getRow(footerRowIdx)
  footer.height = 18
  for (const c of [cols.u, cols.name, cols.ip, cols.power]) {
    applyBorder(footer.getCell(c))
    footer.getCell(c).font = { bold: true, size: 11 }
  }
  footer.getCell(cols.u).value = '总功率'
  try {
    sheet.mergeCells(footerRowIdx, cols.u, footerRowIdx, cols.ip)
  } catch {
    /* ignore */
  }
  footer.getCell(cols.power).value = Math.round(layout.total_power || 0)

  return { rowsUsed: rackTableHeight(totalU), colsUsed: RACK_COLS }
}

function groupByRoomRow(bundles: ExportRackBundle[]): ExportRackBundle[][] {
  const map = new Map<number, ExportRackBundle[]>()
  for (const b of bundles) {
    const rowNo = b.rack.row_no || 1
    if (!map.has(rowNo)) map.set(rowNo, [])
    map.get(rowNo)!.push(b)
  }
  const rows = [...map.entries()].sort((a, b) => a[0] - b[0])
  return rows.map(([, list]) =>
    list.sort((a, b) => (a.rack.column_no || 0) - (b.rack.column_no || 0)),
  )
}

export async function exportRoomRackLayoutsExcel(
  roomTitle: string,
  bundles: ExportRackBundle[],
): Promise<void> {
  const workbook = new ExcelJS.Workbook()
  workbook.creator = 'RackDCIM Pro'
  const sheet = workbook.addWorksheet('机柜布局图')
  sheet.views = [{ showGridLines: false }]

  const bands = groupByRoomRow(bundles)
  if (!bands.length) throw new Error('没有可导出的机柜')

  let cursorRow = 1
  for (let bandIdx = 0; bandIdx < bands.length; bandIdx += 1) {
    const band = bands[bandIdx]
    const maxU = Math.max(...band.map((b) => b.rack.total_u || 42), 1)
    const bandHeight = rackTableHeight(maxU)

    const titleCell = sheet.getRow(cursorRow).getCell(1)
    titleCell.value = `第 ${band[0].rack.row_no} 排`
    titleCell.font = { bold: true, size: 12, color: { argb: 'FF1F3348' } }
    cursorRow += 1

    let cursorCol = 1
    for (let i = 0; i < band.length; i += 1) {
      writeRackTable(sheet, band[i], cursorRow, cursorCol)
      cursorCol += RACK_STRIDE
    }

    cursorRow += bandHeight
    if (bandIdx < bands.length - 1) cursorRow += 1
  }

  cursorRow += 1
  const note = sheet.getRow(cursorRow)
  note.getCell(1).value =
    `机房：${roomTitle}  ·  导出机柜数：${bundles.length}  ·  同排空 1 列，排间空 1 行`
  note.getCell(1).font = { size: 10, color: { argb: 'FF666666' } }

  const buffer = await workbook.xlsx.writeBuffer()
  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${roomTitle || '机房'}-机柜布局图.xlsx`
  a.click()
  URL.revokeObjectURL(url)
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function buildRackHtmlTable(bundle: ExportRackBundle): string {
  const { rack, layout } = bundle
  const totalU = Math.max(1, rack.total_u || 42)
  const devices = collectDevices(layout, hexToArgb(rack.app_color))
  const byTop = new Map(devices.map((d) => [d.topU, d]))
  const covered = new Set<number>()
  const rows: string[] = []

  for (let u = totalU; u >= 1; u -= 1) {
    if (covered.has(u)) {
      rows.push(`<tr><td class="u">${u}</td></tr>`)
      continue
    }
    const device = byTop.get(u)
    if (device) {
      for (let uu = device.topU; uu >= device.bottomU; uu -= 1) covered.add(uu)
      const span = device.height
      const bg = rack.app_color ? `background:${rack.app_color};` : ''
      rows.push(`
        <tr>
          <td class="u">${u}</td>
          <td class="name" rowspan="${span}" style="${bg}">${escapeHtml(device.name)}</td>
          <td class="ip" rowspan="${span}">${escapeHtml(device.ip)}</td>
          <td class="power" rowspan="${span}">${escapeHtml(device.power)}</td>
        </tr>`)
    } else {
      covered.add(u)
      rows.push(`
        <tr>
          <td class="u">${u}</td>
          <td class="name"></td>
          <td class="ip">-</td>
          <td class="power"></td>
        </tr>`)
    }
  }

  return `
    <table class="rack-table">
      <thead>
        <tr>
          <th class="code" colspan="2">${escapeHtml(rack.code)}</th>
          <th class="ip">IP地址</th>
          <th class="power">功率</th>
        </tr>
      </thead>
      <tbody>${rows.join('')}</tbody>
      <tfoot>
        <tr>
          <td colspan="3"><strong>总功率</strong></td>
          <td class="power"><strong>${Math.round(layout.total_power || 0)}</strong></td>
        </tr>
      </tfoot>
    </table>`
}

export function exportRoomRackLayoutsPdf(roomTitle: string, bundles: ExportRackBundle[]): void {
  const bands = groupByRoomRow(bundles)
  const bandsHtml = bands
    .map((band) => {
      const rowNo = band[0]?.rack.row_no || 1
      return `
      <section class="band">
        <h2>第 ${rowNo} 排</h2>
        <div class="rack-row">
          ${band.map((b) => buildRackHtmlTable(b)).join('<div class="rack-gap"></div>')}
        </div>
      </section>`
    })
    .join('<div class="band-gap"></div>')

  const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <title>${escapeHtml(roomTitle)} - 机柜布局图</title>
  <style>
    body { font-family: "Microsoft YaHei", SimSun, sans-serif; margin: 16px; color: #000; }
    h1 { font-size: 16px; margin: 0 0 12px; }
    h2 { font-size: 13px; margin: 0 0 8px; color: #333; }
    .band-gap { height: 28px; }
    .rack-row { display: flex; flex-wrap: nowrap; align-items: flex-start; overflow-x: auto; }
    .rack-gap { width: 24px; flex: 0 0 24px; }
    .rack-table { border-collapse: collapse; table-layout: fixed; width: 260px; font-size: 11px; }
    .rack-table th, .rack-table td { border: 1px solid #000; text-align: center; vertical-align: middle; padding: 1px 3px; }
    .rack-table thead th { background: #000; color: #fff; font-weight: 700; height: 22px; }
    .rack-table .u { width: 28px; }
    .rack-table .name, .rack-table .code { width: 130px; }
    .rack-table .ip { width: 70px; }
    .rack-table .power { width: 42px; }
    .rack-table tbody td { height: 14px; }
    @media print {
      body { margin: 8px; }
      .no-print { display: none; }
      .rack-row { overflow: visible; }
    }
  </style>
</head>
<body>
  <div class="no-print" style="margin-bottom:12px">
    <button onclick="window.print()">打印 / 另存为 PDF</button>
  </div>
  <h1>${escapeHtml(roomTitle)} · 机柜完整布局图（${bundles.length}）</h1>
  ${bandsHtml}
</body>
</html>`

  const win = window.open('', '_blank')
  if (!win) throw new Error('无法打开导出窗口，请允许浏览器弹窗后重试')
  win.document.open()
  win.document.write(html)
  win.document.close()
  win.focus()
  setTimeout(() => {
    try {
      win.print()
    } catch {
      /* ignore */
    }
  }, 300)
}
