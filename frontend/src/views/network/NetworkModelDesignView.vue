<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ModelPanelSchematic from '@/components/ModelPanelSchematic.vue'
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
import type { SwitchSubtype } from '@/api/network'
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
  NETWORK_DEVICE_TYPE_OPTIONS,
  readSwitchSlots,
  renumberPortStarts,
  SWITCH_SLOT_CARD_OPTIONS,
  SWITCH_SLOT_PURPOSE_OPTIONS,
  SWITCH_STYLE_OPTIONS,
  syncSwitchDerivedCounts,
  default100gPortCount,
  sync100gPortFields,
  type SwitchSlotAttr,
  type SwitchSlotCardType,
  type SwitchSlotPurpose,
} from '@/utils/switchModelAttrs'
import {
  applyServerHeightDefaults,
  defaultServerAttributes,
  diskFrontMaxForU,
  diskRearMaxForU,
  normalizeServerFormFactor,
  readServerIfaceSlots,
  renumberServerSlotPorts,
  SERVER_HEIGHT_OPTIONS,
  serverIfaceSlotsToDesignSlots,
  serverSlotLabelFromInterfaces,
  serverSlotNicType,
  applyServerSlotNicType,
  isOnboardSlot,
  defaultExpansionSlot,
  serverSlotPortRangeLabel,
  syncServerDerivedAttrs,
  type ServerIfaceSlotAttr,
  type ServerSlotNicType,
} from '@/utils/serverModelAttrs'
import {
  defaultSecurityAttributes,
  normalizeSecurityFormFactor,
  readSecurityIfaceSlots,
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
import { normalizeGigabitUplinkCount, normalizeTenGigabitUplinkCount } from '@/utils/switchFrontPanel'

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
const modelForm = reactive({
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

const DEFAULT_SUBTYPE: Record<string, string> = {
  network: 'switch',
  server: 'compute',
  security: 'firewall',
}

const selectedFolder = computed(() => findFolder(tree.value, selectedFolderId.value))
const selectedModel = computed(
  () => models.value.find((m) => m.id === selectedModelId.value) || null,
)

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
        'mgmt_ports',
        'fan_count',
        'psu_count',
        'chassis_height_u',
        'security_slots',
        'control_ports',
        'ha_ports',
        'data_port_count',
        'data_port_type',
      ].includes(f.key),
  ),
)

const isSwitchModel = computed(
  () => selectedModel.value?.category === 'network' && selectedModel.value?.subtype === 'switch',
)

const isServerModel = computed(() => selectedModel.value?.category === 'server')

const isSecurityModel = computed(() => selectedModel.value?.category === 'security')

const switchRole = computed<SwitchSubtype>(() => {
  const m = selectedModel.value
  if (!m?.attributes) return 'gigabit'
  const role = resolveDesignSwitchRole(m.attributes)
  return role === 'aggregation' ? 'core' : role
})

/** 各区块说明（相同规则只写一次，挂在标题叹号） */
const SERVER_SLOT_CONFIG_HINT =
  'Slot1 固定为板载（可同时配置 IPMI / VGA / USB / 10G / 1G 并自动编号）；Slot2+ 为扩展卡，仅配置万兆或千兆一种网口。'

const SECURITY_SLOT_CONFIG_HINT =
  '默认 4 槽；每槽含 Control/HA/MGMT/USB、10G 光口与 1G 电口，编号分别为 slotx-10G-(n)、slotx-1G-(n)。'

const switchSlotConfigHint = computed(() => {
  const role = switchRole.value
  if (role === 'core' || role === 'aggregation') {
    return '核心/汇聚：默认 3 槽；每槽可选千兆/万兆/40·100G（MPO+LC-LC）/空白板卡，每槽接口编号从 0 起（如 slot1-(0-47)）。'
  }
  if (role === 'ten_gigabit') {
    return '万兆：默认 3 槽；DOWNLINK 槽接口连续编号（如 slot1 0-23、slot2 24-47），UPLINK 槽各自从 0 起（默认 6 口为 0-5）。'
  }
  return '千兆：默认 2 槽；slot1 DOWNLINK 1G（0-47），slot2 UPLINK 10G（默认 6，≤8，编号 0-5）。'
})

