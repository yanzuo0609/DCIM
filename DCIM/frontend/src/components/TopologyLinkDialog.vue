<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  CABLE_TYPE_LABELS,
  INTERFACE_CLASS_LABELS,
  LINK_ROLE_LABELS,
  LINK_TYPE_LABELS,
  type CableType,
  type InterfaceClass,
  type NetworkLink,
  type NetworkLinkRole,
  type NetworkLinkType,
  type NetworkNode,
  type NodePortOption,
  type PortLayout,
  type SwitchSubtype,
  listNodePortOptions,
} from '@/api/network'
import { listDevices, type Device } from '@/api/device'
import {
  applyDeviceBinding,
  filterDevicesByEndType,
  findTopologyNodeForDevice,
  formatDeviceOptionLabel,
} from '@/utils/deviceBinding'
import {
  enrichLinkFields,
  filterToTopologyKind,
  inferLinkRole,
  linkEndFilterHint,
  linkEndTypeFilters,
  linkEndTypeLabel,
  type LinkEndTypeFilter,
  wiringHint,
} from '@/utils/interfaceDesign'

export type LinkConfirmPayload = {
  link_type: NetworkLinkType
  source_node_id: string
  source_port: string
  target_node_id: string
  target_port: string
  label: string | null
  source_label: string | null
  target_label: string | null
  cable_type: CableType | null
  interface_class: InterfaceClass | null
  link_role: NetworkLinkRole | null
}

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    nodes: NetworkNode[]
    links: NetworkLink[]
    sourceNodeId?: string | null
    targetNodeId?: string | null
    sourcePort?: string | null
    targetPort?: string | null
    lockEndpoints?: boolean
    lockSource?: boolean
    preferredRole?: NetworkLinkRole | null
    editingLink?: NetworkLink | null
  }>(),
  {
    sourceNodeId: null,
    targetNodeId: null,
    sourcePort: null,
    targetPort: null,
    lockEndpoints: false,
    lockSource: false,
    preferredRole: null,
    editingLink: null,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: [payload: LinkConfirmPayload]
}>()

const isEdit = computed(() => !!props.editingLink)
const hydrating = ref(false)

const form = reactive({
  link_type: 'switch_server' as NetworkLinkType,
  source_node_id: '' as string,
  source_port: '' as string,
  target_node_id: '' as string,
  target_port: '' as string,
  label: '',
  source_label: '',
  target_label: '',
  cable_type: 'copper_cat6' as CableType,
  interface_class: 'electric' as InterfaceClass,
  link_role: 'server' as NetworkLinkRole,
  autoLabel: true,
})

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const endFilters = computed(() => linkEndTypeFilters(form.link_type, form.link_role))

const sourceNode = computed(() => props.nodes.find((n) => n.id === form.source_node_id))
const targetNode = computed(() => props.nodes.find((n) => n.id === form.target_node_id))

/** 设备管理清单 */
const inventoryAll = ref<Device[]>([])
const inventoryLoading = ref(false)
const sourceBindId = ref<string | null>(null)
const targetBindId = ref<string | null>(null)

function inventoryFor(filter: LinkEndTypeFilter, currentId: string | null): Device[] {
  let list = filterDevicesByEndType(inventoryAll.value, filter)
  // 编辑时保证当前已选设备在列表中
  if (currentId && !list.some((d) => d.id === currentId)) {
    const cur = inventoryAll.value.find((d) => d.id === currentId)
    if (cur) list = [cur, ...list]
  }
  // 对端排除本端已选；本端排除对端已选（同一条连线两端不能是同一台）
  const otherId = filter === endFilters.value.source ? targetBindId.value : sourceBindId.value
  if (otherId) list = list.filter((d) => d.id !== otherId)
  return list
}

const sourceInventory = computed(() => inventoryFor(endFilters.value.source, sourceBindId.value))
const targetInventory = computed(() => inventoryFor(endFilters.value.target, targetBindId.value))

const sourceEmptyHint = computed(() => {
  if (sourceInventory.value.length) return ''
  return linkEndFilterHint(endFilters.value.source)
})

