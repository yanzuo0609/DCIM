<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import NetworkDevicePalette from '@/components/NetworkDevicePalette.vue'
import NetworkTopologyCanvas from '@/components/NetworkTopologyCanvas.vue'
import NetworkTopologyPicker from '@/components/NetworkTopologyPicker.vue'
import TopologyLinkDialog, { type LinkConfirmPayload } from '@/components/TopologyLinkDialog.vue'
import TopologyNodeInspector from '@/components/TopologyNodeInspector.vue'
import { useNetworkTopology } from '@/composables/useNetworkTopology'
import { cloneNodeOntoCanvas } from '@/utils/topologyClone'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const {
  projects,
  currentProjectId,
  currentProject,
  topologies,
  currentId,
  nodes,
  links,
  loading,
  saving,
  loadProjects,
  selectProject,
  selectTopology,
  saveCanvas,
  createTopology,
  removeTopology,
} = useNetworkTopology()

const canEdit = computed(() => auth.hasPermission('network:update'))
const selectedNodeId = ref<string | null>(null)
/** 左侧选中的模板：可多次点击/拖拽画布克隆 */
const stampTemplateId = ref<string | null>(null)
const linkMode = ref(false)
const linkSourceId = ref<string | null>(null)
const linkDialogVisible = ref(false)
const linkDialogSource = ref<string | null>(null)
const linkDialogTarget = ref<string | null>(null)
const linkDialogSourcePort = ref<string | null>(null)
const linkDialogLockEndpoints = ref(true)
const linkDialogLockSource = ref(false)
const showTopologyList = ref(false)

const selectedNode = computed(() => nodes.value.find((n) => n.id === selectedNodeId.value) || null)
const stampMode = computed(() => !!stampTemplateId.value && !linkMode.value && canEdit.value)

function moveNode(id: string, x: number, y: number) {
  const node = nodes.value.find((n) => n.id === id)
  if (node) {
    node.pos_x = x
    node.pos_y = y
    node.on_canvas = true
  }
}

/** 按模板克隆到画布（拖拽或连续点击） */
function stampAt(templateId: string, x: number, y: number) {
  if (!canEdit.value) return
  const template = nodes.value.find((n) => n.id === templateId)
  if (!template) return
  const created = cloneNodeOntoCanvas(template, x, y, nodes.value)
  nodes.value.push(created)
  selectedNodeId.value = created.id
  ElMessage.success(`已创建：${created.name}`)
}

function placeNode(id: string, x: number, y: number) {
  stampAt(id, x, y)
  stampTemplateId.value = id
}

function onCanvasClick(x: number, y: number) {
  if (!stampTemplateId.value || linkMode.value) return
  stampAt(stampTemplateId.value, x, y)
}

function onPaletteSelect(id: string) {
  selectedNodeId.value = id
  if (canEdit.value && !linkMode.value) {
    stampTemplateId.value = id
    ElMessage.info('放置模式：在画布上多次点击或拖拽创建带序号的设备')
  }
}

function onSelectNode(id: string | null) {
  if (!linkMode.value) {
    selectedNodeId.value = id
    return
  }
  if (!id) return
  if (!linkSourceId.value) {
    linkSourceId.value = id
    selectedNodeId.value = id
    ElMessage.info('已选择本端，请再点击对端设备')
    return
  }
  if (linkSourceId.value === id) {
    ElMessage.warning('请选择另一台设备作为对端')
    return
  }
  openLinkDialog(linkSourceId.value, id, null, true)
  linkSourceId.value = null
}

function openLinkDialog(
  sourceId: string,
  targetId: string | null,
  sourcePort: string | null,
  lockEndpoints: boolean,
  lockSource = false,
) {
  linkDialogSource.value = sourceId
  linkDialogTarget.value = targetId
  linkDialogSourcePort.value = sourcePort
  linkDialogLockEndpoints.value = lockEndpoints
  linkDialogLockSource.value = lockSource
  linkDialogVisible.value = true
}

function toggleLinkMode() {
  linkMode.value = !linkMode.value
  linkSourceId.value = null
  if (linkMode.value) {
    stampTemplateId.value = null
    ElMessage.info('连线模式：依次点击本端与对端设备')
  }
}

function clearStampMode() {
  stampTemplateId.value = null
}

function bindPeerPorts(
  sourceId: string,
  sourcePort: string,
  targetId: string,
  targetPort: string,
  sourceLabel: string | null,
  targetLabel: string | null,
) {
  const source = nodes.value.find((n) => n.id === sourceId)
  const target = nodes.value.find((n) => n.id === targetId)
  if (!source?.port_layout?.ports || !target?.port_layout?.ports) return
  const sp = source.port_layout.ports.find((p) => p.id === sourcePort)
  const tp = target.port_layout.ports.find((p) => p.id === targetPort)
  if (sp) {
    sp.peer_node_id = targetId
    sp.peer_port = targetPort
    sp.peer_label = targetLabel || target.name
  }
  if (tp) {
    tp.peer_node_id = sourceId
    tp.peer_port = sourcePort
    tp.peer_label = sourceLabel || source.name
  }
}

