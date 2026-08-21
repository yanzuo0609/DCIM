<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  calcItemsAmount,
  createDeviceContract,
  downloadContractItemsTemplate,
  formatMoney,
  formatMoneyFromYuan,
  getContractSummary,
  importContractItems,
  listDeviceContracts,
  normalizeContractItems,
  normalizeItemKind,
  normalizePriceUnit,
  normalizeQuantityUnit,
  contractHwQty,
  contractSwQty,
  DEFAULT_PRICE_UNIT,
  FUND_SOURCE_OPTIONS,
  USING_ORG_OPTIONS,
  PRICE_UNIT_OPTIONS,
  QUANTITY_UNIT_OPTIONS,
  syncContractModels,
  updateDeviceContract,
  type ContractItemKind,
  type DeviceContract,
  type DeviceContractItem,
  type DeviceContractSummary,
  type PriceUnit,
} from '@/api/contract'
import { syncParamProfilesFromContracts } from '@/api/device'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()
const canCreate = auth.hasPermission('device:create')
const canUpdate = auth.hasPermission('device:update')

const loading = ref(false)
const summaryLoading = ref(false)
const tableData = ref<DeviceContract[]>([])
const summaryData = ref<DeviceContractSummary[]>([])
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const keyword = ref('')

const dialogVisible = ref(false)
const editingId = ref<string | null>(null)
const saving = ref(false)
const itemsImportInput = ref<HTMLInputElement | null>(null)
const itemsImporting = ref(false)

const emptyItem = (): DeviceContractItem & { _uid: string } => ({
  _uid: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
  device_name: '',
  device_model_name: '',
  manufacturer_name: '',
  item_kind: 'hardware',
  quantity: 0,
  quantity_unit: '台',
  unit_price: null,
  response_quote: null,
  price_unit: DEFAULT_PRICE_UNIT,
})

type FormDeviceItem = DeviceContractItem & { _uid: string }

const form = reactive({
  contract_no: '',
  project_no: '',
  project_budget: null as number | null,
  purchase_org: '',
  fund_source: '国家预算资金',
  using_org: '内部',
  winning_bidder: '',
  contract_total: null as number | null,
  signed_at: '' as string,
  device_items: [emptyItem()] as FormDeviceItem[],
  price_unit: DEFAULT_PRICE_UNIT as PriceUnit,
  purchase_date: '' as string,
  description: '',
})

const itemsAmountHint = computed(() => calcItemsAmount(form.device_items))
const itemsQuantityHint = computed(() =>
  form.device_items.reduce((sum, item) => sum + Number(item.quantity || 0), 0),
)
const formHwCount = computed(
  () => form.device_items.filter((i) => normalizeItemKind(i.item_kind) === 'hardware').length,
)
const formSwCount = computed(
  () => form.device_items.filter((i) => normalizeItemKind(i.item_kind) === 'software').length,
)

const detailVisible = ref(false)
const detailContract = ref<DeviceContract | null>(null)
const detailItems = computed(() =>
  detailContract.value ? normalizeContractItems(detailContract.value) : [],
)
const detailHwItems = computed(() =>
  detailItems.value.filter((i) => normalizeItemKind(i.item_kind) === 'hardware'),
)
const detailSwItems = computed(() =>
  detailItems.value.filter((i) => normalizeItemKind(i.item_kind) === 'software'),
)
const detailPriceUnit = computed(() =>
  normalizePriceUnit(detailContract.value?.price_unit || 'yuan'),
)

