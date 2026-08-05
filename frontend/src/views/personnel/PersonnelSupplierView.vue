<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listManufacturers, listDeviceModels, type Manufacturer, type DeviceModel } from '@/api/device'
import { listDeviceContracts, type DeviceContract } from '@/api/contract'
import {
  createSupplier,
  deleteSupplier,
  listSuppliers,
  updateSupplier,
  type SupplierContact,
  type SupplierProduct,
} from '@/api/personnel'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const tableData = ref<SupplierContact[]>([])
const manufacturers = ref<Manufacturer[]>([])
const contracts = ref<DeviceContract[]>([])
const models = ref<DeviceModel[]>([])
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const keyword = ref('')
const dialogVisible = ref(false)
const editingId = ref<string | null>(null)

const form = reactive({
  name: '',
  role_title: '',
  phone: '',
  email: '',
  wechat: '',
  manufacturer_id: '',
  notes: '',
  contract_ids: [] as string[],
  products: [] as SupplierProduct[],
})

const canCreate = auth.hasPermission('device:create')
const canUpdate = auth.hasPermission('device:update')
const canDelete = auth.hasPermission('device:delete')

async function loadOptions() {
  const [mfgs, contractData, modelList] = await Promise.all([
    listManufacturers(),
    listDeviceContracts({ page: 1, page_size: 200 }),
    listDeviceModels(),
  ])
  manufacturers.value = mfgs
  contracts.value = contractData.items || []
  models.value = modelList
}

async function loadData() {
  loading.value = true
  try {
    const data = await listSuppliers({
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

function openCreate() {
  editingId.value = null
  form.name = ''
  form.role_title = ''
  form.phone = ''
  form.email = ''
  form.wechat = ''
  form.manufacturer_id = ''
  form.notes = ''
  form.contract_ids = []
  form.products = []
  dialogVisible.value = true
}

function openEdit(row: SupplierContact) {
  editingId.value = row.id
  form.name = row.name
  form.role_title = row.role_title || ''
  form.phone = row.phone || ''
  form.email = row.email || ''
  form.wechat = row.wechat || ''
  form.manufacturer_id = row.manufacturer_id
  form.notes = row.notes || ''
  form.contract_ids = [...(row.contract_ids || [])]
  form.products = (row.products || []).map((p) => ({
    device_model_id: p.device_model_id || null,
    device_name: p.device_name || null,
    device_model_name: p.device_model_name || null,
  }))
  dialogVisible.value = true
}

function addProduct() {
  form.products.push({ device_model_id: null, device_name: '', device_model_name: '' })
}

function removeProduct(idx: number) {
  form.products.splice(idx, 1)
}

function onModelPick(idx: number, modelId: string | null) {
  const hit = models.value.find((m) => m.id === modelId)
  if (!hit) return
  form.products[idx].device_model_id = hit.id
  form.products[idx].device_model_name = hit.name
  form.products[idx].device_name = hit.name
}

async function handleSubmit() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写姓名')
    return
  }
  if (!form.manufacturer_id) {
    ElMessage.warning('请选择厂商')
    return
  }
  const payload = {
    name: form.name.trim(),
    role_title: form.role_title.trim(),
    phone: form.phone.trim() || null,
    email: form.email.trim() || null,
    wechat: form.wechat.trim() || null,
    manufacturer_id: form.manufacturer_id,
    notes: form.notes.trim() || null,
    contract_ids: form.contract_ids,
    products: form.products
      .filter((p) => p.device_model_id || p.device_name || p.device_model_name)
      .map((p) => ({
        device_model_id: p.device_model_id || null,
        device_name: (p.device_name || '').trim() || null,
        device_model_name: (p.device_model_name || '').trim() || null,
      })),
  }
  try {
    if (editingId.value) {
      await updateSupplier(editingId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await createSupplier(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await loadData()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '操作失败')
  }
}

async function handleDelete(row: SupplierContact) {
  await ElMessageBox.confirm(`确定删除「${row.name}」吗？`, '确认删除', { type: 'warning' })
  await deleteSupplier(row.id)
  ElMessage.success('删除成功')
  await loadData()
}

function onSearch() {
  pagination.page = 1
  void loadData()
}

onMounted(async () => {
  await loadOptions()
  await loadData()
})
</script>

<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>供应商相关方</span>
          <div class="actions">
            <el-input
              v-model="keyword"
              placeholder="搜索姓名/角色/电话"
              clearable
              style="width: 220px"
              @keyup.enter="onSearch"
              @clear="onSearch"
            />
            <el-button @click="onSearch">搜索</el-button>
            <el-button v-if="canCreate" type="primary" @click="openCreate">新建</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" stripe>
        <el-table-column prop="name" label="姓名" min-width="100" />
        <el-table-column prop="role_title" label="角色" min-width="110" />
        <el-table-column label="厂商" min-width="120">
          <template #default="{ row }">{{ row.manufacturer_name || '—' }}</template>
        </el-table-column>
        <el-table-column prop="phone" label="电话" min-width="110">
          <template #default="{ row }">{{ row.phone || '—' }}</template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.email || '—' }}</template>
        </el-table-column>
        <el-table-column label="关联合同" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            {{ (row.contract_nos || []).join('、') || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="相关产品" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            {{
              (row.products || [])
                .map((p: SupplierProduct) => p.device_model_name || p.device_name)
                .filter(Boolean)
                .join('、') || '—'
            }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="88" fixed="right" align="center">
          <template #default="{ row }">
            <el-dropdown trigger="click">
              <el-button type="primary" link>操作</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-if="canUpdate" @click="openEdit(row)">编辑</el-dropdown-item>
                  <el-dropdown-item v-if="canDelete" divided @click="handleDelete(row)">删除</el-dropdown-item>
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

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑供应商相关方' : '新建供应商相关方'" width="680px">
      <el-form label-width="100px">
        <el-form-item label="姓名" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="角色">
          <el-input v-model="form.role_title" placeholder="如：销售 / 技术支持" />
        </el-form-item>
        <el-form-item label="厂商" required>
          <el-select v-model="form.manufacturer_id" filterable style="width: 100%">
            <el-option v-for="m in manufacturers" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="微信">
          <el-input v-model="form.wechat" />
        </el-form-item>
        <el-form-item label="关联合同">
          <el-select v-model="form.contract_ids" multiple filterable style="width: 100%">
            <el-option
              v-for="c in contracts"
              :key="c.id"
              :label="`${c.contract_no}${c.project_no ? ` · ${c.project_no}` : ''}`"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="相关产品">
          <div class="product-list">
            <div v-for="(p, idx) in form.products" :key="idx" class="product-row">
              <el-select
                :model-value="p.device_model_id || undefined"
                clearable
                filterable
                placeholder="选择型号"
                style="width: 220px"
                @update:model-value="(v: string | null) => onModelPick(idx, v)"
              >
                <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.id" />
              </el-select>
              <el-input v-model="p.device_model_name" placeholder="型号名称" style="flex: 1" />
              <el-button link type="danger" @click="removeProduct(idx)">移除</el-button>
            </div>
            <el-button link type="primary" @click="addProduct">+ 添加产品</el-button>
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存</el-button>
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
.product-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.product-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
