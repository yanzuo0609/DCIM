<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listDatacenters, type DataCenter } from '@/api/datacenter'
import { listRooms, type Room } from '@/api/room'
import {
  createWarehouse,
  deleteWarehouse,
  listWarehouses,
  updateWarehouse,
  type Warehouse,
} from '@/api/warehouse'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const tableData = ref<Warehouse[]>([])
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const keyword = ref('')
const filterDcId = ref('')
const filterRoomId = ref('')
const datacenters = ref<DataCenter[]>([])
const rooms = ref<Room[]>([])
const allRooms = ref<Room[]>([])
const dialogVisible = ref(false)
const editingId = ref<string | null>(null)
const saving = ref(false)

const form = reactive({
  code: '',
  name: '',
  room_id: '',
  description: '',
})

const canCreate = auth.hasPermission('datacenter:create')
const canUpdate = auth.hasPermission('datacenter:update')
const canDelete = auth.hasPermission('datacenter:delete')

const roomOptions = computed(() => {
  if (!filterDcId.value) return allRooms.value
  return allRooms.value.filter((r) => r.datacenter_id === filterDcId.value)
})

const formRoomOptions = computed(() => allRooms.value)

function rowIndex(index: number) {
  return (pagination.page - 1) * pagination.page_size + index + 1
}

function roomLabel(room: Room) {
  const parts = [
    room.datacenter_name || room.location,
    room.building_no,
    room.room_no || room.name,
    room.code,
  ].filter(Boolean)
  return parts.join(' / ') || room.id
}

function warehouseRoomLabel(row: Warehouse) {
  return [row.building_no, row.room_no || row.room_name].filter(Boolean).join('-') || '—'
}

async function loadDatacenters() {
  try {
    const data = await listDatacenters({ page: 1, page_size: 200 })
    datacenters.value = data.items || []
  } catch {
    datacenters.value = []
  }
}

async function loadRooms() {
  try {
    const data = await listRooms({
      page: 1,
      page_size: 500,
    })
    allRooms.value = data.items || []
    rooms.value = allRooms.value
  } catch {
    allRooms.value = []
    rooms.value = []
  }
}

async function loadData() {
  loading.value = true
  try {
    const data = await listWarehouses({
      page: pagination.page,
      page_size: pagination.page_size,
      keyword: keyword.value || undefined,
      room_id: filterRoomId.value || undefined,
      datacenter_id: filterDcId.value || undefined,
    })
    tableData.value = data.items
    pagination.total = data.pagination.total
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.code = ''
  form.name = ''
  form.room_id = filterRoomId.value || ''
  form.description = ''
  dialogVisible.value = true
}

function openEdit(row: Warehouse) {
  editingId.value = row.id
  form.code = row.code
  form.name = row.name
  form.room_id = row.room_id
  form.description = row.description || ''
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写库房名称')
    return
  }
  if (!form.room_id) {
    ElMessage.warning('请选择所属机房')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateWarehouse(editingId.value, {
        name: form.name.trim(),
        code: form.code.trim() || undefined,
        room_id: form.room_id,
        description: form.description || null,
      })
      ElMessage.success('更新成功')
    } else {
      await createWarehouse({
        name: form.name.trim(),
        code: form.code.trim() || null,
        room_id: form.room_id,
        description: form.description || null,
      })
      ElMessage.success('创建成功，已自动生成资产出入库清单')
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

function openAssets(row: Warehouse) {
  void router.push(`/warehouses/${row.id}/assets`)
}

async function handleDelete(row: Warehouse) {
  await ElMessageBox.confirm(
    `确定删除库房「${row.name}」吗？其资产出入库记录将一并删除。`,
    '确认删除',
    { type: 'warning' },
  )
  try {
    await deleteWarehouse(row.id)
    ElMessage.success('删除成功')
    await loadData()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '删除失败')
  }
}

watch(filterDcId, async () => {
  filterRoomId.value = ''
  pagination.page = 1
  await loadData()
})

watch(filterRoomId, () => {
  pagination.page = 1
  void loadData()
})

onMounted(async () => {
  await Promise.all([loadDatacenters(), loadRooms()])
  await loadData()
})
</script>

<template>
  <div class="page">
    <section class="hero">
      <div class="hero-copy">
        <h2>中心库房管理</h2>
        <p>创建库房后自动生成资产出入库清单，可进入库房查看并编辑资产记录。</p>
      </div>
      <div class="hero-actions">
        <el-button v-if="canCreate" type="primary" @click="openCreate">新建库房</el-button>
      </div>
    </section>

    <el-card shadow="never" class="list-card">
      <template #header>
        <div class="card-header">
          <span>库房列表</span>
          <div class="actions">
            <el-select
              v-model="filterDcId"
              clearable
              filterable
              placeholder="数据中心"
              style="width: 180px"
            >
              <el-option
                v-for="dc in datacenters"
                :key="dc.id"
                :label="dc.name"
                :value="dc.id"
              />
            </el-select>
            <el-select
              v-model="filterRoomId"
              clearable
              filterable
              placeholder="所属机房"
              style="width: 220px"
            >
              <el-option
                v-for="room in roomOptions"
                :key="room.id"
                :label="roomLabel(room)"
                :value="room.id"
              />
            </el-select>
            <el-input
              v-model="keyword"
              clearable
              placeholder="搜索名称/编号"
              style="width: 180px"
              @keyup.enter="loadData"
              @clear="loadData"
            />
            <el-button @click="loadData">搜索</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" stripe row-key="id">
        <el-table-column label="序号" width="72" align="center">
          <template #default="{ $index }">{{ rowIndex($index) }}</template>
        </el-table-column>
        <el-table-column label="库房名称" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.name }}</template>
        </el-table-column>
        <el-table-column label="库房编号" width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.code || '—' }}</template>
        </el-table-column>
        <el-table-column label="所属机房" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ warehouseRoomLabel(row) }}</template>
        </el-table-column>
        <el-table-column label="数据中心" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.datacenter_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="资产条数" width="100" align="center">
          <template #default="{ row }">{{ row.asset_count ?? 0 }}</template>
        </el-table-column>
        <el-table-column label="描述" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.description || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openAssets(row)">资产清单</el-button>
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
      :title="editingId ? '编辑库房' : '新建库房'"
      width="560px"
      destroy-on-close
    >
      <el-form label-width="100px">
        <el-form-item label="所属机房" required>
          <el-select
            v-model="form.room_id"
            filterable
            placeholder="选择机房"
            style="width: 100%"
          >
            <el-option
              v-for="room in formRoomOptions"
              :key="room.id"
              :label="roomLabel(room)"
              :value="room.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="库房名称" required>
          <el-input v-model="form.name" maxlength="100" placeholder="例如：A栋备件库" />
        </el-form-item>
        <el-form-item label="库房编号">
          <el-input
            v-model="form.code"
            maxlength="50"
            placeholder="空则自动生成 WH1、WH2…"
          />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
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
  align-items: center;
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
  margin: 0 0 6px;
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
</style>
