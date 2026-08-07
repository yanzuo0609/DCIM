<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import NetworkModelLibraryPane from '@/components/NetworkModelLibraryPane.vue'
import NetworkTopologyCanvas from '@/components/NetworkTopologyCanvas.vue'
import NetworkTopologyPicker from '@/components/NetworkTopologyPicker.vue'
import TopologyLinkDialog, { type LinkConfirmPayload } from '@/components/TopologyLinkDialog.vue'
import TopologyNodeInspector from '@/components/TopologyNodeInspector.vue'
import DeviceGroupManageDialog, {
  type DeviceGroupMeta,
} from '@/components/DeviceGroupManageDialog.vue'
import { useNetworkTopology } from '@/composables/useNetworkTopology'
import { stampDesignModelOntoCanvas } from '@/utils/designModelToNode'
import { applyWiringRule } from '@/utils/wiringRuleApply'
import {
  CONNECTION_TYPE_OPTIONS,
  FABRIC_ROLE_OPTIONS,
  MEDIA_OPTIONS,
  PORT_PURPOSE_OPTIONS,
  SPEED_OPTIONS,
  applyConnectionTypeSideEffects,
  defaultWiringConfig,
  normalizeWiringConfig,
  type FabricRole,
  type WiringRuleConfig,
} from '@/utils/wiringTypes'
import { resolveNodeFabricRole } from '@/utils/fabricRole'
import {
  createWiringRule,
  deleteWiringRule,
  fetchFolderTree,
  listDesignModels,
  listWiringRules,
  updateWiringRule,
  type NetworkDesignModel,
  type NetworkModelFolderTreeNode,
  type NetworkWiringRule,
} from '@/api/networkModelDesign'
import {
  getLabEngineInfo,
  getTopologyLabConsole,
  getTopologyLabSession,
  refreshTopologyLabStatus,
  startTopologyLab,
  stopTopologyLab,
  syncTopologyLab,
  updateNetworkProject,
  type LabEngineInfo,
  type NetworkLabSession,
} from '@/api/network'
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
const selectedLinkId = ref<string | null>(null)
/** 左侧模型库选中的设计模型：点击画布批量放置 */
const stampDesignModelId = ref<string | null>(null)
const designModels = ref<NetworkDesignModel[]>([])
const folderTree = ref<NetworkModelFolderTreeNode[]>([])
const bindSaving = ref(false)
const labEngine = ref<LabEngineInfo | null>(null)
const labSession = ref<NetworkLabSession | null>(null)
const labBusy = ref(false)
const linkMode = ref(false)
const linkSourceId = ref<string | null>(null)
const linkDialogVisible = ref(false)
const linkDialogSource = ref<string | null>(null)
const linkDialogTarget = ref<string | null>(null)
const linkDialogSourcePort = ref<string | null>(null)
const linkDialogLockEndpoints = ref(true)
const linkDialogLockSource = ref(false)
const wiringDrawerVisible = ref(false)
const wiringRules = ref<NetworkWiringRule[]>([])
const wiringSaving = ref(false)
const wiringEditingId = ref<string | null>(null)
const wiringForm = reactive({
  name: '',
  mode: 'sequential' as 'sequential' | 'manual',
  description: '',
  config: defaultWiringConfig() as WiringRuleConfig,
})

const selectedNode = computed(() => nodes.value.find((n) => n.id === selectedNodeId.value) || null)
const selectedLink = computed(() => links.value.find((l) => l.id === selectedLinkId.value) || null)
const stampMode = computed(
  () => !!stampDesignModelId.value && !linkMode.value && canEdit.value,
)
const canvasNodes = computed(() => nodes.value.filter((n) => n.on_canvas !== false))

const previewSourceCount = computed(() => {
  const cfg = wiringForm.config
  if (cfg.source_node_ids?.length) return cfg.source_node_ids.length
  return canvasNodes.value.filter((n) => {
    if (cfg.source_role && resolveNodeFabricRole(n) !== cfg.source_role) return false
    if (cfg.source_group && (n.device_group || '') !== cfg.source_group) return false
    return !!(cfg.source_role || cfg.source_group)
  }).length
})
const previewTargetCount = computed(() => {
  const cfg = wiringForm.config
  if (cfg.peer_link || cfg.connection_type === 'PEER' || cfg.connection_type === 'DAD') {
    return previewSourceCount.value
  }
  if (cfg.target_node_ids?.length) return cfg.target_node_ids.length
  return canvasNodes.value.filter((n) => {
    if (cfg.target_role && resolveNodeFabricRole(n) !== cfg.target_role) return false
    if (cfg.target_group && (n.device_group || '') !== cfg.target_group) return false
    return !!(cfg.target_role || cfg.target_group)
  }).length
})

const peerSectionEnabled = computed(
  () =>
    !!wiringForm.config.peer_link ||
    wiringForm.config.connection_type === 'PEER' ||
    wiringForm.config.connection_type === 'DAD',
)

const defaultProject = computed(
  () => projects.value.find((p) => (p.code || '').toUpperCase() === 'DEFAULT') || null,
)

function onWiringConnectionTypeChange() {
  applyConnectionTypeSideEffects(wiringForm.config)
}

/** 设备组目录（含尚无成员的新建组）；按拓扑缓存到 sessionStorage */
const deviceGroupCatalog = ref<DeviceGroupMeta[]>([])
const groupDialogVisible = ref(false)
const groupDialogMode = ref<'manage' | 'create'>('manage')
const groupDialogInitial = ref<string | null>(null)
/** 从源/目标哪一侧打开「添加组」，创建后自动写入该侧 */
const groupDialogSide = ref<'source' | 'target' | null>(null)

const deviceGroupOptions = computed(() => {
  const names = new Set<string>()
  for (const g of deviceGroupCatalog.value) {
    if (g.name) names.add(g.name)
  }
  for (const n of canvasNodes.value) {
    const g = (n.device_group || '').trim()
    if (g) names.add(g)
  }
  return [...names].sort((a, b) => a.localeCompare(b, 'zh-CN'))
})

