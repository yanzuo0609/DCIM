<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ApplyPanelToDevicesDialog from '@/components/ApplyPanelToDevicesDialog.vue'
import ModelPanelSchematic from '@/components/ModelPanelSchematic.vue'
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
import type { CoreLineCard, NetworkNode, PortLayout, SwitchSubtype, UplinkPosition } from '@/api/network'
import {
  CORE_CARD_TYPE_LABELS,
  newCoreLineCard,
  SWITCH_SUBTYPE_DEFAULTS,
  SWITCH_SUBTYPE_LABELS,
  UPLINK_POSITION_LABELS,
} from '@/api/network'
import { getContractSummary, type DeviceContractSummary } from '@/api/contract'
import { useAuthStore } from '@/stores/auth'
import {
  formatSummaryOptionLabel,
  resolveModelFromSummary,
  summaryOptionKey,
} from '@/utils/contractModelBind'
import {
  buildPortLayoutFromDesignModel,
  designCategoryToNodeKind,
  DESIGN_RAID_LEVEL_OPTIONS,
  DESIGN_SLOT_TYPE_OPTIONS,
  normalizeDesignLineCards,
  normalizeDesignSlots,
  resolveDesignSwitchRole,
  syncCoreLineCardsByHeight,
  syncSlotInterfaces,
  slotTypeLabel,
  type DesignSlotAttr,
  type DesignSlotInterface,
} from '@/utils/designModelToNode'
import {
  buildPanelPalette,
  ensurePanelLayout,
  getCustomAttributes,
  normalizePanelLayoutConfig,
  type CustomAttr,
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
  category: 'server',
  subtype: 'compute',
  manufacturer_name: '',
  vendor_sku: '',
  height_u: 1,
  description: '',
  attributes: {} as Record<string, unknown>,
})

const contractSummaries = ref<DeviceContractSummary[]>([])
const selectedSummaryKey = ref<string | null>(null)
const applyPanelDialogVisible = ref(false)
const applyPanelLoading = ref(false)

const selectedFolder = computed(() => findFolder(tree.value, selectedFolderId.value))
const selectedModel = computed(
  () => models.value.find((m) => m.id === selectedModelId.value) || null,
)

/** 规格字段（slot_count / slots / panel / custom 单独处理） */
const schemaFields = computed(() =>
  (attrSchema.value?.fields || []).filter(
    (f) => !['slots', 'slot_count', 'panel_layout', 'custom_attributes', 'switch_role', 'line_cards'].includes(f.key),
  ),
)

const isSwitchModel = computed(
  () => selectedModel.value?.category === 'network' && selectedModel.value?.subtype === 'switch',
)

const switchRole = computed<SwitchSubtype>(() => {
  const m = selectedModel.value
  if (!m?.attributes) return 'gigabit'
  return resolveDesignSwitchRole(m.attributes)
})

const switchLineCards = computed<CoreLineCard[]>(() => {
  const m = selectedModel.value
  if (!m?.attributes) return [newCoreLineCard('ten_gigabit', 48)]
  return normalizeDesignLineCards(m.attributes.line_cards)
})

const serverSlots = computed<DesignSlotAttr[]>(() => {
  const m = selectedModel.value
  if (!m || m.category !== 'server') return []
  const attrs = m.attributes || {}
  const raw = Array.isArray(attrs.slots) ? (attrs.slots as DesignSlotAttr[]) : []
  const count = Math.max(0, Math.min(16, Number(attrs.slot_count ?? raw.length ?? 0)))
  // 只读展示，避免在 computed 内 normalize 写回导致弹窗状态异常
  return raw.slice(0, count).map((s) => ({
    ...s,
    interfaces: Array.isArray(s.interfaces) ? s.interfaces.map((x) => ({ ...x })) : [],
  }))
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
  void m.attributes.fan_count
  void m.attributes.psu_count
  void m.attributes.data_port_count
  void m.attributes.wan_count
  void m.attributes.lan_count
  void m.attributes.service_port_count
  if (m.category === 'server') {
    return buildPanelPalette(m.attributes, serverSlots.value)
  }
  return buildPanelPalette(m.attributes, [])
})

const usesGridPanel = computed(() => selectedModel.value?.category !== 'software')

const customAttrs = computed<CustomAttr[]>(() => getCustomAttributes(selectedModel.value?.attributes))

const customDraft = reactive({ name: '', value: '' })

