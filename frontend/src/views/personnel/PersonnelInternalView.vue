<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createInternal,
  deleteInternal,
  listInternals,
  updateInternal,
  type InternalContact,
} from '@/api/personnel'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const tableData = ref<InternalContact[]>([])
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const keyword = ref('')
const dialogVisible = ref(false)
const editingId = ref<string | null>(null)

const form = reactive({
  name: '',
  role_title: '',
  phone: '',
  email: '',
  company: '',
  project_no: '',
  notes: '',
})

const canCreate = auth.hasPermission('device:create')
const canUpdate = auth.hasPermission('device:update')
const canDelete = auth.hasPermission('device:delete')

async function loadData() {
  loading.value = true
  try {
    const data = await listInternals({
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
  form.company = ''
  form.project_no = ''
  form.notes = ''
  dialogVisible.value = true
}

function openEdit(row: InternalContact) {
  editingId.value = row.id
  form.name = row.name
  form.role_title = row.role_title || ''
  form.phone = row.phone || ''
  form.email = row.email || ''
  form.company = row.company || ''
  form.project_no = row.project_no || ''
  form.notes = row.notes || ''
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写姓名')
    return
  }
  const payload = {
    name: form.name.trim(),
    role_title: form.role_title.trim(),
    phone: form.phone.trim() || null,
    email: form.email.trim() || null,
    company: form.company.trim() || null,
    project_no: form.project_no.trim() || null,
    notes: form.notes.trim() || null,
  }
  try {
    if (editingId.value) {
      await updateInternal(editingId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await createInternal(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await loadData()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { message?: string } }; message?: string }
    ElMessage.error(err.response?.data?.message || err.message || '操作失败')
  }
}

async function handleDelete(row: InternalContact) {
  await ElMessageBox.confirm(`确定删除「${row.name}」吗？`, '确认删除', { type: 'warning' })
  await deleteInternal(row.id)
  ElMessage.success('删除成功')
  await loadData()
}

function onSearch() {
  pagination.page = 1
  void loadData()
}

onMounted(loadData)
</script>

<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>用户相关方</span>
          <div class="actions">
            <el-input
              v-model="keyword"
              placeholder="搜索姓名/角色/电话/项目"
              clearable
              style="width: 240px"
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
        <el-table-column prop="role_title" label="角色" min-width="120" />
        <el-table-column prop="phone" label="电话" min-width="120">
          <template #default="{ row }">{{ row.phone || '—' }}</template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.email || '—' }}</template>
        </el-table-column>
        <el-table-column prop="company" label="单位" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.company || '—' }}</template>
        </el-table-column>
        <el-table-column prop="project_no" label="项目编号" min-width="120">
          <template #default="{ row }">{{ row.project_no || '—' }}</template>
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

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑用户相关方' : '新建用户相关方'" width="560px">
      <el-form label-width="90px">
        <el-form-item label="姓名" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="角色">
          <el-input v-model="form.role_title" placeholder="如：项目经理 / 运维" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="form.company" />
        </el-form-item>
        <el-form-item label="项目编号">
          <el-input v-model="form.project_no" />
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
</style>
