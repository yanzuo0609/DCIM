<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { EChartsOption } from 'echarts'
import { fetchDashboardAnalytics, type DashboardAnalytics } from '@/api/dashboard'
import ScreenChart from '@/components/screen/ScreenChart.vue'
import ScreenConfigDrawer from '@/components/screen/ScreenConfigDrawer.vue'
import Room3DMonitor from '@/components/screen/Room3DMonitor.vue'
import { useAuthStore } from '@/stores/auth'
import {
  loadScreenLayout,
  resetScreenLayout,
  saveScreenLayout,
  type ScreenLayoutConfig,
} from '@/utils/screenLayout'

const router = useRouter()
const auth = useAuthStore()

const loading = ref(true)
const refreshing = ref(false)
const errorMsg = ref('')
const analytics = ref<DashboardAnalytics | null>(null)
const now = ref(new Date())
const lastUpdated = ref<Date | null>(null)
const configOpen = ref(false)
const layout = ref<ScreenLayoutConfig>(loadScreenLayout())
const roomMonitorRef = ref<InstanceType<typeof Room3DMonitor> | null>(null)

let clockTimer: number | undefined
let refreshTimer: number | undefined

const clockText = computed(() => {
  const d = now.value
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
})

const runtime = computed(() => analytics.value?.runtime)

const COLORS = ['#1ec8a5', '#3aa0ff', '#f0b429', '#e35d5b', '#9b7bff', '#5bd2c8', '#ff8f5a', '#6ec1e4']

const runtimeGaugeOption = computed<EChartsOption | null>(() => {
  const r = runtime.value
  if (!r) return null
  return {
    series: [
      {
        type: 'pie',
        radius: ['62%', '82%'],
        center: ['50%', '50%'],
        silent: true,
        label: { show: false },
        data: [
          {
            value: r.running_ratio,
            itemStyle: {
              color: {
                type: 'linear',
                x: 0,
                y: 0,
                x2: 1,
                y2: 1,
                colorStops: [
                  { offset: 0, color: '#1ec8a5' },
                  { offset: 1, color: '#3aa0ff' },
                ],
              },
            },
          },
          { value: Math.max(0, 100 - r.running_ratio), itemStyle: { color: 'rgba(80,110,130,0.25)' } },
        ],
      },
    ],
    graphic: [
      {
        type: 'text',
        left: 'center',
        top: '38%',
        style: {
          text: `${r.running_ratio}%`,
          fill: '#e8f7f2',
          font: '700 26px "IBM Plex Mono", monospace',
          textAlign: 'center',
        },
      },
      {
        type: 'text',
        left: 'center',
        top: '58%',
        style: {
          text: '运行设备',
          fill: 'rgba(180,210,220,0.75)',
          font: '12px "IBM Plex Sans", sans-serif',
          textAlign: 'center',
        },
      },
    ],
  }
})

const trendOption = computed<EChartsOption | null>(() => {
  const pts = analytics.value?.device_trend || []
  if (!pts.length) return null
  return {
    grid: { left: 36, right: 12, top: 24, bottom: 28 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: pts.map((p) => p.label),
      axisLabel: { color: 'rgba(180,210,220,0.65)', fontSize: 10 },
      axisLine: { lineStyle: { color: 'rgba(94,168,170,0.35)' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: 'rgba(180,210,220,0.55)', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(120,160,180,0.12)' } },
    },
    series: [
      {
        type: 'line',
        smooth: true,
        data: pts.map((p) => p.value),
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2, color: '#1ec8a5' },
        itemStyle: { color: '#1ec8a5' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(30,200,165,0.45)' },
              { offset: 1, color: 'rgba(30,200,165,0.02)' },
            ],
          },
        },
      },
    ],
  }
})

const typeOnlineOption = computed<EChartsOption | null>(() => {
  const rows = analytics.value?.type_online_status || []
  if (!rows.length) return null
  return {
    legend: {
      top: 0,
      textStyle: { color: 'rgba(180,210,220,0.75)', fontSize: 11 },
      data: ['正常', '异常'],
    },
    grid: { left: 48, right: 12, top: 28, bottom: 28 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: rows.map((r) => r.name),
      axisLabel: { color: 'rgba(180,210,220,0.65)', fontSize: 10, rotate: rows.length > 4 ? 20 : 0 },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: 'rgba(180,210,220,0.55)', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(120,160,180,0.12)' } },
    },
    series: [
      {
        name: '正常',
        type: 'bar',
        stack: 's',
        barWidth: 18,
        data: rows.map((r) => r.normal),
        itemStyle: { color: '#1ec8a5' },
      },
      {
        name: '异常',
        type: 'bar',
        stack: 's',
        data: rows.map((r) => r.abnormal),
        itemStyle: { color: '#f0b429' },
      },
    ],
  }
})