function groupStorageKey() {
  return currentId.value ? `dcim.deviceGroups.${currentId.value}` : null
}

function loadDeviceGroupCatalog() {
  const key = groupStorageKey()
  if (!key) {
    deviceGroupCatalog.value = []
    return
  }
  try {
    const raw = sessionStorage.getItem(key)
    const list = raw ? (JSON.parse(raw) as Array<DeviceGroupMeta & { note?: string }>) : []
    deviceGroupCatalog.value = list
      .filter((g) => g?.name)
      .map((g) => ({
        name: g.name,
        role: g.role ?? null,
        description: (g.description ?? g.note ?? '').toString(),
      }))
  } catch {
    deviceGroupCatalog.value = []
  }
}

function persistDeviceGroupCatalog(list: DeviceGroupMeta[]) {
  deviceGroupCatalog.value = list.map((g) => ({
    name: g.name,
    role: g.role ?? null,
    description: g.description ?? '',
  }))
  const key = groupStorageKey()
  if (key) sessionStorage.setItem(key, JSON.stringify(deviceGroupCatalog.value))
}

function openGroupManager(
  mode: 'manage' | 'create' = 'manage',
  groupName?: string | null,
  side?: 'source' | 'target' | null,
) {
  groupDialogMode.value = mode
  groupDialogInitial.value = groupName || null
  groupDialogSide.value = side ?? null
  groupDialogVisible.value = true
}

function onDeviceGroupCreated(name: string) {
  if (groupDialogSide.value === 'source') {
    wiringForm.config.source_group = name
  } else if (groupDialogSide.value === 'target' && !peerSectionEnabled.value) {
    wiringForm.config.target_group = name
  }
  groupDialogSide.value = null
}

function onAssignDeviceGroup(payload: {
  group: string
  nodeIds: string[]
  role: FabricRole | null
}) {
  const idSet = new Set(payload.nodeIds)
  for (const n of nodes.value) {
    if (!idSet.has(n.id)) continue
    n.device_group = payload.group
    if (payload.role) n.network_role = payload.role
  }
  ensureGroupInCatalog(payload.group, payload.role)
}

/** 检视器单点改组时同步目录 */
function onUpdateNodeMeta(patch: { network_role?: string | null; device_group?: string | null }) {
  const node = selectedNode.value
  if (!node || !canEdit.value) return
  if ('network_role' in patch) node.network_role = patch.network_role ?? null
  if ('device_group' in patch) {
    node.device_group = patch.device_group ?? null
    if (patch.device_group) ensureGroupInCatalog(patch.device_group, null)
  }
}

function ensureGroupInCatalog(name: string, role: FabricRole | null) {
  const trimmed = name.trim()
  if (!trimmed) return
  if (deviceGroupCatalog.value.some((g) => g.name === trimmed)) return
  persistDeviceGroupCatalog([
    ...deviceGroupCatalog.value,
    { name: trimmed, role, description: '' },
  ])
}

function onRemoveGroupMembers(payload: { group: string; nodeIds: string[] }) {
  const idSet = new Set(payload.nodeIds)
  for (const n of nodes.value) {
    if (!idSet.has(n.id)) continue
    if ((n.device_group || '') === payload.group) n.device_group = null
  }
}

function onRenameDeviceGroup(payload: { from: string; to: string }) {
  for (const n of nodes.value) {
    if ((n.device_group || '') === payload.from) n.device_group = payload.to
  }
  if (wiringForm.config.source_group === payload.from) {
    wiringForm.config.source_group = payload.to
  }
  if (wiringForm.config.target_group === payload.from) {
    wiringForm.config.target_group = payload.to
  }
}

function onDeleteDeviceGroup(name: string) {
  for (const n of nodes.value) {
    if ((n.device_group || '') === name) n.device_group = null
  }
  if (wiringForm.config.source_group === name) wiringForm.config.source_group = null
  if (wiringForm.config.target_group === name) wiringForm.config.target_group = null
}

watch(currentId, () => {
  loadDeviceGroupCatalog()
})

function moveNode(id: string, x: number, y: number) {
  const node = nodes.value.find((n) => n.id === id)
  if (node) {
    node.pos_x = x
    node.pos_y = y
    node.on_canvas = true
  }
}

function stampDesignAt(modelId: string, x: number, y: number) {
  if (!canEdit.value || !currentId.value) return
  const model = designModels.value.find((m) => m.id === modelId)
  if (!model) return
  const created = stampDesignModelOntoCanvas(model, currentId.value, x, y, nodes.value)
  nodes.value.push(created)
  selectedNodeId.value = created.id
  ElMessage.success(`已放置模型：${created.name}`)
}

function placeNode(id: string, x: number, y: number) {
  // 兼容画布 drop：若拖入的是模型库中的模型 id 则放置
  if (designModels.value.some((m) => m.id === id)) {
    stampDesignModelId.value = id
    stampDesignAt(id, x, y)
  }
}

function onCanvasClick(x: number, y: number) {
  if (linkMode.value) return
  if (!stampDesignModelId.value) return
  stampDesignAt(stampDesignModelId.value, x, y)
}

function onDesignModelSelect(id: string) {
  if (!canEdit.value || linkMode.value) return
  stampDesignModelId.value = id
  if (!currentId.value) {
    ElMessage.info('已选中模型；请先在右侧「拓扑管理」中新建或选择拓扑后再放置')
    return
  }
  ElMessage.info('模型放置模式：在画布上多次点击批量绘制该模型')
}

function onSelectNode(id: string | null) {
  if (!linkMode.value) {
    selectedLinkId.value = null
    selectedNodeId.value = id
    return
  }
  if (!id) return
  selectedLinkId.value = null
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

function onSelectLink(id: string | null) {
  selectedLinkId.value = id
  if (id) selectedNodeId.value = null
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
    stampDesignModelId.value = null
    ElMessage.info('连线模式：依次点击本端与对端设备')
  }
}

