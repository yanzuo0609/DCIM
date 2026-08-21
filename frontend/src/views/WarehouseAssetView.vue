<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createWarehouseAsset,
  deleteWarehouseAsset,
  getWarehouse,
  listWarehouseAssets,
  updateWarehouseAsset,
  type Warehouse,
  type WarehouseAsset,
  type WarehouseAssetCategory,
  type WarehouseAssetStatus,
  type WarehouseAssetUnit,
  type WarehouseOutboundMode,
} from '@/api/warehouse'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const warehouseId = computed(() => String(route.params.id || ''))
const warehouse = ref<Warehouse | null>(null)
const loading = ref(false)
const tableData = ref<WarehouseAsset[]>([])
const pagination = reactive({ page: 1, page_size: 50, total: 0 })
const keyword = ref('')
const dialogVisible = ref(false)
const editingId = ref<string | null>(null)
const saving = ref(false)

const canCreate = auth.hasPermission('datacenter:create')
const canUpdate = auth.hasPermission('datacenter:update')
const canDelete = auth.hasPermission('datacenter:delete')

const CATEGORY_OPTIONS: { value: WarehouseAssetCategory; label: string }[] = [
  { value: 'complete', label: '整机' },
  { value: 'accessory', label: '配件' },
  { value: 'material', label: '辅材' },
  { value: 'tool', label: '工具' },
  { value: 'other', label: '其他' },
]

const STATUS_OPTIONS: { value: WarehouseAssetStatus; label: string }[] = [
  { value: 'new', label: '全新' },
  { value: 'replace', label: '替换' },
  { value: 'fault', label: '故障' },
  { value: 'scrap', label: '报废' },
]

const UNIT_OPTIONS: { value: WarehouseAssetUnit; label: string }[] = [
  { value: 'piece', label: '个' },
  { value: 'unit', label: '台' },
  { value: 'box', label: '箱' },
  { value: 'set', label: '套' },
  { value: 'other', label: '其他' },
]

const form = reactive({
  name: '',
  quantity: 1,
  unit: 'piece' as WarehouseAssetUnit,
  project: '',
  application: '',
  category: 'other' as WarehouseAssetCategory,
  status: 'new' as WarehouseAssetStatus,
  inbound_at: '' as string,
  outbound_mode: 'undetermined' as WarehouseOutboundMode,
  outbound_at: '' as string,
  owner_name: '',
  owner_contact: '',
  remark: '',
})

function rowIndex(index: number) {
  return (pagination.page - 1) * pagination.page_size + index + 1
}

function categoryLabel(value: string) {
  return CATEGORY_OPTIONS.find((o) => o.value === value)?.label || value || '—'
}

function statusLabel(value: string) {
  return STATUS_OPTIONS.find((o) => o.value === value)?.label || value || '—'
}

function unitLabel(value: string) {
  return UNIT_OPTIONS.find((o) => o.value === value)?.label || value || '个'
}