const panelStyleHint = computed(() => {
  if (isSwitchModel.value) {
    return '点选组件后拖拽框选放置；口数自动按交换机双排紧凑均分，空板卡无接口。\n① 点选「设备配置及组件」中的组件 ② 在面板上拖拽框选范围放置；已放置组件可点选后点「删除」，或「清空组件」。'
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

const serverIfaceSlots = computed<ServerIfaceSlotAttr[]>(() => {
  const m = selectedModel.value
  if (!m || m.category !== 'server' || !m.attributes) return []
  return readServerIfaceSlots(m.attributes)
})

const serverOnboardSlot = computed(() => serverIfaceSlots.value.find((s) => isOnboardSlot(s)) || null)

const serverExpansionSlots = computed(() => serverIfaceSlots.value.filter((s) => !isOnboardSlot(s)))

function serverSlotListIndex(slot: ServerIfaceSlotAttr): number {
  return serverIfaceSlots.value.findIndex((s) => s.index === slot.index)
}

const serverSlots = computed<DesignSlotAttr[]>(() => {
  const m = selectedModel.value
  if (!m || m.category !== 'server') return []
  return serverIfaceSlotsToDesignSlots(serverIfaceSlots.value)
})

const serverDiskFrontMax = computed(() =>
  diskFrontMaxForU(selectedModel.value?.height_u ?? selectedModel.value?.attributes?.form_factor_u),
)

const serverDiskRearMax = computed(() => diskRearMaxForU())

const securityIfaceSlots = computed<SecurityIfaceSlotAttr[]>(() => {
  const m = selectedModel.value
  if (!m || m.category !== 'security' || !m.attributes) return []
  return readSecurityIfaceSlots(m.attributes)
})

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
  void m.attributes.server_slots
  void m.attributes.security_slots
  void m.attributes.slot_count
  void m.attributes.fan_count
  void m.attributes.psu_count
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
  modelForm.subtype = DEFAULT_SUBTYPE[modelForm.category] || modelForm.subtype
  const schema = await fetchAttributeSchema(modelForm.category, modelForm.subtype)
  attrSchema.value = schema
  if (modelForm.category === 'network' && modelForm.subtype === 'switch') {
    modelForm.attributes = defaultNetworkSwitchAttributes('gigabit')
    modelForm.height_u = asInt(modelForm.attributes.chassis_height_u, 1)
  } else if (modelForm.category === 'server') {
    modelForm.attributes = defaultServerAttributes(1)
    modelForm.height_u = 1
  } else if (modelForm.category === 'security') {
    modelForm.attributes = defaultSecurityAttributes(1)
    modelForm.height_u = 1
  } else {
    modelForm.attributes = { ...(schema?.default_attributes || {}) }
    modelForm.height_u = 1
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
    modelForm.code = `M${Date.now().toString().slice(-6)}`
    modelForm.name = ''
    modelForm.category = 'network'
    modelForm.subtype = 'switch'
    modelForm.manufacturer_name = ''
    modelForm.vendor_sku = ''
    modelForm.height_u = 1
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
    if (!modelDialogVisible.value) return
    await loadSchemaForForm()
  },
)

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
    modelForm.subtype = DEFAULT_SUBTYPE[modelForm.category] || modelForm.subtype
    let attrs: Record<string, unknown> = { ...(modelForm.attributes || {}) }
    if (modelForm.category === 'network') {
      modelForm.subtype = 'switch'
      attrs = { ...defaultNetworkSwitchAttributes('gigabit'), ...attrs }
      syncSwitchDerivedCounts(attrs)
      modelForm.height_u = asInt(attrs.chassis_height_u, 1)
    } else if (modelForm.category === 'server') {
      modelForm.subtype = 'compute'
      attrs = { ...defaultServerAttributes(normalizeServerFormFactor(modelForm.height_u || 1)), ...attrs }
      attrs.form_factor_u = normalizeServerFormFactor(modelForm.height_u || 1)
      syncServerDerivedAttrs(attrs)
      modelForm.height_u = asInt(attrs.form_factor_u, 1)
    } else if (modelForm.category === 'security') {
      modelForm.subtype = 'firewall'
      attrs = {
        ...defaultSecurityAttributes(normalizeSecurityFormFactor(modelForm.height_u || 1)),
        ...attrs,
      }
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
      description: null,
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
      description: null,
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
  if (m.category === 'network' && m.subtype === 'switch') {
    m.attributes = defaultNetworkSwitchAttributes('gigabit')
    m.height_u = asInt(m.attributes.chassis_height_u, 1)
  } else if (m.category === 'server') {
    m.attributes = defaultServerAttributes(1)
    m.height_u = 1
  } else if (m.category === 'security') {
    m.attributes = defaultSecurityAttributes(1)
    m.height_u = 1
  } else {
    m.attributes = { ...(attrSchema.value?.default_attributes || {}) }
  }
}

async function onSelectedSubtypeChange() {
  const m = selectedModel.value
  if (!m) return
  attrSchema.value = await fetchAttributeSchema(m.category, m.subtype)
  if (m.category === 'network' && m.subtype === 'switch') {
    m.attributes = defaultNetworkSwitchAttributes(
      resolveDesignSwitchRole(m.attributes || {}) || 'gigabit',
    )
  } else if (m.category === 'server') {
    m.attributes = defaultServerAttributes(normalizeServerFormFactor(m.height_u))
  } else if (m.category === 'security') {
    m.attributes = defaultSecurityAttributes(normalizeSecurityFormFactor(m.height_u))
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
    ensurePanelLayout(row.attributes, serverIfaceSlotsToDesignSlots(readServerIfaceSlots(row.attributes)), false)
  }
  if (row.category === 'security' && row.attributes) {
    if (!Array.isArray(row.attributes.security_slots) || !row.attributes.security_slots.length) {
      const seeded = defaultSecurityAttributes(
        normalizeSecurityFormFactor(row.attributes.chassis_height_u ?? row.height_u),
      )
      row.attributes = { ...seeded, ...row.attributes, security_slots: seeded.security_slots }
    }
    syncSecurityDerivedAttrs(row.attributes)
    row.height_u = normalizeSecurityFormFactor(row.attributes.chassis_height_u ?? row.height_u)
    ensurePanelLayout(row.attributes, [], false)
  }
  if (row.category === 'network' && row.subtype === 'switch' && row.attributes) {
    row.attributes.switch_role = resolveDesignSwitchRole(row.attributes)
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
    !(row.category === 'network' && row.subtype === 'switch')
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
      ensurePanelLayout(attrs, serverIfaceSlotsToDesignSlots(readServerIfaceSlots(attrs)), false)
      m.attributes = attrs
      m.height_u = asInt(attrs.form_factor_u, 1)
    }
    if (m.category === 'security') {
      syncSecurityDerivedAttrs(attrs)
      attrs.chassis_height_u = normalizeSecurityFormFactor(m.height_u)
      ensurePanelLayout(attrs, [], false)
      m.attributes = attrs
      m.height_u = normalizeSecurityFormFactor(attrs.chassis_height_u)
    }
    if (m.category === 'network' && m.subtype === 'switch') {
      attrs.switch_role = resolveDesignSwitchRole(attrs)
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
  if (key === 'slot_count' && m.category === 'server') {
    syncServerDerivedAttrs(m.attributes)
  }
  if (
    m.category === 'server' &&
    [
      'psu_count',
      'bmc_ports',
      'usb_ports',
      'slot_count',
      'server_slots',
      'disk_front_count',
      'disk_rear_count',
      'fan_count',
      'form_factor_u',
      'cpu_sockets',
      'cpu_cores_per_socket',
      'memory_module_gb',
      'memory_gb',
    ].includes(key)
  ) {
    if (['slot_count', 'server_slots', 'disk_front_count', 'disk_rear_count', 'form_factor_u'].includes(key)) {
      syncServerDerivedAttrs(m.attributes)
    }
    ensurePanelLayout(
      m.attributes,
      serverIfaceSlotsToDesignSlots(readServerIfaceSlots(m.attributes)),
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
    m.subtype === 'switch' &&
    [
      'switch_role',
      'switch_slots',
      'card_slot_count',
      'downlink_count',
      'optical_card_count',
      'optical_ports_per_card',
      'uplink_count',
      'uplink_position',
      'mgmt_ports',
      'fan_count',
      'psu_count',
      'line_cards',
      'chassis_height_u',
    ].includes(key)
  ) {
    if (key !== 'fan_count' && key !== 'psu_count' && key !== 'mgmt_ports') {
      syncSwitchDerivedCounts(m.attributes)
    }
    ensurePanelLayout(m.attributes, [], false)
  }
}

function refreshSwitchPanelLayout() {
  const m = selectedModel.value
  if (!m?.attributes || !isSwitchModel.value) return
  ensurePanelLayout(m.attributes, [], false)
}

function commitSwitchSlots(slots: SwitchSlotAttr[]) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const next = renumberPortStarts(slots, switchRole.value)
  m.attributes.switch_slots = next
  m.attributes.card_slot_count = next.length
  syncSwitchDerivedCounts(m.attributes)
  if (switchRole.value === 'core' || switchRole.value === 'aggregation') {
    m.height_u = Math.max(1, asInt(m.attributes.chassis_height_u, next.length))
  }
  refreshSwitchPanelLayout()
}

function onSwitchRoleChange(role: SwitchSubtype) {
  const m = selectedModel.value
  if (!m) return
  if (!m.attributes) m.attributes = {}
  const keepFan = m.attributes.fan_count
  const keepPsu = m.attributes.psu_count
  const keepMgmt = m.attributes.mgmt_ports
  const panel = m.attributes.panel_layout
  Object.assign(m.attributes, applySwitchStyleDefaults(m.attributes, role))
  if (keepFan != null) m.attributes.fan_count = keepFan
  if (keepPsu != null) m.attributes.psu_count = keepPsu
  if (keepMgmt != null) m.attributes.mgmt_ports = keepMgmt
  if (panel) m.attributes.panel_layout = panel
  syncSwitchDerivedCounts(m.attributes)
  m.height_u = Math.max(1, asInt(m.attributes.chassis_height_u, 1))
  refreshSwitchPanelLayout()
}

function onCardSlotCountChange(v: number | undefined) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const n = Math.max(1, Math.min(16, v ?? 1))
  m.attributes.card_slot_count = n
  const current = readSwitchSlots(m.attributes)
  const next = current.slice(0, n)
  while (next.length < n) {
    next.push({
      index: next.length + 1,
      purpose: 'BLANK',
      card_type: 'blank',
      port_count: 0,
      port_start: 0,
    })
  }
  commitSwitchSlots(next)
}

function onSwitchSlotCardTypeChange(idx: number, cardType: SwitchSlotCardType) {
  const slots = switchSlots.value.map((s) => ({ ...s }))
  const slot = slots[idx]
  if (!slot) return
  slot.card_type = cardType
  if (cardType === 'blank') {
    slot.purpose = 'BLANK'
    slot.port_count = 0
    slot.mpo_count = 0
    slot.lc_count = 0
  } else if (cardType === '100g') {
    if (slot.purpose === 'BLANK') {
      slot.purpose = switchRole.value === 'ten_gigabit' ? 'UPLINK' : 'DOWNLINK_UPLINK'
    }
    const def = default100gPortCount(switchRole.value)
    const synced = sync100gPortFields(
      { ...slot, lc_count: 0, mpo_count: def, port_count: def },
      def,
    )
    Object.assign(slot, synced)
  } else {
    if (slot.purpose === 'BLANK') slot.purpose = 'DOWNLINK'
    if (!slot.port_count) slot.port_count = cardType === 'gigabit' ? 48 : 24
    slot.mpo_count = 0
    slot.lc_count = 0
  }
  commitSwitchSlots(slots)
}

function onSwitchSlotPurposeChange(idx: number, purpose: SwitchSlotPurpose) {
  const slots = switchSlots.value.map((s) => ({ ...s }))
  const slot = slots[idx]
  if (!slot) return
  slot.purpose = purpose
  if (purpose === 'BLANK') {
    slot.card_type = 'blank'
    slot.port_count = 0
    slot.mpo_count = 0
    slot.lc_count = 0
  } else if (slot.card_type === 'blank') {
    slot.card_type = 'ten_gigabit'
  }
  commitSwitchSlots(slots)
}

function onSwitchSlotPortCountChange(idx: number, count: number | undefined) {
  const slots = switchSlots.value.map((s) => ({ ...s }))
  const slot = slots[idx]
  if (!slot || slot.card_type === 'blank') return
  if (slot.card_type === '100g') {
    const next = Math.max(0, Math.min(36, count ?? default100gPortCount(switchRole.value)))
    Object.assign(slot, sync100gPortFields({ ...slot, lc_count: 0 }, next))
    commitSwitchSlots(slots)
    return
  }
  const max = slot.purpose === 'UPLINK' ? 8 : 48
  let next = Math.max(0, Math.min(max, count ?? 0))
  if (slot.purpose === 'UPLINK') {
    next = Math.min(8, Math.max(0, next || 6))
    if (switchRole.value === 'gigabit') next = normalizeGigabitUplinkCount(next)
    else if (switchRole.value === 'ten_gigabit') next = normalizeTenGigabitUplinkCount(next)
  }
  slot.port_count = next
  commitSwitchSlots(slots)
}

function onSwitchSlotMpoChange(idx: number, count: number | undefined) {
  const slots = switchSlots.value.map((s) => ({ ...s }))
  const slot = slots[idx]
  if (!slot || slot.card_type !== '100g') return
  slot.mpo_count = Math.max(0, Math.min(36, count ?? 0))
  const lc = Math.max(0, Math.min(36, Number(slot.lc_count) || 0))
  slot.lc_count = lc
  slot.port_count = Math.min(36, slot.mpo_count + lc)
  commitSwitchSlots(slots)
}

function onSwitchSlotLcChange(idx: number, count: number | undefined) {
  const slots = switchSlots.value.map((s) => ({ ...s }))
  const slot = slots[idx]
  if (!slot || slot.card_type !== '100g') return
  slot.lc_count = Math.max(0, Math.min(36, count ?? 0))
  const mpo = Math.max(0, Math.min(36, Number(slot.mpo_count) || 0))
  slot.mpo_count = mpo
  slot.port_count = Math.min(36, mpo + slot.lc_count)
  commitSwitchSlots(slots)
}

function onSwitchHeightChange(v: number | undefined) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const h = Math.max(1, Math.min(48, v ?? 1))
  m.height_u = h
  m.attributes.chassis_height_u = h
  refreshSwitchPanelLayout()
}

function slotPortRangeLabel(slot: SwitchSlotAttr): string {
  const n = effectivePortCount(slot)
  if (n <= 0) return '—'
  const end = slot.port_start + n - 1
  return `slot${slot.index}-(${slot.port_start}-${end})`
}


function commitServerIfaceSlots(slots: ServerIfaceSlotAttr[]) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const next = renumberServerSlotPorts(slots)
  m.attributes.server_slots = next
  m.attributes.slot_count = next.length
  m.attributes.slots = serverIfaceSlotsToDesignSlots(next)
  syncServerDerivedAttrs(m.attributes)
  ensurePanelLayout(m.attributes, serverIfaceSlotsToDesignSlots(next), false)
}