/** 属性驱动自动生成的面板简图（兼容合同应用） */
const autoPortLayout = computed<PortLayout | null>(() => {
  const m = selectedModel.value
  if (!m || m.category === 'software') return null
  void m.height_u
  void m.category
  void m.subtype
  void serverSlots.value
  void m.attributes?.slot_count
  void m.attributes?.switch_role
  void m.attributes?.downlink_count
  void m.attributes?.optical_card_count
  void m.attributes?.optical_ports_per_card
  void m.attributes?.uplink_count
  void m.attributes?.uplink_position
  void m.attributes?.downlink_type
  void m.attributes?.line_cards
  void m.attributes?.data_port_count
  void m.attributes?.panel_layout
  return buildPortLayoutFromDesignModel({ ...m, port_layout: null })
})

const applyNode = computed<NetworkNode | null>(() => {
  const m = selectedModel.value
  if (!m) return null
  const layout = autoPortLayout.value
  return {
    id: m.id,
    topology_id: '',
    kind: designCategoryToNodeKind(m.category),
    name: m.name,
    device_id: null,
    device_model_id: m.device_model_id,
    contract_device_name: m.contract_device_name,
    switch_port_count: 0,
    slots: null,
    pos_x: 0,
    pos_y: 0,
    on_canvas: false,
    port_layout: layout,
  }
})

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

const subtypeOptions = computed(() => {
  const cat = taxonomy.value.find((c) => c.value === modelForm.category)
  return cat?.subtypes || []
})

function categoryLabel(cat: string) {
  return taxonomy.value.find((c) => c.value === cat)?.label || cat
}

function subtypeLabel(cat: string, sub: string) {
  const c = taxonomy.value.find((x) => x.value === cat)
  return c?.subtypes.find((s) => s.value === sub)?.label || sub
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
  const schema = await fetchAttributeSchema(modelForm.category, modelForm.subtype)
  attrSchema.value = schema
  modelForm.attributes = { ...(schema?.default_attributes || {}) }
  if (modelForm.category === 'server') {
    modelForm.height_u = asInt(modelForm.attributes.form_factor_u, 1)
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
  modelForm.code = `M${Date.now().toString().slice(-6)}`
  modelForm.name = ''
  modelForm.category = 'server'
  modelForm.subtype = 'compute'
  modelForm.manufacturer_name = ''
  modelForm.vendor_sku = ''
  modelForm.height_u = 1
  modelForm.description = ''
  await loadSchemaForForm()
  modelDialogVisible.value = true
}

watch(
  () => [modelForm.category, modelForm.subtype],
  async () => {
    if (!modelDialogVisible.value) return
    const cat = taxonomy.value.find((c) => c.value === modelForm.category)
    if (cat && !cat.subtypes.some((s) => s.value === modelForm.subtype)) {
      modelForm.subtype = cat.subtypes[0]?.value || modelForm.subtype
    }
    await loadSchemaForForm()
  },
)

async function confirmCreateModel() {
  if (!selectedFolderId.value || !modelForm.code.trim() || !modelForm.name.trim()) {
    ElMessage.warning('请填写编号与名称')
    return
  }
  saving.value = true
  try {
    const attrs = { ...modelForm.attributes }
    if (modelForm.category === 'server') {
      attrs.form_factor_u = modelForm.height_u
      normalizeDesignSlots(attrs)
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
      height_u: modelForm.height_u,
      attributes: attrs,
      port_layout: null,
      device_model_id: null,
      contract_device_name: null,
      is_published: true,
      description: modelForm.description.trim() || null,
      created_at: '',
      updated_at: '',
    }
    const layout = buildPortLayoutFromDesignModel(draft)
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
      description: draft.description,
    })
    modelDialogVisible.value = false
    await refreshTree()
    await refreshModels()
    if (created?.id) selectedModelId.value = created.id
    ElMessage.success('模型已创建')
  } catch (err: unknown) {
    const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
    ElMessage.error(msg || '创建模型失败')
  } finally {
    saving.value = false
  }
}

async function onSelectedCategoryChange() {
  const m = selectedModel.value
  if (!m) return
  const cat = taxonomy.value.find((c) => c.value === m.category)
  m.subtype = cat?.subtypes[0]?.value || m.subtype
  attrSchema.value = await fetchAttributeSchema(m.category, m.subtype)
  m.attributes = { ...(attrSchema.value?.default_attributes || {}) }
  if (m.category === 'server') normalizeDesignSlots(m.attributes)
}

async function onSelectedSubtypeChange() {
  const m = selectedModel.value
  if (!m) return
  attrSchema.value = await fetchAttributeSchema(m.category, m.subtype)
  m.attributes = { ...(attrSchema.value?.default_attributes || {}) }
  if (m.category === 'server') normalizeDesignSlots(m.attributes)
}

