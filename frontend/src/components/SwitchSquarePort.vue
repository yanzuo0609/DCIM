<script setup lang="ts">
import type { SwitchPortFace } from '@/utils/switchModelAttrs'

withDefaults(
  defineProps<{
    kind: SwitchPortFace
    label?: string
    selected?: boolean
  }>(),
  { kind: 'optical', label: '', selected: false },
)
</script>

<template>
  <span class="sq-port" :class="[`is-${kind}`, { selected }]">
    <svg class="sq-glyph" viewBox="0 0 24 24" aria-hidden="true">
      <rect class="sq-body" x="1.2" y="1.2" width="21.6" height="21.6" rx="1.4" />
      <!-- 电口 RJ45 -->
      <g v-if="kind === 'copper'">
        <path
          d="M4.2 5.2h15.6v9.2c0 .7-.3 1.2-.8 1.6l-2.1 1.6c-.4.3-.9.5-1.4.5H8.5c-.5 0-1-.2-1.4-.5L5 16c-.5-.4-.8-.9-.8-1.6z"
          fill="#12151a"
        />
        <rect x="5.4" y="6.4" width="13.2" height="2.2" rx="0.3" fill="#c9a227" />
        <g fill="#e8c547">
          <rect v-for="i in 8" :key="`p${i}`" :x="5.7 + (i - 1) * 1.55" y="6.55" width="1.15" height="1.9" rx="0.15" />
        </g>
        <rect x="6.2" y="10.2" width="11.6" height="3.4" rx="0.4" fill="#2a3038" />
        <path d="M9.2 17.2h5.6v1.6c0 .4-.3.7-.7.7h-4.2c-.4 0-.7-.3-.7-.7z" fill="#3a414a" />
      </g>
      <!-- 光口 SFP -->
      <g v-else-if="kind === 'optical'">
        <rect x="3.4" y="4.8" width="13.2" height="14.4" rx="1" fill="#14171c" />
        <rect x="5" y="7.2" width="10" height="9.6" rx="0.7" fill="#3a424c" />
        <rect x="6.6" y="9.6" width="3.2" height="4.8" rx="0.35" fill="#d8dde4" />
        <rect x="10.4" y="9.6" width="3.2" height="4.8" rx="0.35" fill="#d8dde4" />
        <circle cx="19.4" cy="8.2" r="1.15" fill="#2f8a3c" />
        <circle cx="19.4" cy="12" r="1.15" fill="#c9a227" />
        <circle cx="19.4" cy="15.8" r="1.15" fill="#6a727c" />
      </g>
      <!-- MPO / QSFP -->
      <g v-else>
        <rect x="3.2" y="5.4" width="13.6" height="13.2" rx="1" fill="#14171c" />
        <rect x="4.6" y="8.2" width="10.8" height="7.6" rx="0.6" fill="#3a424c" />
        <rect x="8.6" y="6.2" width="3.2" height="1.5" rx="0.25" fill="#9aa3ad" />
        <g fill="#e8edf3">
          <circle v-for="i in 6" :key="`f${i}`" :cx="6.2 + (i - 1) * 1.7" cy="12" r="0.5" />
        </g>
        <circle cx="19.4" cy="8.4" r="1.15" fill="#2f8a3c" />
        <circle cx="19.4" cy="12" r="1.15" fill="#2f8a3c" />
        <circle cx="19.4" cy="15.6" r="1.15" fill="#c9a227" />
      </g>
    </svg>
    <span v-if="label" class="sq-lab">{{ label }}</span>
  </span>
</template>

<style scoped>
.sq-port {
  position: relative;
  display: block;
  width: 100%;
  height: 100%;
  aspect-ratio: 1;
  box-sizing: border-box;
  overflow: hidden;
  border: 1px solid #1c2128;
  background: #6e7580;
}
.sq-port.is-copper {
  background: #7a818c;
}
.sq-port.is-optical {
  background: #6a727c;
}
.sq-port.is-mpo {
  background: #5e6a78;
}
.sq-port.selected {
  outline: 1px solid #409eff;
  outline-offset: -1px;
}
.sq-glyph {
  display: block;
  width: 100%;
  height: 100%;
}
.sq-body {
  fill: #2c333c;
  stroke: #11141a;
  stroke-width: 0.9;
}
.sq-lab {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  font-size: 5px;
  line-height: 1.05;
  text-align: center;
  color: #f3f5f7;
  text-shadow: 0 0 2px #111;
  pointer-events: none;
}
</style>