const targetEmptyHint = computed(() => {
  if (targetInventory.value.length) return ''
  return linkEndFilterHint(endFilters.value.target)
})

async function loadAllInventory() {
  inventoryLoading.value = true
  try {
    const pageSize = 200
    const first = await listDevices({ page: 1, page_size: pageSize })
    const items = [...(first.items || [])]
    const pages = Math.max(1, Number(first.pagination?.pages || 1))
    for (let page = 2; page <= pages; page += 1) {
      const data = await listDevices({ page, page_size: pageSize })
      items.push(...(data.items || []))
    }
    inventoryAll.value = items
  } catch {
    inventoryAll.value = []
    ElMessage.error('加载设备管理清单失败')
  } finally {
    inventoryLoading.value = false
  }
}

function findDevice(deviceId: string | null | undefined): Device | undefined {
  if (!deviceId) return undefined
  return (
    inventoryAll.value.find((d) => d.id === deviceId) ||
    sourceInventory.value.find((d) => d.id === deviceId) ||
    targetInventory.value.find((d) => d.id === deviceId)
  )
}

/** 将设备定义应用到台账上的面板同步到拓扑节点，供接口下拉使用 */
function syncPanelLayoutToNode(node: NetworkNode, device: Device) {
  const layout = device.port_layout as PortLayout | null | undefined
  if (layout?.ports?.length) {
    node.port_layout = JSON.parse(JSON.stringify(layout)) as PortLayout
  }
}

/** 一对多：为额外台账克隆定义节点（复制面板、清空对端绑定） */
function cloneDefinitionNode(template: NetworkNode): NetworkNode {
  const layout = template.port_layout
    ? (JSON.parse(JSON.stringify(template.port_layout)) as PortLayout)
    : null
  layout?.ports?.forEach((p) => {
    p.peer_node_id = null
    p.peer_port = null
    p.peer_label = null
  })
  const clone: NetworkNode = {
    id: crypto.randomUUID(),
    topology_id: template.topology_id,
    kind: template.kind,
    name: template.name,
    device_id: null,
    device_model_id: template.device_model_id ?? null,
    contract_device_name: template.contract_device_name ?? null,
    pos_x: template.pos_x,
    pos_y: template.pos_y + 40,
    switch_port_count: template.switch_port_count,
    slots: template.slots ? JSON.parse(JSON.stringify(template.slots)) : null,
    port_layout: layout,
    on_canvas: false,
    device: null,
  }
  props.nodes.push(clone)
  return clone
}

/** 台账已应用面板但无匹配定义时，按台账面板创建临时节点 */
function createNodeFromDevicePanel(
  device: Device,
  kind: NonNullable<ReturnType<typeof filterToTopologyKind>>,
): NetworkNode | null {
  const layout = device.port_layout as PortLayout | null | undefined
  if (!layout?.ports?.length) return null
  const name =
    (device.panel_apply_device_name || device.name || device.hostname || kind).trim() || kind
  const node: NetworkNode = {
    id: crypto.randomUUID(),
    topology_id: props.nodes[0]?.topology_id || '',
    kind,
    name,
    device_id: null,
    device_model_id: device.device_model_id || null,
    contract_device_name: device.panel_apply_device_name || device.name || null,
    pos_x: 80,
    pos_y: 80,
    switch_port_count: layout.ports.length,
    slots: null,
    port_layout: JSON.parse(JSON.stringify(layout)) as PortLayout,
    on_canvas: false,
    device: null,
  }
  props.nodes.push(node)
  return node
}