const overview = computed(() => {
  const rows = summaryData.value
  const hw = rows.filter((r) => normalizeItemKind(r.item_kind) === 'hardware')
  const sw = rows.filter((r) => normalizeItemKind(r.item_kind) === 'software')
  const sumQty = (list: DeviceContractSummary[]) =>
    list.reduce((s, r) => s + Number(r.purchase_quantity || 0), 0)
  const sumAmt = (list: DeviceContractSummary[]) => {
    let total = 0
    let has = false
    for (const r of list) {
      if (r.purchase_amount === null || r.purchase_amount === undefined) continue
      total += Number(r.purchase_amount)
      has = true
    }
    return has ? total : null
  }
  const sumLinked = (list: DeviceContractSummary[]) =>
    list.reduce((s, r) => s + Number(r.linked_count || 0), 0)
  const sumRemain = (list: DeviceContractSummary[]) =>
    list.reduce((s, r) => s + Number(r.remaining_quantity ?? Math.max((r.purchase_quantity || 0) - (r.linked_count || 0), 0)), 0)

  return {
    contractCount: pagination.total,
    skuCount: rows.length,
    hwSku: hw.length,
    swSku: sw.length,
    hwQty: sumQty(hw),
    swQty: sumQty(sw),
    totalQty: sumQty(rows),
    hwAmount: sumAmt(hw),
    swAmount: sumAmt(sw),
    totalAmount: sumAmt(rows),
    linked: sumLinked(rows),
    remaining: sumRemain(rows),
  }
})

function convertPriceUnitAmount(
  amount: number | null | undefined,
  fromUnit: PriceUnit,
  toUnit: PriceUnit,
): number | null {
  if (amount === null || amount === undefined || fromUnit === toUnit) {
    return amount ?? null
  }
  const value = Number(amount)
  if (!Number.isFinite(value)) return null
  const converted = toUnit === 'wan' ? value / 10000 : value * 10000
  return Math.round(converted * 100) / 100
}

function oppositePriceUnit(unit: PriceUnit): PriceUnit {
  return unit === 'wan' ? 'yuan' : 'wan'
}

function onItemPriceUnitChange(item: DeviceContractItem, newUnit: PriceUnit) {
  const oldUnit = oppositePriceUnit(newUnit)
  if (item.unit_price !== null && item.unit_price !== undefined) {
    item.unit_price = convertPriceUnitAmount(item.unit_price, oldUnit, newUnit)
  }
}

function onContractPriceUnitChange(newUnit: PriceUnit) {
  const oldUnit = oppositePriceUnit(newUnit)
  if (form.contract_total !== null && form.contract_total !== undefined) {
    form.contract_total = convertPriceUnitAmount(form.contract_total, oldUnit, newUnit)
  }
}

