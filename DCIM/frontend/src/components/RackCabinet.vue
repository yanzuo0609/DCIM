<script setup lang="ts">
import { computed } from 'vue'
import type { RackLayoutDevice, RackLayoutSlot } from '@/api/rack'

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
  }>(),
  {
    slots: () => [],
    totalPower: 0,
    compact: false,
    selectable: false,
    selectedU: null,
    highlightDeviceId: null,
  },
)

const emit = defineEmits<{
  'select-u': [u: number]
}>()

function onSlotClick(slot: RackLayoutSlot) {
  if (!props.selectable || slot.occupied) return
  emit('select-u', slot.u_position)
}

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

const unitPx = computed(() => (props.compact ? 22 : 28))

function heightClass(device: RackLayoutDevice | null | undefined) {
  if (!device) return ''
  if (device.height_u === 2) return 'h-2u'
  if (device.height_u === 4) return 'h-4u'
  return 'h-other'
}

function heightBadge(device: RackLayoutDevice) {
  if (device.height_u === 2) return '2U'
  if (device.height_u === 4) return '4U'
  return `${device.height_u}U`
}

function formatPower(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return '—'
  if (value >= 1000) return `${(value / 1000).toFixed(1)} kW`
  return `${Math.round(value)} W`
}

function rowStyle(_slot: RackLayoutSlot) {
  return { height: `${unitPx.value}px` }
}

function isContinuation(slot: RackLayoutSlot) {
  return slot.occupied && !slot.is_span_start && !!slot.device
}
</script>

<template>
  <div class="cabinet" :class="{ compact }">
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

        <div class="col-headers">
          <span class="col-u">U</span>
          <span class="col-device">设备 / 空闲</span>
          <span class="col-ip">IP</span>
          <span class="col-power">功率</span>
        </div>

        <div class="cabinet-rails">
          <div
            v-for="slot in displaySlots"
            :key="slot.u_position"
            class="u-row"
            :class="[
              {
                empty: !slot.occupied,
                occupied: !!slot.device,
                continuation: isContinuation(slot),
                'span-start': slot.is_span_start,
                selectable: selectable && !slot.occupied,
                selected: selectable && selectedU === slot.u_position,
                highlighted:
                  !!highlightDeviceId && slot.device?.device_id === highlightDeviceId,
              },
              heightClass(slot.device),
            ]"
            :style="rowStyle(slot)"
            @click="onSlotClick(slot)"
          >
            <div class="cell-u">U{{ slot.u_position }}</div>

            <div class="cell-device">
              <template v-if="slot.is_span_start && slot.device">
                <span class="height-badge">{{ heightBadge(slot.device) }}</span>
                <div class="device-meta">
                  <span class="hostname">{{ slot.device.hostname }}</span>
                  <span v-if="slot.device.model_name" class="model">{{ slot.device.model_name }}</span>
                </div>
              </template>
              <template v-else-if="isContinuation(slot)">
                <span class="cont-mark">│</span>
              </template>
              <template v-else>
                <span class="idle">空闲</span>
              </template>
            </div>

            <div class="cell-ip">
              <template v-if="slot.is_span_start && slot.device">
                <div>{{ slot.device.ip_summary || '—' }}</div>
                <div v-if="slot.device.bmc_ip" class="ip-sub">BMC {{ slot.device.bmc_ip }}</div>
                <div v-if="slot.device.vip" class="ip-sub vip">VIP {{ slot.device.vip }}</div>
              </template>
              <template v-else-if="isContinuation(slot)" />
              <template v-else>—</template>
            </div>

            <div class="cell-power">
              <template v-if="slot.is_span_start && slot.device">
                {{ formatPower(slot.device.power) }}
              </template>
              <template v-else-if="isContinuation(slot)" />
              <template v-else>—</template>
            </div>
          </div>
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
  width: 100%;
  max-width: 420px;
}

.cabinet.compact {
  max-width: 360px;
  font-size: 12px;
}

.cabinet-ears {
  display: flex;
  align-items: stretch;
  gap: 0;
}

