<script setup lang="ts">
import { computed } from 'vue'
import SwitchSquarePort from '@/components/SwitchSquarePort.vue'
import {
  SERVER_DEMO,
  frontDriveGrid,
  normalizeDiskSize,
  normalizeServerFormFactor,
  type ServerDiskSize,
  type ServerFormFactorU,
  type ServerPortAttr,
} from '@/utils/serverModelAttrs'

const props = withDefaults(
  defineProps<{
    heightU?: number
    diskCount?: number
    diskSize?: ServerDiskSize | string
    diskProto?: string
    usbPorts?: ServerPortAttr[]
    vgaPorts?: ServerPortAttr[]
    selectedPortId?: string | null
  }>(),
  { heightU: 1, diskCount: 4, diskSize: '3.5', diskProto: 'sas_sata', usbPorts: () => [], vgaPorts: () => [] },
)

const emit = defineEmits<{
  selectPort: [portId: string]
  inspectPort: [portId: string, ev: MouseEvent]
}>()

const u = computed<ServerFormFactorU>(() => normalizeServerFormFactor(props.heightU))
const size = computed(() => normalizeDiskSize(props.diskSize, u.value === 1 ? '3.5' : '3.5'))
const grid = computed(() => frontDriveGrid(u.value, props.diskCount || 0, size.value))
const frameStyle = computed(() => ({
  aspectRatio: SERVER_DEMO.aspect(u.value),
}))
const frontUsb = computed(() => (props.usbPorts || []).slice(0, Math.min(2, (props.usbPorts || []).length)))
const frontVga = computed(() => (u.value >= 2 ? (props.vgaPorts || []).slice(0, 1) : []))

const driveStyle = computed(() => ({
  gridTemplateColumns: `repeat(${Math.max(1, grid.value.cols)}, minmax(0, 1fr))`,
  gridTemplateRows: `repeat(${Math.max(1, grid.value.rows)}, minmax(0, 1fr))`,
}))

function bayId(i: number) {
  return `ID:${String(i).padStart(2, '0')}`
}

function onClick(id: string, ev: MouseEvent) {
  ev.preventDefault()
  ev.stopPropagation()
  emit('selectPort', id)
}

function onContext(id: string, ev: MouseEvent) {
  ev.preventDefault()
  ev.stopPropagation()
  emit('inspectPort', id, ev)
}
</script>

