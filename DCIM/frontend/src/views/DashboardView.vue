<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchDashboardSummary, type DashboardSummary } from '@/api/dashboard'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(true)
const health = ref<{ status: string; version?: string } | null>(null)
const summary = ref<DashboardSummary | null>(null)

onMounted(async () => {
  try {
    const response = await fetch('/health')
    health.value = await response.json()
  } catch {
    health.value = { status: 'offline' }
  }

  if (auth.hasPermission('dashboard:view')) {
    try {
      summary.value = await fetchDashboardSummary()
    } catch {
      summary.value = null
    }
  }

  loading.value = false
})

function openScreen(blank = false) {
  if (blank) {
    window.open(router.resolve({ name: 'dashboard-screen' }).href, '_blank')
    return
  }
  void router.push({ name: 'dashboard-screen' })
}
</script>

<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <el-col :span="24">
        <el-card shadow="never">
          <template #header>
            <div class="card-head">
              <span>系统概览</span>
              <div class="actions">
                <el-button type="primary" @click="openScreen(false)">打开运营大屏</el-button>
                <el-button @click="openScreen(true)">新窗口大屏</el-button>
              </div>
            </div>
          </template>
          <el-skeleton v-if="loading" :rows="2" animated />
          <div v-else class="status">
            <el-tag :type="health?.status === 'ok' ? 'success' : 'danger'" size="large">
              API {{ health?.status === 'ok' ? '在线' : '离线' }}
            </el-tag>
            <p v-if="health?.version">RackDCIM Pro v{{ health.version }}</p>
            <p v-if="auth.profile">欢迎，{{ auth.profile.full_name || auth.profile.username }}</p>
            <p class="hint">运营大屏支持模块化自定义：可开关图表模块、调整布局列宽与 KPI 指标，适合投屏 / 值班室展示。</p>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row v-if="summary" :gutter="20" class="stats">
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover"><div class="stat"><span class="label">数据中心</span><span class="value">{{ summary.datacenter_count }}</span></div></el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover"><div class="stat"><span class="label">机房</span><span class="value">{{ summary.room_count }}</span></div></el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover"><div class="stat"><span class="label">机柜</span><span class="value">{{ summary.rack_count }}</span></div></el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover"><div class="stat"><span class="label">设备</span><span class="value">{{ summary.device_count }}</span></div></el-card>
      </el-col>
    </el-row>

    <el-row v-if="summary" :gutter="20" class="stats">
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover"><div class="stat"><span class="label">已上架</span><span class="value">{{ summary.mounted_device_count }}</span></div></el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover"><div class="stat"><span class="label">总 U 位</span><span class="value">{{ summary.total_u }}</span></div></el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover"><div class="stat"><span class="label">利用率</span><span class="value">{{ summary.utilization }}%</span></div></el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card shadow="hover"><div class="stat"><span class="label">总功耗(W)</span><span class="value">{{ summary.total_power }}</span></div></el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 20px; }
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.actions { display: flex; gap: 8px; flex-wrap: wrap; }
.status p { margin: 12px 0 0; color: #606266; }
.hint { font-size: 13px; }
.stats { margin-top: 0; }
.stat { display: flex; flex-direction: column; gap: 8px; }
.stat .label { color: #909399; font-size: 14px; }
.stat .value { font-size: 28px; font-weight: 600; color: #303133; }
</style>
