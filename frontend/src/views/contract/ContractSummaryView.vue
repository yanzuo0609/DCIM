<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  getContractSummary,
  itemKindLabel,
  normalizeItemKind,
  formatMoneyFromYuan,
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

const showHardware = computed(() => kindFilter.value !== 'software')
const showSoftware = computed(() => kindFilter.value !== 'hardware')
const isSingleKind = computed(() => kindFilter.value !== 'all')

const metaText = computed(() => {
  if (kindFilter.value === 'hardware') return `硬件 ${hwRows.value.length} 项`
  if (kindFilter.value === 'software') return `软件 ${swRows.value.length} 项`
  return `硬件 ${hwRows.value.length} · 软件 ${swRows.value.length}`
})

function remainOf(row: DeviceContractSummary) {
  return row.remaining_quantity ?? Math.max((row.purchase_quantity || 0) - (row.linked_count || 0), 0)
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
  <div class="summary-page" :class="{ single: isSingleKind }">
    <header class="page-head">
      <div>
        <h2>采购汇总</h2>
        <p>按硬件 / 软件分类汇总采购数量；「已关联」为已绑定合同且设备名称/型号与明细一致的台数</p>
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
      <span class="meta">{{ metaText }}</span>
    </div>

    <div class="summary-split" :class="{ single: isSingleKind }">
      <el-card
        v-if="showHardware"
        shadow="never"
        class="kind-card"
        :class="{ full: kindFilter === 'hardware' }"
        :body-style="{ padding: 0, display: 1, displayDirection: 'column', overflow: 'hidden' }"
      >
        <template #header>
          <div class="kind-head">
            <span class="badge hw">硬件采购</span>
            <span class="muted">{{ hwRows.length }} 项</span>
          </div>
        </template>
        <div class="table-wrap">
          <el-table
            v-loading="loading"
            :data="hwRows"
            stripe
            size="small"
            height="100%"
            empty-text="暂无硬件采购记录"
          >
            <el-table-column prop="device_name" label="设备名称" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.device_name || '—' }}</template>
            </el-table-column>
            <el-table-column prop="device_model_name" label="型号" min-width="130" show-overflow-tooltip />
            <el-table-column prop="manufacturer_name" label="厂商" min-width="100" show-overflow-tooltip>
              <template #default="{ row }">{{ row.manufacturer_name || '—' }}</template>
            </el-table-column>
            <el-table-column prop="purchase_quantity" label="采购数量" min-width="96" align="right" />
            <el-table-column prop="linked_count" label="已关联" min-width="88" align="right" />
            <el-table-column label="剩余" min-width="80" align="right">
              <template #default="{ row }">
                <span :class="{ warn: remainOf(row) > 0 }">{{ remainOf(row) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="contract_count" label="合同" min-width="72" align="right" />
            <el-table-column label="均价" min-width="128" align="right">
              <template #default="{ row }">{{ formatMoneyFromYuan(row.avg_unit_price) }}</template>
            </el-table-column>
            <el-table-column label="采购额" min-width="136" align="right">
              <template #default="{ row }">{{ formatMoneyFromYuan(row.purchase_amount) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </el-card>

      <el-card
        v-if="showSoftware"
        shadow="never"
        class="kind-card"
        :class="{ full: kindFilter === 'software' }"
        :body-style="{ padding: 0, flex: 1, flexDirection: 'column', overflow: 'hidden' }"
      >
        <template #header>
          <div class="kind-head">
            <span class="badge sw">软件采购</span>
            <span class="muted">{{ swRows.length }} 项</span>
          </div>
        </template>
        <div class="table-wrap">
          <el-table
            v-loading="loading"
            :data="swRows"
            stripe
            size="small"
            height="100%"
            empty-text="暂无软件采购记录"
          >
            <el-table-column prop="device_name" label="设备名称" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.device_name || '—' }}</template>
            </el-table-column>
            <el-table-column prop="device_model_name" label="型号" min-width="130" show-overflow-tooltip />
            <el-table-column prop="manufacturer_name" label="厂商" min-width="100" show-overflow-tooltip>
              <template #default="{ row }">{{ row.manufacturer_name || '—' }}</template>
            </el-table-column>
            <el-table-column prop="purchase_quantity" label="采购数量" min-width="96" align="right" />
            <el-table-column prop="linked_count" label="已关联" min-width="88" align="right" />
            <el-table-column label="剩余" min-width="80" align="right">
              <template #default="{ row }">
                <span :class="{ warn: remainOf(row) > 0 }">{{ remainOf(row) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="contract_count" label="合同" min-width="72" align="right" />
            <el-table-column label="均价" min-width="128" align="right">
              <template #default="{ row }">{{ formatMoneyFromYuan(row.avg_unit_price) }}</template>
            </el-table-column>
            <el-table-column label="采购额" min-width="136" align="right">
              <template #default="{ row }">{{ formatMoneyFromYuan(row.purchase_amount) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.summary-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: calc(100vh - 180px);
}

.summary-page.single {
  flex: 1;
  height: auto;
  min-height: calc(100vh - 180px);
}

.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  flex-shrink: 0;
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
  flex-shrink: 0;
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
  flex: 1;
  min-height: 420px;
  align-items: stretch;
}

.summary-split.single {
  grid-template-columns: 1fr;
  min-height: 0;
}

.kind-card {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid #e8eef5;
  overflow: hidden;
}

.kind-card.full {
  height: 100%;
}

.kind-card :deep(.el-card__header) {
  padding: 8px 12px;
  flex-shrink: 0;
}

.kind-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.table-wrap {
  flex: 1;
  min-height: 360px;
  overflow: hidden;
}

.summary-split.single .table-wrap {
  min-height: 0;
  height: 100%;
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
  .summary-split:not(.single) {
    grid-template-columns: 1fr;
  }
}
</style>