.ear {
  width: 14px;
  background: linear-gradient(180deg, #4a5568 0%, #2d3544 40%, #1f2530 100%);
  border-radius: 3px;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
  position: relative;
}

.ear::before,
.ear::after {
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

.ear::before {
  top: 18%;
}

.ear::after {
  bottom: 18%;
}

.cabinet-body {
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

.cabinet-header {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: linear-gradient(180deg, #323a4a, #222936);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.rack-code {
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

.power-chip,
.u-chip {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
  font-size: 11px;
}

.power-chip {
  align-items: flex-start;
}

.u-chip {
  align-items: flex-end;
  color: var(--muted);
  font-weight: 600;
}

.power-label {
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-size: 10px;
}

.power-value {
  color: #7ddea8;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.col-headers {
  display: grid;
  grid-template-columns: 52px 1.4fr 0.9fr 0.7fr;
  gap: 4px;
  padding: 6px 10px;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
  background: rgba(0, 0, 0, 0.25);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.cabinet-rails {
  padding: 6px 8px 8px;
  max-height: min(62vh, 720px);
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #4a5568 transparent;
}

.u-row {
  display: grid;
  grid-template-columns: 52px 1.4fr 0.9fr 0.7fr;
  gap: 4px;
  align-items: center;
  margin-bottom: 2px;
  padding: 0 6px;
  border-radius: 3px;
  border: 1px solid transparent;
  box-sizing: border-box;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.u-row.empty {
  background: var(--idle-bg);
  border-color: rgba(255, 255, 255, 0.04);
}

.u-row.selectable {
  cursor: pointer;
}

.u-row.selectable:hover {
  box-shadow: inset 0 0 0 1px rgba(64, 158, 255, 0.55);
}

.u-row.selected {
  box-shadow: inset 0 0 0 2px #409eff;
}

.u-row.highlighted {
  box-shadow: inset 0 0 0 2px #e6a23c;
}

.u-row.occupied {
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.u-row.h-2u {
  background: linear-gradient(90deg, rgba(31, 111, 106, 0.95), rgba(31, 111, 106, 0.7));
  border-color: var(--u2-border);
}

.u-row.h-4u {
  background: linear-gradient(90deg, rgba(138, 90, 30, 0.95), rgba(138, 90, 30, 0.7));
  border-color: var(--u4-border);
}

.u-row.h-other {
  background: linear-gradient(90deg, rgba(47, 77, 122, 0.95), rgba(47, 77, 122, 0.7));
  border-color: var(--uother-border);
}

.u-row.continuation {
  margin-top: -2px;
  border-top-color: transparent;
  border-radius: 0;
}

.u-row.span-start {
  border-radius: 3px 3px 0 0;
}

.u-row.span-start:not(:has(+ .continuation)) {
  border-radius: 3px;
}

.u-row.continuation:last-child,
.u-row.occupied + .u-row.empty {
  border-radius: 0 0 3px 3px;
}

.cont-mark {
  color: rgba(255, 255, 255, 0.35);
  font-size: 12px;
  padding-left: 18px;
}

.u-row.occupied:hover {
  transform: translateX(1px);
  filter: brightness(1.06);
}

.cell-u {
  font-family: 'IBM Plex Mono', 'Consolas', monospace;
  font-size: 11px;
  font-weight: 600;
  color: #c5cddc;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.u-range-sub {
  font-size: 9px;
  color: rgba(255, 255, 255, 0.55);
  font-weight: 500;
}

.cell-device {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.height-badge {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 2px;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.device-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.hostname {
  font-weight: 600;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.65);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.idle {
  color: var(--muted);
  font-size: 12px;
}

.cell-ip,
.cell-power {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  color: #d5dce8;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cell-ip {
  white-space: normal;
  line-height: 1.25;
}

.cell-ip .ip-sub {
  font-size: 10px;
  color: #9aa6b8;
  margin-top: 1px;
}

.cell-ip .ip-sub.vip {
  color: #c9a86c;
}

.cell-power {
  text-align: right;
  font-weight: 600;
  white-space: nowrap;
}

.cabinet-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 12px 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(0, 0, 0, 0.2);
}

.legend {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid transparent;
}

.legend.h-2u {
  background: var(--u2);
  border-color: var(--u2-border);
}

.legend.h-4u {
  background: var(--u4);
  border-color: var(--u4-border);
}

.legend.h-other {
  background: var(--uother);
  border-color: var(--uother-border);
}

.legend.idle-legend {
  background: rgba(255, 255, 255, 0.06);
  color: var(--muted);
  border-color: rgba(255, 255, 255, 0.1);
}
</style>