async function selectModel(row: NetworkDesignModel) {
  selectedModelId.value = row.id
  selectedSummaryKey.value = null
  if (row.category) {
    attrSchema.value = await fetchAttributeSchema(row.category, row.subtype)
  }
  if (row.category === 'server' && row.attributes) {
    const slots = normalizeDesignSlots(row.attributes)
    ensurePanelLayout(row.attributes, slots, false)
  }
  if (row.category === 'network' && row.subtype === 'switch' && row.attributes) {
    row.attributes.switch_role = resolveDesignSwitchRole(row.attributes)
    if (row.attributes.switch_role === 'core') {
      syncCoreLineCardsByHeight(row.attributes, Math.max(1, Number(row.height_u) || 1))
    } else {
      // 千兆/万兆：确保板卡字段存在，设备配置及组件栏才能列出板卡/上联
      const cards = Math.max(1, Math.min(16, Number(row.attributes.optical_card_count) || 1))
      let ppc = Number(row.attributes.optical_ports_per_card) || 0
      if (ppc <= 0) {
        const total = Math.max(1, Number(row.attributes.downlink_count) || 48)
        ppc = Math.max(1, Math.min(128, Math.floor(total / cards)))
      }
      row.attributes.optical_card_count = cards
      row.attributes.optical_ports_per_card = ppc
      row.attributes.downlink_count = Math.max(1, Math.min(256, cards * ppc))
    }
    if (row.attributes.fan_count == null) row.attributes.fan_count = 2
    if (row.attributes.psu_count == null) row.attributes.psu_count = 2
    ensurePanelLayout(row.attributes, [], false)
  }
  if (
    row.attributes &&
    row.category !== 'software' &&
    row.category !== 'server' &&
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
      if (attrs.disk_rear_count != null) {
        attrs.disk_rear_count = Math.max(0, Math.min(4, asInt(attrs.disk_rear_count, 0)))
      }
      normalizeDesignSlots(attrs)
      m.attributes = attrs
    }
    if (m.category === 'network' && m.subtype === 'switch') {
      attrs.switch_role = resolveDesignSwitchRole(attrs)
      if (attrs.switch_role === 'core') {
        syncCoreLineCardsByHeight(attrs, Math.max(1, Number(m.height_u) || 1))
      } else {
        const cards = Math.max(1, Math.min(16, Number(attrs.optical_card_count) || 1))
        let ppc = Number(attrs.optical_ports_per_card) || 0
        if (ppc <= 0) {
          const total = Math.max(1, Number(attrs.downlink_count) || 48)
          ppc = Math.max(1, Math.min(128, Math.floor(total / cards)))
        }
        attrs.optical_card_count = cards
        attrs.optical_ports_per_card = ppc
        attrs.downlink_count = Math.max(1, Math.min(256, cards * ppc))
      }
      attrs.chassis_height_u = m.height_u
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
    normalizeDesignSlots(m.attributes)
  }
  if (
    m.category === 'server' &&
    [
      'psu_count',
      'bmc_ports',
      'usb_ports',
      'slot_count',
      'disk_front_count',
      'disk_rear_count',
      'fan_count',
    ].includes(key)
  ) {
    ensurePanelLayout(m.attributes, normalizeDesignSlots(m.attributes), false)
  }
  if (
    m.category === 'network' &&
    m.subtype === 'switch' &&
    [
      'switch_role',
      'downlink_count',
      'optical_card_count',
      'optical_ports_per_card',
      'uplink_count',
      'uplink_position',
      'fan_count',
      'psu_count',
      'line_cards',
    ].includes(key)
  ) {
    ensurePanelLayout(m.attributes, [], false)
  }
}

function refreshSwitchPanelLayout() {
  const m = selectedModel.value
  if (!m?.attributes || !isSwitchModel.value) return
  ensurePanelLayout(m.attributes, [], false)
}

function syncCoreCardsFromModelHeight() {
  const m = selectedModel.value
  if (!m?.attributes || !isSwitchModel.value) return
  if (resolveDesignSwitchRole(m.attributes) !== 'core') return
  const h = Math.max(1, Math.min(16, Number(m.height_u) || 1))
  m.height_u = h
  syncCoreLineCardsByHeight(m.attributes, h)
  refreshSwitchPanelLayout()
}

function onSwitchRoleChange(role: SwitchSubtype) {
  const m = selectedModel.value
  if (!m) return
  if (!m.attributes) m.attributes = {}
  const defaults = SWITCH_SUBTYPE_DEFAULTS[role]
  m.attributes.switch_role = role
  if (role === 'core') {
    m.attributes.downlink_count = 0
    m.attributes.uplink_count = 0
    if (!m.height_u || m.height_u < 2) m.height_u = 4
    syncCoreLineCardsByHeight(m.attributes, m.height_u)
  } else {
    m.attributes.downlink_type = defaults.mainType
    m.attributes.uplink_type = defaults.uplinkType
    m.attributes.uplink_count = defaults.uplinkPortCount
    m.attributes.optical_card_count = 1
    m.attributes.optical_ports_per_card = defaults.mainPortCount
    m.attributes.downlink_count = defaults.mainPortCount
    if (m.attributes.uplink_position !== 'middle' && m.attributes.uplink_position !== 'right') {
      m.attributes.uplink_position = 'right'
    }
  }
  if (m.attributes.fan_count == null) m.attributes.fan_count = 2
  if (m.attributes.psu_count == null) m.attributes.psu_count = 2
  refreshSwitchPanelLayout()
}

