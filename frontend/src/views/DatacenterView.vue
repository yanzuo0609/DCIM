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
import { listRooms, type Room } from '@/api/room'
import { useAuthStore } from '@/stores/auth'

const ATTR_LABELS: Record<string, string> = {
  private_network: '专网',
  internet: '互联网',
}

const auth = useAuthStore()
const router = useRouter()
const loading = ref(false)
const tableData = ref<DataCenter[]>([])
const selectedRows = ref<DataCenter[]>([])
const roomCountByDc = ref<Record<string, number>>({})
const roomsByDc = ref<Record<string, Room[]>>({})
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const keyword = ref('')
const dialogVisible = ref(false)
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailRow = ref<DataCenter | null>(null)
const detailRooms = ref<Room[]>([])
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

function rowIndex(index: number) {
  return (pagination.page - 1) * pagination.page_size + index + 1
}

function roomDisplayName(room: Room) {
  return room.room_no || room.name || room.code || '—'
}

function roomTypeLabel(room: Room) {
  const attrs = Array.isArray(room.attributes) ? room.attributes : []
  if (!attrs.length) return '其他'
  const labels = attrs.map((a) => ATTR_LABELS[a] || (a === '其他' ? '其他' : a))
  const known = labels.filter((l) => l === '专网' || l === '互联网' || l === '其他')
  if (known.length) return [...new Set(known)].join('、')
  // 自定义属性归为「其他」并附带原文
  return `其他（${labels.join('、')}）`
}

