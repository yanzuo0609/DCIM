<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useNetworkTopology } from '@/composables/useNetworkTopology'
import {
  LINK_TYPE_LABELS,
  NODE_KIND_LABELS,
  listNodePorts,
  type NetworkLink,
  type NetworkLinkType,
} from '@/api/network'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const {
  projects,
  currentProjectId,
  currentProject,
  currentId,
  currentTopology,
  nodes,
  links,
  loading,
  saving,
  loadProjects,
  selectProject,
  saveCanvas,
} = useNetworkTopology()

const canEdit = computed(() => auth.hasPermission('network:update'))
const linkDialogVisible = ref(false)
const linkType = ref<NetworkLinkType>('switch_server')
const linkForm = reactive({
  sourceNodeId: '',
  sourcePort: '',
  targetNodeId: '',
  targetPort: '',
  label: '',
})

const sourcePortOptions = computed(() => {
  const node = nodes.value.find((n) => n.id === linkForm.sourceNodeId)
  return node ? listNodePorts(node) : []
})

const targetPortOptions = computed(() => {
  const node = nodes.value.find((n) => n.id === linkForm.targetNodeId)
  return node ? listNodePorts(node) : []
})

function nodeName(id: string) {
  return nodes.value.find((n) => n.id === id)?.name || id.slice(0, 8)
}

function openLinkDialog() {
  if (!nodes.value.length) {
    ElMessage.warning('请先在「设备定义」中添加设备')
    return
  }
  linkForm.sourceNodeId = ''
  linkForm.sourcePort = ''
  linkForm.targetNodeId = ''
  linkForm.targetPort = ''
  linkForm.label = ''
  linkDialogVisible.value = true
}

function confirmAddLink() {
  if (!linkForm.sourceNodeId || !linkForm.targetNodeId || !linkForm.sourcePort || !linkForm.targetPort) {
    ElMessage.warning('请完整选择连线两端及接口')
    return
  }
  links.value.push({
    id: crypto.randomUUID(),
    topology_id: currentId.value || '',
    link_type: linkType.value,
    source_node_id: linkForm.sourceNodeId,
    source_port: linkForm.sourcePort,
    target_node_id: linkForm.targetNodeId,
    target_port: linkForm.targetPort,
    label: linkForm.label.trim() || null,
  })
  linkDialogVisible.value = false
  ElMessage.success('连线已添加，请保存')
}

function removeLink(linkId: string) {
  links.value = links.value.filter((l) => l.id !== linkId)
}

async function onProjectChange(id: string) {
  if (!id) return
  await selectProject(id)
}

onMounted(() => {
  void loadProjects()
})
</script>

<template>
  <div class="page" v-loading="loading">
    <el-card shadow="never" class="main-card">
      <section class="workspace">
        <div class="toolbar">
          <span class="title">接口设计</span>
          <el-select
            :model-value="currentProjectId"
            placeholder="选择项目"
            style="width: 220px"
            filterable
            @change="onProjectChange"
          >
            <el-option
              v-for="p in projects"
              :key="p.id"
              :label="`${p.name} (${p.code})`"
              :value="p.id"
            />
          </el-select>
          <span v-if="currentProject" class="topology-name">项目：{{ currentProject.name }}</span>
          <span v-if="currentTopology" class="topology-name">拓扑：{{ currentTopology.name }}</span>
          <el-select v-model="linkType" style="width: 220px" :disabled="!canEdit">
              <el-option v-for="(label, key) in LINK_TYPE_LABELS" :key="key" :label="label" :value="key" />
            </el-select>
            <el-button v-if="canEdit" :disabled="!currentId" @click="openLinkDialog">添加连线</el-button>
            <el-button v-if="canEdit" type="primary" :loading="saving" :disabled="!currentId" @click="saveCanvas">
              保存
            </el-button>
          </div>

          <el-table v-if="currentId" :data="links" stripe>
            <el-table-column label="类型" width="160">
              <template #default="{ row }: { row: NetworkLink }">{{ LINK_TYPE_LABELS[row.link_type] }}</template>
            </el-table-column>
            <el-table-column label="源设备" min-width="120">
              <template #default="{ row }">{{ nodeName(row.source_node_id) }}</template>
            </el-table-column>
            <el-table-column prop="source_port" label="源接口" width="120" />
            <el-table-column label="目标设备" min-width="120">
              <template #default="{ row }">{{ nodeName(row.target_node_id) }}</template>
            </el-table-column>
            <el-table-column prop="target_port" label="目标接口" width="120" />
            <el-table-column prop="label" label="备注" min-width="120" />
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ row }">
                <el-button v-if="canEdit" type="danger" link @click="removeLink(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="请先在「设备定义」中创建或选择项目" />
      </section>
    </el-card>

    <el-dialog v-model="linkDialogVisible" title="添加接口连线" width="560px">
      <el-form label-width="100px">
        <el-form-item label="连线类型">
          <el-select v-model="linkType" style="width: 100%">
            <el-option v-for="(label, key) in LINK_TYPE_LABELS" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="源设备">
          <el-select v-model="linkForm.sourceNodeId" filterable style="width: 100%">
            <el-option
              v-for="n in nodes"
              :key="n.id"
              :label="`${n.name} (${NODE_KIND_LABELS[n.kind]})`"
              :value="n.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="源接口">
          <el-select v-model="linkForm.sourcePort" filterable style="width: 100%">
            <el-option v-for="p in sourcePortOptions" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标设备">
          <el-select v-model="linkForm.targetNodeId" filterable style="width: 100%">
            <el-option
              v-for="n in nodes"
              :key="n.id"
              :label="`${n.name} (${NODE_KIND_LABELS[n.kind]})`"
              :value="n.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="目标接口">
          <el-select v-model="linkForm.targetPort" filterable style="width: 100%">
            <el-option v-for="p in targetPortOptions" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="linkForm.label" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="linkDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmAddLink">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  height: calc(100vh - 180px);
}

.main-card {
  height: 100%;
}

.main-card :deep(.el-card__body) {
  height: 100%;
  padding: 16px;
}

.workspace {
  min-width: 0;
  overflow: auto;
  height: 100%;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}

.title {
  font-weight: 600;
  margin-right: 8px;
}

.topology-name {
  color: #606266;
  font-size: 13px;
  margin-right: 8px;
}
</style>
