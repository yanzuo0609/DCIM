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
  groupsExclusiveToParent,
  MULTI_PARENT_GROUP_HINT,
  nodeGroupList,
  nodeInGroup,
  nodeParentGroups,
  renameNodeGroup,
  setNodeGroups,
  uniqueParentGroupNames,
} from '@/utils/deviceGroups'
import {
  buildWiringGroupSelectOptions,
  emptySlot,
  materializeGroupSlots,
  migrateSlotsFromLegacy,
  normalizeDeviceGroupId,
  parentGroupNamesFromRefs,
  parseSubgroupRef,
  subgroupRef,
  summarizeSlots,
  syncGroupInstances,
  totalSlotCount,
  type DeviceGroupInstanceDef,
  type DeviceGroupSlot,
} from '@/utils/deviceGroupSlots'
import {
  layoutGroupGrid,
} from '@/utils/deviceGroupVisual'
import {
  LINE_STYLE_OPTIONS,
  normalizeLineStyle,
  type TopologyLineStyle,
} from '@/utils/topologyLinkStyle'
import { applyWiringRule, previewWiringPairs, previewWiringScenario, listFreePortOptions, type ProposedPair } from '@/utils/wiringRuleApply'
import {
  ALLOCATION_MODE_OPTIONS,
  CONNECTION_TYPE_OPTIONS,
  FABRIC_ROLE_OPTIONS,
  INTERCONNECT_SCOPE_OPTIONS,
  MEDIA_OPTIONS,
  PORT_POLICY_OPTIONS,
  PORT_POOL_OPTIONS,
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
  type WiringScenarioTemplate,
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
import { filterWiringNodesByLocation } from '@/utils/wiring/locationFilter'
import { alignAutomaticAccessRuleToHardware } from '@/utils/wiring/autoRuleConfig'
import {
  validateAutomaticUplinkDistribution,
  validateManualUplinkDistribution,
} from '@/utils/wiring/redundancy'
import { inferFabricRoleFromDesignModel, normalizePortPurposeAlias, resolveNodeFabricRole } from '@/utils/fabricRole'
import { layoutTopologyByRole } from '@/utils/topologyAutoLayout'
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
  getNetworkTopologyDetail,
  updateNetworkProject,
  type LabEngineInfo,
  type NetworkLabSession,
  type NetworkLink,
  type NetworkNode,
} from '@/api/network'
import { listRooms, type Room } from '@/api/room'
import { listRacks, type Rack } from '@/api/rack'
import { batchMountDevices } from '@/api/device'
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
const selectedNodeIds = ref<string[]>([])
const selectedLinkId = ref<string | null>(null)
/** 左侧模型库选中的设计模型：点击画布批量放置 */
const stampDesignModelId = ref<string | null>(null)
const designModels = ref<NetworkDesignModel[]>([])
const folderTree = ref<NetworkModelFolderTreeNode[]>([])
const bindSaving = ref(false)
const labEngine = ref<LabEngineInfo | null>(null)
const labSession = ref<NetworkLabSession | null>(null)
const labBusy = ref(false)
const labRecordVisible = ref(false)
const labRecordTab = ref<'status' | 'traffic' | 'switches' | 'servers'>('status')
const labLastSyncAt = ref<string | null>(null)
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
const autoWiringBusy = ref(false)
const autoWiringSettingsVisible = ref(false)
const autoWiringSelectedRuleIds = ref<string[]>([])
const lastAutoWiringLinkIds = ref<string[]>([])
const autoWiringSettings = reactive({
  maxPortsPerAccessSwitch: 48,
  groupAsUnit: true,
})
const wiringEditingId = ref<string | null>(null)
const wiringForm = reactive({
  name: '',
  mode: 'sequential' as 'sequential' | 'manual',
  description: '',
  config: defaultWiringConfig() as WiringRuleConfig,
})

const availableAutoWiringRules = computed(() =>
  wiringRules.value.filter((rule) => {
    if (rule.enabled === false || rule.mode === 'manual') return false
    const cfg = normalizeWiringConfig((rule.config || {}) as Record<string, unknown>)
    return String(cfg.allocation_mode || 'AUTO').toUpperCase() === 'AUTO'
  }),
)

interface WiringScenarioPreset {
  value: WiringScenarioTemplate
  title: string
  summary: string
  patch: Partial<WiringRuleConfig>
}

const wiringScenarioPresets: WiringScenarioPreset[] = [
  {
    value: 'CORE_TO_TEN_GIG',
    title: '核心/汇聚 → 万兆交换机',
    summary: '100G/40G 双或四上联，源板卡分散、目标上联口分散',
    patch: { connection_type: 'CORE_TO_ACCESS', source_role: 'CORE', target_role: 'ACCESS', speed: '100G', port_speed: '100G', speed_mode: 'MIN', source_port_purpose: 'DOWNLINK', target_port_purpose: 'UPLINK', source_port_pool: 'OPTICAL', target_port_pool: 'UPLINK', source_port_policy: 'SLOT_SPREAD', link_count: 2, min_link_count: 2, max_link_count: 4, redundancy_mode: 'A_B', device_diversity: 'REQUIRED', card_diversity: 'OPTIONAL', port_diversity: 'REQUIRED', lag: true },
  },
  {
    value: 'TEN_GIG_TO_GIG',
    title: '万兆交换机 → 千兆交换机',
    summary: '优先同速上联，允许按目标能力降速，双设备冗余',
    patch: { connection_type: 'CORE_TO_ACCESS', source_role: 'ACCESS', target_role: 'ACCESS', speed: '10G', port_speed: '10G', speed_mode: 'MIN', source_port_purpose: 'DOWNLINK', target_port_purpose: 'UPLINK', source_port_pool: 'OPTICAL', target_port_pool: 'UPLINK', link_count: 2, min_link_count: 2, max_link_count: 4, redundancy_mode: 'A_B', device_diversity: 'REQUIRED', card_diversity: 'OPTIONAL', port_diversity: 'REQUIRED', lag: true },
  },
  {
    value: 'TEN_GIG_TO_SERVER',
    title: '万兆交换机 → 服务器',
    summary: '服务器业务口双归，交换机和服务器 PCIe/Slot 同时分散',
    patch: { connection_type: 'ACCESS_ENDPOINT', source_role: 'ACCESS', target_role: 'SERVER', speed: '10G', port_speed: '10G', speed_mode: 'EXACT', source_port_purpose: 'DOWNLINK', target_port_purpose: 'SERVER', source_port_pool: 'OPTICAL', target_port_pool: 'OPTICAL', link_count: 2, min_link_count: 2, max_link_count: 4, redundancy_mode: 'A_B', device_diversity: 'REQUIRED', card_diversity: 'REQUIRED', target_port_policy: 'SLOT_SPREAD', port_diversity: 'REQUIRED', lag: true },
  },
  {
    value: 'GIG_TO_SERVER',
    title: '千兆交换机 → 服务器',
    summary: '服务器 1G 电口双归，自动选择 Cat6 网线',
    patch: { connection_type: 'ACCESS_ENDPOINT', source_role: 'ACCESS', target_role: 'SERVER', speed: '1G', port_speed: '1G', speed_mode: 'EXACT', source_port_purpose: 'DOWNLINK', target_port_purpose: 'SERVER', source_port_pool: 'AUTO', target_port_pool: 'AUTO', link_count: 2, min_link_count: 2, max_link_count: 4, redundancy_mode: 'A_B', device_diversity: 'REQUIRED', card_diversity: 'REQUIRED', target_port_policy: 'SLOT_SPREAD', port_media: 'COPPER', media: 'AUTO', lag: true },
  },
  {
    value: 'SWITCH_TO_SECURITY',
    title: '交换机 → 安全设备',
    summary: '防火墙/IPS/IDS/VPN/审计设备业务口双归并跨 Slot',
    patch: { connection_type: 'ACCESS_ENDPOINT', source_role: 'ACCESS', target_role: 'FIREWALL', speed: '10G', port_speed: '10G', speed_mode: 'MIN', source_port_purpose: 'DOWNLINK', target_port_purpose: 'SERVICE', source_port_pool: 'OPTICAL', target_port_pool: 'OPTICAL', link_count: 2, min_link_count: 2, max_link_count: 4, redundancy_mode: 'A_B', device_diversity: 'REQUIRED', card_diversity: 'REQUIRED', target_port_policy: 'SLOT_SPREAD', port_diversity: 'REQUIRED', lag: false },
  },
  {
    value: 'BMC_TO_SERVER',
    title: 'BMC 交换机 → 服务器',
    summary: '按最小空闲口顺序连接每台服务器 BMC 管理口',
    patch: { connection_type: 'BMC_ENDPOINT', source_role: 'ACCESS', target_role: 'SERVER', speed: '1G', port_speed: '1G', speed_mode: 'EXACT', source_port_purpose: 'MGMT', target_port_purpose: 'MGMT', source_port_pool: 'AUTO', target_port_pool: 'AUTO', link_count: 1, min_link_count: 1, max_link_count: 1, redundancy_mode: 'NONE', device_diversity: 'OFF', card_diversity: 'OFF', port_media: 'COPPER', media: 'AUTO', lag: false },
  },
  {
    value: 'BMC_TO_SECURITY',
    title: 'BMC 交换机 → 安全设备',
    summary: '千兆管理交换机连接安全设备 MGMT/OOB 接口',
    patch: { connection_type: 'BMC_ENDPOINT', source_role: 'ACCESS', target_role: 'FIREWALL', speed: '1G', port_speed: '1G', speed_mode: 'EXACT', source_port_purpose: 'MGMT', target_port_purpose: 'MGMT', source_port_pool: 'AUTO', target_port_pool: 'AUTO', link_count: 1, min_link_count: 1, max_link_count: 2, redundancy_mode: 'NONE', device_diversity: 'OFF', card_diversity: 'OFF', port_media: 'COPPER', media: 'AUTO', lag: false },
  },
  {
    value: 'SWITCH_PEER',
    title: '交换机堆叠 / Peer / DAD',
    summary: '组内设备互联，Peer 使用上联尾口，DAD 使用下联尾口',
    patch: { connection_type: 'SWITCH_INTERCONNECT', source_role: 'ACCESS', target_role: 'ACCESS', speed: '100G', port_speed: '100G', speed_mode: 'EXACT', source_port_purpose: 'PEER', target_port_purpose: 'PEER', source_port_pool: 'UPLINK', target_port_pool: 'UPLINK', link_count: 2, min_link_count: 2, max_link_count: 4, peer_link: true, interconnect_scope: 'INTRA_GROUP', enable_peer_link: true, enable_dad: true, peer_tail_count: 2, dad_tail_count: 2, redundancy_mode: 'A_B', port_diversity: 'REQUIRED', lag: true },
  },
  {
    value: 'CORE_INTERCONNECT',
    title: '核心 / 汇聚交换机互联',
    summary: '末端高速口交叉互联，支持双链路或四链路',
    patch: { connection_type: 'SWITCH_INTERCONNECT', source_role: 'CORE', target_role: 'CORE', speed: '100G', port_speed: '100G', speed_mode: 'EXACT', source_port_purpose: 'PEER', target_port_purpose: 'PEER', source_port_pool: 'UPLINK', target_port_pool: 'UPLINK', link_count: 2, min_link_count: 2, max_link_count: 4, peer_link: true, interconnect_scope: 'INTRA_GROUP', enable_peer_link: true, enable_dad: false, peer_tail_count: 2, redundancy_mode: 'A_B', card_diversity: 'REQUIRED', port_diversity: 'REQUIRED', lag: true },
  },
  {
    value: 'CUSTOM',
    title: '自定义综合布线',
    summary: '从空白约束开始，自动、混合或逐端口手工指定',
    patch: {},
  },
]

function applyWiringScenarioPreset(value: WiringScenarioTemplate) {
  const preset = wiringScenarioPresets.find((item) => item.value === value)
  if (!preset) return
  const cfg = wiringForm.config
  const endpointScope = {
    source_groups: [...(cfg.source_groups || [])],
    target_groups: [...(cfg.target_groups || [])],
    source_node_ids: [...(cfg.source_node_ids || [])],
    target_node_ids: [...(cfg.target_node_ids || [])],
  }
  Object.assign(cfg, defaultWiringConfig(), preset.patch, endpointScope, { scenario_template: value })
  cfg.source_group = cfg.source_groups?.[0] ?? null
  cfg.target_group = cfg.target_groups?.[0] ?? null
  if (isSwitchInterconnect(cfg.connection_type) && cfg.interconnect_scope === 'INTRA_GROUP') {
    syncIntraGroupTargets()
  }
  onAllocationModeChange()
  pruneManualPairsAgainstDevices()
}

function autoDetectWiringScenario() {
  const sources = previewSourceNodes.value
  const targets = previewTargetNodes.value
  if (!sources.length || !targets.length) {
    ElMessage.warning('请先在“源端与目标端范围”中选择设备组、设备或角色')
    return
  }
  const sourceIsBmc = sources.some((node) => node.is_bmc_switch)
  const targetHasServer = targets.some((node) => node.kind === 'server')
  const targetHasSecurity = targets.some((node) => node.kind === 'security')
  const sourceHasCore = sources.some((node) => ['CORE', 'AGG'].includes(resolveNodeFabricRole(node)))
  const targetHasCore = targets.some((node) => ['CORE', 'AGG'].includes(resolveNodeFabricRole(node)))
  const sourceHasTenGig = sources.some((node) =>
    (node.port_layout?.ports || []).some((port) => ['10g', '25g', '40_100g'].includes(port.port_type)),
  )
  let template: WiringScenarioTemplate = 'CUSTOM'
  if (sourceIsBmc && targetHasServer) template = 'BMC_TO_SERVER'
  else if (sourceIsBmc && targetHasSecurity) template = 'BMC_TO_SECURITY'
  else if (sourceHasCore && targetHasCore) template = 'CORE_INTERCONNECT'
  else if (sourceHasCore) template = 'CORE_TO_TEN_GIG'
  else if (targetHasServer) template = sourceHasTenGig ? 'TEN_GIG_TO_SERVER' : 'GIG_TO_SERVER'
  else if (targetHasSecurity) template = 'SWITCH_TO_SECURITY'
  else if (sources.some((node) => targets.some((target) => target.id === node.id))) template = 'SWITCH_PEER'
  else template = 'TEN_GIG_TO_GIG'
  const targetScope = {
    groups: [...(wiringForm.config.target_groups || [])],
    nodeIds: [...(wiringForm.config.target_node_ids || [])],
    role: wiringForm.config.target_role,
  }
  const sharesDevice = sources.some((source) => targets.some((target) => target.id === source.id))
  applyWiringScenarioPreset(template)
  if ((template === 'CORE_INTERCONNECT' || template === 'SWITCH_PEER') && !sharesDevice) {
    wiringForm.config.interconnect_scope = 'INTER_GROUP'
    wiringForm.config.target_groups = targetScope.groups
    wiringForm.config.target_group = targetScope.groups[0] ?? null
    wiringForm.config.target_node_ids = targetScope.nodeIds
    wiringForm.config.target_role = targetScope.role
    wiringForm.config.allocation_mode = 'AUTO'
  }
  ElMessage.success(`已识别并应用：${wiringScenarioPresets.find((item) => item.value === template)?.title}`)
}

const selectedNode = computed(() => nodes.value.find((n) => n.id === selectedNodeId.value) || null)
const selectedLink = computed(() => links.value.find((l) => l.id === selectedLinkId.value) || null)
const stampMode = computed(
  () => !!stampDesignModelId.value && !linkMode.value && canEdit.value,
)
const canvasNodes = computed(() => nodes.value.filter((n) => n.on_canvas !== false))
const labTrafficRunning = computed(() => labSession.value?.status === 'running')
const labStatusLabel = computed(() => {
  const status = labSession.value?.status || 'not_synced'
  return ({ running: '流量运行中', stopped: '已停止', synced: '配置已同步', not_synced: '未同步' } as Record<string, string>)[status] || status
})

function labNodeModelAttrs(node: NetworkNode): Record<string, unknown> {
  const model = designModels.value.find((item) => item.id === node.design_model_id)
  return (model?.attributes || {}) as Record<string, unknown>
}

function labBusinessArea(node: NetworkNode): string {
  return nodeParentGroups(node)[0] || node.network_role || '默认业务区'
}

function labVlanConfig(node: NetworkNode): string {
  const attrs = labNodeModelAttrs(node)
  const raw = attrs.vlan_config ?? attrs.vlans ?? attrs.vlan_ids ?? attrs.business_vlan ?? attrs.mgmt_vlan
  if (Array.isArray(raw)) return raw.length ? raw.join(', ') : 'VLAN 1（默认）'
  if (raw != null && String(raw).trim()) return String(raw)
  const linkVlans = links.value
    .filter((link) => link.source_node_id === node.id || link.target_node_id === node.id)
    .map((link) => String(link.label || '').match(/vlan\s*\d+/i)?.[0])
    .filter((value): value is string => !!value)
  return linkVlans.length ? [...new Set(linkVlans)].join(', ') : node.kind === 'server' ? '随接入交换机' : 'VLAN 1（默认）'
}

function labUsedPorts(node: NetworkNode): number {
  const ids = new Set<string>()
  for (const link of links.value) {
    if (link.source_node_id === node.id) ids.add(link.source_port)
    if (link.target_node_id === node.id) ids.add(link.target_port)
  }
  return ids.size
}

const labSwitchRows = computed(() => canvasNodes.value.filter((node) => node.kind === 'switch').map((node) => ({
  id: node.id,
  name: node.name,
  role: node.network_role || 'SWITCH',
  area: labBusinessArea(node),
  vlan: labVlanConfig(node),
  managementIp: node.device?.bmc_ip || node.device?.ip_summary || '未分配',
  ports: node.port_layout?.ports?.length || node.switch_port_count || 0,
  usedPorts: labUsedPorts(node),
  model: designModels.value.find((item) => item.id === node.design_model_id)?.name || '通用交换机',
})))

const labServerRows = computed(() => canvasNodes.value.filter((node) => node.kind === 'server').map((node) => ({
  id: node.id,
  name: node.name,
  area: labBusinessArea(node),
  vlan: labVlanConfig(node),
  businessIp: node.device?.ip_summary || '未分配',
  bmcIp: node.device?.bmc_ip || '未分配',
  vip: node.device?.vip || '—',
  ports: (node.port_layout?.ports || []).map((port) => port.code || port.label || port.id).join(', ') || `${node.switch_port_count || 0} 个接口`,
  usedPorts: labUsedPorts(node),
})))

