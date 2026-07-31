<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  calcItemsAmount,
  createDeviceContract,
  deleteDeviceContract,
  downloadContractItemsTemplate,
  getContractSummary,
  importContractItems,
  listDeviceContracts,
  normalizeContractItems,
  normalizeItemKind,
  normalizeQuantityUnit,
  QUANTITY_UNIT_OPTIONS,
  updateDeviceContract,
  type ContractItemKind,
  type DeviceContract,
  type DeviceContractItem,
  type DeviceContractSummary,
} from '@/api/contract'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const canCreate = auth.hasPermission('device:create')
const canUpdate = auth.hasPermission('device:update')
const canDelete = auth.hasPermission('device:delete')

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
  price_unit: 'yuan',
})

type FormDeviceItem = DeviceContractItem & { _uid: string }

const form = reactive({
  contract_no: '',
  project_no: '',
  device_items: [emptyItem()] as FormDeviceItem[],
  contract_total: null as number | null,
  price_unit: 'yuan' as 'yuan' | 'wan',
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
const detailPriceUnit = computed(() => detailContract.value?.price_unit || 'yuan')

type PriceUnit = 'yuan' | 'wan'

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
  form.device_items = [emptyItem()]
  form.contract_total = null
  form.price_unit = 'yuan'
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
    price_unit: item.price_unit === 'wan' ? 'wan' : 'yuan',
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
  detailContract.value = row
  detailVisible.value = true
}

function itemLineAmount(item: DeviceContractItem): number | null {
  const qty = Number(item.quantity || 0)
  const price = item.unit_price
  if (price === null || price === undefined || !qty) return item.line_amount ?? null
  return Math.round(qty * Number(price) * 100) / 100
}

function itemPriceUnit(item: DeviceContractItem): 'yuan' | 'wan' {
  return item.price_unit === 'wan' ? 'wan' : 'yuan'
}

function contractKindSummary(row: DeviceContract) {
  const items = normalizeContractItems(row)
  const hw = items.filter((i) => normalizeItemKind(i.item_kind) === 'hardware').length
  const sw = items.filter((i) => normalizeItemKind(i.item_kind) === 'software').length
  return { hw, sw, total: items.length }
}

function openEdit(row: DeviceContract) {
  editingId.value = row.id
  form.contract_no = row.contract_no
  form.project_no = row.project_no || ''
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
          price_unit: i.price_unit === 'wan' ? 'wan' : 'yuan',
        }),
      )
    : [emptyItem()]
  form.contract_total = row.contract_total ?? row.total_amount ?? null
  form.price_unit = row.price_unit === 'wan' ? 'wan' : 'yuan'
  form.purchase_date = row.purchase_date || ''
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
      price_unit: row.price_unit === 'wan' ? 'wan' : 'yuan',
    })
  }
  if (!deviceItems.length) {
    ElMessage.warning('请至少添加一条设备名称与型号')
    return
  }
  saving.value = true
  try {
    const payload = {
      contract_no: form.contract_no.trim(),
      project_no: form.project_no.trim() || null,
      device_items: deviceItems,
      contract_total: form.contract_total,
      price_unit: form.price_unit,
      purchase_date: form.purchase_date || null,
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
  } catch (error: unknown) {
    ElMessage.error(extractErrorMessage(error, '保存失败'))
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: DeviceContract) {
  await ElMessageBox.confirm(
    `确定删除合同「${row.contract_no}」吗？同步创建且未被设备使用的型号将一并删除。`,
    '确认删除',
    { type: 'warning' },
  )
  await deleteDeviceContract(row.id)
  ElMessage.success('合同已删除')
  await Promise.all([loadData(), loadSummary()])
}

function priceUnitLabel(unit: string | null | undefined) {
  return unit === 'wan' ? '万元' : '元'
}

function formatMoney(value: number | null | undefined, unit?: string | null) {
  if (value === null || value === undefined) return '—'
  const amount = Number(value).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  return `${amount} ${priceUnitLabel(unit)}`
}

function formatYuan(value: number | null | undefined) {
  return formatMoney(value, 'yuan')
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
        <em>{{ formatYuan(overview.hwAmount) }}</em>
      </div>
      <div class="kpi kpi-sw">
        <span class="kpi-label">软件数量</span>
        <strong>{{ overview.swQty }}</strong>
        <em>{{ formatYuan(overview.swAmount) }}</em>
      </div>
      <div class="kpi">
        <span class="kpi-label">采购总额</span>
        <strong class="kpi-money">{{ formatYuan(overview.totalAmount) }}</strong>
      </div>
      <div class="kpi">
        <span class="kpi-label">已关联 / 剩余</span>
        <strong>{{ overview.linked }} / {{ overview.remaining }}</strong>
      </div>
    </section>

    <div class="toolbar compact">
      <el-input
        v-model="keyword"
        placeholder="搜索合同 / 项目 / 设备 / 型号 / 厂商"
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
      <el-table-column prop="contract_no" label="合同编号" min-width="150" show-overflow-tooltip />
      <el-table-column prop="project_no" label="项目编号" min-width="150" show-overflow-tooltip>
        <template #default="{ row }">{{ row.project_no || '—' }}</template>
      </el-table-column>
      <el-table-column label="软硬构成" min-width="140">
        <template #default="{ row }">
          <div class="kind-tags">
            <span v-if="contractKindSummary(row).hw" class="kind-badge hw sm">
              硬 {{ contractKindSummary(row).hw }}
            </span>
            <span v-if="contractKindSummary(row).sw" class="kind-badge sw sm">
              软 {{ contractKindSummary(row).sw }}
            </span>
            <span v-if="!contractKindSummary(row).total" class="muted">—</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="quantity" label="数量" min-width="100" align="center" />
      <el-table-column label="合同总价" min-width="150" align="right">
        <template #default="{ row }">
          {{ formatMoney(row.contract_total ?? row.total_amount, row.price_unit) }}
        </template>
      </el-table-column>
      <el-table-column prop="purchase_date" label="采购时间" min-width="130" align="center">
        <template #default="{ row }">{{ row.purchase_date || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="168" fixed="right" align="center">
        <template #default="{ row }">
          <el-button type="primary" link @click="openDetail(row)">明细</el-button>
          <el-button v-if="canUpdate" type="primary" link @click="openEdit(row)">编辑</el-button>
          <el-button v-if="canDelete" type="danger" link @click="handleDelete(row)">删除</el-button>
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
      :title="editingId ? '编辑合同信息' : '新建合同信息'"
      width="1120px"
      destroy-on-close
      class="contract-dialog"
    >
      <el-form label-width="96px" size="small" @submit.prevent="handleSubmit">
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="合同编号" required>
              <el-input v-model="form.contract_no" maxlength="100" placeholder="采购合同编号" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="项目编号">
              <el-input v-model="form.project_no" maxlength="100" placeholder="可选" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="采购时间">
              <el-date-picker
                v-model="form.purchase_date"
                type="date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="采购明细" required>
          <div class="multi-field">
            <div class="items-toolbar">
              <el-button size="small" @click="handleDownloadItemsTemplate">下载模板</el-button>
              <el-button size="small" :loading="itemsImporting" @click="triggerItemsImport">导入明细</el-button>
              <el-button size="small" @click="addDeviceItem('hardware')">+ 硬件</el-button>
              <el-button size="small" @click="addDeviceItem('software')">+ 软件</el-button>
              <span class="pair-hint">硬件 {{ formHwCount }} · 软件 {{ formSwCount }}</span>
              <input
                ref="itemsImportInput"
                type="file"
                accept=".xlsx,.xls"
                style="display: none"
                @change="handleImportItemsFile"
              />
            </div>
            <div class="pair-header">
              <span>类别</span>
              <span>名称</span>
              <span>型号</span>
              <span>厂商</span>
              <span>数量</span>
              <span>单位</span>
              <span>单价</span>
              <span>金额单位</span>
              <span class="pair-action" />
            </div>
            <div
              v-for="(item, idx) in form.device_items"
              :key="item._uid"
              class="pair-row"
              :class="normalizeItemKind(item.item_kind)"
            >
              <el-radio-group
                :model-value="normalizeItemKind(item.item_kind)"
                size="small"
                class="pair-kind"
                @update:model-value="(val) => setItemKind(item, val as ContractItemKind)"
              >
                <el-radio-button value="hardware">硬</el-radio-button>
                <el-radio-button value="software">软</el-radio-button>
              </el-radio-group>
              <el-input v-model="item.device_name" maxlength="100" placeholder="名称" />
              <el-input v-model="item.device_model_name" maxlength="100" placeholder="型号" />
              <el-input v-model="item.manufacturer_name" maxlength="100" placeholder="厂商" />
              <el-input-number
                v-model="item.quantity"
                :min="0"
                :max="100000"
                controls-position="right"
                class="pair-number"
              />
              <el-select v-model="item.quantity_unit" class="pair-qty-unit">
                <el-option
                  v-for="unit in QUANTITY_UNIT_OPTIONS"
                  :key="unit"
                  :label="unit"
                  :value="unit"
                />
              </el-select>
              <el-input-number
                v-model="item.unit_price"
                :min="0"
                :precision="2"
                :step="item.price_unit === 'wan' ? 0.01 : 100"
                controls-position="right"
                class="pair-number"
              />
              <el-select
                v-model="item.price_unit"
                class="pair-unit"
                @change="(val: PriceUnit) => onItemPriceUnitChange(item, val)"
              >
                <el-option label="元" value="yuan" />
                <el-option label="万元" value="wan" />
              </el-select>
              <el-button size="small" @click="removeDeviceItem(idx)">删</el-button>
            </div>
            <div class="pair-foot">
              <span class="pair-hint">
                合计数量 {{ itemsQuantityHint }}，明细金额
                {{
                  itemsAmountHint === null
                    ? '—'
                    : `${itemsAmountHint.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} 元`
                }}
              </span>
            </div>
          </div>
        </el-form-item>

        <el-row :gutter="12">
          <el-col :span="14">
            <el-form-item label="合同总价">
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
                  style="width: 90px"
                  @change="onContractPriceUnitChange"
                >
                  <el-option label="元" value="yuan" />
                  <el-option label="万元" value="wan" />
                </el-select>
                <el-button size="small" :disabled="itemsAmountHint === null" @click="fillContractTotalFromItems">
                  按明细
                </el-button>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="10">
            <el-form-item label="备注">
              <el-input v-model="form.description" maxlength="200" placeholder="可选备注" />
            </el-form-item>
          </el-col>
        </el-row>
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
          <el-table-column prop="device_name" label="名称" min-width="110" />
          <el-table-column prop="device_model_name" label="型号" min-width="110" />
          <el-table-column label="厂商" min-width="90">
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
          <el-table-column prop="device_name" label="名称" min-width="110" />
          <el-table-column prop="device_model_name" label="型号/版本" min-width="110" />
          <el-table-column label="厂商" min-width="90">
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
