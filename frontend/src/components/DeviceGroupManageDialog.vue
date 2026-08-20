<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { NetworkNode } from '@/api/network'
import { nodeParentGroups } from '@/utils/deviceGroups'
import {
  emptySlot,
  formatDeviceGroupSequenceName,
  migrateSlotsFromLegacy,
  newSlotId,
  normalizeDeviceGroupId,
  summarizeSlots,
  syncGroupInstances,
  totalSlotCount,
  type DeviceGroupDef,
  type DeviceGroupPortRef,
  type DeviceGroupSlot,
} from '@/utils/deviceGroupSlots'
import { FABRIC_ROLE_OPTIONS, type FabricRole } from '@/utils/wiringTypes'
import { DEVICE_GROUP_KIND_LABELS, resolveDeviceGroupKind, nodeKindForGroupRole, type DeviceGroupKind } from '@/utils/deviceGroupVisual'

export type { DeviceGroupPortRef, DeviceGroupSlot }
/** @deprecated 兼容旧 import 名 */
export type DeviceGroupMeta = DeviceGroupDef

const props = defineProps<{
  modelValue: boolean
  catalog: DeviceGroupDef[]
  designModels?: Array<{ id: string; name: string; category: string }>
  /** 当前拓扑画布中的设备，用于创建/编辑组时直接绑定成员 */
  topologyDevices?: NetworkNode[]
  /** 可选绑定的布线规则 */
  wiringRules?: Array<{ id: string; name: string; enabled?: boolean }>
  initialGroup?: string | null
  mode?: 'manage' | 'create'
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
  'update:catalog': [list: DeviceGroupDef[]]
  created: [name: string]
  renameGroup: [payload: { from: string; to: string }]
  deleteGroup: [name: string]
  deleteGroups: [names: string[]]
  bindDevices: [payload: { name: string; previousName: string | null; deviceIds: string[]; candidateIds: string[] }]
  cloneGroups: [payload: { sourceName: string; groups: DeviceGroupDef[]; fullClone: boolean; devicePrefix: string }]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const step = ref<'list' | 'edit' | 'clone'>('list')
const editingOriginalName = ref<string | null>(null)
const form = reactive({
  name: '',
  role: null as FabricRole | null,
  description: '',
})
const groupType = ref<DeviceGroupKind>('access')
const slots = ref<DeviceGroupSlot[]>([])
const wiringRuleIds = ref<string[]>([])
const wiringScope = ref<'group' | 'topology'>('group')
const linkedDeviceIds = ref<string[]>([])
const autoGenerate = ref(true)
const createGroupCount = ref(1)
const cloneSourceName = ref('')
const cloneCount = ref(1)
const cloneGroupPrefix = ref('GROUP-')
const cloneGroupPattern = ref('{prefix}{index:02}')
const cloneStartNo = ref(1)
const cloneFull = ref(true)
const cloneDevicePrefix = ref('DEV-')
const selectedGroupNames = ref<string[]>([])
const groupTableRef = ref<{ toggleAllSelection: () => void; clearSelection: () => void } | null>(null)

const GROUP_TYPE_OPTIONS: Array<{ value: DeviceGroupKind; label: string; role: FabricRole | null }> = [
  { value: 'core', label: '核心交换机组', role: 'CORE' },
  { value: 'aggregation', label: '汇聚交换机组', role: 'AGG' },
  { value: 'access', label: '接入交换机组', role: 'ACCESS' },
  { value: 'server', label: '服务器组', role: 'SERVER' },
  { value: 'security', label: '安全设备组', role: 'FIREWALL' },
  { value: 'mixed', label: '混合组', role: null },
]

const allGroupDevices = computed(() => (props.topologyDevices || []).filter((n) => n?.id))

const topologyDeviceOptions = computed(() =>
  allGroupDevices.value
    .filter((n) => n?.id && n.on_canvas !== false)
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name, 'zh-CN')),
)

