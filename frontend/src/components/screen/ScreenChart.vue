<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import type { ECharts, EChartsOption } from 'echarts'

const props = withDefaults(
  defineProps<{
    option: EChartsOption | null
    height?: string
  }>(),
  { height: '260px' },
)

const elRef = ref<HTMLDivElement | null>(null)
let chart: ECharts | null = null

function render() {
  if (!elRef.value) return
  if (!chart) chart = echarts.init(elRef.value)
  if (props.option) chart.setOption(props.option, true)
}

function onResize() {
  chart?.resize()
}

watch(
  () => props.option,
  () => render(),
  { deep: true },
)

onMounted(() => {
  render()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div ref="elRef" class="screen-chart" :style="{ height }" />
</template>

<style scoped>
.screen-chart {
  width: 100%;
  min-height: 180px;
}
</style>