async function loadData() {
  loading.value = true
  try {
    const data = await listDeviceContracts({
      page: pagination.page,
      page_size: pagination.page_size,
      keyword: keyword.value || undefined,
    })
    tableData.value = data.items
    pagination.total = data.pagination.total
  } catch {
    tableData.value = []
    ElMessage.error('加载合同信息失败')
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  summaryLoading.value = true
  try {
    summaryData.value = await getContractSummary()
  } catch {
    summaryData.value = []
  } finally {
    summaryLoading.value = false
  }
}

function resetForm() {
  form.contract_no = ''
  form.project_no = ''
  form.project_budget = null
  form.purchase_org = ''
  form.fund_source = '国家预算资金'
  form.using_org = '内部'
  form.winning_bidder = ''
  form.signed_at = ''
  form.device_items = [emptyItem()]
  form.contract_total = null
  form.price_unit = DEFAULT_PRICE_UNIT
  form.purchase_date = ''
  form.description = ''
}

function fillContractTotalFromItems() {
  const yuanTotal = itemsAmountHint.value
  if (yuanTotal === null) return
  form.contract_total =
    form.price_unit === 'wan' ? convertPriceUnitAmount(yuanTotal, 'yuan', 'wan') : yuanTotal
}

function addDeviceItem(kind: ContractItemKind = 'hardware') {
  form.device_items.push({
    ...emptyItem(),
    item_kind: kind,
    quantity_unit: kind === 'software' ? '套' : '台',
  })
}

function setItemKind(item: FormDeviceItem, kind: ContractItemKind) {
  const next = normalizeItemKind(kind)
  item.item_kind = next
  // 切换类别时同步默认数量单位，避免被其它逻辑误判
  if (next === 'software' && item.quantity_unit === '台') {
    item.quantity_unit = '套'
  } else if (next === 'hardware' && item.quantity_unit === '套') {
    item.quantity_unit = '台'
  }
}

function removeDeviceItem(index: number) {
  if (form.device_items.length <= 1) {
    form.device_items[0] = emptyItem()
    return
  }
  form.device_items.splice(index, 1)
}

function mapImportedItem(item: DeviceContractItem): FormDeviceItem {
  const kind = normalizeItemKind(item.item_kind)
  return {
    _uid: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    device_name: item.device_name,
    device_model_name: item.device_model_name,
    manufacturer_name: item.manufacturer_name || '',
    item_kind: kind,
    quantity: Number(item.quantity || 0),
    quantity_unit: normalizeQuantityUnit(item.quantity_unit),
    unit_price:
      item.unit_price === null || item.unit_price === undefined ? null : Number(item.unit_price),
    response_quote:
      item.response_quote === null || item.response_quote === undefined
        ? null
        : Number(item.response_quote),
    price_unit: normalizePriceUnit(item.price_unit),
  }
}

function applyImportedItems(items: DeviceContractItem[]) {
  const mapped = items.map(mapImportedItem)
  const onlyEmpty =
    form.device_items.length === 1 &&
    !form.device_items[0].device_name.trim() &&
    !form.device_items[0].device_model_name.trim() &&
    !(form.device_items[0].manufacturer_name || '').trim()
  if (onlyEmpty) {
    form.device_items = mapped.length ? mapped : [emptyItem()]
    return
  }
  form.device_items.push(...mapped)
}

function extractErrorMessage(error: unknown, fallback: string) {
  const err = error as {
    response?: { data?: { message?: string; details?: { errors?: unknown[] } } }
    message?: string
  }
  const details = err.response?.data?.details?.errors
  if (Array.isArray(details) && details.length) {
    const first = details[0] as { msg?: string; loc?: unknown[] }
    if (first?.msg) {
      const field = Array.isArray(first.loc) ? first.loc.slice(-1)[0] : ''
      return field ? `${field}: ${first.msg}` : first.msg
    }
  }
  return err.response?.data?.message || err.message || fallback
}

function triggerItemsImport() {
  itemsImportInput.value?.click()
}

async function handleDownloadItemsTemplate() {
  try {
    await downloadContractItemsTemplate()
  } catch (error: unknown) {
    ElMessage.error(extractErrorMessage(error, '下载模板失败'))
  }
}

async function handleImportItemsFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  itemsImporting.value = true
  try {
    const result = await importContractItems(file)
    if (!result.items.length) {
      ElMessage.warning('未导入有效明细')
      if (result.errors.length) ElMessage.warning(result.errors.slice(0, 3).join('; '))
      return
    }
    applyImportedItems(result.items)
    ElMessage.success(`已导入 ${result.imported} 条明细`)
    if (result.errors.length) ElMessage.warning(result.errors.slice(0, 3).join('; '))
  } catch (error: unknown) {
    ElMessage.error(extractErrorMessage(error, '导入明细失败'))
  } finally {
    itemsImporting.value = false
  }
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openDetail(row: DeviceContract) {
  void router.push({
    path: '/devices/contracts/details',
    query: { contract_id: row.id },
  })
}

function itemLineAmount(item: DeviceContractItem): number | null {
  const qty = Number(item.quantity || 0)
  const price = item.unit_price
  if (price === null || price === undefined || !qty) return item.line_amount ?? null
  return Math.round(qty * Number(price) * 100) / 100
}

function itemPriceUnit(item: DeviceContractItem): PriceUnit {
  return normalizePriceUnit(item.price_unit || 'yuan')
}

function openEdit(row: DeviceContract) {
  editingId.value = row.id
  form.contract_no = row.contract_no
  form.project_no = row.project_no || ''
  form.project_budget = row.project_budget ?? null
  form.purchase_org = row.purchase_org || ''
  form.fund_source = row.fund_source || '国家预算资金'
  form.using_org = row.using_org || '内部'
  form.winning_bidder = row.winning_bidder || ''
  form.signed_at = row.signed_at || row.purchase_date || ''
  const items = normalizeContractItems(row)
  form.device_items = items.length
    ? items.map(
        (i): FormDeviceItem => ({
          _uid: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
          device_name: i.device_name,
          device_model_name: i.device_model_name,
          manufacturer_name: i.manufacturer_name || '',
          item_kind: normalizeItemKind(i.item_kind),
          quantity: Number(i.quantity || 0),
          quantity_unit: normalizeQuantityUnit(i.quantity_unit),
          unit_price: i.unit_price ?? null,
          response_quote: i.response_quote ?? null,
          price_unit: normalizePriceUnit(i.price_unit || 'yuan'),
        }),
      )
    : [emptyItem()]
  form.contract_total = row.contract_total ?? row.total_amount ?? null
  form.price_unit = normalizePriceUnit(row.price_unit || 'yuan')
  form.purchase_date = row.purchase_date || row.signed_at || ''
  form.description = row.description || ''
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!form.contract_no.trim()) {
    ElMessage.warning('请填写采购合同编号')
    return
  }
  const deviceItems: DeviceContractItem[] = []
  for (const row of form.device_items) {
    const name = row.device_name.trim()
    const model = row.device_model_name.trim()
    const mfg = (row.manufacturer_name || '').trim()
    const qty = Number(row.quantity || 0)
    const price = row.unit_price
    if (!name && !model && !mfg && !qty && (price === null || price === undefined)) continue
    if (!name || !model) {
      ElMessage.warning('每条明细需同时填写名称和型号')
      return
    }
    deviceItems.push({
      device_name: name,
      device_model_name: model,
      manufacturer_name: mfg || null,
      item_kind: normalizeItemKind(row.item_kind),
      quantity: qty,
      quantity_unit: normalizeQuantityUnit(row.quantity_unit),
      unit_price: price ?? null,
      response_quote: row.response_quote ?? null,
      price_unit: normalizePriceUnit(row.price_unit),
    })
  }
  if (!deviceItems.length) {
    ElMessage.warning('请至少添加一条设备名称与产品型号')
    return
  }
  saving.value = true
  try {
    const signed = form.signed_at || form.purchase_date || null
    const payload = {
      contract_no: form.contract_no.trim(),
      project_no: form.project_no.trim() || null,
      device_items: deviceItems,
      contract_total: form.contract_total,
      price_unit: form.price_unit,
      purchase_date: signed,
      signed_at: signed,
      project_budget: form.project_budget,
      purchase_org: form.purchase_org.trim() || null,
      fund_source: form.fund_source || null,
      using_org: form.using_org || null,
      winning_bidder: form.winning_bidder.trim() || null,
      description: form.description.trim() || null,
    }
    if (editingId.value) {
      await updateDeviceContract(editingId.value, payload)
      ElMessage.success('合同信息已更新')
    } else {
      await createDeviceContract(payload)
      ElMessage.success('合同信息已创建')
    }
    dialogVisible.value = false
    try {
      await Promise.all([loadData(), loadSummary()])
    } catch (error: unknown) {
      ElMessage.warning(extractErrorMessage(error, '合同已保存，但刷新列表失败'))
    }
    // 合同明细变更后：同步资产详细参数 + 产品型号档案
    try {
      const [syncResult] = await Promise.all([
        syncParamProfilesFromContracts(),
        syncContractModels(),
      ])
      if (syncResult.created > 0 || syncResult.updated > 0) {
        ElMessage.success(
          `已同步资产参数：新建 ${syncResult.created}，对齐 ${syncResult.updated}`,
        )
      }
    } catch {
      /* 无权限或参数模块异常时不阻断合同保存 */
    }
  } catch (error: unknown) {
    ElMessage.error(extractErrorMessage(error, '保存失败'))
  } finally {
    saving.value = false
  }
}

