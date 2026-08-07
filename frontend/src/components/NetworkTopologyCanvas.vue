<script setup lang="ts">
import { computed, ref } from 'vue'
import TopologyDeviceIcon from '@/components/TopologyDeviceIcon.vue'
import { TOPOLOGY_DND_MIME } from '@/utils/topologyDnd'
import type { NetworkLink, NetworkNode, SwitchSubtype } from '@/api/network'

const props = defineProps<{
  nodes: NetworkNode[]
  links: NetworkLink[]
  selectedNodeId: string | null
  selectedLinkId?: string | null
  linkMode: boolean
  linkSourceId?: string | null
  /** 选中模板后，点击空白处可连续创建设备 */
  stampMode?: boolean
  /** 仿真节点状态：nodeId -> running|stopped|error */
  nodeLabStatus?: Record<string, string> | null
}>()

const emit = defineEmits<{
  selectNode: [id: string | null]
  selectLink: [id: string | null]
  moveNode: [id: string, x: number, y: number]
  placeNode: [id: string, x: number, y: number]
  canvasClick: [x: number, y: number]
}>()

const ICON = 72

const dragging = ref<{ id: string; offsetX: number; offsetY: number } | null>(null)
const svgRef = ref<SVGSVGElement | null>(null)
const dropActive = ref(false)

const canvasNodes = computed(() => props.nodes.filter((n) => n.on_canvas !== false))
const nodeMap = computed(() => new Map(canvasNodes.value.map((n) => [n.id, n])))
const canvasLinks = computed(() =>
  props.links.filter(
    (l) => nodeMap.value.has(l.source_node_id) && nodeMap.value.has(l.target_node_id),
  ),
)

