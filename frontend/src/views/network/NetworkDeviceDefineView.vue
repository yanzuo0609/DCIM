<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import NetworkDeviceFrameEditor from '@/components/NetworkDeviceFrameEditor.vue'
import ApplyPanelToDevicesDialog from '@/components/ApplyPanelToDevicesDialog.vue'
import { useNetworkTopology } from '@/composables/useNetworkTopology'
import {
  CORE_CARD_TYPE_LABELS,
  NODE_KIND_LABELS,
  PORT_TYPE_LABELS,
  SERVER_FORM_FACTOR_LABELS,
  SWITCH_SUBTYPE_DEFAULTS,
  SWITCH_SUBTYPE_LABELS,
  UPLINK_POSITION_LABELS,
  newCoreLineCard,
  type CoreCardType,
  type CoreLineCard,
  type FramePort,
  type NetworkNode,
  type NetworkNodeKind,
  type PortType,
  type ServerFormFactor,
  type SwitchSubtype,
  type UplinkPosition,
} from '@/api/network'
import { getContractSummary, type DeviceContractSummary } from '@/api/contract'
import { useAuthStore } from '@/stores/auth'
import {
  formatSummaryOptionLabel,
  resolveModelFromSummary,
  summaryOptionKey,
} from '@/utils/contractModelBind'
import {
  applySecurityLayoutConfig,
  applySwitchLayoutConfig,
  defaultPortLayout,
  ensurePortLayout,
  generatePortsFromSlotsDef,
  RACK_WIDTH_MM,
  syncLegacyFromPortLayout,
  syncLinksFromPortLayout,
} from '@/utils/networkPortLayout'
import { normalizeGigabitUplinkCount, normalizeTenGigabitUplinkCount } from '@/utils/switchFrontPanel'
import { applyServerFormFactor, defaultServerSlotsDef } from '@/utils/serverRearPanel'
import { SEC_FRAME_HEIGHT_BY_U, defaultSecurityZones } from '@/utils/securityFrontPanel'

const auth = useAuthStore()
const {
  projects,
  currentProjectId,
  currentProject,
  currentId,
  nodes,
  links,
  loading,
  saving,
  loadProjects,
  selectProject,
  createProject,
  editProject,
  removeProject,
  saveCanvas,
} = useNetworkTopology()

const canEdit = computed(() => auth.hasPermission('network:update'))
const canCreate = computed(() => auth.hasPermission('network:create'))
const canDelete = computed(() => auth.hasPermission('network:delete'))

/** 项目内可扩展子功能模块（后续可继续追加） */
interface ProjectModuleItem {
  id: string
  label: string
  kind?: NetworkNodeKind
  needTopology?: boolean
  disabled?: boolean
}

interface ProjectModule {
  id: string
  label: string
  items: ProjectModuleItem[]
}

const projectModules = computed<ProjectModule[]>(() => [
  {
    id: 'device-types',
    label: '设备类型',
    items: [
      {
        id: 'add-switch',
        label: '添加网络设备类型',
        kind: 'switch',
        needTopology: true,
        disabled: !canEdit.value || !currentId.value,
      },
      {
        id: 'add-server',
        label: '添加服务器类型',
        kind: 'server',
        needTopology: true,
        disabled: !canEdit.value || !currentId.value,
      },
      {
        id: 'add-security',
        label: '添加安全设备类型',
        kind: 'security',
        needTopology: true,
        disabled: !canEdit.value || !currentId.value,
      },
    ],
  },
])

const contractSummaries = ref<DeviceContractSummary[]>([])
const summaryLoading = ref(false)
const applyPanelLoading = ref(false)
const applyPanelDialogVisible = ref(false)
const selectedSummaryKey = ref<string | null>(null)
const selectedNodeId = ref<string | null>(null)
/** 展开行（单行展开编辑） */
const expandedRowKeys = ref<string[]>([])
const frameEditorRef = ref<{
  openPeerDialog: (port: FramePort) => void
  openPortEdit: (port: FramePort) => void
  onPortClick: (port: FramePort) => void
} | null>(null)
const basicVisible = ref(false)
const projectDialogVisible = ref(false)
const projectDialogMode = ref<'create' | 'edit'>('create')
const projectForm = reactive({
  code: '',
  name: '',
  description: '',
})
const projectSaving = ref(false)
const basicForm = reactive({
  kind: 'switch' as NetworkNodeKind,
  name: '',
  switch_subtype: 'gigabit' as SwitchSubtype,
  main_port_count: 48,
  uplink_port_count: 4,
  uplink_position: 'right' as UplinkPosition,
  line_cards: [newCoreLineCard('ten_gigabit', 48)] as CoreLineCard[],
  server_form_factor: 1 as ServerFormFactor,
  security_height_u: 1,
})

