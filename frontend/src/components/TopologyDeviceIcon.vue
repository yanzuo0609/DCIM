<script setup lang="ts">
import { computed } from 'vue'
import type { NetworkNodeKind, ServerFormFactor, SwitchSubtype } from '@/api/network'

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

const caption = computed(() => {
  if (props.kind === 'switch') {
    if (switchType.value === 'core') return 'CORE'
    if (switchType.value === 'aggregation') return 'AGG'
    if (switchType.value === 'ten_gigabit') return '10G'
    return 'GE'
  }
  if (props.kind === 'server') return `${serverU.value}U`
  return securityU.value >= 2 ? 'FW2U' : 'FW'
})
</script>

<template>
  <svg
    class="topo-device-icon"
    :class="{ selected }"
    :width="size"
    :height="size"
    viewBox="0 0 72 72"
    xmlns="http://www.w3.org/2000/svg"
  >
    <!-- 千兆交换机：扁平机箱 + RJ45 双排 -->
    <g v-if="kind === 'switch' && switchType === 'gigabit'">
      <rect x="6" y="22" width="60" height="28" rx="3" fill="#1e3a5f" stroke="#0d2137" stroke-width="1.2" />
      <rect x="10" y="26" width="52" height="16" rx="1.5" fill="#3a7bd5" opacity="0.25" />
      <rect
        v-for="i in 10"
        :key="`ge-a-${i}`"
        :x="11 + (i - 1) * 5"
        y="27"
        width="4"
        height="5"
        rx="0.4"
        fill="#a8d4ff"
        stroke="#1c7ed6"
        stroke-width="0.35"
      />
      <rect
        v-for="i in 10"
        :key="`ge-b-${i}`"
        :x="11 + (i - 1) * 5"
        y="35"
        width="4"
        height="5"
        rx="0.4"
        fill="#a8d4ff"
        stroke="#1c7ed6"
        stroke-width="0.35"
      />
      <circle cx="14" cy="46" r="1.8" fill="#67c23a" />
      <text x="36" y="64" text-anchor="middle" class="icon-caption">{{ caption }}</text>
    </g>

    <!-- 万兆交换机：机箱更高 + SFP 笼位（少而宽） -->
    <g v-else-if="kind === 'switch' && switchType === 'ten_gigabit'">
      <rect x="5" y="16" width="62" height="38" rx="4" fill="#143d28" stroke="#0a2418" stroke-width="1.2" />
      <rect x="9" y="20" width="54" height="22" rx="2" fill="#2f9e44" opacity="0.28" />
      <g v-for="i in 6" :key="`sfp-${i}`">
        <rect
          :x="12 + (i - 1) * 8.5"
          y="22"
          width="7"
          height="16"
          rx="1"
          fill="#1a1a1a"
          stroke="#2f9e44"
          stroke-width="0.8"
        />
        <rect :x="13.5 + (i - 1) * 8.5" y="24" width="4" height="3" rx="0.3" fill="#7dcea0" />
        <rect :x="13.5 + (i - 1) * 8.5" y="29" width="4" height="3" rx="0.3" fill="#7dcea0" />
        <rect :x="13.5 + (i - 1) * 8.5" y="34" width="4" height="2" rx="0.3" fill="#c8e6c9" />
      </g>
      <rect x="48" y="46" width="14" height="5" rx="1" fill="#69db7c" opacity="0.7" />
      <text x="36" y="66" text-anchor="middle" class="icon-caption">{{ caption }}</text>
    </g>

    <!-- 汇聚交换机：宽机箱 + 双区（下联/上联） -->
    <g v-else-if="kind === 'switch' && switchType === 'aggregation'">
      <rect x="4" y="14" width="64" height="42" rx="4" fill="#3b2f63" stroke="#1e1638" stroke-width="1.2" />
      <rect x="8" y="18" width="36" height="20" rx="2" fill="#845ef7" opacity="0.35" />
      <rect x="46" y="18" width="18" height="20" rx="2" fill="#fcc419" opacity="0.45" />
      <rect
        v-for="i in 6"
        :key="`agg-m-${i}`"
        :x="10 + (i - 1) * 5.5"
        y="22"
        width="4.5"
        height="12"
        rx="0.5"
        fill="#d0bfff"
        stroke="#7048e8"
        stroke-width="0.4"
      />
      <rect
        v-for="i in 3"
        :key="`agg-u-${i}`"
        :x="48 + (i - 1) * 5"
        y="22"
        width="4"
        height="12"
        rx="0.5"
        fill="#ffe066"
        stroke="#f59f00"
        stroke-width="0.4"
      />
      <text x="26" y="48" text-anchor="middle" class="zone-tag">DOWN</text>
      <text x="55" y="48" text-anchor="middle" class="zone-tag">UP</text>
      <text x="36" y="66" text-anchor="middle" class="icon-caption">{{ caption }}</text>
    </g>

    <!-- 核心交换机：立式模块机箱 + 线卡槽 -->
    <g v-else-if="kind === 'switch'">
      <rect x="14" y="6" width="44" height="52" rx="3" fill="#3d4450" stroke="#1f2329" stroke-width="1.2" />
      <rect x="17" y="9" width="38" height="6" rx="1" fill="#5b6b7c" />
      <rect
        v-for="i in 5"
        :key="`slot-${i}`"
        :x="18"
        :y="18 + (i - 1) * 7.2"
        width="36"
        height="6"
        rx="0.8"
        :fill="i === 3 ? '#606266' : '#2b3038'"
        stroke="#909399"
        stroke-width="0.5"
      />
      <rect
        v-for="i in 5"
        :key="`led-${i}`"
        x="20"
        :y="19.5 + (i - 1) * 7.2"
        width="2.5"
        height="3"
        rx="0.3"
        :fill="i % 2 ? '#67c23a' : '#e6a23c'"
      />
      <circle cx="48" cy="12" r="1.6" fill="#f56c6c" />
      <text x="36" y="68" text-anchor="middle" class="icon-caption">{{ caption }}</text>
    </g>

    <!-- 1U 服务器：扁宽机架面 -->
    <g v-else-if="kind === 'server' && serverU === 1">
      <rect x="6" y="24" width="60" height="22" rx="2" fill="#1f2933" stroke="#0b1016" stroke-width="1.2" />
      <rect x="10" y="28" width="28" height="14" rx="1" fill="#3a7bd5" opacity="0.45" />
      <rect x="42" y="28" width="8" height="14" rx="1" fill="#4b5563" />
      <rect x="52" y="28" width="8" height="14" rx="1" fill="#4b5563" />
      <circle cx="14" cy="41" r="1.5" fill="#67c23a" />
      <circle cx="20" cy="41" r="1.5" fill="#909399" />
      <text x="36" y="60" text-anchor="middle" class="icon-caption">SRV {{ caption }}</text>
    </g>

    <!-- 2U 服务器：双层盘位 -->
    <g v-else-if="kind === 'server' && serverU === 2">
      <rect x="10" y="12" width="52" height="42" rx="3" fill="#1f2933" stroke="#0b1016" stroke-width="1.2" />
      <rect x="14" y="16" width="18" height="11" rx="1" fill="#374151" stroke="#6b7280" stroke-width="0.6" />
      <rect x="36" y="16" width="18" height="11" rx="1" fill="#374151" stroke="#6b7280" stroke-width="0.6" />
      <rect x="14" y="30" width="18" height="11" rx="1" fill="#374151" stroke="#6b7280" stroke-width="0.6" />
      <rect x="36" y="30" width="18" height="11" rx="1" fill="#374151" stroke="#6b7280" stroke-width="0.6" />
      <rect x="14" y="44" width="32" height="6" rx="1" fill="#3a7bd5" opacity="0.55" />
      <circle cx="52" cy="47" r="2" fill="#67c23a" />
      <text x="36" y="66" text-anchor="middle" class="icon-caption">SRV {{ caption }}</text>
    </g>

    <!-- 4U 服务器：立式多盘位塔式 -->
    <g v-else-if="kind === 'server'">
      <rect x="18" y="4" width="36" height="56" rx="3" fill="#111827" stroke="#030712" stroke-width="1.2" />
      <rect x="22" y="8" width="28" height="8" rx="1" fill="#3a7bd5" opacity="0.6" />
      <rect
        v-for="i in 6"
        :key="`bay4-${i}`"
        x="22"
        :y="18 + (i - 1) * 6.2"
        width="28"
        height="5"
        rx="0.6"
        fill="#374151"
        stroke="#9ca3af"
        stroke-width="0.45"
      />
      <circle cx="26" cy="56" r="1.8" fill="#67c23a" />
      <circle cx="32" cy="56" r="1.8" fill="#e6a23c" />
      <text x="36" y="68" text-anchor="middle" class="icon-caption">SRV {{ caption }}</text>
    </g>

    <!-- 1U 安全设备：扁砖 + 盾牌 -->
    <g v-else-if="kind === 'security' && securityU === 1">
      <rect x="6" y="22" width="60" height="26" rx="4" fill="#7c2d12" stroke="#431407" stroke-width="1.2" />
      <rect x="10" y="26" width="36" height="18" rx="2" fill="#c45c26" opacity="0.9" />
      <path
        d="M18 35 l6 -7 6 7 6 -7 6 7"
        fill="none"
        stroke="#ffedd5"
        stroke-width="1.5"
        stroke-linecap="round"
      />
      <path
        d="M52 28 l8 4 v6 c0 5 -4 8 -8 10 c-4 -2 -8 -5 -8 -10 v-6 z"
        fill="#fed7aa"
        stroke="#9a3412"
        stroke-width="0.8"
      />
      <text x="36" y="62" text-anchor="middle" class="icon-caption">{{ caption }}</text>
    </g>

    <!-- 2U 安全设备：更高机箱 + 双排口 + 锁 -->
    <g v-else>
      <rect x="8" y="10" width="56" height="46" rx="5" fill="#5c3317" stroke="#2b1608" stroke-width="1.2" />
      <rect x="12" y="14" width="48" height="16" rx="2" fill="#c45c26" opacity="0.85" />
      <rect
        v-for="i in 4"
        :key="`sec-p-${i}`"
        :x="16 + (i - 1) * 11"
        y="36"
        width="8"
        height="10"
        rx="1"
        fill="#f3d2b3"
        stroke="#9a3412"
        stroke-width="0.5"
      />
      <circle cx="36" cy="22" r="5" fill="none" stroke="#ffe8d6" stroke-width="1.6" />
      <rect x="33" y="22" width="6" height="7" rx="1" fill="#ffe8d6" />
      <text x="36" y="68" text-anchor="middle" class="icon-caption">{{ caption }}</text>
    </g>

    <rect
      v-if="selected"
      x="2"
      y="2"
      width="68"
      height="68"
      rx="8"
      fill="none"
      stroke="#409eff"
      stroke-width="2.2"
      stroke-dasharray="4 2"
    />
  </svg>
</template>

<style scoped>
.topo-device-icon {
  display: block;
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.18));
}

.icon-caption {
  fill: #606266;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.zone-tag {
  fill: #e9ecef;
  font-size: 6px;
  font-weight: 700;
}
</style>
