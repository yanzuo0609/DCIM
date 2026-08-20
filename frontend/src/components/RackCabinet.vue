<script setup lang="ts">
import { computed } from 'vue'
import type { RackLayoutDevice, RackLayoutSlot } from '@/api/rack'

export type RackVisualStyle = 'classic' | 'schematic' | 'realistic' | 'grid'

/** IP 单元格角色：both=1U 双行；biz/bmc=多 U 拆分；empty=奇数高最下 1U */
type IpCellKind = 'both' | 'biz' | 'bmc' | 'empty' | 'idle'

type LayoutTableRow = {
  slot: RackLayoutSlot
  showDevice: boolean
  deviceRowspan: number
  showIp: boolean
  ipRowspan: number
  ipKind: IpCellKind
  showPower: boolean
  powerRowspan: number
}

const props = withDefaults(
  defineProps<{
    code: string
    totalU: number
    slots?: RackLayoutSlot[]
    totalPower?: number
    compact?: boolean
    selectable?: boolean
    selectedU?: number | null
    highlightDeviceId?: string | null
    /** classic=原深色立面(默认) | schematic=线框 | realistic=正面面板 | grid=表格占位 */
    visualStyle?: RackVisualStyle
  }>(),
  {
    slots: () => [],
    totalPower: 0,
    compact: false,
    selectable: false,
    selectedU: null,
    highlightDeviceId: null,
    visualStyle: 'classic',
  },
)

const emit = defineEmits<{
  'select-u': [u: number]
}>()

function onSlotClick(slot: RackLayoutSlot) {
  if (!props.selectable || slot.occupied) return
  emit('select-u', slot.u_position)
}

const styleKey = computed<RackVisualStyle>(() => {
  const v = props.visualStyle
  if (v === 'realistic' || v === 'grid' || v === 'schematic' || v === 'classic') return v
  return 'classic'
})

const displaySlots = computed(() => {
  if (props.slots.length) return props.slots
  const empty: RackLayoutSlot[] = []
  for (let u = props.totalU; u >= 1; u -= 1) {
    empty.push({
      u_position: u,
      occupied: false,
      is_span_start: false,
      span_height: 1,
      device: null,
    })
  }
  return empty
})

const unitPx = computed(() => {
  if (styleKey.value === 'grid') return props.compact ? 16 : 20
  if (styleKey.value === 'realistic') return props.compact ? 18 : 24
  return props.compact ? 22 : 28
})

/**
 * 多 U 设备合并规则：
 * - 设备名 / 功率：整段 height_u 合并
 * - IP：固定拆成「业务IP」「BMCIP」两格；每格占 floor(evenHeight/2) 行
 * - 奇数高度：最下面 1U 不计入 IP 拆分（该行 IP 留空单元格）
 * - 1U：单格内两行显示业务IP + BMCIP
 */
const layoutTableRows = computed<LayoutTableRow[]>(() => {
  const rows: LayoutTableRow[] = []
  let spanMeta: { half: number; effective: number; offset: number } | null = null

  for (const slot of displaySlots.value) {
    if (!slot.occupied || !slot.device) {
      spanMeta = null
      rows.push({
        slot,
        showDevice: true,
        deviceRowspan: 1,
        showIp: true,
        ipRowspan: 1,
        ipKind: 'idle',
        showPower: true,
        powerRowspan: 1,
      })
      continue
    }

    const height = Math.max(1, slot.device.height_u || slot.span_height || 1)

    if (slot.is_span_start) {
      if (height === 1) {
        spanMeta = null
        rows.push({
          slot,
          showDevice: true,
          deviceRowspan: 1,
          showIp: true,
          ipRowspan: 1,
          ipKind: 'both',
          showPower: true,
          powerRowspan: 1,
        })
        continue
      }

      const effective = height % 2 === 1 ? height - 1 : height
      const half = Math.max(1, effective / 2)
      spanMeta = { half, effective, offset: 0 }
      rows.push({
        slot,
        showDevice: true,
        deviceRowspan: height,
        showIp: true,
        ipRowspan: half,
        ipKind: 'biz',
        showPower: true,
        powerRowspan: height,
      })
      continue
    }

    // continuation
    const offset: number = spanMeta ? spanMeta.offset + 1 : 0
    if (spanMeta) spanMeta = { ...spanMeta, offset }

    let showIp = false
    let ipRowspan = 1
    let ipKind: IpCellKind = 'empty'

    if (spanMeta) {
      if (offset === spanMeta.half) {
        showIp = true
        ipRowspan = spanMeta.half
        ipKind = 'bmc'
      } else if (offset >= spanMeta.effective) {
        showIp = true
        ipRowspan = 1
        ipKind = 'empty'
      }
    }

    rows.push({
      slot,
      showDevice: false,
      deviceRowspan: 1,
      showIp,
      ipRowspan,
      ipKind,
      showPower: false,
      powerRowspan: 1,
    })
  }

  return rows
})