function clearStampMode() {
  stampDesignModelId.value = null
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

function removeLinkById(linkId: string) {
  const link = links.value.find((l) => l.id === linkId)
  if (!link) return false
  clearPeerOnPort(link.source_node_id, link.source_port)
  clearPeerOnPort(link.target_node_id, link.target_port)
  links.value = links.value.filter((l) => l.id !== linkId)
  if (selectedLinkId.value === linkId) selectedLinkId.value = null
  return true
}

async function removeSelectedLink() {
  if (!canEdit.value || !selectedLinkId.value) return
  const link = selectedLink.value
  if (!link) return
  try {
    await ElMessageBox.confirm('确定删除该连线？保存布局后生效。', '删除连线', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  if (removeLinkById(link.id)) {
    ElMessage.success('连线已删除，请保存布局')
  }
}

function onCanvasKeydown(event: KeyboardEvent) {
  if (!canEdit.value) return
  const tag = (event.target as HTMLElement | null)?.tagName?.toLowerCase()
  if (tag === 'input' || tag === 'textarea' || (event.target as HTMLElement)?.isContentEditable) {
    return
  }
  if (event.key !== 'Delete' && event.key !== 'Backspace') return
  if (!selectedLinkId.value) return
  event.preventDefault()
  void removeSelectedLink()
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
  if (stampDesignModelId.value) stampDesignModelId.value = null
  selectedNodeId.value = null
  selectedLinkId.value = null
  ElMessage.success('已从画布移除，请保存')
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
  stampDesignModelId.value = null
  if (linkSourceId.value === id) linkSourceId.value = null
  selectedNodeId.value = null
  selectedLinkId.value = null
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
      '确定清空画布？将移除画布上所有设备并删除全部连线。',
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
  selectedLinkId.value = null
  stampDesignModelId.value = null
  linkSourceId.value = null
  linkMode.value = false
  ElMessage.success('画布已清空，请保存')
}

function goToDevice(deviceId: string) {
  void router.push({ path: '/devices', query: { device_id: deviceId } })
}

async function handleCreateTopology(name: string, description: string | null) {
  if (!currentProjectId.value) {
    ElMessage.warning('项目未就绪，请刷新页面重试')
    return
  }
  try {
    await createTopology(name, description)
    ElMessage.success('拓扑已创建')
  } catch {
    ElMessage.error('创建失败')
  }
}

async function loadFolderTree() {
  try {
    folderTree.value = await fetchFolderTree()
    const rootId = currentProject.value?.model_root_folder_id || null
    if (rootId && designModels.value.length) {
      const scoped = scopeModelsToRoot(rootId, designModels.value)
      designModels.value = scoped
      modelCache.set(rootId, scoped)
    }
  } catch {
    folderTree.value = []
  }
}

function flattenFolderOptions(
  nodes: NetworkModelFolderTreeNode[],
  depth = 0,
): { id: string; label: string }[] {
  const out: { id: string; label: string }[] = []
  for (const n of nodes) {
    const kindTag = n.kind === 'project' ? '项目' : '文件夹'
    out.push({
      id: n.id,
      label: `${'—'.repeat(depth)} ${n.name}（${kindTag}）`,
    })
    out.push(...flattenFolderOptions(n.children || [], depth + 1))
  }
  return out
}

const allFolderOptions = computed(() => flattenFolderOptions(folderTree.value))

function findFolderNode(
  nodes: NetworkModelFolderTreeNode[],
  id: string,
): NetworkModelFolderTreeNode | null {
  for (const n of nodes) {
    if (n.id === id) return n
    const hit = findFolderNode(n.children || [], id)
    if (hit) return hit
  }
  return null
}

/** 所选项目/文件夹及其子目录 ID（用于前端二次收紧，避免串目录） */
function collectScopedFolderIds(rootId: string): Set<string> {
  const ids = new Set<string>([rootId])
  const root = findFolderNode(folderTree.value, rootId)
  if (!root) return ids
  const walk = (n: NetworkModelFolderTreeNode) => {
    ids.add(n.id)
    for (const c of n.children || []) walk(c)
  }
  walk(root)
  return ids
}

function scopeModelsToRoot(rootId: string, items: NetworkDesignModel[]): NetworkDesignModel[] {
  // 树未就绪时信任后端按 folder_id 的结果，避免把子目录模型误滤掉
  if (!findFolderNode(folderTree.value, rootId)) return items
  const allowed = collectScopedFolderIds(rootId)
  return items.filter((m) => !!m.folder_id && allowed.has(m.folder_id))
}

/** 按目录缓存模型列表，切换时优先命中缓存 */
const modelCache = new Map<string, NetworkDesignModel[]>()
let modelsLoadSeq = 0
const modelsLoading = ref(false)

async function loadDesignModelsForProject(explicitRootId?: string | null, opts?: { clearStamp?: boolean }) {
  const rootId =
    explicitRootId !== undefined
      ? explicitRootId
      : currentProject.value?.model_root_folder_id || null
  if (opts?.clearStamp !== false) stampDesignModelId.value = null
  if (!rootId) {
    designModels.value = []
    return
  }
  const cached = modelCache.get(rootId)
  // 无缓存时立即清空，避免继续展示上一个项目/文件夹的模型
  designModels.value = cached ? scopeModelsToRoot(rootId, cached) : []
  const seq = ++modelsLoadSeq
  modelsLoading.value = true
  try {
    const data = await listDesignModels({
      page: 1,
      page_size: 200,
      published_only: false,
      folder_id: rootId,
      // 项目：含子文件夹；文件夹：含其下子树。均不越出所选根节点
      include_descendants: true,
    })
    if (seq !== modelsLoadSeq) return
    const items = scopeModelsToRoot(rootId, data?.items || [])
    modelCache.set(rootId, items)
    designModels.value = items
  } catch (e: unknown) {
    if (seq !== modelsLoadSeq) return
    if (!cached) designModels.value = []
    const msg =
      (e as { response?: { data?: { message?: string } } })?.response?.data?.message ||
      (e instanceof Error ? e.message : '加载模型库失败')
    ElMessage.error(String(msg))
  } finally {
    if (seq === modelsLoadSeq) modelsLoading.value = false
  }
}

async function onModelRootChange(folderId: string | null) {
  const project = defaultProject.value || currentProject.value
  if (!project) {
    ElMessage.warning('项目未就绪，请刷新页面重试')
    return
  }
  const projectId = project.id
  const nextId = folderId || null
  const prev = project.model_root_folder_id || null
  if ((prev || null) === nextId) return

  // 乐观更新：先切目录并拉模型，保存绑定并行进行
  const idx = projects.value.findIndex((p) => p.id === projectId)
  if (idx >= 0) {
    projects.value[idx] = { ...projects.value[idx], model_root_folder_id: nextId }
  }
  stampDesignModelId.value = null
  if (!nextId) {
    designModels.value = []
  } else {
    void loadDesignModelsForProject(nextId, { clearStamp: false })
  }

  bindSaving.value = true
  try {
    const updated = await updateNetworkProject(projectId, {
      model_root_folder_id: nextId,
    })
    if (idx >= 0) {
      projects.value[idx] = { ...projects.value[idx], ...updated }
    }
  } catch (e: unknown) {
    if (idx >= 0) {
      projects.value[idx] = { ...projects.value[idx], model_root_folder_id: prev }
    }
    await loadDesignModelsForProject(prev, { clearStamp: false })
    const msg =
      (e as { response?: { data?: { message?: string } } })?.response?.data?.message ||
      (e instanceof Error ? e.message : '保存模型目录失败')
    ElMessage.error(String(msg))
  } finally {
    bindSaving.value = false
  }
}

async function loadLabInfo() {
  try {
    labEngine.value = await getLabEngineInfo()
  } catch {
    labEngine.value = null
  }
}

async function loadLabSession() {
  if (!currentId.value) {
    labSession.value = null
    return
  }
  try {
    labSession.value = await getTopologyLabSession(currentId.value)
  } catch {
    labSession.value = null
  }
}

async function runLabSync() {
  if (!currentId.value) return
  labBusy.value = true
  try {
    await saveCanvas()
    labSession.value = await syncTopologyLab(currentId.value)
    ElMessage.success('已同步到实验室')
  } catch (e: unknown) {
    const msg =
      (e as { response?: { data?: { message?: string } } })?.response?.data?.message ||
      (e instanceof Error ? e.message : '同步失败')
    ElMessage.error(String(msg))
  } finally {
    labBusy.value = false
  }
}

async function runLabStart() {
  if (!currentId.value) return
  labBusy.value = true
  try {
    labSession.value = await startTopologyLab(currentId.value)
    ElMessage.success('实验室已启动')
  } catch (e: unknown) {
    const msg =
      (e as { response?: { data?: { message?: string } } })?.response?.data?.message ||
      (e instanceof Error ? e.message : '启动失败')
    ElMessage.error(String(msg))
  } finally {
    labBusy.value = false
  }
}

async function runLabStop() {
  if (!currentId.value) return
  labBusy.value = true
  try {
    labSession.value = await stopTopologyLab(currentId.value)
    ElMessage.success('实验室已停止')
  } catch (e: unknown) {
    const msg =
      (e as { response?: { data?: { message?: string } } })?.response?.data?.message ||
      (e instanceof Error ? e.message : '停止失败')
    ElMessage.error(String(msg))
  } finally {
    labBusy.value = false
  }
}

async function runLabRefresh() {
  if (!currentId.value) return
  try {
    labSession.value = await refreshTopologyLabStatus(currentId.value)
  } catch {
    /* ignore */
  }
}

async function openLabConsole() {
  if (!currentId.value || !selectedNodeId.value) {
    ElMessage.info('请先选中画布上的设备')
    return
  }
  try {
    const data = await getTopologyLabConsole(currentId.value, selectedNodeId.value)
    if (data?.console_url) {
      window.open(data.console_url, '_blank')
    } else {
      ElMessage.warning(data?.message || '无控制台地址，请先同步并启动')
    }
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '打开控制台失败')
  }
}

async function loadWiringRules() {
  if (!currentId.value) {
    wiringRules.value = []
    return
  }
  try {
    wiringRules.value = await listWiringRules(currentId.value)
  } catch {
    wiringRules.value = []
  }
}

function resetWiringForm() {
  wiringEditingId.value = null
  wiringForm.name = ''
  wiringForm.mode = 'sequential'
  wiringForm.description = ''
  wiringForm.config = defaultWiringConfig()
}

async function openWiringDrawer() {
  wiringDrawerVisible.value = true
  resetWiringForm()
  await loadWiringRules()
}

function editWiringRule(rule: NetworkWiringRule) {
  wiringEditingId.value = rule.id
  wiringForm.name = rule.name
  wiringForm.mode = (rule.mode as 'sequential' | 'manual') || 'sequential'
  wiringForm.description = rule.description || ''
  wiringForm.config = normalizeWiringConfig((rule.config || {}) as Record<string, unknown>)
}

function buildWiringConfigPayload(): WiringRuleConfig {
  const cfg = normalizeWiringConfig(wiringForm.config as unknown as Record<string, unknown>)
  cfg.max_links = cfg.max_link_count ?? cfg.link_count
  return cfg
}

async function saveWiringRule() {
  if (!currentId.value || !wiringForm.name.trim()) {
    ElMessage.warning('请填写规则名称')
    return
  }
  const cfg = buildWiringConfigPayload()
  const hasExplicit = !!(cfg.source_node_ids?.length && (cfg.peer_link || cfg.target_node_ids?.length))
  const hasRole =
    !!(cfg.source_role || cfg.source_group) &&
    (cfg.peer_link ||
      cfg.connection_type === 'PEER' ||
      cfg.connection_type === 'DAD' ||
      !!(cfg.target_role || cfg.target_group))
  if (!hasExplicit && !hasRole) {
    ElMessage.warning('请按角色/设备组匹配，或显式选择源/目标设备')
    return
  }
  wiringSaving.value = true
  try {
    if (wiringEditingId.value) {
      await updateWiringRule(wiringEditingId.value, {
        name: wiringForm.name.trim(),
        mode: wiringForm.mode,
        enabled: true,
        description: wiringForm.description.trim() || null,
        config: cfg as unknown as Record<string, unknown>,
      })
      ElMessage.success('布线规则已更新')
    } else {
      await createWiringRule({
        topology_id: currentId.value,
        name: wiringForm.name.trim(),
        mode: wiringForm.mode,
        enabled: true,
        description: wiringForm.description.trim() || null,
        config: cfg as unknown as Record<string, unknown>,
      })
      ElMessage.success('布线规则已保存')
    }
    resetWiringForm()
    await loadWiringRules()
  } catch (err: unknown) {
    const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
    ElMessage.error(msg || '保存规则失败')
  } finally {
    wiringSaving.value = false
  }
}

function runWiringRule(rule: NetworkWiringRule) {
  if (!canEdit.value) return
  const { links: created, report } = applyWiringRule(rule, nodes.value, links.value)
  if (report.issues.length) {
    const first = report.issues[0]
    if (!created.length) {
      ElMessage({
        type: first.level === 'error' ? 'error' : 'warning',
        message: `${first.message}（匹配源 ${report.matched_sources} / 目标 ${report.matched_targets}）`,
        duration: 5000,
      })
      return
    }
    ElMessage.warning(
      `已生成 ${created.length} 条；另有 ${report.issues.length} 条提示：${first.message}`,
    )
  } else if (!created.length) {
    ElMessage.warning('未生成新连线（请检查端口是否空闲、设备角色/Purpose 是否匹配）')
    return
  } else {
    ElMessage.success(`已按规则「${rule.name}」自动布线 ${created.length} 条，请保存拓扑；可在接口设计查看连线表`)
  }
  links.value.push(...created)
}

function countLinksByRule(ruleId: string) {
  return links.value.filter((l) => l.wiring_rule_id === ruleId).length
}

async function undoWiringRule(rule: NetworkWiringRule) {
  if (!canEdit.value) return
  const ruleLinks = links.value.filter((l) => l.wiring_rule_id === rule.id)
  if (!ruleLinks.length) {
    ElMessage.info(`规则「${rule.name}」当前没有可撤销的连线`)
    return
  }
  try {
    await ElMessageBox.confirm(
      `撤销规则「${rule.name}」将删除由其生成的 ${ruleLinks.length} 条连线，手动连线不受影响。确认？`,
      '撤销规则执行',
      { type: 'warning', confirmButtonText: '撤销', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  const removeIds = new Set(ruleLinks.map((l) => l.id))
  for (const link of ruleLinks) {
    clearPeerOnPort(link.source_node_id, link.source_port)
    clearPeerOnPort(link.target_node_id, link.target_port)
  }
  links.value = links.value.filter((l) => !removeIds.has(l.id))
  if (selectedLinkId.value && removeIds.has(selectedLinkId.value)) {
    selectedLinkId.value = null
  }
  ElMessage.success(`已撤销 ${ruleLinks.length} 条连线，请保存布局`)
}

async function removeWiringRule(rule: NetworkWiringRule) {
  try {
    await ElMessageBox.confirm(`删除布线规则「${rule.name}」？`, '确认', { type: 'warning' })
    await deleteWiringRule(rule.id)
    await loadWiringRules()
    ElMessage.success('已删除')
  } catch (err: unknown) {
    if (err === 'cancel') return
    ElMessage.error('删除失败')
  }
}

watch(currentId, () => {
  void loadWiringRules()
  void loadLabSession()
})

onMounted(async () => {
  window.addEventListener('keydown', onCanvasKeydown)
  // 拓扑设计页隐藏 DEFAULT，但用其承载拓扑与模型目录绑定
  await loadProjects(null, { preferDefault: true })
  const def = defaultProject.value
  if (def && currentProjectId.value !== def.id) {
    await selectProject(def.id)
  }
  // 先拉文件夹树，再加载模型库，便于按所选根节点收紧范围
  await loadFolderTree()
  await loadDesignModelsForProject()
  loadDeviceGroupCatalog()
  void loadLabInfo()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onCanvasKeydown)
})

function nodeNameById(id: string) {
  return nodes.value.find((n) => n.id === id)?.name || id.slice(0, 8)
}
</script>

<template>
  <div class="page" v-loading="loading">
    <el-card shadow="never" class="main-card">
      <div class="layout">
        <aside class="project-side">
          <div class="side-title">模型库</div>
          <el-select
            :model-value="currentProject?.model_root_folder_id || null"
            placeholder="选择项目或文件夹"
            style="width: 100%"
            filterable
            clearable
            :disabled="!currentProject || !canEdit"
            :loading="bindSaving || modelsLoading"
            @change="onModelRootChange"
          >
            <el-option v-for="f in allFolderOptions" :key="f.id" :label="f.label" :value="f.id" />
          </el-select>

          <NetworkModelLibraryPane
            :root-folder-id="currentProject?.model_root_folder_id || null"
            :models="designModels"
            :selected-model-id="stampDesignModelId"
            :disabled="!canEdit || linkMode"
            :loading="modelsLoading"
            :hide-title="true"
            @select="onDesignModelSelect"
          />
        </aside>

        <section class="workspace">
          <div class="toolbar">
            <span class="title">拓扑设计</span>
            <span class="hint">
              {{
                stampDesignModelId
                  ? '模型放置中：多次点击画布批量绘制'
                  : '选择项目/文件夹后，从左侧模型库放置设备到画布'
              }}
            </span>
            <el-button v-if="stampMode" @click="clearStampMode">退出放置</el-button>
            <el-button
              v-if="canEdit"
              :disabled="!currentId"
              @click="openGroupManager('manage')"
            >
              组管理
            </el-button>
            <el-button v-if="canEdit" :disabled="!currentId" @click="openWiringDrawer">
              布线规则
            </el-button>
            <el-button
              v-if="canEdit"
              :type="linkMode ? 'warning' : 'default'"
              :disabled="!currentId"
              @click="toggleLinkMode"
            >
              {{ linkMode ? '退出连线' : '单点连线' }}
            </el-button>
            <el-button
              v-if="canEdit"
              type="danger"
              plain
              :disabled="!selectedLinkId"
              @click="removeSelectedLink"
            >
              删除连线
            </el-button>
            <el-divider direction="vertical" />
            <el-tooltip
              :content="
                labEngine?.configured
                  ? labEngine.message || `引擎：${labEngine.engine}`
                  : labEngine?.message || '未配置仿真引擎'
              "
              placement="bottom"
            >
              <el-button
                v-if="canEdit"
                :loading="labBusy"
                :disabled="!currentId"
                @click="runLabSync"
              >
                同步实验室
              </el-button>
            </el-tooltip>
            <el-button
              v-if="canEdit"
              type="success"
              plain
              :loading="labBusy"
              :disabled="!currentId"
              @click="runLabStart"
            >
              启动仿真
            </el-button>
            <el-button
              v-if="canEdit"
              :loading="labBusy"
              :disabled="!currentId"
              @click="runLabStop"
            >
              停止
            </el-button>
            <el-button :disabled="!currentId" @click="runLabRefresh">状态</el-button>
            <el-button :disabled="!currentId || !selectedNodeId" @click="openLabConsole">
              控制台
            </el-button>
            <span v-if="labSession" class="lab-status">仿真：{{ labSession.status }}</span>
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
            :selected-link-id="selectedLinkId"
            :link-mode="linkMode"
            :link-source-id="linkSourceId"
            :stamp-mode="stampMode"
            :node-lab-status="labSession?.node_status || null"
            @select-node="onSelectNode"
            @select-link="onSelectLink"
            @move-node="moveNode"
            @place-node="placeNode"
            @canvas-click="onCanvasClick"
          />
          <el-empty
            v-else-if="!currentProject?.model_root_folder_id"
            description="请在左侧选择模型项目或文件夹"
          />
          <el-empty v-else description="请在右侧「拓扑管理」中新建或选择拓扑" />
        </section>

        <aside class="inspector">
          <NetworkTopologyPicker
            title="拓扑管理"
            :topologies="topologies"
            :current-id="currentId"
            :loading="loading"
            @select="selectTopology"
            @create="handleCreateTopology"
            @delete="removeTopology"
          />
          <el-divider />
          <TopologyNodeInspector
            v-if="selectedNode"
            :node="selectedNode"
            :nodes="nodes"
            :links="links"
            :editable="canEdit"
            :group-options="deviceGroupOptions"
            @connect-port="onConnectPort"
            @clear-port="onClearPort"
            @rename="onRename"
            @update-meta="onUpdateNodeMeta"
            @manage-groups="openGroupManager('manage')"
            @unplace="unplaceSelected"
            @remove="removeSelected"
            @go-device="goToDevice"
          />
          <div v-else-if="selectedLink" class="link-inspector">
            <h3>连线详情</h3>
            <p>
              <span class="label">本端</span>
              {{ nodeNameById(selectedLink.source_node_id) }} · {{ selectedLink.source_port }}
            </p>
            <p>
              <span class="label">对端</span>
              {{ nodeNameById(selectedLink.target_node_id) }} · {{ selectedLink.target_port }}
            </p>
            <p>
              <span class="label">标签</span>{{ selectedLink.label || '—' }}
            </p>
            <p>
              <span class="label">类型</span>{{ selectedLink.link_type }}
            </p>
            <p v-if="selectedLink.wiring_rule_id">
              <span class="label">来源</span>布线规则生成
            </p>
            <el-button
              v-if="canEdit"
              type="danger"
              size="small"
              style="margin-top: 8px"
              @click="removeSelectedLink"
            >
              删除连线
            </el-button>
            <p class="hint">也可按 Delete / Backspace 删除</p>
          </div>
          <el-empty v-else description="点击画布设备或连线查看详情" :image-size="64" />
        </aside>
      </div>
    </el-card>

    <el-drawer v-model="wiringDrawerVisible" title="布线规则" size="720px" class="wiring-drawer">
      <p class="wiring-hint">
        按表格分区配置参数；多选项均为下拉。预览匹配：源 {{ previewSourceCount }} 台 /
        目标 {{ previewTargetCount }} 台。执行后请保存拓扑，连线表见「接口设计」。
      </p>

      <div class="wiring-toolbar">
        <el-input
          v-model="wiringForm.name"
          placeholder="规则名称（必填）"
          style="max-width: 280px"
        />
        <el-input
          v-model="wiringForm.description"
          placeholder="说明（可选）"
          style="flex: 1"
        />
      </div>

      <div class="wiring-sheet">
        <!-- 1 设备参数 -->
        <div class="sheet-block">
          <div class="sheet-title">1. 设备参数</div>
          <table class="param-table">
            <tbody>
              <tr>
                <th class="label-cell">连接类型</th>
                <td colspan="3">
                  <el-select
                    v-model="wiringForm.config.connection_type"
                    style="width: 100%"
                    @change="onWiringConnectionTypeChange"
                  >
                    <el-option
                      v-for="o in CONNECTION_TYPE_OPTIONS"
                      :key="o.value"
                      :label="o.label"
                      :value="o.value"
                    />
                  </el-select>
                </td>
              </tr>
              <tr>
                <th class="label-cell">源角色</th>
                <td>
                  <el-select
                    v-model="wiringForm.config.source_role"
                    clearable
                    filterable
                    allow-create
                    default-first-option
                    placeholder="选择或自定义"
                    style="width: 100%"
                  >
                    <el-option
                      v-for="o in FABRIC_ROLE_OPTIONS"
                      :key="o.value"
                      :label="o.label"
                      :value="o.value"
                    />
                  </el-select>
                </td>
                <th class="label-cell">目标角色</th>
                <td>
                  <el-select
                    v-model="wiringForm.config.target_role"
                    clearable
                    filterable
                    allow-create
                    default-first-option
                    placeholder="选择或自定义"
                    style="width: 100%"
                    :disabled="peerSectionEnabled"
                  >
                    <el-option
                      v-for="o in FABRIC_ROLE_OPTIONS"
                      :key="o.value"
                      :label="o.label"
                      :value="o.value"
                    />
                  </el-select>
                </td>
              </tr>
              <tr>
                <th class="label-cell">源设备组</th>
                <td>
                  <el-select
                    v-model="wiringForm.config.source_group"
                    clearable
                    filterable
                    placeholder="选择设备组"
                    style="width: 100%"
                  >
                    <el-option v-for="g in deviceGroupOptions" :key="g" :label="g" :value="g" />
                  </el-select>
                  <div class="group-actions">
                    <el-button
                      v-if="!deviceGroupOptions.length"
                      type="primary"
                      link
                      size="small"
                      @click="openGroupManager('create', null, 'source')"
                    >
                      添加组
                    </el-button>
                    <template v-else>
                      <el-button type="primary" link size="small" @click="openGroupManager('manage')">
                        管理组
                      </el-button>
                      <el-button
                        link
                        size="small"
                        @click="openGroupManager('create', null, 'source')"
                      >
                        添加组
                      </el-button>
                      <el-button
                        v-if="wiringForm.config.source_group"
                        link
                        size="small"
                        @click="openGroupManager('manage', wiringForm.config.source_group)"
                      >
                        {{ wiringForm.config.source_group }} · 添加设备
                      </el-button>
                    </template>
                  </div>
                </td>
                <th class="label-cell">目标设备组</th>
                <td>
                  <el-select
                    v-model="wiringForm.config.target_group"
                    clearable
                    filterable
                    placeholder="选择设备组"
                    style="width: 100%"
                    :disabled="peerSectionEnabled"
                  >
                    <el-option v-for="g in deviceGroupOptions" :key="g" :label="g" :value="g" />
                  </el-select>
                  <div class="group-actions">
                    <el-button
                      v-if="!deviceGroupOptions.length"
                      type="primary"
                      link
                      size="small"
                      :disabled="peerSectionEnabled"
                      @click="openGroupManager('create', null, 'target')"
                    >
                      添加组
                    </el-button>
                    <template v-else>
                      <el-button
                        type="primary"
                        link
                        size="small"
                        :disabled="peerSectionEnabled"
                        @click="openGroupManager('manage')"
                      >
                        管理组
                      </el-button>
                      <el-button
                        link
                        size="small"
                        :disabled="peerSectionEnabled"
                        @click="openGroupManager('create', null, 'target')"
                      >
                        添加组
                      </el-button>
                      <el-button
                        v-if="wiringForm.config.target_group"
                        link
                        size="small"
                        :disabled="peerSectionEnabled"
                        @click="openGroupManager('manage', wiringForm.config.target_group)"
                      >
                        {{ wiringForm.config.target_group }} · 添加设备
                      </el-button>
                    </template>
                  </div>
                </td>
              </tr>
              <tr>
                <th class="label-cell">源设备(可选)</th>
                <td>
                  <el-select
                    v-model="wiringForm.config.source_node_ids"
                    multiple
                    filterable
                    clearable
                    collapse-tags
                    collapse-tags-tooltip
                    placeholder="不选则按角色/组匹配"
                    style="width: 100%"
                  >
                    <el-option
                      v-for="n in canvasNodes"
                      :key="n.id"
                      :label="`${n.name} [${resolveNodeFabricRole(n)}]${n.device_group ? ' · ' + n.device_group : ''}`"
                      :value="n.id"
                    />
                  </el-select>
                </td>
                <th class="label-cell">目标设备(可选)</th>
                <td>
                  <el-select
                    v-model="wiringForm.config.target_node_ids"
                    multiple
                    filterable
                    clearable
                    collapse-tags
                    collapse-tags-tooltip
                    placeholder="不选则按角色/组匹配"
                    style="width: 100%"
                    :disabled="peerSectionEnabled"
                  >
                    <el-option
                      v-for="n in canvasNodes"
                      :key="n.id"
                      :label="`${n.name} [${resolveNodeFabricRole(n)}]${n.device_group ? ' · ' + n.device_group : ''}`"
                      :value="n.id"
                    />
                  </el-select>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 2 端口参数 -->
        <div class="sheet-block">
          <div class="sheet-title">2. 端口参数</div>
          <table class="param-table">
            <tbody>
              <tr>
                <th class="label-cell">源端口</th>
                <td>
                  <el-select
                    v-model="wiringForm.config.source_port_purpose"
                    clearable
                    style="width: 100%"
                  >
                    <el-option
                      v-for="o in PORT_PURPOSE_OPTIONS"
                      :key="o.value"
                      :label="o.label"
                      :value="o.value"
                    />
                  </el-select>
                </td>
                <th class="label-cell">端口范围</th>
                <td>
                  <el-input
                    v-model="wiringForm.config.source_port_range"
                    placeholder="如 49-52"
                    clearable
                  />
                </td>
              </tr>
              <tr>
                <th class="label-cell">目的端口</th>
                <td>
                  <el-select
                    v-model="wiringForm.config.target_port_purpose"
                    clearable
                    style="width: 100%"
                  >
                    <el-option
                      v-for="o in PORT_PURPOSE_OPTIONS"
                      :key="o.value"
                      :label="o.label"
                      :value="o.value"
                    />
                  </el-select>
                </td>
                <th class="label-cell">端口范围</th>
                <td>
                  <el-input
                    v-model="wiringForm.config.target_port_range"
                    placeholder="如 1-40"
                    clearable
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 3 互联/DAD -->
        <div class="sheet-block">
          <div class="sheet-title">3. 互联/DAD参数</div>
          <table class="param-table">
            <tbody>
              <tr>
                <th class="label-cell">peer-link</th>
                <td>
                  <span class="inline-label">启用开关</span>
                  <el-switch v-model="wiringForm.config.peer_link" />
                </td>
                <th class="label-cell">模式</th>
                <td>
                  <el-select
                    v-model="wiringForm.config.lag_mode"
                    :disabled="!peerSectionEnabled"
                    style="width: 100%"
                  >
                    <el-option label="LACP" value="LACP" />
                    <el-option label="STATIC" value="STATIC" />
                  </el-select>
                </td>
              </tr>
              <tr>
                <th class="label-cell">速率</th>
                <td>
                  <el-select
                    v-model="wiringForm.config.peer_link_speed"
                    :disabled="!peerSectionEnabled"
                    style="width: 100%"
                  >
                    <el-option v-for="s in SPEED_OPTIONS" :key="s" :label="s" :value="s" />
                  </el-select>
                </td>
                <th class="label-cell">peer-link条数</th>
                <td>
                  <el-input-number
                    v-model="wiringForm.config.peer_link_count"
                    :min="1"
                    :max="64"
                    :disabled="!peerSectionEnabled"
                    controls-position="right"
                    style="width: 100%"
                  />
                </td>
              </tr>
              <tr>
                <th class="label-cell">端口范围</th>
                <td colspan="3">
                  <el-input
                    v-model="wiringForm.config.peer_port_range"
                    placeholder="Peer/DAD 专用端口范围，如 45-46"
                    clearable
                    :disabled="!peerSectionEnabled"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 4 介质与距离 -->
        <div class="sheet-block">
          <div class="sheet-title">4. 介质/与距离</div>
          <table class="param-table">
            <tbody>
              <tr>
                <th class="label-cell">介质</th>
                <td colspan="3">
                  <el-select v-model="wiringForm.config.media" style="width: 100%">
                    <el-option
                      v-for="o in MEDIA_OPTIONS"
                      :key="o.value"
                      :label="o.label"
                      :value="o.value"
                    />
                  </el-select>
                </td>
              </tr>
              <tr>
                <th class="label-cell">距离</th>
                <td>
                  <el-select v-model="wiringForm.config.distance_mode" style="width: 100%">
                    <el-option label="AUTO" value="AUTO" />
                    <el-option label="FIXED" value="FIXED" />
                  </el-select>
                </td>
                <th class="label-cell">单位米 (m)</th>
                <td>
                  <el-input-number
                    v-model="wiringForm.config.max_distance_m"
                    :min="0"
                    :max="10000"
                    :step="0.5"
                    controls-position="right"
                    style="width: 100%"
                  />
                </td>
              </tr>
              <tr>
                <th class="label-cell">标签模板</th>
                <td colspan="3">
                  <el-input
                    v-model="wiringForm.config.label_template"
                    placeholder="{conn}-{seq:02d}"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="wiring-actions">
        <el-button type="primary" :loading="wiringSaving" @click="saveWiringRule">
          {{ wiringEditingId ? '更新规则' : '保存规则' }}
        </el-button>
        <el-button v-if="wiringEditingId" @click="resetWiringForm">取消编辑</el-button>
      </div>

      <el-divider>已保存规则</el-divider>
      <div v-if="!wiringRules.length" class="wiring-empty">暂无规则</div>
      <div v-for="rule in wiringRules" :key="rule.id" class="wiring-rule">
        <div>
          <strong>{{ rule.name }}</strong>
          <span class="meta">
            {{ (rule.config as Record<string, unknown>)?.connection_type || rule.mode }}
          </span>
        </div>
        <div class="actions">
          <el-button size="small" @click="editWiringRule(rule)">编辑</el-button>
          <el-button size="small" type="primary" @click="runWiringRule(rule)">执行布线</el-button>
          <el-button
            size="small"
            type="warning"
            plain
            :disabled="!countLinksByRule(rule.id)"
            @click="undoWiringRule(rule)"
          >
            撤销执行{{ countLinksByRule(rule.id) ? ` (${countLinksByRule(rule.id)})` : '' }}
          </el-button>
          <el-button size="small" type="danger" plain @click="removeWiringRule(rule)">删除</el-button>
        </div>
      </div>
    </el-drawer>

    <DeviceGroupManageDialog
      v-model="groupDialogVisible"
      :nodes="nodes"
      :catalog="deviceGroupCatalog"
      :mode="groupDialogMode"
      :initial-group="groupDialogInitial"
      @update:catalog="persistDeviceGroupCatalog"
      @created="onDeviceGroupCreated"
      @assign="onAssignDeviceGroup"
      @remove-members="onRemoveGroupMembers"
      @rename-group="onRenameDeviceGroup"
      @delete-group="onDeleteDeviceGroup"
    />

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
  padding: 12px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}

.inspector :deep(.topology-picker) {
  flex-shrink: 0;
  max-height: 240px;
}

.inspector :deep(.el-divider) {
  margin: 8px 0;
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

.lab-status {
  font-size: 12px;
  color: #409eff;
  margin-right: 4px;
}

.wiring-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}

.wiring-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.wiring-sheet {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sheet-block {
  border: 1px solid #dcdfe6;
  border-radius: 2px;
  overflow: hidden;
  background: #fff;
}

.sheet-title {
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  background: #f5f7fa;
  border-bottom: 1px solid #dcdfe6;
}

.param-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 13px;
}

.param-table th,
.param-table td {
  border: 1px solid #ebeef5;
  padding: 6px 8px;
  vertical-align: middle;
}

.param-table .label-cell {
  width: 112px;
  background: #fafafa;
  color: #606266;
  font-weight: 500;
  text-align: left;
  white-space: nowrap;
}

.param-table :deep(.el-input),
.param-table :deep(.el-select),
.param-table :deep(.el-input-number) {
  width: 100%;
}

.inline-label {
  margin-right: 8px;
  color: #909399;
  font-size: 12px;
}

.group-actions {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
  min-height: 22px;
}

.wiring-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}

.sep {
  margin: 0 6px;
  color: #909399;
}

.wiring-empty {
  color: #909399;
  font-size: 13px;
}

.wiring-rule {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 10px 0;
  border-bottom: 1px solid #ebeef5;
}

.wiring-rule .meta {
  margin-left: 8px;
  color: #909399;
  font-size: 12px;
}

.wiring-rule .actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.link-inspector h3 {
  margin: 0 0 12px;
  font-size: 15px;
}

.link-inspector p {
  margin: 0 0 8px;
  font-size: 13px;
}

.link-inspector .label {
  display: inline-block;
  min-width: 40px;
  color: #909399;
  font-size: 12px;
  margin-right: 6px;
}

.link-inspector .hint {
  margin-top: 10px;
  font-size: 12px;
  color: #909399;
}
</style>
