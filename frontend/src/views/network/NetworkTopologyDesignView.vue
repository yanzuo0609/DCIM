<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import NetworkModelLibraryPane from '@/components/NetworkModelLibraryPane.vue'
import NetworkTopologyCanvas from '@/components/NetworkTopologyCanvas.vue'
import NetworkTopologyPicker from '@/components/NetworkTopologyPicker.vue'
import NetworkDeviceGroupListPane from '@/components/NetworkDeviceGroupListPane.vue'
import TopologyLinkDialog, { type LinkConfirmPayload } from '@/components/TopologyLinkDialog.vue'
import TopologyNodeInspector from '@/components/TopologyNodeInspector.vue'
import DeviceGroupManageDialog, {
  type DeviceGroupMeta,
  type DeviceGroupPortRef,
} from '@/components/DeviceGroupManageDialog.vue'
import DeviceGroupDetailDialog from '@/components/DeviceGroupDetailDialog.vue'
import { useNetworkTopology } from '@/composables/useNetworkTopology'
import { stampDesignModelOntoCanvas, syncTopologyNodesFromDesignModels } from '@/utils/designModelToNode'
import {
  addNodeToGroup,
  nodeGroupList,
  nodeInGroup,
  removeNodeFromGroup,
  renameNodeGroup,
  setNodeGroups,
} from '@/utils/deviceGroups'
import {
  buildWiringGroupSelectOptions,
  materializeGroupSlots,
  migrateSlotsFromLegacy,
  parentGroupNamesFromRefs,
  parseSubgroupRef,
  subgroupRef,
  summarizeSlots,
  totalSlotCount,
} from '@/utils/deviceGroupSlots'
import {
  layoutGroupGrid,
} from '@/utils/deviceGroupVisual'
import { applyWiringRule, previewWiringPairs, previewWiringScenario, listFreePortOptions, type ProposedPair } from '@/utils/wiringRuleApply'
import {
  ALLOCATION_MODE_OPTIONS,
  CONNECTION_TYPE_OPTIONS,
  FABRIC_ROLE_OPTIONS,
  INTERCONNECT_SCOPE_OPTIONS,
  MEDIA_OPTIONS,
  PORT_POLICY_OPTIONS,
  PORT_PURPOSE_OPTIONS,
  SPEED_OPTIONS,
  applyConnectionTypeSideEffects,
  connectionTypeLabel,
  defaultWiringConfig,
  isSwitchInterconnect,
  normalizeWiringConfig,
  poolFromPurpose,
  resolveWiringGroups,
  type FabricRole,
  type WiringPair,
  type WiringRuleConfig,
} from '@/utils/wiringTypes'
import {
  principleBulletsForScenario,
  principleHintsForConnection,
} from '@/utils/wiringPrinciples'
import {
  addCustomPortMediaType,
  applyPortMediaToRuleConfig,
  listPortMediaTypes,
  type PortMediaTypeDef,
} from '@/utils/portMediaCatalog'
import { matchWiringEndpoints } from '@/utils/wiring/matchEndpoints'
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
  type NetworkNode,
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

const previewSourceNodes = computed(() => {
  const cfg = wiringForm.config
  return matchWiringEndpoints(nodes.value, {
    ids: cfg.source_node_ids,
    role: cfg.source_role,
    groups: resolveWiringGroups(cfg.source_groups, cfg.source_group),
  })
})

const previewTargetNodes = computed(() => {
  const cfg = wiringForm.config
  // 组内互联：源=目标，必须同组设备
  if (
    (cfg.peer_link || isSwitchInterconnect(cfg.connection_type)) &&
    (cfg.interconnect_scope || 'INTRA_GROUP') === 'INTRA_GROUP'
  ) {
    return previewSourceNodes.value
  }
  return matchWiringEndpoints(nodes.value, {
    ids: cfg.target_node_ids,
    role: cfg.target_role,
    groups: resolveWiringGroups(cfg.target_groups, cfg.target_group),
  })
})

/** 按 18-rules 场景路由预览（只读） */
const detectedWiringScenario = computed(() => {
  const rule = {
    id: wiringEditingId.value || 'preview',
    topology_id: currentId.value || '',
    name: wiringForm.name || 'preview',
    mode: wiringForm.mode,
    enabled: true,
    description: null,
    config: wiringForm.config,
  } as NetworkWiringRule
  return previewWiringScenario(rule, nodes.value)
})
const previewSourceCount = computed(() => previewSourceNodes.value.length)
const previewTargetCount = computed(() => previewTargetNodes.value.length)

const isAutoAlloc = computed(
  () => String(wiringForm.config.allocation_mode || 'AUTO').toUpperCase() === 'AUTO',
)
const isManualAlloc = computed(
  () => String(wiringForm.config.allocation_mode || '').toUpperCase() === 'MANUAL',
)
const isHybridAlloc = computed(
  () => String(wiringForm.config.allocation_mode || '').toUpperCase() === 'HYBRID',
)

const wiringPrinciple = computed(() => {
  const base = principleHintsForConnection(wiringForm.config.connection_type)
  const extra = principleBulletsForScenario(detectedWiringScenario.value.scenario)
  return {
    ...base,
    bullets: [...base.bullets, ...extra],
  }
})

const portMediaTypeOptions = ref<PortMediaTypeDef[]>(listPortMediaTypes())

function refreshPortMediaOptions() {
  portMediaTypeOptions.value = listPortMediaTypes()
}

function onPortMediaChange() {
  const raw = String(wiringForm.config.port_media || '').trim()
  if (!raw || raw === 'AUTO') {
    applyPortMediaToRuleConfig(wiringForm.config)
    return
  }
  const known = listPortMediaTypes().find((x) => x.value === raw || x.label === raw)
  if (!known) {
    try {
      const def = addCustomPortMediaType(raw)
      refreshPortMediaOptions()
      wiringForm.config.port_media = def.value
    } catch {
      /* ignore duplicate */
    }
  } else if (known.label === raw && known.value !== raw) {
    wiringForm.config.port_media = known.value
  }
  applyPortMediaToRuleConfig(wiringForm.config)
}

async function openAddPortMediaDialog() {
  try {
    const { value } = await ElMessageBox.prompt('输入新的端口介质名称', '添加介质类型', {
      confirmButtonText: '添加',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：MPO12芯光纤、LC-SC光纤跳线',
      inputPattern: /\S+/,
      inputErrorMessage: '名称不能为空',
    })
    const def = addCustomPortMediaType(String(value || '').trim())
    refreshPortMediaOptions()
    wiringForm.config.port_media = def.value
    onPortMediaChange()
    ElMessage.success(`已添加介质「${def.label}」`)
  } catch {
    /* cancel */
  }
}

const occupiedPortKeys = computed(() => {
  const set = new Set<string>()
  for (const l of links.value) {
    set.add(`${l.source_node_id}:${l.source_port}`)
    set.add(`${l.target_node_id}:${l.target_port}`)
  }
  return set
})

/** 端口参数仅可选设备参数匹配到的源/目标（同台或同组） */
const sourceDeviceOptions = computed(() =>
  previewSourceNodes.value.map((n) => ({
    id: n.id,
    name: n.name,
    groups: nodeGroupList(n).join('/') || '—',
  })),
)
const targetDeviceOptions = computed(() =>
  previewTargetNodes.value.map((n) => ({
    id: n.id,
    name: n.name,
    groups: nodeGroupList(n).join('/') || '—',
  })),
)

const devicePortLinkHint = computed(() => {
  const s = previewSourceCount.value
  const t = previewTargetCount.value
  if (!s && !t) return '请先在「1. 设备参数」选择角色/设备组或显式设备，端口下拉才会出现可选设备。'
  if (peerSectionEnabled.value && isIntraInterconnect.value) {
    return `组内互联：源与目标共用同一组匹配结果（${s} 台）。端口对两端须为组内不同设备。`
  }
  return `端口选择已关联设备参数：源 ${s} 台 · 目标 ${t} 台（仅这些设备的空闲口可选）。`
})

function ensureManualPairs() {
  if (!Array.isArray(wiringForm.config.pairs)) wiringForm.config.pairs = []
}

function onAllocationModeChange() {
  const mode = String(wiringForm.config.allocation_mode || 'AUTO').toUpperCase()
  if (mode === 'MANUAL') {
    ensureManualPairs()
    pruneManualPairsAgainstDevices()
    if (!wiringForm.config.pairs!.length) addManualPairRow()
  }
}

function addManualPairRow() {
  ensureManualPairs()
  const srcs = previewSourceNodes.value
  const tgts = previewTargetNodes.value
  if (!srcs.length || !tgts.length) {
    ElMessage.warning('请先在设备参数中匹配源/目标设备（角色或设备组）')
    return
  }
  const src = srcs[0]
  // 组内互联：目标默认选组内另一台
  let tgt = tgts.find((n) => n.id !== src.id) || tgts[0]
  if (peerSectionEnabled.value && isIntraInterconnect.value && tgt.id === src.id && tgts.length < 2) {
    ElMessage.warning('组内互联至少需要同组 2 台设备')
    return
  }
  const sp = listFreePortOptions(src, occupiedPortKeys.value)[0]
  const tp = listFreePortOptions(tgt, occupiedPortKeys.value)[0]
  wiringForm.config.pairs!.push({
    source_node_id: src.id,
    source_port_id: sp?.id || '',
    target_node_id: tgt.id,
    target_port_id: tp?.id || '',
  })
}

function removeManualPairRow(idx: number) {
  ensureManualPairs()
  wiringForm.config.pairs!.splice(idx, 1)
}

function portsForNodeInForm(nodeId: string) {
  const allowed = new Set([
    ...previewSourceNodes.value.map((n) => n.id),
    ...previewTargetNodes.value.map((n) => n.id),
  ])
  if (!nodeId || !allowed.has(nodeId)) return []
  const n = nodes.value.find((x) => x.id === nodeId)
  if (!n) return []
  return listFreePortOptions(n, occupiedPortKeys.value)
}

