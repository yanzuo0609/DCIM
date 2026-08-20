<script setup lang="ts">
import { computed } from 'vue'
import TopologyGroupIcon from '@/components/TopologyGroupIcon.vue'
import type { NetworkLink, NetworkNode } from '@/api/network'
import type { DeviceGroupMeta } from '@/components/DeviceGroupManageDialog.vue'
import { FABRIC_ROLE_OPTIONS } from '@/utils/wiringTypes'
import { listGroupMembers } from '@/utils/deviceGroups'
import { migrateSlotsFromLegacy, normalizeDeviceGroupId, syncGroupInstances } from '@/utils/deviceGroupSlots'
import { DEVICE_GROUP_KIND_LABELS, resolveDeviceGroupKind } from '@/utils/deviceGroupVisual'

const props = defineProps<{
  modelValue: boolean
  groupName: string | null
  catalog: DeviceGroupMeta[]
  nodes: NetworkNode[]
  links: NetworkLink[]
  designModels?: Array<{ id: string; name: string }>
  wiringRules?: Array<{ id: string; name: string; enabled?: boolean }>
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const meta = computed(() => {
  const name = props.groupName
  if (!name) return null
  const found = props.catalog.find((g) => g.name === name)
  if (!found) {
    return {
      name,
      role: null,
      description: '',
      slots: [],
      planned_count: null,
      port_pool: null,
    } as DeviceGroupMeta
  }
  const slots = migrateSlotsFromLegacy(found)
  return {
    ...found,
    slots,
    instances: syncGroupInstances(found.name, slots, found.instances),
  }
})

const slots = computed(() => (meta.value ? migrateSlotsFromLegacy(meta.value) : []))

const topologyMembers = computed(() => {
  const name = props.groupName
  if (!name) return []
  return listGroupMembers(props.nodes, name)
})

const members = computed(() => meta.value?.instances || [])

const memberIds = computed(() => new Set(topologyMembers.value.map((m) => m.id)))

const nodeName = (id: string) => props.nodes.find((n) => n.id === id)?.name || id.slice(0, 8)

const wiringRows = computed(() => {
  const ids = memberIds.value
  return props.links
    .filter((l) => ids.has(l.source_node_id) || ids.has(l.target_node_id))
    .map((l) => ({
      id: l.id,
      source: `${nodeName(l.source_node_id)} · ${l.source_port}`,
      target: `${nodeName(l.target_node_id)} · ${l.target_port}`,
      label: l.label || '—',
      type: l.link_type || '—',
      viaRule: !!l.wiring_rule_id,
    }))
})

const roleLabel = computed(() => {
  const role = meta.value?.role || slots.value[0]?.role
  if (!role) return '混合/未指定'
  return FABRIC_ROLE_OPTIONS.find((o) => o.value === role)?.label || role
})

const visualKind = computed(() =>
  meta.value?.group_type || resolveDeviceGroupKind({
    role: meta.value?.role,
    slotRoles: slots.value.map((s) => s.role),
    members: topologyMembers.value,
  }),
)

const portPoolRows = computed(() => {
  const pool = meta.value?.port_pool
  if (!pool?.length) return []
  return pool.map((p) => ({
    node: nodeName(p.node_id),
    port: p.port_label || p.port_id,
  }))
})

const boundRules = computed(() => {
  const ids = new Set(meta.value?.wiring_rule_ids || [])
  if (!ids.size) return []
  return (props.wiringRules || []).filter((r) => ids.has(r.id))
})

const wiringPatternHint = computed(() => {
  if (!boundRules.value.length && !wiringRows.value.length) {
    return '未绑定规则且本拓扑暂无组相关连线。可在组编辑中绑定规则，拖入画布后自动布线。'
  }
  if (boundRules.value.length) {
    return `已绑定 ${boundRules.value.length} 条规则：${boundRules.value.map((r) => r.name).join('、')}`
  }
  return `本拓扑组相关连线 ${wiringRows.value.length} 条`
})
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="groupName ? `设备组详情 · ${groupName}` : '设备组详情'"
    width="720px"
    destroy-on-close
    append-to-body
  >
    <template v-if="meta">
      <div class="detail-head">
        <TopologyGroupIcon :kind="visualKind" :size="48" :count="members.length || null" />
        <div>
          <div class="detail-kind">{{ DEVICE_GROUP_KIND_LABELS[visualKind] }}</div>
          <div class="detail-role">{{ roleLabel }}</div>
        </div>
      </div>
      <el-descriptions :column="2" size="small" border class="meta-block">
        <el-descriptions-item label="组 ID">{{ normalizeDeviceGroupId(meta.id, meta.name) }}</el-descriptions-item>
        <el-descriptions-item label="设备组类型">{{ DEVICE_GROUP_KIND_LABELS[visualKind] }}</el-descriptions-item>
        <el-descriptions-item label="组图标角色">{{ roleLabel }}</el-descriptions-item>
        <el-descriptions-item label="组内实例设备">{{ members.length }}</el-descriptions-item>
        <el-descriptions-item label="描述">{{ meta.description || '—' }}</el-descriptions-item>
        <el-descriptions-item label="布线方式" :span="2">{{ wiringPatternHint }}</el-descriptions-item>
        <el-descriptions-item label="规则作用域" :span="2">{{ meta.wiring_scope === 'topology' ? '整个拓扑执行' : '仅组内执行' }}</el-descriptions-item>
      </el-descriptions>

      <h4 class="section-title">组内实例化设备</h4>
      <el-table :data="members" size="small" border empty-text="组内尚未生成设备实例" max-height="220">
        <el-table-column type="index" label="序号" width="64" align="center" />
        <el-table-column prop="name" label="设备名称" min-width="150" show-overflow-tooltip />
        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            {{
              FABRIC_ROLE_OPTIONS.find((o) => o.value === row.role)?.label ||
              row.role ||
              '—'
            }}
          </template>
        </el-table-column>
        <el-table-column prop="id" label="设备 ID" min-width="210" show-overflow-tooltip />
      </el-table>

      <h4 class="section-title">绑定规则</h4>
      <el-table
        :data="boundRules"
        size="small"
        border
        empty-text="未绑定规则（编辑组时可添加）"
        max-height="120"
      >
        <el-table-column prop="name" label="规则名" min-width="160" />
        <el-table-column label="状态" width="88">
          <template #default="{ row }">
            {{ row.enabled === false ? '停用' : '启用' }}
          </template>
        </el-table-column>
      </el-table>

      <h4 class="section-title">本拓扑组内/相关连线</h4>
      <el-table :data="wiringRows" size="small" border empty-text="暂无相关连线" max-height="220">
        <el-table-column prop="source" label="本端" min-width="160" show-overflow-tooltip />
        <el-table-column prop="target" label="对端" min-width="160" show-overflow-tooltip />
        <el-table-column prop="type" label="类型" width="90" />
        <el-table-column prop="label" label="标签" width="90" show-overflow-tooltip />
        <el-table-column label="来源" width="88">
          <template #default="{ row }">
            {{ row.viaRule ? '布线规则' : '手动' }}
          </template>
        </el-table-column>
      </el-table>

      <template v-if="portPoolRows.length">
        <h4 class="section-title">已分配端口池（内部）</h4>
        <el-table :data="portPoolRows" size="small" border max-height="140">
          <el-table-column prop="node" label="设备" min-width="140" />
          <el-table-column prop="port" label="端口" min-width="120" />
        </el-table>
      </template>
    </template>

    <template #footer>
      <el-button type="primary" @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.meta-block {
  margin-bottom: 8px;
}
.detail-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.detail-kind {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}
.detail-role {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}
.section-title {
  margin: 16px 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}
</style>