async function handleArchive(row: DeviceContract) {
  const archived = !!row.archived_at
  await ElMessageBox.confirm(
    archived
      ? `确定取消归档合同「${row.contract_no}」吗？`
      : `确定归档合同「${row.contract_no}」吗？归档后仍可在台账中查看。`,
    archived ? '取消归档' : '归档合同',
    { type: 'warning' },
  )
  await updateDeviceContract(row.id, { archived: !archived })
  ElMessage.success(archived ? '已取消归档' : '合同已归档')
  await loadData()
}

async function refreshAll() {
  await Promise.all([loadData(), loadSummary()])
}

onMounted(() => {
  void Promise.all([loadData(), loadSummary()])
})
</script>

<template>
  <div class="page">
    <header class="page-head">
      <div>
        <h2>合同台账</h2>
        <p>采购合同台账管理</p>
      </div>
      <div class="head-actions">
        <el-button
          size="small"
          :loading="summaryLoading || loading"
          @click="refreshAll"
        >
          刷新
        </el-button>
        <el-button v-if="canCreate" type="primary" size="small" @click="openCreate">
          新建合同
        </el-button>
      </div>
    </header>

    <section class="kpi-strip">
      <div class="kpi">
        <span class="kpi-label">合同数</span>
        <strong>{{ overview.contractCount }}</strong>
      </div>
      <div class="kpi">
        <span class="kpi-label">采购品类</span>
        <strong>{{ overview.skuCount }}</strong>
        <em>{{ overview.hwSku }} 硬 / {{ overview.swSku }} 软</em>
      </div>
      <div class="kpi kpi-hw">
        <span class="kpi-label">硬件数量</span>
        <strong>{{ overview.hwQty }}</strong>
        <em>{{ formatMoneyFromYuan(overview.hwAmount) }}</em>
      </div>
      <div class="kpi kpi-sw">
        <span class="kpi-label">软件数量</span>
        <strong>{{ overview.swQty }}</strong>
        <em>{{ formatMoneyFromYuan(overview.swAmount) }}</em>
      </div>
      <div class="kpi">
        <span class="kpi-label">采购总额</span>
        <strong class="kpi-money">{{ formatMoneyFromYuan(overview.totalAmount) }}</strong>
      </div>
      <div class="kpi">
        <span class="kpi-label">已关联 / 剩余</span>
        <strong>{{ overview.linked }} / {{ overview.remaining }}</strong>
      </div>
    </section>

    <div class="toolbar compact">
      <el-input
        v-model="keyword"
        placeholder="搜索合同 / 项目 / 设备名称 / 产品型号 / 产品厂商"
        clearable
        size="small"
        style="width: 260px"
        @keyup.enter="loadData"
        @clear="loadData"
      />
      <el-button size="small" @click="loadData">搜索</el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="tableData"
      stripe
      size="small"
      class="contract-table"
    >
      <el-table-column type="selection" width="36" />
      <el-table-column
        type="index"
        label="序号"
        width="56"
        align="center"
        :index="(i: number) => (pagination.page - 1) * pagination.page_size + i + 1"
      />
      <el-table-column prop="contract_no" label="合同编号" min-width="140" show-overflow-tooltip />
      <el-table-column prop="project_no" label="项目编号" min-width="120" show-overflow-tooltip>
        <template #default="{ row }">{{ row.project_no || '—' }}</template>
      </el-table-column>
      <el-table-column label="采购单位" min-width="120" show-overflow-tooltip>
        <template #default="{ row }">{{ row.purchase_org || '—' }}</template>
      </el-table-column>
      <el-table-column label="资金来源" min-width="120" show-overflow-tooltip>
        <template #default="{ row }">{{ row.fund_source || '—' }}</template>
      </el-table-column>
      <el-table-column label="使用单位" min-width="100" show-overflow-tooltip>
        <template #default="{ row }">{{ row.using_org || '—' }}</template>
      </el-table-column>
      <el-table-column label="硬件数量" width="96" align="center">
        <template #default="{ row }">{{ contractHwQty(row) }}</template>
      </el-table-column>
      <el-table-column label="软件数量" width="96" align="center">
        <template #default="{ row }">{{ contractSwQty(row) }}</template>
      </el-table-column>
      <el-table-column label="合同总价" min-width="130" align="right">
        <template #default="{ row }">
          {{
            formatMoney(
              row.contract_total ?? row.total_amount,
              normalizePriceUnit(row.price_unit || 'yuan'),
            )
          }}
        </template>
      </el-table-column>
      <el-table-column label="采购时间" min-width="120" align="center">
        <template #default="{ row }">{{ row.purchase_date || row.signed_at || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right" align="center">
        <template #default="{ row }">
          <el-dropdown trigger="click">
            <el-button type="primary" link>操作</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="openDetail(row)">查看合同明细</el-dropdown-item>
                <el-dropdown-item v-if="canUpdate" @click="openEdit(row)">编辑合同项</el-dropdown-item>
                <el-dropdown-item v-if="canUpdate" @click="handleArchive(row)">
                  {{ row.archived_at ? '取消归档' : '归档合同' }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :total="pagination.total"
        layout="total, prev, pager, next"
        small
        @current-change="loadData"
      />
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑合同' : '新建合同'"
      width="1180px"
      destroy-on-close
      class="contract-dialog"
    >
      <el-form label-width="96px" size="small" class="contract-sheet-form" @submit.prevent="handleSubmit">
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="合同编号" required>
              <el-input v-model="form.contract_no" maxlength="100" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="项目编号">
              <el-input v-model="form.project_no" maxlength="100" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="项目预算">
              <el-input-number
                v-model="form.project_budget"
                :min="0"
                :precision="2"
                :step="0.01"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="采购单位">
              <el-input v-model="form.purchase_org" maxlength="200" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="资金来源">
              <el-select v-model="form.fund_source" style="width: 100%" filterable allow-create>
                <el-option v-for="o in FUND_SOURCE_OPTIONS" :key="o" :label="o" :value="o" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="使用单位">
              <el-select v-model="form.using_org" style="width: 100%">
                <el-option v-for="o in USING_ORG_OPTIONS" :key="o" :label="o" :value="o" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="中标单位">
              <el-input v-model="form.winning_bidder" maxlength="200" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="合同金额">
              <div class="price-row">
                <el-input-number
                  v-model="form.contract_total"
                  :min="0"
                  :precision="2"
                  :step="form.price_unit === 'wan' ? 0.01 : 100"
                  style="flex: 1"
                />
                <el-select
                  v-model="form.price_unit"
                  style="width: 88px"
                  @change="onContractPriceUnitChange"
                >
                  <el-option
                    v-for="opt in PRICE_UNIT_OPTIONS"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="签署时间">
              <el-date-picker
                v-model="form.signed_at"
                type="date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <div class="items-section-head">
          <span class="items-section-title">采购明细</span>
          <div class="items-toolbar">
            <el-button link type="primary" @click="handleDownloadItemsTemplate">下载模板</el-button>
            <el-button link type="primary" :loading="itemsImporting" @click="triggerItemsImport">
              导入模板
            </el-button>
            <el-button link type="primary" @click="addDeviceItem('hardware')">+硬件</el-button>
            <el-button link type="primary" @click="addDeviceItem('software')">+软件</el-button>
            <input
              ref="itemsImportInput"
              type="file"
              accept=".xlsx,.xls"
              style="display: none"
              @change="handleImportItemsFile"
            />
          </div>
        </div>

        <div class="sheet-item-rows">
          <div
            v-for="(item, idx) in form.device_items"
            :key="item._uid"
            class="sheet-item-row"
            :class="normalizeItemKind(item.item_kind)"
          >
            <label>设备名称</label>
            <el-input v-model="item.device_name" maxlength="100" />
            <label>产品厂商</label>
            <el-input v-model="item.manufacturer_name" maxlength="100" />
            <label>产品型号</label>
            <el-input v-model="item.device_model_name" maxlength="100" />
            <label>数量</label>
            <div class="qty-cell">
              <el-input-number
                v-model="item.quantity"
                :min="0"
                :max="100000"
                controls-position="right"
              />
              <el-select v-model="item.quantity_unit" style="width: 72px">
                <el-option
                  v-for="unit in QUANTITY_UNIT_OPTIONS"
                  :key="unit"
                  :label="unit"
                  :value="unit"
                />
              </el-select>
            </div>
            <label>货物单价</label>
            <el-input-number
              v-model="item.unit_price"
              :min="0"
              :precision="2"
              :step="0.01"
              controls-position="right"
            />
            <label>响应报价</label>
            <el-input-number
              v-model="item.response_quote"
              :min="0"
              :precision="2"
              :step="0.01"
              controls-position="right"
            />
            <el-radio-group
              :model-value="normalizeItemKind(item.item_kind)"
              size="small"
              class="kind-toggle"
              @update:model-value="setItemKind(item, $event as ContractItemKind)"
            >
              <el-radio-button value="hardware">硬</el-radio-button>
              <el-radio-button value="software">软</el-radio-button>
            </el-radio-group>
            <el-button link type="danger" @click="removeDeviceItem(idx)">删</el-button>
          </div>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="detailVisible"
      :title="`采购清单 · ${detailContract?.contract_no || ''}`"
      width="900px"
      destroy-on-close
    >
      <div class="detail-meta">
        <span>项目：{{ detailContract?.project_no || '—' }}</span>
        <span>采购日：{{ detailContract?.purchase_date || '—' }}</span>
        <span>数量：{{ detailContract?.quantity ?? 0 }}</span>
        <span>
          总价：{{
            formatMoney(
              detailContract?.contract_total ?? detailContract?.total_amount,
              detailPriceUnit,
            )
          }}
        </span>
        <span class="kind-badge hw sm">硬 {{ detailHwItems.length }}</span>
        <span class="kind-badge sw sm">软 {{ detailSwItems.length }}</span>
      </div>

      <div v-if="detailHwItems.length" class="detail-block">
        <div class="detail-block-title"><span class="kind-badge hw">硬件</span></div>
        <el-table :data="detailHwItems" stripe size="small" max-height="240">
          <el-table-column type="index" label="#" width="44" />
          <el-table-column prop="device_name" label="设备名称" min-width="110" />
          <el-table-column prop="device_model_name" label="产品型号" min-width="110" />
          <el-table-column label="产品厂商" min-width="90">
            <template #default="{ row }">{{ row.manufacturer_name || '—' }}</template>
          </el-table-column>
          <el-table-column label="数量" width="90">
            <template #default="{ row }">
              {{ row.quantity ?? 0 }}{{ normalizeQuantityUnit(row.quantity_unit) }}
            </template>
          </el-table-column>
          <el-table-column label="单价" width="110">
            <template #default="{ row }">{{ formatMoney(row.unit_price, itemPriceUnit(row)) }}</template>
          </el-table-column>
          <el-table-column label="小计" width="110">
            <template #default="{ row }">{{ formatMoney(itemLineAmount(row), itemPriceUnit(row)) }}</template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="detailSwItems.length" class="detail-block">
        <div class="detail-block-title"><span class="kind-badge sw">软件</span></div>
        <el-table :data="detailSwItems" stripe size="small" max-height="240">
          <el-table-column type="index" label="#" width="44" />
          <el-table-column prop="device_name" label="设备名称" min-width="110" />
          <el-table-column prop="device_model_name" label="产品型号" min-width="110" />
          <el-table-column label="产品厂商" min-width="90">
            <template #default="{ row }">{{ row.manufacturer_name || '—' }}</template>
          </el-table-column>
          <el-table-column label="数量" width="90">
            <template #default="{ row }">
              {{ row.quantity ?? 0 }}{{ normalizeQuantityUnit(row.quantity_unit) }}
            </template>
          </el-table-column>
          <el-table-column label="单价" width="110">
            <template #default="{ row }">{{ formatMoney(row.unit_price, itemPriceUnit(row)) }}</template>
          </el-table-column>
          <el-table-column label="小计" width="110">
            <template #default="{ row }">{{ formatMoney(itemLineAmount(row), itemPriceUnit(row)) }}</template>
          </el-table-column>
        </el-table>
      </div>

      <el-empty v-if="!detailItems.length" description="暂无采购明细" :image-size="64" />

      <template #footer>
        <el-button type="primary" @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 8px;
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
  letter-spacing: 0.02em;
}

