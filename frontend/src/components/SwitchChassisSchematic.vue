<script setup lang="ts">
import { computed, ref } from 'vue'
import { ifaceBoardTwoRowLabels } from '@/utils/switchFrontPanel'
import SwitchSquarePort from '@/components/SwitchSquarePort.vue'
import {
  CHASSIS_DEMO,
  accessPortFace,
  buildChassisDisplayRows,
  rackPanelAspect,
  effectivePortCount,
  IFACE_BOARD_KIND_SHORT,
  resolveSlotPort,
  slotCardToIfaceBoard,
  type SwitchSlotAttr,
} from '@/utils/switchModelAttrs'

const props = defineProps<{
  heightU: number
  slots: SwitchSlotAttr[]
  blankRows?: number[]
  editable?: boolean
  selectedPort?: { slotIndex: number; portIndex: number } | null
}>()

const emit = defineEmits<{
  moveBlank: [fromRow: number, toRow: number]
  moveSlot: [fromSlot: number, toSlot: number]
  nudgeBlank: [fromRow: number, dir: -1 | 1]
  selectPort: [payload: { slotIndex: number; portIndex: number }]
  inspectPort: [payload: { slotIndex: number; portIndex: number; x: number; y: number }]
}>()

const heightRows = computed(() => Math.max(1, Math.min(48, Math.trunc(props.heightU) || 1)))
const slotList = computed(() => (Array.isArray(props.slots) && props.slots.length ? props.slots : []))
const displayRows = computed(() =>
  buildChassisDisplayRows(heightRows.value, slotList.value, props.blankRows || []),
)
const frameStyle = computed(() => ({
  aspectRatio: rackPanelAspect(heightRows.value),
  maxWidth: `${CHASSIS_DEMO.maxW}px`,
}))
const blankCount = computed(() => displayRows.value.filter((r) => r.filler).length)
const dragFrom = ref<number | null>(null)
const dropOver = ref<number | null>(null)

function isFilled(slot: SwitchSlotAttr | null) {
  if (!slot) return false
  return slot.card_type !== 'blank' && slot.purpose !== 'BLANK' && effectivePortCount(slot) > 0
}

function boardShort(slot: SwitchSlotAttr) {
  return IFACE_BOARD_KIND_SHORT[slotCardToIfaceBoard(slot.card_type)] || ''
}

function portLabels(slot: SwitchSlotAttr) {
  return ifaceBoardTwoRowLabels(effectivePortCount(slot), Math.max(0, Number(slot.port_start) || 0))
}

function gridStyle(slot: SwitchSlotAttr) {
  const n = effectivePortCount(slot)
  const highSpeed = ['40g', '100g', '400g'].includes(slot.card_type)
  const rows = n <= 1 ? 1 : 2
  const cols = Math.max(1, Math.ceil(n / rows))
  return {
    gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
    gridTemplateRows: `repeat(${rows}, minmax(0, 1fr))`,
    gridAutoFlow: rows === 1 ? 'row' : 'column',
    gap: highSpeed ? '3px 5px' : '2px 2px',
    padding: highSpeed ? '5px 12px' : '4px 8px',
  }
}

function onDragStart(row: number, ev: DragEvent) {
  if (!props.editable) return
  const t = ev.target as HTMLElement | null
  if (t?.closest('.sw-port')) {
    ev.preventDefault()
    return
  }
  dragFrom.value = row
  ev.dataTransfer?.setData('text/plain', String(row))
  if (ev.dataTransfer) ev.dataTransfer.effectAllowed = 'move'
}

function isPortSelected(slotNo: number | null, portIndex: number) {
  const sel = props.selectedPort
  return !!sel && slotNo != null && sel.slotIndex === slotNo && sel.portIndex === portIndex
}

function onPortClick(slot: SwitchSlotAttr, portIndex: number, ev: MouseEvent) {
  ev.preventDefault()
  ev.stopPropagation()
  emit('selectPort', { slotIndex: slot.index, portIndex })
}

function onPortContext(slot: SwitchSlotAttr, portIndex: number, ev: MouseEvent) {
  ev.preventDefault()
  ev.stopPropagation()
  emit('inspectPort', { slotIndex: slot.index, portIndex, x: ev.clientX, y: ev.clientY })
}

function portTitle(slot: SwitchSlotAttr, portIndex: number, lab: string) {
  const spec = resolveSlotPort(slot, portIndex)
  return `${spec.code} · ${spec.id} · Slot ${slot.index} 第 ${portIndex + 1} 口 · ${lab} · ${spec.speed} ${spec.module}`
}

function onDragOver(row: number, ev: DragEvent) {
  if (!props.editable || dragFrom.value == null) return
  ev.preventDefault()
  if (ev.dataTransfer) ev.dataTransfer.dropEffect = 'move'
  dropOver.value = row
}