const isCoreSwitch = computed(() => basicForm.kind === 'switch' && basicForm.switch_subtype === 'core')
const isGigabitSwitch = computed(() => basicForm.kind === 'switch' && basicForm.switch_subtype === 'gigabit')
const isTenGigabitSwitch = computed(
  () => basicForm.kind === 'switch' && basicForm.switch_subtype === 'ten_gigabit',
)
const isAggregationSwitch = computed(
  () => basicForm.kind === 'switch' && basicForm.switch_subtype === 'aggregation',
)
const isCreateServer = computed(() => basicForm.kind === 'server')
const isCreateSecurity = computed(() => basicForm.kind === 'security')

const selectedNode = computed(
  () => nodes.value.find((n) => n.id === selectedNodeId.value) || null,
)

const peerNodes = computed(() =>
  nodes.value.filter((n) => n.id !== selectedNodeId.value),
)

function openCreate(kind: NetworkNodeKind) {
  if (!currentId.value || !currentProjectId.value) {
    ElMessage.warning('请先创建或选择项目')
    return
  }
  basicForm.kind = kind
  basicForm.name = `${NODE_KIND_LABELS[kind]}${nodes.value.filter((n) => n.kind === kind).length + 1}`
  if (kind === 'switch') {
    basicForm.switch_subtype = 'gigabit'
    basicForm.main_port_count = 48
    basicForm.uplink_port_count = 4
    basicForm.uplink_position = 'right'
    basicForm.line_cards = [newCoreLineCard('ten_gigabit', 48)]
    lastCreateUplinkCount.value = 4
  }
  if (kind === 'server') {
    basicForm.server_form_factor = 1
  }
  if (kind === 'security') {
    basicForm.security_height_u = 1
  }
  basicVisible.value = true
}

function onProjectModuleCommand(command: string) {
  for (const mod of projectModules.value) {
    const item = mod.items.find((i) => i.id === command)
    if (!item) continue
    if (item.disabled) {
      if (item.needTopology && !currentId.value) {
        ElMessage.warning('请先选择或新建项目后再添加设备类型')
      }
      return
    }
    if (item.kind) openCreate(item.kind)
    return
  }
}

function openCreateProject() {
  projectDialogMode.value = 'create'
  projectForm.code = ''
  projectForm.name = ''
  projectForm.description = ''
  projectDialogVisible.value = true
}

function openEditProject() {
  if (!currentProject.value) return
  projectDialogMode.value = 'edit'
  projectForm.code = currentProject.value.code
  projectForm.name = currentProject.value.name
  projectForm.description = currentProject.value.description || ''
  projectDialogVisible.value = true
}

async function confirmProjectDialog() {
  if (!projectForm.code.trim() || !projectForm.name.trim()) {
    ElMessage.warning('请填写项目编码与名称')
    return
  }
  projectSaving.value = true
  try {
    if (projectDialogMode.value === 'create') {
      await createProject({
        code: projectForm.code,
        name: projectForm.name,
        description: projectForm.description || null,
      })
      ElMessage.success('项目已创建')
    } else if (currentProjectId.value) {
      await editProject(currentProjectId.value, {
        code: projectForm.code,
        name: projectForm.name,
        description: projectForm.description || null,
      })
      ElMessage.success('项目已更新')
    }
    projectDialogVisible.value = false
  } catch (err: unknown) {
    const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
    ElMessage.error(msg || '操作失败')
  } finally {
    projectSaving.value = false
  }
}

async function handleRemoveProject() {
  await removeProject()
}

async function onProjectChange(id: string) {
  if (!id || id === currentProjectId.value) return
  selectedNodeId.value = null
  expandedRowKeys.value = []
  await selectProject(id)
  if (nodes.value.length) {
    selectNode(nodes.value[0])
    expandedRowKeys.value = [nodes.value[0].id]
  }
}

function onSwitchSubtypeChange(subtype: SwitchSubtype) {
  const defaults = SWITCH_SUBTYPE_DEFAULTS[subtype]
  basicForm.main_port_count = defaults.mainPortCount
  basicForm.uplink_port_count = defaults.uplinkPortCount
  lastCreateUplinkCount.value = defaults.uplinkPortCount
  if (subtype === 'core' && !basicForm.line_cards.length) {
    basicForm.line_cards = [newCoreLineCard('ten_gigabit', 48)]
  }
}

const lastCreateUplinkCount = ref(4)

function onCreateGigabitUplinkChange(val: number | undefined) {
  if (val == null) return
  const next = normalizeGigabitUplinkCount(val, lastCreateUplinkCount.value)
  basicForm.uplink_port_count = next
  lastCreateUplinkCount.value = next
}

function onCreateTenGigabitUplinkChange(val: number | undefined) {
  if (val == null) return
  const next = normalizeTenGigabitUplinkCount(val, lastCreateUplinkCount.value)
  basicForm.uplink_port_count = next
  lastCreateUplinkCount.value = next
}