function resolveAndBind(end: 'source' | 'target', deviceId: string | null): boolean {
  if (!deviceId) {
    if (end === 'source') {
      sourceBindId.value = null
      form.source_node_id = ''
      form.source_port = ''
    } else {
      targetBindId.value = null
      form.target_node_id = ''
      form.target_port = ''
    }
    return true
  }

  const device = findDevice(deviceId)
  if (!device) {
    ElMessage.warning('未找到该设备，请刷新后重试')
    return false
  }

  const filter = end === 'source' ? endFilters.value.source : endFilters.value.target
  const kind = filterToTopologyKind(filter)
  if (!kind) {
    ElMessage.warning('当前连线类型无法确定设备类型')
    return false
  }

  let node = findTopologyNodeForDevice(props.nodes, device, kind)
  if (node?.device_id && node.device_id !== deviceId) {
    node = cloneDefinitionNode(node)
  }
  if (!node) {
    node = createNodeFromDevicePanel(device, kind)
  }
  if (!node) {
    const typeLabel = linkEndTypeLabel(filter)
    ElMessage.warning(
      `请先在「设备定义」中添加${typeLabel}，并「应用面板到设备」：${device.name || device.hostname}`,
    )
    if (end === 'source') sourceBindId.value = sourceNode.value?.device_id || null
    else targetBindId.value = targetNode.value?.device_id || null
    return false
  }

  const other = end === 'source' ? targetNode.value : sourceNode.value
  if (other?.device_id === deviceId) {
    ElMessage.warning('本端与对端不能选择同一台设备')
    return false
  }

  syncPanelLayoutToNode(node, device)
  applyDeviceBinding(node, device)

  if (end === 'source') {
    sourceBindId.value = deviceId
    form.source_node_id = node.id
    form.source_port = ''
  } else {
    targetBindId.value = deviceId
    form.target_node_id = node.id
    form.target_port = ''
  }
  return true
}

function onSourceDeviceChange(deviceId: string | null) {
  if (hydrating.value) return
  if (!resolveAndBind('source', deviceId)) return
  autofillPorts()
  applyEnrichment(true)
}

function onTargetDeviceChange(deviceId: string | null) {
  if (hydrating.value) return
  if (!resolveAndBind('target', deviceId)) return
  autofillPorts()
  applyEnrichment(true)
}

function occupiedPorts(nodeId: string) {
  const used = new Set<string>()
  const skipId = props.editingLink?.id
  props.links.forEach((l) => {
    if (skipId && l.id === skipId) return
    if (l.source_node_id === nodeId) used.add(l.source_port)
    if (l.target_node_id === nodeId) used.add(l.target_port)
  })
  const node = props.nodes.find((n) => n.id === nodeId)
  const edit = props.editingLink
  node?.port_layout?.ports?.forEach((p) => {
    if (!p.peer_node_id || !p.peer_port) return
    if (
      edit &&
      ((edit.source_node_id === nodeId && edit.source_port === p.id) ||
        (edit.target_node_id === nodeId && edit.target_port === p.id))
    ) {
      return
    }
    used.add(p.id)
  })
  return used
}

function freePortOptions(node: NetworkNode | undefined): NodePortOption[] {
  if (!node) return []
  const used = occupiedPorts(node.id)
  const options = listNodePortOptions(node)
  const free = options.filter((o) => !used.has(o.id))
  return free.length ? free : options
}

const sourcePorts = computed(() => freePortOptions(sourceNode.value))
const targetPorts = computed(() => freePortOptions(targetNode.value))

const sourcePortHint = computed(() => {
  if (!sourceBindId.value) return ''
  if (sourcePorts.value.length) return ''
  return '该设备尚未应用面板定义，请先在「设备定义」中应用面板到该设备'
})

const targetPortHint = computed(() => {
  if (!targetBindId.value) return ''
  if (targetPorts.value.length) return ''
  return '该设备尚未应用面板定义，请先在「设备定义」中应用面板到该设备'
})

const sourceHint = computed(() => {
  const sub = sourceNode.value?.port_layout?.switch_subtype as SwitchSubtype | undefined
  return wiringHint(sub)
})

function pickDefaultPort(options: NodePortOption[], current: string) {
  if (current && options.some((o) => o.id === current)) return current
  return options[0]?.id || ''
}

function syncLinkTypeFromRole(role: NetworkLinkRole) {
  if (role === 'server') form.link_type = 'switch_server'
  else if (role === 'security') form.link_type = 'switch_security'
  else form.link_type = 'switch_switch'
}

function syncRoleFromType(type: NetworkLinkType) {
  if (type === 'switch_server') form.link_role = 'server'
  else if (type === 'switch_security') form.link_role = 'security'
  else if (form.link_role === 'server' || form.link_role === 'security') {
    form.link_role = 'interconnect'
  }
}