function onDrop(row: number, ev: DragEvent) {
  ev.preventDefault()
  const from = dragFrom.value
  dragFrom.value = null
  dropOver.value = null
  if (!props.editable || from == null || from === row) return
  const fromRow = displayRows.value.find((item) => item.row === from)
  const toRow = displayRows.value.find((item) => item.row === row)
  if (!fromRow || !toRow) return
  if (!fromRow.filler && !toRow.filler && fromRow.slotNo != null && toRow.slotNo != null) {
    emit('moveSlot', fromRow.slotNo, toRow.slotNo)
    return
  }
  emit('moveBlank', from, row)
}

function onDragEnd() {
  dragFrom.value = null
  dropOver.value = null
}
</script>

<template>
  <div
    class="chassis"
    :style="frameStyle"
    :title="`${heightU}U · 扩展槽 ${slotList.length}${blankCount ? ` · 空白面板 ${blankCount}` : ''}`"
  >
    <span class="rack-ear ear-left"><i /><i /><i /></span>
    <span class="rack-ear ear-right"><i /><i /><i /></span>
    <div class="chassis-inner">
      <div class="chassis-head">
        <span class="vendor-mark">MODULAR CORE</span>
        <span class="status-led on" />
        <span class="status-led" />
        <span class="chassis-meta">{{ heightU }}U · {{ slotList.length }} SLOT</span>
      </div>
      <div class="slot-stack">
        <div
          v-for="row in displayRows"
          :key="row.row"
          class="exp-slot"
          :class="{
            filled: isFilled(row.slot),
            empty: !row.filler && !isFilled(row.slot),
            filler: row.filler,
            dragging: dragFrom === row.row,
            drop: dropOver === row.row && dragFrom !== row.row,
            editable,
          }"
          :draggable="!!editable"
          @dragstart="onDragStart(row.row, $event)"
          @dragover="onDragOver(row.row, $event)"
          @drop="onDrop(row.row, $event)"
          @dragend="onDragEnd"
        >
          <span
            v-if="!row.filler && row.slotNo != null"
            class="slot-no"
            :title="`Slot ${row.slotNo}`"
          >{{ row.slotNo }}</span>
          <span v-else-if="row.filler" class="slot-no filler-no" title="空白面板">空</span>
          <div v-if="row.slot && isFilled(row.slot)" class="board-body">
            <span v-if="editable" class="board-grip" title="按住拖动接口板">⋮⋮</span>
            <span class="board-kind">{{ boardShort(row.slot) }}</span>
            <div class="port-grid" :style="gridStyle(row.slot)">
              <button
                v-for="(lab, pi) in portLabels(row.slot)"
                :key="`${row.row}-${pi}`"
                type="button"
                class="sw-port"
                :class="{ selected: isPortSelected(row.slotNo, pi) }"
                :title="portTitle(row.slot, pi, lab)"
                @mousedown.stop
                @click.stop="onPortClick(row.slot, pi, $event)"
                @contextmenu.prevent="onPortContext(row.slot, pi, $event)"
              >
                <SwitchSquarePort
                  :kind="accessPortFace(resolveSlotPort(row.slot, pi))"
                  :speed="resolveSlotPort(row.slot, pi).speed"
                  :label="lab"
                  :selected="isPortSelected(row.slotNo, pi)"
                />
              </button>
            </div>
          </div>
          <span v-else-if="row.filler" class="filler-lab">机框空白面板</span>
          <span v-else class="empty-slot-lab">EMPTY SLOT · 可拖入接口板</span>
          <div v-if="editable && row.filler" class="filler-nav" @mousedown.stop>
            <button
              type="button"
              class="filler-btn"
              title="上移"
              :disabled="row.row <= 1"
              @click.stop="emit('nudgeBlank', row.row, -1)"
            >
              ↑
            </button>
            <button
              type="button"
              class="filler-btn"
              title="下移"
              :disabled="row.row >= heightRows"
              @click.stop="emit('nudgeBlank', row.row, 1)"
            >
              ↓
            </button>
          </div>
        </div>
      </div>
      <div class="bay-row">
        <span class="bay control"><b>MPU</b><i /><i /></span>
        <span class="bay fabric"><b>SFU</b><i /><i /><i /></span>
        <span class="bay fan"><b>FAN</b><i /></span>
        <span class="bay power"><b>POWER</b><i /><i /></span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chassis {
  box-sizing: border-box;
  width: 100%;
  position: relative;
  padding: 5px 14px;
  overflow: hidden;
  background: linear-gradient(145deg, #8b949c 0%, #38434d 18%, #202a33 82%, #66717a 100%);
  border: 2px solid #1c252d;
  border-radius: 3px;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,.28), 0 5px 16px rgba(21,33,43,.22);
}
.rack-ear { position: absolute; top: 3px; bottom: 3px; width: 9px; display: flex; flex-direction: column; justify-content: space-around; align-items: center; background: linear-gradient(90deg,#2e3942,#77828b 50%,#252f37); border: 1px solid #111920; z-index: 2; }
.rack-ear i { width: 4px; height: 4px; border-radius: 50%; background: #0d1216; box-shadow: 0 0 0 1px #aeb6bc; }
.ear-left { left: 2px; }
.ear-right { right: 2px; transform: scaleX(-1); }
.chassis-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #c5c9cf;
  border: 1px solid #8a9098;
  box-sizing: border-box;
}
.chassis-head { flex: 0 0 16px; display: flex; align-items: center; gap: 5px; padding: 0 7px; color: #d7e6ee; background: linear-gradient(180deg,#303b44,#172129); border-bottom: 1px solid #0d1419; font: 700 7px/1 Arial; letter-spacing: .08em; }
.vendor-mark { margin-right: auto; color: #e8f2f6; }
.chassis-meta { color: #8497a3; font-weight: 600; }
.status-led { width: 4px; height: 4px; border-radius: 50%; background: #48535b; box-shadow: inset 0 0 0 1px #1a2228; }
.status-led.on { background: #63d66e; box-shadow: 0 0 4px #63d66e; }
.slot-stack {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 0 6px 4px;
  min-height: 0;
}
.exp-slot {
  position: relative;
  display: flex;
  align-items: stretch;
  flex: 1 1 0;
  min-height: 0;
  min-height: 28px;
  height: auto;
  background: #fff;
  border: 1.5px solid #7ed321;
  box-sizing: border-box;
  user-select: none;
}
.exp-slot.filler {
  background: repeating-linear-gradient(90deg,#7c858c 0 3px,#515a61 3px 6px);
  border-color: #333d45;
}
.exp-slot.empty { background: linear-gradient(180deg,#2d3740,#182129); border-color: #52616d; box-shadow: inset 0 0 8px rgba(0,0,0,.65); }
.exp-slot.editable {
  cursor: grab;
}
.exp-slot.dragging {
  opacity: 0.55;
}
.exp-slot.drop {
  outline: 1px dashed #409eff;
  outline-offset: -1px;
}
.slot-no {
  flex: 0 0 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 700;
  color: #4a5560;
  background: #e8eaed;
  border-right: 1px solid #c5c9cf;
  user-select: none;
}
.filler-no {
  font-size: 8px;
  color: #909399;
  background: #dde1e6;
}
.filler-lab {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  color: #909399;
  user-select: none;
}
.filler-nav {
  display: flex;
  flex-direction: column;
  justify-content: center;
  flex: 0 0 16px;
}
.filler-btn {
  height: 11px;
  padding: 0;
  border: 0;
  background: transparent;
  color: #606266;
  font-size: 9px;
  line-height: 1;
  cursor: pointer;
}
.filler-btn:disabled {
  opacity: 0.3;
  cursor: default;
}
.board-body {
  position: relative;
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  padding: 1px 3px 1px 11px;
  background: linear-gradient(180deg,#dfe5e8 0%,#aeb8be 48%,#8e999f 100%);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,.65), inset 0 -2px 3px rgba(34,49,59,.22);
}
.board-grip { position: absolute; left: 2px; top: 50%; z-index: 3; transform: translateY(-50%); color: #40515c; font-size: 10px; line-height: 8px; cursor: grab; }
.empty-slot-lab { flex: 1; display: flex; align-items: center; justify-content: center; color: #71818d; font: 700 7px Arial; letter-spacing: .12em; }
.board-kind {
  position: absolute;
  top: 0;
  right: 2px;
  z-index: 1;
  font-size: 8px;
  font-weight: 700;
  color: #16324f;
  background: rgba(255, 255, 255, 0.82);
  padding: 0 3px;
  line-height: 10px;
  pointer-events: none;
}
.port-grid {
  flex: 1 1 auto;
  display: grid;
  min-width: 0;
  min-height: 0;
  padding: 4px 8px;
  gap: 2px;
}
.sw-port {
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  border: 0;
  background: transparent;
  min-width: 0;
  min-height: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
  padding: 0;
  cursor: pointer;
}
.sw-port :deep(.sq-port) { width: 100%; height: 100%; min-height: 8px; border-radius: 1px; }
.sw-port :deep(.is-copper) { max-width: 34px; aspect-ratio: 1.08; }
.sw-port :deep(.is-optical) { max-width: 28px; aspect-ratio: .82; }
.sw-port :deep(.is-mpo) { max-width: 42px; aspect-ratio: 1.35; }
.sw-port:hover :deep(.sq-port) {
  outline: 1px solid #79bbff;
  outline-offset: -1px;
}
.bay-row {
  flex: 0 0 14px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 3px;
  padding: 2px 6px 5px;
}
.bay { display: flex; align-items: center; gap: 3px; height: 12px; padding: 0 3px; color: #d8e0e4; background: linear-gradient(180deg,#4c5962,#252f36); border: 1px solid #151d23; box-shadow: inset 0 0 0 1px rgba(255,255,255,.12); font: 700 6px Arial; }
.bay b { margin-right: auto; font-size: 6px; }
.bay i { width: 4px; height: 4px; border-radius: 50%; background: #5b6972; }
.bay.control i:first-of-type,.bay.power i:first-of-type { background: #5dd76d; box-shadow: 0 0 3px #5dd76d; }
.bay.fabric { background: linear-gradient(180deg,#566875,#293942); }
.bay.fan i { width: 9px; height: 9px; background: repeating-radial-gradient(circle,#151b1f 0 1px,#65727a 2px 3px); }
</style>
