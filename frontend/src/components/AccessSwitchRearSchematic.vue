<script setup lang="ts">
import { computed } from 'vue'
import { ACCESS_DEMO, type SwitchSystemPortAttr } from '@/utils/switchModelAttrs'

const props = defineProps<{
  fanCount?: number
  mgmtPorts?: SwitchSystemPortAttr[]
  selectedPortId?: string | null
}>()

const emit = defineEmits<{
  selectPort: [portId: string]
  inspectPort: [portId: string, ev: MouseEvent]
}>()

const fans = computed(() => Math.max(1, Math.min(4, Math.trunc(props.fanCount || 2) || 2)))
const mgmt = computed(() => (Array.isArray(props.mgmtPorts) ? props.mgmtPorts : []))

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
  height: `${ACCESS_DEMO.height}px`,
}))
</script>

<template>
  <div class="access-rear" :style="frameStyle">
    <div class="rear-inner">
      <div class="fan-row">
        <div v-for="i in fans" :key="`fan-${i}`" class="fan-mod" :title="`风扇/电源 ${i}`">
          <span class="fan-hub" />
        </div>
      </div>
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
.fan-row {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  gap: 8px;
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
  width: 22px;
  height: 22px;
  margin: -11px 0 0 -11px;
  border-radius: 50%;
  border: 2px solid #3a4048;
  background: #8a929c;
  box-shadow: inset 0 0 0 3px #5e656e;
}
.mgmt-col {
  flex: 0 0 28px;
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
