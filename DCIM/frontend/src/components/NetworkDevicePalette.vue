<script setup lang="ts">
import { computed } from 'vue'
import TopologyDeviceIcon from '@/components/TopologyDeviceIcon.vue'
import {
  NODE_KIND_LABELS,
  SWITCH_SUBTYPE_LABELS,
  type NetworkNode,
  type SwitchSubtype,
} from '@/api/network'
import { TOPOLOGY_DND_MIME } from '@/utils/topologyDnd'

const props = defineProps<{
  nodes: NetworkNode[]
  selectedNodeId: string | null
  stampTemplateId?: string | null
}>()

const emit = defineEmits<{
  select: [id: string]
  dragStart: [id: string]
}>()

const pending = computed(() => props.nodes.filter((n) => n.on_canvas === false))
const placed = computed(() => props.nodes.filter((n) => n.on_canvas !== false))

function kindLabel(node: NetworkNode) {
  if (node.kind === 'switch' && node.port_layout?.switch_subtype) {
    return SWITCH_SUBTYPE_LABELS[node.port_layout.switch_subtype as SwitchSubtype] || NODE_KIND_LABELS.switch
  }
  return NODE_KIND_LABELS[node.kind]
}

function switchSubtype(node: NetworkNode): SwitchSubtype | null {
  return (node.port_layout?.switch_subtype as SwitchSubtype) || null
}

function serverFormFactor(node: NetworkNode) {
  const v = node.port_layout?.server_form_factor ?? node.port_layout?.height_u
  return v === 2 || v === 4 ? v : 1
}

function securityHeightU(node: NetworkNode) {
  return Number(node.port_layout?.height_u) >= 2 ? 2 : 1
}

function onDragStart(event: DragEvent, node: NetworkNode) {
  if (!event.dataTransfer) return
  event.dataTransfer.setData(TOPOLOGY_DND_MIME, node.id)
  event.dataTransfer.setData('text/plain', node.id)
  event.dataTransfer.effectAllowed = 'copy'
  emit('dragStart', node.id)
  emit('select', node.id)
}

function onItemClick(node: NetworkNode) {
  emit('select', node.id)
}
</script>

<template>
  <div class="device-palette">
    <div class="palette-header">设备列表</div>
    <p class="palette-hint">选中后可多次点击/拖拽画布创建带序号的设备</p>
    <div class="palette-section">
      <div class="section-title">待放置 ({{ pending.length }})</div>
      <div v-if="!pending.length" class="empty-hint">请先在「设备定义」中添加设备</div>
      <div
        v-for="node in pending"
        :key="node.id"
        class="palette-item"
        :class="{ active: selectedNodeId === node.id, stamp: stampTemplateId === node.id }"
        draggable="true"
        @dragstart="onDragStart($event, node)"
        @click="onItemClick(node)"
      >
        <TopologyDeviceIcon
          :kind="node.kind"
          :switch-subtype="switchSubtype(node)"
          :server-form-factor="serverFormFactor(node)"
          :security-height-u="securityHeightU(node)"
          :size="40"
        />
        <div class="meta">
          <div class="name">{{ node.name }}</div>
          <div class="kind">
            {{ kindLabel(node) }}
            <span v-if="stampTemplateId === node.id" class="stamp-tag">放置中</span>
          </div>
        </div>
      </div>
    </div>
    <div class="palette-section">
      <div class="section-title">已放置 ({{ placed.length }})</div>
      <div v-if="!placed.length" class="empty-hint">从上方拖入或点击画布创建</div>
      <div
        v-for="node in placed"
        :key="node.id"
        class="palette-item placed"
        :class="{ active: selectedNodeId === node.id, stamp: stampTemplateId === node.id }"
        draggable="true"
        @dragstart="onDragStart($event, node)"
        @click="onItemClick(node)"
      >
        <TopologyDeviceIcon
          :kind="node.kind"
          :switch-subtype="switchSubtype(node)"
          :server-form-factor="serverFormFactor(node)"
          :security-height-u="securityHeightU(node)"
          :size="40"
        />
        <div class="meta">
          <div class="name">{{ node.name }}</div>
          <div class="kind">
            {{ kindLabel(node) }}
            <span v-if="stampTemplateId === node.id" class="stamp-tag">放置中</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.device-palette {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  flex: 1;
  overflow: auto;
}

.palette-header {
  font-weight: 600;
  font-size: 14px;
}

.palette-hint {
  margin: 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}

.palette-item.stamp {
  border-color: #e6a23c;
  background: #fdf6ec;
}

.stamp-tag {
  margin-left: 4px;
  color: #e6a23c;
  font-weight: 600;
}

.palette-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.section-title {
  font-size: 12px;
  color: #909399;
  font-weight: 600;
}

.empty-hint {
  font-size: 12px;
  color: #c0c4cc;
  padding: 6px 4px;
}

.palette-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fff;
  cursor: grab;
  user-select: none;
}

.palette-item:hover {
  border-color: #b3d8ff;
  background: #f5f9ff;
}

.palette-item.active {
  border-color: #409eff;
  background: #ecf5ff;
}

.palette-item.placed {
  opacity: 0.92;
}

.meta {
  min-width: 0;
}

.name {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kind {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}
</style>
