<script setup lang="ts">
import { reactive, ref } from 'vue'
import type { NetworkTopology } from '@/api/network'
import { useAuthStore } from '@/stores/auth'

defineProps<{
  topologies: NetworkTopology[]
  currentId: string | null
  loading?: boolean
}>()

const emit = defineEmits<{
  select: [id: string]
  create: [name: string, description: string | null]
  delete: []
}>()

const auth = useAuthStore()
const createDialogVisible = ref(false)
const createForm = reactive({ name: '', description: '' })

const canCreate = auth.hasPermission('network:create')
const canDelete = auth.hasPermission('network:delete')

function openCreateDialog() {
  createForm.name = ''
  createForm.description = ''
  createDialogVisible.value = true
}

function submitCreate() {
  if (!createForm.name.trim()) return
  emit('create', createForm.name.trim(), createForm.description.trim() || null)
  createDialogVisible.value = false
}
</script>

<template>
  <aside class="topology-picker">
    <div class="picker-header">
      <span>拓扑列表</span>
      <el-button v-if="canCreate" type="primary" link @click="openCreateDialog">新建</el-button>
    </div>
    <el-scrollbar v-loading="loading" class="topology-list">
      <div
        v-for="item in topologies"
        :key="item.id"
        class="topology-item"
        :class="{ active: currentId === item.id }"
        @click="emit('select', item.id)"
      >
        <div class="name">{{ item.name }}</div>
        <div class="desc">{{ item.description || '无描述' }}</div>
      </div>
      <el-empty v-if="!topologies.length" description="暂无拓扑" />
    </el-scrollbar>
    <el-button
      v-if="canDelete && currentId"
      type="danger"
      plain
      size="small"
      class="delete-btn"
      @click="emit('delete')"
    >
      删除当前拓扑
    </el-button>

    <el-dialog v-model="createDialogVisible" title="新建网络拓扑" width="420px" append-to-body>
      <el-form label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="createForm.name" maxlength="200" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </aside>
</template>

<style scoped>
.topology-picker {
  width: 220px;
  border-right: 1px solid #ebeef5;
  padding: 16px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.picker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-weight: 600;
}

.topology-list {
  flex: 1;
  min-height: 120px;
}

.topology-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 8px;
  border: 1px solid transparent;
}

.topology-item:hover {
  background: #f5f7fa;
}

.topology-item.active {
  background: #ecf5ff;
  border-color: #b3d8ff;
}

.topology-item .name {
  font-weight: 500;
}

.topology-item .desc {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.delete-btn {
  margin-top: 12px;
  width: 100%;
}
</style>
