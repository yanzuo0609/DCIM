<script setup lang="ts">
import { computed, ref } from 'vue'
import { ifaceBoardTwoRowLabels } from '@/utils/switchFrontPanel'
import SwitchSquarePort from '@/components/SwitchSquarePort.vue'
import {
  CHASSIS_DEMO,
  accessPortFace,
  buildChassisDisplayRows,
  chassisDemoHeight,
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
  nudgeBlank: [fromRow: number, dir: -1 | 1]
  selectPort: [payload: { slotIndex: number; portIndex: number }]
  inspectPort: [payload: { slotIndex: number; portIndex: number; x: number; y: number }]
}>()

const heightRows = computed(() => Math.max(1, Math.min(48, Math.trunc(props.heightU) || 1)))
const slotList = computed(() => (Array.isArray(props.slots) && props.slots.length ? props.slots : []))
const displayRows = computed(() =>
  buildChassisDisplayRows(heightRows.value, slotList.value, props.blankRows || []),
)
const frameHeight = computed(() => chassisDemoHeight(heightRows.value))
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
  const rows = n <= 1 ? 1 : 2
  const cols = Math.max(1, Math.ceil(n / rows))
  return {
    gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
    gridTemplateRows: `repeat(${rows}, minmax(0, 1fr))`,
    gridAutoFlow: rows === 1 ? 'row' : 'column',
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
    :style="{ height: `${frameHeight}px`, maxWidth: `${CHASSIS_DEMO.maxW}px` }"
    :title="`${heightU}U · 扩展槽 ${slotList.length}${blankCount ? ` · 空白面板 ${blankCount}` : ''}`"
  >
    <div class="chassis-inner">
      <div class="top-space" />
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
                  :label="lab"
                  :selected="isPortSelected(row.slotNo, pi)"
                />
              </button>
            </div>
          </div>
          <span v-else-if="row.filler" class="filler-lab">空白面板</span>
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
        <span v-for="b in 4" :key="b" class="bay" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.chassis {
  box-sizing: border-box;
  width: 100%;
  padding: 5px;
  background: #4a5560;
  border: 2px solid #2c3540;
  border-radius: 2px;
}
.chassis-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #c5c9cf;
  border: 1px solid #8a9098;
  box-sizing: border-box;
}
.top-space {
  flex: 0 0 12px;
  background: #c5c9cf;
}
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
  height: 24px;
  max-height: 24px;
  background: #fff;
  border: 1.5px solid #7ed321;
  box-sizing: border-box;
  user-select: none;
}
.exp-slot.filler {
  background: #eceff3;
  border-color: #9aa3ad;
}
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
}
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
  padding: 1px;
  gap: 0;
}
.sw-port {
  display: block;
  box-sizing: border-box;
  border: 0;
  background: transparent;
  min-width: 0;
  min-height: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  padding: 0;
  cursor: pointer;
}
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
.bay {
  display: block;
  height: 10px;
  background: #6a6e74;
  border: 1px solid #4a4e54;
}
</style>
