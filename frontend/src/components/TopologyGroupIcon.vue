<script setup lang="ts">
import { computed } from 'vue'
import type { DeviceGroupKind } from '@/utils/deviceGroupVisual'

const props = withDefaults(
  defineProps<{
    kind: DeviceGroupKind | 'switch'
    size?: number
    selected?: boolean
    count?: number | null
  }>(),
  {
    size: 40,
    selected: false,
    count: null,
  },
)

const resolvedKind = computed<DeviceGroupKind>(() =>
  props.kind === 'switch' ? 'access' : props.kind,
)

const palette = computed(() => {
  switch (resolvedKind.value) {
    case 'core':
      return { plate: '#1e3a8a', fill: '#1d4ed8', soft: '#60a5fa', accent: '#fbbf24', badge: '#0f172a' }
    case 'aggregation':
      return { plate: '#5b21b6', fill: '#7c3aed', soft: '#c4b5fd', accent: '#e9d5ff', badge: '#2e1065' }
    case 'access':
      return { plate: '#0f766e', fill: '#0d9488', soft: '#5eead4', accent: '#ccfbf1', badge: '#134e4a' }
    case 'server':
      return { plate: '#115e59', fill: '#0f766e', soft: '#5eead4', accent: '#99f6e4', badge: '#042f2e' }
    case 'security':
      return { plate: '#9a3412', fill: '#c2410c', soft: '#fdba74', accent: '#ffedd5', badge: '#7c2d12' }
    default:
      return { plate: '#334155', fill: '#475569', soft: '#94a3b8', accent: '#e2e8f0', badge: '#1e293b' }
  }
})

const badgeText = computed(() => {
  switch (resolvedKind.value) {
    case 'core':
      return '核'
    case 'aggregation':
      return '汇'
    case 'access':
      return '接'
    case 'server':
      return '服'
    case 'security':
      return '安'
    default:
      return '混'
  }
})

