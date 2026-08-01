<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createDatacenter,
  deleteDatacenter,
  listDatacenters,
  updateDatacenter,
  type DataCenter,
} from '@/api/datacenter'
import { listRooms } from '@/api/room'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(false)
const tableData = ref<DataCenter[]>([])
const roomCountByDc = ref<Record<string, number>>({})
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const keyword = ref('')
const dialogVisible = ref(false)
const editingId = ref<string | null>(null)

const form = reactive({
  code: '',
  name: '',
  location: '',
  description: '',
})

const canCreate = auth.hasPermission('datacenter:create')
const canUpdate = auth.hasPermission('datacenter:update')
const canDelete = auth.hasPermission('datacenter:delete')

async function loadRoomCounts() {
  try {
    const res = await listRooms({ page: 1, page_size: 500 })
    const counts: Record<string, number> = {}
    for (const room of res.items) {
      const id = room.datacenter_id
      if (!id) continue
      counts[id] = (counts[id] || 0) + 1
    }
    roomCountByDc.value = counts
  } catch {
    /* ignore count failures */
  }
}

async function loadData() {
  loading.value = true
  try {
    const data = await listDatacenters({
      page: pagination.page,
      page_size: pagination.page_size,
      keyword: keyword.value || undefined,
    })
    tableData.value = data.items
    pagination.total = data.pagination.total
    void loadRoomCounts()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.code = ''
  form.name = ''
  form.location = ''
  form.description = ''
  dialogVisible.value = true
}

function openEdit(row: DataCenter) {
  editingId.value = row.id
  form.code = row.code
  form.name = row.name
  form.location = row.location || ''
  form.description = row.description || ''
  dialogVisible.value = true
}

function openRooms(row: DataCenter) {
  void router.push({
    path: '/rooms/manage',
    query: { datacenter_id: row.id },
  })
}

function openSimulate(row: DataCenter) {
  void router.push({ name: 'rooms-simulate', query: { datacenter_id: row.id } })
}

async function handleSubmit() {
  if (!form.code || !form.name) {
    ElMessage.warning('请填写编码和名称')
    return
  }

  try {
    if (editingId.value) {
      await updateDatacenter(editingId.value, {
        code: form.code,
        name: form.name,
        location: form.location || null,
        description: form.description || null,
      })
      ElMessage.success('更新成功')
    } else {
      await createDatacenter({
        code: form.code,
        name: form.name,
        location: form.location || null,
        description: form.description || null,
      })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await loadData()
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleDelete(row: DataCenter) {
  const roomCount = roomCountByDc.value[row.id] || 0
  try {
    if (roomCount > 0) {
      await ElMessageBox.confirm(
        `数据中心「${row.name}」下仍有 ${roomCount} 个机房，不能直接删除。\n\n选择「强制删除」将一并删除并清空其下全部机房及机柜，机柜上的设备会自动下架回库存。此操作不可恢复，是否继续？`,
        '无法直接删除',
        {
          type: 'warning',
          confirmButtonText: '强制删除',
          cancelButtonText: '取消',
          confirmButtonClass: 'el-button--danger',
          distinguishCancelAndClose: true,
        },
      )
      await deleteDatacenter(row.id, { force: true })
      ElMessage.success(`已强制删除数据中心，并清空 ${roomCount} 个机房`)
    } else {
      await ElMessageBox.confirm(`确定删除数据中心「${row.name}」吗？`, '确认删除', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      })
      await deleteDatacenter(row.id)
      ElMessage.success('删除成功')
    }
    await loadData()
  } catch (err: unknown) {
    if (err === 'cancel' || err === 'close') return
    const ax = err as { response?: { status?: number; data?: { message?: string; details?: { room_count?: number } } } }
    const status = ax.response?.status
    const details = ax.response?.data?.details
    const serverRooms = details?.room_count
    if (status === 409 && serverRooms && serverRooms > 0) {
      try {
        await ElMessageBox.confirm(
          ax.response?.data?.message ||
            `数据中心下仍有 ${serverRooms} 个机房。是否强制删除并清空全部机房？`,
          '强制删除确认',
          {
            type: 'warning',
            confirmButtonText: '强制删除',
            cancelButtonText: '取消',
            confirmButtonClass: 'el-button--danger',
          },
        )
        await deleteDatacenter(row.id, { force: true })
        ElMessage.success(`已强制删除数据中心，并清空 ${serverRooms} 个机房`)
        await loadData()
      } catch (inner) {
        if (inner === 'cancel' || inner === 'close') return
        ElMessage.error('强制删除失败')
      }
      return
    }
    ElMessage.error(ax.response?.data?.message || '删除失败')
  }
}

onMounted(loadData)
</script>

<template>
  <div class="page">
    <section class="hero">
      <div class="hero-copy">
        <h2>数据中心</h2>
        <p>统一管理数据中心台账、机房布局、机柜模板与 3D 仿真视图。</p>
      </div>
      <div class="hero-actions">
        <el-button @click="$router.push('/rooms/manage')">机房管理</el-button>
        <el-button @click="$router.push('/rooms/simulate')">进入 3D 仿真</el-button>
        <el-button type="primary" @click="$router.push('/rooms/templates')">机柜模板</el-button>
      </div>
    </section>

    <el-card shadow="never" class="dc-card">
      <template #header>
        <div class="card-header">
          <span>数据中心台账</span>
          <div class="actions">
            <el-input
              v-model="keyword"
              placeholder="搜索编码/名称/位置"
              clearable
              style="width: 240px"
              @keyup.enter="loadData"
              @clear="loadData"
            />
            <el-button @click="loadData">搜索</el-button>
            <el-button v-if="canCreate" type="primary" @click="openCreate">新建</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" stripe class="dc-table">
        <el-table-column prop="code" label="编码" width="140" />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="location" label="位置" min-width="160" />
        <el-table-column label="机房数" width="100" align="center">
          <template #default="{ row }">
            <span class="count-pill">{{ roomCountByDc[row.id] ?? '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openRooms(row)">进入机房管理</el-button>
            <el-button type="primary" link @click="openSimulate(row)">3D 仿真</el-button>
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
      :title="editingId ? '编辑数据中心' : '新建数据中心'"
      width="520px"
    >
      <el-form label-width="80px">
        <el-form-item label="编码" required>
          <el-input v-model="form.code" :disabled="!!editingId" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="位置">
          <el-input v-model="form.location" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
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
  margin: 0;
  font-size: 20px;
  color: #1f2d3d;
}

.hero-copy p {
  margin: 6px 0 0;
  font-size: 13px;
  color: #6b7c8f;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.dc-card {
  border-radius: 10px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.count-pill {
  display: inline-block;
  min-width: 28px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #ecf5ff;
  color: #409eff;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