function topologyDeviceLabel(node: NetworkNode): string {
  const parent = nodeParentGroups(node)[0]
  return parent ? `${node.name}（当前组：${parent}）` : node.name
}

function normalizeMeta(raw: Partial<DeviceGroupDef> & { note?: string; name: string }): DeviceGroupDef {
  const migrated = migrateSlotsFromLegacy(raw)
  const primaryRole = raw.role || migrated[0]?.role || null
  const ruleIds = Array.isArray(raw.wiring_rule_ids)
    ? raw.wiring_rule_ids.filter((x): x is string => typeof x === 'string' && !!x.trim())
    : []
  return {
    id: normalizeDeviceGroupId(raw.id, raw.name),
    name: raw.name,
    role: (primaryRole as FabricRole | null) || null,
    description: (raw.description ?? raw.note ?? '').toString(),
    group_type: raw.group_type || resolveDeviceGroupKind({
      role: primaryRole as FabricRole | null,
      slotRoles: migrated.map((slot) => slot.role),
    }),
    slots: migrated,
    instances: syncGroupInstances(raw.name, migrated, raw.instances),
    wiring_rule_ids: ruleIds.length ? ruleIds : null,
    wiring_scope: raw.wiring_scope === 'topology' ? 'topology' : 'group',
    auto_generate: raw.auto_generate !== false,
    planned_count: totalSlotCount(migrated) || null,
    design_model_id: migrated[0]?.design_model_id || raw.design_model_id || null,
    port_pool: Array.isArray(raw.port_pool) ? raw.port_pool : null,
  }
}

const allGroups = computed(() =>
  props.catalog
    .filter((g) => g?.name)
    .map((g) => normalizeMeta(g))
    .sort((a, b) => a.name.localeCompare(b.name, 'zh-CN')),
)

const tableRows = computed(() =>
  allGroups.value.map((g, index) => {
    const members = g.instances || []
    return {
      ...g,
      sequence: index + 1,
      groupId: normalizeDeviceGroupId(g.id, g.name),
      slotSummary: summarizeSlots(g.slots, props.designModels),
      totalCount: totalSlotCount(g.slots),
      ruleCount: g.wiring_rule_ids?.length || 0,
      memberCount: members.length,
      memberIds: members.map((device) => device.id),
      groupTypeLabel: DEVICE_GROUP_KIND_LABELS[g.group_type || visualKind(g.role, g.slots)],
    }
  }),
)

function visualKind(role: FabricRole | null | undefined, slotList: DeviceGroupSlot[] = slots.value) {
  return resolveDeviceGroupKind({
    role,
    slotRoles: slotList.map((s) => s.role),
  })
}

function metaOf(name: string): DeviceGroupDef {
  return allGroups.value.find((g) => g.name === name) || {
    name,
    role: null,
    description: '',
    slots: [],
  }
}

function resetForm() {
  form.name = ''
  form.role = 'ACCESS'
  form.description = ''
  groupType.value = 'access'
  slots.value = [emptySlot({ count: 2, role: 'ACCESS' })]
  wiringRuleIds.value = []
  wiringScope.value = 'group'
  linkedDeviceIds.value = []
  autoGenerate.value = true
  createGroupCount.value = 1
  editingOriginalName.value = null
}

watch(
  () => [props.modelValue, props.initialGroup, props.mode] as const,
  ([open, initial, mode]) => {
    if (!open) return
    if (mode === 'create') {
      openCreate()
      return
    }
    if (initial) {
      openEdit(initial)
      return
    }
    step.value = 'list'
    resetForm()
  },
)

function openCreate() {
  resetForm()
  step.value = 'edit'
}

function openClone(name?: string) {
  const source = name || allGroups.value[0]?.name || ''
  cloneSourceName.value = source
  cloneCount.value = 1
  cloneGroupPrefix.value = source ? `${source}-` : 'GROUP-'
  cloneGroupPattern.value = '{prefix}{index:02}'
  cloneStartNo.value = 1
  cloneFull.value = true
  cloneDevicePrefix.value = source ? `${source}-DEV-` : 'DEV-'
  step.value = 'clone'
}

