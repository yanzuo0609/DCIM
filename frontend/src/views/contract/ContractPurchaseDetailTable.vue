<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  formatMoney,
  itemKindLabel,
  normalizeContractItems,
  normalizeItemKind,
  normalizePriceUnit,
  type ContractItemKind,
  type DeviceContract,
  type DeviceContractItem,
} from '@/api/contract'
import {
  listDeviceTypes,
  listParamProfiles,
  type DeviceType,
  type ParamProfile,
} from '@/api/device'
import { ElMessage } from 'element-plus'
import ParamProfileDetailDialog from '@/components/ParamProfileDetailDialog.vue'

const props = defineProps<{
  contract: DeviceContract | null
  loading?: boolean
}>()

const kindFilter = ref<'all' | ContractItemKind>('all')
const keyword = ref('')
const paramByName = ref<Map<string, ParamProfile>>(new Map())
const deviceTypes = ref<DeviceType[]>([])
const detailVisible = ref(false)
const detailProfile = ref<ParamProfile | null>(null)

watch(
  () => props.contract?.id,
  () => {
    kindFilter.value = 'all'
    keyword.value = ''
  },
)

type DisplayRow = {
  device_name?: string | null
  device_model_name: string
  manufacturer_name?: string | null
  item_kind?: string
  purchase_quantity: number
  purchase_amount?: number | null
  avg_unit_price: number | null
  response_quote?: number | null
  price_unit?: string
}

function itemToDisplayRow(item: DeviceContractItem): DisplayRow {
  const qty = Number(item.quantity || 0)
  const price = item.unit_price
  const amount =
    price != null && qty ? Math.round(qty * Number(price) * 100) / 100 : null
  return {
    device_name: item.device_name,
    device_model_name: item.device_model_name,
    manufacturer_name: item.manufacturer_name,
    item_kind: normalizeItemKind(item.item_kind),
    purchase_quantity: qty,
    purchase_amount: amount,
    avg_unit_price: price ?? null,
    response_quote: item.response_quote ?? null,
    price_unit: item.price_unit,
  }
}