function heightClass(device: RackLayoutDevice | null | undefined) {
  if (!device) return ''
  if (device.height_u === 2) return 'h-2u'
  if (device.height_u === 4) return 'h-4u'
  return 'h-other'
}

/** 按最长设备名 / IP 估算机柜宽度，保证格内信息完整显示 */
const adaptiveWidthPx = computed(() => {
  let maxName = 6
  let maxIp = 14
  for (const slot of displaySlots.value) {
    const d = slot.device
    if (!d) continue
    maxName = Math.max(maxName, (d.hostname || '').length, (d.model_name || '').length)
    const biz = `业务IP: ${d.ip_summary?.trim() || '—'}`
    const bmc = `BMCIP: ${d.bmc_ip?.trim() || '—'}`
    maxIp = Math.max(maxIp, biz.length, bmc.length)
  }
  // 等宽近似字符宽：名称略宽、IP 数字略窄
  const nameCol = Math.max(120, maxName * 8.2)
  const ipCol = Math.max(110, maxIp * 6.8)
  const sideCol = 42 // U / 功率各约 8%
  // 50% + 34% + 8% + 8% = 100%；以名称/IP 反推总宽
  const byName = nameCol / 0.5
  const byIp = ipCol / 0.34
  const bySide = sideCol / 0.08
  const width = Math.ceil(Math.max(byName, byIp, bySide))
  return Math.min(props.compact ? 420 : 580, Math.max(props.compact ? 420 : 340, width))
})

const cabinetStyle = computed(() => ({
  width: props.compact ? '100%' : `${adaptiveWidthPx.value}px`,
  maxWidth: props.compact ? '420px' : '580px',
}))

function formatPower(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return '—'
  if (value >= 1000) return `${(value / 1000).toFixed(1)} kW`
  return `${Math.round(value)}W`
}

function rowStyle(_slot: RackLayoutSlot, ipKind?: IpCellKind) {
  const base = unitPx.value
  // 1U 双行 IP 略增高，避免挤在一起
  const h = ipKind === 'both' ? Math.max(base, 36) : base
  return { height: `${h}px`, minHeight: `${h}px` }
}

function isContinuation(slot: RackLayoutSlot) {
  return slot.occupied && !slot.is_span_start && !!slot.device
}

function panelKind(device: RackLayoutDevice | null | undefined) {
  if (!device) return 'empty'
  const text = `${device.hostname || ''} ${device.model_name || ''}`.toLowerCase()
  if (/pdu|电源|power/.test(text)) return 'pdu'
  if (/switch|交换|sw/.test(text)) return 'switch'
  if (/monitor|显示|kvm|lcd/.test(text)) return 'monitor'
  if (/amp|功放|audio/.test(text)) return 'amp'
  if (/storage|存储|nas|disk/.test(text)) return 'storage'
  return 'server'
}

function showSectionDivider(u: number) {
  // 仅经典立面保留分段粗线；线框/表格占位保持细线，避免三条粗分割线干扰
  if (styleKey.value !== 'classic') return false
  return u === 10 || u === 18 || u === 29
}

const rowState = (slot: RackLayoutSlot) => ({
  empty: !slot.occupied,
  occupied: !!slot.device,
  continuation: isContinuation(slot),
  'span-start': slot.is_span_start,
  selectable: props.selectable && !slot.occupied,
  selected: props.selectable && props.selectedU === slot.u_position,
  highlighted: !!props.highlightDeviceId && slot.device?.device_id === props.highlightDeviceId,
})

function bizIpText(device: RackLayoutDevice | null | undefined) {
  return device?.ip_summary?.trim() || '—'
}

function bmcIpText(device: RackLayoutDevice | null | undefined) {
  return device?.bmc_ip?.trim() || '—'
}
</script>