function onCloneSourceChange(name: string) {
  cloneGroupPrefix.value = name ? `${name}-` : 'GROUP-'
  cloneDevicePrefix.value = name ? `${name}-DEV-` : 'DEV-'
}

function openEdit(name: string) {
  const m = metaOf(name)
  editingOriginalName.value = name
  form.name = m.name
  form.role = m.role
  form.description = m.description
  groupType.value = m.group_type || visualKind(m.role, m.slots)
  slots.value = migrateSlotsFromLegacy(m).map((s) => ({ ...s, id: s.id || newSlotId() }))
  if (!slots.value.length) slots.value = [emptySlot({ role: m.role, count: 1 })]
  wiringRuleIds.value = [...(m.wiring_rule_ids || [])]
  wiringScope.value = m.wiring_scope === 'topology' ? 'topology' : 'group'
  linkedDeviceIds.value = topologyDeviceOptions.value
    .filter((node) => nodeParentGroups(node).includes(name))
    .map((node) => node.id)
  autoGenerate.value = m.auto_generate !== false
  step.value = 'edit'
}

function onGroupTypeChange(value: DeviceGroupKind) {
  const option = GROUP_TYPE_OPTIONS.find((item) => item.value === value)
  form.role = option?.role || null
  if (value !== 'mixed') {
    for (const slot of slots.value) {
      slot.role = option?.role || null
      onSlotRoleChange(slot)
    }
  }
}

function modelsForSlot(slot: DeviceGroupSlot) {
  const models = props.designModels || []
  const want = nodeKindForGroupRole(slot.role)
  return models.filter((m) => {
    if (!slot.role) return true
    if (want === 'server') return m.category === 'server' || m.category === 'software'
    if (want === 'security') return m.category === 'security'
    return m.category === 'switch' || !['server', 'software', 'security'].includes(m.category)
  })
}

function onSlotRoleChange(slot: DeviceGroupSlot) {
  const allowed = new Set(modelsForSlot(slot).map((m) => m.id))
  if (slot.design_model_id && !allowed.has(slot.design_model_id)) {
    slot.design_model_id = null
  }
  if (!slot.label.trim() && slot.role) {
    slot.label = FABRIC_ROLE_OPTIONS.find((o) => o.value === slot.role)?.label || ''
  }
}

function onSlotModelChange(slot: DeviceGroupSlot) {
  const m = (props.designModels || []).find((x) => x.id === slot.design_model_id)
  if (m && !slot.label.trim()) slot.label = m.name
}

function addSlot() {
  slots.value.push(emptySlot({ count: 1, role: form.role }))
}

function removeSlot(idx: number) {
  if (slots.value.length <= 1) {
    ElMessage.warning('至少保留一种设备规格')
    return
  }
  slots.value.splice(idx, 1)
}

function upsertCatalog(entry: DeviceGroupDef, removeName?: string | null) {
  const next = props.catalog
    .filter((g) => g.name !== entry.name && g.name !== removeName)
    .map((g) => normalizeMeta(g))
  next.push(entry)
  emit('update:catalog', next.sort((a, b) => a.name.localeCompare(b.name, 'zh-CN')))
}