const sourceRows = computed(() =>
  props.contract ? normalizeContractItems(props.contract).map(itemToDisplayRow) : [],
)

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return sourceRows.value.filter((row) => {
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

function moneyText(value: number | null | undefined, unit?: string | null) {
  return formatMoney(value, normalizePriceUnit(unit || 'wan'))
}

function nameKey(name: string | null | undefined) {
  return (name || '').trim().toLowerCase()
}

function paramOf(row: DisplayRow): ParamProfile | null {
  const key = nameKey(row.device_name)
  return key ? paramByName.value.get(key) || null : null
}

function openParams(row: DisplayRow) {
  const profile = paramOf(row)
  if (!profile) {
    ElMessage.warning('该设备尚未关联参数档案，请先在资产详细参数中同步或新建')
    return
  }
  detailProfile.value = profile
  detailVisible.value = true
}

async function loadParamMap() {
  try {
    const [profiles, types] = await Promise.all([listParamProfiles(), listDeviceTypes()])
    deviceTypes.value = types || []
    const map = new Map<string, ParamProfile>()
    for (const p of profiles) {
      for (const raw of [p.name, p.source_device_name, p.payload?.source_device_name]) {
        const key = nameKey(raw)
        if (key && !map.has(key)) map.set(key, p)
      }
    }
    paramByName.value = map
  } catch {
    paramByName.value = new Map()
  }
}

onMounted(() => {
  void loadParamMap()
})
</script>

<template>
  <div class="detail-panel" :class="{ single: isSingleKind }">
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
        placeholder="筛选设备名称 / 产品型号 / 产品厂商"
        style="width: 260px"
      />
      <span class="meta">{{ metaText }}</span>
    </div>

    <div class="summary-split" :class="{ single: isSingleKind }">
      <el-card
        v-if="showHardware"
        shadow="never"
        class="kind-card"
        :class="{ full: kindFilter === 'hardware' }"
        :body-style="{ padding: 0, flex: 1, flexDirection: 'column', overflow: 'hidden' }"
      >
        <template #header>
          <div class="kind-head">
            <span class="badge hw">硬件</span>
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
            class="sheet-table"
            empty-text="暂无硬件明细"
          >
            <el-table-column type="selection" width="40" />
            <el-table-column type="index" label="序号" width="56" align="center" />
            <el-table-column prop="device_name" label="设备名称" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.device_name || '—' }}</template>
            </el-table-column>
            <el-table-column prop="device_model_name" label="产品型号" min-width="120" show-overflow-tooltip />
            <el-table-column prop="manufacturer_name" label="产品厂商" min-width="100" show-overflow-tooltip>
              <template #default="{ row }">{{ row.manufacturer_name || '—' }}</template>
            </el-table-column>
            <el-table-column label="设备数量" width="88" align="center">
              <template #default="{ row }">{{ row.purchase_quantity || 0 }}</template>
            </el-table-column>
            <el-table-column label="货物单价" min-width="110" align="right">
              <template #default="{ row }">{{ moneyText(row.avg_unit_price, row.price_unit) }}</template>
            </el-table-column>
            <el-table-column label="响应报价" min-width="110" align="right">
              <template #default="{ row }">
                {{ row.response_quote != null ? moneyText(row.response_quote, row.price_unit) : '—' }}
              </template>
            </el-table-column>
            <el-table-column label="采购额" min-width="120" align="right">
              <template #default="{ row }">{{ moneyText(row.purchase_amount, row.price_unit) }}</template>
            </el-table-column>
            <el-table-column label="关联跳转" width="88" fixed="right" align="center">
              <template #default="{ row }">
                <el-button link type="primary" @click="openParams(row)">参数</el-button>
              </template>
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
            <span class="badge sw">软件</span>
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
            class="sheet-table"
            empty-text="暂无软件明细"
          >
            <el-table-column type="selection" width="40" />
            <el-table-column type="index" label="序号" width="56" align="center" />
            <el-table-column prop="device_name" label="设备名称" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.device_name || '—' }}</template>
            </el-table-column>
            <el-table-column prop="device_model_name" label="产品型号" min-width="120" show-overflow-tooltip />
            <el-table-column prop="manufacturer_name" label="产品厂商" min-width="100" show-overflow-tooltip>
              <template #default="{ row }">{{ row.manufacturer_name || '—' }}</template>
            </el-table-column>
            <el-table-column label="设备数量" width="88" align="center">
              <template #default="{ row }">{{ row.purchase_quantity || 0 }}</template>
            </el-table-column>
            <el-table-column label="货物单价" min-width="110" align="right">
              <template #default="{ row }">{{ moneyText(row.avg_unit_price, row.price_unit) }}</template>
            </el-table-column>
            <el-table-column label="响应报价" min-width="110" align="right">
              <template #default="{ row }">
                {{ row.response_quote != null ? moneyText(row.response_quote, row.price_unit) : '—' }}
              </template>
            </el-table-column>
            <el-table-column label="采购额" min-width="120" align="right">
              <template #default="{ row }">{{ moneyText(row.purchase_amount, row.price_unit) }}</template>
            </el-table-column>
            <el-table-column label="关联跳转" width="88" fixed="right" align="center">
              <template #default="{ row }">
                <el-button link type="primary" @click="openParams(row)">参数</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-card>
    </div>

    <ParamProfileDetailDialog
      v-model="detailVisible"
      :profile="detailProfile"
      :device-types="deviceTypes"
    />
  </div>
</template>

<style scoped>
.detail-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  min-height: 0;
}
.detail-panel.single {
  min-height: 360px;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.meta {
  font-size: 12px;
  color: #6b7c8f;
}
.summary-split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  flex: 1;
  min-height: 0;
}
.summary-split.single {
  grid-template-columns: 1fr;
}
.kind-card {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid #8aa0b8;
  background: #e8f0f8;
}
.kind-card.full {
  min-height: 360px;
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
  background: #dbeafe;
  color: #1d4ed8;
}
.badge.sw {
  background: #d1fae5;
  color: #047857;
}
.muted {
  color: #94a3b8;
  font-size: 12px;
}
.table-wrap {
  flex: 1;
  min-height: 240px;
}
.sheet-table {
  --el-table-header-bg-color: #c8d8ea;
  --el-table-header-text-color: #1f2a37;
  --el-table-bg-color: #eef4fb;
  --el-table-tr-bg-color: #eef4fb;
  --el-table-row-hover-bg-color: #dce8f7;
  --el-table-border-color: #8aa0b8;
}
</style>
