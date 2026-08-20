<script setup lang="ts">
import { computed } from 'vue'
import { ACCESS_DEMO, rackPanelAspect, type SwitchSystemPortAttr } from '@/utils/switchModelAttrs'

const props = defineProps<{
  fanCount?: number
  psuCount?: number
  mgmtPorts?: SwitchSystemPortAttr[]
  selectedPortId?: string | null
}>()

const emit = defineEmits<{
  selectPort: [portId: string]
  inspectPort: [portId: string, ev: MouseEvent]
}>()

const fans = computed(() => Math.max(0, Math.min(16, Math.trunc(props.fanCount || 0) || 0)))
const psus = computed(() => Math.max(0, Math.min(8, Math.trunc(props.psuCount ?? 2) || 0)))
const mgmt = computed(() => (Array.isArray(props.mgmtPorts) ? props.mgmtPorts : []))

const psuStyle = computed(() => {
  const n = Math.max(1, psus.value)
  const w = n <= 2 ? 58 : n <= 4 ? 48 : 40
  return { width: `${w}px`, flexBasis: `${w}px` }
})

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

const frameStyle = computed(() => ({
  aspectRatio: rackPanelAspect(1),
  maxWidth: `${ACCESS_DEMO.maxW}px`,
}))
</script>

<template>
  <div class="access-rear" :style="frameStyle">
    <div class="rear-inner">
      <div v-if="psus" class="psu-row">
        <div v-for="i in psus" :key="`psu-${i}`" class="psu-mod" :style="psuStyle" :title="`电源 ${i}`">
          <span class="psu-inlet" aria-hidden="true" />
          <span class="psu-led" />
        </div>
      </div>
      <div v-if="fans" class="fan-row">
        <div v-for="i in fans" :key="`fan-${i}`" class="fan-mod" :title="`风扇 ${i}`">
          <span class="fan-hub" />
        </div>
      </div>
      <div v-else class="vent-fill" />
      <div class="mgmt-col">
        <button
          v-for="p in mgmt"
          :key="p.id"
          type="button"
          class="mgmt-port"
          :class="{ selected: selectedPortId === p.id }"
          :title="`${p.code} · ${p.id}`"
          @click.stop="onClick(p.id, $event)"
          @contextmenu.prevent="onContext(p.id, $event)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.access-rear {
  box-sizing: border-box;
  width: 100%;
  padding: 4px;
  background: #cfd4db;
  border: 2px solid #2c3e50;
  border-radius: 2px;
}
.rear-inner {
  height: 100%;
  display: flex;
  align-items: stretch;
  gap: 8px;
  padding: 6px 8px;
  background: #5e656e;
  border: 1px solid #2c3e50;
  box-sizing: border-box;
}
.psu-row {
  flex: 0 0 auto;
  display: flex;
  align-items: stretch;
  gap: 6px;
}
.psu-mod {
  flex: 0 0 auto;
  position: relative;
  box-sizing: border-box;
  height: 100%;
  background: linear-gradient(180deg, #4a515a 0%, #323840 100%);
  border: 1px solid #1c2126;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
}
.psu-inlet {
  width: 20px;
  height: 15px;
  box-sizing: border-box;
  border: 2px solid #c9ced6;
  border-radius: 1px 1px 5px 5px;
  background: #15181c;
  box-shadow: inset 0 1px 0 #6a727c;
}
.psu-led {
  position: absolute;
  top: 5px;
  right: 5px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #3d8b4a;
  box-shadow: 0 0 3px #3d8b4a;
}
.fan-row {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: stretch;
  gap: 6px;
}
.fan-mod {
  flex: 1 1 0;
  min-width: 0;
  position: relative;
  border: 1px solid #2c3e50;
  background-color: #6a727c;
  background-image:
    repeating-linear-gradient(45deg, rgba(232, 236, 242, 0.75) 0 1px, transparent 1px 7px),
    repeating-linear-gradient(-45deg, rgba(232, 236, 242, 0.75) 0 1px, transparent 1px 7px);
  background-size: 9px 9px;
}
.fan-hub {
  position: absolute;
  top: 50%;
  left: 50%;
  width: clamp(10px, 28%, 22px);
  height: clamp(10px, 28%, 22px);
  margin: 0;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  border: 2px solid #3a4048;
  background: #8a929c;
  box-shadow: inset 0 0 0 3px #5e656e;
  box-sizing: border-box;
}
.vent-fill {
  flex: 1 1 auto;
  min-width: 0;
  background:
    repeating-linear-gradient(90deg, #6a727c 0 2px, #5e656e 2px 5px);
  opacity: 0.55;
}
.mgmt-col {
  flex: 0 0 28px;
  margin-left: auto;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 6px;
}
.mgmt-port {
  width: 16px;
  height: 16px;
  padding: 0;
  border: 1px solid #1f2a33;
  background: #3a4048;
  cursor: pointer;
}
.mgmt-port:hover,
.mgmt-port.selected {
  background: #409eff;
  border-color: #1d6ec7;
}
</style>
