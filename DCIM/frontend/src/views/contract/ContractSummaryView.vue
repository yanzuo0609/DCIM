<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  getContractSummary,
  itemKindLabel,
  normalizeItemKind,
  type ContractItemKind,
  type DeviceContractSummary,
} from '@/api/contract'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const summaryData = ref<DeviceContractSummary[]>([])
const kindFilter = ref<'all' | ContractItemKind>('all')
const keyword = ref('')

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return summaryData.value.filter((row) => {
    if (kindFilter.value !== 'all' && normalizeItemKind(row.item_kind) !== kindFilter.value) {
      return false
    }
    if (!kw) return true
    const hay = [row.device_name, row.device_model_name, row.manufacturer_name, itemKindLabel(row.item_kind)]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return hay.includes(kw)
  })
})

const hwRows = computed(() =>
  filtered.value.filter((r) => normalizeItemKind(r.item_kind) === 'hardware'),
)
const swRows = computed(() =>
  filtered.value.filter((r) => normalizeItemKind(r.item_kind) === 'software'),
)

function remainOf(row: DeviceContractSummary) {
  return row.remaining_quantity ?? Math.max((row.purchase_quantity || 0) - (row.linked_count || 0), 0)
}

function formatYuan(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  return `${Number(value).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} 元`
}

async function loadSummary() {
  loading.value = true
  try {
    summaryData.value = await getContractSummary()
  } catch {
    summaryData.value = []
    ElMessage.error('加载采购汇总失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadSummary()
})
</script>

<template>
  <div class="summary-page">
    <header class="page-head">
      <div>
        <h2>采购汇总</h2>
        <p>按硬件 / 软件分类汇总采购数量、关联与金额</p>
      </div>
      <el-button size="small" :loading="loading" @click="loadSummary">刷新</el-button>
    </header>

    <div class="toolbar">
      <el-radio-group v-model="kindFilter" size="small">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="hardware">硬件</el-radio-button>
        <el-radio-button value="software">软件</el-radio-button>
      </el-radio-group>
      <el-input
        v-model="keyword"
        clearable
        size="small"
        placeholder="筛选名称 / 型号 / 厂商"
        style="width: 220px"
      />
      <span class="meta">硬件 {{ hwRows.length }} · 软件 {{ swRows.length }}</span>
    </div>

    <div class="summary-split">
      <el-card v-if="kindFilter !== 'software'" shadow="never" class="kind-card" :body-style="{ padding: 0 }">
        <template #header>
          <div class="kind-head">
            <span class="badge hw">硬件采购</span>
            <span class="muted">{{ hwRows.length }} 项</span>
          </div>
        </template>
        <el-table v-loading="loading" :data="hwRows" stripe size="small" max-height="420" empty-text="暂无硬件采购记录">
          <el-table-column prop="device_name" label="名称" min-width="110" show-overflow-tooltip>
            <template #default="{ row }">{{ row.device_name || '—' }}</template>
          </el-table-column>
          <el-table-column prop="device_model_name" label="型号" min-width="120" show-overflow-tooltip />
          <el-table-column prop="manufacturer_name" label="厂商" width="100" show-overflow-tooltip>
            <template #default="{ row }">{{ row.manufacturer_name || '—' }}</template>
          </el-table-column>
          <el-table-column prop="purchase_quantity" label="采购" width="70" align="right" />
          <el-table-column prop="linked_count" label="已关联" width="72" align="right" />
          <el-table-column label="剩余" width="64" align="right">
            <template #default="{ row }">
              <span :class="{ warn: remainOf(row) > 0 }">{{ remainOf(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="contract_count" label="合同" width="58" align="right" />
          <el-table-column label="均价" width="110" align="right">
            <template #default="{ row }">{{ formatYuan(row.avg_unit_price) }}</template>
          </el-table-column>
          <el-table-column label="采购额" width="120" align="right">
            <template #default="{ row }">{{ formatYuan(row.purchase_amount) }}</template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card v-if="kindFilter !== 'hardware'" shadow="never" class="kind-card" :body-style="{ padding: 0 }">
        <template #header>
          <div class="kind-head">
            <span class="badge sw">软件采购</span>
            <span class="muted">{{ swRows.length }} 项</span>
          </div>
        </template>
        <el-table v-loading="loading" :data="swRows" stripe size="small" max-height="420" empty-text="暂无软件采购记录">
          <el-table-column prop="device_name" label="名称" min-width="110" show-overflow-tooltip>
            <template #default="{ row }">{{ row.device_name || '—' }}</template>
          </el-table-column>
          <el-table-column prop="device_model_name" label="型号/版本" min-width="120" show-overflow-tooltip />
          <el-table-column prop="manufacturer_name" label="厂商" width="100" show-overflow-tooltip>
            <template #default="{ row }">{{ row.manufacturer_name || '—' }}</template>
          </el-table-column>
          <el-table-column prop="purchase_quantity" label="采购" width="70" align="right" />
          <el-table-column prop="linked_count" label="已关联" width="72" align="right" />
          <el-table-column label="剩余" width="64" align="right">
            <template #default="{ row }">
              <span :class="{ warn: remainOf(row) > 0 }">{{ remainOf(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="contract_count" label="合同" width="58" align="right" />
          <el-table-column label="均价" width="110" align="right">
            <template #default="{ row }">{{ formatYuan(row.avg_unit_price) }}</template>
          </el-table-column>
          <el-table-column label="采购额" width="120" align="right">
            <template #default="{ row }">{{ formatYuan(row.purchase_amount) }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.summary-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
}

.page-head h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #1f2a37;
}

.page-head p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #6b7c8f;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.meta {
  margin-left: auto;
  font-size: 12px;
  color: #8090a0;
}

.summary-split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.kind-card :deep(.el-card__header) {
  padding: 8px 12px;
}

.kind-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.badge {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
}

.badge.hw {
  color: #1d4ed8;
  background: #dbeafe;
}

.badge.sw {
  color: #6d28d9;
  background: #ede9fe;
}

.muted {
  color: #9aa8b6;
  font-size: 12px;
}

.warn {
  color: #b45309;
  font-weight: 600;
}

@media (max-width: 1200px) {
  .summary-split {
    grid-template-columns: 1fr;
  }
}
</style>