const countText = computed(() => {
  if (props.count == null) return ''
  return props.count > 99 ? '99+' : String(props.count)
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
    <rect x="1" y="1" width="46" height="46" rx="10" :fill="palette.plate" />
    <rect x="1" y="1" width="46" height="46" rx="10" fill="none" :stroke="palette.soft" stroke-width="1.2" opacity="0.45" />

    <!-- 核心：双引擎机箱 + 金条 -->
    <g v-if="resolvedKind === 'core'">
      <rect x="9" y="10" width="30" height="26" rx="3" :fill="palette.fill" />
      <rect x="9" y="10" width="30" height="4" rx="2" :fill="palette.accent" />
      <rect x="12" y="17" width="24" height="4" rx="1" fill="#fff" opacity="0.22" />
      <rect x="12" y="23" width="24" height="4" rx="1" fill="#fff" opacity="0.16" />
      <circle cx="14" cy="31.5" r="1.4" :fill="palette.accent" />
      <circle cx="19" cy="31.5" r="1.4" fill="#fff" opacity="0.85" />
      <circle cx="24" cy="31.5" r="1.4" :fill="palette.accent" />
      <circle cx="29" cy="31.5" r="1.4" fill="#fff" opacity="0.7" />
      <circle cx="34" cy="31.5" r="1.4" fill="#fff" opacity="0.9" />
    </g>

    <!-- 汇聚：双台叠放中型交换机 -->
    <g v-else-if="resolvedKind === 'aggregation'">
      <rect x="12" y="9" width="24" height="11" rx="2" :fill="palette.soft" opacity="0.55" />
      <rect x="9" y="18" width="30" height="16" rx="3" :fill="palette.fill" />
      <path d="M15 13h18" stroke="#fff" stroke-width="1.4" opacity="0.45" />
      <rect x="13" y="23" width="22" height="3" rx="1" fill="#fff" opacity="0.28" />
      <circle cx="14" cy="30" r="1.3" fill="#fff" />
      <circle cx="19" cy="30" r="1.3" fill="#fff" opacity="0.7" />
      <circle cx="24" cy="30" r="1.3" fill="#fff" />
      <circle cx="29" cy="30" r="1.3" fill="#fff" opacity="0.7" />
      <circle cx="34" cy="30" r="1.3" fill="#fff" />
    </g>

    <!-- 接入：端口密布的接入交换机 -->
    <g v-else-if="resolvedKind === 'access'">
      <rect x="8" y="16" width="32" height="16" rx="3" :fill="palette.fill" />
      <rect x="11" y="20" width="3" height="8" rx="0.6" fill="#fff" opacity="0.85" />
      <rect x="16" y="20" width="3" height="8" rx="0.6" fill="#fff" opacity="0.55" />
      <rect x="21" y="20" width="3" height="8" rx="0.6" fill="#fff" opacity="0.85" />
      <rect x="26" y="20" width="3" height="8" rx="0.6" fill="#fff" opacity="0.55" />
      <rect x="31" y="20" width="3" height="8" rx="0.6" fill="#fff" opacity="0.85" />
      <rect x="36" y="20" width="3" height="8" rx="0.6" :fill="palette.accent" />
    </g>

    <!-- 服务器：机架 U 条 -->
    <g v-else-if="resolvedKind === 'server'">
      <rect x="11" y="9" width="26" height="8" rx="1.5" :fill="palette.soft" opacity="0.45" />
      <rect x="10" y="18" width="28" height="8" rx="1.5" :fill="palette.soft" opacity="0.75" />
      <rect x="9" y="27" width="30" height="10" rx="2" :fill="palette.fill" />
      <rect x="12" y="29.5" width="12" height="5" rx="1" fill="#fff" opacity="0.28" />
      <rect x="27" y="29.5" width="4" height="5" rx="1" fill="#fff" opacity="0.5" />
      <rect x="33" y="29.5" width="4" height="5" rx="1" fill="#fff" opacity="0.5" />
    </g>

    <!-- 安全：盾牌 -->
    <g v-else-if="resolvedKind === 'security'">
      <path
        d="M24 9 L36 14.2 V24 C36 32 30.2 37.5 24 40.2 C17.8 37.5 12 32 12 24 V14.2 Z"
        :fill="palette.fill"
      />
      <path
        d="M24 14 L31 17.2 V24 C31 29.2 27.6 33 24 35 C20.4 33 17 29.2 17 24 V17.2 Z"
        fill="#fff"
        opacity="0.22"
      />
      <path d="M21 24.2 L23.4 26.6 L28.2 20.8" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
    </g>

    <!-- 混合：交换机 + 服务器叠影 -->
    <g v-else>
      <rect x="7" y="18" width="20" height="12" rx="2" :fill="palette.fill" />
      <rect x="10" y="21" width="2.2" height="6" rx="0.4" fill="#fff" opacity="0.8" />
      <rect x="14" y="21" width="2.2" height="6" rx="0.4" fill="#fff" opacity="0.5" />
      <rect x="18" y="21" width="2.2" height="6" rx="0.4" fill="#fff" opacity="0.8" />
      <rect x="22" y="21" width="2.2" height="6" rx="0.4" fill="#fff" opacity="0.5" />
      <rect x="24" y="12" width="17" height="7" rx="1.2" :fill="palette.soft" opacity="0.55" />
      <rect x="23" y="20" width="18" height="8" rx="1.4" :fill="palette.soft" />
      <rect x="26" y="22" width="7" height="4" rx="0.8" fill="#fff" opacity="0.28" />
      <rect x="35" y="22" width="3.2" height="4" rx="0.6" fill="#fff" opacity="0.45" />
    </g>

    <circle cx="39" cy="10" r="7" :fill="palette.badge" />
    <text x="39" y="13.4" text-anchor="middle" fill="#fff" font-size="8" font-weight="700">{{ badgeText }}</text>

    <g v-if="countText">
      <rect x="28" y="33" width="17" height="12" rx="6" fill="#fff" />
      <text x="36.5" y="42" text-anchor="middle" :fill="palette.badge" font-size="8" font-weight="700">
        {{ countText }}
      </text>
    </g>
  </svg>
</template>

<style scoped>
.topo-group-icon.selected {
  filter: drop-shadow(0 0 3px #409eff);
}
</style>