async function confirmSave() {
  const name = form.name.trim()
  if (!name) {
    ElMessage.warning('请填写组名')
    return
  }
  const original = editingOriginalName.value
  const groupCount = original ? 1 : Math.max(1, Math.min(100, Math.floor(Number(createGroupCount.value) || 1)))
  const targetNames = groupCount === 1
    ? [name]
    : Array.from({ length: groupCount }, (_, index) => `${name}-${String(index + 1).padStart(2, '0')}`)
  const occupiedName = targetNames.find((target) => allGroups.value.some((group) => group.name === target && group.name !== original))
  if (occupiedName) {
    ElMessage.warning(`设备组「${occupiedName}」已存在，请调整组名或组数`)
    return
  }
  const cleaned = slots.value
    .map((s) =>
      emptySlot({
        ...s,
        label: (s.label || '').trim() || FABRIC_ROLE_OPTIONS.find((o) => o.value === s.role)?.label || '设备',
        count: Math.max(1, Math.floor(Number(s.count) || 1)),
      }),
    )
    .filter((s) => s.count > 0)
  if (!cleaned.length) {
    ElMessage.warning('请至少添加一种设备（类型/模型 + 数量）')
    return
  }
  for (const s of cleaned) {
    if (!s.design_model_id) {
      ElMessage.warning(`请为「${s.label}」选择设计模型，否则无法放到拓扑或参与布线`)
      return
    }
  }

  if (original && original !== name) {
    emit('renameGroup', { from: original, to: name })
  }

  const primaryRole = form.role || cleaned[0]?.role || null
  const prevPool = original ? metaOf(original).port_pool : null
  const ruleIds = [...new Set(wiringRuleIds.value.filter(Boolean))]
  const baseEntry: DeviceGroupDef = {
    id: normalizeDeviceGroupId(original ? metaOf(original).id : null, name),
    name,
    role: primaryRole,
    description: form.description.trim(),
    group_type: groupType.value,
    slots: cleaned,
    instances: syncGroupInstances(name, cleaned, original ? metaOf(original).instances : null),
    wiring_rule_ids: ruleIds.length ? ruleIds : null,
    wiring_scope: wiringScope.value,
    auto_generate: autoGenerate.value,
    planned_count: totalSlotCount(cleaned),
    design_model_id: cleaned[0]?.design_model_id || null,
    port_pool: prevPool ?? null,
  }

  if (!original && groupCount > 1) {
    const entries = targetNames.map((targetName) => {
      const copiedSlots = cleaned.map((slot) => ({ ...slot, id: newSlotId() }))
      return {
        ...baseEntry,
        id: normalizeDeviceGroupId(null, targetName),
        name: targetName,
        slots: copiedSlots,
        instances: syncGroupInstances(targetName, copiedSlots, null),
        planned_count: totalSlotCount(copiedSlots),
        design_model_id: copiedSlots[0]?.design_model_id || null,
        port_pool: null,
      }
    })
    emit(
      'update:catalog',
      [...props.catalog.map((group) => normalizeMeta(group)), ...entries].sort((a, b) =>
        a.name.localeCompare(b.name, 'zh-CN'),
      ),
    )
    for (const targetName of targetNames) emit('created', targetName)
    if (linkedDeviceIds.value.length) ElMessage.info('批量建组不重复关联同一设备；请在各组中分别选择已有设备')
    ElMessage.success(`已创建 ${entries.length} 个相同类型的设备组`)
  } else {
    upsertCatalog(baseEntry, original && original !== name ? original : null)
    emit('bindDevices', {
      name,
      previousName: original,
      deviceIds: [...new Set(linkedDeviceIds.value.filter(Boolean))],
      candidateIds: topologyDeviceOptions.value.map((node) => node.id),
    })
    if (!original) emit('created', name)
    ElMessage.success(original ? `已更新设备组「${name}」` : `已创建设备组「${name}」`)
  }
  step.value = 'list'
  resetForm()
}

