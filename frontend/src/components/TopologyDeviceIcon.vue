<script setup lang="ts">
import { computed } from 'vue'
import type { NetworkNodeKind, ServerFormFactor, SwitchSubtype } from '@/api/network'

/** 扁平实心图标色（对齐参考图深蓝单色风格） */
const FILL = '#2f5f9e'
const FILL_SOFT = '#4a7ab8'

const props = withDefaults(
  defineProps<{
    kind: NetworkNodeKind
    switchSubtype?: SwitchSubtype | null
    serverFormFactor?: ServerFormFactor | null
    securityHeightU?: number | null
    size?: number
    selected?: boolean
  }>(),
  {
    switchSubtype: null,
    serverFormFactor: 1,
    securityHeightU: 1,
    size: 56,
    selected: false,
  },
)

const switchType = computed<SwitchSubtype>(() => props.switchSubtype || 'gigabit')
const serverU = computed<ServerFormFactor>(() => {
  const v = props.serverFormFactor
  return v === 2 || v === 4 ? v : 1
})
const securityU = computed(() => (Number(props.securityHeightU) >= 2 ? 2 : 1))

const variantKey = computed(() => {
  if (props.kind === 'switch') return `switch:${switchType.value}`
  if (props.kind === 'server') return `server:${serverU.value}`
  return `security:${securityU.value}`
})
</script>