function onServerHeightChange(v: number | string | undefined) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const u = normalizeServerFormFactor(v)
  m.height_u = u
  Object.assign(m.attributes, applyServerHeightDefaults(m.attributes, u))
  ensurePanelLayout(
    m.attributes,
    serverIfaceSlotsToDesignSlots(readServerIfaceSlots(m.attributes)),
    false,
  )
}

function onServerSlotCountChange(v: number | undefined) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const n = Math.max(1, Math.min(16, v ?? 3))
  m.attributes.slot_count = n
  const current = readServerIfaceSlots(m.attributes)
  const next = current.slice(0, n)
  while (next.length < n) {
    next.push(defaultExpansionSlot(next.length + 1))
  }
  commitServerIfaceSlots(next)
}

function patchServerIfaceSlot(idx: number, patch: Partial<ServerIfaceSlotAttr>) {
  const slots = serverIfaceSlots.value.map((s) => ({ ...s }))
  const slot = slots[idx]
  if (!slot) return
  Object.assign(slot, patch)
  // 扩展槽：同槽网口互斥；板载允许 10G+1G 共存
  if (!isOnboardSlot(slot)) {
    if (patch.ports_10g != null && Number(patch.ports_10g) > 0) slot.ports_1g = 0
    if (patch.ports_1g != null && Number(patch.ports_1g) > 0) slot.ports_10g = 0
  }
  commitServerIfaceSlots(slots)
}