const typePieOption = computed<EChartsOption | null>(() => {
  const rows = analytics.value?.device_by_type || []
  if (!rows.length) return null
  return {
    color: COLORS,
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [
      {
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '50%'],
        roseType: false,
        itemStyle: { borderColor: '#071018', borderWidth: 2 },
        label: {
          color: 'rgba(210,230,235,0.9)',
          formatter: '{b}\n{c}',
          fontSize: 11,
        },
        data: rows.map((r) => ({ name: r.name, value: r.value })),
      },
    ],
  }
})

const dcRankOption = computed<EChartsOption | null>(() => {
  const rows = [...(analytics.value?.devices_by_datacenter || [])].reverse()
  if (!rows.length) return null
  return {
    grid: { left: 110, right: 40, top: 8, bottom: 8 },
    xAxis: {
      type: 'value',
      axisLabel: { color: 'rgba(180,210,220,0.55)', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(120,160,180,0.12)' } },
    },
    yAxis: {
      type: 'category',
      data: rows.map((r) => r.name),
      axisLabel: { color: 'rgba(210,230,235,0.85)', fontSize: 11, width: 96, overflow: 'truncate' },
    },
    series: [
      {
        type: 'bar',
        data: rows.map((r) => r.value),
        barWidth: 12,
        itemStyle: {
          borderRadius: [0, 6, 6, 0],
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 1,
            y2: 0,
            colorStops: [
              { offset: 0, color: '#1a6fb5' },
              { offset: 1, color: '#3aa0ff' },
            ],
          },
        },
        label: { show: true, position: 'right', color: 'rgba(210,230,235,0.85)', fontSize: 11 },
      },
    ],
  }
})

const powerRankOption = computed<EChartsOption | null>(() => {
  const rows = [...(analytics.value?.power_by_rack || [])].reverse()
  if (!rows.length) return null
  return {
    grid: { left: 56, right: 40, top: 8, bottom: 8 },
    xAxis: {
      type: 'value',
      axisLabel: { color: 'rgba(180,210,220,0.55)', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(120,160,180,0.12)' } },
    },
    yAxis: {
      type: 'category',
      data: rows.map((r) => r.name),
      axisLabel: { color: 'rgba(210,230,235,0.85)', fontSize: 11 },
    },
    series: [
      {
        type: 'bar',
        data: rows.map((r) => r.value),
        barWidth: 12,
        itemStyle: {
          borderRadius: [0, 6, 6, 0],
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 1,
            y2: 0,
            colorStops: [
              { offset: 0, color: '#0e8f76' },
              { offset: 1, color: '#1ec8a5' },
            ],
          },
        },
        label: {
          show: true,
          position: 'right',
          color: 'rgba(210,230,235,0.85)',
          fontSize: 11,
          formatter: (p: { data: number }) => `${p.data}W`,
        },
      },
    ],
  }
})