function addLineCard() {
  if (basicForm.line_cards.length >= 16) return
  basicForm.line_cards.push(newCoreLineCard('ten_gigabit', 48))
}

function removeLineCard(idx: number) {
  if (basicForm.line_cards.length <= 1) return
  basicForm.line_cards.splice(idx, 1)
}

function onCreateLineCardTypeChange(card: CoreLineCard) {
  if (card.card_type === 'blank') card.port_count = 0
  else if (!card.port_count || card.port_count < 1) card.port_count = 48
}

function confirmCreate() {
  if (!basicForm.name.trim() || !currentId.value) return
  if (basicForm.kind === 'switch' && basicForm.switch_subtype === 'core' && !basicForm.line_cards.length) {
    ElMessage.warning('请至少定义一块板卡')
    return
  }
  const securityHeightU = basicForm.kind === 'security' && Number(basicForm.security_height_u) >= 2 ? 2 : 1
  if (basicForm.kind === 'security') basicForm.security_height_u = securityHeightU

  const portLayout =
    basicForm.kind === 'security'
      ? defaultPortLayout('security', RACK_WIDTH_MM, securityHeightU)
      : defaultPortLayout(basicForm.kind)

  if (basicForm.kind === 'switch') {
    const uplinkCount =
      basicForm.switch_subtype === 'gigabit'
        ? normalizeGigabitUplinkCount(basicForm.uplink_port_count)
        : basicForm.switch_subtype === 'ten_gigabit' || basicForm.switch_subtype === 'aggregation'
          ? normalizeTenGigabitUplinkCount(basicForm.uplink_port_count)
          : basicForm.uplink_port_count
    basicForm.uplink_port_count = uplinkCount
    applySwitchLayoutConfig(portLayout, {
      subtype: basicForm.switch_subtype,
      mainPortCount: basicForm.main_port_count,
      uplinkPortCount: uplinkCount,
      uplinkPosition: basicForm.uplink_position,
      lineCards: basicForm.switch_subtype === 'core' ? basicForm.line_cards : [],
    })
  } else if (basicForm.kind === 'server') {
    applyServerFormFactor(portLayout, basicForm.server_form_factor)
    portLayout.slots_def = defaultServerSlotsDef(basicForm.server_form_factor)
    portLayout.slot_count = portLayout.slots_def.length
    portLayout.server_panel_side = 'rear'
    portLayout.server_onboard_1g_count = 4
    generatePortsFromSlotsDef(portLayout, false)
  } else if (basicForm.kind === 'security') {
    applySecurityLayoutConfig(portLayout, {
      heightU: securityHeightU,
      zones: defaultSecurityZones(),
      preservePeers: false,
    })
    // 强制落盘高度，避免后续归一化覆盖
    portLayout.height_u = securityHeightU
    portLayout.frame_height = SEC_FRAME_HEIGHT_BY_U[securityHeightU as 1 | 2]
    portLayout.security_panel = true
  } else {
    generatePortsFromSlotsDef(portLayout, false)
  }
  portLayout.layout_locked = false
  const node: NetworkNode = {
    id: crypto.randomUUID(),
    topology_id: currentId.value,
    kind: basicForm.kind,
    name: basicForm.name.trim(),
    device_id: null,
    device_model_id: null,
    contract_device_name: null,
    pos_x: 80 + (nodes.value.length % 6) * 180,
    pos_y: 80 + Math.floor(nodes.value.length / 6) * 120,
    switch_port_count: portLayout.ports.length,
    slots: null,
    port_layout: portLayout,
    on_canvas: false,
    device: null,
  }
  syncLegacyFromPortLayout(node)
  nodes.value.push(node)
  selectNode(node)
  expandedRowKeys.value = [node.id]
  basicVisible.value = false
}

function selectNode(node: NetworkNode) {
  selectedNodeId.value = node.id
  node.port_layout = ensurePortLayout(node)
  syncSummaryKeyFromNode(node)
}

function expandNode(node: NetworkNode) {
  selectNode(node)
  expandedRowKeys.value = [node.id]
}

function onExpandChange(row: NetworkNode, expandedRows: NetworkNode[]) {
  const isExpanded = expandedRows.some((r) => r.id === row.id)
  if (isExpanded) {
    expandedRowKeys.value = [row.id]
    selectNode(row)
  } else {
    expandedRowKeys.value = expandedRows.map((r) => r.id)
    if (selectedNodeId.value === row.id) {
      const next = expandedRowKeys.value[0]
      if (next) {
        const n = nodes.value.find((x) => x.id === next)
        if (n) selectNode(n)
      } else {
        selectedNodeId.value = null
        selectedSummaryKey.value = null
      }
    }
  }
}

function nodeKindLabel(node: NetworkNode) {
  if (node.kind === 'switch' && node.port_layout?.switch_subtype) {
    return SWITCH_SUBTYPE_LABELS[node.port_layout.switch_subtype]
  }
  return NODE_KIND_LABELS[node.kind]
}

