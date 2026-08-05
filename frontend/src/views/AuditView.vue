<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { listAuditLogs, type AuditLog } from '@/api/audit'

const loading = ref(false)
const tableData = ref<AuditLog[]>([])
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const keyword = ref('')

const ACTION_LABELS: Record<string, string> = {
  login: '登录',
  login_failed: '登录失败',
  logout: '退出',
  refresh: '刷新令牌',
  create: '创建',
  update: '更新',
  delete: '删除',
  batch_mount: '批量上架',
  batch_unmount: '批量下架',
}

const RESOURCE_LABELS: Record<string, string> = {
  auth: '认证',
  users: '用户',
  roles: '角色',
  devices: '设备',
  racks: '机柜',
  rooms: '机房',
  layout: '布局',
  network: '网络',
  contracts: '合同',
  datacenters: '数据中心',
}

function actionLabel(code: string) {
  return ACTION_LABELS[code] || code
}

function resourceLabel(code: string) {
  return RESOURCE_LABELS[code] || code
}

function formatTime(iso: string) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function statusType(code: number) {
  if (code >= 200 && code < 300) return 'success'
  if (code >= 400 && code < 500) return 'warning'
  if (code >= 500) return 'danger'
  return 'info'
}

async function loadData() {
  loading.value = true
  try {
    const data = await listAuditLogs({
      page: pagination.page,
      page_size: pagination.page_size,
      keyword: keyword.value || undefined,
    })
    tableData.value = data.items
    pagination.total = data.pagination.total
  } finally {
    loading.value = false
  }
}

function onSearch() {
  pagination.page = 1
  void loadData()
}

onMounted(loadData)
</script>

<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>日志管理</span>
          <div class="actions">
            <el-input
              v-model="keyword"
              placeholder="搜索用户/动作/资源/路径"
              clearable
              style="width: 260px"
              @keyup.enter="onSearch"
              @clear="onSearch"
            />
            <el-button @click="onSearch">搜索</el-button>
            <el-button @click="loadData">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" stripe>
        <el-table-column label="时间" min-width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="用户" min-width="110">
          <template #default="{ row }">{{ row.username || '—' }}</template>
        </el-table-column>
        <el-table-column label="动作" min-width="110">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ actionLabel(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="资源" min-width="100">
          <template #default="{ row }">{{ resourceLabel(row.resource) }}</template>
        </el-table-column>
        <el-table-column prop="method" label="方法" width="80" />
        <el-table-column prop="path" label="路径" min-width="200" show-overflow-tooltip />
        <el-table-column label="IP" min-width="120">
          <template #default="{ row }">{{ row.ip_address || '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="88" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="statusType(row.status_code)">{{ row.status_code }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="detail" label="详情" min-width="180" show-overflow-tooltip />
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :total="pagination.total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="loadData"
          @size-change="
            () => {
              pagination.page = 1
              loadData()
            }
          "
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
