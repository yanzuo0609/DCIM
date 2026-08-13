<script setup lang="ts">
import { computed } from 'vue'
import type { DeviceGroupKind } from '@/utils/deviceGroupVisual'

const props = withDefaults(
  defineProps<{
    kind: DeviceGroupKind
    size?: number
    selected?: boolean
  }>(),
  {
    size: 40,
    selected: false,
  },
)

const palette = computed(() => {
  if (props.kind === 'server') {
    return { fill: '#0f766e', soft: '#14b8a6', badge: '#134e4a' }
  }
  if (props.kind === 'security') {
    return { fill: '#c2410c', soft: '#ea580c', badge: '#7c2d12' }
  }
  return { fill: '#2f5f9e', soft: '#4a7ab8', badge: '#1e3a5f' }
})
</script>

<template>
  <svg
    class="topo-group-icon"
    :class="{ selected }"
    :width="size"
    :height="size"
    viewBox="0 0 48 48"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <!-- 交换机组：叠放三台交换机 -->
    <g v-if="kind === 'switch'">
      <rect x="10" y="8" width="28" height="10" rx="2" :fill="palette.soft" opacity="0.55" />
      <rect x="8" y="16" width="30" height="12" rx="2.5" :fill="palette.soft" opacity="0.8" />
      <rect x="6" y="26" width="34" height="14" rx="3" :fill="palette.fill" />
      <rect x="10" y="30" width="26" height="3" rx="1" fill="#fff" opacity="0.35" />
      <circle cx="12" cy="36.5" r="1.2" fill="#fff" opacity="0.9" />
      <circle cx="17" cy="36.5" r="1.2" fill="#fff" opacity="0.7" />
      <circle cx="22" cy="36.5" r="1.2" fill="#fff" opacity="0.9" />
      <circle cx="27" cy="36.5" r="1.2" fill="#fff" opacity="0.55" />
      <circle cx="32" cy="36.5" r="1.2" fill="#fff" opacity="0.9" />
      <circle cx="38" cy="12" r="7" :fill="palette.badge" />
      <text x="38" y="15.5" text-anchor="middle" fill="#fff" font-size="9" font-weight="700">S</text>
    </g>

    <!-- 服务器组：叠放机架条 -->
    <g v-else-if="kind === 'server'">
      <rect x="11" y="7" width="26" height="9" rx="2" :fill="palette.soft" opacity="0.5" />
      <rect x="9" y="15" width="28" height="10" rx="2" :fill="palette.soft" opacity="0.75" />
      <rect x="7" y="25" width="32" height="14" rx="2.5" :fill="palette.fill" />
      <rect x="11" y="28" width="14" height="7" rx="1" fill="#fff" opacity="0.3" />
      <rect x="28" y="28" width="5" height="7" rx="1" fill="#fff" opacity="0.45" />
      <rect x="35" y="28" width="5" height="7" rx="1" fill="#fff" opacity="0.45" />
      <circle cx="38" cy="12" r="7" :fill="palette.badge" />
      <text x="38" y="15.5" text-anchor="middle" fill="#fff" font-size="9" font-weight="700">R</text>
    </g>

    <!-- 安全应用组：叠放盾牌 -->
    <g v-else>
      <path
        d="M24 6 L36 11 V20 C36 28 30 34 24 37 C18 34 12 28 12 20 V11 Z"
        :fill="palette.soft"
        opacity="0.45"
        transform="translate(0,-2) scale(0.78) translate(6.5,6)"
      />
      <path
        d="M24 6 L36 11 V20 C36 28 30 34 24 37 C18 34 12 28 12 20 V11 Z"
        :fill="palette.soft"
        opacity="0.7"
        transform="translate(0,1) scale(0.88) translate(3.2,2)"
      />
      <path
        d="M24 8 L37 13.5 V23 C37 32 30.5 38.5 24 42 C17.5 38.5 11 32 11 23 V13.5 Z"
        :fill="palette.fill"
      />
      <path
        d="M24 14 L31 17 V23.5 C31 28.5 27.5 32.2 24 34.2 C20.5 32.2 17 28.5 17 23.5 V17 Z"
        fill="#fff"
        opacity="0.28"
      />
      <circle cx="38" cy="12" r="7" :fill="palette.badge" />
      <text x="38" y="15.5" text-anchor="middle" fill="#fff" font-size="9" font-weight="700">F</text>
    </g>
  </svg>
</template>

<style scoped>
.topo-group-icon.selected {
  filter: drop-shadow(0 0 2px #409eff);
}
</style>
