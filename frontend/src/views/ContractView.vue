<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  bindContractDevices,
  calcItemsAmount,
  createDeviceContract,
  deleteDeviceContract,
  downloadContractItemsTemplate,
  formatContractItems,
  getContractSummary,
  importContractItems,
  listDeviceContracts,
  normalizeContractItems,
  normalizeQuantityUnit,
  QUANTITY_UNIT_OPTIONS,
  unbindContractDevices,
  updateDeviceContract,
  type DeviceContract,
  type DeviceContractItem,
  type DeviceContractSummary,
} from '@/api/contract'
import { listDevices, type Device } from '@/api/device'
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
const emptyItem = (): DeviceContractItem => ({
  device_name: '',
  device_model_name: '',
  manufacturer_name: '',
  quantity: 0,
  quantity_unit: '台',
  unit_price: null,
  price_unit: 'yuan',
})

const form = reactive({
  contract_no: '',
  project_no: '',
  device_items: [emptyItem()] as DeviceContractItem[],
  contract_total: null as number | null,
  price_unit: 'yuan' as 'yuan' | 'wan',
  purchase_date: '' as string,
  description: '',
})

const itemsAmountHint = computed(() => calcItemsAmount(form.device_items))
const itemsQuantityHint = computed(() =>
  form.device_items.reduce((sum, item) => sum + Number(item.quantity || 0), 0),
)

const bindVisible = ref(false)
const bindContract = ref<DeviceContract | null>(null)
const bindLoading = ref(false)
const bindDevices = ref<Device[]>([])
const selectedBindIds = ref<string[]>([])
const bindTableRef = ref<{
  clearSelection?: () => void
  toggleRowSelection?: (row: Device, selected?: boolean) => void
} | null>(null)

const detailVisible = ref(false)
const detailContract = ref<DeviceContract | null>(null)
const detailItems = computed(() =>
  detailContract.value ? normalizeContractItems(detailContract.value) : [],
)
const detailPriceUnit = computed(() => detailContract.value?.price_unit || 'yuan')

type PriceUnit = 'yuan' | 'wan'

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
    form.price_unit === 'wan'
      ? convertPriceUnitAmount(yuanTotal, 'yuan', 'wan')
      : yuanTotal
}

function addDeviceItem() {
  form.device_items.push(emptyItem())
}

function removeDeviceItem(index: number) {
  if (form.device_items.length <= 1) {
    form.device_items[0] = emptyItem()
    return
  }
  form.device_items.splice(index, 1)
}

