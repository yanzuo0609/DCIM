<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ModelPanelSchematic from '@/components/ModelPanelSchematic.vue'
import SwitchChassisSchematic from '@/components/SwitchChassisSchematic.vue'
import SwitchChassisRearSchematic from '@/components/SwitchChassisRearSchematic.vue'
import AccessSwitchSchematic from '@/components/AccessSwitchSchematic.vue'
import AccessSwitchRearSchematic from '@/components/AccessSwitchRearSchematic.vue'
import ServerFrontSchematic from '@/components/ServerFrontSchematic.vue'
import ServerRearSchematic from '@/components/ServerRearSchematic.vue'
import SecurityDeviceSchematic from '@/components/SecurityDeviceSchematic.vue'
import SecurityDeviceRearSchematic from '@/components/SecurityDeviceRearSchematic.vue'
import TitleHintBang from '@/components/TitleHintBang.vue'
import TopologyDeviceIcon from '@/components/TopologyDeviceIcon.vue'
import {
  createDesignModel,
  createFolder,
  deleteDesignModel,
  deleteFolder,
  fetchAttributeSchema,
  fetchFolderTree,
  fetchModelTaxonomy,
  listDesignModels,
  updateDesignModel,
  type AttributeFieldDef,
  type CategoryAttributeSchema,
  type NetworkDesignModel,
  type NetworkModelFolderTreeNode,
  type TaxonomyCategory,
} from '@/api/networkModelDesign'
import type { SwitchSubtype, UplinkPosition } from '@/api/network'
import { UPLINK_POSITION_LABELS } from '@/api/network'
import { getContractSummary, type DeviceContractSummary } from '@/api/contract'
import { useAuthStore } from '@/stores/auth'
import {
  formatSummaryOptionLabel,
  resolveModelFromSummary,
  summaryOptionKey,
} from '@/utils/contractModelBind'
import {
  applySwitchStyleDefaults,
  defaultNetworkSwitchAttributes,
  effectivePortCount,
  isCoreOrAggRole,
  NETWORK_DEVICE_TYPE_OPTIONS,
  readSwitchSlots,
  rebuildCoreExpansionSlots,
  persistCoreIfaceBoards,
  adjustCoreIfaceBoardCount,
  readCoreIfaceBoards,
  emptyCoreSlotIndexes,
  addCoreIfaceBoard,
  updateCoreIfaceBoard,
  removeCoreIfaceBoard,
  patchCoreBoardPort,
  patchAccessBoardPort,
  patchSwitchSystemPort,
  resolveSlotPort,
  readSwitchSystemPorts,
  groupSwitchSystemPorts,
  systemPortKindLabel,
  defaultPortSpecForKind,
  defaultAccessDownlinkSpec,
  defaultAccessUplinkSpec,
  defaultSystemPortSpec,
  suggestPortSpecBySpeed,
  ifaceBoardKindLabel,
  switchPortFieldLabel,
  slotCardToIfaceBoard,
  coreExpansionCap,
  computeBlankPanelRows,
  moveBlankPanelRow,
  nudgeBlankPanelRow,
  normalizeBlankPanelRows,
  portTypeToIfaceKind,
  AIRFLOW_OPTIONS,
  SWITCH_IFACE_BOARD_OPTIONS,
  SWITCH_IFACE_BOARD_PORT_PRESETS,
  ACCESS_DOWNLINK_COUNT_PRESETS,
  ACCESS_TENGIG_UPLINK_COUNT_PRESETS,
  GIGABIT_DOWNLINK_MEDIA_OPTIONS,
  TENGIG_UPLINK_KIND_OPTIONS,
  readGigabitDownlinkMedia,
  readTenGigUplinkKind,
  SWITCH_PORT_IFACE_TYPE_OPTIONS,
  SWITCH_PORT_SPEED_OPTIONS,
  SWITCH_PORT_MODULE_OPTIONS,
  SWITCH_PORT_CONNECTOR_OPTIONS,
  SWITCH_PORT_FIBER_MODE_OPTIONS,
  SWITCH_STYLE_OPTIONS,
  syncSwitchDerivedCounts,
  type SwitchIfaceBoardKind,
  type SwitchIfaceBoardPlacement,
  type SwitchBoardPortAttr,
  type SwitchPortFiberMode,
  type SwitchPortIfaceType,
  type SwitchSystemPortAttr,
  type SwitchSlotAttr,
  type GigabitDownlinkMedia,
  type TenGigUplinkKind,
} from '@/utils/switchModelAttrs'
import {
  applyServerHeightDefaults,
  defaultServerAttributes,
  diskFrontMaxForU,
  diskRearMaxForU,
  groupServerPorts,
  listServerPorts,
  PCIE_CARD_TYPE_OPTIONS,
  PCIE_ORIENTATION_OPTIONS,
  PCIE_PLACEMENT_OPTIONS,
  PCIE_PORT_COUNT_OPTIONS,
  pcieSlotMaxForU,
  readPcieSlots,
  normalizeDiskSize,
  normalizeMemoryType,
  normalizeOsSupport,
  normalizePsuRedundancy,
  normalizeServerFormFactor,
  readServerIfaceSlots,
  renumberServerSlotPorts,
  SERVER_DISK_PROTO_OPTIONS,
  SERVER_DISK_SIZE_OPTIONS,
  SERVER_FLEX_SPEED_OPTIONS,
  SERVER_HEIGHT_OPTIONS,
  SERVER_MEMORY_TYPE_OPTIONS,
  SERVER_OS_OPTIONS,
  SERVER_PSU_REDUNDANCY_OPTIONS,
  SERVER_SSD_IFACE_OPTIONS,
  SERVER_SSD_TYPE_OPTIONS,
  SERVER_DEMO,
  serverIfaceSlotsToDesignSlots,
  serverPortKindLabel,
  serverSlotLabelFromInterfaces,
  isOnboardSlot,
  defaultExpansionSlot,
  syncServerDerivedAttrs,
  type ServerIfaceSlotAttr,
  type ServerPcieSlotAttr,
  type ServerPcieCardType,
  type ServerFlexSpeed,
  type ServerPortAttr,
} from '@/utils/serverModelAttrs'
import {
  defaultSecurityAttributes,
  normalizeSecurityFormFactor,
  normalizeSecurityDeviceType,
  securityDeviceProfile,
  readSecurityIfaceSlots,
  MAX_SECURITY_IFACE_SLOTS,
  SECURITY_HEIGHT_OPTIONS,
  securitySlot10gRangeLabel,
  securitySlot1gRangeLabel,
  syncSecurityDerivedAttrs,
  type SecurityIfaceSlotAttr,
} from '@/utils/securityModelAttrs'
import {
  buildPortLayoutFromDesignModel,
  DESIGN_RAID_LEVEL_OPTIONS,
  DESIGN_SLOT_TYPE_OPTIONS,
  normalizeDesignSlots,
  resolveDesignSwitchRole,
  syncSlotInterfaces,
  slotTypeLabel,
  type DesignSlotAttr,
  type DesignSlotInterface,
} from '@/utils/designModelToNode'
import {
  buildPanelPalette,
  ensurePanelLayout,
  normalizePanelLayoutConfig,
  type PanelLayoutConfig,
  type PanelLayoutItem,
  type PanelSide,
} from '@/utils/modelPanelLayout'
import { designModelIconProps } from '@/utils/designModelIcon'
import { ifaceBoardTwoRowLabels } from '@/utils/switchFrontPanel'
import {
  NETWORK_MODEL_PRESET_GROUPS,
  buildNetworkModelPresetAttributes,
  findNetworkModelPreset,
} from '@/utils/networkModelPresets'

const auth = useAuthStore()
const canEdit = computed(() => auth.hasPermission('network:update'))
const canCreate = computed(() => auth.hasPermission('network:create'))
const canDelete = computed(() => auth.hasPermission('network:delete'))

const loading = ref(false)
const saving = ref(false)
const tree = ref<NetworkModelFolderTreeNode[]>([])
const taxonomy = ref<TaxonomyCategory[]>([])
const selectedFolderId = ref<string | null>(null)
const models = ref<NetworkDesignModel[]>([])
const selectedModelId = ref<string | null>(null)
const attrSchema = ref<CategoryAttributeSchema | null>(null)

const folderDialogVisible = ref(false)
const folderForm = reactive({
  kind: 'folder' as 'folder' | 'project',
  name: '',
  code: '',
  description: '',
  parent_id: null as string | null,
})

const modelDialogVisible = ref(false)
const applyingPreset = ref(false)
const modelForm = reactive({
  preset_id: null as string | null,
  code: '',
  name: '',
  category: 'network' as 'network' | 'server' | 'security',
  subtype: 'switch',
  manufacturer_name: '',
  vendor_sku: '',
  height_u: 1,
  description: '',
  attributes: {} as Record<string, unknown>,
  createSummaryKey: null as string | null,
  device_model_id: null as string | null,
  contract_device_name: null as string | null,
})

const contractSummaries = ref<DeviceContractSummary[]>([])
const selectedSummaryKey = ref<string | null>(null)
const customPanelVisible = ref(false)
const securityInterfaceEditorVisible = ref(false)
const panelDemoZoom = ref<0.5 | 1 | 2>(1)
const panelDemoSide = ref<'front' | 'rear'>('front')
const panelDemoCssZoom = computed(() => panelDemoZoom.value)
const serverStyleFrontInput = ref<HTMLInputElement | null>(null)
const serverStyleRearInput = ref<HTMLInputElement | null>(null)
const serverPanelShowImage = ref(false)
const ifaceBoardViewport = ref<HTMLElement | null>(null)
const ifaceBoardCanPrev = ref(false)
const ifaceBoardCanNext = ref(false)
const selectedChassisPort = ref<{ slotIndex: number; portIndex: number; portId?: string } | null>(null)
const chassisPortEditVisible = ref(false)
const chassisPortInfo = ref<{
  x: number
  y: number
  slotIndex: number
  portIndex: number
  portId?: string
  boardLabel: string
  ordinal: string
  portNo: string
  spec: SwitchBoardPortAttr
} | null>(null)
const chassisPortDraft = reactive<SwitchBoardPortAttr>({
  index: 0,
  id: '',
  code: '',
  iface_type: 'optical',
  speed: '10GE',
  module: 'SFP+',
  connector: 'LC',
  fiber_mode: 'mm',
})
const chassisPortDraftMeta = reactive({
  slotIndex: 0,
  portId: '',
  boardLabel: '',
  ordinal: '',
  portNo: '',
})

const DEFAULT_SUBTYPE: Record<string, string> = {
  network: 'gigabit',
  server: 'compute',
  security: 'firewall',
}

function switchRoleFromSubtype(value: unknown): SwitchSubtype {
  const subtype = String(value || '')
  return subtype === 'ten_gigabit' || subtype === 'aggregation' || subtype === 'core'
    ? subtype
    : 'gigabit'
}

const selectedFolder = computed(() => findFolder(tree.value, selectedFolderId.value))
const selectedModel = computed(
  () => models.value.find((m) => m.id === selectedModelId.value) || null,
)
const createSubtypeOptions = computed(
  () => taxonomy.value.find((item) => item.value === modelForm.category)?.subtypes || [],
)
const selectedCreatePreset = computed(() => findNetworkModelPreset(modelForm.preset_id))

/** 规格字段（slot_count / slots / panel / custom 单独处理） */
const schemaFields = computed(() =>
  (attrSchema.value?.fields || []).filter(
    (f) =>
      ![
        'slots',
        'slot_count',
        'panel_layout',
        'custom_attributes',
        'switch_role',
        'line_cards',
        'switch_slots',
        'card_slot_count',
        'optical_card_count',
        'optical_ports_per_card',
        'downlink_count',
        'uplink_count',
        'uplink_position',
        'downlink_type',
        'uplink_type',
        'downlink_media',
        'mgmt_ports',
        'fan_count',
        'psu_count',
        'chassis_height_u',
        'console_ports',
        'eth_mgmt_ports',
        'usb_ports',
        'stack_cluster_ports',
        'fabric_slot_count',
        'airflow_type',
        'airflow_custom',
        'chassis_dim_a',
        'chassis_dim_b',
        'chassis_dim_c',
        'max_power_watt',
        'modular_expansion_slots',
        'service_board_count',
        'iface_board_type',
        'iface_board_port_count',
        'iface_board_port_custom',
        'iface_boards',
        'blank_panel_rows',
        'system_ports',
        'panel_style_image',
        'panel_style_mode',
        'panel_style_image_rear',
        'security_slots',
        'control_ports',
        'ha_ports',
        'data_port_count',
        'data_port_type',
      ].includes(f.key),
  ),
)

const isSwitchModel = computed(
  () => selectedModel.value?.category === 'network',
)

const isServerModel = computed(() => selectedModel.value?.category === 'server')

const isSecurityModel = computed(() => selectedModel.value?.category === 'security')

const switchRole = computed<SwitchSubtype>(() => {
  const m = selectedModel.value
  if (!m?.attributes) return 'gigabit'
  const role = resolveDesignSwitchRole(m.attributes)
  return role === 'aggregation' ? 'core' : role
})

const isCoreAggSwitch = computed(() => isCoreOrAggRole(switchRole.value))
const isAccessSwitch = computed(() => isSwitchModel.value && !isCoreAggSwitch.value)

const coreIfaceBoards = computed<SwitchIfaceBoardPlacement[]>(() => {
  const m = selectedModel.value
  if (!m?.attributes || !isCoreAggSwitch.value) return []
  return readCoreIfaceBoards(m.attributes)
})

const chassisHeightU = computed(() => {
  const m = selectedModel.value
  return Math.max(1, Number(m?.attributes?.chassis_height_u ?? m?.height_u ?? 10) || 10)
})

const expansionSlotMax = computed(() => coreExpansionCap(chassisHeightU.value))

const blankPanelRows = computed<number[]>(() => {
  const m = selectedModel.value
  if (!m?.attributes || !isCoreAggSwitch.value) return []
  void m.attributes.blank_panel_rows
  void m.attributes.modular_expansion_slots
  void m.attributes.chassis_height_u
  return computeBlankPanelRows(m.attributes)
})

/** 各区块说明（相同规则只写一次，挂在标题叹号） */
const SERVER_PANEL_HINT =
  '按机箱 1U/2U/4U 与盘位自动生成前后面板仿真。可 1×/2× 缩放、自定义网格，或上传前后面板样式图片覆盖演示。左键选接口、右键查看 ID/编号。'

const switchSlotConfigHint = computed(() => {
  const role = switchRole.value
  if (role === 'core' || role === 'aggregation') {
    return '核心/汇聚：正面/背面同时显示。左键点击接口编辑，右键查看接口信息。空白面板可拖拽或用 ↑↓ 调整位置。点击「自定义面板」后，在网格上框选定义业务接口板。'
  }
  if (role === 'ten_gigabit') {
    return '万兆：业务口为万兆以太网光接口（默认 48，可自定义）；上联为 40G 或 100G 光接口（默认 6 或 8）。面板演示可将上联放在中间或右侧；mgmt 在背面右侧。点击「自定义面板」可在网格上框选自定义布局。'
  }
  return '千兆：业务口为千兆以太网光接口或电口（默认 48，可自定义）；上联默认 8 个，面板演示上联在右侧；mgmt 在背面右侧。点击「自定义面板」可在网格上框选自定义布局。'
})

const panelStyleHint = computed(() => {
  if (isSwitchModel.value) {
    return '点选组件后拖拽框选放置；口数自动按交换机双排紧凑均分，空板卡无接口。'
  }
  if (isSecurityModel.value) {
    return '安全设备面板按 Slot 分区展示 Control/HA/MGMT/USB 与 10G/1G 接口。\n① 点选「设备配置及组件」中的组件 ② 在面板上拖拽框选范围放置；已放置组件可点选后点「删除」，或「清空组件」。'
  }
  return '点选组件后在面板上拖拽框选范围进行放置。\n① 点选「设备配置及组件」中的组件 ② 在面板上拖拽框选范围放置；已放置组件可点选后点「删除」，或「清空组件」。'
})

function securitySlotRangeHint(slot: SecurityIfaceSlotAttr): string {
  const parts = [securitySlot10gRangeLabel(slot), securitySlot1gRangeLabel(slot)].filter((x) => x && x !== '—')
  return parts.length ? parts.join(' · ') : '—'
}
const switchSlots = computed<SwitchSlotAttr[]>(() => {
  const m = selectedModel.value
  if (!m?.attributes) return []
  return readSwitchSlots(m.attributes)
})

const switchSystemPorts = computed<SwitchSystemPortAttr[]>(() => {
  const m = selectedModel.value
  if (!m?.attributes || !isSwitchModel.value) return []
  return readSwitchSystemPorts(m.attributes)
})

const switchSystemPortGroups = computed(() => groupSwitchSystemPorts(switchSystemPorts.value))

const accessDownlinkSlot = computed(
  () => switchSlots.value.find((s) => s.purpose === 'DOWNLINK' && s.card_type !== 'blank') || null,
)
const accessUplinkSlot = computed(
  () => switchSlots.value.find((s) => s.purpose === 'UPLINK' && s.card_type !== 'blank') || null,
)
const accessDownlinkPreset = computed(() => {
  const n = Number(attrFieldValue('downlink_count') ?? 48)
  return ACCESS_DOWNLINK_COUNT_PRESETS.includes(n as (typeof ACCESS_DOWNLINK_COUNT_PRESETS)[number])
    ? String(n)
    : 'other'
})
const accessDownlinkLabel = computed(() => {
  if (switchRole.value === 'gigabit') {
    return readGigabitDownlinkMedia(selectedModel.value?.attributes) === 'optical' ? '1G 光' : '1G 电'
  }
  return '10GE'
})
const accessUplinkLabel = computed(() => {
  if (switchRole.value === 'gigabit') return '10G UPLINK'
  return readTenGigUplinkKind(selectedModel.value?.attributes) === '100ge' ? '100G' : '40G'
})
const accessUplinkPosition = computed<UplinkPosition>(() =>
  switchRole.value === 'gigabit'
    ? 'right'
    : selectedModel.value?.attributes?.uplink_position === 'middle'
      ? 'middle'
      : 'right',
)

const accessMgmtPorts = computed(() => switchSystemPorts.value.filter((p) => p.kind === 'eth_mgmt'))
const accessOtherSystemGroups = computed(() =>
  switchSystemPortGroups.value.filter((g) => g.kind !== 'eth_mgmt'),
)

watch(
  () => [selectedModel.value?.id, switchRole.value] as const,
  () => {
    const m = selectedModel.value
    if (!m?.attributes || !isAccessSwitch.value) return
    syncSwitchDerivedCounts(m.attributes)
  },
)

const serverIfaceSlots = computed<ServerIfaceSlotAttr[]>(() => {
  const m = selectedModel.value
  if (!m || m.category !== 'server' || !m.attributes) return []
  return readServerIfaceSlots(m.attributes)
})

const serverPorts = computed<ServerPortAttr[]>(() => {
  const m = selectedModel.value
  if (!m?.attributes || !isServerModel.value) return []
  return listServerPorts(m.attributes)
})

const serverPortGroups = computed(() => groupServerPorts(serverPorts.value))

const serverPcieSlots = computed<ServerPcieSlotAttr[]>(() => {
  const m = selectedModel.value
  if (!m?.attributes || !isServerModel.value) return []
  return readPcieSlots(m.attributes)
})

const serverPcieSlotMax = computed(() =>
  pcieSlotMaxForU(selectedModel.value?.height_u ?? selectedModel.value?.attributes?.form_factor_u),
)

const serverStyleImageFront = computed(() => String(selectedModel.value?.attributes?.panel_style_image || ''))
const serverStyleImageRear = computed(() => String(selectedModel.value?.attributes?.panel_style_image_rear || ''))

const serverSlots = computed<DesignSlotAttr[]>(() => {
  const m = selectedModel.value
  if (!m || m.category !== 'server') return []
  return serverIfaceSlotsToDesignSlots(serverIfaceSlots.value, m.attributes)
})

const serverDiskFrontMax = computed(() =>
  diskFrontMaxForU(
    selectedModel.value?.height_u ?? selectedModel.value?.attributes?.form_factor_u,
    selectedModel.value?.attributes?.disk_front_size,
  ),
)

const serverFrontDriveLayoutLabel = computed(() => {
  const u = normalizeServerFormFactor(selectedModel.value?.height_u ?? selectedModel.value?.attributes?.form_factor_u)
  const n = Number(selectedModel.value?.attributes?.disk_front_count || 0)
  if (u === 2) return n > 12 ? '竖向 SFF（24位等宽）' : '横向托架（3 × 4）'
  if (u === 1) {
    return normalizeDiskSize(selectedModel.value?.attributes?.disk_front_size, '3.5') === '2.5'
      ? '竖向 SFF（10位等宽）'
      : '横向托架（1 × 4）'
  }
  return '按机箱容量等比排列'
})

const serverDiskRearMax = computed(() => diskRearMaxForU())