<template>
  <svg
    class="topo-device-icon"
    :class="{ selected }"
    :width="size"
    :height="size"
    viewBox="0 0 48 48"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <!-- 千兆交换机：扁机箱 + 端口条 -->
    <g v-if="variantKey === 'switch:gigabit'" :key="variantKey">
      <rect x="6" y="16" width="36" height="18" rx="3" :fill="FILL" />
      <rect x="10" y="20" width="28" height="4" rx="1" fill="#fff" opacity="0.35" />
      <circle cx="12" cy="29" r="1.4" fill="#fff" opacity="0.85" />
      <circle cx="17" cy="29" r="1.4" fill="#fff" opacity="0.85" />
      <circle cx="22" cy="29" r="1.4" fill="#fff" opacity="0.55" />
      <circle cx="27" cy="29" r="1.4" fill="#fff" opacity="0.85" />
      <circle cx="32" cy="29" r="1.4" fill="#fff" opacity="0.55" />
      <circle cx="37" cy="29" r="1.4" fill="#fff" opacity="0.85" />
    </g>

    <!-- 万兆：略高机箱 + SFP 槽暗示 -->
    <g v-else-if="variantKey === 'switch:ten_gigabit'" :key="variantKey">
      <rect x="5" y="14" width="38" height="22" rx="3" :fill="FILL" />
      <rect x="9" y="18" width="5" height="12" rx="1" fill="#fff" opacity="0.3" />
      <rect x="16" y="18" width="5" height="12" rx="1" fill="#fff" opacity="0.45" />
      <rect x="23" y="18" width="5" height="12" rx="1" fill="#fff" opacity="0.3" />
      <rect x="30" y="18" width="5" height="12" rx="1" fill="#fff" opacity="0.45" />
      <rect x="37" y="18" width="3" height="12" rx="0.8" fill="#fff" opacity="0.25" />
    </g>

    <!-- 汇聚：与其它交换机同宽机箱 + 分区端口 -->
    <g v-else-if="variantKey === 'switch:aggregation'" :key="variantKey">
      <rect x="5" y="14" width="38" height="22" rx="3" :fill="FILL" />
      <rect x="9" y="18" width="16" height="12" rx="1.5" fill="#fff" opacity="0.28" />
      <rect x="27" y="18" width="12" height="12" rx="1.5" fill="#fff" opacity="0.45" />
      <circle cx="12" cy="24" r="1.2" fill="#fff" />
      <circle cx="17" cy="24" r="1.2" fill="#fff" />
      <circle cx="22" cy="24" r="1.2" fill="#fff" opacity="0.6" />
      <circle cx="31" cy="24" r="1.5" fill="#fff" />
      <circle cx="35" cy="24" r="1.5" fill="#fff" />
    </g>

    <!-- 核心：同宽横向机框 + 线卡槽暗示（不再用窄立柜） -->
    <g v-else-if="variantKey.startsWith('switch:')" :key="variantKey">
      <rect x="5" y="14" width="38" height="22" rx="3" :fill="FILL" />
      <rect x="9" y="17" width="30" height="3.2" rx="0.8" fill="#fff" opacity="0.4" />
      <rect x="9" y="22" width="30" height="3.2" rx="0.8" fill="#fff" opacity="0.28" />
      <rect x="9" y="27" width="30" height="3.2" rx="0.8" fill="#fff" opacity="0.28" />
      <circle cx="36" cy="18.6" r="1.1" fill="#fff" />
    </g>

    <!-- 1U 服务器：扁条机架 -->
    <g v-else-if="variantKey === 'server:1'" :key="variantKey">
      <rect x="5" y="17" width="38" height="14" rx="2.5" :fill="FILL" />
      <rect x="9" y="20" width="16" height="8" rx="1" fill="#fff" opacity="0.3" />
      <rect x="28" y="20" width="5" height="8" rx="1" fill="#fff" opacity="0.45" />
      <rect x="35" y="20" width="5" height="8" rx="1" fill="#fff" opacity="0.45" />
      <circle cx="11" cy="28" r="1.1" fill="#fff" />
    </g>

    <!-- 2U 服务器 -->
    <g v-else-if="variantKey === 'server:2'" :key="variantKey">
      <rect x="8" y="10" width="32" height="28" rx="3" :fill="FILL" />
      <rect x="12" y="14" width="10" height="7" rx="1" fill="#fff" opacity="0.35" />
      <rect x="26" y="14" width="10" height="7" rx="1" fill="#fff" opacity="0.35" />
      <rect x="12" y="24" width="10" height="7" rx="1" fill="#fff" opacity="0.28" />
      <rect x="26" y="24" width="10" height="7" rx="1" fill="#fff" opacity="0.28" />
      <circle cx="34" cy="34" r="1.4" fill="#fff" />
    </g>

    <!-- 4U / 塔式服务器 -->
    <g v-else-if="variantKey.startsWith('server:')" :key="variantKey">
      <rect x="13" y="5" width="22" height="38" rx="3" :fill="FILL" />
      <rect x="16" y="9" width="16" height="5" rx="1" :fill="FILL_SOFT" />
      <rect x="16" y="17" width="16" height="3.2" rx="0.7" fill="#fff" opacity="0.3" />
      <rect x="16" y="22" width="16" height="3.2" rx="0.7" fill="#fff" opacity="0.3" />
      <rect x="16" y="27" width="16" height="3.2" rx="0.7" fill="#fff" opacity="0.3" />
      <rect x="16" y="32" width="16" height="3.2" rx="0.7" fill="#fff" opacity="0.3" />
      <circle cx="19" cy="39" r="1.2" fill="#fff" />
      <circle cx="24" cy="39" r="1.2" fill="#fff" opacity="0.7" />
    </g>

    <!-- 1U 安全设备：盾牌 -->
    <g v-else-if="variantKey === 'security:1'" :key="variantKey">
      <path
        d="M24 6 L38 12 V24 C38 33 31 39 24 42 C17 39 10 33 10 24 V12 Z"
        :fill="FILL"
      />
      <path
        d="M24 14 L32 17.5 V24.5 C32 29.5 28 33.2 24 35.2 C20 33.2 16 29.5 16 24.5 V17.5 Z"
        fill="#fff"
        opacity="0.28"
      />
      <path
        d="M21 24.5 L23.2 26.7 L28.2 20.8"
        fill="none"
        stroke="#fff"
        stroke-width="2.2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </g>

    <!-- 2U 安全：盾牌 + 底座 -->
    <g v-else :key="variantKey">
      <rect x="8" y="32" width="32" height="8" rx="2" :fill="FILL_SOFT" />
      <path
        d="M24 5 L37 11 V22 C37 30 31 35.5 24 38 C17 35.5 11 30 11 22 V11 Z"
        :fill="FILL"
      />
      <circle cx="24" cy="20" r="5" fill="none" stroke="#fff" stroke-width="2" opacity="0.9" />
      <rect x="22" y="20" width="4" height="6" rx="1" fill="#fff" />
    </g>

    <rect
      v-if="selected"
      x="1"
      y="1"
      width="46"
      height="46"
      rx="8"
      fill="none"
      stroke="#409eff"
      stroke-width="2"
      stroke-dasharray="3 2"
    />
  </svg>
</template>

<style scoped>
.topo-device-icon {
  display: block;
  flex-shrink: 0;
}
</style>