async function loadRoomIndex() {
  try {
    const res = await listRooms({ page: 1, page_size: 500 })
    const counts: Record<string, number> = {}
    const grouped: Record<string, Room[]> = {}
    for (const room of res.items) {
      const id = room.datacenter_id
      if (!id) continue
      counts[id] = (counts[id] || 0) + 1
      if (!grouped[id]) grouped[id] = []
      grouped[id].push(room)
    }
    roomCountByDc.value = counts
    roomsByDc.value = grouped
  } catch {
    /* ignore */
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
    void loadRoomIndex()
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

async function openDetail(row: DataCenter) {
  detailRow.value = row
  detailVisible.value = true
  detailLoading.value = true
  try {
    const cached = roomsByDc.value[row.id]
    if (cached) {
      detailRooms.value = cached
    } else {
      const res = await listRooms({
        page: 1,
        page_size: 200,
        datacenter_id: row.id,
      })
      detailRooms.value = res.items.filter((r) => r.datacenter_id === row.id)
      roomsByDc.value = { ...roomsByDc.value, [row.id]: detailRooms.value }
      roomCountByDc.value = {
        ...roomCountByDc.value,
        [row.id]: detailRooms.value.length,
      }
    }
  } catch {
    detailRooms.value = []
    ElMessage.error('加载机房列表失败')
  } finally {
    detailLoading.value = false
  }
}

function goRoomList(dc: DataCenter, room?: Room) {
  detailVisible.value = false
  void router.push({
    path: '/rooms/manage',
    query: {
      datacenter_id: dc.id,
      ...(room ? { keyword: room.code || room.room_no || room.name } : {}),
    },
  })
}

async function handleSubmit() {
  if (!form.name) {
    ElMessage.warning('请填写数据中心名称')
    return
  }

  try {
    if (editingId.value) {
      await updateDatacenter(editingId.value, {
        name: form.name,
        location: form.location || null,
      })
      ElMessage.success('修改成功')
    } else {
      await createDatacenter({
        code: form.code.trim() || null,
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
    const ax = err as {
      response?: { status?: number; data?: { message?: string; details?: { room_count?: number } } }
    }
    const status = ax.response?.status
    const serverRooms = ax.response?.data?.details?.room_count
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
              placeholder="搜索编号/名称/地理位置"
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

      <el-table
        v-loading="loading"
        :data="tableData"
        stripe
        class="dc-table"
        row-key="id"
        @selection-change="(rows: DataCenter[]) => (selectedRows = rows)"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column label="序号" width="72" align="center">
          <template #default="{ $index }">{{ rowIndex($index) }}</template>
        </el-table-column>
        <el-table-column prop="name" label="数据中心名称" min-width="160" />
        <el-table-column prop="code" label="数据中心编号" width="130" />
        <el-table-column label="数据中心ID(唯一)" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono-id">{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="location" label="地理位置" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.location || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="88" fixed="right" align="center">
          <template #default="{ row }">
            <el-dropdown trigger="click">
              <el-button type="primary" link>操作</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="openDetail(row)">详细信息</el-dropdown-item>
                  <el-dropdown-item v-if="canUpdate" @click="openEdit(row)">修改信息</el-dropdown-item>
                  <el-dropdown-item v-if="canDelete" divided @click="handleDelete(row)">
                    删除
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
          layout="total, prev, pager, next"
          :total="pagination.total"
          @change="loadData"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '修改信息' : '新建数据中心'"
      width="480px"
    >
      <el-form label-width="110px">
        <template v-if="editingId">
          <el-form-item label="数据中心名称" required>
            <el-input v-model="form.name" placeholder="请输入数据中心名称" />
          </el-form-item>
          <el-form-item label="地理位置">
            <el-input v-model="form.location" placeholder="请输入地理位置" />
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="数据中心编号">
            <el-input v-model="form.code" placeholder="空则自动生成 DC1、DC2…" />
          </el-form-item>
          <el-form-item label="数据中心名称" required>
            <el-input v-model="form.name" placeholder="请输入数据中心名称" />
          </el-form-item>
          <el-form-item label="地理位置">
            <el-input v-model="form.location" placeholder="请输入地理位置" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model="form.description" type="textarea" :rows="3" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailVisible" title="详细信息" width="640px">
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="detailRow">
          <el-descriptions :column="1" border class="detail-meta">
            <el-descriptions-item label="数据中心名称">{{ detailRow.name }}</el-descriptions-item>
            <el-descriptions-item label="数据中心编号">{{ detailRow.code }}</el-descriptions-item>
            <el-descriptions-item label="数据中心ID(唯一)">
              <span class="mono-id">{{ detailRow.id }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="地理位置">
              {{ detailRow.location || '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="机房总数">
              {{ detailRooms.length }}
            </el-descriptions-item>
          </el-descriptions>

          <div class="room-block">
            <div class="room-block-title">
              机房列表
              <el-button
                v-if="detailRooms.length"
                type="primary"
                link
                @click="goRoomList(detailRow)"
              >
                查看全部机房
              </el-button>
            </div>
            <el-table
              v-if="detailRooms.length"
              :data="detailRooms"
              size="small"
              stripe
              class="room-mini-table"
            >
              <el-table-column label="机房名称" min-width="120">
                <template #default="{ row }">
                  <el-button type="primary" link @click="goRoomList(detailRow!, row)">
                    {{ roomDisplayName(row) }}
                  </el-button>
                </template>
              </el-table-column>
              <el-table-column label="编号" width="100">
                <template #default="{ row }">{{ row.code || '—' }}</template>
              </el-table-column>
              <el-table-column label="机房类型" min-width="120">
                <template #default="{ row }">
                  <span class="type-tag" :class="roomTypeLabel(row).includes('专网') ? 'private' : roomTypeLabel(row).includes('互联网') ? 'internet' : 'other'">
                    {{ roomTypeLabel(row) }}
                  </span>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="暂无下属机房" :image-size="72" />
          </div>
        </template>
      </div>
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
  gap: 16px;
}

.mono-id {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  color: #606266;
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
  font-size: 22px;
  color: #1f2d3d;
}

.hero-copy p {
  margin: 8px 0 0;
  color: #5f6b7a;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
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
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.detail-body {
  min-height: 120px;
}

.detail-meta {
  margin-bottom: 16px;
}

.room-block-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  font-weight: 600;
  color: #303133;
}

.room-mini-table {
  width: 100%;
}

.type-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.type-tag.private {
  background: #f0f5ff;
  color: #2f54eb;
}

.type-tag.internet {
  background: #f6ffed;
  color: #389e0d;
}

.type-tag.other {
  background: #f5f5f5;
  color: #595959;
}
</style>