function applyEnrichment(forceLabels = false) {
  if (!sourceNode.value || !targetNode.value || !form.source_port || !form.target_port) return
  const enriched = enrichLinkFields(
    form.link_type,
    sourceNode.value,
    targetNode.value,
    form.source_port,
    form.target_port,
  )
  // 接口类/线缆始终按对端接口速率联动
  form.interface_class = enriched.interface_class
  form.cable_type = enriched.cable_type
  if (!isEdit.value || forceLabels) {
    form.link_role = enriched.link_role
  } else if (!form.link_role) {
    form.link_role = enriched.link_role
  }
  if (form.autoLabel || forceLabels) {
    form.source_label = enriched.source_label
    form.target_label = enriched.target_label
  }
}

function autofillPorts() {
  form.source_port = pickDefaultPort(sourcePorts.value, form.source_port)
  form.target_port = pickDefaultPort(targetPorts.value, form.target_port)
  applyEnrichment()
}

function clearEndpoints() {
  form.source_node_id = ''
  form.target_node_id = ''
  form.source_port = ''
  form.target_port = ''
  form.source_label = ''
  form.target_label = ''
  sourceBindId.value = null
  targetBindId.value = null
}

function resetCreateForm() {
  form.link_type = 'switch_server'
  form.link_role = 'server'
  form.label = ''
  form.cable_type = 'copper_cat6'
  form.interface_class = 'electric'
  form.autoLabel = true
  clearEndpoints()
  applyPreferredRole()
}

function applyPreferredRole() {
  if (!props.preferredRole) return
  form.link_role = props.preferredRole
  syncLinkTypeFromRole(props.preferredRole)
}

function loadEditingLink(link: NetworkLink) {
  form.link_type = link.link_type
  form.source_node_id = link.source_node_id
  form.target_node_id = link.target_node_id
  form.source_port = link.source_port
  form.target_port = link.target_port
  form.label = link.label || ''
  form.source_label = link.source_label || ''
  form.target_label = link.target_label || ''
  form.cable_type = (link.cable_type as CableType) || 'copper_cat6'
  form.interface_class = (link.interface_class as InterfaceClass) || 'electric'
  form.link_role = (link.link_role as NetworkLinkRole) || 'server'
  form.autoLabel = !(link.source_label || link.target_label)
  sourceBindId.value = sourceNode.value?.device_id || null
  targetBindId.value = targetNode.value?.device_id || null
  // 同步已应用面板到节点，保证接口列表完整
  const sd = findDevice(sourceBindId.value)
  const td = findDevice(targetBindId.value)
  if (sd && sourceNode.value) syncPanelLayoutToNode(sourceNode.value, sd)
  if (td && targetNode.value) syncPanelLayoutToNode(targetNode.value, td)
  form.source_port = pickDefaultPort(sourcePorts.value, form.source_port)
  form.target_port = pickDefaultPort(targetPorts.value, form.target_port)
  if (form.autoLabel) applyEnrichment(true)
}

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return
    hydrating.value = true
    try {
      await loadAllInventory()
      if (props.editingLink) {
        loadEditingLink(props.editingLink)
        return
      }
      resetCreateForm()
      // 画布点选预填：按节点反查台账
      if (props.sourceNodeId) {
        form.source_node_id = props.sourceNodeId
        sourceBindId.value = sourceNode.value?.device_id || null
      }
      if (props.targetNodeId) {
        form.target_node_id = props.targetNodeId
        targetBindId.value = targetNode.value?.device_id || null
      }
      if (props.sourcePort) form.source_port = props.sourcePort
      if (props.targetPort) form.target_port = props.targetPort
      if (form.source_node_id || form.target_node_id) autofillPorts()
    } finally {
      hydrating.value = false
    }
  },
)

watch(
  () => form.link_role,
  (role) => {
    if (!props.modelValue || hydrating.value) return
    syncLinkTypeFromRole(role)
    // 切换场景后类型变化，清空两端重选
    if (!isEdit.value) {
      clearEndpoints()
    }
  },
)

watch(
  () => form.link_type,
  (type) => {
    if (!props.modelValue || hydrating.value) return
    syncRoleFromType(type)
    if (!isEdit.value) {
      clearEndpoints()
    }
  },
)

