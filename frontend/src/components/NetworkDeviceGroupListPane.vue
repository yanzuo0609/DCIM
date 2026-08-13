<script setup lang="ts">
import { computed } from 'vue'
import TopologyGroupIcon from '@/components/TopologyGroupIcon.vue'
import type { NetworkNode } from '@/api/network'
import type { DeviceGroupMeta } from '@/components/DeviceGroupManageDialog.vue'
import { FABRIC_ROLE_OPTIONS } from '@/utils/wiringTypes'
import { nodeInGroup } from '@/utils/deviceGroups'
import { migrateSlotsFromLegacy, summarizeSlots, totalSlotCount } from '@/utils/deviceGroupSlots'
import { groupKindFromRole, groupKindLabel } from '@/utils/deviceGroupVisual'
import { setDeviceGroupDragData } from '@/utils/topologyDnd'

const props = defineProps<{
  catalog: DeviceGroupMeta[]
  nodes: NetworkNode[]
  /** 可选：用于摘要显示模型名 */
  designModels?: Array<{ id: string; name: string }>
  selectedGroup?: string | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  select: [name: string]
  create: []
  edit: [name: string]
  detail: [name: string]
  manage: []
}>()

const rows = computed(() =>
  props.catalog
    .filter((g) => g?.name)
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
    .map((g) => {
      const slots = migrateSlotsFromLegacy(g)
      const onTopo = props.nodes.filter((n) => nodeInGroup(n, g.name)).length
      const planned = totalSlotCount(slots)
      const kind = groupKindFromRole(g.role || slots[0]?.role)
      const kindLabel = groupKindLabel(g.role || slots[0]?.role)
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
    <div class="pane-actions">
      <el-button type="primary" link size="small" :disabled="disabled" @click="emit('create')">
        新建
      </el-button>
      <el-button type="primary" link size="small" :disabled="disabled" @click="emit('manage')">
        管理
      </el-button>
    </div>
    <div v-if="!rows.length" class="empty-hint">
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
        :title="disabled ? row.summary : `拖到画布放置「${row.name}」`"
        @click="emit('select', row.name)"
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
.pane-actions {
  display: flex;
  gap: 4px;
  justify-content: flex-end;
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
