<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import TopologyGroupIcon from '@/components/TopologyGroupIcon.vue'
import {
  emptySlot,
  migrateSlotsFromLegacy,
  newSlotId,
  summarizeSlots,
  totalSlotCount,
  type DeviceGroupDef,
  type DeviceGroupPortRef,
  type DeviceGroupSlot,
} from '@/utils/deviceGroupSlots'
import { FABRIC_ROLE_OPTIONS, type FabricRole } from '@/utils/wiringTypes'
import { groupKindFromRole, groupKindLabel, nodeKindForGroupRole } from '@/utils/deviceGroupVisual'

export type { DeviceGroupPortRef, DeviceGroupSlot }
/** @deprecated 兼容旧 import 名 */
export type DeviceGroupMeta = DeviceGroupDef

const props = defineProps<{
  modelValue: boolean
  catalog: DeviceGroupDef[]
  designModels?: Array<{ id: string; name: string; category: string }>
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
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const step = ref<'list' | 'edit'>('list')
const editingOriginalName = ref<string | null>(null)
const form = reactive({
  name: '',
  role: null as FabricRole | null,
  description: '',
})
const slots = ref<DeviceGroupSlot[]>([])
const wiringRuleIds = ref<string[]>([])

function normalizeMeta(raw: Partial<DeviceGroupDef> & { note?: string; name: string }): DeviceGroupDef {
  const migrated = migrateSlotsFromLegacy(raw)
  const primaryRole = raw.role || migrated[0]?.role || null
  const ruleIds = Array.isArray(raw.wiring_rule_ids)
    ? raw.wiring_rule_ids.filter((x): x is string => typeof x === 'string' && !!x.trim())
    : []
  return {
    name: raw.name,
    role: (primaryRole as FabricRole | null) || null,
    description: (raw.description ?? raw.note ?? '').toString(),
    slots: migrated,
    wiring_rule_ids: ruleIds.length ? ruleIds : null,
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
  allGroups.value.map((g) => ({
    ...g,
    slotSummary: summarizeSlots(g.slots, props.designModels),
    totalCount: totalSlotCount(g.slots),
    ruleCount: g.wiring_rule_ids?.length || 0,
  })),
)

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
  form.role = null
  form.description = ''
  slots.value = [emptySlot({ count: 2, role: 'ACCESS' })]
  wiringRuleIds.value = []
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

function openEdit(name: string) {
  const m = metaOf(name)
  editingOriginalName.value = name
  form.name = m.name
  form.role = m.role
  form.description = m.description
  slots.value = migrateSlotsFromLegacy(m).map((s) => ({ ...s, id: s.id || newSlotId() }))
  if (!slots.value.length) slots.value = [emptySlot({ role: m.role, count: 1 })]
  wiringRuleIds.value = [...(m.wiring_rule_ids || [])]
  step.value = 'edit'
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
  if (allGroups.value.some((g) => g.name === name && g.name !== original)) {
    ElMessage.warning('组名已存在')
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
  upsertCatalog(
    {
      name,
      role: primaryRole,
      description: form.description.trim(),
      slots: cleaned,
      wiring_rule_ids: ruleIds.length ? ruleIds : null,
      planned_count: totalSlotCount(cleaned),
      design_model_id: cleaned[0]?.design_model_id || null,
      port_pool: prevPool ?? null,
    },
    original && original !== name ? original : null,
  )

  if (!original) emit('created', name)
  ElMessage.success(original ? `已更新设备组「${name}」` : `已创建设备组「${name}」`)
  step.value = 'list'
  resetForm()
}

async function onDeleteGroup(name: string) {
  try {
    await ElMessageBox.confirm(
      `删除设备组「${name}」仅删除组定义，不会删除各拓扑画布上已放置的设备。确认删除？`,
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

const title = computed(() => {
  if (step.value !== 'edit') return '设备组管理'
  return editingOriginalName.value ? '编辑设备组' : '新建设备组'
})
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="title"
    width="780px"
    destroy-on-close
    append-to-body
  >
    <div v-if="step === 'list'" class="group-list">
      <p class="hint">
        设备组内按<strong>类型分子组</strong>（每种类型一条）。新建布线规则时，源/目标可选「整组」或「组 / 子组」。
        拖到画布会实例化各子组设备并打上对应标签，便于自动布线。
      </p>
      <el-table :data="tableRows" size="small" border empty-text="暂无设备组，请先新建">
        <el-table-column prop="name" label="组名" min-width="110" show-overflow-tooltip />
        <el-table-column prop="description" label="描述" min-width="100" show-overflow-tooltip>
          <template #default="{ row }">{{ row.description || '—' }}</template>
        </el-table-column>
        <el-table-column label="子组规格" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.slotSummary }}</template>
        </el-table-column>
        <el-table-column label="合计" width="64" align="center">
          <template #default="{ row }">{{ row.totalCount }}</template>
        </el-table-column>
        <el-table-column label="规则" width="64" align="center">
          <template #default="{ row }">{{ row.ruleCount || '—' }}</template>
        </el-table-column>
        <el-table-column label="图标" width="100">
          <template #default="{ row }">
            <span class="kind-cell">
              <TopologyGroupIcon :kind="groupKindFromRole(row.role)" :size="28" />
              <span>{{ groupKindLabel(row.role) }}</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openEdit(row.name)">编辑</el-button>
            <el-button type="danger" link size="small" @click="onDeleteGroup(row.name)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-button type="primary" plain class="add-btn" @click="openCreate">新建组</el-button>
    </div>

    <div v-else class="edit-form">
      <el-form label-width="88px" size="default">
        <el-form-item label="组名" required>
          <el-input v-model="form.name" placeholder="如 ACCESS-A / SER-POD1" maxlength="80" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            placeholder="如：接入平面 A；可含交换机与服务器混合"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="组图标">
          <el-select v-model="form.role" clearable placeholder="可选，默认取首个槽位类型" style="width: 100%">
            <el-option
              v-for="o in FABRIC_ROLE_OPTIONS"
              :key="o.value"
              :label="`${o.label}（${groupKindLabel(o.value)}）`"
              :value="o.value"
            />
          </el-select>
          <div class="kind-preview">
            <TopologyGroupIcon :kind="groupKindFromRole(form.role || slots[0]?.role)" :size="36" />
            <span>{{ groupKindLabel(form.role || slots[0]?.role) }}</span>
          </div>
        </el-form-item>

        <el-form-item label="子组设备" required>
          <div class="slots">
            <div v-for="(slot, idx) in slots" :key="slot.id" class="slot-row">
              <el-select
                v-model="slot.role"
                clearable
                placeholder="角色/类型"
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
                placeholder="设计模型"
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
              <el-input v-model="slot.label" placeholder="子组名" style="width: 110px" />
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
            <el-button type="primary" link @click="addSlot">+ 添加子组（不同类型）</el-button>
            <p class="slot-hint">
              不同类型请分成不同子组（如「接入交换机」「服务器」）。新建布线规则时，源/目标可选整组或某一子组。
            </p>
          </div>
        </el-form-item>

        <el-form-item label="绑定规则">
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
      </el-form>
    </div>

    <template #footer>
      <template v-if="step === 'list'">
        <el-button @click="visible = false">关闭</el-button>
      </template>
      <template v-else>
        <el-button @click="step = 'list'; resetForm()">返回列表</el-button>
        <el-button
          v-if="editingOriginalName"
          type="danger"
          plain
          @click="onDeleteGroup(editingOriginalName)"
        >
          删除此组
        </el-button>
        <el-button type="primary" @click="confirmSave">保存</el-button>
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
.add-btn {
  width: 100%;
  margin-top: 12px;
}
.kind-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.kind-preview {
  margin-top: 8px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #606266;
}
.slots {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.slot-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.slot-hint {
  margin: 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.45;
}
</style>
