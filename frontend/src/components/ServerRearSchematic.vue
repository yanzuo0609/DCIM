<script setup lang="ts">
import { computed } from 'vue'
import SwitchSquarePort from '@/components/SwitchSquarePort.vue'
import {
  SERVER_DEMO,
  groupServerPorts,
  normalizeDiskSize,
  normalizeServerFormFactor,
  rearDriveGrid,
  type ServerDiskSize,
  type ServerFormFactorU,
  type ServerPcieSlotAttr,
  type ServerPortAttr,
} from '@/utils/serverModelAttrs'

const props = withDefaults(
  defineProps<{
    heightU?: number
    psuCount?: number
    psuWatt?: number
    pcieSlotDefs?: ServerPcieSlotAttr[]
    diskCount?: number
    diskSize?: ServerDiskSize | string
    ports?: ServerPortAttr[]
    selectedPortId?: string | null
  }>(),
  {
    heightU: 1,
    psuCount: 2,
    psuWatt: 800,
    pcieSlotDefs: () => [],
    diskCount: 0,
    diskSize: '2.5',
    ports: () => [],
  },
)

const emit = defineEmits<{
  selectPort: [portId: string]
  inspectPort: [portId: string, ev: MouseEvent]
}>()

const u = computed<ServerFormFactorU>(() => normalizeServerFormFactor(props.heightU))
const psus = computed(() => Math.max(0, Math.min(8, Math.trunc(props.psuCount || 0))))
const pcieSlots = computed(() => (props.pcieSlotDefs?.length ? props.pcieSlotDefs : []))
const grid = computed(() => rearDriveGrid(props.diskCount || 0, normalizeDiskSize(props.diskSize, '2.5')))
const groups = computed(() => groupServerPorts(props.ports || []))
const bmc = computed(() => groups.value.find((g) => g.kind === 'bmc')?.ports || [])
const ipmi = computed(() => groups.value.find((g) => g.kind === 'ipmi')?.ports || [])
const vga = computed(() => groups.value.find((g) => g.kind === 'vga')?.ports || [])
const usb = computed(() => groups.value.find((g) => g.kind === 'usb')?.ports || [])
const lom = computed(() => groups.value.find((g) => g.kind === 'lom')?.ports || [])
const frameStyle = computed(() => ({
  aspectRatio: SERVER_DEMO.aspect(u.value),
}))
const rearDiskStyle = computed(() => ({
  gridTemplateColumns: `repeat(${Math.max(1, grid.value.cols)}, minmax(0, 1fr))`,
  gridTemplateRows: `repeat(${Math.max(1, grid.value.rows)}, minmax(0, 1fr))`,
}))

