<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createDatacenter,
  deleteDatacenter,
  listDatacenters,
  updateDatacenter,
  type DataCenter,
} from '@/api/datacenter'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const tableData = ref<DataCenter[]>([])
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
  await ElMessageBox.confirm(`确定删除数据中心「${row.name}」吗？`, '确认删除', { type: 'warning' })
  await deleteDatacenter(row.id)
  ElMessage.success('删除成功')
  await loadData()
}

onMounted(loadData)
</script>

<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>数据中心管理</span>
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

      <el-table v-loading="loading" :data="tableData" stripe>
        <el-table-column prop="code" label="编码" width="140" />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="location" label="位置" min-width="180" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="160" fixed="right">
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

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
