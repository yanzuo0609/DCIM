<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import NetworkTopologyCanvas from '@/components/NetworkTopologyCanvas.vue'
import NetworkTopologyPicker from '@/components/NetworkTopologyPicker.vue'
import { useNetworkTopology } from '@/composables/useNetworkTopology'
import { NODE_KIND_LABELS } from '@/api/network'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const {
  topologies,
  currentId,
  nodes,
  links,
  loading,
  saving,
  loadTopologies,
  selectTopology,
  saveCanvas,
  createTopology,
  removeTopology,
} = useNetworkTopology()

const canEdit = computed(() => auth.hasPermission('network:update'))
const selectedNodeId = ref<string | null>(null)

const selectedNode = computed(() => nodes.value.find((n) => n.id === selectedNodeId.value) || null)

function moveNode(id: string, x: number, y: number) {
  const node = nodes.value.find((n) => n.id === id)
  if (node) {
    node.pos_x = x
    node.pos_y = y
  }
}

function goToDevice(deviceId: string) {
  void router.push({ path: '/devices', query: { device_id: deviceId } })
}

async function handleCreateTopology(name: string, description: string | null) {
  try {
    await createTopology(name, description)
    ElMessage.success('拓扑已创建')
  } catch {
    ElMessage.error('创建失败')
  }
}

onMounted(() => {
  void loadTopologies()
})
</script>

<template>
  <div class="page" v-loading="loading">
    <el-card shadow="never" class="main-card">
      <div class="layout">
        <NetworkTopologyPicker
          :topologies="topologies"
          :current-id="currentId"
          :loading="loading"
          @select="selectTopology"
          @create="handleCreateTopology"
          @delete="removeTopology"
        />

        <section class="workspace">
          <div class="toolbar">
            <span class="title">拓扑设计</span>
            <span v-if="nodes.length" class="hint">拖拽节点调整布局，连线请在「接口设计」中配置</span>
            <el-button
              v-if="canEdit"
              type="primary"
              :loading="saving"
              :disabled="!currentId"
              @click="saveCanvas"
            >
              保存布局
            </el-button>
          </div>

          <NetworkTopologyCanvas
            v-if="currentId"
            :nodes="nodes"
            :links="links"
            :selected-node-id="selectedNodeId"
            :link-mode="false"
            @select-node="selectedNodeId = $event"
            @move-node="moveNode"
          />
          <el-empty v-else description="请选择或新建拓扑" />
        </section>

        <aside class="inspector">
          <template v-if="selectedNode">
            <h3>设备信息</h3>
            <p><strong>名称：</strong>{{ selectedNode.name }}</p>
            <p><strong>类型：</strong>{{ NODE_KIND_LABELS[selectedNode.kind] }}</p>
            <p><strong>坐标：</strong>{{ Math.round(selectedNode.pos_x) }}, {{ Math.round(selectedNode.pos_y) }}</p>
            <template v-if="selectedNode.device">
              <p><strong>主机名：</strong>{{ selectedNode.device.hostname }}</p>
              <p>
                <strong>机房/机柜：</strong>{{ selectedNode.device.room_name || '-' }} /
                {{ selectedNode.device.rack_code || '-' }}
              </p>
              <p><strong>U 位：</strong>{{ selectedNode.device.u_position ?? '-' }}</p>
              <p><strong>系统 IP：</strong>{{ selectedNode.device.ip_summary || '-' }}</p>
              <el-button type="primary" link @click="goToDevice(selectedNode.device!.device_id)">
                查看设备详情 →
              </el-button>
            </template>
            <p v-else class="muted">未关联设备管理记录，请在「设备定义」中配置</p>
          </template>
          <el-empty v-else description="点击画布节点查看信息" />
        </aside>
      </div>
    </el-card>
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
  padding: 0;
}

.layout {
  display: grid;
  grid-template-columns: 220px 1fr 280px;
  height: 100%;
}

.workspace {
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 16px;
  gap: 12px;
}

.inspector {
  border-left: 1px solid #ebeef5;
  padding: 16px;
  overflow: auto;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.title {
  font-weight: 600;
}

.hint {
  color: #909399;
  font-size: 13px;
}

.inspector h3 {
  margin: 0 0 12px;
}

.inspector p {
  margin: 0 0 8px;
  font-size: 13px;
}

.muted {
  color: #909399;
  font-size: 13px;
}
</style>