/** 设备参数变更后：清掉不在匹配集合内的端口对 */
function pruneManualPairsAgainstDevices() {
  if (!Array.isArray(wiringForm.config.pairs)) return
  const srcIds = new Set(previewSourceNodes.value.map((n) => n.id))
  const tgtIds = new Set(previewTargetNodes.value.map((n) => n.id))
  wiringForm.config.pairs = wiringForm.config.pairs.filter((p) => {
    if (!p.source_node_id || !p.target_node_id) return false
    if (!srcIds.has(p.source_node_id) || !tgtIds.has(p.target_node_id)) return false
    // 组内：禁止自己连自己
    if (
      peerSectionEnabled.value &&
      isIntraInterconnect.value &&
      p.source_node_id === p.target_node_id
    ) {
      return false
    }
    return true
  })
  // 端口若已不属于该设备空闲口则清空口号，留给用户重选
  for (const p of wiringForm.config.pairs) {
    const srcPorts = portsForNodeInForm(p.source_node_id).map((o) => o.id)
    const tgtPorts = portsForNodeInForm(p.target_node_id).map((o) => o.id)
    if (p.source_port_id && !srcPorts.includes(p.source_port_id)) p.source_port_id = ''
    if (p.target_port_id && !tgtPorts.includes(p.target_port_id)) p.target_port_id = ''
  }
}

function onManualSourceDeviceChange(row: WiringPair) {
  row.source_port_id = ''
  if (
    peerSectionEnabled.value &&
    isIntraInterconnect.value &&
    row.source_node_id &&
    row.source_node_id === row.target_node_id
  ) {
    const other = previewTargetNodes.value.find((n) => n.id !== row.source_node_id)
    row.target_node_id = other?.id || ''
    row.target_port_id = ''
  }
}

function onManualTargetDeviceChange(row: WiringPair) {
  row.target_port_id = ''
  if (
    peerSectionEnabled.value &&
    isIntraInterconnect.value &&
    row.target_node_id &&
    row.source_node_id === row.target_node_id
  ) {
    ElMessage.warning('组内互联请选择同组内的另一台设备')
    const other = previewTargetNodes.value.find((n) => n.id !== row.source_node_id)
    row.target_node_id = other?.id || ''
  }
}

const pairPreviewVisible = ref(false)
const pairPreviewLoading = ref(false)
const pairPreviewRule = ref<NetworkWiringRule | null>(null)
const pairPreviewRows = ref<ProposedPair[]>([])
const pairPreviewScenario = ref('')

function onSourcePurposeChange() {
  if (!wiringForm.config.source_port_pool || wiringForm.config.source_port_pool === 'AUTO') {
    wiringForm.config.source_port_pool = poolFromPurpose(wiringForm.config.source_port_purpose)
  }
}

function onTargetPurposeChange() {
  if (!wiringForm.config.target_port_pool || wiringForm.config.target_port_pool === 'AUTO') {
    wiringForm.config.target_port_pool = poolFromPurpose(wiringForm.config.target_port_purpose)
  }
}

const peerSectionEnabled = computed(() => isSwitchInterconnect(wiringForm.config.connection_type))
const isIntraInterconnect = computed(
  () => (wiringForm.config.interconnect_scope || 'INTRA_GROUP') === 'INTRA_GROUP',
)

function syncIntraGroupTargets() {
  if (!peerSectionEnabled.value || !isIntraInterconnect.value) return
  const cfg = wiringForm.config
  cfg.target_groups = [...(cfg.source_groups || [])]
  cfg.target_group = cfg.source_groups?.[0] ?? null
  cfg.target_role = cfg.source_role
  cfg.target_node_ids = [...(cfg.source_node_ids || [])]
}

function onInterconnectScopeChange() {
  if (!peerSectionEnabled.value) return
  if (wiringForm.config.interconnect_scope === 'INTER_GROUP') {
    wiringForm.config.allocation_mode = 'MANUAL'
    // 组间：目标组与源组分开，清空与源相同的目标以免误配
    if (
      JSON.stringify(wiringForm.config.target_groups || []) ===
      JSON.stringify(wiringForm.config.source_groups || [])
    ) {
      wiringForm.config.target_groups = []
      wiringForm.config.target_group = null
      wiringForm.config.target_node_ids = []
    }
    onAllocationModeChange()
  } else {
    wiringForm.config.allocation_mode = 'AUTO'
    syncIntraGroupTargets()
  }
  pruneManualPairsAgainstDevices()
}

function ensureGroupList(side: 'source' | 'target'): string[] {
  const cfg = wiringForm.config
  if (side === 'source') {
    if (!Array.isArray(cfg.source_groups)) cfg.source_groups = []
    return cfg.source_groups
  }
  if (!Array.isArray(cfg.target_groups)) cfg.target_groups = []
  return cfg.target_groups
}

function syncLegacyGroupFields() {
  const cfg = wiringForm.config
  cfg.source_groups = resolveWiringGroups(cfg.source_groups, cfg.source_group)
  cfg.target_groups = resolveWiringGroups(cfg.target_groups, cfg.target_group)
  cfg.source_group = cfg.source_groups[0] ?? null
  cfg.target_group = cfg.target_groups[0] ?? null
  syncIntraGroupTargets()
  pruneManualPairsAgainstDevices()
}

function addGroupToSide(side: 'source' | 'target', name: string) {
  const trimmed = name.trim()
  if (!trimmed) return
  const list = ensureGroupList(side)
  if (!list.includes(trimmed)) list.push(trimmed)
  syncLegacyGroupFields()
}

function renameGroupInConfig(from: string, to: string) {
  const mapOne = (g: string) => {
    if (g === from) return to
    const sub = parseSubgroupRef(g)
    if (sub && sub.groupName === from) return subgroupRef(to, sub.slotId)
    return g
  }
  const mapList = (list: string[] | undefined) =>
    (list || []).map(mapOne).filter((g, i, arr) => arr.indexOf(g) === i)
  wiringForm.config.source_groups = mapList(wiringForm.config.source_groups)
  wiringForm.config.target_groups = mapList(wiringForm.config.target_groups)
  syncLegacyGroupFields()
}

function removeGroupFromConfig(name: string) {
  const drop = (g: string) => {
    if (g === name) return false
    const sub = parseSubgroupRef(g)
    if (sub && sub.groupName === name) return false
    return true
  }
  wiringForm.config.source_groups = (wiringForm.config.source_groups || []).filter(drop)
  wiringForm.config.target_groups = (wiringForm.config.target_groups || []).filter(drop)
  syncLegacyGroupFields()
}

function onPeerLinkToggle(on: boolean | string | number) {
  const enabled = !!on
  wiringForm.config.peer_link = enabled
  if (enabled) {
    if (!isSwitchInterconnect(wiringForm.config.connection_type)) {
      wiringForm.config.connection_type = 'SWITCH_INTERCONNECT'
      applyConnectionTypeSideEffects(wiringForm.config)
    } else {
      wiringForm.config.peer_link = true
    }
    wiringForm.config.interconnect_scope = wiringForm.config.interconnect_scope || 'INTRA_GROUP'
    syncIntraGroupTargets()
  } else if (isSwitchInterconnect(wiringForm.config.connection_type)) {
    wiringForm.config.connection_type = 'CORE_TO_ACCESS'
    applyConnectionTypeSideEffects(wiringForm.config)
  }
  pruneManualPairsAgainstDevices()
}

const defaultProject = computed(
  () => projects.value.find((p) => (p.code || '').toUpperCase() === 'DEFAULT') || null,
)

function onWiringConnectionTypeChange() {
  applyConnectionTypeSideEffects(wiringForm.config)
  if (isSwitchInterconnect(wiringForm.config.connection_type)) {
    wiringForm.config.interconnect_scope = wiringForm.config.interconnect_scope || 'INTRA_GROUP'
    syncIntraGroupTargets()
  }
  onAllocationModeChange()
  pruneManualPairsAgainstDevices()
}

function onDeviceMatchChange() {
  syncIntraGroupTargets()
  pruneManualPairsAgainstDevices()
}

watch(
  () => [
    wiringForm.config.source_role,
    wiringForm.config.target_role,
    ...(wiringForm.config.source_groups || []),
    ...(wiringForm.config.target_groups || []),
    ...(wiringForm.config.source_node_ids || []),
    ...(wiringForm.config.target_node_ids || []),
    wiringForm.config.interconnect_scope,
    wiringForm.config.connection_type,
  ],
  () => {
    onDeviceMatchChange()
  },
)

/** 设备组目录（含尚无成员的新建组）；按拓扑缓存到 localStorage，成员关系随节点持久化 */
const deviceGroupCatalog = ref<DeviceGroupMeta[]>([])
const groupDialogVisible = ref(false)
const groupDialogMode = ref<'manage' | 'create'>('manage')
const groupDialogInitial = ref<string | null>(null)
/** 从源/目标哪一侧打开「添加组」，创建后自动写入该侧 */
const groupDialogSide = ref<'source' | 'target' | null>(null)
const selectedGroupName = ref<string | null>(null)
const groupDetailVisible = ref(false)
const groupDetailName = ref<string | null>(null)
/** 画布显示：逐台设备 / 按组简化 */
const canvasViewMode = ref<'devices' | 'groups'>('devices')
/** 左侧手风琴：一次只展开一项 */
const sideAccordion = ref<'models' | 'topology' | 'groups' | 'rules'>('models')

const groupRolesMap = computed(() => {
  const m: Record<string, FabricRole | null> = {}
  for (const g of deviceGroupCatalog.value) {
    m[g.name] = g.role ?? null
  }
  return m
})

const deviceGroupOptions = computed(() => {
  // 整组 + 子组，供布线源/目标选择
  return buildWiringGroupSelectOptions(deviceGroupCatalog.value)
})

