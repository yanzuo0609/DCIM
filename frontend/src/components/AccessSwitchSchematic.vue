<script setup lang="ts">
import { computed } from 'vue'
import SwitchSquarePort from '@/components/SwitchSquarePort.vue'
import {
  ACCESS_DEMO,
  rackPanelAspect,
  accessPortFace,
  effectivePortCount,
  resolveSlotPort,
  type SwitchSlotAttr,
} from '@/utils/switchModelAttrs'
import type { UplinkPosition } from '@/api/network'

const props = defineProps<{
  downlink: SwitchSlotAttr | null
  uplink: SwitchSlotAttr | null
  uplinkPosition?: UplinkPosition
  selectedPort?: { slotIndex: number; portIndex: number } | null
}>()

const emit = defineEmits<{
  selectPort: [payload: { slotIndex: number; portIndex: number }]
  inspectPort: [payload: { slotIndex: number; portIndex: number; x: number; y: number }]
}>()

const downCount = computed(() => (props.downlink ? effectivePortCount(props.downlink) : 0))
const upCount = computed(() => (props.uplink ? effectivePortCount(props.uplink) : 0))
const middle = computed(() => props.uplinkPosition === 'middle' && upCount.value > 0 && downCount.value > 0)
const position = computed(() => (props.uplinkPosition === 'middle' ? 'middle' : 'right'))
const downHalf = computed(() => Math.ceil(downCount.value / 2))

const leftIndexes = computed(() => {
  const n = middle.value ? downHalf.value : downCount.value
  return Array.from({ length: n }, (_, i) => i)
})
const rightIndexes = computed(() => {
  if (!middle.value) return []
  return Array.from({ length: downCount.value - downHalf.value }, (_, i) => downHalf.value + i)
})
const upIndexes = computed(() => Array.from({ length: upCount.value }, (_, i) => i))

function downGridStyle(count: number) {
  const n = Math.max(1, count)
  const rows = n <= 1 ? 1 : 2
  const cols = Math.max(1, Math.ceil(n / rows))
  return {
    gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
    gridTemplateRows: `repeat(${rows}, minmax(0, 1fr))`,
    gridAutoFlow: rows === 1 ? 'row' : 'column',
  }
}

const upGridStyle = computed(() => {
  const n = Math.max(1, upCount.value)
  const rows = n <= 1 ? 1 : 2
  const cols = Math.max(1, Math.ceil(n / rows))
  return {
    gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
    gridTemplateRows: `repeat(${rows}, minmax(0, 1fr))`,
    gridAutoFlow: rows === 1 ? 'row' : 'column',
  }
})

function isSelected(slotIndex: number, portIndex: number) {
  const sel = props.selectedPort
  return !!sel && sel.slotIndex === slotIndex && sel.portIndex === portIndex
}

function onClick(slot: SwitchSlotAttr, portIndex: number, ev: MouseEvent) {
  ev.preventDefault()
  ev.stopPropagation()
  emit('selectPort', { slotIndex: slot.index, portIndex })
}

function onContext(slot: SwitchSlotAttr, portIndex: number, ev: MouseEvent) {
  ev.preventDefault()
  ev.stopPropagation()
  emit('inspectPort', { slotIndex: slot.index, portIndex, x: ev.clientX, y: ev.clientY })
}

function portTitle(slot: SwitchSlotAttr, portIndex: number) {
  const spec = resolveSlotPort(slot, portIndex)
  return `${spec.code} · ${spec.id} · ${spec.speed} ${spec.module}`
}

function portLab(slot: SwitchSlotAttr, portIndex: number) {
  if (slot.purpose === 'UPLINK') return String(portIndex)
  return String(Math.max(0, Number(slot.port_start) || 0) + portIndex)
}

function portKind(slot: SwitchSlotAttr, portIndex: number) {
  return accessPortFace(resolveSlotPort(slot, portIndex))
}