async function loadData(silent = false) {
  if (!auth.hasPermission('dashboard:view')) {
    errorMsg.value = '当前账号无 Dashboard 查看权限'
    loading.value = false
    return
  }
  if (!silent) loading.value = true
  else refreshing.value = true
  errorMsg.value = ''
  try {
    analytics.value = await fetchDashboardAnalytics()
    lastUpdated.value = new Date()
    await roomMonitorRef.value?.reload()
  } catch (err: unknown) {
    const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
    errorMsg.value = msg || '加载大屏数据失败'
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

function restartRefreshTimer() {
  if (refreshTimer) window.clearInterval(refreshTimer)
  refreshTimer = window.setInterval(() => void loadData(true), layout.value.refreshSec * 1000)
}

function onSaveLayout(next: ScreenLayoutConfig) {
  layout.value = saveScreenLayout({
    ...next,
    title: next.title || '智慧机房管理驾驶舱',
  })
  restartRefreshTimer()
}

function onResetLayout() {
  const base = resetScreenLayout()
  base.title = '智慧机房管理驾驶舱'
  base.theme = 'teal'
  layout.value = saveScreenLayout(base)
  restartRefreshTimer()
}

async function enterFullscreen() {
  try {
    if (!document.fullscreenElement) await document.documentElement.requestFullscreen?.()
  } catch {
    /* ignore */
  }
}

async function exitScreen() {
  try {
    if (document.fullscreenElement) await document.exitFullscreen()
  } catch {
    /* ignore */
  }
  void router.push('/')
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && !configOpen.value) void exitScreen()
  if (e.key === 'f' || e.key === 'F') void enterFullscreen()
  if (e.key === 'c' || e.key === 'C') configOpen.value = true
}

onMounted(async () => {
  if (!layout.value.title || layout.value.title === '数据中心运营大屏') {
    layout.value = saveScreenLayout({ ...layout.value, title: '智慧机房管理驾驶舱' })
  }
  clockTimer = window.setInterval(() => {
    now.value = new Date()
  }, 1000)
  await loadData()
  restartRefreshTimer()
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  if (clockTimer) window.clearInterval(clockTimer)
  if (refreshTimer) window.clearInterval(refreshTimer)
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="cockpit" :class="`theme-${layout.theme || 'teal'}`">
    <div class="bg-grid" />
    <div class="bg-glow" />

    <header class="top">
      <div class="top-left">
        <span class="brand">RackDCIM Pro</span>
        <span class="meta">{{ refreshing ? '刷新中…' : lastUpdated ? '数据已同步' : '' }}</span>
      </div>
      <h1 class="title">
        <span class="title-deco" />
        {{ layout.title || '智慧机房管理驾驶舱' }}
        <span class="title-deco mirror" />
      </h1>
      <div class="top-right">
        <span class="clock">{{ clockText }}</span>
        <button type="button" class="btn ghost" @click="configOpen = true">自定义</button>
        <button type="button" class="btn ghost" @click="enterFullscreen">全屏</button>
        <button type="button" class="btn" @click="loadData(true)">刷新</button>
        <button type="button" class="btn ghost" @click="exitScreen">退出</button>
      </div>
    </header>

    <div v-if="loading" class="state">正在加载驾驶舱数据…</div>
    <div v-else-if="errorMsg" class="state warn">{{ errorMsg }}</div>

    <main v-else class="layout">
      <!-- 左栏 -->
      <section class="col left">
        <article class="panel">
          <header class="panel-title">设备运行状态</header>
          <div class="runtime">
            <ScreenChart class="runtime-chart" :option="runtimeGaugeOption" height="150px" />
            <div class="runtime-stats">
              <div class="stat blue">
                <span>运行中</span>
                <strong>{{ runtime?.running || 0 }}/{{ runtime?.total || 0 }}</strong>
              </div>
              <div class="stat red">
                <span>故障</span>
                <strong>{{ runtime?.fault || 0 }}/{{ runtime?.total || 0 }}</strong>
              </div>
              <div class="stat yellow">
                <span>离线</span>
                <strong>{{ runtime?.offline || 0 }}/{{ runtime?.total || 0 }}</strong>
              </div>
              <div class="stat amber">
                <span>待维修</span>
                <strong>{{ runtime?.repair || 0 }}/{{ runtime?.total || 0 }}</strong>
              </div>
            </div>
          </div>
        </article>

        <article class="panel">
          <header class="panel-title">新增设备趋势</header>
          <ScreenChart v-if="trendOption" :option="trendOption" height="170px" />
          <p v-else class="empty">暂无趋势数据</p>
        </article>

        <article class="panel grow">
          <header class="panel-title">各品类设备在线状态</header>
          <ScreenChart v-if="typeOnlineOption" :option="typeOnlineOption" height="190px" />
          <p v-else class="empty">暂无品类在线数据</p>
        </article>
      </section>

      <!-- 中栏 -->
      <section class="col center">
        <article class="panel room-panel">
          <Room3DMonitor ref="roomMonitorRef" />
        </article>

        <article class="panel alert-panel">
          <header class="panel-title">异常隐患记录</header>
          <table class="alert-table">
            <thead>
              <tr>
                <th>故障编号</th>
                <th>设备名称</th>
                <th>异常时间</th>
                <th>数值</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in analytics?.alert_records || []" :key="`${row.code}-${idx}`">
                <td>{{ row.code }}</td>
                <td>{{ row.device_name }}</td>
                <td>{{ row.event_time }}</td>
                <td>{{ row.value || '-' }}</td>
              </tr>
              <tr v-if="!(analytics?.alert_records || []).length">
                <td colspan="4" class="empty-cell">当前无高利用率告警</td>
              </tr>
            </tbody>
          </table>
        </article>
      </section>

      <!-- 右栏 -->
      <section class="col right">
        <article class="panel">
          <header class="panel-title">设备分类统计</header>
          <ScreenChart v-if="typePieOption" :option="typePieOption" height="210px" />
          <p v-else class="empty">暂无分类数据</p>
        </article>

        <article class="panel">
          <header class="panel-title">数据中心设备数量排名</header>
          <ScreenChart v-if="dcRankOption" :option="dcRankOption" height="180px" />
          <p v-else class="empty">暂无排名数据</p>
        </article>

        <article class="panel grow">
          <header class="panel-title">设备连接功率排名</header>
          <ScreenChart v-if="powerRankOption" :option="powerRankOption" height="180px" />
          <p v-else class="empty">暂无功率数据</p>
        </article>
      </section>
    </main>

    <ScreenConfigDrawer
      v-model="configOpen"
      :config="layout"
      @save="onSaveLayout"
      @reset="onResetLayout"
    />
  </div>
</template>

<style scoped>
.cockpit {
  --bg: #06101a;
  --bg-mid: #0b1c2c;
  --panel: rgba(8, 28, 42, 0.78);
  --line: rgba(64, 180, 190, 0.35);
  --text: #e7f4f1;
  --muted: rgba(170, 205, 215, 0.72);
  --accent: #1ec8a5;
  --accent-2: #3aa0ff;
  --grid: rgba(30, 200, 165, 0.045);
  --glow-a: rgba(58, 160, 255, 0.16);
  --glow-b: rgba(30, 200, 165, 0.1);
  --btn-bg: rgba(30, 200, 165, 0.14);
  --btn-border: rgba(30, 200, 165, 0.5);
  --title-shadow: rgba(58, 160, 255, 0.35);
  min-height: 100vh;
  color: var(--text);
  background: radial-gradient(ellipse at top, var(--bg-mid) 0%, var(--bg) 55%);
  font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
  position: relative;
  overflow: hidden;
  padding: 10px 16px 14px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.cockpit.theme-teal {
  --bg: #06101a;
  --bg-mid: #0b1c2c;
  --panel: rgba(8, 28, 42, 0.78);
  --line: rgba(64, 180, 190, 0.35);
  --text: #e7f4f1;
  --muted: rgba(170, 205, 215, 0.72);
  --accent: #1ec8a5;
  --accent-2: #3aa0ff;
  --grid: rgba(30, 200, 165, 0.045);
  --glow-a: rgba(58, 160, 255, 0.16);
  --glow-b: rgba(30, 200, 165, 0.1);
  --btn-bg: rgba(30, 200, 165, 0.14);
  --btn-border: rgba(30, 200, 165, 0.5);
  --title-shadow: rgba(58, 160, 255, 0.35);
}

.cockpit.theme-cyan {
  --bg: #040b14;
  --bg-mid: #071824;
  --panel: rgba(6, 24, 40, 0.82);
  --line: rgba(34, 211, 238, 0.32);
  --text: #e0f7ff;
  --muted: rgba(148, 200, 220, 0.72);
  --accent: #22d3ee;
  --accent-2: #60a5fa;
  --grid: rgba(34, 211, 238, 0.05);
  --glow-a: rgba(96, 165, 250, 0.18);
  --glow-b: rgba(34, 211, 238, 0.12);
  --btn-bg: rgba(34, 211, 238, 0.14);
  --btn-border: rgba(34, 211, 238, 0.5);
  --title-shadow: rgba(34, 211, 238, 0.4);
}

.cockpit.theme-amber {
  --bg: #120c08;
  --bg-mid: #1c140c;
  --panel: rgba(36, 22, 12, 0.82);
  --line: rgba(245, 158, 11, 0.32);
  --text: #fff4e6;
  --muted: rgba(220, 190, 150, 0.72);
  --accent: #f59e0b;
  --accent-2: #fb7185;
  --grid: rgba(245, 158, 11, 0.05);
  --glow-a: rgba(251, 113, 133, 0.14);
  --glow-b: rgba(245, 158, 11, 0.12);
  --btn-bg: rgba(245, 158, 11, 0.14);
  --btn-border: rgba(245, 158, 11, 0.5);
  --title-shadow: rgba(245, 158, 11, 0.35);
}

.cockpit.theme-violet {
  --bg: #0b0616;
  --bg-mid: #140a24;
  --panel: rgba(24, 14, 42, 0.82);
  --line: rgba(167, 139, 250, 0.34);
  --text: #f3eeff;
  --muted: rgba(190, 175, 230, 0.72);
  --accent: #a78bfa;
  --accent-2: #38bdf8;
  --grid: rgba(167, 139, 250, 0.05);
  --glow-a: rgba(56, 189, 248, 0.16);
  --glow-b: rgba(167, 139, 250, 0.14);
  --btn-bg: rgba(167, 139, 250, 0.14);
  --btn-border: rgba(167, 139, 250, 0.5);
  --title-shadow: rgba(167, 139, 250, 0.4);
}

.cockpit.theme-steel {
  --bg: #0a0e12;
  --bg-mid: #121820;
  --panel: rgba(18, 24, 32, 0.86);
  --line: rgba(148, 163, 184, 0.3);
  --text: #e8eef5;
  --muted: rgba(160, 175, 195, 0.72);
  --accent: #94a3b8;
  --accent-2: #38bdf8;
  --grid: rgba(148, 163, 184, 0.05);
  --glow-a: rgba(56, 189, 248, 0.12);
  --glow-b: rgba(148, 163, 184, 0.1);
  --btn-bg: rgba(148, 163, 184, 0.14);
  --btn-border: rgba(148, 163, 184, 0.45);
  --title-shadow: rgba(56, 189, 248, 0.28);
}

.bg-grid,
.bg-glow {
  pointer-events: none;
  position: absolute;
  inset: 0;
}

.bg-grid {
  background-image:
    linear-gradient(var(--grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--grid) 1px, transparent 1px);
  background-size: 42px 42px;
  mask-image: radial-gradient(ellipse at center, #000 40%, transparent 85%);
}

.bg-glow {
  background:
    radial-gradient(circle at 50% 0%, var(--glow-a), transparent 42%),
    radial-gradient(circle at 20% 80%, var(--glow-b), transparent 40%);
}

.top,
.layout,
.state {
  position: relative;
  z-index: 1;
}

.top {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  min-height: 56px;
}

.brand {
  font-weight: 700;
  letter-spacing: 0.04em;
}

.meta {
  margin-left: 10px;
  font-size: 12px;
  color: var(--muted);
}

.title {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: clamp(22px, 2.4vw, 34px);
  font-weight: 700;
  letter-spacing: 0.12em;
  text-shadow: 0 0 18px var(--title-shadow);
}

.title-deco {
  width: 72px;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--accent-2));
}

.title-deco.mirror {
  background: linear-gradient(90deg, var(--accent-2), transparent);
}

.top-right {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.clock {
  font-family: 'IBM Plex Mono', monospace;
  font-weight: 700;
  margin-right: 4px;
}

.btn {
  border: 1px solid var(--btn-border);
  background: var(--btn-bg);
  color: var(--text);
  border-radius: 4px;
  padding: 5px 10px;
  font-size: 12px;
  cursor: pointer;
}

.btn.ghost {
  background: transparent;
  border-color: color-mix(in srgb, var(--text) 28%, transparent);
}

.layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1.05fr 1.5fr 1.05fr;
  gap: 12px;
}

.col {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 10px 12px 12px;
  box-shadow: inset 0 0 24px color-mix(in srgb, var(--accent) 8%, transparent);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.panel.grow {
  flex: 1;
}

.panel-title {
  position: relative;
  margin: 0 0 8px;
  padding-left: 10px;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.panel-title::before {
  content: '';
  position: absolute;
  left: 0;
  top: 3px;
  bottom: 3px;
  width: 3px;
  border-radius: 2px;
  background: linear-gradient(180deg, var(--accent-2), var(--accent));
}

.runtime {
  display: grid;
  grid-template-columns: 150px 1fr;
  gap: 10px;
  align-items: center;
}

.runtime-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.stat {
  border: 1px solid rgba(94, 168, 170, 0.25);
  background: rgba(6, 20, 30, 0.55);
  border-radius: 6px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat span {
  font-size: 12px;
  color: var(--muted);
}

.stat strong {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 16px;
}

.stat.blue strong { color: #3aa0ff; }
.stat.red strong { color: #e35d5b; }
.stat.yellow strong { color: #f0b429; }
.stat.amber strong { color: #ffcf70; }

.room-panel {
  flex: 1.4;
  min-height: 360px;
}

.alert-panel {
  min-height: 180px;
}

.alert-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.alert-table th,
.alert-table td {
  border-bottom: 1px solid rgba(94, 168, 170, 0.18);
  padding: 8px 6px;
  text-align: left;
}

.alert-table th {
  color: var(--muted);
  font-weight: 600;
}

.empty,
.empty-cell {
  color: var(--muted);
  text-align: center;
  font-size: 13px;
}

.state {
  flex: 1;
  display: grid;
  place-items: center;
  font-size: 18px;
  color: var(--muted);
}

.state.warn {
  color: #f0b429;
}

@media (max-width: 1200px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .top {
    grid-template-columns: 1fr;
  }
  .title {
    justify-content: center;
  }
  .room-box {
    transform: none;
  }
  .target-tip {
    transform: none;
  }
}
</style>
