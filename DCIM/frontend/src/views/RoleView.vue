<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createRole,
  deleteRole,
  listPermissions,
  listRoles,
  updateRole,
  type Permission,
  type Role,
} from '@/api/user'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const tableData = ref<Role[]>([])
const permissions = ref<Permission[]>([])
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const keyword = ref('')
const dialogVisible = ref(false)
const editingId = ref<string | null>(null)

const form = reactive({
  code: '',
  name: '',
  description: '',
  permission_ids: [] as string[],
})

const canCreate = auth.hasPermission('role:create')
const canUpdate = auth.hasPermission('role:update')
const canDelete = auth.hasPermission('role:delete')

async function loadData() {
  loading.value = true
  try {
    const [roleData, permList] = await Promise.all([
      listRoles({ page: pagination.page, page_size: pagination.page_size, keyword: keyword.value || undefined }),
      listPermissions(),
    ])
    tableData.value = roleData.items
    pagination.total = roleData.pagination.total
    permissions.value = permList
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.code = ''
  form.name = ''
  form.description = ''
  form.permission_ids = []
  dialogVisible.value = true
}

function openEdit(row: Role) {
  editingId.value = row.id
  form.code = row.code
  form.name = row.name
  form.description = row.description || ''
  form.permission_ids = row.permissions.map((p) => p.id)
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!form.code || !form.name) {
    ElMessage.warning('请填写编码和名称')
    return
  }
  try {
    if (editingId.value) {
      await updateRole(editingId.value, {
        name: form.name,
        description: form.description || null,
        permission_ids: form.code === 'admin' ? undefined : form.permission_ids,
      })
      ElMessage.success('更新成功')
    } else {
      await createRole({
        code: form.code,
        name: form.name,
        description: form.description || null,
        permission_ids: form.permission_ids,
      })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await loadData()
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleDelete(row: Role) {
  if (row.code === 'admin') {
    ElMessage.warning('不能删除管理员角色')
    return
  }
  await ElMessageBox.confirm(`确定删除角色「${row.name}」吗？`, '确认删除', { type: 'warning' })
  await deleteRole(row.id)
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
          <span>角色管理</span>
          <div class="actions">
            <el-input v-model="keyword" placeholder="搜索编码/名称" clearable style="width: 220px" @keyup.enter="loadData" />
            <el-button @click="loadData">搜索</el-button>
            <el-button v-if="canCreate" type="primary" @click="openCreate">新建角色</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" stripe>
        <el-table-column prop="code" label="编码" min-width="120" />
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
        <el-table-column label="权限" min-width="260">
          <template #default="{ row }">
            <el-tag v-for="perm in row.permissions.slice(0, 4)" :key="perm.id" size="small" style="margin: 2px">
              {{ perm.code }}
            </el-tag>
            <span v-if="row.permissions.length > 4">+{{ row.permissions.length - 4 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canUpdate" type="primary" link @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canDelete && row.code !== 'admin'" type="danger" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑角色' : '新建角色'" width="640px">
      <el-form label-width="80px">
        <el-form-item label="编码" required>
          <el-input v-model="form.code" :disabled="!!editingId" />
        </el-form-item>
        <el-form-item label="名称" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
        <el-form-item v-if="form.code !== 'admin'" label="权限">
          <el-select v-model="form.permission_ids" multiple filterable style="width:100%">
            <el-option
              v-for="p in permissions"
              :key="p.id"
              :label="`${p.name} (${p.code})`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-alert v-else title="管理员角色拥有全部权限，不可修改权限分配" type="info" :closable="false" />
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page { display: flex; flex-direction: column; gap: 16px; }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.actions { display: flex; align-items: center; gap: 8px; }
</style>