function confirmCloneGroups() {
  const source = metaOf(cloneSourceName.value)
  if (!cloneSourceName.value || !allGroups.value.some((group) => group.name === cloneSourceName.value)) {
    ElMessage.warning('请选择要克隆的源设备组')
    return
  }
  const prefix = cloneGroupPrefix.value.trim()
  if (!prefix) {
    ElMessage.warning('请输入新组名前缀')
    return
  }
  const count = Math.max(1, Math.min(100, Math.floor(Number(cloneCount.value) || 1)))
  const pattern = cloneGroupPattern.value.trim()
  if (!pattern) {
    ElMessage.warning('请输入组名顺序规则')
    return
  }
  if (count > 1 && !/\{index(?::\d+)?\}/.test(pattern)) {
    ElMessage.warning('批量克隆多个组时，组名规则必须包含 {index} 或 {index:02} 序号占位符')
    return
  }
  const previewName = formatDeviceGroupSequenceName(pattern, {
    group: '', label: '', index: Math.max(0, Math.floor(Number(cloneStartNo.value) || 1)), prefix, source: source.name,
  })
  if (!previewName) {
    ElMessage.warning('组名顺序规则生成的名称为空，请加入前缀、源组名或序号占位符')
    return
  }
  const occupied = new Set(props.catalog.map((group) => group.name))
  const groups: DeviceGroupDef[] = []
  let serial = Math.max(0, Math.floor(Number(cloneStartNo.value) || 1))
  while (groups.length < count) {
    const name = formatDeviceGroupSequenceName(pattern, {
      group: '',
      label: '',
      index: serial,
      prefix,
      source: source.name,
    })
    serial += 1
    if (occupied.has(name)) continue
    occupied.add(name)
    const clonedSlots = migrateSlotsFromLegacy(source).map((slot) => ({ ...slot, id: newSlotId() }))
    groups.push({
      ...source,
      id: normalizeDeviceGroupId(null, name),
      name,
      description: source.description ? `${source.description}（克隆自 ${source.name}）` : `克隆自 ${source.name}`,
      slots: clonedSlots,
      planned_count: totalSlotCount(clonedSlots),
      design_model_id: clonedSlots[0]?.design_model_id || null,
      port_pool: null,
      wiring_rule_ids: source.wiring_rule_ids ? [...source.wiring_rule_ids] : null,
    })
  }
  emit(
    'update:catalog',
    [...props.catalog.map((group) => normalizeMeta(group)), ...groups].sort((a, b) =>
      a.name.localeCompare(b.name, 'zh-CN'),
    ),
  )
  emit('cloneGroups', {
    sourceName: source.name,
    groups,
    fullClone: cloneFull.value,
    devicePrefix: cloneDevicePrefix.value.trim() || 'DEV-',
  })
  ElMessage.success(`已快速创建 ${groups.length} 个克隆组`)
  step.value = 'list'
}