function clearPeerOnPort(nodeId: string, portId: string) {
  const node = nodes.value.find((n) => n.id === nodeId)
  const port = node?.port_layout?.ports?.find((p) => p.id === portId)
  if (!port) return
  const peerId = port.peer_node_id
  const peerPort = port.peer_port
  port.peer_node_id = null
  port.peer_port = null
  port.peer_label = null
  if (peerId && peerPort) {
    const peer = nodes.value.find((n) => n.id === peerId)
    const pp = peer?.port_layout?.ports?.find((p) => p.id === peerPort)
    if (pp && pp.peer_node_id === nodeId && pp.peer_port === portId) {
      pp.peer_node_id = null
      pp.peer_port = null
      pp.peer_label = null
    }
  }
}

function onLinkConfirm(payload: LinkConfirmPayload) {
  const dup = links.value.some(
    (l) =>
      (l.source_node_id === payload.source_node_id &&
        l.source_port === payload.source_port &&
        l.target_node_id === payload.target_node_id &&
        l.target_port === payload.target_port) ||
      (l.source_node_id === payload.target_node_id &&
        l.source_port === payload.target_port &&
        l.target_node_id === payload.source_node_id &&
        l.target_port === payload.source_port),
  )
  if (dup) {
    ElMessage.warning('该接口连线已存在')
    return
  }
  links.value.push({
    id: crypto.randomUUID(),
    topology_id: currentId.value || '',
    link_type: payload.link_type,
    source_node_id: payload.source_node_id,
    source_port: payload.source_port,
    target_node_id: payload.target_node_id,
    target_port: payload.target_port,
    label: payload.label,
    source_label: payload.source_label,
    target_label: payload.target_label,
    cable_type: payload.cable_type,
    interface_class: payload.interface_class,
    link_role: payload.link_role,
  })
  bindPeerPorts(
    payload.source_node_id,
    payload.source_port,
    payload.target_node_id,
    payload.target_port,
    payload.source_label,
    payload.target_label,
  )
  ElMessage.success('连线已添加，请保存')
}

function onConnectPort(portId: string) {
  if (!selectedNodeId.value || !canEdit.value) return
  openLinkDialog(selectedNodeId.value, null, portId, false, true)
}

function onClearPort(portId: string) {
  if (!selectedNodeId.value || !canEdit.value) return
  const nodeId = selectedNodeId.value
  links.value = links.value.filter(
    (l) =>
      !(
        (l.source_node_id === nodeId && l.source_port === portId) ||
        (l.target_node_id === nodeId && l.target_port === portId)
      ),
  )
  clearPeerOnPort(nodeId, portId)
  ElMessage.success('已断开接口，请保存')
}

function onRename(name: string) {
  const node = selectedNode.value
  if (!node || !canEdit.value) return
  node.name = name
}

function unplaceSelected() {
  const node = selectedNode.value
  if (!node || !canEdit.value) return
  node.on_canvas = false
  links.value = links.value.filter(
    (l) => l.source_node_id !== node.id && l.target_node_id !== node.id,
  )
  node.port_layout?.ports?.forEach((p) => {
    if (p.peer_node_id) clearPeerOnPort(node.id, p.id)
  })
  if (stampTemplateId.value === node.id) stampTemplateId.value = null
  selectedNodeId.value = null
  ElMessage.success('已移回待放置列表')
}