function onSwitchMainCountChange(v: number | undefined) {
  setAttrField('downlink_count', Math.max(1, Math.min(128, v ?? 48)))
}

/** 千兆/万兆/汇聚：板卡数 × 每板口数 → 下联总口数 */
function syncAccessSwitchPorts() {
  const m = selectedModel.value
  if (!m?.attributes) return
  const cards = Math.max(1, Math.min(16, Number(m.attributes.optical_card_count) || 1))
  const ppc = Math.max(1, Math.min(128, Number(m.attributes.optical_ports_per_card) || 48))
  m.attributes.optical_card_count = cards
  m.attributes.optical_ports_per_card = ppc
  m.attributes.downlink_count = Math.max(1, Math.min(256, cards * ppc))
  refreshSwitchPanelLayout()
}

function onOpticalCardCountChange(v: number | undefined) {
  const m = selectedModel.value
  if (!m?.attributes) return
  m.attributes.optical_card_count = Math.max(1, Math.min(16, v ?? 1))
  if (!m.attributes.optical_ports_per_card) {
    m.attributes.optical_ports_per_card = 48
  }
  syncAccessSwitchPorts()
}

function onOpticalPortsPerCardChange(v: number | undefined) {
  const m = selectedModel.value
  if (!m?.attributes) return
  m.attributes.optical_ports_per_card = Math.max(1, Math.min(128, v ?? 48))
  if (!m.attributes.optical_card_count) {
    m.attributes.optical_card_count = 1
  }
  syncAccessSwitchPorts()
}

function onSwitchUplinkCountChange(v: number | undefined) {
  const role = switchRole.value
  let next = Math.max(0, Math.min(8, v ?? 0))
  if (role === 'gigabit') next = normalizeGigabitUplinkCount(next)
  else if (role === 'ten_gigabit' || role === 'aggregation') next = normalizeTenGigabitUplinkCount(next)
  setAttrField('uplink_count', next)
}

function onSwitchUplinkPositionChange(v: UplinkPosition) {
  setAttrField('uplink_position', v)
}

function syncSwitchLineCards(cards: CoreLineCard[]) {
  const m = selectedModel.value
  if (!m) return
  if (!m.attributes) m.attributes = {}
  m.attributes.line_cards = cards.map((c) => ({ ...c }))
  refreshSwitchPanelLayout()
}

function onSwitchLineCardTypeChange(idx: number, cardType: string) {
  const cards = switchLineCards.value.map((c) => ({ ...c }))
  const card = cards[idx]
  if (!card) return
  card.card_type = cardType as CoreLineCard['card_type']
  card.port_count = card.card_type === 'blank' ? 0 : Math.max(1, card.port_count || 48)
  syncSwitchLineCards(cards)
}

function onSwitchLineCardPortCountChange(idx: number, count: number | undefined) {
  const cards = switchLineCards.value.map((c) => ({ ...c }))
  const card = cards[idx]
  if (!card || card.card_type === 'blank') return
  card.port_count = Math.max(1, Math.min(128, count ?? 48))
  syncSwitchLineCards(cards)
}

watch(
  () => [selectedModel.value?.id, selectedModel.value?.height_u, switchRole.value] as const,
  () => {
    if (!isSwitchModel.value || switchRole.value !== 'core') return
    syncCoreCardsFromModelHeight()
  },
)

function onSlotTypeChange(index: number, type: string) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const slots = normalizeDesignSlots(m.attributes)
  const slot = slots[index]
  if (!slot) return
  slot.type = type
  if (type === 'nic_1g' || type === 'nic_10g') {
    slot.port_count = slot.port_count && slot.port_count > 0 ? slot.port_count : 2
    delete slot.raid_level
  } else if (type === 'raid') {
    slot.raid_level = slot.raid_level || 'raid1'
    slot.port_count = 0
  } else if (type === 'blank') {
    slot.port_count = 0
    delete slot.raid_level
  } else {
    slot.port_count = slot.port_count && slot.port_count > 0 ? slot.port_count : 1
    delete slot.raid_level
  }
  syncSlotInterfaces(slot)
  m.attributes.slots = [...slots]
  // 强制刷新面板标签
  ensurePanelLayout(m.attributes, slots)
}