<template>
  <div class="srv-front" :class="`u${u}`" :style="frameStyle">
    <div class="ear left-ear">
      <span class="pwr" title="电源" />
      <span class="uid" title="UID" />
      <span class="leds">
        <i class="ok" />
        <i class="net" />
        <i class="warn" />
      </span>
      <template v-if="u >= 2 && frontUsb.length">
        <button
          v-for="p in frontUsb"
          :key="p.id"
          type="button"
          class="mini-port"
          :class="{ selected: selectedPortId === p.id }"
          :title="`${p.code} · ${p.id}`"
          @click="onClick(p.id, $event)"
          @contextmenu="onContext(p.id, $event)"
        >
          <SwitchSquarePort kind="copper" />
        </button>
      </template>
    </div>
    <div class="face">
      <div v-if="u === 1" class="top-strip">
        <span class="vent" />
        <div class="io-inline">
          <button
            v-for="p in frontUsb"
            :key="p.id"
            type="button"
            class="mini-port"
            :class="{ selected: selectedPortId === p.id }"
            :title="`${p.code} · ${p.id}`"
            @click="onClick(p.id, $event)"
            @contextmenu="onContext(p.id, $event)"
          >
            <SwitchSquarePort kind="copper" />
          </button>
        </div>
        <span class="vent" />
      </div>
      <div v-if="grid.empty" class="bezel" />
      <div v-else class="bays" :class="{ vertical: grid.vertical, sff: size === '2.5' }" :style="driveStyle">
        <div v-for="i in diskCount" :key="`bay-${i}`" class="bay" :title="`${bayId(i - 1)} · ${diskProto || 'SAS/SATA'}`">
          <span class="mesh" />
          <span class="latch" />
          <span class="id">{{ bayId(i - 1) }}</span>
        </div>
      </div>
    </div>
    <div class="ear right-ear">
      <span class="brand">SRV</span>
      <button
        v-for="p in frontVga"
        :key="p.id"
        type="button"
        class="vga-port"
        :class="{ selected: selectedPortId === p.id }"
        :title="`${p.code} · ${p.id}`"
        @click="onClick(p.id, $event)"
        @contextmenu="onContext(p.id, $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.srv-front {
  box-sizing: border-box;
  width: 100%;
  max-width: 860px;
  height: auto;
  display: flex;
  background: linear-gradient(180deg, #c5c9d0 0%, #9aa1ab 55%, #8b929c 100%);
  border: 1px solid #5c636c;
  box-shadow: inset 0 1px 0 #eceff3, inset 0 -1px 0 #6d737c;
  overflow: hidden;
}
.ear {
  flex: 0 0 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 4px 2px;
  background: #1c1f24;
}
.u4 .ear {
  flex-basis: 16px;
}
.pwr {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #7ad0ff, #1a6aa8 55%, #0b2a44);
  box-shadow: 0 0 4px #3aa0e0;
}
.uid {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3a414a;
  border: 1px solid #6a727c;
}
.leds {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.leds i {
  display: block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.leds .ok {
  background: #2f8a3c;
}
.leds .net {
  background: #c9a227;
}
.leds .warn {
  background: #8a3232;
}
.brand {
  margin-top: auto;
  writing-mode: vertical-rl;
  font-size: 9px;
  letter-spacing: 1px;
  color: #d8dde4;
}
.face {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 3px 4px;
  gap: 3px;
}
.top-strip {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 14px;
  flex: 0 0 14px;
}
.vent {
  flex: 1 1 auto;
  height: 100%;
  background: radial-gradient(#2a2e34 0.7px, transparent 0.8px);
  background-size: 4px 4px;
  background-color: #6d737c;
  border: 1px solid #4a5058;
}
.io-inline {
  display: flex;
  gap: 2px;
}
.bezel {
  flex: 1 1 auto;
  background: repeating-linear-gradient(90deg, #5a616a 0 2px, #6a727c 2px 6px);
  border: 1px solid #3a414a;
}
.bays {
  flex: 1 1 auto;
  display: grid;
  gap: clamp(1px, 0.32vw, 3px);
  min-height: 0;
  align-content: stretch;
}
.u4 .bays { grid-auto-columns: minmax(0, 1fr); }
.u4 .bay { width: 100%; height: 100%; }
.bay {
  position: relative;
  min-width: 0;
  min-height: 0;
  background: #1a1d22;
  border: 1px solid #0e1014;
  display: flex;
  overflow: hidden;
}
.bays:not(.vertical) .bay {
  flex-direction: row;
}
.bays.vertical .bay {
  flex-direction: column;
}
.mesh {
  flex: 1 1 auto;
  background: radial-gradient(#3a3f46 0.55px, transparent 0.65px);
  background-size: 3px 3px;
  background-color: #22262c;
}
.latch {
  flex: 0 0 7px;
  background: linear-gradient(180deg, #3d6ea8, #24548a);
  border-left: 1px solid #1a3a5c;
}
.bays.vertical .latch {
  flex-basis: 6px;
  border-left: 0;
  border-top: 1px solid #1a3a5c;
}
.id {
  position: absolute;
  left: 2px;
  top: 1px;
  font-size: 7px;
  color: #c9d0d8;
  text-shadow: 0 1px 1px #000;
  pointer-events: none;
}
.mini-port {
  width: 14px;
  height: 14px;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}
.u1 .mini-port {
  width: 12px;
  height: 12px;
}
.mini-port.selected,
.vga-port.selected {
  outline: 1px solid #409eff;
}
.vga-port {
  width: 14px;
  height: 10px;
  margin-top: auto;
  margin-bottom: 8px;
  border: 0;
  background: #3b6ea8;
  clip-path: polygon(8% 0, 92% 0, 100% 30%, 100% 100%, 0 100%, 0 30%);
  cursor: pointer;
}
</style>