function nodeBindStatus(node: NetworkNode) {
  const parts: string[] = []
  if (node.contract_device_name) parts.push(`合同:${node.contract_device_name}`)
  if (node.device_id) parts.push('已绑台账')
  return parts.length ? parts.join(' · ') : '未绑定'
}

function portPeerSummary(port: FramePort) {
  if (port.peer_device_id) {
    return `台账 ${port.peer_device_name || port.peer_device_id} / ${port.peer_port || '—'}`
  }
  if (port.peer_node_id) {
    const n = nodes.value.find((x) => x.id === port.peer_node_id)
    return `${n?.name || '未知'} / ${port.peer_port || '—'}`
  }
  return '—'
}

function portSlotLabel(port: FramePort) {
  if (port.slot_index != null) return `Slot ${port.slot_index}`
  if (port.group_id) return port.group_id
  return '—'
}

function onPortRowClick(port: FramePort) {
  frameEditorRef.value?.onPortClick(port)
}

function openPortPeerFromTable(port: FramePort) {
  frameEditorRef.value?.openPeerDialog(port)
}

function portTypeLabel(portType: PortType | string | null | undefined) {
  const key = (portType || '1g') as PortType
  return PORT_TYPE_LABELS[key] || String(portType || '1g')
}

const portTypeOptions = Object.entries(PORT_TYPE_LABELS).map(([value, label]) => ({
  value: value as PortType,
  label,
}))

function syncSummaryKeyFromNode(node: NetworkNode) {
  if (!node.contract_device_name && !node.device_model_id) {
    selectedSummaryKey.value = null
    return
  }
  const exact = contractSummaries.value.find(
    (row) => row.device_name === node.contract_device_name,
  )
  selectedSummaryKey.value = exact ? summaryOptionKey(exact) : null
}

async function loadContractSummaries() {
  summaryLoading.value = true
  try {
    contractSummaries.value = (await getContractSummary()) || []
    if (selectedNode.value) syncSummaryKeyFromNode(selectedNode.value)
  } catch {
    contractSummaries.value = []
    ElMessage.error('加载合同厂商型号采购汇总失败')
  } finally {
    summaryLoading.value = false
  }
}

async function bindContractSummary(key: string | null) {
  const node = selectedNode.value
  if (!node || !canEdit.value) return
  if (!key) {
    node.device_model_id = null
    node.contract_device_name = null
    selectedSummaryKey.value = null
    return
  }
  const row = contractSummaries.value.find((r) => summaryOptionKey(r) === key)
  if (!row) {
    ElMessage.warning('未找到该汇总条目')
    return
  }
  summaryLoading.value = true
  try {
    const model = await resolveModelFromSummary(row)
    node.device_model_id = model.id
    node.contract_device_name = (row.device_name || '').trim() || null
    selectedSummaryKey.value = key
    if (node.contract_device_name) {
      const kindPrefix = NODE_KIND_LABELS[node.kind]
      if (!node.name.trim() || node.name.startsWith(kindPrefix)) {
        node.name = node.contract_device_name
      }
    }
    ElMessage.success(
      `已关联合同型号：${row.manufacturer_name || '-'} / ${row.device_name || '-'} / ${row.device_model_name}`,
    )
  } catch (err: unknown) {
    const msg = (err as { message?: string })?.message
    ElMessage.error(msg || '关联合同型号失败')
    selectedSummaryKey.value = null
  } finally {
    summaryLoading.value = false
  }
}

const canApplyPanel = computed(
  () =>
    !!selectedNode.value?.port_layout &&
    !!selectedNode.value?.device_model_id &&
    !!selectedNode.value?.contract_device_name,
)

const applyPanelHint = computed(() => {
  if (!selectedNode.value) return '请先展开设备'
  if (!selectedNode.value.device_model_id || !selectedNode.value.contract_device_name) {
    return '请先在上方选择「关联合同厂商型号采购汇总」，再应用面板到设备清单'
  }
  return `「应用（未绑定）」将按采购汇总设备名称「${selectedNode.value.contract_device_name}」列出对应台账，可单选或全选应用；已应用仅可修改`
})

async function openApplyPanelDialog() {
  const node = selectedNode.value
  if (!node?.port_layout) {
    ElMessage.warning('请先完成设备面板定义')
    return
  }
  if (!node.device_model_id || !node.contract_device_name) {
    ElMessage.warning('请先关联合同「厂商型号采购汇总」中的型号与设备名称')
    // 引导聚焦汇总下拉
    if (!contractSummaries.value.length) await loadContractSummaries()
    return
  }
  applyPanelLoading.value = true
  try {
    if (node.port_layout) node.port_layout.layout_locked = true
    syncLegacyFromPortLayout(node)
    syncLinksFromPortLayout(nodes.value, links.value)
    await saveCanvas()
    applyPanelDialogVisible.value = true
  } catch (err: unknown) {
    const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
    ElMessage.error(msg || '保存设备定义失败，无法应用面板')
  } finally {
    applyPanelLoading.value = false
  }
}