const labTrafficRows = computed(() => {
  const names = new Map(canvasNodes.value.map((node) => [node.id, node.name]))
  return links.value.map((link, index) => ({
    id: link.id,
    source: names.get(link.source_node_id) || link.source_node_id,
    sourcePort: link.source_label || link.source_port,
    target: names.get(link.target_node_id) || link.target_node_id,
    targetPort: link.target_label || link.target_port,
    speed: link.speed || '1G',
    vlan: String(link.label || '').match(/vlan\s*\d+/i)?.[0] || '按端口配置',
    traffic: labTrafficRunning.value ? `${18 + ((index * 17) % 73)} Mbps` : '0 Mbps',
    packets: labTrafficRunning.value ? 1200 + ((index * 791) % 8800) : 0,
    state: labTrafficRunning.value ? '运行' : '停止',
  }))
})

const previewSourceNodes = computed(() => {
  const cfg = wiringForm.config
  return filterWiringNodesByLocation(matchWiringEndpoints(nodes.value, {
    ids: cfg.source_node_ids,
    role: cfg.source_roles?.length ? cfg.source_roles : cfg.source_role,
    groups: resolveWiringGroups(cfg.source_groups, cfg.source_group),
  }), cfg, 'source')
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
  return filterWiringNodesByLocation(matchWiringEndpoints(nodes.value, {
    ids: cfg.target_node_ids,
    role: cfg.target_roles?.length ? cfg.target_roles : cfg.target_role,
    groups: resolveWiringGroups(cfg.target_groups, cfg.target_group),
  }), cfg, 'target')
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
const modelMatchedPairPreview = computed(() => {
  const rule = {
    id: wiringEditingId.value || 'model-match-preview',
    topology_id: currentId.value || '',
    name: wiringForm.name || '模型接口匹配预览',
    mode: 'sequential',
    enabled: true,
    description: null,
    // 手动规则预览时清空 pairs，走自动配对引擎
    config: { ...wiringForm.config, pairs: [] },
  } as NetworkWiringRule
  return previewWiringPairs(rule, nodes.value, links.value)
})
const previewSourceCount = computed(() => previewSourceNodes.value.length)
const previewTargetCount = computed(() => previewTargetNodes.value.length)

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

function onCableMediaChange() {
  const media = String(wiringForm.config.media || 'CUSTOM_SYNC')
  wiringForm.config.sync_media_color = media === 'CUSTOM_SYNC'
  if (media === 'COPPER') wiringForm.config.port_media = 'COPPER'
  else if (media === 'CUSTOM_SYNC') wiringForm.config.port_media = 'AUTO'
  else if (media.startsWith('LC_LC')) wiringForm.config.port_media = 'LC_LC'
  else if (media.startsWith('MPO')) wiringForm.config.port_media = 'MPO8'
  else wiringForm.config.port_media = 'FIBER'
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

type PortSelectorSide = 'source' | 'target'

function buildPortSelectorCatalog(side: PortSelectorSide) {
  const matched = side === 'source' ? previewSourceNodes.value : previewTargetNodes.value
  const types = new Map<string, number>()
  const slots = new Set<number>()
  const ids = new Map<string, string>()
  let total = 0
  let free = 0
  for (const node of matched) {
    for (const port of node.port_layout?.ports || []) {
      total += 1
      const portType = String(port.port_type || '').trim()
      if (portType) types.set(portType, (types.get(portType) || 0) + 1)
      if (Number.isInteger(port.slot_index)) slots.add(Number(port.slot_index))
      if (!ids.has(port.id)) ids.set(port.id, `${port.label || port.id} · ${portType || 'unknown'}`)
      const used =
        !!port.peer_node_id ||
        !!port.reserved ||
        occupiedPortKeys.value.has(`${node.id}:${port.id}`) ||
        (!!port.label && occupiedPortKeys.value.has(`${node.id}:${port.label}`))
      if (!used) free += 1
    }
  }
  return {
    total,
    free,
    types: [...types.entries()]
      .sort(([a], [b]) => a.localeCompare(b, 'zh-CN', { numeric: true }))
      .map(([value, count]) => ({ value, label: `${value}（${count}口）` })),
    slots: [...slots].sort((a, b) => a - b),
    ids: [...ids.entries()].map(([value, label]) => ({ value, label })),
  }
}

const sourcePortCatalog = computed(() => buildPortSelectorCatalog('source'))
const targetPortCatalog = computed(() => buildPortSelectorCatalog('target'))

function validNumericRange(value: string | null | undefined) {
  if (!value) return true
  return /^\d+(?:\s*[-~–]\s*\d+)?$/.test(String(value).trim())
}

function portSelectorSummary(side: PortSelectorSide) {
  const cfg = wiringForm.config
  const prefix = side === 'source' ? 'source' : 'target'
  const purpose = cfg[`${prefix}_port_purpose` as 'source_port_purpose'] || '不限用途'
  const slots = cfg[`${prefix}_slot_ids` as 'source_slot_ids'] || []
  const slotRange = cfg[`${prefix}_slot_range` as 'source_slot_range']
  const portRange = cfg[`${prefix}_port_range` as 'source_port_range']
  const types = cfg[`${prefix}_port_types` as 'source_port_types'] || []
  return [
    purpose,
    slots.length ? `Slot ${slots.join(',')}` : slotRange ? `Slot ${slotRange}` : '全部Slot',
    types.length ? types.join('/') : '全部类型',
    portRange ? `端口 ${portRange}` : '全部口号',
  ].join(' · ')
}

function ensureManualPairs() {
  if (!Array.isArray(wiringForm.config.pairs)) wiringForm.config.pairs = []
}

function onAllocationModeChange() {
  const mode = String(wiringForm.config.allocation_mode || 'AUTO').toUpperCase()
  wiringForm.mode = mode === 'MANUAL' ? 'manual' : 'sequential'
  if (mode === 'AUTO') {
    applyAutomaticRuleCategory()
    return
  }
  if (mode === 'MANUAL') {
    wiringForm.config.source_roles = []
    wiringForm.config.target_roles = []
    wiringForm.config.source_device_types = []
    wiringForm.config.target_device_types = []
    // 手动定义规则：只填参数，由系统自动配对；可选 pairs 作为覆盖
    if (!Array.isArray(wiringForm.config.pairs)) wiringForm.config.pairs = []
    void hydrateWiringLocationOptions()
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
  if (String(wiringForm.config.target_port_purpose || '') === 'MGMT') {
    wiringForm.config.speed = '1G'
    wiringForm.config.port_speed = '1G'
    wiringForm.config.link_count = 1
    wiringForm.config.min_link_count = 1
    wiringForm.config.max_link_count = 1
    wiringForm.config.target_port_types = ['bmc']
    wiringForm.config.target_connection_strategy = 'FIXED_PORT'
    wiringForm.config.target_port_policy = 'MIN_ASC'
    wiringForm.config.connection_type = 'BMC_ENDPOINT'
    wiringForm.config.peer_link = false
    onEndpointStrategyChange('target')
  } else if (
    Array.isArray(wiringForm.config.target_port_types)
    && wiringForm.config.target_port_types.length === 1
    && wiringForm.config.target_port_types[0] === 'bmc'
  ) {
    wiringForm.config.target_port_types = []
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
    // 组间互联同样支持自动交叉配对；需要逐端口控制时用户可另选混合/手动。
    wiringForm.config.allocation_mode = 'AUTO'
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
const selectedGroupNames = ref<string[]>([])
const groupDetailVisible = ref(false)
const groupDetailName = ref<string | null>(null)
const deviceDetailVisible = ref(false)
const deviceDetailNodeId = ref<string | null>(null)
const deviceDetailNode = computed(() =>
  nodes.value.find((node) => node.id === deviceDetailNodeId.value) || null,
)
/** 画布显示：全设备 / 按组简化；默认按组呈现，有组收拢、无组仍显示单台 */
const canvasViewMode = ref<'devices' | 'groups'>('groups')
/** 组视图图标独立坐标（不移动组内设备，避免 allacc 拖动带动小组） */
const groupViewPositions = ref<Record<string, { x: number; y: number }>>({})
const canvasLineStyle = ref<TopologyLineStyle>('orthogonal')
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

const ruleCategoryOptions = [
  { value: 'CORE_AGG_TO_10G', label: '核心/汇聚 —万兆交换机' },
  { value: 'TEN_GIG_TO_GIG', label: '万兆汇聚—千兆交换机' },
  { value: 'TEN_GIG_TO_ENDPOINT', label: '万兆交换机—服务器设备&&安全设备' },
  { value: 'GIG_TO_ENDPOINT', label: '千兆交换机—服务器设备&&安全设备' },
  { value: 'BMC_TO_SERVER', label: 'BMC交换机—服务器BMC接口' },
  { value: 'SWITCH_STACK_PEER_DAD', label: '交换机堆叠&&Peer-link&&DAD信号线' },
  { value: 'CORE_AGG_INTERCONNECT', label: '核心&&汇聚互联' },
  { value: 'CUSTOM', label: '自定义类型' },
]
const selectedRuleCategoryLabel = computed(() =>
  ruleCategoryOptions.find((item) => item.value === wiringForm.config.rule_category)?.label || '未选择',
)

const automaticCategoryPatches: Record<string, Partial<WiringRuleConfig>> = {
  CORE_AGG_TO_10G: {
    scenario_template: 'CORE_TO_TEN_GIG', connection_type: 'CORE_TO_ACCESS',
    source_role: 'CORE', target_role: 'ACCESS', source_roles: ['CORE', 'AGG'], target_roles: ['ACCESS'],
    source_device_types: ['CORE_SWITCH', 'AGG_SWITCH'], target_device_types: ['ACCESS_SWITCH_10G'],
    source_port_purpose: 'DOWNLINK', target_port_purpose: 'UPLINK', speed: '100G', port_speed: '100G',
    speed_mode: 'MIN', link_count: 2, media: 'MPO_MPO_OS2', device_diversity: 'REQUIRED', card_diversity: 'OPTIONAL',
  },
  TEN_GIG_TO_GIG: {
    scenario_template: 'TEN_GIG_TO_GIG', connection_type: 'CORE_TO_ACCESS',
    source_role: 'ACCESS', target_role: 'ACCESS', source_roles: ['ACCESS'], target_roles: ['ACCESS'],
    source_device_types: ['ACCESS_SWITCH_10G'], target_device_types: ['ACCESS_SWITCH_1G'],
    source_port_purpose: 'DOWNLINK', target_port_purpose: 'UPLINK', speed: '10G', port_speed: '10G',
    speed_mode: 'MIN', link_count: 2, media: 'LC_LC_OM34', device_diversity: 'REQUIRED', card_diversity: 'OPTIONAL',
  },
  TEN_GIG_TO_ENDPOINT: {
    scenario_template: 'TEN_GIG_TO_SERVER', connection_type: 'ACCESS_ENDPOINT',
    source_role: 'ACCESS', target_role: 'SERVER', source_roles: ['ACCESS'], target_roles: ['SERVER', 'FIREWALL'],
    source_device_types: ['ACCESS_SWITCH_10G'], target_device_types: ['SERVER', 'SECURITY_DEVICE'],
    source_port_purpose: 'DOWNLINK', target_port_purpose: 'SERVER', speed: '10G', port_speed: '10G',
    speed_mode: 'MIN', link_count: 2, media: 'LC_LC_OM34', device_diversity: 'REQUIRED', card_diversity: 'REQUIRED',
  },
  GIG_TO_ENDPOINT: {
    scenario_template: 'GIG_TO_SERVER', connection_type: 'ACCESS_ENDPOINT',
    source_role: 'ACCESS', target_role: 'SERVER', source_roles: ['ACCESS'], target_roles: ['SERVER', 'FIREWALL'],
    source_device_types: ['ACCESS_SWITCH_1G'], target_device_types: ['SERVER', 'SECURITY_DEVICE'],
    source_port_purpose: 'DOWNLINK', target_port_purpose: 'SERVER', speed: '1G', port_speed: '1G',
    speed_mode: 'EXACT', link_count: 2, port_media: 'COPPER', media: 'COPPER', device_diversity: 'REQUIRED', card_diversity: 'REQUIRED',
  },
  BMC_TO_SERVER: {
    scenario_template: 'BMC_TO_SERVER', connection_type: 'BMC_ENDPOINT',
    source_role: 'ACCESS', target_role: 'SERVER', source_roles: ['ACCESS'], target_roles: ['SERVER'],
    source_device_types: ['BMC_SWITCH'], target_device_types: ['SERVER'],
    source_port_purpose: 'DOWNLINK', target_port_purpose: 'MGMT', speed: '1G', port_speed: '1G',
    speed_mode: 'EXACT', link_count: 1, port_media: 'COPPER', media: 'COPPER', device_diversity: 'OFF', card_diversity: 'OFF',
  },
  SWITCH_STACK_PEER_DAD: {
    scenario_template: 'SWITCH_PEER', connection_type: 'SWITCH_INTERCONNECT',
    source_role: 'ACCESS', target_role: 'ACCESS', source_roles: ['ACCESS'], target_roles: ['ACCESS'],
    source_device_types: ['ACCESS_SWITCH_10G', 'ACCESS_SWITCH_1G'], target_device_types: ['ACCESS_SWITCH_10G', 'ACCESS_SWITCH_1G'],
    source_port_purpose: 'PEER', target_port_purpose: 'PEER', speed: '100G', port_speed: '100G',
    speed_mode: 'MIN', link_count: 2, media: 'MPO_MPO_OM34', peer_link: true, enable_peer_link: true, enable_dad: true,
    interconnect_scope: 'INTRA_GROUP', device_diversity: 'REQUIRED', card_diversity: 'OPTIONAL',
  },
  CORE_AGG_INTERCONNECT: {
    scenario_template: 'CORE_INTERCONNECT', connection_type: 'SWITCH_INTERCONNECT',
    source_role: 'CORE', target_role: 'CORE', source_roles: ['CORE', 'AGG'], target_roles: ['CORE', 'AGG'],
    source_device_types: ['CORE_SWITCH', 'AGG_SWITCH'], target_device_types: ['CORE_SWITCH', 'AGG_SWITCH'],
    source_port_purpose: 'PEER', target_port_purpose: 'PEER', speed: '100G', port_speed: '100G',
    speed_mode: 'EXACT', link_count: 2, media: 'MPO_MPO_OS2', peer_link: true, enable_peer_link: true, enable_dad: false,
    interconnect_scope: 'INTRA_GROUP', device_diversity: 'REQUIRED', card_diversity: 'REQUIRED',
  },
}

const endpointStrategyOptions = [
  { value: 'ROUND_ROBIN_ASC', label: '多设备间循环递增' },
  { value: 'DEVICE_ASC', label: '单设备顺序递增' },
  { value: 'DEVICE_DESC', label: '多设备间最大接口递减' },
  { value: 'SLOT_ROUND_ROBIN', label: '不同 Slot 循环互联' },
  { value: 'SAME_SLOT_ASC', label: '同 Slot 顺序递增互联' },
  { value: 'SAME_NUMBER', label: '最大接口同号互联' },
  { value: 'CROSS', label: '交叉互联' },
  { value: 'FULL_MESH', label: '口型互联/全互联' },
  { value: 'FIXED_PORT', label: '固定端口' },
  { value: 'MANUAL', label: '手动选择' },
]

const targetInterfaceLimitOptions = computed(() => {
  if (String(wiringForm.config.target_port_purpose || '') === 'MGMT') {
    return [{ label: 'BMC/IPMI', value: 1 }]
  }
  return [
    { label: '单接口', value: 1 },
    { label: '双接口', value: 2 },
    { label: '四接口', value: 4 },
  ]
})

const endpointScopeOptions = computed(() => [
  ...deviceGroupOptions.value.map((group) => ({
    value: `group:${group.value}`,
    label: `设备组 · ${group.label}`,
  })),
  ...canvasNodes.value.map((node) => ({
    value: `node:${node.id}`,
    label: `设备 · ${node.name} [${resolveNodeFabricRole(node)}]`,
  })),
])

function endpointScopeModel(side: 'source' | 'target') {
  return computed<string[]>({
    get: () => [
      ...resolveWiringGroups(
        side === 'source' ? wiringForm.config.source_groups : wiringForm.config.target_groups,
        side === 'source' ? wiringForm.config.source_group : wiringForm.config.target_group,
      ).map((value) => `group:${value}`),
      ...((side === 'source' ? wiringForm.config.source_node_ids : wiringForm.config.target_node_ids) || [])
        .map((value) => `node:${value}`),
    ],
    set: (values) => {
      const groups = values.filter((value) => value.startsWith('group:')).map((value) => value.slice(6))
      const nodeIds = values.filter((value) => value.startsWith('node:')).map((value) => value.slice(5))
      if (side === 'source') {
        wiringForm.config.source_groups = groups
        wiringForm.config.source_group = groups[0] || null
        wiringForm.config.source_node_ids = nodeIds
      } else {
        wiringForm.config.target_groups = groups
        wiringForm.config.target_group = groups[0] || null
        wiringForm.config.target_node_ids = nodeIds
      }
      onDeviceMatchChange()
    },
  })
}

const sourceScopeSelection = endpointScopeModel('source')
const targetScopeSelection = endpointScopeModel('target')

const infraRooms = ref<Room[]>([])
const infraRacks = ref<Rack[]>([])
const infraCatalogLoaded = ref(false)
const locationSyncing = ref(false)

async function loadAllInfraPages<T>(
  fetcher: (page: number, pageSize: number) => Promise<{ items?: T[]; pagination?: { pages?: number } }>,
  pageSize = 500,
): Promise<T[]> {
  const first = await fetcher(1, pageSize)
  const items = [...(first.items || [])]
  const pages = Math.max(1, Number(first.pagination?.pages || 1))
  for (let page = 2; page <= pages; page += 1) {
    const data = await fetcher(page, pageSize)
    items.push(...(data.items || []))
  }
  return items
}

async function ensureInfraRoomsLoaded() {
  if (infraCatalogLoaded.value) return
  infraRooms.value = await loadAllInfraPages<Room>((page, page_size) => listRooms({ page, page_size }))
  infraCatalogLoaded.value = true
}

async function refreshInfraRacksForSelectedRooms(roomIdsOverride?: string[]) {
  const roomIds = [...new Set(
    (roomIdsOverride
      || [
        ...(wiringForm.config.source_room_ids || []),
        ...(wiringForm.config.target_room_ids || []),
      ]
    ).map(String).filter(Boolean),
  )]
  if (!roomIds.length) {
    infraRacks.value = []
    return
  }
  const batches = await Promise.all(
    roomIds.map((room_id) =>
      loadAllInfraPages<Rack>((page, page_size) =>
        listRacks({ room_id, page, page_size, sort: 'code', order: 'asc' }),
      ),
    ),
  )
  infraRacks.value = batches.flat()
}

async function hydrateWiringLocationOptions() {
  try {
    await ensureInfraRoomsLoaded()
    await refreshInfraRacksForSelectedRooms()
  } catch {
    ElMessage.warning('同步机房/机柜列表失败，将回退为拓扑内已知位置')
  }
}

const roomOptions = computed(() => {
  const seen = new Map<string, string>()
  for (const room of infraRooms.value) {
    const label = room.datacenter_name ? `${room.name}（${room.datacenter_name}）` : room.name
    seen.set(room.id, label)
  }
  for (const node of canvasNodes.value) {
    const value = String(node.device?.room_id || node.device?.room_name || '').trim()
    if (value && !seen.has(value)) seen.set(value, node.device?.room_name || value)
  }
  return [...seen].map(([value, label]) => ({ value, label }))
})

function rackOptionsForRooms(roomIds: string[]) {
  const idSet = new Set(roomIds.map(String).filter(Boolean))
  const collator = new Intl.Collator('zh-CN', { numeric: true, sensitivity: 'base' })
  let racks = infraRacks.value
  if (idSet.size) racks = racks.filter((r) => idSet.has(String(r.room_id)))
  if (racks.length) {
    return [...racks]
      .sort((a, b) => {
        const seqDiff = (Number(a.seq_no) || 0) - (Number(b.seq_no) || 0)
        if (seqDiff) return seqDiff
        return collator.compare(String(a.code || ''), String(b.code || ''))
      })
      .map((r) => {
        const code = String(r.code || '').trim()
        const seq = r.seq_no == null ? null : Number(r.seq_no)
        return {
          value: code,
          label: seq != null && Number.isFinite(seq) ? `序${seq} · ${code}` : code,
          seq,
        }
      })
      .filter((o) => o.value)
  }
  return [...new Set(
    canvasNodes.value.map((node) => String(node.device?.rack_code || '').trim()).filter(Boolean),
  )]
    .sort((a, b) => collator.compare(a, b))
    .map((code) => ({ value: code, label: code, seq: null as number | null }))
}

const sourceRackOptions = computed(() => rackOptionsForRooms(wiringForm.config.source_room_ids || []))
const targetRackOptions = computed(() => rackOptionsForRooms(wiringForm.config.target_room_ids || []))
/** 兼容旧模板中的统一机柜选项名 */
const rackOptions = computed(() => {
  const map = new Map<string, string>()
  for (const o of [...sourceRackOptions.value, ...targetRackOptions.value]) {
    map.set(o.value, o.label)
  }
  return [...map.entries()]
    .sort((a, b) => a[0].localeCompare(b[0], 'zh-CN', { numeric: true }))
    .map(([value, label]) => ({ value, label }))
})

async function onLocationRoomChange(side: 'source' | 'target') {
  await refreshInfraRacksForSelectedRooms()
  const codes = new Set(
    (side === 'source' ? sourceRackOptions.value : targetRackOptions.value).map((o) => o.value),
  )
  if (side === 'source') {
    if (wiringForm.config.source_rack_start && !codes.has(wiringForm.config.source_rack_start)) {
      wiringForm.config.source_rack_start = null
    }
    if (wiringForm.config.source_rack_end && !codes.has(wiringForm.config.source_rack_end)) {
      wiringForm.config.source_rack_end = null
    }
  } else {
    if (wiringForm.config.target_rack_start && !codes.has(wiringForm.config.target_rack_start)) {
      wiringForm.config.target_rack_start = null
    }
    if (wiringForm.config.target_rack_end && !codes.has(wiringForm.config.target_rack_end)) {
      wiringForm.config.target_rack_end = null
    }
  }
  onDeviceMatchChange()
}

function filterRackIdsByCodeRange(roomId: string, start: string | null | undefined, end: string | null | undefined) {
  const collator = new Intl.Collator('zh-CN', { numeric: true, sensitivity: 'base' })
  const startCode = String(start || '').trim()
  const endCode = String(end || '').trim()
  return infraRacks.value
    .filter((r) => String(r.room_id) === roomId)
    .filter((r) => {
      const code = String(r.code || '').trim()
      if (!code) return false
      if (startCode && collator.compare(code, startCode) < 0) return false
      if (endCode && collator.compare(code, endCode) > 0) return false
      return true
    })
    .sort((a, b) => collator.compare(String(a.code), String(b.code)))
    .map((r) => r.id)
}

function deviceIdsFromNodes(list: NetworkNode[]) {
  return [...new Set(
    list
      .map((n) => String(n.device_id || n.device?.device_id || '').trim())
      .filter(Boolean),
  )]
}

/** 按规则中的机房/机柜/U 位，将匹配设备同步上架到资源管理（可覆盖原位置） */
async function syncMatchedDevicesToResourceLocation(cfg: WiringRuleConfig) {
  await ensureInfraRoomsLoaded()
  await refreshInfraRacksForSelectedRooms([
    ...(cfg.source_room_ids || []),
    ...(cfg.target_room_ids || []),
  ])
  const sourceDevices = matchWiringEndpoints(nodes.value, {
    ids: cfg.source_node_ids,
    role: cfg.source_roles?.length ? cfg.source_roles : cfg.source_role,
    groups: resolveWiringGroups(cfg.source_groups, cfg.source_group),
  })
  let targetDevices = matchWiringEndpoints(nodes.value, {
    ids: cfg.target_node_ids,
    role: cfg.target_roles?.length ? cfg.target_roles : cfg.target_role,
    groups: resolveWiringGroups(cfg.target_groups, cfg.target_group),
  })
  if (
    (cfg.peer_link || isSwitchInterconnect(cfg.connection_type)) &&
    (cfg.interconnect_scope || 'INTRA_GROUP') === 'INTRA_GROUP'
  ) {
    targetDevices = sourceDevices
  }
  const jobs: Array<Promise<unknown>> = []
  const sides: Array<{
    roomIds: string[]
    rackStart: string | null | undefined
    rackEnd: string | null | undefined
    startU: number | null | undefined
    interval: number | null | undefined
    perRack: number | null | undefined
    devices: NetworkNode[]
  }> = [
    {
      roomIds: cfg.source_room_ids || [],
      rackStart: cfg.source_rack_start,
      rackEnd: cfg.source_rack_end,
      startU: cfg.source_start_u,
      interval: cfg.source_u_interval,
      perRack: cfg.source_devices_per_rack,
      devices: sourceDevices,
    },
    {
      roomIds: cfg.target_room_ids || [],
      rackStart: cfg.target_rack_start,
      rackEnd: cfg.target_rack_end,
      startU: cfg.target_start_u,
      interval: cfg.target_u_interval,
      perRack: cfg.target_devices_per_rack,
      devices: targetDevices,
    },
  ]
  for (const side of sides) {
    if (!side.roomIds.length) continue
    const deviceIds = deviceIdsFromNodes(side.devices)
    if (!deviceIds.length) continue
    const roomId = side.roomIds[0]
    const rackIds = filterRackIdsByCodeRange(roomId, side.rackStart, side.rackEnd)
    const interval = Math.max(1, Number(side.interval) || 1)
    jobs.push(batchMountDevices({
      room_id: roomId,
      device_ids: deviceIds,
      rack_ids: rackIds.length ? rackIds : undefined,
      start_u: side.startU == null ? 1 : Math.max(1, Number(side.startU) || 1),
      gap_u: Math.max(0, interval - 1),
      per_rack_count: side.perRack == null ? undefined : Math.max(1, Number(side.perRack) || 1),
    }))
  }
  if (!jobs.length) return 0
  locationSyncing.value = true
  try {
    const results = await Promise.all(jobs)
    let mounted = 0
    for (const result of results) {
      const data = result as { mounted?: number }
      mounted += Number(data?.mounted || 0)
    }
    if (currentId.value) {
      const detail = await getNetworkTopologyDetail(currentId.value)
      nodes.value = detail.nodes || nodes.value
    }
    return mounted
  } finally {
    locationSyncing.value = false
  }
}

function onEndpointStrategyChange(side: 'source' | 'target') {
  const strategy = side === 'source'
    ? wiringForm.config.source_connection_strategy
    : wiringForm.config.target_connection_strategy
  if (strategy === 'MANUAL') {
    // 仅表示端口选取偏手动预览，不强制填写 pairs
    return
  }
  if (strategy === 'FIXED_PORT') {
    if (side === 'source') wiringForm.config.source_port_policy = 'MIN_ASC'
    else wiringForm.config.target_port_policy = 'MIN_ASC'
    return
  }
  if (strategy === 'SLOT_ROUND_ROBIN') {
    wiringForm.config.card_diversity = 'REQUIRED'
    if (side === 'source') wiringForm.config.source_port_policy = 'SLOT_SPREAD'
    else wiringForm.config.target_port_policy = 'SLOT_SPREAD'
  } else if (strategy === 'SAME_NUMBER') {
    if (side === 'source') wiringForm.config.source_port_policy = 'SAME_NUMBER'
    else wiringForm.config.target_port_policy = 'SAME_NUMBER'
  } else if (strategy === 'DEVICE_DESC') {
    if (side === 'source') wiringForm.config.source_port_policy = 'MAX_DESC'
    else wiringForm.config.target_port_policy = 'MAX_DESC'
  } else if (strategy === 'CROSS' || strategy === 'FULL_MESH') {
    wiringForm.config.device_diversity = 'REQUIRED'
    wiringForm.config.pairing = 'PER_SOURCE_TARGET'
  } else {
    if (side === 'source') wiringForm.config.source_port_policy = 'MIN_ASC'
    else wiringForm.config.target_port_policy = 'MIN_ASC'
  }
}

function syncRuleConnectionTypeFromSheet() {
  const cfg = wiringForm.config
  const sourcePurpose = String(cfg.source_port_purpose || '')
  const targetPurpose = String(cfg.target_port_purpose || '')
  if (
    cfg.rule_category === 'SWITCH_STACK_PEER_DAD' ||
    cfg.rule_category === 'CORE_AGG_INTERCONNECT' ||
    ['PEER', 'DAD'].includes(sourcePurpose) ||
    ['PEER', 'DAD'].includes(targetPurpose)
  ) {
    cfg.connection_type = 'SWITCH_INTERCONNECT'
    cfg.peer_link = true
  } else if (
    cfg.rule_category === 'BMC_TO_SERVER' ||
    sourcePurpose === 'MGMT' ||
    targetPurpose === 'MGMT'
  ) {
    cfg.connection_type = 'BMC_ENDPOINT'
    cfg.peer_link = false
  } else if (['CORE', 'AGG'].includes(String(cfg.source_role)) && cfg.target_role === 'ACCESS') {
    cfg.connection_type = 'CORE_TO_ACCESS'
    cfg.peer_link = false
  } else {
    cfg.connection_type = 'ACCESS_ENDPOINT'
    cfg.peer_link = false
  }
  cfg.scenario_template = 'CUSTOM'
}

function applyAutomaticRuleCategory() {
  const cfg = wiringForm.config
  const category = String(cfg.rule_category || '')
  if (category === 'CUSTOM') {
    cfg.allocation_mode = 'MANUAL'
    wiringForm.mode = 'manual'
    cfg.source_roles = []
    cfg.target_roles = []
    cfg.source_device_types = []
    cfg.target_device_types = []
    if (!Array.isArray(cfg.pairs)) cfg.pairs = []
    void hydrateWiringLocationOptions()
    return
  }
  const patch = automaticCategoryPatches[category]
  if (!patch) return
  Object.assign(cfg, {
    allocation_mode: 'AUTO',
    source_groups: [], target_groups: [], source_group: null, target_group: null,
    source_node_ids: [], target_node_ids: [], pairs: [],
    source_room_ids: [], target_room_ids: [],
    source_rack_start: null, source_rack_end: null, target_rack_start: null, target_rack_end: null,
    source_devices_per_rack: null, target_devices_per_rack: null,
    source_start_u: null, target_start_u: null, source_u_interval: 1, target_u_interval: 1,
    source_port_limit_per_device: null,
    source_connection_strategy: 'ROUND_ROBIN_ASC',
    target_connection_strategy: 'SLOT_ROUND_ROBIN',
    port_media: 'AUTO', media: 'AUTO', peer_link: false, enable_peer_link: false, enable_dad: false,
    interconnect_scope: 'INTRA_GROUP', lag: true, redundancy_mode: 'A_B',
  }, patch, { rule_category: category })
  cfg.source_port_pool = poolFromPurpose(cfg.source_port_purpose)
  cfg.target_port_pool = poolFromPurpose(cfg.target_port_purpose)
  wiringForm.mode = 'sequential'
}

function onRuleCategoryChange() {
  if (String(wiringForm.config.allocation_mode || 'AUTO').toUpperCase() === 'AUTO') {
    applyAutomaticRuleCategory()
  } else {
    syncRuleConnectionTypeFromSheet()
  }
}

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
    id: normalizeDeviceGroupId(g.id, g.name),
    name: g.name,
    role: g.role ?? slots[0]?.role ?? null,
    description: (g.description ?? g.note ?? '').toString(),
    group_type: g.group_type ?? null,
    slots,
    instances: syncGroupInstances(g.name, slots, g.instances as DeviceGroupInstanceDef[] | null | undefined),
    wiring_rule_ids: ruleIds.length ? ruleIds : null,
    wiring_scope: g.wiring_scope === 'topology' ? 'topology' : 'group',
    auto_generate: g.auto_generate !== false,
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

function inferPortableSlotsFromMembers(groupName: string, members: NetworkNode[]): DeviceGroupSlot[] {
  const buckets = new Map<string, DeviceGroupSlot>()
  for (const node of members) {
    const modelId = node.design_model_id || null
    if (!modelId) continue
    const storedSlotId = String(node.contract_device_name || '').startsWith('dgslot:')
      ? String(node.contract_device_name).slice('dgslot:'.length)
      : ''
    const role = (node.network_role as FabricRole) || null
    const key = storedSlotId || `${modelId}:${role || ''}`
    const found = buckets.get(key)
    if (found) {
      found.count += 1
      continue
    }
    const modelName = designModels.value.find((model) => model.id === modelId)?.name
    const roleName = FABRIC_ROLE_OPTIONS.find((option) => option.value === role)?.label
    buckets.set(
      key,
      emptySlot({
        id: storedSlotId || undefined,
        label: modelName || roleName || '设备',
        name_pattern: `${groupName}-{index:02}`,
        role,
        design_model_id: modelId,
        count: 1,
      }),
    )
  }
  return [...buckets.values()]
}

async function recoverGroupBlueprintFromOtherTopology(groupName: string): Promise<DeviceGroupMeta | null> {
  const current = deviceGroupCatalog.value.find((group) => group.name === groupName)
  for (const topology of topologies.value) {
    if (topology.id === currentId.value) continue
    try {
      const detail = await getNetworkTopologyDetail(topology.id)
      const members = detail.nodes.filter((node) => nodeInGroup(node, groupName))
      const slots = inferPortableSlotsFromMembers(groupName, members)
      if (!slots.length) continue
      const recovered = normalizeCatalogEntry({
        ...(current || { name: groupName, role: null, description: '' }),
        name: groupName,
        role: current?.role || slots[0]?.role || null,
        slots,
        planned_count: totalSlotCount(slots),
        design_model_id: slots[0]?.design_model_id || null,
      })
      persistDeviceGroupCatalog([
        ...deviceGroupCatalog.value.filter((group) => group.name !== groupName),
        recovered,
      ])
      return recovered
    } catch {
      // 某个旧拓扑不可读取时继续查找其它同项目拓扑。
    }
  }
  return null
}

/** 补齐目录组名，并把旧拓扑节点中的模型/角色/数量回写为项目级可复用蓝图。 */
function syncCatalogFromNodes() {
  if (!groupScopeId()) return
  const nextCatalog = deviceGroupCatalog.value.map((group) => normalizeCatalogEntry(group))
  const known = new Set(nextCatalog.map((g) => g.name))
  const extras: DeviceGroupMeta[] = []
  for (const n of nodes.value) {
    for (const name of nodeGroupList(n)) {
      // 子组引用（父组::槽位）只用于规则与实例归属，不能同步成新的父设备组。
      if (!name || parseSubgroupRef(name) || known.has(name)) continue
      known.add(name)
      extras.push({
        name,
        role: (n.network_role as FabricRole) || null,
        description: '',
        slots: [],
        planned_count: null,
        design_model_id: null,
        port_pool: null,
        auto_generate: true,
      })
    }
  }
  let changed = extras.length > 0
  for (let index = 0; index < nextCatalog.length; index += 1) {
    const group = nextCatalog[index]
    if (group.slots.length) continue
    const slots = inferPortableSlotsFromMembers(
      group.name,
      nodes.value.filter((node) => nodeInGroup(node, group.name)),
    )
    if (!slots.length) continue
    nextCatalog[index] = normalizeCatalogEntry({
      ...group,
      role: group.role || slots[0]?.role || null,
      slots,
      planned_count: totalSlotCount(slots),
      design_model_id: slots[0]?.design_model_id || null,
    })
    changed = true
  }
  for (let index = 0; index < extras.length; index += 1) {
    const group = extras[index]
    const slots = inferPortableSlotsFromMembers(
      group.name,
      nodes.value.filter((node) => nodeInGroup(node, group.name)),
    )
    if (!slots.length) continue
    extras[index] = normalizeCatalogEntry({
      ...group,
      role: group.role || slots[0]?.role || null,
      slots,
      planned_count: totalSlotCount(slots),
      design_model_id: slots[0]?.design_model_id || null,
    })
  }
  if (!changed) return
  persistDeviceGroupCatalog(
    [...nextCatalog, ...extras].sort((a, b) =>
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

  const cleaned = list.filter((group) => !parseSubgroupRef(group.name))
  if (cleaned.length !== list.length) {
    list = cleaned
    localStorage.setItem(key, JSON.stringify(list))
  }
  deviceGroupCatalog.value = list
  // 写回标准化后的项目级实例清单，确保切换拓扑时实例 ID、名称和数量保持一致。
  localStorage.setItem(key, JSON.stringify(list))
  // 目录可能为空但节点上仍有组名：补齐后列表与「已在组」一致
  syncCatalogFromNodes()
}

function persistDeviceGroupCatalog(list: DeviceGroupMeta[]) {
  deviceGroupCatalog.value = list.filter((g) => !parseSubgroupRef(g.name)).map((g) => normalizeCatalogEntry(g))
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

function selectDeviceFromGroupPane(id: string) {
  if (!nodes.value.some((node) => node.id === id)) return
  selectedNodeIds.value = [id]
  selectedNodeId.value = id
  selectedGroupNames.value = []
  selectedGroupName.value = null
  selectedLinkId.value = null
}

function openDeviceDetailFromGroupPane(id: string) {
  selectDeviceFromGroupPane(id)
  deviceDetailNodeId.value = id
  deviceDetailVisible.value = true
}

function onSelectGroup(name: string) {
  selectedGroupName.value = name
  selectedGroupNames.value = name ? [name] : []
  sideAccordion.value = 'groups'
}

function onSelectGroups(names: string[]) {
  const known = new Set(deviceGroupCatalog.value.map((group) => group.name))
  selectedGroupNames.value = [...new Set(names.filter((name) => known.has(name)))]
  selectedGroupName.value = selectedGroupNames.value.length === 1 ? selectedGroupNames.value[0] : null
}

function onCanvasSelectGroup(name: string | null) {
  selectedGroupName.value = name
  if (name && !selectedGroupNames.value.includes(name)) selectedGroupNames.value = [name]
  selectedNodeId.value = null
  selectedLinkId.value = null
}

function groupViewPosKey() {
  return currentId.value ? `dcim.groupViewPos.${currentId.value}` : null
}

function loadGroupViewPositions() {
  const key = groupViewPosKey()
  if (!key) {
    groupViewPositions.value = {}
    return
  }
  try {
    const raw = localStorage.getItem(key)
    const parsed = raw ? (JSON.parse(raw) as Record<string, { x: number; y: number }>) : null
    groupViewPositions.value = parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    groupViewPositions.value = {}
  }
}

function persistGroupViewPositions() {
  const key = groupViewPosKey()
  if (!key) return
  try {
    localStorage.setItem(key, JSON.stringify(groupViewPositions.value))
  } catch {
    /* ignore quota */
  }
}

function lineStyleKey() {
  return currentId.value ? `dcim.lineStyle.${currentId.value}` : null
}

function loadCanvasLineStyle() {
  const key = lineStyleKey()
  if (!key) {
    canvasLineStyle.value = 'orthogonal'
    return
  }
  try {
    canvasLineStyle.value = normalizeLineStyle(localStorage.getItem(key))
  } catch {
    canvasLineStyle.value = 'orthogonal'
  }
}

function persistCanvasLineStyle() {
  const key = lineStyleKey()
  if (!key) return
  try {
    localStorage.setItem(key, canvasLineStyle.value)
  } catch {
    /* ignore */
  }
}

function applyLineStyleToAll() {
  const style = canvasLineStyle.value
  for (const link of links.value) link.line_style = style
  ElMessage.success('已将当前连线样式应用到全部连线，请保存布局')
}

function setSelectedLineStyle(style: TopologyLineStyle | '') {
  if (!selectedLink.value) return
  selectedLink.value.line_style = style || null
}

function moveGroupGlyph(name: string, x: number, y: number) {
  groupViewPositions.value = {
    ...groupViewPositions.value,
    [name]: { x: Math.max(0, x), y: Math.max(0, y) },
  }
  persistGroupViewPositions()
}

async function onBindDeviceGroupDevices(payload: {
  name: string
  previousName: string | null
  deviceIds: string[]
  candidateIds: string[]
}) {
  const name = payload.name.trim()
  if (!name) return
  const selected = new Set(payload.deviceIds)
  const candidates = new Set(payload.candidateIds)
  const previous = payload.previousName?.trim() || name
  const affectedGroups = new Set<string>()
  let changed = false
  let moved = 0

  for (const node of nodes.value) {
    if (!candidates.has(node.id)) continue
    const parentsBefore = nodeParentGroups(node)
    const selectedForGroup = selected.has(node.id)
    const belongsEditedGroup = parentsBefore.includes(name) || parentsBefore.includes(previous)

    if (selectedForGroup) {
      for (const parent of parentsBefore) {
        if (parent !== name) affectedGroups.add(parent)
      }
      if (parentsBefore.some((parent) => parent !== name && parent !== previous)) moved += 1
      const currentRefs = groupsExclusiveToParent(nodeGroupList(node), name)
      const nextRefs = parentsBefore.includes(name) ? currentRefs : [name]
      if (nodeGroupList(node).join('|') !== nextRefs.join('|')) {
        setNodeGroups(node, nextRefs)
        changed = true
      }
    } else if (belongsEditedGroup) {
      setNodeGroups(node, [])
      affectedGroups.add(previous)
      affectedGroups.add(name)
      changed = true
    }
  }

  for (const group of affectedGroups) {
    if (group !== name && deviceGroupCatalog.value.some((item) => item.name === group)) {
      refreshPortPoolForGroup(group)
    }
  }
  refreshPortPoolForGroup(name)
  if (changed) await persistGroupMembership()
  if (moved) ElMessage.info(`已将 ${moved} 台设备从原设备组转移到「${name}」`)
}

function onCloneDeviceGroups(payload: {
  sourceName: string
  groups: DeviceGroupMeta[]
  fullClone: boolean
  devicePrefix: string
}) {
  if (!payload.groups.length) return
  const normalized = payload.groups.map((group) => normalizeCatalogEntry(group))
  persistDeviceGroupCatalog([
    ...deviceGroupCatalog.value.filter(
      (existing) => !normalized.some((group) => group.name === existing.name),
    ),
    ...normalized,
  ])
  selectedGroupName.value = payload.groups[0]?.name || null
  ElMessage.success(
    `已克隆 ${payload.groups.length} 个设备组并生成 ${normalized.reduce((sum, group) => sum + (group.instances?.length || 0), 0)} 台项目级组内实例`,
  )
}

function onDeviceGroupCreated(name: string) {
  if (groupDialogSide.value === 'source') {
    addGroupToSide('source', name)
  } else if (groupDialogSide.value === 'target') {
    addGroupToSide('target', name)
  }
  groupDialogSide.value = null
  selectedGroupName.value = name
  const raw = deviceGroupCatalog.value.find((group) => group.name === name)
  if (!raw) return
  const def = normalizeCatalogEntry(raw)
  persistDeviceGroupCatalog([
    ...deviceGroupCatalog.value.filter((group) => group.name !== name),
    def,
  ])
  ElMessage.success(`设备组「${name}」已生成 ${def.instances?.length || 0} 台项目级组内实例，可用于所有拓扑`)
}

/** 检视器改组：同一拓扑一台设备只能属于一个父组 */
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
    const requested = patch.device_groups || []
    const parents = uniqueParentGroupNames(requested)
    if (parents.length > 1) {
      ElMessage.warning(MULTI_PARENT_GROUP_HINT)
      return
    }
    const parent = parents[0] || null
    setNodeGroups(
      node,
      parent ? groupsExclusiveToParent([...nodeGroupList(node), ...requested], parent) : [],
    )
    for (const g of nodeGroupList(node)) ensureGroupInCatalog(g, null)
    groupsChanged = true
  } else if ('device_group' in patch) {
    const g = (patch.device_group || '').trim()
    const parent = uniqueParentGroupNames(g ? [g] : [])[0] || null
    setNodeGroups(node, parent ? groupsExclusiveToParent([g], parent) : [])
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
  if (groupViewPositions.value[payload.from]) {
    const { [payload.from]: pos, ...rest } = groupViewPositions.value
    groupViewPositions.value = { ...rest, [payload.to]: pos }
    persistGroupViewPositions()
  }
  await persistGroupMembership()
}

function removeDeviceGroupDefinitions(names: string[]) {
  const removeNames = new Set(names.filter(Boolean))
  if (!removeNames.size) return
  for (const node of nodes.value) {
    if (node.on_canvas !== false) continue
    if (nodeParentGroups(node).some((group) => removeNames.has(group))) setNodeGroups(node, [])
  }
  for (const name of removeNames) removeGroupFromConfig(name)
  persistDeviceGroupCatalog(deviceGroupCatalog.value.filter((group) => !removeNames.has(group.name)))
  const nextPositions = { ...groupViewPositions.value }
  for (const name of removeNames) delete nextPositions[name]
  groupViewPositions.value = nextPositions
  persistGroupViewPositions()
  selectedGroupNames.value = selectedGroupNames.value.filter((name) => !removeNames.has(name))
  if (selectedGroupName.value && removeNames.has(selectedGroupName.value)) selectedGroupName.value = null
}

async function onDeleteDeviceGroup(name: string) {
  const memberIds = nodes.value
    .filter((node) => node.on_canvas !== false && nodeInGroup(node, name))
    .map((node) => node.id)
  const removedCount = deleteNodesByIds(memberIds)
  removeDeviceGroupDefinitions([name])
  if (currentId.value && canEdit.value) await saveCanvas({ silent: true })
  if (removedCount) ElMessage.success(`已同步删除设备组「${name}」及画布中的 ${removedCount} 台设备`)
}

async function onDeleteDeviceGroups(names: string[]) {
  const removeNames = new Set(names.filter(Boolean))
  if (!removeNames.size) return
  const memberIds = nodes.value
    .filter((node) => node.on_canvas !== false && nodeParentGroups(node).some((group) => removeNames.has(group)))
    .map((node) => node.id)
  const removedCount = deleteNodesByIds(memberIds)
  removeDeviceGroupDefinitions([...removeNames])
  if (currentId.value && canEdit.value) await saveCanvas({ silent: true })
  ElMessage.success(`已同步删除 ${removeNames.size} 个设备组和画布中的 ${removedCount} 台设备`)
}

watch(currentId, (id) => {
  // 同项目内切换拓扑：模型库与设备组目录保持项目级共享，仅刷新端口池/实验室
  loadDeviceGroupCatalog()
  loadGroupViewPositions()
  loadCanvasLineStyle()
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

async function autoArrangeTopology(persist = true) {
  if (!currentId.value || !nodes.value.length) {
    ElMessage.warning('当前拓扑暂无可布局设备')
    return
  }
  const positions = layoutTopologyByRole(nodes.value, links.value)
  for (const node of nodes.value) {
    const position = positions.get(node.id)
    if (!position) continue
    node.pos_x = position.x
    node.pos_y = position.y
  }
  groupViewPositions.value = {}
  if (persist && canEdit.value) await saveCanvas()
  ElMessage.success(`已按核心—汇聚—接入—安全—服务器分层整理 ${positions.size} 台设备`)
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
const batchDeployGroup = ref('')
const batchDeployRole = ref<FabricRole | ''>('')
const batchDeployAutoWire = ref(true)
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
  batchDeployGroup.value = ''
  batchDeployRole.value = inferFabricRoleFromDesignModel(model)
  batchDeployAutoWire.value = true
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
      const groupName = batchDeployGroup.value.trim()
      if (groupName) setNodeGroups(created, [groupName])
      created.network_role = batchDeployRole.value || inferFabricRoleFromDesignModel(model)
      working.push(created)
      createdList.push(created)
      nodes.value.push(created)
    }
    const groupName = batchDeployGroup.value.trim()
    if (groupName) {
      syncCatalogFromNodes()
      refreshPortPoolForGroup(groupName, batchDeployRole.value || inferFabricRoleFromDesignModel(model))
      if (batchDeployAutoWire.value) {
        const def = deviceGroupCatalog.value.find((group) => group.name === groupName)
        if (def) applyBoundRulesForGroup(def, { silent: true })
      }
    }
    await autoArrangeTopology(false)
    await saveCanvas()
    selectedNodeId.value = createdList[createdList.length - 1]?.id ?? null
    batchDeployVisible.value = false
    ElMessage.success(`已自动部署、分层布局并保存 ${createdList.length} 台「${model.name}」`)
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

function applyGroupInventoryIdentity(groupName: string, def: DeviceGroupMeta) {
  const inventory = def.instances || []
  if (!inventory.length) return
  for (const slot of def.slots) {
    const identities = inventory.filter((item) => item.slot_id === slot.id)
    const placed = nodes.value.filter(
      (node) =>
        nodeInGroup(node, groupName) &&
        String(node.contract_device_name || '') === `dgslot:${slot.id}`,
    )
    for (let index = 0; index < Math.min(identities.length, placed.length); index += 1) {
      placed[index].name = identities[index].name
      placed[index].network_role = identities[index].role || placed[index].network_role
    }
  }
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
  let def = normalizeCatalogEntry(raw)
  const existingMembers = nodes.value.filter((node) => nodeInGroup(node, name))
  const existingOnCanvas = existingMembers.filter((node) => node.on_canvas !== false)
  if (existingOnCanvas.length) {
    selectedGroupName.value = name
    selectedNodeId.value = existingOnCanvas[existingOnCanvas.length - 1]?.id ?? null
    ElMessage.info(`设备组「${name}」已存在于当前拓扑画布中，共 ${existingOnCanvas.length} 台设备`)
    return
  }
  if (!def.slots.length) {
    if (!existingMembers.length) {
      if (!designModels.value.length) await loadDesignModelsForProject()
      const recovered = await recoverGroupBlueprintFromOtherTopology(name)
      if (!recovered?.slots.length) {
        ElMessage.warning(`组「${name}」在项目内没有可复用的模型与数量配置，请先编辑设备组`)
        return
      }
      def = recovered
    } else {
      const hidden = existingMembers.filter((node) => node.on_canvas === false)
      const positions = layoutGroupGrid(hidden.length, x, y)
      for (let index = 0; index < hidden.length; index += 1) {
        hidden[index].pos_x = positions[index].x
        hidden[index].pos_y = positions[index].y
        hidden[index].on_canvas = true
      }
      selectedGroupName.value = name
      selectedNodeId.value = existingMembers[existingMembers.length - 1]?.id ?? null
      refreshPortPoolForGroup(name)
      const wired = applyBoundRulesForGroup(def, { silent: true })
      ElMessage.success(
        `组「${name}」已复用 ${existingMembers.length} 台组内实例，放入当前画布` +
          (wired > 0 ? `，自动布线 ${wired} 条` : ''),
      )
      return
    }
  }

  const planned = totalSlotCount(def.slots)
  if (def.auto_generate === false && existingMembers.length) {
    const members = existingMembers
    const hidden = members.filter((node) => node.on_canvas === false)
    const positions = layoutGroupGrid(hidden.length, x, y)
    for (let index = 0; index < hidden.length; index += 1) {
      hidden[index].pos_x = positions[index].x
      hidden[index].pos_y = positions[index].y
      hidden[index].on_canvas = true
    }
    selectedGroupName.value = name
    selectedNodeId.value = members[members.length - 1]?.id ?? null
    refreshPortPoolForGroup(name)
    const wired = applyBoundRulesForGroup(def, { silent: true })
    ElMessage.info(
      `组「${name}」已将组内已有设备 ${members.length} 台放入画布，已关闭自动补齐` +
        (wired > 0 ? `，自动布线 ${wired} 条` : ''),
    )
    return
  }
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
  applyGroupInventoryIdentity(name, def)

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

function onSelectNodes(ids: string[]) {
  const valid = new Set(nodes.value.map((node) => node.id))
  selectedNodeIds.value = [...new Set(ids.filter((id) => valid.has(id)))]
  if (selectedNodeIds.value.length === 1) selectedNodeId.value = selectedNodeIds.value[0]
  else if (selectedNodeIds.value.length !== 1) selectedNodeId.value = null
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
  if (id) {
    selectedNodeIds.value = []
    selectedNodeId.value = null
  }
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
    line_style: payload.line_style || canvasLineStyle.value,
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
  if (selectedNodeIds.value.length || selectedNodeId.value || selectedGroupNames.value.length) {
    event.preventDefault()
    void removeSelected()
    return
  }
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

function deleteNodesByIds(ids: string[]): number {
  const removeIds = new Set(ids.filter(Boolean))
  if (!removeIds.size) return 0
  const affectedGroups = new Set<string>()
  for (const node of nodes.value) {
    if (!removeIds.has(node.id)) continue
    for (const group of nodeParentGroups(node)) affectedGroups.add(group)
  }
  links.value = links.value.filter(
    (link) => !removeIds.has(link.source_node_id) && !removeIds.has(link.target_node_id),
  )
  for (const node of nodes.value) {
    node.port_layout?.ports?.forEach((port) => {
      if (port.peer_node_id && removeIds.has(port.peer_node_id)) {
        port.peer_node_id = null
        port.peer_port = null
        port.peer_label = null
      }
    })
  }
  nodes.value = nodes.value.filter((node) => !removeIds.has(node.id))
  for (const group of affectedGroups) {
    if (deviceGroupCatalog.value.some((entry) => entry.name === group)) refreshPortPoolForGroup(group)
  }
  if (linkSourceId.value && removeIds.has(linkSourceId.value)) linkSourceId.value = null
  selectedNodeIds.value = []
  selectedNodeId.value = null
  selectedLinkId.value = null
  stampDesignModelId.value = null
  return removeIds.size
}

function removeNodesFromCanvasByIds(ids: string[]): number {
  const removeIds = new Set(ids.filter(Boolean))
  if (!removeIds.size) return 0
  const affectedGroups = new Set<string>()
  for (const node of nodes.value) {
    if (!removeIds.has(node.id) || node.on_canvas === false) continue
    node.on_canvas = false
    for (const group of nodeParentGroups(node)) affectedGroups.add(group)
  }
  links.value = links.value.filter(
    (link) => !removeIds.has(link.source_node_id) && !removeIds.has(link.target_node_id),
  )
  for (const node of nodes.value) {
    node.port_layout?.ports?.forEach((port) => {
      if (port.peer_node_id && removeIds.has(port.peer_node_id)) {
        port.peer_node_id = null
        port.peer_port = null
        port.peer_label = null
      }
      if (removeIds.has(node.id)) {
        port.peer_node_id = null
        port.peer_port = null
        port.peer_label = null
      }
    })
  }
  for (const group of affectedGroups) refreshPortPoolForGroup(group)
  selectedNodeIds.value = selectedNodeIds.value.filter((id) => !removeIds.has(id))
  if (selectedNodeId.value && removeIds.has(selectedNodeId.value)) selectedNodeId.value = null
  selectedLinkId.value = null
  if (linkSourceId.value && removeIds.has(linkSourceId.value)) linkSourceId.value = null
  return removeIds.size
}

async function removeNodeFromCanvas(id: string) {
  if (!canEdit.value || !currentId.value) return
  const count = removeNodesFromCanvasByIds([id])
  if (!count) return
  await saveCanvas({ silent: true })
  ElMessage.success('设备已移出当前拓扑画布，所属设备组定义保持不变')
}

async function removeGroupFromCanvas(name: string) {
  if (!canEdit.value || !currentId.value) return
  const ids = nodes.value
    .filter((node) => node.on_canvas !== false && nodeInGroup(node, name))
    .map((node) => node.id)
  const count = removeNodesFromCanvasByIds(ids)
  const { [name]: _removed, ...remainingPositions } = groupViewPositions.value
  groupViewPositions.value = remainingPositions
  persistGroupViewPositions()
  selectedGroupNames.value = selectedGroupNames.value.filter((group) => group !== name)
  if (selectedGroupName.value === name) selectedGroupName.value = null
  if (!count) return
  await saveCanvas({ silent: true })
  ElMessage.success(`设备组「${name}」已移出当前画布，组定义与配置仍保留`)
}

async function removeSelected() {
  if (!canEdit.value) return
  const groupNames = [...selectedGroupNames.value]
  const ids = new Set(
    selectedNodeIds.value.length
      ? selectedNodeIds.value
      : selectedNodeId.value
        ? [selectedNodeId.value]
        : [],
  )
  for (const node of nodes.value) {
    if (node.on_canvas !== false && groupNames.some((group) => nodeInGroup(node, group))) ids.add(node.id)
  }
  if (!ids.size && !groupNames.length) return
  const idList = [...ids]
  const names = nodes.value.filter((node) => ids.has(node.id)).map((node) => node.name)
  const message = groupNames.length
    ? `确定从当前画布移除选中的 ${groupNames.length} 个设备组和 ${idList.length} 台设备？相关连线会清理，但设备组定义和配置仍保留。`
    : idList.length === 1
      ? `确定删除设备「${names[0] || idList[0]}」？将同时移除其连线，保存后生效。`
      : `确定删除选中的 ${idList.length} 台设备？将同时移除相关连线，保存后生效。`
  try {
    await ElMessageBox.confirm(message, groupNames.length ? '从画布移除设备组' : idList.length === 1 ? '删除设备' : '批量删除设备', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  if (groupNames.length) {
    const groupMemberIds = new Set(
      nodes.value
        .filter((node) => groupNames.some((group) => nodeInGroup(node, group)))
        .map((node) => node.id),
    )
    const groupCount = removeNodesFromCanvasByIds([...groupMemberIds])
    const standaloneIds = idList.filter((id) => !groupMemberIds.has(id))
    const standaloneCount = deleteNodesByIds(standaloneIds)
    const nextPositions = { ...groupViewPositions.value }
    for (const name of groupNames) delete nextPositions[name]
    groupViewPositions.value = nextPositions
    persistGroupViewPositions()
    selectedGroupNames.value = []
    selectedGroupName.value = null
    await saveCanvas({ silent: true })
    ElMessage.success(`已从画布移除 ${groupNames.length} 个设备组、${groupCount} 台组内设备` + (standaloneCount ? `，另删除 ${standaloneCount} 台独立设备` : '') + '；组列表定义保持不变')
    return
  }
  const count = deleteNodesByIds(idList)
  ElMessage.success(`已删除 ${count} 台设备，请保存布局`)
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

function buildLocalLabSession(status: 'synced' | 'running' | 'stopped'): NetworkLabSession {
  const now = new Date().toISOString()
  const nodeState = status === 'running' ? 'running' : 'stopped'
  return {
    id: labSession.value?.id || `local-${currentId.value || 'topology'}`,
    topology_id: currentId.value || '',
    engine: 'mock-traffic',
    external_lab_path: null,
    status,
    last_sync_at: labLastSyncAt.value || now,
    error_message: null,
    node_map: Object.fromEntries(canvasNodes.value.map((node) => [node.id, node.name])),
    node_status: Object.fromEntries(canvasNodes.value.map((node) => [node.id, nodeState])),
    created_at: labSession.value?.created_at || now,
    updated_at: now,
  }
}

async function loadLabInfo() {
  labEngine.value = {
    engine: 'mock-traffic',
    configured: true,
    base_url: null,
    message: '本地流量模拟：记录交换机、服务器、接口、IP、业务区域和 VLAN 配置',
  }
}

async function loadLabSession() {
  labSession.value = null
  labLastSyncAt.value = null
}

async function runLabSync() {
  if (!currentId.value) return
  labBusy.value = true
  try {
    await saveCanvas({ silent: true })
    labLastSyncAt.value = new Date().toISOString()
    labSession.value = buildLocalLabSession('synced')
    labRecordTab.value = 'status'
    ElMessage.success(`已同步 ${canvasNodes.value.length} 台设备、${links.value.length} 条链路的配置记录`)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '同步配置失败')
  } finally {
    labBusy.value = false
  }
}

async function runLabStart() {
  if (!currentId.value) return
  labBusy.value = true
  try {
    if (!labSession.value) {
      labLastSyncAt.value = new Date().toISOString()
    }
    labSession.value = buildLocalLabSession('running')
    labRecordTab.value = 'traffic'
    ElMessage.success(`流量模拟已启动：${links.value.length} 条链路正在运行`)
  } finally {
    labBusy.value = false
  }
}

async function runLabStop() {
  if (!currentId.value) return
  labBusy.value = true
  try {
    labSession.value = buildLocalLabSession('stopped')
    ElMessage.success('流量模拟已停止，配置记录已保留')
  } finally {
    labBusy.value = false
  }
}

async function runLabRefresh() {
  if (!currentId.value) return
  labRecordTab.value = 'status'
  labRecordVisible.value = true
}

async function openLabConsole() {
  if (!currentId.value) return
  if (selectedNode.value?.kind === 'switch') labRecordTab.value = 'switches'
  else if (selectedNode.value?.kind === 'server') labRecordTab.value = 'servers'
  else labRecordTab.value = 'traffic'
  labRecordVisible.value = true
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
  await Promise.all([loadWiringRules(), hydrateWiringLocationOptions()])
}

async function editWiringRule(rule: NetworkWiringRule) {
  wiringEditingId.value = rule.id
  wiringForm.name = rule.name
  wiringForm.mode = (rule.mode as 'sequential' | 'manual') || 'sequential'
  wiringForm.description = rule.description || ''
  wiringForm.config = normalizeWiringConfig((rule.config || {}) as Record<string, unknown>)
  wiringDrawerVisible.value = true
  sideAccordion.value = 'rules'
  await hydrateWiringLocationOptions()
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
  if (!cfg.rule_category) {
    ElMessage.warning('请选择规则分类')
    return
  }
  const invalidRange = [
    ['源 Slot 范围', cfg.source_slot_range],
    ['目标 Slot 范围', cfg.target_slot_range],
    ['源端口号范围', cfg.source_port_range],
    ['目标端口号范围', cfg.target_port_range],
  ].find(([, value]) => !validNumericRange(value))
  if (invalidRange) {
    ElMessage.warning(`${invalidRange[0]}格式错误，请输入单个数字或范围（例如 1-4）`)
    return
  }
  if (!cfg.speed) {
    ElMessage.warning('请设置接口速率')
    return
  }
  const hasCompleteManualPairs = (cfg.pairs || []).length > 0
    && (cfg.pairs || []).every((p) => p.source_node_id && p.source_port_id && p.target_node_id && p.target_port_id)
  // 手动定义规则：默认按参数自动配对；仅当用户显式填了完整 pairs 时才按 pairs 校验
  if (cfg.allocation_mode === 'MANUAL' && hasCompleteManualPairs) {
    const distributionIssues = validateManualUplinkDistribution(cfg, cfg.pairs || [], nodes.value)
    if (distributionIssues.length) {
      ElMessage.warning(distributionIssues[0])
      return
    }
  } else {
    if (cfg.allocation_mode === 'MANUAL') cfg.pairs = []
    if (!previewSourceNodes.value.length || !previewTargetNodes.value.length) {
      ElMessage.warning('当前拓扑没有匹配到本端或对端设备，请检查设备/组、类型和位置条件')
      return
    }
    if (!sourcePortCatalog.value.free || !targetPortCatalog.value.free) {
      ElMessage.warning('当前模型实例没有满足 Purpose、速率、介质和 Slot 条件的空闲端口')
      return
    }
    if (!modelMatchedPairPreview.value.pairs.length) {
      ElMessage.warning(modelMatchedPairPreview.value.issues[0]?.message || '当前参数无法生成任何有效端口对')
      return
    }
    const distributionIssues = validateAutomaticUplinkDistribution(cfg, previewSourceNodes.value.length)
    if (distributionIssues.length) {
      ElMessage.warning(distributionIssues[0])
      return
    }
  }
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
    if (pairs.length) {
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
      void applyWiringRuleWithLocationSync({
        ...rule,
        mode: 'manual',
        config: { ...(rule.config || {}), allocation_mode: 'MANUAL', pairs },
      })
      return
    }
    // 无显式端口对：按手动定义的规则参数自动布线
    void applyWiringRuleWithLocationSync({
      ...rule,
      mode: 'sequential',
      config: { ...(rule.config || {}), allocation_mode: 'MANUAL', pairs: [] },
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
  void applyWiringRuleWithLocationSync(rule)
}

async function applyWiringRuleWithLocationSync(rule: NetworkWiringRule) {
  const cfg = normalizeWiringConfig((rule.config || {}) as Record<string, unknown>)
  const needLocationSync = !!(
    (cfg.source_room_ids?.length && (cfg.source_rack_start || cfg.source_rack_end || cfg.source_start_u != null))
    || (cfg.target_room_ids?.length && (cfg.target_rack_start || cfg.target_rack_end || cfg.target_start_u != null))
  )
  if (needLocationSync) {
    try {
      const mounted = await syncMatchedDevicesToResourceLocation(cfg)
      if (mounted > 0) {
        ElMessage.success(`已同步 ${mounted} 台设备位置到资源管理（机房/机柜/U 位）`)
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      ElMessage.warning(msg || '设备位置同步未完成，将继续按当前拓扑位置布线')
    }
  }
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
  const cfg = normalizeWiringConfig((rule.config || {}) as Record<string, unknown>)
  const distributionIssues = validateManualUplinkDistribution(cfg, pairs, nodes.value)
  if (distributionIssues.length) {
    ElMessage.warning(distributionIssues[0])
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
  const cablePlan = [...created.reduce((summary, link) => {
    const cable = String(link.cable_type || link.media || '其他线缆')
    const length = link.cable_length_m == null ? '待测量' : `${link.cable_length_m}m`
    const key = `${cable} · ${length}`
    summary.set(key, (summary.get(key) || 0) + 1)
    return summary
  }, new Map<string, number>())]
    .map(([key, count]) => `${key} × ${count}`)
    .join('；')
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
      `已按规则「${rule.name}」${scene ? `（${scene} ${report.scenario_label || ''}）` : ''}自动布线 ${created.length} 条；线缆计划：${cablePlan || '无'}。请保存拓扑`,
    )
  }
  links.value.push(...created)
  return created.length
}

function autoWiringBatchStorageKey(topologyId = currentId.value) {
  return topologyId ? `rackdcim:last-auto-wiring-batch:${topologyId}` : null
}

function loadLastAutoWiringBatch() {
  const key = autoWiringBatchStorageKey()
  if (!key) {
    lastAutoWiringLinkIds.value = []
    return
  }
  try {
    const raw = JSON.parse(localStorage.getItem(key) || '{}') as { linkIds?: unknown }
    lastAutoWiringLinkIds.value = Array.isArray(raw.linkIds)
      ? raw.linkIds.map(String).filter(Boolean)
      : []
  } catch {
    lastAutoWiringLinkIds.value = []
  }
}

function saveLastAutoWiringBatch(linkIds: string[]) {
  const key = autoWiringBatchStorageKey()
  if (!key) return
  lastAutoWiringLinkIds.value = [...linkIds]
  localStorage.setItem(key, JSON.stringify({ linkIds, createdAt: new Date().toISOString() }))
}

function clearLastAutoWiringBatch() {
  const key = autoWiringBatchStorageKey()
  if (key) localStorage.removeItem(key)
  lastAutoWiringLinkIds.value = []
}

async function cancelLastAutoWiring() {
  loadLastAutoWiringBatch()
  const idSet = new Set(lastAutoWiringLinkIds.value)
  const removable = links.value.filter((link) => idSet.has(link.id))
  if (!removable.length) {
    clearLastAutoWiringBatch()
    ElMessage.info('当前拓扑没有可取消的最近一次自动布线')
    return
  }
  try {
    await ElMessageBox.confirm(
      `将取消最近一次一键自动布线生成的 ${removable.length} 条连线。手动连线和此前批次不受影响，是否继续？`,
      '取消自动布线',
      { type: 'warning', confirmButtonText: '取消这次布线', cancelButtonText: '返回' },
    )
  } catch {
    return
  }
  const removeIds = new Set(removable.map((link) => link.id))
  for (const link of removable) {
    clearPeerOnPort(link.source_node_id, link.source_port)
    clearPeerOnPort(link.target_node_id, link.target_port)
  }
  links.value = links.value.filter((link) => !removeIds.has(link.id))
  if (selectedLinkId.value && removeIds.has(selectedLinkId.value)) selectedLinkId.value = null
  await saveCanvas()
  clearLastAutoWiringBatch()
  autoWiringSettingsVisible.value = false
  ElMessage.success(`已取消最近一次自动布线，共删除 ${removable.length} 条连线并保存拓扑`)
}

async function openAutoWiringSettings() {
  if (!wiringRules.value.length) await loadWiringRules()
  loadLastAutoWiringBatch()
  // 自动模式必须保证服务器组不跨交换机组；跨组只能通过手动端口对明确指定。
  autoWiringSettings.groupAsUnit = true
  autoWiringSelectedRuleIds.value = availableAutoWiringRules.value.map((rule) => rule.id)
  autoWiringSettingsVisible.value = true
}

function autoWiringRuleSummary(rule: NetworkWiringRule) {
  const cfg = normalizeWiringConfig((rule.config || {}) as Record<string, unknown>)
  const preset = wiringScenarioPresets.find((item) => item.value === cfg.scenario_template)
  return preset?.title || connectionTypeLabel(cfg.connection_type)
}

function planningLink(pair: ProposedPair, rule: NetworkWiringRule): NetworkLink {
  return {
    id: `planning-${rule.id}-${pair.source_node_id}-${pair.source_port_id}-${pair.target_node_id}-${pair.target_port_id}`,
    topology_id: currentId.value || '',
    link_type: 'switch_server',
    source_node_id: pair.source_node_id,
    source_port: pair.source_port_id,
    target_node_id: pair.target_node_id,
    target_port: pair.target_port_id,
    label: null,
    wiring_rule_id: rule.id,
  }
}

function linkPortOnNode(link: NetworkLink, nodeId: string): string | null {
  if (link.source_node_id === nodeId) return link.source_port
  if (link.target_node_id === nodeId) return link.target_port
  return null
}

function planGroupedAccessRule(
  rule: NetworkWiringRule,
  temporaryLinks: NetworkLink[],
  remainingBySwitch: Map<string, number>,
): { rule: NetworkWiringRule | null; issues: string[] } {
  const cfg = normalizeWiringConfig((rule.config || {}) as Record<string, unknown>)
  const sources = filterWiringNodesByLocation(matchWiringEndpoints(nodes.value, {
    ids: cfg.source_node_ids,
    role: cfg.source_roles?.length ? cfg.source_roles : cfg.source_role,
    groups: resolveWiringGroups(cfg.source_groups, cfg.source_group),
  }), cfg, 'source').filter((node) => node.kind === 'switch')
  const targets = filterWiringNodesByLocation(matchWiringEndpoints(nodes.value, {
    ids: cfg.target_node_ids,
    role: cfg.target_roles?.length ? cfg.target_roles : cfg.target_role,
    groups: resolveWiringGroups(cfg.target_groups, cfg.target_group),
  }), cfg, 'target').filter((node) => node.kind !== 'switch')
  alignAutomaticAccessRuleToHardware(cfg, sources)
  const issues: string[] = []
  if (!sources.length || !targets.length) {
    return { rule: null, issues: [`规则「${rule.name}」没有匹配到接入交换机或目标设备`] }
  }
  if (cfg.source_port_limit_per_device != null) {
    for (const source of sources) {
      remainingBySwitch.set(
        source.id,
        Math.min(remainingBySwitch.get(source.id) || 0, cfg.source_port_limit_per_device),
      )
    }
  }

  const sourceById = new Map(sources.map((node) => [node.id, node]))
  const groupBuckets = new Map<string, NetworkNode[]>()
  if (autoWiringSettings.groupAsUnit) {
    for (const source of sources) {
      const parent = nodeParentGroups(source)[0]
      if (!parent) continue
      if (!groupBuckets.has(parent)) groupBuckets.set(parent, [])
      groupBuckets.get(parent)!.push(source)
    }
    const explicitOrder = uniqueParentGroupNames(resolveWiringGroups(cfg.source_groups, cfg.source_group))
    const ordered = new Map<string, NetworkNode[]>()
    for (const name of explicitOrder) {
      const members = groupBuckets.get(name)
      if (members?.length) ordered.set(name, members)
    }
    for (const [name, members] of groupBuckets) {
      if (!ordered.has(name)) ordered.set(name, members)
    }
    groupBuckets.clear()
    for (const [name, members] of ordered) groupBuckets.set(name, members)
    if (!groupBuckets.size) {
      return {
        rule: null,
        issues: [`规则「${rule.name}」启用了“以组为单位”，但匹配到的接入交换机均未加入设备组`],
      }
    }
  } else {
    groupBuckets.set('全部接入交换机', sources)
  }

  const desiredLinks = Math.max(1, Number(cfg.link_count) || 1)
  const plannedPairs: WiringPair[] = []
  const natural = new Intl.Collator('zh-CN', { numeric: true, sensitivity: 'base' })
  const targetAssignedGroup = new Map<string, string>()

  if (autoWiringSettings.groupAsUnit) {
    const targetBatches = new Map<string, NetworkNode[]>()
    for (const target of [...targets].sort((a, b) => natural.compare(a.name, b.name))) {
      const serverGroup = nodeParentGroups(target)[0] || `单台设备::${target.id}`
      if (!targetBatches.has(serverGroup)) targetBatches.set(serverGroup, [])
      targetBatches.get(serverGroup)!.push(target)
    }
    const capacityShadow = new Map(remainingBySwitch)

    for (const [serverGroup, batchTargets] of targetBatches) {
      const batchExistingSwitchGroups = new Set<string>()
      for (const target of batchTargets) {
        for (const link of temporaryLinks) {
          const otherId = link.source_node_id === target.id
            ? link.target_node_id
            : link.target_node_id === target.id
              ? link.source_node_id
              : null
          const source = otherId ? sourceById.get(otherId) : null
          const switchGroup = source ? nodeParentGroups(source)[0] : null
          if (switchGroup) batchExistingSwitchGroups.add(switchGroup)
        }
      }
      if (batchExistingSwitchGroups.size > 1) {
        issues.push(`服务器组「${serverGroup}」已有线路跨越交换机组 ${[...batchExistingSwitchGroups].join('、')}，自动模式不会继续跨组布线`)
        continue
      }
      const fixedGroup = batchExistingSwitchGroups.size === 1
        ? [...batchExistingSwitchGroups][0]
        : null
      const candidateGroups = fixedGroup
        ? [...groupBuckets].filter(([name]) => name === fixedGroup)
        : [...groupBuckets]
      let assigned = false

      for (const [switchGroup, groupSources] of candidateGroups) {
        const requiredDistinct = desiredLinks
        if (groupSources.length < requiredDistinct) continue
        const localCapacity = new Map(capacityShadow)
        let fits = true
        for (const target of batchTargets) {
          const related = temporaryLinks.filter((link) => {
            const otherId = link.source_node_id === target.id
              ? link.target_node_id
              : link.target_node_id === target.id
                ? link.source_node_id
                : null
            return !!otherId && groupSources.some((source) => source.id === otherId)
          })
          const distinct = new Set(
            related.map((link) => link.source_node_id === target.id ? link.target_node_id : link.source_node_id),
          )
          const needed = Math.max(0, desiredLinks - related.length)
          for (let index = 0; index < needed; index++) {
            let candidates = groupSources.filter((source) => (localCapacity.get(source.id) || 0) > 0)
            if (distinct.size < requiredDistinct) {
              candidates = candidates.filter((source) => !distinct.has(source.id))
            }
            candidates.sort((a, b) =>
              (localCapacity.get(b.id) || 0) - (localCapacity.get(a.id) || 0) ||
              natural.compare(a.name, b.name),
            )
            const selected = candidates[0]
            if (!selected) {
              fits = false
              break
            }
            distinct.add(selected.id)
            localCapacity.set(selected.id, (localCapacity.get(selected.id) || 0) - 1)
          }
          if (!fits || distinct.size < requiredDistinct) {
            fits = false
            break
          }
        }
        if (!fits) continue
        capacityShadow.clear()
        for (const [id, count] of localCapacity) capacityShadow.set(id, count)
        for (const target of batchTargets) targetAssignedGroup.set(target.id, switchGroup)
        assigned = true
        break
      }

      if (!assigned) {
        const capacity = [...groupBuckets].map(([name, members]) =>
          `${name}：${members.map((source) => `${source.name}剩余${capacityShadow.get(source.id) || 0}口`).join('、')}`,
        ).join('；')
        issues.push(`服务器组「${serverGroup}」共 ${batchTargets.length} 台，无法整体放入同一个交换机组。${capacity}`)
      }
    }
    if (issues.length) return { rule: null, issues }
  }

  for (const target of [...targets].sort((a, b) => natural.compare(a.name, b.name))) {
    const ruleSpeed = String(cfg.speed || cfg.port_speed || '').toUpperCase()
    const eligibleTargetSlots = new Set(
      (target.port_layout?.ports || [])
        .filter((port) => {
          const purpose = String(port.purpose || '').toUpperCase()
          const purposeMatches =
            !cfg.target_port_purpose ||
            purpose === String(cfg.target_port_purpose).toUpperCase() ||
            (cfg.target_port_purpose === 'SERVER' && purpose === 'DATA')
          const portSpeed = String(port.port_type || '').toUpperCase()
          const speedMatches =
            !ruleSpeed ||
            (ruleSpeed === '1G' && portSpeed === '1G') ||
            (ruleSpeed === '10G' && portSpeed === '10G') ||
            (ruleSpeed === '25G' && portSpeed === '25G') ||
            ((ruleSpeed === '40G' || ruleSpeed === '100G') && portSpeed === '40_100G')
          return purposeMatches && speedMatches && port.slot_index != null
        })
        .map((port) => Number(port.slot_index)),
    )
    const canSpreadAcrossTargetSlots = eligibleTargetSlots.size >= 2
    const related = temporaryLinks.filter((link) => {
      const otherId = link.source_node_id === target.id
        ? link.target_node_id
        : link.target_node_id === target.id
          ? link.source_node_id
          : null
      return !!otherId && sourceById.has(otherId)
    })
    const existingSourceIds = new Set(
      related.map((link) => link.source_node_id === target.id ? link.target_node_id : link.source_node_id),
    )
    const existingGroups = new Set(
      [...existingSourceIds].map((id) => {
        const source = sourceById.get(id)
        return autoWiringSettings.groupAsUnit ? nodeParentGroups(source)[0] || '未分组' : '全部接入交换机'
      }),
    )
    if (autoWiringSettings.groupAsUnit && existingGroups.size > 1) {
      issues.push(`${target.name} 已跨组连接到 ${[...existingGroups].join('、')}，无法继续按组形成冗余`)
      continue
    }
    const needed = Math.max(0, desiredLinks - related.length)
    if (!needed) continue

    const pinnedGroup = existingGroups.size === 1
      ? [...existingGroups][0]
      : targetAssignedGroup.get(target.id) || null
    const candidateGroups = pinnedGroup
      ? [...groupBuckets].filter(([name]) => name === pinnedGroup)
      : [...groupBuckets]
    let accepted = false

    for (const groupSources of candidateGroups.map(([, members]) => members)) {
      const requiredDistinct = desiredLinks
      if (groupSources.length < requiredDistinct) continue
      const localRemaining = new Map(remainingBySwitch)
      const localLinks = [...temporaryLinks]
      const localPairs: WiringPair[] = []
      const distinctSources = new Set(
        [...existingSourceIds].filter((id) => groupSources.some((source) => source.id === id)),
      )
      const usedTargetSlots = new Set<number>()
      for (const link of related) {
        const portId = linkPortOnNode(link, target.id)
        const slot = target.port_layout?.ports?.find((port) => port.id === portId || port.label === portId)?.slot_index
        if (slot != null) usedTargetSlots.add(slot)
      }
      let failed = false

      for (let index = 0; index < needed; index++) {
        let candidates = groupSources.filter((source) => (localRemaining.get(source.id) || 0) > 0)
        if (distinctSources.size < requiredDistinct) {
          candidates = candidates.filter((source) => !distinctSources.has(source.id))
        }
        candidates.sort((a, b) =>
          (localRemaining.get(b.id) || 0) - (localRemaining.get(a.id) || 0) ||
          natural.compare(a.name, b.name),
        )
        let selectedPair: ProposedPair | null = null
        for (const source of candidates) {
          const unusedTargetSlots = [...new Set(
            (target.port_layout?.ports || [])
              .map((port) => port.slot_index)
              .filter((slot): slot is number => slot != null && !usedTargetSlots.has(slot)),
          )]
          const requireNewTargetSlot =
            cfg.card_diversity === 'REQUIRED' &&
            canSpreadAcrossTargetSlots &&
            desiredLinks > 1 &&
            usedTargetSlots.size < 2
          const previewCfg: WiringRuleConfig = {
            ...cfg,
            source_groups: [],
            source_group: null,
            source_node_ids: [source.id],
            target_groups: [],
            target_group: null,
            target_node_ids: [target.id],
            link_count: 1,
            min_link_count: 1,
            max_link_count: 1,
            allocation_mode: 'AUTO',
            device_diversity: 'OFF',
            card_diversity: 'OFF',
            target_slot_ids: requireNewTargetSlot ? unusedTargetSlots : cfg.target_slot_ids,
            pairs: [],
          }
          if (requireNewTargetSlot && !unusedTargetSlots.length) continue
          const preview = previewWiringPairs(
            { ...rule, config: previewCfg as unknown as Record<string, unknown> },
            nodes.value,
            localLinks,
          )
          if (preview.pairs.length) {
            selectedPair = preview.pairs[0]
            break
          }
        }
        if (!selectedPair) {
          failed = true
          break
        }
        const pair: WiringPair = {
          source_node_id: selectedPair.source_node_id,
          source_port_id: selectedPair.source_port_id,
          target_node_id: selectedPair.target_node_id,
          target_port_id: selectedPair.target_port_id,
        }
        localPairs.push(pair)
        localLinks.push(planningLink(selectedPair, rule))
        distinctSources.add(pair.source_node_id)
        localRemaining.set(pair.source_node_id, (localRemaining.get(pair.source_node_id) || 0) - 1)
        const targetSlot = target.port_layout?.ports?.find((port) => port.id === pair.target_port_id)?.slot_index
        if (targetSlot != null) usedTargetSlots.add(targetSlot)
      }

      if (!failed && localPairs.length === needed && distinctSources.size >= requiredDistinct) {
        plannedPairs.push(...localPairs)
        temporaryLinks.splice(0, temporaryLinks.length, ...localLinks)
        remainingBySwitch.clear()
        for (const [id, count] of localRemaining) remainingBySwitch.set(id, count)
        accepted = true
        break
      }
    }

    if (!accepted) {
      const capacity = [...groupBuckets].map(([name, members]) =>
        `${name}：${members.reduce((sum, source) => sum + (remainingBySwitch.get(source.id) || 0), 0)} 个可用配额`,
      ).join('；')
      issues.push(`${target.name} 需要 ${needed} 条新链路，无法在同一组的不同交换机内完成。${capacity}`)
    }
  }

  if (issues.length || !plannedPairs.length) return { rule: null, issues }
  return {
    rule: {
      ...rule,
      mode: 'manual',
      config: {
        ...cfg,
        allocation_mode: 'MANUAL',
        pairs: plannedPairs,
      } as unknown as Record<string, unknown>,
    },
    issues: [],
  }
}

async function runAllAutoWiringRules() {
  if (!canEdit.value || !currentId.value) {
    ElMessage.warning('请先选择拓扑')
    return
  }
  if (!wiringRules.value.length) await loadWiringRules()
  const selected = new Set(autoWiringSelectedRuleIds.value)
  const runnable = availableAutoWiringRules.value.filter((rule) => selected.has(rule.id))
  if (!runnable.length) {
    ElMessage.warning('请至少选择一条要执行的自动规则')
    return
  }
  autoWiringSettings.groupAsUnit = true
  autoWiringSettingsVisible.value = false
  autoWiringBusy.value = true
  let restoreReplacedLinks: (() => void) | null = null
  try {
    if (designModels.value.length) syncTopologyNodesFromDesignModels(nodes.value, designModels.value)
    const accessRuleIds = new Set(
      runnable
        .filter((rule) => normalizeWiringConfig((rule.config || {}) as Record<string, unknown>).connection_type === 'ACCESS_ENDPOINT')
        .map((rule) => rule.id),
    )
    const originalLinks = [...links.value]
    const portPeerSnapshot = nodes.value.flatMap((node) =>
      (node.port_layout?.ports || []).map((port) => ({
        nodeId: node.id,
        portId: port.id,
        peer_node_id: port.peer_node_id,
        peer_port: port.peer_port,
        peer_label: port.peer_label,
        status: port.status,
      })),
    )
    const replacedLinks = links.value.filter(
      (link) => !!link.wiring_rule_id && accessRuleIds.has(link.wiring_rule_id),
    )
    restoreReplacedLinks = () => {
      links.value = [...originalLinks]
      for (const snapshot of portPeerSnapshot) {
        const node = nodes.value.find((item) => item.id === snapshot.nodeId)
        const port = node?.port_layout?.ports?.find((item) => item.id === snapshot.portId)
        if (!port) continue
        port.peer_node_id = snapshot.peer_node_id
        port.peer_port = snapshot.peer_port
        port.peer_label = snapshot.peer_label
        port.status = snapshot.status
      }
    }
    if (replacedLinks.length) {
      const removeIds = new Set(replacedLinks.map((link) => link.id))
      for (const link of replacedLinks) {
        clearPeerOnPort(link.source_node_id, link.source_port)
        clearPeerOnPort(link.target_node_id, link.target_port)
      }
      links.value = links.value.filter((link) => !removeIds.has(link.id))
    }
    const temporaryLinks: NetworkLink[] = [...links.value]
    const remainingBySwitch = new Map<string, number>()
    for (const node of nodes.value.filter((item) => item.kind === 'switch')) {
      // “最大接口”只约束 DOWNLINK 业务口。先按模型实际下联口数量封顶，再扣除
      // 已占用的下联口；UPLINK、Peer、DAD、MGMT 永远不计入该配额。
      const downlinkPorts = (node.port_layout?.ports || []).filter((port) => {
        if (normalizePortPurposeAlias(port.purpose, node.kind) !== 'DOWNLINK') return false
        const status = String(port.status || '').toUpperCase()
        return status !== 'DISABLED' && status !== 'FAULT' && status !== 'NOT_SUPPORTED'
      })
      const downlinkIds = new Set(downlinkPorts.flatMap((port) => [port.id, port.label].filter(Boolean)))
      const occupied = links.value.filter((link) => {
        const portId = link.source_node_id === node.id
          ? link.source_port
          : link.target_node_id === node.id
            ? link.target_port
            : null
        return !!portId && downlinkIds.has(portId)
      }).length
      const downlinkLimit = Math.min(
        autoWiringSettings.maxPortsPerAccessSwitch,
        downlinkPorts.length,
      )
      remainingBySwitch.set(
        node.id,
        Math.max(0, downlinkLimit - occupied),
      )
    }
    const plannedRules: NetworkWiringRule[] = []
    const capacityIssues: string[] = []
    for (const rule of runnable) {
      const cfg = normalizeWiringConfig((rule.config || {}) as Record<string, unknown>)
      if (cfg.connection_type === 'ACCESS_ENDPOINT') {
        const planned = planGroupedAccessRule(rule, temporaryLinks, remainingBySwitch)
        if (planned.rule) plannedRules.push(planned.rule)
        capacityIssues.push(...planned.issues)
      } else {
        plannedRules.push(rule)
      }
    }
    if (capacityIssues.length) {
      restoreReplacedLinks?.()
      restoreReplacedLinks = null
      await ElMessageBox.alert(capacityIssues.join('\n'), '接口容量不足，未执行自动布线', {
        type: 'warning',
        confirmButtonText: '知道了',
      })
      return
    }
    const beforeLinkIds = new Set(links.value.map((link) => link.id))
    let total = 0
    for (const rule of plannedRules) {
      const cfg = normalizeWiringConfig((rule.config || {}) as Record<string, unknown>)
      const created = commitWiringRuleApply(rule, { silent: true })
      const expected = cfg.connection_type === 'ACCESS_ENDPOINT' && cfg.allocation_mode === 'MANUAL'
        ? cfg.pairs?.length || 0
        : null
      if (expected != null && created !== expected) {
        throw new Error(`规则「${rule.name}」计划 ${expected} 条接入链路，实际仅生成 ${created} 条，已拒绝保存不完整的双上联`)
      }
      total += created
    }
    await autoArrangeTopology(false)
    await saveCanvas()
    restoreReplacedLinks = null
    if (total > 0) {
      saveLastAutoWiringBatch(
        links.value.filter((link) => !beforeLinkIds.has(link.id)).map((link) => link.id),
      )
      ElMessage.success(`已执行 ${plannedRules.length} 条自动规则，生成 ${total} 条连线并保存拓扑`)
    } else {
      ElMessage.info(`已检查 ${runnable.length} 条自动规则，没有需要新增的连线`)
    }
  } catch (error) {
    restoreReplacedLinks?.()
    const message = error instanceof Error ? error.message : '未知错误'
    ElMessage.error(`自动布线失败，已恢复原线路：${message}`)
  } finally {
    autoWiringBusy.value = false
  }
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

watch(currentId, () => loadLastAutoWiringBatch(), { immediate: true })

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
  loadGroupViewPositions()
  loadCanvasLineStyle()
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
                <span class="acc-title">设备与设备组 <span class="acc-sub">实例 · 分组 · 布线</span></span>
              </template>
              <div v-if="!groupScopeId()" class="empty-hint">
                请先在「模型库」选择项目。设备组与画布独立：配置类型/数量后可拖入拓扑，并可作为布线源或目标。
              </div>
              <NetworkDeviceGroupListPane
                v-else
                :catalog="deviceGroupCatalog"
                :nodes="nodes"
                :design-models="designModels"
                :selected-node="selectedNodeId"
                :selected-group="selectedGroupName"
                :disabled="!canEdit || !groupScopeId()"
                @select="onSelectGroup"
                @select-device="selectDeviceFromGroupPane"
                @detail-device="openDeviceDetailFromGroupPane"
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
                  </el-button>                  <el-button
                    type="success"
                    link
                    size="small"
                    :loading="autoWiringBusy"
                    :disabled="!canEdit || !currentId || !wiringRules.length"
                    @click="openAutoWiringSettings"
                  >
                    一键自动布线
                  </el-button>
                  <el-button
                    type="danger"
                    link
                    size="small"
                    :disabled="!canEdit || !currentId || !lastAutoWiringLinkIds.length"
                    @click="cancelLastAutoWiring"
                  >
                    取消布线
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
              <el-radio-button value="devices">全设备</el-radio-button>
              <el-radio-button value="groups">按组简化</el-radio-button>
            </el-radio-group>
            <span v-if="canvasViewMode === 'groups'" class="hint">拖动只移动当前组图标，右键查看组内详情</span>
            <span v-else class="hint">在画布空白区域按住鼠标拖动，可框选多台设备</span>
            <el-select
              v-model="canvasLineStyle"
              size="small"
              style="width: 118px"
              :disabled="!currentId"
              title="连线样式"
              @change="persistCanvasLineStyle"
            >
              <el-option v-for="o in LINE_STYLE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-button
              v-if="canEdit"
              size="small"
              :disabled="!currentId || !links.length"
              @click="applyLineStyleToAll"
            >
              应用到全部
            </el-button>            <el-button
              v-if="canEdit"
              size="small"
              :disabled="!currentId || !nodes.length"
              @click="autoArrangeTopology(true)"
            >
              智能布局
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
              :disabled="!selectedNodeIds.length && !selectedNodeId && !selectedGroupNames.length"
              @click="removeSelected"
            >
              {{ selectedGroupNames.length ? `删除选中（${selectedGroupNames.length}组）` : selectedNodeIds.length > 1 ? `删除选中设备（${selectedNodeIds.length}）` : '删除设备' }}
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
                同步配置
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
              启动流量
            </el-button>
            <el-button
              v-if="canEdit"
              :loading="labBusy"
              :disabled="!currentId"
              @click="runLabStop"
            >
              停止流量
            </el-button>
            <el-button :disabled="!currentId" @click="runLabRefresh">状态</el-button>
            <el-button :disabled="!currentId" @click="openLabConsole">
              模拟控制台
            </el-button>
            <span v-if="labSession" class="lab-status" :class="{ running: labTrafficRunning }">模拟：{{ labStatusLabel }}</span>
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
            :selected-node-ids="selectedNodeIds"
            :selected-link-id="selectedLinkId"
            :selected-group-name="selectedGroupName"
            :selected-group-names="selectedGroupNames"
            :link-mode="linkMode"
            :link-source-id="linkSourceId"
            :stamp-mode="stampMode"
            :view-mode="canvasViewMode"
            :group-roles="groupRolesMap"
            :group-positions="groupViewPositions"
            :line-style="canvasLineStyle"
            :node-lab-status="labSession?.node_status || null"
            :traffic-running="labTrafficRunning"
            @select-node="onSelectNode"
            @select-nodes="onSelectNodes"
            @select-link="onSelectLink"
            @select-group="onCanvasSelectGroup"
            @select-groups="onSelectGroups"
            @inspect-group="openGroupDetail"
            @move-node="moveNode"
            @move-group="moveGroupGlyph"
            @place-node="placeNode"
            @place-device-group="placeDeviceGroup"
            @remove-node-from-canvas="removeNodeFromCanvas"
            @remove-group-from-canvas="removeGroupFromCanvas"
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
            <p>
              <span class="label">样式</span>
            </p>
            <el-select
              size="small"
              style="width: 100%"
              :model-value="selectedLink.line_style || canvasLineStyle"
              :disabled="!canEdit"
              @change="setSelectedLineStyle($event as TopologyLineStyle)"
            >
              <el-option v-for="o in LINE_STYLE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
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

    <el-dialog
      v-model="autoWiringSettingsVisible"
      title="一键自动布线设置"
      width="640px"
      append-to-body
      destroy-on-close
    >
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="系统将先完成全部端口预规划；任一设备接口不足时不会写入部分连线。"
      />
      <el-form label-width="170px" class="auto-wiring-settings-form">
        <el-form-item label="以设备组为分配单位">
          <div class="auto-setting-control">
            <el-switch
              v-model="autoWiringSettings.groupAsUnit"
              disabled
              inline-prompt
              active-text="是"
              inactive-text="否"
            />
            <small>
              自动模式强制开启。同一服务器组只能连接同一个交换机组，组内每台服务器分别连接A/B两台不同交换机；跨组只能手动指定。
            </small>
          </div>
        </el-form-item>
        <el-form-item label="每台交换机最大下联口">
          <div class="auto-setting-control">
            <el-input-number
              v-model="autoWiringSettings.maxPortsPerAccessSwitch"
              :min="1"
              :max="512"
              :step="1"
              controls-position="right"
            />
            <small>只统计连接服务器/安全设备的下联业务口；核心上联、Peer、DAD和管理口不占用该配额。达到上限后整台目标设备转入下一组。</small>
          </div>
        </el-form-item>
        <el-form-item label="本次执行内容">
          <el-checkbox-group v-model="autoWiringSelectedRuleIds" class="auto-rule-checkboxes">
            <el-checkbox
              v-for="rule in availableAutoWiringRules"
              :key="rule.id"
              :value="rule.id"
              border
            >
              <span>{{ rule.name }}</span>
              <small>{{ autoWiringRuleSummary(rule) }}</small>
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button
          type="danger"
          plain
          :disabled="!lastAutoWiringLinkIds.length"
          @click="cancelLastAutoWiring"
        >
          取消最近一次布线
        </el-button>
        <el-button @click="autoWiringSettingsVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="autoWiringBusy"
          :disabled="!autoWiringSelectedRuleIds.length"
          @click="runAllAutoWiringRules"
        >
          预检并自动布线
        </el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="wiringDrawerVisible"
      :title="wiringEditingId ? '编辑规则' : '新建规则'"
      size="1180px"
      class="wiring-drawer"
    >
      <p class="wiring-hint">
        先选择真实布线场景，再限定源端与目标端。系统按设备模型接口能力自动匹配端口、分散冗余路径、判断介质并估算标准线长；
        需要指定端口时切换为混合或手动模式。规则可作用于设备、设备组或两者组合。
      </p>

      <section v-if="false" class="wiring-designer-section scenario-section">
        <div class="designer-section-heading">
          <div>
            <strong>1. 选择综合布线场景</strong>
            <span>选择模板后仍可修改下面的全部参数</span>
          </div>
          <div class="designer-heading-actions">
            <el-tag type="info" effect="plain">
              匹配源 {{ previewSourceCount }} 台 / 目标 {{ previewTargetCount }} 台
            </el-tag>
            <el-button size="small" type="primary" plain @click="autoDetectWiringScenario">
              根据所选设备自动识别
            </el-button>
          </div>
        </div>
        <el-radio-group
          v-model="wiringForm.config.scenario_template"
          class="scenario-preset-grid"
          @change="applyWiringScenarioPreset"
        >
          <el-radio
            v-for="preset in wiringScenarioPresets"
            :key="preset.value"
            :value="preset.value"
            border
            class="scenario-preset-card"
          >
            <span class="scenario-preset-title">{{ preset.title }}</span>
            <small>{{ preset.summary }}</small>
          </el-radio>
        </el-radio-group>
        <div class="scenario-runtime-summary">
          <span>执行算法：{{ detectedWiringScenario.scenario }} · {{ detectedWiringScenario.label }}</span>
          <span>每个目标 {{ wiringForm.config.link_count || 1 }} 条链路</span>
          <span>{{ wiringForm.config.redundancy_mode === 'A_B' ? 'A/B 冗余' : '单路径' }}</span>
          <span>介质与长度：{{ wiringForm.config.media === 'AUTO' ? '自动判断' : wiringForm.config.media }}</span>
        </div>
      </section>

      <div v-if="false" class="wiring-toolbar">
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

      <div class="rule-engine-sheet">
        <div class="rule-engine-title">新建规则</div>
        <table class="rule-engine-table">
          <tbody>
            <tr>
              <th>规则名称</th>
              <td><el-input v-model="wiringForm.name" placeholder="请输入唯一规则名称" /></td>
              <th>规则分类</th>
              <td>
                <el-select v-model="wiringForm.config.rule_category" placeholder="必选" @change="onRuleCategoryChange">
                  <el-option v-for="o in ruleCategoryOptions" :key="o.value" :label="o.label" :value="o.value" />
                </el-select>
              </td>
              <th>生成方式</th>
              <td>
                <el-select v-model="wiringForm.config.allocation_mode" @change="onAllocationModeChange">
                  <el-option label="自动生成规则" value="AUTO" />
                  <el-option label="手动定义规则" value="MANUAL" />
                </el-select>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="isManualAlloc" class="rule-endpoint-section">
          <div class="rule-endpoint-heading">本端设备与接口定义</div>
          <table class="rule-engine-table endpoint-table">
            <tbody>
              <tr>
                <th>本端类型</th>
                <td>
                  <el-select v-model="wiringForm.config.source_role" clearable placeholder="核心层/汇聚层/接入层/应用" @change="syncRuleConnectionTypeFromSheet">
                    <el-option v-for="o in FABRIC_ROLE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
                  </el-select>
                </td>
                <th>本端设备/组</th>
                <td>
                  <el-select v-model="sourceScopeSelection" multiple filterable clearable collapse-tags collapse-tags-tooltip placeholder="选择拓扑实例或设备组">
                    <el-option v-for="o in endpointScopeOptions" :key="o.value" :label="o.label" :value="o.value" />
                  </el-select>
                </td>
                <th>接口类型</th>
                <td>
                  <el-select v-model="wiringForm.config.source_port_purpose" @change="() => { onSourcePurposeChange(); syncRuleConnectionTypeFromSheet() }">
                    <el-option v-for="o in PORT_PURPOSE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
                  </el-select>
                </td>
              </tr>
              <tr>
                <th>本端接口速率</th>
                <td>
                  <el-select v-model="wiringForm.config.speed" clearable @change="wiringForm.config.port_speed = wiringForm.config.speed">
                    <el-option v-for="s in SPEED_OPTIONS" :key="s" :label="s" :value="s" />
                  </el-select>
                </td>
                <th>端口限制使用个数</th>
                <td><el-input-number v-model="wiringForm.config.source_port_limit_per_device" :min="1" :max="1024" controls-position="right" /></td>
                <th>本端接口连接方式</th>
                <td>
                  <el-select v-model="wiringForm.config.source_connection_strategy" @change="onEndpointStrategyChange('source')">
                    <el-option v-for="o in endpointStrategyOptions" :key="o.value" :label="o.label" :value="o.value" />
                  </el-select>
                </td>
              </tr>
              <tr>
                <th>介质</th>
                <td>
                  <el-select v-model="wiringForm.config.media" @change="onCableMediaChange">
                    <el-option v-for="o in MEDIA_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
                  </el-select>
                </td>
                <th>介质颜色</th>
                <td><el-switch v-model="wiringForm.config.sync_media_color" active-text="和对端介质颜色同步" /></td>
                <th>业务类型</th>
                <td>
                  <el-select v-model="wiringForm.config.business_plane" clearable allow-create filterable placeholder="专网/互联网/其他">
                    <el-option label="专网" value="专网" /><el-option label="互联网" value="互联网" /><el-option label="其他" value="其他" />
                  </el-select>
                </td>
              </tr>
            </tbody>
          </table>
          <div class="location-caption">本端设备位置（可选；与设备/组/角色条件取交集；可同步资源管理）</div>
          <table class="rule-engine-table location-table">
            <tbody>
              <tr>
                <th>机房</th><td><el-select v-model="wiringForm.config.source_room_ids" multiple clearable collapse-tags filterable placeholder="全部机房" @change="onLocationRoomChange('source')"><el-option v-for="o in roomOptions" :key="o.value" :label="o.label" :value="o.value" /></el-select></td>
                <th>起始机柜</th><td><el-select v-model="wiringForm.config.source_rack_start" clearable filterable allow-create placeholder="编号或顺序号" @change="onDeviceMatchChange"><el-option v-for="o in sourceRackOptions" :key="o.value" :label="o.label" :value="o.value" /></el-select></td>
                <th>终止机柜</th><td><el-select v-model="wiringForm.config.source_rack_end" clearable filterable allow-create placeholder="编号或顺序号" @change="onDeviceMatchChange"><el-option v-for="o in sourceRackOptions" :key="o.value" :label="o.label" :value="o.value" /></el-select></td>
              </tr>
              <tr>
                <th>单机柜设备台数</th><td><el-input-number v-model="wiringForm.config.source_devices_per_rack" :min="1" :max="100" controls-position="right" /></td>
                <th>起始 U 为</th><td><el-input-number v-model="wiringForm.config.source_start_u" :min="1" :max="60" controls-position="right" /></td>
                <th>间隔 U 位数</th><td><el-input-number v-model="wiringForm.config.source_u_interval" :min="1" :max="60" controls-position="right" /></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="isManualAlloc" class="rule-endpoint-section target-section">
          <div class="rule-endpoint-heading">对端设备与接口定义</div>
          <table class="rule-engine-table endpoint-table">
            <tbody>
              <tr>
                <th>对端类型</th>
                <td><el-select v-model="wiringForm.config.target_role" clearable placeholder="核心层/汇聚层/接入层/应用" @change="syncRuleConnectionTypeFromSheet"><el-option v-for="o in FABRIC_ROLE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" /></el-select></td>
                <th>对端设备/组</th>
                <td><el-select v-model="targetScopeSelection" multiple filterable clearable collapse-tags collapse-tags-tooltip placeholder="选择拓扑实例或设备组"><el-option v-for="o in endpointScopeOptions" :key="o.value" :label="o.label" :value="o.value" /></el-select></td>
                <th>接口类型</th>
                <td><el-select v-model="wiringForm.config.target_port_purpose" @change="() => { onTargetPurposeChange(); syncRuleConnectionTypeFromSheet() }"><el-option v-for="o in PORT_PURPOSE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" /></el-select></td>
              </tr>
              <tr>
                <th>对端接口速率</th>
                <td><el-select v-model="wiringForm.config.speed" clearable @change="wiringForm.config.port_speed = wiringForm.config.speed"><el-option v-for="s in SPEED_OPTIONS" :key="s" :label="s" :value="s" /></el-select></td>
                <th>对端接口限制</th>
                <td><el-select v-model="wiringForm.config.link_count"><el-option v-for="o in targetInterfaceLimitOptions" :key="o.value" :label="o.label" :value="o.value" /></el-select></td>
                <th>对端接口连接方式</th>
                <td><el-select v-model="wiringForm.config.target_connection_strategy" @change="onEndpointStrategyChange('target')"><el-option v-for="o in endpointStrategyOptions" :key="o.value" :label="o.label" :value="o.value" /></el-select></td>
              </tr>
              <tr>
                <th>介质</th><td><el-select v-model="wiringForm.config.media" @change="onCableMediaChange"><el-option v-for="o in MEDIA_OPTIONS" :key="o.value" :label="o.label" :value="o.value" /></el-select></td>
                <th>介质颜色</th><td><span class="sync-media-text">{{ wiringForm.config.sync_media_color ? '和本端介质颜色同步' : '独立设置' }}</span></td>
                <th>业务类型</th><td><el-select v-model="wiringForm.config.business_plane" clearable allow-create filterable><el-option label="专网" value="专网" /><el-option label="互联网" value="互联网" /><el-option label="其他" value="其他" /></el-select></td>
              </tr>
            </tbody>
          </table>
          <div class="location-caption">对端设备位置（可选；与设备/组/角色条件取交集；可同步资源管理）</div>
          <table class="rule-engine-table location-table">
            <tbody>
              <tr>
                <th>机房</th><td><el-select v-model="wiringForm.config.target_room_ids" multiple clearable collapse-tags filterable placeholder="全部机房" @change="onLocationRoomChange('target')"><el-option v-for="o in roomOptions" :key="o.value" :label="o.label" :value="o.value" /></el-select></td>
                <th>起始机柜</th><td><el-select v-model="wiringForm.config.target_rack_start" clearable filterable allow-create placeholder="编号或顺序号" @change="onDeviceMatchChange"><el-option v-for="o in targetRackOptions" :key="o.value" :label="o.label" :value="o.value" /></el-select></td>
                <th>终止机柜</th><td><el-select v-model="wiringForm.config.target_rack_end" clearable filterable allow-create placeholder="编号或顺序号" @change="onDeviceMatchChange"><el-option v-for="o in targetRackOptions" :key="o.value" :label="o.label" :value="o.value" /></el-select></td>
              </tr>
              <tr>
                <th>单机柜设备台数</th><td><el-input-number v-model="wiringForm.config.target_devices_per_rack" :min="1" :max="100" controls-position="right" /></td>
                <th>起始 U 为</th><td><el-input-number v-model="wiringForm.config.target_start_u" :min="1" :max="60" controls-position="right" /></td>
                <th>间隔 U 位数</th><td><el-input-number v-model="wiringForm.config.target_u_interval" :min="1" :max="60" controls-position="right" /></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="isManualAlloc" class="rule-match-summary">
          <strong>模型参数匹配：</strong>
          本端 {{ previewSourceCount }} 台、{{ sourcePortCatalog.free }}/{{ sourcePortCatalog.total }} 个空闲接口；
          对端 {{ previewTargetCount }} 台、{{ targetPortCatalog.free }}/{{ targetPortCatalog.total }} 个空闲接口。
          按当前手动规则可自动生成 {{ modelMatchedPairPreview.pairs.length }} 条端口对；执行规则时系统将自动完成布线（无需逐条指定接口）。
          <span v-if="modelMatchedPairPreview.issues.length" class="auto-summary-warning">{{ modelMatchedPairPreview.issues[0]?.message }}</span>
        </div>

        <div v-if="isManualAlloc && (wiringForm.config.pairs || []).length" class="compact-manual-pairs">
          <div class="location-caption">端口对覆盖（可选；留空则完全按规则自动配对）</div>
          <el-table :data="wiringForm.config.pairs || []" size="small" border>
            <el-table-column label="本端设备" min-width="160"><template #default="{ row }"><el-select v-model="row.source_node_id" filterable @change="onManualSourceDeviceChange(row)"><el-option v-for="n in sourceDeviceOptions" :key="n.id" :label="n.name" :value="n.id" /></el-select></template></el-table-column>
            <el-table-column label="本端接口" min-width="180"><template #default="{ row }"><el-select v-model="row.source_port_id" filterable><el-option v-for="o in portsForNodeInForm(row.source_node_id)" :key="o.id" :label="o.label" :value="o.id" /></el-select></template></el-table-column>
            <el-table-column label="对端设备" min-width="160"><template #default="{ row }"><el-select v-model="row.target_node_id" filterable @change="onManualTargetDeviceChange(row)"><el-option v-for="n in targetDeviceOptions" :key="n.id" :label="n.name" :value="n.id" /></el-select></template></el-table-column>
            <el-table-column label="对端接口" min-width="180"><template #default="{ row }"><el-select v-model="row.target_port_id" filterable><el-option v-for="o in portsForNodeInForm(row.target_node_id)" :key="o.id" :label="o.label" :value="o.id" /></el-select></template></el-table-column>
            <el-table-column width="64"><template #default="{ $index }"><el-button link type="danger" @click="removeManualPairRow($index)">删除</el-button></template></el-table-column>
          </el-table>
          <el-button size="small" style="margin-top:8px" @click="addManualPairRow">添加端口对</el-button>
        </div>

        <div v-else class="rule-auto-summary">
          <strong>{{ selectedRuleCategoryLabel }}</strong>
          <span>系统已自动确定设备硬件分类、两端角色、Purpose、接口速率、介质和冗余方式。</span>
          <div class="auto-rule-limits">
            <label>
              最多使用交换机数量
              <el-input-number v-model="wiringForm.config.max_source_devices" :min="1" :max="256" controls-position="right" />
            </label>
            <label>
              每台交换机最大 DOWNLINK 口数
              <el-input-number v-model="wiringForm.config.source_port_limit_per_device" :min="1" :max="1024" controls-position="right" />
            </label>
          </div>
          <span>当前拓扑匹配本端 {{ previewSourceCount }} 台、对端 {{ previewTargetCount }} 台，可规划 {{ modelMatchedPairPreview.pairs.length }} 条链路。</span>
          <span v-if="modelMatchedPairPreview.issues.length" class="auto-summary-warning">{{ modelMatchedPairPreview.issues[0]?.message }}</span>
        </div>

        <table class="rule-engine-table cable-rule-table">
          <tbody>
            <tr>
              <th>线缆长度估算方法</th>
              <td><el-select v-model="wiringForm.config.cable_length_mode"><el-option label="机柜高度 + 跨机柜距离 + 通道预留" value="AUTO" /><el-option label="固定长度" value="FIXED" /></el-select></td>
              <th>长度</th>
              <td><el-input-number v-model="wiringForm.config.cable_length_m" :disabled="wiringForm.config.cable_length_mode !== 'FIXED'" :min="0.5" :max="10000" :step="0.5" controls-position="right" /></td>
              <th>条数</th><td><el-input :model-value="'自动估算（按实际生成链路）'" disabled /></td>
            </tr>
            <tr>
              <th>本端标签</th><td colspan="2"><el-input v-model="wiringForm.config.source_label_template" type="textarea" :rows="2" /></td>
              <th>对端标签</th><td colspan="2"><el-input v-model="wiringForm.config.target_label_template" type="textarea" :rows="2" /></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="false" class="wiring-sheet">
        <!-- 1 设备参数 -->
        <div v-if="false" class="sheet-block">
          <div class="sheet-title">2. 源端与目标端范围</div>
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
        <div v-if="false" class="sheet-block">
          <div class="sheet-title">3. 端口规划与冗余约束</div>
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
                <th class="label-cell">路径冗余</th>
                <td>
                  <el-select v-model="wiringForm.config.redundancy_mode" style="width: 100%">
                    <el-option label="A/B 双路径" value="A_B" />
                    <el-option label="不强制冗余" value="NONE" />
                  </el-select>
                </td>
                <th class="label-cell">跨源设备</th>
                <td>
                  <el-select v-model="wiringForm.config.device_diversity" style="width: 100%">
                    <el-option label="必须（不足则停止）" value="REQUIRED" />
                    <el-option label="优先" value="OPTIONAL" />
                    <el-option label="不要求" value="OFF" />
                  </el-select>
                </td>
              </tr>
              <tr v-if="!isManualAlloc">
                <th class="label-cell">跨 Slot/接口卡</th>
                <td>
                  <el-select v-model="wiringForm.config.card_diversity" style="width: 100%">
                    <el-option label="必须（不足则停止）" value="REQUIRED" />
                    <el-option label="优先" value="OPTIONAL" />
                    <el-option label="不要求" value="OFF" />
                  </el-select>
                </td>
                <th class="label-cell">链路聚合</th>
                <td>
                  <div class="inline-pair">
                    <el-switch v-model="wiringForm.config.lag" inline-prompt active-text="启用" inactive-text="关闭" />
                    <el-select v-model="wiringForm.config.lag_mode" :disabled="!wiringForm.config.lag" style="flex: 1">
                      <el-option label="LACP" value="LACP" />
                      <el-option label="静态聚合" value="STATIC" />
                    </el-select>
                  </div>
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

          <div v-if="!isManualAlloc" class="port-selector-panel">
            <div class="selector-strict-row">
              <div>
                <strong>物理端口精确匹配</strong>
                <p>严格按照 Purpose → 端口池 → Slot → 端口类型/口号 → 速率 → 介质 → 空闲状态筛选。</p>
              </div>
              <el-switch v-model="wiringForm.config.strict_port_match" inline-prompt active-text="严格" inactive-text="兼容" />
            </div>
            <div class="port-selector-grid">
              <section class="endpoint-selector source">
                <header><strong>源端口选择器</strong><span>{{ sourcePortCatalog.free }}/{{ sourcePortCatalog.total }} 空闲</span></header>
                <p class="selector-summary">{{ portSelectorSummary('source') }}</p>
                <label>端口池<el-select v-model="wiringForm.config.source_port_pool"><el-option v-for="o in PORT_POOL_OPTIONS" :key="o.value" :label="o.label" :value="o.value" /></el-select></label>
                <label>Slot 白名单<el-select v-model="wiringForm.config.source_slot_ids" multiple clearable collapse-tags placeholder="全部 Slot"><el-option v-for="s in sourcePortCatalog.slots" :key="s" :label="`Slot ${s}`" :value="s" /></el-select></label>
                <label>Slot 范围<el-input v-model="wiringForm.config.source_slot_range" clearable placeholder="如 1-4" /></label>
                <label>端口类型<el-select v-model="wiringForm.config.source_port_types" multiple clearable collapse-tags placeholder="全部类型"><el-option v-for="o in sourcePortCatalog.types" :key="o.value" :label="o.label" :value="o.value" /></el-select></label>
                <label>端口号范围<el-input v-model="wiringForm.config.source_port_range" clearable placeholder="如 0-35；按复合编号末段" /></label>
                <label>指定接口 ID<el-select v-model="wiringForm.config.source_port_ids" multiple clearable filterable collapse-tags placeholder="自动选择"><el-option v-for="o in sourcePortCatalog.ids" :key="o.value" :label="o.label" :value="o.value" /></el-select></label>
              </section>
              <section class="endpoint-selector target">
                <header><strong>目标端口选择器</strong><span>{{ targetPortCatalog.free }}/{{ targetPortCatalog.total }} 空闲</span></header>
                <p class="selector-summary">{{ portSelectorSummary('target') }}</p>
                <label>端口池<el-select v-model="wiringForm.config.target_port_pool"><el-option v-for="o in PORT_POOL_OPTIONS" :key="o.value" :label="o.label" :value="o.value" /></el-select></label>
                <label>Slot 白名单<el-select v-model="wiringForm.config.target_slot_ids" multiple clearable collapse-tags placeholder="全部 Slot"><el-option v-for="s in targetPortCatalog.slots" :key="s" :label="`Slot ${s}`" :value="s" /></el-select></label>
                <label>Slot 范围<el-input v-model="wiringForm.config.target_slot_range" clearable placeholder="如 1-4" /></label>
                <label>端口类型<el-select v-model="wiringForm.config.target_port_types" multiple clearable collapse-tags placeholder="全部类型"><el-option v-for="o in targetPortCatalog.types" :key="o.value" :label="o.label" :value="o.value" /></el-select></label>
                <label>端口号范围<el-input v-model="wiringForm.config.target_port_range" clearable placeholder="如 0-47；按复合编号末段" /></label>
                <label>指定接口 ID<el-select v-model="wiringForm.config.target_port_ids" multiple clearable filterable collapse-tags placeholder="自动选择"><el-option v-for="o in targetPortCatalog.ids" :key="o.value" :label="o.label" :value="o.value" /></el-select></label>
              </section>
            </div>
            <p class="selector-numbering-hint">编号按设备自然顺序执行：H1/H2、W1/W2、Q1/Q2、SER1/SER2；接口按 Slot → 端口号排序，例如 H1-S2-0、W1-S1-0、Q1-U1、SER1-S1-1。</p>
          </div>

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
        <div v-if="false" class="sheet-block">
          <div class="sheet-title">4. 交换机互联 / Peer-link / DAD</div>
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

        <!-- 5 介质与距离 -->
        <div class="sheet-block">
          <div class="sheet-title">5. 介质、标准线长与标签</div>
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
                <th class="label-cell">线长计算</th>
                <td>
                  <el-select v-model="wiringForm.config.cable_length_mode" style="width: 100%">
                    <el-option label="AUTO（按机房/机柜/U位/画布估算）" value="AUTO" />
                    <el-option label="FIXED（固定长度）" value="FIXED" />
                  </el-select>
                </td>
                <th class="label-cell">固定线长 (m)</th>
                <td>
                  <el-input-number
                    v-model="wiringForm.config.cable_length_m"
                    :disabled="wiringForm.config.cable_length_mode !== 'FIXED'"
                    :min="0.5"
                    :max="10000"
                    :step="0.5"
                    controls-position="right"
                    style="width: 100%"
                  />
                </td>
              </tr>
              <tr>
                <th class="label-cell">走线预留 (m)</th>
                <td>
                  <el-input-number
                    v-model="wiringForm.config.route_extra_m"
                    :disabled="wiringForm.config.cable_length_mode === 'FIXED'"
                    :min="0"
                    :max="100"
                    :step="0.5"
                    controls-position="right"
                    style="width: 100%"
                  />
                </td>
                <th class="label-cell">长度余量 (%)</th>
                <td>
                  <el-input-number
                    v-model="wiringForm.config.cable_slack_percent"
                    :disabled="wiringForm.config.cable_length_mode === 'FIXED'"
                    :min="0"
                    :max="100"
                    :step="5"
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

    <el-drawer v-model="labRecordVisible" title="流量模拟与配置台账" size="76%" append-to-body>
      <div class="lab-summary-cards">
        <div><span>模拟状态</span><strong :class="{ running: labTrafficRunning }">{{ labStatusLabel }}</strong></div>
        <div><span>设备</span><strong>{{ canvasNodes.length }}</strong></div>
        <div><span>链路</span><strong>{{ links.length }}</strong></div>
        <div><span>最近同步</span><strong>{{ labLastSyncAt ? new Date(labLastSyncAt).toLocaleString() : '未同步' }}</strong></div>
      </div>
      <el-tabs v-model="labRecordTab" class="lab-record-tabs">
        <el-tab-pane label="状态" name="status">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="执行模式">本地流量模拟，不启动外部虚拟机</el-descriptions-item>
            <el-descriptions-item label="运行效果">拓扑连线动态流动，节点显示运行状态</el-descriptions-item>
            <el-descriptions-item label="交换机记录">型号、角色、端口占用、管理 IP、业务区域、VLAN</el-descriptions-item>
            <el-descriptions-item label="服务器记录">业务 IP、BMC IP、VIP、端口、业务区域、VLAN</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
        <el-tab-pane :label="`流量记录（${labTrafficRows.length}）`" name="traffic">
          <el-table :data="labTrafficRows" border size="small" max-height="560" empty-text="暂无拓扑连线">
            <el-table-column prop="source" label="源设备" min-width="130" show-overflow-tooltip />
            <el-table-column prop="sourcePort" label="源端口" min-width="115" show-overflow-tooltip />
            <el-table-column prop="target" label="目标设备" min-width="130" show-overflow-tooltip />
            <el-table-column prop="targetPort" label="目标端口" min-width="115" show-overflow-tooltip />
            <el-table-column prop="speed" label="速率" width="90" />
            <el-table-column prop="vlan" label="VLAN" width="120" show-overflow-tooltip />
            <el-table-column prop="traffic" label="模拟流量" width="110" />
            <el-table-column prop="packets" label="包/秒" width="90" />
            <el-table-column prop="state" label="状态" width="72" />
          </el-table>
        </el-tab-pane>
        <el-tab-pane :label="`交换机配置（${labSwitchRows.length}）`" name="switches">
          <el-table :data="labSwitchRows" border size="small" max-height="560" empty-text="暂无交换机">
            <el-table-column prop="name" label="设备名称" min-width="130" show-overflow-tooltip />
            <el-table-column prop="model" label="型号" min-width="140" show-overflow-tooltip />
            <el-table-column prop="role" label="角色" width="100" />
            <el-table-column prop="managementIp" label="管理IP" min-width="120" />
            <el-table-column prop="area" label="业务区域" min-width="120" show-overflow-tooltip />
            <el-table-column prop="vlan" label="VLAN配置" min-width="130" show-overflow-tooltip />
            <el-table-column prop="ports" label="接口总数" width="90" />
            <el-table-column prop="usedPorts" label="已用接口" width="90" />
          </el-table>
        </el-tab-pane>
        <el-tab-pane :label="`服务器配置（${labServerRows.length}）`" name="servers">
          <el-table :data="labServerRows" border size="small" max-height="560" empty-text="暂无服务器">
            <el-table-column prop="name" label="服务器" min-width="130" show-overflow-tooltip />
            <el-table-column prop="businessIp" label="业务IP" min-width="120" />
            <el-table-column prop="bmcIp" label="BMC IP" min-width="120" />
            <el-table-column prop="vip" label="VIP" min-width="105" />
            <el-table-column prop="area" label="业务区域" min-width="120" show-overflow-tooltip />
            <el-table-column prop="vlan" label="VLAN配置" min-width="130" show-overflow-tooltip />
            <el-table-column prop="ports" label="端口明细" min-width="220" show-overflow-tooltip />
            <el-table-column prop="usedPorts" label="已用" width="72" />
          </el-table>
        </el-tab-pane>
      </el-tabs>
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
      :topology-devices="nodes"
      :wiring-rules="wiringRules"
      :mode="groupDialogMode"
      :initial-group="groupDialogInitial"
      @update:catalog="onCatalogFromDialog"
      @created="onDeviceGroupCreated"
      @rename-group="onRenameDeviceGroup"
      @delete-group="onDeleteDeviceGroup"
      @delete-groups="onDeleteDeviceGroups"
      @bind-devices="onBindDeviceGroupDevices"
      @clone-groups="onCloneDeviceGroups"
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
          <el-form-item label="设备组">
            <el-select
              v-model="batchDeployGroup"
              clearable
              filterable
              allow-create
              placeholder="可选择或新建设备组"
              style="width: 100%"
            >
              <el-option v-for="name in deviceGroupParentNames" :key="name" :label="name" :value="name" />
            </el-select>
          </el-form-item>
          <el-form-item label="网络角色">
            <el-select v-model="batchDeployRole" clearable style="width: 100%">
              <el-option v-for="role in FABRIC_ROLE_OPTIONS" :key="role.value" :label="role.label" :value="role.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="自动处理">
            <el-checkbox v-model="batchDeployAutoWire">执行设备组绑定规则</el-checkbox>
          </el-form-item>
        </el-form>
        <p class="batch-deploy-hint">
          自动生成实例、写入设备组与角色，按网络层级紧凑布局并保存；若设备组绑定了规则，可同步自动布线。
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

    <el-dialog
      v-model="deviceDetailVisible"
      :title="deviceDetailNode ? `设备详情 · ${deviceDetailNode.name}` : '设备详情'"
      width="560px"
      append-to-body
      destroy-on-close
    >
      <div v-if="deviceDetailNode" class="device-detail-dialog-body">
        <TopologyNodeInspector
          :node="deviceDetailNode"
          :nodes="nodes"
          :links="links"
          :editable="false"
          :group-options="deviceGroupParentNames"
          @go-device="goToDevice"
        />
      </div>
      <el-empty v-else description="设备不存在或已被删除" />
      <template #footer>
        <el-button type="primary" @click="deviceDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

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
.rule-engine-sheet {
  overflow: hidden;
  border: 1px solid #a9adb3;
  background: #d3d1d1;
  color: #24272b;
}
.rule-engine-title {
  padding: 7px 10px;
  border-bottom: 1px solid #b5b5b5;
  font-size: 17px;
  font-weight: 700;
}
.rule-endpoint-section {
  margin-top: 8px;
  border-top: 8px solid #b7b5b5;
}
.rule-endpoint-heading,
.location-caption {
  padding: 7px 10px 4px;
  font-weight: 700;
}
.rule-engine-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}
.rule-engine-table th,
.rule-engine-table td {
  padding: 5px 7px;
  border: 1px solid #999b9f;
  vertical-align: middle;
}
.rule-engine-table th {
  width: 126px;
  background: #c8c7c7;
  text-align: right;
  font-weight: 500;
  white-space: nowrap;
}
.rule-engine-table td {
  background: #d8d6d6;
}
.rule-engine-table :deep(.el-select),
.rule-engine-table :deep(.el-input),
.rule-engine-table :deep(.el-input-number) {
  width: 100%;
}
.rule-engine-table :deep(.el-input__wrapper),
.rule-engine-table :deep(.el-select__wrapper),
.rule-engine-table :deep(.el-textarea__inner) {
  border-radius: 0;
  background: #f7f7f7;
  box-shadow: 0 0 0 1px #6f747a inset;
}
.rule-engine-table :deep(.el-switch__label) {
  color: #30343a;
}
.location-table th {
  text-align: center;
}
.rule-match-summary {
  margin: 8px;
  padding: 8px 10px;
  border-left: 4px solid #4a90e2;
  background: #edf4fb;
  color: #394b5d;
  line-height: 1.55;
}
.rule-auto-summary {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin: 10px;
  padding: 12px 14px;
  border: 1px solid #9eb9d5;
  background: #edf5fc;
  color: #334d66;
  line-height: 1.5;
}
.rule-auto-summary strong {
  color: #174f87;
  font-size: 15px;
}
.auto-rule-limits {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 22px;
  margin: 4px 0;
}
.auto-rule-limits label {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #34495e;
}
.auto-rule-limits :deep(.el-input-number) {
  width: 150px;
}
.auto-summary-warning {
  color: #b65c00;
}
.compact-manual-pairs {
  padding: 0 8px 10px;
  background: #d3d1d1;
}
.compact-manual-pairs :deep(.el-select) {
  width: 100%;
}
.cable-rule-table {
  margin-top: 8px;
  border-top: 8px solid #b7b5b5;
}
.sync-media-text {
  color: #4d5560;
}
.device-detail-dialog-body {
  height: min(620px, 68vh);
  min-height: 360px;
  overflow: hidden;
}
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

.auto-wiring-settings-form {
  margin-top: 18px;
}

.auto-setting-control {
  display: flex;
  width: 100%;
  align-items: flex-start;
  gap: 12px;
}

.auto-setting-control small {
  flex: 1;
  color: #69788b;
  line-height: 1.5;
}

.auto-rule-checkboxes {
  display: grid;
  width: 100%;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.auto-rule-checkboxes .el-checkbox {
  width: 100%;
  height: auto;
  min-height: 54px;
  margin: 0;
  padding: 8px 10px;
  align-items: flex-start;
}

.auto-rule-checkboxes :deep(.el-checkbox__label) {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
  white-space: normal;
}

.auto-rule-checkboxes small {
  color: #7a8797;
  line-height: 1.3;
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

.lab-summary-cards { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 10px; margin-bottom: 14px; }
.lab-summary-cards>div { display:flex; flex-direction:column; gap:5px; padding:12px; border:1px solid #dcdfe6; border-radius:8px; background:linear-gradient(180deg,#fff,#f5f7fa); }
.lab-summary-cards span { color:#909399; font-size:12px; }.lab-summary-cards strong { color:#303133; font-size:16px; }.lab-summary-cards strong.running { color:#67c23a; }
.lab-record-tabs { min-height: 420px; }
.lab-status.running { color:#67c23a; border-color:#b3e19d; background:#f0f9eb; }
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
.port-selector-panel {
  margin: 12px;
  border: 1px solid #cfd8e6;
  border-radius: 10px;
  background: linear-gradient(180deg, #f8fbff, #f4f7fb);
  overflow: hidden;
}
.selector-strict-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 12px;
  border-bottom: 1px solid #dfe6ef;
}
.selector-strict-row p { margin: 3px 0 0; color: #6b7788; font-size: 12px; }
.port-selector-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 12px;
}
.endpoint-selector {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  padding: 12px;
  border: 1px solid #d7dee8;
  border-radius: 8px;
  background: #fff;
}
.endpoint-selector.source { border-top: 3px solid #3b82f6; }
.endpoint-selector.target { border-top: 3px solid #10b981; }
.endpoint-selector header, .selector-summary { grid-column: 1 / -1; }
.endpoint-selector header { display: flex; justify-content: space-between; color: #24364b; }
.endpoint-selector header span { color: #69788b; font-size: 12px; }
.endpoint-selector label { display: flex; flex-direction: column; gap: 5px; color: #566579; font-size: 12px; }
.endpoint-selector label :deep(.el-select), .endpoint-selector label :deep(.el-input) { width: 100%; }
.selector-summary { margin: 0; padding: 6px 8px; border-radius: 5px; background: #eef3f9; color: #42546a; font-size: 12px; }
.selector-numbering-hint { margin: 0; padding: 0 12px 12px; color: #64748b; font-size: 12px; line-height: 1.5; }
@media (max-width: 1100px) {
  .port-selector-grid { grid-template-columns: 1fr; }
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

.wiring-designer-section {
  margin-bottom: 14px;
  padding: 14px;
  border: 1px solid #d8e2ee;
  border-radius: 10px;
  background: linear-gradient(145deg, #f8fbff 0%, #f4f8fc 100%);
}

.designer-section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  color: #24364b;
}

.designer-section-heading div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.designer-section-heading span {
  color: #718096;
  font-size: 12px;
}

.designer-section-heading .designer-heading-actions {
  align-items: flex-end;
  flex-direction: row;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.scenario-preset-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  width: 100%;
}

.scenario-preset-card.el-radio {
  width: 100%;
  height: auto;
  min-height: 62px;
  margin: 0;
  padding: 10px 12px;
  align-items: flex-start;
  background: #fff;
}

.scenario-preset-card :deep(.el-radio__label) {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
  white-space: normal;
}

.scenario-preset-title {
  color: #25364d;
  font-weight: 600;
}

.scenario-preset-card small {
  color: #718096;
  line-height: 1.35;
}

.scenario-runtime-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  background: #eaf2fb;
  color: #486079;
  font-size: 12px;
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