const deviceGroupOptionValues = computed(() => deviceGroupOptions.value.map((o) => o.value))

/** 检视器仅展示父组名（子组由放置时自动打标） */
const deviceGroupParentNames = computed(() =>
  deviceGroupCatalog.value
    .map((g) => g.name)
    .filter(Boolean)
    .sort((a, b) => a.localeCompare(b, 'zh-CN')),
)

function parentNameFromGroupRef(ref: string | null | undefined): string | null {
  const t = (ref || '').trim()
  if (!t) return null
  return parseSubgroupRef(t)?.groupName || t
}

/** 用户侧「项目」= 模型根目录；设备组按该目录隔离（非网络 DEFAULT 项目） */
function groupScopeId(): string | null {
  return currentProject.value?.model_root_folder_id || null
}

function groupStorageKey() {
  const scope = groupScopeId()
  return scope ? `dcim.deviceGroups.folder.${scope}` : null
}

function normalizeCatalogEntry(
  g: Partial<DeviceGroupMeta> & { note?: string; name: string },
): DeviceGroupMeta {
  const slots = migrateSlotsFromLegacy(g)
  const ruleIds = Array.isArray(g.wiring_rule_ids)
    ? g.wiring_rule_ids.filter((x): x is string => typeof x === 'string' && !!x.trim())
    : []
  return {
    name: g.name,
    role: g.role ?? slots[0]?.role ?? null,
    description: (g.description ?? g.note ?? '').toString(),
    slots,
    wiring_rule_ids: ruleIds.length ? ruleIds : null,
    planned_count: totalSlotCount(slots) || null,
    design_model_id: slots[0]?.design_model_id || g.design_model_id || null,
    port_pool: Array.isArray(g.port_pool) ? g.port_pool : null,
  }
}

function legacyGroupStorageKeys(): string[] {
  const keys = topologies.value.map((t) => `dcim.deviceGroups.${t.id}`)
  // 兼容上一版误按网络项目（常为 DEFAULT）存储的目录
  if (currentProjectId.value) {
    keys.push(`dcim.deviceGroups.project.${currentProjectId.value}`)
  }
  return keys
}

function readGroupCatalogRaw(key: string): Array<DeviceGroupMeta & { note?: string }> {
  try {
    const raw = localStorage.getItem(key) || sessionStorage.getItem(key)
    if (!raw) return []
    const list = JSON.parse(raw) as Array<DeviceGroupMeta & { note?: string }>
    return Array.isArray(list) ? list.filter((g) => g?.name) : []
  } catch {
    return []
  }
}

/**
 * 仅补目录中缺失的组名（不从画布反推规格）；组定义以目录 slots 为准，与画布解耦。
 */
function syncCatalogFromNodes() {
  if (!groupScopeId()) return
  const known = new Set(deviceGroupCatalog.value.map((g) => g.name))
  const extras: DeviceGroupMeta[] = []
  for (const n of nodes.value) {
    for (const name of nodeGroupList(n)) {
      if (!name || known.has(name)) continue
      known.add(name)
      extras.push({
        name,
        role: (n.network_role as FabricRole) || null,
        description: '',
        slots: [],
        planned_count: null,
        design_model_id: null,
        port_pool: null,
      })
    }
  }
  if (!extras.length) return
  persistDeviceGroupCatalog(
    [...deviceGroupCatalog.value, ...extras].sort((a, b) =>
      a.name.localeCompare(b.name, 'zh-CN'),
    ),
  )
}

function loadDeviceGroupCatalog() {
  const key = groupStorageKey()
  if (!key) {
    deviceGroupCatalog.value = []
    return
  }
  let list = readGroupCatalogRaw(key).map((g) => normalizeCatalogEntry(g))

  // 迁移：旧拓扑键 / 旧网络项目键 → 仅迁入当前模型项目，不跨项目共享
  if (!list.length) {
    const merged = new Map<string, DeviceGroupMeta>()
    const legacyKeys = legacyGroupStorageKeys()
    for (const legacyKey of legacyKeys) {
      for (const g of readGroupCatalogRaw(legacyKey)) {
        const entry = normalizeCatalogEntry(g)
        const prev = merged.get(entry.name)
        if (!prev) {
          merged.set(entry.name, entry)
          continue
        }
        merged.set(entry.name, {
          ...prev,
          role: prev.role || entry.role,
          description: prev.description || entry.description,
          planned_count: prev.planned_count ?? entry.planned_count,
          design_model_id: prev.design_model_id || entry.design_model_id,
          port_pool: prev.port_pool?.length ? prev.port_pool : entry.port_pool,
        })
      }
    }
    list = [...merged.values()].sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
    if (list.length) {
      localStorage.setItem(key, JSON.stringify(list))
      // 旧网络项目级缓存删除，避免其它模型项目再次读到同一份
      for (const legacyKey of legacyKeys) {
        localStorage.removeItem(legacyKey)
        sessionStorage.removeItem(legacyKey)
      }
    }
  }

  deviceGroupCatalog.value = list
  // 目录可能为空但节点上仍有组名：补齐后列表与「已在组」一致
  syncCatalogFromNodes()
}

function persistDeviceGroupCatalog(list: DeviceGroupMeta[]) {
  deviceGroupCatalog.value = list.map((g) => normalizeCatalogEntry(g))
  const key = groupStorageKey()
  if (key) {
    localStorage.setItem(key, JSON.stringify(deviceGroupCatalog.value))
    sessionStorage.removeItem(key)
  }
}

function onCatalogFromDialog(list: DeviceGroupMeta[]) {
  persistDeviceGroupCatalog(
    list.map((g) => {
      const old = deviceGroupCatalog.value.find((x) => x.name === g.name)
      return {
        ...normalizeCatalogEntry(g),
        port_pool: old?.port_pool ?? g.port_pool ?? null,
      }
    }),
  )
}

/** 为组内每台设备自动分配 1 个空闲口，写入内部端口池（列表不展示） */
function allocatePortsForGroup(groupName: string, members: NetworkNode[]): DeviceGroupPortRef[] {
  const occupied = new Set(occupiedPortKeys.value)
  for (const g of deviceGroupCatalog.value) {
    if (g.name === groupName) continue
    for (const p of g.port_pool || []) {
      occupied.add(`${p.node_id}:${p.port_id}`)
    }
  }
  const refs: DeviceGroupPortRef[] = []
  for (const n of members) {
    const free = listFreePortOptions(n, occupied)
    const pick = free[0]
    if (!pick) continue
    occupied.add(`${n.id}:${pick.id}`)
    refs.push({ node_id: n.id, port_id: pick.id, port_label: pick.label })
  }
  return refs
}

function refreshPortPoolForGroup(groupName: string, role?: FabricRole | null) {
  const members = canvasNodes.value.filter((n) => nodeInGroup(n, groupName))
  const pool = allocatePortsForGroup(groupName, members)
  const existing = deviceGroupCatalog.value.find((g) => g.name === groupName)
  const base = existing
    ? normalizeCatalogEntry(existing)
    : ({
        name: groupName,
        role: null,
        description: '',
        slots: [],
      } as DeviceGroupMeta)
  const nextEntry: DeviceGroupMeta = {
    ...base,
    role: role !== undefined ? role : base.role,
    port_pool: pool,
  }
  const next = deviceGroupCatalog.value.filter((g) => g.name !== groupName)
  next.push(nextEntry)
  persistDeviceGroupCatalog(next)
}

async function persistGroupMembership() {
  if (!canEdit.value || !currentId.value) return
  // 空拓扑没有节点可写回；设备组目录已持久化到本项目本地，无需调画布保存
  if (!nodes.value.length) return
  const ok = await saveCanvas({ silent: true })
  if (!ok) {
    ElMessage.warning('组已更新到画布，但自动保存布局失败，请手动点「保存布局」')
  }
}

function openGroupManager(
  mode: 'manage' | 'create' = 'manage',
  groupName?: string | null,
  side?: 'source' | 'target' | null,
) {
  if (!groupScopeId()) {
    ElMessage.warning('请先在左侧模型库选择项目或文件夹，设备组保存在各自项目内')
    sideAccordion.value = 'models'
    return
  }
  void loadWiringRules()
  groupDialogMode.value = mode
  groupDialogInitial.value = groupName || null
  groupDialogSide.value = side ?? null
  groupDialogVisible.value = true
  sideAccordion.value = 'groups'
}

function openGroupDetail(name: string) {
  selectedGroupName.value = name
  groupDetailName.value = name
  groupDetailVisible.value = true
  sideAccordion.value = 'groups'
}

function onSelectGroup(name: string) {
  selectedGroupName.value = name
  sideAccordion.value = 'groups'
}

function onCanvasSelectGroup(name: string | null) {
  selectedGroupName.value = name
  selectedNodeId.value = null
  selectedLinkId.value = null
  if (name) {
    groupDetailName.value = name
    groupDetailVisible.value = true
  }
}

function moveGroupMembers(name: string, dx: number, dy: number) {
  if (!dx && !dy) return
  for (const n of nodes.value) {
    if (n.on_canvas === false) continue
    if (!nodeInGroup(n, name)) continue
    n.pos_x = Math.max(0, n.pos_x + dx)
    n.pos_y = Math.max(0, n.pos_y + dy)
  }
}

function onDeviceGroupCreated(name: string) {
  if (groupDialogSide.value === 'source') {
    addGroupToSide('source', name)
  } else if (groupDialogSide.value === 'target') {
    addGroupToSide('target', name)
  }
  groupDialogSide.value = null
  refreshPortPoolForGroup(name)
  selectedGroupName.value = name
}