function onServerSlotNicTypeChange(idx: number, type: ServerSlotNicType) {
  const slots = serverIfaceSlots.value.map((s) => ({ ...s }))
  const slot = slots[idx]
  if (!slot) return
  slots[idx] = applyServerSlotNicType(slot, type)
  commitServerIfaceSlots(slots)
}

function onServerSlotNicCountChange(idx: number, v: number | undefined) {
  const slots = serverIfaceSlots.value.map((s) => ({ ...s }))
  const slot = slots[idx]
  if (!slot) return
  const type = serverSlotNicType(slot)
  if (type === 'none') {
    slots[idx] = applyServerSlotNicType(slot, '10g', v ?? 2)
  } else {
    slots[idx] = applyServerSlotNicType(slot, type, v ?? 2)
  }
  commitServerIfaceSlots(slots)
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

function onSecuritySlotCountChange(v: number | undefined) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const n = Math.max(1, Math.min(16, v ?? 4))
  m.attributes.slot_count = n
  const current = readSecurityIfaceSlots(m.attributes)
  const next = current.slice(0, n)
  while (next.length < n) {
    next.push({
      index: next.length + 1,
      control_count: 0,
      ha_count: 0,
      mgmt_count: 0,
      usb_count: 0,
      ports_10g: 4,
      ports_1g: 2,
    })
  }
  commitSecurityIfaceSlots(next)
}