.page-head p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #6b7c8f;
}

.head-actions {
  display: flex;
  gap: 8px;
}

.kpi-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8px;
}

.kpi {
  background: #f7f9fc;
  border: 1px solid #e6edf5;
  border-radius: 6px;
  padding: 8px 10px;
  min-height: 58px;
}

.kpi-hw {
  border-color: #cfe0f5;
  background: linear-gradient(180deg, #f3f8ff 0%, #f7f9fc 100%);
}

.kpi-sw {
  border-color: #ddd6fe;
  background: linear-gradient(180deg, #f8f5ff 0%, #f7f9fc 100%);
}

.kpi-label {
  display: block;
  font-size: 11px;
  color: #7a8b9c;
  margin-bottom: 4px;
}

.kpi strong {
  display: block;
  font-size: 17px;
  line-height: 1.2;
  color: #1f2a37;
  font-variant-numeric: tabular-nums;
}

.kpi-money {
  font-size: 13px !important;
}

.kpi em {
  display: block;
  margin-top: 2px;
  font-style: normal;
  font-size: 11px;
  color: #6b7c8f;
}

.toolbar.compact {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.contract-table {
  width: 100%;
}

.contract-table :deep(.el-table__header .cell),
.contract-table :deep(.el-table__body .cell) {
  padding: 10px 14px;
  line-height: 1.4;
}

.contract-table :deep(.el-table__header th) {
  background: #f7f9fc;
  color: #4b5968;
  font-weight: 600;
}

.kind-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.kind-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.kind-badge.hw {
  color: #1d4ed8;
  background: #dbeafe;
}

.kind-badge.sw {
  color: #6d28d9;
  background: #ede9fe;
}

.kind-badge.sm {
  font-size: 11px;
  padding: 1px 6px;
}

.muted {
  color: #9aa8b6;
  font-size: 12px;
}

.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.price-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.items-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 4px 0 10px;
}
.items-section-title {
  font-weight: 700;
  color: #1f2937;
}
.sheet-item-rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 360px;
  overflow: auto;
  padding: 8px;
  background: #d7e4f2;
  border: 1px solid #7a8fa8;
}
.sheet-item-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 8px;
  background: #eef4fb;
  border: 1px solid #8aa0b8;
}
.sheet-item-row label {
  font-size: 12px;
  color: #1f2937;
  white-space: nowrap;
}
.sheet-item-row :deep(.el-input),
.sheet-item-row :deep(.el-input-number) {
  width: 120px;
}
.sheet-item-row .qty-cell {
  display: flex;
  align-items: center;
  gap: 4px;
}
.sheet-item-row .qty-cell :deep(.el-input-number) {
  width: 90px;
}
.sheet-item-row .kind-toggle {
  margin-left: 4px;
}
.sheet-item-row.hardware {
  border-left: 3px solid #3b82f6;
}
.sheet-item-row.software {
  border-left: 3px solid #10b981;
}
.contract-dialog :deep(.el-dialog__body) {
  background: #c8d8ea;
}