const securityIfaceSlots = computed<SecurityIfaceSlotAttr[]>(() => {
  const m = selectedModel.value
  if (!m || m.category !== 'security' || !m.attributes) return []
  return readSecurityIfaceSlots(m.attributes)
})
const securityDeviceType = computed(() =>
  normalizeSecurityDeviceType(selectedModel.value?.subtype || selectedModel.value?.attributes?.security_device_type),
)
const securityProfile = computed(() => securityDeviceProfile(securityDeviceType.value))

const panelLayout = computed<PanelLayoutConfig>({
  get() {
    const m = selectedModel.value
    if (!m || m.category === 'software') {
      return {
        cols: 38,
        rows: 16,
        grid_scale: 4,
        front: { cols: 38, rows: 16, items: [] },
        rear: { cols: 38, rows: 16, items: [] },
      }
    }
    if (!m.attributes) m.attributes = {}
    // 归一化；纠正误放大尺寸后写回，避免一直停在 64×48
    const layout = normalizePanelLayoutConfig(m.attributes.panel_layout)
    const prev = m.attributes.panel_layout as PanelLayoutConfig | undefined
    if (
      !prev ||
      prev.cols !== layout.cols ||
      prev.rows !== layout.rows ||
      prev.grid_scale !== layout.grid_scale
    ) {
      m.attributes.panel_layout = layout
    }
    return layout
  },
  set(v: PanelLayoutConfig) {
    const m = selectedModel.value
    if (!m) return
    if (!m.attributes) m.attributes = {}
    m.attributes.panel_layout = normalizePanelLayoutConfig(v)
  },
})

const panelPalette = computed(() => {
  const m = selectedModel.value
  if (!m?.attributes || m.category === 'software') return []
  void m.attributes.switch_role
  void m.attributes.downlink_count
  void m.attributes.optical_card_count
  void m.attributes.optical_ports_per_card
  void m.attributes.uplink_count
  void m.attributes.line_cards
  void m.attributes.switch_slots
  void m.attributes.iface_boards
  void m.attributes.server_slots
  void m.attributes.security_slots
  void m.attributes.slot_count
  void m.attributes.fan_count
  void m.attributes.psu_count
  void m.attributes.chassis_height_u
  void m.attributes.blank_panel_rows
  void m.attributes.service_board_count
  void m.attributes.iface_board_type
  void m.attributes.iface_board_port_count
  void m.attributes.panel_style_image
  void m.attributes.panel_style_mode
  void m.attributes.data_port_count
  void m.attributes.disk_front_count
  void m.attributes.disk_rear_count
  void m.attributes.wan_count
  void m.attributes.lan_count
  void m.attributes.service_port_count
  void serverIfaceSlots.value
  void securityIfaceSlots.value
  if (m.category === 'server') {
    return buildPanelPalette(m.attributes, serverSlots.value)
  }
  return buildPanelPalette(m.attributes, [])
})

const usesGridPanel = computed(() => selectedModel.value?.category !== 'software')

function findFolder(
  nodes: NetworkModelFolderTreeNode[],
  id: string | null,
): NetworkModelFolderTreeNode | null {
  if (!id) return null
  for (const n of nodes) {
    if (n.id === id) return n
    const hit = findFolder(n.children || [], id)
    if (hit) return hit
  }
  return null
}

function flattenFolders(
  nodes: NetworkModelFolderTreeNode[],
  depth = 0,
): { id: string; label: string; kind: string }[] {
  const out: { id: string; label: string; kind: string }[] = []
  for (const n of nodes) {
    out.push({
      id: n.id,
      label: `${'　'.repeat(depth)}${n.kind === 'project' ? '📁' : '📂'} ${n.name}`,
      kind: n.kind,
    })
    out.push(...flattenFolders(n.children || [], depth + 1))
  }
  return out
}

const folderOptions = computed(() => flattenFolders(tree.value))

function categoryLabel(cat: string) {
  return (
    NETWORK_DEVICE_TYPE_OPTIONS.find((c) => c.value === cat)?.label ||
    taxonomy.value.find((c) => c.value === cat)?.label ||
    cat
  )
}

async function refreshTree() {
  tree.value = await fetchFolderTree()
}

async function refreshModels() {
  if (!selectedFolderId.value) {
    models.value = []
    return
  }
  const data = await listDesignModels({
    folder_id: selectedFolderId.value,
    page: 1,
    page_size: 200,
  })
  models.value = data?.items || []
}

async function loadAll() {
  loading.value = true
  try {
    taxonomy.value = await fetchModelTaxonomy()
    await refreshTree()
    if (!selectedFolderId.value && tree.value.length) {
      selectedFolderId.value = tree.value[0].id
    }
    await refreshModels()
  } catch (err: unknown) {
    const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
    ElMessage.error(msg || '加载模型设计失败')
  } finally {
    loading.value = false
  }
}

function openFolderDialog(kind: 'folder' | 'project') {
  folderForm.kind = kind
  folderForm.name = ''
  folderForm.code = ''
  folderForm.description = ''
  folderForm.parent_id = selectedFolderId.value
  folderDialogVisible.value = true
}

async function confirmFolder() {
  if (!folderForm.name.trim()) {
    ElMessage.warning('请填写名称')
    return
  }
  saving.value = true
  try {
    const created = await createFolder({
      kind: folderForm.kind,
      name: folderForm.name.trim(),
      code: folderForm.code.trim() || null,
      description: folderForm.description.trim() || null,
      parent_id: folderForm.parent_id,
    })
    folderDialogVisible.value = false
    await refreshTree()
    if (created?.id) selectedFolderId.value = created.id
    ElMessage.success(folderForm.kind === 'project' ? '项目已创建' : '文件夹已创建')
  } catch (err: unknown) {
    const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
    ElMessage.error(msg || '创建失败')
  } finally {
    saving.value = false
  }
}

async function removeFolder() {
  if (!selectedFolderId.value) return
  try {
    await ElMessageBox.confirm('删除前请确保其下无子节点与模型。确定删除？', '删除确认', {
      type: 'warning',
    })
    await deleteFolder(selectedFolderId.value)
    selectedFolderId.value = null
    selectedModelId.value = null
    await refreshTree()
    await refreshModels()
    ElMessage.success('已删除')
  } catch (err: unknown) {
    if (err === 'cancel') return
    const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
    ElMessage.error(msg || '删除失败')
  }
}

async function loadSchemaForForm() {
  const options = taxonomy.value.find((item) => item.value === modelForm.category)?.subtypes || []
  if (!options.some((item) => item.value === modelForm.subtype)) {
    modelForm.subtype = DEFAULT_SUBTYPE[modelForm.category] || options[0]?.value || modelForm.subtype
  }
  const schema = await fetchAttributeSchema(modelForm.category, modelForm.subtype)
  attrSchema.value = schema
  if (modelForm.category === 'network') {
    modelForm.attributes = defaultNetworkSwitchAttributes(switchRoleFromSubtype(modelForm.subtype))
    modelForm.height_u = asInt(modelForm.attributes.chassis_height_u, 1)
  } else if (modelForm.category === 'server') {
    modelForm.attributes = defaultServerAttributes(1)
    modelForm.height_u = Number(modelForm.attributes.form_factor_u) || 1
  } else if (modelForm.category === 'security') {
    modelForm.attributes = defaultSecurityAttributes(undefined, modelForm.subtype)
    modelForm.height_u = Number(modelForm.attributes.form_factor_u) || 1
  } else {
    modelForm.attributes = { ...(schema?.default_attributes || {}) }
    modelForm.height_u = Number(modelForm.attributes.form_factor_u) || 1
  }
}

function asInt(v: unknown, fallback: number) {
  const n = Number(v)
  return Number.isFinite(n) ? Math.trunc(n) : fallback
}

async function openCreateModel() {
  if (!selectedFolderId.value) {
    ElMessage.warning('请先选择文件夹或项目')
    return
  }
  try {
    modelForm.preset_id = null
    modelForm.code = `M${Date.now().toString().slice(-6)}`
    modelForm.name = ''
    modelForm.category = 'network'
    modelForm.subtype = 'gigabit'
    modelForm.manufacturer_name = ''
    modelForm.vendor_sku = ''
    modelForm.height_u = Number(modelForm.attributes.form_factor_u) || 1
    modelForm.description = ''
    modelForm.createSummaryKey = null
    modelForm.device_model_id = null
    modelForm.contract_device_name = null
    modelDialogVisible.value = true
    if (!contractSummaries.value.length) {
      loadContractSummaries().catch(() => {
        contractSummaries.value = []
      })
    }
    await loadSchemaForForm()
  } catch (err: unknown) {
    modelDialogVisible.value = true
    const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
    ElMessage.error(msg || '打开新建模型失败，可先填写基础信息')
  }
}

watch(
  () => modelForm.category,
  async () => {
    if (!modelDialogVisible.value || applyingPreset.value) return
    await loadSchemaForForm()
  },
)

async function onCreatePresetChange(id: string | null) {
  const preset = findNetworkModelPreset(id)
  modelForm.preset_id = id
  if (!preset) return
  applyingPreset.value = true
  try {
    modelForm.category = preset.category
    modelForm.subtype = preset.subtype
    modelForm.name = preset.name
    modelForm.vendor_sku = preset.vendorSku
    modelForm.height_u = preset.heightU
    modelForm.description = preset.summary
    modelForm.createSummaryKey = null
    modelForm.device_model_id = null
    modelForm.contract_device_name = preset.name
    attrSchema.value = await fetchAttributeSchema(preset.category, preset.subtype)
    modelForm.attributes = buildNetworkModelPresetAttributes(preset)
  } finally {
    applyingPreset.value = false
  }
}

async function onCreateSummaryChange(key: string | null) {
  // allow-create 时可能直接传入自定义名称字符串
  if (!key) {
    modelForm.createSummaryKey = null
    modelForm.device_model_id = null
    modelForm.contract_device_name = null
    return
  }
  if (!contractSummaries.value.length) await loadContractSummaries()
  const row = contractSummaries.value.find((r) => summaryOptionKey(r) === key)
  if (!row) {
    // 手动输入的设备名称
    modelForm.createSummaryKey = null
    modelForm.name = String(key).trim()
    modelForm.contract_device_name = modelForm.name || null
    return
  }
  modelForm.createSummaryKey = key
  modelForm.name = (row.device_name || '').trim()
  modelForm.vendor_sku = (row.device_model_name || '').trim()
  modelForm.manufacturer_name = (row.manufacturer_name || '').trim()
  modelForm.contract_device_name = modelForm.name || null
  try {
    const resolved = await resolveModelFromSummary(row)
    modelForm.device_model_id = resolved.id
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '关联采购汇总失败'
    ElMessage.warning(msg)
  }
}

async function confirmCreateModel() {
  if (!selectedFolderId.value || !modelForm.code.trim()) {
    ElMessage.warning('请填写编号')
    return
  }
  if (!modelForm.name.trim()) {
    ElMessage.warning('请填写设备名称，或从采购汇总中选择')
    return
  }
  saving.value = true
  try {

    let attrs: Record<string, unknown> = { ...(modelForm.attributes || {}) }
    if (modelForm.category === 'network') {
      const role = switchRoleFromSubtype(modelForm.subtype)
      attrs = { ...defaultNetworkSwitchAttributes(role), ...attrs, switch_role: role }
      syncSwitchDerivedCounts(attrs)
      modelForm.height_u = asInt(attrs.chassis_height_u, 1)
    } else if (modelForm.category === 'server') {

      attrs = { ...defaultServerAttributes(normalizeServerFormFactor(modelForm.height_u || 1)), ...attrs }
      attrs.form_factor_u = normalizeServerFormFactor(modelForm.height_u || 1)
      syncServerDerivedAttrs(attrs)
      modelForm.height_u = asInt(attrs.form_factor_u, 1)
    } else if (modelForm.category === 'security') {

      attrs = {
        ...defaultSecurityAttributes(normalizeSecurityFormFactor(modelForm.height_u || 1), modelForm.subtype),
        ...attrs,
      }
      attrs.security_device_type = normalizeSecurityDeviceType(modelForm.subtype)
      syncSecurityDerivedAttrs(attrs)
      modelForm.height_u = normalizeSecurityFormFactor(attrs.chassis_height_u)
    }
    const draft: NetworkDesignModel = {
      id: '',
      folder_id: selectedFolderId.value,
      code: modelForm.code.trim(),
      name: modelForm.name.trim(),
      category: modelForm.category,
      subtype: modelForm.subtype,
      manufacturer_name: modelForm.manufacturer_name.trim() || null,
      vendor_sku: modelForm.vendor_sku.trim() || null,
      height_u: modelForm.height_u || 1,
      attributes: attrs,
      port_layout: null,
      device_model_id: modelForm.device_model_id,
      contract_device_name: modelForm.contract_device_name || modelForm.name.trim() || null,
      is_published: true,
      description: modelForm.description.trim() || null,
      created_at: '',
      updated_at: '',
    }
    let layout = null
    try {
      layout = buildPortLayoutFromDesignModel(draft)
    } catch (layoutErr) {
      console.warn('buildPortLayoutFromDesignModel failed', layoutErr)
      layout = null
    }
    const created = await createDesignModel({
      folder_id: selectedFolderId.value,
      code: draft.code,
      name: draft.name,
      category: draft.category,
      subtype: draft.subtype,
      manufacturer_name: draft.manufacturer_name,
      vendor_sku: draft.vendor_sku,
      height_u: draft.height_u,
      attributes: attrs,
      port_layout: layout,
      device_model_id: draft.device_model_id,
      contract_device_name: draft.contract_device_name,
      description: modelForm.description.trim() || null,
    })
    modelDialogVisible.value = false
    await refreshTree()
    await refreshModels()
    if (created?.id) {
      selectedModelId.value = created.id
      await selectModel(created)
    }
    ElMessage.success('模型已创建，已生成详细属性')
  } catch (err: unknown) {
    console.error(err)
    const msg =
      err instanceof Error
        ? err.message
        : (err as { response?: { data?: { message?: string } } })?.response?.data?.message
    ElMessage.error(msg || '创建模型失败')
  } finally {
    saving.value = false
  }
}

async function onSelectedCategoryChange() {
  const m = selectedModel.value
  if (!m) return
  m.subtype = DEFAULT_SUBTYPE[m.category] || m.subtype
  const cat = taxonomy.value.find((c) => c.value === m.category)
  if (cat && !cat.subtypes.some((s) => s.value === m.subtype)) {
    m.subtype = cat.subtypes[0]?.value || m.subtype
  }
  attrSchema.value = await fetchAttributeSchema(m.category, m.subtype)
  if (m.category === 'network') {
    m.attributes = defaultNetworkSwitchAttributes(switchRoleFromSubtype(m.subtype))
    m.height_u = asInt(m.attributes.chassis_height_u, 1)
  } else if (m.category === 'server') {
    m.attributes = defaultServerAttributes(1)
    m.height_u = 1
  } else if (m.category === 'security') {
    m.attributes = defaultSecurityAttributes(undefined, m.subtype)
    m.height_u = Number(m.attributes.form_factor_u) || 1
  } else {
    m.attributes = { ...(attrSchema.value?.default_attributes || {}) }
  }
}

async function onSelectedSubtypeChange() {
  const m = selectedModel.value
  if (!m) return
  attrSchema.value = await fetchAttributeSchema(m.category, m.subtype)
  if (m.category === 'network') {
    m.attributes = defaultNetworkSwitchAttributes(switchRoleFromSubtype(m.subtype))
    m.height_u = asInt(m.attributes.chassis_height_u, 1)
  } else if (m.category === 'server') {
    m.attributes = defaultServerAttributes(normalizeServerFormFactor(m.height_u))
  } else if (m.category === 'security') {
    m.attributes = defaultSecurityAttributes(undefined, m.subtype)
    m.height_u = Number(m.attributes.form_factor_u) || 1
  } else {
    m.attributes = { ...(attrSchema.value?.default_attributes || {}) }
  }
}

async function selectModel(row: NetworkDesignModel) {
  selectedModelId.value = row.id
  selectedSummaryKey.value = null
  if (row.category) {
    attrSchema.value = await fetchAttributeSchema(row.category, row.subtype)
  }
  if (row.category === 'server' && row.attributes) {
    if (!Array.isArray(row.attributes.server_slots) || !row.attributes.server_slots.length) {
      const seeded = defaultServerAttributes(
        normalizeServerFormFactor(row.attributes.form_factor_u ?? row.height_u),
      )
      row.attributes = { ...seeded, ...row.attributes, server_slots: seeded.server_slots }
    }
    syncServerDerivedAttrs(row.attributes)
    row.height_u = normalizeServerFormFactor(row.attributes.form_factor_u ?? row.height_u)
    ensurePanelLayout(row.attributes, serverIfaceSlotsToDesignSlots(readServerIfaceSlots(row.attributes), row.attributes), false)
  }
  if (row.category === 'security' && row.attributes) {
    row.attributes.security_device_type = normalizeSecurityDeviceType(row.subtype)
    if (!Array.isArray(row.attributes.security_slots) || !row.attributes.security_slots.length) {
      const seeded = defaultSecurityAttributes(
        normalizeSecurityFormFactor(row.attributes.chassis_height_u ?? row.height_u),
        row.subtype,
      )
      row.attributes = { ...seeded, ...row.attributes, security_slots: seeded.security_slots }
    }
    syncSecurityDerivedAttrs(row.attributes)
    row.height_u = normalizeSecurityFormFactor(row.attributes.chassis_height_u ?? row.height_u)
    ensurePanelLayout(row.attributes, [], false)
  }
  if (row.category === 'network' && row.attributes) {
    row.attributes.switch_role = row.subtype === 'switch' ? resolveDesignSwitchRole(row.attributes) : switchRoleFromSubtype(row.subtype)
    if (!Array.isArray(row.attributes.switch_slots) || !row.attributes.switch_slots.length) {
      const seeded = defaultNetworkSwitchAttributes(row.attributes.switch_role as SwitchSubtype)
      row.attributes = { ...seeded, ...row.attributes, switch_slots: seeded.switch_slots }
    }
    syncSwitchDerivedCounts(row.attributes)
    row.height_u = Math.max(
      1,
      asInt(row.attributes.chassis_height_u ?? row.height_u, row.height_u || 1),
    )
    if (row.attributes.fan_count == null) row.attributes.fan_count = 2
    if (row.attributes.psu_count == null) row.attributes.psu_count = 2
    if (row.attributes.mgmt_ports == null) row.attributes.mgmt_ports = 1
    ensurePanelLayout(row.attributes, [], false)
  }
  if (
    row.attributes &&
    row.category !== 'software' &&
    row.category !== 'server' &&
    row.category !== 'security' &&
    row.category !== 'network'
  ) {
    ensurePanelLayout(row.attributes, [], false)
  }
  syncSummaryKeyFromModel(row)
}

async function saveSelectedModel() {
  const m = selectedModel.value
  if (!m || !canEdit.value) return
  saving.value = true
  try {
    const attrs = { ...(m.attributes || {}) }
    if (m.category === 'server') {
      attrs.form_factor_u = normalizeServerFormFactor(m.height_u)
      syncServerDerivedAttrs(attrs)
      ensurePanelLayout(attrs, serverIfaceSlotsToDesignSlots(readServerIfaceSlots(attrs), attrs), false)
      m.attributes = attrs
      m.height_u = asInt(attrs.form_factor_u, 1)
    }
    if (m.category === 'security') {
      attrs.security_device_type = normalizeSecurityDeviceType(m.subtype)
      syncSecurityDerivedAttrs(attrs)
      attrs.chassis_height_u = normalizeSecurityFormFactor(m.height_u)
      ensurePanelLayout(attrs, [], false)
      m.attributes = attrs
      m.height_u = normalizeSecurityFormFactor(attrs.chassis_height_u)
    }
    if (m.category === 'network') {
      attrs.switch_role = m.subtype === 'switch' ? resolveDesignSwitchRole(attrs) : switchRoleFromSubtype(m.subtype)
      m.height_u = Math.max(1, asInt(attrs.chassis_height_u ?? m.height_u, m.height_u || 1))
      attrs.chassis_height_u = m.height_u
      syncSwitchDerivedCounts(attrs)
      ensurePanelLayout(attrs, [], false)
      m.attributes = attrs
    }
    // 面板始终由属性自动生成后落库
    const layout = buildPortLayoutFromDesignModel({ ...m, attributes: attrs, port_layout: null })
    m.port_layout = layout
    const updated = await updateDesignModel(m.id, {
      name: m.name,
      code: m.code,
      category: m.category,
      subtype: m.subtype,
      manufacturer_name: m.manufacturer_name,
      vendor_sku: m.vendor_sku,
      height_u: m.height_u,
      attributes: attrs,
      port_layout: layout,
      device_model_id: m.device_model_id,
      contract_device_name: m.contract_device_name,
      description: m.description,
      is_published: m.is_published,
    })
    if (updated) {
      const idx = models.value.findIndex((x) => x.id === m.id)
      if (idx >= 0) models.value[idx] = updated
    }
    ElMessage.success('模型已保存')
  } catch (err: unknown) {
    const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
    ElMessage.error(msg || '保存失败')
  } finally {
    saving.value = false
  }
}