/** 检视器改组：支持多选 */
async function onUpdateNodeMeta(patch: {
  network_role?: string | null
  device_group?: string | null
  device_groups?: string[] | null
}) {
  const node = selectedNode.value
  if (!node || !canEdit.value) return
  if ('network_role' in patch) node.network_role = patch.network_role ?? null
  let groupsChanged = false
  if ('device_groups' in patch) {
    setNodeGroups(node, patch.device_groups || [])
    for (const g of nodeGroupList(node)) ensureGroupInCatalog(g, null)
    groupsChanged = true
  } else if ('device_group' in patch) {
    const g = (patch.device_group || '').trim()
    setNodeGroups(node, g ? [g] : [])
    if (g) ensureGroupInCatalog(g, null)
    groupsChanged = true
  }
  if (groupsChanged) {
    for (const g of nodeGroupList(node)) refreshPortPoolForGroup(g)
    await persistGroupMembership()
  }
}

function ensureGroupInCatalog(name: string, role: FabricRole | null) {
  const trimmed = name.trim()
  if (!trimmed) return
  // 子组引用不写入父目录
  if (parseSubgroupRef(trimmed)) return
  if (deviceGroupCatalog.value.some((g) => g.name === trimmed)) return
  persistDeviceGroupCatalog([
    ...deviceGroupCatalog.value,
    {
      name: trimmed,
      role,
      description: '',
      slots: [],
      planned_count: null,
      design_model_id: null,
      port_pool: null,
    },
  ])
}

async function onRenameDeviceGroup(payload: { from: string; to: string }) {
  for (const n of nodes.value) {
    renameNodeGroup(n, payload.from, payload.to)
  }
  renameGroupInConfig(payload.from, payload.to)
  const entry = deviceGroupCatalog.value.find((g) => g.name === payload.from)
  if (entry) {
    persistDeviceGroupCatalog([
      ...deviceGroupCatalog.value.filter((g) => g.name !== payload.from),
      { ...entry, name: payload.to },
    ])
  }
  if (selectedGroupName.value === payload.from) selectedGroupName.value = payload.to
  await persistGroupMembership()
}

async function onDeleteDeviceGroup(name: string) {
  let touched = false
  for (const n of nodes.value) {
    if (!nodeInGroup(n, name)) continue
    removeNodeFromGroup(n, name)
    touched = true
  }
  removeGroupFromConfig(name)
  persistDeviceGroupCatalog(deviceGroupCatalog.value.filter((g) => g.name !== name))
  if (selectedGroupName.value === name) selectedGroupName.value = null
  // 空组或空拓扑：只删目录，不触发画布保存（避免 Topology must contain at least one node）
  if (touched && nodes.value.length) {
    await persistGroupMembership()
  }
}

watch(currentId, (id) => {
  // 同项目内切换拓扑：模型库与设备组目录保持项目级共享，仅刷新端口池/实验室
  loadDeviceGroupCatalog()
  if (!designModels.value.length && groupScopeId()) {
    void loadDesignModelsForProject()
  }
  if (id && deviceGroupCatalog.value.length) {
    for (const g of deviceGroupCatalog.value) {
      refreshPortPoolForGroup(g.name)
    }
  }
  selectedGroupName.value = null
  if (!id) sideAccordion.value = 'topology'
  void loadLabSession()
})

/** 拓扑节点异步加载完成后，再按节点组名补齐目录（避免列表空白） */
watch(
  () =>
    nodes.value
      .map((n) => `${n.id}:${nodeGroupList(n).join(',')}`)
      .join('|'),
  () => {
    if (!groupScopeId() || !nodes.value.length) return
    syncCatalogFromNodes()
  },
)

watch(currentProjectId, () => {
  loadDeviceGroupCatalog()
  selectedGroupName.value = null
})

watch(
  () => currentProject.value?.model_root_folder_id || null,
  () => {
    // 切换模型「项目/文件夹」时切换设备组目录
    loadDeviceGroupCatalog()
    selectedGroupName.value = null
  },
)