function mapImportedItem(item: DeviceContractItem): DeviceContractItem {
  return {
    device_name: item.device_name,
    device_model_name: item.device_model_name,
    manufacturer_name: item.manufacturer_name || '',
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
      if (result.errors.length) {
        ElMessage.warning(result.errors.slice(0, 3).join('; '))
      }
      return
    }
    applyImportedItems(result.items)
    ElMessage.success(`已导入 ${result.imported} 条设备明细`)
    if (result.errors.length) {
      ElMessage.warning(result.errors.slice(0, 3).join('; '))
    }
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

function openEdit(row: DeviceContract) {
  editingId.value = row.id
  form.contract_no = row.contract_no
  form.project_no = row.project_no || ''
  const items = normalizeContractItems(row)
  form.device_items = items.length
    ? items.map((i) => ({
        device_name: i.device_name,
        device_model_name: i.device_model_name,
        manufacturer_name: i.manufacturer_name || '',
        quantity: Number(i.quantity || 0),
        quantity_unit: normalizeQuantityUnit(i.quantity_unit),
        unit_price: i.unit_price ?? null,
        price_unit: i.price_unit === 'wan' ? 'wan' : 'yuan',
      }))
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
      ElMessage.warning('每条设备明细需同时填写名称和型号')
      return
    }
    deviceItems.push({
      device_name: name,
      device_model_name: model,
      manufacturer_name: mfg || null,
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
    `确定删除合同「${row.contract_no}」吗？关联设备将解除绑定。`,
    '确认删除',
    { type: 'warning' },
  )
  await deleteDeviceContract(row.id)
  ElMessage.success('已删除')
  await Promise.all([loadData(), loadSummary()])
}

async function openBind(row: DeviceContract) {
  bindContract.value = row
  selectedBindIds.value = []
  bindVisible.value = true
  bindLoading.value = true
  try {
    const pages: Device[] = []
    let page = 1
    let total = 0
    do {
      const data = await listDevices({ page, page_size: 200 })
      pages.push(...(data.items || []))
      total = data.pagination?.total ?? 0
      page += 1
    } while ((page - 1) * 200 < total && page <= 10)
    bindDevices.value = pages
    await nextTick()
    bindTableRef.value?.clearSelection?.()
    for (const device of pages) {
      if (device.contract_id === row.id) {
        bindTableRef.value?.toggleRowSelection?.(device, true)
      }
    }
  } catch {
    bindDevices.value = []
    ElMessage.error('加载设备失败')
  } finally {
    bindLoading.value = false
  }
}

function onBindSelectionChange(rows: Device[]) {
  selectedBindIds.value = rows.map((r) => r.id)
}

async function submitBind() {
  if (!bindContract.value) return
  bindLoading.value = true
  try {
    const currently = bindDevices.value
      .filter((d) => d.contract_id === bindContract.value!.id)
      .map((d) => d.id)
    const toBind = selectedBindIds.value.filter((id) => !currently.includes(id))
    const toUnbind = currently.filter((id) => !selectedBindIds.value.includes(id))
    if (toBind.length) {
      const result = await bindContractDevices(bindContract.value.id, toBind)
      if (result.errors.length) ElMessage.warning(result.errors.slice(0, 3).join('; '))
    }
    if (toUnbind.length) {
      await unbindContractDevices(bindContract.value.id, toUnbind)
    }
    ElMessage.success('设备关联已更新')
    bindVisible.value = false
    await Promise.all([loadData(), loadSummary()])
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '关联失败')
  } finally {
    bindLoading.value = false
  }
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

onMounted(() => {
  void Promise.all([loadData(), loadSummary()])
})
</script>

<template>
  <div class="page">
    <el-card shadow="never" class="summary-card">
      <template #header>
        <div class="card-header">
          <span>厂商型号采购汇总</span>
          <el-button :loading="summaryLoading" @click="loadSummary">刷新</el-button>
        </div>
      </template>
      <el-table v-loading="summaryLoading" :data="summaryData" stripe size="small" max-height="260">
        <el-table-column prop="device_name" label="设备名称" min-width="120">
          <template #default="{ row }">{{ row.device_name || '—' }}</template>
        </el-table-column>
        <el-table-column prop="device_model_name" label="设备型号" min-width="140" />
        <el-table-column prop="manufacturer_name" label="厂商" min-width="120">
          <template #default="{ row }">{{ row.manufacturer_name || '—' }}</template>
        </el-table-column>
        <el-table-column prop="purchase_quantity" label="采购数量" width="100" />
        <el-table-column prop="linked_count" label="已关联设备" width="110" />
        <el-table-column prop="contract_count" label="合同数" width="90" />
      </el-table>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>合同信息</span>
          <div class="actions">
            <el-input
              v-model="keyword"
              placeholder="搜索合同/项目/设备名称/型号/厂商"
              clearable
              style="width: 260px"
              @keyup.enter="loadData"
              @clear="loadData"
            />
            <el-button @click="loadData">搜索</el-button>
            <el-button v-if="canCreate" type="primary" @click="openCreate">新建合同</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" stripe>
        <el-table-column prop="contract_no" label="采购合同编号" min-width="140" />
        <el-table-column prop="project_no" label="项目编号" min-width="120">
          <template #default="{ row }">{{ row.project_no || '—' }}</template>
        </el-table-column>
        <el-table-column prop="quantity" label="采购数量" width="100" />
        <el-table-column prop="linked_count" label="已关联" width="90" />
        <el-table-column label="合同总价" width="140">
          <template #default="{ row }">
            {{ formatMoney(row.contract_total ?? row.total_amount, row.price_unit) }}
          </template>
        </el-table-column>
        <el-table-column prop="purchase_date" label="采购时间" width="120">
          <template #default="{ row }">{{ row.purchase_date || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openDetail(row)">查看明细</el-button>
            <el-button v-if="canUpdate" type="primary" link @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canUpdate" type="primary" link @click="openBind(row)">关联设备</el-button>
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
          @current-change="loadData"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑合同信息' : '新建合同信息'"
      width="1040px"
      destroy-on-close
    >
      <el-form label-width="110px" @submit.prevent="handleSubmit">
        <el-form-item label="采购合同编号" required>
          <el-input v-model="form.contract_no" maxlength="100" placeholder="请输入合同编号" />
        </el-form-item>
        <el-form-item label="项目编号">
          <el-input v-model="form.project_no" maxlength="100" placeholder="请输入项目编号" />
        </el-form-item>
        <el-form-item label="设备明细" required>
          <div class="multi-field">
            <div class="items-toolbar">
              <el-button @click="handleDownloadItemsTemplate">下载明细模板</el-button>
              <el-button :loading="itemsImporting" @click="triggerItemsImport">导入明细</el-button>
              <input
                ref="itemsImportInput"
                type="file"
                accept=".xlsx,.xls"
                style="display: none"
                @change="handleImportItemsFile"
              />
            </div>
            <div class="pair-header">
              <span>设备名称</span>
              <span>设备型号</span>
              <span>厂商</span>
              <span>采购数量</span>
              <span>数量单位</span>
              <span>单价</span>
              <span>金额单位</span>
              <span class="pair-action" />
            </div>
            <div v-for="(item, idx) in form.device_items" :key="`item-${idx}`" class="multi-row pair-row">
              <el-input
                v-model="item.device_name"
                maxlength="100"
                placeholder="设备名称"
              />
              <el-input
                v-model="item.device_model_name"
                maxlength="100"
                placeholder="对应型号"
              />
              <el-input
                v-model="item.manufacturer_name"
                maxlength="100"
                placeholder="对应厂商"
              />
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
              <el-button @click="removeDeviceItem(idx)">删除</el-button>
            </div>
            <div class="pair-foot">
              <el-button type="primary" link @click="addDeviceItem">
                + 添加设备（名称+型号+厂商+数量+单价）
              </el-button>
              <span class="pair-hint">
                明细合计数量 {{ itemsQuantityHint }}，金额
                {{
                  itemsAmountHint === null
                    ? '—'
                    : `${itemsAmountHint.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} 元`
                }}
              </span>
            </div>
          </div>
        </el-form-item>
        <el-row :gutter="16" class="contract-meta-row">
          <el-col :span="15">
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
                  style="width: 100px"
                  @change="onContractPriceUnitChange"
                >
                  <el-option label="元" value="yuan" />
                  <el-option label="万元" value="wan" />
                </el-select>
                <el-button
                  :disabled="itemsAmountHint === null"
                  @click="fillContractTotalFromItems"
                >
                  按明细合计
                </el-button>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="9">
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
        <el-form-item label="备注">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="detailVisible"
      :title="`设备采购清单 · ${detailContract?.contract_no || ''}`"
      width="820px"
      destroy-on-close
    >
      <div class="detail-meta">
        <span>项目编号：{{ detailContract?.project_no || '—' }}</span>
        <span>采购数量合计：{{ detailContract?.quantity ?? 0 }}</span>
        <span>
          合同总价：{{
            formatMoney(
              detailContract?.contract_total ?? detailContract?.total_amount,
              detailPriceUnit,
            )
          }}
        </span>
      </div>
      <el-table :data="detailItems" stripe max-height="420" empty-text="暂无设备采购明细">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="device_name" label="设备名称" min-width="120" />
        <el-table-column prop="device_model_name" label="设备型号" min-width="120" />
        <el-table-column label="厂商" min-width="110">
          <template #default="{ row }">{{ row.manufacturer_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="采购数量" width="110">
          <template #default="{ row }">
            {{ row.quantity ?? 0 }}{{ normalizeQuantityUnit(row.quantity_unit) }}
          </template>
        </el-table-column>
        <el-table-column label="单价" width="130">
          <template #default="{ row }">
            {{ formatMoney(row.unit_price, itemPriceUnit(row)) }}
          </template>
        </el-table-column>
        <el-table-column label="小计" width="130">
          <template #default="{ row }">
            {{ formatMoney(itemLineAmount(row), itemPriceUnit(row)) }}
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button type="primary" @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="bindVisible"
      :title="`关联设备 · ${bindContract?.contract_no || ''}`"
      width="720px"
      destroy-on-close
    >
      <p class="bind-hint">
        合同设备：{{ bindContract ? formatContractItems(bindContract) : '—' }}。勾选设备管理中的设备后保存即可关联。
      </p>
      <el-table
        ref="bindTableRef"
        v-loading="bindLoading"
        :data="bindDevices"
        row-key="id"
        stripe
        max-height="420"
        @selection-change="onBindSelectionChange"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column label="名称" min-width="120">
          <template #default="{ row }">{{ row.name || row.hostname }}</template>
        </el-table-column>
        <el-table-column prop="device_model_name" label="型号" min-width="110" />
        <el-table-column prop="serial_number" label="序列号" min-width="120" />
        <el-table-column label="当前合同" min-width="120">
          <template #default="{ row }">{{ row.contract_no || '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            {{ row.contract_id === bindContract?.id ? '已关联' : '未关联' }}
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="bindVisible = false">取消</el-button>
        <el-button type="primary" :loading="bindLoading" @click="submitBind">保存关联</el-button>
      </template>
    </el-dialog>
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
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.bind-hint {
  margin: 0 0 12px;
  color: #606266;
  font-size: 13px;
  line-height: 1.5;
}

.contract-meta-row {
  width: 100%;
}

.contract-meta-row :deep(.el-form-item) {
  margin-bottom: 18px;
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
  margin-bottom: 4px;
}

.multi-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.multi-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.pair-header {
  display: grid;
  grid-template-columns: 1.05fr 1.05fr 0.95fr 0.82fr 0.62fr 0.82fr 0.68fr 64px;
  gap: 8px;
  color: #909399;
  font-size: 12px;
}

.pair-row {
  display: grid;
  grid-template-columns: 1.05fr 1.05fr 0.95fr 0.82fr 0.62fr 0.82fr 0.68fr 64px;
  gap: 8px;
  align-items: center;
}

.pair-number {
  width: 100%;
}

.pair-qty-unit,
.pair-unit {
  width: 100%;
}

.pair-foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.pair-hint {
  color: #909399;
  font-size: 12px;
}

.pair-action {
  width: 64px;
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 24px;
  margin-bottom: 12px;
  color: #606266;
  font-size: 13px;
}
</style>