async function removeModel(row: NetworkDesignModel) {
  try {
    await ElMessageBox.confirm(`确定删除模型「${row.name}」？`, '删除确认', { type: 'warning' })
    await deleteDesignModel(row.id)
    if (selectedModelId.value === row.id) selectedModelId.value = null
    await refreshTree()
    await refreshModels()
    ElMessage.success('已删除')
  } catch (err: unknown) {
    if (err === 'cancel') return
    const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
    ElMessage.error(msg || '删除失败')
  }
}

function attrFieldValue(key: string) {
  const m = selectedModel.value
  if (!m) return null
  if (!m.attributes) m.attributes = {}
  return m.attributes[key]
}

function setAttrField(key: string, value: unknown) {
  const m = selectedModel.value
  if (!m) return
  if (!m.attributes) m.attributes = {}
  m.attributes[key] = value
  if (m.category === 'server' && key === 'flex_io_slot_count') {
    m.attributes.pcie_slot_max = value
  } else if (m.category === 'server' && key === 'pcie_slot_max') {
    m.attributes.flex_io_slot_count = value
  }
  if (key === 'eth_mgmt_ports') {
    m.attributes.mgmt_ports = value
  }
  if (key === 'slot_count' && m.category === 'server') {
    syncServerDerivedAttrs(m.attributes)
  }
  if (
    m.category === 'server' &&
    [
      'psu_count',
      'psu_watt',
      'psu_redundancy',
      'bmc_ports',
      'ipmi_iface_count',
      'vga_count',
      'usb_count',
      'usb_ports',
      'lom_1g_count',
      'flex_io_count',
      'flex_io_speed',
      'slot_count',
      'server_slots',
      'disk_front_count',
      'disk_rear_count',
      'disk_front_size',
      'disk_rear_size',
      'disk_front_proto',
      'disk_rear_proto',
      'ssd_internal_count',
      'ssd_internal_iface',
      'ssd_max_count',
      'ssd_max_type',
      'flex_io_slot_count',
      'pcie_slot_max',
      'pcie_slots',
      'memory_type',
      'memory_modules',
      'os_support',
      'os_support_custom',
      'fan_count',
      'form_factor_u',
      'cpu_sockets',
      'cpu_cores_per_socket',
      'memory_module_gb',
      'memory_gb',
      'panel_style_image',
      'panel_style_image_rear',
    ].includes(key)
  ) {
    if (
      [
        'slot_count',
        'server_slots',
        'disk_front_count',
        'disk_rear_count',
        'form_factor_u',
        'bmc_ports',
        'ipmi_iface_count',
        'vga_count',
        'usb_count',
        'lom_1g_count',
        'flex_io_count',
        'flex_io_speed',
        'flex_io_slot_count',
        'pcie_slot_max',
        'pcie_slots',
      ].includes(key)
    ) {
      syncServerDerivedAttrs(m.attributes)
    }
    ensurePanelLayout(
      m.attributes,
      serverIfaceSlotsToDesignSlots(readServerIfaceSlots(m.attributes), m.attributes),
      false,
    )
  }
  if (
    m.category === 'security' &&
    ['slot_count', 'security_slots', 'fan_count', 'psu_count', 'chassis_height_u'].includes(key)
  ) {
    if (key === 'slot_count' || key === 'security_slots' || key === 'chassis_height_u') {
      syncSecurityDerivedAttrs(m.attributes)
    }
    ensurePanelLayout(m.attributes, [], false)
  }
  if (
    m.category === 'network' &&
    [
      'switch_role',
      'switch_slots',
      'card_slot_count',
      'downlink_count',
      'optical_card_count',
      'optical_ports_per_card',
      'uplink_count',
      'uplink_position',
      'uplink_type',
      'downlink_type',
      'downlink_media',
      'mgmt_ports',
      'console_ports',
      'eth_mgmt_ports',
      'usb_ports',
      'stack_cluster_ports',
      'fabric_slot_count',
      'airflow_type',
      'airflow_custom',
      'chassis_dim_a',
      'chassis_dim_b',
      'chassis_dim_c',
      'max_power_watt',
      'modular_expansion_slots',
      'service_board_count',
      'iface_board_type',
      'iface_board_port_count',
      'iface_board_port_custom',
      'iface_boards',
      'blank_panel_rows',
      'fan_count',
      'psu_count',
      'line_cards',
      'chassis_height_u',
    ].includes(key)
  ) {
    if (
      ![
        'mgmt_ports',
        'console_ports',
        'eth_mgmt_ports',
        'usb_ports',
        'stack_cluster_ports',
        'fabric_slot_count',
        'airflow_type',
        'airflow_custom',
        'chassis_dim_a',
        'chassis_dim_b',
        'chassis_dim_c',
        'max_power_watt',
        'fan_count',
        'psu_count',
      ].includes(key)
    ) {
      syncSwitchDerivedCounts(m.attributes)
    } else if (
      ['mgmt_ports', 'console_ports', 'eth_mgmt_ports', 'usb_ports', 'stack_cluster_ports'].includes(key)
    ) {
      syncSwitchDerivedCounts(m.attributes)
    }
    if (key === 'chassis_height_u') {
      m.height_u = Math.max(1, asInt(m.attributes.chassis_height_u, 1))
    }
    ensurePanelLayout(m.attributes, [], false)
  }
}

function refreshSwitchPanelLayout() {
  const m = selectedModel.value
  if (!m?.attributes || !isSwitchModel.value) return
  ensurePanelLayout(m.attributes, [], false)
}


function onSwitchRoleChange(role: SwitchSubtype) {
  const m = selectedModel.value
  if (!m) return
  if (!m.attributes) m.attributes = {}
  const panel = m.attributes.panel_layout
  const keepHw = {
    airflow_type: m.attributes.airflow_type,
    airflow_custom: m.attributes.airflow_custom,
    chassis_dim_a: m.attributes.chassis_dim_a,
    chassis_dim_b: m.attributes.chassis_dim_b,
    chassis_dim_c: m.attributes.chassis_dim_c,
    max_power_watt: m.attributes.max_power_watt,
    chassis_height_u: m.attributes.chassis_height_u,
    panel_style_image: m.attributes.panel_style_image,
  }
  m.subtype = role
  Object.assign(m.attributes, applySwitchStyleDefaults(m.attributes, role))
  if (panel) m.attributes.panel_layout = panel
  if (isCoreOrAggRole(role)) {
    Object.assign(m.attributes, keepHw)
  }
  syncSwitchDerivedCounts(m.attributes)
  m.height_u = Math.max(1, asInt(m.attributes.chassis_height_u, 1))
  refreshSwitchPanelLayout()
}

function onSwitchHeightChange(v: number | undefined) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const h = Math.max(1, Math.min(48, v ?? 1))
  m.height_u = h
  m.attributes.chassis_height_u = h
  if (isCoreAggSwitch.value) {
    const slots = Number(m.attributes.modular_expansion_slots) || 6
    if (slots > h) {
      m.attributes.modular_expansion_slots = h
      m.attributes.switch_slots = rebuildCoreExpansionSlots(m.attributes)
      syncSwitchDerivedCounts(m.attributes)
    }
    normalizeBlankPanelRows(m.attributes)
  }
  refreshSwitchPanelLayout()
}

function onModularExpansionChange(v: number | undefined) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const cap = coreExpansionCap(m.attributes)
  const n = Math.max(1, Math.min(cap, v ?? 6))
  m.attributes.modular_expansion_slots = n
  m.attributes.switch_slots = rebuildCoreExpansionSlots(m.attributes)
  syncSwitchDerivedCounts(m.attributes)
  normalizeBlankPanelRows(m.attributes)
  refreshSwitchPanelLayout()
}

function onServiceBoardCountChange(v: number | undefined) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const max = Math.max(1, Number(m.attributes.modular_expansion_slots) || 6)
  adjustCoreIfaceBoardCount(m.attributes, Math.max(0, Math.min(max, v ?? 4)))
  syncSwitchDerivedCounts(m.attributes)
  normalizeBlankPanelRows(m.attributes)
  refreshSwitchPanelLayout()
  nextTick(updateIfaceBoardNav)
}

function commitCoreIfaceBoards() {
  const m = selectedModel.value
  if (!m?.attributes) return
  syncSwitchDerivedCounts(m.attributes)
  refreshSwitchPanelLayout()
}

function coreBoardSlotOptions(slotIndex: number): number[] {
  const m = selectedModel.value
  if (!m?.attributes) return [slotIndex]
  return [slotIndex, ...emptyCoreSlotIndexes(m.attributes)].sort((a, b) => a - b)
}

function boardPortPreset(board: SwitchIfaceBoardPlacement): string {
  if (board.port_custom) return 'other'
  if (SWITCH_IFACE_BOARD_PORT_PRESETS.includes(board.port_count as (typeof SWITCH_IFACE_BOARD_PORT_PRESETS)[number])) {
    return String(board.port_count)
  }
  return 'other'
}

function onCoreBoardSlotChange(fromSlot: number, toSlot: number) {
  const m = selectedModel.value
  if (!m?.attributes) return
  updateCoreIfaceBoard(m.attributes, fromSlot, { slot_index: toSlot })
  commitCoreIfaceBoards()
}

function onCoreBoardKindChange(slotIndex: number, kind: SwitchIfaceBoardKind) {
  const m = selectedModel.value
  if (!m?.attributes) return
  updateCoreIfaceBoard(m.attributes, slotIndex, { kind })
  commitCoreIfaceBoards()
}

function onCoreBoardPortPreset(slotIndex: number, v: string) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const board = readCoreIfaceBoards(m.attributes).find((b) => b.slot_index === slotIndex)
  if (v === 'other') {
    const cur = board?.port_count || 48
    const next = SWITCH_IFACE_BOARD_PORT_PRESETS.includes(cur as (typeof SWITCH_IFACE_BOARD_PORT_PRESETS)[number])
      ? 36
      : cur
    updateCoreIfaceBoard(m.attributes, slotIndex, { port_custom: true, port_count: next })
  } else {
    updateCoreIfaceBoard(m.attributes, slotIndex, {
      port_custom: false,
      port_count: Math.max(1, Number(v) || 48),
    })
  }
  commitCoreIfaceBoards()
}

function onCoreBoardPortCustom(slotIndex: number, v: number | undefined) {
  const m = selectedModel.value
  if (!m?.attributes) return
  updateCoreIfaceBoard(m.attributes, slotIndex, {
    port_custom: true,
    port_count: Math.max(1, Math.min(128, v ?? 36)),
  })
  commitCoreIfaceBoards()
}

function onAddCoreIfaceBoard() {
  const m = selectedModel.value
  if (!m?.attributes) return
  if (!addCoreIfaceBoard(m.attributes)) {
    ElMessage.warning('模块化扩展插槽已满')
    return
  }
  commitCoreIfaceBoards()
  nextTick(() => {
    const el = ifaceBoardViewport.value
    if (el) el.scrollTo({ left: el.scrollWidth, behavior: 'smooth' })
    updateIfaceBoardNav()
  })
}

function updateIfaceBoardNav() {
  const el = ifaceBoardViewport.value
  if (!el) {
    ifaceBoardCanPrev.value = false
    ifaceBoardCanNext.value = false
    return
  }
  ifaceBoardCanPrev.value = el.scrollLeft > 2
  ifaceBoardCanNext.value = el.scrollLeft + el.clientWidth < el.scrollWidth - 2
}

function scrollIfaceBoards(dir: -1 | 1) {
  const el = ifaceBoardViewport.value
  if (!el) return
  const card = el.querySelector('.iface-board-card') as HTMLElement | null
  const step = (card?.offsetWidth || 168) + 8
  el.scrollBy({ left: dir * step, behavior: 'smooth' })
  window.setTimeout(updateIfaceBoardNav, 280)
}

function onRemoveCoreIfaceBoard(slotIndex: number) {
  const m = selectedModel.value
  if (!m?.attributes) return
  removeCoreIfaceBoard(m.attributes, slotIndex)
  commitCoreIfaceBoards()
}

function chassisPortMeta(slotIndex: number, portIndex: number) {
  const slot = switchSlots.value.find((s) => s.index === slotIndex)
  if (!slot) return null
  const kind = slotCardToIfaceBoard(slot.card_type)
  const spec = resolveSlotPort(slot, portIndex)
  const labels = ifaceBoardTwoRowLabels(effectivePortCount(slot), Math.max(0, Number(slot.port_start) || 0))
  const boardLabel = isAccessSwitch.value
    ? slot.purpose === 'UPLINK'
      ? `上联接口 / UPLINK · ${accessUplinkLabel.value}`
      : `业务接口 / DOWNLINK · ${accessDownlinkLabel.value}`
    : `Slot ${slot.index} ${ifaceBoardKindLabel(kind)}`
  return {
    slot,
    spec,
    boardLabel,
    ordinal: `第 ${portIndex + 1} 个`,
    portNo: labels[portIndex] ?? String(portIndex),
  }
}

function applyChassisPortDraft(
  spec: SwitchBoardPortAttr,
  meta: { slotIndex: number; portId: string; boardLabel: string; ordinal: string; portNo: string },
) {
  chassisPortDraftMeta.slotIndex = meta.slotIndex
  chassisPortDraftMeta.portId = meta.portId
  chassisPortDraftMeta.boardLabel = meta.boardLabel
  chassisPortDraftMeta.ordinal = meta.ordinal
  chassisPortDraftMeta.portNo = meta.portNo
  Object.assign(chassisPortDraft, spec)
}

function onChassisPortSelect(payload: { slotIndex: number; portIndex: number }) {
  chassisPortInfo.value = null
  const meta = chassisPortMeta(payload.slotIndex, payload.portIndex)
  if (!meta) return
  selectedChassisPort.value = { ...payload }
  applyChassisPortDraft(meta.spec, {
    slotIndex: payload.slotIndex,
    portId: '',
    boardLabel: meta.boardLabel,
    ordinal: meta.ordinal,
    portNo: meta.portNo,
  })
  chassisPortEditVisible.value = true
}

function onChassisPortInspect(payload: { slotIndex: number; portIndex: number; x: number; y: number }) {
  const meta = chassisPortMeta(payload.slotIndex, payload.portIndex)
  if (!meta) return
  selectedChassisPort.value = { slotIndex: payload.slotIndex, portIndex: payload.portIndex }
  chassisPortInfo.value = {
    x: Math.min(payload.x, window.innerWidth - 300),
    y: Math.min(payload.y, window.innerHeight - 320),
    slotIndex: payload.slotIndex,
    portIndex: payload.portIndex,
    boardLabel: meta.boardLabel,
    ordinal: meta.ordinal,
    portNo: meta.portNo,
    spec: meta.spec,
  }
}

function systemPortMeta(portId: string) {
  const spec = switchSystemPorts.value.find((p) => p.id === portId)
  if (spec) {
    return {
      spec,
      boardLabel: systemPortKindLabel(spec.kind),
      ordinal: `第 ${spec.index + 1} 个`,
      portNo: spec.code,
    }
  }
  const srv = serverPorts.value.find((p) => p.id === portId)
  if (!srv) return null
  const serverSpec: SwitchBoardPortAttr = {
    index: srv.index,
    id: srv.id,
    code: srv.code,
    iface_type: srv.iface_type === 'optical' ? 'optical' : 'copper',
    speed: srv.speed,
    module: srv.module,
    connector: srv.connector,
    fiber_mode: srv.fiber_mode === 'sm' || srv.fiber_mode === 'mm' ? srv.fiber_mode : 'na',
  }
  return {
    spec: serverSpec,
    boardLabel: serverPortKindLabel(srv.kind),
    ordinal: `第 ${srv.index + 1} 个`,
    portNo: srv.code,
  }
}

function onSystemPortSelect(portId: string) {
  chassisPortInfo.value = null
  const meta = systemPortMeta(portId)
  if (!meta) return
  selectedChassisPort.value = { slotIndex: 0, portIndex: meta.spec.index, portId }
  if (isServerModel.value) return
  applyChassisPortDraft(meta.spec, {
    slotIndex: 0,
    portId,
    boardLabel: meta.boardLabel,
    ordinal: meta.ordinal,
    portNo: meta.portNo,
  })
  chassisPortEditVisible.value = true
}

function onSystemPortInspect(portId: string, ev: MouseEvent) {
  ev.preventDefault()
  ev.stopPropagation()
  const meta = systemPortMeta(portId)
  if (!meta) return
  selectedChassisPort.value = { slotIndex: 0, portIndex: meta.spec.index, portId }
  chassisPortInfo.value = {
    x: Math.min(ev.clientX, window.innerWidth - 300),
    y: Math.min(ev.clientY, window.innerHeight - 320),
    slotIndex: 0,
    portIndex: meta.spec.index,
    portId,
    boardLabel: meta.boardLabel,
    ordinal: meta.ordinal,
    portNo: meta.portNo,
    spec: meta.spec,
  }
}

function onChassisPortEditFromInfo() {
  const info = chassisPortInfo.value
  if (!info) return
  if (info.portId) onSystemPortSelect(info.portId)
  else onChassisPortSelect({ slotIndex: info.slotIndex, portIndex: info.portIndex })
}

function closeChassisPortInfo() {
  chassisPortInfo.value = null
}

function onChassisPortDraftType(v: SwitchPortIfaceType) {
  chassisPortDraft.iface_type = v
  if (v === 'copper') {
    const usb = chassisPortDraftMeta.portId.startsWith('usb-')
    chassisPortDraft.speed = usb ? 'USB' : '1GE'
    chassisPortDraft.module = usb ? 'USB' : 'RJ45'
    chassisPortDraft.connector = usb ? 'USB' : 'RJ45'
    chassisPortDraft.fiber_mode = 'na'
    return
  }
  if (chassisPortDraftMeta.portId) {
    Object.assign(chassisPortDraft, defaultSystemPortSpec('stack'), {
      iface_type: 'optical',
      index: chassisPortDraft.index,
      id: chassisPortDraft.id,
      code: chassisPortDraft.code,
    })
    return
  }
  if (isAccessSwitch.value) {
    const slot = switchSlots.value.find((s) => s.index === chassisPortDraftMeta.slotIndex)
    const spec =
      slot?.purpose === 'UPLINK'
        ? defaultAccessUplinkSpec(switchRole.value, readTenGigUplinkKind(selectedModel.value?.attributes))
        : defaultAccessDownlinkSpec(switchRole.value, readGigabitDownlinkMedia(selectedModel.value?.attributes))
    Object.assign(chassisPortDraft, spec, {
      iface_type: 'optical',
      index: chassisPortDraft.index,
      id: chassisPortDraft.id,
      code: chassisPortDraft.code,
    })
    return
  }
  const kind = slotCardToIfaceBoard(
    switchSlots.value.find((s) => s.index === chassisPortDraftMeta.slotIndex)?.card_type || 'ten_gigabit',
  )
  Object.assign(chassisPortDraft, defaultPortSpecForKind(kind), {
    iface_type: 'optical',
    index: chassisPortDraft.index,
    id: chassisPortDraft.id,
    code: chassisPortDraft.code,
  })
}

function onChassisPortDraftSpeed(v: string) {
  chassisPortDraft.speed = v
  if (chassisPortDraft.iface_type === 'copper') return
  Object.assign(chassisPortDraft, suggestPortSpecBySpeed(v), {
    speed: v,
    index: chassisPortDraft.index,
    id: chassisPortDraft.id,
    code: chassisPortDraft.code,
  })
}

function saveChassisPortEdit() {
  const m = selectedModel.value
  const sel = selectedChassisPort.value
  if (!m?.attributes || !sel || !canEdit.value) return
  const patch: Partial<SwitchBoardPortAttr> = {
    iface_type: chassisPortDraft.iface_type,
    speed: chassisPortDraft.speed,
    module: chassisPortDraft.module,
    connector: chassisPortDraft.connector,
    fiber_mode: chassisPortDraft.fiber_mode as SwitchPortFiberMode,
  }
  if (sel.portId) patchSwitchSystemPort(m.attributes, sel.portId, patch)
  else if (isCoreAggSwitch.value) patchCoreBoardPort(m.attributes, sel.slotIndex, sel.portIndex, patch)
  else patchAccessBoardPort(m.attributes, sel.slotIndex, sel.portIndex, patch)
  chassisPortEditVisible.value = false
}

function onMoveBlankPanel(fromRow: number, toRow: number) {
  const m = selectedModel.value
  if (!m?.attributes || !canEdit.value) return
  moveBlankPanelRow(m.attributes, fromRow, toRow)
}