function patchSecurityIfaceSlot(idx: number, patch: Partial<SecurityIfaceSlotAttr>) {
  const slots = securityIfaceSlots.value.map((s) => ({ ...s }))
  const slot = slots[idx]
  if (!slot) return
  Object.assign(slot, patch)
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
      serverIfaceSlotsToDesignSlots(readServerIfaceSlots(m.attributes)),
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
            <div class="sec-title">基础属性</div>
            <el-form label-position="left" label-width="108px" size="small" class="attr-grid-form">
              <el-form-item label="编号">
                <el-input v-model="selectedModel.code" :disabled="!canEdit" />
              </el-form-item>
              <el-form-item label="设备名称" class="span-2">
                <el-select
                  v-model="selectedSummaryKey"
                  filterable
                  clearable
                  placeholder="关联合同/采购汇总设备名称"
                  style="width: 100%"
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
              <el-form-item label="设备高度(U)">
                <el-select
                  v-if="isServerModel"
                  :model-value="normalizeServerFormFactor(selectedModel.height_u)"
                  :disabled="!canEdit"
                  style="width: 120px"
                  @change="onServerHeightChange"
                >
                  <el-option
                    v-for="opt in SERVER_HEIGHT_OPTIONS"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
                <el-select
                  v-else-if="isSecurityModel"
                  :model-value="normalizeSecurityFormFactor(selectedModel.height_u)"
                  :disabled="!canEdit"
                  style="width: 120px"
                  @change="onSecurityHeightChange"
                >
                  <el-option
                    v-for="opt in SECURITY_HEIGHT_OPTIONS"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
                <el-input-number
                  v-else
                  :model-value="selectedModel.height_u"
                  :min="1"
                  :max="48"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="onSwitchHeightChange"
                />
              </el-form-item>
              <el-form-item label="风扇个数">
                <el-input-number
                  :model-value="Number(attrFieldValue('fan_count') ?? 2)"
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
                  :model-value="Number(attrFieldValue('psu_count') ?? 2)"
                  :min="0"
                  :max="8"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('psu_count', v ?? 0)"
                />
              </el-form-item>
            </el-form>
          </template>
          <template v-else>
            <div class="sec-title">基本属性</div>
            <el-form label-position="left" label-width="64px" size="small" class="attr-grid-form">
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

          <template v-if="isServerModel">
            <div class="sec-title">配置属性（{{ normalizeServerFormFactor(selectedModel.height_u) }}U）</div>
            <el-form label-position="left" label-width="120px" size="small" class="attr-grid-form">
              <el-form-item label="CPU个数">
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
              <el-form-item label="核心数">
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
              <el-form-item label="单内存大小">
                <el-input-number
                  :model-value="Number(attrFieldValue('memory_module_gb') ?? 16)"
                  :min="1"
                  :max="1024"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="onServerMemoryModuleChange"
                />
                <span class="slot-lab muted">GB</span>
              </el-form-item>
              <el-form-item label="总内存大小">
                <el-input-number
                  :model-value="Number(attrFieldValue('memory_gb') ?? 128)"
                  :min="1"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('memory_gb', v ?? 1)"
                />
                <span class="slot-lab muted">GB</span>
              </el-form-item>
              <el-form-item label="前面板磁盘插槽">
                <el-input-number
                  :model-value="Number(attrFieldValue('disk_front_count') ?? 0)"
                  :min="0"
                  :max="serverDiskFrontMax"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="onServerDiskFrontChange"
                />
                <span class="slot-lab muted">≤{{ serverDiskFrontMax }}</span>
              </el-form-item>
              <el-form-item label="后面板磁盘插槽">
                <el-input-number
                  :model-value="Number(attrFieldValue('disk_rear_count') ?? 0)"
                  :min="0"
                  :max="serverDiskRearMax"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="onServerDiskRearChange"
                />
                <span class="slot-lab muted">≤{{ serverDiskRearMax }}</span>
              </el-form-item>
            </el-form>

            <div class="sec-title">接口属性</div>
            <el-form label-position="left" label-width="120px" size="small" class="attr-grid-form">
              <el-form-item label="板卡插槽数">
                <el-input-number
                  :model-value="Number(attrFieldValue('slot_count') ?? serverIfaceSlots.length)"
                  :min="1"
                  :max="16"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="onServerSlotCountChange"
                />
              </el-form-item>
            </el-form>

            <div class="sec-title-row">
              <span class="sec-title with-hint">
                Slot 配置（共 {{ serverIfaceSlots.length }} 槽）
                <TitleHintBang title="说明" :content="SERVER_SLOT_CONFIG_HINT" />
              </span>
            </div>

            <div v-if="serverOnboardSlot" class="slot-row-block">
              <div class="slot-row-label with-hint">
                板载
                <TitleHintBang
                  title="接口编号"
                  :content="serverSlotPortRangeLabel(serverOnboardSlot)"
                  :width="320"
                />
              </div>
              <div class="slot-grid slot-grid-onboard">
                <div class="slot-card switch-slot-card is-onboard">
                  <span class="slot-idx">板载</span>
                  <span class="slot-lab">IPMI</span>
                  <el-input-number
                    :model-value="serverOnboardSlot.ipmi_count"
                    :min="0"
                    :max="4"
                    :controls="false"
                    size="small"
                    class="slot-num"
                    :disabled="!canEdit"
                    @change="(v: number | undefined) => patchServerIfaceSlot(serverSlotListIndex(serverOnboardSlot), { ipmi_count: v ?? 0 })"
                  />
                  <span class="slot-lab">VGA</span>
                  <el-input-number
                    :model-value="serverOnboardSlot.hdmi_count"
                    :min="0"
                    :max="4"
                    :controls="false"
                    size="small"
                    class="slot-num"
                    :disabled="!canEdit"
                    @change="(v: number | undefined) => patchServerIfaceSlot(serverSlotListIndex(serverOnboardSlot), { hdmi_count: v ?? 0 })"
                  />
                  <span class="slot-lab">USB</span>
                  <el-input-number
                    :model-value="serverOnboardSlot.usb_count"
                    :min="0"
                    :max="8"
                    :controls="false"
                    size="small"
                    class="slot-num"
                    :disabled="!canEdit"
                    @change="(v: number | undefined) => patchServerIfaceSlot(serverSlotListIndex(serverOnboardSlot), { usb_count: v ?? 0 })"
                  />
                  <span class="slot-lab">10G光口</span>
                  <el-input-number
                    :model-value="serverOnboardSlot.ports_10g"
                    :min="0"
                    :max="16"
                    :controls="false"
                    size="small"
                    class="slot-num"
                    :disabled="!canEdit"
                    @change="(v: number | undefined) => patchServerIfaceSlot(serverSlotListIndex(serverOnboardSlot), { ports_10g: v ?? 0 })"
                  />
                  <span class="slot-lab">1G电口</span>
                  <el-input-number
                    :model-value="serverOnboardSlot.ports_1g"
                    :min="0"
                    :max="16"
                    :controls="false"
                    size="small"
                    class="slot-num"
                    :disabled="!canEdit"
                    @change="(v: number | undefined) => patchServerIfaceSlot(serverSlotListIndex(serverOnboardSlot), { ports_1g: v ?? 0 })"
                  />
                </div>
              </div>
            </div>

            <div v-if="serverExpansionSlots.length" class="slot-row-block">
              <div class="slot-row-label">扩展 Slot</div>
              <div class="slot-grid">
                <div
                  v-for="slot in serverExpansionSlots"
                  :key="`srv-exp-${slot.index}`"
                  class="slot-card switch-slot-card"
                >
                  <span class="slot-idx-wrap with-hint">
                    <span class="slot-idx">Slot {{ slot.index }}</span>
                    <TitleHintBang
                      title="接口编号"
                      :content="serverSlotPortRangeLabel(slot)"
                      :width="280"
                    />
                  </span>
                  <span class="slot-lab">网口类型</span>
                  <el-select
                    :model-value="serverSlotNicType(slot)"
                    size="small"
                    class="slot-nic-type"
                    :disabled="!canEdit"
                    teleported
                    @change="(v: ServerSlotNicType) => onServerSlotNicTypeChange(serverSlotListIndex(slot), v)"
                  >
                    <el-option label="万兆 10G" value="10g" />
                    <el-option label="千兆 1G" value="1g" />
                    <el-option label="无网口" value="none" />
                  </el-select>
                  <span class="slot-lab">口数</span>
                  <el-input-number
                    :model-value="
                      serverSlotNicType(slot) === '10g'
                        ? slot.ports_10g
                        : serverSlotNicType(slot) === '1g'
                          ? slot.ports_1g
                          : 0
                    "
                    :min="serverSlotNicType(slot) === 'none' ? 0 : 1"
                    :max="16"
                    :controls="false"
                    size="small"
                    class="slot-num"
                    :disabled="!canEdit || serverSlotNicType(slot) === 'none'"
                    @change="(v: number | undefined) => onServerSlotNicCountChange(serverSlotListIndex(slot), v)"
                  />
                </div>
              </div>
            </div>
          </template>

          <template v-else-if="isSecurityModel">
            <div class="sec-title">接口属性</div>
            <el-form label-position="left" label-width="120px" size="small" class="attr-grid-form">
              <el-form-item label="板卡插槽数">
                <el-input-number
                  :model-value="Number(attrFieldValue('slot_count') ?? securityIfaceSlots.length)"
                  :min="1"
                  :max="16"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="onSecuritySlotCountChange"
                />
              </el-form-item>
            </el-form>

            <div class="sec-title-row">
              <span class="sec-title with-hint">
                Slot 配置（共 {{ securityIfaceSlots.length }} 槽）
                <TitleHintBang title="说明" :content="SECURITY_SLOT_CONFIG_HINT" />
              </span>
            </div>
            <div class="slot-grid">
              <div
                v-for="(slot, idx) in securityIfaceSlots"
                :key="`sec-${slot.index}`"
                class="slot-card switch-slot-card"
              >
                <span class="slot-idx-wrap with-hint">
                  <span class="slot-idx">Slot {{ slot.index }}</span>
                  <TitleHintBang title="接口编号" :content="securitySlotRangeHint(slot)" :width="280" />
                </span>
                <span class="slot-lab">Control</span>
                <el-input-number
                  :model-value="slot.control_count"
                  :min="0"
                  :max="8"
                  :controls="false"
                  size="small"
                  class="slot-num"
                  :disabled="!canEdit"
                  @change="(v: number | undefined) => patchSecurityIfaceSlot(idx, { control_count: v ?? 0 })"
                />
                <span class="slot-lab">HA</span>
                <el-input-number
                  :model-value="slot.ha_count"
                  :min="0"
                  :max="8"
                  :controls="false"
                  size="small"
                  class="slot-num"
                  :disabled="!canEdit"
                  @change="(v: number | undefined) => patchSecurityIfaceSlot(idx, { ha_count: v ?? 0 })"
                />
                <span class="slot-lab">MGMT</span>
                <el-input-number
                  :model-value="slot.mgmt_count"
                  :min="0"
                  :max="8"
                  :controls="false"
                  size="small"
                  class="slot-num"
                  :disabled="!canEdit"
                  @change="(v: number | undefined) => patchSecurityIfaceSlot(idx, { mgmt_count: v ?? 0 })"
                />
                <span class="slot-lab">USB</span>
                <el-input-number
                  :model-value="slot.usb_count"
                  :min="0"
                  :max="8"
                  :controls="false"
                  size="small"
                  class="slot-num"
                  :disabled="!canEdit"
                  @change="(v: number | undefined) => patchSecurityIfaceSlot(idx, { usb_count: v ?? 0 })"
                />
                <span class="slot-lab">10G光口</span>
                <el-input-number
                  :model-value="slot.ports_10g"
                  :min="0"
                  :max="48"
                  :controls="false"
                  size="small"
                  class="slot-num"
                  :disabled="!canEdit"
                  @change="(v: number | undefined) => patchSecurityIfaceSlot(idx, { ports_10g: v ?? 0 })"
                />
                <span class="slot-lab">1G电口</span>
                <el-input-number
                  :model-value="slot.ports_1g"
                  :min="0"
                  :max="48"
                  :controls="false"
                  size="small"
                  class="slot-num"
                  :disabled="!canEdit"
                  @change="(v: number | undefined) => patchSecurityIfaceSlot(idx, { ports_1g: v ?? 0 })"
                />
              </div>
            </div>
          </template>

          <template v-else-if="isSwitchModel">
            <div class="sec-title">接口属性</div>
            <el-form label-position="left" label-width="120px" size="small" class="attr-grid-form">
              <el-form-item label="交换机样式" class="span-2">
                <el-select
                  :model-value="switchRole"
                  :disabled="!canEdit"
                  style="width: 100%"
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
              <el-form-item v-if="switchRole === 'gigabit'" label="BMC管理交换机" class="span-2">
                <el-switch
                  :model-value="!!attrFieldValue('is_bmc_switch')"
                  :disabled="!canEdit"
                  @change="(v: boolean | string | number) => setAttrField('is_bmc_switch', !!v)"
                />
                <span class="field-hint">勾选后按 BMC_SWITCH 参与带外管理布线（场景 B1）</span>
              </el-form-item>
              <el-form-item label="板卡插槽数">
                <el-input-number
                  :model-value="Number(attrFieldValue('card_slot_count') ?? switchSlots.length)"
                  :min="1"
                  :max="16"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="onCardSlotCountChange"
                />
              </el-form-item>
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
            </el-form>

            <div class="sec-title-row">
              <span class="sec-title with-hint">
                Slot 配置（共 {{ switchSlots.length }} 槽）
                <TitleHintBang title="说明" :content="switchSlotConfigHint" :width="360" />
              </span>
            </div>
            <div class="slot-grid">
              <div v-for="(slot, idx) in switchSlots" :key="`sw-${slot.index}`" class="slot-card switch-slot-card">
                <span class="slot-idx-wrap with-hint">
                  <span class="slot-idx">Slot {{ slot.index }}</span>
                  <TitleHintBang
                    title="接口编号"
                    :content="slot.card_type === 'blank' || slot.purpose === 'BLANK' ? '空白板卡' : slotPortRangeLabel(slot)"
                    :width="260"
                  />
                </span>
                <el-select
                  :model-value="slot.purpose"
                  size="small"
                  :disabled="!canEdit"
                  class="slot-type"
                  @change="(v: string) => onSwitchSlotPurposeChange(idx, v as SwitchSlotPurpose)"
                >
                  <el-option
                    v-for="opt in SWITCH_SLOT_PURPOSE_OPTIONS"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
                <el-select
                  :model-value="slot.card_type"
                  size="small"
                  :disabled="!canEdit || slot.purpose === 'BLANK'"
                  class="slot-type"
                  @change="(v: string) => onSwitchSlotCardTypeChange(idx, v as SwitchSlotCardType)"
                >
                  <el-option
                    v-for="opt in SWITCH_SLOT_CARD_OPTIONS"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
                <template v-if="slot.card_type === '100g'">
                  <span class="slot-lab">口数</span>
                  <el-input-number
                    :model-value="Number(slot.port_count ?? 0)"
                    :min="0"
                    :max="36"
                    :controls="false"
                    size="small"
                    class="slot-num"
                    :disabled="!canEdit"
                    @change="(v: number | undefined) => onSwitchSlotPortCountChange(idx, v)"
                  />
                  <span class="slot-lab">MPO</span>
                  <el-input-number
                    :model-value="Number(slot.mpo_count ?? 0)"
                    :min="0"
                    :max="36"
                    :controls="false"
                    size="small"
                    class="slot-num"
                    :disabled="!canEdit"
                    @change="(v: number | undefined) => onSwitchSlotMpoChange(idx, v)"
                  />
                  <span class="slot-lab">LC-LC</span>
                  <el-input-number
                    :model-value="Number(slot.lc_count ?? 0)"
                    :min="0"
                    :max="36"
                    :controls="false"
                    size="small"
                    class="slot-num"
                    :disabled="!canEdit"
                    @change="(v: number | undefined) => onSwitchSlotLcChange(idx, v)"
                  />
                </template>
                <template v-else-if="slot.card_type !== 'blank'">
                  <span class="slot-lab">口数</span>
                  <el-input-number
                    :model-value="slot.port_count"
                    :min="0"
                    :max="slot.purpose === 'UPLINK' ? 8 : 48"
                    :controls="false"
                    size="small"
                    class="slot-num"
                    :disabled="!canEdit"
                    @change="(v: number | undefined) => onSwitchSlotPortCountChange(idx, v)"
                  />
                </template>
                <span v-else class="slot-lab muted">空白</span>
              </div>
            </div>
          </template>

          <template v-else-if="selectedModel.category !== 'software'">
            <div class="sec-title">规格属性</div>
            <el-form label-position="left" label-width="auto" size="small" class="attr-grid-form">
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

          <template v-if="usesGridPanel">
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

    <el-dialog v-model="modelDialogVisible" title="新建模型" width="620px">
      <el-form label-width="100px">
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
          title="创建后按设备类型生成基础/接口属性；可在右侧继续完善 Slot 与面板样式。"
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
.model-design {
  display: grid;
  grid-template-columns: 260px 340px minmax(360px, 1fr);
  gap: 12px;
  height: calc(100vh - 140px);
  min-height: 520px;
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
  padding: 10px 12px 20px;
}
.sec-title {
  font-weight: 700;
  font-size: 13px;
  margin: 10px 0 6px;
  color: #303133;
}
.sec-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 4px;
}
.sec-title-row .sec-title {
  margin: 10px 0 6px;
}
.sec-title.with-hint,
.slot-row-label.with-hint,
.slot-idx-wrap.with-hint {
  position: relative;
  display: inline-block;
  padding-right: 14px;
}
.attr-grid-form {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  column-gap: 10px;
  row-gap: 4px;
  align-items: start;
}
.attr-grid-form :deep(.el-form-item) {
  margin-bottom: 0;
  min-width: 0;
}
.attr-grid-form :deep(.el-form-item__label) {
  padding-right: 6px;
  line-height: 28px;
  height: auto;
  white-space: nowrap;
  color: var(--el-text-color-regular);
  font-size: 12px;
}
.attr-grid-form :deep(.el-form-item__content) {
  line-height: 28px;
  min-width: 0;
}
.attr-grid-form :deep(.el-input),
.attr-grid-form :deep(.el-select),
.attr-grid-form :deep(.el-input-number) {
  width: 100%;
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
.attr-grid-form .span-3 {
  grid-column: span 3;
}
.attr-grid-form .span-4 {
  grid-column: span 4;
}
.attr-grid-form .apply-item :deep(.el-form-item__content) {
  justify-content: flex-start;
}
.num-compact {
  width: 100%;
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
@media (max-width: 1400px) {
  .attr-grid-form {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .attr-grid-form .span-4 {
    grid-column: span 3;
  }
  .attr-grid-form .span-3 {
    grid-column: span 3;
  }
}
@media (max-width: 1100px) {
  .model-design {
    grid-template-columns: 1fr;
    height: auto;
  }
  .attr-grid-form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .attr-grid-form .span-2,
  .attr-grid-form .span-3,
  .attr-grid-form .span-4 {
    grid-column: span 2;
  }
  .slot-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 640px) {
  .attr-grid-form {
    grid-template-columns: 1fr;
  }
  .attr-grid-form .span-1,
  .attr-grid-form .span-2,
  .attr-grid-form .span-3,
  .attr-grid-form .span-4 {
    grid-column: span 1;
  }
  .slot-grid {
    grid-template-columns: 1fr;
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