function onApplyPanelDone() {
  ElMessage.info('可在设备管理中查看已应用面板的设备')
}

function removeNode(node: NetworkNode) {
  nodes.value = nodes.value.filter((n) => n.id !== node.id)
  links.value = links.value.filter(
    (l) => l.source_node_id !== node.id && l.target_node_id !== node.id,
  )
  expandedRowKeys.value = expandedRowKeys.value.filter((id) => id !== node.id)
  if (selectedNodeId.value === node.id) {
    const next = nodes.value[0]
    selectedNodeId.value = next?.id ?? null
    if (next) {
      expandedRowKeys.value = [next.id]
      syncSummaryKeyFromNode(next)
    } else {
      selectedSummaryKey.value = null
    }
  }
}

async function handleSave() {
  if (!currentId.value) return
  nodes.value.forEach((node) => {
    if (node.port_layout) {
      node.port_layout.layout_locked = true
      syncLegacyFromPortLayout(node)
    }
  })
  syncLinksFromPortLayout(nodes.value, links.value)
  const ok = await saveCanvas()
  if (ok) {
    // 保存回写后再次锁定，避免后端未带回 layout_locked 时仍可改结构
    nodes.value.forEach((node) => {
      if (node.port_layout) node.port_layout.layout_locked = true
    })
    ElMessage.info('布局已锁定；可继续配置接口对端，修改布局请点击「编辑布局」')
  }
}

function startLayoutEdit() {
  const node = selectedNode.value
  if (!node?.port_layout || !canEdit.value) return
  node.port_layout.layout_locked = false
  ElMessage.info('已进入布局编辑：可调整面板结构；保存后将再次锁定')
}

const layoutLocked = computed(() => !!selectedNode.value?.port_layout?.layout_locked)
const canConfigPorts = computed(() => canEdit.value)
const canEditLayout = computed(() => canEdit.value && !layoutLocked.value)

watch(
  nodes,
  () => {
    if (selectedNodeId.value && !nodes.value.some((n) => n.id === selectedNodeId.value)) {
      selectedNodeId.value = nodes.value[0]?.id ?? null
      expandedRowKeys.value = selectedNodeId.value ? [selectedNodeId.value] : []
    }
    if (!selectedNodeId.value && nodes.value.length) {
      selectNode(nodes.value[0])
      if (!expandedRowKeys.value.length) expandedRowKeys.value = [nodes.value[0].id]
    }
    expandedRowKeys.value = expandedRowKeys.value.filter((id) =>
      nodes.value.some((n) => n.id === id),
    )
  },
  { deep: true },
)

onMounted(async () => {
  await loadProjects()
  await loadContractSummaries()
  if (nodes.value.length && !selectedNodeId.value) {
    selectNode(nodes.value[0])
    expandedRowKeys.value = [nodes.value[0].id]
  }
})
</script>