function onMoveSwitchSlot(fromSlot: number, toSlot: number) {
  const m = selectedModel.value
  if (!m?.attributes || !canEdit.value || fromSlot === toSlot) return
  const boards = readCoreIfaceBoards(m.attributes)
  const source = boards.find((board) => board.slot_index === fromSlot)
  const target = boards.find((board) => board.slot_index === toSlot)
  if (source) {
    // updateCoreIfaceBoard 在目标已占用时会交换两块板的位置。
    updateCoreIfaceBoard(m.attributes, fromSlot, { slot_index: toSlot })
  } else if (target) {
    // 从空槽拖向接口板时，将目标板移动到该空槽。
    updateCoreIfaceBoard(m.attributes, toSlot, { slot_index: fromSlot })
  } else {
    return
  }
  commitCoreIfaceBoards()
}

function onNudgeBlankPanel(fromRow: number, dir: -1 | 1) {
  const m = selectedModel.value
  if (!m?.attributes || !canEdit.value) return
  nudgeBlankPanelRow(m.attributes, fromRow, dir)
}

function onAccessDownlinkPreset(v: string) {
  if (v === 'other') {
    const cur = Number(attrFieldValue('downlink_count') ?? 48)
    if (ACCESS_DOWNLINK_COUNT_PRESETS.includes(cur as (typeof ACCESS_DOWNLINK_COUNT_PRESETS)[number])) {
      setAttrField('downlink_count', 36)
    }
    return
  }
  setAttrField('downlink_count', Number(v) || 48)
}

function onAccessUplinkPreset(v: string) {
  setAttrField('uplink_count', Number(v) || (switchRole.value === 'gigabit' ? 8 : 6))
}

function onTenGigUplinkKind(v: TenGigUplinkKind) {
  setAttrField('uplink_type', v === '100ge' ? '100g' : '40g')
}

function onGigabitDownlinkMedia(v: GigabitDownlinkMedia) {
  setAttrField('downlink_media', v)
}

function openCustomPanel() {
  const m = selectedModel.value
  if (!m?.attributes) return
  ensurePanelLayout(m.attributes, [], false)
  customPanelVisible.value = true
}

function onCustomPanelBoardChange(payload: { items: PanelLayoutItem[] }) {
  const m = selectedModel.value
  if (!m?.attributes || !canEdit.value) return
  if (!isCoreAggSwitch.value) return
  const attrs = m.attributes
  const cap = Math.max(1, Number(attrs.modular_expansion_slots) || 6)
  const boards = payload.items
    .filter((item) => item.kind === 'line_card' && !item.blank)
    .slice()
    .sort((a, b) => a.row - b.row || a.col - b.col)
    .slice(0, cap)
    .map((item, idx) => {
      const slotIndex = Math.max(1, Math.min(cap, Number(item.slot_index) || idx + 1))
      const prev = readCoreIfaceBoards(attrs).find((b) => b.slot_index === slotIndex)
      return {
        slot_index: slotIndex,
        kind: portTypeToIfaceKind(item.port_type),
        port_count: Math.max(1, Math.min(128, Number(item.port_count) || 48)),
        ports: prev?.ports,
      }
    })
  const used = new Set<number>()
  for (const board of boards) {
    if (used.has(board.slot_index)) {
      let slot = 1
      while (used.has(slot) && slot <= cap) slot += 1
      board.slot_index = slot
    }
    if (board.slot_index <= cap) used.add(board.slot_index)
  }
  persistCoreIfaceBoards(
    attrs,
    boards.filter((b) => b.slot_index >= 1 && b.slot_index <= cap),
  )
  syncSwitchDerivedCounts(attrs)
}



function commitServerIfaceSlots(slots: ServerIfaceSlotAttr[]) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const next = renumberServerSlotPorts(slots)
  m.attributes.server_slots = next
  m.attributes.slot_count = next.length
  m.attributes.slots = serverIfaceSlotsToDesignSlots(next, m.attributes)
  syncServerDerivedAttrs(m.attributes)
  ensurePanelLayout(m.attributes, serverIfaceSlotsToDesignSlots(next, m.attributes), false)
}

function onFlexIoSlotCountChange(v: number | undefined) {
  const requested = Math.max(0, v ?? 0)
  const count = Math.min(serverPcieSlotMax.value, requested)
  if (requested > serverPcieSlotMax.value) {
    ElMessage.warning(`当前 ${normalizeServerFormFactor(selectedModel.value?.height_u ?? selectedModel.value?.attributes?.form_factor_u)}U 背板最多可安装 ${serverPcieSlotMax.value} 个 PCIe Slot`)
  }
  setAttrField('flex_io_slot_count', count)
}

function onServerHeightChange(v: number | string | undefined) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const u = normalizeServerFormFactor(v)
  m.height_u = u
  Object.assign(m.attributes, applyServerHeightDefaults(m.attributes, u))
  ensurePanelLayout(
    m.attributes,
    serverIfaceSlotsToDesignSlots(readServerIfaceSlots(m.attributes), m.attributes),
    false,
  )
}

function onServerMemoryModuleChange(v: number | undefined) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const moduleGb = Math.max(1, v ?? 16)
  m.attributes.memory_module_gb = moduleGb
  const modules = Math.max(1, Number(m.attributes.memory_modules) || 8)
  // 若总内存为空或仍等于旧模块推导值，则按模块刷新
  m.attributes.memory_gb = moduleGb * modules
  setAttrField('memory_module_gb', moduleGb)
}

function onServerDiskFrontChange(v: number | undefined) {
  setAttrField('disk_front_count', Math.max(0, Math.min(serverDiskFrontMax.value, v ?? 0)))
}

function onServerDiskRearChange(v: number | undefined) {
  setAttrField('disk_rear_count', Math.max(0, Math.min(serverDiskRearMax.value, v ?? 0)))
}

function pcieSpeedOptions(slot: ServerPcieSlotAttr) {
  return slot.card_type === 'nic_copper'
    ? SERVER_FLEX_SPEED_OPTIONS.filter((option) => option.value === '1ge' || option.value === '10ge')
    : SERVER_FLEX_SPEED_OPTIONS.filter((option) => option.value !== '1ge')
}

function patchPcieSlot(slotIndex: number, patch: Partial<ServerPcieSlotAttr>) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const normalizedPatch = normalizeServerFormFactor(m.height_u ?? m.attributes.form_factor_u) === 1
    ? { ...patch, orientation: 'horizontal' as const }
    : patch
  const next = readPcieSlots(m.attributes).map((slot) => {
    if (slot.index !== slotIndex) return { ...slot }
    const merged = { ...slot, ...normalizedPatch }
    const isNic = merged.card_type === 'nic_copper' || merged.card_type === 'nic_optical'
    const portCount = (isNic ? (merged.port_count === 4 ? 4 : 2) : 0) as 0 | 2 | 4
    const allowedSpeeds = pcieSpeedOptions(merged).map((option) => option.value)
    const speed = allowedSpeeds.includes(merged.speed) ? merged.speed : allowedSpeeds[0] || '10ge'
    return {
      ...merged,
      port_count: portCount,
      flex_ports: portCount,
      speed,
      raid_level: merged.card_type === 'raid' ? merged.raid_level || 'raid1' : undefined,
    }
  })
  setAttrField('pcie_slots', next)
}

function onPcieCardTypeChange(slotIndex: number, cardType: ServerPcieCardType) {
  patchPcieSlot(slotIndex, { card_type: cardType, port_count: cardType.startsWith('nic_') ? 2 : 0 })
}

function onPciePortCountChange(slotIndex: number, count: number) {
  patchPcieSlot(slotIndex, { port_count: count === 4 ? 4 : 2 })
}

function onPcieSpeedChange(slotIndex: number, speed: ServerFlexSpeed) {
  patchPcieSlot(slotIndex, { speed })
}

function onServerMemoryModulesChange(v: number | undefined) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const modules = Math.max(1, Math.min(64, v ?? 8))
  m.attributes.memory_modules = modules
  const moduleGb = Math.max(1, Number(m.attributes.memory_module_gb) || 16)
  m.attributes.memory_gb = moduleGb * modules
  setAttrField('memory_modules', modules)
}

function onServerOsSupportChange(v: string[]) {
  setAttrField('os_support', normalizeOsSupport(v))
}

function onServerStyleImageUpload(side: 'front' | 'rear', ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请选择图片文件')
    return
  }
  if (file.size > 2 * 1024 * 1024) {
    ElMessage.warning('图片不超过 2MB')
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    const key = side === 'front' ? 'panel_style_image' : 'panel_style_image_rear'
    setAttrField(key, String(reader.result || ''))
    setAttrField('panel_style_mode', 'custom')
    serverPanelShowImage.value = true
    ElMessage.success(side === 'front' ? '已上传前面板样式图' : '已上传后面板样式图')
  }
  reader.readAsDataURL(file)
}

function clearServerStyleImage(side: 'front' | 'rear') {
  const key = side === 'front' ? 'panel_style_image' : 'panel_style_image_rear'
  setAttrField(key, null)
  if (!serverStyleImageFront.value && !serverStyleImageRear.value) {
    setAttrField('panel_style_mode', 'generated')
    serverPanelShowImage.value = false
  }
}

function commitSecurityIfaceSlots(slots: SecurityIfaceSlotAttr[]) {
  const m = selectedModel.value
  if (!m?.attributes) return
  m.attributes.security_slots = slots.map((s, i) => ({ ...s, index: i + 1 }))
  m.attributes.slot_count = slots.length
  syncSecurityDerivedAttrs(m.attributes)
  ensurePanelLayout(m.attributes, [], false)
}

function onSecurityHeightChange(v: number | string | undefined) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const u = normalizeSecurityFormFactor(v)
  m.height_u = u
  m.attributes.chassis_height_u = u
  syncSecurityDerivedAttrs(m.attributes)
  ensurePanelLayout(m.attributes, [], false)
}

function patchSecurityIfaceSlot(idx: number, patch: Partial<SecurityIfaceSlotAttr>) {
  const slots = securityIfaceSlots.value.map((s) => ({ ...s }))
  const slot = slots[idx]
  if (!slot) return
  Object.assign(slot, patch)
  commitSecurityIfaceSlots(slots)
}

function addSecurityIfaceSlot() {
  const slots = securityIfaceSlots.value.map((slot) => ({ ...slot }))
  if (slots.length >= MAX_SECURITY_IFACE_SLOTS) {
    ElMessage.warning('安全设备最多支持 8 个 Slot')
    return
  }
  slots.push({
    index: slots.length + 1,
    control_count: 0,
    ha_count: 0,
    mgmt_count: 0,
    usb_count: 0,
    ports_10g: 4,
    ports_1g: 2,
  })
  commitSecurityIfaceSlots(slots)
}

