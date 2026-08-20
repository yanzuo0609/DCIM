<script setup lang="ts">
import { computed, ref } from 'vue'
import TopologyGroupIcon from '@/components/TopologyGroupIcon.vue'
import { NODE_KIND_LABELS, type NetworkNode } from '@/api/network'
import type { DeviceGroupMeta } from '@/components/DeviceGroupManageDialog.vue'
import { FABRIC_ROLE_OPTIONS } from '@/utils/wiringTypes'
import { nodeInGroup } from '@/utils/deviceGroups'
import { migrateSlotsFromLegacy, summarizeSlots, totalSlotCount } from '@/utils/deviceGroupSlots'
import { DEVICE_GROUP_KIND_LABELS, resolveDeviceGroupKind } from '@/utils/deviceGroupVisual'
import { setDeviceGroupDragData } from '@/utils/topologyDnd'

const props = defineProps<{
  catalog: DeviceGroupMeta[]
  nodes: NetworkNode[]
  /** 可选：用于摘要显示模型名 */
  designModels?: Array<{ id: string; name: string }>
  selectedNode?: string | null
  selectedGroup?: string | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  select: [name: string]
  selectDevice: [id: string]
  detailDevice: [id: string]
  create: []
  edit: [name: string]
  detail: [name: string]
  manage: []
}>()

const activeTab = ref<'devices' | 'groups'>('groups')

const modelNameMap = computed(() => new Map((props.designModels || []).map((model) => [model.id, model.name])))

const deviceRows = computed(() =>
  props.nodes
    .filter((node) => node.on_canvas !== false && !!node.design_model_id)
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name, 'zh-CN', { numeric: true }))
    .map((node) => ({
      ...node,
      kindLabel: NODE_KIND_LABELS[node.kind] || node.kind,
      modelName: modelNameMap.value.get(node.design_model_id || '') || '模型实例',
      roleLabel:
        FABRIC_ROLE_OPTIONS.find((option) => option.value === node.network_role)?.label ||
        node.network_role ||
        '未指定角色',
    })),
)

const rows = computed(() =>
  props.catalog
    .filter((g) => g?.name)
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
    .map((g) => {
      const slots = migrateSlotsFromLegacy(g)
      const members = props.nodes.filter((n) => n.on_canvas !== false && nodeInGroup(n, g.name))
      const onTopo = members.length
      const planned = totalSlotCount(slots)
      const kind = g.group_type || resolveDeviceGroupKind({
        role: g.role,
        slotRoles: slots.map((s) => s.role),
        members,
      })
      const kindLabel = DEVICE_GROUP_KIND_LABELS[kind]
      const roleLabel =
        FABRIC_ROLE_OPTIONS.find((o) => o.value === (g.role || slots[0]?.role))?.label ||
        g.role ||
        '混合/未指定'
      const slotSummary = summarizeSlots(slots, props.designModels)
      return {
        ...g,
        kind,
        kindLabel,
        roleLabel,
        planned,
        onTopo,
        slotSummary,
        summary:
          planned > 0
            ? `${slotSummary} · 本拓扑 ${onTopo}/${planned}`
            : `${kindLabel} · 本拓扑 ${onTopo} 台（请编辑组规格）`,
      }
    }),
)

function onDragStart(event: DragEvent, name: string) {
  if (props.disabled || !event.dataTransfer) {
    event.preventDefault()
    return
  }
  setDeviceGroupDragData(event.dataTransfer, { name })
}
</script>

<template>
  <div class="group-pane">
    <div class="pane-head">
      <el-radio-group v-model="activeTab" size="small" class="mode-switch">
        <el-radio-button value="devices">设备（{{ deviceRows.length }}）</el-radio-button>
        <el-radio-button value="groups">设备组（{{ rows.length }}）</el-radio-button>
      </el-radio-group>
      <div v-if="activeTab === 'groups'" class="pane-actions">
        <el-button type="primary" link size="small" :disabled="disabled" @click="emit('create')">
          新建
        </el-button>
        <el-button type="primary" link size="small" :disabled="disabled" @click="emit('manage')">
          管理
        </el-button>
      </div>
    </div>

    <template v-if="activeTab === 'devices'">
      <div v-if="!deviceRows.length" class="empty-hint">
        当前拓扑暂无通过模型生成并已放入画布的设备。右键设备可查看详细信息。
      </div>
      <div v-else class="group-list device-list">
        <button
          v-for="row in deviceRows"
          :key="row.id"
          type="button"
          class="device-card"
          :class="{ active: selectedNode === row.id }"
          title="左键选中设备；右键查看详细信息"
          @click="emit('selectDevice', row.id)"
          @contextmenu.prevent="emit('detailDevice', row.id)"
        >
          <span class="device-kind">{{ row.kindLabel.slice(0, 2) }}</span>
          <div class="meta">
            <span class="name">{{ row.name }}</span>
            <span class="sub">{{ row.modelName }} · {{ row.roleLabel }}</span>
            <span class="desc">ID：{{ row.id }}</span>
          </div>
          <el-button type="primary" link size="small" @click.stop="emit('detailDevice', row.id)">详情</el-button>
        </button>
      </div>
    </template>

    <div v-else-if="!rows.length" class="empty-hint">
      暂无设备组。组与画布独立：配置类型与数量后，可拖到拓扑，也可作为布线源/目标。
    </div>
    <div v-else class="group-list">
      <button
        v-for="row in rows"
        :key="row.name"
        type="button"
        class="group-card"
        :class="{ active: selectedGroup === row.name, disabled }"
        :draggable="!disabled"
        :title="disabled ? row.summary : `拖到画布放置「${row.name}」；右键查看组内详情`"
        @click="emit('select', row.name)"
        @contextmenu.prevent="emit('detail', row.name)"
        @dragstart="onDragStart($event, row.name)"
      >
        <TopologyGroupIcon :kind="row.kind" :size="40" :selected="selectedGroup === row.name" />
        <div class="meta">
          <span class="name">{{ row.name }}</span>
          <span class="sub">{{ row.summary }}</span>
          <span v-if="row.description" class="desc">{{ row.description }}</span>
        </div>
        <div class="card-actions" @click.stop>
          <el-button type="primary" link size="small" @click="emit('detail', row.name)">
            详情
          </el-button>
          <el-button
            type="primary"
            link
            size="small"
            :disabled="disabled"
            @click="emit('edit', row.name)"
          >
            编辑
          </el-button>
        </div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.group-pane {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.pane-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.mode-switch { flex-shrink: 0; }
.pane-actions {
  display: flex;
  gap: 4px;
  justify-content: flex-end;
}
.device-card {
  display: flex;
  align-items: center;
  gap: 9px;
  width: 100%;
  padding: 8px 9px;
  text-align: left;
  border: 1px solid #e4e7ed;
  border-radius: 7px;
  background: #fff;
  cursor: pointer;
}
.device-card:hover,
.device-card.active {
  border-color: #409eff;
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.16);
}
.device-kind {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  border-radius: 8px;
  background: linear-gradient(145deg, #3b82c4, #245b94);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}
.empty-hint {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  padding: 4px 0;
}
.group-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 360px;
  overflow: auto;
}
.group-card {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.group-card:hover:not(.disabled) {
  border-color: #409eff;
}
.group-card.active {
  border-color: #409eff;
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.25);
}
.group-card.disabled {
  cursor: default;
  opacity: 0.75;
}
.meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.name {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sub {
  font-size: 11px;
  color: #909399;
}
.desc {
  font-size: 11px;
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-actions {
  display: flex;
  flex-direction: column;
  gap: 0;
  flex-shrink: 0;
}
</style>