.items-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 4px;
}

.multi-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}

.pair-header,
.pair-row {
  display: grid;
  grid-template-columns: 92px 1fr 1fr 0.9fr 0.72fr 0.58fr 0.78fr 0.68fr 44px;
  gap: 6px;
  align-items: center;
}

.pair-header {
  color: #909399;
  font-size: 12px;
}

.pair-row.hardware {
  background: rgba(219, 234, 254, 0.28);
  border-radius: 4px;
  padding: 2px;
}

.pair-row.software {
  background: rgba(237, 233, 254, 0.4);
  border-radius: 4px;
  padding: 2px;
}

.pair-number,
.pair-qty-unit,
.pair-unit,
.pair-kind {
  width: 100%;
}

.pair-kind :deep(.el-radio-button__inner) {
  padding: 5px 8px;
}

.pair-foot {
  display: flex;
  justify-content: flex-end;
}

.pair-hint {
  color: #909399;
  font-size: 12px;
}

.pair-action {
  width: 44px;
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  align-items: center;
  margin-bottom: 12px;
  color: #606266;
  font-size: 13px;
}

.detail-block {
  margin-bottom: 12px;
}

.detail-block-title {
  margin-bottom: 6px;
}

@media (max-width: 1200px) {
  .kpi-strip {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .kpi-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .page-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