<template>
  <div class="page" v-loading="loading">
    <el-card shadow="never" class="main-card">
      <section class="workspace">
        <div class="toolbar">
          <span class="title">设备定义</span>
          <div class="project-bar">
            <span class="project-label">项目</span>
            <el-select
              :model-value="currentProjectId"
              placeholder="选择项目"
              style="width: 220px"
              filterable
              :disabled="!projects.length"
              @change="onProjectChange"
            >
              <el-option
                v-for="p in projects"
                :key="p.id"
                :label="
                  p.code?.toUpperCase() === 'DEFAULT'
                    ? `${p.name || '默认项目'}（DEFAULT）`
                    : `${p.name} (${p.code})`
                "
                :value="p.id"
              />
            </el-select>

            <div class="project-actions">
              <el-dropdown
                v-if="canCreate || canEdit"
                trigger="click"
                :disabled="!canCreate && !canEdit"
              >
                <el-button type="primary" plain>
                  新建
                  <span class="dropdown-caret">▾</span>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu class="project-module-menu">
                    <el-dropdown-item
                      v-if="canCreate"
                      @click="openCreateProject"
                    >
                      <span class="menu-primary">新建项目</span>
                      <span class="menu-desc">创建空项目并进入设备定义</span>
                    </el-dropdown-item>
                    <el-dropdown-item
                      v-if="canEdit"
                      :disabled="!currentProjectId"
                      @click="openEditProject"
                    >
                      编辑当前项目
                    </el-dropdown-item>
                    <template v-for="mod in projectModules" :key="mod.id">
                      <el-dropdown-item disabled class="module-header" divided>
                        {{ mod.label }}
                      </el-dropdown-item>
                      <el-dropdown-item
                        v-for="item in mod.items"
                        :key="item.id"
                        :command="item.id"
                        :disabled="item.disabled"
                        @click="onProjectModuleCommand(item.id)"
                      >
                        {{ item.label }}
                      </el-dropdown-item>
                    </template>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>

              <el-button
                v-if="canDelete"
                type="danger"
                plain
                :disabled="!currentProjectId || currentProject?.code?.toUpperCase() === 'DEFAULT'"
                :title="
                  currentProject?.code?.toUpperCase() === 'DEFAULT'
                    ? '系统默认项目不可删除'
                    : '删除当前项目'
                "
                @click="handleRemoveProject"
              >
                删除项目
              </el-button>
            </div>
          </div>

          <el-button v-if="canEdit" type="primary" :loading="saving" :disabled="!currentId" @click="handleSave">
            保存
          </el-button>
        </div>

        <div v-if="currentId" class="content">
          <el-table
            :data="nodes"
            row-key="id"
            class="device-table"
            :expand-row-keys="expandedRowKeys"
            @expand-change="onExpandChange"
          >
            <el-table-column type="expand">
              <template #default="{ row }">
                <div v-if="selectedNodeId === row.id && selectedNode" class="expand-panel">
                  <div class="panel-header">
                    <el-input
                      v-model="selectedNode.name"
                      :disabled="!canEdit"
                      style="width: 200px"
                      placeholder="设备名称"
                    />
                    <el-select
                      v-model="selectedSummaryKey"
                      filterable
                      clearable
                      :loading="summaryLoading"
                      placeholder="① 关联合同厂商型号采购汇总（必选）"
                      :disabled="!canEdit"
                      style="width: 420px"
                      @change="bindContractSummary"
                      @focus="() => { if (!contractSummaries.length) loadContractSummaries() }"
                    >
                      <el-option
                        v-for="sum in contractSummaries"
                        :key="summaryOptionKey(sum)"
                        :label="formatSummaryOptionLabel(sum)"
                        :value="summaryOptionKey(sum)"
                      />
                    </el-select>
                    <el-tag v-if="layoutLocked" type="info" size="small">布局已锁定</el-tag>
                    <el-tag v-else-if="canEdit" type="warning" size="small">布局编辑中</el-tag>
                    <el-button
                      v-if="canEdit && layoutLocked"
                      type="primary"
                      @click="startLayoutEdit"
                    >
                      编辑布局
                    </el-button>
                  </div>

                  <div v-if="canEdit" class="apply-bar">
                    <div class="apply-bar-main">
                      <span class="apply-title">② 应用面板到设备</span>
                      <span class="apply-hint">{{ applyPanelHint }}</span>
                    </div>
                    <el-button
                      type="success"
                      :loading="applyPanelLoading"
                      :disabled="!canApplyPanel"
                      @click="openApplyPanelDialog"
                    >
                      应用面板到设备
                    </el-button>
                  </div>

                  <p v-if="selectedNode.contract_device_name" class="mode-hint">
                    已关联采购汇总设备名称「{{ selectedNode.contract_device_name }}」：应用时仅显示该名称对应的设备管理台账
                  </p>
                  <p v-if="layoutLocked" class="mode-hint">
                    布局已锁定，不可拖动/调整结构；单击选中接口，双击配置对端；下方接口表可改标签与对端
                  </p>

                  <NetworkDeviceFrameEditor
                    ref="frameEditorRef"
                    :key="selectedNode.id"
                    :node="selectedNode"
                    :peer-nodes="peerNodes"
                    :editable="canConfigPorts"
                    :layout-editable="canEditLayout"
                  />

                  <div class="ports-section">
                    <div class="ports-title">接口列表</div>
                    <el-table
                      :data="selectedNode.port_layout?.ports || []"
                      size="small"
                      border
                      max-height="280"
                      @row-click="onPortRowClick"
                    >
                      <el-table-column prop="id" label="端口 ID" min-width="100" show-overflow-tooltip />
                      <el-table-column label="标签" min-width="120">
                        <template #default="{ row: port }">
                          <el-input
                            v-if="canConfigPorts"
                            v-model="port.label"
                            size="small"
                            @click.stop
                          />
                          <span v-else>{{ port.label }}</span>
                        </template>
                      </el-table-column>
                      <el-table-column label="类型" width="130">
                        <template #default="{ row: port }">
                          <el-select
                            v-if="canEditLayout"
                            v-model="port.port_type"
                            size="small"
                            style="width: 100%"
                            @click.stop
                          >
                            <el-option
                              v-for="opt in portTypeOptions"
                              :key="opt.value"
                              :label="opt.label"
                              :value="opt.value"
                            />
                          </el-select>
                          <span v-else>{{ portTypeLabel(port.port_type) }}</span>
                        </template>
                      </el-table-column>
                      <el-table-column label="板卡/槽位" width="110" show-overflow-tooltip>
                        <template #default="{ row: port }">{{ portSlotLabel(port) }}</template>
                      </el-table-column>
                      <el-table-column label="对端" min-width="180" show-overflow-tooltip>
                        <template #default="{ row: port }">{{ portPeerSummary(port) }}</template>
                      </el-table-column>
                      <el-table-column v-if="canConfigPorts" label="操作" width="100" fixed="right">
                        <template #default="{ row: port }">
                          <el-button type="primary" link size="small" @click.stop="openPortPeerFromTable(port)">
                            对端
                          </el-button>
                        </template>
                      </el-table-column>
                    </el-table>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="名称" min-width="160">
              <template #default="{ row }">
                <button type="button" class="name-link" @click="expandNode(row)">{{ row.name }}</button>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="140">
              <template #default="{ row }">{{ nodeKindLabel(row) }}</template>
            </el-table-column>
            <el-table-column label="U 高" width="72" align="center">
              <template #default="{ row }">{{ row.port_layout?.height_u ?? 1 }}U</template>
            </el-table-column>
            <el-table-column label="端口数" width="80" align="center">
              <template #default="{ row }">{{ row.port_layout?.ports?.length ?? 0 }}</template>
            </el-table-column>
            <el-table-column label="合同/台账" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">{{ nodeBindStatus(row) }}</template>
            </el-table-column>
            <el-table-column v-if="canEdit" label="操作" width="90" fixed="right">
              <template #default="{ row }">
                <el-button type="danger" link size="small" @click.stop="removeNode(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!nodes.length" description="请添加设备" />
        </div>
        <el-empty v-else description="请先新建或选择项目，再添加设备" />
      </section>
    </el-card>

    <el-dialog
      v-model="projectDialogVisible"
      :title="projectDialogMode === 'create' ? '新建项目' : '编辑项目'"
      width="480px"
    >
      <el-form label-width="90px">
        <el-form-item label="项目编码" required>
          <el-input v-model="projectForm.code" placeholder="如 PROJ01" maxlength="50" />
        </el-form-item>
        <el-form-item label="项目名称" required>
          <el-input v-model="projectForm.name" placeholder="项目显示名称" maxlength="100" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="projectForm.description" type="textarea" :rows="3" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="projectDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="projectSaving" @click="confirmProjectDialog">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="basicVisible" title="新建设备" width="620px">
      <el-form label-width="120px">
        <el-form-item label="所属项目">
          <el-tag type="info">{{ currentProject?.name || '—' }}</el-tag>
        </el-form-item>
        <el-form-item label="类型">
          <el-tag>{{ NODE_KIND_LABELS[basicForm.kind] }}</el-tag>
        </el-form-item>
        <template v-if="basicForm.kind === 'switch'">
          <el-form-item label="设备类型" required>
            <el-select v-model="basicForm.switch_subtype" style="width: 100%" @change="onSwitchSubtypeChange">
              <el-option
                v-for="(label, key) in SWITCH_SUBTYPE_LABELS"
                :key="key"
                :label="label"
                :value="key"
              />
            </el-select>
          </el-form-item>

          <template v-if="isGigabitSwitch">
            <el-form-item label="电口数量">
              <el-input-number v-model="basicForm.main_port_count" :min="1" :max="128" />
            </el-form-item>
            <el-form-item label="上联光口数量">
              <el-input-number
                v-model="basicForm.uplink_port_count"
                :min="0"
                :max="8"
                @change="onCreateGigabitUplinkChange"
              />
              <div class="form-hint">最多 8 个；大于 4 时须为偶数（6/8），两排显示</div>
            </el-form-item>
            <el-form-item label="上联位置">
              <el-radio-group v-model="basicForm.uplink_position">
                <el-radio v-for="(label, key) in UPLINK_POSITION_LABELS" :key="key" :value="key">{{ label }}</el-radio>
              </el-radio-group>
            </el-form-item>
          </template>

          <template v-else-if="isTenGigabitSwitch || isAggregationSwitch">
            <el-form-item :label="isAggregationSwitch ? '下联光口数量' : '光口数量'">
              <el-input-number v-model="basicForm.main_port_count" :min="1" :max="128" />
            </el-form-item>
            <el-form-item label="40/100G上联数量">
              <el-input-number
                v-model="basicForm.uplink_port_count"
                :min="0"
                :max="8"
                :step="2"
                @change="onCreateTenGigabitUplinkChange"
              />
              <div class="form-hint">
                {{
                  isAggregationSwitch
                    ? '汇聚：下联接入交换机用 10G；上联核心用 40/100G，须为偶数'
                    : '须为偶数（2/4/6/8），两排向后扩展排列'
                }}
              </div>
            </el-form-item>
            <el-form-item label="上联位置">
              <el-radio-group v-model="basicForm.uplink_position">
                <el-radio v-for="(label, key) in UPLINK_POSITION_LABELS" :key="key" :value="key">{{ label }}</el-radio>
              </el-radio-group>
            </el-form-item>
          </template>

          <template v-else-if="isCoreSwitch">
            <el-form-item label="板卡定义">
              <div class="card-list">
                <div v-for="(card, idx) in basicForm.line_cards" :key="card.id" class="card-row">
                  <span class="card-idx">板卡 {{ idx + 1 }}</span>
                  <el-select v-model="card.card_type" style="width: 140px" @change="onCreateLineCardTypeChange(card)">
                    <el-option
                      v-for="(label, key) in CORE_CARD_TYPE_LABELS"
                      :key="key"
                      :label="label"
                      :value="key as CoreCardType"
                    />
                  </el-select>
                  <span>接口数量</span>
                  <el-input-number
                    v-model="card.port_count"
                    :min="card.card_type === 'blank' ? 0 : 1"
                    :max="128"
                    :disabled="card.card_type === 'blank'"
                  />
                  <el-button
                    type="danger"
                    link
                    :disabled="basicForm.line_cards.length <= 1"
                    @click="removeLineCard(idx)"
                  >
                    删除
                  </el-button>
                </div>
                <el-button type="primary" link :disabled="basicForm.line_cards.length >= 16" @click="addLineCard">
                  + 添加板卡
                </el-button>
                <p class="card-hint">核心交换机按板卡定义接口，无独立上联口</p>
              </div>
            </el-form-item>
          </template>
        </template>
        <template v-else-if="isCreateServer">
          <el-form-item label="服务器规格" required>
            <el-radio-group v-model="basicForm.server_form_factor">
              <el-radio v-for="(label, key) in SERVER_FORM_FACTOR_LABELS" :key="key" :value="Number(key)">
                {{ label }}
              </el-radio>
            </el-radio-group>
            <div class="form-hint">
              1U 默认 2 张扩展卡；2U 参考背板左 3 / 中 3 / 右 2 共 8 槽。创建后可继续添加或删除网卡 / RAID / HBA。
            </div>
          </el-form-item>
        </template>
        <template v-else-if="isCreateSecurity">
          <el-form-item label="设备高度" required>
            <el-radio-group v-model="basicForm.security_height_u">
              <el-radio :value="1">1U</el-radio>
              <el-radio :value="2">2U</el-radio>
            </el-radio-group>
            <div class="form-hint">
              1U / 2U 机箱同宽；默认生成 WAN / LAN / HA / MGMT 接口区，创建后可调整位置与大小。
            </div>
          </el-form-item>
        </template>
        <el-form-item label="名称" required>
          <el-input v-model="basicForm.name" placeholder="建议与合同设备名称一致" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="basicVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmCreate">创建并编辑接口</el-button>
      </template>
    </el-dialog>

    <ApplyPanelToDevicesDialog
      v-model="applyPanelDialogVisible"
      :node="selectedNode"
      @done="onApplyPanelDone"
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
  padding: 16px;
}