async function removeSecurityIfaceSlot(idx: number) {
  const slots = securityIfaceSlots.value.map((slot) => ({ ...slot }))

  try {
    await ElMessageBox.confirm(
      `确定删除 Slot ${idx + 1}？后续 Slot 与接口编号将自动顺延。`,
      '删除 Slot',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  slots.splice(idx, 1)
  commitSecurityIfaceSlots(slots)
}


function onPanelSlotUpdate(slot: DesignSlotAttr) {
  const m = selectedModel.value
  if (!m?.attributes || !canEdit.value) return
  const slots = normalizeDesignSlots(m.attributes)
  const idx = slots.findIndex((s) => s.index === slot.index)
  if (idx < 0) return
  const next = { ...slot }
  syncSlotInterfaces(next)
  slots[idx] = next
  m.attributes.slots = [...slots]
  m.attributes.slot_count = slots.length
  // 同步回 server_slots，保留原 IPMI/HDMI/USB
  const iface = readServerIfaceSlots(m.attributes).map((s) => ({ ...s }))
  while (iface.length < slots.length) {
    iface.push(defaultExpansionSlot(iface.length + 1))
  }
  const target = iface[idx]
  if (target) {
    if (next.type === 'nic_10g' || next.type === 'nic_1g') {
      const list = Array.isArray(next.interfaces) ? next.interfaces : []
      const n10 = list.filter((x) => String(x.port_type) === '10g').length
      const n1 = list.filter((x) => String(x.port_type) === '1g').length
      if (list.length) {
        if (isOnboardSlot(target) || target.index === 1) {
          target.kind = 'onboard'
          target.ports_10g = n10
          target.ports_1g = n1
        } else if (n10 > 0) {
          target.ports_10g = n10
          target.ports_1g = 0
        } else {
          target.ports_10g = 0
          target.ports_1g = n1
        }
      } else if (next.type === 'nic_10g') {
        target.ports_10g = Math.max(0, Number(next.port_count) || 0)
        if (!isOnboardSlot(target)) target.ports_1g = 0
      } else {
        target.ports_1g = Math.max(0, Number(next.port_count) || 0)
        if (!isOnboardSlot(target)) target.ports_10g = 0
      }
    } else if (next.type === 'blank' || next.type === 'raid') {
      target.ports_10g = 0
      target.ports_1g = 0
    }
  }
  commitServerIfaceSlots(iface.slice(0, slots.length))
}

const SLOT_PORT_TYPE_OPTIONS = [
  { value: '1g', label: '千兆 1G' },
  { value: '10g', label: '万兆 10G' },
  { value: 'disk', label: '磁盘' },
  { value: 'other', label: '其它' },
]

const slotEditorVisible = ref(false)
const slotEditorSide = ref<PanelSide>('rear')
const slotEditorItemId = ref<string | null>(null)
/** 关闭后短时禁止再次打开，避免点击穿透立刻重开 */
const suppressSlotEditorOpenUntil = ref(0)
const slotDraft = reactive<{
  index: number
  type: string
  port_count: number
  raid_level: string
  interfaces: DesignSlotInterface[]
}>({
  index: 0,
  type: 'nic_10g',
  port_count: 2,
  raid_level: 'raid1',
  interfaces: [],
})

function openPanelSlotEditor(payload: { side: PanelSide; item: PanelLayoutItem }) {
  if (Date.now() < suppressSlotEditorOpenUntil.value) return
  if (slotEditorVisible.value) return
  const m = selectedModel.value
  if (!m?.attributes) return
  const slots = normalizeDesignSlots(m.attributes)
  const slot = slots.find((s) => s.index === payload.item.slot_index)
  if (!slot) {
    ElMessage.warning('未找到对应 Slot 属性')
    return
  }
  const synced = { ...slot, interfaces: [...(slot.interfaces || [])] }
  syncSlotInterfaces(synced)
  // 仅补全缺失的口类型，保留 Slot 内 10G/1G 混排
  if (synced.type === 'nic_1g' || synced.type === 'nic_10g') {
    const def = synced.type === 'nic_1g' ? '1g' : '10g'
    synced.interfaces = (synced.interfaces || []).map((x) => ({
      ...x,
      port_type: String(x.port_type || def),
    }))
  }
  slotEditorSide.value = payload.side
  slotEditorItemId.value = payload.item.id
  slotDraft.index = synced.index
  slotDraft.type = String(synced.type)
  slotDraft.port_count = Number(synced.port_count) || 0
  slotDraft.raid_level = String(synced.raid_level || 'raid1')
  slotDraft.interfaces = (synced.interfaces || []).map((x) => ({ ...x }))
  slotEditorVisible.value = true
}

function closePanelSlotEditor() {
  slotEditorVisible.value = false
  suppressSlotEditorOpenUntil.value = Date.now() + 600
}

function onSlotDraftTypeChange(type: string) {
  slotDraft.type = type
  if (type === 'nic_1g' || type === 'nic_10g') {
    slotDraft.port_count = slotDraft.port_count > 0 ? slotDraft.port_count : 2
  } else if (type === 'raid') {
    slotDraft.port_count = 0
    slotDraft.raid_level = slotDraft.raid_level || 'raid1'
  } else if (type === 'blank') {
    slotDraft.port_count = 0
  } else {
    slotDraft.port_count = slotDraft.port_count > 0 ? slotDraft.port_count : 1
  }
  const tmp: DesignSlotAttr = {
    index: slotDraft.index,
    type: slotDraft.type,
    port_count: slotDraft.port_count,
    raid_level: slotDraft.raid_level,
    interfaces: slotDraft.interfaces,
  }
  syncSlotInterfaces(tmp)
  slotDraft.interfaces = (tmp.interfaces || []).map((x) => ({ ...x }))
}

function onSlotDraftPortCountChange(n: number | undefined) {
  slotDraft.port_count = Math.max(1, Math.min(8, n ?? 1))
  const tmp: DesignSlotAttr = {
    index: slotDraft.index,
    type: slotDraft.type,
    port_count: slotDraft.port_count,
    raid_level: slotDraft.raid_level,
    interfaces: slotDraft.interfaces,
  }
  syncSlotInterfaces(tmp)
  slotDraft.interfaces = (tmp.interfaces || []).map((x) => ({ ...x }))
}

function savePanelSlotEditor() {
  const m = selectedModel.value
  // 先关窗，再写数据，避免关闭瞬间点击穿透重开
  closePanelSlotEditor()
  if (!m?.attributes || !canEdit.value) return
  try {
    const next: DesignSlotAttr = {
      index: slotDraft.index,
      type: slotDraft.type,
      port_count: slotDraft.port_count,
      raid_level: slotDraft.type === 'raid' ? slotDraft.raid_level : undefined,
      interfaces: (slotDraft.interfaces || []).map((x) => ({ ...x })),
    }
    syncSlotInterfaces(next)
    onPanelSlotUpdate(next)

    const layout = normalizePanelLayoutConfig(m.attributes.panel_layout)
    const side = slotEditorSide.value
    const itemId = slotEditorItemId.value
    layout[side].items = layout[side].items.map((it) => {
      if (it.id !== itemId) return it
      const label =
        next.type === 'nic_1g' || next.type === 'nic_10g'
          ? serverSlotLabelFromInterfaces(next.index, next.interfaces)
          : next.type === 'blank'
            ? `Slot${next.index}:空白`
            : `Slot${next.index}:${slotTypeLabel(String(next.type)).replace(/接口$/, '')}`
      const n10 = (next.interfaces || []).filter((x) => String(x.port_type) === '10g').length
      const n1 = (next.interfaces || []).filter((x) => String(x.port_type) === '1g').length
      return {
        ...it,
        label,
        slot_index: next.index,
        port_count: next.port_count,
        port_type: n10 > 0 && n1 <= 0 ? '10g' : n1 > 0 && n10 <= 0 ? '1g' : undefined,
        blank: next.type === 'blank',
      }
    })
    m.attributes.panel_layout = layout
    ElMessage.success('已更新 Slot 接口')
  } catch (e) {
    console.error(e)
    ElMessage.error('保存失败')
  }
}

function removePanelSlotItem() {
  const m = selectedModel.value
  const itemId = slotEditorItemId.value
  const side = slotEditorSide.value
  closePanelSlotEditor()
  if (!m?.attributes || !itemId) return
  const layout = normalizePanelLayoutConfig(m.attributes.panel_layout)
  layout[side].items = layout[side].items.filter((i) => i.id !== itemId)
  m.attributes.panel_layout = layout
  ElMessage.success('已从面板移除')
}

function listFieldText(key: string) {
  const v = attrFieldValue(key)
  if (Array.isArray(v)) return v.join(', ')
  return v == null ? '' : String(v)
}

function setListField(key: string, text: string) {
  const parts = text
    .split(/[,，\n]/)
    .map((s) => s.trim())
    .filter(Boolean)
  setAttrField(key, parts)
}

function resetPanelAutoPlace() {
  const m = selectedModel.value
  if (!m?.attributes || !canEdit.value || m.category === 'software') return
  if (m.category === 'server') {
    syncServerDerivedAttrs(m.attributes)
    ensurePanelLayout(
      m.attributes,
      serverIfaceSlotsToDesignSlots(readServerIfaceSlots(m.attributes), m.attributes),
      true,
    )
  } else {
    ensurePanelLayout(m.attributes, [], true)
  }
  ElMessage.success('已在当前自定义网格内按属性自动定位')
}

async function loadContractSummaries() {
  try {
    contractSummaries.value = (await getContractSummary()) || []
  } catch {
    contractSummaries.value = []
  }
}

function syncSummaryKeyFromModel(m: NetworkDesignModel) {
  if (!m.contract_device_name && !m.device_model_id) {
    selectedSummaryKey.value = null
    return
  }
  const exact = contractSummaries.value.find((row) => row.device_name === m.contract_device_name)
  selectedSummaryKey.value = exact ? summaryOptionKey(exact) : null
}

async function onSummaryChange(key: string | null) {
  const m = selectedModel.value
  if (!m) return
  if (!key) {
    m.device_model_id = null
    m.contract_device_name = null
    return
  }
  if (!contractSummaries.value.length) await loadContractSummaries()
  const row = contractSummaries.value.find((r) => summaryOptionKey(r) === key)
  if (!row) return
  try {
    const resolved = await resolveModelFromSummary(row)
    m.device_model_id = resolved.id
    m.contract_device_name = (row.device_name || '').trim() || null
    m.name = m.contract_device_name || m.name
    m.vendor_sku = (row.device_model_name || '').trim() || m.vendor_sku
    m.manufacturer_name = (row.manufacturer_name || '').trim() || m.manufacturer_name
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '关联合同型号失败'
    ElMessage.error(msg)
  }
}

function modelRowClassName({ row }: { row: NetworkDesignModel }) {
  return row.id === selectedModelId.value ? 'is-current' : ''
}

const selectedSubtypeOptions = computed(() => {
  const cat = selectedModel.value?.category
  if (!cat) return []
  return taxonomy.value.find((c) => c.value === cat)?.subtypes || []
})

/** 属性字段跨列：短字段 1 列，列表 2 列，长文本占满行 */
function attrFieldSpan(field: AttributeFieldDef): number {
  if (field.key === 'slot_count') return 1
  if (field.type === 'list') return 2
  if (field.type === 'string' && (field.key === 'version' || (field.label?.length || 0) > 8)) return 2
  if (field.description && field.type !== 'bool' && field.type !== 'int' && field.type !== 'float') return 2
  return 1
}

watch(selectedFolderId, async () => {
  selectedModelId.value = null
  await refreshModels()
})

watch(
  [coreIfaceBoards, selectedModelId],
  () => {
    nextTick(updateIfaceBoardNav)
  },
)

onMounted(() => {
  void loadAll()
  void loadContractSummaries()
})
</script>

<template>
  <div v-loading="loading" class="model-design">
    <aside class="tree-pane">
      <div class="pane-head">
        <span class="pane-title">模型库</span>
        <div class="pane-actions">
          <el-button size="small" :disabled="!canCreate" @click="openFolderDialog('folder')">
            新建文件夹
          </el-button>
          <el-button size="small" type="primary" :disabled="!canCreate" @click="openFolderDialog('project')">
            新建项目
          </el-button>
        </div>
      </div>
      <el-tree
        :data="tree"
        node-key="id"
        highlight-current
        default-expand-all
        :current-node-key="selectedFolderId || undefined"
        :props="{ label: 'name', children: 'children' }"
        @node-click="(data: NetworkModelFolderTreeNode) => (selectedFolderId = data.id)"
      >
        <template #default="{ data }">
          <span class="tree-node">
            <span>{{ data.kind === 'project' ? '项目' : '目录' }} · {{ data.name }}</span>
            <span class="muted">{{ data.model_count }}</span>
          </span>
        </template>
      </el-tree>
      <div class="tree-foot">
        <el-button
          size="small"
          type="danger"
          plain
          :disabled="!canDelete || !selectedFolderId"
          @click="removeFolder"
        >
          删除选中
        </el-button>
      </div>
    </aside>

    <section class="list-pane">
      <div class="pane-head">
        <span class="pane-title">
          {{ selectedFolder ? `模型 · ${selectedFolder.name}` : '请选择文件夹/项目' }}
        </span>
        <el-button
          type="primary"
          size="small"
          :disabled="!canCreate || !selectedFolderId"
          @click="openCreateModel"
        >
          新建模型
        </el-button>
      </div>
      <el-table
        :data="models"
        height="100%"
        highlight-current-row
        :row-class-name="modelRowClassName"
        @row-click="selectModel"
      >
        <el-table-column prop="code" label="编号" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="model-code">{{ row.code || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="设备名称" min-width="180">
          <template #default="{ row }">
            <div class="model-name-cell">
              <TopologyDeviceIcon
                v-bind="designModelIconProps(row)"
                :size="40"
                :selected="row.id === selectedModelId"
              />
              <div class="model-name-stack">
                <span class="model-name-text">{{ row.name }}</span>
                <span v-if="row.code" class="model-code-sub">{{ row.code }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="设备类型" width="110">
          <template #default="{ row }">
            {{ categoryLabel(row.category) }}
          </template>
        </el-table-column>
        <el-table-column label="型号" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.vendor_sku || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="danger"
              :disabled="!canDelete"
              @click.stop="removeModel(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="editor-pane">
      <template v-if="selectedModel">
        <div class="pane-head">
          <span class="pane-title model-editor-title">
            <TopologyDeviceIcon
              v-bind="designModelIconProps(selectedModel)"
              :size="36"
              selected
            />
            <span>模型属性 · {{ selectedModel.name }}</span>
          </span>
          <el-button type="primary" :loading="saving" :disabled="!canEdit" @click="saveSelectedModel">
            保存
          </el-button>
        </div>

        <div class="editor-scroll">
          <template v-if="isSwitchModel || isServerModel || isSecurityModel">
            <div class="sec-title">基本信息</div>
            <el-form label-position="left" label-width="7em" size="small" class="attr-grid-form">
              <el-form-item label="编号">
                <el-input v-model="selectedModel.code" :disabled="!canEdit" />
              </el-form-item>
              <el-form-item label="型号">
                <el-input v-model="selectedModel.vendor_sku" disabled placeholder="自动关联合同型号" />
              </el-form-item>
              <el-form-item label="厂商">
                <el-input
                  v-model="selectedModel.manufacturer_name"
                  disabled
                  placeholder="自动关联合同厂商"
                />
              </el-form-item>
              <el-form-item v-if="isSwitchModel" label="交换机样式">
                <el-select
                  :model-value="switchRole"
                  :disabled="!canEdit"
                  @change="(v: SwitchSubtype) => onSwitchRoleChange(v)"
                >
                  <el-option
                    v-for="opt in SWITCH_STYLE_OPTIONS"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="设备名称" class="span-2">
                <el-select
                  v-model="selectedSummaryKey"
                  filterable
                  clearable
                  placeholder="关联合同/采购汇总设备名称"
                  :disabled="!canEdit"
                  @change="onSummaryChange"
                  @focus="() => { if (!contractSummaries.length) loadContractSummaries() }"
                >
                  <el-option
                    v-for="sum in contractSummaries"
                    :key="summaryOptionKey(sum)"
                    :label="formatSummaryOptionLabel(sum)"
                    :value="summaryOptionKey(sum)"
                  />
                </el-select>
              </el-form-item>
            </el-form>
          </template>
          <template v-else>
            <div class="sec-title">基本属性</div>
            <el-form label-position="left" label-width="7em" size="small" class="attr-grid-form">
              <el-form-item label="编号">
                <el-input v-model="selectedModel.code" :disabled="!canEdit" />
              </el-form-item>
              <el-form-item label="名称">
                <el-input v-model="selectedModel.name" :disabled="!canEdit" />
              </el-form-item>
              <el-form-item label="类型">
                <el-select
                  v-model="selectedModel.category"
                  :disabled="!canEdit"
                  style="width: 100%"
                  @change="onSelectedCategoryChange"
                >
                  <el-option
                    v-for="opt in NETWORK_DEVICE_TYPE_OPTIONS"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="子样式">
                <el-select
                  v-model="selectedModel.subtype"
                  :disabled="!canEdit"
                  style="width: 100%"
                  @change="onSelectedSubtypeChange"
                >
                  <el-option
                    v-for="s in selectedSubtypeOptions"
                    :key="s.value"
                    :label="s.label"
                    :value="s.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="型号">
                <el-input v-model="selectedModel.vendor_sku" :disabled="!canEdit" />
              </el-form-item>
              <el-form-item label="厂商">
                <el-input v-model="selectedModel.manufacturer_name" :disabled="!canEdit" />
              </el-form-item>
              <el-form-item v-if="selectedModel.category !== 'software'" label="高度">
                <el-input-number
                  v-model="selectedModel.height_u"
                  :min="1"
                  :max="48"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                />
              </el-form-item>
            </el-form>
          </template>

          <template v-if="isSwitchModel">
            <div class="sec-title">硬件配置信息</div>
            <el-form label-position="left" label-width="7em" size="small" class="attr-grid-form hw-attr-form">
              <el-form-item label="风道类型">
                <el-select
                  :model-value="String(attrFieldValue('airflow_type') || 'front_to_rear')"
                  :disabled="!canEdit"
                  @change="(v: string) => setAttrField('airflow_type', v)"
                >
                  <el-option
                    v-for="opt in AIRFLOW_OPTIONS"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="整机高度">
                <div class="unit-field">
                  <el-input-number
                    :model-value="Number(attrFieldValue('chassis_height_u') ?? selectedModel.height_u ?? 1)"
                    :min="1"
                    :max="48"
                    :controls="false"
                    :disabled="!canEdit"
                    class="num-compact"
                    @change="onSwitchHeightChange"
                  />
                  <span class="unit-lab">U</span>
                </div>
              </el-form-item>
              <el-form-item label="最大供电能力">
                <div class="unit-field">
                  <el-input-number
                    :model-value="Number(attrFieldValue('max_power_watt') ?? 3000)"
                    :min="0"
                    :controls="false"
                    :disabled="!canEdit"
                    class="num-compact"
                    @change="(v: number | undefined) => setAttrField('max_power_watt', v ?? 0)"
                  />
                  <span class="unit-lab">W</span>
                </div>
              </el-form-item>
              <el-form-item label="风扇个数">
                <el-input-number
                  :model-value="Number(attrFieldValue('fan_count') ?? (isCoreAggSwitch ? 4 : 2))"
                  :min="0"
                  :max="16"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('fan_count', v ?? 0)"
                />
              </el-form-item>
              <el-form-item label="电源个数">
                <el-input-number
                  :model-value="Number(attrFieldValue('psu_count') ?? (isCoreAggSwitch ? 4 : 2))"
                  :min="0"
                  :max="16"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('psu_count', v ?? 0)"
                />
              </el-form-item>
              <el-form-item v-if="isCoreAggSwitch" label="交换网板槽位">
                <el-input-number
                  :model-value="Number(attrFieldValue('fabric_slot_count') ?? 2)"
                  :min="0"
                  :max="16"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('fabric_slot_count', v ?? 0)"
                />
              </el-form-item>
              <el-form-item v-if="attrFieldValue('airflow_type') === 'custom'" label="自定义风道" class="span-2">
                <el-input
                  :model-value="String(attrFieldValue('airflow_custom') || '')"
                  :disabled="!canEdit"
                  placeholder="请输入风道说明"
                  @update:model-value="(v: string) => setAttrField('airflow_custom', v)"
                />
              </el-form-item>
              <el-form-item label="尺寸" class="span-2">
                <div class="dim-row">
                  <el-input-number
                    :model-value="Number(attrFieldValue('chassis_dim_a') ?? 442)"
                    :min="1"
                    :controls="false"
                    :disabled="!canEdit"
                    class="num-compact"
                    @change="(v: number | undefined) => setAttrField('chassis_dim_a', v ?? 1)"
                  />
                  <span class="dim-x">×</span>
                  <el-input-number
                    :model-value="Number(attrFieldValue('chassis_dim_b') ?? 660)"
                    :min="1"
                    :controls="false"
                    :disabled="!canEdit"
                    class="num-compact"
                    @change="(v: number | undefined) => setAttrField('chassis_dim_b', v ?? 1)"
                  />
                  <span class="dim-x">×</span>
                  <el-input-number
                    :model-value="Number(attrFieldValue('chassis_dim_c') ?? 175)"
                    :min="1"
                    :controls="false"
                    :disabled="!canEdit"
                    class="num-compact"
                    @change="(v: number | undefined) => setAttrField('chassis_dim_c', v ?? 1)"
                  />
                  <span class="unit-lab">mm</span>
                </div>
              </el-form-item>
            </el-form>
          </template>

          <template v-if="isServerModel">
            <div class="sec-title">硬件配置信息（{{ normalizeServerFormFactor(selectedModel.height_u) }}U）</div>
            <el-form label-position="left" label-width="7em" size="small" class="attr-grid-form hw-attr-form">
              <div class="attr-subhead span-4">处理器 / 内存 / 扩展</div>
              <el-form-item label="处理器颗数">
                <el-input-number
                  :model-value="Number(attrFieldValue('cpu_sockets') ?? 2)"
                  :min="1"
                  :max="8"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('cpu_sockets', v ?? 1)"
                />
              </el-form-item>
              <el-form-item label="每颗核数">
                <el-input-number
                  :model-value="Number(attrFieldValue('cpu_cores_per_socket') ?? 16)"
                  :min="1"
                  :max="128"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('cpu_cores_per_socket', v ?? 1)"
                />
              </el-form-item>
              <el-form-item label="内存类型">
                <el-select
                  :model-value="normalizeMemoryType(attrFieldValue('memory_type'))"
                  :disabled="!canEdit"
                  @change="(v: string) => setAttrField('memory_type', v)"
                >
                  <el-option v-for="opt in SERVER_MEMORY_TYPE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="单条容量">
                <div class="unit-field">
                  <el-input-number
                    :model-value="Number(attrFieldValue('memory_module_gb') ?? 16)"
                    :min="1"
                    :max="1024"
                    :controls="false"
                    :disabled="!canEdit"
                    class="num-compact"
                    @change="onServerMemoryModuleChange"
                  />
                  <span class="unit-lab">GB</span>
                </div>
              </el-form-item>
              <el-form-item label="内存条数">
                <el-input-number
                  :model-value="Number(attrFieldValue('memory_modules') ?? 8)"
                  :min="1"
                  :max="64"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="onServerMemoryModulesChange"
                />
              </el-form-item>
              <el-form-item label="内存总量">
                <div class="unit-field">
                  <el-input-number
                    :model-value="Number(attrFieldValue('memory_gb') ?? 128)"
                    :min="1"
                    :controls="false"
                    :disabled="!canEdit"
                    class="num-compact"
                    @change="(v: number | undefined) => setAttrField('memory_gb', v ?? 1)"
                  />
                  <span class="unit-lab">GB</span>
                </div>
              </el-form-item>

              <el-form-item label="机箱高度">
                <el-select
                  :model-value="normalizeServerFormFactor(selectedModel.height_u)"
                  :disabled="!canEdit"
                  @change="onServerHeightChange"
                >
                  <el-option v-for="opt in SERVER_HEIGHT_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </el-form-item>
              <div class="attr-subhead span-4">存储方案</div>
              <el-form-item label="前置盘位">
                <div class="unit-field">
                  <el-input-number
                    :model-value="Number(attrFieldValue('disk_front_count') ?? 0)"
                    :min="0"
                    :max="serverDiskFrontMax"
                    :controls="false"
                    :disabled="!canEdit"
                    class="num-compact"
                    @change="onServerDiskFrontChange"
                  />
                  <span class="unit-lab">≤{{ serverDiskFrontMax }}</span>
                </div>
              </el-form-item>
              <el-form-item label="前置尺寸">
                <el-select
                  :model-value="normalizeDiskSize(attrFieldValue('disk_front_size'), '3.5')"
                  :disabled="!canEdit"
                  @change="(v: string) => setAttrField('disk_front_size', v)"
                >
                  <el-option v-for="opt in SERVER_DISK_SIZE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="盘位方向">
                <el-tag effect="plain">{{ serverFrontDriveLayoutLabel }}</el-tag>
              </el-form-item>
              <el-form-item label="前置协议">
                <el-select
                  :model-value="String(attrFieldValue('disk_front_proto') || 'sas_sata')"
                  :disabled="!canEdit"
                  @change="(v: string) => setAttrField('disk_front_proto', v)"
                >
                  <el-option v-for="opt in SERVER_DISK_PROTO_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="后置盘位">
                <div class="unit-field">
                  <el-input-number
                    :model-value="Number(attrFieldValue('disk_rear_count') ?? 0)"
                    :min="0"
                    :max="serverDiskRearMax"
                    :controls="false"
                    :disabled="!canEdit"
                    class="num-compact"
                    @change="onServerDiskRearChange"
                  />
                  <span class="unit-lab">≤{{ serverDiskRearMax }}</span>
                </div>
              </el-form-item>
              <el-form-item label="后置尺寸">
                <el-select
                  :model-value="normalizeDiskSize(attrFieldValue('disk_rear_size'), '2.5')"
                  :disabled="!canEdit"
                  @change="(v: string) => setAttrField('disk_rear_size', v)"
                >
                  <el-option v-for="opt in SERVER_DISK_SIZE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="后置协议">
                <el-select
                  :model-value="String(attrFieldValue('disk_rear_proto') || 'sas_sata')"
                  :disabled="!canEdit"
                  @change="(v: string) => setAttrField('disk_rear_proto', v)"
                >
                  <el-option v-for="opt in SERVER_DISK_PROTO_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="内置SSD">
                <el-input-number
                  :model-value="Number(attrFieldValue('ssd_internal_count') ?? 0)"
                  :min="0"
                  :max="16"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('ssd_internal_count', v ?? 0)"
                />
              </el-form-item>
              <el-form-item label="SSD接口">
                <el-select
                  :model-value="String(attrFieldValue('ssd_internal_iface') || 'sata')"
                  :disabled="!canEdit"
                  @change="(v: string) => setAttrField('ssd_internal_iface', v)"
                >
                  <el-option v-for="opt in SERVER_SSD_IFACE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="最大SSD">
                <el-input-number
                  :model-value="Number(attrFieldValue('ssd_max_count') ?? 2)"
                  :min="0"
                  :max="64"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('ssd_max_count', v ?? 0)"
                />
              </el-form-item>
              <el-form-item label="SSD类型">
                <el-select
                  :model-value="String(attrFieldValue('ssd_max_type') || 'sata')"
                  :disabled="!canEdit"
                  @change="(v: string) => setAttrField('ssd_max_type', v)"
                >
                  <el-option v-for="opt in SERVER_SSD_TYPE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </el-form-item>
              <div class="attr-subhead span-4">电源 / 散热 / 系统</div>
              <el-form-item label="电源功率">
                <div class="unit-field">
                  <el-input-number
                    :model-value="Number(attrFieldValue('psu_watt') ?? 800)"
                    :min="100"
                    :max="5000"
                    :controls="false"
                    :disabled="!canEdit"
                    class="num-compact"
                    @change="(v: number | undefined) => setAttrField('psu_watt', v ?? 800)"
                  />
                  <span class="unit-lab">W</span>
                </div>
              </el-form-item>
              <el-form-item label="电源冗余">
                <el-select
                  :model-value="normalizePsuRedundancy(attrFieldValue('psu_redundancy'))"
                  :disabled="!canEdit"
                  @change="(v: string) => setAttrField('psu_redundancy', v)"
                >
                  <el-option v-for="opt in SERVER_PSU_REDUNDANCY_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="电源数量">
                <el-input-number
                  :model-value="Number(attrFieldValue('psu_count') ?? 2)"
                  :min="0"
                  :max="8"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('psu_count', v ?? 2)"
                />
              </el-form-item>
              <el-form-item label="风扇模组">
                <el-input-number
                  :model-value="Number(attrFieldValue('fan_count') ?? 4)"
                  :min="0"
                  :max="16"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('fan_count', v ?? 0)"
                />
              </el-form-item>
              <el-form-item label="操作系统" class="span-2">
                <el-checkbox-group
                  :model-value="normalizeOsSupport(attrFieldValue('os_support'))"
                  :disabled="!canEdit"
                  @change="onServerOsSupportChange"
                >
                  <el-checkbox v-for="opt in SERVER_OS_OPTIONS" :key="opt.value" :label="opt.value">
                    {{ opt.label }}
                  </el-checkbox>
                </el-checkbox-group>
              </el-form-item>
              <el-form-item v-if="normalizeOsSupport(attrFieldValue('os_support')).includes('other')" label="自定义系统" class="span-2">
                <el-input
                  :model-value="String(attrFieldValue('os_support_custom') || '')"
                  :disabled="!canEdit"
                  placeholder="其他操作系统名称"
                  @update:model-value="(v: string) => setAttrField('os_support_custom', v)"
                />
              </el-form-item>
            </el-form>

            <div class="sec-title">接口属性</div>
            <el-form label-position="left" label-width="7em" size="small" class="attr-grid-form hw-attr-form">
              <div class="attr-subhead span-4">管理功能</div>
              <el-form-item label="BMC管理口">
                <el-input-number
                  :model-value="Number(attrFieldValue('bmc_ports') ?? 1)"
                  :min="0"
                  :max="4"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('bmc_ports', v ?? 0)"
                />
              </el-form-item>
              <el-form-item label="IPMI接口">
                <el-input-number
                  :model-value="Number(attrFieldValue('ipmi_iface_count') ?? 0)"
                  :min="0"
                  :max="4"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('ipmi_iface_count', v ?? 0)"
                />
              </el-form-item>
              <el-form-item label="VGA接口">
                <el-input-number
                  :model-value="Number(attrFieldValue('vga_count') ?? 1)"
                  :min="0"
                  :max="4"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('vga_count', v ?? 0)"
                />
              </el-form-item>
              <el-form-item label="USB个数">
                <el-input-number
                  :model-value="Number(attrFieldValue('usb_count') ?? 2)"
                  :min="0"
                  :max="8"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('usb_count', v ?? 0)"
                />
              </el-form-item>
              <div class="attr-subhead span-4">网络接口</div>
              <el-form-item label="板载LOM">
                <el-input-number
                  :model-value="Number(attrFieldValue('lom_1g_count') ?? 2)"
                  :min="0"
                  :max="8"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('lom_1g_count', v ?? 0)"
                />
              </el-form-item>
              <el-form-item label="灵活IO插槽数量">
                <div class="unit-field">
                  <el-input-number
                    :model-value="Number(attrFieldValue('flex_io_slot_count') ?? attrFieldValue('pcie_slot_max') ?? 6)"
                    :min="0"
                    :max="serverPcieSlotMax"
                    :controls="false"
                    :disabled="!canEdit"
                    class="num-compact"
                    @change="onFlexIoSlotCountChange"
                  />
                  <span class="unit-lab">个 PCIe 槽位（最多 {{ serverPcieSlotMax }} 个）</span>
                </div>
              </el-form-item>
              <el-form-item label="PCIe 插槽" class="span-4">
                <div class="pcie-slot-defs pcie-card-configs">
                  <div v-for="slot in serverPcieSlots" :key="`pcie-def-${slot.index}`" class="pcie-slot-def pcie-card-config">
                    <span class="pcie-slot-lab">PCIe {{ slot.index }}</span>
                    <el-select :model-value="slot.card_type" size="small" :disabled="!canEdit" @change="(v: ServerPcieCardType) => onPcieCardTypeChange(slot.index, v)">
                      <el-option v-for="opt in PCIE_CARD_TYPE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                    </el-select>
                    <el-select v-if="slot.card_type === 'nic_copper' || slot.card_type === 'nic_optical'" :model-value="slot.port_count" size="small" :disabled="!canEdit" @change="(v: number) => onPciePortCountChange(slot.index, v)">
                      <el-option v-for="opt in PCIE_PORT_COUNT_OPTIONS.filter((item) => item.value > 0)" :key="opt.value" :label="opt.label" :value="opt.value" />
                    </el-select>
                    <el-select v-if="slot.card_type === 'nic_copper' || slot.card_type === 'nic_optical'" :model-value="slot.speed" size="small" :disabled="!canEdit" @change="(v: ServerFlexSpeed) => onPcieSpeedChange(slot.index, v)">
                      <el-option v-for="opt in pcieSpeedOptions(slot)" :key="opt.value" :label="opt.label" :value="opt.value" />
                    </el-select>
                    <el-select v-if="slot.card_type === 'raid'" :model-value="slot.raid_level || 'raid1'" size="small" :disabled="!canEdit" @change="(v: string) => patchPcieSlot(slot.index, { raid_level: v })">
                      <el-option v-for="opt in DESIGN_RAID_LEVEL_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                    </el-select>
                    <el-select :model-value="slot.orientation" size="small" :disabled="!canEdit || normalizeServerFormFactor(selectedModel.height_u ?? selectedModel.attributes?.form_factor_u) === 1" @change="(v: ServerPcieSlotAttr['orientation']) => patchPcieSlot(slot.index, { orientation: v })">
                      <el-option v-for="opt in PCIE_ORIENTATION_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                    </el-select>
                    <el-button-group class="pcie-placement-buttons" aria-label="PCIe 插槽位置">
                      <el-button
                        v-for="opt in PCIE_PLACEMENT_OPTIONS"
                        :key="opt.value"
                        size="small"
                        :type="slot.placement === opt.value ? 'primary' : 'default'"
                        :plain="slot.placement !== opt.value"
                        :disabled="!canEdit"
                        :aria-pressed="slot.placement === opt.value"
                        @click="patchPcieSlot(slot.index, { placement: opt.value })"
                      >
                        {{ opt.label }}
                      </el-button>
                    </el-button-group>
                  </div>
                </div>
              </el-form-item>
            </el-form>
            <div v-if="serverPortGroups.length" class="sys-port-strip">
              <div v-for="group in serverPortGroups" :key="`${group.kind}-${group.label}`" class="sys-port-group">
                <span class="sys-port-kind">{{ group.label }}</span>
                <button
                  v-for="p in group.ports"
                  :key="p.id"
                  type="button"
                  class="sys-port-chip"
                  :class="{ selected: selectedChassisPort?.portId === p.id }"
                  :title="`${p.code} · ${p.id}`"
                  @click="onSystemPortSelect(p.id)"
                  @contextmenu="onSystemPortInspect(p.id, $event)"
                >
                  {{ p.code }}
                </button>
              </div>
            </div>

            <div class="sec-title-row">
              <span class="sec-title with-hint">
                面板演示
                <TitleHintBang title="说明" :content="SERVER_PANEL_HINT" :width="360" />
              </span>
              <el-radio-group v-model="panelDemoZoom" size="small" class="panel-zoom-toggles">
                <el-radio-button :value="0.5">0.5×</el-radio-button>
                <el-radio-button :value="1">1×</el-radio-button>
                <el-radio-button :value="2">2×</el-radio-button>
              </el-radio-group>
              <el-radio-group v-model="panelDemoSide" size="small" class="panel-side-toggles">
                <el-radio-button value="front">正面</el-radio-button>
                <el-radio-button value="rear">背面</el-radio-button>
              </el-radio-group>
              <el-button v-if="canEdit" type="primary" plain size="small" @click="openCustomPanel">自定义面板</el-button>
              <el-button v-if="canEdit" size="small" @click="serverStyleFrontInput?.click()">上传前面板</el-button>
              <el-button v-if="canEdit" size="small" @click="serverStyleRearInput?.click()">上传后面板</el-button>
              <el-radio-group
                v-if="serverStyleImageFront || serverStyleImageRear"
                v-model="serverPanelShowImage"
                size="small"
                class="panel-zoom-toggles"
              >
                <el-radio-button :value="false">仿真</el-radio-button>
                <el-radio-button :value="true">图片</el-radio-button>
              </el-radio-group>
              <input
                ref="serverStyleFrontInput"
                class="hidden-file"
                type="file"
                accept="image/*"
                @change="(e: Event) => onServerStyleImageUpload('front', e)"
              />
              <input
                ref="serverStyleRearInput"
                class="hidden-file"
                type="file"
                accept="image/*"
                @change="(e: Event) => onServerStyleImageUpload('rear', e)"
              />
            </div>
            <div class="chassis-demo-pair server-demo-pair" :style="{ zoom: panelDemoCssZoom }">
              <div v-if="panelDemoSide === 'front'" class="chassis-demo-col">
                <div class="chassis-demo-lab">
                  正面
                  <el-button
                    v-if="canEdit && serverStyleImageFront"
                    link
                    type="danger"
                    size="small"
                    @click="clearServerStyleImage('front')"
                  >
                    清除图片
                  </el-button>
                </div>
                <img
                  v-if="serverPanelShowImage && serverStyleImageFront"
                  class="style-preview"
                  :src="serverStyleImageFront"
                  alt="前面板样式"
                  :style="{ aspectRatio: SERVER_DEMO.aspect(normalizeServerFormFactor(selectedModel.height_u)) }"
                />
                <ServerFrontSchematic
                  v-else
                  :height-u="normalizeServerFormFactor(selectedModel.height_u)"
                  :disk-count="Number(attrFieldValue('disk_front_count') ?? 0)"
                  :disk-size="String(attrFieldValue('disk_front_size') || '3.5')"
                  :disk-proto="String(attrFieldValue('disk_front_proto') || 'sas_sata')"
                  :usb-ports="serverPorts.filter((p) => p.kind === 'usb')"
                  :vga-ports="serverPorts.filter((p) => p.kind === 'vga')"
                  :selected-port-id="selectedChassisPort?.portId"
                  @select-port="onSystemPortSelect"
                  @inspect-port="onSystemPortInspect"
                />
              </div>
              <div v-else class="chassis-demo-col">
                <div class="chassis-demo-lab">
                  背面
                  <el-button
                    v-if="canEdit && serverStyleImageRear"
                    link
                    type="danger"
                    size="small"
                    @click="clearServerStyleImage('rear')"
                  >
                    清除图片
                  </el-button>
                </div>
                <img
                  v-if="serverPanelShowImage && serverStyleImageRear"
                  class="style-preview"
                  :src="serverStyleImageRear"
                  alt="后面板样式"
                  :style="{ aspectRatio: SERVER_DEMO.aspect(normalizeServerFormFactor(selectedModel.height_u)) }"
                />
                <ServerRearSchematic
                  v-else
                  :height-u="normalizeServerFormFactor(selectedModel.height_u)"
                  :psu-count="Number(attrFieldValue('psu_count') ?? 2)"
                  :psu-watt="Number(attrFieldValue('psu_watt') ?? 800)"
                  :pcie-slot-defs="serverPcieSlots"
                  :disk-count="Number(attrFieldValue('disk_rear_count') ?? 0)"
                  :disk-size="String(attrFieldValue('disk_rear_size') || '2.5')"
                  :ports="serverPorts"
                  :selected-port-id="selectedChassisPort?.portId"
                  @select-port="onSystemPortSelect"
                  @inspect-port="onSystemPortInspect"
                />
              </div>
            </div>
            <div v-if="canEdit" class="chassis-hint">
              左键点击接口编辑，右键查看接口 ID 与编号；可上传自定义前后面板样式图
            </div>
          </template>

          <template v-else-if="isSecurityModel">
            <div class="sec-title-row">
              <span class="sec-title">{{ securityProfile.label }} · {{ securityProfile.hardwareTitle }}</span>
              <el-tag size="small" effect="dark" :color="securityProfile.accent">{{ securityProfile.shortLabel }}</el-tag>
            </div>
            <el-form label-position="left" label-width="7em" size="small" class="attr-grid-form hw-attr-form">
              <el-form-item label="设备高度">
                <el-select :model-value="normalizeSecurityFormFactor(selectedModel.height_u)" :disabled="!canEdit" @change="onSecurityHeightChange">
                  <el-option v-for="opt in SECURITY_HEIGHT_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="部署方式"><el-input :model-value="String(attrFieldValue('deployment_mode') || securityProfile.deploymentMode)" :disabled="!canEdit" @update:model-value="(v: string) => setAttrField('deployment_mode', v)" /></el-form-item>
              <el-form-item :label="securityProfile.processorLabel"><el-input-number :model-value="Number(attrFieldValue('cpu_cores') ?? securityProfile.cpuCores)" :min="1" :max="128" :controls="false" :disabled="!canEdit" @change="(v: number | undefined) => setAttrField('cpu_cores', v ?? securityProfile.cpuCores)" /></el-form-item>
              <el-form-item label="内存 GB"><el-input-number :model-value="Number(attrFieldValue('memory_gb') ?? securityProfile.memoryGb)" :min="1" :max="2048" :controls="false" :disabled="!canEdit" @change="(v: number | undefined) => setAttrField('memory_gb', v ?? securityProfile.memoryGb)" /></el-form-item>
              <el-form-item label="磁盘数量"><el-input-number :model-value="Number(attrFieldValue('disk_count') ?? securityProfile.diskCount)" :min="0" :max="24" :controls="false" :disabled="!canEdit" @change="(v: number | undefined) => setAttrField('disk_count', v ?? securityProfile.diskCount)" /></el-form-item>
              <el-form-item :label="securityProfile.storageLabel"><el-input-number :model-value="Number(attrFieldValue('disk_gb') ?? securityProfile.diskGb)" :min="0" :max="100000" :controls="false" :disabled="!canEdit" @change="(v: number | undefined) => setAttrField('disk_gb', v ?? securityProfile.diskGb)" /></el-form-item>
              <el-form-item :label="securityProfile.throughputLabel"><el-input-number :model-value="Number(attrFieldValue('throughput_gbps') ?? securityProfile.throughputGbps)" :min="0" :max="6400" :controls="false" :disabled="!canEdit" @change="(v: number | undefined) => setAttrField('throughput_gbps', v ?? securityProfile.throughputGbps)" /></el-form-item>
              <el-form-item label="日志留存天数"><el-input-number :model-value="Number(attrFieldValue('retention_days') ?? securityProfile.retentionDays)" :min="1" :max="3650" :controls="false" :disabled="!canEdit" @change="(v: number | undefined) => setAttrField('retention_days', v ?? securityProfile.retentionDays)" /></el-form-item>
              <el-form-item :label="securityProfile.metricLabel"><el-input-number :model-value="Number(attrFieldValue(securityProfile.metricKey) ?? securityProfile.metricDefault)" :min="0" :max="100000000" :controls="false" :disabled="!canEdit" @change="(v: number | undefined) => setAttrField(securityProfile.metricKey, v ?? securityProfile.metricDefault)" /></el-form-item>
              <el-form-item label="电源数量"><el-input-number :model-value="Number(attrFieldValue('psu_count') ?? 2)" :min="1" :max="8" :controls="false" :disabled="!canEdit" @change="(v: number | undefined) => setAttrField('psu_count', v ?? 2)" /></el-form-item>
              <el-form-item label="风扇模组"><el-input-number :model-value="Number(attrFieldValue('fan_count') ?? 2)" :min="0" :max="16" :controls="false" :disabled="!canEdit" @change="(v: number | undefined) => setAttrField('fan_count', v ?? 2)" /></el-form-item>
            </el-form>

            <div class="sec-title-row">
              <span class="sec-title">面板演示</span>
              <el-radio-group v-model="panelDemoZoom" size="small" class="panel-zoom-toggles">
                <el-radio-button :value="0.5">0.5×</el-radio-button>
                <el-radio-button :value="1">1×</el-radio-button>
                <el-radio-button :value="2">2×</el-radio-button>
              </el-radio-group>
              <el-radio-group v-model="panelDemoSide" size="small" class="panel-side-toggles">
                <el-radio-button value="front">正面</el-radio-button>
                <el-radio-button value="rear">背面</el-radio-button>
              </el-radio-group>
              <el-button size="small" @click="securityInterfaceEditorVisible = !securityInterfaceEditorVisible">{{ securityInterfaceEditorVisible ? '收起接口参数' : '接口参数' }}</el-button>
              <el-button v-if="canEdit" type="primary" plain size="small" @click="openCustomPanel">自定义面板</el-button>
            </div>
            <SecurityDeviceSchematic
              v-if="panelDemoSide === 'front'"
              :style="{ zoom: panelDemoCssZoom }"
              :subtype="securityDeviceType"
              :height-u="selectedModel.height_u"
              :slots="securityIfaceSlots"
              :cpu-cores="Number(attrFieldValue('cpu_cores') ?? securityProfile.cpuCores)"
              :memory-gb="Number(attrFieldValue('memory_gb') ?? securityProfile.memoryGb)"
              :disk-count="Number(attrFieldValue('disk_count') ?? securityProfile.diskCount)"
              :disk-gb="Number(attrFieldValue('disk_gb') ?? securityProfile.diskGb)"
              :throughput-gbps="Number(attrFieldValue('throughput_gbps') ?? securityProfile.throughputGbps)"
              :psu-count="Number(attrFieldValue('psu_count') ?? 2)"
              @edit-slot="securityInterfaceEditorVisible = true"
            />
            <SecurityDeviceRearSchematic
              v-else
              :style="{ zoom: panelDemoCssZoom }"
              :subtype="securityDeviceType"
              :height-u="selectedModel.height_u"
              :slots="securityIfaceSlots"
              :fan-count="Number(attrFieldValue('fan_count') ?? securityProfile.fanCount)"
              :psu-count="Number(attrFieldValue('psu_count') ?? 2)"
              @edit-slot="securityInterfaceEditorVisible = true"
            />
            <div class="chassis-hint">通过正面/背面按钮切换模板；不同安全设备采用独立配色、背板散热、电源与接口分区，接口 ID 唯一可定位。</div>

            <div v-if="securityInterfaceEditorVisible" class="security-interface-editor">
              <div class="security-editor-head">
                <div class="security-editor-title">
                  <strong>接口参数</strong>
                  <span>支持多个接口 Slot，修改后自动同步唯一端口编号与自定义面板组件</span>
                </div>
                <el-button v-if="canEdit" type="primary" plain size="small" :disabled="securityIfaceSlots.length >= MAX_SECURITY_IFACE_SLOTS" @click="addSecurityIfaceSlot">
                  添加 Slot（{{ securityIfaceSlots.length }}/{{ MAX_SECURITY_IFACE_SLOTS }}）
                </el-button>
              </div>
              <div v-for="(slot, idx) in securityIfaceSlots" :key="`sec-editor-${slot.index}`" class="security-editor-row">
                <span class="slot-idx-wrap with-hint"><b>Slot {{ slot.index }}</b><TitleHintBang title="接口编号" :content="securitySlotRangeHint(slot)" :width="280" /></span>
                <label>Control<el-input-number :model-value="slot.control_count" :min="0" :max="8" :controls="false" size="small" :disabled="!canEdit" @change="(v: number | undefined) => patchSecurityIfaceSlot(idx, { control_count: v ?? 0 })" /></label>
                <label>HA<el-input-number :model-value="slot.ha_count" :min="0" :max="8" :controls="false" size="small" :disabled="!canEdit" @change="(v: number | undefined) => patchSecurityIfaceSlot(idx, { ha_count: v ?? 0 })" /></label>
                <label>MGMT<el-input-number :model-value="slot.mgmt_count" :min="0" :max="8" :controls="false" size="small" :disabled="!canEdit" @change="(v: number | undefined) => patchSecurityIfaceSlot(idx, { mgmt_count: v ?? 0 })" /></label>
                <label>USB<el-input-number :model-value="slot.usb_count" :min="0" :max="8" :controls="false" size="small" :disabled="!canEdit" @change="(v: number | undefined) => patchSecurityIfaceSlot(idx, { usb_count: v ?? 0 })" /></label>
                <label>10G 光口<el-input-number :model-value="slot.ports_10g" :min="0" :max="48" :controls="false" size="small" :disabled="!canEdit" @change="(v: number | undefined) => patchSecurityIfaceSlot(idx, { ports_10g: v ?? 0 })" /></label>
                <label>1G 电口<el-input-number :model-value="slot.ports_1g" :min="0" :max="48" :controls="false" size="small" :disabled="!canEdit" @change="(v: number | undefined) => patchSecurityIfaceSlot(idx, { ports_1g: v ?? 0 })" /></label>
                <el-button v-if="canEdit" link type="danger" size="small" class="security-slot-delete" @click="removeSecurityIfaceSlot(idx)">删除 Slot</el-button>
              </div>
            </div>
          </template>
          <template v-else-if="isSwitchModel">
            <div class="sec-title">接口属性</div>
            <el-form
              v-if="isCoreAggSwitch"
              label-position="left"
              label-width="7em"
              size="small"
              class="attr-grid-form"
            >
              <div class="attr-subhead span-4">管理与带外口</div>
              <el-form-item label="Console口">
                <el-input-number
                  :model-value="Number(attrFieldValue('console_ports') ?? 1)"
                  :min="0"
                  :max="8"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('console_ports', v ?? 0)"
                />
              </el-form-item>
              <el-form-item label="ETH管理口">
                <el-input-number
                  :model-value="Number(attrFieldValue('eth_mgmt_ports') ?? 1)"
                  :min="0"
                  :max="8"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('eth_mgmt_ports', v ?? 0)"
                />
              </el-form-item>
              <el-form-item label="USB接口">
                <el-input-number
                  :model-value="Number(attrFieldValue('usb_ports') ?? 1)"
                  :min="0"
                  :max="8"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('usb_ports', v ?? 0)"
                />
              </el-form-item>
              <div class="attr-subhead span-4">高可用与扩展</div>
              <el-form-item label="堆叠/集群接口">
                <el-input-number
                  :model-value="Number(attrFieldValue('stack_cluster_ports') ?? 2)"
                  :min="0"
                  :max="16"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('stack_cluster_ports', v ?? 0)"
                />
              </el-form-item>
              <el-form-item label="模块化扩展插槽">
                <el-input-number
                  :model-value="Number(attrFieldValue('modular_expansion_slots') ?? 6)"
                  :min="1"
                  :max="expansionSlotMax"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="onModularExpansionChange"
                />
                <span class="slot-lab muted">≤ {{ expansionSlotMax }}U</span>
              </el-form-item>
              <el-form-item label="业务接口板数">
                <el-input-number
                  :model-value="Number(attrFieldValue('service_board_count') ?? coreIfaceBoards.length)"
                  :min="0"
                  :max="Number(attrFieldValue('modular_expansion_slots') ?? 6)"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="onServiceBoardCountChange"
                />
              </el-form-item>
              <div class="attr-subhead span-4 iface-board-head">
                <span>接口板</span>
                <el-button
                  v-if="canEdit"
                  type="primary"
                  plain
                  size="small"
                  :disabled="coreIfaceBoards.length >= Number(attrFieldValue('modular_expansion_slots') ?? 6)"
                  @click="onAddCoreIfaceBoard"
                >
                  添加接口板
                </el-button>
              </div>
              <div class="span-4 iface-board-row">
                <button
                  type="button"
                  class="iface-nav"
                  :disabled="!ifaceBoardCanPrev"
                  @click="scrollIfaceBoards(-1)"
                >
                  &lt;
                </button>
                <div
                  ref="ifaceBoardViewport"
                  class="iface-board-viewport"
                  @scroll="updateIfaceBoardNav"
                >
                  <div
                    v-for="board in coreIfaceBoards"
                    :key="`board-${board.slot_index}`"
                    class="iface-board-card"
                  >
                    <div class="iface-card-field">
                      <span class="iface-card-lab">槽位</span>
                      <el-select
                        :model-value="board.slot_index"
                        size="small"
                        :disabled="!canEdit"
                        @change="(v: number) => onCoreBoardSlotChange(board.slot_index, v)"
                      >
                        <el-option
                          v-for="s in coreBoardSlotOptions(board.slot_index)"
                          :key="s"
                          :label="`Slot ${s}`"
                          :value="s"
                        />
                      </el-select>
                    </div>
                    <div class="iface-card-field">
                      <span class="iface-card-lab">类型</span>
                      <el-select
                        :model-value="board.kind"
                        size="small"
                        :disabled="!canEdit"
                        @change="(v: string) => onCoreBoardKindChange(board.slot_index, v as SwitchIfaceBoardKind)"
                      >
                        <el-option
                          v-for="opt in SWITCH_IFACE_BOARD_OPTIONS"
                          :key="opt.value"
                          :label="opt.label"
                          :value="opt.value"
                        />
                      </el-select>
                    </div>
                    <div class="iface-card-foot">
                      <span class="iface-card-lab">口数</span>
                      <el-select
                        :model-value="boardPortPreset(board)"
                        size="small"
                        :disabled="!canEdit"
                        class="iface-port-sel"
                        @change="(v: string) => onCoreBoardPortPreset(board.slot_index, v)"
                      >
                        <el-option
                          v-for="n in SWITCH_IFACE_BOARD_PORT_PRESETS"
                          :key="n"
                          :label="String(n)"
                          :value="String(n)"
                        />
                        <el-option label="其他" value="other" />
                      </el-select>
                      <el-input-number
                        v-if="boardPortPreset(board) === 'other'"
                        :model-value="board.port_count"
                        :min="1"
                        :max="128"
                        :controls="false"
                        size="small"
                        class="iface-port-custom"
                        :disabled="!canEdit"
                        @change="(v: number | undefined) => onCoreBoardPortCustom(board.slot_index, v)"
                      />
                      <el-button
                        v-if="canEdit"
                        link
                        type="danger"
                        size="small"
                        class="iface-del"
                        @click="onRemoveCoreIfaceBoard(board.slot_index)"
                      >
                        删除
                      </el-button>
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  class="iface-nav"
                  :disabled="!ifaceBoardCanNext"
                  @click="scrollIfaceBoards(1)"
                >
                  &gt;
                </button>
              </div>
            </el-form>
            <el-form
              v-else
              label-position="left"
              label-width="7em"
              size="small"
              class="attr-grid-form"
            >
              <el-form-item v-if="switchRole === 'gigabit'" label="BMC管理交换机" class="span-2">
                <el-switch
                  :model-value="!!attrFieldValue('is_bmc_switch')"
                  :disabled="!canEdit"
                  @change="(v: boolean | string | number) => setAttrField('is_bmc_switch', !!v)"
                />
                <span class="field-hint">勾选后按 BMC_SWITCH 参与带外管理布线（场景 B1）</span>
              </el-form-item>
              <div class="attr-subhead span-4">业务接口</div>
              <el-form-item v-if="switchRole === 'gigabit'" label="接口类型">
                <el-select
                  :model-value="readGigabitDownlinkMedia(selectedModel.attributes)"
                  :disabled="!canEdit"
                  @change="(v: string) => onGigabitDownlinkMedia(v as GigabitDownlinkMedia)"
                >
                  <el-option
                    v-for="opt in GIGABIT_DOWNLINK_MEDIA_OPTIONS"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item v-else label="接口类型">
                <span class="field-static">万兆以太网光接口</span>
              </el-form-item>
              <el-form-item label="接口数量">
                <div class="dim-row">
                  <el-select
                    :model-value="accessDownlinkPreset"
                    :disabled="!canEdit"
                    style="width: 110px"
                    @change="onAccessDownlinkPreset"
                  >
                    <el-option
                      v-for="n in ACCESS_DOWNLINK_COUNT_PRESETS"
                      :key="n"
                      :label="String(n)"
                      :value="String(n)"
                    />
                    <el-option label="其他" value="other" />
                  </el-select>
                  <el-input-number
                    v-if="accessDownlinkPreset === 'other'"
                    :model-value="Number(attrFieldValue('downlink_count') ?? 48)"
                    :min="1"
                    :max="128"
                    :controls="false"
                    :disabled="!canEdit"
                    class="num-compact"
                    @change="(v: number | undefined) => setAttrField('downlink_count', v ?? 48)"
                  />
                </div>
              </el-form-item>
              <div class="attr-subhead span-4">上联接口</div>
              <el-form-item v-if="switchRole === 'ten_gigabit'" label="上联类型" class="span-2">
                <el-radio-group
                  :model-value="readTenGigUplinkKind(selectedModel.attributes)"
                  :disabled="!canEdit"
                  @change="(v: string | number | boolean | undefined) => onTenGigUplinkKind(v as TenGigUplinkKind)"
                >
                  <el-radio v-for="opt in TENGIG_UPLINK_KIND_OPTIONS" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item v-else label="上联类型" class="span-2">
                <span class="field-static">10G 光接口</span>
              </el-form-item>
              <el-form-item v-if="switchRole === 'ten_gigabit'" label="上联数量">
                <el-radio-group
                  :model-value="Number(attrFieldValue('uplink_count') ?? 6)"
                  :disabled="!canEdit"
                  @change="(v: string | number | boolean | undefined) => onAccessUplinkPreset(String(v))"
                >
                  <el-radio v-for="n in ACCESS_TENGIG_UPLINK_COUNT_PRESETS" :key="n" :value="n">
                    {{ n }}
                  </el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item v-else label="上联数量">
                <el-input-number
                  :model-value="Number(attrFieldValue('uplink_count') ?? 8)"
                  :min="0"
                  :max="8"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('uplink_count', v ?? 8)"
                />
              </el-form-item>
              <el-form-item v-if="switchRole === 'ten_gigabit'" label="上联位置" class="span-2">
                <el-radio-group
                  :model-value="accessUplinkPosition"
                  :disabled="!canEdit"
                  @change="(v: string | number | boolean | undefined) => setAttrField('uplink_position', v)"
                >
                  <el-radio v-for="(lab, key) in UPLINK_POSITION_LABELS" :key="key" :value="key">
                    {{ lab }}
                  </el-radio>
                </el-radio-group>
              </el-form-item>
              <div class="attr-subhead span-4">管理与堆叠</div>
              <el-form-item label="mgmt接口">
                <el-input-number
                  :model-value="Number(attrFieldValue('mgmt_ports') ?? 1)"
                  :min="0"
                  :max="8"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('mgmt_ports', v ?? 0)"
                />
              </el-form-item>
              <el-form-item label="堆叠/集群接口">
                <el-input-number
                  :model-value="Number(attrFieldValue('stack_cluster_ports') ?? 0)"
                  :min="0"
                  :max="16"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('stack_cluster_ports', v ?? 0)"
                />
              </el-form-item>
            </el-form>

            <template v-if="isCoreAggSwitch">
              <div class="sec-title-row">
                <span class="sec-title with-hint">
                  面板演示
                  <TitleHintBang title="说明" :content="switchSlotConfigHint" :width="360" />
                </span>
                <el-radio-group v-model="panelDemoZoom" size="small" class="panel-zoom-toggles">
                  <el-radio-button :value="0.5">0.5×</el-radio-button>
                  <el-radio-button :value="1">1×</el-radio-button>
                  <el-radio-button :value="2">2×</el-radio-button>
                </el-radio-group>
              <el-radio-group v-model="panelDemoSide" size="small" class="panel-side-toggles">
                <el-radio-button value="front">正面</el-radio-button>
                <el-radio-button value="rear">背面</el-radio-button>
              </el-radio-group>
                <el-button v-if="canEdit" type="primary" plain size="small" @click="openCustomPanel">
                  自定义面板
                </el-button>
              </div>
              <div class="chassis-demo-pair" :style="{ zoom: panelDemoCssZoom }">
                <div v-if="panelDemoSide === 'front'" class="chassis-demo-col">
                  <div class="chassis-demo-lab">正面</div>
                  <SwitchChassisSchematic
                    :height-u="chassisHeightU"
                    :slots="switchSlots"
                    :blank-rows="blankPanelRows"
                    :editable="canEdit"
                    :selected-port="selectedChassisPort"
                    @move-blank="onMoveBlankPanel"
                    @move-slot="onMoveSwitchSlot"
                    @nudge-blank="onNudgeBlankPanel"
                    @select-port="onChassisPortSelect"
                    @inspect-port="onChassisPortInspect"
                  />
                  <div v-if="switchSystemPortGroups.length" class="sys-port-strip">
                    <div
                      v-for="group in switchSystemPortGroups"
                      :key="group.kind"
                      class="sys-port-group"
                    >
                      <span class="sys-port-kind">{{ group.label }}</span>
                      <button
                        v-for="p in group.ports"
                        :key="p.id"
                        type="button"
                        class="sys-port-chip"
                        :class="{ selected: selectedChassisPort?.portId === p.id }"
                        :title="`${p.code} · ${p.id}`"
                        @click="onSystemPortSelect(p.id)"
                        @contextmenu="onSystemPortInspect(p.id, $event)"
                      >
                        {{ p.code }}
                      </button>
                    </div>
                  </div>
                  <div v-if="canEdit" class="chassis-hint">
                    拖动接口板可交换或修改槽位；左键点击接口编辑，右键查看接口信息（含管理口与堆叠/集群）
                    <template v-if="blankPanelRows.length">；机框空白面板可拖拽或用 ↑↓ 调整位置</template>
                  </div>
                </div>
                <div v-else class="chassis-demo-col">
                  <div class="chassis-demo-lab">背面</div>
                  <SwitchChassisRearSchematic
                    :height-u="chassisHeightU"
                    :fan-count="Number(attrFieldValue('fan_count') ?? 4)"
                    :psu-count="Number(attrFieldValue('psu_count') ?? 4)"
                  />
                </div>
              </div>
            </template>
            <template v-else>
              <div class="sec-title-row">
                <span class="sec-title with-hint">
                  面板演示
                  <TitleHintBang title="说明" :content="switchSlotConfigHint" :width="360" />
                </span>
                <el-radio-group v-model="panelDemoZoom" size="small" class="panel-zoom-toggles">
                  <el-radio-button :value="0.5">0.5×</el-radio-button>
                  <el-radio-button :value="1">1×</el-radio-button>
                  <el-radio-button :value="2">2×</el-radio-button>
                </el-radio-group>
              <el-radio-group v-model="panelDemoSide" size="small" class="panel-side-toggles">
                <el-radio-button value="front">正面</el-radio-button>
                <el-radio-button value="rear">背面</el-radio-button>
              </el-radio-group>
                <el-button v-if="canEdit" type="primary" plain size="small" @click="openCustomPanel">
                  自定义面板
                </el-button>
              </div>
              <div class="chassis-demo-pair access-demo-pair" :style="{ zoom: panelDemoCssZoom }">
                <div v-if="panelDemoSide === 'front'" class="chassis-demo-col">
                  <div class="chassis-demo-lab">正面</div>
                  <AccessSwitchSchematic
                    :downlink="accessDownlinkSlot"
                    :uplink="accessUplinkSlot"
                    :uplink-position="accessUplinkPosition"
                    :selected-port="selectedChassisPort"
                    @select-port="onChassisPortSelect"
                    @inspect-port="onChassisPortInspect"
                  />
                </div>
                <div v-else class="chassis-demo-col">
                  <div class="chassis-demo-lab">背面</div>
                  <AccessSwitchRearSchematic
                    :fan-count="Number(attrFieldValue('fan_count') ?? 2)"
                    :psu-count="Number(attrFieldValue('psu_count') ?? 2)"
                    :mgmt-ports="accessMgmtPorts"
                    :selected-port-id="selectedChassisPort?.portId"
                    @select-port="onSystemPortSelect"
                    @inspect-port="onSystemPortInspect"
                  />
                </div>
              </div>
              <div v-if="accessOtherSystemGroups.length" class="sys-port-strip access-sys-ports">
                <div
                  v-for="group in accessOtherSystemGroups"
                  :key="group.kind"
                  class="sys-port-group"
                >
                  <span class="sys-port-kind">{{ group.label }}</span>
                  <button
                    v-for="p in group.ports"
                    :key="p.id"
                    type="button"
                    class="sys-port-chip"
                    :class="{ selected: selectedChassisPort?.portId === p.id }"
                    :title="`${p.code} · ${p.id}`"
                    @click="onSystemPortSelect(p.id)"
                    @contextmenu="onSystemPortInspect(p.id, $event)"
                  >
                    {{ p.code }}
                  </button>
                </div>
              </div>
              <div v-if="canEdit" class="chassis-hint">
                左键点击接口编辑，右键查看接口信息；mgmt 接口在背面右侧
              </div>
            </template>
          </template>

          <template v-else-if="selectedModel.category !== 'software'">
            <div class="sec-title">规格属性</div>
            <el-form label-position="left" label-width="7em" size="small" class="attr-grid-form">
              <template v-for="field in schemaFields" :key="field.key">
                <el-form-item
                  v-if="field.type === 'list'"
                  :label="field.label"
                  :class="`span-${attrFieldSpan(field)}`"
                >
                  <el-input
                    :model-value="listFieldText(field.key)"
                    :disabled="!canEdit"
                    placeholder="逗号分隔"
                    @update:model-value="(v: string) => setListField(field.key, v)"
                  />
                </el-form-item>
                <el-form-item v-else-if="field.type === 'bool'" :label="field.label" class="span-1">
                  <el-switch
                    :model-value="!!attrFieldValue(field.key)"
                    :disabled="!canEdit"
                    @change="(v: boolean) => setAttrField(field.key, v)"
                  />
                </el-form-item>
                <el-form-item
                  v-else-if="field.type === 'select'"
                  :label="field.label"
                  :class="`span-${attrFieldSpan(field)}`"
                >
                  <el-select
                    :model-value="attrFieldValue(field.key)"
                    :disabled="!canEdit"
                    style="width: 100%"
                    @change="(v: string) => setAttrField(field.key, v)"
                  >
                    <el-option
                      v-for="opt in field.options || []"
                      :key="opt.value"
                      :label="opt.label"
                      :value="opt.value"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item
                  v-else-if="field.type === 'int' || field.type === 'float'"
                  :label="field.label"
                  :class="`span-${attrFieldSpan(field)}`"
                >
                  <el-input-number
                    :model-value="Number(attrFieldValue(field.key) ?? 0)"
                    :min="field.min ?? undefined"
                    :max="field.max ?? undefined"
                    :step="field.type === 'float' ? 0.1 : 1"
                    :controls="false"
                    :disabled="!canEdit"
                    class="num-compact"
                    @change="(v: number | undefined) => setAttrField(field.key, v ?? 0)"
                  />
                </el-form-item>
                <el-form-item v-else :label="field.label" :class="`span-${attrFieldSpan(field)}`">
                  <el-input
                    :model-value="String(attrFieldValue(field.key) ?? '')"
                    :disabled="!canEdit"
                    @update:model-value="(v: string) => setAttrField(field.key, v)"
                  />
                </el-form-item>
              </template>
            </el-form>
          </template>

          <template v-if="usesGridPanel && !isSwitchModel && !isServerModel && !isSecurityModel">
            <div class="sec-title-row">
              <span class="sec-title with-hint">
                面板样式
                <TitleHintBang title="操作说明" :content="panelStyleHint" :width="360" />
              </span>
              <el-button v-if="canEdit" link type="primary" size="small" @click="resetPanelAutoPlace">
                在当前尺寸内自动定位
              </el-button>
            </div>
            <ModelPanelSchematic
              v-model="panelLayout"
              :palette="panelPalette"
              :slots="serverSlots"
              :editable="canEdit"
              @edit-slot="openPanelSlotEditor"
            />
          </template>
        </div>
      </template>
      <el-empty v-else description="选择左侧模型进行编辑" />
    </section>

    <Teleport to="body">
      <div v-if="chassisPortInfo" class="port-info-mask" @mousedown="closeChassisPortInfo" />
      <div
        v-if="chassisPortInfo"
        class="port-info-pop"
        :style="{ left: `${chassisPortInfo.x}px`, top: `${chassisPortInfo.y}px` }"
        @mousedown.stop
        @contextmenu.prevent
      >
        <div class="port-info-title">接口信息</div>
        <dl class="port-info-dl">
          <div><dt>所属</dt><dd>{{ chassisPortInfo.boardLabel }}</dd></div>
          <div><dt>接口ID</dt><dd>{{ chassisPortInfo.spec.id }}</dd></div>
          <div><dt>编号</dt><dd>{{ chassisPortInfo.spec.code }}</dd></div>
          <div><dt>接口序号</dt><dd>{{ chassisPortInfo.ordinal }}（口 {{ chassisPortInfo.portNo }}）</dd></div>
          <div>
            <dt>接口类型</dt>
            <dd>{{ switchPortFieldLabel('iface_type', chassisPortInfo.spec.iface_type) }}</dd>
          </div>
          <div><dt>速率</dt><dd>{{ switchPortFieldLabel('speed', chassisPortInfo.spec.speed) }}</dd></div>
          <div><dt>模块类型</dt><dd>{{ switchPortFieldLabel('module', chassisPortInfo.spec.module) }}</dd></div>
          <div>
            <dt>光纤接口</dt>
            <dd>{{ switchPortFieldLabel('connector', chassisPortInfo.spec.connector) }}</dd>
          </div>
          <div>
            <dt>单/多模</dt>
            <dd>{{ switchPortFieldLabel('fiber_mode', chassisPortInfo.spec.fiber_mode) }}</dd>
          </div>
        </dl>
        <el-button
          v-if="canEdit"
          type="primary"
          link
          size="small"
          @click="onChassisPortEditFromInfo"
        >
          编辑此接口
        </el-button>
      </div>
    </Teleport>

    <el-dialog v-model="chassisPortEditVisible" title="编辑接口" width="460px" append-to-body destroy-on-close>
      <el-form label-width="92px" size="small">
        <el-form-item label="所属">
          <span class="field-static">{{ chassisPortDraftMeta.boardLabel }}</span>
        </el-form-item>
        <el-form-item label="接口ID">
          <span class="field-static">{{ chassisPortDraft.id }}</span>
        </el-form-item>
        <el-form-item label="编号">
          <span class="field-static">{{ chassisPortDraft.code }}</span>
        </el-form-item>
        <el-form-item label="接口序号">
          <span class="field-static">{{ chassisPortDraftMeta.ordinal }}（口 {{ chassisPortDraftMeta.portNo }}）</span>
        </el-form-item>
        <el-form-item label="接口类型">
          <el-select
            :model-value="chassisPortDraft.iface_type"
            style="width: 100%"
            :disabled="!canEdit"
            @change="(v: string) => onChassisPortDraftType(v as SwitchPortIfaceType)"
          >
            <el-option
              v-for="opt in SWITCH_PORT_IFACE_TYPE_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="速率">
          <el-select
            :model-value="chassisPortDraft.speed"
            style="width: 100%"
            :disabled="!canEdit"
            @change="onChassisPortDraftSpeed"
          >
            <el-option
              v-for="opt in SWITCH_PORT_SPEED_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="模块类型">
          <el-select v-model="chassisPortDraft.module" style="width: 100%" :disabled="!canEdit">
            <el-option
              v-for="opt in SWITCH_PORT_MODULE_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="光纤接口">
          <el-select v-model="chassisPortDraft.connector" style="width: 100%" :disabled="!canEdit">
            <el-option
              v-for="opt in SWITCH_PORT_CONNECTOR_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="单/多模">
          <el-select
            v-model="chassisPortDraft.fiber_mode"
            style="width: 100%"
            :disabled="!canEdit || chassisPortDraft.iface_type === 'copper'"
          >
            <el-option
              v-for="opt in SWITCH_PORT_FIBER_MODE_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="chassisPortEditVisible = false">取消</el-button>
        <el-button v-if="canEdit" type="primary" @click="saveChassisPortEdit">保存</el-button>
      </template>
    </el-dialog>

    <Teleport to="body">
      <div
        v-if="slotEditorVisible"
        class="slot-editor-mask"
        @mousedown.self.prevent="closePanelSlotEditor"
      >
        <div class="slot-editor-panel" role="dialog" aria-modal="true" @mousedown.stop @click.stop>
          <div class="slot-editor-head">
            <strong>编辑 Slot {{ slotDraft.index }} 接口</strong>
            <button type="button" class="slot-editor-x" aria-label="关闭" @click="closePanelSlotEditor">
              ×
            </button>
          </div>
          <div class="slot-editor-body">
            <el-form label-width="88px" size="small">
              <el-form-item label="接口类型">
                <el-select
                  :model-value="slotDraft.type"
                  style="width: 220px"
                  :disabled="!canEdit"
                  teleported
                  @update:model-value="onSlotDraftTypeChange"
                >
                  <el-option
                    v-for="o in DESIGN_SLOT_TYPE_OPTIONS"
                    :key="o.value"
                    :label="o.label"
                    :value="o.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item v-if="slotDraft.type === 'nic_1g' || slotDraft.type === 'nic_10g'" label="接口数">
                <el-input-number
                  :model-value="slotDraft.port_count"
                  :min="1"
                  :max="8"
                  :disabled="!canEdit"
                  @update:model-value="onSlotDraftPortCountChange"
                />
              </el-form-item>
              <el-form-item v-else-if="slotDraft.type === 'disk_bay'" label="盘位数">
                <el-input-number
                  :model-value="slotDraft.port_count"
                  :min="1"
                  :max="8"
                  :disabled="!canEdit"
                  @update:model-value="onSlotDraftPortCountChange"
                />
              </el-form-item>
              <el-form-item v-else-if="slotDraft.type === 'raid'" label="RAID">
                <el-select v-model="slotDraft.raid_level" style="width: 220px" :disabled="!canEdit" teleported>
                  <el-option
                    v-for="o in DESIGN_RAID_LEVEL_OPTIONS"
                    :key="o.value"
                    :label="o.label"
                    :value="o.value"
                  />
                </el-select>
              </el-form-item>
            </el-form>

            <div v-if="slotDraft.interfaces.length" class="if-editor">
              <div class="if-editor-title">接口明细（本端 / 对端）</div>
              <el-table :data="slotDraft.interfaces" size="small" border>
                <el-table-column label="#" prop="index" width="48" />
                <el-table-column label="类型" width="110">
                  <template #default="{ row }">
                    <el-select v-model="row.port_type" size="small" :disabled="!canEdit" teleported>
                      <el-option
                        v-for="o in SLOT_PORT_TYPE_OPTIONS"
                        :key="o.value"
                        :label="o.label"
                        :value="o.value"
                      />
                    </el-select>
                  </template>
                </el-table-column>
                <el-table-column label="本端标签" min-width="110">
                  <template #default="{ row }">
                    <el-input v-model="row.local_label" size="small" :disabled="!canEdit" placeholder="本端接口" />
                  </template>
                </el-table-column>
                <el-table-column label="本端信息" min-width="120">
                  <template #default="{ row }">
                    <el-input v-model="row.local_info" size="small" :disabled="!canEdit" placeholder="本端说明" />
                  </template>
                </el-table-column>
                <el-table-column label="对端标签" min-width="110">
                  <template #default="{ row }">
                    <el-input v-model="row.peer_label" size="small" :disabled="!canEdit" placeholder="对端接口/设备" />
                  </template>
                </el-table-column>
                <el-table-column label="对端信息" min-width="120">
                  <template #default="{ row }">
                    <el-input v-model="row.peer_info" size="small" :disabled="!canEdit" placeholder="对端说明" />
                  </template>
                </el-table-column>
              </el-table>
            </div>
            <p v-else class="muted" style="margin: 8px 0 0">当前类型无接口明细（RAID/空白卡槽）</p>
          </div>
          <div class="slot-editor-foot">
            <el-button v-if="canEdit" type="danger" plain @click="removePanelSlotItem">从面板移除</el-button>
            <el-button @click="closePanelSlotEditor">取消</el-button>
            <el-button v-if="canEdit" type="primary" @click="savePanelSlotEditor">保存</el-button>
          </div>
        </div>
      </div>
    </Teleport>

    <el-dialog
      v-model="customPanelVisible"
      title="自定义面板"
      width="92%"
      top="4vh"
      destroy-on-close
      append-to-body
      class="custom-panel-dialog"
    >
      <p class="custom-panel-hint">
        {{
          isCoreAggSwitch
            ? '在网格上拖拽框选定义业务接口板；右键已放置的接口板设置接口类型和个数。数量不超过模块化扩展插槽。'
            : '在网格上拖拽框选自定义面板布局；右键已放置的组件可设置接口类型和个数。完成后与模型属性一并保存。'
        }}
      </p>
      <ModelPanelSchematic
        v-if="customPanelVisible"
        v-model="panelLayout"
        :palette="panelPalette"
        :slots="serverSlots"
        :editable="canEdit"
        :free-board="isCoreAggSwitch"
        :max-boards="
          isCoreAggSwitch ? Number(attrFieldValue('modular_expansion_slots') ?? 6) : 8
        "
        @edit-slot="openPanelSlotEditor"
        @board-change="onCustomPanelBoardChange"
      />
      <template #footer>
        <el-button v-if="canEdit" @click="resetPanelAutoPlace">在当前尺寸内自动定位</el-button>
        <el-button type="primary" @click="customPanelVisible = false">完成</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="folderDialogVisible"
      :title="folderForm.kind === 'project' ? '新建项目' : '新建文件夹'"
      width="420px"
    >
      <el-form label-width="80px">
        <el-form-item label="上级">
          <el-select v-model="folderForm.parent_id" clearable placeholder="根级" style="width: 100%">
            <el-option
              v-for="f in folderOptions"
              :key="f.id"
              :label="f.label"
              :value="f.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="folderForm.name" />
        </el-form-item>
        <el-form-item label="编码">
          <el-input v-model="folderForm.code" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="folderForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="folderDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="confirmFolder">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="modelDialogVisible" title="新建模型" width="760px">
      <el-form label-width="100px">
        <el-form-item label="专业模板">
          <el-select
            :model-value="modelForm.preset_id"
            clearable
            filterable
            placeholder="选择典型型号，一键生成硬件与接口定义"
            style="width: 100%"
            @change="onCreatePresetChange"
          >
            <el-option-group
              v-for="group in NETWORK_MODEL_PRESET_GROUPS"
              :key="group.family"
              :label="group.label"
            >
              <el-option
                v-for="preset in group.presets"
                :key="preset.id"
                :label="`${preset.name} · ${preset.summary}`"
                :value="preset.id"
              />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-alert
          v-if="selectedCreatePreset"
          type="success"
          :closable="false"
          show-icon
          class="preset-summary"
        >
          <template #title>{{ selectedCreatePreset.summary }}</template>
          <div class="preset-tags">
            <el-tag v-for="tag in selectedCreatePreset.tags" :key="tag" size="small" effect="plain">
              {{ tag }}
            </el-tag>
          </div>
        </el-alert>
        <el-form-item label="编号" required>
          <el-input v-model="modelForm.code" />
        </el-form-item>
        <el-form-item label="设备类型" required>
          <el-select v-model="modelForm.category" style="width: 100%">
            <el-option
              v-for="opt in NETWORK_DEVICE_TYPE_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="设备子类型" required>
          <el-select v-model="modelForm.subtype" style="width: 100%">
            <el-option
              v-for="opt in createSubtypeOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="设备名称" required>
          <el-select
            :model-value="modelForm.createSummaryKey"
            filterable
            clearable
            allow-create
            default-first-option
            placeholder="从采购汇总选择，或直接输入设备名称"
            style="width: 100%"
            @change="onCreateSummaryChange"
            @focus="() => { if (!contractSummaries.length) loadContractSummaries() }"
          >
            <el-option
              v-for="sum in contractSummaries"
              :key="summaryOptionKey(sum)"
              :label="formatSummaryOptionLabel(sum)"
              :value="summaryOptionKey(sum)"
            />
          </el-select>
          <el-input
            v-model="modelForm.name"
            class="mt-name-fallback"
            placeholder="设备名称（可手动修改）"
            style="margin-top: 8px"
          />
        </el-form-item>
        <el-form-item label="型号">
          <el-input v-model="modelForm.vendor_sku" placeholder="自动关联或手动填写型号" />
        </el-form-item>
        <el-form-item label="厂商">
          <el-input v-model="modelForm.manufacturer_name" placeholder="自动关联或手动填写厂商" />
        </el-form-item>
        <el-alert
          type="info"
          :closable="false"
          title="创建后按设备类型生成基本信息与接口属性；可在右侧继续完善硬件配置与面板样式。"
        />
      </el-form>
      <template #footer>
        <el-button @click="modelDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="confirmCreateModel">创建</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<style scoped>
.preset-summary {
  margin-bottom: 16px;
}
.preset-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.model-design {
  display: grid;
  grid-template-columns: 260px 340px minmax(0, 1fr);
  gap: 12px;
  height: calc(100vh - 140px);
  min-height: 520px;
}
.tree-pane {
  min-width: 260px;
}
.list-pane {
  min-width: 340px;
}
.tree-pane,
.list-pane,
.editor-pane {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
.pane-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.pane-title {
  font-weight: 600;
  font-size: 14px;
}
.model-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.model-name-stack {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.model-name-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.model-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  color: #606266;
}
.model-code-sub {
  font-size: 11px;
  color: #909399;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.model-editor-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.pane-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.tree-node {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding-right: 8px;
  font-size: 13px;
}
.muted {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.if-editor {
  margin-top: 4px;
}
.if-editor-title {
  font-size: 13px;
  margin-bottom: 6px;
  color: #303133;
}
.tree-foot {
  padding: 8px 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}
.list-pane :deep(.el-table) {
  flex: 1;
}
.editor-scroll {
  flex: 1;
  overflow: auto;
  padding: 8px 10px 16px;
  container-type: inline-size;
  container-name: model-attrs;
}
.sec-title {
  font-weight: 700;
  font-size: 13px;
  margin: 8px 0 4px;
  color: #303133;
}
.sec-title-row {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 2px;
}
.sec-title-row .sec-title {
  margin: 8px 0 4px;
}
.panel-side-toggles { margin-left: auto; }
.panel-zoom-toggles {
  flex: 0 0 auto;
}
.sec-title.with-hint,
.slot-row-label.with-hint,
.slot-idx-wrap.with-hint {
  position: relative;
  display: inline-block;
  padding-right: 14px;
}
.attr-grid-form {
  font-size: 12px;
  --attr-label-w: 7em;
  --attr-col-w: 272px;
  width: max-content;
  max-width: 100%;
  display: grid;
  grid-template-columns: var(--attr-col-w) var(--attr-col-w);
  column-gap: 16px;
  row-gap: 4px;
  justify-content: start;
  align-items: start;
  --el-form-label-width: var(--attr-label-w);
}
.attr-grid-form :deep(.el-form-item) {
  margin-bottom: 0;
  min-width: 0;
  width: 100%;
  --el-form-label-width: var(--attr-label-w);
}
.attr-grid-form :deep(.el-form-item__label-wrap) {
  margin: 0;
  margin-right: 0 !important;
}
.attr-grid-form :deep(.el-form-item__label) {
  display: block !important;
  box-sizing: border-box !important;
  width: var(--attr-label-w) !important;
  min-width: var(--attr-label-w) !important;
  max-width: var(--attr-label-w) !important;
  flex: 0 0 var(--attr-label-w) !important;
  padding: 0 8px 0 0 !important;
  margin: 0 !important;
  line-height: 28px;
  height: 28px;
  overflow: hidden;
  white-space: nowrap;
  text-align: justify;
  text-align-last: justify;
  color: var(--el-text-color-regular);
  font-size: 12px;
}
.attr-grid-form :deep(.el-form-item__content) {
  line-height: 28px;
  min-width: 0;
  flex: 1 1 auto;
  justify-content: flex-start;
  align-items: center;
  gap: 4px;
}
.attr-grid-form :deep(.el-input),
.attr-grid-form :deep(.el-select),
.attr-grid-form :deep(.el-input-number) {
  width: 100% !important;
  max-width: 100%;
  min-width: 0;
}
.attr-grid-form :deep(.el-input-number .el-input__inner) {
  text-align: left;
}
.attr-grid-form .span-1 {
  grid-column: span 1;
}
.attr-grid-form .span-2 {
  grid-column: span 2;
}
.pcie-card-configs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.pcie-card-config {
  min-width: 0;
  padding: 8px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: linear-gradient(180deg, var(--el-fill-color-blank), var(--el-fill-color-light));
}
.pcie-card-config :deep(.el-select) {
  width: 118px !important;
}
.pcie-placement-buttons {
  display: inline-flex;
  flex-wrap: nowrap;
}
.pcie-placement-buttons :deep(.el-button) {
  min-width: 46px;
  padding-inline: 10px;
}
.security-interface-editor {
  margin-top: 10px;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-fill-color-extra-light);
}
.security-editor-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  color: var(--el-text-color-regular);
  font-size: 12px;
}
.security-editor-head span { color: var(--el-text-color-secondary); }
.security-editor-title { display: flex; flex-direction: column; gap: 3px; }
.security-editor-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 14px;
  padding: 9px 0;
  border-top: 1px dashed var(--el-border-color);
}
.security-editor-row label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--el-text-color-regular);
  font-size: 12px;
}
.security-editor-row :deep(.el-input-number) { width: 72px; }
.security-slot-delete { margin-left: auto; }
.pcie-slot-defs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
  width: 100%;
}
.pcie-slot-def {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 118px;
}
.pcie-slot-lab {
  flex: 0 0 auto;
  font-size: 12px;
  color: var(--el-text-color-regular);
  white-space: nowrap;
}
.pcie-slot-def :deep(.el-select) {
  width: 88px !important;
}
.attr-grid-form .span-3,
.attr-grid-form .span-4,
.attr-grid-form .attr-subhead {
  grid-column: 1 / -1;
}
.attr-grid-form :deep(.el-checkbox-group) {
  flex-wrap: wrap;
  row-gap: 2px;
}
.attr-grid-form :deep(.el-checkbox) {
  margin-right: 12px;
}
.attr-subhead {
  margin: 4px 0 1px;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-regular);
}
.iface-board-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.iface-board-row {
  display: flex;
  align-items: stretch;
  gap: 6px;
  margin: 4px 0 8px;
  min-width: 0;
}
.iface-nav {
  flex: 0 0 22px;
  width: 22px;
  padding: 0;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  background: #fff;
  color: var(--el-text-color-regular);
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
}
.iface-nav:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.iface-board-viewport {
  flex: 1 1 auto;
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
  overflow-x: hidden;
  min-width: 0;
  padding-bottom: 2px;
}
.iface-board-card {
  flex: 0 0 168px;
  width: 168px;
  box-sizing: border-box;
  padding: 8px 10px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  background: #fff;
  display: flex;
  flex-direction: column;
  gap: 0;
}
.iface-card-field {
  padding: 4px 0 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.iface-card-field :deep(.el-select),
.iface-card-field :deep(.el-input) {
  width: 100%;
}
.iface-card-lab {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-regular);
  margin-bottom: 4px;
  line-height: 1.2;
}
.iface-card-foot {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-top: 8px;
}
.iface-card-foot .iface-card-lab {
  margin: 0;
  flex: 0 0 auto;
}
.iface-port-sel {
  width: 72px;
  flex: 0 0 72px;
}
.iface-port-custom {
  width: 56px;
}
.iface-del {
  margin-left: auto;
  padding: 0;
}
.dim-row,
.unit-field {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 4px;
  min-width: 0;
  width: 100%;
}
.unit-field :deep(.el-input-number) {
  flex: 1 1 auto;
  min-width: 0;
  width: auto !important;
  max-width: none;
}
.dim-row :deep(.el-input-number) {
  flex: 1 1 64px;
  min-width: 0;
  width: auto !important;
  max-width: none;
}
.unit-lab {
  flex: 0 0 auto;
  font-size: 12px;
  line-height: 28px;
  color: var(--el-text-color-regular);
  white-space: nowrap;
}
.dim-x {
  color: var(--el-text-color-secondary);
  flex: 0 0 auto;
}
.panel-demo-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}
.hidden-file {
  display: none;
}
.chassis-demo-pair {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px 16px;
  max-width: 860px;
  margin: 6px 0 12px;
  align-items: start;
}
.server-demo-pair {
  grid-template-columns: 1fr;
  max-width: 860px;
}
.access-demo-pair {
  max-width: 860px;
  grid-template-columns: 1fr;
}
@media (max-width: 900px) {
  .chassis-demo-pair {
    grid-template-columns: 1fr;
  }
}
.chassis-demo-col {
  min-width: 0;
}
.chassis-demo-lab {
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-regular);
  display: flex;
  align-items: center;
  gap: 8px;
}
.style-preview {
  display: block;
  width: 100%;
  max-height: 280px;
  object-fit: contain;
  background: #1c1f24;
  border: 1px solid #5c636c;
}
.chassis-demo {
  max-width: 420px;
  margin: 6px 0 12px;
}
.chassis-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
}
.sys-port-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-top: 8px;
  padding: 8px;
  background: #f4f6f8;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
}
.sys-port-strip.access-sys-ports {
  max-width: 880px;
  margin: 10px 0 0;
}
.sys-port-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}
.sys-port-kind {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-right: 2px;
}
.sys-port-chip {
  min-width: 42px;
  height: 22px;
  padding: 0 6px;
  border: 1px solid #8aa0b8;
  border-radius: 3px;
  background: #fff;
  font-size: 11px;
  font-family: ui-monospace, Consolas, monospace;
  color: #303133;
  cursor: pointer;
}
.sys-port-chip.selected,
.sys-port-chip:hover {
  border-color: #409eff;
  color: #409eff;
  background: #ecf5ff;
}
.port-info-mask {
  position: fixed;
  inset: 0;
  z-index: 3999;
}
.port-info-pop {
  position: fixed;
  z-index: 4000;
  min-width: 260px;
  max-width: 320px;
  padding: 10px 12px;
  background: #fff;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}
.port-info-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}
.port-info-dl {
  margin: 0 0 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.port-info-dl > div {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 8px;
  font-size: 12px;
  line-height: 1.4;
}
.port-info-dl dt {
  margin: 0;
  color: var(--el-text-color-secondary);
}
.port-info-dl dd {
  margin: 0;
  color: var(--el-text-color-primary);
  word-break: break-all;
}
.custom-panel-hint {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}
.chassis-photo {
  display: block;
  width: 100%;
  max-width: 420px;
  border: 2px solid #2c3540;
  background: #c5c9cf;
}
.attr-grid-form .apply-item :deep(.el-form-item__content) {
  justify-content: flex-start;
}
.num-compact {
  width: 100%;
  min-width: 0;
}
.field-static {
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 32px;
}
.field-hint {
  margin-top: 2px;
  font-size: 11px;
  line-height: 1.3;
  color: var(--el-text-color-secondary);
}
.slot-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 4px;
}
.slot-grid-onboard {
  grid-template-columns: 1fr;
}
.slot-row-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}
.slot-row-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-regular);
}
.switch-slot-card {
  flex-wrap: wrap;
  min-height: 40px;
}
.slot-card {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  background: #fff;
}
.slot-idx-wrap {
  position: relative;
  display: inline-flex;
  align-items: flex-start;
  margin-right: 4px;
  padding-right: 12px;
}
.slot-idx {
  font-size: 12px;
  font-weight: 600;
  min-width: 48px;
  line-height: 1.4;
}
.slot-lab {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.slot-type {
  width: 118px;
}
.slot-card.is-onboard {
  border-color: #79bbff;
  background: #f5f9ff;
}
.slot-nic-type {
  width: 110px;
}
.slot-raid {
  width: 110px;
}
.slot-num {
  width: 64px;
}
.custom-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.custom-name {
  width: 160px;
}
.custom-val {
  width: 200px;
  flex: 1;
  min-width: 120px;
}
.custom-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 6px;
}
.custom-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  padding: 4px 8px;
  border-bottom: 1px dashed var(--el-border-color-lighter);
}
.desc-before-panel {
  margin-bottom: 4px;
}
@media (max-width: 1100px) {
  .preset-summary {
  margin-bottom: 16px;
}
.preset-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.model-design {
    grid-template-columns: 1fr;
    height: auto;
  }
  .tree-pane,
  .list-pane {
    min-width: 0;
  }
  .slot-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 640px) {
  .slot-grid {
    grid-template-columns: 1fr;
  }
}
@container model-attrs (max-width: 520px) {
  .attr-grid-form {
    grid-template-columns: minmax(0, var(--attr-col-w));
  }
  .attr-grid-form .span-2,
  .attr-grid-form .span-3,
  .attr-grid-form .span-4 {
    grid-column: span 1;
  }
}
</style>

<style>
/* Teleport 到 body，需非 scoped 才能生效 */
.slot-editor-mask {
  position: fixed;
  inset: 0;
  z-index: 4000;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  box-sizing: border-box;
}
.slot-editor-panel {
  width: min(720px, 100%);
  max-height: min(86vh, 900px);
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.18);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.slot-editor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
  font-size: 16px;
}
.slot-editor-x {
  border: none;
  background: transparent;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  color: #909399;
  padding: 0 4px;
}
.slot-editor-x:hover {
  color: #303133;
}
.slot-editor-body {
  padding: 12px 16px;
  overflow: auto;
  flex: 1 1 auto;
  min-height: 0;
}
.slot-editor-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 16px;
  border-top: 1px solid #ebeef5;
}
</style>