<template>
  <div class="cabinet" :class="[`style-${styleKey}`, { compact }]" :style="cabinetStyle">
    <!-- ========== 表格占位 (grid) ========== -->
    <template v-if="styleKey === 'grid'">
      <div class="grid-title">{{ code || '机柜' }}</div>
      <table class="grid-table">
        <tbody>
          <tr
            v-for="row in layoutTableRows"
            :key="row.slot.u_position"
            class="grid-row"
            :class="[
              { divider: showSectionDivider(row.slot.u_position) },
              rowState(row.slot),
              heightClass(row.slot.device),
            ]"
            :style="rowStyle(row.slot)"
            @click="onSlotClick(row.slot)"
          >
            <td class="grid-u">{{ row.slot.u_position }}U</td>
            <!-- 无 IP / 功率列：仅合并设备名格（同经典立面 device rowspan） -->
            <td
              v-if="row.showDevice"
              class="grid-cell"
              :rowspan="row.deviceRowspan"
            >
              <template v-if="row.slot.device">
                {{ row.slot.device.hostname || '设备' }}
              </template>
            </td>
            <td class="grid-u">{{ row.slot.u_position }}U</td>
          </tr>
        </tbody>
      </table>
    </template>

    <!-- ========== 正面面板 (realistic) ========== -->
    <template v-else-if="styleKey === 'realistic'">
      <div class="realistic-frame">
        <div class="realistic-top">{{ totalU }}U</div>
        <div class="realistic-main">
          <div class="u-scale">
            <span
              v-for="u in displaySlots.filter((_, i) => i % 2 === 0)"
              :key="u.u_position"
              class="u-tick"
            >{{ u.u_position }}U</span>
          </div>
          <div class="realistic-rails">
            <div
              v-for="slot in displaySlots"
              :key="slot.u_position"
              class="face-row"
              :class="[rowState(slot), `panel-${panelKind(slot.device)}`, heightClass(slot.device)]"
              :style="rowStyle(slot)"
              @click="onSlotClick(slot)"
            >
              <template v-if="slot.is_span_start && slot.device">
                <div class="faceplate" :data-kind="panelKind(slot.device)">
                  <span class="face-name">{{ slot.device.hostname }}</span>
                  <span v-if="slot.device.model_name" class="face-model">{{ slot.device.model_name }}</span>
                </div>
              </template>
              <template v-else-if="isContinuation(slot)">
                <div class="faceplate cont" :data-kind="panelKind(slot.device)" />
              </template>
              <template v-else>
                <div class="bay-empty" />
              </template>
            </div>
          </div>
        </div>
        <div class="realistic-foot">正面 · {{ code || '未命名' }}</div>
      </div>
    </template>

    <!-- ========== 线框立面 (schematic) ========== -->
    <template v-else-if="styleKey === 'schematic'">
      <div class="sch-ears">
        <span class="sch-ear" />
        <div class="sch-body">
          <header class="sch-header">
            <div class="sch-power">
              <span class="sch-power-label">功率</span>
              <span class="sch-power-value">{{ formatPower(totalPower) }}</span>
            </div>
            <div class="sch-code">{{ code || '未命名' }}</div>
            <div class="sch-u">{{ totalU }}U</div>
          </header>
          <table class="sch-table">
            <thead>
              <tr>
                <th>U</th>
                <th>设备 / 空闲</th>
                <th>IP</th>
                <th>功率</th>
                <th>U</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in layoutTableRows"
                :key="row.slot.u_position"
                class="sch-row"
                :class="[
                  rowState(row.slot),
                  heightClass(row.slot.device),
                  { divider: showSectionDivider(row.slot.u_position) },
                ]"
                :style="rowStyle(row.slot, row.ipKind)"
                @click="onSlotClick(row.slot)"
              >
                <td class="sch-cell-u">{{ row.slot.u_position }}</td>
                <td
                  v-if="row.showDevice"
                  class="sch-cell-device"
                  :rowspan="row.deviceRowspan"
                >
                    <template v-if="row.slot.device">
                      <div class="sch-device-inner">
                        <span class="sch-host">{{ row.slot.device.hostname }}</span>
                        <span v-if="row.slot.device.model_name" class="sch-model">{{ row.slot.device.model_name }}</span>
                      </div>
                    </template>
                  <template v-else><span class="sch-idle">空闲</span></template>
                </td>
                <td
                  v-if="row.showIp"
                  class="sch-cell-ip"
                  :class="`ip-${row.ipKind}`"
                  :rowspan="row.ipRowspan"
                >
                  <template v-if="row.ipKind === 'both' && row.slot.device">
                    <div>业务IP: {{ bizIpText(row.slot.device) }}</div>
                    <div>BMCIP: {{ bmcIpText(row.slot.device) }}</div>
                    <div v-if="row.slot.device.vip" class="ip-sub vip">VIP {{ row.slot.device.vip }}</div>
                  </template>
                  <template v-else-if="row.ipKind === 'biz' && row.slot.device">
                    业务IP: {{ bizIpText(row.slot.device) }}
                  </template>
                  <template v-else-if="row.ipKind === 'bmc' && row.slot.device">
                    <div>BMCIP: {{ bmcIpText(row.slot.device) }}</div>
                    <div v-if="row.slot.device.vip" class="ip-sub vip">VIP {{ row.slot.device.vip }}</div>
                  </template>
                  <template v-else-if="row.ipKind === 'empty'" />
                  <template v-else>—</template>
                </td>
                <td
                  v-if="row.showPower"
                  class="sch-cell-power"
                  :rowspan="row.powerRowspan"
                >
                  <template v-if="row.slot.device">
                    {{ formatPower(row.slot.device.power) }}
                  </template>
                  <template v-else>—</template>
                </td>
                <td class="sch-cell-u">{{ row.slot.u_position }}</td>
              </tr>
            </tbody>
          </table>
          <footer class="sch-footer">
            <span class="sch-legend h-2u">2U</span>
            <span class="sch-legend h-4u">4U</span>
            <span class="sch-legend h-other">其它 U 高</span>
            <span class="sch-legend idle">空闲</span>
          </footer>
        </div>
        <span class="sch-ear" />
      </div>
    </template>

    <!-- ========== 经典深色立面 (classic，默认) ========== -->
    <template v-else>
      <div class="cabinet-ears">
        <span class="ear left" />
        <div class="cabinet-body">
          <header class="cabinet-header">
            <div class="power-chip" title="机柜设备总功率">
              <span class="power-label">功率</span>
              <span class="power-value">{{ formatPower(totalPower) }}</span>
            </div>
            <div class="rack-code" :title="code || '机柜编号'">
              {{ code || '未命名' }}
            </div>
            <div class="u-chip">{{ totalU }}U</div>
          </header>

          <div class="cabinet-rails">
            <table class="rack-table">
              <thead>
                <tr>
                  <th class="col-u">U</th>
                  <th class="col-device">设备 / 空闲</th>
                  <th class="col-ip">IP</th>
                  <th class="col-power">功率</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in layoutTableRows"
                  :key="row.slot.u_position"
                  class="u-row"
                  :class="[rowState(row.slot), heightClass(row.slot.device)]"
                  :style="rowStyle(row.slot, row.ipKind)"
                  @click="onSlotClick(row.slot)"
                >
                  <td class="cell-u">U{{ row.slot.u_position }}</td>
                  <td
                    v-if="row.showDevice"
                    class="cell-device"
                    :rowspan="row.deviceRowspan"
                  >
                    <template v-if="row.slot.device">
                      <div class="device-inner">
                        <span class="hostname">{{ row.slot.device.hostname }}</span>
                        <span v-if="row.slot.device.model_name" class="model">{{ row.slot.device.model_name }}</span>
                      </div>
                    </template>
                    <template v-else>
                      <span class="idle">空闲</span>
                    </template>
                  </td>
                  <td
                    v-if="row.showIp"
                    class="cell-ip"
                    :class="`ip-${row.ipKind}`"
                    :rowspan="row.ipRowspan"
                  >
                    <template v-if="row.ipKind === 'both' && row.slot.device">
                      <div>业务IP: {{ bizIpText(row.slot.device) }}</div>
                      <div>BMCIP: {{ bmcIpText(row.slot.device) }}</div>
                      <div v-if="row.slot.device.vip" class="ip-sub vip">VIP {{ row.slot.device.vip }}</div>
                    </template>
                    <template v-else-if="row.ipKind === 'biz' && row.slot.device">
                      业务IP: {{ bizIpText(row.slot.device) }}
                    </template>
                    <template v-else-if="row.ipKind === 'bmc' && row.slot.device">
                      <div>BMCIP: {{ bmcIpText(row.slot.device) }}</div>
                      <div v-if="row.slot.device.vip" class="ip-sub vip">VIP {{ row.slot.device.vip }}</div>
                    </template>
                    <template v-else-if="row.ipKind === 'empty'" />
                    <template v-else>—</template>
                  </td>
                  <td
                    v-if="row.showPower"
                    class="cell-power"
                    :rowspan="row.powerRowspan"
                  >
                    <template v-if="row.slot.device">
                      {{ formatPower(row.slot.device.power) }}
                    </template>
                    <template v-else>—</template>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <footer class="cabinet-footer">
            <span class="legend h-2u">2U</span>
            <span class="legend h-4u">4U</span>
            <span class="legend h-other">其它 U 高</span>
            <span class="legend idle-legend">空闲</span>
          </footer>
        </div>
        <span class="ear right" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.cabinet {
  --rail: #2a3140;
  --panel: #1a1f2a;
  --frame: #3d4658;
  --text: #e8edf5;
  --muted: #8b95a8;
  --idle-bg: rgba(255, 255, 255, 0.04);
  --u2: #1f6f6a;
  --u2-border: #2bb5a8;
  --u4: #8a5a1e;
  --u4-border: #e0a04a;
  --uother: #2f4d7a;
  --uother-border: #6a9adf;
  font-family: 'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif;
  color: var(--text);
  width: auto;
  max-width: none;
}