.workspace {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}

.project-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-right: 8px;
}

.project-actions {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.project-label {
  color: #606266;
  font-size: 13px;
}

.dropdown-caret {
  margin-left: 4px;
  font-size: 11px;
  opacity: 0.85;
}

.title {
  font-weight: 600;
  margin-right: 4px;
}

.content {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.device-table {
  width: 100%;
}

.name-link {
  border: none;
  background: transparent;
  color: #409eff;
  cursor: pointer;
  padding: 0;
  font: inherit;
}

.name-link:hover {
  text-decoration: underline;
}

.expand-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 8px 12px 16px;
  min-width: 0;
}

.ports-section {
  margin-top: 4px;
}

.ports-title {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 8px;
  color: #303133;
}

.panel-header {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.apply-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 4px 0 8px;
  padding: 10px 12px;
  border: 1px solid #b3e19d;
  background: #f0f9eb;
  border-radius: 8px;
}

.apply-bar-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.apply-title {
  font-weight: 600;
  color: #67c23a;
  font-size: 14px;
}

.apply-hint {
  font-size: 12px;
  color: #606266;
  line-height: 1.4;
}

.mode-hint {
  margin: 0;
  font-size: 12px;
  color: #909399;
}

.card-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.card-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.card-idx {
  font-weight: 500;
  min-width: 56px;
}

.card-hint {
  margin: 0;
  color: #909399;
  font-size: 12px;
}

.form-hint {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
  line-height: 1.4;
}
</style>

<style>
/* teleported dropdown — keep module menu readable & extensible */
.project-module-menu.el-dropdown-menu {
  min-width: 220px;
  padding: 6px 0;
}

.project-module-menu .el-dropdown-menu__item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1.35;
  padding: 8px 16px;
  gap: 2px;
}

.project-module-menu .menu-primary {
  font-weight: 600;
  color: #303133;
}

.project-module-menu .menu-desc {
  font-size: 12px;
  color: #909399;
}

.project-module-menu .module-header {
  font-size: 12px;
  font-weight: 600;
  color: #909399 !important;
  cursor: default;
  opacity: 1 !important;
  background: #f5f7fa !important;
  margin-top: 4px;
}
</style>
