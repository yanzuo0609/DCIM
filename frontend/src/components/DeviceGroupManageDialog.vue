<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { NetworkNode } from '@/api/network'
import { FABRIC_ROLE_OPTIONS, type FabricRole } from '@/utils/wiringTypes'
import { resolveNodeFabricRole } from '@/utils/fabricRole'

export interface DeviceGroupMeta {
  name: string
  /** 组内设备统一角色（可选） */
  role: FabricRole | null
  /** 描述 */
  description: string
}

const props = defineProps<{
  modelValue: boolean
  nodes: NetworkNode[]
  catalog: DeviceGroupMeta[]
  initialGroup?: string | null
  mode?: 'manage' | 'create'
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
  'update:catalog': [list: DeviceGroupMeta[]]
  created: [name: string]
  assign: [payload: { group: string; nodeIds: string[]; role: FabricRole | null }]
  removeMembers: [payload: { group: string; nodeIds: string[] }]
  renameGroup: [payload: { from: string; to: string }]
  deleteGroup: [name: string]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const step = ref<'list' | 'edit'>('list')
/** 编辑中的原组名；新建时为空 */
const editingOriginalName = ref<string | null>(null)
const form = reactive({
  name: '',
  role: null as FabricRole | null,
  description: '',
})
const memberIds = ref<string[]>([])

const canvasNodes = computed(() => props.nodes.filter((n) => n.on_canvas !== false))

const groupsFromNodes = computed(() => {
  const set = new Set<string>()
  for (const n of canvasNodes.value) {
    const g = (n.device_group || '').trim()
    if (g) set.add(g)
  }
  return set
})

function normalizeMeta(raw: Partial<DeviceGroupMeta> & { note?: string; name: string }): DeviceGroupMeta {
  return {
    name: raw.name,
    role: (raw.role as FabricRole | null) || null,
    description: (raw.description ?? raw.note ?? '').toString(),
  }
}

const allGroups = computed(() => {
  const map = new Map<string, DeviceGroupMeta>()
  for (const g of props.catalog) {
    if (g?.name) map.set(g.name, normalizeMeta(g as DeviceGroupMeta & { note?: string }))
  }
  for (const name of groupsFromNodes.value) {
    if (!map.has(name)) {
      map.set(name, { name, role: null, description: '' })
    }
  }
  return [...map.values()].sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
})

const tableRows = computed(() =>
  allGroups.value.map((g) => ({
    ...g,
    memberCount: membersOf(g.name).length,
  })),
)

function membersOf(group: string) {
  return canvasNodes.value.filter((n) => (n.device_group || '').trim() === group)
}

function metaOf(name: string): DeviceGroupMeta {
  return allGroups.value.find((g) => g.name === name) || { name, role: null, description: '' }
}

function resetForm() {
  form.name = ''
  form.role = null
  form.description = ''
  memberIds.value = []
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
  memberIds.value = membersOf(name).map((n) => n.id)
  step.value = 'edit'
}

function upsertCatalog(entry: DeviceGroupMeta, removeName?: string | null) {
  const next = props.catalog
    .filter((g) => g.name !== entry.name && g.name !== removeName)
    .map((g) => normalizeMeta(g as DeviceGroupMeta & { note?: string }))
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
  const conflict = allGroups.value.some((g) => g.name === name && g.name !== original)
  if (conflict) {
    ElMessage.warning('组名已存在')
    return
  }

  if (original && original !== name) {
    emit('renameGroup', { from: original, to: name })
  }

  const prev = new Set(original ? membersOf(original).map((n) => n.id) : [])
  const next = new Set(memberIds.value)
  const removed = [...prev].filter((id) => !next.has(id))
  if (removed.length && original) {
    emit('removeMembers', { group: original, nodeIds: removed })
  }
  emit('assign', {
    group: name,
    nodeIds: [...next],
    role: form.role,
  })

  upsertCatalog(
    { name, role: form.role, description: form.description.trim() },
    original && original !== name ? original : null,
  )

  if (!original) emit('created', name)
  ElMessage.success(original ? `已更新组「${name}」` : `已创建组「${name}」`)
  step.value = 'list'
  resetForm()
}

async function onDeleteGroup(name: string) {
  try {
    await ElMessageBox.confirm(
      `删除组「${name}」后，组内设备将取消分组（设备本身保留）。确认删除？`,
      '删除设备组',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  emit('deleteGroup', name)
  emit(
    'update:catalog',
    props.catalog
      .filter((g) => g.name !== name)
      .map((g) => normalizeMeta(g as DeviceGroupMeta & { note?: string })),
  )
  if (editingOriginalName.value === name) {
    step.value = 'list'
    resetForm()
  }
  ElMessage.success(`已删除组「${name}」`)
}

function deviceOptionLabel(n: NetworkNode) {
  const role = resolveNodeFabricRole(n)
  const g = (n.device_group || '').trim()
  const editing = editingOriginalName.value
  if (g && g !== editing) return `${n.name} [${role}] · 当前：${g}`
  if (g && g === editing) return `${n.name} [${role}]`
  return `${n.name} [${role}] · 未分组`
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
    width="640px"
    destroy-on-close
    append-to-body
  >
    <!-- 列表 -->
    <div v-if="step === 'list'" class="group-list">
      <p class="hint">
        不同设备可归属不同组；同一设备同一时刻只属于一个组。可将设备从一组改到另一组。
      </p>
      <el-table :data="tableRows" size="small" border empty-text="暂无设备组，请先新建">
        <el-table-column prop="name" label="组名" min-width="120" show-overflow-tooltip />
        <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.description || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="统一角色" width="110">
          <template #default="{ row }">
            {{ FABRIC_ROLE_OPTIONS.find((o) => o.value === row.role)?.label || row.role || '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="memberCount" label="设备数" width="72" align="center" />
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

    <!-- 新建 / 编辑 -->
    <div v-else class="edit-form">
      <el-form label-width="88px" size="default">
        <el-form-item label="组名" required>
          <el-input v-model="form.name" placeholder="如 ACCESS-A / CORE-G01" maxlength="80" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            placeholder="如：接入层 A 平面主备 / 同功能互联设备"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="统一角色">
          <el-select v-model="form.role" clearable placeholder="可选，保存时同步到组内设备" style="width: 100%">
            <el-option
              v-for="o in FABRIC_ROLE_OPTIONS"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="组成员">
          <el-select
            v-model="memberIds"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择画布设备；已在其他组的设备加入后将改属本组"
            style="width: 100%"
          >
            <el-option
              v-for="n in canvasNodes"
              :key="n.id"
              :label="deviceOptionLabel(n)"
              :value="n.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <p class="hint small">
        保存后请再点拓扑工具栏「保存布局」持久化。一台设备可随时改到其他组。
      </p>
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
.hint.small {
  font-size: 12px;
  color: #909399;
}
.add-btn {
  width: 100%;
  margin-top: 12px;
}
</style>