watch(
  () => [form.source_port, form.target_port] as const,
  () => {
    if (!props.modelValue || hydrating.value) return
    applyEnrichment()
  },
)

function onConfirm() {
  if (!form.source_node_id || !form.target_node_id || !form.source_port || !form.target_port) return
  if (form.source_node_id === form.target_node_id) return
  if (!sourceBindId.value || !targetBindId.value) {
    ElMessage.warning('请选择本端和对端设备管理中的设备')
    return
  }
  if (!sourcePorts.value.length || !targetPorts.value.length) {
    ElMessage.warning('所选设备缺少面板接口，请先在设备定义中应用面板')
    return
  }
  const skipId = props.editingLink?.id
  const dup = props.links.some((l) => {
    if (skipId && l.id === skipId) return false
    return (
      (l.source_node_id === form.source_node_id &&
        l.source_port === form.source_port &&
        l.target_node_id === form.target_node_id &&
        l.target_port === form.target_port) ||
      (l.source_node_id === form.target_node_id &&
        l.source_port === form.target_port &&
        l.target_node_id === form.source_node_id &&
        l.target_port === form.source_port)
    )
  })
  if (dup) {
    ElMessage.warning('该接口连线已存在')
    return
  }
  const editing = isEdit.value
  emit('confirm', {
    link_type: form.link_type,
    source_node_id: form.source_node_id,
    source_port: form.source_port,
    target_node_id: form.target_node_id,
    target_port: form.target_port,
    label: form.label.trim() || null,
    source_label: form.source_label.trim() || null,
    target_label: form.target_label.trim() || null,
    cable_type: form.cable_type,
    interface_class: form.interface_class,
    link_role: form.link_role || inferLinkRole(form.link_type, sourceNode.value, targetNode.value),
  })
  if (editing) {
    dialogVisible.value = false
    return
  }
  hydrating.value = true
  try {
    resetCreateForm()
  } finally {
    hydrating.value = false
  }
}

function regenerateLabels() {
  form.autoLabel = true
  applyEnrichment(true)
}

const canSubmit = computed(
  () =>
    !!form.source_node_id &&
    !!form.target_node_id &&
    !!form.source_port &&
    !!form.target_port &&
    form.source_node_id !== form.target_node_id &&
    !!sourceBindId.value &&
    !!targetBindId.value &&
    !!sourcePorts.value.length &&
    !!targetPorts.value.length,
)

