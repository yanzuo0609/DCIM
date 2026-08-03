<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createUser,
  deleteUser,
  listRoles,
  listUsers,
  updateUser,
  type User,
} from '@/api/user'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const tableData = ref<User[]>([])
const roles = ref<{ id: string; code: string; name: string }[]>([])
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const keyword = ref('')
const dialogVisible = ref(false)
const editingId = ref<string | null>(null)

const form = reactive({
  username: '',
  email: '',
  password: '',
  full_name: '',
  status: 'active',
  role_ids: [] as string[],
})

const canCreate = auth.hasPermission('user:create')
const canUpdate = auth.hasPermission('user:update')
const canDelete = auth.hasPermission('user:delete')

async function loadData() {
  loading.value = true
  try {
    const [userData, roleData] = await Promise.all([
      listUsers({ page: pagination.page, page_size: pagination.page_size, keyword: keyword.value || undefined }),
      listRoles({ page_size: 100 }),
    ])
    tableData.value = userData.items
    pagination.total = userData.pagination.total
    roles.value = roleData.items
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.username = ''
  form.email = ''
  form.password = ''
  form.full_name = ''
  form.status = 'active'
  form.role_ids = []
  dialogVisible.value = true
}

function openEdit(row: User) {
  editingId.value = row.id
  form.username = row.username
  form.email = row.email
  form.password = ''
  form.full_name = row.full_name || ''
  form.status = row.status
  form.role_ids = row.roles.map((r) => r.id)
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!form.email || (!editingId.value && (!form.username || !form.password))) {
    ElMessage.warning('请填写必填项')
    return
  }
  try {
    if (editingId.value) {
      await updateUser(editingId.value, {
        email: form.email,
        password: form.password || undefined,
        full_name: form.full_name || null,
        status: form.status,
        role_ids: form.role_ids,
      })
      ElMessage.success('更新成功')
    } else {
      await createUser({
        username: form.username,
        email: form.email,
        password: form.password,
        full_name: form.full_name || null,
        status: form.status,
        role_ids: form.role_ids,
      })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await loadData()
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleDelete(row: User) {
  if (row.username === 'admin') {
    ElMessage.warning('不能删除默认管理员')
    return
  }
  await ElMessageBox.confirm(`确定删除用户「${row.username}」吗？`, '确认删除', { type: 'warning' })
  await deleteUser(row.id)
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
          <span>用户管理</span>
          <div class="actions">
            <el-input v-model="keyword" placeholder="搜索用户名/邮箱" clearable style="width: 220px" @keyup.enter="loadData" />
            <el-button @click="loadData">搜索</el-button>
            <el-button v-if="canCreate" type="primary" @click="openCreate">新建用户</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" stripe>
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column prop="full_name" label="姓名" min-width="120" />
        <el-table-column label="角色" min-width="160">
          <template #default="{ row }">
            <el-tag v-for="role in row.roles" :key="role.id" size="small" style="margin-right: 4px">
              {{ role.name }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column label="操作" width="88" fixed="right" align="center">
          <template #default="{ row }">
            <el-dropdown trigger="click">
              <el-button type="primary" link>操作</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-if="canUpdate" @click="openEdit(row)">编辑</el-dropdown-item>
                  <el-dropdown-item
                    v-if="canDelete && row.username !== 'admin'"
                    divided
                    @click="handleDelete(row)"
                  >
                    删除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑用户' : '新建用户'" width="560px">
      <el-form label-width="90px">
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" :disabled="!!editingId" />
        </el-form-item>
        <el-form-item label="邮箱" required><el-input v-model="form.email" /></el-form-item>
        <el-form-item :label="editingId ? '新密码' : '密码'" :required="!editingId">
          <el-input v-model="form.password" type="password" show-password placeholder="至少12位" />
        </el-form-item>
        <el-form-item label="姓名"><el-input v-model="form.full_name" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width:100%">
            <el-option label="启用" value="active" />
            <el-option label="禁用" value="inactive" />
            <el-option label="锁定" value="locked" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role_ids" multiple style="width:100%">
            <el-option v-for="r in roles" :key="r.id" :label="`${r.name} (${r.code})`" :value="r.id" />
          </el-select>
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
.page { display: flex; flex-direction: column; gap: 16px; }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.actions { display: flex; align-items: center; gap: 8px; }
</style>