async function removeSelected() {
  const node = selectedNode.value
  if (!node || !canEdit.value) return
  try {
    await ElMessageBox.confirm(
      `确定删除设备「${node.name}」？将同时移除其连线，保存后生效。`,
      '删除设备',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  const id = node.id
  links.value = links.value.filter((l) => l.source_node_id !== id && l.target_node_id !== id)
  nodes.value.forEach((n) => {
    n.port_layout?.ports?.forEach((p) => {
      if (p.peer_node_id === id) {
        p.peer_node_id = null
        p.peer_port = null
        p.peer_label = null
      }
    })
  })
  nodes.value = nodes.value.filter((n) => n.id !== id)
  if (stampTemplateId.value === id) stampTemplateId.value = null
  if (linkSourceId.value === id) linkSourceId.value = null
  selectedNodeId.value = null
  ElMessage.success('设备已删除，请保存')
}

async function clearCanvas() {
  if (!canEdit.value || !currentId.value) return
  const placed = nodes.value.filter((n) => n.on_canvas !== false)
  if (!placed.length && !links.value.length) {
    ElMessage.info('画布已是空的')
    return
  }
  try {
    await ElMessageBox.confirm(
      '确定清空画布？将移回所有已放置设备并删除全部连线，设备定义仍保留在左侧列表。',
      '清空布局',
      { type: 'warning', confirmButtonText: '清空', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  links.value = []
  nodes.value.forEach((n) => {
    n.on_canvas = false
    n.port_layout?.ports?.forEach((p) => {
      p.peer_node_id = null
      p.peer_port = null
      p.peer_label = null
    })
  })
  selectedNodeId.value = null
  stampTemplateId.value = null
  linkSourceId.value = null
  linkMode.value = false
  ElMessage.success('画布已清空，请保存')
}

function goToDevice(deviceId: string) {
  void router.push({ path: '/devices', query: { device_id: deviceId } })
}

async function handleCreateTopology(name: string, description: string | null) {
  if (!currentProjectId.value) {
    ElMessage.warning('请先在「设备定义」中创建项目')
    return
  }
  try {
    await createTopology(name, description)
    ElMessage.success('拓扑已创建')
  } catch {
    ElMessage.error('创建失败')
  }
}

async function onProjectChange(id: string) {
  if (!id) return
  selectedNodeId.value = null
  stampTemplateId.value = null
  linkMode.value = false
  linkSourceId.value = null
  await selectProject(id)
}

onMounted(() => {
  void loadProjects()
})
</script>

<template>
  <div class="page" v-loading="loading">
    <el-card shadow="never" class="main-card">
      <div class="layout">
        <aside class="project-side">
          <div class="side-title">项目</div>
          <el-select
            :model-value="currentProjectId"
            placeholder="选择项目"
            style="width: 100%"
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
          <p v-if="currentProject" class="side-hint">{{ currentProject.description || '当前项目画布' }}</p>

          <NetworkDevicePalette
            v-if="currentId"
            :nodes="nodes"
            :selected-node-id="selectedNodeId"
            :stamp-template-id="stampTemplateId"
            @select="onPaletteSelect"
          />

          <el-button link type="primary" class="topo-toggle" @click="showTopologyList = !showTopologyList">
            {{ showTopologyList ? '收起拓扑列表' : '拓扑管理' }}
          </el-button>
          <NetworkTopologyPicker
            v-if="showTopologyList"
            :topologies="topologies"
            :current-id="currentId"
            :loading="loading"
            @select="selectTopology"
            @create="handleCreateTopology"
            @delete="removeTopology"
          />
        </aside>

        <section class="workspace">
          <div class="toolbar">
            <span class="title">拓扑设计</span>
            <span class="hint">
              {{
                stampMode
                  ? '放置中：多次点击或拖拽画布创建带序号设备'
                  : '选中左侧设备后可连续放置；开启连线后依次点两端'
              }}
            </span>
            <el-button v-if="stampMode" @click="clearStampMode">退出放置</el-button>
            <el-button
              v-if="canEdit"
              :type="linkMode ? 'warning' : 'default'"
              :disabled="!currentId"
              @click="toggleLinkMode"
            >
              {{ linkMode ? '退出连线' : '连线' }}
            </el-button>
            <el-button
              v-if="canEdit"
              type="danger"
              plain
              :disabled="!currentId"
              @click="clearCanvas"
            >
              清空画布
            </el-button>
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
            :link-mode="linkMode"
            :link-source-id="linkSourceId"
            :stamp-mode="stampMode"
            @select-node="onSelectNode"
            @move-node="moveNode"
            @place-node="placeNode"
            @canvas-click="onCanvasClick"
          />
          <el-empty v-else description="请先在「设备定义」中创建或选择项目" />
        </section>

        <aside class="inspector">
          <TopologyNodeInspector
            v-if="selectedNode"
            :node="selectedNode"
            :nodes="nodes"
            :links="links"
            :editable="canEdit"
            @connect-port="onConnectPort"
            @clear-port="onClearPort"
            @rename="onRename"
            @unplace="unplaceSelected"
            @remove="removeSelected"
            @go-device="goToDevice"
          />
          <el-empty v-else description="点击画布或列表中的设备查看接口与连线" />
        </aside>
      </div>
    </el-card>

    <TopologyLinkDialog
      v-model="linkDialogVisible"
      :nodes="nodes"
      :links="links"
      :source-node-id="linkDialogSource"
      :target-node-id="linkDialogTarget"
      :source-port="linkDialogSourcePort"
      :lock-endpoints="linkDialogLockEndpoints"
      :lock-source="linkDialogLockSource"
      @confirm="onLinkConfirm"
    />
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
  grid-template-columns: 260px 1fr 320px;
  height: 100%;
}

.project-side {
  border-right: 1px solid #ebeef5;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: auto;
  min-height: 0;
}

.side-title {
  font-weight: 600;
  font-size: 14px;
}

.side-hint {
  margin: 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}

.topo-toggle {
  align-self: flex-start;
  padding: 0;
}

.workspace {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
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
  flex: 1;
}
</style>