const assocRuleTitle = computed(() => {
  const s = linkEndTypeLabel(endFilters.value.source)
  const t = linkEndTypeLabel(endFilters.value.target)
  return `按连线类型从设备管理选择：本端→全部${s}，对端→全部${t}；接口取自设备定义已应用到该设备的面板。对端万兆→光口/多模光纤，千兆→电口/超六类铜缆`
})
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    :title="isEdit ? '编辑连线（接口设计）' : '添加连线（接口设计）'"
    width="680px"
    append-to-body
    destroy-on-close
  >
    <el-form label-width="108px">
      <el-form-item label="连线类型">
        <el-select v-model="form.link_type" style="width: 100%" :disabled="lockEndpoints">
          <el-option v-for="(label, key) in LINK_TYPE_LABELS" :key="key" :label="label" :value="key" />
        </el-select>
      </el-form-item>
      <el-form-item label="连线场景">
        <el-select v-model="form.link_role" style="width: 100%" :disabled="lockEndpoints">
          <el-option v-for="(label, key) in LINK_ROLE_LABELS" :key="key" :label="label" :value="key" />
        </el-select>
      </el-form-item>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="assoc-alert"
        :title="assocRuleTitle"
      />

      <el-form-item label="本端设备">
        <el-select
          v-model="sourceBindId"
          filterable
          clearable
          :loading="inventoryLoading"
          style="width: 100%"
          :disabled="lockEndpoints || lockSource"
          :placeholder="sourceEmptyHint || `选择设备管理中的${linkEndTypeLabel(endFilters.source)}`"
          @change="onSourceDeviceChange"
        >
          <el-option
            v-for="d in sourceInventory"
            :key="d.id"
            :label="formatDeviceOptionLabel(d)"
            :value="d.id"
          />
        </el-select>
        <p v-if="sourceEmptyHint" class="field-warn">{{ sourceEmptyHint }}</p>
        <p v-else-if="sourceNode" class="field-meta">
          定义：{{ sourceNode.name }}
          <template v-if="sourceNode.port_layout?.ports?.length">
            · {{ sourceNode.port_layout.ports.length }} 接口
          </template>
        </p>
      </el-form-item>

      <el-form-item label="本端接口">
        <el-select
          v-model="form.source_port"
          filterable
          style="width: 100%"
          :disabled="(lockSource && !!sourcePort) || !sourceBindId"
          placeholder="选择设备定义面板上的接口"
        >
          <el-option v-for="p in sourcePorts" :key="p.id" :label="p.label" :value="p.id" />
        </el-select>
        <p v-if="sourcePortHint" class="field-warn">{{ sourcePortHint }}</p>
      </el-form-item>

      <el-form-item label="对端设备">
        <el-select
          v-model="targetBindId"
          filterable
          clearable
          :loading="inventoryLoading"
          style="width: 100%"
          :disabled="lockEndpoints"
          :placeholder="targetEmptyHint || `选择设备管理中的${linkEndTypeLabel(endFilters.target)}`"
          @change="onTargetDeviceChange"
        >
          <el-option
            v-for="d in targetInventory"
            :key="d.id"
            :label="formatDeviceOptionLabel(d)"
            :value="d.id"
          />
        </el-select>
        <p v-if="targetEmptyHint" class="field-warn">{{ targetEmptyHint }}</p>
        <p v-else-if="targetNode" class="field-meta">
          定义：{{ targetNode.name }}
          <template v-if="targetNode.port_layout?.ports?.length">
            · {{ targetNode.port_layout.ports.length }} 接口
          </template>
        </p>
      </el-form-item>

      <el-form-item label="对端接口">
        <el-select
          v-model="form.target_port"
          filterable
          style="width: 100%"
          :disabled="!targetBindId"
          placeholder="选择设备定义面板上的接口"
        >
          <el-option v-for="p in targetPorts" :key="p.id" :label="p.label" :value="p.id" />
        </el-select>
        <p v-if="targetPortHint" class="field-warn">{{ targetPortHint }}</p>
      </el-form-item>

      <el-form-item label="接口类">
        <el-select v-model="form.interface_class" style="width: 100%">
          <el-option
            v-for="(label, key) in INTERFACE_CLASS_LABELS"
            :key="key"
            :label="label"
            :value="key"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="线缆类">
        <el-select v-model="form.cable_type" style="width: 100%">
          <el-option v-for="(label, key) in CABLE_TYPE_LABELS" :key="key" :label="label" :value="key" />
        </el-select>
      </el-form-item>
      <el-form-item label="自动标签">
        <el-switch v-model="form.autoLabel" />
        <el-button link type="primary" class="regen" @click="regenerateLabels">重新生成</el-button>
        <span class="inline-hint">按两端名称/位置/U位/接口生成</span>
      </el-form-item>
      <el-form-item label="本端标签">
        <el-input v-model="form.source_label" :disabled="form.autoLabel" />
      </el-form-item>
      <el-form-item label="对端标签">
        <el-input v-model="form.target_label" :disabled="form.autoLabel" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.label" placeholder="可选" />
      </el-form-item>
      <p class="hint">{{ sourceHint }}</p>
      <p class="hint">添加连线后表单会自动清空，可继续添加；完成后请在接口设计页点击「保存」。</p>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :disabled="!canSubmit" @click="onConfirm">
        {{ isEdit ? '保存修改' : '添加连线' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.assoc-alert {
  margin: 0 0 12px;
}

.hint {
  margin: 0 0 8px 108px;
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}

.inline-hint {
  margin-left: 8px;
  font-size: 12px;
  color: #909399;
}

.regen {
  margin-left: 8px;
}

.field-warn {
  margin: 4px 0 0;
  font-size: 12px;
  color: #e6a23c;
  line-height: 1.4;
}

.field-meta {
  margin: 4px 0 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}
</style>