function slotPorts(slotIndex: number) {
  return (props.ports || []).filter((p) => p.kind === 'flex' && p.slot_index === slotIndex)
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
  <div class="srv-rear" :class="`u${u}`" :style="frameStyle">
    <div class="ear" />
    <div class="body">
      <div class="pcie-col" :title="`PCIE ×${pcieSlots.length}`">
        <div
          v-for="slot in pcieSlots"
          :key="`pcie-${slot.index}`"
          class="pcie-slot"
          :class="{ occupied: slot.flex_ports > 0 }"
        >
          <span class="pcie-num">{{ slot.index }}</span>
          <div v-if="slot.flex_ports" class="pcie-ports">
            <button
              v-for="p in slotPorts(slot.index)"
              :key="p.id"
              type="button"
              class="sq"
              :class="{ selected: selectedPortId === p.id }"
              :title="`${p.code} · ${p.id}`"
              @click="onClick(p.id, $event)"
              @contextmenu="onContext(p.id, $event)"
            >
              <SwitchSquarePort kind="optical" :label="p.code" />
            </button>
          </div>
        </div>
      </div>
      <div class="io">
        <button
          v-for="p in vga"
          :key="p.id"
          type="button"
          class="vga"
          :class="{ selected: selectedPortId === p.id }"
          :title="`${p.code} · ${p.id}`"
          @click="onClick(p.id, $event)"
          @contextmenu="onContext(p.id, $event)"
        />
        <button
          v-for="p in usb"
          :key="p.id"
          type="button"
          class="sq"
          :class="{ selected: selectedPortId === p.id }"
          :title="`${p.code} · ${p.id}`"
          @click="onClick(p.id, $event)"
          @contextmenu="onContext(p.id, $event)"
        >
          <SwitchSquarePort kind="copper" :label="p.code.replace('USB', '')" />
        </button>
        <button
          v-for="p in bmc"
          :key="p.id"
          type="button"
          class="sq"
          :class="{ selected: selectedPortId === p.id }"
          :title="`${p.code} · ${p.id}`"
          @click="onClick(p.id, $event)"
          @contextmenu="onContext(p.id, $event)"
        >
          <SwitchSquarePort kind="copper" :label="p.code" />
        </button>
        <button
          v-for="p in ipmi"
          :key="p.id"
          type="button"
          class="sq"
          :class="{ selected: selectedPortId === p.id }"
          :title="`${p.code} · ${p.id}`"
          @click="onClick(p.id, $event)"
          @contextmenu="onContext(p.id, $event)"
        >
          <SwitchSquarePort kind="copper" :label="p.code" />
        </button>
        <button
          v-for="p in lom"
          :key="p.id"
          type="button"
          class="sq"
          :class="{ selected: selectedPortId === p.id }"
          :title="`${p.code} · ${p.id}`"
          @click="onClick(p.id, $event)"
          @contextmenu="onContext(p.id, $event)"
        >
          <SwitchSquarePort kind="copper" :label="p.code" />
        </button>
      </div>
      <div v-if="!grid.empty" class="rear-disks" :style="rearDiskStyle">
        <div v-for="i in diskCount" :key="`rd-${i}`" class="rdisk" :title="`后置盘 ${i}`">
          <span class="mesh" />
        </div>
      </div>
      <div class="psu-col" :class="{ stacked: u >= 2 && psus > 1 }">
        <div v-for="i in psus" :key="`psu-${i}`" class="psu" :title="`PSU ${i} · ${psuWatt}W`">
          <span class="inlet" />
          <span class="led" />
        </div>
      </div>
    </div>
    <div class="ear" />
  </div>
</template>

<style scoped>
.srv-rear {
  box-sizing: border-box;
  width: 100%;
  height: auto;
  display: flex;
  background: linear-gradient(180deg, #c8ccd3 0%, #9aa1ab 60%, #8a919b 100%);
  border: 1px solid #5c636c;
  overflow: hidden;
}
.ear {
  flex: 0 0 10px;
  background: #2a2e34;
}
.body {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  gap: 2px;
  padding: 1px 2px;
}
.pcie-col {
  flex: 1 1 62%;
  min-width: 0;
  display: flex;
  gap: 2px;
}
.pcie-slot {
  flex: 1 1 0;
  min-width: 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 1px;
  padding: 1px;
  background: repeating-linear-gradient(180deg, #7a818c 0 3px, #5c636c 3px 5px);
  border: 1px solid #3a414a;
  position: relative;
}
.pcie-slot.occupied {
  background: #3a424c;
}
.u1 .pcie-slot {
  flex-direction: row;
  justify-content: flex-start;
  padding: 1px 2px;
}
.pcie-num {
  position: absolute;
  top: 1px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 7px;
  line-height: 1;
  color: #e8edf3;
  text-shadow: 0 1px 1px #000;
}
.u1 .pcie-num {
  left: 2px;
  transform: none;
  top: 50%;
  margin-top: -4px;
}
.pcie-ports {
  display: flex;
  flex-direction: column;
  gap: 1px;
  width: 100%;
  margin-top: 8px;
}
.u1 .pcie-ports {
  flex-direction: row;
  margin-top: 0;
  margin-left: 10px;
  width: auto;
  flex: 1;
}
.io {
  flex: 0 0 auto;
  display: flex;
  flex-wrap: wrap;
  align-content: center;
  align-items: center;
  gap: 1px;
  max-width: 22%;
}
.sq {
  width: 18px;
  height: 18px;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  flex: 0 0 18px;
}
.u2 .sq,
.u4 .sq {
  width: 20px;
  height: 20px;
  flex-basis: 20px;
}
.sq.selected,
.vga.selected {
  outline: 1px solid #409eff;
}
.vga {
  width: 16px;
  height: 11px;
  border: 0;
  background: #3b6ea8;
  clip-path: polygon(8% 0, 92% 0, 100% 28%, 100% 100%, 0 100%, 0 28%);
  cursor: pointer;
}
.rear-disks {
  flex: 0 0 14px;
  display: grid;
  gap: 1px;
}
.rdisk {
  display: flex;
  background: #1a1d22;
  border: 1px solid #0e1014;
  overflow: hidden;
}
.mesh {
  flex: 1;
  background: radial-gradient(#3a3f46 0.5px, transparent 0.6px);
  background-size: 3px 3px;
  background-color: #22262c;
}
.psu-col {
  flex: 0 0 18px;
  display: flex;
  gap: 1px;
}
.psu-col.stacked {
  flex-direction: column;
}
.u1 .psu-col {
  flex-direction: row;
  flex-basis: 26px;
}
.psu {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 2px;
  background: #2c3138;
  border: 1px solid #15181c;
}
.inlet {
  width: 10px;
  height: 6px;
  background: #111;
  border: 1px solid #444;
  border-radius: 1px;
}
.led {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #2f8a3c;
}
</style>
