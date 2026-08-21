<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  formatMoney,
  getDeviceContract,
  listDeviceContracts,
  normalizePriceUnit,
  type DeviceContract,
} from '@/api/contract'
import { ElMessage } from 'element-plus'
import ContractPurchaseDetailTable from './ContractPurchaseDetailTable.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const listLoading = ref(false)
const contracts = ref<DeviceContract[]>([])
const contractDetail = ref<DeviceContract | null>(null)

const selectedId = computed({
  get: () => String(route.query.contract_id || ''),
  set: (id: string) => {
    if (!id) {
      void router.replace({ path: '/devices/contracts/details' })
      return
    }
    void router.replace({
      path: '/devices/contracts/details',
      query: { contract_id: id },
    })
  },
})

const contractOptions = computed(() =>
  contracts.value.map((c) => ({
    id: c.id,
    label: `${c.contract_no}${c.project_no ? ` · ${c.project_no}` : ''}`,
  })),
)

async function loadContractList() {
  listLoading.value = true
  try {
    const res = await listDeviceContracts({ page: 1, page_size: 200, sort: 'purchase_date', order: 'desc' })
    contracts.value = res.items || []
  } catch {
    contracts.value = []
    ElMessage.error('加载合同列表失败')
  } finally {
    listLoading.value = false
  }
}

async function loadDetail() {
  const id = selectedId.value
  if (!id) {
    contractDetail.value = null
    return
  }
  loading.value = true
  try {
    contractDetail.value = await getDeviceContract(id)
  } catch {
    contractDetail.value = null
    ElMessage.error('加载合同明细失败')
  } finally {
    loading.value = false
  }
}

function refreshAll() {
  void loadContractList()
  void loadDetail()
}

watch(
  () => route.query.contract_id,
  () => {
    void loadDetail()
  },
)

onMounted(async () => {
  await loadContractList()
  await loadDetail()
})
</script>

<template>
  <div class="summary-page">
    <header class="page-head">
      <div>
        <h2>资产汇总</h2>
        <p>按合同查看采购明细；硬件 / 软件分表展示，样式与「按设备类型」一致</p>
      </div>
      <div class="head-actions">
        <el-select
          v-model="selectedId"
          filterable
          clearable
          size="small"
          placeholder="选择合同编号"
          :loading="listLoading"
          style="width: 280px"
        >
          <el-option
            v-for="opt in contractOptions"
            :key="opt.id"
            :label="opt.label"
            :value="opt.id"
          />
        </el-select>
        <el-button size="small" :loading="loading || listLoading" @click="refreshAll">刷新</el-button>
      </div>
    </header>

    <div v-if="contractDetail" class="contract-meta">
      <span>合同：{{ contractDetail.contract_no }}</span>
      <span>项目：{{ contractDetail.project_no || '—' }}</span>
      <span>采购单位：{{ contractDetail.purchase_org || '—' }}</span>
      <span>使用单位：{{ contractDetail.using_org || '—' }}</span>
      <span>
        合同总价：{{
          formatMoney(
            contractDetail.contract_total ?? contractDetail.total_amount,
            normalizePriceUnit(contractDetail.price_unit || 'wan'),
          )
        }}
      </span>
      <span>采购时间：{{ contractDetail.purchase_date || contractDetail.signed_at || '—' }}</span>
    </div>

    <el-empty
      v-if="!selectedId"
      description="请选择合同，或从资产汇总「按设备类型」/ 合同台账进入查看"
    />
    <ContractPurchaseDetailTable
      v-else
      :contract="contractDetail"
      :loading="loading"
    />
  </div>
</template>

<style scoped>
.summary-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: calc(100vh - 210px);
  min-height: 420px;
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
.head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.contract-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 18px;
  padding: 8px 12px;
  background: #e8f0f8;
  border: 1px solid #8aa0b8;
  font-size: 13px;
  color: #1f2a37;
  flex-shrink: 0;
}
</style>