.cabinet.compact {
  width: auto;
  max-width: none;
  font-size: 12px;
}

.cabinet.compact.style-classic .hostname {
  font-size: clamp(8px, 1.5vw, 11px);
}

.cabinet.compact.style-classic .cell-ip {
  font-size: clamp(7px, 1.4vw, 10px);
}

.cabinet.compact.style-classic .cell-power,
.cabinet.compact.style-classic .cell-u {
  font-size: clamp(7px, 1.3vw, 9px);
}

/* ===== classic (原深色立面) ===== */
.style-classic .cabinet-ears {
  display: flex;
  align-items: stretch;
  gap: 0;
}

.style-classic .ear {
  width: 14px;
  background: linear-gradient(180deg, #4a5568 0%, #2d3544 40%, #1f2530 100%);
  border-radius: 3px;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
  position: relative;
}

.style-classic .ear::before,
.style-classic .ear::after {
  content: '';
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #0d1118;
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.15);
}

.style-classic .ear::before { top: 18%; }
.style-classic .ear::after { bottom: 18%; }

.style-classic .cabinet-body {
  flex: 1;
  background: linear-gradient(180deg, #242b38 0%, var(--panel) 12%, #12161e 100%);
  border: 1px solid var(--frame);
  border-left: none;
  border-right: none;
  box-shadow:
    0 12px 28px rgba(0, 0, 0, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

.style-classic .cabinet-header {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: linear-gradient(180deg, #323a4a, #222936);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.style-classic .rack-code {
  justify-self: center;
  font-family: 'IBM Plex Mono', 'Consolas', monospace;
  font-weight: 700;
  font-size: 15px;
  letter-spacing: 0.06em;
  padding: 4px 14px;
  border-radius: 4px;
  background: #0e1219;
  border: 1px solid rgba(232, 196, 90, 0.45);
  color: #f0d78c;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.4);
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.style-classic .power-chip,
.style-classic .u-chip {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
  font-size: 11px;
}

.style-classic .power-chip { align-items: flex-start; }
.style-classic .u-chip {
  align-items: flex-end;
  color: var(--muted);
  font-weight: 600;
}

.style-classic .power-label {
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-size: 10px;
}

.style-classic .power-value {
  color: #7ddea8;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.style-classic .cabinet-rails {
  padding: 6px 8px 8px;
  max-height: min(62vh, 720px);
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #4a5568 transparent;
}

.style-classic .rack-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

.style-classic .rack-table thead th {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
  font-weight: 600;
  padding: 6px 4px;
  text-align: center;
  background: rgba(0, 0, 0, 0.25);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.style-classic .rack-table .col-u { width: 8%; }
.style-classic .rack-table .col-device { width: 50%; }
.style-classic .rack-table .col-ip { width: 34%; }
.style-classic .rack-table .col-power { width: 8%; }

.style-classic .u-row td {
  padding: 2px 3px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  vertical-align: middle;
  text-align: center;
  box-sizing: border-box;
}

.style-classic .u-row td.cell-u {
  padding: 2px 1px;
  white-space: nowrap;
}

.style-classic .u-row td.cell-power {
  padding: 2px 1px;
  white-space: normal;
  word-break: break-all;
}

.style-classic .u-row.empty td {
  background: var(--idle-bg);
  border-color: rgba(255, 255, 255, 0.04);
}

.style-classic .u-row.selectable { cursor: pointer; }
.style-classic .u-row.selectable:hover td {
  box-shadow: inset 0 0 0 1px rgba(64, 158, 255, 0.55);
}
.style-classic .u-row.selected td { box-shadow: inset 0 0 0 2px #409eff; }
.style-classic .u-row.highlighted td { box-shadow: inset 0 0 0 2px #e6a23c; }

.style-classic .u-row.h-2u td {
  background: linear-gradient(90deg, rgba(31, 111, 106, 0.95), rgba(31, 111, 106, 0.7));
  border-color: var(--u2-border);
}
.style-classic .u-row.h-4u td {
  background: linear-gradient(90deg, rgba(138, 90, 30, 0.95), rgba(138, 90, 30, 0.7));
  border-color: var(--u4-border);
}
.style-classic .u-row.h-other td {
  background: linear-gradient(90deg, rgba(47, 77, 122, 0.95), rgba(47, 77, 122, 0.7));
  border-color: var(--uother-border);
}

.style-classic .u-row.continuation td.cell-u {
  border-top-color: transparent;
}

.style-classic .u-row.occupied:hover td {
  filter: brightness(1.06);
}

.style-classic .cell-u {
  font-family: 'IBM Plex Mono', 'Consolas', monospace;
  font-size: clamp(8px, 1.5vw, 10px);
  font-weight: 600;
  color: #c5cddc;
}

.style-classic .cell-device {
  min-width: 0;
}

.style-classic td.cell-device {
  padding-top: 3px;
  padding-bottom: 3px;
}

.style-classic td.cell-device .device-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-width: 0;
  width: 100%;
  height: 100%;
  text-align: center;
}

.style-classic .hostname {
  display: block;
  width: 100%;
  font-weight: 600;
  font-size: clamp(8px, 1.55vw, 11px);
  overflow: hidden;
  white-space: normal;
  word-break: break-word;
  line-height: 1.25;
  text-align: center;
}

.style-classic .model {
  display: block;
  width: 100%;
  font-size: clamp(7px, 1.3vw, 9px);
  color: rgba(255, 255, 255, 0.65);
  overflow: hidden;
  white-space: normal;
  word-break: break-word;
  line-height: 1.2;
  text-align: center;
}

.style-classic .idle {
  color: var(--muted);
  font-size: clamp(8px, 1.5vw, 11px);
  text-align: center;
}

.style-classic .cell-ip,
.style-classic .cell-power {
  font-variant-numeric: tabular-nums;
  color: #d5dce8;
  overflow: hidden;
}

.style-classic .cell-ip {
  font-size: clamp(7px, 1.4vw, 10px);
  white-space: normal;
  word-break: break-all;
  line-height: 1.3;
  padding-top: 2px;
  padding-bottom: 2px;
  text-align: center;
}

.style-classic .cell-ip.ip-biz,
.style-classic .cell-ip.ip-bmc,
.style-classic .cell-ip.ip-both {
  border-left: 1px solid rgba(255, 255, 255, 0.12);
  border-right: 1px solid rgba(255, 255, 255, 0.12);
}

.style-classic .cell-ip .ip-sub {
  font-size: clamp(7px, 1.25vw, 9px);
  color: #9aa6b8;
  margin-top: 1px;
  text-align: center;
}
.style-classic .cell-ip .ip-sub.vip { color: #c9a86c; }
.style-classic .cell-power {
  font-weight: 600;
  white-space: normal;
  word-break: break-all;
  font-size: clamp(7px, 1.3vw, 10px);
  line-height: 1.2;
  text-align: center;
}

.style-classic .cabinet-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 12px 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(0, 0, 0, 0.2);
}

.style-classic .legend {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid transparent;
}
.style-classic .legend.h-2u { background: var(--u2); border-color: var(--u2-border); }
.style-classic .legend.h-4u { background: var(--u4); border-color: var(--u4-border); }
.style-classic .legend.h-other { background: var(--uother); border-color: var(--uother-border); }
.style-classic .legend.idle-legend {
  background: rgba(255, 255, 255, 0.06);
  color: var(--muted);
  border-color: rgba(255, 255, 255, 0.1);
}

/* ===== schematic ===== */
.style-schematic { color: #1f2937; }
.style-schematic .sch-ears {
  display: flex;
  border: 1px solid #c5ccd6;
  border-radius: 6px;
  background: #e8ecf1;
  overflow: hidden;
}
.style-schematic .sch-ear {
  width: 10px;
  background: linear-gradient(90deg, #d1d5db, #9ca3af);
  flex-shrink: 0;
}
.style-schematic .sch-body {
  flex: 1;
  min-width: 0;
  background: #f7f8fa;
}
.style-schematic .sch-header {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  padding: 6px 10px;
  background: #4b5563;
  color: #e8edf5;
}
.style-schematic .sch-power {
  display: flex;
  gap: 4px;
  font-size: 11px;
  color: #cbd5e1;
}
.style-schematic .sch-power-value,
.style-schematic .sch-u { font-weight: 600; color: #fff; text-align: right; }
.style-schematic .sch-code {
  text-align: center;
  font-weight: 700;
  font-size: 13px;
}
.style-schematic .sch-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  background: #fff;
}
.style-schematic .sch-table thead th {
  padding: 4px 2px;
  font-size: 10px;
  color: #64748b;
  background: #eef1f5;
  text-align: center;
  border-bottom: 1px solid #d5dbe3;
  font-weight: 600;
}
.style-schematic .sch-table thead th:nth-child(1),
.style-schematic .sch-table thead th:nth-child(5) { width: 8%; }
.style-schematic .sch-table thead th:nth-child(2) { width: 50%; }
.style-schematic .sch-table thead th:nth-child(3) { width: 34%; }
.style-schematic .sch-table thead th:nth-child(4) { width: 8%; }
.style-schematic .sch-row td {
  border-bottom: 1px solid #e5e7eb;
  font-size: 11px;
  vertical-align: middle;
  text-align: center;
  box-sizing: border-box;
}
.style-schematic .sch-row.divider td { border-bottom: 1px solid #e5e7eb; }
/* 多 U 合并：着色落在设备/IP/功率上，延续行 U 列去顶边，视觉上连成一块 */
.style-schematic .sch-row.occupied.h-2u .sch-cell-device,
.style-schematic .sch-row.occupied.h-2u .sch-cell-ip,
.style-schematic .sch-row.occupied.h-2u .sch-cell-power { background: #d1fae5; }
.style-schematic .sch-row.occupied.h-4u .sch-cell-device,
.style-schematic .sch-row.occupied.h-4u .sch-cell-ip,
.style-schematic .sch-row.occupied.h-4u .sch-cell-power { background: #fef3c7; }
.style-schematic .sch-row.occupied.h-other .sch-cell-device,
.style-schematic .sch-row.occupied.h-other .sch-cell-ip,
.style-schematic .sch-row.occupied.h-other .sch-cell-power { background: #dbeafe; }
.style-schematic .sch-row.continuation td.sch-cell-u {
  border-top-color: transparent;
}
.style-schematic .sch-row.selectable { cursor: pointer; }
.style-schematic .sch-row.selectable:hover td { background: #eff6ff; }
.style-schematic .sch-row.selectable:hover .sch-cell-u { background: #4b5563 !important; }
.style-schematic .sch-row.selected td { outline: 2px solid #3b82f6; outline-offset: -2px; }
.style-schematic .sch-cell-u {
  text-align: center;
  font-size: 10px;
  color: #fff;
  background: #4b5563 !important;
}
.style-schematic .sch-cell-device {
  padding: 2px 4px;
  min-width: 0;
  text-align: center;
  vertical-align: middle;
}
.style-schematic .sch-device-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  width: 100%;
  height: 100%;
  min-width: 0;
}
.style-schematic .sch-host {
  display: block;
  font-weight: 600;
  font-size: clamp(8px, 1.5vw, 11px);
  overflow: hidden;
  white-space: normal;
  word-break: break-word;
  line-height: 1.25;
  text-align: center;
}
.style-schematic .sch-model {
  display: block;
  font-size: clamp(7px, 1.25vw, 9px);
  color: #64748b;
  text-align: center;
  word-break: break-word;
}
.style-schematic .sch-idle { color: #94a3b8; text-align: center; }
.style-schematic .sch-cell-ip,
.style-schematic .sch-cell-power {
  color: #475569;
  padding: 2px 3px;
  line-height: 1.3;
  text-align: center;
  vertical-align: middle;
}
.style-schematic .sch-cell-ip {
  font-size: clamp(7px, 1.35vw, 10px);
  word-break: break-all;
  white-space: normal;
}
.style-schematic .sch-cell-ip .ip-sub.vip { color: #b45309; }
.style-schematic .sch-cell-power {
  font-weight: 600;
  white-space: normal;
  word-break: break-all;
  font-size: clamp(7px, 1.25vw, 10px);
}
.style-schematic .sch-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 6px 8px;
  background: #eef1f5;
  border-top: 1px solid #d5dbe3;
}
.style-schematic .sch-legend {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
  border: 1px solid transparent;
}
.style-schematic .sch-legend.h-2u { background: #d1fae5; border-color: #6ee7b7; }
.style-schematic .sch-legend.h-4u { background: #fef3c7; border-color: #fcd34d; }
.style-schematic .sch-legend.h-other { background: #dbeafe; border-color: #93c5fd; }
.style-schematic .sch-legend.idle { background: #fff; border-color: #e5e7eb; color: #64748b; }

/* ===== grid ===== */
.style-grid {
  max-width: 280px;
  color: #111;
  background: #fff;
  --grid-line: 1px solid #d1d5db;
}
.style-grid.compact { max-width: 240px; }
.grid-title {
  text-align: center;
  font-weight: 700;
  font-size: 14px;
  padding: 6px 0 8px;
  color: #111827;
}
.grid-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  border: 1px solid #c5ccd6;
  border-radius: 4px;
  overflow: hidden;
  box-sizing: border-box;
}
.grid-row td {
  border-bottom: var(--grid-line);
  box-sizing: border-box;
  vertical-align: middle;
}
.grid-row:last-child td { border-bottom: none; }
.grid-row.divider td { border-bottom: var(--grid-line); }
.grid-u {
  width: 36px;
  text-align: center;
  font-size: 9px;
  background: #f8fafc;
  border-right: var(--grid-line);
  color: #64748b;
}
.grid-row .grid-u:last-child {
  border-right: none;
  border-left: var(--grid-line);
}
.grid-cell {
  text-align: center;
  font-size: 11px;
  font-weight: 600;
  background: #fff;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 4px;
  vertical-align: middle;
}
/* 多 U 设备：中间格 rowspan 合并为一块浅黄底 */
.grid-row.occupied .grid-cell,
.grid-row.span-start .grid-cell { background: #fde68a; }
.grid-row.continuation .grid-u {
  border-top-color: transparent;
}
.grid-row.selectable { cursor: pointer; }
.grid-row.selectable:hover .grid-cell { background: #fef9c3; }
.grid-row.selected .grid-cell {
  box-shadow: inset 0 0 0 1px #2563eb;
}

/* ===== realistic ===== */
.style-realistic { max-width: 300px; }
.style-realistic.compact { max-width: 260px; }
.realistic-frame {
  border: 4px solid #2f3542;
  border-radius: 3px;
  background: #1c212b;
  overflow: hidden;
}
.realistic-top {
  text-align: center;
  font-size: 11px;
  font-weight: 700;
  color: #cbd5e1;
  padding: 6px;
  background: #2f3542;
}
.realistic-main {
  display: flex;
  background: #111827;
}
.u-scale {
  width: 34px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 4px 0;
  background: #1f2937;
  border-right: 1px solid #374151;
}
.u-tick {
  font-size: 8px;
  color: #9ca3af;
  text-align: center;
  line-height: 1;
}
.realistic-rails {
  flex: 1;
  min-width: 0;
  padding: 4px 6px;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.face-row {
  border-radius: 2px;
  overflow: hidden;
}
.face-row.selectable { cursor: pointer; }
.face-row.selected { outline: 2px solid #60a5fa; }
.bay-empty {
  height: 100%;
  background: linear-gradient(180deg, #2a303c, #1f2430);
  border: 1px solid #3b4454;
  border-radius: 2px;
}
.faceplate {
  height: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 8px;
  border-radius: 2px;
  border: 1px solid #4b5563;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.08), transparent 40%),
    #2d3442;
  color: #e5e7eb;
  font-size: 10px;
  min-width: 0;
}
.faceplate.cont { opacity: 0.7; }
.faceplate[data-kind='switch'] {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.06), transparent 35%),
    repeating-linear-gradient(90deg, #1e293b 0 3px, #334155 3px 5px);
}
.faceplate[data-kind='pdu'] {
  background: linear-gradient(90deg, #374151, #1f2937 30%, #374151);
}
.faceplate[data-kind='monitor'] {
  background: linear-gradient(180deg, #0f172a, #1e293b);
}
.faceplate[data-kind='amp'] {
  background: linear-gradient(180deg, #111827, #0b1220);
  border-color: #2563eb;
}
.faceplate[data-kind='storage'] {
  background: linear-gradient(180deg, #1f2937, #111827);
}
.face-badge {
  flex-shrink: 0;
  font-size: 9px;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 2px;
  background: #0ea5e9;
  color: #fff;
}
.face-name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.face-model {
  margin-left: auto;
  color: #94a3b8;
  font-size: 9px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 40%;
}
.realistic-foot {
  text-align: center;
  font-size: 11px;
  color: #94a3b8;
  padding: 6px;
  background: #2f3542;
  border-top: 1px solid #3b4454;
}
</style>