function onSlotPortCountChange(index: number, count: number | undefined) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const slots = normalizeDesignSlots(m.attributes)
  if (!slots[index]) return
  slots[index].port_count = Math.max(1, Math.min(8, count ?? 1))
  syncSlotInterfaces(slots[index])
  m.attributes.slots = [...slots]
}

function onSlotRaidLevelChange(index: number, level: string) {
  const m = selectedModel.value
  if (!m?.attributes) return
  const slots = normalizeDesignSlots(m.attributes)
  if (!slots[index]) return
  slots[index].raid_level = level
  m.attributes.slots = [...slots]
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
  // 再次确保千兆/万兆接口类型与 Slot 一致
  if (synced.type === 'nic_1g' || synced.type === 'nic_10g') {
    const def = synced.type === 'nic_1g' ? '1g' : '10g'
    synced.interfaces = (synced.interfaces || []).map((x) => ({ ...x, port_type: def }))
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
      return {
        ...it,
        label: `S${next.index}:${slotTypeLabel(String(next.type)).replace('接口', '').slice(0, 2)}`,
        slot_index: next.index,
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

function addCustomAttr() {
  const m = selectedModel.value
  if (!m || !canEdit.value) return
  const name = customDraft.name.trim()
  if (!name) {
    ElMessage.warning('请填写属性名称')
    return
  }
  if (!m.attributes) m.attributes = {}
  const list = getCustomAttributes(m.attributes)
  list.push({ name, value: customDraft.value.trim() })
  m.attributes.custom_attributes = list
  customDraft.name = ''
  customDraft.value = ''
}

function removeCustomAttr(idx: number) {
  const m = selectedModel.value
  if (!m?.attributes || !canEdit.value) return
  const list = getCustomAttributes(m.attributes)
  list.splice(idx, 1)
  m.attributes.custom_attributes = list
}

function resetPanelAutoPlace() {
  const m = selectedModel.value
  if (!m?.attributes || !canEdit.value || m.category === 'software') return
  if (m.category === 'server') {
    ensurePanelLayout(m.attributes, normalizeDesignSlots(m.attributes), true)
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
    if (m.contract_device_name && (!m.name || m.name.startsWith('M'))) {
      m.name = m.contract_device_name
    }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '关联合同型号失败'
    ElMessage.error(msg)
  }
}

async function openApplyPanel() {
  const m = selectedModel.value
  if (!m) return
  if (!m.device_model_id || !m.contract_device_name) {
    ElMessage.warning('请先关联合同厂商型号采购汇总中的设备名称')
    return
  }
  applyPanelLoading.value = true
  try {
    await saveSelectedModel()
    applyPanelDialogVisible.value = true
  } finally {
    applyPanelLoading.value = false
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
        <el-table-column prop="name" label="名称" min-width="180">
          <template #default="{ row }">
            <div class="model-name-cell">
              <TopologyDeviceIcon
                v-bind="designModelIconProps(row)"
                :size="40"
                :selected="row.id === selectedModelId"
              />
              <span class="model-name-text">{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="分类" width="120">
          <template #default="{ row }">
            {{ categoryLabel(row.category) }}
          </template>
        </el-table-column>
        <el-table-column label="子类型" width="120">
          <template #default="{ row }">
            {{ subtypeLabel(row.category, row.subtype) }}
          </template>
        </el-table-column>
        <el-table-column prop="code" label="编号" width="110" />
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
                <el-option v-for="c in taxonomy" :key="c.value" :label="c.label" :value="c.value" />
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

          <template v-if="selectedModel.category === 'server'">
            <div class="sec-title">配置属性</div>
            <el-form label-position="left" label-width="88px" size="small" class="attr-grid-form">
              <el-form-item label="CPU个数">
                <el-input-number
                  :model-value="Number(attrFieldValue('cpu_sockets') ?? 0)"
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
                  :model-value="Number(attrFieldValue('cpu_cores_per_socket') ?? 0)"
                  :min="1"
                  :max="128"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('cpu_cores_per_socket', v ?? 1)"
                />
              </el-form-item>
              <el-form-item label="内存条大小">
                <el-input-number
                  :model-value="Number(attrFieldValue('memory_module_gb') ?? 0)"
                  :min="1"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('memory_module_gb', v ?? 1)"
                />
              </el-form-item>
              <el-form-item label="条数">
                <el-input-number
                  :model-value="Number(attrFieldValue('memory_modules') ?? 0)"
                  :min="1"
                  :max="64"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('memory_modules', v ?? 1)"
                />
              </el-form-item>
              <el-form-item label="电源数量">
                <el-input-number
                  :model-value="Number(attrFieldValue('psu_count') ?? 0)"
                  :min="1"
                  :max="8"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('psu_count', v ?? 1)"
                />
              </el-form-item>
              <el-form-item label="电源功率">
                <el-input-number
                  :model-value="Number(attrFieldValue('psu_watt') ?? 0)"
                  :min="100"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('psu_watt', v ?? 100)"
                />
              </el-form-item>
              <el-form-item label="扩展Slot数">
                <el-input-number
                  :model-value="Number(attrFieldValue('slot_count') ?? 0)"
                  :min="0"
                  :max="16"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('slot_count', v ?? 0)"
                />
              </el-form-item>
            </el-form>

            <div class="sec-title">接口属性</div>
            <el-form label-position="left" label-width="120px" size="small" class="attr-grid-form">
              <el-form-item label="IPMI/BMC接口数">
                <el-input-number
                  :model-value="Number(attrFieldValue('bmc_ports') ?? 0)"
                  :min="0"
                  :max="4"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('bmc_ports', v ?? 0)"
                />
              </el-form-item>
              <el-form-item label="USB接口">
                <el-input-number
                  :model-value="Number(attrFieldValue('usb_ports') ?? 0)"
                  :min="0"
                  :max="8"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('usb_ports', v ?? 0)"
                />
              </el-form-item>
              <el-form-item label="前面板硬盘插槽">
                <el-input-number
                  :model-value="Number(attrFieldValue('disk_front_count') ?? 0)"
                  :min="0"
                  :max="48"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('disk_front_count', v ?? 0)"
                />
              </el-form-item>
              <el-form-item label="后面板插槽">
                <el-input-number
                  :model-value="Number(attrFieldValue('disk_rear_count') ?? 0)"
                  :min="0"
                  :max="4"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('disk_rear_count', v ?? 0)"
                />
              </el-form-item>
              <el-form-item label="风扇个数">
                <el-input-number
                  :model-value="Number(attrFieldValue('fan_count') ?? 0)"
                  :min="0"
                  :max="16"
                  :controls="false"
                  :disabled="!canEdit"
                  class="num-compact"
                  @change="(v: number | undefined) => setAttrField('fan_count', v ?? 0)"
                />
              </el-form-item>
            </el-form>

            <div class="sec-title">扩展Slot明细</div>
            <div class="slot-grid">
              <div v-for="(slot, idx) in serverSlots" :key="slot.index" class="slot-card">
                <span class="slot-idx">Slot {{ slot.index }}</span>
                <el-select
                  :model-value="slot.type"
                  size="small"
                  :disabled="!canEdit"
                  class="slot-type"
                  @change="(v: string) => onSlotTypeChange(idx, v)"
                >
                  <el-option
                    v-for="opt in DESIGN_SLOT_TYPE_OPTIONS"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
                <template v-if="slot.type === 'nic_1g' || slot.type === 'nic_10g'">
                  <span class="slot-lab">接口数</span>
                  <el-input-number
                    :model-value="slot.port_count ?? 2"
                    :min="1"
                    :max="8"
                    :controls="false"
                    size="small"
                    class="slot-num"
                    :disabled="!canEdit"
                    @change="(v: number | undefined) => onSlotPortCountChange(idx, v)"
                  />
                </template>
                <template v-else-if="slot.type === 'raid'">
                  <span class="slot-lab">RAID</span>
                  <el-select
                    :model-value="slot.raid_level || 'raid1'"
                    size="small"
                    :disabled="!canEdit"
                    class="slot-raid"
                    @change="(v: string) => onSlotRaidLevelChange(idx, v)"
                  >
                    <el-option
                      v-for="opt in DESIGN_RAID_LEVEL_OPTIONS"
                      :key="opt.value"
                      :label="opt.label"
                      :value="opt.value"
                    />
                  </el-select>
                </template>
                <template v-else-if="slot.type === 'disk_bay'">
                  <span class="slot-lab">盘位数</span>
                  <el-input-number
                    :model-value="slot.port_count ?? 1"
                    :min="1"
                    :max="8"
                    :controls="false"
                    size="small"
                    class="slot-num"
                    :disabled="!canEdit"
                    @change="(v: number | undefined) => onSlotPortCountChange(idx, v)"
                  />
                </template>
                <span v-else class="slot-lab muted">空白卡槽</span>
              </div>
            </div>
          </template>

          <template v-else-if="isSwitchModel">
            <div class="sec-title">交换机接口样式</div>
            <el-form label-position="left" label-width="120px" size="small" class="attr-grid-form">
              <el-form-item label="设备样式" class="span-2">
                <el-select
                  :model-value="switchRole"
                  :disabled="!canEdit"
                  style="width: 100%"
                  @change="(v: SwitchSubtype) => onSwitchRoleChange(v)"
                >
                  <el-option
                    v-for="key in (['gigabit', 'ten_gigabit', 'core'] as const)"
                    :key="key"
                    :label="SWITCH_SUBTYPE_LABELS[key]"
                    :value="key"
                  />
                </el-select>
              </el-form-item>

              <template v-if="switchRole === 'gigabit' || switchRole === 'ten_gigabit' || switchRole === 'aggregation'">
                <el-form-item label="板卡数">
                  <el-input-number
                    :model-value="Number(attrFieldValue('optical_card_count') ?? 1)"
                    :min="1"
                    :max="16"
                    :controls="false"
                    :disabled="!canEdit"
                    class="num-compact"
                    @change="onOpticalCardCountChange"
                  />
                </el-form-item>
                <el-form-item :label="switchRole === 'gigabit' ? '电口个数' : '光口个数'">
                  <el-input-number
                    :model-value="Number(attrFieldValue('optical_ports_per_card') ?? 48)"
                    :min="1"
                    :max="128"
                    :controls="false"
                    :disabled="!canEdit"
                    class="num-compact"
                    @change="onOpticalPortsPerCardChange"
                  />
                </el-form-item>
                <el-form-item :label="switchRole === 'gigabit' ? '总电口' : '总光口'" class="span-2">
                  <span class="field-static">
                    {{
                      Math.max(1, Number(attrFieldValue('optical_card_count') ?? 1)) *
                        Math.max(1, Number(attrFieldValue('optical_ports_per_card') ?? 48))
                    }}
                    （板卡数 × {{ switchRole === 'gigabit' ? '电口' : '光口' }}个数）
                  </span>
                </el-form-item>
                <el-form-item :label="switchRole === 'gigabit' ? '上联光口数量' : '40/100G上联'">
                  <el-input-number
                    :model-value="Number(attrFieldValue('uplink_count') ?? 4)"
                    :min="0"
                    :max="8"
                    :step="switchRole === 'gigabit' ? 1 : 2"
                    :controls="false"
                    :disabled="!canEdit"
                    class="num-compact"
                    @change="onSwitchUplinkCountChange"
                  />
                </el-form-item>
                <el-form-item label="上联位置" class="span-2">
                  <el-radio-group
                    :model-value="(attrFieldValue('uplink_position') as string) || 'right'"
                    :disabled="!canEdit"
                    @change="(v: string) => onSwitchUplinkPositionChange(v as UplinkPosition)"
                  >
                    <el-radio
                      v-for="(label, key) in UPLINK_POSITION_LABELS"
                      :key="key"
                      :value="key"
                    >
                      {{ label }}
                    </el-radio>
                  </el-radio-group>
                </el-form-item>
                <p class="panel-hint span-2">
                  <template v-if="switchRole === 'gigabit'">
                    千兆样式：按板卡拆分 1G 电口，上联 10G；大于 4 个上联须为偶数并两排显示。
                  </template>
                  <template v-else>
                    万兆样式：按板卡拆分 10G 光口，上联 40/100G QSFP 两排向右扩展。
                  </template>
                </p>
              </template>

              <template v-else>
                <p class="panel-hint span-2">
                  核心交换机（高度≥2U 时多槽）：板卡数=高度(U)；每槽可选千兆/万兆/100G/空白板卡，有口板卡在前面板放置后接口自动均分。
                </p>
              </template>

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
              <el-form-item label="电源数量">
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

            <template v-if="switchRole === 'core' && Number(selectedModel.height_u || 1) > 2">
              <div class="sec-title-row">
                <span class="sec-title">线卡板卡（共 {{ switchLineCards.length }} 槽 = {{ selectedModel.height_u }}U）</span>
              </div>
              <p class="panel-hint">可为每槽选择接口类型与数量；空白板卡无接口。放置到前面板后接口按数量自动均分。</p>
              <div class="slot-grid">
                <div v-for="(card, idx) in switchLineCards" :key="card.id" class="slot-card">
                  <span class="slot-idx">卡 {{ idx + 1 }}</span>
                  <el-select
                    :model-value="card.card_type"
                    size="small"
                    :disabled="!canEdit"
                    class="slot-type"
                    @change="(v: string) => onSwitchLineCardTypeChange(idx, v)"
                  >
                    <el-option
                      v-for="(label, key) in CORE_CARD_TYPE_LABELS"
                      :key="key"
                      :label="label"
                      :value="key"
                    />
                  </el-select>
                  <template v-if="card.card_type !== 'blank'">
                    <span class="slot-lab">接口数</span>
                    <el-input-number
                      :model-value="card.port_count"
                      :min="1"
                      :max="128"
                      :controls="false"
                      size="small"
                      class="slot-num"
                      :disabled="!canEdit"
                      @change="(v: number | undefined) => onSwitchLineCardPortCountChange(idx, v)"
                    />
                  </template>
                  <span v-else class="slot-lab muted">空白</span>
                </div>
              </div>
            </template>
            <template v-else-if="switchRole === 'core'">
              <p class="panel-hint">核心交换机高度超过 2U 后按 U 数展开线卡槽；当前 ≤2U，可先调高「高度(U)」再配置板卡。</p>
            </template>
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

          <div class="sec-title">自定义属性</div>
          <div class="custom-row">
            <span class="slot-lab">属性名称</span>
            <el-input v-model="customDraft.name" size="small" class="custom-name" :disabled="!canEdit" />
            <span class="slot-lab">属性值</span>
            <el-input v-model="customDraft.value" size="small" class="custom-val" :disabled="!canEdit" />
            <el-button link type="primary" :disabled="!canEdit" @click="addCustomAttr">添加属性</el-button>
          </div>
          <div v-if="customAttrs.length" class="custom-list">
            <div v-for="(ca, i) in customAttrs" :key="i" class="custom-item">
              <span>{{ ca.name }}</span>
              <span class="muted">{{ ca.value }}</span>
              <el-button link type="danger" size="small" :disabled="!canEdit" @click="removeCustomAttr(i)">删除</el-button>
            </div>
          </div>

          <div class="sec-title">合同应用</div>
          <el-form label-position="left" label-width="72px" size="small" class="attr-grid-form">
            <el-form-item label="合同设备" class="span-3">
              <el-select
                v-model="selectedSummaryKey"
                filterable
                clearable
                placeholder="关联采购汇总设备名称"
                style="width: 100%"
                :disabled="!canEdit"
                @focus="() => { if (!contractSummaries.length) loadContractSummaries() }"
                @change="onSummaryChange"
              >
                <el-option
                  v-for="sum in contractSummaries"
                  :key="summaryOptionKey(sum)"
                  :label="formatSummaryOptionLabel(sum)"
                  :value="summaryOptionKey(sum)"
                />
              </el-select>
            </el-form-item>
            <el-form-item label-width="0" class="span-1 apply-item">
              <el-button
                type="primary"
                plain
                :loading="applyPanelLoading"
                :disabled="!canEdit || !selectedModel.contract_device_name"
                @click="openApplyPanel"
              >
                应用到合同设备
              </el-button>
            </el-form-item>
          </el-form>

          <div class="sec-title">说明</div>
          <el-input
            v-model="selectedModel.description"
            type="textarea"
            :rows="2"
            placeholder="模型说明"
            :disabled="!canEdit"
            class="desc-before-panel"
          />

          <template v-if="usesGridPanel">
            <div class="sec-title-row">
              <span class="sec-title">面板样式</span>
              <el-button v-if="canEdit" link type="primary" size="small" @click="resetPanelAutoPlace">
                在当前尺寸内自动定位
              </el-button>
            </div>
            <p class="panel-hint">
              {{
                isSwitchModel
                  ? '点选组件后拖拽框选放置；口数自动按交换机双排紧凑均分，空板卡无接口。'
                  : '点选组件后在面板上拖拽框选范围进行放置。'
              }}
            </p>
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

    <el-dialog v-model="modelDialogVisible" title="新建模型" width="560px">
      <el-form label-width="100px">
        <el-form-item label="编号" required>
          <el-input v-model="modelForm.code" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="modelForm.name" />
        </el-form-item>
        <el-form-item label="分类" required>
          <el-select v-model="modelForm.category" style="width: 100%">
            <el-option v-for="c in taxonomy" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="子类型" required>
          <el-select v-model="modelForm.subtype" style="width: 100%">
            <el-option
              v-for="s in subtypeOptions"
              :key="s.value"
              :label="s.label"
              :value="s.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="modelForm.category !== 'software'" label="高度(U)">
          <el-input-number v-model="modelForm.height_u" :min="1" :max="48" />
        </el-form-item>
        <el-form-item label="厂商">
          <el-input v-model="modelForm.manufacturer_name" />
        </el-form-item>
        <el-alert
          type="info"
          :closable="false"
          title="创建后可在右侧继续完善 CPU/内存/Slot、上下联口、安全板卡口、软件授权等属性，并可应用到合同设备名称。"
        />
      </el-form>
      <template #footer>
        <el-button @click="modelDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="confirmCreateModel">创建</el-button>
      </template>
    </el-dialog>

    <ApplyPanelToDevicesDialog
      v-model="applyPanelDialogVisible"
      :node="applyNode"
      @done="ElMessage.success('已应用到设备清单')"
    />
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
.model-name-text {
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
.slot-idx {
  font-size: 12px;
  font-weight: 600;
  min-width: 48px;
}
.slot-lab {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.slot-type {
  width: 118px;
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
.panel-hint {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
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
