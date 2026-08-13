<script setup lang="ts">
import { computed } from 'vue'
import { CHASSIS_DEMO, chassisDemoHeight } from '@/utils/switchModelAttrs'

const props = defineProps<{
  heightU: number
  expansionSlots?: number
  fanCount: number
  psuCount: number
}>()

const fans = computed(() => Math.max(0, Math.min(16, Math.trunc(props.fanCount) || 0)))
const psus = computed(() => Math.max(0, Math.min(16, Math.trunc(props.psuCount) || 0)))
const psuLeft = computed(() => Math.ceil(psus.value / 2))
const psuRight = computed(() => Math.floor(psus.value / 2))
const fanCols = computed(() => (fans.value <= 1 ? 1 : 2))
const fanRows = computed(() => Math.max(1, Math.ceil(fans.value / Math.max(1, fanCols.value))))
const frameHeight = computed(() => chassisDemoHeight(props.heightU))

const fanGridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${Math.max(1, fanCols.value)}, minmax(0, 1fr))`,
  gridTemplateRows: `repeat(${fanRows.value}, minmax(0, 1fr))`,
}))
</script>

<template>
  <div
    class="rear"
    :style="{ height: `${frameHeight}px`, maxWidth: `${CHASSIS_DEMO.maxW}px` }"
    :title="`${heightU}U · 风扇 ${fans} · 电源 ${psus}`"
  >
    <div class="rear-inner">
      <div class="top-space" />
      <div class="rear-main">
        <div class="psu-col">
          <span v-for="i in psuLeft" :key="`l${i}`" class="psu" :title="`电源 ${i}`" />
        </div>
        <div class="fan-grid" :style="fanGridStyle">
          <span v-for="i in fans" :key="`f${i}`" class="fan" :title="`风扇 ${i}`" />
        </div>
        <div class="psu-col">
          <span v-for="i in psuRight" :key="`r${i}`" class="psu" :title="`电源 ${psuLeft + i}`" />
        </div>
      </div>
      <div class="rear-base" />
    </div>
  </div>
</template>

<style scoped>
.rear {
  box-sizing: border-box;
  width: 100%;
  padding: 5px;
  background: #d4d8de;
  border: 2px solid #c8ccd2;
  border-radius: 2px;
  overflow: hidden;
}
.rear-inner {
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-rows: 12px minmax(0, 1fr) 12px;
  background: #5e656e;
  border: 1px solid #2c3e50;
  box-sizing: border-box;
  overflow: hidden;
}
.top-space {
  min-height: 0;
}
.rear-main {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr) 22px;
  gap: 8px;
  padding: 4px 8px;
  align-items: center;
}
.psu-col {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 6px;
  overflow: hidden;
}
.psu {
  display: block;
  flex: 0 0 auto;
  width: 18px;
  height: 26px;
  background: #3a4048;
  border: 1px solid #2c3e50;
  box-sizing: border-box;
}
.fan-grid {
  min-width: 0;
  min-height: 0;
  height: 100%;
  display: grid;
  gap: 4px;
  overflow: hidden;
}
.fan {
  display: block;
  min-width: 0;
  min-height: 0;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  border: 1px solid #2c3e50;
  background-color: #6a727c;
  background-image:
    repeating-linear-gradient(
      45deg,
      rgba(232, 236, 242, 0.85) 0 1px,
      transparent 1px 6px
    ),
    repeating-linear-gradient(
      -45deg,
      rgba(232, 236, 242, 0.85) 0 1px,
      transparent 1px 6px
    );
  background-size: 8px 8px;
}
.rear-base {
  min-height: 0;
  margin: 0 6px 4px;
  background: #8a9098;
  border: 1px solid #2c3e50;
  box-sizing: border-box;
}
</style>