async function onDeleteGroup(name: string) {
  try {
    await ElMessageBox.confirm(
      `删除设备组「${name}」将同时删除当前拓扑画布中的组内设备及相关连线。确认删除？`,
      '删除设备组',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  emit('deleteGroup', name)
  emit(
    'update:catalog',
    props.catalog.filter((g) => g.name !== name).map((g) => normalizeMeta(g)),
  )
  if (editingOriginalName.value === name) {
    step.value = 'list'
    resetForm()
  }
  ElMessage.success(`已删除组「${name}」`)
}

function onGroupSelectionChange(rows: DeviceGroupDef[]) {
  selectedGroupNames.value = rows.map((row) => row.name)
}

async function onBatchDeleteGroups() {
  const names = [...new Set(selectedGroupNames.value.filter(Boolean))]
  if (!names.length) {
    ElMessage.warning('请先选择要删除的设备组')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${names.length} 个设备组？将同时删除当前拓扑中的组内设备及相关连线。`,
      '批量删除设备组',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  emit('deleteGroups', names)
  emit('update:catalog', props.catalog.filter((group) => !names.includes(group.name)).map((group) => normalizeMeta(group)))
  selectedGroupNames.value = []
  ElMessage.success(`已删除 ${names.length} 个设备组`)
}

const title = computed(() => {
  if (step.value === 'clone') return '批量克隆设备组'
  if (step.value !== 'edit') return '设备组管理'
  return editingOriginalName.value ? '编辑设备组' : '新建设备组'
})
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="title"
    width="min(1080px, 94vw)"
    destroy-on-close
    append-to-body
  >
    <div v-if="step === 'list'" class="group-list">
      <p class="hint">设备组作为拓扑与布线规则的稳定对象；组 ID、组类型、成员 ID 和规则范围会随组定义保存。</p>
      <el-table ref="groupTableRef" :data="tableRows" size="small" border empty-text="暂无设备组，请先新建" @selection-change="onGroupSelectionChange">
        <el-table-column type="selection" width="44" align="center" />
        <el-table-column prop="sequence" label="序号" width="58" align="center" />
        <el-table-column prop="name" label="组名" min-width="130" show-overflow-tooltip />
        <el-table-column prop="groupId" label="组 ID" min-width="122" show-overflow-tooltip />
        <el-table-column label="设备数量" width="86" align="center">
          <template #default="{ row }">
            <span :title="`当前拓扑 ${row.memberCount} 台；定义数量 ${row.totalCount} 台`">{{ row.memberCount || row.totalCount }}</span>
          </template>
        </el-table-column>
        <el-table-column label="组内设备 ID" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.memberIds.length ? row.memberIds.join('、') : '尚未关联' }}</template>
        </el-table-column>
        <el-table-column prop="groupTypeLabel" label="设备组类型" min-width="126" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button type="success" link size="small" @click="openClone(row.name)">克隆</el-button>
            <el-button type="primary" link size="small" @click="openEdit(row.name)">编辑</el-button>
            <el-button type="danger" link size="small" @click="onDeleteGroup(row.name)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="list-actions">
        <el-button :disabled="!allGroups.length" @click="groupTableRef?.toggleAllSelection()">全选</el-button>
        <el-button type="danger" plain :disabled="!selectedGroupNames.length" @click="onBatchDeleteGroups">删除</el-button>
        <el-button type="primary" @click="openCreate">新建组</el-button>
      </div>
    </div>

    <div v-else-if="step === 'clone'" class="clone-form">
      <el-alert type="info" :closable="false" show-icon class="clone-alert">
        完全克隆会为每个新组复制源组内部实例的模型、角色与子组归属，生成独立设备实例；连线不会复制。
        非完全克隆按子组计划数量新建设备，并按设备名前缀连续编号。
      </el-alert>
      <el-form label-width="110px">
        <el-form-item label="源设备组" required>
          <el-select v-model="cloneSourceName" filterable style="width: 100%" @change="onCloneSourceChange">
            <el-option v-for="group in allGroups" :key="group.name" :label="group.name" :value="group.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="克隆组数量" required>
          <el-input-number v-model="cloneCount" :min="1" :max="100" controls-position="right" />
        </el-form-item>
        <el-form-item label="新组名前缀" required>
          <el-input v-model="cloneGroupPrefix" placeholder="如 POD- / ACCESS-GROUP-" />
        </el-form-item>
        <el-form-item label="组名顺序规则" required>
          <el-input v-model="cloneGroupPattern" placeholder="如 {prefix}{index:02} / {source}-A-{index:03}" />
          <p class="slot-hint">支持 {prefix}、{source}、{index}、{index:03}，可自由定义编号位置和补零宽度。</p>
        </el-form-item>
        <el-form-item label="起始编号">
          <el-input-number v-model="cloneStartNo" :min="0" :max="9999" controls-position="right" />
        </el-form-item>
        <el-form-item label="完全克隆">
          <el-switch v-model="cloneFull" active-text="复制当前组内设备" inactive-text="按子组定义生成" />
        </el-form-item>
        <el-form-item v-if="!cloneFull" label="设备名前缀" required>
          <el-input v-model="cloneDevicePrefix" placeholder="如 SERVER- / SW-" />
        </el-form-item>
      </el-form>
    </div>

    <div v-else class="edit-form">
      <div class="create-guide">组 ID 自动生成；保存后按设备模型与台数在设备组内部生成实例，默认不占用拓扑画布。</div>
      <el-form label-width="88px" size="default" class="group-create-form">
        <el-form-item label="组名" required class="field-name">
          <el-input v-model="form.name" placeholder="如 ACCESS-A / SER-POD1" maxlength="80" />
        </el-form-item>
        <el-form-item v-if="!editingOriginalName" label="类似组数量" required class="field-count">
          <el-input-number v-model="createGroupCount" :min="1" :max="100" controls-position="right" />
          <p class="slot-hint">
            设置为多个时，将按“{{ form.name || '组名' }}-01、{{ form.name || '组名' }}-02…”创建相同类型和子组配置。
          </p>
        </el-form-item>
        <el-form-item label="设备组类型" required class="field-kind">
          <el-select v-model="groupType" style="width: 100%" @change="onGroupTypeChange">
            <el-option v-for="option in GROUP_TYPE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述" class="field-description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            placeholder="如：接入平面 A；可含交换机与服务器混合"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="设备配置" required class="field-devices">
          <div class="slots">
            <div class="slot-row slot-row-head" aria-hidden="true">
              <span>设备类型</span><span>设备模型</span><span>子组名称</span><span>设备命名规则</span><span>创建台数</span><span>操作</span>
            </div>
            <div v-for="(slot, idx) in slots" :key="slot.id" class="slot-row">
              <el-select
                v-model="slot.role"
                clearable
                placeholder="设备类型"
                style="width: 120px"
                @change="onSlotRoleChange(slot)"
              >
                <el-option
                  v-for="o in FABRIC_ROLE_OPTIONS"
                  :key="o.value"
                  :label="o.label"
                  :value="o.value"
                />
              </el-select>
              <el-select
                v-model="slot.design_model_id"
                filterable
                clearable
                placeholder="关联模型 / 已创建模型"
                style="flex: 1; min-width: 140px"
                @change="onSlotModelChange(slot)"
              >
                <el-option
                  v-for="m in modelsForSlot(slot)"
                  :key="m.id"
                  :label="`${m.name}（${m.category}）`"
                  :value="m.id"
                />
              </el-select>
              <el-input v-model="slot.label" placeholder="子组名称" style="width: 110px" />
              <el-input
                v-model="slot.name_pattern"
                placeholder="设备命名：{label}-{index:03}"
                title="支持 {group}、{label}、{index}、{index:03}"
                style="width: 210px"
              />
              <el-input-number
                v-model="slot.count"
                :min="1"
                :max="5000"
                controls-position="right"
                style="width: 110px"
              />
              <el-button type="danger" link :disabled="slots.length <= 1" @click="removeSlot(idx)">
                删除
              </el-button>
            </div>
            <el-button type="primary" plain @click="addSlot">添加设备</el-button>
            <p class="slot-hint">
              不同类型请分成不同子组（如「接入交换机」「服务器」）。新建布线规则时，源/目标可选整组或某一子组。
            </p>
          </div>
        </el-form-item>

        <el-form-item label="生成方式" class="field-generation">
          <el-checkbox v-model="autoGenerate">
            拖入拓扑时，根据子组设置数量自动补齐缺少的设备
          </el-checkbox>
          <p class="slot-hint">
            已关联的拓扑设备会优先占用对应子组名额；关闭后拖入只使用已有成员，不生成新设备。
          </p>
        </el-form-item>

        <el-form-item label="关联设备" class="field-linked">
          <el-select
            v-model="linkedDeviceIds"
            multiple
            filterable
            clearable
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择当前拓扑中的设备名称"
            :disabled="!editingOriginalName && createGroupCount > 1"
            style="width: 100%"
          >
            <el-option
              v-for="node in topologyDeviceOptions"
              :key="node.id"
              :label="topologyDeviceLabel(node)"
              :value="node.id"
            />
          </el-select>
          <p class="slot-hint">
            保存后立即更新当前拓扑的设备组成员关系；已属于其他设备组的设备将转移到本组。
          </p>
        </el-form-item>

        <el-form-item label="组内布线规则" class="field-rules">
          <el-select
            v-model="wiringRuleIds"
            multiple
            filterable
            clearable
            collapse-tags
            collapse-tags-tooltip
            placeholder="拖入画布后自动执行这些布线规则"
            style="width: 100%"
          >
            <el-option
              v-for="r in wiringRules || []"
              :key="r.id"
              :label="r.enabled === false ? `${r.name}（已停用）` : r.name"
              :value="r.id"
              :disabled="r.enabled === false"
            />
          </el-select>
          <p class="slot-hint">
            无规则时可先到左侧「规则管理」创建。规则中请把本组设为源/目标组之一。
          </p>
        </el-form-item>
        <el-form-item label="规则作用域" class="field-scope">
          <el-radio-group v-model="wiringScope">
            <el-radio-button value="group">仅组内执行</el-radio-button>
            <el-radio-button value="topology">整个拓扑执行</el-radio-button>
          </el-radio-group>
          <p class="slot-hint">预留给布线引擎：仅组内限制端点为本组/子组；整个拓扑允许规则继续匹配其它设备组。</p>
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <template v-if="step === 'list'">
        <el-button @click="visible = false">关闭</el-button>
      </template>
      <template v-else-if="step === 'clone'">
        <el-button @click="step = 'list'">返回列表</el-button>
        <el-button type="success" @click="confirmCloneGroups">批量克隆</el-button>
      </template>
      <template v-else>
        <el-button @click="step = 'list'; resetForm()">返回列表</el-button>

        <el-button
          v-if="editingOriginalName"
          type="success"
          plain
          @click="openClone(editingOriginalName)"
        >
          克隆此组
        </el-button>
        <el-button
          v-if="editingOriginalName"
          type="danger"
          plain
          @click="onDeleteGroup(editingOriginalName)"
        >
          删除此组
        </el-button>
        <el-button type="primary" @click="confirmSave">{{ editingOriginalName ? '保存' : '创建并生成设备' }}</el-button>
      </template>
    </template>
  </el-dialog>
</template>

<style scoped>
.hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}
.list-actions {
  display: grid;
  grid-template-columns: auto auto 1fr;
  gap: 10px;
  margin-top: 12px;
}
.list-actions .el-button:last-child { justify-self: end; }
.create-guide {
  margin-bottom: 10px;
  padding: 7px 10px;
  border-left: 3px solid #409eff;
  border-radius: 3px;
  background: #f4f8ff;
  color: #606266;
  font-size: 12px;
  line-height: 1.45;
}
.clone-alert {
  margin-bottom: 16px;
  line-height: 1.55;
}
.kind-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.slots {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.slot-row {
  display: grid;
  grid-template-columns: 120px minmax(180px, 1fr) 110px 210px 110px 50px;
  align-items: center;
  gap: 8px;
}
.slot-row > :deep(.el-select),
.slot-row > :deep(.el-input),
.slot-row > :deep(.el-input-number) { width: 100% !important; min-width: 0 !important; }
.slot-row-head {
  padding: 0 4px 4px;
  color: #606266;
  font-size: 12px;
  font-weight: 600;
  border-bottom: 1px solid #ebeef5;
}
.group-create-form {
  max-width: 100%;
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  column-gap: 12px;
  align-items: start;
}
.group-create-form :deep(.el-form-item) { margin-bottom: 10px; }
.group-create-form :deep(.el-form-item__content) { min-width: 0; }
.field-name { grid-column: span 4; }
.field-count { grid-column: span 3; }
.field-kind { grid-column: span 5; }
.field-description,
.field-devices { grid-column: 1 / -1; }
.field-generation,
.field-linked { grid-column: span 6; }
.field-rules { grid-column: span 8; }
.field-scope { grid-column: span 4; }
.field-count .slot-hint { display: none; }
.field-description :deep(textarea) { min-height: 52px !important; }
.slot-hint {
  margin: 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.45;
}
@media (max-width: 920px) {
  .group-create-form { grid-template-columns: 1fr; }
  .field-name,
  .field-count,
  .field-kind,
  .field-description,
  .field-devices,
  .field-generation,
  .field-linked,
  .field-rules,
  .field-scope { grid-column: 1; }
  .slot-row { grid-template-columns: 1fr 1fr; }
  .slot-row-head { display: none; }
}
</style>