function quantityDisplay(row: WarehouseAsset) {
  const qty = Math.max(1, Number(row.quantity) || 1)
  return `${qty} ${unitLabel(row.unit || 'piece')}`
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function toLocalInput(value: string | null | undefined) {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function fromLocalInput(value: string) {
  if (!value) return null
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return null
  return d.toISOString()
}

function outboundDisplay(row: WarehouseAsset) {
  if (row.outbound_mode === 'undetermined' || !row.outbound_at) return '未确定'
  return formatDateTime(row.outbound_at)
}

async function loadWarehouse() {
  if (!warehouseId.value) return
  warehouse.value = await getWarehouse(warehouseId.value)
}

async function loadData() {
  if (!warehouseId.value) return
  loading.value = true
  try {
    const data = await listWarehouseAssets(warehouseId.value, {
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

function resetForm() {
  form.name = ''
  form.quantity = 1
  form.unit = 'piece'
  form.project = ''
  form.application = ''
  form.category = 'other'
  form.status = 'new'
  form.inbound_at = toLocalInput(new Date().toISOString())
  form.outbound_mode = 'undetermined'
  form.outbound_at = ''
  form.owner_name = ''
  form.owner_contact = ''
  form.remark = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: WarehouseAsset) {
  editingId.value = row.id
  form.name = row.name
  form.quantity = Math.max(1, Number(row.quantity) || 1)
  form.unit = (row.unit as WarehouseAssetUnit) || 'piece'
  form.project = row.project || ''
  form.application = row.application || ''
  form.category = (row.category as WarehouseAssetCategory) || 'other'
  form.status = (row.status as WarehouseAssetStatus) || 'new'
  form.inbound_at = toLocalInput(row.inbound_at)
  form.outbound_mode = (row.outbound_mode as WarehouseOutboundMode) || 'undetermined'
  form.outbound_at = toLocalInput(row.outbound_at)
  form.owner_name = row.owner_name || ''
  form.owner_contact = row.owner_contact || ''
  form.remark = row.remark || ''
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写资产名称')
    return
  }
  if (!form.quantity || form.quantity < 1) {
    ElMessage.warning('数量至少为 1')
    return
  }
  if (form.outbound_mode === 'fixed' && !form.outbound_at) {
    ElMessage.warning('请选择固定出库时间')
    return
  }
  saving.value = true
  const payload = {
    name: form.name.trim(),
    quantity: Math.max(1, Math.floor(form.quantity)),
    unit: form.unit,
    project: form.project.trim() || null,
    application: form.application.trim() || null,
    category: form.category,
    status: form.status,
    inbound_at: fromLocalInput(form.inbound_at),
    outbound_mode: form.outbound_mode,
    outbound_at: form.outbound_mode === 'fixed' ? fromLocalInput(form.outbound_at) : null,
    owner_name: form.owner_name.trim() || null,
    owner_contact: form.owner_contact.trim() || null,
    remark: form.remark.trim() || null,
  }
  try {
    if (editingId.value) {
      await updateWarehouseAsset(warehouseId.value, editingId.value, payload)
      ElMessage.success('已更新资产记录')
    } else {
      await createWarehouseAsset(warehouseId.value, payload)
      ElMessage.success('已新增资产记录')
    }
    dialogVisible.value = false
    await loadData()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '操作失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: WarehouseAsset) {
  await ElMessageBox.confirm(`确定删除资产「${row.name}」吗？`, '确认删除', { type: 'warning' })
  try {
    await deleteWarehouseAsset(warehouseId.value, row.id)
    ElMessage.success('删除成功')
    await loadData()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '删除失败')
  }
}

function goBack() {
  void router.push('/warehouses')
}

watch(
  () => route.params.id,
  async () => {
    pagination.page = 1
    await loadWarehouse()
    await loadData()
  },
)

onMounted(async () => {
  try {
    await loadWarehouse()
    await loadData()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '加载失败')
    goBack()
  }
})
</script>

<template>
  <div class="page">
    <section class="hero">
      <div class="hero-copy">
        <el-button link type="primary" @click="goBack">← 返回库房列表</el-button>
        <h2>{{ warehouse?.name || '资产出入库清单' }}</h2>
        <p>
          {{ warehouse?.code || '—' }}
          · 所属机房 {{ [warehouse?.building_no, warehouse?.room_no || warehouse?.room_name].filter(Boolean).join('-') || '—' }}
          · 创建库房后已自动生成本清单，可在此编辑与记录资产出入库
        </p>
      </div>
      <div class="hero-actions">
        <el-button v-if="canCreate" type="primary" @click="openCreate">新增资产记录</el-button>
      </div>
    </section>

    <el-card shadow="never" class="list-card">
      <template #header>
        <div class="card-header">
          <span>资产出入库记录清单</span>
          <div class="actions">
            <el-input
              v-model="keyword"
              clearable
              placeholder="搜索名称/项目/应用/负责人"
              style="width: 240px"
              @keyup.enter="loadData"
              @clear="loadData"
            />
            <el-button @click="loadData">搜索</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" stripe row-key="id">
        <el-table-column label="序号" width="64" align="center">
          <template #default="{ $index }">{{ rowIndex($index) }}</template>
        </el-table-column>
        <el-table-column label="资产名称" min-width="140" show-overflow-tooltip prop="name" />
        <el-table-column label="数量" width="100" align="center">
          <template #default="{ row }">{{ quantityDisplay(row) }}</template>
        </el-table-column>
        <el-table-column label="所属项目" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.project || '—' }}</template>
        </el-table-column>
        <el-table-column label="所属应用" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.application || '—' }}</template>
        </el-table-column>
        <el-table-column label="资产分类" width="90" align="center">
          <template #default="{ row }">{{ categoryLabel(row.category) }}</template>
        </el-table-column>
        <el-table-column label="资产状态" width="90" align="center">
          <template #default="{ row }">{{ statusLabel(row.status) }}</template>
        </el-table-column>
        <el-table-column label="入库时间" width="150">
          <template #default="{ row }">{{ formatDateTime(row.inbound_at) }}</template>
        </el-table-column>
        <el-table-column label="出库时间" width="150">
          <template #default="{ row }">{{ outboundDisplay(row) }}</template>
        </el-table-column>
        <el-table-column label="资产负责人" width="110" show-overflow-tooltip>
          <template #default="{ row }">{{ row.owner_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="联系方式" width="130" show-overflow-tooltip>
          <template #default="{ row }">{{ row.owner_contact || '—' }}</template>
        </el-table-column>
        <el-table-column label="备注" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.remark || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canUpdate" type="primary" link @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canDelete" type="danger" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          layout="total, prev, pager, next"
          :total="pagination.total"
          @change="loadData"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑资产记录' : '新增资产记录'"
      width="640px"
      destroy-on-close
    >
      <el-form label-width="110px">
        <el-form-item label="资产名称" required>
          <el-input v-model="form.name" maxlength="200" placeholder="例如：交换机整机" />
        </el-form-item>
        <el-form-item label="数量" required>
          <div class="qty-row">
            <el-input-number v-model="form.quantity" :min="1" :max="999999" :step="1" controls-position="right" />
            <el-select v-model="form.unit" style="width: 120px">
              <el-option
                v-for="opt in UNIT_OPTIONS"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </div>
        </el-form-item>
        <el-form-item label="所属项目">
          <el-input v-model="form.project" maxlength="200" />
        </el-form-item>
        <el-form-item label="所属应用">
          <el-input v-model="form.application" maxlength="200" />
        </el-form-item>
        <el-form-item label="资产分类" required>
          <el-select v-model="form.category" style="width: 100%">
            <el-option
              v-for="opt in CATEGORY_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="资产状态" required>
          <el-select v-model="form.status" style="width: 100%">
            <el-option
              v-for="opt in STATUS_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="入库时间">
          <el-date-picker
            v-model="form.inbound_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm"
            placeholder="选择入库时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="出库时间">
          <div class="outbound-row">
            <el-radio-group v-model="form.outbound_mode">
              <el-radio value="undetermined">未确定</el-radio>
              <el-radio value="fixed">固定时间</el-radio>
            </el-radio-group>
            <el-date-picker
              v-if="form.outbound_mode === 'fixed'"
              v-model="form.outbound_at"
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm"
              placeholder="选择出库时间"
              style="width: 100%; margin-top: 8px"
            />
          </div>
        </el-form-item>
        <el-form-item label="资产负责人">
          <el-input v-model="form.owner_name" maxlength="100" />
        </el-form-item>
        <el-form-item label="联系方式">
          <el-input v-model="form.owner_contact" maxlength="100" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSubmit">保存</el-button>
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

.hero {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 22px;
  border-radius: 12px;
  border: 1px solid #d7e3ef;
  background:
    radial-gradient(ellipse at 0% 0%, rgba(58, 160, 255, 0.12), transparent 50%),
    linear-gradient(135deg, #f7fbff 0%, #e8f1fa 100%);
}

.hero-copy h2 {
  margin: 8px 0 6px;
  font-size: 20px;
}

.hero-copy p {
  margin: 0;
  color: #607080;
  font-size: 13px;
}

.list-card :deep(.el-card__header) {
  padding: 12px 16px;
}

.card-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}

.outbound-row {
  width: 100%;
}

.qty-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}
</style>