function nodeCenter(node: NetworkNode) {
  return { x: node.pos_x + ICON / 2, y: node.pos_y + ICON / 2 }
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

function svgPointFromEvent(event: MouseEvent | DragEvent) {
  const svg = svgRef.value
  if (!svg) return null
  const pt = svg.createSVGPoint()
  pt.x = event.clientX
  pt.y = event.clientY
  return pt.matrixTransform(svg.getScreenCTM()?.inverse())
}

function onNodeMouseDown(event: MouseEvent, node: NetworkNode) {
  event.stopPropagation()
  emit('selectLink', null)
  emit('selectNode', node.id)
  if (props.linkMode) return
  const cursor = svgPointFromEvent(event)
  if (!cursor) return
  dragging.value = {
    id: node.id,
    offsetX: cursor.x - node.pos_x,
    offsetY: cursor.y - node.pos_y,
  }
}

function onMouseMove(event: MouseEvent) {
  if (!dragging.value) return
  const cursor = svgPointFromEvent(event)
  if (!cursor) return
  emit(
    'moveNode',
    dragging.value.id,
    Math.max(0, cursor.x - dragging.value.offsetX),
    Math.max(0, cursor.y - dragging.value.offsetY),
  )
}

function onMouseUp() {
  dragging.value = null
}

function onBackgroundClick(event: MouseEvent) {
  if (props.linkMode) return
  // 点击落在设备/连线上时由自身处理
  const target = event.target as Element | null
  if (target?.closest?.('.node') || target?.closest?.('.link-hit')) return
  const cursor = svgPointFromEvent(event)
  if (!cursor) {
    emit('selectLink', null)
    emit('selectNode', null)
    return
  }
  if (props.stampMode) {
    emit('canvasClick', Math.max(0, cursor.x - ICON / 2), Math.max(0, cursor.y - ICON / 2))
    return
  }
  emit('selectLink', null)
  emit('selectNode', null)
  emit('canvasClick', cursor.x, cursor.y)
}

function onNodeClick(event: MouseEvent, node: NetworkNode) {
  event.stopPropagation()
  emit('selectLink', null)
  emit('selectNode', node.id)
}

function onLinkClick(event: MouseEvent, link: NetworkLink) {
  event.stopPropagation()
  if (props.linkMode || props.stampMode) return
  emit('selectNode', null)
  emit('selectLink', link.id)
}

function onDragOver(event: DragEvent) {
  if (!event.dataTransfer) return
  const types = Array.from(event.dataTransfer.types || [])
  if (types.includes(TOPOLOGY_DND_MIME) || types.includes('text/plain')) {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
    dropActive.value = true
  }
}

function onDragLeave() {
  dropActive.value = false
}

function onDrop(event: DragEvent) {
  event.preventDefault()
  dropActive.value = false
  const id =
    event.dataTransfer?.getData(TOPOLOGY_DND_MIME) ||
    event.dataTransfer?.getData('text/plain') ||
    ''
  if (!id) return
  const cursor = svgPointFromEvent(event)
  if (!cursor) return
  emit('placeNode', id, Math.max(0, cursor.x - ICON / 2), Math.max(0, cursor.y - ICON / 2))
}

function linkPath(link: NetworkLink) {
  const source = nodeMap.value.get(link.source_node_id)
  const target = nodeMap.value.get(link.target_node_id)
  if (!source || !target) return ''
  const s = nodeCenter(source)
  const t = nodeCenter(target)
  const mx = (s.x + t.x) / 2
  const my = (s.y + t.y) / 2
  return `M ${s.x} ${s.y} Q ${mx} ${my} ${t.x} ${t.y}`
}

function linkLabelPos(link: NetworkLink) {
  const source = nodeMap.value.get(link.source_node_id)
  const target = nodeMap.value.get(link.target_node_id)
  if (!source || !target) return { x: 0, y: 0 }
  const s = nodeCenter(source)
  const t = nodeCenter(target)
  return { x: (s.x + t.x) / 2, y: (s.y + t.y) / 2 - 8 }
}

function linkColor(linkType: string) {
  if (linkType === 'switch_switch') return '#606266'
  if (linkType === 'switch_security') return '#e6a23c'
  return '#409eff'
}
</script>

<template>
  <div
    class="canvas-wrap"
    :class="{ 'drop-active': dropActive, 'link-mode': linkMode, 'stamp-mode': stampMode && !linkMode }"
    @mousemove="onMouseMove"
    @mouseup="onMouseUp"
    @mouseleave="onMouseUp"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <svg ref="svgRef" class="canvas" @click="onBackgroundClick">
      <defs>
        <marker id="topo-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L0,6 L6,3 z" fill="#606266" />
        </marker>
      </defs>

      <g class="links">
        <g
          v-for="link in canvasLinks"
          :key="link.id"
          class="link-group"
          :class="{ selected: selectedLinkId === link.id }"
        >
          <!-- 加宽命中区域，便于点选 -->
          <path
            class="link-hit"
            :d="linkPath(link)"
            fill="none"
            stroke="transparent"
            stroke-width="14"
            @click.stop="onLinkClick($event, link)"
          />
          <path
            class="link-line"
            :d="linkPath(link)"
            fill="none"
            :stroke="selectedLinkId === link.id ? '#f56c6c' : linkColor(link.link_type)"
            :stroke-width="selectedLinkId === link.id ? 3.2 : 2.2"
            marker-end="url(#topo-arrow)"
            pointer-events="none"
          />
          <text
            :x="linkLabelPos(link).x"
            :y="linkLabelPos(link).y"
            class="link-label"
            text-anchor="middle"
            @click.stop="onLinkClick($event, link)"
          >
            {{ link.label || `${link.source_port} → ${link.target_port}` }}
          </text>
        </g>
      </g>

      <g class="nodes">
        <g
          v-for="node in canvasNodes"
          :key="node.id"
          class="node"
          :class="{
            selected: selectedNodeId === node.id,
            'link-source': linkSourceId === node.id,
            'link-target': linkMode,
          }"
          :transform="`translate(${node.pos_x}, ${node.pos_y})`"
          @mousedown="onNodeMouseDown($event, node)"
          @click.stop="onNodeClick($event, node)"
        >
          <foreignObject :width="ICON" :height="ICON">
            <div xmlns="http://www.w3.org/1999/xhtml" class="icon-host">
              <TopologyDeviceIcon
                :kind="node.kind"
                :switch-subtype="switchSubtype(node)"
                :server-form-factor="serverFormFactor(node)"
                :security-height-u="securityHeightU(node)"
                :size="ICON"
                :selected="selectedNodeId === node.id || linkSourceId === node.id"
              />
            </div>
          </foreignObject>
          <text :x="ICON / 2" :y="ICON + 14" text-anchor="middle" class="node-name">
            {{ node.name }}
          </text>
          <text
            v-if="node.device_group"
            :x="ICON / 2"
            :y="ICON + 28"
            text-anchor="middle"
            class="node-group"
          >
            {{ node.device_group }}
          </text>
          <circle
            v-if="nodeLabStatus?.[node.id]"
            :cx="ICON - 6"
            :cy="8"
            r="5"
            class="lab-dot"
            :class="`lab-${nodeLabStatus[node.id]}`"
          />
        </g>
      </g>
    </svg>
    <div v-if="!canvasNodes.length" class="canvas-empty">
      {{ stampMode ? '点击画布连续放置选中模型' : '从左侧模型库选择模型后点击画布放置' }}
    </div>
  </div>
</template>

<style scoped>
.canvas-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: auto;
  background:
    linear-gradient(#e8edf3 1px, transparent 1px) 0 0 / 24px 24px,
    linear-gradient(90deg, #e8edf3 1px, transparent 1px) 0 0 / 24px 24px,
    #f4f7fb;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
}

.canvas-wrap.drop-active {
  outline: 2px dashed #409eff;
  outline-offset: -2px;
}

.canvas-wrap.link-mode {
  cursor: crosshair;
}

.canvas-wrap.stamp-mode {
  cursor: copy;
}

.canvas {
  width: 1800px;
  height: 1200px;
  display: block;
}

.node {
  cursor: grab;
}

.node.link-target {
  cursor: crosshair;
}

.node-name {
  fill: #303133;
  font-size: 12px;
  font-weight: 600;
  pointer-events: none;
}

.node-group {
  fill: #909399;
  font-size: 10px;
  pointer-events: none;
}

.icon-host {
  width: 72px;
  height: 72px;
  line-height: 0;
}

.link-hit {
  cursor: pointer;
}

.link-label {
  fill: #606266;
  font-size: 11px;
  cursor: pointer;
  pointer-events: auto;
}

.link-group.selected .link-label {
  fill: #f56c6c;
  font-weight: 600;
}

.canvas-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  font-size: 14px;
  pointer-events: none;
}

.lab-dot {
  stroke: #fff;
  stroke-width: 1.5;
}
.lab-dot.lab-running {
  fill: #67c23a;
}
.lab-dot.lab-stopped {
  fill: #909399;
}
.lab-dot.lab-error {
  fill: #f56c6c;
}
</style>