watch(sideAccordion, (name) => {
  if (name === 'rules') void loadWiringRules()
  if (name === 'groups') loadDeviceGroupCatalog()
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

/** 批量部署对话框 */
const batchDeployVisible = ref(false)
const batchDeployModelId = ref<string | null>(null)
const batchDeployCount = ref(10)
const batchDeploying = ref(false)

const batchDeployModel = computed(
  () => designModels.value.find((m) => m.id === batchDeployModelId.value) || null,
)

function nextBatchOrigin(): { x: number; y: number } {
  const onCanvas = nodes.value.filter((n) => n.on_canvas !== false)
  if (!onCanvas.length) return { x: 80, y: 80 }
  const maxX = Math.max(...onCanvas.map((n) => n.pos_x))
  const maxY = Math.max(...onCanvas.map((n) => n.pos_y))
  // 新批次放在现有设备下方，避免重叠
  if (maxX > 1400) return { x: 80, y: maxY + 130 }
  return { x: 80, y: maxY + 130 }
}

function openBatchDeploy(modelId: string) {
  if (!canEdit.value) return
  if (!currentId.value) {
    ElMessage.warning('请先选择或新建拓扑后再批量部署')
    return
  }
  const model = designModels.value.find((m) => m.id === modelId)
  if (!model) {
    ElMessage.warning('模型不存在')
    return
  }
  stampDesignModelId.value = modelId
  batchDeployModelId.value = modelId
  batchDeployCount.value = 10
  batchDeployVisible.value = true
}

async function confirmBatchDeploy() {
  if (!canEdit.value || !currentId.value || !batchDeployModelId.value) return
  const model = designModels.value.find((m) => m.id === batchDeployModelId.value)
  if (!model) return
  const count = Math.max(1, Math.min(5000, Math.floor(Number(batchDeployCount.value) || 0)))
  if (!count) {
    ElMessage.warning('请输入 1–5000 的部署数量')
    return
  }
  if (count >= 200) {
    try {
      await ElMessageBox.confirm(
        `将一次性部署 ${count} 台「${model.name}」到画布，可能需要几秒。是否继续？`,
        '批量部署确认',
        { type: 'warning', confirmButtonText: '继续部署', cancelButtonText: '取消' },
      )
    } catch {
      return
    }
  }
  batchDeploying.value = true
  try {
    const origin = nextBatchOrigin()
    const positions = layoutGroupGrid(count, origin.x, origin.y)
    const working = [...nodes.value]
    const createdList: typeof nodes.value = []
    for (let i = 0; i < count; i++) {
      const pos = positions[i]
      const created = stampDesignModelOntoCanvas(
        model,
        currentId.value,
        pos.x,
        pos.y,
        working,
      )
      working.push(created)
      createdList.push(created)
      nodes.value.push(created)
    }
    selectedNodeId.value = createdList[createdList.length - 1]?.id ?? null
    batchDeployVisible.value = false
    ElMessage.success(`已批量部署 ${createdList.length} 台「${model.name}」，请保存布局`)
  } finally {
    batchDeploying.value = false
  }
}

function onDesignModelSelect(id: string) {
  if (!canEdit.value || linkMode.value) return
  stampDesignModelId.value = id
  if (!currentId.value) {
    ElMessage.info('已选中模型；请先在左侧「拓扑管理」中新建或选择拓扑后再放置')
    return
  }
  ElMessage.info('模型放置模式：在画布上多次点击批量绘制；也可右键模型「批量部署」')
}

/** 拖入独立设备组：按槽位规格实例化到本拓扑（同拓扑按槽位数量封顶，不重复超量） */
async function placeDeviceGroup(groupName: string, x: number, y: number) {
  if (!canEdit.value || !currentId.value) {
    ElMessage.warning('请先选择拓扑后再拖入设备组')
    return
  }
  const name = groupName.trim()
  if (!name) return

  const raw =
    deviceGroupCatalog.value.find((g) => g.name === name) ||
    ({ name, role: null, description: '', slots: [] } as DeviceGroupMeta)
  const def = normalizeCatalogEntry(raw)
  if (!def.slots.length) {
    ElMessage.warning(`组「${name}」尚未配置设备规格，请先在组管理中添加类型/模型与数量`)
    return
  }

  const planned = totalSlotCount(def.slots)
  if (planned >= 200) {
    try {
      await ElMessageBox.confirm(
        `将按组规格放置最多约 ${planned} 台设备到画布，可能需要几秒。是否继续？`,
        '批量放置确认',
        { type: 'warning', confirmButtonText: '继续放置', cancelButtonText: '取消' },
      )
    } catch {
      return
    }
  }

  const result = materializeGroupSlots({
    groupName: name,
    def,
    topologyId: currentId.value,
    nodes: nodes.value,
    models: designModels.value,
    originX: x,
    originY: y,
    onCanvas: true,
  })
  for (const n of result.created) nodes.value.push(n)
  for (const w of result.warnings) ElMessage.warning(w)

  if (!result.placed.length && !result.created.length) {
    const local = nodes.value.filter((n) => nodeInGroup(n, name)).length
    const wired = applyBoundRulesForGroup(def, { silent: true })
    ElMessage.info(
      `组「${name}」在本拓扑已满足规格（${local}/${planned} 台）` +
        (wired > 0 ? `，并补充布线 ${wired} 条` : '，不会重复放置') +
        '。',
    )
    selectedGroupName.value = name
    return
  }

  selectedGroupName.value = name
  selectedNodeId.value = result.placed[result.placed.length - 1]?.id ?? null
  refreshPortPoolForGroup(name)
  const wired = applyBoundRulesForGroup(def, { silent: true })
  ElMessage.success(
    `已放置组「${name}」：新建 ${result.created.length} 台` +
      (wired > 0 ? ` · 自动布线 ${wired} 条` : '') +
      ` · ${summarizeSlots(def.slots, designModels.value)} · 记得保存布局`,
  )
}

/** 执行设备组绑定的布线规则，返回新建连线总数 */
function applyBoundRulesForGroup(
  def: DeviceGroupMeta,
  opts?: { silent?: boolean },
): number {
  const ids = def.wiring_rule_ids || []
  if (!ids.length) return 0
  let total = 0
  for (const id of ids) {
    const rule = wiringRules.value.find((r) => r.id === id)
    if (!rule) {
      if (!opts?.silent) ElMessage.warning(`组「${def.name}」绑定的规则不存在或已删除`)
      continue
    }
    if (rule.enabled === false) continue
    total += commitWiringRuleApply(rule, { silent: true })
  }
  if (!opts?.silent && total > 0) {
    ElMessage.success(`组「${def.name}」已自动执行绑定规则，生成 ${total} 条连线`)
  }
  return total
}

/** 布线前：将规则引用的设备组按规格实例化到当前拓扑，以便匹配源/目标 */
function ensureRuleGroupsMaterialized(rule: NetworkWiringRule) {
  if (!currentId.value) return
  const cfg = rule.config || {}
  const refs = [
    ...resolveWiringGroups(cfg.source_groups, cfg.source_group),
    ...resolveWiringGroups(cfg.target_groups, cfg.target_group),
  ]
  const unique = parentGroupNamesFromRefs(refs)
  if (!unique.length) return

  const origin = nextBatchOrigin()
  let created = 0
  for (const name of unique) {
    const raw = deviceGroupCatalog.value.find((g) => g.name === name)
    if (!raw) continue
    const def = normalizeCatalogEntry(raw)
    if (!def.slots.length) continue
    const result = materializeGroupSlots({
      groupName: name,
      def,
      topologyId: currentId.value,
      nodes: nodes.value,
      models: designModels.value,
      originX: origin.x + created * 24,
      originY: origin.y + created * 16,
      onCanvas: true,
    })
    for (const n of result.created) {
      nodes.value.push(n)
      created += 1
    }
    for (const w of result.warnings) ElMessage.warning(w)
    refreshPortPoolForGroup(name)
  }
  if (created > 0) {
    ElMessage.info(`已按组规格自动补齐 ${created} 台设备到本拓扑，再执行布线`)
  }
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
  if (cached?.length && nodes.value.length) {
    syncTopologyNodesFromDesignModels(nodes.value, designModels.value)
  }
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
    if (nodes.value.length) {
      syncTopologyNodesFromDesignModels(nodes.value, items)
    }
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
  selectedGroupName.value = null
  loadDeviceGroupCatalog()
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
    const data = (e as { response?: { data?: { message?: string; details?: { detail?: string } } } })
      ?.response?.data
    const msg = data?.details?.detail || data?.message || (e instanceof Error ? e.message : '同步失败')
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
  try {
    wiringRules.value = await listWiringRules()
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

async function openWiringDrawer(createNew = true) {
  wiringDrawerVisible.value = true
  if (createNew) resetWiringForm()
  sideAccordion.value = 'rules'
  await loadWiringRules()
}

function editWiringRule(rule: NetworkWiringRule) {
  wiringEditingId.value = rule.id
  wiringForm.name = rule.name
  wiringForm.mode = (rule.mode as 'sequential' | 'manual') || 'sequential'
  wiringForm.description = rule.description || ''
  wiringForm.config = normalizeWiringConfig((rule.config || {}) as Record<string, unknown>)
  wiringDrawerVisible.value = true
  sideAccordion.value = 'rules'
}

function buildWiringConfigPayload(): WiringRuleConfig {
  const cfg = normalizeWiringConfig(wiringForm.config as unknown as Record<string, unknown>)
  cfg.max_links = cfg.max_link_count ?? cfg.link_count
  return cfg
}

async function saveWiringRule() {
  if (!wiringForm.name.trim()) {
    ElMessage.warning('请填写规则名称')
    return
  }
  const cfg = buildWiringConfigPayload()
  const sourceGroups = resolveWiringGroups(cfg.source_groups, cfg.source_group)
  const targetGroups = resolveWiringGroups(cfg.target_groups, cfg.target_group)
  const hasExplicit = !!(cfg.source_node_ids?.length && (cfg.peer_link || cfg.target_node_ids?.length))
  const hasRole =
    !!(cfg.source_role || sourceGroups.length) &&
    (cfg.peer_link ||
      isSwitchInterconnect(cfg.connection_type) ||
      !!(cfg.target_role || targetGroups.length))
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
      ElMessage.success('布线规则已更新（全部项目通用）')
    } else {
      await createWiringRule({
        project_id: currentProjectId.value || null,
        topology_id: currentId.value || null,
        name: wiringForm.name.trim(),
        mode: wiringForm.mode,
        enabled: true,
        description: wiringForm.description.trim() || null,
        config: cfg as unknown as Record<string, unknown>,
      })
      ElMessage.success('布线规则已保存（全部项目通用）')
    }
    resetWiringForm()
    await loadWiringRules()
    sideAccordion.value = 'rules'
  } catch (err: unknown) {
    const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
    ElMessage.error(msg || '保存规则失败')
  } finally {
    wiringSaving.value = false
  }
}

function runWiringRule(rule: NetworkWiringRule) {
  if (!canEdit.value) return
  if (!currentId.value) {
    ElMessage.warning('请先选择拓扑后再执行规则（规则本身为全部项目通用）')
    return
  }
  if (designModels.value.length) {
    syncTopologyNodesFromDesignModels(nodes.value, designModels.value)
  }
  const cfg = normalizeWiringConfig((rule.config || {}) as Record<string, unknown>)
  const mode = String(cfg.allocation_mode || 'AUTO').toUpperCase()

  if (mode === 'MANUAL') {
    const pairs = (cfg.pairs || []).filter(
      (p) => p.source_node_id && p.source_port_id && p.target_node_id && p.target_port_id,
    )
    if (!pairs.length) {
      ElMessage.warning('请先在规则中通过下拉菜单指定至少一对端口')
      return
    }
    const srcIds = new Set(previewSourceNodes.value.map((n) => n.id))
    const tgtIds = new Set(previewTargetNodes.value.map((n) => n.id))
    const invalid = pairs.find(
      (p) => !srcIds.has(p.source_node_id) || !tgtIds.has(p.target_node_id),
    )
    if (invalid) {
      ElMessage.warning('端口对中的设备不在当前设备参数匹配范围内，请重新选择')
      return
    }
    if (
      peerSectionEnabled.value &&
      isIntraInterconnect.value &&
      pairs.some((p) => p.source_node_id === p.target_node_id)
    ) {
      ElMessage.warning('组内互联两端须为同组内的不同设备')
      return
    }
    commitWiringRuleApply({
      ...rule,
      mode: 'manual',
      config: { ...(rule.config || {}), allocation_mode: 'MANUAL', pairs },
    })
    return
  }

  if (mode === 'HYBRID') {
    const ruleForPreview: NetworkWiringRule = {
      ...rule,
      config: { ...(rule.config || {}), pairs: [] },
    }
    const preview = previewWiringPairs(ruleForPreview, nodes.value, links.value)
    if (!preview.pairs.length) {
      ElMessage.warning(
        preview.issues[0]?.message || '无法生成预览端口对，请检查规则参数与空闲口',
      )
      return
    }
    openPairPreviewEditor(rule, preview.pairs, preview.scenario_label || mode)
    return
  }

  // AUTO
  commitWiringRuleApply(rule)
}

function openPairPreviewEditor(
  rule: NetworkWiringRule,
  pairs: ProposedPair[],
  scenarioLabel: string,
) {
  pairPreviewRule.value = rule
  pairPreviewRows.value = pairs.map((p) => ({ ...p }))
  pairPreviewScenario.value = scenarioLabel
  pairPreviewVisible.value = true
}

function addPreviewPairRow() {
  const src = previewSourceNodes.value[0] || nodes.value.find((n) => n.on_canvas !== false)
  const tgt =
    previewTargetNodes.value[0] ||
    nodes.value.find((n) => n.on_canvas !== false && n.id !== src?.id)
  if (!src || !tgt) {
    ElMessage.warning('请先匹配源/目标设备')
    return
  }
  const sp = listFreePortOptions(src, occupiedPortKeys.value)[0]
  const tp = listFreePortOptions(tgt, occupiedPortKeys.value)[0]
  pairPreviewRows.value.push({
    source_node_id: src.id,
    source_port_id: sp?.id || '',
    source_label: sp ? `${src.name}:${sp.port.label}` : src.name,
    target_node_id: tgt.id,
    target_port_id: tp?.id || '',
    target_label: tp ? `${tgt.name}:${tp.port.label}` : tgt.name,
  })
}

function removePreviewPairRow(idx: number) {
  pairPreviewRows.value.splice(idx, 1)
}

function portsForNode(nodeId: string) {
  const n = nodes.value.find((x) => x.id === nodeId)
  if (!n) return []
  return listFreePortOptions(n, occupiedPortKeys.value)
}

function onPreviewSourcePortChange(row: ProposedPair) {
  const n = nodes.value.find((x) => x.id === row.source_node_id)
  const p = n?.port_layout?.ports?.find((x) => x.id === row.source_port_id)
  row.source_label = n && p ? `${n.name}:${p.label}` : row.source_label
}

function onPreviewTargetPortChange(row: ProposedPair) {
  const n = nodes.value.find((x) => x.id === row.target_node_id)
  const p = n?.port_layout?.ports?.find((x) => x.id === row.target_port_id)
  row.target_label = n && p ? `${n.name}:${p.label}` : row.target_label
}

async function confirmPairPreviewApply() {
  const rule = pairPreviewRule.value
  if (!rule) return
  const pairs: WiringPair[] = pairPreviewRows.value
    .filter((r) => r.source_node_id && r.source_port_id && r.target_node_id && r.target_port_id)
    .map((r) => ({
      source_node_id: r.source_node_id,
      source_port_id: r.source_port_id,
      target_node_id: r.target_node_id,
      target_port_id: r.target_port_id,
    }))
  if (!pairs.length) {
    ElMessage.warning('请至少指定一对有效端口')
    return
  }
  pairPreviewLoading.value = true
  try {
    const patched: NetworkWiringRule = {
      ...rule,
      mode: 'manual',
      config: {
        ...(rule.config || {}),
        allocation_mode: 'MANUAL',
        pairs,
      },
    }
    pairPreviewVisible.value = false
    commitWiringRuleApply(patched)
  } finally {
    pairPreviewLoading.value = false
  }
}

function commitWiringRuleApply(
  rule: NetworkWiringRule,
  opts?: { silent?: boolean },
): number {
  ensureRuleGroupsMaterialized(rule)
  const { links: created, report } = applyWiringRule(rule, nodes.value, links.value)
  const scene = report.scenario ? `场景 ${report.scenario}` : ''
  if (report.issues.length) {
    const first = report.issues[0]
    if (!created.length) {
      if (!opts?.silent) {
        ElMessage({
          type: first.level === 'error' ? 'error' : 'warning',
          message: `${scene ? scene + '：' : ''}${first.message}（匹配源 ${report.matched_sources} / 目标 ${report.matched_targets}）`,
          duration: 6000,
        })
      }
      return 0
    }
    if (!opts?.silent) {
      ElMessage.warning(
        `${scene ? scene + ' · ' : ''}已生成 ${created.length} 条；另有 ${report.issues.length} 条提示：${first.message}`,
      )
    }
  } else if (!created.length) {
    if (!opts?.silent) {
      ElMessage.warning('未生成新连线（请检查端口是否空闲、设备角色/Purpose 是否匹配）')
    }
    return 0
  } else if (!opts?.silent) {
    ElMessage.success(
      `已按规则「${rule.name}」${scene ? `（${scene} ${report.scenario_label || ''}）` : ''}自动布线 ${created.length} 条，请保存拓扑`,
    )
  }
  links.value.push(...created)
  return created.length
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
  void loadWiringRules()
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
          <el-collapse v-model="sideAccordion" accordion class="side-accordion">
            <el-collapse-item name="models">
              <template #title>
                <span class="acc-title">模型库</span>
              </template>
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
                <el-option
                  v-for="f in allFolderOptions"
                  :key="f.id"
                  :label="f.label"
                  :value="f.id"
                />
              </el-select>
              <NetworkModelLibraryPane
                :root-folder-id="currentProject?.model_root_folder_id || null"
                :models="designModels"
                :selected-model-id="stampDesignModelId"
                :disabled="!canEdit || linkMode"
                :loading="modelsLoading"
                :hide-title="true"
                @select="onDesignModelSelect"
                @batch-deploy="openBatchDeploy"
              />
            </el-collapse-item>

            <el-collapse-item name="topology">
              <template #title>
                <span class="acc-title">拓扑管理</span>
              </template>
              <NetworkTopologyPicker
                title="拓扑管理"
                hide-title
                compact
                :topologies="topologies"
                :current-id="currentId"
                :loading="loading"
                @select="selectTopology"
                @create="handleCreateTopology"
                @delete="removeTopology"
              />
            </el-collapse-item>

            <el-collapse-item name="groups">
              <template #title>
                <span class="acc-title">设备组 <span class="acc-sub">独立规格 · 可布线</span></span>
              </template>
              <div v-if="!groupScopeId()" class="empty-hint">
                请先在「模型库」选择项目。设备组与画布独立：配置类型/数量后可拖入拓扑，并可作为布线源或目标。
              </div>
              <NetworkDeviceGroupListPane
                v-else
                :catalog="deviceGroupCatalog"
                :nodes="nodes"
                :design-models="designModels"
                :selected-group="selectedGroupName"
                :disabled="!canEdit || !groupScopeId()"
                @select="onSelectGroup"
                @create="openGroupManager('create')"
                @edit="(name) => openGroupManager('manage', name)"
                @detail="openGroupDetail"
                @manage="openGroupManager('manage')"
              />
            </el-collapse-item>

            <el-collapse-item name="rules">
              <template #title>
                <span class="acc-title">
                  规则管理 <span class="acc-sub">全项目通用</span>
                  <span v-if="wiringRules.length" class="acc-count">{{ wiringRules.length }}</span>
                </span>
              </template>
              <div class="rules-pane">
                <div class="pane-actions">
                  <el-button
                    type="primary"
                    link
                    size="small"
                    :disabled="!canEdit"
                    @click="openWiringDrawer(true)"
                  >
                    新建
                  </el-button>
                </div>
                <div v-if="!wiringRules.length" class="empty-hint">
                  暂无规则。规则在全部项目间通用，切换项目后仍可见；执行时写入当前拓扑。
                </div>
                <div v-else class="rule-list">
                  <div
                    v-for="rule in wiringRules"
                    :key="rule.id"
                    class="rule-card"
                    :class="{ active: wiringEditingId === rule.id }"
                  >
                    <div class="meta">
                      <span class="name">{{ rule.name }}</span>
                      <span class="sub">
                        {{
                          connectionTypeLabel(
                            String((rule.config as Record<string, unknown>)?.connection_type || ''),
                          ) || rule.mode
                        }}
                      </span>
                    </div>
                    <div class="card-actions">
                      <el-button
                        type="primary"
                        link
                        size="small"
                        :disabled="!canEdit"
                        @click="runWiringRule(rule)"
                      >
                        执行
                      </el-button>
                      <el-button type="primary" link size="small" @click="editWiringRule(rule)">
                        编辑
                      </el-button>
                      <el-button
                        type="warning"
                        link
                        size="small"
                        :disabled="!canEdit || !countLinksByRule(rule.id)"
                        @click="undoWiringRule(rule)"
                      >
                        撤销
                      </el-button>
                      <el-button
                        type="danger"
                        link
                        size="small"
                        :disabled="!canEdit"
                        @click="removeWiringRule(rule)"
                      >
                        删除
                      </el-button>
                    </div>
                  </div>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </aside>

        <section class="workspace">
          <div class="toolbar">
            <span class="title">拓扑设计</span>
            <span class="hint">
              {{
                stampDesignModelId
                  ? '模型放置中：多次点击画布绘制；右键模型可指定数量批量部署'
                  : '模型库：拖拽/点击放置，或右键批量部署'
              }}
            </span>
            <el-button
              v-if="canEdit && stampDesignModelId"
              type="primary"
              plain
              :disabled="!currentId"
              @click="openBatchDeploy(stampDesignModelId)"
            >
              批量部署
            </el-button>
            <el-button v-if="stampMode" @click="clearStampMode">退出放置</el-button>
            <el-radio-group
              v-model="canvasViewMode"
              size="small"
              :disabled="!currentId"
              style="margin-right: 8px"
            >
              <el-radio-button value="devices">逐台</el-radio-button>
              <el-radio-button value="groups">按组简化</el-radio-button>
            </el-radio-group>
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
            :selected-group-name="selectedGroupName"
            :link-mode="linkMode"
            :link-source-id="linkSourceId"
            :stamp-mode="stampMode"
            :view-mode="canvasViewMode"
            :group-roles="groupRolesMap"
            :node-lab-status="labSession?.node_status || null"
            @select-node="onSelectNode"
            @select-link="onSelectLink"
            @select-group="onCanvasSelectGroup"
            @move-node="moveNode"
            @move-group="moveGroupMembers"
            @place-node="placeNode"
            @place-device-group="placeDeviceGroup"
            @canvas-click="onCanvasClick"
          />
          <el-empty
            v-else-if="!currentProject?.model_root_folder_id"
            description="请在左侧选择模型项目或文件夹"
          />
          <el-empty v-else description="请在左侧「拓扑管理」中新建或选择拓扑" />
        </section>

        <aside class="inspector">
          <TopologyNodeInspector
            v-if="selectedNode"
            :node="selectedNode"
            :nodes="nodes"
            :links="links"
            :editable="canEdit"
            :group-options="deviceGroupParentNames"
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

    <el-drawer
      v-model="wiringDrawerVisible"
      :title="wiringEditingId ? '编辑规则' : '新建规则'"
      size="720px"
      class="wiring-drawer"
    >
      <p class="wiring-hint">
        按表格分区配置参数。源/目标可分别用设备组、手选设备或角色（组与手选为并集，两侧独立，无需组对组对应）。
        预览匹配：源 {{ previewSourceCount }} 台 / 目标 {{ previewTargetCount }} 台。执行后请保存拓扑，连线表见「接口设计」。
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
                  <p class="scenario-hint">
                    检测到场景：
                    <strong>{{ detectedWiringScenario.scenario }}</strong>
                    — {{ detectedWiringScenario.label }}
                    （源 {{ detectedWiringScenario.sources }} / 目标 {{ detectedWiringScenario.targets }}；端口过滤与选口原则见下方「端口参数」）
                  </p>
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
                    placeholder="未选组/手选时按角色"
                    style="width: 100%"
                    @change="onDeviceMatchChange"
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
                    placeholder="未选组/手选时按角色"
                    style="width: 100%"
                    :disabled="peerSectionEnabled && isIntraInterconnect"
                    @change="onDeviceMatchChange"
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
                    v-model="wiringForm.config.source_groups"
                    multiple
                    clearable
                    filterable
                    collapse-tags
                    collapse-tags-tooltip
                    placeholder="可选整组或组内子组"
                    style="width: 100%"
                    @change="syncLegacyGroupFields"
                  >
                    <el-option
                      v-for="g in deviceGroupOptions"
                      :key="g.value"
                      :label="g.label"
                      :value="g.value"
                    />
                  </el-select>
                  <div class="group-actions">
                    <el-button
                      v-if="!deviceGroupOptionValues.length"
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
                        v-if="wiringForm.config.source_groups?.length"
                        link
                        size="small"
                        @click="
                          openGroupManager(
                            'manage',
                            parentNameFromGroupRef(wiringForm.config.source_groups?.[0]),
                          )
                        "
                      >
                        编辑子组规格
                      </el-button>
                    </template>
                  </div>
                </td>
                <th class="label-cell">目标设备组</th>
                <td>
                  <el-select
                    v-model="wiringForm.config.target_groups"
                    multiple
                    clearable
                    filterable
                    collapse-tags
                    collapse-tags-tooltip
                    placeholder="可选整组或组内子组"
                    style="width: 100%"
                    :disabled="peerSectionEnabled && isIntraInterconnect"
                    @change="syncLegacyGroupFields"
                  >
                    <el-option
                      v-for="g in deviceGroupOptions"
                      :key="g.value"
                      :label="g.label"
                      :value="g.value"
                    />
                  </el-select>
                  <div class="group-actions">
                    <el-button
                      v-if="!deviceGroupOptionValues.length"
                      type="primary"
                      link
                      size="small"
                      @click="openGroupManager('create', null, 'target')"
                    >
                      添加组
                    </el-button>
                    <template v-else>
                      <el-button
                        type="primary"
                        link
                        size="small"
                        @click="openGroupManager('manage')"
                      >
                        管理组
                      </el-button>
                      <el-button
                        link
                        size="small"
                        @click="openGroupManager('create', null, 'target')"
                      >
                        添加组
                      </el-button>
                      <el-button
                        v-if="wiringForm.config.target_groups?.length"
                        link
                        size="small"
                        @click="
                          openGroupManager(
                            'manage',
                            parentNameFromGroupRef(wiringForm.config.target_groups?.[0]),
                          )
                        "
                      >
                        编辑子组规格
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
                    @change="onDeviceMatchChange"
                  >
                    <el-option
                      v-for="n in canvasNodes"
                      :key="n.id"
                      :label="`${n.name} [${resolveNodeFabricRole(n)}]${nodeGroupList(n).length ? ' · ' + nodeGroupList(n).join('/') : ''}`"
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
                    :disabled="peerSectionEnabled && isIntraInterconnect"
                    @change="onDeviceMatchChange"
                  >
                    <el-option
                      v-for="n in canvasNodes"
                      :key="n.id"
                      :label="`${n.name} [${resolveNodeFabricRole(n)}]${nodeGroupList(n).length ? ' · ' + nodeGroupList(n).join('/') : ''}`"
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
          <div class="principle-box">
            <div class="principle-title">{{ wiringPrinciple.title }}</div>
            <ul>
              <li v-for="(b, i) in wiringPrinciple.bullets" :key="i">{{ b }}</li>
            </ul>
          </div>
          <table class="param-table">
            <tbody>
              <tr>
                <th class="label-cell">分配模式</th>
                <td>
                  <el-select
                    v-model="wiringForm.config.allocation_mode"
                    style="width: 100%"
                    @change="onAllocationModeChange"
                  >
                    <el-option
                      v-for="o in ALLOCATION_MODE_OPTIONS"
                      :key="o.value"
                      :label="o.label"
                      :value="o.value"
                    />
                  </el-select>
                </td>
                <th class="label-cell">链路数</th>
                <td>
                  <el-input-number
                    v-model="wiringForm.config.link_count"
                    :min="1"
                    :max="128"
                    controls-position="right"
                    style="width: 100%"
                    :disabled="isManualAlloc"
                  />
                </td>
              </tr>
              <tr v-if="!isManualAlloc">
                <th class="label-cell">速率</th>
                <td>
                  <el-select
                    v-model="wiringForm.config.speed"
                    clearable
                    style="width: 100%"
                    @change="wiringForm.config.port_speed = wiringForm.config.speed"
                  >
                    <el-option v-for="s in SPEED_OPTIONS" :key="s" :label="s" :value="s" />
                  </el-select>
                </td>
                <th class="label-cell">Speed Mode</th>
                <td>
                  <el-select v-model="wiringForm.config.speed_mode" style="width: 100%">
                    <el-option label="EXACT（精确同速）" value="EXACT" />
                    <el-option label="MIN（允许降速）" value="MIN" />
                  </el-select>
                </td>
              </tr>
              <tr v-if="!isManualAlloc">
                <th class="label-cell">端口介质</th>
                <td>
                  <div class="inline-pair" style="gap: 8px">
                    <el-select
                      v-model="wiringForm.config.port_media"
                      filterable
                      allow-create
                      default-first-option
                      placeholder="选择或新建介质"
                      style="flex: 1; width: 100%"
                      @change="onPortMediaChange"
                      @visible-change="(v: boolean) => v && refreshPortMediaOptions()"
                    >
                      <el-option
                        v-for="o in portMediaTypeOptions"
                        :key="o.value"
                        :label="o.label"
                        :value="o.value"
                      />
                    </el-select>
                    <el-button size="small" @click="openAddPortMediaDialog">添加介质</el-button>
                  </div>
                </td>
                <th class="label-cell">源/目标排序</th>
                <td>
                  <div class="inline-pair">
                    <el-select v-model="wiringForm.config.source_port_policy" style="width: 48%">
                      <el-option
                        v-for="o in PORT_POLICY_OPTIONS"
                        :key="'s'+o.value"
                        :label="'源:'+o.label"
                        :value="o.value"
                      />
                    </el-select>
                    <el-select v-model="wiringForm.config.target_port_policy" style="width: 48%">
                      <el-option
                        v-for="o in PORT_POLICY_OPTIONS"
                        :key="'t'+o.value"
                        :label="'目标:'+o.label"
                        :value="o.value"
                      />
                    </el-select>
                  </div>
                </td>
              </tr>
              <tr v-if="!isManualAlloc">
                <th class="label-cell">源 Purpose</th>
                <td>
                  <el-select
                    v-model="wiringForm.config.source_port_purpose"
                    style="width: 100%"
                    @change="onSourcePurposeChange"
                  >
                    <el-option
                      v-for="o in PORT_PURPOSE_OPTIONS"
                      :key="o.value"
                      :label="o.label"
                      :value="o.value"
                    />
                  </el-select>
                </td>
                <th class="label-cell">目标 Purpose</th>
                <td>
                  <el-select
                    v-model="wiringForm.config.target_port_purpose"
                    style="width: 100%"
                    :disabled="peerSectionEnabled"
                    @change="onTargetPurposeChange"
                  >
                    <el-option
                      v-for="o in PORT_PURPOSE_OPTIONS"
                      :key="o.value"
                      :label="o.label"
                      :value="o.value"
                    />
                  </el-select>
                </td>
              </tr>
              <tr v-if="isHybridAlloc">
                <th class="label-cell" colspan="4">
                  <span class="pool-legend" style="margin:0">自动后可改：执行时先预览端口对，再确认写入。</span>
                </th>
              </tr>
            </tbody>
          </table>

          <div v-if="isManualAlloc" class="manual-pairs">
            <div class="sheet-sub">手动指定端口对（仅可选设备参数匹配到的设备）</div>
            <p class="pool-legend" style="margin: 0 0 8px">{{ devicePortLinkHint }}</p>
            <el-table :data="wiringForm.config.pairs || []" size="small" border>
              <el-table-column label="源设备" min-width="150">
                <template #default="{ row }">
                  <el-select
                    v-model="row.source_node_id"
                    filterable
                    style="width: 100%"
                    :disabled="!sourceDeviceOptions.length"
                    @change="onManualSourceDeviceChange(row)"
                  >
                    <el-option
                      v-for="n in sourceDeviceOptions"
                      :key="n.id"
                      :label="`${n.name} · ${n.groups}`"
                      :value="n.id"
                    />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="源端口" min-width="160">
                <template #default="{ row }">
                  <el-select v-model="row.source_port_id" filterable style="width: 100%">
                    <el-option
                      v-for="o in portsForNodeInForm(row.source_node_id)"
                      :key="o.id"
                      :label="o.label"
                      :value="o.id"
                    />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="目标设备" min-width="150">
                <template #default="{ row }">
                  <el-select
                    v-model="row.target_node_id"
                    filterable
                    style="width: 100%"
                    :disabled="!targetDeviceOptions.length"
                    @change="onManualTargetDeviceChange(row)"
                  >
                    <el-option
                      v-for="n in targetDeviceOptions"
                      :key="n.id"
                      :label="`${n.name} · ${n.groups}`"
                      :value="n.id"
                    />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="目标端口" min-width="160">
                <template #default="{ row }">
                  <el-select v-model="row.target_port_id" filterable style="width: 100%">
                    <el-option
                      v-for="o in portsForNodeInForm(row.target_node_id)"
                      :key="o.id"
                      :label="o.label"
                      :value="o.id"
                    />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column width="64" align="center">
                <template #default="{ $index }">
                  <el-button link type="danger" @click="removeManualPairRow($index)">删</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-button size="small" style="margin-top: 8px" @click="addManualPairRow">添加端口对</el-button>
          </div>
          <p v-else class="pool-legend">
            {{ devicePortLinkHint }} 自动分配仅在这些匹配设备的空闲口上选口。
          </p>
        </div>

        <!-- 3 互联/DAD -->
        <div class="sheet-block">
          <div class="sheet-title">3. 互联 / Peer-link / DAD</div>
          <table class="param-table">
            <tbody>
              <tr>
                <th class="label-cell">启用互联规则</th>
                <td>
                  <el-switch
                    :model-value="wiringForm.config.peer_link"
                    @change="onPeerLinkToggle"
                  />
                </td>
                <th class="label-cell">互联范围</th>
                <td>
                  <el-select
                    v-model="wiringForm.config.interconnect_scope"
                    :disabled="!peerSectionEnabled"
                    style="width: 100%"
                    @change="onInterconnectScopeChange"
                  >
                    <el-option
                      v-for="o in INTERCONNECT_SCOPE_OPTIONS"
                      :key="o.value"
                      :label="o.label"
                      :value="o.value"
                    />
                  </el-select>
                </td>
              </tr>
              <template v-if="peerSectionEnabled && isIntraInterconnect">
                <tr>
                  <th class="label-cell">peer-link</th>
                  <td>
                    <el-switch v-model="wiringForm.config.enable_peer_link" />
                    <span class="inline-label">UPLINK 末口互联</span>
                  </td>
                  <th class="label-cell">末口数量</th>
                  <td>
                    <el-input-number
                      v-model="wiringForm.config.peer_tail_count"
                      :min="1"
                      :max="8"
                      controls-position="right"
                      style="width: 100%"
                    />
                  </td>
                </tr>
                <tr>
                  <th class="label-cell">DAD</th>
                  <td>
                    <el-switch v-model="wiringForm.config.enable_dad" />
                    <span class="inline-label">DOWNLINK 末口互联</span>
                  </td>
                  <th class="label-cell">末口数量</th>
                  <td>
                    <el-input-number
                      v-model="wiringForm.config.dad_tail_count"
                      :min="1"
                      :max="8"
                      controls-position="right"
                      style="width: 100%"
                    />
                  </td>
                </tr>
                <tr>
                  <th class="label-cell">LAG 模式</th>
                  <td>
                    <el-select v-model="wiringForm.config.lag_mode" style="width: 100%">
                      <el-option label="LACP" value="LACP" />
                      <el-option label="STATIC" value="STATIC" />
                    </el-select>
                  </td>
                  <th class="label-cell">互联速率</th>
                  <td>
                    <el-select v-model="wiringForm.config.peer_link_speed" style="width: 100%">
                      <el-option v-for="s in SPEED_OPTIONS" :key="s" :label="s" :value="s" />
                    </el-select>
                  </td>
                </tr>
              </template>
              <template v-else-if="peerSectionEnabled">
                <tr>
                  <th class="label-cell">组间原则</th>
                  <td colspan="3">
                    <div class="pool-legend" style="margin:0">
                      默认手动指定端口对；若选自动，则取各板卡末口交叉互联，并保证源/目标组每台设备至少 1 条线。
                    </div>
                  </td>
                </tr>
                <tr>
                  <th class="label-cell">板卡末口数</th>
                  <td>
                    <el-input-number
                      v-model="wiringForm.config.peer_tail_count"
                      :min="1"
                      :max="8"
                      controls-position="right"
                      style="width: 100%"
                    />
                  </td>
                  <th class="label-cell">互联速率</th>
                  <td>
                    <el-select v-model="wiringForm.config.peer_link_speed" style="width: 100%">
                      <el-option v-for="s in SPEED_OPTIONS" :key="s" :label="s" :value="s" />
                    </el-select>
                  </td>
                </tr>
              </template>
              <tr v-else>
                <th class="label-cell" colspan="4">
                  <span class="pool-legend" style="margin:0">
                    连接类型选「交换机到交换机互联」后可配置组内 Peer/DAD 或组间交叉。
                  </span>
                </th>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 4 介质与距离 -->
        <div class="sheet-block">
          <div class="sheet-title">4. 线缆介质/与距离</div>
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
        <el-button @click="wiringDrawerVisible = false">关闭</el-button>
      </div>
    </el-drawer>

    <el-dialog
      v-model="pairPreviewVisible"
      :title="`端口对确认 · ${pairPreviewScenario || ''}`"
      width="860px"
      destroy-on-close
    >
      <p class="pool-legend" style="margin-top: 0">
        {{ devicePortLinkHint }} 可修改任一侧端口后确认应用。
      </p>
      <el-table :data="pairPreviewRows" size="small" border max-height="420">
        <el-table-column label="源设备" min-width="140">
          <template #default="{ row }">
            <el-select
              v-model="row.source_node_id"
              filterable
              style="width: 100%"
              @change="row.source_port_id = ''; onPreviewSourcePortChange(row)"
            >
              <el-option
                v-for="n in sourceDeviceOptions"
                :key="n.id"
                :label="`${n.name} · ${n.groups}`"
                :value="n.id"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="源端口" min-width="160">
          <template #default="{ row }">
            <el-select
              v-model="row.source_port_id"
              filterable
              style="width: 100%"
              @change="onPreviewSourcePortChange(row)"
            >
              <el-option
                v-for="o in portsForNodeInForm(row.source_node_id)"
                :key="o.id"
                :label="o.label"
                :value="o.id"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="目标设备" min-width="140">
          <template #default="{ row }">
            <el-select
              v-model="row.target_node_id"
              filterable
              style="width: 100%"
              @change="row.target_port_id = ''; onPreviewTargetPortChange(row)"
            >
              <el-option
                v-for="n in targetDeviceOptions"
                :key="n.id"
                :label="`${n.name} · ${n.groups}`"
                :value="n.id"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="目标端口" min-width="160">
          <template #default="{ row }">
            <el-select
              v-model="row.target_port_id"
              filterable
              style="width: 100%"
              @change="onPreviewTargetPortChange(row)"
            >
              <el-option
                v-for="o in portsForNodeInForm(row.target_node_id)"
                :key="o.id"
                :label="o.label"
                :value="o.id"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="" width="64" align="center">
          <template #default="{ $index }">
            <el-button link type="danger" @click="removePreviewPairRow($index)">删</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 10px">
        <el-button size="small" @click="addPreviewPairRow">添加端口对</el-button>
      </div>
      <template #footer>
        <el-button @click="pairPreviewVisible = false">取消</el-button>
        <el-button type="primary" :loading="pairPreviewLoading" @click="confirmPairPreviewApply">
          确认布线
        </el-button>
      </template>
    </el-dialog>

    <DeviceGroupManageDialog
      v-model="groupDialogVisible"
      :catalog="deviceGroupCatalog"
      :design-models="designModels"
      :wiring-rules="wiringRules"
      :mode="groupDialogMode"
      :initial-group="groupDialogInitial"
      @update:catalog="onCatalogFromDialog"
      @created="onDeviceGroupCreated"
      @rename-group="onRenameDeviceGroup"
      @delete-group="onDeleteDeviceGroup"
    />

    <el-dialog
      v-model="batchDeployVisible"
      title="批量部署设备"
      width="420px"
      append-to-body
      destroy-on-close
    >
      <div class="batch-deploy-body">
        <p class="batch-deploy-model">
          模型：
          <strong>{{ batchDeployModel?.name || '—' }}</strong>
          <span v-if="batchDeployModel" class="batch-deploy-sub">
            （{{ batchDeployModel.category }}/{{ batchDeployModel.subtype }}）
          </span>
        </p>
        <el-form label-width="88px">
          <el-form-item label="部署数量" required>
            <el-input-number
              v-model="batchDeployCount"
              :min="1"
              :max="5000"
              :step="1"
              controls-position="right"
              style="width: 100%"
            />
          </el-form-item>
        </el-form>
        <p class="batch-deploy-hint">
          将按网格排布到画布空白区域。也可继续用拖拽或点击画布逐台放置。部署后请「保存布局」。
        </p>
      </div>
      <template #footer>
        <el-button @click="batchDeployVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchDeploying" @click="confirmBatchDeploy">
          部署到画布
        </el-button>
      </template>
    </el-dialog>

    <DeviceGroupDetailDialog
      v-model="groupDetailVisible"
      :group-name="groupDetailName"
      :catalog="deviceGroupCatalog"
      :nodes="nodes"
      :links="links"
      :design-models="designModels"
      :wiring-rules="wiringRules"
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
  grid-template-columns: 280px 1fr 300px;
  height: 100%;
}

.project-side {
  border-right: 1px solid #ebeef5;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 0;
  overflow: hidden;
  min-height: 0;
}

.side-accordion {
  border: none;
  --el-collapse-header-height: 40px;
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.side-accordion :deep(.el-collapse-item__header) {
  padding: 0 4px;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  background: transparent;
  border-bottom: 1px solid #ebeef5;
}

.side-accordion :deep(.el-collapse-item__arrow) {
  margin: 0 6px 0 0;
  order: -1;
}

.side-accordion :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}

.side-accordion :deep(.el-collapse-item__content) {
  padding: 10px 4px 14px;
}

.side-accordion :deep(.model-list) {
  max-height: min(320px, 40vh);
}

.acc-title {
  letter-spacing: 0.02em;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.acc-sub {
  font-size: 11px;
  font-weight: 400;
  color: #909399;
}

.acc-count {
  font-size: 11px;
  font-weight: 500;
  color: #909399;
  background: #f0f2f5;
  border-radius: 10px;
  padding: 0 6px;
  line-height: 18px;
}

.rules-pane {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}

.rules-pane .pane-actions {
  display: flex;
  justify-content: flex-end;
}

.rules-pane .empty-hint {
  font-size: 12px;
  color: #909399;
  padding: 4px 0 8px;
  line-height: 1.4;
}

.rule-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow: auto;
  max-height: min(360px, 42vh);
}

.rule-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 10px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  background: #fff;
}

.rule-card.active {
  background: #ecf5ff;
  border-color: #b3d8ff;
}

.rule-card .meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.rule-card .name {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.rule-card .sub {
  font-size: 11px;
  color: #606266;
}

.rule-card .card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 4px;
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
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  min-width: 0;
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

.batch-deploy-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.batch-deploy-model {
  margin: 0;
  font-size: 13px;
  color: #303133;
}
.batch-deploy-sub {
  color: #909399;
  font-weight: 400;
  margin-left: 4px;
}
.batch-deploy-hint {
  margin: 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
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

.pool-hint {
  font-size: 12px;
  color: #606266;
  line-height: 1.4;
}

.pool-legend {
  margin: 8px 12px 10px;
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}
.inline-pair {
  display: flex;
  gap: 4%;
  align-items: center;
}
.principle-box {
  margin: 0 12px 12px;
  padding: 10px 12px;
  background: #f7f8fa;
  border-left: 3px solid #409eff;
  border-radius: 2px;
}
.principle-title {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 6px;
  color: #303133;
}
.principle-box ul {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: #606266;
  line-height: 1.55;
}
.sheet-sub {
  margin: 8px 12px;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}
.manual-pairs {
  margin: 0 12px 8px;
}

.scenario-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: #606266;
  line-height: 1.45;
}

.scenario-hint strong {
  color: #303133;
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