const frameStyle = computed(() => ({
  aspectRatio: rackPanelAspect(1),
  maxWidth: `${ACCESS_DEMO.maxW}px`,
}))
</script>

<template>
  <div class="access-chassis" :style="frameStyle">
    <div class="access-inner">
      <div class="port-band">
        <div v-if="downlink && leftIndexes.length" class="port-block">
          <div class="port-grid" :style="downGridStyle(leftIndexes.length)">
            <button
              v-for="pi in leftIndexes"
              :key="`d-${pi}`"
              type="button"
              class="sw-port"
              :class="{ selected: isSelected(downlink.index, pi) }"
              :title="portTitle(downlink, pi)"
              @click.stop="onClick(downlink, pi, $event)"
              @contextmenu.prevent="onContext(downlink, pi, $event)"
            >
              <SwitchSquarePort
                :kind="portKind(downlink, pi)"
                :label="portLab(downlink, pi)"
                :selected="isSelected(downlink.index, pi)"
              />
            </button>
          </div>
        </div>
        <div v-if="uplink && upCount && (middle || position !== 'right')" class="port-block up">
          <div class="port-grid" :style="upGridStyle">
            <button
              v-for="pi in upIndexes"
              :key="`u-${pi}`"
              type="button"
              class="sw-port"
              :class="{ selected: isSelected(uplink.index, pi) }"
              :title="portTitle(uplink, pi)"
              @click.stop="onClick(uplink, pi, $event)"
              @contextmenu.prevent="onContext(uplink, pi, $event)"
            >
              <SwitchSquarePort
                :kind="portKind(uplink, pi)"
                :label="portLab(uplink, pi)"
                :selected="isSelected(uplink.index, pi)"
              />
            </button>
          </div>
        </div>
        <div v-if="downlink && rightIndexes.length" class="port-block">
          <div class="port-grid" :style="downGridStyle(rightIndexes.length)">
            <button
              v-for="pi in rightIndexes"
              :key="`d-${pi}`"
              type="button"
              class="sw-port"
              :class="{ selected: isSelected(downlink.index, pi) }"
              :title="portTitle(downlink, pi)"
              @click.stop="onClick(downlink, pi, $event)"
              @contextmenu.prevent="onContext(downlink, pi, $event)"
            >
              <SwitchSquarePort
                :kind="portKind(downlink, pi)"
                :label="portLab(downlink, pi)"
                :selected="isSelected(downlink.index, pi)"
              />
            </button>
          </div>
        </div>
        <div v-if="uplink && upCount && !middle && position === 'right'" class="port-block up">
          <div class="port-grid" :style="upGridStyle">
            <button
              v-for="pi in upIndexes"
              :key="`ur-${pi}`"
              type="button"
              class="sw-port"
              :class="{ selected: isSelected(uplink.index, pi) }"
              :title="portTitle(uplink, pi)"
              @click.stop="onClick(uplink, pi, $event)"
              @contextmenu.prevent="onContext(uplink, pi, $event)"
            >
              <SwitchSquarePort
                :kind="portKind(uplink, pi)"
                :label="portLab(uplink, pi)"
                :selected="isSelected(uplink.index, pi)"
              />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.access-chassis {
  box-sizing: border-box;
  width: 100%;
  padding: 4px;
  background: #cfd4db;
  border: 2px solid #2c3e50;
  border-radius: 2px;
}
.access-inner {
  height: 100%;
  display: flex;
  align-items: stretch;
  padding: 6px 8px;
  background: #d8dde3;
  border: 1px solid #8a9098;
  box-sizing: border-box;
}
.port-band {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: stretch;
  gap: 8px;
}
.port-block {
  display: flex;
  min-width: 0;
  background: #eef1f4;
  border: 1.5px solid #7ed321;
  flex: 1 1 auto;
}
.port-block.up {
  flex: 0 0 22%;
  max-width: 120px;
}
.port-grid {
  flex: 1 1 auto;
  display: grid;
  min-width: 0;
  min-height: 0;
  padding: 3px;
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
</style>
